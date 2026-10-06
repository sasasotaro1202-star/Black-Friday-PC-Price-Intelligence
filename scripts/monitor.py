import hashlib, json, os, re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import quote, parse_qs, urlparse
from urllib.request import Request, urlopen

JST=timezone(timedelta(hours=9))
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW=datetime.now(JST).replace(microsecond=0)
UA="Mozilla/5.0 (compatible; BF-PC-Price-Intelligence/2.0)"

PRIMARY_DOMAINS={
    "lenovo.com","asus.com","hp.com","msi.com","acer.com","gigabyte.com",
    "mouse-jp.co.jp","dospara.co.jp"
}
SECONDARY_DOMAINS={
    "kakaku.com","ascii.jp","pc.watch.impress.co.jp","akiba-pc.watch.impress.co.jp",
    "joshinweb.jp","shop.applied-net.co.jp"
}

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

class SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results=[]
        self.current={}
        self.capture=None
        self.buf=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        cls=d.get("class","")
        if tag=="a" and "result__a" in cls:
            self.current={"url":d.get("href",""),"title":""}
            self.capture="title";self.buf=[]
        elif tag in ("a","div","span") and "result__snippet" in cls:
            if self.current:
                self.capture="snippet";self.buf=[]
    def handle_endtag(self,tag):
        if self.capture and tag in ("a","div","span"):
            txt=" ".join("".join(self.buf).split())
            if self.capture=="title":self.current["title"]=txt
            else:self.current["snippet"]=txt
            self.buf=[]
            if self.capture=="snippet":
                self.results.append(self.current);self.current={};self.capture=None
    def handle_data(self,data):
        if self.capture:self.buf.append(data)

def ddg_search(query,timeout=20):
    if not query:return []
    req=Request("https://html.duckduckgo.com/html/?q="+quote(query),
                headers={"User-Agent":UA,"Accept-Language":"ja-JP,ja;q=0.9"})
    with urlopen(req,timeout=timeout) as r:
        enc=r.headers.get_content_charset() or "utf-8"
        html=r.read().decode(enc,errors="replace")
    p=SearchParser();p.feed(html)
    out=[]
    for item in p.results:
        h=item.get("url","")
        if "uddg=" in h:
            u=parse_qs(urlparse(h).query).get("uddg")
            if u:h=u[0]
        if h.startswith("http"):
            item["url"]=h;out.append(item)
    return out

def prices(text):
    vals=[]
    for m in re.findall(r"(?:¥|￥)\s*([0-9]{2,3}(?:,[0-9]{3})+|[0-9]{5,7})",text):
        try:vals.append(int(m.replace(",","")))
        except Exception:pass
    for m in re.findall(r"(?<![0-9])([0-9]{2,3}(?:,[0-9]{3})+)\s*円",text):
        try:vals.append(int(m.replace(",","")))
        except Exception:pass
    return [x for x in vals if 50000<=x<=1000000]

def price(text):
    vals=prices(text)
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
    gpu=re.search(r"(RTX\s*(?:5090|5080|5070\s*Ti|5070|5060\s*Ti|5060)\s*Laptop(?:\s*GPU)?)",s,re.I)
    if gpu:out["gpu"]=gpu.group(1)
    tgp=re.search(r"(?:TGP|Total Graphics Power|最大(?:GPU)?電力)[^0-9]{0,30}(\d{2,3})\s*W",s,re.I)
    if tgp:out["tgp_w"]=int(tgp.group(1))
    ram=re.search(r"(?:メモリ|Memory|RAM)[^0-9]{0,18}(\d{1,3})\s*GB",s,re.I)
    if ram:out["ram_gb"]=int(ram.group(1))
    vram=re.search(r"(?:VRAM|ビデオメモリ)[^0-9]{0,20}(\d{1,2})\s*GB",s,re.I)
    if vram:out["vram_gb"]=int(vram.group(1))
    cpu_patterns=[
      r"Ryzen\s+9\s+\d{3,5}[A-Z0-9\-]*",r"Ryzen\s+7\s+\d{3,5}[A-Z0-9\-]*",
      r"Core\s+Ultra\s+9\s+\d{3}[A-Z]*",r"Core\s+Ultra\s+7\s+\d{3}[A-Z]*",
      r"Core\s+i9[- ]\d{4,5}[A-Z]*",r"Core\s+i7[- ]\d{4,5}[A-Z]*"
    ]
    for pat in cpu_patterns:
        m=re.search(pat,s,re.I)
        if m:
            out["cpu"]=m.group(0)
            break
    m=re.search(r"(?:SSD|ストレージ|Storage)[^0-9]{0,18}(\d+(?:\.\d+)?)\s*(TB|GB)",s,re.I)
    if m:out["ssd"]=m.group(1)+" "+m.group(2)
    return out

