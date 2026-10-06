import json
import math
import os
import re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUDGET = 280000
MAX_TRACKED_PRICE = 900000

GPU_POINTS = {
    "rtx 5090": 25,
    "rtx 5080": 23,
    "rtx 5070 ti": 21,
    "rtx 5070": 17,
    "rtx 5060 ti": 11,
    "rtx 5060": 8,
}

GPU_FLOORS = {
    "rtx 5090": 300000,
    "rtx 5080": 240000,
    "rtx 5070 ti": 180000,
    "rtx 5070": 150000,
    "rtx 5060 ti": 120000,
    "rtx 5060": 100000,
}

CPU_POINTS = [
    ("9955hx3d", 15),
    ("9955hx", 14),
    ("8940hx", 13),
    ("8945hx", 13),
    ("290hx", 13),
    ("275hx", 13),
    ("ultra 9", 12),
    ("core i9", 12),
    ("13700hx", 11),
    ("14650hx", 10),
    ("13620h", 8),
    ("ryzen 9", 9),
    ("core ultra 7", 9),
]

GPU_ORDER = (
    "rtx 5090",
    "rtx 5080",
    "rtx 5070 ti",
    "rtx 5070",
    "rtx 5060 ti",
    "rtx 5060",
)

PRICE_EXCLUDE_CONTEXT = (
    "月額", "月々", "分割", "円/月", "円／月", "1回", "２４回",
    "24回", "36回", "48回", "ポイント還元", "ポイント付与",
    "通常価格", "定価", "参考価格", "メーカー希望", "上限",
)

PRICE_INCLUDE_CONTEXT = (
    "販売価格", "税込", "税込価格", "価格", "セール価格", "特価",
    "割引価格", "支払価格", "price", "sale",
)

def now_jst():
    return datetime.now(JST).replace(microsecond=0)

def iso(dt):
    return dt.astimezone(JST).replace(microsecond=0).isoformat()

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return None

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_catalog():
    path = os.path.join(ROOT, "config", "candidate_catalog.json")
    data = load_json(path, {"candidates": []})
    return {str(x.get("id")): x for x in data.get("candidates", []) if x.get("id")}

def load_anchors():
    data = load_json(os.path.join(ROOT, "config", "history_anchors.json"), {})
    return data.get("anchors", [])

def norm_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()

def normalize_gpu(value):
    s = norm_text(value).replace("geforce ", "")
    s = s.replace("nvidia ", "")
    if "5070 ti" in s:
        return "rtx 5070 ti"
    for g in GPU_ORDER:
        if g in s:
            return g
    return ""

def gpu_key(item):
    spec = item.get("spec") or {}
    parts = [
        spec.get("gpu"),
        item.get("gpu"),
        item.get("name"),
        item.get("title"),
        item.get("query"),
    ]
    blob = norm_text(" ".join(str(x) for x in parts if x))
    for g in GPU_ORDER:
        if g in blob:
            return g
    return ""

def cpu_key(item):
    spec = item.get("spec") or {}
    blob = norm_text(" ".join([
        str(spec.get("cpu") or ""),
        str(item.get("cpu") or ""),
        str(item.get("name") or ""),
        str(item.get("query") or ""),
    ]))
    best = 0
    for token, pts in CPU_POINTS:
        if token in blob:
            best = max(best, pts)
    return best

def expected_spec(catalog_item):
    if not catalog_item:
        return {}
    keys = ("gpu", "cpu", "tgp_w", "ram_gb", "ssd", "vram_gb", "form_factor", "display_hz", "resolution")
    return {k: catalog_item.get(k) for k in keys if catalog_item.get(k) not in (None, "")}

