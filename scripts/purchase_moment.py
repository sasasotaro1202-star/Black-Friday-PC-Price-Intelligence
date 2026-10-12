"""Season-aware purchase timing and stock-risk decision for the 2026 Black Friday window.

This module emits a current action, not a forecast of the exact future minimum.
It only authorizes BUY_NOW when price, completed configuration, stock, point-in-time
validity, BF-window observation, and all-in budget evidence are all satisfied.
"""
import json
import os
from datetime import timedelta

from intelligence import (
    ROOT, now_jst, iso, parse_dt, load_json, purchase_budget_policy,
    peripheral_budget_projection, actionable_max_age_minutes,
    configuration_readiness, history_match, performance_score,
)

APPROVED_PRICE_VALIDATION = {
    "validated", "validated_exact_model_page", "anomaly_corroborated"
}
APPROVED_VARIANTS = {"exact", "trusted_url", "strong"}
AVAILABLE_STOCK = {"in_stock", "low_stock"}


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return rows


def season_window(target_config):
    strategy = target_config.get("purchase_strategy") or {}
    semantics = strategy.get("price_semantics") or {}
    start = parse_dt(
        semantics.get("window_start_jst")
        or target_config.get("monitor_window_start")
    )
    end = parse_dt(
        semantics.get("window_end_jst")
        or target_config.get("monitor_window_end")
    )
    return start, end


def season_phase(now, start, end):
    if not start or not end:
        return "WINDOW_UNCONFIRMED", None
    if now < start:
        return "PRE_BF", max(0.0, (start - now).total_seconds() / 3600)
    if now > end:
        return "POST_BF", 0.0
    remaining_hours = max(0.0, (end - now).total_seconds() / 3600)
    total_hours = max(1.0, (end - start).total_seconds() / 3600)
    elapsed_hours = max(0.0, (now - start).total_seconds() / 3600)
    if remaining_hours <= 48:
        phase = "FINAL_48H"
    elif elapsed_hours <= min(72, total_hours * 0.15):
        phase = "EARLY_WINDOW"
    else:
        phase = "MID_WINDOW"
    return phase, remaining_hours


def trusted_live_price(item, now):
    price = item.get("current_price_jpy")
    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        return False, "price_missing_or_invalid", None
    if item.get("price_source_mode") != "direct_structured":
        return False, "not_direct_structured", None
    if item.get("price_validation_status") not in APPROVED_PRICE_VALIDATION:
        return False, "price_validation_not_approved", None
    if item.get("variant_match") not in APPROVED_VARIANTS:
        return False, "exact_variant_not_confirmed", None
    available = parse_dt(item.get("available_at"))
    retrieved = parse_dt(item.get("retrieval_time"))
    predicted = parse_dt(item.get("prediction_time"))
    if not available or not retrieved or not predicted:
        return False, "pit_timestamp_missing", None
    if available > retrieved or retrieved > predicted or predicted > now + timedelta(minutes=5):
        return False, "pit_order_invalid", None
    age_minutes = (predicted - retrieved).total_seconds() / 60.0
    max_age = actionable_max_age_minutes(predicted)
    if age_minutes < -1 or age_minutes > max_age:
        return False, "price_observation_stale", age_minutes
    return True, "verified_live_price", age_minutes


def item_price_history(candidate_id, events, start=None, end=None):
    observations = []
    for event in events:
        if str(event.get("id") or "") != str(candidate_id):
            continue
        if event.get("pit_valid") is False:
            continue
        if event.get("price_source_mode") not in (None, "direct_structured"):
            continue
        observed = parse_dt(event.get("observed_at") or event.get("retrieval_time"))
        if not observed:
            continue
        if start and observed < start:
            continue
        if end and observed > end:
            continue
        # Only the new/current price is assigned to the observation timestamp.
        # The old price may have been observed at an earlier, unknown time.
        price = event.get("new_price_jpy")
        if price is None:
            price = event.get("current_price_jpy")
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            continue
        observations.append({
            "observed_at": iso(observed),
            "price_jpy": price,
            "stock_status": event.get("stock_status"),
        })
    observations.sort(key=lambda x: x["observed_at"])
    return observations


def historical_sellout_signal(item, anchors):
    for anchor in anchors:
        try:
            if history_match(item, anchor) and (
                anchor.get("historical_sellout")
                or "売り切れ" in str(anchor.get("historical_note") or "")
                or "sold out" in str(anchor.get("historical_note") or "").lower()
            ):
                return True, anchor
        except Exception:
            continue
    return False, None


