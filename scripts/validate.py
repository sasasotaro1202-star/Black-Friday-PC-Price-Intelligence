import json
import os
import sys

from intelligence import ROOT, parse_dt, load_catalog, load_json

def fail(message):
    print("VALIDATION_FAIL:", message)
    raise SystemExit(1)

def main():
    errors = []
    catalog = load_catalog()
    if len(catalog) != len(set(catalog)):
        errors.append("duplicate catalog ids")

    latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {})
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
        if p.get("available_at") and p.get("retrieval_time"):
            a = parse_dt(p["available_at"])
            r = parse_dt(p["retrieval_time"])
            if a and r and a > r:
                errors.append(f"PIT availability after retrieval: {cid}")

    for r in rankings.get("products", []):
        score = r.get("decision_score")
        detail = r.get("score_detail") or {}
        if score is not None:
            comps = sum(int(detail.get(k, 0) or 0) for k in ("performance","price","history","stock","timing"))
            if comps > 100:
                errors.append(f"score components >100: {r.get('id')}")
            cap = int(detail.get("score_cap", 100) or 0)
            if score > cap:
                errors.append(f"score exceeds cap: {r.get('id')}")
            if score < 0 or score > 100:
                errors.append(f"score outside 0..100: {r.get('id')}")
            if not r.get("prediction_time"):
                errors.append(f"missing prediction_time: {r.get('id')}")
            av = r.get("available_at")
            pr = r.get("prediction_time")
            if av and pr:
                a = parse_dt(av)
                p = parse_dt(pr)
                if not a or not p or a > p:
                    errors.append(f"PIT violation in ranking: {r.get('id')}")

    if rankings.get("quality", {}).get("pit_failures", 0) != 0:
        errors.append("reported PIT failures != 0")

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
