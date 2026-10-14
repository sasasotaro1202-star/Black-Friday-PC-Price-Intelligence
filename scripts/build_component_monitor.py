"""Collect component comparison prices as non-actionable market references."""
import hashlib
import html as html_lib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone, timedelta
from urllib.parse import quote, urlparse, urljoin
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from intelligence import load_json, save_json, now_jst, iso, parse_dt
from monitor import fetch, parse_page, ddg_search, bing_search, search_identity_anchor, pick_price

JST = timezone(timedelta(hours=9))
CONFIG_PATH = os.path.join(ROOT, "config", "build_components.json")
OUTPUT_PATH = os.path.join(ROOT, "data", "build_component_prices.json")
OBSERVATIONS_PATH = os.path.join(ROOT, "data", "build_component_observations.jsonl")
EVENTS_PATH = os.path.join(ROOT, "data", "build_component_change_events.jsonl")
DEFAULT_DOMAINS = ("kakaku.com",)

RETAILER_SEARCH_TEMPLATES = {
    "amazon.co.jp": "https://www.amazon.co.jp/s?k={query}",
    "shopping.yahoo.co.jp": "https://shopping.yahoo.co.jp/search?p={query}",
    "rakuten.co.jp": "https://search.rakuten.co.jp/search/mall/{query}/",
    "yodobashi.com": "https://www.yodobashi.com/?word={query}",
    "biccamera.com": "https://www.biccamera.com/bc/category/?q={query}",
    "tsukumo.co.jp": "https://shop.tsukumo.co.jp/search/?keyword={query}",
    "pc-koubou.jp": "https://www.pc-koubou.jp/user_data/search.php?q={query}",
    "sofmap.com": "https://www.sofmap.com/search_result.aspx?keyword={query}",
    "joshinweb.jp": "https://joshinweb.jp/search.html?KEYWORD={query}",
    "ark-pc.co.jp": "https://www.ark-pc.co.jp/search/?key={query}",
}


def normalized(value):
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]+", "", str(value or "").lower())


def allowed_url(url, domains):
    try:
        parsed = urlparse(str(url or ""))
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in domains)
    except Exception:
        return False


def identity_match(part, raw):
    text = normalized(str(raw.get("name") or "") + " " + str(raw.get("page_text_excerpt") or "")[:4500])
    terms = [part.get("model_code")] + list(part.get("identity_terms") or []) + list(part.get("aliases") or [])
    candidates = []
    for term in terms:
        value = normalized(term)
        if len(value) >= 5 and value not in candidates:
            candidates.append(value)
    found = [term for term in candidates if term in text]
    return bool(found), found[:5]


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except (TypeError, ValueError):
                    pass
    except OSError:
        pass
    return rows