def stock_risk(item, phase, anchors):
    stock = item.get("stock_status", "unknown")
    if stock == "out_of_stock":
        return "UNAVAILABLE", "商品ページで在庫切れを確認"
    if stock == "low_stock":
        return "HIGH_OBSERVED", "商品ページで低在庫を確認。価格条件を満たすなら待つリスクが高い"
    if stock in ("unknown", None, ""):
        return "UNKNOWN", "在庫を直接確認できていない。取得失敗は売り切れを意味しない"
    sold_out, anchor = historical_sellout_signal(item, anchors)
    if sold_out:
        return "MEDIUM_HISTORY", (
            "同系統・同モデルの過去セールに売り切れ記録あり。今回の在庫切れ確率を示すものではない"
        )
    if phase == "FINAL_48H":
        return "TIME_LIMITED", "セール終了まで48時間以内。終了リスクと在庫切れリスクは別に扱う"
    if stock == "in_stock":
        return "NO_CURRENT_SIGNAL", "現時点で低在庫の直接シグナルなし。売り切れない保証ではない"
    return "UNKNOWN", "在庫状況を要確認"


def target_for_item(item, strategy, policy):
    candidate_id = str(item.get("id") or "")
    for plan in strategy.get("priority_plans") or []:
        if str(plan.get("candidate_id") or "") == candidate_id:
            return int(plan.get("black_friday_target_price_jpy") or policy["pc_target_jpy"])
    outlier = strategy.get("outlier_rule") or {}
    gpu = str((item.get("spec") or {}).get("gpu") or item.get("gpu") or "").lower()
    form_factor = item.get("form_factor") or (item.get("spec") or {}).get("form_factor")
    if form_factor == "desktop" and "5070 ti" in gpu:
        return int(outlier.get("black_friday_target_cap_jpy") or policy["pc_target_jpy"])
    return int(policy["pc_target_jpy"])


def score_moment(item, price, target, phase, history, trusted):
    # Score components sum to 100. This is purchase-timing priority, not a
    # probability that the price will fall or that the item will sell out.
    if price <= target:
        price_points = min(40, 30 + int(10 * max(0, target - price) / max(1, target)))
    else:
        over_pct = 100.0 * (price - target) / max(1, target)
        price_points = max(0, 30 - int(over_pct * 2.0))

    observations = [x["price_jpy"] for x in history]
    distinct = len(set(observations))
    if len(observations) >= 5 and distinct >= 3 and price <= min(observations):
        history_points = 20
    elif len(observations) >= 3 and distinct >= 2 and price <= min(observations):
        history_points = 16
    elif len(observations) >= 3 and distinct >= 2 and price <= min(observations) * 1.02:
        history_points = 13
    elif len(observations) >= 3 and distinct >= 2:
        history_points = 7
    else:
        history_points = 0

    stock = item.get("stock_status", "unknown")
    stock_points = {
        "low_stock": 20, "in_stock": 12, "preorder_or_backorder": 3,
        "unknown": 2, "out_of_stock": 0,
    }.get(stock, 2)
    timing_points = {
        "FINAL_48H": 10, "MID_WINDOW": 6, "EARLY_WINDOW": 4,
    }.get(phase, 0)
    data_points = 10 if trusted else 0
    score = max(0, min(100, price_points + history_points + stock_points + timing_points + data_points))
    return {
        "score_100": score,
        "components": {
            "price_vs_target": price_points,
            "observed_bf_price_history": history_points,
            "observed_stock_signal": stock_points,
            "sale_window_timing": timing_points,
            "live_data_quality": data_points,
        },
        "bf_observation_count": len(observations),
        "bf_distinct_price_count": distinct,
        "bf_observed_min_jpy": min(observations) if observations else None,
        "history_evidence": (
            "MEDIUM" if len(observations) >= 3 and distinct >= 2
            else "LOW"
        ),
        "score_note": "購入タイミングの優先度スコア。値下がり確率・売り切れ確率ではない。",
    }


