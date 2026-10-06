import json,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(path,default):
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return default
BUDGET=280000
MAX_OBSERVATION_PRICE=600000

def required_discount(price):
    return 0 if price<=BUDGET else (price-BUDGET)/price*100

def score(x):
    p=x.get("price_jpy")
    if not p or p>MAX_OBSERVATION_PRICE or x.get("fetch_status")!="ok":return -999
    s=json.dumps(x.get("spec",{}),ensure_ascii=False).lower()
    z=0
    if "rtx 5090" in s:z+=90
    elif "rtx 5080" in s:z+=75
    elif "rtx 5070 ti" in s:z+=55
    if x.get("stock_status")=="in_stock":z+=15
    elif x.get("stock_status")=="low_stock":z+=9
    if x.get("spec",{}).get("ram_gb",0)>=32:z+=8
    if x.get("spec",{}).get("vram_gb",0)>=16:z+=5
    req=required_discount(p)
    if req<=5:z+=12
    elif req<=10:z+=10
    elif req<=20:z+=7
    elif req<=30:z+=4
    elif req<=40:z+=1
    return z
def main():
    latest=load(os.path.join(ROOT,"data/current_latest.json"),{})
    products=[x for x in latest.get("products",[]) if x.get("price_jpy") and x["price_jpy"]<=MAX_OBSERVATION_PRICE and x.get("fetch_status")=="ok"]
    ranked=sorted(products,key=score,reverse=True)
    lines=["# 現在の購入判断","", "自動観測時点: "+str(latest.get("generated_at","")), ""]
    labels=["今この瞬間の最有力候補","今この瞬間の次善候補","今この瞬間の売り切れ対策候補"]
    for label,item in zip(labels,ranked[:3]):
        lines += ["## "+label,
                   "- 商品: "+item["name"],
                   "- 店舗: "+item["store"],
                   "- 価格: ¥"+format(item["price_jpy"],","),
                   "- 在庫: "+str(item.get("stock_status")),
                   "- 主要仕様: "+json.dumps(item.get("spec",{}),ensure_ascii=False),
                   "- 観測時刻: "+str(item.get("observed_at","")),""]
    event_path=os.path.join(ROOT,"data/change_events.jsonl")
    lines += ["## 価格・在庫の変化履歴",""]
    if os.path.exists(event_path):
        rows=[]
        with open(event_path,"r",encoding="utf-8") as f:
            for line in f:
                try:rows.append(json.loads(line))
                except Exception:pass
        for e in rows[-80:]:
            if e.get("old_price_jpy")!=e.get("new_price_jpy") or e.get("old_stock_status")!=e.get("new_stock_status"):
                lines.append("- "+e["observed_at"]+" | "+e["name"]+" | ¥"+str(e.get("old_price_jpy"))+" → ¥"+str(e.get("new_price_jpy"))+" | "+str(e.get("old_stock_status"))+" → "+str(e.get("new_stock_status"))+" | 前回観測 "+str(e.get("previous_observed_at")))
    if not ranked:
        lines += ["","## 結論","現時点では購入判断に使える候補なし。"]
    report=os.path.join(ROOT,"data/reports/latest.md")
    os.makedirs(os.path.dirname(report),exist_ok=True)
    with open(report,"w",encoding="utf-8") as f:f.write("\n".join(lines))
if __name__=="__main__":main()
