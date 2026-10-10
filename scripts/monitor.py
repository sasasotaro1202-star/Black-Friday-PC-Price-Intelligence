import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import subprocess
import time
import base64
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
    "akiba-pc.watch.impress.co.jp", "joshinweb.jp", "shop.applied-net.co.jp",
    "amazon.co.jp", "rakuten.co.jp", "yodobashi.com", "biccamera.com",
    "yamada-denkiweb.com", "pc-koubou.jp", "ozgaming.jp", "sofmap.com",
    "edion.com", "ksdenki.com", "nojima.co.jp"
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


class BingSearchParser(HTMLParser):
    """Small dependency-free parser for Bing's organic result cards."""
    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None
        self.capture = None
        self.buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "li" and "b_algo" in classes:
            self.current = {"url": "", "title": "", "snippet": ""}
            self.capture = None
            self.buf = []
            return
        if self.current is None:
            return
        if tag == "a" and not self.current.get("title") and attrs.get("href"):
            self.current["url"] = attrs.get("href", "")
            self.capture = "title"
            self.buf = []
        elif tag == "p" and not self.current.get("snippet"):
            self.capture = "snippet"
            self.buf = []

    def handle_endtag(self, tag):
        if self.current is None:
            return
        if tag == "a" and self.capture == "title":
            self.current["title"] = " ".join("".join(self.buf).split())
            self.capture = None
            self.buf = []
        elif tag == "p" and self.capture == "snippet":
            self.current["snippet"] = " ".join("".join(self.buf).split())
            self.capture = None
            self.buf = []
        elif tag == "li":
            if self.current.get("url") and self.current.get("title"):
                self.results.append(self.current)
            self.current = None
            self.capture = None
            self.buf = []

    def handle_data(self, data):
        if self.current is not None and self.capture:
            self.buf.append(data)


def _unpack_bing_url(url):
    """Resolve Bing's base64 redirect parameter when present; otherwise keep the URL."""
    try:
        parsed = urlparse(url)
        if not (parsed.hostname or "").lower().endswith("bing.com"):
            return url
        params = parse_qs(parsed.query)
        encoded = (params.get("u") or [""])[0]
        if encoded.startswith("a1"):
            raw = encoded[2:]
            raw += "=" * ((4 - len(raw) % 4) % 4)
            decoded = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8", errors="replace")
            if decoded.startswith(("https://", "http://")):
                return decoded
    except Exception:
        pass
    return url


def bing_search(query, timeout=9):
    if not query:
        return []
    req = Request(
        "https://www.bing.com/search?q=" + quote(query),
        headers={"User-Agent": UA, "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.5"},
    )
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    parser = BingSearchParser()
    parser.feed(html)
    out = []
    for row in parser.results:
        url = _unpack_bing_url(row.get("url", ""))
        if url.startswith(("https://", "http://")):
            out.append({**row, "url": url})
    return out


def _normalized_model_anchor(value):
    return re.sub(r"[^a-z0-9]+", "", norm_text(str(value or "")).lower())


def search_identity_anchor(result, expected):
    """Return the SKU/model alias actually present in a search result, or None.

    The canonical product URL cannot prove that a different search-result snippet
    describes the same SKU. A result must itself contain a curated alias/model code.
    """
    expected = expected or {}
    blob = _normalized_model_anchor(
        (result or {}).get("title", "") + " " + (result or {}).get("snippet", "")
    )
    aliases = []
    if expected.get("model_code"):
        aliases.append(expected["model_code"])
    aliases.extend(expected.get("aliases") or [])
    for alias in aliases:
        normalized = _normalized_model_anchor(alias)
        if len(normalized) >= 5 and normalized in blob:
            return str(alias)
    return None


def _search_providers(query):
    """Yield free HTML search providers in order; credentials and paid APIs are not required."""
    yield "duckduckgo", ddg_search
    yield "bing", bing_search


