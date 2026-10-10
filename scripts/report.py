import hashlib
import json
import os
from datetime import datetime

from intelligence import (
    ROOT, BUDGET, EFFECTIVE_SOFT_MAX, EFFECTIVE_HARD_MAX,
    load_json, save_json, load_catalog, load_anchors,
    build_row, cash_total_cost, confirmed_benefit_value, effective_cost, noncash_benefit_value_jpy, value_equivalent_cost,
    now_jst, iso, scenario_prices, purchase_budget_policy, peripheral_budget_projection,
    configuration_readiness, gpu_key
)

def sales_url(item):
    """Return only a real HTTP(S) product URL; never fabricate a purchase URL."""
    url = str(item.get("url") or "").strip()
    return url if url.startswith(("https://", "http://")) else None


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def suppress_current_price(row):
    """Convert a non-actionable row into reference-only evidence."""
    out = dict(row)
    if out.get("current_price_jpy") is not None:
        out["last_valid_price_jpy"] = (
            out.get("last_valid_price_jpy")
            or out.get("current_price_jpy")
        )
    out["reference_price_jpy"] = (
        out.get("reference_price_jpy")
        or out.get("last_valid_price_jpy")
    )
    out["current_price_jpy"] = None
    out["price_jpy"] = None
    out["current_price_suppressed"] = True
    return out


def _trusted_live_offer(item):
    price = item.get("current_price_jpy")
    return bool(
        isinstance(price, int) and not isinstance(price, bool) and price > 0
        and item.get("price_source_mode") == "direct_structured"
        and item.get("price_validation_status") not in (
            None, "missing", "anomaly_rejected", "reference_only", "variant_ambiguous"
        )
        and item.get("variant_match") in ("exact", "trusted_url", "strong")
        and item.get("pit_valid") is True
    )


