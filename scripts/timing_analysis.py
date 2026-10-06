import json, os
from collections import Counter
from datetime import datetime, timezone, timedelta

JST=timezone(timedelta(hours=9))
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET=280000
TARGET=datetime(2026,11,27,tzinfo=JST)

GPU_ORDER=("rtx 5090","rtx 5080","rtx 5070 ti","rtx 5070","rtx 5060 ti","rtx 5060")
GPU_POINTS={"rtx 5090":100,"rtx 5080":92,"rtx 5070 ti":82,"rtx 5070":65,"rtx 5060 ti":47,"rtx 5060":38}

HISTORY=[
  {"date":"2025-11-19","label":"Amazon surprise/pre-sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-21","label":"Amazon early sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-22","label":"ROG Strix G16 RTX 5070 Ti 32GB/1TB observed at ¥299,800","price":299800,"source":"https://note.com/utopia_pc/n/nf617ebb9eec3"},
  {"date":"2025-11-24","label":"Amazon main Black Friday begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-24","label":"TUF Gaming A16 RTX 5070 32GB/1TB observed at ¥219,800","price":219800,"source":"https://pc.watch.impress.co.jp/docs/news/todays_sales/2067328.html"},
  {"date":"2025-11-30","label":"TUF Gaming A16 RTX 5070 32GB/1TB still observed at ¥219,800","price":219800,"source":"https://ascii.jp/elem/000/004/356/4356081/"},
  {"date":"2025-11-14","label":"Lenovo Black Friday campaign begins","source":"https://www.lenovo.com/jp/ja/campaigns/black-friday/"}
]

def load(path,default):
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def required_discount(price):
    if not price:return None
    return max(0.0,(price-BUDGET)/price*100)

def gpu_key(item):
    s=json.dumps(item.get("spec",{}),ensure_ascii=False).lower()+" "+str(item.get("name","")).lower()
    for g in GPU_ORDER:
        if g in s:return g
    return None

def performance_score(item):
    g=gpu_key(item)
    if not g:return -1
    spec=item.get("spec",{})
    tgp=spec.get("tgp_w") or 0
    ram=spec.get("ram_gb") or 0
    score=GPU_POINTS[g]
    score += 10 if any(x in json.dumps(spec,ensure_ascii=False).lower() for x in ["9955hx3d","9955hx","8940hx","290hx","275hx"]) else 8 if "ultra 9" in json.dumps(spec,ensure_ascii=False).lower() else 5
    score += 7 if ram>=32 else 3
    score += 4 if tgp>=130 else 3 if tgp>=115 else 2 if tgp>=100 else 0
    return score

def timing_windows():
    return [
      ("2026-11-14","2026-11-20","メーカー予告・先行","HIGH"),
      ("2026-11-19","2026-11-23","先行セール/サプライズ","VERY_HIGH"),
      ("2026-11-24","2026-11-27","本番前半〜BF当日","MAX"),
      ("2026-11-28","2026-11-30","本番後半/Cyber Monday","HIGH"),
      ("2026-12-01","2026-12-04","延長・在庫処分","MEDIUM")
    ]

def dynamic_change_timing():
    path=os.path.join(ROOT,"data/change_events.jsonl")
    hours=Counter();dates=Counter();price_changes=[]
    if os.path.exists(path):
        with open(path,encoding="utf-8") as f:
            for line in f:
                try:e=json.loads(line)
                except Exception:continue
                old=e.get("old_price_jpy");new=e.get("new_price_jpy")
                if old is None or new is None or old==new:continue
                ts=e.get("observed_at")
                if not ts:continue
                try:d=datetime.fromisoformat(ts)
                except Exception:continue
                hours[d.hour]+=1
                dates[d.strftime("%m-%d")]+=1
                price_changes.append({
                  "observed_at":ts,"old_price_jpy":old,"new_price_jpy":new,
                  "delta_jpy":new-old,"url":e.get("url"),"name":e.get("name"),
                  "mode":e.get("price_source_mode")
                })
    if not price_changes:
        return {"sample_size":0,"hourly_counts":{},"date_counts":{},"top_hours":[],"recent_changes":[]}
    top=hours.most_common()
    return {"sample_size":len(price_changes),
            "hourly_counts":dict(sorted(hours.items())),
            "date_counts":dict(sorted(dates.items())),
            "top_hours":[h for h in top if h[1]>0][:8],
            "recent_changes":price_changes[-50:]}

