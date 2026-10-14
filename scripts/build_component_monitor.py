"""Collect component comparison prices as non-actionable market references."""
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone, timedelta
from urllib.parse import urlparse

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


def build_component_search_queries(part):
    """Use diversified SKU/name searches instead of forcing an indexed comparison URL path."""
    model_code = str(part.get("model_code") or "").strip()
    name = str(part.get("name") or "").strip()
    queries = []
    if model_code:
        queries.append('"{}" 価格'.format(model_code))
    if name:
        queries.append('"{}" 価格 最安値'.format(name))
    unique = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip()
        if query and query not in unique:
            unique.append(query)
    return unique[:3]


def verify_retailer_listing(part, candidate_url, domains):
    """Fetch an allowlisted seller page and verify identity, direct price and stock.

    Search snippets are discovery hints only. A listing is emitted as a current
    retailer reference only after the page itself parses a plausible price and
    the configured exact product identity is present in the fetched page.
    """
    if not allowed_url(candidate_url, domains):
        return None
    candidate_host = (urlparse(candidate_url).hostname or "").lower()
    if candidate_host == "kakaku.com" or candidate_host.endswith(".kakaku.com"):
        return None
    try:
        html, final_url, _headers = fetch(candidate_url, timeout=11)
        if not allowed_url(final_url, domains):
            return None
        final_host = (urlparse(final_url).hostname or "").lower()
        if final_host == "kakaku.com" or final_host.endswith(".kakaku.com"):
            return None
        raw = parse_page(final_url, html, expected=part)
        anchor = component_search_identity_anchor({
            "title": raw.get("name") or "",
            "snippet": raw.get("page_text_excerpt") or "",
        }, part)
        if not anchor:
            return None
        price = raw.get("price_jpy")
        minimum = int(part.get("min_price_jpy") or 1)
        maximum = int(part.get("max_price_jpy") or 10**9)
        if isinstance(price, bool) or not isinstance(price, int) or not minimum <= price <= maximum:
            return None
        source_mode = raw.get("price_source_mode")
        if source_mode not in ("direct_structured", "direct_meta", "direct_text"):
            return None
        retrieved = iso(now_jst())
        return {
            "url": final_url,
            "title": raw.get("name") or part.get("name"),
            "price_jpy": price,
            "price_source_mode": source_mode,
            "stock_status": raw.get("stock_status") or "unknown",
            "identity_anchor": anchor,
            "identity_match": True,
            "source_role": "direct_retailer_listing_reference",
            "available_at": retrieved,
            "retrieval_time": retrieved,
            "pit_valid": True,
            "bf_actual_authorized": False,
        }
    except Exception:
        return None


def search_comparison_snippet(part, domains):
    """Search approved sites, verify seller-page offers directly, and keep snippets display-only.

    Result URLs are untrusted until their host is allowlisted. Seller prices are
    accepted only after re-fetching the listing and validating identity, a
    plausible directly parsed price, and an in-stock signal.
    """
    queries = build_component_search_queries(part)
    diagnostics = []
    all_snippet_candidates = []
    verified_offers = []
    direct_fetch_attempts = 0
    for provider, search_fn in (("duckduckgo", ddg_search), ("bing", bing_search)):
        for query_index, query in enumerate(queries, 1):
            try:
                results = search_fn(query, timeout=9) or []
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
                # lightweight and does not hammer retailer sites.
                if not is_comparison_site and direct_fetch_attempts < 2:
                    direct_fetch_attempts += 1
                    offer = verify_retailer_listing(part, url, domains)
                    if offer and offer.get("url") not in {x.get("url") for x in verified_offers}:
                        verified_offers.append(offer)

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