def _parse_strategy_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def build_purchase_strategy_status(products, strategy, budget, peripheral_projection):
    """Report BF targets separately from pre-sale reference observations."""
    now = now_jst()
    phase = strategy.get("price_semantics") or {}
    bf_start = _parse_strategy_dt(phase.get("window_start_jst"))
    bf_end = _parse_strategy_dt(phase.get("window_end_jst"))
    in_bf_window = bool(bf_start and bf_end and bf_start <= now <= bf_end)
    budget_ready = bool(peripheral_projection.get("budget_data_ready"))
    live_cap = int(peripheral_projection.get("pc_dynamic_cap_jpy") or 0)
    planned_bf_cap = min(
        int(budget["pc_budget_jpy"]),
        int(budget["total_budget_jpy"]) - int(budget["peripheral_budget_jpy"]),
    )
    bf_cap = min(int(budget["pc_budget_jpy"]), live_cap) if in_bf_window and budget_ready else planned_bf_cap
    by_id = {str(x.get("id")): x for x in products if x.get("id")}
    rows = []

    for plan in strategy.get("priority_plans", []):
        cid = str(plan.get("candidate_id") or "")
        item = by_id.get(cid, {})
        verified = _trusted_live_offer(item)
        observed_price = item.get("current_price_jpy") if verified else None
        observed_at = _parse_strategy_dt(item.get("retrieval_time"))
        observation_is_bf = bool(verified and in_bf_window and observed_at and bf_start <= observed_at <= bf_end)
        bf_target = int(plan.get("black_friday_target_price_jpy") or budget["pc_target_jpy"])
        ready, reasons = configuration_readiness(item) if item else (False, ["候補の構成未確認"])
        stock = item.get("stock_status", "unknown")
        role = plan.get("role")
        row = {
            "candidate_id": cid, "role": role, "label": plan.get("label") or item.get("name") or cid,
            "url": sales_url(item) or plan.get("purchase_url"),
            "black_friday_target_price_jpy": bf_target, "black_friday_price_cap_jpy": bf_cap,
            "black_friday_price_observed_jpy": observed_price if observation_is_bf else None,
            "black_friday_offer_verified": observation_is_bf,
            "pre_black_friday_reference_price_jpy": observed_price if verified and not observation_is_bf else None,
            "pre_black_friday_reference_at": item.get("retrieval_time") if verified and not observation_is_bf else None,
            "observed_price_jpy": observed_price,
            "observed_price_phase": "BLACK_FRIDAY_WINDOW" if observation_is_bf else ("PRE_BLACK_FRIDAY_REFERENCE" if verified else "UNVERIFIED"),
            "price_verified": verified, "stock_status": stock, "configuration_ready": ready,
            "configuration_reasons": reasons, "target_ram_gb": plan.get("target_ram_gb"),
            "target_ssd_gb": plan.get("target_ssd_gb"),
            "current_live_pc_budget_cap_reference_jpy": live_cap,
            "bf_budget_cap_is_final": bool(in_bf_window and budget_ready),
            "status": "PRE_BF_TARGET_MONITORING" if not in_bf_window else "BF_PRICE_UNVERIFIED",
            "detail": "",
        }
        if role == "primary_configuration_upgrade":
            baseline = int(plan.get("baseline_price_jpy") or 0)
            row.update({
                "baseline_price_reference_jpy": baseline,
                "baseline_price_reference_phase": "PRE_BLACK_FRIDAY_BASE_CONFIGURATION",
                "baseline_ram_gb": plan.get("baseline_ram_gb"), "baseline_ssd_gb": plan.get("baseline_ssd_gb"),
                "max_upgrade_cost_to_bf_target_jpy": max(0, bf_target-baseline),
                "max_upgrade_cost_to_bf_hard_cap_jpy": max(0, bf_cap-baseline),
                "max_upgrade_cost_to_target_jpy": max(0, bf_target-baseline),
                "max_upgrade_cost_to_hard_cap_jpy": max(0, bf_cap-baseline),
                "max_upgrade_cost_to_dynamic_cap_jpy": max(0, bf_cap-baseline),
            })
            if not in_bf_window:
                row["detail"] = (
                    f"BF完成構成の目標は¥{bf_target:,}、計画上限は¥{bf_cap:,}。"
                    f"¥{baseline:,}は16GB/500GB基本構成の事前参考価格でありBF価格ではありません。"
                    f"構成変更費は理想まで¥{row['max_upgrade_cost_to_bf_target_jpy']:,}以内、"
                    f"計画上限まで¥{row['max_upgrade_cost_to_bf_hard_cap_jpy']:,}以内が条件です。"
                    "追加費用は未確認で、0円とは仮定しません。"
                )
            elif not observation_is_bf:
                row["status"], row["detail"] = "BF_PRICE_UNVERIFIED", "BF期間内の完成構成価格を直接確認できていません。事前価格をBF価格に流用しません。"
            elif stock == "out_of_stock":
                row["status"], row["detail"] = "OUT_OF_STOCK", "BF期間中の商品ページで在庫切れを確認。"
            elif stock not in ("in_stock", "low_stock"):
                row["status"], row["detail"] = "STOCK_UNCONFIRMED", "BF期間中の在庫を直接確認できていません。"
            elif not ready:
                row["status"], row["detail"] = "NEEDS_CONFIGURATION", "BF期間中に観測した価格も構成要件未達です。32GB RAM/1TB SSD完成構成の最終価格が必要です。"
            elif observed_price <= bf_cap:
                row["status"], row["detail"] = "MEETS_BF_PRICE_AND_CONFIGURATION", "BF期間内の直接観測価格・在庫・完成構成が条件内。全体購入ゲートは別途必要です。"
            else:
                row["status"], row["detail"] = "WAIT_FOR_DISCOUNT", f"BF観測価格から本体上限まで¥{observed_price-bf_cap:,}の値下げが必要です。"
        elif role == "secondary_outlet_complete_configuration":
            reference = int(plan.get("last_verified_listing_reference_jpy") or 0)
            row["listing_reference_price_jpy"] = reference
            if not in_bf_window:
                row["pre_bf_reference_gap_to_target_jpy"] = max(0, reference - bf_target) if reference else None
                row["pre_bf_reference_gap_to_planned_cap_jpy"] = max(0, reference - bf_cap) if reference else None
                row["detail"] = (
                    f"BF目標は¥{bf_target:,}、完成構成の計画上限は¥{bf_cap:,}。"
                    f"¥{reference:,}は10月の参考掲載額でBF価格ではありません。"
                    + (f" 参考額からBF目標まで¥{reference-bf_target:,}、計画上限まで¥{reference-bf_cap:,}の差があります。" if reference else "")
                )
            elif not observation_is_bf:
                row["status"], row["detail"] = "BF_PRICE_UNVERIFIED", "BF期間中の価格・在庫・SKUを直接確認できていません。"
            elif stock == "out_of_stock":
                row["status"], row["detail"] = "OUT_OF_STOCK", "BF期間中の商品ページで在庫切れを確認。"
            elif stock not in ("in_stock", "low_stock"):
                row["status"], row["detail"] = "STOCK_UNCONFIRMED", "BF期間中の在庫を直接確認できていません。"
            elif not ready:
                row["status"], row["detail"] = "NEEDS_CONFIGURATION", "BF期間中の価格を確認しましたが、32GB/1TB完成構成ではありません。"
            elif not budget_ready:
                row["status"], row["detail"] = "BF_BUDGET_UNVERIFIED", "PC価格・構成は確認できましたが、BF周辺機器の実売価格/在庫が揃わず、37万円総額の本体上限が未確定です。"
            elif observed_price <= bf_cap:
                row["status"], row["detail"] = "MEETS_BF_PRICE_AND_CONFIGURATION", "BF期間内の直接観測価格・在庫・完成構成が条件内。全体購入ゲートは別途必要です。"
            else:
                row["status"] = "WAIT_FOR_DISCOUNT"
                row["bf_price_target_gap_jpy"] = max(0, observed_price-bf_target)
                row["bf_price_cap_gap_jpy"] = max(0, observed_price-bf_cap)
                row["detail"] = f"BF観測価格から理想目標まで¥{row['bf_price_target_gap_jpy']:,}、BF本体上限まで¥{row['bf_price_cap_gap_jpy']:,}の値下げが必要です。"
        rows.append(row)

    outlier = strategy.get("outlier_rule") or {}
    token = str(outlier.get("gpu") or "RTX 5070 Ti").lower().replace("rtx ", "")
    candidates = [x for x in products if x.get("form_factor") == outlier.get("form_factor", "desktop") and token in gpu_key(x).lower()]
    observed_complete, bf_complete, eligible = [], [], []
    for item in candidates:
        if not _trusted_live_offer(item) or item.get("stock_status") not in ("in_stock", "low_stock"):
            continue
        ready, _ = configuration_readiness(item)
        if not ready:
            continue
        observed_complete.append(item)
        observed_at = _parse_strategy_dt(item.get("retrieval_time"))
        if in_bf_window and observed_at and bf_start <= observed_at <= bf_end:
            bf_complete.append(item)
            if budget_ready and int(item["current_price_jpy"]) <= bf_cap:
                eligible.append(item)
    eligible.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    bf_complete.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    observed_complete.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    if not in_bf_window:
        best = observed_complete[0] if observed_complete else None
        status, detail = "PRE_BF_TARGET_MONITORING", "事前価格は比較用参考情報のみ。ブラックフライデー販売価格として扱いません。"
    elif eligible:
        best = eligible[0]
        status, detail = "MEETS_BF_PRICE_AND_CONFIGURATION", "条件を満たすBF期間内の完成構成を検出。全体購入ゲート通過前は購入許可ではありません。"
    elif bf_complete and not budget_ready:
        best = bf_complete[0]
        status, detail = "BF_BUDGET_UNVERIFIED", f"BF期間中の完成構成を確認しましたが、周辺機器の価格/在庫が未確認で本体上限は未確定。参考の確認価格は¥{best['current_price_jpy']:,}です。"
    elif bf_complete:
        best = bf_complete[0]
        status, detail = "WAIT_FOR_DISCOUNT", f"BF期間中の完成構成を確認しましたが、本体上限を超過。最安確認価格は¥{best['current_price_jpy']:,}です。"
    else:
        best = None
        status, detail = "NO_VERIFIED_COMPLETE_CONFIGURATION", "BF期間内に価格・在庫・SKU・PITを直接確認できた32GB/1TB以上のRTX 5070 Tiデスクトップは未発見。"
    rows.append({
        "candidate_id": None, "role": "rtx_5070_ti_outlier", "label": outlier.get("label") or "RTX 5070 Ti 大穴",
        "black_friday_target_price_jpy": int(outlier.get("black_friday_target_cap_jpy") or budget["pc_budget_jpy"]),
        "black_friday_price_observed_jpy": best.get("current_price_jpy") if best and in_bf_window else None,
        "pre_black_friday_reference_price_jpy": best.get("current_price_jpy") if best and not in_bf_window else None,
        "black_friday_offer_verified": bool(best and in_bf_window), "price_verified": bool(best),
        "stock_status": best.get("stock_status", "unknown") if best else "unknown",
        "configuration_ready": bool(eligible), "configuration_reasons": [],
        "target_ram_gb": int(outlier.get("minimum_ram_gb") or 32), "target_ssd_gb": int(outlier.get("minimum_ssd_gb") or 1000),
        "bf_price_cap_jpy": bf_cap, "current_live_pc_budget_cap_reference_jpy": live_cap,
        "bf_budget_cap_is_final": bool(in_bf_window and budget_ready), "status": status, "detail": detail,
        "eligible_candidate_ids": [x.get("id") for x in eligible],
        "verified_complete_candidate_count": len(bf_complete if in_bf_window else observed_complete),
        "monitored_candidate_count": len(candidates), "url": sales_url(best) if best else None,
    })
    return {
        "generated_at": iso(now_jst()),
        "pricing_phase": "BLACK_FRIDAY_WINDOW" if in_bf_window else "PRE_BLACK_FRIDAY_REFERENCE",
        "black_friday_window_start_jst": phase.get("window_start_jst"),
        "black_friday_window_end_jst": phase.get("window_end_jst"),
        "future_black_friday_prices_known": bool(in_bf_window),
        "total_budget_jpy": budget["total_budget_jpy"],
        "peripheral_target_budget_jpy": budget["peripheral_budget_jpy"],
        "pc_target_jpy": budget["pc_target_jpy"],
        "pc_planned_cap_jpy": budget["pc_budget_jpy"],
        "black_friday_pc_price_cap_jpy": bf_cap,
        "black_friday_pc_price_cap_final": bool(in_bf_window and budget_ready),
        "current_live_pc_budget_cap_reference_jpy": live_cap,
        "rows": rows,
        "score_policy_note": strategy.get("score_policy", "Actual scores are evidence-derived; no target score is hardcoded."),
        "price_semantics_note": "BF目標額と実際に観測した価格は別フィールド。BF期間外の価格は参考値であり、BF実売価格として扱いません。",
    }


