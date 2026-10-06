import json, os
from datetime import datetime, timezone, timedelta

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST=timezone(timedelta(hours=9))
BUDGET=280000

def load(path,default):
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def required_discount(price):
    if not price or price<=0:return None
    return max(0.0,(price-BUDGET)/price*100)

def bf_discount(price):
    # Scenario bands are planning ranges, not probabilities.
    if not price:return []
    return [
      {"discount_pct":10,"price_jpy":round(price*0.90,-2)},
      {"discount_pct":15,"price_jpy":round(price*0.85,-2)},
      {"discount_pct":20,"price_jpy":round(price*0.80,-2)},
      {"discount_pct":25,"price_jpy":round(price*0.75,-2)},
      {"discount_pct":30,"price_jpy":round(price*0.70,-2)}
    ]

def outcome(price, historical_floor=None):
    req=required_discount(price)
    if req is None:return {"band":"unknown","reason":"current price unavailable"}
    if req<=10:
        band="high"
        reason="28万円到達に必要な値下げが小さく、先行〜本番序盤から現実的に監視"
    elif req<=20:
        band="realistic"
        reason="大幅値下げだが、BF大型セールで到達余地あり"
    elif req<=30:
        band="aggressive"
        reason="大穴。過去最安値・在庫・クーポンが揃った場合のみ到達を狙う"
    elif req<=40:
        band="low"
        reason="かなり大幅な値下げが必要。価格期待だけで待ち続けない"
    else:
        band="very_low"
        reason="28万円化は極端な特価/在庫処分が必要"
    hist=None
    if historical_floor:
        hist=max(0,price-historical_floor)
        if historical_floor<=BUDGET:
            hist=max(hist,1)
    return {"band":band,"required_discount_pct":round(req,1),"reason":reason,
            "historical_floor_jpy":historical_floor}

def main():
    latest=load(os.path.join(ROOT,"data/current_latest.json"),{})
    baselines=load(os.path.join(ROOT,"config/public_baselines.json"),{})
    historical=load(os.path.join(ROOT,"config/history_anchors.json"),{}).get("anchors",[])
    floors={}
    for h in historical:
        fam=h.get("family","").lower()
        p=h.get("historical_price_jpy")
        if fam and p:
            floors[fam]=min(floors.get(fam,p),p)

    rows=[]
    for p in latest.get("products",[]):
        price=p.get("price_jpy")
        if not price:continue
        name=str(p.get("name",""))
        fam=fam_key=next((k for k in floors if k in name.lower()),None)
        floor=floors.get(fam)
        o=outcome(price,floor)
        sc=bf_discount(price)
        target=next((x for x in sc if x["price_jpy"]<=BUDGET),None)
        rows.append({
          "id":p.get("id"),"name":name,"current_price_jpy":price,
          "required_discount_pct":o["required_discount_pct"],
          "reachability":o["band"],"historical_floor_jpy":floor,
          "scenario_prices":sc,
          "first_280k_scenario":target,
          "stock_status":p.get("stock_status"),
          "source_mode":p.get("price_source_mode"),
          "confidence":p.get("data_confidence")
        })

    out={
      "generated_at":datetime.now(JST).replace(microsecond=0).isoformat(),
      "budget_jpy":BUDGET,
      "note":"Scenario bands are decision aids, not statistical probabilities.",
      "rows":rows
    }
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","scenario_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)

    lines=["# ブラックフライデー価格シナリオ分析","",
           f"自動更新: {out['generated_at']}",
           f"目標: ¥{BUDGET:,}","",
           "|商品|現在|必要値下げ|到達帯|過去最安値|28万円到達の最初の割引シナリオ|",
           "|---|---:|---:|---|---:|---:|"]
    for r in rows:
        first=r["first_280k_scenario"]
        lines.append(f"|{r['name'][:55]}|¥{r['current_price_jpy']:,}|{r['required_discount_pct']:.1f}%|{r['reachability']}|"
                     + (f"¥{r['historical_floor_jpy']:,}" if r["historical_floor_jpy"] else "—")
                     + "|"
                     + (f"{first['discount_pct']}%→¥{first['price_jpy']:,}" if first else "30%でも未到達")
                     + "|")
    lines += ["","## 4つの想定ケース",
              "- **ケースA: 28万円到達＋在庫あり** → 総合点を即時再計算し、購入優先度を上げる。",
              "- **ケースB: 28万円到達＋低在庫** → 最安値更新待ちをせず、在庫を優先して買い判断。",
              "- **ケースC: 大幅値下げだが28万円未満に届かない** → 価格・性能・次の値下げ余地で再評価。",
              "- **ケースD: 売り切れ/取得不能** → 売り切れと断定せず、別販売店・別構成・代替機へフェイルオーバー。"]
    with open(os.path.join(ROOT,"data","reports","scenario_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
