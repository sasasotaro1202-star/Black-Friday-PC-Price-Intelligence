import json, os
from datetime import datetime, timezone, timedelta

JST=timezone(timedelta(hours=9))
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET=280000
TARGET=datetime(2026,11,27,tzinfo=JST)

GPU_ORDER=("rtx 5080","rtx 5070 ti","rtx 5070","rtx 5060 ti","rtx 5060")
GPU_POINTS={"rtx 5080":100,"rtx 5070 ti":90,"rtx 5070":72,"rtx 5060 ti":48,"rtx 5060":40}

# Historical sale/event anchors. These describe public sale/published times,
# not the seller's hidden internal price-change timestamp.
HISTORY=[
  {"date":"2025-11-19","label":"Amazon surprise pre-sale begins","kind":"sale_start","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-21","label":"Amazon early sale begins","kind":"sale_start","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-22","label":"ASUS TUF A16 RTX 5070 32GB/1TB observed at ¥219,800","kind":"price_observation","price":219800,"product":"TUF Gaming A16 FA608UP","source":"https://note.com/utopia_pc/n/nf617ebb9eec3"},
  {"date":"2025-11-22","label":"ASUS ROG Strix G16 RTX 5070 Ti 32GB/1TB observed at ¥299,800","kind":"price_observation","price":299800,"product":"ROG Strix G16 G614PR-R9R5070TI","source":"https://note.com/utopia_pc/n/nf617ebb9eec3"},
  {"date":"2025-11-24","label":"Amazon main Black Friday begins","kind":"sale_start","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-30","label":"ASUS TUF A16 RTX 5070 32GB/1TB still observed at ¥219,800","kind":"price_observation","price":219800,"product":"TUF Gaming A16 FA608UP","source":"https://ascii.jp/elem/000/004/356/4356081/"},
  {"date":"2025-11-21","label":"MSI Vector 16 HX AI RTX 5070 Ti observed at ¥409,800","kind":"price_observation","price":409800,"product":"MSI Vector 16 HX AI","source":"https://akiba-pc.watch.impress.co.jp/docs/sale/online_shopping/2065186.html"},
  {"date":"2025-11-14","label":"Lenovo Black Friday campaign begins","kind":"sale_window","source":"https://www.lenovo.com/jp/ja/campaigns/black-friday/"},
  {"date":"2024-11-27","label":"Amazon Black Friday early sale period","kind":"sale_start","source":"https://akiba-pc.watch.impress.co.jp/docs/sale/online_shopping/1642325.html"},
  {"date":"2024-11-29","label":"Amazon Black Friday main sale period","kind":"sale_start","source":"https://akiba-pc.watch.impress.co.jp/docs/sale/online_shopping/1642325.html"},
  {"date":"2023-11-22","label":"Amazon Black Friday early sale period","kind":"sale_start","source":"https://akiba-pc.watch.impress.co.jp/docs/news/news/1548903.html"},
  {"date":"2023-11-24","label":"Amazon Black Friday main sale period","kind":"sale_start","source":"https://akiba-pc.watch.impress.co.jp/docs/news/news/1548903.html"}
]

