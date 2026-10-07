import hashlib
import json
import os
import re
import subprocess
import time
from html.parser import HTMLParser
from urllib.parse import quote, parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from intelligence import (
    ROOT, JST, load_json, save_json, load_catalog, now_jst,
    norm_text, pick_price, price_candidates, validate_price,
    enrich_identity, iso, plausible_floor
)

PRIMARY_DOMAINS = {
    "lenovo.com", "asus.com", "hp.com", "msi.com", "acer.com", "gigabyte.com",
    "mouse-jp.co.jp", "dospara.co.jp", "tsukumo.co.jp", "frontier-direct.jp",
    "sycom.co.jp", "ark-pc.co.jp", "stormst.com"
}
SECONDARY_DOMAINS = {
    "kakaku.com", "ascii.jp", "pc.watch.impress.co.jp",
    "akiba-pc.watch.impress.co.jp", "joshinweb.jp", "shop.applied-net.co.jp"
}
UA = "Mozilla/5.0 (compatible; BF-PC-Price-Intelligence/3.0)"

def read(path, default):
    return load_json(path, default)

def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

def fetch(url, timeout=18):
    headers = {
        "User-Agent": UA,
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as r:
            enc = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(enc, errors="replace"), r.geturl(), dict(r.headers)
    except (HTTPError, URLError, TimeoutError):
        # A second request with a normal browser UA handles transient blocks
        # without trusting the response unless it actually returns 2xx/3xx.
        time.sleep(1)
        browser_headers = dict(headers)
        browser_headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
        )
        try:
            req = Request(url, headers=browser_headers)
            with urlopen(req, timeout=timeout) as r:
                enc = r.headers.get_content_charset() or "utf-8"
                return r.read().decode(enc, errors="replace"), r.geturl(), dict(r.headers)
        except (HTTPError, URLError, TimeoutError):
            pass

    # GitHub-hosted runners normally include curl. It is used only as a
    # transport fallback; candidate URLs still come exclusively from the
    # curated watchlist/catalog.
    cmd = [
        "curl", "-L", "--compressed", "-sS",
        "--connect-timeout", str(min(10, timeout)),
        "--max-time", str(timeout),
        "-A", (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
        ),
        "-H", "Accept-Language: ja-JP,ja;q=0.9,en;q=0.5",
        "-H", "Cache-Control: no-cache",
        "-w", "\n__BF_STATUS__:%{http_code}\n__BF_URL__:%{url_effective}",
        url,
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=False, timeout=timeout + 5, check=False)
        body = p.stdout.decode("utf-8", errors="replace")
        status_marker = "\n__BF_STATUS__:"
        url_marker = "\n__BF_URL__:"
        if status_marker in body and url_marker in body:
            body_part, tail = body.rsplit(status_marker, 1)
            status_text, final_url = tail.split(url_marker, 1)
            status = int(status_text.strip())
            final_url = final_url.strip()
            if 200 <= status < 400:
                return body_part, final_url or url, {
                    "X-BF-Fetch-Method": "curl",
                    "X-BF-HTTP-Status": str(status),
                }
            raise RuntimeError(f"curl_http_{status}")
        if p.returncode != 0:
            raise RuntimeError(f"curl_exit_{p.returncode}")
    except Exception as exc:
        raise exc
    raise RuntimeError("curl_no_response")

class SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None
        self.capture = None
        self.buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "a" and "result__a" in cls:
            self.current = {"url": d.get("href", ""), "title": ""}
            self.capture = "title"
            self.buf = []
        elif tag in ("a", "div", "span") and "result__snippet" in cls and self.current:
            self.capture = "snippet"
            self.buf = []

    def handle_endtag(self, tag):
        if self.capture and tag in ("a", "div", "span"):
            text = " ".join("".join(self.buf).split())
            if self.capture == "title" and self.current:
                self.current["title"] = text
            elif self.capture == "snippet" and self.current:
                self.current["snippet"] = text
                self.results.append(self.current)
                self.current = None
            self.capture = None
            self.buf = []

    def handle_data(self, data):
        if self.capture:
            self.buf.append(data)

