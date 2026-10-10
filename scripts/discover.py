import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import quote, parse_qs, urlparse
from urllib.request import Request, urlopen

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; BF-PC-Price-Intelligence/3.0)"

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def stable_discovered_id(url):
    parsed = urlparse(url)
    canonical = parsed.scheme.lower() + "://" + parsed.netloc.lower() + parsed.path
    if parsed.query:
        pairs = []
        for k, vals in parse_qs(parsed.query, keep_blank_values=True).items():
            if k.lower().startswith(("utm_", "tracking", "ref")):
                continue
            for v in vals:
                pairs.append((k, v))
        pairs.sort()
        canonical += "?" + "&".join(f"{k}={v}" for k, v in pairs)
    return "discovered-" + hashlib.sha1(canonical.encode()).hexdigest()[:16]

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            if d.get("href"):
                self.links.append(d["href"])

def fetch(url, timeout=20):
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ja-JP,ja;q=0.9"})
    with urlopen(req, timeout=timeout) as r:
        enc = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(enc, errors="replace")

def search(query):
    html = fetch("https://html.duckduckgo.com/html/?q=" + quote(query))
    p = LinkParser()
    p.feed(html)
    out, seen = [], set()
    for h in p.links:
        if "uddg=" in h:
            u = parse_qs(urlparse(h).query).get("uddg")
            if u:
                h = u[0]
        if h.startswith("http") and h not in seen:
            seen.add(h)
            out.append(h)
    return out

def allowed(url, domains):
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in domains)

def useful(url):
    combined = urlparse(url).path.lower() + "?" + urlparse(url).query.lower()
    blocked = ("/search", "/filter", "/category", "/campaigns/black-friday", "/store/laptops/for-gaming/all-series")
    return not any(x in combined for x in blocked)

def main():
    cfg = load(os.path.join(ROOT, "config", "targets.json"), {})
    watch_path = os.path.join(ROOT, "data", "watchlist.json")
    previous = load(watch_path, {"generated_at": None, "urls": []})
    previous_ids = {
        str(e.get("id") or "")
        for e in (previous.get("urls") or [])
        if isinstance(e, dict) and e.get("id")
    }
    catalog_data = load(os.path.join(ROOT, "config", "candidate_catalog.json"), {"candidates": []})
    catalog_items = [
        x for x in (catalog_data.get("candidates") or [])
        if isinstance(x, dict) and x.get("id") and x.get("url")
    ]
    catalog_by_id = {str(x["id"]): x for x in catalog_items}
    entries, seen_ids, seen_urls = [], set(), set()

    def add(entry):
        if isinstance(entry, str):
            entry = {"url": entry, "query": "", "priority": "normal"}
        elif isinstance(entry, dict):
            entry = dict(entry)
        else:
            return
        url = entry.get("url", "")
        if not url.startswith("http") or not allowed(url, cfg.get("allowed_domains", [])) or not useful(url):
            return
        cid = str(entry.get("id") or stable_discovered_id(url))
        catalog_item = catalog_by_id.get(cid, {})
        # A non-exact family page may represent multiple curated SKUs. Keep
        # each SKU as a separate identity so the monitor can mark it ambiguous
        # instead of silently omitting it. Search-only results remain URL-deduped.
        shared_catalog_page = bool(catalog_item) and not bool(catalog_item.get("url_is_exact"))
        if cid in seen_ids or (url in seen_urls and not shared_catalog_page):
            return
        entry["id"] = cid
        entry.setdefault("query", "")
        entry.setdefault("priority", "discovered")
        seen_ids.add(cid)
        seen_urls.add(url)
        entries.append(entry)

    for entry in previous.get("urls", []):
        # When the curated SKU URL is corrected, update the saved watch entry
        # by ID before deduplication; otherwise the stale URL wins forever.
        if isinstance(entry, dict):
            cid = str(entry.get("id") or "")
            curated = catalog_by_id.get(cid)
            if curated and curated.get("url") and entry.get("url") != curated["url"]:
                entry = dict(entry)
                entry["url"] = curated["url"]
                aliases = curated.get("aliases") or []
                entry.setdefault("query", aliases[0] if aliases else (curated.get("name") or "curated catalog candidate"))
        add(entry)

    # The curated catalog is authoritative for candidate identity/coverage.
    # Re-add missing catalog entries after stale/corrupt watchlists and allow
    # multiple distinct SKUs to reference a shared non-exact family page.
    for item in catalog_items:
        aliases = item.get("aliases") or []
        add({
            "id": str(item["id"]),
            "url": item["url"],
            "query": aliases[0] if aliases else (item.get("name") or "curated catalog candidate"),
            "priority": "high",
        })

    for query in cfg.get("queries", []):
        try:
            found = search(query)
        except Exception:
            continue
        for url in found:
            add({"url": url, "query": query, "priority": "discovered"})

    priorities = {"critical": 0, "high": 1, "normal": 2, "discovered": 3}
    entries.sort(key=lambda e: priorities.get(e.get("priority"), 9))
    entries = entries[:100]

    now = datetime.now(JST).replace(microsecond=0).isoformat()
    current_ids = {str(e.get("id") or "") for e in entries if e.get("id")}
    added_ids = sorted(current_ids - previous_ids)
    retained_ids = sorted(current_ids & previous_ids)
    removed_ids = sorted(previous_ids - current_ids)
    discovery_stats = {
        "previous_count": len(previous_ids),
        "current_count": len(current_ids),
        "newly_discovered_count": len(added_ids),
        "retained_count": len(retained_ids),
        "removed_count": len(removed_ids),
        "newly_discovered_ids": added_ids[:100],
        "removed_ids": removed_ids[:100],
    }
    previous.update({
        "generated_at": now,
        "urls": entries,
        "discovery_status": "ok" if entries else "empty",
        "discovery_error": None if entries else "No usable URLs discovered.",
        "discovered_count": len(entries),
        "discovery_stats": discovery_stats,
    })
    save(watch_path, previous)
    print(json.dumps({"generated_at": now, "urls": len(entries), "status": previous["discovery_status"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