def load(path,default):
    try:
        with open(path,encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def pct_required(price):
    if not price or price<=0:return None
    return max(0.0,(price-BUDGET)/price*100)

def gpu_key(item):
    s=json.dumps(item.get("spec",{}),ensure_ascii=False).lower()
    for g in GPU_ORDER:
        if g in s:return g
    return None

def cpu_points(item):
    s=json.dumps(item.get("spec",{}),ensure_ascii=False).lower()
    pts=0
    for token,bonus in [
        ("9955hx3d",18),("9955hx",16),("8940hx",14),("8945hx",13),
        ("ultra 9",13),("275hx",13),("290hx",13),("13700hx",11),
        ("14650hx",10),("13620h",8),("ryzen 9",8),("core i9",9)
    ]:
        if token in s: pts=max(pts,bonus)
    return pts

def performance_score(item):
    g=gpu_key(item)
    if not g:return -1
    s=GPU_POINTS[g]+cpu_points(item)
    spec=item.get("spec",{})
    if spec.get("ram_gb",0)>=32:s+=7
    if spec.get("vram_gb",0)>=12:s+=3
    if spec.get("refresh_hz",0)>=240:s+=2
    return s

def feasibility(required):
    if required is None:return "UNKNOWN"
    if required<=10:return "HIGH"
    if required<=20:return "REALISTIC"
    if required<=30:return "AGGRESSIVE"
    if required<=40:return "LOW"
    if required<=50:return "VERY_LOW"
    return "EXTREME"

def parse_date(s):
    return datetime.fromisoformat(s+"T00:00:00+09:00")

def timing_windows():
    return [
      ("2026-11-14","2026-11-20","manufacturer/preview window","HIGH"),
      ("2026-11-19","2026-11-23","Amazon-like surprise/early-sale window","VERY_HIGH"),
      ("2026-11-24","2026-11-27","main-sale lead-in + Black Friday","MAX"),
      ("2026-11-28","2026-11-30","post-Black-Friday / Cyber-Monday tail","HIGH"),
      ("2026-12-01","2026-12-04","campaign tail / clearance risk","MEDIUM")
    ]

def main():
    latest=load(os.path.join(ROOT,"data/current_latest.json"),{})
    products=[x for x in latest.get("products",[]) if x.get("fetch_status")=="ok" and x.get("price_jpy")]
    rows=[]
    for p in products:
        price=p["price_jpy"]
        req=pct_required(price)
        g=gpu_key(p)
        perf=performance_score(p)
        if g:
            rank_value=perf + max(0,35-req*0.55)
            rows.append({
              "name":p.get("name"),"store":p.get("store"),"price_jpy":price,
              "required_discount_pct":round(req,1),"feasibility":feasibility(req),
              "gpu":g,"performance_score":perf,"rank_value":round(rank_value,1),
              "observed_at":p.get("observed_at"),"url":p.get("url")
            })
    rows.sort(key=lambda x:x["rank_value"],reverse=True)
    out={
      "generated_at":datetime.now(JST).replace(microsecond=0).isoformat(),
      "budget_jpy":BUDGET,"target_black_friday":TARGET.date().isoformat(),
      "target_products":rows[:30],
      "historical_events":HISTORY,
      "historical_timing_windows":timing_windows(),
      "interpretation":{
        "important_caveat":"Observed/publication time is not the seller's exact hidden price-change time.",
        "why_watch_early":"Historical Amazon and manufacturer campaigns show material prices can appear before the main Black Friday start.",
        "why_keep_monitoring":"A good price can persist into the sale, but inventory can disappear before the main event."
      }
    }
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","timing_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    lines=[
      "# Black Friday price timing analysis",
      "",
      f"Generated: {out['generated_at']}",
      f"Budget: ¥{BUDGET:,}",
      f"Target Black Friday date: {TARGET.date()}",
      "",
      "## Current candidates by performance × required discount",
      "",
      "| Rank | Product | Current | Required discount | Feasibility | GPU | Perf score |",
      "|---:|---|---:|---:|---|---|---:|"
    ]
    for i,r in enumerate(rows[:20],1):
        lines.append(f"| {i} | {r['name'][:55]} | ¥{r['price_jpy']:,} | {r['required_discount_pct']:.1f}% | {r['feasibility']} | {r['gpu']} | {r['performance_score']} |")
    lines += [
      "","## 2026 watch windows (forecast, not guaranteed price-change timestamps)","",
      "| Window | Reason | Priority |","|---|---|---|"
    ]
    for a,b,label,prio in timing_windows():
        lines.append(f"| {a} → {b} | {label} | **{prio}** |")
    lines += ["","## Historical anchors",""]
    for h in HISTORY:
        price=f" ¥{h['price']:,}" if h.get("price") else ""
        lines.append(f"- {h['date']} | {h['label']}{price} | {h['source']}")
    lines += [
      "","## Rules",
      "- Do not treat a missing fetch as stockout.",
      "- Do not infer an exact seller price-change timestamp from article publication time.",
      "- Prefer the first observed price and retain every subsequent change event.",
      "- For the 2026 campaign, a lower-than-expected price should be evaluated immediately against stock and configuration."
    ]
    with open(os.path.join(ROOT,"data","reports","timing_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":main()