def enrich_identity(item, catalog_item):
    out = dict(item)
    cat = catalog_item or {}
    out["catalog_id"] = cat.get("id")
    out["catalog_name"] = cat.get("name") or item.get("name")
    out["family"] = cat.get("family") or item.get("family")
    out["form_factor"] = cat.get("form_factor") or item.get("form_factor") or "unknown"
    exp = expected_spec(cat)
    parsed = dict(item.get("parsed_spec") or item.get("spec") or {})
    spec = dict(exp)
    spec.update({k: v for k, v in parsed.items() if v not in (None, "")})
    out["expected_spec"] = exp
    out["parsed_spec"] = parsed
    out["spec"] = spec

    # URL equality alone is insufficient: shared family pages can expose many variants.
    exact_url = bool(cat.get("url_is_exact"))

    blob = norm_text(" ".join([
        str(item.get("page_text_excerpt") or ""),
        str(item.get("name") or ""),
        str(item.get("title") or ""),
        str(item.get("query") or ""),
    ]))
    expected_cpu = norm_text(exp.get("cpu"))
    expected_gpu = norm_text(exp.get("gpu"))
    cpu_ok = bool(expected_cpu and expected_cpu in blob)
    gpu_ok = bool(expected_gpu and normalize_gpu(expected_gpu) == gpu_key(item)) if expected_gpu else True
    if exact_url and (cpu_ok and gpu_ok):
        variant = "exact"
    elif exact_url and (cat.get("identity_confidence") == "high"):
        variant = "trusted_url"
    elif cpu_ok and gpu_ok:
        variant = "strong"
    elif expected_gpu and normalize_gpu(expected_gpu) == gpu_key(item):
        variant = "gpu_only"
    else:
        variant = "ambiguous"

    out["variant_match"] = variant
    out["identity_confidence"] = cat.get("identity_confidence", "low")
    return out

def price_context_score(context):
    c = norm_text(context)
    score = 0
    if any(x in c for x in PRICE_EXCLUDE_CONTEXT):
        score -= 20
    score += sum(3 for x in PRICE_INCLUDE_CONTEXT if x in c)
    if "送料無料" in c:
        score -= 1
    return score

