import json
import os

from intelligence import (
    ROOT, load_json, save_json, load_catalog, enrich_identity,
    validate_price
)

def main():
    path = os.path.join(ROOT, "data", "current_latest.json")
    state = load_json(path, {"products": []})
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
    state.setdefault("sanitizer", {})
    state["sanitizer"] = stats
    save_json(path, state)
    print(json.dumps(stats, ensure_ascii=False))

if __name__ == "__main__":
    main()