def append_jsonl(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def last_by_id(rows):
    out = {}
    for row in rows:
        if row.get("id"):
            out[str(row["id"])] = row
    return out


def parse_snippet_price(text, minimum, maximum):
    """Extract an explicit currency amount under component-specific price bounds."""
    text = re.sub(r"\s+", " ", str(text or ""))
    patterns = [
        re.compile(r"(?:¥|￥)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})(?:\s*円)?"),
        re.compile(r"(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円")
    ]
    candidates = []
    excluded_prefix = re.compile(r"割引|値引|クーポン|ポイント|還元|月額|毎月|分割|off", re.IGNORECASE)
    for pattern in patterns:
        for match in pattern.finditer(text):
            try:
                price = int(match.group(1).replace(",", ""))
            except (TypeError, ValueError):
                continue
            if not int(minimum) <= price <= int(maximum):
                continue
            prefix = text[max(0, match.start() - 36):match.start()]
            if excluded_prefix.search(prefix[-24:]):
                continue
            context = text[max(0, match.start() - 70):min(len(text), match.end() + 35)]
            score = 10 if "最安価格" in prefix else 5 if "価格" in prefix else 0
            candidates.append((score, -price, match.start(), price, context))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, _, _, price, context = candidates[0]
    return {"price_jpy": price, "context": context}




class _KakakuNode:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []
        self.parent = parent


class _KakakuSearchTreeParser(HTMLParser):
    """Small standard-library HTML tree builder; no third-party parser required."""

    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _KakakuNode("document", {})
        self.stack = [self.root]
        self.nodes = [self.root]

    def handle_starttag(self, tag, attrs):
        parent = self.stack[-1]
        node = _KakakuNode(tag.lower(), attrs, parent)
        parent.children.append(node)
        self.nodes.append(node)
        if tag.lower() not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        parent = self.stack[-1]
        node = _KakakuNode(tag.lower(), attrs, parent)
        parent.children.append(node)
        self.nodes.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if not self.stack:
            return
        if any(node.tag in ("script", "style", "noscript", "template") for node in self.stack):
            return
        value = str(data or "").strip()
        if value:
            self.stack[-1].children.append(value)


def _kakaku_node_text(node):
    pieces = []
    for child in node.children:
        pieces.append(child if isinstance(child, str) else _kakaku_node_text(child))
    return re.sub(r"\s+", " ", " ".join(pieces)).strip()


def _kakaku_is_product_card(node):
    if node.tag in ("article", "li"):
        return True
    attrs = node.attrs or {}
    if str(attrs.get("role") or "").lower() == "listitem":
        return True
    classes = [str(x).lower() for x in str(attrs.get("class") or "").split()]
    for token in classes:
        compact = re.sub(r"[^a-z0-9]+", "", token)
        if compact in {
            "item", "result", "card", "productitem", "productcard",
            "searchresultitem", "productlistitem", "searchresultcard",
        }:
            return True
        if re.search(r"(?:^|[-_])(?:item|result|card)(?:$|[-_])", token):
            return True
        if compact.endswith((
            "productitem", "resultitem", "searchitem", "listitem", "catalogitem",
            "searchresult", "productresult", "productcard", "resultcard", "searchresultcard",
        )):
            return True
    return False


def _kakaku_card_prices(text, minimum, maximum):
    """Return distinct in-range yen values within one structural product card."""
    pattern = re.compile(
        r"(?:[¥￥]\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})(?:\s*円)?|"
        r"(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円)"
    )
    excluded_prefix = re.compile(r"割引|値引|クーポン|ポイント|還元|月額|毎月|分割|off", re.I)
    prices = []
    for match in pattern.finditer(text):
        raw = match.group(1) or match.group(2)
        try:
            price = int(raw.replace(",", ""))
        except (TypeError, ValueError):
            continue
        if not minimum <= price <= maximum:
            continue
        prefix = text[max(0, match.start() - 36):match.start()]
        if excluded_prefix.search(prefix[-24:]):
            continue
        prices.append(price)
    return sorted(set(prices))


def parse_kakaku_search_page_reference(part, html_body, source_url, diagnostics=None):
    """Extract a display-only reference only when SKU and one price share a product card.

    A page-wide nearest-price heuristic is unsafe: a price from an adjacent SKU can
    appear close to a product title in flattened HTML. This parser requires a bounded
    structural card (article/li/known item/result/card class), a curated identity
    phrase in that card, and exactly one distinct plausible yen price in that card.
    """
    metrics = {
        "product_card_count": 0,
        "identity_card_count": 0,
        "single_price_identity_card_count": 0,
        "ambiguous_price_card_count": 0,
        "extraction_reason": "unclassified",
    }

    def finish(value, reason):
        metrics["extraction_reason"] = reason
        if isinstance(diagnostics, dict):
            diagnostics.update(metrics)
        return value

    try:
        parsed = urlparse(str(source_url or ""))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != "search.kakaku.com":
            return finish(None, "source_host_rejected")
    except Exception:
        return finish(None, "source_url_invalid")

    try:
        parser = _KakakuSearchTreeParser()
        parser.feed(str(html_body or ""))
        parser.close()
    except Exception:
        return finish(None, "html_parse_error")

    card_nodes = [
        node for node in parser.nodes
        if node is not parser.root and _kakaku_is_product_card(node)
    ]
    metrics["product_card_count"] = len(card_nodes)
    if not card_nodes:
        return finish(None, "no_product_card_nodes")

    minimum = int(part.get("min_price_jpy") or 1)
    maximum = int(part.get("max_price_jpy") or 10**9)
    candidates = []
    found_identity = False
    found_any_in_range_price = False
    for node in card_nodes:
        text = _kakaku_node_text(node)
        # A card is small enough to represent one result, not a whole result list.
        if not text or len(text) > 1800:
            continue
        anchor = component_search_identity_anchor({"title": text, "snippet": ""}, part)
        if not anchor:
            continue
        found_identity = True
        metrics["identity_card_count"] += 1
        prices = _kakaku_card_prices(text, minimum, maximum)
        if prices:
            found_any_in_range_price = True
        # Price ranges, new/used offers, installment rates, or more than one offer
        # within the card remain ambiguous and are not rendered as a reference.
        if len(prices) != 1:
            if len(prices) > 1:
                metrics["ambiguous_price_card_count"] += 1
            continue
        metrics["single_price_identity_card_count"] += 1
        price = prices[0]
        context = text[:500]
        normalized_anchor = normalized(anchor)
        # Prefer exact SKU/model-code evidence; otherwise prefer the smallest card.
        identity_priority = 3 if normalized_anchor == normalized(part.get("model_code")) else (
            2 if normalized_anchor == normalized(part.get("name")) else 1
        )
        candidates.append((identity_priority, len(text), {
            "url": str(source_url),
            "title": anchor,
            "snippet": context,
            "price_jpy": price,
            "price_context": context,
            "identity_anchor": anchor,
            "source_role": "comparison_site_search_snippet_reference",
            "bf_actual_authorized": False,
            "search_provider": "kakaku_search_page",
            "query": str(part.get("name") or part.get("model_code") or ""),
            "same_comparison_item_path": False,
        }))

    if not candidates:
        if not found_identity:
            reason = "sku_identity_not_found_in_product_card"
        elif metrics["ambiguous_price_card_count"]:
            reason = "ambiguous_multiple_prices_in_product_card"
        elif not found_any_in_range_price:
            reason = "matching_product_card_has_no_in_range_price"
        else:
            reason = "matching_product_card_price_unusable"
        return finish(None, reason)

    candidates.sort(key=lambda row: (-row[0], row[1], row[2]["price_jpy"]))
    # If equally strong product cards disagree on price, keep the reference unknown.
    best_priority = candidates[0][0]
    best_size = candidates[0][1]
    top = [row[2] for row in candidates if row[0] == best_priority and row[1] == best_size]
    distinct_prices = {row["price_jpy"] for row in top}
    if len(distinct_prices) != 1:
        return finish(None, "conflicting_equally_specific_product_cards")
    return finish(top[0], "display_only_price_from_single_product_card")

def parse_search_snippet_reference(part, results, domains=DEFAULT_DOMAINS):
    """Use a search snippet only as display-only context, never as a direct/live price."""
    expected_path = urlparse(str(part.get("monitor_url") or "")).path.rstrip("/").lower()
    minimum = int(part.get("min_price_jpy") or 1)
    maximum = int(part.get("max_price_jpy") or 10**9)
    for result in results or []:
        url = str(result.get("url") or "")
        if not allowed_url(url, domains):
            continue
        path = urlparse(url).path.rstrip("/").lower()
        if not expected_path or path != expected_path:
            continue
        anchor = search_identity_anchor(result, part)
        if not anchor:
            continue
        blob = str(result.get("title") or "") + " " + str(result.get("snippet") or "")
        candidate = parse_snippet_price(blob, minimum, maximum)
        price = candidate.get("price_jpy") if isinstance(candidate, dict) else None
        if isinstance(price, bool) or not isinstance(price, int) or not minimum <= price <= maximum:
            continue
        return {
            "url": url, "title": result.get("title") or "",
            "snippet": result.get("snippet") or "", "price_jpy": price,
            "price_context": candidate.get("context") if isinstance(candidate, dict) else None,
            "identity_anchor": anchor,
            "source_role": "comparison_site_search_snippet_reference",
            "bf_actual_authorized": False
        }
    return None


def component_search_identity_anchor(result, part):
    """Prefer exact model codes and full product identities over generic spec labels."""
    title = str((result or {}).get("title") or "")
    snippet = str((result or {}).get("snippet") or "")
    blob = normalized(title + " " + snippet)
    generic = {
        "rtx507012gb", "rtx5060ti16gb", "rtx5070ti16gb",
        "ddr5600032gb", "windows11home", "ryzen79700x"
    }
    candidates = []
    model_code = str(part.get("model_code") or "")
    if model_code:
        candidates.append((1000, model_code))
    for term in (part.get("name"), *(part.get("identity_terms") or []), *(part.get("aliases") or [])):
        value = str(term or "").strip()
        normalized_term = normalized(value)
        if len(normalized_term) < 9 or normalized_term in generic:
            continue
        # Broad GPU/memory capacity names are insufficient to prove the selected
        # retail SKU; require a branded/model-specific phrase instead.
        if normalized_term in generic:
            continue
        candidates.append((len(normalized_term), value))
    unique = {}
    for score, term in candidates:
        key = normalized(term)
        if key and key not in unique:
            unique[key] = (score, term)
    matches = [item for key, item in unique.items() if key in blob]
    if not matches:
        return None
    matches.sort(key=lambda x: (-x[0], x[1]))
    return matches[0][1]



def _normalized_text_span(text, term):
    """Find a normalized identity term while retaining original text positions."""
    output_chars = []
    original_positions = []
    for index, char in enumerate(str(text or "")):
        normalized_char = normalized(char)
        for normalized_item in normalized_char:
            output_chars.append(normalized_item)
            original_positions.append(index)
    haystack = "".join(output_chars)
    needle = normalized(term)
    if not needle:
        return None
    start = haystack.find(needle)
    if start < 0:
        return None
    return original_positions[start], original_positions[start + len(needle) - 1] + 1


def component_primary_identity_anchor(part, html_body, raw=None):
    """Prove the exact SKU from primary H1/title, never from metadata or related items.

    A matching OpenGraph tag, parser result, recommendation card or page-body token
    cannot override a conflicting primary product heading.
    """
    try:
        parser = _KakakuSearchTreeParser()
        parser.feed(str(html_body or ""))
        parser.close()
    except Exception:
        return None

    def exact_anchor(candidate):
        candidate = str(candidate or "").strip()
        if not candidate or len(candidate) > 700:
            return None
        return component_search_identity_anchor({"title": candidate, "snippet": ""}, part)

    h1_candidates = []
    title_candidates = []
    for node in parser.nodes:
        if node.tag not in ("h1", "title"):
            continue
        candidate = _kakaku_node_text(node)
        if not candidate or len(candidate) > 700:
            continue
        (h1_candidates if node.tag == "h1" else title_candidates).append(candidate)

    # A present H1 is decisive. Never rescue a mismatched H1 with an OG tag,
    # an HTML title, recommendation text, or an adjacent related-product card.
    primary_candidates = h1_candidates if h1_candidates else title_candidates
    if not primary_candidates:
        return None

    matches = []
    for title in primary_candidates:
        anchor = exact_anchor(title)
        if not anchor:
            continue
        model_code = normalized(part.get("model_code"))
        exact_model_code = bool(model_code and normalized(anchor) == model_code)
        matches.append((
            0 if exact_model_code else 1,
            -len(normalized(anchor)),
            len(title),
            anchor,
        ))
    if not matches:
        return None
    matches.sort()
    return matches[0][3]


def direct_price_context_conflicts_with_selected_gpu(part, context):
    """Reject a GPU amount whose adjacent price context names a different GPU."""
    if str(part.get("category") or "").lower() != "gpu":
        return False
    expected = normalized(" ".join(
        [str(part.get("name") or ""), str(part.get("model_code") or "")]
        + [str(x) for x in (part.get("aliases") or [])]
        + [str(x) for x in (part.get("identity_terms") or [])]
    ))
    value = str(context or "")
    patterns = (
        re.compile(r"\b(?:RTX|GTX)\s*\d{3,4}\s*(?:TI|SUPER)?\b", re.I),
        re.compile(r"\bRX\s*\d{4}\s*(?:XT|XTX)?\b", re.I),
    )
    for pattern in patterns:
        for match in pattern.finditer(value):
            token = normalized(match.group(0))
            if token and token not in expected:
                return True
    return False



def stock_from_component_context(text):
    """Interpret stock only from the directly associated title/price context."""
    value = str(text or "")
    if re.search(r"在庫切れ|品切れ|売り切れ|在庫なし|out of stock|sold out", value, re.I):
        return "out_of_stock"
    if re.search(r"残りわずか|残り1|low stock|only 1|only one", value, re.I):
        return "low_stock"
    if re.search(r"取り寄せ|予約|preorder|back order", value, re.I):
        return "preorder_or_backorder"
    if re.search(r"在庫あり|在庫有|即納|in stock|お取り寄せ可能", value, re.I):
        return "in_stock"
    return "unknown"


def parse_component_direct_text_price(part, html_body, identity_anchor=None):
    """Extract an identity-local price using the part-specific yen bounds.

    The shared PC parser deliberately filters sub-¥50k prices so accessories do
    not become PC prices. Reusing it for DIY parts meant that motherboards, SSDs,
    PSUs, cases and CPU coolers could never become direct listing references.
    """
    try:
        parser = _KakakuSearchTreeParser()
        parser.feed(str(html_body or ""))
        parser.close()
    except Exception:
        return None

    page_text = _kakaku_node_text(parser.root)
    if not page_text:
        return None
    anchor = identity_anchor or component_primary_identity_anchor(part, html_body)
    if not anchor:
        return None
    span = _normalized_text_span(page_text, anchor)
    if not span:
        return None

    # A neighboring result/recommendation may mention the requested SKU elsewhere
    # on the page. Use only the price area near the primary product heading.
    window_start = max(0, span[0] - 450)
    window_end = min(len(page_text), span[1] + 1800)
    local_text = page_text[window_start:window_end]
    anchor_start = span[0] - window_start
    anchor_end = span[1] - window_start
    anchor_center = (anchor_start + anchor_end) // 2
    minimum = int(part.get("min_price_jpy") or 1)
    maximum = int(part.get("max_price_jpy") or 10**9)
    pattern = re.compile(
        r"(?:[¥￥]\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})(?:\s*円)?|"
        r"(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})\s*円)"
    )
    excluded = re.compile(
        r"クーポン|ポイント|還元|割引|値引|円OFF|OFF|月額|毎月|分割|送料分|買取",
        re.I,
    )
    current_label = re.compile(r"販売価格|税込価格|価格|price|amount", re.I)
    non_current_label = re.compile(r"通常価格|参考価格|希望小売価格|メーカー希望|定価|旧価格|値下げ前", re.I)
    candidates = []
    for match in pattern.finditer(local_text):
        raw_price = match.group(1) or match.group(2)
        try:
            value = int(raw_price.replace(",", ""))
        except (TypeError, ValueError):
            continue
        if not minimum <= value <= maximum:
            continue
        # The listing price must appear next to the primary product title, not
        # an arbitrary related item elsewhere on the page.
        if match.start() < anchor_start - 400 or match.start() > anchor_end + 1500:
            continue
        before = local_text[max(0, match.start() - 42):match.start()]
        context = local_text[max(0, match.start() - 90):min(len(local_text), match.end() + 90)]
        if excluded.search(before[-28:]):
            continue
        # Reject a price adjacent to a recommendation for a different GPU model.
        if direct_price_context_conflicts_with_selected_gpu(part, context):
            continue
        score = 0
        if current_label.search(before) or current_label.search(context[:90]):
            score += 8
        if "¥" in match.group(0) or "￥" in match.group(0):
            score += 2
        if non_current_label.search(before):
            score -= 8
        if re.search(r"カートに入れる|在庫あり|購入する|add to cart", context, re.I):
            score += 1
        distance = abs(anchor_center - match.start())
        score -= min(5, distance // 900)
        candidates.append({
            "price_jpy": value, "score": score,
            "context": context[:260], "identity_anchor": anchor,
        })
    if not candidates:
        return None
    best_score = max(item["score"] for item in candidates)
    best = [item for item in candidates if item["score"] == best_score]
    best_values = {item["price_jpy"] for item in best}
    if len(best_values) != 1:
        return None
    chosen = sorted(best, key=lambda item: len(item["context"]))[0]
    return {
        "price_jpy": chosen["price_jpy"],
        "price_source_mode": "direct_text",
        "price_context": chosen["context"],
        "identity_anchor": chosen["identity_anchor"],
    }


def build_retailer_search_urls(part, domains, now=None, limit=2):
    """Build free retailer-site search URLs from the explicit allowlist."""
    now = now or now_jst()
    allowed = set(str(domain or "").lower().strip(".") for domain in (domains or ()))
    available = [domain for domain in RETAILER_SEARCH_TEMPLATES if domain in allowed]
    if not available:
        return []
    terms = [str(part.get("name") or "").strip(), str(part.get("model_code") or "").strip()]
    query = " ".join(term for term in terms if term)
    if not query:
        query = next((str(term).strip() for term in (part.get("aliases") or []) if str(term).strip()), "")
    if not query:
        return []
    offset = sum(ord(ch) for ch in str(part.get("id") or query))
    slot = now.hour * 12 + now.minute // 5 + offset
    count = min(max(1, int(limit)), len(available))
    chosen = [available[(slot + index) % len(available)] for index in range(count)]
    encoded_query = quote(query, safe="")
    return [
        {
            "provider": "retailer_search_page",
            "retailer_domain": domain,
            "query": query,
            "url": RETAILER_SEARCH_TEMPLATES[domain].format(query=encoded_query),
        }
        for domain in chosen
    ]


def _is_descendant_node(node, ancestor):
    current = getattr(node, "parent", None)
    while current is not None:
        if current is ancestor:
            return True
        current = getattr(current, "parent", None)
    return False


def parse_retailer_search_page(part, html_body, source_url, domains, retailer_domain):
    """Find exact-identity product-detail links; never trust search-card price as live."""
    metrics = {
        "product_card_count": 0,
        "identity_card_count": 0,
        "price_unambiguous_card_count": 0,
        "detail_link_count": 0,
        "extraction_reason": "unclassified",
    }

    def finish(links, reason):
        metrics["extraction_reason"] = reason
        return links, metrics

    if not allowed_url(source_url, domains) or not allowed_url(source_url, (retailer_domain,)):
        return finish([], "search_page_host_rejected")
    try:
        parser = _KakakuSearchTreeParser()
        parser.feed(str(html_body or ""))
        parser.close()
    except Exception:
        return finish([], "html_parse_error")

    cards = [
        node for node in parser.nodes
        if node is not parser.root and _kakaku_is_product_card(node)
    ]
    metrics["product_card_count"] = len(cards)
    if not cards:
        return finish([], "no_product_card_nodes")

    minimum = int(part.get("min_price_jpy") or 1)
    maximum = int(part.get("max_price_jpy") or 10**9)
    links_out = []
    seen = set()
    for card in cards:
        card_text = _kakaku_node_text(card)
        if not card_text or len(card_text) > 2400:
            continue
        identity = component_search_identity_anchor({"title": card_text, "snippet": ""}, part)
        if not identity:
            continue
        metrics["identity_card_count"] += 1
        card_prices = _kakaku_card_prices(card_text, minimum, maximum)
        if len(card_prices) == 1:
            metrics["price_unambiguous_card_count"] += 1
        # Search-card price is never trusted as the listing price. Keep following
        # the same-card product link even if search markup has no price or several
        # prices; the detail page must independently verify identity, price and stock.

        anchors = [
            node for node in parser.nodes
            if node.tag == "a" and _is_descendant_node(node, card)
        ]
        exact_identity_urls = set()
        unique_allowed_urls = set()
        for anchor_node in anchors:
            href = str((anchor_node.attrs or {}).get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            destination = urljoin(source_url, href)
            parsed_destination = urlparse(destination)
            if not allowed_url(destination, domains) or not allowed_url(destination, (retailer_domain,)):
                continue
            path_lower = parsed_destination.path.lower()
            if any(token in path_lower for token in (
                "/cart", "/login", "/wishlist", "/favorite", "/review", "/compare",
                "/search", "/category", "/ranking", "/support", "/help",
            )):
                continue
            if destination.rstrip("/") == source_url.rstrip("/"):
                continue
            unique_allowed_urls.add(destination)
            link_text = _kakaku_node_text(anchor_node)
            if component_search_identity_anchor({"title": link_text, "snippet": ""}, part):
                exact_identity_urls.add(destination)

        preferred = sorted(exact_identity_urls) if exact_identity_urls else (
            sorted(unique_allowed_urls) if len(unique_allowed_urls) == 1 else []
        )
        for destination in preferred:
            if destination in seen:
                continue
            seen.add(destination)
            links_out.append({
                "url": destination,
                "identity_anchor": identity,
                "card_price_jpy": card_prices[0] if len(card_prices) == 1 else None,
                "source_url": source_url,
            })
    metrics["detail_link_count"] = len(links_out)
    if links_out:
        return finish(links_out[:3], "exact_identity_detail_link_found")
    if metrics["identity_card_count"] == 0:
        reason = "sku_identity_not_found_in_product_card"
    else:
        reason = "no_allowed_product_detail_link"
    return finish([], reason)


def build_component_search_queries(part, domains=DEFAULT_DOMAINS, now=None):
    """Create a comparison-item query, a rotating retailer query, and a broad discovery fallback.

    Strict site-scoped queries can return no results when an engine ignores a site
    operator or the exact SKU is absent from the index. The final query is therefore
    intentionally unscoped; every returned URL is still host-allowlisted and seller
    candidates must be fetched and verified before becoming a trusted price.
    """
    model_code = str(part.get("model_code") or "").strip()
    name = str(part.get("name") or "").strip()
    aliases = [str(x).strip() for x in (part.get("aliases") or []) if str(x).strip()]
    safe_domains = []
    for raw_domain in domains or DEFAULT_DOMAINS:
        domain = str(raw_domain or "").strip().lower().strip(".")
        if re.fullmatch(r"[a-z0-9.-]+", domain) and "." in domain and domain not in safe_domains:
            safe_domains.append(domain)
    if not safe_domains:
        safe_domains = list(DEFAULT_DOMAINS)

    retailer_priority = (
        "amazon.co.jp", "shopping.yahoo.co.jp", "rakuten.co.jp", "yodobashi.com", "biccamera.com",
        "dospara.co.jp", "tsukumo.co.jp", "pc-koubou.jp", "sofmap.com",
        "joshinweb.jp", "ark-pc.co.jp", "edion.com", "ksdenki.com",
        "nojima.co.jp", "yamada-denkiweb.com",
    )
    seller_domains = [d for d in retailer_priority if d in safe_domains]
    seller_domains.extend(
        d for d in safe_domains
        if d != "kakaku.com" and d not in seller_domains
    )
    now = now or now_jst()
    queries = []

    # Query the canonical comparison item by visible product name rather than
    # SKU alone: comparison-site snippets often index the product title but not
    # the manufacturer's complete model code.
    monitor_url = str(part.get("monitor_url") or "")
    monitor = urlparse(monitor_url)
    if (monitor.hostname or "").lower().removeprefix("www.") == "kakaku.com":
        path_match = re.match(r"^/item/[A-Za-z0-9]+", monitor.path, re.I)
        item_scope = path_match.group(0) if path_match else ""
        term = name or model_code
        if term:
            queries.append('site:kakaku.com{} "{}"'.format(item_scope, term))
    elif model_code:
        queries.append('"{}" 価格 site:kakaku.com'.format(model_code))

    if seller_domains:
        # Stable part-specific offset + current 5-minute slot; the seller rotates
        # so the free monitor spreads traffic across configured retailers.
        part_offset = sum(ord(ch) for ch in str(part.get("id") or name))
        slot = now.hour * 12 + (now.minute // 5) + part_offset
        seller_domain = seller_domains[slot % len(seller_domains)]
        term = (aliases[0] if aliases else name) or model_code
        if term:
            queries.append('site:{} "{}" 価格'.format(seller_domain, term))

    # Important fallback: don't let an unsupported/ignored site: operator make
    # all candidates disappear. URLs are still checked against the configured
    # allowlist, and no search snippet is promoted to a current/checkout price.
    discovery_term = (aliases[0] if aliases else name) or model_code
    if discovery_term:
        queries.append("{} 価格 最安値".format(discovery_term))

    unique = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip()
        if query and query not in unique:
            unique.append(query)
    return unique[:3]


def verify_retailer_listing(part, candidate_url, domains, diagnostic_out=None):
    """Fetch and verify a direct seller listing with explicit failure diagnostics.

    Search results are hints only. The page itself must prove the requested
    exact model, a plausible directly parsed price, and valid point-in-time
    evidence. Inventory is tracked separately from price/identity validity.
    """
    diagnostic = diagnostic_out if isinstance(diagnostic_out, dict) else {}

    def fail(reason_code, **details):
        diagnostic.update({
            "status": "unverified",
            "reason_code": reason_code,
            **details,
        })
        return None

    diagnostic.update({
        "provider": "direct_listing_verifier",
        "candidate_url": str(candidate_url or "")[:240],
        "final_url": None,
        "retailer_domain": (urlparse(str(candidate_url or "")).hostname or "").lower(),
        "identity_anchor": None,
        "page_name": None,
        "price_source_mode": None,
        "parsed_price_jpy": None,
        "price_context_excerpt": None,
        "stock_status": "unknown",
        "structured_stock_status": None,
        "text_stock_status": None,
    })
    if not allowed_url(candidate_url, domains):
        return fail("candidate_url_host_not_allowlisted")
    candidate_host = (urlparse(candidate_url).hostname or "").lower()
    if candidate_host == "kakaku.com" or candidate_host.endswith(".kakaku.com"):
        return fail("comparison_site_is_not_direct_retailer")
    try:
        try:
            html, final_url, _headers = fetch(candidate_url, timeout=11)
        except Exception as exc:
            return fail(
                "fetch_error",
                error_type=type(exc).__name__,
                error_message=str(exc)[:180],
            )
        diagnostic["final_url"] = str(final_url or "")[:240]
        final_host = (urlparse(final_url).hostname or "").lower()
        diagnostic["final_host"] = final_host
        if not allowed_url(final_url, domains):
            return fail("redirect_left_allowlist")
        if final_host == "kakaku.com" or final_host.endswith(".kakaku.com"):
            return fail("comparison_site_redirect_not_retailer")

        try:
            raw = parse_page(final_url, html, expected=part)
        except Exception as exc:
            return fail(
                "page_parse_error",
                error_type=type(exc).__name__,
                error_message=str(exc)[:180],
            )
        diagnostic.update({
            "page_name": str(raw.get("name") or "")[:180] or None,
            "price_source_mode": raw.get("price_source_mode"),
            "parsed_price_jpy": raw.get("price_jpy"),
            "raw_stock_status": raw.get("stock_status"),
            "structured_stock_status": raw.get("structured_stock_status"),
            "text_stock_status": raw.get("text_stock_status"),
            "stock_ambiguity": raw.get("stock_ambiguity"),
            "structured_identity_match": raw.get("structured_identity_match"),
        })

        try:
            anchor = component_primary_identity_anchor(part, html, raw)
        except Exception as exc:
            return fail(
                "identity_parse_error",
                error_type=type(exc).__name__,
                error_message=str(exc)[:180],
            )
        if not anchor:
            excerpt = str(raw.get("page_text_excerpt") or "")
            return fail(
                "exact_model_identity_not_found_in_primary_page",
                page_text_excerpt=excerpt[:220] or None,
            )
        diagnostic["identity_anchor"] = str(anchor)[:180]

        price = raw.get("price_jpy")
        source_mode = raw.get("price_source_mode")
        price_context = raw.get("price_context")
        # Reparse direct-text prices around the primary product heading. The
        # shared PC parser has a higher minimum price and may select a related
        # product amount from an accessory page.
        if price is None or source_mode == "direct_text" or source_mode not in (
            "direct_structured", "direct_meta", "direct_text"
        ):
            try:
                direct = parse_component_direct_text_price(part, html, anchor)
            except Exception as exc:
                direct = None
                diagnostic["direct_text_parse_error"] = type(exc).__name__ + ":" + str(exc)[:140]
            if direct:
                price = direct["price_jpy"]
                source_mode = direct["price_source_mode"]
                price_context = direct.get("price_context")
                anchor = direct.get("identity_anchor") or anchor
                diagnostic.update({
                    "identity_anchor": str(anchor)[:180],
                    "price_source_mode": source_mode,
                    "parsed_price_jpy": price,
                })
            elif source_mode == "direct_text":
                price = None
                source_mode = "none"
                diagnostic.update({"price_source_mode": source_mode, "parsed_price_jpy": None})

        minimum = int(part.get("min_price_jpy") or 1)
        maximum = int(part.get("max_price_jpy") or 10**9)
        diagnostic["price_context_excerpt"] = str(price_context or "")[:220] or None
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            return fail("direct_price_missing_or_not_integer")
        if not minimum <= price <= maximum:
            return fail(
                "direct_price_outside_configured_range",
                minimum_price_jpy=minimum,
                maximum_price_jpy=maximum,
            )
        if source_mode not in ("direct_structured", "direct_meta", "direct_text"):
            return fail("price_source_mode_not_directly_parsed")

        # Stock proof must relate to the exact product. If parse_page found
        # JSON-LD offers for the exact Product node, trust that scoped signal,
        # not store-wide text that may mention unrelated sold-out branches.
        if source_mode == "direct_structured":
            if "structured_stock_status" in raw:
                stock_status = raw.get("structured_stock_status") or "unknown"
                if stock_status == "unknown":
                    stock_status = stock_from_component_context(price_context)
            else:
                # Backwards-compatible for callers/tests mocking the older
                # parser schema. Live parse_page now emits the scoped field.
                stock_status = raw.get("stock_status") or "unknown"
        else:
            stock_status = stock_from_component_context(price_context)
        diagnostic["stock_status"] = stock_status

        retrieved = iso(now_jst())
        offer = {
            "url": final_url,
            "title": raw.get("name") if component_search_identity_anchor(
                {"title": raw.get("name") or "", "snippet": ""}, part
            ) else anchor,
            "price_jpy": price,
            "price_source_mode": source_mode,
            "stock_status": stock_status,
            "identity_anchor": anchor,
            "identity_match": True,
            "source_role": "direct_retailer_listing_reference",
            "available_at": retrieved,
            "retrieval_time": retrieved,
            "pit_valid": True,
            "bf_actual_authorized": False,
            "price_context": price_context,
        }
        diagnostic.update({
            "status": "verified",
            "reason_code": "exact_identity_direct_price_and_pit_verified",
        })
        return offer
    except Exception as exc:
        return fail(
            "verification_exception",
            error_type=type(exc).__name__,
            error_message=str(exc)[:180],
        )

def search_comparison_snippet(part, domains):
    """Search approved sites, verify seller-page offers directly, and keep snippets display-only.

    Result URLs are untrusted until their host is allowlisted. Seller prices are
    accepted only after re-fetching the listing and validating identity, a
    plausible directly parsed price, and an in-stock signal.
    """
    queries = build_component_search_queries(part, domains)
    diagnostics = []
    all_snippet_candidates = []
    verified_offers = []
    direct_fetch_attempts = 0

    # Some exact retailer detail URLs are curated from official seller/product
    # pages when rotating search markup consistently hides the item link.
    # They remain untrusted until this same verifier confirms identity, price,
    # inventory state and point-in-time evidence.
    for candidate_url in (part.get("direct_retailer_urls") or [])[:4]:
        url = str(candidate_url or "").strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        fetch_before = direct_fetch_attempts
        offers_before = len(verified_offers)
        if not allowed_url(url, domains):
            diagnostics.append({
                "provider": "configured_direct_retailer",
                "retailer_domain": host or None,
                "url": url[:240] or None,
                "status": "rejected",
                "error": "configured_direct_url_host_not_allowlisted",
                "result_count": 0,
                "page_fetch_count": 0,
                "allowed_reference_host_count": 0,
                "identity_anchor_count": 0,
                "in_range_price_count": 0,
                "direct_retailer_fetch_attempt_count": 0,
                "verified_retailer_listing_count": 0,
                "source_role": "direct_retailer_listing_reference",
            })
            continue
        if direct_fetch_attempts >= 5:
            diagnostics.append({
                "provider": "configured_direct_retailer",
                "retailer_domain": host,
                "url": url[:240],
                "status": "skipped",
                "error": "per_part_direct_fetch_budget_reached_after_five_attempts",
                "result_count": 0,
                "page_fetch_count": 0,
                "allowed_reference_host_count": 1,
                "identity_anchor_count": 0,
                "in_range_price_count": 0,
                "direct_retailer_fetch_attempt_count": 0,
                "verified_retailer_listing_count": 0,
                "source_role": "direct_retailer_listing_reference",
            })
            continue
        direct_fetch_attempts += 1
        verification = {}
        offer = verify_retailer_listing(part, url, domains, diagnostic_out=verification)
        if offer and offer.get("url") not in {x.get("url") for x in verified_offers}:
            verified_offers.append(offer)
        diagnostics.append({
            "provider": "configured_direct_retailer",
            "retailer_domain": host,
            "url": url[:240],
            "status": "verified" if offer else "unverified",
            "error": verification.get("reason_code") if not offer else None,
            "validation": {
                key: verification.get(key)
                for key in (
                    "reason_code", "final_url", "final_host", "identity_anchor",
                    "page_name", "price_source_mode", "parsed_price_jpy",
                    "price_context_excerpt", "raw_stock_status",
                    "structured_stock_status", "text_stock_status",
                    "stock_ambiguity", "structured_identity_match",
                    "error_type", "error_message", "page_text_excerpt",
                )
                if verification.get(key) is not None
            },
            "result_count": 1 if offer else 0,
            "page_fetch_count": 1,
            "allowed_reference_host_count": 1,
            "identity_anchor_count": 1 if offer and offer.get("identity_match") else 0,
            "in_range_price_count": 1 if offer else 0,
            "direct_retailer_fetch_attempt_count": direct_fetch_attempts - fetch_before,
            "verified_retailer_listing_count": len(verified_offers) - offers_before,
            "stock_status": (offer or verification).get("stock_status") or "unknown",
            "source_role": "direct_retailer_listing_reference",
        })
    # Evaluate every configured candidate before selecting; returning at the
    # first in-stock seller biases the ranking toward configuration order and
    # can miss a cheaper exact-SKU offer at the next retailer.
    if any(item.get("stock_status") == "in_stock" for item in verified_offers):
        verified_offers.sort(key=lambda item: (
            0 if item.get("stock_status") == "in_stock" else 1,
            item.get("price_jpy", 10**12),
            0 if item.get("price_source_mode") == "direct_structured" else 1,
            0 if item.get("identity_anchor") == str(part.get("model_code") or "") else 1,
        ))
        return {
            "retailer_listing_offer": verified_offers[0],
            "retailer_listing_offers": verified_offers,
            "search_diagnostics": diagnostics,
        }

    # Kakaku's product page often loads its price table client-side. Try its own
    # search-results page as a weaker display-only source before external search.
    # It does not count as direct retailer evidence and never authorizes buying.
    monitor = urlparse(str(part.get("monitor_url") or ""))
    if (monitor.hostname or "").lower().removeprefix("www.") == "kakaku.com":
        search_term = str(part.get("name") or part.get("model_code") or "").strip()
        kakaku_url = "https://search.kakaku.com/{}/".format(quote(search_term, safe="")) if search_term else ""
        if kakaku_url and allowed_url(kakaku_url, domains):
            try:
                body, final_url, _headers = fetch(kakaku_url, timeout=6)
                page_metrics = {}
                reference = parse_kakaku_search_page_reference(part, body, final_url, page_metrics)
                diagnostics.append({
                    "provider": "kakaku_search_page",
                    "query_index": 0,
                    "query": search_term,
                    "status": "ok",
                    "error": None,
                    "result_count": page_metrics.get("product_card_count", 0),
                    "page_fetch_count": 1,
                    "allowed_reference_host_count": 1,
                    "rejected_host_samples": [],
                    "rejected_url_samples": [],
                    "same_comparison_item_path_count": 0,
                    "identity_anchor_count": page_metrics.get("identity_card_count", 0),
                    "in_range_price_count": page_metrics.get("single_price_identity_card_count", 0),
                    "ambiguous_price_card_count": page_metrics.get("ambiguous_price_card_count", 0),
                    "extraction_reason": page_metrics.get("extraction_reason", "unclassified"),
                    "direct_retailer_fetch_attempt_count": 0,
                    "verified_retailer_listing_count": 0,
                    "source_role": "comparison_site_search_snippet_reference",
                })
                if reference:
                    all_snippet_candidates.append(reference)
            except Exception as exc:
                diagnostics.append({
                    "provider": "kakaku_search_page",
                    "query_index": 0,
                    "query": search_term,
                    "status": "error",
                    "error": type(exc).__name__ + ":" + str(exc)[:140],
                    "result_count": 0,
                    "allowed_reference_host_count": 0,
                    "rejected_host_samples": [],
                    "rejected_url_samples": [],
                    "same_comparison_item_path_count": 0,
                    "identity_anchor_count": 0,
                    "in_range_price_count": 0,
                    "direct_retailer_fetch_attempt_count": 0,
                    "verified_retailer_listing_count": 0,
                    "source_role": "comparison_site_search_snippet_reference",
                })

    # Search a rotating set of allowlisted retailer pages directly. Search-card
    # prices only identify candidate listings; each detail URL is fetched again.
    for search in build_retailer_search_urls(part, domains, limit=2):
        page_metrics = {}
        search_url = search["url"]
        retailer_domain = search["retailer_domain"]
        links = []
        page_status = "error"
        page_error = None
        direct_before = direct_fetch_attempts
        offer_before = len(verified_offers)
        try:
            body, final_url, _headers = fetch(search_url, timeout=6)
            if not allowed_url(final_url, domains) or not allowed_url(final_url, (retailer_domain,)):
                raise RuntimeError("retailer_search_redirect_left_allowlist")
            links, page_metrics = parse_retailer_search_page(
                part, body, final_url, domains, retailer_domain
            )
            page_status = "ok"
            for link in links[:2]:
                if direct_fetch_attempts >= 5:
                    break
                direct_fetch_attempts += 1
                offer = verify_retailer_listing(part, link["url"], domains)
                if offer and offer.get("url") not in {x.get("url") for x in verified_offers}:
                    verified_offers.append(offer)
        except Exception as exc:
            page_status = "error"
            page_error = type(exc).__name__ + ":" + str(exc)[:140]
        diagnostics.append({
            "provider": "retailer_search_page",
            "query_index": 0,
            "query": search.get("query"),
            "retailer_domain": retailer_domain,
            "status": page_status,
            "error": page_error,
            "result_count": page_metrics.get("product_card_count", 0),
            "page_fetch_count": 1,
            "allowed_reference_host_count": 1 if page_status == "ok" else 0,
            "rejected_host_samples": [],
            "rejected_url_samples": [],
            "identity_anchor_count": page_metrics.get("identity_card_count", 0),
            "in_range_price_count": page_metrics.get("price_unambiguous_card_count", 0),
            "detail_link_count": page_metrics.get("detail_link_count", 0),
            "extraction_reason": page_metrics.get("extraction_reason", "fetch_failed"),
            "direct_retailer_fetch_attempt_count": direct_fetch_attempts - direct_before,
            "verified_retailer_listing_count": len(verified_offers) - offer_before,
            "source_role": "direct_retailer_listing_reference",
        })

    if any(item.get("stock_status") == "in_stock" for item in verified_offers):
        verified_offers.sort(key=lambda item: (
            0 if item.get("stock_status") == "in_stock" else 1,
            item.get("price_jpy", 10**12),
            0 if item.get("price_source_mode") == "direct_structured" else 1,
            0 if item.get("identity_anchor") == str(part.get("model_code") or "") else 1,
        ))
        return {
            "retailer_listing_offer": verified_offers[0],
            "retailer_listing_offers": verified_offers,
            "search_diagnostics": diagnostics,
        }

    # Bing is the primary free search path. DuckDuckGo's HTML endpoint has
    # frequently returned an empty/blocked document in runners, so only repeat
    # the broad unscoped discovery query there instead of doubling every request.
    search_jobs = [("bing", bing_search, query, index) for index, query in enumerate(queries, 1)]
    if queries:
        search_jobs.append(("duckduckgo", ddg_search, queries[-1], len(queries)))

    for provider, search_fn, query, query_index in search_jobs:
            try:
                results = search_fn(query, timeout=7) or []
                error = None
            except Exception as exc:
                results = []
                error = type(exc).__name__ + ":" + str(exc)[:140]
            domain_count = 0
            same_item_count = 0
            identity_count = 0
            price_count = 0
            rejected_host_samples = []
            rejected_url_samples = []
            local_fetch_start = direct_fetch_attempts
            local_offer_start = len(verified_offers)
            for result in results:
                url = str(result.get("url") or "")
                if not allowed_url(url, domains):
                    parsed_rejected = urlparse(url)
                    rejected_host = (parsed_rejected.hostname or "").lower()
                    if rejected_host and rejected_host not in rejected_host_samples and len(rejected_host_samples) < 5:
                        rejected_host_samples.append(rejected_host)
                    if url and len(rejected_url_samples) < 3:
                        rejected_url_samples.append(url[:180])
                    continue
                domain_count += 1
                parsed_url = urlparse(url)
                path = parsed_url.path.rstrip("/").lower()
                anchor = component_search_identity_anchor(result, part)
                product_path = urlparse(str(part.get("monitor_url") or "")).path.rstrip("/").lower()
                same_item_path = bool(product_path and (path == product_path or path.startswith(product_path + "/")))
                same_item_count += int(same_item_path)
                if not anchor:
                    continue
                identity_count += 1

                host = (parsed_url.hostname or "").lower()
                is_comparison_site = host == "kakaku.com" or host.endswith(".kakaku.com")
                # Bound direct seller-page fetches so each scheduled run remains
                # lightweight while checking a bounded number of imperfect search results.
                if not is_comparison_site and direct_fetch_attempts < 4:
                    direct_fetch_attempts += 1
                    verification = {}
                    offer = verify_retailer_listing(part, url, domains, diagnostic_out=verification)
                    if offer and offer.get("url") not in {x.get("url") for x in verified_offers}:
                        verified_offers.append(offer)
                    if len(rejected_url_samples) < 3:
                        # Keep search diagnostics compact; only retain reason
                        # categories and a few exact identity/stock fields.
                        rejected_url_samples.append(json.dumps({
                            "url": str(url)[:160],
                            "reason_code": verification.get("reason_code"),
                            "identity_anchor": verification.get("identity_anchor"),
                            "price_source_mode": verification.get("price_source_mode"),
                            "parsed_price_jpy": verification.get("parsed_price_jpy"),
                            "stock_status": verification.get("stock_status"),
                            "error_type": verification.get("error_type"),
                        }, ensure_ascii=False)[:480])

                blob = str(result.get("title") or "") + " " + str(result.get("snippet") or "")
                candidate = parse_snippet_price(
                    blob, part.get("min_price_jpy") or 1, part.get("max_price_jpy") or 10**9
                )
                if not candidate:
                    continue
                price_count += 1
                all_snippet_candidates.append({
                    "url": url, "title": result.get("title") or "",
                    "snippet": result.get("snippet") or "", "price_jpy": candidate["price_jpy"],
                    "price_context": candidate.get("context"), "identity_anchor": anchor,
                    "source_role": "comparison_site_search_snippet_reference",
                    "bf_actual_authorized": False, "search_provider": provider, "query": query,
                    "same_comparison_item_path": same_item_path,
                })
            diagnostics.append({
                "provider": provider, "query_index": query_index, "query": query,
                "status": "error" if error else "ok", "error": error,
                "result_count": len(results), "allowed_reference_host_count": domain_count,
                "rejected_host_samples": rejected_host_samples, "rejected_url_samples": rejected_url_samples,
                "same_comparison_item_path_count": same_item_count,
                "identity_anchor_count": identity_count, "in_range_price_count": price_count,
                "direct_retailer_fetch_attempt_count": direct_fetch_attempts - local_fetch_start,
                "verified_retailer_listing_count": len(verified_offers) - local_offer_start,
            })
            if any(item.get("stock_status") == "in_stock" for item in verified_offers):
                verified_offers.sort(key=lambda item: (
                    0 if item.get("stock_status") == "in_stock" else 1,
                    item.get("price_jpy", 10**12),
                    0 if item.get("price_source_mode") == "direct_structured" else 1,
                    0 if item.get("identity_anchor") == str(part.get("model_code") or "") else 1,
                ))
                return {
                    "retailer_listing_offer": verified_offers[0],
                    "retailer_listing_offers": verified_offers,
                    "search_diagnostics": diagnostics,
                }
    if all_snippet_candidates:
        all_snippet_candidates.sort(key=lambda item: (
            1 if item.get("same_comparison_item_path") else 0,
            1 if item.get("search_provider") == "bing" else 0,
            item.get("identity_anchor") == str(part.get("model_code") or ""),
        ), reverse=True)
        chosen = all_snippet_candidates[0]
        chosen["search_diagnostics"] = diagnostics
        chosen["retailer_listing_offers"] = verified_offers
        return chosen
    if verified_offers:
        verified_offers.sort(key=lambda item: (
            0 if item.get("stock_status") == "in_stock" else 1,
            item.get("price_jpy", 10**12),
            0 if item.get("price_source_mode") == "direct_structured" else 1,
            0 if item.get("identity_anchor") == str(part.get("model_code") or "") else 1,
        ))
        return {
            "retailer_listing_offer": verified_offers[0],
            "retailer_listing_offers": verified_offers,
            "search_diagnostics": diagnostics,
        }
    return {"search_diagnostics": diagnostics} if diagnostics else None

def fetch_part(part, domains, search_domains=None):
    # Search fallback hosts are explicitly configured; default to the direct
    # comparison allowlist for standalone/test calls rather than an undefined name.
    search_domains = tuple(search_domains or domains)
    result = {
        "id": part["id"], "category": part["category"], "name": part["name"],
        "model_code": part.get("model_code"), "monitor_url": part.get("monitor_url"),
        "purchase_url": part.get("purchase_url") or part.get("monitor_url"),
        "role": part.get("role"), "target_price_jpy": part.get("target_price_jpy"),
        "source_role": "comparison_site_reference", "bf_actual_authorized": False,
        "price_source_mode": "none", "price_validation_status": "missing",
        "market_reference_price_jpy": None, "search_snippet_reference_price_jpy": None,
        "search_snippet_reference_url": None, "search_snippet_reference_title": None,
        "search_snippet_identity_anchor": None, "search_diagnostics": [],
        "retailer_listing_offer": None, "retailer_listing_offers": [],
        "retailer_listing_reference_price_jpy": None, "retailer_listing_reference_url": None,
        "comparison_stock_signal": "unknown", "retrieval_time": None,
        "available_at": None, "pit_valid": False,
        "fetch_status": "error", "last_fetch_error": None, "identity_match": False,
        "identity_matches": []
    }
    url = part.get("monitor_url")
    if not url or not allowed_url(url, domains):
        result["last_fetch_error"] = "unapproved_comparison_url"
        return result
    retrieval = iso(now_jst())
    try:
        html, final_url, _headers = fetch(url, timeout=14)
        if not allowed_url(final_url, domains):
            raise RuntimeError("redirect_left_allowed_comparison_domain")
        raw = parse_page(final_url, html, expected=part)
        identity_ok, matches = identity_match(part, raw)
        result.update({
            "fetch_status": "ok", "retrieval_time": retrieval,
            "available_at": retrieval if raw.get("price_jpy") is not None else None,
            "pit_valid": bool(raw.get("price_jpy") is not None and parse_dt(retrieval) and parse_dt(retrieval) >= parse_dt(retrieval)),
            "identity_match": identity_ok, "identity_matches": matches, "final_url": final_url,
            "comparison_stock_signal": raw.get("stock_status") or "unknown",
            "price_source_mode": raw.get("price_source_mode") or "none"
        })
        price = raw.get("price_jpy")
        if not identity_ok:
            result["price_validation_status"] = "identity_unverified"
            result["last_fetch_error"] = "model_identity_not_found_in_returned_page_text"
        elif not result["available_at"] or not result["pit_valid"]:
            result["price_validation_status"] = "missing"
            result["last_fetch_error"] = "price_or_point_in_time_missing"
        elif result["price_source_mode"] not in ("direct_structured", "direct_meta", "direct_text"):
            result["price_validation_status"] = "reference_only"
            result["last_fetch_error"] = "not_directly_parsed_from_comparison_page"
        elif isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            result["price_validation_status"] = "invalid_price"
            result["last_fetch_error"] = "price_not_positive_integer"
        elif part.get("min_price_jpy") is not None and price < int(part["min_price_jpy"]):
            result["price_validation_status"] = "anomaly_rejected"
            result["last_fetch_error"] = "below_part_specific_plausibility_floor"
        elif part.get("max_price_jpy") is not None and price > int(part["max_price_jpy"]):
            result["price_validation_status"] = "anomaly_rejected"
            result["last_fetch_error"] = "above_part_specific_tracking_ceiling"
        else:
            result["market_reference_price_jpy"] = int(price)
            result["price_validation_status"] = "verified_market_reference"
            result["data_confidence"] = raw.get("data_confidence") or "medium"
            result["page_name"] = raw.get("name")
            result["price_context"] = raw.get("price_context")

        # Some comparison pages render their price table client-side. When the
        # exact page/model was found but the parser could not read a price, use
        # a model-anchored search snippet for display only, never as a total.
        if identity_ok and price is None:
            snippet = search_comparison_snippet(part, search_domains)
            if snippet:
                result["search_diagnostics"] = snippet.get("search_diagnostics") or []
                offers = snippet.get("retailer_listing_offers") or []
                best_offer = snippet.get("retailer_listing_offer")
                result["retailer_listing_offers"] = offers or ([best_offer] if best_offer else [])
                if best_offer:
                    result["retailer_listing_offer"] = best_offer
                    result["retailer_listing_reference_url"] = best_offer.get("url")
                    if best_offer.get("stock_status") == "in_stock":
                        result["retailer_listing_reference_price_jpy"] = int(best_offer["price_jpy"])
                        result["available_at"] = best_offer.get("available_at") or retrieval
                        result["retrieval_time"] = best_offer.get("retrieval_time") or retrieval
                        result["pit_valid"] = best_offer.get("pit_valid") is True
                        result["price_validation_status"] = "verified_retailer_listing_reference"
                        result["price_source_mode"] = best_offer.get("price_source_mode")
                        result["identity_match"] = best_offer.get("identity_match") is True
                        result["identity_matches"] = [best_offer.get("identity_anchor")]
                        result["last_fetch_error"] = (
                            "Direct retailer listing verified; final checkout price, delivery cost and final-cart stock remain unconfirmed."
                        )
            if result["price_validation_status"] != "verified_retailer_listing_reference":
                if snippet and isinstance(snippet.get("price_jpy"), int):
                    result["search_snippet_reference_price_jpy"] = int(snippet["price_jpy"])
                    result["search_snippet_reference_url"] = snippet["url"]
                    result["search_snippet_reference_title"] = snippet["title"]
                    result["search_snippet_identity_anchor"] = snippet["identity_anchor"]
                    result["search_provider"] = snippet.get("search_provider")
                    result["search_query"] = snippet.get("query")
                    result["available_at"] = retrieval
                    result["pit_valid"] = True
                    result["price_source_mode"] = "search_snippet"
                    result["price_validation_status"] = "search_snippet_reference"
                    result["last_fetch_error"] = "direct price unavailable; snippet reference is display-only and excluded from estimates"
                else:
                    counts = [
                        "{}:{} results / {} allowed host / {} identity / {} priced / {} seller listings".format(
                            item.get("provider"), item.get("result_count", 0),
                            item.get("allowed_reference_host_count", 0),
                            item.get("identity_anchor_count", 0), item.get("in_range_price_count", 0),
                            item.get("verified_retailer_listing_count", 0)
                        ) for item in result["search_diagnostics"]
                    ]
                    result["last_fetch_error"] = "price_or_point_in_time_missing; search diagnostic: " + "; ".join(counts)[:260]
    except Exception as exc:
        result["fetch_status"] = "error"
        result["last_fetch_error"] = type(exc).__name__ + ":" + str(exc)[:180]
    return result


def collect_component_prices(config=None):
    config = config or load_json(CONFIG_PATH, {})
    profile = config.get("profile") or {}
    domains = tuple(profile.get("allowed_comparison_domains") or DEFAULT_DOMAINS)
    search_domains = tuple(profile.get("allowed_search_reference_domains") or domains)
    parts = [x for x in (config.get("parts") or []) if isinstance(x, dict) and x.get("track_price")]
    prior = load_json(OUTPUT_PATH, {})
    prior_by_id = last_by_id(prior.get("products") or [])
    previous_events = last_by_id(read_jsonl(EVENTS_PATH))
    results = {}
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(parts)))) as pool:
        futures = {pool.submit(fetch_part, part, domains, search_domains): part for part in parts}
        for future in as_completed(futures):
            part = futures[future]
            try:
                results[part["id"]] = future.result()
            except Exception as exc:
                results[part["id"]] = {
                    "id": part["id"], "category": part.get("category"), "name": part.get("name"),
                    "model_code": part.get("model_code"), "monitor_url": part.get("monitor_url"),
                    "purchase_url": part.get("purchase_url"), "target_price_jpy": part.get("target_price_jpy"),
                    "source_role": "comparison_site_reference", "bf_actual_authorized": False,
                    "price_source_mode": "none", "price_validation_status": "missing",
                    "market_reference_price_jpy": None, "search_snippet_reference_price_jpy": None,
                    "search_snippet_reference_url": None, "search_snippet_reference_title": None,
                    "search_snippet_identity_anchor": None, "search_diagnostics": [],
                    "comparison_stock_signal": "unknown", "retrieval_time": None,
                    "available_at": None, "pit_valid": False,
                    "fetch_status": "error", "last_fetch_error": type(exc).__name__ + ":" + str(exc)[:180],
                    "identity_match": False, "identity_matches": []
                }
    output_rows, observations, events = [], [], []
    counts = {"verified_market_reference": 0, "verified_retailer_listing_reference": 0, "search_snippet_reference": 0, "identity_unverified": 0, "fetch_error": 0, "unverified_or_missing": 0}
    for part in parts:
        row = results[part["id"]]
        previous = prior_by_id.get(part["id"]) or {}
        prev_price = previous.get("market_reference_price_jpy")
        price = row.get("market_reference_price_jpy")
        row["last_valid_market_reference_jpy"] = price if row.get("price_validation_status") == "verified_market_reference" else (prev_price if isinstance(prev_price, int) else None)
        row["bf_actual_authorized"] = False
        if row.get("price_validation_status") == "verified_market_reference":
            counts["verified_market_reference"] += 1
            observations.append({
                "id": row["id"], "category": row["category"], "model_code": row.get("model_code"),
                "market_reference_price_jpy": price, "source_role": "comparison_site_reference",
                "source_url": row.get("final_url") or row.get("monitor_url"),
                "available_at": row.get("available_at"), "retrieval_time": row.get("retrieval_time"),
                "observed_at": row.get("retrieval_time"), "pit_valid": row.get("pit_valid") is True,
                "identity_match": True, "price_validation_status": "verified_market_reference",
                "stock_signal": row.get("comparison_stock_signal"), "bf_actual_authorized": False
            })
            if isinstance(prev_price, int) and prev_price != price:
                events.append({
                    "id": row["id"], "category": row["category"], "model_code": row.get("model_code"),
                    "observed_at": row.get("retrieval_time"), "available_at": row.get("available_at"),
                    "retrieval_time": row.get("retrieval_time"), "prediction_time": row.get("retrieval_time"),
                    "pit_valid": row.get("pit_valid") is True, "old_market_reference_price_jpy": prev_price,
                    "new_market_reference_price_jpy": price, "delta_jpy": price-prev_price,
                    "source_role": "comparison_site_reference", "bf_actual_authorized": False,
                    "source_url": row.get("final_url") or row.get("monitor_url")
                })
        elif row.get("price_validation_status") == "verified_retailer_listing_reference" and isinstance(row.get("retailer_listing_reference_price_jpy"), int):
            counts["verified_retailer_listing_reference"] += 1
            offer = row.get("retailer_listing_offer") or {}
            retail_price = int(row["retailer_listing_reference_price_jpy"])
            observations.append({
                "id": row["id"], "category": row["category"], "model_code": row.get("model_code"),
                "market_reference_price_jpy": retail_price, "source_role": "direct_retailer_listing_reference",
                "source_url": offer.get("url") or row.get("retailer_listing_reference_url"),
                "available_at": row.get("available_at"), "retrieval_time": row.get("retrieval_time"),
                "observed_at": row.get("retrieval_time"), "pit_valid": row.get("pit_valid") is True,
                "identity_match": row.get("identity_match") is True,
                "price_validation_status": "verified_retailer_listing_reference",
                "stock_signal": offer.get("stock_status"), "bf_actual_authorized": False
            })
            previous_retail_price = previous.get("retailer_listing_reference_price_jpy")
            if isinstance(previous_retail_price, int) and previous_retail_price != retail_price:
                events.append({
                    "id": row["id"], "category": row["category"], "model_code": row.get("model_code"),
                    "observed_at": row.get("retrieval_time"), "available_at": row.get("available_at"),
                    "retrieval_time": row.get("retrieval_time"), "prediction_time": row.get("retrieval_time"),
                    "pit_valid": row.get("pit_valid") is True, "old_market_reference_price_jpy": previous_retail_price,
                    "new_market_reference_price_jpy": retail_price, "delta_jpy": retail_price-previous_retail_price,
                    "source_role": "direct_retailer_listing_reference", "bf_actual_authorized": False,
                    "source_url": offer.get("url") or row.get("retailer_listing_reference_url")
                })
        elif row.get("price_validation_status") == "search_snippet_reference" and isinstance(row.get("search_snippet_reference_price_jpy"), int):
            counts["search_snippet_reference"] += 1
            observations.append({
                "id": row["id"], "category": row["category"], "model_code": row.get("model_code"),
                "search_snippet_reference_price_jpy": row["search_snippet_reference_price_jpy"],
                "source_role": "comparison_site_search_snippet_reference",
                "source_url": row.get("search_snippet_reference_url"),
                "retrieval_time": row.get("retrieval_time"), "available_at": row.get("available_at"),
                "observed_at": row.get("retrieval_time"), "pit_valid": row.get("pit_valid") is True,
                "identity_match": row.get("identity_match") is True,
                "search_snippet_identity_anchor": row.get("search_snippet_identity_anchor"),
                "bf_actual_authorized": False
            })
        elif row.get("price_validation_status") == "identity_unverified":
            counts["identity_unverified"] += 1
        else:
            counts["unverified_or_missing"] += 1
        if row.get("fetch_status") == "error":
            counts["fetch_error"] += 1
        output_rows.append(row)
    append_jsonl(OBSERVATIONS_PATH, observations)
    append_jsonl(EVENTS_PATH, events)
    output = {
        "generated_at": iso(now_jst()), "schema_version": 1,
        "source_role": "comparison_site_reference",
        "policy": "References may be direct comparison-site prices or directly fetched retailer product listings after identity and price checks; neither proves final checkout price or official BF actuals.",
        "bf_actual_authorized": False,
        "coverage": {"tracked_part_count": len(parts), **counts},
        "products": output_rows
    }
    save_json(OUTPUT_PATH, output)
    print(json.dumps({"status":"OK","generated_at":output["generated_at"],"coverage":output["coverage"]},ensure_ascii=False))
    return output


if __name__ == "__main__":
    collect_component_prices()