def price_candidates(text):
    text = re.sub(r"\s+", " ", str(text or ""))
    out = []
    patterns = [
        r"(?:¥|￥)\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{5,7})(?:\s*円)?",
        r"(?<![0-9])([0-9]{2,3}(?:,[0-9]{3})+)\s*円",
        r"(?<![0-9])([0-9]{6,7})\s*円",
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            try:
                value = int(m.group(1).replace(",", ""))
            except Exception:
                continue
            if value < 50000 or value > MAX_TRACKED_PRICE:
                continue
            if value in seen:
                continue
            seen.add(value)
            context = text[max(0, m.start()-110):min(len(text), m.end()+110)]
            score = price_context_score(context)
            if 100000 <= value <= 700000:
                score += 4
            if value < 120000:
                score -= 8
            out.append({
                "price_jpy": value,
                "score": score,
                "context": context[:260],
            })
    out.sort(key=lambda x: (x["score"], -x["price_jpy"]), reverse=True)
    return out

def pick_price(text):
    candidates = price_candidates(text)
    return candidates[0] if candidates else None

def plausible_floor(item):
    g = gpu_key(item)
    return GPU_FLOORS.get(g, 100000)

def validate_price(price_jpy, item, reference_price=None, corroborated=False):
    if not price_jpy:
        return {"valid": False, "status": "missing", "reason": "price_missing"}
    p = int(price_jpy)
    floor = plausible_floor(item)
    ref = reference_price
    reasons = []
    suspicious = False
    if p > MAX_TRACKED_PRICE:
        return {"valid": False, "status": "out_of_range", "reason": "price_above_tracking_limit"}
    if p < max(80000, int(floor * 0.60)):
        suspicious = True
        reasons.append("below_gpu_plausibility_floor")
    if ref and ref > 0:
        ratio = p / float(ref)
        if ratio < 0.55:
            suspicious = True
            reasons.append("large_drop_vs_reference")
        if ratio > 1.90:
            suspicious = True
            reasons.append("large_jump_vs_reference")
    if suspicious and not corroborated:
        return {
            "valid": False,
            "status": "anomaly_rejected",
            "reason": ",".join(reasons),
        }
    if suspicious:
        return {
            "valid": True,
            "status": "anomaly_corroborated",
            "reason": ",".join(reasons),
        }
    return {"valid": True, "status": "validated", "reason": "within_expected_range"}

def required_discount(price):
    if not price or price <= 0:
        return None
    return max(0.0, (price - BUDGET) / float(price) * 100.0)

def scenario_prices(price):
    if not price or price <= 0:
        return []
    return [
        {"discount_pct": d, "price_jpy": int(round(price * (1 - d/100.0), -2))}
        for d in (10, 15, 20, 25, 30)
    ]

def price_score(price):
    d = required_discount(price)
    if d is None:
        return 0
    bands = ((0,20),(5,19),(10,18),(15,16),(20,13),(25,10),(30,7),(40,4),(50,2),(1000,0))
    for bound, points in bands:
        if d <= bound:
            return points
    return 0

def history_match_strength(item, anchor):
    name = norm_text(item.get("name"))
    family = norm_text(item.get("family"))
    key = norm_text(item.get("id"))
    afamily = norm_text(anchor.get("family"))
    akey = norm_text(anchor.get("key"))
    aliases = [norm_text(x) for x in (item.get("aliases") or [])]
    g = gpu_key(item)
    ag = normalize_gpu(anchor.get("gpu"))

    exact = bool(
        (akey and (akey == key or akey in name)) or
        (akey and any(akey in a for a in aliases))
    )
    if exact:
        return 3
    same_family = bool(afamily and (afamily in family or afamily in name))
    if same_family and g and ag and g == ag:
        return 2
    if same_family:
        return 1
    return 0

def history_match(item, anchor):
    return history_match_strength(item, anchor) > 0

def history_score(item, anchors):
    best = 0
    matched = []
    g = gpu_key(item)
    for a in anchors:
        strength = history_match_strength(item, a)
        if strength <= 0:
            continue
        matched.append(a)
        p = a.get("historical_price_jpy")
        ag = normalize_gpu(a.get("gpu"))
        if p and p <= BUDGET:
            local = {3: 13, 2: 10, 1: 7}[strength]
        elif p:
            d = required_discount(p)
            base = 10 if d is not None and d <= 20 else 6
            local = {3: base, 2: max(5, base-1), 1: max(4, base-3)}[strength]
        else:
            local = 0
        if g and ag and g == ag:
            local += 2
        if a.get("historical_sellout") or "売り切れ" in norm_text(a.get("historical_note")):
            local += 1
        best = max(best, min(15, local))
    return best, matched

def stock_score(item, anchors):
    status = item.get("stock_status", "unknown")
    base = {
        "in_stock": 11,
        "low_stock": 7,
        "preorder_or_backorder": 3,
        "unknown": 3,
        "out_of_stock": 0,
    }.get(status, 3)
    historical_sellout = any(
        history_match(item, a) and (
            a.get("historical_sellout") or
            "売り切れ" in norm_text(a.get("historical_note")) or
            "sold out" in norm_text(a.get("historical_note"))
        )
        for a in anchors
    )
    if historical_sellout and status == "in_stock":
        base += 4
    elif historical_sellout and status == "low_stock":
        base += 3
    return min(15, base)

def season_phase(now=None):
    now = now or now_jst()
    cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    start = parse_dt(cfg.get("monitor_window_start")) or datetime(now.year, 11, 14, tzinfo=JST)
    end = parse_dt(cfg.get("monitor_window_end")) or datetime(now.year, 12, 4, 23, 59, 59, tzinfo=JST)
    if not (start <= now <= end):
        return "通常監視期間"
    windows = [
        (11,14,20,"メーカー予告/先行"),
        (11,21,23,"先行セール/サプライズ"),
        (11,24,27,"本番前半/BF当日"),
        (11,28,30,"本番後半/Cyber Monday周辺"),
        (12,1,4,"セール末期/在庫処分"),
    ]
    for sm, sd, ed, label in windows:
        a = datetime(now.year, sm, sd, tzinfo=JST)
        b = datetime(now.year, sm, ed, 23, 59, 59, tzinfo=JST)
        if a <= now <= b:
            return label
    return "ブラックフライデー監視期間"

def timing_score(item, now=None):
    price = item.get("current_price_jpy") if item.get("current_price_jpy") is not None else item.get("price_jpy")
    d = required_discount(price)
    stock = item.get("stock_status", "unknown")
    phase = season_phase(now)
    if d is None:
        return 0, "情報不足"
    if d <= 0:
        if stock == "low_stock":
            return 10, "目標価格以下かつ低在庫。待たずに確認"
        if stock == "in_stock":
            return 10, "目標価格以下。次の値下げより在庫確保を優先"
        return 7, "目標価格以下だが在庫状態を要確認"
    base = (
        9 if d <= 10 else
        8 if d <= 15 else
        7 if d <= 20 else
        5 if d <= 30 else
        3 if d <= 40 else
        1
    )
    if "本番" in phase or "先行" in phase:
        base = min(10, base + 1 if d <= 20 else base)
    if stock == "low_stock":
        base = min(10, base + 1)
    guidance = (
        "小幅値下げで28万円化。近いセール帯を重点監視" if d <= 10 else
        "現実的な値下げ幅。価格と在庫を同時監視" if d <= 20 else
        "大幅値下げ待ち。28万円到達時は即再評価" if d <= 30 else
        "大幅特価が必要。価格期待だけで待ち続けない"
    )
    return base, guidance

def performance_score(item):
    g = gpu_key(item)
    gp = GPU_POINTS.get(g, 0)
    cp = cpu_key(item)
    spec = item.get("spec") or {}
    tgp = int(spec.get("tgp_w") or 0)
    ram = int(spec.get("ram_gb") or 0)
    vram = int(spec.get("vram_gb") or 0)
    ssd = str(spec.get("ssd") or "")
    ram_bonus = 2 if ram >= 32 else 1 if ram >= 24 else 0
    ssd_bonus = 2 if re.search(r"1\s*TB", ssd, re.I) else 1 if re.search(r"[2-9]\s*TB", ssd, re.I) else 0
    tgp_bonus = 4 if tgp >= 130 else 3 if tgp >= 115 else 2 if tgp >= 100 else 0
    vram_bonus = 1 if vram >= 12 else 0
    return min(40, gp + cp + ram_bonus + ssd_bonus + tgp_bonus + vram_bonus), g

def confidence_from_item(item):
    if item.get("price_validation_status") == "anomaly_rejected":
        return "none"
    mode = item.get("price_source_mode")
    if mode in ("direct_structured", "direct_page"):
        return "high"
    if mode == "direct_text":
        return "medium"
    if mode == "search_snippet":
        return "medium"
    if mode == "public_baseline":
        return "low"
    if mode in ("stale_previous", "none"):
        return "low"
    return item.get("data_confidence") or "low"

def data_quality_cap(item):
    if item.get("price_validation_status") == "anomaly_rejected":
        return 0
    if item.get("current_price_jpy") is None:
        return 0
    cap = 100
    variant = item.get("variant_match")
    mode = item.get("price_source_mode")
    if item.get("dynamic_candidate"):
        cap = min(cap, 74)
    if variant == "ambiguous":
        cap = min(cap, 74)
    elif variant == "gpu_only":
        cap = min(cap, 82)
    if mode == "search_snippet":
        cap = min(cap, 84)
    elif mode == "public_baseline":
        cap = min(cap, 69)
    elif mode == "stale_previous":
        cap = min(cap, 69)
    if item.get("stock_status") == "unknown":
        cap = min(cap, 89)
    if confidence_from_item(item) == "low":
        cap = min(cap, 79)
    return cap

def price_trend(item, events):
    cid = str(item.get("id") or "")
    relevant = []
    for e in events:
        if str(e.get("id") or "") == cid:
            relevant.append(e)
    price_events = [e for e in relevant if e.get("old_price_jpy") is not None and e.get("new_price_jpy") is not None]
    downs = [e for e in price_events if e["new_price_jpy"] < e["old_price_jpy"]]
    ups = [e for e in price_events if e["new_price_jpy"] > e["old_price_jpy"]]
    last = price_events[-1] if price_events else None
    return {
        "sample_size": len(price_events),
        "down_count": len(downs),
        "up_count": len(ups),
        "down_rate": round(len(downs) / len(price_events), 3) if price_events else None,
        "latest_delta_jpy": (last["new_price_jpy"] - last["old_price_jpy"]) if last else None,
    }

def wait_risk(item, trend=None):
    stock = item.get("stock_status", "unknown")
    price = item.get("current_price_jpy")
    d = required_discount(price)
    if stock == "out_of_stock":
        return "NOT_AVAILABLE"
    if stock == "low_stock":
        return "HIGH"
    if stock == "unknown":
        return "UNKNOWN"
    if price and d is not None and d <= 0:
        if item.get("historical_sellout"):
            return "HIGH"
        return "MEDIUM"
    if item.get("historical_sellout") and d is not None and d <= 15:
        return "HIGH"
    if trend and trend.get("sample_size", 0) >= 3:
        latest = trend.get("latest_delta_jpy")
        if latest is not None and latest > 0:
            return "HIGH"
        if trend.get("down_rate") is not None and trend["down_rate"] >= 0.67:
            return "MEDIUM"
    return "LOW"

def decision_score(item, anchors, events=None):
    events = events or []
    price = item.get("current_price_jpy")
    if price is None or item.get("price_validation_status") in (None, "missing", "anomaly_rejected"):
        return None, {
            "status": "UNACTIONABLE",
            "reason": "current_price_not_verified",
            "performance": 0,
            "price": 0,
            "history": 0,
            "stock": 0,
            "timing": 0,
            "score_cap": 0,
        }

    perf, gpu = performance_score(item)
    ps = price_score(price)
    hs, matched = history_score(item, anchors)
    ss = stock_score(item, anchors)
    ts, guidance = timing_score(item)
    trend = price_trend(item, events)
    total = min(100, perf + ps + hs + ss + ts)
    cap = data_quality_cap(item)
    score = min(total, cap)
    wr = wait_risk(item, trend)

    status = "WATCH"
    if item.get("stock_status") == "out_of_stock":
        status = "UNAVAILABLE"
    elif item.get("price_source_mode") in ("search_snippet", "public_baseline", "stale_previous"):
        status = "VERIFY_NOW"
    elif price <= BUDGET and item.get("stock_status") == "in_stock" and score >= 90:
        status = "BUY_NOW"
    elif price <= BUDGET and item.get("stock_status") == "low_stock" and score >= 85:
        status = "BUY_NOW_LOW_STOCK"
    elif required_discount(price) > 20:
        status = "WAIT_FOR_DISCOUNT"
    elif score >= 85:
        status = "STRONG_WATCH"

    reason_bits = [
        f"28万円まで必要値下げ {required_discount(price):.1f}%" if price > BUDGET else "目標価格以下",
        f"在庫 {item.get('stock_status', 'unknown')}",
        f"構成判定 {item.get('variant_match', 'ambiguous')}",
    ]
    if wr == "HIGH":
        reason_bits.append("待機リスク高")
    elif wr == "UNKNOWN":
        reason_bits.append("待機リスク観測不足")
    reasons = " / ".join(reason_bits)

    hist_floor = None
    for a in matched:
        ap = a.get("historical_price_jpy")
        if ap and (hist_floor is None or ap < hist_floor):
            hist_floor = ap

    detail = {
        "status": status,
        "performance": perf,
        "price": ps,
        "history": hs,
        "stock": ss,
        "timing": ts,
        "gpu": gpu,
        "required_discount_pct": round(required_discount(price), 1),
        "score_before_cap": total,
        "score_cap": cap,
        "wait_risk": wr,
        "timing_guidance": guidance,
        "reason": reasons,
        "historical_floor_jpy": hist_floor,
        "price_trend": trend,
        "data_confidence": confidence_from_item(item),
        "price_source_mode": item.get("price_source_mode"),
        "variant_match": item.get("variant_match"),
    }
    return score, detail

def build_row(item, anchors, events=None, rank=None):
    out = dict(item)
    score, detail = decision_score(item, anchors, events)
    out["decision_score"] = score
    out["score_detail"] = detail
    out["rank"] = rank
    out["prediction_time"] = iso(now_jst())
    out["available_at"] = item.get("available_at")
    out["pit_valid"] = False if not item.get("available_at") else bool(
        parse_dt(item.get("available_at")) and
        parse_dt(item.get("available_at")) <= parse_dt(out["prediction_time"])
    )
    return out
