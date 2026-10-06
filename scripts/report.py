import json
import os

from intelligence import (
    ROOT, BUDGET, load_json, save_json, load_catalog, load_anchors,
    build_row, now_jst, iso, scenario_prices
)

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
    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {"products": []})
    anchors = load_anchors()
    catalog = load_catalog()
    events = read_events()

    products = build_products(latest, catalog)
    generated = iso(now_jst())
    scored = []
    reference_only = []

    for product in products:
        row = build_row(product, anchors, events, prediction_time=generated)
        if row.get("decision_score") is None:
            reference_only.append(row)
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

    quality = {
        "candidate_count": len(products),
        "actionable_count": len(scored),
        "reference_only_count": len(reference_only),
        "dynamic_candidate_count": sum(1 for x in products if x.get("dynamic_candidate")),
        "direct_verified": sum(
            1 for x in products
            if x.get("current_price_jpy") is not None and
               x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
        ),
        "search_verified": sum(
            1 for x in products
            if x.get("current_price_jpy") is not None and x.get("price_source_mode") == "search_snippet"
        ),
        "anomaly_rejected": sum(1 for x in products if x.get("price_validation_status") == "anomaly_rejected"),
        "variant_ambiguous": sum(1 for x in products if x.get("variant_match") == "ambiguous"),
        "unknown_stock": sum(1 for x in products if x.get("stock_status") == "unknown"),
        "out_of_stock": sum(1 for x in products if x.get("stock_status") == "out_of_stock"),
        "pit_unknown": sum(
            1 for x in products
            if x.get("current_price_jpy") is not None and not x.get("available_at")
        ),
        "pit_failures": sum(
            1 for x in products
            if x.get("current_price_jpy") is not None and
               x.get("available_at") and
               x.get("prediction_time") and
               not x.get("pit_valid", False)
        ),
    }

    out = {
        "generated_at": generated,
        "prediction_time": generated,
        "budget_jpy": BUDGET,
        "season_phase": __import__("intelligence").season_phase(),
        "top_recommendation": {
            "id": action.get("id") if action else None,
            "name": action.get("name") if action else None,
            "decision_score": action.get("decision_score") if action else None,
            "status": action.get("score_detail", {}).get("status") if action else "NO_VERIFIED_CANDIDATE",
        },
        "quality": quality,
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
        f"予算: ¥{BUDGET:,}",
        f"フェーズ: **{out['season_phase']}**",
        "",
    ]

    if action:
        d = action["score_detail"]
        price = action["current_price_jpy"]
        lines += [
            "## 現時点の最優先候補",
            "",
            f"**1位: {action.get('name','')} — {action['decision_score']}/100**",
            f"- 現在価格: ¥{price:,}",
            f"- 判定: **{d['status']}**",
            f"- 買い判断: {d['reason']}",
            f"- 待つリスク: **{d['wait_risk']}**",
            f"- 28万円まで必要値下げ: {d['required_discount_pct']:.1f}%",
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
        "|順位|商品|現在価格|必要値下げ|性能|価格|過去根拠|在庫|時期|総合|判定|",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in scored[:20]:
        d = row["score_detail"]
        lines.append(
            f"|{row['rank']}|{row.get('name','')[:55]}|¥{row['current_price_jpy']:,}|"
            f"{d['required_discount_pct']:.1f}%|{d['performance']}/40|{d['price']}/20|"
            f"{d['history']}/15|{d['stock']}/15|{d['timing']}/10|"
            f"**{row['decision_score']}/100**|{d['status']}|"
        )

    lines += [
        "",
        "## データ品質",
        "",
        f"- 候補総数: {quality['candidate_count']}",
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
        "- BUY_NOW: 目標価格以下・購入可能・データ品質を通過。",
        "- BUY_NOW_LOW_STOCK: 目標価格以下・低在庫。最安値待ちを避ける。",
        "- STRONG_WATCH: 未到達でも性能・価格距離・過去根拠が強い。",
        "- WAIT_FOR_DISCOUNT: 大幅値下げ待ち。",
        "- VERIFY_NOW: 検索補完など。購入前に販売ページで再確認。",
        "- UNACTIONABLE: 現行価格を確認できない、または異常値・構成不一致。",
        "",
        "## Fail-closedルール",
        "",
        "- 取得失敗は売り切れではない。",
        "- 月額、分割、ポイント等の数字を販売価格として採用しない。",
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
