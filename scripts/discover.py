import json,os
from html.parser import HTMLParser
from urllib.parse import quote,parse_qs,urlparse
from urllib.request import Request,urlopen
from datetime import datetime,timezone,timedelta

JST=timezone(timedelta(hours=9))
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW=datetime.now(JST).replace(microsecond=0)
UA="Mozilla/5.0 (compatible; BF-PC-Price-Intelligence/1.1)"

def load(path,default):
    try:
        with open(path,"r",encoding="utf-8") as f:return json.load(f)
    except Exception:return default

def save(path,obj):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2)

def fetch(url):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"ja-JP,ja;q=0.9"})
    with urlopen(req,timeout=20) as r:
        enc=r.headers.get_content_charset() or "utf-8"
        return r.read().decode(enc,errors="replace")

class P(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            d=dict(attrs)
            if d.get("href"):self.links.append(d["href"])

def search(q):
    html=fetch("https://html.duckduckgo.com/html/?q="+quote(q))
    p=P();p.feed(html)
    out=[];seen=set()
    for h in p.links:
        if "uddg=" in h:
            u=parse_qs(urlparse(h).query).get("uddg")
            if u:h=u[0]
        if h.startswith("http") and h not in seen:
            seen.add(h);out.append(h)
    return out

def allowed(u,domains):
    host=urlparse(u).netloc.lower()
    return any(host==d or host.endswith("."+d) for d in domains)

def useful(u):
    p=urlparse(u).path.lower()
    blocked=["/filter","/search","/search?","/store/laptops/for-gaming","/laptops/for-gaming/all-series"]
    return not any(x in (p+"?"+urlparse(u).query.lower()) for x in blocked)

def main():
    cfg=load(os.path.join(ROOT,"config/targets.json"),{})
    urls=[];seen=set()
    previous=load(os.path.join(ROOT,"data/watchlist.json"),{"generated_at":None,"urls":[]})
    # Preserve all known URLs first; discovery only appends new candidates.
    for u in previous.get("urls",[]):
        if isinstance(u,str) and u.startswith("http") and u not in seen:
            seen.add(u);urls.append(u)
    for q in cfg.get("queries",[]):
        try:found=search(q)
        except Exception:continue
        for u in found:
            if not allowed(u,cfg.get("allowed_domains",[])) or not useful(u) or u in seen:continue
            seen.add(u);urls.append(u)
    urls=urls[:100]
    watch_path=os.path.join(ROOT,"data/watchlist.json")
    previous["generated_at"]=NOW.isoformat()
    previous["urls"]=urls
    previous["discovery_status"]="ok" if urls else "empty"
    previous["discovery_error"]=None if urls else "No usable URLs discovered."
    save(watch_path,previous)
    print(json.dumps({"generated_at":NOW.isoformat(),"urls":len(urls),"status":previous["discovery_status"]},ensure_ascii=False))

if __name__=="__main__":main()