def evaluate_candidate(item, catalog_item, events, anchors, start, end, now, phase, policy, projection, strategy):
    candidate_id = str(item.get("id") or "")
    price = item.get("current_price_jpy")
    trusted, trust_reason, age_minutes = trusted_live_price(item, now)
    retrieved = parse_dt(item.get("retrieval_time"))
    observed_in_bf = bool(
        trusted and retrieved and start and end and start <= retrieved <= end
    )
    stock = item.get("stock_status", "unknown")
    ready, config_reasons = configuration_readiness(item)
    target = target_for_item(item, strategy, policy)
    dynamic_cap = int(projection.get("pc_dynamic_cap_jpy") or 0)
    budget_ready = bool(projection.get("budget_data_ready"))
    form = item.get("form_factor") or (item.get("spec") or {}).get("form_factor") or "unknown"
    history = item_price_history(candidate_id, events, start if phase not in ("PRE_BF", "POST_BF") else None,
                                 end if phase not in ("PRE_BF", "POST_BF") else None)
    risk, risk_reason = stock_risk(item, phase, anchors)
    sellout, sellout_anchor = historical_sellout_signal(item, anchors)
    price_ok = trusted and isinstance(price, int) and price <= dynamic_cap and dynamic_cap > 0
    stock_ok = stock in AVAILABLE_STOCK
    candidate_action = "PRE_BF_REFERENCE_ONLY"
    reasons = []

    if phase == "POST_BF":
        candidate_action = "SEASON_ENDED"
        reasons.append("設定されたBF監視窓は終了")
    elif phase == "PRE_BF":
        candidate_action = "PRE_BF_REFERENCE_ONLY"
        reasons.append("現行価格はセール前参考値。2026年BF実売価格とは扱わない")
    elif not trusted:
        candidate_action = "VERIFY_PRICE_FIRST"
        reasons.append(f"価格/PIT確認不可: {trust_reason}")
    elif stock == "out_of_stock":
        candidate_action = "SOLD_OUT"
        reasons.append("有効な新しい観測で在庫切れを確認")
    elif not observed_in_bf:
        candidate_action = "VERIFY_BF_OFFER"
        reasons.append("BF期間内に取得した価格ではない")
    elif not ready:
        candidate_action = "CONFIGURATION_REQUIRED"
        reasons.extend(config_reasons or ["32GB RAM・1TB SSDの完成構成を確認できない"])
    elif not stock_ok:
        candidate_action = "VERIFY_STOCK_FIRST"
        reasons.append("在庫を直接確認できない")
    elif not price_ok:
        candidate_action = "WAIT_FOR_BUDGET_PRICE"
        reasons.append(
            f"PC価格が動的上限¥{dynamic_cap:,}を超過"
            if dynamic_cap > 0 else "PC本体の動的上限を確定できない"
        )
    else:
        candidate_action = "CONDITIONAL_BUY_NOW" if not budget_ready else "BUY_NOW"
        reasons.append(f"BF期間内の価格¥{price:,}、完成構成、在庫は確認済み")
        reasons.append(f"PC本体の動的上限¥{dynamic_cap:,}以内")
        if not budget_ready:
            reasons.append("周辺機器の全価格・在庫が確定していないため、総額確認後に購入")
        elif stock == "low_stock":
            reasons.append("低在庫。さらに値下がりする保証はなく、在庫確保を優先")
        else:
            reasons.append("総額ゲートを通過。現時点で購入してよい条件")

    moment = score_moment(item, price if isinstance(price, int) else 0, target, phase, history, trusted)
    performance = None
    try:
        performance = (item.get("score_detail") or {}).get("performance")
        if performance is None:
            performance = performance_score(item)[0]
    except Exception:
        performance = None
    try:
        existing_score = int(item.get("decision_score"))
    except (TypeError, ValueError):
        existing_score = 0
    # Only eligible/near-eligible completed builds are ultimately actionable;
    # this combined score is a tie-breaker, not a replacement for safety gates.
    combined = round(0.6 * existing_score + 0.4 * moment["score_100"])
    if form == "desktop" and policy.get("desktop_preferred"):
        combined = min(100, combined + 3)

    return {
        "id": candidate_id,
        "name": item.get("name") or catalog_item.get("name") or candidate_id,
        "url": item.get("purchase_url") or item.get("url") or catalog_item.get("url"),
        "form_factor": form,
        "gpu": (item.get("spec") or {}).get("gpu") or item.get("gpu"),
        "cpu": (item.get("spec") or {}).get("cpu") or item.get("cpu"),
        "price_jpy": price if isinstance(price, int) else None,
        "target_price_jpy": target,
        "dynamic_pc_cap_jpy": dynamic_cap,
        "gap_to_dynamic_cap_jpy": max(0, price - dynamic_cap) if isinstance(price, int) and dynamic_cap else None,
        "stock_status": stock,
        "stock_risk": risk,
        "stock_risk_reason": risk_reason,
        "historical_sellout_signal": sellout,
        "historical_sellout_reference": (sellout_anchor or {}).get("source") if sellout_anchor else None,
        "price_verified": trusted,
        "price_trust_reason": trust_reason,
        "observation_age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "black_friday_price_verified": observed_in_bf,
        "configuration_ready": ready,
        "configuration_reasons": config_reasons,
        "all_in_budget_data_ready": budget_ready,
        "candidate_action": candidate_action,
        "reasons": reasons,
        "moment_priority": moment,
        "existing_decision_score": existing_score,
        "performance_score": performance,
        "combined_priority_score_100": combined,
        "price_history_sample_count": len(history),
        "price_history_distinct_values": len(set(x["price_jpy"] for x in history)),
    }


