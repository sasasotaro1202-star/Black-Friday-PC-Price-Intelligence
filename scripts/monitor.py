import hashlib,json,os,re
from datetime import datetime,timezone,timedelta
from html.parser import HTMLParser
from urllib.parse import quote,parse_qs,urlparse
from urllib.request import Request,urlopen

JST=timezone(timedelta(hours=9))
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW=datetime.now(JST).replace(microsecond=0)
UA="Mozilla/5.0 (compatible; BF-PC-Price-Intelligence/1.0)"

def read_json(path,default):
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def write_json(path,obj):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    tmp=path+".tmp"
    with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2)
    os.replace(tmp,path)

def fetch(url,timeout=18):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"ja-JP,ja;q=0.9,en;q=0.5"})
    with urlopen(req,timeout=timeout) as r:
        enc=r.headers.get_content_charset() or "utf-8"
        return r.read().decode(enc,errors="replace"),r.geturl()

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            d=dict(attrs)
            if d.get("href"):self.links.append(d["href"])

def search_web(q):
    html,_=fetch("https://html.duckduckgo.com/html/?q="+quote(q),22)
    p=Links();p.feed(html)
    out=[];seen=set()
    for href in p.links:
        if "uddg=" in href:
            u=parse_qs(urlparse(href).query).get("uddg")
            if u:href=u[0]
        if href.startswith("http") and href not in seen:
            seen.add(href);out.append(href)
    return out

def allowed(u,domains):
    host=urlparse(u).netloc.lower()
    return any(host==d or host.endswith("."+d) for d in domains)

def jsonld(html):
    blocks=re.findall(r'<script[^>]+type=["\\\']application/ld\\+json["\\\'][^>]*>(.*?)</script>',html,re.I|re.S)
    out=[]
    for b in blocks:
        try:
            x=json.loads(b.strip())
            out.extend(x if isinstance(x,list) else ([x] if isinstance(x,dict) else []))
        except Exception:pass
    return out

def price(text):
    vals=[]
    for m in re.findall(r"(?:¥|￥)\\s*([0-9]{2,3}(?:,[0-9]{3})+|[0-9]{5,7})",text):
        try:vals.append(int(m.replace(",","")))
        except Exception:pass
    vals=[x for x in vals if 50000<=x<=1000000]
    return min(vals) if vals else None

def stock(text):
    s=text.lower()
    if any(x in s for x in ["在庫切れ","売り切れ","out of stock","sold out"]):return "out_of_stock"
    if any(x in s for x in ["残りわずか","low stock","only 1","only one"]):return "low_stock"
    if any(x in s for x in ["取り寄せ","予約","preorder","back order"]):return "preorder_or_backorder"
    if any(x in s for x in ["在庫あり","in stock","available"]):return "in_stock"
    return "unknown"

def specs(text):
    s=" ".join(text.split());out={}
    for k,p in {
      "gpu":r"(RTX\\s*(?:5090|5080|5070\\s*Ti|5070|5060)\\s*Laptop(?:\\s*GPU)?)",
      "tgp_w":r"(?:TGP|Total Graphics Power|最大(?:GPU)?電力)[^0-9]{0,30}(\\d{2,3})\\s*W",
      "ram_gb":r"(?:メモリ|Memory|RAM)[^0-9]{0,18}(\\d{2,3})\\s*GB",
      "refresh_hz":r"(\\d{2,3})\\s*Hz"
    }.items():
        m=re.search(p,s,re.I)
        if m:out[k]=int(m.group(1)) if k!="gpu" else m.group(1)
    m=re.search(r"(?:VRAM|ビデオメモリ)[^0-9]{0,20}(\\d{1,2})\\s*GB",s,re.I)
    if m:out["vram_gb"]=int(m.group(1))
    m=re.search(r"((?:Core\\s+Ultra\\s+[579])[^,;|]{0,40}|(?:Ryzen\\s+(?:AI\\s+)?[975])[^,;|]{0,40})",s,re.I)
    if m:out["cpu"]=m.group(1).strip()
    m=re.search(r"(?:SSD|ストレージ|Storage)[^0-9]{0,18}(\\d+(?:\\.\\d+)?)\\s*(TB|GB)",s,re.I)
    if m:out["ssd"]=m.group(1)+" "+m.group(2)
    return out

