import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta

from intelligence import (
    ROOT, BUDGET, GPU_ORDER, gpu_key, performance_score,
    required_discount, load_json, load_catalog, load_anchors, now_jst, iso,
    parse_dt, actionable_max_age_minutes, configuration_readiness
)
from sale_calendar import campaign_window_for_item

JST=timezone(timedelta(hours=9))
TARGET=datetime(2026,11,27,tzinfo=JST)

HISTORY=[
  {"date":"2025-11-19","label":"Amazon surprise/pre-sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-21","label":"Amazon early sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-22","label":"ROG Strix G16 RTX 5070 Ti 32GB/1TB observed at ¥299,800","price":299800,"source":"https://note.com/utopia_pc/n/nf617ebb9eec3"},
  {"date":"2025-11-24","label":"Amazon main Black Friday begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-24","label":"TUF Gaming A16 RTX 5070 32GB/1TB observed at ¥219,800","price":219800,"source":"https://pc.watch.impress.co.jp/docs/news/todays_sales/2067328.html"},
  {"date":"2025-11-30","label":"TUF Gaming A16 RTX 5070 32GB/1TB still observed at ¥219,800","price":219800,"source":"https://ascii.jp/elem/000/004/356/4356081/"},
  {"date":"2025-11-14","label":"Lenovo Black Friday campaign begins","source":"https://www.lenovo.com/jp/ja/campaigns/black-friday/"}
]

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_events():
    path=os.path.join(ROOT,"data","change_events.jsonl")
    events=[]
    if not os.path.exists(path):
        return events
    with open(path,encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events

def dynamic_change_timing(events):
    hours=Counter()
    dates=Counter()
    price_changes=[]
    for e in events:
        old=e.get("old_price_jpy")
        new=e.get("new_price_jpy")
        if old is None or new is None or old==new:
            continue
        if e.get("pit_valid") is not True:
            continue
        ts=e.get("observed_at") or e.get("retrieval_time")
        if not ts:
            continue
        try:
            dt=datetime.fromisoformat(str(ts).replace("Z","+00:00")).astimezone(JST)
        except Exception:
            continue
        hours[dt.hour]+=1
        dates[dt.strftime("%m-%d")]+=1
        price_changes.append({
            "id":e.get("id"),
            "observed_at":ts,
            "old_price_jpy":old,
            "new_price_jpy":new,
            "delta_jpy":new-old,
            "url":e.get("url"),
            "name":e.get("name"),
            "source_mode":e.get("price_source_mode"),
        })
    price_changes.sort(key=lambda x:x["observed_at"])
    return {
        "sample_size":len(price_changes),
        "hourly_counts":dict(sorted(hours.items())),
        "date_counts":dict(sorted(dates.items())),
        "top_hours":hours.most_common(8),
        "recent_changes":price_changes[-50:],
    }


def _is_positive_yen(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _event_dt(event):
    return parse_dt(event.get("observed_at") or event.get("retrieval_time"))



def read_buy_now_observations(start=None, end=None):
    """Read only observations inside the requested window; avoid replaying old season data."""
    path = os.path.join(ROOT, "data", "buy_now_observations.jsonl")
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            observed = parse_dt(row.get("observed_at"))
            if not observed or (start and observed < start) or (end and observed > end):
                continue
            rows.append(row)
    return rows


def append_buy_now_observations(latest, config, now=None):
    """Persist timestamped, SKU-verified prices in the provisional broad watch window."""
    now = now or now_jst()
    start = parse_dt(config.get("monitor_window_start"))
    end = parse_dt(config.get("monitor_window_end"))
    if not start or not end or not (start <= now <= end):
        return 0

    path = os.path.join(ROOT, "data", "buy_now_observations.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    count = 0
    with open(path, "a", encoding="utf-8") as f:
        for item in latest.get("products") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            price = item.get("current_price_jpy")
            stock = item.get("stock_status")
            available = parse_dt(item.get("available_at"))
            retrieved = parse_dt(item.get("retrieval_time"))
            valid = bool(
                _is_positive_yen(price)
                and stock in ("in_stock", "low_stock")
                and item.get("price_source_mode") == "direct_structured"
                and item.get("price_validation_status") in (
                    "validated", "validated_exact_model_page"
                )
                and item.get("variant_match") in ("exact", "trusted_url", "strong")
                and available and retrieved and start <= retrieved <= end
                and available <= retrieved <= now
            )
            if not valid:
                continue
            observation = {
                "id": str(item.get("id")),
                "name": item.get("name") or item.get("catalog_name"),
                "url": item.get("url"),
                "observed_at": iso(retrieved),
                "available_at": iso(available),
                "retrieval_time": iso(retrieved),
                "price_jpy": int(price),
                "stock_status": stock,
                "price_source_mode": item.get("price_source_mode"),
                "price_validation_status": item.get("price_validation_status"),
                "variant_match": item.get("variant_match"),
                "pit_valid": True,
            }
            f.write(json.dumps(observation, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def _window_observations(events, item, start, end, include_current, price_observations=None):
    product_id = str(item.get("id") or "")
    observations = []
    for event in events:
        if str(event.get("id") or "") != product_id or event.get("pit_valid") is not True:
            continue
        if event.get("price_source_mode") != "direct_structured":
            continue
        if event.get("price_validation_status") not in ("validated", "validated_exact_model_page"):
            continue
        dt = _event_dt(event)
        price = event.get("new_price_jpy")
        if (
            dt and start <= dt <= end and _is_positive_yen(price)
            and event.get("new_stock_status") in ("in_stock", "low_stock")
        ):
            observations.append({
                "price_jpy": price,
                "at": iso(dt),
                "source": "price_change_event",
            })
    for observation in price_observations or []:
        if str(observation.get("id") or "") != product_id or observation.get("pit_valid") is not True:
            continue
        dt = parse_dt(observation.get("observed_at"))
        price = observation.get("price_jpy")
        if (
            dt and start <= dt <= end and _is_positive_yen(price)
            and observation.get("price_source_mode") == "direct_structured"
            and observation.get("price_validation_status") in ("validated", "validated_exact_model_page")
            and observation.get("variant_match") in ("exact", "trusted_url", "strong")
            and observation.get("stock_status") in ("in_stock", "low_stock")
        ):
            observations.append({
                "price_jpy": price,
                "at": iso(dt),
                "source": "verified_window_observation",
            })
    if include_current:
        dt = parse_dt(item.get("retrieval_time"))
        price = item.get("current_price_jpy")
        if (
            dt and start <= dt <= end and _is_positive_yen(price)
            and item.get("price_source_mode") == "direct_structured"
            and item.get("price_validation_status") in ("validated", "validated_exact_model_page")
            and item.get("variant_match") in ("exact", "trusted_url", "strong")
            and item.get("stock_status") in ("in_stock", "low_stock")
        ):
            observations.append({
                "price_jpy": price,
                "at": iso(dt),
                "source": "current_verified_snapshot",
            })
    deduped = {(x["price_jpy"], x["at"]): x for x in observations}
    return sorted(deduped.values(), key=lambda x: x["at"])


def _window_price_movement(events, candidate_id, start, end):
    changes = []
    for event in events:
        if str(event.get("id") or "") != str(candidate_id) or event.get("pit_valid") is not True:
            continue
        if event.get("price_source_mode") != "direct_structured":
            continue
        if event.get("price_validation_status") not in ("validated", "validated_exact_model_page"):
            continue
        dt = _event_dt(event)
        old_price = event.get("old_price_jpy")
        new_price = event.get("new_price_jpy")
        if not dt or not start <= dt <= end:
            continue
        if not (_is_positive_yen(old_price) and _is_positive_yen(new_price)) or old_price == new_price:
            continue
        changes.append({"at": iso(dt), "delta_jpy": new_price - old_price})
    changes.sort(key=lambda x: x["at"])
    if len(changes) < 3:
        label = "変更履歴不足（値下がり確率は推定しない）"
    else:
        down = sum(1 for x in changes if x["delta_jpy"] < 0)
        up = sum(1 for x in changes if x["delta_jpy"] > 0)
        if changes[-1]["delta_jpy"] > 0 or up > down:
            label = "値上がり・値戻りを警戒"
        elif down / len(changes) >= 0.67:
            label = "観測上は値下がり傾向"
        else:
            label = "方向性は不明"
    return {
        "change_count": len(changes),
        "label": label,
        "recent_changes": changes[-5:],
    }


def _valid_component_observation(row, now=None):
    if not isinstance(row, dict):
        return False
    price = row.get("market_reference_price_jpy")
    available = parse_dt(row.get("available_at"))
    retrieved = parse_dt(row.get("retrieval_time"))
    now = now or now_jst()
    source_role = row.get("source_role")
    validation_status = row.get("price_validation_status")
    source_status_valid = (
        source_role == "comparison_site_reference" and validation_status == "verified_market_reference"
    ) or (
        source_role == "direct_retailer_listing_reference"
        and validation_status == "verified_retailer_listing_reference"
        and row.get("stock_signal") == "in_stock"
    )
    return bool(
        _is_positive_yen(price)
        and source_status_valid
        and row.get("identity_match") is True
        and row.get("pit_valid") is True
        and row.get("bf_actual_authorized") is False
        and available and retrieved and available <= retrieved <= now
    )


def build_component_timing_rows(components, observations=None, watch_config=None, now=None):
    """Expose component-level reference-vs-target gaps without issuing buy-now claims."""
    now = now or now_jst()
    observations = observations or []
    watch_config = watch_config or {}
    window_start = parse_dt(watch_config.get("monitor_window_start"))
    window_end = parse_dt(watch_config.get("monitor_window_end"))
    history_by_id = {}
    for row in observations:
        if not _valid_component_observation(row, now):
            continue
        cid = str(row.get("id") or "")
        if not cid:
            continue
        stamp = parse_dt(row.get("retrieval_time"))
        history_by_id.setdefault(cid, []).append((stamp, row))
    for values in history_by_id.values():
        values.sort(key=lambda item: item[0])

    output = []
    for part in components:
        cid = str(part.get("id") or "")
        valid_history = history_by_id.get(cid, [])
        live_price = part.get("market_reference_price_jpy")
        live_trusted = bool(
            part.get("trusted_for_market_estimate") is True
            and _is_positive_yen(live_price)
        )
        display_only_price = part.get("display_reference_price_jpy")
        display_only_reference = bool(
            not live_trusted
            and part.get("price_status") == "search_snippet_reference_only"
            and _is_positive_yen(display_only_price)
            and part.get("source_role") == "comparison_site_reference"
        )
        target = part.get("target_price_jpy")
        if not live_trusted:
            live_price = None
            if display_only_reference:
                status, label = "DISPLAY_ONLY_SEARCH_REFERENCE", "検索ページ表示値のみ（検証価格なし）"
            else:
                status = "REFERENCE_UNVERIFIED" if part.get("track_price") else "MANUAL_REFERENCE_ONLY"
                label = "参考価格未確認" if part.get("track_price") else "手動参考値・未追跡"
            gap = None
            drop_pct = None
        else:
            gap = max(0, int(live_price) - int(target)) if isinstance(target, int) else None
            drop_pct = round((gap / live_price) * 100, 1) if gap is not None and live_price else None
            if gap == 0:
                status, label = "TARGET_LEVEL_REFERENCE_ONLY", "目標水準以下の比較参考値（実売未確認）"
            elif drop_pct is not None and drop_pct <= 3:
                status, label = "NEAR_TARGET_REFERENCE_ONLY", "目標に近い比較参考値（実売未確認）"
            else:
                status, label = "WAIT_FOR_TARGET", "目標まで値下がり待ち"
        low = min((int(row["market_reference_price_jpy"]) for _, row in valid_history), default=None)
        window_values = [
            (stamp, row) for stamp, row in valid_history
            if window_start and window_end and window_start <= stamp <= window_end
        ]
        window_low = min((int(row["market_reference_price_jpy"]) for _, row in window_values), default=None)
        last_at = valid_history[-1][0].isoformat() if valid_history else None
        purchase_url = part.get("purchase_url") or part.get("monitor_url")
        output.append({
            "id": cid, "name": part.get("name"), "category": part.get("category"),
            "model_code": part.get("model_code"), "target_price_jpy": target,
            "current_market_reference_price_jpy": live_price,
            "current_reference_status": part.get("price_status") or "not_observed",
            "reference_age_minutes": part.get("reference_age_minutes"),
            "display_only_reference_price_jpy": display_only_price if display_only_reference else None,
            "display_only_reference_url": part.get("search_snippet_reference_url") if display_only_reference else None,
            "display_only_reference_title": part.get("search_snippet_reference_title") if display_only_reference else None,
            "display_only_reference_is_estimate_eligible": False,
            "target_gap_jpy": gap, "required_drop_pct": drop_pct,
            "history_low_reference_price_jpy": low,
            "history_sample_count": len(valid_history),
            "history_latest_at": last_at,
            "watch_window_low_reference_price_jpy": window_low,
            "watch_window_sample_count": len(window_values),
            "reference_source_url": part.get("reference_source_url"),
            "reference_source_role": part.get("source_role"),
            "reference_source_label": part.get("reference_source_label"),
            "status": status, "status_label": label,
            "purchase_allowed": False, "bf_actual_authorized": False,
            "purchase_url": purchase_url,
        })
    return output


def build_self_build_timing_summary(build_plan, build_config=None, component_observations=None, watch_config=None, now=None):
    """Summarize DIY-first selection without treating target/reference prices as checkout offers."""
    build_plan = build_plan if isinstance(build_plan, dict) else {}
    build_config = build_config if isinstance(build_config, dict) else {}
    profile = build_config.get("profile") if isinstance(build_config.get("profile"), dict) else {}
    builds = [x for x in (build_plan.get("builds") or []) if isinstance(x, dict)]
    wanted_gpu = profile.get("primary_gpu_choice_id")
    chosen = next((x for x in builds if x.get("gpu_choice_id") == wanted_gpu), None)
    if chosen is None:
        chosen = next((x for x in builds if x.get("rank") == 1), None)
    policy = build_plan.get("purchase_method_policy") or {}
    if component_observations is None:
        observation_path = os.path.join(ROOT, "data", "build_component_observations.jsonl")
        component_observations = []
        try:
            with open(observation_path, encoding="utf-8") as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict):
                            component_observations.append(item)
                    except (TypeError, ValueError):
                        continue
        except OSError:
            pass
    if watch_config is None:
        watch_config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    timing_now = now or now_jst()
    if not chosen:
        return {
            "primary_method": "SELF_BUILD",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 0,
            "status": "SELF_BUILD_DATA_UNAVAILABLE",
            "purchase_allowed": False, "bf_actual_authorized": False,
            "blockers": ["data/self_build_plan.json と config/build_components.json を確認する"],
            "target_pc_total_jpy": None, "target_all_in_jpy": None,
            "market_reference_estimate_jpy": None,
            "tracked_component_count": 0, "verified_market_reference_count": 0,
            "verified_checkout_offer_count": 0,
        }

    components = [x for x in (chosen.get("components") or []) if isinstance(x, dict)]
    component_timing = build_component_timing_rows(components, component_observations, watch_config, timing_now)
    tracked = [x for x in components if x.get("track_price")]
    reference_count = sum(1 for x in tracked
        if x.get("trusted_for_market_estimate") is True
        and _is_positive_yen(x.get("market_reference_price_jpy")))
    display_only_reference_count = sum(1 for x in tracked
        if x.get("price_status") == "search_snippet_reference_only"
        and _is_positive_yen(x.get("display_reference_price_jpy"))
        and x.get("source_role") == "comparison_site_reference")
    checkout_count = sum(1 for x in components
        if x.get("source_role") == "retailer_checkout_offer"
        and x.get("checkout_price_verified") is True
        and _is_positive_yen(x.get("checkout_price_jpy")))
    target_pc, target_all = chosen.get("target_pc_total_jpy"), chosen.get("target_all_in_jpy")
    total_budget, pc_budget = build_plan.get("total_budget_jpy"), build_plan.get("pc_budget_jpy")
    remaining = total_budget - target_all if isinstance(total_budget, int) and isinstance(target_all, int) else None
    missing_ids = list(chosen.get("missing_or_untrusted_market_reference_ids") or [])
    compatibility = chosen.get("compatibility_status") or "REVIEW"
    blockers = [
        "BF購入目標額は希望価格であり、確認済み実売価格ではない。",
        "比較サイト価格は購入店舗の最終決済価格・在庫・送料を証明しない。",
    ]
    if compatibility == "FAIL":
        status = "BLOCKED_COMPATIBILITY"
        blockers.insert(0, "互換性チェックにFAILがある。該当パーツを修正するまで購入不可。")
    elif compatibility == "REVIEW":
        status = "WAIT_FOR_COMPATIBILITY_REVIEW"
        blockers.insert(0, "GPUの正確な型番寸法・補助電源など未確認の互換性項目を解消する。")
    elif isinstance(target_pc, int) and isinstance(pc_budget, int) and target_pc > pc_budget:
        status = "OVER_BUDGET_TARGET"
        blockers.insert(0, "PC本体の購入目標がPC予算を超過している。")
    elif isinstance(target_all, int) and isinstance(total_budget, int) and target_all > total_budget:
        status = "OVER_BUDGET_TARGET"
        blockers.insert(0, "周辺機器込みの購入目標が総予算を超過している。")
    elif reference_count < len(tracked):
        status = "WAIT_FOR_COMPONENT_REFERENCES"
        blockers.insert(0, "比較参考価格の確認が完了していない部品がある: " + (", ".join(missing_ids) or "未確認の部品"))
    elif checkout_count < len(components):
        status = "WAIT_FOR_OFFICIAL_COMPONENT_OFFERS"
        blockers.insert(0, "全構成部品の購入店舗・公式セール期間・在庫・送料込み決済価格がそろっていない。")
    else:
        status = "WAIT_FOR_FINAL_COMPATIBILITY_AND_BUDGET_GATE"
        blockers.insert(0, "全パーツを同じ完成構成として最終互換性・送料込み総額で再検証する。")

    return {
        "primary_method": "SELF_BUILD",
        "assembly_time_is_constraint": bool(policy.get("assembly_time_is_constraint", False)),
        "assembly_time_penalty_points": int(policy.get("assembly_time_penalty_points", 0) or 0),
        "bto_role": "REFERENCE_BENCHMARK_ONLY",
        "selected_build_id": chosen.get("id"), "selected_build_name": chosen.get("name"),
        "gpu_choice_id": chosen.get("gpu_choice_id"),
        "status": status, "label": "自作PC本命：部品価格・購入条件の確認継続",
        "purchase_allowed": False, "bf_actual_authorized": False,
        "compatibility_status": compatibility,
        "target_parts_subtotal_jpy": chosen.get("target_parts_subtotal_jpy"),
        "target_pc_total_jpy": target_pc, "target_all_in_jpy": target_all,
        "total_budget_jpy": total_budget, "target_remaining_budget_jpy": remaining,
        "target_within_total_budget": chosen.get("target_within_total_budget") is True,
        "market_reference_estimate_jpy": chosen.get("market_reference_estimate_jpy"),
        "market_reference_all_in_estimate_jpy": chosen.get("market_reference_all_in_estimate_jpy"),
        "market_reference_estimate_is_checkout_price": False,
        "tracked_component_count": len(tracked),
        "verified_market_reference_count": reference_count,
        "display_only_search_reference_count": display_only_reference_count,
        "component_count": len(components), "verified_checkout_offer_count": checkout_count,
        "missing_or_untrusted_market_reference_ids": missing_ids,
        "component_timing": component_timing,
        "component_timing_policy": "確認済み比較参考値・保存済み履歴と、検索結果ページの表示専用参考値を別々に示す。表示専用参考値は価格目標との差・市場推定・購入判定に使用しない。最終決済額・送料・BF実売確定ではなく、買い許可は出さない。",
        "blockers": blockers,
        "purchase_decision_factors": profile.get("purchase_decision_factors") or [],
    }


def build_buy_now_decision(rankings, events, config, price_observations=None, official_campaign_dates=None):
    """Separate provisional observation coverage from source-verified seller campaign windows."""
    now = now_jst()
    start = parse_dt(config.get("monitor_window_start")) or datetime(now.year, 11, 1, tzinfo=JST)
    end = parse_dt(config.get("monitor_window_end")) or datetime(now.year, 12, 11, 23, 59, 59, tzinfo=JST)
    in_window = start <= now <= end
    phase = "PRE_WATCH_WINDOW" if now < start else "POST_WATCH_WINDOW" if now > end else "PROVISIONAL_BROAD_WATCH_WINDOW"
    max_age = actionable_max_age_minutes(now)

    total_budget = rankings.get("total_budget_jpy")
    pc_target = rankings.get("pc_target_jpy")
    pc_cap = rankings.get("dynamic_pc_cap_jpy")
    peripheral_cost = rankings.get("peripheral_projection_jpy")
    budget_ready = rankings.get("peripheral_budget_data_ready") is True
    gate = rankings.get("purchase_gate") or {}
    method_policy = rankings.get("purchase_method_policy") or {}
    self_build_primary = method_policy.get("primary_method") == "SELF_BUILD"
    # Never let a BTO benchmark authorize a purchase when DIY is the primary method.
    gate_allowed = gate.get("allowed") is True and not self_build_primary
    coverage_complete = gate.get("coverage_status") == "COMPLETE"

    rows = []
    cap = None
    source_products = (rankings.get("products") or []) + (rankings.get("unavailable_products") or [])
    seen_ids = set()
    for item in source_products:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if str(item.get("id") or "") in seen_ids:
            continue
        seen_ids.add(str(item.get("id") or ""))
        detail = item.get("score_detail") or {}
        price = item.get("current_price_jpy")
        cash_cost = item.get("cash_total_cost_jpy")
        if not _is_positive_yen(cash_cost):
            cash_cost = price if _is_positive_yen(price) else None

        retrieved = parse_dt(item.get("retrieval_time"))
        available = parse_dt(item.get("available_at"))
        predicted = parse_dt(item.get("prediction_time") or rankings.get("prediction_time") or rankings.get("generated_at"))
        age_minutes = (now - retrieved).total_seconds() / 60 if retrieved else None
        fresh = age_minutes is not None and 0 <= age_minutes <= max_age
        pit_ok = bool(
            item.get("pit_valid") is True and available and retrieved and predicted
            and available <= retrieved <= predicted and predicted <= now
        )
        sku_ok = item.get("variant_match") in ("exact", "trusted_url", "strong")
        source_ok = bool(
            item.get("price_source_mode") == "direct_structured"
            and item.get("price_validation_status") in (
                "validated", "validated_exact_model_page", "anomaly_corroborated"
            )
            and _is_positive_yen(price) and sku_ok
        )
        campaign = campaign_window_for_item(item, now, config, official_campaign_dates)
        current_is_watch_window = bool(retrieved and start <= retrieved <= end)
        retailer_dates_confirmed = bool(
            campaign.get("date_status") in ("CONFIRMED", "CONFIRMED_MANUAL")
            and campaign.get("start_jst") and campaign.get("end_jst")
        )
        retailer_campaign_active_now = bool(campaign.get("active_now"))
        official_sale_active = bool(campaign.get("active_at_observation"))
        price_verified = bool(
            in_window and current_is_watch_window and official_sale_active
            and source_ok and fresh and pit_ok
        )

        config_ready = detail.get("configuration_ready") is True
        config_reasons = detail.get("configuration_reasons") or []
        if not config_ready:
            computed_ready, computed_reasons = configuration_readiness(item)
            config_ready = bool(computed_ready)
            if not config_reasons:
                config_reasons = computed_reasons
        stock = item.get("stock_status") or "unknown"
        stock_available = stock in ("in_stock", "low_stock")
        score_status = str(detail.get("status") or "UNCONFIRMED")
        wait_risk = detail.get("wait_risk") or "UNKNOWN"

        try:
            cap = int(pc_cap) if pc_cap is not None else None
        except (TypeError, ValueError):
            cap = None
        try:
            all_in_budget = int(total_budget) if total_budget is not None else None
        except (TypeError, ValueError):
            all_in_budget = None
        try:
            accessories = int(peripheral_cost) if peripheral_cost is not None else None
        except (TypeError, ValueError):
            accessories = None
        estimated_all_in = cash_cost + accessories if isinstance(cash_cost, int) and accessories is not None else None
        within_cap = bool(
            budget_ready and cap is not None and isinstance(cash_cost, int) and cash_cost <= cap
        )
        within_total = bool(
            budget_ready and all_in_budget is not None and estimated_all_in is not None
            and estimated_all_in <= all_in_budget
        )

        # Window history is useful for trend comparisons even before a seller's
        # campaign dates are confirmed. It is explicitly a watch-window low,
        # not a claim that the seller's official Black Friday sale was active.
        observations = _window_observations(
            events, item, start, end,
            bool(source_ok and fresh and pit_ok and stock in ("in_stock", "low_stock")),
            price_observations,
        ) if in_window else []
        observed_prices = [x["price_jpy"] for x in observations]
        sale_low = min(observed_prices) if observed_prices else None
        sale_low_observation = next((x for x in observations if x.get("price_jpy") == sale_low), None)
        sale_low_at = sale_low_observation.get("at") if sale_low_observation else None
        low_is_comparable = len(observations) >= 2
        gap_from_low_pct = (
            round((price / sale_low - 1) * 100, 2)
            if price_verified and sale_low and low_is_comparable else None
        )
        movement = _window_price_movement(events, item.get("id"), start, end) if in_window else {
            "change_count": 0, "label": "監視窓外", "recent_changes": []
        }

        timing_score = None
        if in_window and price_verified:
            score = 0
            target = int(pc_target) if pc_target is not None else None
            if target is not None and price <= target:
                score += 35
            elif cap is not None and price <= cap:
                score += 25
            elif cap and price <= int(cap * 1.05):
                score += 10
            if low_is_comparable and gap_from_low_pct is not None:
                score += 20 if gap_from_low_pct <= 0.5 else 14 if gap_from_low_pct <= 2 else 6 if gap_from_low_pct <= 5 else 0
            score += 12 if stock == "low_stock" else 4 if stock == "in_stock" else 0
            if movement["label"] == "値上がり・値戻りを警戒":
                score += 8
            elif movement["label"] == "観測上は値下がり傾向":
                score -= 5
            hours_left = max(0, (end - now).total_seconds() / 3600)
            score += 8 if hours_left <= 48 else 4 if hours_left <= 168 else 0
            # Raw component maximum is 83; normalize to a true 0-100 comparison scale.
            timing_score = int(round(max(0, min(83, score)) * 100 / 83))

        blockers = []
        if not in_window:
            blockers.append("暫定の広域監視窓外。現行価格はBF実売として扱わない")
        elif not current_is_watch_window:
            blockers.append("商品価格の観測時刻が暫定の広域監視窓内ではない")
        if in_window and not retailer_dates_confirmed:
            retailer = campaign.get("retailer_key") or "販売店未特定"
            blockers.append(retailer + "の2026年公式セール日程が未確認。暫定監視窓だけではBF実売として認定しない")
        elif in_window and not retailer_campaign_active_now:
            blockers.append("販売店の2026年公式日程は確認済みですが、現在はその公式開催期間外です")
        elif in_window and not official_sale_active:
            blockers.append("販売店の公式開催期間は現在有効ですが、価格観測時刻がその公式期間内ではありません。最新価格を取り直す必要があります")
        if not source_ok:
            blockers.append("直接取得価格・SKU一致・価格検証の条件未達")
        if not fresh:
            blockers.append("価格観測が古いか取得時刻が未確認")
        if not pit_ok:
            blockers.append("PIT未通過（available_at ≤ retrieval_time ≤ prediction_time が必要）")
        if not stock_available:
            blockers.append("在庫が確認できない、または売り切れ")
        if not config_ready:
            blockers.extend(config_reasons or ["RAM 32GB / SSD 1TB以上の完成構成が未確認"])
        if not budget_ready:
            blockers.append("周辺機器の価格・在庫が揃わず、本体動的上限が確定していない")
        if budget_ready and not within_cap and isinstance(cash_cost, int) and cap is not None:
            blockers.append("PC本体が動的上限を ¥{:,} 超過".format(max(0, cash_cost - cap)))
        if budget_ready and not within_total:
            blockers.append("PC＋周辺機器の現金総額が総予算内と確認できない")
        if score_status not in ("BUY_NOW", "BUY_NOW_NEAR_BUDGET", "BUY_NOW_LOW_STOCK"):
            blockers.append("既存ランキングの判定は " + score_status)
        if not coverage_complete:
            blockers.append("重要候補の価格・在庫カバレッジが未完了")
        if not gate_allowed:
            blockers.append("既存の全体購入ゲートが保留")

        individual_ok = bool(
            in_window and price_verified and stock_available and config_ready
            and within_cap and within_total
            and score_status in ("BUY_NOW", "BUY_NOW_NEAR_BUDGET", "BUY_NOW_LOW_STOCK")
        )
        qualified = bool(individual_ok and budget_ready and coverage_complete and gate_allowed)

        if not in_window:
            status = "PRE_BF_REFERENCE_ONLY" if now < start else "SALE_WINDOW_CLOSED"
        elif stock == "out_of_stock":
            status = "OUT_OF_STOCK"
        elif not retailer_dates_confirmed:
            status = "WAIT_FOR_OFFICIAL_DATES"
        elif not retailer_campaign_active_now:
            status = "WAIT_FOR_CAMPAIGN_WINDOW"
        elif not official_sale_active or not price_verified:
            status = "VERIFY_PRICE_OR_PIT"
        elif not stock_available:
            status = "STOCK_UNCONFIRMED"
        elif not config_ready:
            status = "NEEDS_CONFIGURATION"
        elif not budget_ready or not coverage_complete or not gate_allowed:
            status = "PURCHASE_GATE_BLOCKED"
        elif not within_cap or not within_total:
            status = "WAIT_FOR_DISCOUNT"
        elif score_status not in ("BUY_NOW", "BUY_NOW_NEAR_BUDGET", "BUY_NOW_LOW_STOCK"):
            status = "WAIT_FOR_TIMING_SIGNAL"
        else:
            status = "BUY_NOW"

        rows.append({
            "id": str(item.get("id")),
            "name": item.get("name") or item.get("catalog_name") or str(item.get("id")),
            "form_factor": item.get("form_factor") or "unknown",
            "price_jpy": price if price_verified else None,
            "pre_bf_reference_price_jpy": price if price is not None and retrieved and retrieved < start else None,
            "post_bf_reference_price_jpy": price if price is not None and retrieved and retrieved > end else None,
            "watch_window_observed_price_jpy": (
                price if price is not None and current_is_watch_window and source_ok and fresh and pit_ok else None
            ),
            "retailer_key": campaign.get("retailer_key"),
            "retailer_campaign_status": campaign.get("status"),
            "retailer_campaign_date_status": campaign.get("date_status"),
            "retailer_campaign_dates_confirmed": retailer_dates_confirmed,
            "retailer_campaign_start_jst": campaign.get("start_jst"),
            "retailer_campaign_end_jst": campaign.get("end_jst"),
            "retailer_campaign_source_url": campaign.get("source_url"),
            "retailer_campaign_active": retailer_campaign_active_now,
            "retailer_campaign_active_at_observation": official_sale_active,
            "reference_price_phase": (
                "PRE_BF_REFERENCE" if price is not None and retrieved and retrieved < start else
                "POST_BF_REFERENCE" if price is not None and retrieved and retrieved > end else
                "OFFICIAL_CAMPAIGN_STALE_OR_EXPIRED" if price is not None and official_sale_active and not price_verified else
                "PROVISIONAL_WATCH_WINDOW_REFERENCE" if price is not None and current_is_watch_window and not official_sale_active else
                "UNVERIFIED_REFERENCE" if price is not None and not price_verified else None
            ),
            "cash_total_cost_jpy": cash_cost,
            "estimated_all_in_jpy": estimated_all_in,
            "pc_dynamic_cap_jpy": cap,
            "gap_to_pc_cap_jpy": max(0, cash_cost - cap) if isinstance(cash_cost, int) and cap is not None else None,
            "stock_status": stock,
            "wait_risk": wait_risk,
            "configuration_ready": config_ready,
            "configuration_reasons": config_reasons,
            "price_verified_for_bf": price_verified,
            "price_age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
            "pit_valid": pit_ok,
            "variant_match": item.get("variant_match"),
            "price_source_mode": item.get("price_source_mode"),
            "ranking_score_100": item.get("decision_score"),
            "timing_score_100": timing_score,
            "ranking_status": score_status,
            "status": status,
            "qualified_to_buy": qualified,
            "watch_window_low_observed_jpy": sale_low,
            "watch_window_low_observed_at": sale_low_at,
            "watch_window_price_observation_count": len(observations),
            "watch_window_low_is_comparable": low_is_comparable,
            "gap_from_watch_window_low_pct": gap_from_low_pct,
            "price_movement": movement,
            "purchase_url": item.get("purchase_url") if str(item.get("purchase_url") or "").startswith(("https://", "http://")) else None,
            "blockers": list(dict.fromkeys(blockers)),
        })

    rows.sort(key=lambda x: (
        x.get("timing_score_100") is None,
        -(x.get("timing_score_100") or 0),
        -(x.get("ranking_score_100") or 0),
        x.get("gap_to_pc_cap_jpy") if x.get("gap_to_pc_cap_jpy") is not None else 10**12,
    ))
    qualified = [x for x in rows if x.get("qualified_to_buy")]
    urgent_blocked = [
        x for x in rows if x.get("price_verified_for_bf")
        and x.get("configuration_ready") and x.get("stock_status") == "low_stock"
        and x.get("gap_to_pc_cap_jpy", 1) == 0 and not x.get("qualified_to_buy")
    ]
    over_budget = [
        x for x in rows if budget_ready and x.get("price_verified_for_bf") and x.get("configuration_ready")
        and x.get("stock_status") in ("in_stock", "low_stock")
        and isinstance(x.get("cash_total_cost_jpy"), int) and cap is not None
        and x["cash_total_cost_jpy"] > int(cap)
    ]
    over_budget.sort(key=lambda x: (
        x["cash_total_cost_jpy"] - int(cap), -(x.get("ranking_score_100") or 0)
    ))

    chosen = None
    any_official_campaign_active = any(x.get("retailer_campaign_active") for x in rows)
    any_campaign_dates_confirmed = any(x.get("retailer_campaign_dates_confirmed") for x in rows)
    if now < start:
        status, label = "PRE_BF_MONITORING", "事前監視継続・公式日程未確認"
        recommendation = "現在価格は事前参考値です。設定期間は各社の公式開催日ではありません。公式ページで2026年の日付範囲を確認できるまではBF価格として扱わず、開催日推定に基づく購入推奨を出しません。"
        reasons = [
            "暫定の広域監視窓はまだ始まっていません。",
            "各販売店の公式2026年セール日程は個別に確認します。過去の日程や曜日からは推定しません。",
        ]
    elif now > end:
        status, label = "SALE_WINDOW_CLOSED", "設定した監視期間は終了"
        recommendation = "期間終了後の価格を2026年BF実売として扱いません。公式の次回セール日程が判明したら監視窓を更新します。"
        reasons = ["設定された監視期間外です。"]
    elif qualified:
        chosen = qualified[0]
        status, label = "BUY_NOW", "今買う候補あり"
        recommendation = "既存の全体購入ゲートを通過しました。決済直前に同一SKU、在庫、構成、送料込みの最終支払額を再確認してください。"
        reasons = ["価格・在庫・完成構成・PIT・重要候補カバレッジ・周辺機器込み予算が確認済みです。"]
    elif urgent_blocked:
        chosen = sorted(urgent_blocked, key=lambda x: (
            -(x.get("timing_score_100") or 0), x.get("ranking_score_100") or 0
        ))[0]
        status, label = "URGENT_BUT_GATE_BLOCKED", "売り切れリスクあり・購入ゲート未通過"
        recommendation = "低在庫の条件は見えていますが、購入ゲートが未通過です。予算・カバレッジ・価格情報の不足を解消するまで購入許可は出しません。"
        reasons = chosen.get("blockers") or ["購入ゲート未通過"]
    elif in_window and not any_campaign_dates_confirmed:
        status, label = "WAIT_FOR_OFFICIAL_DATES", "公式セール日程の確認待ち"
        recommendation = "価格監視は継続中ですが、対象販売店の2026年公式セール日程が未確認です。暫定の広域監視窓だけではBF実売として扱わず、公式日付確認前に購入推奨を出しません。"
        reasons = [
            "各候補の販売元について、公式ページ上の2026年日付範囲が未確認です。",
            "取得済み価格は広域監視窓の比較材料として保存し、公式BF価格とは区別します。",
            "購入ゲート: " + str(gate.get("reason") or "未確認"),
        ]
    elif in_window and not any_official_campaign_active:
        status, label = "WAIT_FOR_CAMPAIGN_WINDOW", "公式セール開催窓の開始待ち"
        recommendation = "公式の2026年開催日程は確認済みですが、監視対象のいずれの公式開催窓も現在アクティブではありません。対象店舗の期間に入ったら価格・在庫・PITを再確認します。"
        reasons = ["公式日程は未開始、またはすでに終了しています。"]
    elif over_budget:
        chosen = over_budget[0]
        status, label = "WAIT_FOR_DISCOUNT", "値下げ待ち"
        gap = max(0, chosen["cash_total_cost_jpy"] - int(pc_cap))
        recommendation = "公式セール期間内で確認した完成構成価格が本体動的上限を ¥{:,} 超えています。予算超過のまま買わず、目標額到達を監視します。".format(gap)
        reasons = chosen.get("blockers") or ["PC本体価格が動的上限を超過"]
    elif not budget_ready or not coverage_complete or not gate_allowed:
        status, label = "WAIT_FOR_VERIFICATION", "データ確認が揃うまで判断保留"
        recommendation = "価格・在庫・完成構成・周辺機器込み予算・重要候補の確認が不足しています。取得失敗を売り切れとみなさず、確認できた時点で再判定します。"
        reasons = [
            "既存購入ゲートの理由: " + str(gate.get("reason") or "未確認"),
            "在庫切れと取得失敗を区別し、未確認情報では購入許可を出しません。",
        ]
    else:
        status, label = "WAIT_FOR_VERIFIED_OFFER", "購入条件を満たす価格・在庫が未確認"
        recommendation = "価格・在庫・PIT・完成構成・総予算を同時に満たす候補がありません。監視を継続します。"
        reasons = ["購入条件を通過した販売条件を確認できていません。"]

    if chosen is None:
        chosen = next((x for x in rows if x.get("price_verified_for_bf")), rows[0] if rows else None)
    hours_left = max(0, (end - now).total_seconds() / 3600) if in_window else None
    return {
        "generated_at": iso(now),
        "purchase_method_policy": {
            "primary_method": "SELF_BUILD" if self_build_primary else method_policy.get("primary_method", "RANKED_COMPLETE_PC"),
            "assembly_time_is_constraint": bool(method_policy.get("assembly_time_is_constraint", False)),
            "assembly_time_penalty_points": int(method_policy.get("assembly_time_penalty_points", 0) or 0),
            "bto_role": method_policy.get("bto_role", "REFERENCE_BENCHMARK_ONLY" if self_build_primary else "RANKED_COMPLETE_PC"),
            "completed_pc_purchase_actionable": not self_build_primary,
        },
        "status": status,
        "label": label,
        "recommendation": recommendation,
        "reasons": reasons,
        "sale_phase": phase,
        "watch_window_start_jst": iso(start),
        "watch_window_end_jst": iso(end),
        "watch_window_active": in_window,
        "watch_window_type": config.get("monitor_window_type", "PROVISIONAL_BROAD_WATCH_WINDOW"),
        "official_campaign_dates_summary": {
            "retailer_count": len((official_campaign_dates or {}).get("sources") or {}),
            "confirmed_count": sum(
                1 for entry in ((official_campaign_dates or {}).get("sources") or {}).values()
                if isinstance(entry, dict) and entry.get("status") in ("CONFIRMED", "CONFIRMED_MANUAL")
            ),
            "unconfirmed_count": sum(
                1 for entry in ((official_campaign_dates or {}).get("sources") or {}).values()
                if isinstance(entry, dict) and entry.get("status") == "UNCONFIRMED"
            ),
            "fetch_error_count": sum(
                1 for entry in ((official_campaign_dates or {}).get("sources") or {}).values()
                if isinstance(entry, dict) and entry.get("status") == "FETCH_ERROR"
            ),
            "policy": "A provisional monitoring window does not confirm retailer campaign dates; fetch errors are separate from unconfirmed/no-date findings.",
        },
        "remaining_hours_in_watch_window": round(hours_left, 1) if hours_left is not None else None,
        "total_budget_jpy": total_budget,
        "pc_target_jpy": pc_target,
        "pc_dynamic_cap_jpy": pc_cap,
        "peripheral_projection_jpy": peripheral_cost,
        "peripheral_budget_data_ready": budget_ready,
        "purchase_gate_allowed": gate_allowed,
        "coverage_status": gate.get("coverage_status"),
        "purchase_gate_reason": gate.get("reason"),
        "source_snapshot_generated_at": rankings.get("source_snapshot_generated_at"),
        "source_snapshot_sha256": rankings.get("source_snapshot_sha256"),
        "chosen_candidate": chosen,
        "candidates": rows[:15],
        "score_policy": "買い時スコアは比較用の優先度指標であり、値下がり確率や将来価格の予測ではありません。",
        "history_policy": "期間内の最低観測価格は保存されたイベントと確認済み現行価格から作成し、標本不足では傾向を推定しません。",
    }


def render_buy_now_markdown(decision):
    lines = [
        "# 今この瞬間の買い時判定",
        "",
        "- 更新時刻（JST）: " + str(decision.get("generated_at")),
        "- 判定: **" + str(decision.get("label")) + "** (" + str(decision.get("status")) + ")",
        "- 暫定の広域監視窓（公式セール日程ではない）: " + str(decision.get("watch_window_start_jst")) + " ～ " + str(decision.get("watch_window_end_jst")),
        "- 公式日程確認: " + str(decision.get("official_campaign_dates_summary", {}).get("confirmed_count", 0)) + "/" + str(decision.get("official_campaign_dates_summary", {}).get("retailer_count", 0)) + " 店舗（公式期間が確認できない店舗: " + str(decision.get("official_campaign_dates_summary", {}).get("unconfirmed_count", 0)) + "、取得エラー: " + str(decision.get("official_campaign_dates_summary", {}).get("fetch_error_count", 0)) + "）",
        "- 監視窓内の価格を保存して比較しますが、公式日程・価格適用の確認がない価格はBF実売として扱いません。",
        "- 総予算: " + ("¥{:,}".format(decision["total_budget_jpy"]) if decision.get("total_budget_jpy") is not None else "未確認"),
        "- PC本体の動的上限: " + ("¥{:,}".format(decision["pc_dynamic_cap_jpy"]) if decision.get("pc_dynamic_cap_jpy") is not None else "未確認"),
        "- 周辺機器の価格・在庫確認: " + ("完了" if decision.get("peripheral_budget_data_ready") else "未完了"),
        "- 購入ゲート: " + ("通過" if decision.get("purchase_gate_allowed") else "保留") + " (" + str(decision.get("purchase_gate_reason") or "未確認") + ")",
        "",
        str(decision.get("recommendation") or ""),
        "",
        "## 判定根拠",
        "",
    ]
    diy = decision.get("self_build_purchase_timing") or {}
    method = decision.get("purchase_method_policy") or {}
    diy_lines = [
        "## 自作PC本命の買い時",
        "",
        "- 正式な購入方式: **自作PC**",
        "- 組み立て時間を考慮するか: " + ("はい" if method.get("assembly_time_is_constraint") else "いいえ（減点なし）"),
        "- BTOの位置付け: 価格・性能・部品品質・保証の比較ベンチマークのみ",
        "- 本命構成: " + str(diy.get("selected_build_name") or "未確認"),
        "- PC本体のBF購入目標（送料・小物予備費込み）: " + ("¥{:,}".format(diy["target_pc_total_jpy"]) if diy.get("target_pc_total_jpy") is not None else "未確認"),
        "- 周辺機器込みBF購入目標: " + ("¥{:,}".format(diy["target_all_in_jpy"]) if diy.get("target_all_in_jpy") is not None else "未確認"),
        "- 目標上の総予算残額: " + ("¥{:,}".format(diy["target_remaining_budget_jpy"]) if diy.get("target_remaining_budget_jpy") is not None else "未確認"),
        "- 互換性判定: " + str(diy.get("compatibility_status") or "未確認"),
        "- 検証済み比較参考価格: " + str(diy.get("verified_market_reference_count", 0)) + "/" + str(diy.get("tracked_component_count", 0)),
        "- 検索ページ表示専用の参考価格（推定・購入判定には不使用）: " + str(diy.get("display_only_search_reference_count", 0)) + "/" + str(diy.get("tracked_component_count", 0)),
        "- 確認済み店舗決済オファー: " + str(diy.get("verified_checkout_offer_count", 0)) + "/" + str(diy.get("component_count", 0)),
        "- 自作購入判定: **" + str(diy.get("status") or "SELF_BUILD_DATA_UNAVAILABLE") + "**",
        "- 購入許可: **出していません**（BF目標・比較サイト参考価格では購入許可しない）",
        "",
        "### 自作本命の未解決条件",
        "",
    ]
    for blocker in diy.get("blockers") or []:
        diy_lines.append("- " + str(blocker))
    diy_lines += [
        "",
        "### 部品別のBF購入目標・比較参考値・値下がり履歴",
        "",
        "検証済み比較参考値と検索ページ表示専用値は別列です。表示専用値は近傍テキストから得た参考情報で、販売店掲載・在庫・最終決済価格を証明しません。目標との差や買い時判定、購入許可には使用しません。",
        "",
        "|部品|BF購入目標|検証済み比較参考値|検索ページ表示専用値（不採用）|目標までの差|履歴内参考最安|監視窓内参考最安|履歴件数 / 監視窓件数|判定|価格確認ページ|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for part in diy.get("component_timing") or []:
        target_text = "¥{:,}".format(part["target_price_jpy"]) if part.get("target_price_jpy") is not None else "—"
        current_text = "¥{:,}".format(part["current_market_reference_price_jpy"]) if part.get("current_market_reference_price_jpy") is not None else "未確認"
        display_only_text = "¥{:,}".format(part["display_only_reference_price_jpy"]) if part.get("display_only_reference_price_jpy") is not None else "—"
        if part.get("display_only_reference_url"):
            display_only_text += " ([検索結果](" + str(part["display_only_reference_url"]) + "))"
        gap_text = "¥{:,}".format(part["target_gap_jpy"]) if part.get("target_gap_jpy") is not None else "—"
        if part.get("required_drop_pct") is not None:
            gap_text += " (" + str(part["required_drop_pct"]) + "%)"
        low_text = "¥{:,}".format(part["history_low_reference_price_jpy"]) if part.get("history_low_reference_price_jpy") is not None else "未観測"
        window_low_text = "¥{:,}".format(part["watch_window_low_reference_price_jpy"]) if part.get("watch_window_low_reference_price_jpy") is not None else "未観測"
        sample_text = str(part.get("history_sample_count", 0)) + " / " + str(part.get("watch_window_sample_count", 0))
        url = part.get("purchase_url")
        link_text = "[比較・仕様ページ](" + url + ")" if url and str(url).startswith(("https://", "http://")) else "未確認"
        diy_lines.append(
            "|" + str(part.get("name") or part.get("id")) + "|" + target_text + "|" + current_text + "|" + display_only_text + "|"
            + gap_text + "|" + low_text + "|" + window_low_text + "|" + sample_text + "|"
            + str(part.get("status_label") or part.get("status")) + "|" + link_text + "|"
        )
    diy_lines.append("")
    try:
        reason_index = lines.index("## 判定根拠")
        lines[reason_index:reason_index] = diy_lines
    except ValueError:
        lines.extend(diy_lines)

    for reason in decision.get("reasons") or []:
        lines.append("- " + str(reason))
    chosen = decision.get("chosen_candidate")
    if chosen:
        lines += [
            "",
            "## 注目候補",
            "",
            "- 商品: **" + str(chosen.get("name")) + "**",
            "- 商品判定: " + str(chosen.get("status")),
            "- 価格区分: " + (
                "BF期間内の確認価格 ¥{:,}".format(chosen["price_jpy"]) if chosen.get("price_jpy") is not None else
                "BF前の参考価格 ¥{:,}".format(chosen["pre_bf_reference_price_jpy"]) if chosen.get("pre_bf_reference_price_jpy") is not None else
                "BF後の参考価格 ¥{:,}".format(chosen["post_bf_reference_price_jpy"]) if chosen.get("post_bf_reference_price_jpy") is not None else
                "BF期間内の最終観測 ¥{:,}（現在価格ではない）".format(chosen["last_bf_observed_price_jpy"]) if chosen.get("last_bf_observed_price_jpy") is not None else
                "未確認"
            ),
            "- BF前の参考価格: " + ("¥{:,}".format(chosen["pre_bf_reference_price_jpy"]) if chosen.get("pre_bf_reference_price_jpy") is not None else "—"),
            "- PC本体動的上限: " + ("¥{:,}".format(chosen["pc_dynamic_cap_jpy"]) if chosen.get("pc_dynamic_cap_jpy") is not None else "未確認"),
            "- PC＋周辺機器の総額試算: " + ("¥{:,}".format(chosen["estimated_all_in_jpy"]) if chosen.get("estimated_all_in_jpy") is not None else "未確認"),
            "- 在庫・待つリスク: " + str(chosen.get("stock_status")) + " / " + str(chosen.get("wait_risk")),
            "- RAM32GB/SSD1TB以上: " + ("達成" if chosen.get("configuration_ready") else "未達/未確認"),
            "- 暫定監視窓内の最低観測価格（BF公式価格とは限らない）: " + (
                "¥{:,}".format(chosen["watch_window_low_observed_jpy"])
                + ("（" + str(chosen["watch_window_low_observed_at"]) + "）" if chosen.get("watch_window_low_observed_at") else "")
                if chosen.get("watch_window_low_observed_jpy") is not None else "未観測"
            ),
            "- 監視窓内の比較可能な観測数: " + str(chosen.get("watch_window_price_observation_count", 0)),
            "- 販売店の2026年公式日程: " + str(chosen.get("retailer_campaign_status") or "UNCONFIRMED"),
            "- 買い時スコア: " + (str(chosen.get("timing_score_100")) + "/100" if chosen.get("timing_score_100") is not None else "未算出"),
            "- 購入リンク: " + ("[販売ページ](" + chosen["purchase_url"] + ")" if chosen.get("purchase_url") else "未確認"),
            "",
            "### この候補の未解決条件",
            "",
        ]
        for blocker in chosen.get("blockers") or []:
            lines.append("- " + str(blocker))
    lines += [
        "",
        "## 候補一覧",
        "",
        "|順位|商品|公式期間内の確認価格|暫定監視窓内参考価格|総額試算|在庫|構成|監視窓内最低観測|買い時スコア|判定|商品ページ|",
        "|---:|---|---:|---:|---:|---|---|---:|---:|---|---|",
    ]
    for index, row in enumerate(decision.get("candidates") or [], 1):
        price_text = "¥{:,}".format(row["price_jpy"]) if row.get("price_jpy") is not None else "未確認"
        watch_price_text = "¥{:,}".format(row["watch_window_observed_price_jpy"]) if row.get("watch_window_observed_price_jpy") is not None else "—"
        all_in = "¥{:,}".format(row["estimated_all_in_jpy"]) if row.get("estimated_all_in_jpy") is not None else "未確認"
        low = (
            "¥{:,}".format(row["watch_window_low_observed_jpy"])
            + (" @ " + str(row["watch_window_low_observed_at"]) if row.get("watch_window_low_observed_at") else "")
            if row.get("watch_window_low_observed_jpy") is not None else "未観測"
        )
        score = str(row["timing_score_100"]) + "/100" if row.get("timing_score_100") is not None else "—"
        url = "[販売ページ](" + row["purchase_url"] + ")" if row.get("purchase_url") else "未確認"
        lines.append(
            "|" + str(index) + "|" + str(row.get("name", "")) + "|" + price_text + "|" + watch_price_text + "|" + all_in + "|"
            + str(row.get("stock_status")) + "|" + ("達成" if row.get("configuration_ready") else "未達/未確認") + "|"
            + low + "|" + score + "|" + str(row.get("status")) + "|" + url + "|"
        )
    lines += [
        "",
        "## 読み方と安全規則",
        "",
        "- BUY_NOWはBF期間内の直接価格・SKU・鮮度・PIT・在庫・完成構成・総予算・重要候補カバレッジを全て通過した場合だけ表示します。",
        "- URGENT_BUT_GATE_BLOCKEDは売り切れリスクがあっても、購入ゲートが未通過のため購入許可を出さない状態です。",
        "- 買い時スコアは優先順位の補助であり、値下がり確率ではありません。",
        "- 暫定監視窓の最低価格は観測履歴の最小値であり、販売店の全履歴最安値や公式BF価格を意味しません。",
        "- 価格取得失敗は売り切れとは扱いません。ポイントや未適用クーポンを現金値引きに数えません。",
        "- 監視窓外の現在価格は参考情報であり、2026年BF実売価格として表示しません。",
        "",
    ]
    return "\n".join(lines)



def append_buy_now_summary_to_latest(decision):
    """Make the action visible in the main report as well as the detailed timing report."""
    path = os.path.join(ROOT, "data", "reports", "latest.md")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        content = f.read()
    marker = "## 今この瞬間の買い時判定"
    if marker in content:
        content = content.split(marker, 1)[0].rstrip()

    lines = [
        marker,
        "",
        "- 更新時刻（JST）: " + str(decision.get("generated_at")),
        "- 判定: **" + str(decision.get("label")) + "** (" + str(decision.get("status")) + ")",
        "- 暫定の広域監視窓（公式セール日程ではない）: " + str(decision.get("watch_window_start_jst")) + " ～ " + str(decision.get("watch_window_end_jst")),
        "- 公式日程確認: " + str(decision.get("official_campaign_dates_summary", {}).get("confirmed_count", 0)) + "/" + str(decision.get("official_campaign_dates_summary", {}).get("retailer_count", 0)) + " 店舗（未確認: " + str(decision.get("official_campaign_dates_summary", {}).get("unconfirmed_count", 0)) + "、取得エラー: " + str(decision.get("official_campaign_dates_summary", {}).get("fetch_error_count", 0)) + "）",
        "- 総予算: " + ("¥{:,}".format(decision["total_budget_jpy"]) if decision.get("total_budget_jpy") is not None else "未確認"),
        "- PC本体の動的上限: " + ("¥{:,}".format(decision["pc_dynamic_cap_jpy"]) if decision.get("pc_dynamic_cap_jpy") is not None else "未確認"),
        "- 周辺機器の価格・在庫確認: " + ("完了" if decision.get("peripheral_budget_data_ready") else "未完了"),
        "- 全体購入ゲート: " + ("通過" if decision.get("purchase_gate_allowed") else "保留") + " (" + str(decision.get("purchase_gate_reason") or "未確認") + ")",
        "",
        str(decision.get("recommendation") or ""),
        "",
    ]
    chosen = decision.get("chosen_candidate")
    if chosen:
        if chosen.get("price_jpy") is not None:
            chosen_price = "¥{:,}".format(chosen["price_jpy"]) + "（BF期間内の確認価格）"
        elif chosen.get("pre_bf_reference_price_jpy") is not None:
            chosen_price = "¥{:,}".format(chosen["pre_bf_reference_price_jpy"]) + "（BF前の参考価格・購入判断には不使用）"
        elif chosen.get("post_bf_reference_price_jpy") is not None:
            chosen_price = "¥{:,}".format(chosen["post_bf_reference_price_jpy"]) + "（BF後の参考価格・購入判断には不使用）"
        elif chosen.get("last_bf_observed_price_jpy") is not None:
            chosen_price = "¥{:,}".format(chosen["last_bf_observed_price_jpy"]) + "（BF期間内の最終観測・現在価格ではない）"
        else:
            chosen_price = "未確認"
        lines += [
            "- 注目候補: **" + str(chosen.get("name")) + "**",
            "- 価格: " + chosen_price,
            "- BF後の参考価格: " + ("¥{:,}".format(chosen["post_bf_reference_price_jpy"]) if chosen.get("post_bf_reference_price_jpy") is not None else "—"),
            "- 暫定監視窓内の最低観測価格（BF公式価格とは限らない）: " + (
                "¥{:,}".format(chosen["watch_window_low_observed_jpy"])
                + ("（" + str(chosen["watch_window_low_observed_at"]) + "）" if chosen.get("watch_window_low_observed_at") else "")
                if chosen.get("watch_window_low_observed_jpy") is not None else "未観測"
            ),
            "- 監視窓内観測件数: " + str(chosen.get("watch_window_price_observation_count", 0)),
            "- 販売店の2026年公式日程: " + str(chosen.get("retailer_campaign_status") or "UNCONFIRMED"),
            "- 在庫 / 待つリスク: " + str(chosen.get("stock_status")) + " / " + str(chosen.get("wait_risk")),
            "- RAM32GB・SSD1TB以上: " + ("達成" if chosen.get("configuration_ready") else "未達/未確認"),
            "- 買い時スコア: " + (str(chosen.get("timing_score_100")) + "/100" if chosen.get("timing_score_100") is not None else "未算出"),
            "- 購入リンク: " + ("[販売ページ](" + chosen["purchase_url"] + ")" if chosen.get("purchase_url") else "未確認"),
        ]
        if chosen.get("blockers"):
            lines.append("- 主な未解決条件: " + "；".join(str(x) for x in chosen["blockers"][:4]))
        lines.append("")
    diy = decision.get("self_build_purchase_timing") or {}
    method = decision.get("purchase_method_policy") or {}
    lines += [
        "",
        "## 自作PC本命の買い時",
        "",
        "- 正式な購入方式: **自作PC**。組み立て時間・作業時間は減点しません。",
        "- BTO: 価格・性能・部品品質・保証の比較ベンチマークのみ。",
        "- 本命構成: " + str(diy.get("selected_build_name") or "未確認"),
        "- PC本体BF購入目標: " + ("¥{:,}".format(diy["target_pc_total_jpy"]) if diy.get("target_pc_total_jpy") is not None else "未確認"),
        "- 周辺機器込みBF購入目標: " + ("¥{:,}".format(diy["target_all_in_jpy"]) if diy.get("target_all_in_jpy") is not None else "未確認"),
        "- 互換性 / 部品の比較参考価格 / 店舗決済オファー: " + str(diy.get("compatibility_status") or "未確認") + " / " + str(diy.get("verified_market_reference_count", 0)) + "/" + str(diy.get("tracked_component_count", 0)) + " / " + str(diy.get("verified_checkout_offer_count", 0)) + "/" + str(diy.get("component_count", 0)),
        "- 自作の買い時判定: **" + str(diy.get("status") or "SELF_BUILD_DATA_UNAVAILABLE") + "**",
        "- 購入許可: **保留**。購入目標や比較価格は確定実売ではありません。",
        "- 主な未解決条件: " + "；".join(str(x) for x in (diy.get("blockers") or [])[:3]),
        "",
        "詳細レポート: [今この瞬間の買い時判定](buy-now-now.md)",
        "",
        "買い時スコアは優先順位の補助指標です。値下がり確率の予測ではありません。価格取得失敗は売り切れ扱いせず、BF前の価格はBF実売と区別します。",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n\n" + "\n".join(lines))
    return True


def main():
    latest_path=os.path.join(ROOT,"data","current_latest.json")
    latest=load_json(latest_path,{"products":[]})
    source_snapshot_generated_at=latest.get("generated_at")
    source_snapshot_sha256=file_sha256(latest_path) if os.path.exists(latest_path) else None
    catalog=load_catalog()
    live={str(x.get("id")):x for x in latest.get("products",[]) if x.get("id")}

    rows=[]
    for cid,item in live.items():
        price=item.get("current_price_jpy")
        if price is None:
            continue
        gpu=gpu_key(item)
        req=required_discount(price)
        perf=performance_score(item)[0] if gpu else -1
        rows.append({
            "id":cid,
            "name":item.get("name") or catalog.get(cid,{}).get("name"),
            "store":item.get("store"),
            "price_jpy":price,
            "required_discount_pct":round(req,1) if req is not None else None,
            "feasibility":(
                "HIGH" if req is not None and req<=10 else
                "REALISTIC" if req is not None and req<=20 else
                "AGGRESSIVE" if req is not None and req<=30 else
                "LOW" if req is not None and req<=40 else
                "VERY_LOW"
            ),
            "gpu":gpu or None,
            "performance_score":perf,
            "source_mode":item.get("price_source_mode"),
            "confidence":item.get("data_confidence"),
            "dynamic_candidate":bool(item.get("dynamic_candidate")),
        })
    rows.sort(key=lambda x:(x["required_discount_pct"] if x["required_discount_pct"] is not None else 999999, -x["performance_score"]))
    events = read_events()
    dynamic=dynamic_change_timing(events)
    config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    recorded_observations = append_buy_now_observations(latest, config)
    window_start = parse_dt(config.get("monitor_window_start"))
    window_end = parse_dt(config.get("monitor_window_end"))
    now = now_jst()
    window_active = bool(window_start and window_end and window_start <= now <= window_end)
    price_observations = (
        read_buy_now_observations(window_start, window_end) if window_active else []
    )
    rankings = load_json(os.path.join(ROOT, "data", "decision_rankings.json"), {})
    official_campaign_dates = load_json(
        os.path.join(ROOT, "data", "official_campaign_dates_status.json"), {}
    )
    decision = build_buy_now_decision(
        rankings, events, config, price_observations, official_campaign_dates
    )
    build_config = load_json(os.path.join(ROOT, "config", "build_components.json"), {})
    build_plan = load_json(os.path.join(ROOT, "data", "self_build_plan.json"), {})
    self_build_timing = build_self_build_timing_summary(build_plan, build_config)
    decision["self_build_purchase_timing"] = self_build_timing
    decision["purchase_method_policy"] = decision.get("purchase_method_policy") or {
        "primary_method": "SELF_BUILD",
        "assembly_time_is_constraint": False,
        "assembly_time_penalty_points": 0,
        "bto_role": "REFERENCE_BENCHMARK_ONLY",
        "completed_pc_purchase_actionable": False,
    }
    if decision["purchase_method_policy"].get("primary_method") == "SELF_BUILD":
        decision["purchase_gate_allowed"] = False
        decision["purchase_gate_reason"] = "self_build_primary_method_required"
    out={
        "generated_at":iso(now_jst()),
        "source_snapshot_generated_at":source_snapshot_generated_at,
        "source_snapshot_sha256":source_snapshot_sha256,
        "budget_jpy":BUDGET,
        "target_black_friday":TARGET.date().isoformat(),
        "target_products":rows[:50],
        "historical_events":HISTORY,
        "observed_change_timing":dynamic,
        "buy_now_decision": decision,
        "price_observation_ledger": {
            "path": "data/buy_now_observations.jsonl",
            "appended_this_run": recorded_observations,
            "historical_rows_loaded": len(price_observations),
            "window_type": config.get("monitor_window_type", "PROVISIONAL_BROAD_WATCH_WINDOW"),
            "window_start_jst": config.get("monitor_window_start"),
            "window_end_jst": config.get("monitor_window_end"),
        },
        "interpretation":{
            "important_caveat":"Observed/retrieval time is an upper bound on when this system knew the change, not seller-internal price-change time.",
            "minimum_sample_for_hour_pattern":20
        }
    }
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","timing_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    with open(os.path.join(ROOT,"data","buy_now_decision.json"),"w",encoding="utf-8") as f:
        json.dump(decision,f,ensure_ascii=False,indent=2)
    with open(os.path.join(ROOT,"data","reports","buy-now-now.md"),"w",encoding="utf-8") as f:
        f.write(render_buy_now_markdown(decision))
    append_buy_now_summary_to_latest(decision)
    lines=[
        "# Black Friday price timing analysis","",
        f"Generated: {out['generated_at']}",
        f"Source snapshot: {source_snapshot_generated_at or 'UNCONFIRMED'}",
        f"Source snapshot SHA256: {source_snapshot_sha256 or 'UNCONFIRMED'}",
        f"Budget: ¥{BUDGET:,}",
        f"Target Black Friday: {TARGET.date()}","",
        "## Current actionable candidates","",
        "|Rank|Product|Current|Required discount|Feasibility|GPU|Perf|Source|",
        "|---:|---|---:|---:|---|---|---:|---|"
    ]
    for i,r in enumerate(rows[:30],1):
        lines.append(f"|{i}|{str(r['name'])[:55]}|¥{r['price_jpy']:,}|{r['required_discount_pct']:.1f}%|{r['feasibility']}|{r['gpu'] or '—'}|{r['performance_score']}|{r['source_mode']}|")
    lines += ["","## Empirical price-change timing","",f"- Meaningful change sample: **{dynamic['sample_size']}**"]
    if dynamic["sample_size"]<20:
        lines.append("- **観測不足:** 20件未満なので時間帯の傾向は作りません。")
    else:
        lines.append("- 20件以上のため実測時間帯を参照します。")
        lines.append("- 上位時間帯: "+", ".join(f"{h:02d}時={n}件" for h,n in dynamic["top_hours"]))
    lines += ["","## Historical anchors",""]
    for h in HISTORY:
        p=f" ¥{h['price']:,}" if h.get("price") else ""
        lines.append(f"- {h['date']} | {h['label']}{p} | {h['source']}")
    lines += ["", "## BF window observation ledger", "",
              "- Ledger: data/buy_now_observations.jsonl",
              "- Rows loaded: {}".format(len(price_observations)),
              "- Rows appended this run: {}".format(recorded_observations),
              "- Only in-stock/low-stock, exact-identity, direct-structured and PIT-valid observations are added.",
              "", "## Current buy-now decision", "",
              "- Status: **{}** ({})".format(decision.get("label"), decision.get("status")),
              "- Recommendation: {}".format(decision.get("recommendation")),
              "- Full detail: data/reports/buy-now-now.md",
              "- The timing score is a heuristic priority signal, not a probability forecast.",
              "", "## Rules",
              "- Missing retrieval is not stockout.",
              "- Seller-internal price-change time is never inferred from article publication time.",
              "- Timing observations are empirical only after sufficient sample size."]
    with open(os.path.join(ROOT,"data","reports","timing_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