def build_decision(now, target_config, rankings, catalog_data, events, anchors, projection):
    policy = purchase_budget_policy()
    strategy = target_config.get("purchase_strategy") or {}
    start, end = season_window(target_config)
    phase, hours_remaining = season_phase(now, start, end)
    catalog = {
        str(x.get("id")): x
        for x in (catalog_data.get("candidates") or [])
        if x.get("id")
    }
    rows = []
    products = rankings.get("products") or []
    for item in products:
        candidate_id = str(item.get("id") or "")
        if not candidate_id:
            continue
        rows.append(evaluate_candidate(
            item, catalog.get(candidate_id, {}), events, anchors, start, end,
            now, phase, policy, projection, strategy
        ))

    buy_now = [x for x in rows if x["candidate_action"] == "BUY_NOW"]
    conditional = [x for x in rows if x["candidate_action"] == "CONDITIONAL_BUY_NOW"]
    near_candidates = [
        x for x in rows if x["candidate_action"] in (
            "VERIFY_PRICE_FIRST", "VERIFY_BF_OFFER", "VERIFY_STOCK_FIRST",
            "CONFIGURATION_REQUIRED", "WAIT_FOR_BUDGET_PRICE",
        )
    ]
    sort_key = lambda x: (
        x["combined_priority_score_100"],
        x["moment_priority"]["score_100"],
        x["performance_score"] or 0,
    )
    buy_now.sort(key=sort_key, reverse=True)
    conditional.sort(key=sort_key, reverse=True)
    near_candidates.sort(key=sort_key, reverse=True)

    if phase == "PRE_BF":
        action = "MONITOR_PRE_BF"
        label = "セール開始まで監視"
        reason = "現在はBF監視窓の前です。事前価格と2026年BF実売価格を混同せず、価格・在庫の基準値を蓄積します。"
    elif phase == "POST_BF":
        action = "SEASON_ENDED"
        label = "設定したセール期間は終了"
        reason = "設定された監視窓が終了しています。新しい公式日程が確認された場合は設定を更新します。"
    elif buy_now:
        action = "BUY_NOW"
        label = "今買うべき候補あり"
        reason = "完成構成・BF期間内の直接価格・在庫・PIT・周辺機器込み総額の購入ゲートを満たす候補があります。"
    elif conditional:
        action = "VERIFY_BUNDLE_THEN_BUY"
        label = "PC価格は買い条件。総額を先に確定"
        reason = "PC本体は完成構成・BF価格・在庫・動的上限を満たしますが、周辺機器の価格/在庫が未確定です。カートの最終現金支払総額を確認するまで購入許可は保留です。"
    elif near_candidates:
        action = "VERIFY_FIRST"
        label = "価格・構成・在庫の再確認が先"
        reason = "今は購入条件の一部が未確認、構成要件未達、または動的予算上限超過です。低在庫だけを理由に上限超過商品を買う判断はしません。"
    else:
        action = "WAIT_FOR_TARGET"
        label = "目標条件を満たす候補なし"
        reason = "確認済みの完成構成が購入条件に達していません。5分ごとの監視窓内で価格・在庫の変化を追います。"

    primary = buy_now[0] if buy_now else (conditional[0] if conditional else (near_candidates[0] if near_candidates else None))
    if primary and action in ("BUY_NOW", "VERIFY_BUNDLE_THEN_BUY"):
        timing_instruction = (
            "購入先の商品ページと最終カート総額を開き、値段・型番・在庫・RAM/SSDを再確認して購入"
            if action == "BUY_NOW"
            else "PCの価格・在庫は購入水準。まず周辺機器の最終現金支払額を確認し、総額40万円以内なら購入"
        )
    elif phase == "PRE_BF":
        timing_instruction = "BF開始前は監視を継続。現在の値段をBF実売価格として扱わない"
    elif primary and primary["stock_risk"] == "HIGH_OBSERVED":
        timing_instruction = "低在庫のシグナルはあるが、価格・構成・総額ゲートを満たすまでは急いで買わない"
    else:
        timing_instruction = "目標価格と総額条件を満たすまで待つ。最終日まで待てば安くなるという前提は置かない"

    return {
        "generated_at": iso(now),
        "prediction_time": iso(now),
        "season_window": {
            "start_jst": iso(start) if start else None,
            "end_jst": iso(end) if end else None,
            "phase": phase,
            "hours_remaining": round(hours_remaining, 1) if hours_remaining is not None else None,
            "within_window": phase in ("EARLY_WINDOW", "MID_WINDOW", "FINAL_48H"),
        },
        "budget": {
            "total_budget_jpy": policy["total_budget_jpy"],
            "peripheral_target_budget_jpy": policy["peripheral_budget_jpy"],
            "pc_target_jpy": policy["pc_target_jpy"],
            "pc_planned_cap_jpy": policy["pc_budget_jpy"],
            "pc_dynamic_cap_jpy": projection.get("pc_dynamic_cap_jpy"),
            "peripheral_projection_jpy": projection.get("peripheral_projection_jpy"),
            "all_in_budget_data_ready": bool(projection.get("budget_data_ready")),
            "unverified_peripheral_ids": projection.get("tracked_peripheral_unverified_ids", []),
            "budget_policy": "現金支払を基準にし、未確認クーポン/ポイントは値引き扱いしない",
        },
        "current_action": {
            "action": action,
            "label": label,
            "reason": reason,
            "instruction": timing_instruction,
            "should_buy_now": action == "BUY_NOW",
            "best_candidate_id": primary.get("id") if primary else None,
            "best_candidate_name": primary.get("name") if primary else None,
            "purchase_url": primary.get("url") if primary else None,
            "priority_score_100": primary.get("combined_priority_score_100") if primary else None,
            "conditional": action == "VERIFY_BUNDLE_THEN_BUY",
        },
        "counts": {
            "candidate_count": len(rows),
            "buy_now_count": len(buy_now),
            "conditional_buy_now_count": len(conditional),
            "needs_verification_or_wait_count": len(near_candidates),
        },
        "ranking": buy_now + conditional + near_candidates + [
            x for x in rows if x not in buy_now and x not in conditional and x not in near_candidates
        ],
        "methodology": {
            "stockout_probability_reported": False,
            "future_minimum_price_prediction_reported": False,
            "reason": "確認済みの現在価格・在庫・構成・過去観測だけを使う。サンプル不足なら統計的な最安時刻や確率を出さない。",
            "purchase_gate": [
                "直接取得の価格/型番/PITが有効で観測が新しい",
                "設定したBF期間内に実測された価格",
                "RAM 32GB以上・SSD 1TB以上の完成構成",
                "在庫がin_stockまたはlow_stock",
                "PC価格が周辺機器の実売/予算枠を反映した動的上限以内",
                "総額判定では未確認特典を値引き扱いしない",
            ],
        },
    }


