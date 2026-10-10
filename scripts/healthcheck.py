import hashlib
import json
import os

from intelligence import (
    ROOT, load_json, load_anchors, parse_dt, decision_score,
    effective_cost, EFFECTIVE_SOFT_MAX, EFFECTIVE_HARD_MAX,
    purchase_budget_policy, configuration_readiness, peripheral_budget_projection
)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_events():
    path = os.path.join(ROOT, "data", "change_events.jsonl")
    events = []
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    return events

def main():
    errors = []
    budget_policy = purchase_budget_policy()
    budget_projection = peripheral_budget_projection()
    if budget_policy["pc_budget_jpy"] + budget_policy["peripheral_budget_jpy"] != budget_policy["total_budget_jpy"]:
        errors.append("budget arithmetic mismatch")
    if sum(int(p.get("target_price_jpy") or 0) for p in budget_policy["peripherals"] if p.get("mandatory", True)) != budget_policy["peripheral_budget_jpy"]:
        errors.append("peripheral target budget mismatch")

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
    watch_priority = {}
    watch_url_ids = {}
    catalog_map = {str(x.get("id") or ""): x for x in catalog_items if isinstance(x, dict)}
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
            watch_priority[cid] = str(entry.get("priority") or "normal").lower()
        if url:
            watch_urls.append(url)
            watch_url_ids.setdefault(url, []).append(cid)
    if len(watch_ids) != len(set(watch_ids)):
        errors.append("watchlist duplicate id")
    for url, ids in watch_url_ids.items():
        if len(ids) > 1:
            # Duplicate URLs are valid only for explicitly shared family pages.
            if not all(not catalog_map.get(cid, {}).get("url_is_exact") for cid in ids):
                errors.append(f"watchlist duplicate url for non-shared page: {url}")

    # Latest observation integrity
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    latest = load_json(latest_path, {})
    products = latest.get("products", [])
    latest_generated = parse_dt(latest.get("generated_at"))
    if latest_generated is None:
        errors.append("latest.generated_at is missing or invalid")
    if not isinstance(products, list):
        errors.append("latest.products is not a list")
        products = []

    fetch_stats = latest.get("fetch_stats") or {}
    coverage = latest.get("coverage") or {}
    latest_ids = [
        str(p.get("id") or "") for p in products
        if isinstance(p, dict) and p.get("id")
    ]
    if coverage:
        required = ("watchlist_count", "processed_count", "skipped_count", "max_urls")
        if any(not isinstance(coverage.get(k), int) or coverage.get(k) < 0 for k in required):
            errors.append("coverage contains invalid counters")
        else:
            if coverage.get("processed_count") != len(products):
                errors.append("coverage.processed_count != latest product count")
            if coverage.get("watchlist_count") < coverage.get("processed_count"):
                errors.append("coverage.watchlist_count < processed_count")
            if coverage.get("skipped_count") != coverage.get("watchlist_count") - coverage.get("processed_count"):
                errors.append("coverage.skipped_count mismatch")
            ids = coverage.get("skipped_ids") or []
            if not isinstance(ids, list) or len(ids) != coverage.get("skipped_count"):
                errors.append("coverage.skipped_ids mismatch")
            if len(ids) != len(set(ids)):
                errors.append("coverage.skipped_ids contains duplicates")
            if set(ids) & set(latest_ids):
                errors.append("coverage skipped id overlaps processed id")
            expected_processing_rate = round(
                100.0 * coverage["processed_count"] / coverage["watchlist_count"], 1
            ) if coverage["watchlist_count"] else 100.0
            if coverage.get("processing_rate_pct") != expected_processing_rate:
                errors.append("coverage.processing_rate_pct mismatch")
            expected_transport_rate = round(
                100.0 * sum(1 for p in products if p.get("fetch_status") == "ok") / len(products), 1
            ) if products else 0.0
            if coverage.get("transport_success_rate_pct") != expected_transport_rate:
                errors.append("coverage.transport_success_rate_pct mismatch")
            expected_price_rate = round(
                100.0 * sum(1 for p in products if p.get("current_price_jpy") is not None) / len(products), 1
            ) if products else 0.0
            if coverage.get("price_verified_rate_pct") != expected_price_rate:
                errors.append("coverage.price_verified_rate_pct mismatch")
    if fetch_stats:
        keys = ("total", "direct_verified", "search_corrob", "stale_previous", "baseline_only", "anomaly_rejected", "errors")
        if any(not isinstance(fetch_stats.get(k), int) or fetch_stats.get(k) < 0 for k in keys):
            errors.append("fetch_stats contains invalid counters")
        elif fetch_stats.get("total") != len(products):
            errors.append("fetch_stats.total != latest product count")
        else:
            expected_fetch_stats = {
                "direct_verified": sum(
                    1 for x in products
                    if x.get("current_price_jpy") is not None
                    and x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
                ),
                "search_corrob": sum(
                    1 for x in products
                    if x.get("current_price_jpy") is not None
                    and x.get("price_source_mode") == "search_snippet"
                ),
                "stale_previous": sum(1 for x in products if x.get("price_source_mode") == "stale_previous"),
                "baseline_only": sum(1 for x in products if x.get("price_source_mode") == "public_baseline"),
                "anomaly_rejected": sum(
                    1 for x in products if x.get("price_validation_status") == "anomaly_rejected"
                ),
                "errors": sum(1 for x in products if x.get("fetch_status") == "error"),
            }
            for key, expected in expected_fetch_stats.items():
                if fetch_stats.get(key) != expected:
                    errors.append(f"fetch_stats.{key} mismatch")

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
            if latest_generated is not None and rt is not None and rt != latest_generated:
                errors.append(f"latest retrieval timestamp mismatch: {cid}")

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

    anchors = load_anchors()
    events = read_events()

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

    ranking_generated = parse_dt(rankings.get("generated_at"))
    ranking_prediction = parse_dt(rankings.get("prediction_time"))
    if ranking_generated is None or ranking_prediction is None:
        errors.append("ranking generated_at/prediction_time missing or invalid")
    elif ranking_generated != ranking_prediction:
        errors.append("ranking generated_at != prediction_time")

    # Derived ranking must identify exactly which observation snapshot produced it.
    latest_hash = file_sha256(latest_path) if os.path.exists(latest_path) else None
    if "source_snapshot_generated_at" not in rankings or "source_snapshot_sha256" not in rankings:
        errors.append("ranking source snapshot provenance missing")
    else:
        if rankings.get("source_snapshot_generated_at") != latest.get("generated_at"):
            errors.append("ranking source snapshot generated_at mismatch")
        if latest_hash and rankings.get("source_snapshot_sha256") != latest_hash:
            errors.append("ranking source snapshot SHA256 mismatch")
    top = rankings.get("top_recommendation") or {}
    if ranked:
        if top.get("id") != ranked[0].get("id"):
            errors.append("top recommendation does not match rank 1")
    elif top.get("id") is not None:
        errors.append("top recommendation exists while ranking is empty")
    if top.get("status") == "UNAVAILABLE":
        errors.append("top recommendation is unavailable")
    if not ranked and top.get("id") is not None:
        errors.append("top recommendation must be empty when no actionable ranking exists")

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
        partition = ranked + unavailable + reference_only
        expected_quality = {
            "direct_verified": sum(
                1 for x in partition
                if x.get("current_price_jpy") is not None
                and x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
            ),
            "search_verified": sum(
                1 for x in partition
                if x.get("current_price_jpy") is not None
                and x.get("price_source_mode") == "search_snippet"
            ),
            "anomaly_rejected": sum(1 for x in partition if x.get("price_validation_status") == "anomaly_rejected"),
            "variant_ambiguous": sum(1 for x in partition if x.get("variant_match") == "ambiguous"),
            "unknown_stock": sum(1 for x in partition if x.get("stock_status") == "unknown"),
            "out_of_stock": sum(1 for x in partition if x.get("stock_status") == "out_of_stock"),
            "dynamic_candidate_count": sum(1 for x in partition if x.get("dynamic_candidate")),
            "pit_unknown": sum(
                1 for x in partition
                if x.get("current_price_jpy") is not None and not x.get("available_at")
            ),
            "pit_failures": sum(
                1 for x in partition
                if x.get("current_price_jpy") is not None
                and x.get("available_at") and x.get("prediction_time")
                and not x.get("pit_valid", False)
            ),
        }
        for key, expected in expected_quality.items():
            if quality.get(key) != expected:
                errors.append(f"quality.{key} mismatch")

        # New coverage/purchase-gate fields are strictly validated once the
        # current ranking snapshot contains them. Older committed snapshots are
        # accepted during schema migration so code-only CI commits stay green.
        if "critical_unverified_count" in quality or "purchase_gate" in rankings:
            critical_ids = sorted(cid for cid, priority in watch_priority.items() if priority == "critical")
            partition_by_id = {str(x.get("id")): x for x in partition if x.get("id")}
            critical_unverified = sorted(
                cid for cid in critical_ids
                if not (
                    partition_by_id.get(cid, {}).get("current_price_jpy") is not None
                    and partition_by_id.get(cid, {}).get("price_source_mode") == "direct_structured"
                    and partition_by_id.get(cid, {}).get("variant_match") in ("exact", "trusted_url", "strong")
                    and partition_by_id.get(cid, {}).get("stock_status") in ("in_stock", "low_stock", "out_of_stock")
                )
            )
            if quality.get("critical_candidate_count") != len(critical_ids):
                errors.append("quality.critical_candidate_count mismatch")
            if quality.get("critical_unverified_count") != len(critical_unverified):
                errors.append("quality.critical_unverified_count mismatch")
            expected_coverage = "COMPLETE" if not critical_unverified else "PARTIAL"
            if quality.get("coverage_status") != expected_coverage:
                errors.append("quality.coverage_status mismatch")
    
            gate = rankings.get("purchase_gate") or {}
            gate_ids = sorted(str(x) for x in (gate.get("critical_unverified_ids") or []))
            if gate_ids != critical_unverified:
                errors.append("purchase_gate critical_unverified_ids mismatch")
            if gate.get("coverage_status") != expected_coverage:
                errors.append("purchase_gate coverage_status mismatch")
            expected_allowed = bool(
                ranked
                and expected_coverage == "COMPLETE"
                and rankings.get("peripheral_budget_data_ready")
                and (ranked[0].get("score_detail") or {}).get("status") in ("BUY_NOW", "BUY_NOW_LOW_STOCK", "BUY_NOW_NEAR_BUDGET")
                and effective_cost(ranked[0]) is not None
                and effective_cost(ranked[0]) <= budget_projection.get("pc_dynamic_cap_jpy", 0)
            )
            if bool(gate.get("allowed")) != expected_allowed:
                errors.append("purchase_gate allowed mismatch")
    

    # Purchase links are data, not presentation-only decoration.
    # A row may be unpriced/reference-only, but when a purchase URL exists it must
    # be the same trusted product URL recorded in the source row and use HTTP(S).
    for r in ranked + unavailable + reference_only:
        purl = r.get("purchase_url")
        if purl is not None:
            if not isinstance(purl, str) or not purl.startswith(("https://", "http://")):
                errors.append(f"invalid purchase_url: {r.get('id')}")
            elif purl != r.get("url"):
                errors.append(f"purchase_url does not match source url: {r.get('id')}")

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

        recomputed_score, recomputed_detail = decision_score(r, anchors, events)
        if recomputed_score != score_num:
            errors.append(f"recomputed score mismatch: {rid}")
        for key in (
            "status", "performance", "price", "history", "stock", "timing",
            "gpu", "required_discount_pct", "required_effective_discount_pct",
            "cash_total_cost_jpy", "confirmed_benefit_value_jpy", "effective_cost_jpy",
            "score_before_cap", "score_cap",
            "wait_risk", "historical_floor_jpy", "price_source_mode", "variant_match",
        ):
            if recomputed_detail.get(key) != detail.get(key):
                errors.append(f"recomputed detail mismatch: {rid}:{key}")

        status = detail.get("status")
        source = r.get("price_source_mode")
        stock = r.get("stock_status")

        if stock == "out_of_stock":
            errors.append(f"out_of_stock leaked into actionable ranking: {rid}")
        if source in ("search_snippet", "public_baseline", "stale_previous", "direct_text", "direct_meta") and status != "VERIFY_NOW":
            errors.append(f"verification-source status mismatch: {rid}")

        if status in ("BUY_NOW", "BUY_NOW_LOW_STOCK", "BUY_NOW_NEAR_BUDGET"):
            if source != "direct_structured":
                errors.append(f"buy-now source not direct_structured: {rid}")
            eff = effective_cost(r)
            if eff is None:
                errors.append(f"buy-now effective cost missing: {rid}")
            elif status in ("BUY_NOW", "BUY_NOW_LOW_STOCK") and eff > EFFECTIVE_SOFT_MAX:
                errors.append(f"buy-now effective cost above soft limit: {rid}")
            elif status == "BUY_NOW_NEAR_BUDGET" and not (EFFECTIVE_SOFT_MAX < eff <= EFFECTIVE_HARD_MAX):
                errors.append(f"near-budget effective cost outside 285-290k band: {rid}")
            if r.get("variant_match") not in ("exact", "trusted_url", "strong"):
                errors.append(f"buy-now identity not verified: {rid}")
            config_ready, config_reasons = configuration_readiness(r)
            if not config_ready:
                errors.append(f"buy-now configuration below 32GB/1TB: {rid}:{','.join(config_reasons)}")
            if eff is not None and eff > budget_projection.get("pc_dynamic_cap_jpy", 0):
                errors.append(f"buy-now violates all-in budget cap: {rid}")
            if stock not in ("in_stock", "low_stock"):
                errors.append(f"buy-now stock not verified: {rid}")
            if status == "BUY_NOW_LOW_STOCK":
                threshold = 85
            elif status == "BUY_NOW_NEAR_BUDGET":
                threshold = 94
                if r.get("stock_status") != "in_stock":
                    errors.append(f"near-budget candidate must be in_stock: {rid}")
                try:
                    perf = int((r.get("score_detail") or {}).get("performance", 0))
                except Exception:
                    perf = 0
                if perf < 38:
                    errors.append(f"near-budget performance below threshold: {rid}")
            else:
                threshold = 90
            if score_num < threshold:
                errors.append(f"buy-now score below threshold: {rid}")

        av = parse_dt(r.get("available_at"))
        rt = parse_dt(r.get("retrieval_time"))
        pr = parse_dt(r.get("prediction_time"))
        if av is None or rt is None or pr is None or av > rt or rt > pr:
            errors.append(f"ranking PIT violation: {rid}")

    # The entire ranked state must be partitioned back to the catalog/live candidate set.
    expected_ids = set(catalog_ids)
    expected_ids.update(str(x.get("id") or "") for x in products if x.get("id"))
    if set(all_ranked_ids) != expected_ids:
        missing = sorted(expected_ids - set(all_ranked_ids))
        extra = sorted(set(all_ranked_ids) - expected_ids)
        errors.append(f"ranking partition does not match live/catalog ids: missing={missing}, extra={extra}")

    for r in ranked:
        if ranking_prediction is not None and parse_dt(r.get("prediction_time")) != ranking_prediction:
            errors.append(f"ranking prediction snapshot mismatch: {r.get('id')}")

    for r in unavailable:
        if r.get("stock_status") != "out_of_stock":
            errors.append(f"unavailable partition contains non-out-of-stock row: {r.get('id')}")
        if r.get("rank") is not None:
            errors.append(f"unavailable row has a rank: {r.get('id')}")

    for r in reference_only:
        if r.get("decision_score") is not None:
            errors.append(f"reference-only row has a decision score: {r.get('id')}")
        if r.get("current_price_jpy") is not None:
            errors.append(f"reference-only row exposes current price: {r.get('id')}")

    # Timing/scenario files are also derived artifacts. When present, they
    # must point to the same exact current observation snapshot.
    for derived_name in ("timing_analysis.json", "scenario_analysis.json"):
        derived_path = os.path.join(ROOT, "data", derived_name)
        if os.path.exists(derived_path):
            derived = load_json(derived_path, {})
            if derived.get("source_snapshot_generated_at") != latest.get("generated_at"):
                errors.append(f"{derived_name} source snapshot generated_at mismatch")
            if latest_hash and derived.get("source_snapshot_sha256") != latest_hash:
                errors.append(f"{derived_name} source snapshot SHA256 mismatch")

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
