import json, os, re
from datetime import datetime, timezone, timedelta

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST=timezone(timedelta(hours=9))
BUDGET=280000
MAX_OBSERVATION_PRICE=700000

GPU_POINTS={
    "rtx 5090":25,
    "rtx 5080":23,
    "rtx 5070 ti":21,
    "rtx 5070":17,
    "rtx 5060 ti":11,
    "rtx 5060":8
}

CPU_POINTS=[
    ("9955hx3d",15),("9955hx",14),("8940hx",13),("8945hx",13),
    ("290hx",13),("275hx",13),("ultra 9",12),("core i9",12),
    ("13700hx",11),("14650hx",10),("13620h",8),("ryzen 9",9)
]

def load(path,default):
    try:
        with open(path,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path,obj):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        json.dump(obj,f,ensure_ascii=False,indent=2)

def normalized_name(x):
    return re.sub(r"\s+"," ",str(x.get("name","")).lower()).strip()

def spec_text(x):
    return json.dumps(x.get("spec",{}),ensure_ascii=False).lower()+" "+normalized_name(x)

def gpu_points(x):
    s=spec_text(x)
    for g,p in GPU_POINTS.items():
        if g in s:
            return g,p
    return "",0

def cpu_points(x):
    s=spec_text(x)
    best=0
    for token,p in CPU_POINTS:
        if token in s:
            best=max(best,p)
    return best

def required_discount(price):
    if not price or price<=0:
        return None
    return max(0.0,(price-BUDGET)/price*100)

def price_score(price):
    d=required_discount(price)
    if d is None:return 0
    if d<=0:return 20
    if d<=5:return 19
    if d<=10:return 18
    if d<=15:return 16
    if d<=20:return 13
    if d<=25:return 10
    if d<=30:return 7
    if d<=40:return 4
    if d<=50:return 2
    return 0

def history_score(x,anchors):
    name=normalized_name(x)
    gpu,_=gpu_points(x)
    best=0
    for a in anchors:
        k=a.get("key","").lower()
        fam=a.get("family","").lower()
        agpu=a.get("gpu","").lower()
        match=(k and k in name) or (fam and fam in name)
        if not match:
            continue
        ap=a.get("historical_price_jpy")
        if ap and ap<=BUDGET:
            best=max(best,15)
        elif ap:
            req=required_discount(ap)
            best=max(best,12 if req is not None and req<=20 else 8)
        if gpu and agpu and gpu==agpu:
            best=max(best, min(15,best+2))
    return best

def stock_score(x,anchors):
    status=x.get("stock_status","unknown")
    base={
        "in_stock":10,
        "low_stock":6,
        "preorder_or_backorder":3,
        "unknown":3,
        "out_of_stock":0
    }.get(status,3)
    name=normalized_name(x)
    risk=0
    for a in anchors:
        family=a.get("family","").lower()
        key=a.get("key","").lower()
        note=a.get("historical_note","").lower()
        if ((family and family in name) or (key and key in name)) and ("sold out" in note or "売り切れ" in note or "在庫切れ" in note):
            risk=5
            break
    return max(0, min(15, base + (5 if status=="in_stock" and risk else 0) - risk))

def timing_score(x,anchors):
    price=x.get("price_jpy")
    d=required_discount(price)
    score=0
    if d is None:return 0,"情報不足"
    # Ten points reward an actionable price and penalize waiting for a very large drop.
    if d<=0:
        return 10,"今の価格が目標以下。売り切れ前に確保"
    if d<=10:
        return 9,"先行セール〜本番序盤を重点監視"
    if d<=15:
        return 8,"先行セール開始後を重点監視"
    if d<=20:
        return 7,"先行〜本番開始直後。価格と在庫を同時監視"
    if d<=30:
        return 5,"本番期間の大幅値引き待ち。在庫リスク高"
    if d<=40:
        return 3,"大穴。28万円到達時のみ即判断"
    return 1,"超大穴。値下げ期待だけで待ち続けない"

def performance_score(x):
    gpu,gp=gpu_points(x)
    cp=cpu_points(x)
    spec=x.get("spec",{})
    tgp=spec.get("tgp_w") or 0
    vram=spec.get("vram_gb") or 0
    ram=2 if spec.get("ram_gb",0)>=32 else 0
    ssd=2 if re.search(r"1\s*TB",str(spec.get("ssd","")),re.I) else 0
    tgp_bonus=4 if tgp>=130 else 3 if tgp>=115 else 2 if tgp>=100 else 0
    vram_bonus=1 if vram>=12 else 0
    return min(40,gp+cp+ram+ssd+tgp_bonus+vram_bonus),gpu

def decision_score(x,anchors):
    p=x.get("price_jpy")
    if not p or x.get("fetch_status")!="ok":
        return 0
    perf,gpu=performance_score(x)
    ps=price_score(p)
    hs=history_score(x,anchors)
    ss=stock_score(x,anchors)
    ts,timing=timing_score(x,anchors)
    total=min(100,perf+ps+hs+ss+ts)
    return total,{
        "performance":perf,"price":ps,"history":hs,"stock":ss,"timing":ts,
        "gpu":gpu,"required_discount_pct":round(required_discount(p),1),
        "timing_guidance":timing
    }

