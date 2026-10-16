import hashlib
import json
import os
import sys

from intelligence import ROOT, parse_dt, load_catalog, load_json, purchase_budget_policy, peripheral_budget_projection, configuration_readiness

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message):
    print("VALIDATION_FAIL:", message)
    raise SystemExit(1)

def main():
    errors = []
    policy = purchase_budget_policy()
    peripheral_projection = peripheral_budget_projection()
    peripheral_snapshot = load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {})
    # pc_budget_jpy is the absolute PC-side cap before dynamic peripheral allocation.
    # It therefore balances with the separate contingency, while the actual build
    # target is checked against peripherals + contingency under the total hard ceiling.
    if policy["pc_budget_jpy"] + policy.get("unallocated_contingency_jpy", 0) != policy["total_budget_jpy"]:
        errors.append("budget arithmetic mismatch: PC cap + contingency != total budget")
    dynamic_pc_cap = peripheral_projection.get("pc_dynamic_cap_jpy")
    projected_peripherals = peripheral_projection.get("peripheral_projection_jpy")
    contingency = policy.get("unallocated_contingency_jpy", 0)
    if not isinstance(dynamic_pc_cap, int) or not isinstance(projected_peripherals, int):
        errors.append("dynamic all-in budget projection is missing or invalid")
    elif dynamic_pc_cap + projected_peripherals + contingency > policy["total_budget_jpy"]:
        errors.append("dynamic PC cap + projected peripherals + contingency exceeds total budget")
    if policy["pc_target_jpy"] > policy["pc_budget_jpy"]:
        errors.append("PC target exceeds PC cap")
    if sum(int(p.get("target_price_jpy") or 0) for p in policy["peripherals"] if p.get("mandatory", True)) != policy["peripheral_budget_jpy"]:
        errors.append("peripheral target rows do not sum to peripheral budget")
    tracked_ids = {str(p.get("id")) for p in policy["peripherals"] if p.get("track_current_price")}
    snapshot_ids = {str(p.get("id")) for p in (peripheral_snapshot.get("products") or []) if p.get("id")}
    if tracked_ids and not tracked_ids.issubset(snapshot_ids):
        errors.append("peripheral snapshot missing tracked product ids")
    for peripheral in (peripheral_snapshot.get("products") or []):
        if peripheral.get("current_price_jpy") is not None and not peripheral.get("price_verified"):
            errors.append(f"unverified peripheral price exposed as current: {peripheral.get('id')}")
    catalog = load_catalog()
    if len(catalog) != len(set(catalog)):
        errors.append("duplicate catalog ids")

    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {})
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    coverage = latest.get("coverage") or {}
    if coverage:
        processed = coverage.get("processed_count")
        watchlist_count = coverage.get("watchlist_count")
        skipped = coverage.get("skipped_count")
        if processed != len(latest.get("products", [])):
            errors.append("coverage.processed_count mismatch")
        if not isinstance(watchlist_count, int) or not isinstance(skipped, int) or not isinstance(processed, int):
            errors.append("coverage counters invalid")
        elif watchlist_count < processed or skipped != watchlist_count - processed:
            errors.append("coverage counters inconsistent")
        expected_rate = round(100.0 * processed / watchlist_count, 1) if watchlist_count else 100.0
        if coverage.get("processing_rate_pct") != expected_rate:
            errors.append("coverage.processing_rate_pct mismatch")

    rankings = load_json(os.path.join(ROOT, "data", "decision_rankings.json"), {})

    seen = set()
    for p in latest.get("products", []):
        cid = str(p.get("id") or "")
        if cid and cid in seen:
            errors.append(f"duplicate latest id: {cid}")
        seen.add(cid)

        current = p.get("current_price_jpy")
        status = p.get("price_validation_status")
        if status == "validated" and current is None:
            errors.append(f"validated without current price: {cid}")
        if status == "anomaly_rejected" and current is not None:
            errors.append(f"anomaly rejected but current price exposed: {cid}")
        if current is not None and (isinstance(current, bool) or not isinstance(current, (int, float)) or int(current) != current):
            errors.append(f"current price is not an integer number: {cid}")
        if current is not None and p.get("price_jpy") != current:
            errors.append(f"current price field mismatch: {cid}")
        if current is None and p.get("price_jpy") is not None:
            errors.append(f"price_jpy exposed without current price: {cid}")
        if current is not None and not p.get("available_at"):
            errors.append(f"current price without available_at: {cid}")
        if current is not None and not p.get("retrieval_time"):
            errors.append(f"current price without retrieval_time: {cid}")
        if current is not None:
            a = parse_dt(p.get("available_at"))
            r = parse_dt(p.get("retrieval_time"))
            # current_latest is an observation snapshot. It must prove
            # available_at <= retrieval_time; prediction_time is added later
            # by report.py for the ranking decision snapshot.
            if not a or not r or a > r:
                errors.append(f"observation PIT violation: {cid}")

    ranked = rankings.get("products", [])
    ranking_prediction = parse_dt(rankings.get("prediction_time"))
    ranking_generated = parse_dt(rankings.get("generated_at"))
    if ranking_prediction is None or ranking_generated is None:
        errors.append("ranking prediction/generated time missing")
    elif ranking_prediction != ranking_generated:
        errors.append("ranking prediction_time != generated_at")
    latest_hash = file_sha256(latest_path) if os.path.exists(latest_path) else None
    if rankings.get("source_snapshot_generated_at") != latest.get("generated_at"):
        errors.append("ranking source snapshot generated_at mismatch")
    if latest_hash and rankings.get("source_snapshot_sha256") != latest_hash:
        errors.append("ranking source snapshot SHA256 mismatch")

    for r in ranked + list(rankings.get("unavailable_products", [])) + list(rankings.get("reference_only", [])):
        purl = r.get("purchase_url")
        if purl is not None:
            if not isinstance(purl, str) or not purl.startswith(("https://", "http://")):
                errors.append(f"invalid purchase_url: {r.get('id')}")
            elif purl != r.get("url"):
                errors.append(f"purchase_url/source url mismatch: {r.get('id')}")

    expected_order = sorted(ranked, key=lambda x: (
        -(x.get("decision_score") if x.get("decision_score") is not None else -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        str(x.get("id") or ""),
    ))
    if [str(x.get("id") or "") for x in ranked] != [str(x.get("id") or "") for x in expected_order]:
        errors.append("ranking is not deterministically sorted")
    if ranked and (rankings.get("top_recommendation") or {}).get("id") != ranked[0].get("id"):
        errors.append("top_recommendation is not rank 1")

    for r in ranked:
        score = r.get("decision_score")
        detail = r.get("score_detail") or {}
        if detail.get("status") in ("BUY_NOW", "BUY_NOW_LOW_STOCK", "BUY_NOW_NEAR_BUDGET"):
            ready, reasons = configuration_readiness(r)
            if not ready:
                errors.append(f"buy-now PC below required configuration: {r.get('id')}:{','.join(reasons)}")
            if effective_cost(r) is None or effective_cost(r) > peripheral_projection.get("pc_dynamic_cap_jpy", 0):
                errors.append(f"buy-now purchase exceeds all-in budget: {r.get('id')}")
        detail = r.get("score_detail") or {}
        if score is not None:
            comps = sum(int(detail.get(k, 0) or 0) for k in ("performance","price","history","stock","timing"))
            if comps > 100:
                errors.append(f"score components >100: {r.get('id')}")
            cap = int(detail.get("score_cap", 100) or 0)
            if score > cap:
                errors.append(f"score exceeds cap: {r.get('id')}")
            components = sum(int(detail.get(k, 0) or 0) for k in ("performance", "price", "history", "stock", "timing"))
            expected_before_cap = min(100, components)
            if detail.get("score_before_cap") != expected_before_cap:
                errors.append(f"score_before_cap mismatch: {r.get('id')}")
            if score != min(expected_before_cap, cap):
                errors.append(f"decision_score arithmetic mismatch: {r.get('id')}")
            if score < 0 or score > 100:
                errors.append(f"score outside 0..100: {r.get('id')}")
            if not r.get("prediction_time"):
                errors.append(f"missing prediction_time: {r.get('id')}")
            elif ranking_prediction is not None and parse_dt(r.get("prediction_time")) != ranking_prediction:
                errors.append(f"ranking prediction snapshot mismatch: {r.get('id')}")
            av = r.get("available_at")
            rt = r.get("retrieval_time")
            pr = r.get("prediction_time")
            if not av:
                errors.append(f"missing available_at in ranking: {r.get('id')}")
            if not rt:
                errors.append(f"missing retrieval_time in ranking: {r.get('id')}")
            if not pr:
                errors.append(f"missing prediction_time: {r.get('id')}")
            if av and rt and pr:
                a = parse_dt(av)
                rdt = parse_dt(rt)
                p = parse_dt(pr)
                if not a or not rdt or not p or a > rdt or rdt > p:
                    errors.append(f"PIT violation in ranking: {r.get('id')}")

    if rankings.get("quality", {}).get("pit_failures", 0) != 0:
        errors.append("reported PIT failures != 0")
    if rankings.get("quality", {}).get("pit_unknown", 0) != 0:
        errors.append("reported PIT unknown != 0")

    component_snapshot = load_json(os.path.join(ROOT, "data", "build_component_prices.json"), {})
    component_rows = component_snapshot.get("products") or []
    for component_row in component_rows:
        cid = str(component_row.get("id") or "")
        if component_row.get("bf_actual_authorized") is not False:
            errors.append("component reference must never authorize BF actual: " + cid)
        if component_row.get("price_validation_status") == "search_snippet_reference":
            snippet_price = component_row.get("search_snippet_reference_price_jpy")
            if component_row.get("market_reference_price_jpy") is not None:
                errors.append("search snippet exposed as trusted market price: " + cid)
            if component_row.get("retailer_listing_reference_price_jpy") is not None:
                errors.append("search snippet exposed as direct retailer price: " + cid)
            if component_row.get("source_role") != "comparison_site_reference":
                errors.append("search snippet source role mismatch: " + cid)
            if not isinstance(snippet_price, int) or isinstance(snippet_price, bool) or snippet_price <= 0:
                errors.append("search snippet reference missing positive display-only price: " + cid)
            if not component_row.get("search_snippet_identity_anchor"):
                errors.append("search snippet reference missing identity anchor: " + cid)

    build_plan = load_json(os.path.join(ROOT, "data", "self_build_plan.json"), {})
    if not build_plan:
        errors.append("self_build_plan_missing")
    else:
        if build_plan.get("bf_actual_authorized") is not False or build_plan.get("buy_now_authorized") is not False:
            errors.append("self_build_plan must never authorize purchase from target/comparison prices")
        if build_plan.get("budget_arithmetic_valid") is not True:
            errors.append("self_build_plan budget arithmetic invalid")
        pc_budget, periph_budget, contingency, total_budget = (build_plan.get("pc_budget_jpy"), build_plan.get("peripheral_budget_jpy"), build_plan.get("unallocated_contingency_jpy", policy.get("unallocated_contingency_jpy", 0)), build_plan.get("total_budget_jpy"))
        if not all(isinstance(x, int) and x >= 0 for x in (pc_budget, periph_budget, contingency, total_budget)):
            errors.append("self_build_plan has invalid budget values")
        elif pc_budget + contingency != total_budget:
            errors.append("self_build_plan PC cap + contingency mismatch")
        builds = build_plan.get("builds") or []
        if len(builds) != 3:
            errors.append("self_build_plan should contain exactly three mutually exclusive GPU alternatives")
        seen_build_ids = set()
        for build in builds:
            bid = str(build.get("id") or "")
            if not bid or bid in seen_build_ids:
                errors.append("self_build_plan id missing or duplicated")
            seen_build_ids.add(bid)
            if build.get("bf_actual_authorized") is not False or build.get("buy_now_authorized") is not False:
                errors.append("self_build_plan build purchase authorization invalid: " + bid)
            components = build.get("components") or []
            component_ids = [str(p.get("id") or "") for p in components]
            categories = [str(p.get("category") or "") for p in components]
            if len(component_ids) != len(set(component_ids)) or len(categories) != len(set(categories)):
                errors.append("self_build_plan duplicate component/category: " + bid)
            if sum(int(p.get("target_price_jpy") or 0) for p in components) != build.get("target_parts_subtotal_jpy"):
                errors.append("self_build_plan part target subtotal mismatch: " + bid)
            if build.get("target_pc_total_jpy") != build.get("target_parts_subtotal_jpy", 0) + build.get("build_shipping_reserve_jpy", 0) + build.get("small_parts_reserve_jpy", 0):
                errors.append("self_build_plan PC total mismatch: " + bid)
            if build.get("target_all_in_jpy") != build.get("target_pc_total_jpy", 0) + periph_budget + contingency:
                errors.append("self_build_plan all-in total mismatch: " + bid)
            if build.get("target_all_in_jpy", total_budget + 1) > total_budget:
                errors.append("self_build_plan exceeds total budget: " + bid)
            statuses = [c.get("status") for c in (build.get("compatibility_checks") or [])]
            expected_status = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
            if build.get("compatibility_status") != expected_status:
                errors.append("self_build_plan compatibility status mismatch: " + bid)
            for part in components:
                pid = str(part.get("id") or "")
                if part.get("bf_actual_authorized") is not False:
                    errors.append("self_build_plan component BF authorization invalid: " + bid + ":" + pid)
                if part.get("market_reference_price_jpy") is not None and part.get("trusted_for_market_estimate") is not True:
                    errors.append("self_build_plan exposed untrusted component price: " + bid + ":" + pid)
                if part.get("trusted_for_market_estimate") is True:
                    trusted_price = part.get("market_reference_price_jpy")
                    if not isinstance(trusted_price, int) or isinstance(trusted_price, bool) or trusted_price <= 0:
                        errors.append("self_build_plan trusted component lacks positive integer reference: " + bid + ":" + pid)
                    retrieved = parse_dt(part.get("retrieval_time"))
                    planned = parse_dt(build_plan.get("generated_at"))
                    if retrieved is None or planned is None or retrieved > planned:
                        errors.append("self_build_plan trusted component observation is missing/future-dated: " + bid + ":" + pid)
                if part.get("price_status") == "manual_reference_unverified":
                    if part.get("market_reference_price_jpy") is not None or part.get("trusted_for_market_estimate") is not False:
                        errors.append("unverified manual reference leaked into market estimate: " + bid + ":" + pid)
                if part.get("price_status") == "search_snippet_reference_only":
                    display_price = part.get("display_reference_price_jpy")
                    if part.get("market_reference_price_jpy") is not None or part.get("trusted_for_market_estimate") is not False:
                        errors.append("search snippet leaked into market estimate: " + bid + ":" + pid)
                    if not isinstance(display_price, int) or isinstance(display_price, bool) or display_price <= 0:
                        errors.append("search snippet display reference missing positive value: " + bid + ":" + pid)
                    if part.get("source_role") != "comparison_site_reference":
                        errors.append("search snippet display reference source mismatch: " + bid + ":" + pid)
            missing_market_refs = set(build.get("missing_or_untrusted_market_reference_ids") or [])
            expected_reference_count = build.get("market_reference_required_count")
            observed_reference_count = build.get("market_reference_coverage_count")
            if isinstance(expected_reference_count, int) and isinstance(observed_reference_count, int):
                if observed_reference_count + len(missing_market_refs) != expected_reference_count:
                    errors.append("self_build_plan market-reference coverage count mismatch: " + bid)
            if missing_market_refs and build.get("market_reference_estimate_jpy") is not None:
                errors.append("self_build_plan market estimate includes missing/untrusted references: " + bid)
            if build.get("market_reference_estimate_jpy") is not None:
                if build.get("market_reference_coverage_complete") is not True or build.get("market_reference_estimate_is_checkout_price") is not False or missing_market_refs:
                    errors.append("self_build_plan market estimate lacks complete reference coverage/caveat: " + bid)
            if build.get("market_reference_coverage_complete") is not (build.get("market_reference_estimate_jpy") is not None):
                errors.append("self_build_plan market-reference completeness flag mismatch: " + bid)
            if build.get("market_reference_estimate_jpy") is None and isinstance(expected_reference_count, int) and isinstance(observed_reference_count, int) and observed_reference_count == expected_reference_count:
                errors.append("self_build_plan missing market estimate despite complete-reference count: " + bid)

    build_config = load_json(os.path.join(ROOT, "config", "build_components.json"), {})
    build_profile = build_config.get("profile") or {}
    self_build_required = build_profile.get("pc_build_method_preference") == "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION"
    if self_build_required:
        expected_policy = build_plan.get("purchase_method_policy") or {}
        if expected_policy.get("primary_method") != "SELF_BUILD":
            errors.append("self_build_plan primary_method must be SELF_BUILD")
        if expected_policy.get("assembly_time_is_constraint") is not False:
            errors.append("self_build_plan must not treat assembly time as a constraint")
        if expected_policy.get("assembly_time_penalty_points") != 0:
            errors.append("self_build_plan assembly-time penalty must be zero")
        if expected_policy.get("bto_role") != "REFERENCE_BENCHMARK_ONLY":
            errors.append("self_build_plan must label BTO as reference benchmark only")

        if rankings.get("purchase_method_policy", {}).get("primary_method") != "SELF_BUILD":
            errors.append("decision rankings must keep SELF_BUILD as primary method")
        if rankings.get("purchase_method_policy", {}).get("assembly_time_penalty_points") != 0:
            errors.append("decision rankings must not penalize assembly time")
        ranking_gate = rankings.get("purchase_gate") or {}
        if (
            ranking_gate.get("allowed") is not False
            or ranking_gate.get("scope") != "completed_pc_candidates_only"
            or ranking_gate.get("reason") != "completed_pc_candidates_reference_only"
        ):
            errors.append("completed-PC reference gate must stay closed and be clearly scoped when self-build is primary")

        buy_now = load_json(os.path.join(ROOT, "data", "buy_now_decision.json"), {})
        if not buy_now:
            errors.append("buy_now_decision missing after timing analysis")
        else:
            buy_policy = buy_now.get("purchase_method_policy") or {}
            if buy_policy.get("primary_method") != "SELF_BUILD":
                errors.append("buy-now decision must keep SELF_BUILD as primary method")
            if buy_policy.get("completed_pc_purchase_actionable") is not False:
                errors.append("BTO completed-PC benchmark must not be purchase-actionable")
            if buy_now.get("purchase_gate_allowed") is not False:
                errors.append("buy-now decision must keep overall gate closed while DIY is primary")
            if buy_now.get("status") == "BUY_NOW":
                errors.append("BTO reference candidate must never produce BUY_NOW under self-build-first policy")
            if (buy_now.get("chosen_candidate") or {}).get("qualified_to_buy") is True:
                errors.append("BTO reference candidate cannot be marked qualified_to_buy under self-build-first policy")
            diy = buy_now.get("self_build_purchase_timing")
            if not isinstance(diy, dict):
                errors.append("DIY build-level timing summary missing")
            else:
                if diy.get("primary_method") != "SELF_BUILD":
                    errors.append("DIY build-level timing summary primary method mismatch")
                if diy.get("purchase_allowed") is not False or diy.get("bf_actual_authorized") is not False:
                    errors.append("DIY plan must not authorize from target/reference-only observations")
                if diy.get("assembly_time_is_constraint") is not False or diy.get("assembly_time_penalty_points") != 0:
                    errors.append("DIY timing summary must ignore assembly time")
                display_only_count = 0
                for row in (diy.get("component_timing") or []):
                    if row.get("display_only_reference_price_jpy") is None:
                        continue
                    display_only_count += 1
                    if row.get("current_market_reference_price_jpy") is not None:
                        errors.append("display-only timing price exposed as market reference: " + str(row.get("id")))
                    if row.get("target_gap_jpy") is not None or row.get("required_drop_pct") is not None:
                        errors.append("display-only timing price used for target-gap calculation: " + str(row.get("id")))
                    if row.get("display_only_reference_is_estimate_eligible") is not False:
                        errors.append("display-only timing reference must be estimate-ineligible: " + str(row.get("id")))
                    if row.get("purchase_allowed") is not False or row.get("bf_actual_authorized") is not False:
                        errors.append("display-only timing reference must never authorize purchase: " + str(row.get("id")))
                    if row.get("direct_listing_display_price_jpy") is None and row.get("status") != "DISPLAY_ONLY_SEARCH_REFERENCE":
                        errors.append("display-only timing reference status label missing: " + str(row.get("id")))
                if diy.get("display_only_search_reference_count") != display_only_count:
                    errors.append("DIY display-only reference count mismatch")

                direct_listing_display_count = 0
                for row in (diy.get("component_timing") or []):
                    direct_price = row.get("direct_listing_display_price_jpy")
                    if direct_price is None:
                        continue
                    direct_listing_display_count += 1
                    if row.get("current_market_reference_price_jpy") is not None:
                        errors.append("direct listing display price exposed as market reference: " + str(row.get("id")))
                    if row.get("target_gap_jpy") is not None or row.get("required_drop_pct") is not None:
                        errors.append("direct listing display price used in target-gap calculation: " + str(row.get("id")))
                    if row.get("direct_listing_display_is_estimate_eligible") is not False:
                        errors.append("direct listing display price must be estimate-ineligible: " + str(row.get("id")))
                    if row.get("direct_listing_display_purchase_allowed") is not False or row.get("purchase_allowed") is not False:
                        errors.append("direct listing display price must never authorize purchase: " + str(row.get("id")))
                    if row.get("status") != "DIRECT_LISTING_DISPLAY_ONLY":
                        errors.append("direct listing display price status label mismatch: " + str(row.get("id")))
                    stock_label = str(row.get("direct_listing_display_stock_label") or "")
                    if stock_label and stock_label not in str(row.get("status_label") or ""):
                        errors.append("direct listing stock label missing from status text: " + str(row.get("id")))
                if diy.get("direct_listing_display_count") != direct_listing_display_count:
                    errors.append("DIY direct-listing display count mismatch")

                report_path = os.path.join(ROOT, "data", "reports", "buy-now-now.md")
                try:
                    with open(report_path, encoding="utf-8") as report_stream:
                        buy_now_markdown = report_stream.read()
                    if "検索ページ表示専用値（不採用）" not in buy_now_markdown:
                        errors.append("buy-now report missing separate display-only reference column")
                    if display_only_count and "検索ページ表示値のみ（検証価格なし）" not in buy_now_markdown:
                        errors.append("buy-now report missing display-only status label")
                    if direct_listing_display_count and "直接掲載価格（在庫条件未達・推定不採用）" not in buy_now_markdown:
                        errors.append("buy-now report missing direct listing display column")
                except OSError:
                    errors.append("buy-now report missing after timing analysis")

    if errors:
        for e in errors:
            print(" -", e)
        raise SystemExit(1)

    print(json.dumps({
        "status": "PASS",
        "catalog_count": len(catalog),
        "latest_count": len(latest.get("products", [])),
        "ranking_count": len(rankings.get("products", [])),
        "message": "Fail-closed data validation passed.",
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
