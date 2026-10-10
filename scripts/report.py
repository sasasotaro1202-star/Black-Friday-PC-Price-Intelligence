import hashlib
import json
import os

from intelligence import (
    ROOT, BUDGET, EFFECTIVE_SOFT_MAX, EFFECTIVE_HARD_MAX,
    load_json, save_json, load_catalog, load_anchors,
    build_row, cash_total_cost, confirmed_benefit_value, effective_cost, noncash_benefit_value_jpy, value_equivalent_cost,
    now_jst, iso, scenario_prices, purchase_budget_policy, peripheral_budget_projection
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
            f"- 実質コスト: ¥{action.get('effective_cost_jpy'):,}" if action.get("effective_cost_jpy") is not None else "- 実質コスト: 未確認",
            f"- 参考総価値換算額: ¥{action.get('value_equivalent_cost_jpy'):,}（購入許可には不使用）" if action.get("value_equivalent_cost_jpy") is not None else "- 参考総価値換算額: 未確認",
            f"- 判定: **{d['status']}**",
            (f"- 購入リンク: [販売ページ]({sales_url(action)})" if sales_url(action) else "- 購入リンク: 未確認"),
            f"- 買い判断: {d['reason']}",
            f"- 待つリスク: **{d['wait_risk']}**",
            f"- 実質28万円まで必要値下げ: {d['required_effective_discount_pct']:.1f}%" if d.get("required_effective_discount_pct") is not None else "- 実質28万円まで必要値下げ: 未確認",
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
        "## 100点ランキング",
        "",
        "|順位|タイプ|商品|現在価格|現金総額|確定現金特典|実質コスト|非現金価値|価値加点|28万円まで|性能|価格価値|過去根拠|在庫|時期|総合|判定|購入リンク|",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in scored[:20]:
        d = row["score_detail"]
        lines.append(
            f"|{row['rank']}|{row.get('form_factor','unknown')}|{row.get('name','')[:55]}|¥{row['current_price_jpy']:,}|"
            f"¥{row.get('cash_total_cost_jpy'):,}|¥{row.get('confirmed_benefit_value_jpy', 0):,}|¥{row.get('effective_cost_jpy'):,}|"
            f"¥{row.get('noncash_benefit_value_jpy', 0):,}|+{d.get('value_bonus', 0)}|"
            f"{d.get('required_effective_discount_pct', 0):.1f}%|"
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
        f"- 実質予算: ¥{BUDGET:,}",
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
            + (f" / 28万円到達→{first['discount_pct']}%" if first else " / 30%でも28万円未到達")
        )
        lines.append("")

    lines += [
        "## 判定ルール",
        "",
        "- BUY_NOW: 実質コスト28.5万円以下・購入可能・データ品質を通過。",
        "- BUY_NOW_NEAR_BUDGET: 実質28.5〜29.0万円でも、性能・在庫・データ品質が特に強い場合だけ許可。",
        "- BUY_NOW_LOW_STOCK: 実質予算内・低在庫。最安値待ちを避ける。",
        "- STRONG_WATCH: 未到達でも性能・価格距離・過去根拠が強い。",
        "- VALUE_WATCH: 29万円超でも、デスクトップの性能と確認済み周辺機器/構成特典が強い候補。購入許可ではなく値下げ監視対象。",
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
