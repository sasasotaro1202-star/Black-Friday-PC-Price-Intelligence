import json
import os

from intelligence import (
    ROOT, load_json, save_json, load_catalog, enrich_identity,
    validate_price
)

def final_fetch_stats(final_products, monitor_stats=None):
    """Recompute final price counts after sanitization while preserving monitor diagnostics."""
    monitor_stats = monitor_stats or {}
    result = {
        "total": len(final_products),
        "direct_verified": sum(
            1 for x in final_products
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
        ),
        "search_corrob": sum(
            1 for x in final_products
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") == "search_snippet"
        ),
        "stale_previous": sum(1 for x in final_products if x.get("price_source_mode") == "stale_previous"),
        "baseline_only": sum(1 for x in final_products if x.get("price_source_mode") == "public_baseline"),
        "anomaly_rejected": sum(1 for x in final_products if x.get("price_validation_status") == "anomaly_rejected"),
        "errors": sum(1 for x in final_products if x.get("fetch_status") == "error"),
    }
    # Monitor-side diagnostics are independent observations and survive sanitization.
    for key in (
        "search_fallback_attempts", "search_fallback_successes", "search_fallback_failures",
        "search_identity_rejections", "errors_by_host_reason",
    ):
        if key in monitor_stats:
            result[key] = monitor_stats[key]
    return result


def main():
    path = os.path.join(ROOT, "data", "current_latest.json")
    state = load_json(path, {"products": []})
    monitor_fetch_stats = dict(state.get("fetch_stats") or {})
    catalog = load_catalog()

    stats = {
        "checked": 0,
        "accepted": 0,
        "rejected_anomaly": 0,
        "variant_ambiguous": 0,
        "repaired": 0,
    }

    repaired = []
    for raw in state.get("products", []):
        stats["checked"] += 1
        cid = str(raw.get("id") or "")
        cat = catalog.get(cid, {})
        item = enrich_identity(raw, cat)

        price = item.get("current_price_jpy")
        if price is None:
            price = item.get("price_jpy")

        reference = item.get("last_valid_price_jpy")
        if reference is None:
            reference = cat.get("reference_price_jpy", cat.get("price_jpy"))

        # Shared family pages are not sufficient evidence for a specific configuration.
        # Keep the observed number as a reference, but remove it from the actionable price field.
        if price is not None and not cat.get("url_is_exact") and item.get("price_source_mode") in (
            "direct_structured", "direct_page", "direct_text"
        ):
            item["variant_match"] = "ambiguous"
            item["variant_ambiguity_reason"] = "shared_family_page_without_exact_variant_identity"
            item["last_valid_price_jpy"] = price
            item["reference_price_jpy"] = reference
            item["current_price_jpy"] = None
            item["price_jpy"] = None
            item["price_validation_status"] = "variant_ambiguous"
            item["price_validation_reason"] = "current_price_not_tied_to_exact_configuration"
            item["price_source_mode"] = "public_baseline"
            item["data_confidence"] = "low"
            stats["variant_ambiguous"] += 1
            stats["repaired"] += 1
            repaired.append(item)
            continue

        if price is not None:
            result = validate_price(price, item, reference_price=reference, corroborated=False)
            if not result["valid"]:
                item["last_valid_price_jpy"] = reference
                item["reference_price_jpy"] = reference
                item["current_price_jpy"] = None
                item["price_jpy"] = None
                item["price_validation_status"] = result["status"]
                item["price_validation_reason"] = result["reason"]
                item["data_confidence"] = "low"
                stats["rejected_anomaly"] += 1
                stats["repaired"] += 1
            else:
                item["current_price_jpy"] = int(price)
                item["price_jpy"] = int(price)
                item["price_validation_status"] = result["status"]
                item["price_validation_reason"] = result["reason"]
                stats["accepted"] += 1

        repaired.append(item)

    state["products"] = repaired

    # Recompute fetch statistics from the final sanitized observation state.
    # Monitor-level counters can become stale when sanitize moves a price into
    # reference-only evidence, so the published snapshot must describe what is
    # actually present in current_latest.json.
    final = state["products"]
    # Normalize coverage against the final sanitized state as well. This prevents
    # a parser/sanitizer downgrade from leaving an obsolete verification rate.
    prior_coverage = state.get("coverage") or {}
    watchlist_count = int(prior_coverage.get("watchlist_count") or len(final))
    processed_count = len(final)
    skipped_count = max(0, watchlist_count - processed_count)
    transport_success_count = sum(1 for x in final if x.get("fetch_status") == "ok")
    price_verified_count = sum(1 for x in final if x.get("current_price_jpy") is not None)
    state["coverage"] = {
        "watchlist_count": watchlist_count,
        "processed_count": processed_count,
        "skipped_count": skipped_count,
        "max_urls": int(prior_coverage.get("max_urls") or watchlist_count or processed_count or 1),
        "processing_rate_pct": round(100.0 * processed_count / watchlist_count, 1) if watchlist_count else 100.0,
        "transport_success_rate_pct": round(100.0 * transport_success_count / processed_count, 1) if processed_count else 0.0,
        "price_verified_rate_pct": round(100.0 * price_verified_count / processed_count, 1) if processed_count else 0.0,
        "skipped_reason": prior_coverage.get("skipped_reason"),
        "skipped_ids": prior_coverage.get("skipped_ids") or [],
    }
    state["fetch_stats"] = final_fetch_stats(final, monitor_fetch_stats)

    state.setdefault("sanitizer", {})
    state["sanitizer"] = stats
    save_json(path, state)
    print(json.dumps(stats, ensure_ascii=False))

if __name__ == "__main__":
    main()
