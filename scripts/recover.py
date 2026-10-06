import json
import os

from intelligence import ROOT, load_json, load_catalog, validate_price, enrich_identity, iso, now_jst
from monitor import search_fallback

def main():
    path = os.path.join(ROOT, "data", "current_latest.json")
    state = load_json(path, {"products": []})
    catalog = load_catalog()
    repaired = 0
    rejected = 0
    fallback_used = 0
    fallback_attempts = 0
    max_fallback_attempts = 8

    for raw in state.get("products", []):
        cid = str(raw.get("id") or "")
        cat = catalog.get(cid, {})
        item = enrich_identity(raw, cat)

        needs_fallback = (
            item.get("current_price_jpy") is None and
            item.get("query") and
            item.get("price_source_mode") not in ("public_baseline", "stale_previous")
        )
        if needs_fallback and fallback_attempts < max_fallback_attempts:
            fallback_attempts += 1
            fb = search_fallback(item.get("query"), item.get("url"))
            if fb:
                reference = item.get("last_valid_price_jpy")
                if reference is None:
                    reference = cat.get("reference_price_jpy", cat.get("price_jpy"))
                checked = validate_price(fb["price_jpy"], item, reference_price=reference, corroborated=False)
                if checked["valid"]:
                    item.update({
                        "name": fb.get("title") or item.get("name"),
                        "stock_status": item.get("stock_status") if item.get("stock_status") != "unknown" else fb.get("stock_status","unknown"),
                        "parsed_spec": {**item.get("parsed_spec", {}), **fb.get("spec", {})},
                        "price_jpy": int(fb["price_jpy"]),
                        "current_price_jpy": int(fb["price_jpy"]),
                        "last_valid_price_jpy": int(fb["price_jpy"]),
                        "available_at": item.get("retrieval_time") or iso(now_jst()),
                        "price_source_mode": "search_snippet",
                        "price_validation_status": checked["status"],
                        "price_validation_reason": checked["reason"],
                        "data_confidence": "medium",
                        "corroborating_source_url": fb.get("url"),
                        "corroborating_source_title": fb.get("title"),
                        "corroborating_source_snippet": fb.get("snippet"),
                    })
                    item = enrich_identity(item, cat)
                    fallback_used += 1

        current = item.get("current_price_jpy")
        if current is not None:
            reference = item.get("last_valid_price_jpy")
            if reference is None:
                reference = cat.get("reference_price_jpy", cat.get("price_jpy"))
            checked = validate_price(current, item, reference_price=reference, corroborated=item.get("price_validation_status") == "anomaly_corroborated")
            if not checked["valid"]:
                item["last_valid_price_jpy"] = reference
                item["reference_price_jpy"] = reference
                item["current_price_jpy"] = None
                item["price_jpy"] = None
                item["price_validation_status"] = checked["status"]
                item["price_validation_reason"] = checked["reason"]
                item["data_confidence"] = "low"
                rejected += 1
            else:
                item["price_validation_status"] = checked["status"]
                item["price_validation_reason"] = checked["reason"]
                item["price_jpy"] = int(current)
                repaired += 1

        raw.clear()
        raw.update(item)

    state["products"] = state.get("products", [])
    state.setdefault("recovery", {})
    state["recovery"] = {
        "fallback_used": fallback_used,
        "repaired": repaired,
        "rejected": rejected,
        "fallback_attempts": fallback_attempts,
        "fallback_limit": max_fallback_attempts,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(json.dumps(state["recovery"], ensure_ascii=False))

if __name__ == "__main__":
    main()
