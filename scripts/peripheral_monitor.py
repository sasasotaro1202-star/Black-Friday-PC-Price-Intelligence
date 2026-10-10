#!/usr/bin/env python3
"""Observe exact peripheral product pages independently from PC ranking candidates."""
import json
import os
from urllib.parse import urlparse
from intelligence import ROOT, iso, now_jst, load_json, save_json, norm_text
from monitor import fetch, parse_page

TARGETS_PATH = os.path.join(ROOT, "config", "targets.json")
OUTPUT_PATH = os.path.join(ROOT, "data", "peripheral_prices.json")
EVENTS_PATH = os.path.join(ROOT, "data", "peripheral_change_events.jsonl")


def allowed_host(url, hosts):
    host = urlparse(url).netloc.lower()
    return any(host == str(h).lower() for h in hosts or [])


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
        parsed = parse_page(final_url, html)
        excerpt = norm_text(parsed.get("page_text_excerpt") or "")
        terms = [norm_text(x) for x in target.get("identity_terms", []) if norm_text(x)]
        identity_verified = bool(terms and any(term in excerpt for term in terms))
        if not identity_verified:
            row["status"], row["error"] = "identity_unverified", "exact_model_term_not_found"
            row["stock_status"] = parsed.get("stock_status") or "unknown"
            return row
        try:
            price = int(parsed.get("price_jpy")) if parsed.get("price_jpy") is not None else None
        except (TypeError, ValueError):
            price = None
        lower, upper = int(target.get("min_price_jpy") or 1), int(target.get("max_price_jpy") or 1000000)
        if price is None or price < lower or price > upper:
            row["status"], row["error"] = "price_unverified", "missing_or_implausible_price"
            row["stock_status"], row["identity_verified"] = parsed.get("stock_status") or "unknown", True
            return row
        stock = parsed.get("stock_status") or "unknown"
        if stock == "unknown" and any(x in excerpt for x in ("カートに追加", "カートに入れる", "add to cart")):
            stock = "in_stock"
        row.update({
            "current_price_jpy": price, "last_valid_price_jpy": price, "price_verified": True,
            "stock_status": stock, "price_source_mode": parsed.get("price_source_mode") or "none",
            "price_validation_status": "validated_exact_model_page", "identity_verified": True,
            "available_at": retrieved_at,
            "status": "verified" if stock in ("in_stock", "low_stock") else "price_verified_stock_unknown",
            "target_met": price <= int(target.get("target_price_jpy") or 0),
            "page_title": parsed.get("name"), "price_context": parsed.get("price_context"),
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