def search_fallback(query, canonical_url, expected=None, diagnostics=None):
    """Find a price only when the result itself contains the curated exact model anchor."""
    expected = expected or {}
    diagnostics = diagnostics if diagnostics is not None else []
    candidates = []
    for provider, search_fn in _search_providers(query):
        try:
            results = search_fn(query, timeout=9)
            provider_error = None
        except Exception as exc:
            diagnostics.append({
                "provider": provider,
                "status": "error",
                "error": f"{type(exc).__name__}:{str(exc)[:160]}",
                "result_count": 0,
                "identity_rejected_count": 0,
            })
            continue

        identity_rejected = 0
        priced_result_count = 0
        matched_count = 0
        for result in results or []:
            url = result.get("url", "")
            if not url.startswith(("https://", "http://")) or not host_allowed(url):
                continue
            blob = (result.get("title", "") + " " + result.get("snippet", "")).strip()
            anchor = search_identity_anchor(result, expected)
            if not anchor:
                identity_rejected += 1
                continue
            raw = pick_price(blob)
            if not raw:
                continue
            priced_result_count += 1
            rel = relevance(query, blob)
            if canonical_url and urlparse(url).netloc.lower() == urlparse(canonical_url).netloc.lower():
                rel += 4
            matched_count += 1
            candidates.append({
                "rank": rel + source_bonus(url),
                "url": url,
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "price_jpy": raw["price_jpy"],
                "stock_status": stock_from_text(blob),
                "spec": parse_specs(blob),
                "identity_anchor": anchor,
                "provider": provider,
            })
        diagnostics.append({
            "provider": provider,
            "status": "ok" if results is not None else "empty",
            "result_count": len(results or []),
            "priced_exact_model_count": priced_result_count,
            "identity_rejected_count": identity_rejected,
            "matched_count": matched_count,
        })
        # Stop on the first provider with an exact-identity price candidate. If
        # it had only irrelevant results, try the next provider instead.
        if candidates:
            break
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x["rank"], -x["price_jpy"]), reverse=True)
    return candidates[0]


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
    compact = "".join(s.split()).lower()

    # Prefer the strongest identity anchors first. The exact model/SKU code is
    # substantially safer than the broad product name, id, or search query,
    # because manufacturer pages often contain multiple related variants.
    anchor_groups = [
        [str(hints.get("model_code"))] if hints.get("model_code") else [],
        [str(x) for x in (hints.get("aliases") or []) if x],
        [str(hints.get("name"))] if hints.get("name") else [],
        [str(hints.get("id"))] if hints.get("id") else [],
        [str(hints.get("query"))] if hints.get("query") else [],
    ]

    best = None
    for group in anchor_groups:
        positions = []
        for term in group:
            t = "".join(norm_text(term).split()).lower()
            if not t:
                continue
            pos = compact.find(t)
            if pos >= 0:
                positions.append(pos)
        if positions:
            best = min(positions)
            break

    if best is None:
        return s[:14000]

    # Exact model/SKU anchors usually precede the product's own specification
    # table. Do not include a large prefix: shared manufacturer pages often place
    # related variants immediately before the selected variant and that can
    # contaminate CPU/GPU/SSD parsing.
    strongest_anchor = bool(
        (hints.get("model_code") and "".join(norm_text(str(hints.get("model_code"))).split()).lower() in compact)
        or any(
            "".join(norm_text(str(x)).split()).lower() in compact
            for x in (hints.get("aliases") or [])
            if x
        )
    )
    if strongest_anchor:
        return s[max(0, best-400):min(len(s), best+12000)]

    return s[max(0, best-3500):min(len(s), best+12000)]