def render_markdown(data):
    action = data["current_action"]
    season = data["season_window"]
    budget = data["budget"]
    lines = [
        "# 今この瞬間の購入判断",
        "",
        f"- 判定時刻（JST）: **{data['generated_at']}**",
        f"- セール局面: **{season['phase']}**",
        f"- セール終了まで: **{season['hours_remaining']}時間**" if season["hours_remaining"] is not None else "- セール期間: 未確認",
        f"- 総予算: **¥{budget['total_budget_jpy']:,}**",
        f"- PC動的上限: **¥{budget['pc_dynamic_cap_jpy']:,}**",
        f"- 周辺機器予算データ: **{'全件確認済み' if budget['all_in_budget_data_ready'] else '一部未確認'}**",
        "",
        f"## 判定: {action['label']}",
        "",
        action["reason"],
        "",
        f"**次の行動:** {action['instruction']}",
        "",
    ]
    if action.get("purchase_url"):
        lines.append(f"**第一候補:** [{action.get('best_candidate_name')}]({action['purchase_url']})")
        lines.append(f"**購入優先度スコア:** {action.get('priority_score_100')}/100（値下がり/売り切れ確率ではない）")
        lines.append("")
    lines += [
        "## 候補別の今すぐ判断",
        "",
        "|候補|判定|価格|BF目標|在庫|待機リスク|BF価格サンプル|優先度|リンク|理由|",
        "|---|---|---:|---:|---|---|---:|---:|---|---|",
    ]
    for row in data["ranking"][:20]:
        def money(value):
            return f"¥{value:,}" if isinstance(value, int) else "未確認"
        name = str(row.get("name") or row.get("id") or "").replace("|", "/")
        link = f"[商品ページ]({row['url']})" if row.get("url") else "リンク未確認"
        reasons = "；".join(row.get("reasons") or []).replace("|", "/")
        lines.append(
            f"|{name}|{row.get('candidate_action')}|{money(row.get('price_jpy'))}|"
            f"{money(row.get('target_price_jpy'))}|{row.get('stock_status')}|"
            f"{row.get('stock_risk')}|{row.get('price_history_sample_count', 0)}|"
            f"{row.get('moment_priority', {}).get('score_100', 0)}|{link}|{reasons}|"
        )
    lines += [
        "",
        "## 判断ルール",
        "",
        "- **買う:** セール期間内の実測価格、完成構成、在庫、PIT、PC動的上限が全て通り、周辺機器込みの予算データも確認済み。",
        "- **総額確認後に買う:** PC側の条件は満たすが、周辺機器の最終価格や在庫が未確認。税込み・送料込みの現金支払総額を確認する。",
        "- **待つ:** 目標/動的上限を超えている。セール終盤や低在庫だけを理由に上限超過を許可しない。",
        "- **確認する:** 価格、型番、RAM/SSD、在庫、取得時刻のいずれかが未確認。",
        "- 過去の観測数が少ない場合、最安時刻・将来価格・売り切れ確率を推定値として表示しない。",
        "- GitHub Actionsのscheduleは遅延する場合があるため、購入直前に必ず商品ページとカートで再確認する。",
    ]
    return "\n".join(lines) + "\n"


