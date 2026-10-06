import json
import os

from intelligence import (
    ROOT, BUDGET, load_json, load_catalog, load_anchors,
    scenario_prices, required_discount, now_jst, iso
)

def main():
    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {"products": []})
    catalog = load_catalog()
    anchors = load_anchors()
    current = {str(x.get("id")): x for x in latest.get("products", []) if x.get("id")}

    rows = []
    for cid, cat in catalog.items():
        item = current.get(cid, {})
        price = item.get("current_price_jpy")
        reference = item.get("reference_price_jpy", cat.get("reference_price_jpy", cat.get("price_jpy")))
        base_price = price if price is not None else reference
        if base_price is None:
            continue

        floor = None
        family = str(cat.get("family") or item.get("family") or "").lower()
        gpu = str(cat.get("gpu") or (item.get("spec") or {}).get("gpu") or "").lower()
        for a in anchors:
            if family and family in str(a.get("family","")).lower():
                ap = a.get("historical_price_jpy")
                if ap and (floor is None or ap < floor):
                    floor = ap
            elif gpu and gpu in str(a.get("gpu","")).lower():
                ap = a.get("historical_price_jpy")
                if ap and (floor is None or ap < floor):
                    floor = ap

        scenarios = scenario_prices(base_price)
        first_target = next((x for x in scenarios if x["price_jpy"] <= BUDGET), None)
        rows.append({
            "id": cid,
            "name": item.get("name") or cat.get("name"),
            "form_factor": item.get("form_factor") or cat.get("form_factor"),
            "current_price_jpy": price,
            "reference_price_jpy": reference,
            "reference_only": price is None,
            "required_discount_pct": round(required_discount(base_price), 1),
            "historical_floor_jpy": floor,
            "historical_floor_relevance": "same_family" if floor is not None else "none",
            "scenario_prices": scenarios,
            "first_280k_scenario": first_target,
            "stock_status": item.get("stock_status") or cat.get("stock_status", "unknown"),
            "price_source_mode": item.get("price_source_mode") or "public_baseline",
            "price_validation_status": item.get("price_validation_status"),
        })

    rows.sort(key=lambda x: (
        x["reference_only"],
        x["required_discount_pct"],
        -(x["historical_floor_jpy"] or 9999999),
    ))

    out = {
        "generated_at": iso(now_jst()),
        "budget_jpy": BUDGET,
        "note": "10/15/20/25/30% scenarios are planning bands, not probabilities.",
        "rows": rows,
    }
    os.makedirs(os.path.join(ROOT, "data", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "scenario_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    lines = [
        "# ブラックフライデー価格シナリオ分析",
        "",
        f"更新: {out['generated_at']}",
        f"目標: ¥{BUDGET:,}",
        "",
        "|商品|現行価格|参照価格|必要値下げ|10%|15%|20%|25%|30%|28万円到達|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        s = r["scenario_prices"]
        first = r["first_280k_scenario"]
        vals = {x["discount_pct"]: x["price_jpy"] for x in s}
        lines.append(
            f"|{r['name'][:50]}|"
            f"{'¥'+format(r['current_price_jpy'], ',') if r['current_price_jpy'] else '—'}|"
            f"{'¥'+format(r['reference_price_jpy'], ',') if r['reference_price_jpy'] else '—'}|"
            f"{r['required_discount_pct']:.1f}%|"
            f"¥{vals.get(10,0):,}|¥{vals.get(15,0):,}|¥{vals.get(20,0):,}|"
            f"¥{vals.get(25,0):,}|¥{vals.get(30,0):,}|"
            f"{str(first['discount_pct'])+'%' if first else '未到達'}|"
        )

    lines += [
        "",
        "## ケース判定",
        "",
        "- **A: 28万円到達＋在庫あり** → 100点判定を即時再計算し、購入候補を優先。",
        "- **B: 28万円到達＋低在庫** → 最安値更新待ちより在庫確保を優先。",
        "- **C: 大幅値下げだが28万円未満未達** → 性能・在庫・次の下落余地を再評価。",
        "- **D: 売り切れ/取得不能** → 売り切れと取得不能を区別し、代替候補へフェイルオーバー。",
        "- **E: 異常価格** → 独立確認できない激安値はランキングに入れず、再確認待ち。",
    ]
    with open(os.path.join(ROOT, "data", "reports", "scenario_analysis.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