def _spec_anchor_position(text, hints=None):
    s = " ".join(str(text or "").split())
    hints = hints or {}
    compact = "".join(s.split()).lower()
    anchor_groups = [
        [str(hints.get("model_code"))] if hints.get("model_code") else [],
        [str(x) for x in (hints.get("aliases") or []) if x],
        [str(hints.get("name"))] if hints.get("name") else [],
        [str(hints.get("id"))] if hints.get("id") else [],
        [str(hints.get("query"))] if hints.get("query") else [],
    ]
    for group in anchor_groups:
        positions = []
        for term in group:
            t = "".join(norm_text(term).split()).lower()
            if t:
                pos = compact.find(t)
                if pos >= 0:
                    positions.append(pos)
        if positions:
            return positions[0]
    return None

def parse_specs(text, expected=None):
    s = _spec_window(text, expected)
    out = {}
    expected = expected or {}
    anchor = _spec_anchor_position(s, expected)
    compact = "".join(s.split()).lower()
    compact_core = re.sub(r"[^a-z0-9]+", "", s.lower())

    anchor_core = None
    for group_key in ("model_code", "aliases", "name", "id", "query"):
        terms = [str(x) for x in (expected.get(group_key) or [])] if group_key == "aliases" else ([str(expected.get(group_key))] if expected.get(group_key) else [])
        for term in terms:
            core_term = re.sub(r"[^a-z0-9]+", "", term.lower())
            if core_term:
                pos = compact_core.find(core_term)
                if pos >= 0:
                    anchor_core = pos
                    break
        if anchor_core is not None:
            break

    def near_expected(value, radius=2600):
        if value in (None, ""):
            return False
        term_core = re.sub(r"[^a-z0-9]+", "", str(value).lower())
        if not term_core or anchor_core is None:
            return False
        pos = compact_core.find(term_core)
        return pos >= 0 and abs(pos - anchor_core) <= radius

    gpu_patterns = [
        r"(RTX\s*(?:5090|5080|5070\s*Ti|5070|5060\s*Ti|5060)(?:\s*Laptop(?:\s*GPU)?)?)",
        r"(Radeon\s+RX\s*(?:9070\s*XT|9070|9060\s*XT|9060|9050|7900\s*(?:XTX|XT)|7800\s*XT|7700\s*XT))",
    ]
    for pat in gpu_patterns:
        m = re.search(pat, s, re.I)
        if m:
            out["gpu"] = re.sub(r"\s+", " ", m.group(1)).strip()
            break
    if near_expected(expected.get("gpu")):
        out["gpu"] = str(expected["gpu"])

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
    if near_expected(expected.get("cpu")):
        out["cpu"] = str(expected["cpu"])

    m = re.search(r"(?:SSD|ストレージ|Storage|M\.2 SSD)[^0-9]{0,18}(\d+(?:\.\d+)?)\s*(TB|GB)", s, re.I)
    if m:
        out["ssd"] = m.group(1) + " " + m.group(2)
    if re.search(r"(?:デスクトップ(?:PC|パソコン)?|Desktop PC)", s, re.I):
        out["form_factor"] = "desktop"
    elif re.search(r"(?:ノート(?:PC|パソコン)?|Laptop PC)", s, re.I):
        out["form_factor"] = "laptop"

    if str(expected.get("form_factor") or "").lower() in ("desktop", "laptop") and anchor is not None:
        form_terms = (
            [r"デスクトップ(?:PC|パソコン)?", r"Desktop PC", r"Desktop"]
            if str(expected["form_factor"]).lower() == "desktop"
            else [r"ノート(?:PC|パソコン)?", r"Laptop PC", r"Laptop"]
        )
        form_positions = []
        for pat in form_terms:
            for m in re.finditer(pat, s, re.I):
                form_positions.append(m.start())
        if form_positions and min(abs(p - anchor) for p in form_positions) <= 2600:
            out["form_factor"] = str(expected["form_factor"])

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
    """Extract promotions into cash-equivalent vs non-cash value layers.

    Only an explicitly additional checkout/coupon discount can reduce effective
    cost. Generic "X円OFF" is kept as unconfirmed because it may already be
    reflected in the displayed sale price. Peripheral/configuration benefits
    never reduce effective cost; they are separate value evidence.
    """
    s = re.sub(r"\s+", " ", str(text or ""))
    signals = []
    seen = set()
    peripheral_terms = (
        "周辺機器", "アクセサリ", "アクセサリー", "モニター", "ディスプレイ",
        "キーボード", "マウス", "ヘッドセット", "スピーカー", "webカメラ",
        "ドッキングステーション", "ドック"
    )

    def add(kind, value=None, certainty="unconfirmed", counts=False, context=""):
        key = (kind, value)
        if key in seen:
            return
        seen.add(key)
        signals.append({
            "kind": kind,
            "value": value,
            "value_jpy": value if kind.endswith("_jpy") else None,
            "text": context[:320],
            "certainty": certainty,
            "counts_toward_effective_cost": bool(counts),
        })

    # Points/cashback remain separate unless the program is explicitly cash-like
    # and guaranteed. Generic point language is never subtracted.
    for pat, kind in [
        (r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:分|相当)?\s*(?:の)?(?:ポイント|ポイント還元|還元)", "point_value_jpy"),
        (r"(?:ポイント|還元)[^0-9]{0,20}([0-9]{1,2})\s*%", "point_percent"),
        (r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:の)?(?:キャッシュバック|還元)", "cashback_value_jpy"),
    ]:
        for m in re.finditer(pat, s, re.I):
            try:
                value = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            ctx = s[max(0, m.start()-90):min(len(s), m.end()+90)]
            add(kind, value, "unconfirmed", False, ctx)

    # Additional checkout/coupon discount: count only when the text explicitly
    # describes an extra discount triggered at checkout/cart/code time.
    coupon_pat = r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円\s*(?:OFF|オフ|引き|値引き|割引)"
    for m in re.finditer(coupon_pat, s, re.I):
        try:
            value = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        ctx = s[max(0, m.start()-120):min(len(s), m.end()+120)]
        ctx_norm = norm_text(ctx)
        is_peripheral = any(term in ctx_norm for term in peripheral_terms)
        extra_checkout = bool(re.search(
            r"(?:クーポン|coupon|コード|カート|購入時|決済時|注文時|適用後|追加で|さらに|併用)",
            ctx, re.I
        ))
        # Avoid subtracting a displayed sale reduction that is already included
        # in current price, or a peripheral-only discount.
        if extra_checkout and not is_peripheral:
            add("additional_cash_discount_jpy", value, "confirmed", True, ctx)
        else:
            add("displayed_discount_jpy", value, "unconfirmed", False, ctx)

    # Explicit accessory/bundle value: useful for desktop value comparison, never
    # a cash deduction. This is deliberately limited to stated monetary value.
    value_patterns = [
        r"(?:モニター|ディスプレイ|キーボード|マウス|ヘッドセット|スピーカー|webカメラ|ドッキングステーション|周辺機器|アクセサリ)[^。\n]{0,90}?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:相当|分)",
        r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円(?:相当|分)[^。\n]{0,90}?(?:モニター|ディスプレイ|キーボード|マウス|ヘッドセット|スピーカー|webカメラ|ドッキングステーション|周辺機器|アクセサリ)",
    ]
    for value_pat in value_patterns:
        for m in re.finditer(value_pat, s, re.I):
            try:
                value = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            ctx = s[max(0, m.start()-100):min(len(s), m.end()+120)]
            bundled = bool(re.search(
                r"(?:プレゼント|付属|同梱|セット|無料|無償|進呈|特典|キャンペーン)",
                ctx,
                re.I
            ))
            add(
                "accessory_stated_value_jpy",
                value,
                "confirmed" if bundled else "unconfirmed",
                False,
                ctx,
            )

    # Accessory-specific discount is an opportunity signal, not PC cash value.
    for m in re.finditer(r"(?:周辺機器|アクセサリ|アクセサリー)[^。\n]{0,80}?([0-9]{1,2})\s*%\s*(?:OFF|オフ|割引)", s, re.I):
        try:
            value = int(m.group(1))
        except ValueError:
            continue
        ctx = s[max(0, m.start()-60):min(len(s), m.end()+100)]
        add("accessory_bundle_percent", value, "confirmed", False, ctx)

    # Free configuration upgrades are tracked as value evidence. Warranty/support
    # is counted only when it is clearly an incremental offer (extension or
    # enhanced support), not a generic site-wide warranty statement.
    for m in re.finditer(
        r"(?:メモリ|RAM|SSD|ストレージ|容量)[^。\n]{0,80}(?:無料|無償|アップグレード)",
        s, re.I
    ):
        ctx = s[max(0, m.start()-40):min(len(s), m.end()+100)]
        add("configuration_upgrade", 1, "confirmed", False, ctx)

    for m in re.finditer(
        r"(?:保証|サポート)[^。\n]{0,80}(?:延長|追加|プレミアム|5年|4年)",
        s, re.I
    ):
        ctx = s[max(0, m.start()-40):min(len(s), m.end()+100)]
        add("warranty_or_support_value", 1, "confirmed", False, ctx)

    # Clearly free/included peripherals are useful but remain non-cash evidence.
    # Keep the proximity tight and exclude the retailer brand phrase
    # "マウスコンピューター", which is not a bundled mouse.
    peripheral_terms = r"(?:モニター|ディスプレイ|キーボード|(?<!コンピューター)マウス|ヘッドセット|スピーカー|webカメラ)"
    benefit_terms = r"(?:(?<!送料)無料|無償|プレゼント|同梱|付属(?!品))"
    for m in re.finditer(
        peripheral_terms + r"[^。\n]{0,25}" + benefit_terms,
        s, re.I
    ):
        ctx = s[max(0, m.start()-40):min(len(s), m.end()+90)]
        if re.search(r"(?:送料|金利|手数料|分割|ショッピングローン|ローン)", ctx, re.I):
            continue
        add("included_peripheral", 1, "confirmed", False, ctx)
    for m in re.finditer(
        benefit_terms + r"[^。\n]{0,25}" + peripheral_terms,
        s, re.I
    ):
        ctx = s[max(0, m.start()-40):min(len(s), m.end()+90)]
        if re.search(r"(?:送料|金利|手数料|分割|ショッピングローン|ローン)", ctx, re.I):
            continue
        add("included_peripheral", 1, "confirmed", False, ctx)

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

    expected_aliases = [str(x) for x in (expected.get("aliases") or []) if expected] if expected else []
    expected_name = str(expected.get("name") or "") if expected else ""
    expected_model_code = str(expected.get("model_code") or "") if expected else ""

    def _jsonld_match_level(product_name):
        pn = "".join(norm_text(product_name).split())
        if not pn:
            return 0
        alias_terms = ["".join(norm_text(x).split()) for x in expected_aliases if x]
        model_term = "".join(norm_text(expected_model_code).split())
        name_term = "".join(norm_text(expected_name).split())
        if any(term and term in pn for term in alias_terms):
            return 3
        if model_term and model_term in pn:
            return 3
        if name_term and (pn == name_term or pn.startswith(name_term + "[")):
            return 2
        if name_term and name_term in pn:
            return 1
        return 0

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
            match_level = _jsonld_match_level(product_name)
            if match_level:
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
                        "match_level": match_level,
                        "availability": str(offer.get("availability") or ""),
                    })

    if matched_structured:
        best_match = max(x["match_level"] for x in structured_offers)
        selected_offers = [x for x in structured_offers if x["match_level"] == best_match]
    else:
        selected_offers = structured_offers
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
    if len(all_availability_states) == 1:
        structured_stock = next(iter(all_availability_states))

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
        "stock_ambiguity": "multiple_offer_availability" if len(all_availability_states) > 1 else None,
        "parsed_spec": specs,
        "page_text_excerpt": text_html[:12000],
        "benefit_signals": benefit_signals,
        "confirmed_benefit_value_jpy": sum(
            int(x.get("value_jpy") or 0)
            for x in benefit_signals
            if x.get("counts_toward_effective_cost") and x.get("certainty") == "confirmed"
        ),
        "benefit_confidence": (
            "confirmed"
            if any(x.get("counts_toward_effective_cost") and x.get("certainty") == "confirmed"
                   for x in benefit_signals)
            else "unconfirmed"
        ),
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
            "confirmed_benefit_value_jpy": int(raw.get("confirmed_benefit_value_jpy") or 0),
            "benefit_confidence": raw.get("benefit_confidence") or "unconfirmed",
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
    if not search or not search.get("identity_anchor") or item.get("price_validation_status") != "anomaly_rejected":
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

    total_watchlist_entries = len(entries)
    try:
        max_urls = max(1, min(int(os.environ.get("MONITOR_MAX_URLS", "100")), 100))
    except Exception:
        max_urls = 100
    skipped_entries = entries[max_urls:]
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
        "search_fallback_attempts": 0,
        "search_fallback_successes": 0,
        "search_fallback_failures": 0,
        "search_identity_rejections": 0,
        "errors_by_host_reason": {},
    }
    retrieval_time = iso(now_jst())

    # Fetch/parse product pages concurrently. The ranking/event logic below stays
    # deterministic because results are reassembled in original watchlist order.
    def fetch_one(entry):
        cid = entry["id"]
        cat = catalog.get(cid, {})
        try:
            html, final_url, _headers = fetch(entry["url"])
            return cid, parse_page(final_url, html, expected=cat), None
        except HTTPError as exc:
            return cid, None, f"HTTPError:{exc.code}"
        except URLError as exc:
            return cid, None, f"URLError:{getattr(exc, 'reason', 'unknown')}"
        except Exception as exc:
            # Keep transport diagnostics (e.g. curl_http_403 or curl_exit_6).
            # Exception class alone made every curl failure look identical.
            return cid, None, f"{type(exc).__name__}:{str(exc)[:180]}"

    fetch_results = {}
    # Limit concurrency to reduce merchant-side 403/429 responses on free runners.
    workers = min(6, max(1, len(entries)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(fetch_one, entry): entry["id"] for entry in entries}
        for future in as_completed(future_map):
            cid, raw, request_error = future.result()
            fetch_results[cid] = (raw, request_error)

    for entry in entries:
        cid = entry["id"]
        previous = previous_by_id.get(cid, {})
        cat = catalog.get(cid, {})
        raw, request_error = fetch_results.get(cid, (None, "fetch_result_missing"))

        item = apply_observation(entry, raw, previous, cat, retrieval_time)

        if request_error:
            item["fetch_status"] = "error"
            item["last_fetch_status"] = "error"
            item["last_fetch_error"] = request_error
            stats["errors"] += 1

            fallback_diagnostics = []
            stats["search_fallback_attempts"] += 1 if entry.get("query") else 0
            fallback = search_fallback(
                entry.get("query", ""), entry["url"], expected=cat, diagnostics=fallback_diagnostics
            ) if entry.get("query") else None
            item["search_fallback_diagnostics"] = fallback_diagnostics
            for diagnostic in fallback_diagnostics:
                stats["search_identity_rejections"] += int(diagnostic.get("identity_rejected_count") or 0)
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
                # The result snippet itself must contain a curated exact alias.
                # Never grant identity from the canonical page URL when the price
                # came from a different search-result URL.
                identity_ok = bool(fallback.get("identity_anchor"))
                if checked["valid"] and identity_ok:
                    item["price_jpy"] = fallback["price_jpy"]
                    item["current_price_jpy"] = fallback["price_jpy"]
                    item["last_valid_price_jpy"] = fallback["price_jpy"]
                    item["available_at"] = retrieval_time
                    item["price_source_mode"] = "search_snippet"
                    item["price_validation_status"] = checked["status"]
                    item["price_validation_reason"] = "search_fallback:" + checked["reason"]
                    item["data_confidence"] = "medium"
                    item["variant_match"] = "strong"
                    item["identity_evidence_source"] = "search_result_model_anchor"
                    stats["search_fallback_successes"] += 1
                    item["corroborating_source_url"] = fallback["url"]
                    item["corroborating_source_title"] = fallback["title"]
                    item["corroborating_source_snippet"] = fallback["snippet"]
                    item["search_provider"] = fallback.get("provider")
                    item["search_identity_anchor"] = fallback.get("identity_anchor")
                    stats["search_corrob"] += 1
                else:
                    item["current_price_jpy"] = None
                    item["price_jpy"] = None
                    item["price_validation_status"] = "reference_only" if reference is not None else "missing"
                    item["price_validation_reason"] = "search_fallback_rejected:" + ("identity_mismatch" if not identity_ok else checked["reason"])
                    stats["search_fallback_failures"] += 1
            else:
                stats["search_fallback_failures"] += 1

            host = (urlparse(entry.get("url", "")).hostname or "unknown").lower()
            reason = str(request_error or "unknown").split(":")[-1][:100]
            key = f"{host}|{reason}"
            stats["errors_by_host_reason"][key] = stats["errors_by_host_reason"].get(key, 0) + 1

            # Only fall back to stale/reference states when no validated exact-SKU
            # search price was accepted. Keep successfully corroborated prices.
            if item.get("current_price_jpy") is None and previous.get("current_price_jpy") is not None:
                item["current_price_jpy"] = None
                item["price_jpy"] = None
                item["last_valid_price_jpy"] = previous.get("current_price_jpy")
                item["price_source_mode"] = "stale_previous"
                item["available_at"] = None
                item["data_confidence"] = "low"
                stats["stale_previous"] += 1
            elif item.get("current_price_jpy") is None and (cat.get("reference_price_jpy") is not None or cat.get("price_jpy") is not None):
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
                anomaly_diagnostics = []
                stats["search_fallback_attempts"] += 1
                fallback = search_fallback(entry["query"], entry["url"], expected=cat, diagnostics=anomaly_diagnostics)
                item["search_fallback_diagnostics"] = anomaly_diagnostics
                for diagnostic in anomaly_diagnostics:
                    stats["search_identity_rejections"] += int(diagnostic.get("identity_rejected_count") or 0)
                item = corroborate_anomaly(item, fallback)
                if item.get("price_validation_status") == "anomaly_corroborated":
                    stats["search_fallback_successes"] += 1
                else:
                    stats["search_fallback_failures"] += 1
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

    processed_count = len(products)
    transport_success_count = sum(1 for x in products if x.get("fetch_status") == "ok")
    price_verified_count = sum(1 for x in products if x.get("current_price_jpy") is not None)
    coverage = {
        "watchlist_count": total_watchlist_entries,
        "processed_count": processed_count,
        "skipped_count": len(skipped_entries),
        "max_urls": max_urls,
        "processing_rate_pct": round(
            100.0 * processed_count / total_watchlist_entries, 1
        ) if total_watchlist_entries else 100.0,
        "transport_success_rate_pct": round(
            100.0 * transport_success_count / processed_count, 1
        ) if processed_count else 0.0,
        "price_verified_rate_pct": round(
            100.0 * price_verified_count / processed_count, 1
        ) if processed_count else 0.0,
        "skipped_reason": "capacity_limit" if skipped_entries else None,
        "skipped_ids": [x.get("id") for x in skipped_entries if x.get("id")],
    }

    write_path_state = {
        "generated_at": retrieval_time,
        "watchlist_generated_at": watch.get("generated_at"),
        "fetch_stats": stats,
        "coverage": coverage,
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
        "coverage": coverage,
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
