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
        if current is not None and p.get("price_jpy") != current:
            errors.append(f"current price field mismatch: {cid}")
        if current is None and p.get("price_jpy") is not None:
            errors.append(f"price_jpy exposed without current price: {cid}")
        if current is not None and not p.get("available_at"):
            errors.append(f"current price without available_at: {cid}")
        if current is not None and not p.get("retrieval_time"):
            errors.append(f"current price without retrieval_time: {cid}")
        if p.get("available_at") or p.get("retrieval_time"):
            a = parse_dt(p.get("available_at"))
            r = parse_dt(p.get("retrieval_time"))
            pr = parse_dt(p.get("prediction_time"))
            if not a or not r or not pr or a > r or r > pr:
                errors.append(f"PIT chain violation: {cid}")

    ranked = rankings.get("products", [])
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
