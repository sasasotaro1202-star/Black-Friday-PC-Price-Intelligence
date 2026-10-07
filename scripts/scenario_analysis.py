import hashlib
import json
import os

from intelligence import (
    ROOT, BUDGET, load_json, load_catalog, load_anchors,
    scenario_prices, required_discount, now_jst, iso
)

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    latest_path=os.path.join(ROOT,"data","current_latest.json")
    latest=load_json(latest_path,{"products":[]})
    source_snapshot_generated_at=latest.get("generated_at")
    source_snapshot_sha256=file_sha256(latest_path) if os.path.exists(latest_path) else None
    catalog=load_catalog()
    anchors=load_anchors()
    live={str(x.get("id")):x for x in latest.get("products",[]) if x.get("id")}

    products=dict(live)
    for cid,cat in catalog.items():
        products.setdefault(cid,{
            "id":cid,
            "name":cat.get("name"),
            "family":cat.get("family"),
            "form_factor":cat.get("form_factor"),
            "stock_status":cat.get("stock_status","unknown"),
            "current_price_jpy":None,
            "reference_price_jpy":cat.get("reference_price_jpy",cat.get("price_jpy")),
            "price_source_mode":"public_baseline",
        })

    rows=[]
    for cid,p in products.items():
        cat=catalog.get(cid,{})
        current=p.get("current_price_jpy")
        reference=p.get("reference_price_jpy",cat.get("reference_price_jpy",cat.get("price_jpy")))
        base=current if current is not None else reference
        if base is None:
            continue

        family=str(p.get("family") or cat.get("family") or "").lower()
        gpu=str((p.get("spec") or {}).get("gpu") or cat.get("gpu") or "").lower()
        floor=None
        floor_strength="none"
        for a in anchors:
            af=str(a.get("family","")).lower()
            ag=str(a.get("gpu","")).lower()
            ap=a.get("historical_price_jpy")
            if not ap:
                continue
            same_family=bool(family and af and af in family)
            same_gpu=bool(gpu and ag and gpu in ag)
            if same_family and same_gpu:
                strength="same_family_same_gpu"
            elif same_family:
                strength="same_family"
            elif same_gpu:
                strength="same_gpu"
            else:
                continue
            priority={"same_family_same_gpu":3,"same_family":2,"same_gpu":1}[strength]
            cur_priority={"same_family_same_gpu":3,"same_family":2,"same_gpu":1,"none":0}[floor_strength]
            if floor is None or priority>cur_priority or (priority==cur_priority and ap<floor):
                floor=ap
                floor_strength=strength

        scenarios=scenario_prices(base)
        first=next((x for x in scenarios if x["price_jpy"]<=BUDGET),None)
        rows.append({
            "id":cid,
            "name":p.get("name") or cat.get("name"),
            "form_factor":p.get("form_factor") or cat.get("form_factor"),
            "current_price_jpy":current,
            "reference_price_jpy":reference,
            "reference_only":current is None,
            "required_discount_pct":round(required_discount(base),1),
            "historical_floor_jpy":floor,
            "historical_floor_strength":floor_strength,
            "scenario_prices":scenarios,
            "first_280k_scenario":first,
            "stock_status":p.get("stock_status") or cat.get("stock_status","unknown"),
            "price_source_mode":p.get("price_source_mode") or "public_baseline",
            "price_validation_status":p.get("price_validation_status"),
            "dynamic_candidate":bool(p.get("dynamic_candidate")),
        })

    rows.sort(key=lambda x:(x["reference_only"],x["required_discount_pct"],x["historical_floor_jpy"] or 999999999))
    out={"generated_at":iso(now_jst()),
         "source_snapshot_generated_at":source_snapshot_generated_at,
         "source_snapshot_sha256":source_snapshot_sha256,
         "budget_jpy":BUDGET,
         "note":"10/15/20/25/30% scenarios are planning bands, not probabilities.",
         "rows":rows}
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","scenario_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)

    lines=["# ブラックフライデー価格シナリオ分析","",f"更新: {out['generated_at']}",
           f"目標: ¥{BUDGET:,}","",
           "|商品|現行価格|参照価格|必要値下げ|10%|15%|20%|25%|30%|28万円到達|過去最安根拠|",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        s={x["discount_pct"]:x["price_jpy"] for x in r["scenario_prices"]}
        first=r["first_280k_scenario"]
        lines.append(
            f"|{r['name'][:50]}|"
            f"{('¥'+format(r['current_price_jpy'],',')) if r['current_price_jpy'] else '—'}|"
            f"{('¥'+format(r['reference_price_jpy'],',')) if r['reference_price_jpy'] else '—'}|"
            f"{r['required_discount_pct']:.1f}%|"
            f"¥{s[10]:,}|¥{s[15]:,}|¥{s[20]:,}|¥{s[25]:,}|¥{s[30]:,}|"
            f"{str(first['discount_pct'])+'%' if first else '未到達'}|{r['historical_floor_strength']}|"
        )
    lines += ["","## ケース","",
              "- A: 28万円到達＋在庫あり → 即時再評価。",
              "- B: 28万円到達＋低在庫 → 最安値待ちを避ける。",
              "- C: 大幅値下げだが未達 → 性能・在庫・次の値下げ余地を再評価。",
              "- D: 売り切れ → 代替候補へ。",
              "- E: 取得不能 → 売り切れとはみなさず、別ソース再確認。",
              "- F: 異常価格 → 独立確認なしでは現行価格に採用しない。"]
    with open(os.path.join(ROOT,"data","reports","scenario_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
