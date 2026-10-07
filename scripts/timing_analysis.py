import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta

from intelligence import (
    ROOT, BUDGET, GPU_ORDER, gpu_key, performance_score,
    required_discount, load_json, load_catalog, load_anchors, now_jst, iso
)

JST=timezone(timedelta(hours=9))
TARGET=datetime(2026,11,27,tzinfo=JST)

HISTORY=[
  {"date":"2025-11-19","label":"Amazon surprise/pre-sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-21","label":"Amazon early sale begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-22","label":"ROG Strix G16 RTX 5070 Ti 32GB/1TB observed at ¥299,800","price":299800,"source":"https://note.com/utopia_pc/n/nf617ebb9eec3"},
  {"date":"2025-11-24","label":"Amazon main Black Friday begins","source":"https://game.watch.impress.co.jp/docs/news/2064238.html"},
  {"date":"2025-11-24","label":"TUF Gaming A16 RTX 5070 32GB/1TB observed at ¥219,800","price":219800,"source":"https://pc.watch.impress.co.jp/docs/news/todays_sales/2067328.html"},
  {"date":"2025-11-30","label":"TUF Gaming A16 RTX 5070 32GB/1TB still observed at ¥219,800","price":219800,"source":"https://ascii.jp/elem/000/004/356/4356081/"},
  {"date":"2025-11-14","label":"Lenovo Black Friday campaign begins","source":"https://www.lenovo.com/jp/ja/campaigns/black-friday/"}
]

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_events():
    path=os.path.join(ROOT,"data","change_events.jsonl")
    events=[]
    if not os.path.exists(path):
        return events
    with open(path,encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events

def dynamic_change_timing(events):
    hours=Counter()
    dates=Counter()
    price_changes=[]
    for e in events:
        old=e.get("old_price_jpy")
        new=e.get("new_price_jpy")
        if old is None or new is None or old==new:
            continue
        if e.get("pit_valid") is False:
            continue
        ts=e.get("observed_at") or e.get("retrieval_time")
        if not ts:
            continue
        try:
            dt=datetime.fromisoformat(str(ts).replace("Z","+00:00")).astimezone(JST)
        except Exception:
            continue
        hours[dt.hour]+=1
        dates[dt.strftime("%m-%d")]+=1
        price_changes.append({
            "id":e.get("id"),
            "observed_at":ts,
            "old_price_jpy":old,
            "new_price_jpy":new,
            "delta_jpy":new-old,
            "url":e.get("url"),
            "name":e.get("name"),
            "source_mode":e.get("price_source_mode"),
        })
    price_changes.sort(key=lambda x:x["observed_at"])
    return {
        "sample_size":len(price_changes),
        "hourly_counts":dict(sorted(hours.items())),
        "date_counts":dict(sorted(dates.items())),
        "top_hours":hours.most_common(8),
        "recent_changes":price_changes[-50:],
    }

def main():
    latest_path=os.path.join(ROOT,"data","current_latest.json")
    latest=load_json(latest_path,{"products":[]})
    source_snapshot_generated_at=latest.get("generated_at")
    source_snapshot_sha256=file_sha256(latest_path) if os.path.exists(latest_path) else None
    catalog=load_catalog()
    live={str(x.get("id")):x for x in latest.get("products",[]) if x.get("id")}

    rows=[]
    for cid,item in live.items():
        price=item.get("current_price_jpy")
        if price is None:
            continue
        gpu=gpu_key(item)
        req=required_discount(price)
        perf=performance_score(item)[0] if gpu else -1
        rows.append({
            "id":cid,
            "name":item.get("name") or catalog.get(cid,{}).get("name"),
            "store":item.get("store"),
            "price_jpy":price,
            "required_discount_pct":round(req,1) if req is not None else None,
            "feasibility":(
                "HIGH" if req is not None and req<=10 else
                "REALISTIC" if req is not None and req<=20 else
                "AGGRESSIVE" if req is not None and req<=30 else
                "LOW" if req is not None and req<=40 else
                "VERY_LOW"
            ),
            "gpu":gpu or None,
            "performance_score":perf,
            "source_mode":item.get("price_source_mode"),
            "confidence":item.get("data_confidence"),
            "dynamic_candidate":bool(item.get("dynamic_candidate")),
        })
    rows.sort(key=lambda x:(x["required_discount_pct"] if x["required_discount_pct"] is not None else 999999, -x["performance_score"]))
    dynamic=dynamic_change_timing(read_events())
    out={
        "generated_at":iso(now_jst()),
        "source_snapshot_generated_at":source_snapshot_generated_at,
        "source_snapshot_sha256":source_snapshot_sha256,
        "budget_jpy":BUDGET,
        "target_black_friday":TARGET.date().isoformat(),
        "target_products":rows[:50],
        "historical_events":HISTORY,
        "observed_change_timing":dynamic,
        "interpretation":{
            "important_caveat":"Observed/retrieval time is an upper bound on when this system knew the change, not seller-internal price-change time.",
            "minimum_sample_for_hour_pattern":20
        }
    }
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","timing_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    lines=[
        "# Black Friday price timing analysis","",
        f"Generated: {out['generated_at']}",
        f"Source snapshot: {source_snapshot_generated_at or 'UNCONFIRMED'}",
        f"Source snapshot SHA256: {source_snapshot_sha256 or 'UNCONFIRMED'}",
        f"Budget: ¥{BUDGET:,}",
        f"Target Black Friday: {TARGET.date()}","",
        "## Current actionable candidates","",
        "|Rank|Product|Current|Required discount|Feasibility|GPU|Perf|Source|",
        "|---:|---|---:|---:|---|---|---:|---|"
    ]
    for i,r in enumerate(rows[:30],1):
        lines.append(f"|{i}|{str(r['name'])[:55]}|¥{r['price_jpy']:,}|{r['required_discount_pct']:.1f}%|{r['feasibility']}|{r['gpu'] or '—'}|{r['performance_score']}|{r['source_mode']}|")
    lines += ["","## Empirical price-change timing","",f"- Meaningful change sample: **{dynamic['sample_size']}**"]
    if dynamic["sample_size"]<20:
        lines.append("- **観測不足:** 20件未満なので時間帯の傾向は作りません。")
    else:
        lines.append("- 20件以上のため実測時間帯を参照します。")
        lines.append("- 上位時間帯: "+", ".join(f"{h:02d}時={n}件" for h,n in dynamic["top_hours"]))
    lines += ["","## Historical anchors",""]
    for h in HISTORY:
        p=f" ¥{h['price']:,}" if h.get("price") else ""
        lines.append(f"- {h['date']} | {h['label']}{p} | {h['source']}")
    lines += ["","## Rules",
              "- Missing retrieval is not stockout.",
              "- Seller-internal price-change time is never inferred from article publication time.",
              "- Timing observations are empirical only after sufficient sample size."]
    with open(os.path.join(ROOT,"data","reports","timing_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