def read_events():
    path = os.path.join(ROOT, "data", "change_events.jsonl")
    events = []
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events

def build_products(latest, catalog):
    live = {str(x.get("id")): x for x in latest.get("products", []) if x.get("id")}
    out = []

    for cid, cat in catalog.items():
        if cid in live:
            out.append(live[cid])
            continue
        out.append({
            "id": cid,
            "url": cat.get("url"),
            "name": cat.get("name"),
            "family": cat.get("family"),
            "form_factor": cat.get("form_factor", "unknown"),
            "stock_status": cat.get("stock_status", "unknown"),
            "current_price_jpy": None,
            "last_valid_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
            "reference_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
            "price_source_mode": "public_baseline",
            "price_validation_status": "reference_only",
            "data_confidence": "low",
            "spec": {k: cat.get(k) for k in ("gpu","cpu","tgp_w","ram_gb","ssd","vram_gb") if cat.get(k) not in (None, "")},
            "variant_match": "trusted_url" if cat.get("url_is_exact") else "ambiguous",
        })

    for cid, item in live.items():
        if cid in catalog:
            continue
        dynamic = dict(item)
        dynamic["dynamic_candidate"] = True
        dynamic.setdefault("variant_match", "ambiguous")
        dynamic.setdefault("data_confidence", "medium" if dynamic.get("current_price_jpy") is not None else "low")
        out.append(dynamic)

    return out

