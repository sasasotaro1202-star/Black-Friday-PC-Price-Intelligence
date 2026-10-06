import json
import os

from intelligence import ROOT, load_json, parse_dt


def main():
    errors = []

    # Catalog integrity
    catalog = load_json(os.path.join(ROOT, "config", "candidate_catalog.json"), {})
    catalog_items = catalog.get("candidates", [])
    catalog_ids = [str(x.get("id") or "") for x in catalog_items if isinstance(x, dict)]
    if len(catalog_ids) != len(catalog_items):
        errors.append("catalog contains missing id")
    if len(catalog_ids) != len(set(catalog_ids)):
        errors.append("catalog duplicate id")

    # Watchlist integrity
    watch = load_json(os.path.join(ROOT, "data", "watchlist.json"), {})
    watch_items = watch.get("urls", [])
    if not isinstance(watch_items, list):
        errors.append("watchlist.urls is not a list")
        watch_items = []
    watch_ids = []
    watch_urls = []
    for i, entry in enumerate(watch_items):
        if not isinstance(entry, dict):
            errors.append(f"watchlist entry {i} is not an object")
            continue
        cid = str(entry.get("id") or "")
        url = str(entry.get("url") or "")
        if not cid:
            errors.append(f"watchlist entry {i} missing id")
        if not url.startswith(("http://", "https://")):
            errors.append(f"watchlist entry {i} invalid url")
        if cid:
            watch_ids.append(cid)
        if url:
            watch_urls.append(url)
    if len(watch_ids) != len(set(watch_ids)):
        errors.append("watchlist duplicate id")
    if len(watch_urls) != len(set(watch_urls)):
        errors.append("watchlist duplicate url")

    # Latest observation integrity
    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {})
    products = latest.get("products", [])
    if not isinstance(products, list):
        errors.append("latest.products is not a list")
        products = []

    fetch_stats = latest.get("fetch_stats") or {}
    if fetch_stats:
        keys = ("total", "direct_verified", "search_corrob", "stale_previous", "baseline_only", "anomaly_rejected", "errors")
        if any(not isinstance(fetch_stats.get(k), int) or fetch_stats.get(k) < 0 for k in keys):
            errors.append("fetch_stats contains invalid counters")
        elif fetch_stats.get("total") != len(products):
            errors.append("fetch_stats.total != latest product count")

    latest_ids = []
    for p in products:
        if not isinstance(p, dict):
            errors.append("latest contains non-object product")
            continue

        cid = str(p.get("id") or "")
        if not cid:
            errors.append("latest product missing id")
        elif cid in latest_ids:
            errors.append(f"latest duplicate id: {cid}")
        else:
            latest_ids.append(cid)

        current = p.get("current_price_jpy")
        price = p.get("price_jpy")
        status = p.get("price_validation_status")

        if current is None and price is not None:
            errors.append(f"price_jpy exposed without current price: {cid}")
        if current is not None and price != current:
            errors.append(f"price_jpy/current_price_jpy mismatch: {cid}")

        if status in ("validated", "anomaly_corroborated") and current is None:
            errors.append(f"validated status without current price: {cid}")
        if status in ("reference_only", "variant_ambiguous", "anomaly_rejected") and current is not None:
            errors.append(f"non-actionable status exposes current price: {cid}")

        if current is not None:
            if status in (None, "missing", "reference_only", "variant_ambiguous", "anomaly_rejected"):
                errors.append(f"current price has non-actionable validation status: {cid}")
            try:
                if int(current) <= 0:
                    errors.append(f"non-positive current price: {cid}")
            except Exception:
                errors.append(f"current price is not numeric: {cid}")

            av = parse_dt(p.get("available_at"))
            rt = parse_dt(p.get("retrieval_time"))
            if av is None or rt is None:
                errors.append(f"current price lacks observation timestamps: {cid}")
            elif av > rt:
                errors.append(f"available_at after retrieval_time: {cid}")

    # Event-log integrity
    event_path = os.path.join(ROOT, "data", "change_events.jsonl")
    event_count = 0
    if os.path.exists(event_path):
        seen_events = set()
        with open(event_path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                event_count += 1
                try:
                    e = json.loads(line)
                except Exception:
                    errors.append(f"malformed change_events line {n}")
                    continue

                key = (
                    str(e.get("id") or ""),
                    str(e.get("observed_at") or ""),
                    e.get("old_price_jpy"),
                    e.get("new_price_jpy"),
                    e.get("old_stock_status"),
                    e.get("new_stock_status"),
                )
                if key in seen_events:
                    errors.append(f"duplicate change event line {n}")
                seen_events.add(key)

                if e.get("new_price_jpy") is not None:
                    av = parse_dt(e.get("available_at"))
                    rt = parse_dt(e.get("retrieval_time"))
                    pr = parse_dt(e.get("prediction_time"))
                    if av is None or rt is None or pr is None or av > rt or rt > pr:
                        errors.append(f"invalid PIT in change event line {n}")

    # Ranking integrity
    rankings = load_json(os.path.join(ROOT, "data", "decision_rankings.json"), {})
    ranked = rankings.get("products", [])
    unavailable = rankings.get("unavailable_products", [])
    reference_only = rankings.get("reference_only", [])
    if not isinstance(ranked, list):
        errors.append("rankings.products is not a list")
        ranked = []
    if not isinstance(unavailable, list):
        errors.append("rankings.unavailable_products is not a list")
        unavailable = []
    if not isinstance(reference_only, list):
        errors.append("rankings.reference_only is not a list")
        reference_only = []

    all_ranked_ids = [
        str(x.get("id") or "") for x in (ranked + unavailable + reference_only)
        if isinstance(x, dict) and x.get("id")
    ]
    if len(all_ranked_ids) != len(set(all_ranked_ids)):
        errors.append("ranking/reference/unavailable ids are not unique")

    ranks = [x.get("rank") for x in ranked if isinstance(x, dict)]
    if len(ranks) != len(set(ranks)) or (ranks and sorted(ranks) != list(range(1, len(ranks) + 1))):
        errors.append("ranking ranks are not contiguous and unique")

    expected_order = sorted(
        ranked,
        key=lambda x: (
            -(x.get("decision_score") if x.get("decision_score") is not None else -1),
            x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
            str(x.get("id") or ""),
        ),
    )
    if [str(x.get("id") or "") for x in ranked] != [str(x.get("id") or "") for x in expected_order]:
        errors.append("ranking order is not deterministic score-desc/price-asc/id-asc")

    top = rankings.get("top_recommendation") or {}
    if ranked:
        if top.get("id") != ranked[0].get("id"):
            errors.append("top recommendation does not match rank 1")
    elif top.get("id") is not None:
        errors.append("top recommendation exists while ranking is empty")
    if top.get("status") == "UNAVAILABLE":
        errors.append("top recommendation is unavailable")

    # Quality counters must describe the actual output partition.
    quality = rankings.get("quality") or {}
    if quality:
        if quality.get("candidate_count") != len(ranked) + len(unavailable) + len(reference_only):
            errors.append("quality.candidate_count does not match ranking partitions")
        if quality.get("actionable_count") != len(ranked):
            errors.append("quality.actionable_count mismatch")
        if quality.get("reference_only_count") != len(reference_only):
            errors.append("quality.reference_only_count mismatch")
        if quality.get("out_of_stock") != sum(
            1 for x in ranked + unavailable + reference_only
            if x.get("stock_status") == "out_of_stock"
        ):
            errors.append("quality.out_of_stock mismatch")
        if quality.get("unknown_stock") != sum(
            1 for x in ranked + unavailable + reference_only
            if x.get("stock_status") == "unknown"
        ):
            errors.append("quality.unknown_stock mismatch")

    # Actionable row invariants.
    for r in ranked:
        rid = str(r.get("id") or "")
        score = r.get("decision_score")
        detail = r.get("score_detail") or {}
        if score is None:
            errors.append(f"actionable ranking has null score: {rid}")
            continue

        try:
            score_num = int(score)
            cap = int(detail.get("score_cap"))
        except Exception:
            errors.append(f"invalid score/cap: {rid}")
            continue

        if not 0 <= score_num <= 100:
            errors.append(f"score range violation: {rid}")
        if score_num > cap:
            errors.append(f"score cap violation: {rid}")

        components = sum(int(detail.get(k, 0) or 0) for k in ("performance", "price", "history", "stock", "timing"))
        expected_before_cap = min(100, components)
        if detail.get("score_before_cap") != expected_before_cap:
            errors.append(f"score_before_cap mismatch: {rid}")
        if score_num != min(expected_before_cap, cap):
            errors.append(f"decision_score arithmetic mismatch: {rid}")

        status = detail.get("status")
        source = r.get("price_source_mode")
        stock = r.get("stock_status")

        if stock == "out_of_stock":
            errors.append(f"out_of_stock leaked into actionable ranking: {rid}")
        if source in ("search_snippet", "public_baseline", "stale_previous", "direct_text") and status != "VERIFY_NOW":
            errors.append(f"verification-source status mismatch: {rid}")

        if status in ("BUY_NOW", "BUY_NOW_LOW_STOCK"):
            if source != "direct_structured":
                errors.append(f"buy-now source not direct_structured: {rid}")
            if r.get("current_price_jpy") is None or r.get("current_price_jpy") > 280000:
                errors.append(f"buy-now price invalid: {rid}")
            if r.get("variant_match") not in ("exact", "trusted_url", "strong"):
                errors.append(f"buy-now identity not verified: {rid}")
            if stock not in ("in_stock", "low_stock"):
                errors.append(f"buy-now stock not verified: {rid}")
            threshold = 90 if status == "BUY_NOW" else 85
            if score_num < threshold:
                errors.append(f"buy-now score below threshold: {rid}")

        av = parse_dt(r.get("available_at"))
        rt = parse_dt(r.get("retrieval_time"))
        pr = parse_dt(r.get("prediction_time"))
        if av is None or rt is None or pr is None or av > rt or rt > pr:
            errors.append(f"ranking PIT violation: {rid}")

    # The entire ranked state must be partitioned back to the catalog/live candidate set.
    if quality:
        dynamic = sum(1 for x in ranked + unavailable + reference_only if x.get("dynamic_candidate"))
        if quality.get("dynamic_candidate_count") != dynamic:
            errors.append("quality.dynamic_candidate_count mismatch")

    if errors:
        for e in errors:
            print(" -", e)
        raise SystemExit(1)

    print(json.dumps({
        "status": "PASS",
        "catalog": len(catalog_items),
        "watchlist": len(watch_items),
        "latest_products": len(products),
        "ranked_products": len(ranked),
        "unavailable_products": len(unavailable),
        "reference_only": len(reference_only),
        "events": event_count,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
