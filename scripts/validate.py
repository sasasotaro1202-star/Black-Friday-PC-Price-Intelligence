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
    if policy["pc_budget_jpy"] + policy["peripheral_budget_jpy"] != policy["total_budget_jpy"]:
        errors.append("budget arithmetic mismatch: PC cap + peripheral target != total budget")
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

    build_plan = load_json(os.path.join(ROOT, "data", "self_build_plan.json"), {})
    if not build_plan:
        errors.append("self_build_plan_missing")
    else:
        if build_plan.get("bf_actual_authorized") is not False or build_plan.get("buy_now_authorized") is not False:
            errors.append("self_build_plan must never authorize purchase from target/comparison prices")
        if build_plan.get("budget_arithmetic_valid") is not True:
            errors.append("self_build_plan budget arithmetic invalid")
        pc_budget, periph_budget, total_budget = build_plan.get("pc_budget_jpy"), build_plan.get("peripheral_budget_jpy"), build_plan.get("total_budget_jpy")
        if not all(isinstance(x, int) and x >= 0 for x in (pc_budget, periph_budget, total_budget)) or pc_budget + periph_budget != total_budget:
            errors.append("self_build_plan total/PC/peripheral budget mismatch")
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
            if build.get("target_all_in_jpy") != build.get("target_pc_total_jpy", 0) + periph_budget:
                errors.append("self_build_plan all-in total mismatch: " + bid)
            statuses = [c.get("status") for c in (build.get("compatibility_checks") or [])]
            expected_status = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
            if build.get("compatibility_status") != expected_status:
                errors.append("self_build_plan compatibility status mismatch: " + bid)
            for part in components:
                if part.get("bf_actual_authorized") is not False:
                    errors.append("self_build_plan component BF authorization invalid: " + bid + ":" + str(part.get("id")))
                if part.get("track_price") and part.get("market_reference_price_jpy") is not None and part.get("trusted_for_market_estimate") is not True:
                    errors.append("self_build_plan exposed untrusted component price: " + bid + ":" + str(part.get("id")))
            if build.get("market_reference_estimate_jpy") is not None:
                if build.get("market_reference_coverage_complete") is not True or build.get("market_reference_estimate_is_checkout_price") is not False:
                    errors.append("self_build_plan market estimate lacks complete reference coverage/caveat: " + bid)

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