def main():
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    latest = load_json(latest_path, {"products": []})
    anchors = load_anchors()
    catalog = load_catalog()
    events = read_events()
    budget = purchase_budget_policy()
    peripheral_projection = peripheral_budget_projection()
    target_config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    strategy_config = target_config.get("purchase_strategy") or {}

    source_snapshot_generated_at = latest.get("generated_at")
    source_snapshot_sha256 = file_sha256(latest_path) if os.path.exists(latest_path) else None

    products = build_products(latest, catalog)
    generated = iso(now_jst())
    watch = load_json(os.path.join(ROOT, "data", "watchlist.json"), {"urls": []})
    priority_by_id = {
        str(x.get("id")): str(x.get("priority") or "normal").lower()
        for x in (watch.get("urls") or [])
        if isinstance(x, dict) and x.get("id")
    }
    scored = []
    reference_only = []

    for product in products:
        row = build_row(product, anchors, events, prediction_time=generated)
        row["cash_total_cost_jpy"] = cash_total_cost(product)
        row["confirmed_benefit_value_jpy"] = confirmed_benefit_value(product)
        row["effective_cost_jpy"] = effective_cost(product)
        row["noncash_benefit_value_jpy"] = noncash_benefit_value_jpy(product)
        row["value_equivalent_cost_jpy"] = value_equivalent_cost(product)
        row["benefit_confidence"] = product.get("benefit_confidence")
        row["purchase_url"] = sales_url(product)
        row["source_snapshot_generated_at"] = source_snapshot_generated_at
        row["source_snapshot_sha256"] = source_snapshot_sha256
        if row.get("decision_score") is None:
            reference_only.append(suppress_current_price(row))
        else:
            scored.append(row)

    # Never let an out-of-stock product become the purchase recommendation.
    available = [x for x in scored if x.get("stock_status") != "out_of_stock"]
    unavailable = [x for x in scored if x.get("stock_status") == "out_of_stock"]
    available.sort(key=lambda x: (
        -x.get("decision_score", -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        x.get("id", ""),
    ))
    unavailable.sort(key=lambda x: (
        -x.get("decision_score", -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        x.get("id", ""),
    ))
    for i, row in enumerate(available, 1):
        row["rank"] = i
    for row in unavailable:
        row["rank"] = None

    scored = available
    action = scored[0] if scored else None

    partition = scored + unavailable + reference_only
    purchase_strategy_status = build_purchase_strategy_status(
        partition, strategy_config, budget, peripheral_projection
    )
    critical_ids = [cid for cid, priority in priority_by_id.items() if priority == "critical"]
    by_id = {str(x.get("id")): x for x in partition if x.get("id")}
    critical_unverified = [
        cid for cid in critical_ids
        if not (
            by_id.get(cid, {}).get("current_price_jpy") is not None
            and by_id.get(cid, {}).get("price_source_mode") == "direct_structured"
            and by_id.get(cid, {}).get("variant_match") in ("exact", "trusted_url", "strong")
            and by_id.get(cid, {}).get("stock_status") in ("in_stock", "low_stock", "out_of_stock")
        )
    ]
    coverage_status = "COMPLETE" if not critical_unverified else "PARTIAL"
    purchase_gate_allowed = bool(
        action
        and coverage_status == "COMPLETE"
        and peripheral_projection.get("budget_data_ready")
        and action.get("score_detail", {}).get("status") in ("BUY_NOW", "BUY_NOW_LOW_STOCK", "BUY_NOW_NEAR_BUDGET")
        and action.get("effective_cost_jpy") is not None
        and action.get("effective_cost_jpy") <= peripheral_projection.get("pc_dynamic_cap_jpy", 0)
    )

    quality = {
        "candidate_count": len(partition),
        "critical_candidate_count": len(critical_ids),
        "critical_unverified_count": len(critical_unverified),
        "coverage_status": coverage_status,
        "actionable_count": len(scored),
        "reference_only_count": len(reference_only),
        "dynamic_candidate_count": sum(1 for x in partition if x.get("dynamic_candidate")),
        "direct_verified": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
        ),
        "search_verified": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") == "search_snippet"
        ),
        "anomaly_rejected": sum(
            1 for x in partition if x.get("price_validation_status") == "anomaly_rejected"
        ),
        "variant_ambiguous": sum(
            1 for x in partition if x.get("variant_match") == "ambiguous"
        ),
        "unknown_stock": sum(
            1 for x in partition if x.get("stock_status") == "unknown"
        ),
        "out_of_stock": sum(
            1 for x in partition if x.get("stock_status") == "out_of_stock"
        ),
        "pit_unknown": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None and not x.get("available_at")
        ),
        "pit_failures": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("available_at")
            and x.get("prediction_time")
            and not x.get("pit_valid", False)
        ),
    }

    out = {
        "generated_at": generated,
        "prediction_time": generated,
        "source_snapshot_generated_at": source_snapshot_generated_at,
        "source_snapshot_sha256": source_snapshot_sha256,
        "budget_jpy": BUDGET,
        "budget_scope": "pc_only_excluding_peripherals",
        "total_budget_jpy": budget["total_budget_jpy"],
        "peripheral_budget_jpy": budget["peripheral_budget_jpy"],
        "pc_target_jpy": budget["pc_target_jpy"],
        "pc_budget_jpy": budget["pc_budget_jpy"],
        "dynamic_pc_cap_jpy": peripheral_projection["pc_dynamic_cap_jpy"],
        "peripheral_projection_jpy": peripheral_projection["peripheral_projection_jpy"],
        "peripheral_budget_data_ready": peripheral_projection["budget_data_ready"],
        "peripheral_prices_unverified_ids": peripheral_projection["tracked_peripheral_unverified_ids"],
        "peripherals": peripheral_projection["peripherals"],
        "effective_budget_jpy": BUDGET,
        "effective_soft_max_jpy": EFFECTIVE_SOFT_MAX,
        "effective_hard_max_jpy": EFFECTIVE_HARD_MAX,
        "season_phase": __import__("intelligence").season_phase(),
        "purchase_gate": {
            "allowed": purchase_gate_allowed,
            "coverage_status": coverage_status,
            "critical_unverified_ids": critical_unverified,
            "reason": (
                "critical_candidates_not_fully_verified" if critical_unverified else
                "peripheral_prices_or_availability_unverified" if not peripheral_projection.get("budget_data_ready") else
                "all_in_cost_exceeds_total_budget" if action and action.get("effective_cost_jpy", 10**12) > peripheral_projection.get("pc_dynamic_cap_jpy", 0) else
                "no_buy_now_candidate" if not purchase_gate_allowed else
                "all_critical_and_peripheral_candidates_verified"
            ),
        },
        "top_recommendation": {
            "id": action.get("id") if action else None,
            "name": action.get("name") if action else None,
            "decision_score": action.get("decision_score") if action else None,
            "status": action.get("score_detail", {}).get("status") if action else "NO_VERIFIED_CANDIDATE",
            "purchase_url": sales_url(action) if action else None,
        },
        "quality": quality,
        "coverage": latest.get("coverage") or {},
        "products": scored,
        "unavailable_products": unavailable,
        "reference_only": reference_only,
        "purchase_strategy": purchase_strategy_status,
        "method": {
            "total": 100,
            "performance_max": 40,
            "price_max": 20,
            "historical_evidence_max": 15,
            "stock_max": 15,
            "timing_max": 10,
            "note": "100点は購入判断の優先度であり、確率ではない。未確認情報はscore capまたはランキング除外で安全側に処理する。",
        }
    }
    save_json(os.path.join(ROOT, "data", "decision_rankings.json"), out)

    fetch_stats = latest.get("fetch_stats") or {}
    error_breakdown = fetch_stats.get("errors_by_host_reason") or {}
    error_breakdown_text = ", ".join(
        "{}={}".format(k, v) for k, v in sorted(error_breakdown.items())
    ) or "なし"

    lines = [
        "# ブラックフライデー期間通算・購入ランキング",
        "",
        f"更新: {generated}",
        f"観測スナップショット: {source_snapshot_generated_at or '未確認'}",
        f"観測スナップショットSHA256: {source_snapshot_sha256 or '未確認'}",
        f"総予算（PC＋周辺機器）: ¥{budget['total_budget_jpy']:,}",
        f"周辺機器の目標予算: ¥{budget['peripheral_budget_jpy']:,}",
        f"PC本体の目標価格: ¥{budget['pc_target_jpy']:,}",
        f"PC本体の計画上限（周辺機器が目標価格の場合）: ¥{budget['pc_budget_jpy']:,}",
        f"PC本体の動的上限（追跡した周辺機器の実売を反映）: ¥{peripheral_projection['pc_dynamic_cap_jpy']:,}",
        f"周辺機器の現行/目標価格ベース試算: ¥{peripheral_projection['peripheral_projection_jpy']:,}",
        f"周辺機器の価格・在庫確認: {peripheral_projection['tracked_peripheral_verified_count']}/{peripheral_projection['tracked_peripheral_count']}",
        f"全体購入許可: **{'許可' if purchase_gate_allowed else '保留'}**（{out['purchase_gate']['reason']}）",
        f"フェーズ: **{out['season_phase']}**",
        "",
    ]

    if action:
        d = action["score_detail"]
        price = action["current_price_jpy"]
        lines += [
            "## 現時点の最優先候補",
            "",
            f"**1位: [{action.get('form_factor','unknown')}] {action.get('name','')} — {action['decision_score']}/100**",
            f"- 現在価格: ¥{price:,}",
            f"- 必須費用込み現金総額: ¥{action.get('cash_total_cost_jpy'):,}" if action.get("cash_total_cost_jpy") is not None else "- 必須費用込み現金総額: 未確認",
            f"- 確定特典価値: ¥{action.get('confirmed_benefit_value_jpy', 0):,}",
            f"- 実質コスト（PC単体）: ¥{action.get('effective_cost_jpy'):,}" if action.get("effective_cost_jpy") is not None else "- 実質コスト（PC単体）: 未確認",
            (
                f"- PC＋周辺機器の参考試算総額（構成変更費未含む）: ¥{(action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']:,}"
                if action.get("effective_cost_jpy") is not None and not d.get("configuration_ready")
                else f"- PC＋周辺機器の試算総額: ¥{(action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']:,}"
                if action.get("effective_cost_jpy") is not None
                else "- PC＋周辺機器の試算総額: 未確認"
            ),
            (
                f"- 参考残額（構成変更費未含む）: ¥{budget['total_budget_jpy'] - ((action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']):,}"
                if action.get("effective_cost_jpy") is not None and not d.get("configuration_ready")
                else f"- 総予算の残額（試算）: ¥{budget['total_budget_jpy'] - ((action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']):,}"
                if action.get("effective_cost_jpy") is not None
                else "- 総予算の残額: 未確認"
            ),
            f"- PC構成要件: {'達成' if d.get('configuration_ready') else '未達/未確認 (' + ', '.join(d.get('configuration_reasons') or []) + ')'}",
            f"- 参考総価値換算額: ¥{action.get('value_equivalent_cost_jpy'):,}（購入許可には不使用）" if action.get("value_equivalent_cost_jpy") is not None else "- 参考総価値換算額: 未確認",
            f"- 判定: **{d['status']}**",
            (f"- 購入リンク: [販売ページ]({sales_url(action)})" if sales_url(action) else "- 購入リンク: 未確認"),
            f"- 買い判断: {d['reason']}",
            f"- 待つリスク: **{d['wait_risk']}**",
            f"- PC目標価格まで必要値下げ: {d['required_effective_discount_pct']:.1f}%" if d.get("required_effective_discount_pct") is not None else "- PC目標価格まで必要値下げ: 未算出（完成構成の価格・変更費用が未確認）" if not d.get("configuration_ready") else "- PC目標価格まで必要値下げ: 未確認",
            f"- 構成判定: **{d.get('variant_match')}**",
            f"- 価格情報: **{d.get('price_source_mode')} / {d.get('data_confidence')}**",
            "",
        ]
    else:
        lines += [
            "## 現時点の最優先候補",
            "",
            "**購入判断に使える現行価格が未確認です。**",
            "価格取得失敗・構成不一致・異常価格は安全側に除外しています。",
            "",
        ]

    lines += [
        "## 37万円・ブラックフライデー購入目標の監視",
        "",
        f"- 価格フェーズ: **{purchase_strategy_status['pricing_phase']}**",
        "- 以下のBF購入目標価格は開催期間の目標。開催前の表示価格は参考であり、BF価格の確定値ではありません。",
        f"- BF期間: {purchase_strategy_status['black_friday_window_start_jst']} ～ {purchase_strategy_status['black_friday_window_end_jst']}",
        f"- BF本体計画上限: ¥{purchase_strategy_status['pc_planned_cap_jpy']:,}",
        f"- BF本体上限（BF期間中の周辺機器価格を反映）: ¥{purchase_strategy_status['black_friday_pc_price_cap_jpy']:,}"
        + ("（確定）" if purchase_strategy_status["black_friday_pc_price_cap_final"] else "（目標予算からの計画値。BF実売ではない）"),
        "- BF期間外の観測価格は参考値。BF価格としてカウントしません。",
        "",
        "|優先方針|BF購入目標価格|BF期間内の確認済み価格|BF前の参考価格|判定|必要条件・値下げ額|",
        "|---|---:|---:|---:|---|---|",
        *[
            f"|{r['label']}|"
            f"{('¥'+format(r['black_friday_target_price_jpy'],',')) if r.get('black_friday_target_price_jpy') is not None else '動的上限'}|"
            f"{('¥'+format(r['black_friday_price_observed_jpy'],',')) if r.get('black_friday_offer_verified') and r.get('black_friday_price_observed_jpy') is not None else '未確認'}|"
            f"{('¥'+format(r['pre_black_friday_reference_price_jpy'],',')) if r.get('pre_black_friday_reference_price_jpy') is not None else '—'}|"
            f"**{r['status']}**|{r.get('detail','')}|"
            for r in purchase_strategy_status["rows"]
        ],
        "",
        purchase_strategy_status["score_policy_note"],
        "",
        "## 周辺機器の価格監視（サブモニター・ヘッドセットなし）",
        "",
        "|項目|BF購入目標価格|観測価格（BF前は参考）|在庫|価格確認|購入ページ|",
        "|---|---:|---:|---|---|---|",
        *[
            f"|{p['name']}|¥{p['target_price_jpy']:,}|{('¥'+format(p['current_price_jpy'],',')) if p.get('current_price_jpy') is not None else '—（目標額で仮計算）'}|{p.get('stock_status','unknown')}|{('確認済み' if p.get('price_verified') else '未確認')}|{('[商品ページ]('+p['purchase_url']+')') if p.get('purchase_url') else '予算枠のみ'}|"
            for p in peripheral_projection["peripherals"]
        ],
        "",
        f"周辺機器価格確認: {peripheral_projection['tracked_peripheral_verified_count']}/{peripheral_projection['tracked_peripheral_count']}。未確認項目は目標額を試算に使用し、全体購入許可を保留します。",
        "",
        "## 100点ランキング",
        "",
        "|順位|タイプ|商品|観測価格（BF前は参考）|現金総額|確定現金特典|実質コスト|非現金価値|価値加点|PC目標まで|性能|価格価値|過去根拠|在庫|時期|総合|判定|購入リンク|",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in scored[:20]:
        d = row["score_detail"]
        lines.append(
            f"|{row['rank']}|{row.get('form_factor','unknown')}|{row.get('name','')[:55]}|¥{row['current_price_jpy']:,}|"
            f"¥{row.get('cash_total_cost_jpy'):,}|¥{row.get('confirmed_benefit_value_jpy', 0):,}|¥{row.get('effective_cost_jpy'):,}|"
            f"¥{row.get('noncash_benefit_value_jpy', 0):,}|+{d.get('value_bonus', 0)}|"
            f"{(format(d['required_effective_discount_pct'], '.1f') + '%') if d.get('required_effective_discount_pct') is not None else '未算出'}|"
            f"{d['performance']}/40|{d['price']}/20|"
            f"{d['history']}/15|{d['stock']}/15|{d['timing']}/10|"
            f"**{row['decision_score']}/100**|{d['status']}|"
            + (f"[販売ページ]({sales_url(row)})" if sales_url(row) else "未確認")
            + "|"
        )

    lines += [
        "",
        "## データ品質",
        "",
        f"- 候補総数: {quality['candidate_count']}",
        f"- デスクトップ候補: {sum(1 for x in products if x.get('form_factor') == 'desktop')}",
        f"- ノート候補: {sum(1 for x in products if x.get('form_factor') == 'laptop')}",
        f"- PC本体の目標価格: ¥{BUDGET:,}",
        f"- 実質ソフト上限: ¥{EFFECTIVE_SOFT_MAX:,}",
        f"- 実質ハード上限: ¥{EFFECTIVE_HARD_MAX:,}",
        f"- 重要候補: {quality['critical_candidate_count']}",
        f"- 重要候補の未確認: {quality['critical_unverified_count']}",
        f"- カバレッジ: {quality['coverage_status']}",
        f"- 現行価格を使える候補: {quality['actionable_count']}",
        f"- 参照情報のみ: {quality['reference_only_count']}",
        f"- 自動発見候補: {quality['dynamic_candidate_count']}",
        f"- 直接確認: {quality['direct_verified']}",
        f"- 検索補完: {quality['search_verified']}",
        f"- 異常価格棄却: {quality['anomaly_rejected']}",
        f"- 構成不明: {quality['variant_ambiguous']}",
        f"- 在庫不明: {quality['unknown_stock']}",
        f"- 売り切れ確認: {quality['out_of_stock']}",
        f"- PIT失敗: {quality['pit_failures']}",
        f"- 処理対象: {(latest.get('coverage') or {}).get('processed_count', len(products))} / {(latest.get('coverage') or {}).get('watchlist_count', len(products))}",
        f"- 処理率: {(latest.get('coverage') or {}).get('processing_rate_pct', 100.0):.1f}%",
        f"- 取得成功率: {(latest.get('coverage') or {}).get('transport_success_rate_pct', 0.0):.1f}%",
        f"- 価格確認率: {(latest.get('coverage') or {}).get('price_verified_rate_pct', 0.0):.1f}%",
        f"- 検索補完（成功/試行）: {fetch_stats.get('search_fallback_successes', 0)}/{fetch_stats.get('search_fallback_attempts', 0)}",
        f"- 検索SKU不一致による除外: {fetch_stats.get('search_identity_rejections', 0)}",
        f"- 取得エラー内訳（host|reason）: {error_breakdown_text}",
        f"- 未処理候補: {', '.join((latest.get('coverage') or {}).get('skipped_ids', [])) or 'なし'}",
        "",
        "## 価格シナリオ",
        "",
    ]

    for row in scored[:10]:
        price = row["current_price_jpy"]
        scenarios = scenario_prices(price)
        first = next((x for x in scenarios if x["price_jpy"] <= BUDGET), None)
        lines.append(f"### {row['rank']}. {row.get('name','')}")
        lines.append(
            " / ".join(f"{x['discount_pct']}%→¥{x['price_jpy']:,}" for x in scenarios)
            + (f" / PC目標価格到達→{first['discount_pct']}%" if first else " / 30%でもPC目標価格未到達")
        )
        lines.append("")

    lines += [
        "## 判定ルール",
        "",
        "- BUY_NOW: PC本体の実質コストが、現在の周辺機器予算を反映した動的上限以下で、構成・在庫・データ品質を通過。",
        "- BUY_NOW_NEAR_BUDGET: 動的上限付近でも、性能・在庫・構成一致・データ品質が特に強い場合だけ許可。",
        "- BUY_NOW_LOW_STOCK: PC本体の動的上限内かつ低在庫。最安値待ちを避ける。",
        "- NEEDS_CONFIGURATION: RAM32GBまたはSSD1TBを満たさない基本構成。変更後価格が確認できるまで購入不可。",
        "- STRONG_WATCH: 未到達でも性能・価格距離・過去根拠が強い。",
        "- VALUE_WATCH: PC本体の上限超でも、高性能候補として値下げを監視。購入許可ではない。",
        "- WAIT_FOR_DISCOUNT: 大幅値下げ待ち。",
        "- VERIFY_NOW: 検索補完など。購入前に販売ページで再確認。",
        "- UNACTIONABLE: 現行価格を確認できない、または異常値・構成不一致。",
        "",
        "## Fail-closedルール",
        "",
        "- 取得失敗は売り切れではない。",
        "- 月額、分割、ポイント等の数字を販売価格として採用しない。",
        "- 一般的な「X円OFF」は表示価格に既に反映済みの可能性があるため、実質コストから二重控除しない。",
        "- 追加クーポン/カート値引きだけを confirmed cash benefit として実質コストに反映する。",
        "- モニター等の周辺機器価値、無料アップグレード、保証延長は実質コストから控除せず、別の価値加点・参考総価値換算として扱う。",
        "- 異常な激安価格は独立確認なしでは採用しない。",
        "- 参照価格は現在価格ではない。",
        "- 共有商品ページは exact variant とみなさない。",
        "- 過去価格は同一構成 > 同GPU同シリーズ > 同シリーズの順で証拠力を下げる。",
        "- PIT不明・違反データから購入判断を作らない。",
    ]

    os.makedirs(os.path.join(ROOT, "data", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "reports", "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