def parse_page(url,html):
    name=None;offer_price=None;offer_stock="unknown"
    blocks=re.findall(r'<script[^>]+type=["\\\']application/ld\\+json["\\\'][^>]*>(.*?)</script>',html,re.I|re.S)
    for b in blocks:
        try:
            x=json.loads(b.strip())
            objs=x if isinstance(x,list) else ([x] if isinstance(x,dict) else [])
        except Exception:
            continue
        for obj in objs:
            if "Product" not in str(obj.get("@type","")):continue
            name=obj.get("name") or name
            offers=obj.get("offers")
            if isinstance(offers,dict):
                try:offer_price=int(float(str(offers.get("price")).replace(",","")))
                except Exception:pass
                av=str(offers.get("availability",""))
                if "InStock" in av:offer_stock="in_stock"
                elif "OutOfStock" in av:offer_stock="out_of_stock"
    text_html=re.sub(r"<[^>]+>"," ",html)
    text_html=re.sub(r"\s+"," ",text_html)
    p=offer_price or price(text_html)
    return {
        "url":url,
        "store":urlparse(url).netloc.lower(),
        "name":name or url,
        "price_jpy":p,
        "stock_status":offer_stock if offer_stock!="unknown" else stock(text_html),
        "spec":specs(text_html[:400000]),
        "fetch_status":"ok",
        "observed_at":NOW.isoformat(),
        "last_checked_at":NOW.isoformat(),
        "price_source_mode":"direct_page",
        "data_confidence":"high" if p else "low"
    }

def host_allowed(url):
    host=urlparse(url).netloc.lower()
    return any(host==d or host.endswith("."+d) for d in PRIMARY_DOMAINS|SECONDARY_DOMAINS)

def relevance_score(query,text):
    tokens=[t for t in re.split(r"[^a-z0-9]+",query.lower()) if len(t)>=3]
    s=text.lower()
    return sum(1 for t in set(tokens) if t in s)

def search_fallback(query,canonical_url):
    try:results=ddg_search(query)
    except Exception:return None
    candidates=[]
    for r in results:
        if not host_allowed(r.get("url","")):continue
        blob=(r.get("title","")+" "+r.get("snippet","")).strip()
        p=price(blob)
        if p is None:continue
        rel=relevance_score(query,blob)
        if canonical_url and urlparse(r["url"]).netloc.lower()==urlparse(canonical_url).netloc.lower():
            rel+=4
        domain=urlparse(r["url"]).netloc.lower()
        source_bonus=4 if any(domain==d or domain.endswith("."+d) for d in PRIMARY_DOMAINS) else 1
        candidates.append((rel+source_bonus,p,r,blob))
    if not candidates:return None
    candidates.sort(key=lambda x:(x[0],-x[1]),reverse=True)
    rel,p,r,blob=candidates[0]
    return {
        "price_jpy":p,
        "stock_status":stock(blob),
        "spec":specs(blob),
        "source_url":r["url"],
        "source_title":r.get("title",""),
        "source_snippet":r.get("snippet",""),
        "confidence":"medium" if rel>=7 else "low"
    }

def normalize_watch_entry(entry):
    if isinstance(entry,str):
        return {"url":entry,"query":""}
    if isinstance(entry,dict):
        return {"url":entry.get("url",""),"query":entry.get("query",""),"priority":entry.get("priority","normal")}
    return {"url":"","query":""}

def fingerprint(x):
    stable={k:x.get(k) for k in ["url","name","price_jpy","stock_status","spec","fetch_status","price_source_mode","data_confidence"]}
    return hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def meaningful_change(prev,item):
    if not prev:return bool(item.get("price_jpy") is not None or item.get("spec"))
    return (
        prev.get("price_jpy")!=item.get("price_jpy") or
        prev.get("stock_status")!=item.get("stock_status") or
        prev.get("spec")!=item.get("spec")
    )

