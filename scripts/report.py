import json
import os
from intelligence import (
    ROOT, BUDGET, load_json, save_json, load_catalog, load_anchors,
    build_row, now_jst, iso, scenario_prices, required_discount
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
                pass
    return events

def main():
    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {"products": []})
    anchors = load_anchors()
    catalog = load_catalog()
    events = read_events()

    products = []
    by_id = {str(x.get("id")): x for x in latest.get("products", []) if x.get("id")}
    for cid, cat in catalog.items():
        if cid in by_id:
            products.append(by_id[cid])
        else:
            products.append({
                "id": cid,
                "url": cat.get("url"),
                "name": cat.get("name"),
                "family": cat.get("family"),
                "form_factor": cat.get("form_factor"),
                "stock_status": cat.get("stock_status", "unknown"),
                "current_price_jpy": None,
                "last_valid_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
                "reference_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
                "price_source_mode": "public_baseline",
                "price_validation_status": "reference_only",
                "data_confidence": "low",
                "spec": {
                    k: cat.get(k) for k in ("gpu","cpu","tgp_w","ram_gb","ssd","vram_gb")
                    if cat.get(k) not in (None, "")
                },
                "variant_match": "trusted_url" if cat.get("url_is_exact") else "ambiguous",
            })

    scored = []
    reference_only = []
    for p in products:
        row = build_row(p, anchors, events)
        if row.get("decision_score") is None:
            reference_only.append(row)
        else:
            scored.append(row)

    scored.sort(key=lambda x: (x["decision_score"], -x.get("current_price_jpy", 9999999)), reverse=True)
    for i, row in enumerate(scored, 1):
        row["rank"] = i

    top = scored[:3]
    action = top[0] if top else None
    generated = iso(now_jst())

    quality = {
        "candidate_count": len(products),
        "actionable_count": len(scored),
        "reference_only_count": len(reference_only),
        "direct_verified": sum(1 for x in products if x.get("price_source_mode") in ("direct_structured","direct_page","direct_text") and x.get("current_price_jpy") is not None),
        "search_verified": sum(1 for x in products if x.get("price_source_mode") == "search_snippet" and x.get("current_price_jpy") is not None),
        "anomaly_rejected": sum(1 for x in products if x.get("price_validation_status") == "anomaly_rejected"),
        "unknown_stock": sum(1 for x in products if x.get("stock_status") == "unknown"),
        "out_of_stock": sum(1 for x in products if x.get("stock_status") == "out_of_stock"),
        "pit_failures": sum(1 for x in products if x.get("current_price_jpy") is not None and x.get("available_at") and not x.get("pit_valid", False)),
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
        "reference_only": reference_only,
        "method": {
            "total": 100,
            "performance_max": 40,
            "price_max": 20,
            "historical_evidence_max": 15,
            "stock_max": 15,
            "timing_max": 10,
            "note": "100点は購入判断の優先度であり、確率ではない。データ品質ガードで上限を設定し、未確認情報から高得点を作らない。",
            "score_cap_rules": {
                "ambiguous_variant": 74,
                "gpu_only_match": 82,
                "search_snippet": 84,
                "unknown_stock": 89,
                "low_confidence": 79,
                "reference_only": 0,
                "anomaly_rejected": 0
            }
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
            "",
        ]
    else:
        lines += [
            "## 現時点の最優先候補",
            "",
            "**購入判断に使える現行価格が未確認です。**",
            "価格取得失敗・構成不一致・異常価格はランキングから安全側に除外しています。",
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
        f"- 直接確認: {quality['direct_verified']}",
        f"- 検索補完: {quality['search_verified']}",
        f"- 異常価格として棄却: {quality['anomaly_rejected']}",
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
        first_target = next((x for x in scenarios if x["price_jpy"] <= BUDGET), None)
        lines.append(f"### {row['rank']}. {row.get('name','')}")
        lines.append(
            " / ".join(f"{x['discount_pct']}%→¥{x['price_jpy']:,}" for x in scenarios)
            + (f" / 28万円到達→{first_target['discount_pct']}%" if first_target else " / 30%でも28万円未満にならない")
        )
        lines.append("")

    lines += [
        "## 買う/待つルール",
        "",
        "- **BUY_NOW:** 目標価格以下・購入可能・データ品質を通過した候補。原則、次の価格更新を待たない。",
        "- **BUY_NOW_LOW_STOCK:** 目標価格以下で低在庫。最安値更新待ちは避ける。",
        "- **STRONG_WATCH:** 現価格は未到達でも構成・価格距離・過去根拠が強い。",
        "- **WAIT_FOR_DISCOUNT:** 必要値下げが大きい。28万円到達の瞬間に再評価する。",
        "- **VERIFY_NOW:** 検索補完や基準価格であり、購入前に販売ページで再確認する。",
        "- **UNACTIONABLE:** 現行価格を確認できない、または異常価格を安全側に棄却した状態。",
        "",
        "## 重要な安全ルール",
        "",
        "- 取得エラーは売り切れとみなさない。",
        "- 価格を取得できても、構成違い・月額表示・ポイント表示などの可能性がある価格はそのまま採用しない。",
        "- 異常な大幅値下げは独立検索で裏付けが取れない限り棄却する。",
        "- 参照価格は現在価格ではない。購入判断の現行価格として使用しない。",
        "- seller内部の値札変更時刻は推測しない。観測時刻は上限時刻として記録する。",
    ]

    os.makedirs(os.path.join(ROOT, "data", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "reports", "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