def main():
    latest=load(os.path.join(ROOT,"data/current_latest.json"),{})
    products=[x for x in latest.get("products",[])
              if x.get("price_jpy") and x.get("price_jpy")<=700000
              and x.get("fetch_status") in ("ok","search_fallback","baseline")]
    rows=[]
    for p in products:
        req=required_discount(p["price_jpy"])
        g=gpu_key(p)
        perf=performance_score(p)
        rows.append({
          "id":p.get("id"),"name":p.get("name"),"store":p.get("store"),
          "price_jpy":p["price_jpy"],"required_discount_pct":round(req,1),
          "feasibility":"HIGH" if req<=10 else "REALISTIC" if req<=20 else "AGGRESSIVE" if req<=30 else "LOW" if req<=40 else "VERY_LOW",
          "gpu":g,"performance_score":perf,"observed_at":p.get("last_checked_at") or p.get("observed_at"),
          "source_mode":p.get("price_source_mode"),"confidence":p.get("data_confidence")
        })
    rows.sort(key=lambda x:(x["performance_score"],-x["required_discount_pct"]),reverse=True)

    dynamic=dynamic_change_timing()
    out={
      "generated_at":datetime.now(JST).replace(microsecond=0).isoformat(),
      "budget_jpy":BUDGET,
      "target_black_friday":TARGET.date().isoformat(),
      "target_products":rows[:30],
      "historical_events":HISTORY,
      "historical_timing_windows":timing_windows(),
      "observed_change_timing":dynamic,
      "interpretation":{
        "important_caveat":"Observed/publication time is not the seller's hidden internal price-change timestamp.",
        "dynamic_timing_rule":"Only meaningful price changes with both old and new prices are used for empirical hour analysis.",
        "minimum_sample_for_hour_pattern":20
      }
    }
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","timing_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)

    lines=[
      "# Black Friday price timing analysis","",
      f"Generated: {out['generated_at']}",
      f"Budget: ¥{BUDGET:,}",
      f"Target Black Friday: {TARGET.date()}","",
      "## Current candidates",
      "",
      "|Rank|Product|Current|Required discount|Feasibility|GPU|Perf|Source|",
      "|---:|---|---:|---:|---|---|---:|---|"
    ]
    for i,r in enumerate(rows[:20],1):
        lines.append(f"|{i}|{str(r['name'])[:55]}|¥{r['price_jpy']:,}|{r['required_discount_pct']:.1f}%|{r['feasibility']}|{r['gpu']}|{r['performance_score']}|{r['source_mode']}|")

    lines += ["","## Empirical price-change timing","",
              f"- Meaningful price-change sample: **{dynamic['sample_size']}**"]
    if dynamic["sample_size"]<20:
        lines.append("- **観測不足:** 20件未満なので、時間帯の傾向を断定しません。")
    else:
        lines.append("- 観測件数が20件以上になったため、実測ベースの時間帯傾向を参照します。")
        lines.append("- 上位時間帯: "+", ".join(f"{h:02d}時={n}件" for h,n in dynamic["top_hours"]))

    lines += ["","## 2026 watch windows (forecast, not guaranteed price-change timestamps)","",
              "|Window|Reason|Priority|","|---|---|---|"]
    for a,b,label,prio in timing_windows():
        lines.append(f"|{a} → {b}|{label}|**{prio}**|")

    lines += ["","## Historical anchors",""]
    for h in HISTORY:
        p=f" ¥{h['price']:,}" if h.get("price") else ""
        lines.append(f"- {h['date']} | {h['label']}{p} | {h['source']}")

    lines += ["","## Rules",
              "- Missing retrieval is not stockout.",
              "- Baseline/search-snippet prices are evidence with lower confidence than direct structured product data.",
              "- Seller-internal price-change time is never claimed from an article publication timestamp.",
              "- A lower-than-expected price should be evaluated together with stock and configuration before purchase."]
    with open(os.path.join(ROOT,"data","reports","timing_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