def season_phase():
    now=datetime.now(JST)
    y=now.year
    # Forecast window based on prior Japan retailer campaign patterns.
    windows=[
        (datetime(y,11,14,tzinfo=JST),datetime(y,11,20,23,59,tzinfo=JST),"メーカー先行/予告"),
        (datetime(y,11,21,tzinfo=JST),datetime(y,11,23,23,59,tzinfo=JST),"先行セール"),
        (datetime(y,11,24,tzinfo=JST),datetime(y,11,27,23,59,tzinfo=JST),"本番前半〜BF当日"),
        (datetime(y,11,28,tzinfo=JST),datetime(y,11,30,23,59,tzinfo=JST),"本番後半"),
        (datetime(y,12,1,tzinfo=JST),datetime(y,12,4,23,59,tzinfo=JST),"セール末期/延長")
    ]
    for a,b,label in windows:
        if a<=now<=b:return label
    return "通常監視期間"

def main():
    latest=load(os.path.join(ROOT,"data/current_latest.json"),{})
    hist=load(os.path.join(ROOT,"config/history_anchors.json"),{})
    anchors=hist.get("anchors",[])
    products=[x for x in latest.get("products",[])
              if x.get("price_jpy") and x.get("price_jpy")<=MAX_OBSERVATION_PRICE
              and x.get("fetch_status") in ("ok","search_fallback","baseline")]

    ranked=[]
    for p in products:
        total,detail=decision_score(p,anchors)
        detail["source_mode"]=p.get("price_source_mode","unknown")
        detail["data_confidence"]=p.get("data_confidence","unknown")
        ranked.append({
            **p,
            "decision_score":total,
            "score_detail":detail
        })
    ranked.sort(key=lambda x:(x["decision_score"],x["price_jpy"]),reverse=True)

    out={
        "generated_at":datetime.now(JST).replace(microsecond=0).isoformat(),
        "budget_jpy":BUDGET,
        "season_phase":season_phase(),
        "products":ranked,
        "method":{
            "total":100,
            "performance_max":40,
            "price_max":20,
            "historical_evidence_max":15,
            "stock_max":15,
            "timing_max":10,
            "note":"100-point buy score combines performance and season-long purchase readiness; it is not a probability."
        }
    }
    save(os.path.join(ROOT,"data","decision_rankings.json"),out)

    lines=[
        "# ブラックフライデー期間通算・購入ランキング",
        "",
        f"自動更新: {out['generated_at']}",
        f"予算: ¥{BUDGET:,}",
        f"現在のフェーズ: **{out['season_phase']}**",
        "",
        "## 100点満点の評価",
        "",
        "|順位|商品|現在価格|必要値下げ|性能|価格|過去根拠|在庫|タイミング|総合|",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for i,r in enumerate(ranked[:20],1):
        d=r["score_detail"]
        lines.append(
            f"|{i}|{r.get('name','')[:45]}|¥{r['price_jpy']:,}|{d['required_discount_pct']:.1f}%|"
            f"{d['performance']}/40|{d['price']}/20|{d['history']}/15|{d['stock']}/15|{d['timing']}/10|"
            f"**{r['decision_score']}/100**|"
        )

    lines += ["", "## 上位候補の買い方", ""]
    for i,r in enumerate(ranked[:10],1):
        d=r["score_detail"]
        lines += [
            f"### {i}. {r.get('name','')}",
            f"- **総合: {r['decision_score']}/100**",
            f"- 性能 {d['performance']}/40 / 価格 {d['price']}/20 / 過去セール根拠 {d['history']}/15 / 在庫安全度 {d['stock']}/15 / タイミング {d['timing']}/10",
            f"- 現在価格: ¥{r['price_jpy']:,} / 28万円まで必要な値下げ: {d['required_discount_pct']:.1f}%",
            f"- 判断: {d['timing_guidance']}",
            ""
        ]

    lines += [
        "",
        "## 買い方のルール",
        "- **95〜100点:** 目標価格を確認できたら原則即購入。待つことで失う在庫メリットが大きい。",
        "- **90〜94点:** その日〜翌日までの価格変化と在庫を確認。次の大幅下落を期待しすぎない。",
        "- **80〜89点:** 期間中の値下げ候補。先行セールから本番序盤を重点監視。",
        "- **70〜79点:** 大幅値下げ待ち。28万円到達時に再評価。",
        "- **69点以下:** 高性能でも28万円化の条件が厳しければ無理に待たない。",
        "",
        "## 重要な在庫ルール",
        "- 先行セールで目標価格が出た場合、本番まで価格維持される保証はなく、人気商品は先行期間中に在庫切れとなり得る。",
        "- したがって「最安価格の期待値」だけではなく、**現在価格が目標に到達した時点の購入可能性**を総合点に反映する。",
        "",
        "## 期間の考え方",
        "- 2026年の正式な各社日程が公開されるまでは、11/14〜12/4を広域監視期間として扱う。",
        "- Amazonの2025年は11/21〜11/23先行、11/24〜12/1本番だった。",
        "- Lenovoの2025年キャンペーンは11/14〜12/4だった。",
        "- exactな値下げ時刻は断定せず、公開セール開始時刻と自前観測時刻を分離する。"
    ]
    with open(os.path.join(ROOT,"data","reports","latest.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