def ddg_search(query, timeout=20):
    if not query:
        return []
    req = Request(
        "https://html.duckduckgo.com/html/?q=" + quote(query),
        headers={"User-Agent": UA, "Accept-Language": "ja-JP,ja;q=0.9"},
    )
    with urlopen(req, timeout=timeout) as r:
        enc = r.headers.get_content_charset() or "utf-8"
        html = r.read().decode(enc, errors="replace")
    p = SearchParser()
    p.feed(html)
    out = []
    for item in p.results:
        h = item.get("url", "")
        if "uddg=" in h:
            u = parse_qs(urlparse(h).query).get("uddg")
            if u:
                h = u[0]
        if h.startswith("http"):
            item["url"] = h
            out.append(item)
    return out

def host_allowed(url):
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in PRIMARY_DOMAINS | SECONDARY_DOMAINS)

def source_bonus(url):
    host = urlparse(url).netloc.lower()
    return 4 if any(host == d or host.endswith("." + d) for d in PRIMARY_DOMAINS) else 1

def stock_from_text(text):
    s = norm_text(text)
    if any(x in s for x in ("在庫切れ", "品切れ", "売り切れ", "out of stock", "sold out", "在庫なし")):
        return "out_of_stock"
    if any(x in s for x in ("残りわずか", "low stock", "only 1", "only one", "残り1")):
        return "low_stock"
    if any(x in s for x in ("取り寄せ", "予約", "preorder", "back order")):
        return "preorder_or_backorder"
    if any(x in s for x in ("在庫あり", "in stock", "お取り寄せ可能")):
        return "in_stock"
    return "unknown"

def _spec_window(text, hints=None):
    s = " ".join(str(text or "").split())
    hints = hints or {}
    terms = [str(x) for x in (hints.get("aliases") or []) if x]
    for key in ("model_code", "name", "id", "query"):
        if hints.get(key):
            terms.append(str(hints[key]))
    compact = "".join(s.split()).lower()
    best = None
    for term in terms:
        t = "".join(norm_text(term).split()).lower()
        if not t:
            continue
        pos = compact.find(t)
        if pos >= 0:
            # Use the compact position only as an anchor; widen enough to include the surrounding spec table.
            best = pos if best is None else min(best, pos)
    if best is None:
        return s[:14000]
    return s[max(0, best-3500):min(len(s), best+12000)]

def parse_specs(text, hints=None):
    s = _spec_window(text, hints)
    out = {}
    gpu_patterns = [
        r"(RTX\s*(?:5090|5080|5070\s*Ti|5070|5060\s*Ti|5060)(?:\s*Laptop(?:\s*GPU)?)?)",
        r"(Radeon\s+RX\s*(?:9070\s*XT|9070|9060\s*XT|9060|9050|7900\s*(?:XTX|XT)|7800\s*XT|7700\s*XT))",
    ]
    for pat in gpu_patterns:
        m = re.search(pat, s, re.I)
        if m:
            out["gpu"] = re.sub(r"\s+", " ", m.group(1)).strip()
            break
    tgp = re.search(r"(?:TGP|Total Graphics Power|最大(?:GPU)?電力|GPU電力)[^0-9]{0,40}(\d{2,3})\s*W", s, re.I)
    if tgp:
        out["tgp_w"] = int(tgp.group(1))
    ram = re.search(r"(?:メモリ|Memory|RAM)[^0-9]{0,18}(\d{1,3})\s*GB", s, re.I)
    if ram:
        out["ram_gb"] = int(ram.group(1))
    vram = re.search(r"(?:VRAM|ビデオメモリ)[^0-9]{0,20}(\d{1,2})\s*GB", s, re.I)
    if vram:
        out["vram_gb"] = int(vram.group(1))
    cpu_patterns = [
        r"Ryzen\s+9\s+\d{3,5}[A-Z0-9\-]*",
        r"Ryzen\s+7\s+\d{3,5}[A-Z0-9\-]*",
        r"Ryzen\s+5\s+\d{3,5}[A-Z0-9\-]*",
        r"Core\s+Ultra\s+9\s+\d{3,5}[A-Z0-9\-]*",
        r"Core\s+Ultra\s+7\s+\d{3,5}[A-Z0-9\-]*",
        r"Core\s+Ultra\s+5\s+\d{3,5}[A-Z0-9\-]*",
        r"Core\s+i9[- ]\d{4,5}[A-Z0-9\-]*",
        r"Core\s+i7[- ]\d{4,5}[A-Z0-9\-]*",
        r"Core\s+i5[- ]\d{4,5}[A-Z0-9\-]*",
    ]
    for pat in cpu_patterns:
        m = re.search(pat, s, re.I)
        if m:
            out["cpu"] = re.sub(r"\s+", " ", m.group(0)).strip()
            break
    m = re.search(r"(?:SSD|ストレージ|Storage|M\.2 SSD)[^0-9]{0,18}(\d+(?:\.\d+)?)\s*(TB|GB)", s, re.I)
    if m:
        out["ssd"] = m.group(1) + " " + m.group(2)
    if re.search(r"(?:デスクトップ(?:PC|パソコン)?|Desktop PC)", s, re.I):
        out["form_factor"] = "desktop"
    elif re.search(r"(?:ノート(?:PC|パソコン)?|Laptop PC)", s, re.I):
        out["form_factor"] = "laptop"
    psu = re.search(r"(?:電源|Power Supply)[^0-9]{0,30}(\d{3,4})\s*W", s, re.I)
    if psu:
        out["psu_w"] = int(psu.group(1))
    if re.search(r"(?:水冷|簡易水冷)", s, re.I):
        mm = re.search(r"(\d{2,3})\s*mm\s*(?:ラジエーター|radiator)", s, re.I)
        out["cooler"] = f"{mm.group(1)}mm liquid" if mm else "liquid"
    elif re.search(r"(?:CPUクーラー[^\n]{0,40}|空冷)", s, re.I):
        out["cooler"] = "air"
    return out