def main():
    latest_path=os.path.join(ROOT,"data/current_latest.json")
    events_path=os.path.join(ROOT,"data/change_events.jsonl")
    watch_path=os.path.join(ROOT,"data/watchlist.json")
    watch=read_json(watch_path,{"generated_at":None,"urls":[]})
    entries=[normalize_watch_entry(x) for x in watch.get("urls",[]) if normalize_watch_entry(x).get("url")]
    try:max_urls=max(1,min(int(os.environ.get("MONITOR_MAX_URLS","80")),80))
    except Exception:max_urls=80
    entries=entries[:max_urls]
    previous=read_json(latest_path,{}).get("products",[])
    previous_by_url={x["url"]:x for x in previous if x.get("url")}
    products=[];changes=[];fetch_stats={"direct_ok":0,"fallback_ok":0,"partial":0,"error":0,"total":len(entries)}

    for entry in entries:
        u=entry["url"];query=entry.get("query","");prev=previous_by_url.get(u)
        item=None
        try:
            html,final=fetch(u)
            item=parse_page(final,html)
            if item.get("price_jpy") is not None:
                item["last_fetch_status"]="ok"
                fetch_stats["direct_ok"]+=1
            else:
                fb=search_fallback(query,u) if query else None
                if fb:
                    item["price_jpy"]=fb["price_jpy"]
                    if item.get("stock_status")=="unknown":item["stock_status"]=fb["stock_status"]
                    if not item.get("spec"):item["spec"]=fb["spec"]
                    item["price_source_mode"]="search_snippet"
                    item["price_source_url"]=fb["source_url"]
                    item["price_source_title"]=fb["source_title"]
                    item["price_source_snippet"]=fb["source_snippet"]
                    item["data_confidence"]=fb["confidence"]
                    item["last_fetch_status"]="partial"
                    fetch_stats["fallback_ok"]+=1
                elif prev:
                    item=dict(prev);item["last_checked_at"]=NOW.isoformat();item["last_fetch_status"]="partial"
                    item["data_confidence"]=prev.get("data_confidence","medium")
                    fetch_stats["partial"]+=1
                else:
                    item["last_fetch_status"]="partial"
                    fetch_stats["partial"]+=1
            item["fingerprint"]=fingerprint(item)
        except Exception as exc:
            if prev:
                item=dict(prev)
                item["last_checked_at"]=NOW.isoformat()
                item["last_fetch_status"]="error"
                item["last_fetch_error"]=type(exc).__name__
                item["data_confidence"]=prev.get("data_confidence","medium")
                item["fingerprint"]=fingerprint(item)
            else:
                fb=search_fallback(query,u) if query else None
                if fb:
                    item={
                      "url":u,"store":urlparse(u).netloc.lower(),
                      "name":fb["source_title"] or u,
                      "price_jpy":fb["price_jpy"],
                      "stock_status":fb["stock_status"],
                      "spec":fb["spec"],
                      "fetch_status":"search_fallback",
                      "observed_at":NOW.isoformat(),
                      "last_checked_at":NOW.isoformat(),
                      "last_fetch_status":"error",
                      "last_fetch_error":type(exc).__name__,
                      "price_source_mode":"search_snippet",
                      "price_source_url":fb["source_url"],
                      "price_source_title":fb["source_title"],
                      "price_source_snippet":fb["source_snippet"],
                      "data_confidence":fb["confidence"]
                    }
                    item["fingerprint"]=fingerprint(item)
                    fetch_stats["fallback_ok"]+=1
                else:
                    item={"url":u,"store":urlparse(u).netloc.lower(),"name":u,
                          "price_jpy":None,"stock_status":"unknown","spec":{},
                          "fetch_status":"error","observed_at":NOW.isoformat(),
                          "last_checked_at":NOW.isoformat(),"last_fetch_status":"error",
                          "last_fetch_error":type(exc).__name__,
                          "price_source_mode":"none","data_confidence":"none",
                          "fingerprint":hashlib.sha256(u.encode()).hexdigest()}
                fetch_stats["error"]+=1

        products.append(item)
        if meaningful_change(prev,item):
            changes.append({
              "observed_at":item["observed_at"],
              "previous_observed_at":prev.get("last_checked_at") if prev else None,
              "url":u,"store":item.get("store"),"name":item.get("name"),
              "old_price_jpy":prev.get("price_jpy") if prev else None,
              "new_price_jpy":item.get("price_jpy"),
              "old_stock_status":prev.get("stock_status") if prev else None,
              "new_stock_status":item.get("stock_status"),
              "fetch_status":item.get("fetch_status"),
              "last_fetch_status":item.get("last_fetch_status"),
              "price_source_mode":item.get("price_source_mode"),
              "old_spec":prev.get("spec") if prev else None,
              "new_spec":item.get("spec"),
              "event_type":"new" if not prev else "changed"
            })

    # Always keep the latest observation state, but only meaningful changes enter the event log.
    write_json(latest_path,{
        "generated_at":NOW.isoformat(),
        "watchlist_generated_at":watch.get("generated_at"),
        "fetch_stats":fetch_stats,
        "products":products
    })
    if changes:
        os.makedirs(os.path.dirname(events_path),exist_ok=True)
        with open(events_path,"a",encoding="utf-8") as f:
            for e in changes:f.write(json.dumps(e,ensure_ascii=False)+"\n")
    print(json.dumps({"observed_at":NOW.isoformat(),"watch_urls":len(entries),
                      "products":len(products),"changes":len(changes),
                      "fetch_stats":fetch_stats},ensure_ascii=False))

if __name__=="__main__":main()