def parse(url,html):
    name=None;offer_price=None;offer_stock="unknown"
    for obj in jsonld(html):
        if "Product" not in str(obj.get("@type","")):continue
        name=obj.get("name") or name
        offers=obj.get("offers")
        if isinstance(offers,dict):
            try:offer_price=int(float(str(offers.get("price")).replace(",","")))
            except Exception:pass
            av=str(offers.get("availability",""))
            if "InStock" in av:offer_stock="in_stock"
            elif "OutOfStock" in av:offer_stock="out_of_stock"
    text=re.sub(r"<[^>]+>"," ",html);text=re.sub(r"\\s+"," ",text)
    return {"url":url,"store":urlparse(url).netloc.lower(),"name":name or url,
            "price_jpy":offer_price or price(text),
            "stock_status":offer_stock if offer_stock!="unknown" else stock(text),
            "spec":specs(text[:300000]),"fetch_status":"ok","observed_at":NOW.isoformat()}

def fingerprint(x):
    s={k:x.get(k) for k in ["name","price_jpy","stock_status","spec","fetch_status"]}
    return hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def main():
    cfg=read_json(os.path.join(ROOT,"config/targets.json"),{})
    latest_path=os.path.join(ROOT,"data/current_latest.json")
    events_path=os.path.join(ROOT,"data/change_events.jsonl")
    previous=read_json(latest_path,{}).get("products",[])
    previous_by_url={x["url"]:x for x in previous}
    discovered=[]
    for q in cfg.get("queries",[]):
        try:discovered.extend(search_web(q)[:cfg.get("max_results_per_query",6)])
        except Exception:pass
    urls=[];seen=set()
    for u in discovered:
        if u in seen or not allowed(u,cfg.get("allowed_domains",[])):continue
        seen.add(u);urls.append(u)
        if len(urls)>=cfg.get("max_pages_per_run",35):break
    products=[]
    for u in urls:
        try:
            html,final=fetch(u)
            item=parse(final,html)
            blob=(item["name"]+" "+json.dumps(item["spec"],ensure_ascii=False)).lower()
            if any(g in blob for g in ["rtx 5080","rtx 5090","rtx 5070 ti"]) and any(k in blob for k in ["laptop","ノート","gaming","ゲーミング"]):
                item["fingerprint"]=fingerprint(item);products.append(item)
        except Exception:
            products.append({"url":u,"store":urlparse(u).netloc.lower(),"name":u,"price_jpy":None,
                             "stock_status":"unknown","spec":{},"fetch_status":"error",
                             "observed_at":NOW.isoformat(),"fingerprint":hashlib.sha256(u.encode()).hexdigest()})
    changes=[]
    for item in products:
        prev=previous_by_url.get(item["url"])
        if prev and prev.get("fingerprint")==item.get("fingerprint"):continue
        changes.append({"observed_at":item["observed_at"],
                        "previous_observed_at":prev.get("observed_at") if prev else None,
                        "url":item["url"],"store":item["store"],"name":item["name"],
                        "old_price_jpy":prev.get("price_jpy") if prev else None,
                        "new_price_jpy":item.get("price_jpy"),
                        "old_stock_status":prev.get("stock_status") if prev else None,
                        "new_stock_status":item.get("stock_status"),
                        "fetch_status":item.get("fetch_status"),
                        "old_spec":prev.get("spec") if prev else None,
                        "new_spec":item.get("spec"),
                        "event_type":"new" if not prev else "changed"})
    write_json(latest_path,{"generated_at":NOW.isoformat(),"products":products})
    if changes:
        os.makedirs(os.path.dirname(events_path),exist_ok=True)
        with open(events_path,"a",encoding="utf-8") as f:
            for e in changes:f.write(json.dumps(e,ensure_ascii=False)+"\\n")
    print(json.dumps({"observed_at":NOW.isoformat(),"checked_urls":len(urls),
                      "products":len(products),"changes":len(changes)},ensure_ascii=False))

if __name__=="__main__":main()
