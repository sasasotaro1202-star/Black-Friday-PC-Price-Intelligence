import json
import os
import sys

from intelligence import ROOT, load_json, parse_dt

def fail(msg):
    print("HEALTHCHECK_FAIL:", msg)
    raise SystemExit(1)

def main():
    errors = []

    catalog = load_json(os.path.join(ROOT, "config", "candidate_catalog.json"), {})
    catalog_items = catalog.get("candidates", [])
    catalog_ids = [str(x.get("id") or "") for x in catalog_items]
    if any(not x for x in catalog_ids):
        errors.append("catalog contains missing id")
    if len(catalog_ids) != len(set(catalog_ids)):
        errors.append("catalog duplicate id")

    watch = load_json(os.path.join(ROOT, "data", "watchlist.json"), {})
    watch_items = watch.get("urls", [])
    watch_ids = [str(x.get("id") or "") for x in watch_items if isinstance(x, dict)]
    watch_urls = [str(x.get("url") or "") for x in watch_items if isinstance(x, dict)]
    if len(watch_ids) != len(set(watch_ids)):
        errors.append("watchlist duplicate id")
    if len(watch_urls) != len(set(watch_urls)):
        errors.append("watchlist duplicate url")
    if any(not x for x in watch_ids):
        errors.append("watchlist missing id")
    if any(not x.startswith("http") for x in watch_urls):
        errors.append("watchlist invalid url")

    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {})
    products = latest.get("products", [])
    latest_ids = [str(x.get("id") or "") for x in products if x.get("id")]
    if len(latest_ids) != len(set(latest_ids)):
        errors.append("latest duplicate id")

    for p in products:
        cid = str(p.get("id") or "")
        current = p.get("current_price_jpy")
        if current is None:
            continue
        if p.get("price_validation_status") in (None, "missing", "reference_only", "variant_ambiguous", "anomaly_rejected"):
            errors.append(f"current price has non-actionable validation status: {cid}")
        av = parse_dt(p.get("available_at"))
        rt = parse_dt(p.get("retrieval_time"))
        pr = parse_dt(p.get("prediction_time"))
        if av is None or rt is None or pr is None:
            errors.append(f"current price lacks PIT timestamps: {cid}")
        elif av > rt:
            errors.append(f"available_at after retrieval_time: {cid}")
        elif rt > pr:
            errors.append(f"retrieval_time after prediction_time: {cid}")
        if int(current) <= 0:
            errors.append(f"non-positive current price: {cid}")

    event_path = os.path.join(ROOT, "data", "change_events.jsonl")
    if os.path.exists(event_path):
        seen_events = set()
        with open(event_path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
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
                    pr = parse_dt(e.get("prediction_time"))
                    if av is None or pr is None or av > pr:
                        errors.append(f"invalid PIT in change event line {n}")

    rankings = load_json(os.path.join(ROOT, "data", "decision_rankings.json"), {})
    products_ranked = rankings.get("products", [])
    ranks = [x.get("rank") for x in products_ranked if x.get("rank") is not None]
    if len(ranks) != len(set(ranks)):
        errors.append("duplicate ranking rank")
    if ranks and sorted(ranks) != list(range(1, len(ranks)+1)):
        errors.append("ranking ranks are not contiguous")

    expected_order = sorted(products_ranked, key=lambda x: (
        -(x.get("decision_score") if x.get("decision_score") is not None else -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        str(x.get("id") or ""),
    ))
    if [str(x.get("id") or "") for x in products_ranked] != [str(x.get("id") or "") for x in expected_order]:
        errors.append("ranking order is not deterministic score-desc/price-asc/id-asc")
    if products_ranked and (rankings.get("top_recommendation") or {}).get("id") != products_ranked[0].get("id"):
        errors.append("top recommendation does not match rank 1")

    for r in products_ranked:
        if r.get("stock_status") == "out_of_stock":
            errors.append(f"out_of_stock leaked into actionable rankings: {r.get('id')}")
        score = r.get("decision_score")
        d = r.get("score_detail") or {}
        if score is not None:
            cap = d.get("score_cap")
            if cap is None or score > cap:
                errors.append(f"score cap violation: {r.get('id')}")
            if not 0 <= score <= 100:
                errors.append(f"score range violation: {r.get('id')}")
            av = parse_dt(r.get("available_at"))
            rt = parse_dt(r.get("retrieval_time"))
            pr = parse_dt(r.get("prediction_time"))
            if av is None or rt is None or pr is None or av > rt or rt > pr:
                errors.append(f"ranking PIT violation: {r.get('id')}")

    top = rankings.get("top_recommendation") or {}
    if top.get("status") == "UNAVAILABLE":
        errors.append("top recommendation is unavailable")

    if errors:
        for e in errors:
            print(" -", e)
        raise SystemExit(1)

    print(json.dumps({
        "status": "PASS",
        "catalog": len(catalog_items),
        "watchlist": len(watch_items),
        "latest_products": len(products),
        "ranked_products": len(products_ranked),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