def extract_benefit_signals(text):
    """Extract benefit hints without treating them as guaranteed cash savings."""
    s = re.sub(r"\s+", " ", str(text or ""))
    signals = []
    patterns = [
        (r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:分|相当)?\s*(?:の)?(?:ポイント|ポイント還元|還元)",
         "point_value_jpy"),
        (r"(?:ポイント|還元)[^0-9]{0,20}([0-9]{1,2})\s*%",
         "point_percent"),
        (r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:の)?(?:キャッシュバック|還元)",
         "cashback_value_jpy"),
        (r"(?:周辺機器|アクセサリ)[^。\n]{0,60}([0-9]{1,2})\s*%\s*(?:OFF|オフ)",
         "accessory_bundle_percent"),
    ]
    seen = set()
    for pat, kind in patterns:
        for m in re.finditer(pat, s, re.I):
            raw = m.group(1)
            try:
                value = int(raw.replace(",", "")) if "value_jpy" in kind else int(raw)
            except ValueError:
                continue
            key = (kind, value)
            if key in seen:
                continue
            seen.add(key)
            signals.append({
                "kind": kind,
                "value": value,
                "text": s[max(0, m.start()-60):min(len(s), m.end()+60)],
                "certainty": "unconfirmed",
                "counts_toward_effective_cost": False,
            })
    return signals