def main():
    now = now_jst()
    target_config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    catalog_data = load_json(os.path.join(ROOT, "config", "candidate_catalog.json"), {"candidates": []})
    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {"products": []})
    rankings = load_json(os.path.join(ROOT, "data", "decision_rankings.json"), {"products": []})
    events = read_jsonl(os.path.join(ROOT, "data", "change_events.jsonl"))
    anchors_data = load_json(os.path.join(ROOT, "config", "history_anchors.json"), {"anchors": []})
    projection = peripheral_budget_projection()
    decision = build_decision(
        now, target_config, rankings, catalog_data, events,
        anchors_data.get("anchors") or [], projection
    )
    # Keep the upstream snapshot timestamp visible for auditability.
    decision["source_snapshot_generated_at"] = latest.get("generated_at")
    decision["decision_rankings_generated_at"] = rankings.get("generated_at")
    markdown = render_markdown(decision)
    json_path = os.path.join(ROOT, "data", "purchase_moment.json")
    md_path = os.path.join(ROOT, "data", "reports", "purchase_moment.md")
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    tmp = json_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(decision, f, ensure_ascii=False, indent=2)
    os.replace(tmp, json_path)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    # The main report is regenerated immediately before this step in production,
    # so append exactly one fresh decision section per reporting cycle.
    latest_report = os.path.join(ROOT, "data", "reports", "latest.md")
    if os.path.exists(latest_report):
        with open(latest_report, "a", encoding="utf-8") as f:
            f.write("\n\n---\n\n" + markdown)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown)
    print(
        f"action={decision['current_action']['action']} "
        f"phase={decision['season_window']['phase']} "
        f"buy_now={decision['counts']['buy_now_count']} "
        f"conditional={decision['counts']['conditional_buy_now_count']} "
        f"all_in_ready={decision['budget']['all_in_budget_data_ready']}"
    )


if __name__ == "__main__":
    main()
