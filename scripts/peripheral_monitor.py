#!/usr/bin/env python3
"""Observe exact peripheral product pages independently from PC ranking candidates."""
import json
import os
import re
from urllib.parse import urlparse
from intelligence import ROOT, iso, now_jst, load_json, save_json, norm_text
from monitor import fetch, parse_page, stock_from_text
from intelligence import pick_price

TARGETS_PATH = os.path.join(ROOT, "config", "targets.json")
OUTPUT_PATH = os.path.join(ROOT, "data", "peripheral_prices.json")
EVENTS_PATH = os.path.join(ROOT, "data", "peripheral_change_events.jsonl")


def allowed_host(url, hosts):
    host = urlparse(url).netloc.lower()
    return any(host == str(h).lower() for h in hosts or [])


def product_context_excerpt(excerpt, terms, before=300, after=1200):
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
    text = re.sub(r"\\s+", " ", str(context or ""))
    matches = []
    patterns = (
        re.compile(r"(?:¥|￥)\\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,7})(?:\\s*円)?"),
        re.compile(r"(?<![0-9,])([0-9]{4,7})\\s*円"),
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


def run_one(target, previous, retrieved_at):
    url = target.get("monitor_url")
    row = {
        "id": target["id"], "name": target.get("name"),
        "target_price_jpy": int(target.get("target_price_jpy") or 0),
        "monitor_url": url, "purchase_url": target.get("purchase_url") or url,
        "retrieval_time": retrieved_at, "available_at": None,
        "current_price_jpy": None,
        "last_valid_price_jpy": previous.get("current_price_jpy") or previous.get("last_valid_price_jpy"),
        "price_verified": False, "stock_status": "unknown",
        "price_source_mode": "none", "price_validation_status": "missing",
        "identity_verified": False, "status": "error", "error": None,
    }
    if not url or not allowed_host(url, target.get("allowed_hosts")):
        row["status"], row["error"] = "configuration_error", "missing_or_disallowed_product_url"
        return row
    try:
        html, final_url, _headers = fetch(url, timeout=18)
        if not allowed_host(final_url, target.get("allowed_hosts")):
            raise ValueError("redirected_to_unapproved_host")
        terms = [norm_text(x) for x in target.get("identity_terms", []) if norm_text(x)]
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
        row["product_context_excerpt"] = context[:1400]
        identity_verified = bool(terms and any(term in excerpt for term in terms))
        if not identity_verified:
            row["status"], row["error"] = "identity_unverified", "exact_model_term_not_found"
            row["stock_status"] = parsed.get("stock_status") or "unknown"
            return row
        price_source = parsed.get("price_source_mode") or "none"
        price_context = parsed.get("price_context")
        try:
            price = int(parsed.get("price_jpy")) if parsed.get("price_jpy") is not None else None
        except (TypeError, ValueError):
            price = None
        # If structured product offers are absent/ambiguous, fall back only to
        # price text in the exact product-title window, never the whole page.
        if price is None and context:
            contextual_price = local_price_candidate(context)
            if contextual_price:
                price = contextual_price["price_jpy"]
                price_source = "direct_text"
                price_context = contextual_price["context"]
        lower, upper = int(target.get("min_price_jpy") or 1), int(target.get("max_price_jpy") or 1000000)
        if price is None or price < lower or price > upper:
            row["unverified_price_candidate_jpy"] = price
            row["status"], row["error"] = "price_unverified", "missing_or_implausible_price"
            row["stock_status"] = local_product_stock(context, parsed.get("stock_status") or "unknown")
            row["identity_verified"] = True
            row["price_source_mode"] = price_source
            row["price_context"] = price_context
            return row
        stock = local_product_stock(context, parsed.get("stock_status") or "unknown")
        row.update({
            "current_price_jpy": price, "last_valid_price_jpy": price, "price_verified": True,
            "stock_status": stock, "price_source_mode": price_source,
            "price_validation_status": "validated_exact_model_page", "identity_verified": True,
            "available_at": retrieved_at,
            "status": "verified" if stock in ("in_stock", "low_stock") else "price_verified_stock_unknown",
            "target_met": price <= int(target.get("target_price_jpy") or 0),
            "page_title": parsed.get("name"), "price_context": price_context,
            "coupon_note": target.get("coupon_policy"),
        })
        return row
    except Exception as exc:
        row["status"], row["error"] = "error", type(exc).__name__
        return row


def main():
    cfg = load_json(TARGETS_PATH, {})
    targets = [p for p in (cfg.get("peripherals") or []) if isinstance(p, dict)]
    previous = load_json(OUTPUT_PATH, {"products": []})
    previous_by_id = {str(x.get("id")): x for x in (previous.get("products") or []) if x.get("id")}
    observed_at = iso(now_jst())
    rows = []
    for target in targets:
        if not target.get("track_current_price"):
            old = previous_by_id.get(target["id"], {})
            rows.append({
                "id": target["id"], "name": target.get("name"), "target_price_jpy": int(target.get("target_price_jpy") or 0),
                "current_price_jpy": None, "last_valid_price_jpy": old.get("last_valid_price_jpy"),
                "price_verified": False, "stock_status": "unknown", "status": "target_only",
                "monitor_url": None, "purchase_url": target.get("purchase_url"),
                "retrieval_time": observed_at, "available_at": None, "price_source_mode": "none",
            })
        else:
            rows.append(run_one(target, previous_by_id.get(target["id"], {}), observed_at))
    old = {str(x.get("id")): x for x in (previous.get("products") or []) if x.get("id")}
    events = []
    for item in rows:
        before = old.get(str(item.get("id")), {})
        old_price, new_price = before.get("current_price_jpy"), item.get("current_price_jpy")
        old_stock, new_stock = before.get("stock_status"), item.get("stock_status")
        if old_price == new_price and old_stock == new_stock:
            continue
        if new_price is None and new_stock in (None, "unknown") and not before:
            continue
        events.append({
            "id": item.get("id"), "observed_at": observed_at,
            "event_time": None, "event_time_upper_bound": observed_at,
            "publication_time": None, "available_at": item.get("available_at"),
            "retrieval_time": observed_at, "prediction_time": observed_at,
            "pit_valid": bool(item.get("available_at") and item.get("available_at") <= observed_at),
            "url": item.get("monitor_url"), "old_price_jpy": old_price, "new_price_jpy": new_price,
            "old_stock_status": old_stock, "new_stock_status": new_stock,
            "price_source_mode": item.get("price_source_mode"),
            "price_verified": item.get("price_verified", False), "status": item.get("status"),
        })
    out = {
        "schema_version": 1, "generated_at": observed_at,
        "budget_scope": "Peripherals are separate from PC rankings; uncertain coupons/points are not deducted.",
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