def parse_page(url, html, expected=None):
    text_html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text_html = re.sub(r"<style[^>]*>.*?</style>", " ", text_html, flags=re.I | re.S)
    text_html = re.sub(r"<[^>]+>", " ", text_html)
    text_html = re.sub(r"\s+", " ", text_html)

    name = None
    structured_offers = []
    all_availability_states = set()
    structured_stock = "unknown"
    price_ambiguity = None
    matched_structured = False

    expected_terms = []
    if expected:
        expected_terms.extend([str(x) for x in (expected.get("aliases") or []) if x])
        for key in ("model_code", "name"):
            if expected.get(key):
                expected_terms.append(str(expected[key]))

    def _jsonld_name_matches(product_name):
        pn = "".join(norm_text(product_name).split())
        if not pn or not expected_terms:
            return False
        return any(
            "".join(norm_text(term).split()) in pn or
            pn in "".join(norm_text(term).split())
            for term in expected_terms
        )

    blocks = re.findall(
        r'<script[^>]+type=["\\\']application/ld\+json["\\\'][^>]*>(.*?)</script>',
        html, re.I | re.S
    )
    for block in blocks:
        try:
            x = json.loads(block.strip())
        except Exception:
            continue
        objs = x if isinstance(x, list) else [x] if isinstance(x, dict) else []
        for obj in objs:
            if "Product" not in str(obj.get("@type", "")):
                continue
            product_name = str(obj.get("name") or "")
            name = obj.get("name") or name
            matched = _jsonld_name_matches(product_name)
            if matched:
                matched_structured = True
            offers = obj.get("offers")
            offers_list = offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []
            for offer in offers_list:
                if not isinstance(offer, dict):
                    continue
                currency = str(offer.get("priceCurrency") or "").upper()
                try:
                    p = int(float(str(offer.get("price")).replace(",", "")))
                except Exception:
                    p = None
                if p and (currency in ("JPY", "YEN", "") or "¥" in str(offer.get("price"))):
                    structured_offers.append({
                        "price": p,
                        "matched": matched,
                        "availability": str(offer.get("availability") or ""),
                    })

    selected_offers = [x for x in structured_offers if x["matched"]] if matched_structured else structured_offers
    unique_structured_prices = sorted(set(x["price"] for x in selected_offers))
    structured_price = unique_structured_prices[0] if len(unique_structured_prices) == 1 else None
    if len(unique_structured_prices) > 1:
        price_ambiguity = "multiple_structured_prices"

    selected_states = {x["availability"] for x in selected_offers if x["availability"]}
    for av in selected_states:
        if "InStock" in av:
            all_availability_states.add("in_stock")
        elif "OutOfStock" in av:
            all_availability_states.add("out_of_stock")
        elif "PreOrder" in av or "BackOrder" in av:
            all_availability_states.add("preorder_or_backorder")

    meta = re.search(
        r'<meta[^>]+(?:property|name)=["\\\']product:price:amount["\\\'][^>]+content=["\\\']([^"\\\']+)',
        html, re.I
    )
    meta_price = None
    if meta:
        try:
            meta_price = int(float(meta.group(1).replace(",", "")))
        except Exception:
            meta_price = None

    picked = None
    if price_ambiguity:
        picked = None
    elif structured_price:
        picked = {"price_jpy": structured_price, "source": "direct_structured"}
    elif meta_price:
        picked = {"price_jpy": meta_price, "source": "direct_meta"}
    else:
        raw = pick_price(text_html)
        if raw:
            picked = {"price_jpy": raw["price_jpy"], "source": "direct_text", "context": raw["context"]}

    text_stock = stock_from_text(text_html)
    if len(all_availability_states) > 1:
        final_stock = "unknown"
    elif text_stock in ("out_of_stock", "low_stock", "preorder_or_backorder"):
        final_stock = text_stock
    elif structured_stock != "unknown":
        final_stock = structured_stock
    else:
        final_stock = text_stock

    specs = parse_specs(text_html[:450000], expected=expected)
    benefit_signals = extract_benefit_signals(text_html[:450000])
    return {
        "url": url,
        "store": urlparse(url).netloc.lower(),
        "name": name or url,
        "price_jpy": picked["price_jpy"] if picked else None,
        "stock_status": final_stock,
        "stock_ambiguity": "multiple_offer_availability" if len(availability_states) > 1 else None,
        "parsed_spec": specs,
        "page_text_excerpt": text_html[:12000],
        "benefit_signals": benefit_signals,
        "confirmed_benefit_value_jpy": 0,
        "benefit_confidence": "unconfirmed",
        "fetch_status": "ok",
        "price_source_mode": picked["source"] if picked else "none",
        "price_context": picked.get("context") if picked else None,
        "price_ambiguity": price_ambiguity,
        "data_confidence": "high" if picked and picked["source"] == "direct_structured" else "medium" if picked else "low",
    }

def relevance(query, blob):
    tokens = [t for t in re.split(r"[^a-z0-9]+", norm_text(query)) if len(t) >= 3]
    s = norm_text(blob)
    return sum(1 for t in set(tokens) if t in s)

def search_fallback(query, canonical_url):
    try:
        results = ddg_search(query)
    except Exception:
        return None
    candidates = []
    for r in results:
        u = r.get("url", "")
        if not host_allowed(u):
            continue
        blob = (r.get("title", "") + " " + r.get("snippet", "")).strip()
        raw = pick_price(blob)
        if not raw:
            continue
        rel = relevance(query, blob)
        if canonical_url and urlparse(u).netloc.lower() == urlparse(canonical_url).netloc.lower():
            rel += 4
        candidates.append({
            "rank": rel + source_bonus(u),
            "url": u,
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "price_jpy": raw["price_jpy"],
            "stock_status": stock_from_text(blob),
            "spec": parse_specs(blob),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x["rank"], -x["price_jpy"]), reverse=True)
    return candidates[0]

