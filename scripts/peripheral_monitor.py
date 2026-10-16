#!/usr/bin/env python3
"""Observe exact peripheral product pages independently from PC ranking candidates."""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlparse
from intelligence import ROOT, iso, now_jst, load_json, save_json, norm_text, store_observation_validation
from monitor import fetch, parse_page, stock_from_text

TARGETS_PATH = os.path.join(ROOT, "config", "targets.json")
OUTPUT_PATH = os.path.join(ROOT, "data", "peripheral_prices.json")
EVENTS_PATH = os.path.join(ROOT, "data", "peripheral_change_events.jsonl")


def allowed_host(url, hosts):
    host = urlparse(url).netloc.lower()
    return any(host == str(h).lower() for h in hosts or [])


class VisibleTextParser(HTMLParser):
    """Extract visible text only; ignore script/style bodies."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript"):
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript") and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data and data.strip():
            self.parts.append(data.strip())


def normalized_visible_text(html):
    parser = VisibleTextParser()
    parser.feed(str(html or ""))
    parser.close()
    text = unicodedata.normalize("NFKC", " ".join(parser.parts)).lower()
    return re.sub(r"\s+", " ", text).strip()


def _compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text or "")).lower())


def _branch_stock_status(text):
    """Interpret explicit branch stock wording; never infer out-of-stock from absence."""
    compact = _compact(text)
    if any(token in compact for token in ("在庫切れ", "在庫なし", "在庫ございません")):
        return "out_of_stock"
    if "在庫残少" in compact or "残りわずか" in compact:
        return "low_stock"
    if "在庫あり" in compact:
        return "in_stock"
    if "お取り寄せ" in compact or "取り寄せ" in compact:
        return "preorder_or_backorder"
    return "unknown"


def observe_store_inventory(target, retrieved_at):
    """Check product-specific official branch pickup/stock pages separately from store price.

    A positive branch result means the page reports reservation/pickup stock for the
    named branch. It does not prove the cash register price, shelf stock, or that the
    item can still be reserved after this observation.
    """
    if not (
        target.get("purchase_channel") == "physical_store"
        and target.get("store_inventory_required_before_purchase")
    ):
        return {
            "store_inventory_observations": [],
            "store_inventory_status": "unknown",
            "store_inventory_verified": False,
            "store_inventory_checked_at": None,
            "store_inventory_source_url": None,
            "store_inventory_store_ids_available": [],
        }

    checks = target.get("store_inventory_checks") or []
    candidate_ids = {str(x) for x in (target.get("physical_store_candidate_ids") or [])}
    identity_terms = [str(x) for x in (target.get("identity_terms") or []) if str(x).strip()]
    observations = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        store_id = str(check.get("store_id") or "")
        url = str(check.get("url") or "")
        store_name = str(check.get("store_name") or store_id)
        allowed_hosts = [str(x) for x in (check.get("allowed_hosts") or [])]
        branch_terms = [str(x) for x in (check.get("branch_match_terms") or []) if str(x).strip()]
        record = {
            "store_id": store_id,
            "store_name": store_name,
            "checked_at": retrieved_at,
            "check_url": url,
            "source_url": None,
            "source_type": check.get("source_type") or "official_branch_stock_page",
            "status": "unknown",
            "verified": False,
            "branch_match": False,
            "model_match": False,
            "evidence_notes": "オンライン取り置き/店舗在庫ページの観測。店頭現金価格・棚在庫の保証ではない。",
            "error": None,
        }
        if (
            store_id not in candidate_ids
            or not url.startswith("https://")
            or not allowed_host(url, allowed_hosts)
            or not branch_terms
            or not identity_terms
        ):
            record["error"] = "store_inventory_configuration_invalid"
            observations.append(record)
            continue
        try:
            html, final_url, _headers = fetch(url, timeout=10)
            if not allowed_host(final_url, allowed_hosts):
                raise ValueError("store_inventory_redirected_to_unapproved_host")
            text = normalized_visible_text(html)
            compact = _compact(text)
            matched_branch_term = next(
                (term for term in branch_terms if _compact(term) in compact),
                None,
            )
            record["branch_match"] = bool(matched_branch_term)
            record["model_match"] = any(_compact(term) in compact for term in identity_terms)
            record["source_url"] = final_url
            if not record["branch_match"]:
                record["error"] = "configured_branch_not_found_on_product_stock_page"
            elif not record["model_match"]:
                record["error"] = "exact_product_identity_not_found_on_stock_page"
            else:
                pos = compact.find(_compact(matched_branch_term))
                local_context = compact[pos:pos + 260]
                record["status"] = _branch_stock_status(local_context)
                # A verified page with "unknown" status stays an observed page,
                # but is never treated as available or unavailable.
                record["verified"] = True
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}:{str(exc)[:180]}"
        observations.append(record)

    verified = [x for x in observations if x.get("verified")]
    order = {"in_stock": 0, "low_stock": 1, "preorder_or_backorder": 2, "unknown": 3, "out_of_stock": 4}
    verified.sort(key=lambda x: order.get(x.get("status"), 3))
    usable = [x for x in verified if x.get("status") in ("in_stock", "low_stock", "preorder_or_backorder")]
    chosen = usable[0] if usable else (verified[0] if verified else None)
    available_ids = sorted({
        str(x["store_id"]) for x in verified
        if x.get("status") in ("in_stock", "low_stock")
    })
    return {
        "store_inventory_observations": observations,
        "store_inventory_status": chosen.get("status", "unknown") if chosen else "unknown",
        "store_inventory_verified": bool(chosen and chosen.get("verified") and chosen.get("status") != "unknown"),
        "store_inventory_checked_at": chosen.get("checked_at") if chosen else None,
        "store_inventory_source_url": chosen.get("source_url") if chosen else None,
        "store_inventory_store_id": chosen.get("store_id") if chosen else None,
        "store_inventory_store_name": chosen.get("store_name") if chosen else None,
        "store_inventory_evidence_notes": chosen.get("evidence_notes") if chosen else None,
        "store_inventory_store_ids_available": available_ids,
    }


def product_context_excerpt(excerpt, terms, before=80, after=450):
    """Return a bounded text window around the first exact product/model anchor."""
    text = norm_text(excerpt)
    hits = []
    for raw in terms or []:
        term = norm_text(raw)
        if not term:
            continue
        pos = text.find(term)
        if pos >= 0:
            hits.append((pos, -len(term), term))
    if not hits:
        return ""
    pos, _neg_len, _term = min(hits)
    return text[max(0, pos - before):pos + after]


def local_price_candidate(context):
    """Extract explicit JPY-denominated values from a short exact-model window.

    Unlike the general PC parser, this permits sub-50,000-yen prices for monitors,
    mice and mousepads. A points balance alone is not accepted as a price because it
    is not preceded by a yen symbol or followed by the yen unit.
    """
    text = re.sub(r"\s+", " ", str(context or ""))
    matches = []
    patterns = (
        re.compile(r"(?:¥|￥)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})(?:\s*円)?"),
        re.compile(r"(?<![0-9,])([0-9]{4,7})\s*円"),
    )
    for pattern in patterns:
        for match in pattern.finditer(text):
            raw = match.group(1)
            try:
                value = int(raw.replace(",", ""))
            except (TypeError, ValueError):
                continue
            snippet = text[max(0, match.start()-80):min(len(text), match.end()+80)]
            matches.append((match.start(), value, snippet))
    if not matches:
        return None
    # If multiple distinct explicit prices occur in the exact-model window, fail closed.
    distinct = {value for _pos, value, _snippet in matches}
    if len(distinct) != 1:
        return None
    _pos, value, snippet = min(matches, key=lambda x: x[0])
    return {"price_jpy": value, "context": snippet}


def local_product_stock(context, parsed_stock="unknown"):
    """Prefer explicit availability beside the exact product title, not site-wide related items."""
    text = norm_text(context)
    if any(x in text for x in ("在庫切れ", "品切れ", "売り切れ", "out of stock", "sold out", "在庫なし")):
        return "out_of_stock"
    if any(x in text for x in ("在庫残少", "残りわずか", "残り僅か", "在庫僅少", "残り1", "low stock", "在庫残りわずか")):
        return "low_stock"
    if any(x in text for x in ("在庫あり", "在庫有り", "in stock")):
        return "in_stock"
    if parsed_stock in ("in_stock", "low_stock", "out_of_stock"):
        return parsed_stock
    if any(x in text for x in ("取り寄せ", "お取り寄せ", "予約", "preorder", "back order")):
        return "preorder_or_backorder"
    if any(x in text for x in ("カートに追加", "カートに入れる", "ショッピングカート", "add to cart")):
        return "in_stock"
    return parsed_stock if parsed_stock in ("preorder_or_backorder", "unknown") else "unknown"


def previous_matches_target(previous, target):
    """Only reuse last-valid price history when it belongs to this exact tracked product."""
    if not previous:
        return False

    if norm_text(previous.get("name")) != norm_text(target.get("name")):
        return False

    def url_identity(value):
        if not value:
            return None
        parsed = urlparse(str(value))
        # Ignore query-string differences, but retain retailer and product path.
        return (parsed.netloc.lower(), (parsed.path or "/").rstrip("/") or "/")

    old_url = url_identity(previous.get("monitor_url"))
    new_url = url_identity(target.get("monitor_url"))
    if not old_url or old_url != new_url:
        return False

    old_model = norm_text(previous.get("model_code"))
    new_model = norm_text(target.get("model_code"))
    if old_model != new_model:
        return False

    old_terms = sorted({norm_text(x) for x in (previous.get("identity_terms") or []) if norm_text(x)})
    new_terms = sorted({norm_text(x) for x in (target.get("identity_terms") or []) if norm_text(x)})
    if old_terms and new_terms and old_terms != new_terms:
        return False

    return True


def run_one(target, previous, retrieved_at):
    primary_url = target.get("monitor_url")
    configured_urls = target.get("monitor_urls") or ([primary_url] if primary_url else [])
    row = {
        "id": target["id"], "name": target.get("name"),
        "purchase_channel": target.get("purchase_channel", "online"),
        "store_inventory_required_before_purchase": bool(target.get("store_inventory_required_before_purchase", False)),
        "online_price_is_comparison_only": bool(target.get("online_price_is_comparison_only", False)),
        "physical_store_candidate_ids": target.get("physical_store_candidate_ids") or [],
        "identity_terms": target.get("identity_terms") or [], "model_code": target.get("model_code"),
        "target_price_jpy": int(target.get("target_price_jpy") or 0),
        "monitor_url": primary_url,
        "purchase_url": target.get("purchase_url") or primary_url,
        "retrieval_time": retrieved_at, "available_at": None,
        "current_price_jpy": None,
        "online_comparison_price_jpy": None,
        "online_reference_price_verified": False,
        **store_observation_validation(target, retrieved_at),
        **observe_store_inventory(target, retrieved_at),
        "last_valid_price_jpy": (previous.get("current_price_jpy") or previous.get("last_valid_price_jpy")) if previous_matches_target(previous, target) else None,
        "price_verified": False, "stock_status": "unknown",
        "price_source_mode": "none", "price_validation_status": "missing",
        "identity_verified": False, "status": "error", "error": None,
        "retrieval_attempts": [],
    }
    allowed_hosts = target.get("allowed_hosts") or []
    urls = []
    for candidate_url in configured_urls:
        if candidate_url and allowed_host(candidate_url, allowed_hosts) and candidate_url not in urls:
            urls.append(candidate_url)
        else:
            row["retrieval_attempts"].append({
                "url": candidate_url, "status": "configuration_error",
                "error": "missing_or_disallowed_product_url",
            })
    if not urls:
        row["status"], row["error"] = "configuration_error", "missing_or_disallowed_product_url"
        return row

    terms = [norm_text(x) for x in target.get("identity_terms", []) if norm_text(x)]
    last_candidate_state = None
    for attempt_index, candidate_url in enumerate(urls):
        try:
            html, final_url, _headers = fetch(candidate_url, timeout=18)
            if not allowed_host(final_url, allowed_hosts):
                raise ValueError("redirected_to_unapproved_host")
            expected = {
                "name": target.get("name") or "",
                "aliases": target.get("identity_terms") or [],
                "model_code": target.get("model_code") or "",
                "url_is_exact": True,
                "identity_confidence": "high",
            }
            parsed = parse_page(final_url, html, expected=expected)
            full_excerpt = parsed.get("page_text_excerpt") or ""
            excerpt = norm_text(full_excerpt)
            context = product_context_excerpt(full_excerpt, terms)
            identity_verified = bool(terms and any(term in excerpt for term in terms))
            last_candidate_state = {
                "product_context_excerpt": context[:1400],
                "stock_status": local_product_stock(context, parsed.get("stock_status") or "unknown"),
                "identity_verified": identity_verified,
                "page_title": parsed.get("name"),
            }
            if not identity_verified:
                row["retrieval_attempts"].append({
                    "url": candidate_url, "final_url": final_url,
                    "status": "identity_unverified", "error": "exact_model_term_not_found",
                })
                continue

            price_source = parsed.get("price_source_mode") or "none"
            price_context = parsed.get("price_context")
            try:
                price = int(parsed.get("price_jpy")) if parsed.get("price_jpy") is not None else None
            except (TypeError, ValueError):
                price = None

            # Whole-page text/meta prices can be from recommendations. Only
            # structured exact-model offers or text beside the exact model title
            # are considered here.
            if price_source != "direct_structured":
                contextual_price = local_price_candidate(context) if context else None
                if contextual_price:
                    price = contextual_price["price_jpy"]
                    price_source = "direct_text"
                    price_context = contextual_price["context"]
                else:
                    price = None
                    price_source = "none"
                    price_context = None

            lower = int(target.get("min_price_jpy") or 1)
            upper = int(target.get("max_price_jpy") or 1000000)
            if price is None or price < lower or price > upper:
                row["retrieval_attempts"].append({
                    "url": candidate_url, "final_url": final_url,
                    "status": "price_unverified",
                    "error": "missing_or_implausible_price",
                    "price_candidate_jpy": price,
                })
                last_candidate_state.update({
                    "unverified_price_candidate_jpy": price,
                    "price_source_mode": price_source,
                    "price_context": price_context,
                })
                continue

            stock = local_product_stock(context, parsed.get("stock_status") or "unknown")
            row.update({
                "current_price_jpy": price,
                "online_comparison_price_jpy": price,
                "online_reference_price_verified": True,
                "last_valid_price_jpy": price,
                "price_verified": True,
                "stock_status": stock,
                "price_source_mode": price_source,
                "price_validation_status": "validated_exact_model_page",
                "identity_verified": True,
                "available_at": retrieved_at,
                "status": "verified" if stock in ("in_stock", "low_stock") else "price_verified_stock_unknown",
                "target_met": price <= int(target.get("target_price_jpy") or 0),
                "page_title": parsed.get("name"),
                "price_context": price_context,
                "coupon_note": target.get("coupon_policy"),
                "monitor_url_used": candidate_url,
                "source_url": final_url,
                "purchase_url": final_url,
                "fallback_url_used": attempt_index > 0,
            })
            row["retrieval_attempts"].append({
                "url": candidate_url, "final_url": final_url, "status": "verified",
            })
            return row
        except Exception as exc:
            row["retrieval_attempts"].append({
                "url": candidate_url,
                "status": "error",
                "error": f"{type(exc).__name__}:{str(exc)[:180]}",
            })

    if last_candidate_state:
        row.update(last_candidate_state)
    statuses = {x.get("status") for x in row["retrieval_attempts"]}
    if "identity_unverified" in statuses:
        row["status"] = "identity_unverified"
    elif "price_unverified" in statuses:
        row["status"] = "price_unverified"
    else:
        row["status"] = "error"
    row["error"] = "; ".join(
        f"{x.get('url')}: {x.get('error')}"
        for x in row["retrieval_attempts"] if x.get("error")
    )[:700] or "all_configured_urls_failed"
    return row



def _target_only_row(target, previous, observed_at):
    old = previous if isinstance(previous, dict) else {}
    return {
        "id": target["id"], "name": target.get("name"),
        "target_price_jpy": int(target.get("target_price_jpy") or 0),
        "purchase_channel": target.get("purchase_channel", "online"),
        "store_inventory_required_before_purchase": bool(target.get("store_inventory_required_before_purchase", False)),
        "online_price_is_comparison_only": bool(target.get("online_price_is_comparison_only", False)),
        "physical_store_candidate_ids": target.get("physical_store_candidate_ids") or [],
        "current_price_jpy": None,
        "last_valid_price_jpy": old.get("last_valid_price_jpy"),
        "online_comparison_price_jpy": None,
        "online_reference_price_verified": False,
        **store_observation_validation(target, observed_at),
        "price_verified": False, "stock_status": "unknown", "status": "target_only",
        "monitor_url": None, "purchase_url": target.get("purchase_url"),
        "retrieval_time": observed_at, "available_at": None, "price_source_mode": "none",
    }


def observe_targets(targets, previous_by_id, observed_at, max_workers=3):
    """Observe targets with bounded concurrency while preserving config-order output.

    Three workers reduce serial timeout cost without creating an unbounded burst
    against retail sites. The returned list always follows the input target order.
    """
    indexed = list(enumerate(targets))
    if not indexed:
        return []
    try:
        worker_limit = max(1, min(int(max_workers), 3, len(indexed)))
    except (TypeError, ValueError):
        worker_limit = min(3, len(indexed))

    def observe(index_target):
        index, target = index_target
        target_id = str(target.get("id") or "")
        previous = previous_by_id.get(target_id, {})
        if not target.get("track_current_price"):
            row = _target_only_row(target, previous, observed_at)
        else:
            row = run_one(target, previous, observed_at)
        return index, row

    results = [None] * len(indexed)
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        futures = [executor.submit(observe, pair) for pair in indexed]
        for future in as_completed(futures):
            index, row = future.result()
            results[index] = row
    if any(row is None for row in results):
        raise RuntimeError("peripheral_observation_result_missing")
    return results


def main():
    cfg = load_json(TARGETS_PATH, {})
    primary_targets = [p for p in (cfg.get("peripherals") or []) if isinstance(p, dict)]
    # Ranked alternatives are price-monitored separately. They never enter mandatory
    # budget arithmetic unless the user explicitly promotes one into peripherals.
    alternative_targets = [
        p for p in (cfg.get("peripheral_alternatives") or [])
        if isinstance(p, dict) and p.get("track_current_price")
    ]
    primary_ids = {str(p.get("id")) for p in primary_targets}
    duplicate_alternative_ids = primary_ids.intersection(str(p.get("id")) for p in alternative_targets)
    if duplicate_alternative_ids:
        raise ValueError(f"peripheral alternative IDs overlap primary targets: {sorted(duplicate_alternative_ids)}")
    targets = primary_targets + alternative_targets
    previous = load_json(OUTPUT_PATH, {"products": []})
    previous_by_id = {str(x.get("id")): x for x in (previous.get("products") or []) if x.get("id")}
    observed_at = iso(now_jst())
    # Keep target-only items cheap, but fetch tracked products concurrently with a
    # small worker cap. This prevents 20+ independent 18-second timeouts from
    # serially consuming the entire workflow window. Results are reassembled in
    # configuration order so report/event output stays deterministic.
    rows = observe_targets(targets, previous_by_id, observed_at, max_workers=3)
    old = {str(x.get("id")): x for x in (previous.get("products") or []) if x.get("id")}
    events = []
    for item in rows:
        before = old.get(str(item.get("id")), {})
        old_price, new_price = before.get("current_price_jpy"), item.get("current_price_jpy")
        old_stock, new_stock = before.get("stock_status"), item.get("stock_status")
        old_store_signature = (
            before.get("store_price_jpy"), before.get("store_stock_status"),
            before.get("store_observation_status"), before.get("store_observation_store_id"),
            before.get("store_inventory_status"), before.get("store_inventory_store_id"),
        )
        new_store_signature = (
            item.get("store_price_jpy"), item.get("store_stock_status"),
            item.get("store_observation_status"), item.get("store_observation_store_id"),
            item.get("store_inventory_status"), item.get("store_inventory_store_id"),
        )
        if old_price == new_price and old_stock == new_stock and old_store_signature == new_store_signature:
            continue
        if new_price is None and new_stock in (None, "unknown") and not before:
            continue
        events.append({
            "id": item.get("id"), "observed_at": observed_at,
            "event_time": None, "event_time_upper_bound": observed_at,
            "publication_time": None, "available_at": item.get("available_at"),
            "retrieval_time": observed_at, "prediction_time": observed_at,
            "pit_valid": bool(item.get("available_at") and item.get("available_at") <= observed_at),
            "url": item.get("source_url") or item.get("monitor_url"), "old_price_jpy": old_price, "new_price_jpy": new_price,
            "old_stock_status": old_stock, "new_stock_status": new_stock,
            "old_store_price_jpy": before.get("store_price_jpy"),
            "new_store_price_jpy": item.get("store_price_jpy"),
            "old_store_stock_status": before.get("store_stock_status"),
            "new_store_stock_status": item.get("store_stock_status"),
            "store_observation_status": item.get("store_observation_status"),
            "store_observation_store_id": item.get("store_observation_store_id"),
            "store_inventory_status": item.get("store_inventory_status"),
            "store_inventory_store_id": item.get("store_inventory_store_id"),
            "store_inventory_source_url": item.get("store_inventory_source_url"),
            "store_inventory_verified": item.get("store_inventory_verified"),
            "price_source_mode": item.get("price_source_mode"),
            "price_verified": item.get("price_verified", False), "status": item.get("status"),
        })
    out = {
        "schema_version": 1, "generated_at": observed_at,
        "budget_scope": "Primary peripheral targets affect the mandatory budget. Ranked alternatives are observed but do not affect budget projections unless selected.",
        "primary_target_count": len(primary_targets),
        "alternative_target_count": len(alternative_targets),
        "tracked_count": sum(1 for x in targets if x.get("track_current_price")),
        "verified_count": sum(1 for x in rows if x.get("price_verified")), "products": rows,
    }
    save_json(OUTPUT_PATH, out)
    if events:
        os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)
        with open(EVENTS_PATH, "a", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({
        "generated_at": observed_at, "tracked_count": out["tracked_count"],
        "verified_count": out["verified_count"], "price_changes": len(events),
        "statuses": {str(x["id"]): x["status"] for x in rows},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