def normalize_entry(entry):
    if isinstance(entry, str):
        return {"id": entry, "url": entry, "query": "", "priority": "normal"}
    if isinstance(entry, dict):
        out = dict(entry)
        out["id"] = out.get("id") or out.get("url", "")
        out["url"] = out.get("url", "")
        out["query"] = out.get("query", "")
        out["priority"] = out.get("priority", "normal")
        return out
    return {"id": "", "url": "", "query": "", "priority": "normal"}

def fingerprint(item):
    stable = {
        k: item.get(k)
        for k in ("id", "url", "current_price_jpy", "stock_status",
                  "spec", "price_validation_status", "price_source_mode",
                  "benefit_signals", "confirmed_benefit_value_jpy",
                  "benefit_confidence",
                  "variant_match", "fetch_status")
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def load_last_event_prices(path):
    last = {}
    if not os.path.exists(path):
        return last
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            cid = str(e.get("id") or "")
            if cid and e.get("new_price_jpy") is not None:
                last[cid] = e
    return last

def meaningful_change(prev, item):
    if not prev:
        return item.get("current_price_jpy") is not None or item.get("stock_status") != "unknown"
    return (
        prev.get("current_price_jpy") != item.get("current_price_jpy") or
        prev.get("stock_status") != item.get("stock_status") or
        prev.get("price_validation_status") != item.get("price_validation_status") or
        prev.get("variant_match") != item.get("variant_match") or
        prev.get("benefit_signals") != item.get("benefit_signals") or
        prev.get("confirmed_benefit_value_jpy") != item.get("confirmed_benefit_value_jpy")
    )

def apply_observation(entry, raw, previous, catalog_item, retrieval_time):
    cid = entry["id"]
    current_url = entry["url"]
    previous_valid = previous.get("current_price_jpy") if previous else None
    reference = previous_valid
    if reference is None and catalog_item:
        reference = catalog_item.get("reference_price_jpy")
    if reference is None and catalog_item:
        reference = catalog_item.get("price_jpy")

    item = {
        "id": cid,
        "url": current_url,
        "query": entry.get("query", ""),
        "priority": entry.get("priority", "normal"),
        "retrieval_time": retrieval_time,
        "observed_at": retrieval_time,
        "available_at": retrieval_time if raw and raw.get("price_jpy") is not None else None,
        "fetch_status": "ok",
        "last_fetch_status": "ok",
        "last_fetch_error": None,
        "current_price_jpy": None,
        "price_jpy": None,
        "last_valid_price_jpy": previous_valid,
        "stock_status": "unknown",
        "price_source_mode": "none",
        "price_validation_status": "missing",
        "price_validation_reason": "price_missing",
        "data_confidence": "low",
        "name": entry.get("name") or (catalog_item or {}).get("name") or current_url,
        "family": (catalog_item or {}).get("family"),
        "parsed_spec": {},
        "spec": {},
        "page_text_excerpt": "",
        "benefit_signals": [],
        "confirmed_benefit_value_jpy": 0,
        "benefit_confidence": "unconfirmed",
    }

    if raw:
        item.update({
            "name": raw.get("name") or item["name"],
            "stock_status": raw.get("stock_status") or "unknown",
            "price_source_mode": raw.get("price_source_mode") or "none",
            "data_confidence": raw.get("data_confidence") or "low",
            "parsed_spec": raw.get("parsed_spec") or {},
            "page_text_excerpt": raw.get("page_text_excerpt") or "",
            "price_context": raw.get("price_context"),
            "benefit_signals": raw.get("benefit_signals") or [],
            "confirmed_benefit_value_jpy": 0,
            "benefit_confidence": "unconfirmed",
        })
        item = enrich_identity(item, catalog_item)
        candidate_price = raw.get("price_jpy")
        if candidate_price is not None:
            val = validate_price(candidate_price, item, reference_price=reference, corroborated=False)
            item["price_validation_status"] = val["status"]
            item["price_validation_reason"] = val["reason"]
            if val["valid"]:
                item["current_price_jpy"] = candidate_price
                item["price_jpy"] = candidate_price
                item["available_at"] = retrieval_time
                item["last_valid_price_jpy"] = candidate_price
            else:
                item["current_price_jpy"] = None
        if item.get("current_price_jpy") is None and previous_valid is not None:
            item["price_source_mode"] = "stale_previous"
            item["price_validation_status"] = item.get("price_validation_status") or "missing"
            item["data_confidence"] = "low"
    else:
        item = enrich_identity(item, catalog_item)

    return item

def corroborate_anomaly(item, search):
    if not search or item.get("price_validation_status") != "anomaly_rejected":
        return item
    p = item.get("price_jpy")
    if p is None:
        return item
    sp = search.get("price_jpy")
    if sp is None:
        return item
    item["parsed_spec"] = {**item.get("parsed_spec", {}), **search.get("spec", {})}
    item["page_text_excerpt"] = ((search.get("title") or "") + " " + (search.get("snippet") or ""))[:12000]
    item = enrich_identity(item, load_catalog().get(str(item.get("id")), {}))
    reference = item.get("last_valid_price_jpy") or item.get("reference_price_jpy")
    checked = validate_price(sp, item, reference_price=reference, corroborated=False)
    identity_ok = item.get("variant_match") in ("exact", "trusted_url", "strong")
    close_to_anomalous = abs(sp - p) / float(max(1, p)) <= 0.10
    if checked["valid"] and identity_ok and close_to_anomalous:
        item["current_price_jpy"] = sp
        item["price_jpy"] = sp
        item["available_at"] = item.get("retrieval_time")
        item["price_validation_status"] = "anomaly_corroborated"
        item["price_validation_reason"] = "independent_search_corroboration"
        item["price_source_mode"] = "search_snippet"
        item["data_confidence"] = "medium"
        item["corroborating_source_url"] = search.get("url")
        item["corroborating_source_title"] = search.get("title")
        item["corroborating_source_snippet"] = search.get("snippet")
    return item

def main():
    watch_path = os.path.join(ROOT, "data", "watchlist.json")
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    event_path = os.path.join(ROOT, "data", "change_events.jsonl")

    watch = read(watch_path, {"generated_at": None, "urls": []})
    entries = [normalize_entry(x) for x in watch.get("urls", [])]
    entries = [x for x in entries if x.get("id") and x.get("url")]

    try:
        max_urls = max(1, min(int(os.environ.get("MONITOR_MAX_URLS", "80")), 80))
    except Exception:
        max_urls = 80
    entries = entries[:max_urls]

    previous_state = read(latest_path, {"products": []})
    previous_by_id = {
        str(x.get("id")): x for x in previous_state.get("products", []) if x.get("id")
    }
    catalog = load_catalog()

    products = []
    changes = []
    stats = {
        "total": len(entries),
        "direct_verified": 0,
        "search_corrob": 0,
        "stale_previous": 0,
        "baseline_only": 0,
        "anomaly_rejected": 0,
        "errors": 0,
    }
    retrieval_time = iso(now_jst())

    for entry in entries:
        cid = entry["id"]
        previous = previous_by_id.get(cid, {})
        cat = catalog.get(cid, {})
        raw = None
        request_error = None

        try:
            html, final_url, _headers = fetch(entry["url"])
            raw = parse_page(final_url, html, expected=cat)
        except HTTPError as exc:
            request_error = f"HTTPError:{exc.code}"
        except URLError as exc:
            request_error = f"URLError:{getattr(exc, 'reason', 'unknown')}"
        except Exception as exc:
            request_error = type(exc).__name__

        item = apply_observation(entry, raw, previous, cat, retrieval_time)

        if request_error:
            item["fetch_status"] = "error"
            item["last_fetch_status"] = "error"
            item["last_fetch_error"] = request_error
            stats["errors"] += 1

            fallback = search_fallback(entry.get("query", ""), entry["url"]) if entry.get("query") else None
            if fallback:
                item["name"] = fallback.get("title") or item["name"]
                item["stock_status"] = item["stock_status"] if item["stock_status"] != "unknown" else fallback["stock_status"]
                item["parsed_spec"] = {**fallback.get("spec", {}), **item.get("parsed_spec", {})}
                item["page_text_excerpt"] = item.get("page_text_excerpt", "")
                item["page_text_excerpt"] = ((fallback.get("title") or "") + " " + (fallback.get("snippet") or ""))[:12000]
                item = enrich_identity(item, cat)
                reference = item.get("last_valid_price_jpy")
                if reference is None:
                    reference = cat.get("reference_price_jpy", cat.get("price_jpy"))
                checked = validate_price(fallback["price_jpy"], item, reference_price=reference, corroborated=False)
                identity_ok = item.get("variant_match") in ("exact", "trusted_url", "strong")
                if checked["valid"] and identity_ok:
                    item["price_jpy"] = fallback["price_jpy"]
                    item["current_price_jpy"] = fallback["price_jpy"]
                    item["last_valid_price_jpy"] = fallback["price_jpy"]
                    item["available_at"] = retrieval_time
                    item["price_source_mode"] = "search_snippet"
                    item["price_validation_status"] = checked["status"]
                    item["price_validation_reason"] = "search_fallback:" + checked["reason"]
                    item["data_confidence"] = "medium"
                    item["corroborating_source_url"] = fallback["url"]
                    item["corroborating_source_title"] = fallback["title"]
                    item["corroborating_source_snippet"] = fallback["snippet"]
                    stats["search_corrob"] += 1
                else:
                    item["current_price_jpy"] = None
                    item["price_jpy"] = None
                    item["price_validation_status"] = "reference_only" if reference is not None else "missing"
                    item["price_validation_reason"] = "search_fallback_rejected:" + ("identity_mismatch" if not identity_ok else checked["reason"])
            elif previous.get("current_price_jpy") is not None:
                item["current_price_jpy"] = None
                item["price_jpy"] = None
                item["last_valid_price_jpy"] = previous.get("current_price_jpy")
                item["price_source_mode"] = "stale_previous"
                item["available_at"] = None
                item["data_confidence"] = "low"
                stats["stale_previous"] += 1
            elif cat.get("reference_price_jpy") is not None or cat.get("price_jpy") is not None:
                item["reference_price_jpy"] = cat.get("reference_price_jpy", cat.get("price_jpy"))
                item["price_source_mode"] = "public_baseline"
                item["price_validation_status"] = "reference_only"
                item["data_confidence"] = "low"
                item["current_price_jpy"] = None
                item["price_jpy"] = None
                stats["baseline_only"] += 1

        else:
            # If a suspicious direct price appeared, use an independent search before discarding it.
            if item.get("price_validation_status") == "anomaly_rejected" and entry.get("query"):
                fallback = search_fallback(entry["query"], entry["url"])
                item = corroborate_anomaly(item, fallback)
                if item.get("price_validation_status") == "anomaly_rejected":
                    stats["anomaly_rejected"] += 1
            if item.get("current_price_jpy") is not None and item.get("price_validation_status") != "anomaly_rejected":
                stats["direct_verified"] += 1
            elif item.get("price_validation_status") == "anomaly_rejected":
                stats["anomaly_rejected"] += 1

        item["fingerprint"] = fingerprint(item)
        products.append(item)

        if meaningful_change(previous, item):
            old_price = previous.get("current_price_jpy")
            new_price = item.get("current_price_jpy")
            event = {
                "id": cid,
                "observed_at": retrieval_time,
                "event_time": None,
                "event_time_upper_bound": retrieval_time,
                "publication_time": item.get("source_publication_time"),
                "available_at": item.get("available_at"),
                "retrieval_time": retrieval_time,
                "prediction_time": retrieval_time,
                "pit_valid": bool(item.get("available_at") and item.get("available_at") <= retrieval_time),
                "url": entry["url"],
                "store": item.get("store"),
                "name": item.get("name"),
                "old_price_jpy": old_price,
                "new_price_jpy": new_price,
                "old_stock_status": previous.get("stock_status"),
                "new_stock_status": item.get("stock_status"),
                "fetch_status": item.get("fetch_status"),
                "last_fetch_status": item.get("last_fetch_status"),
                "price_source_mode": item.get("price_source_mode"),
                "price_validation_status": item.get("price_validation_status"),
                "old_spec": previous.get("spec"),
                "new_spec": item.get("spec"),
                "event_type": "new" if not previous else "changed",
            }
            changes.append(event)

    write_path_state = {
        "generated_at": retrieval_time,
        "watchlist_generated_at": watch.get("generated_at"),
        "fetch_stats": stats,
        "products": products,
    }
    save_json(latest_path, write_path_state)
    append_jsonl(event_path, changes)

    print(json.dumps({
        "retrieval_time": retrieval_time,
        "watch_urls": len(entries),
        "products": len(products),
        "changes": len(changes),
        "fetch_stats": stats,
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
