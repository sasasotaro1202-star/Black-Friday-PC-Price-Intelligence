import json
import math
import os
import re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _initial_budget_settings():
    """Read explicit all-in budget settings once at process start."""
    path = os.path.join(ROOT, "config", "targets.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    try:
        total = int(cfg.get("total_budget_jpy", 370000))
        peripherals = int(cfg.get("peripheral_budget_jpy", 49800))
        pc_cap = int(cfg.get("pc_budget_jpy", total - peripherals))
        pc_target = int(cfg.get("pc_target_jpy", min(317800, pc_cap)))
    except (TypeError, ValueError):
        total, peripherals, pc_cap, pc_target = 370000, 49800, 320200, 317800
    if min(total, peripherals, pc_cap, pc_target) < 0 or pc_cap + peripherals != total or pc_target > pc_cap:
        total, peripherals, pc_cap, pc_target = 370000, 49800, 320200, 317800
    return total, peripherals, pc_target, pc_cap

TOTAL_BUDGET, PERIPHERAL_BUDGET, BUDGET, PC_BUDGET = _initial_budget_settings()
EFFECTIVE_BUDGET = BUDGET
EFFECTIVE_SOFT_MAX = BUDGET
EFFECTIVE_HARD_MAX = PC_BUDGET
CASH_REFERENCE_MAX = PC_BUDGET
MINIMUM_RAM_GB = 32
MINIMUM_SSD_GB = 1000
MAX_TRACKED_PRICE = 900000
ACTIONABLE_MAX_AGE_NORMAL_MINUTES = 60
ACTIONABLE_MAX_AGE_BF_MINUTES = 30

GPU_POINTS = {
    "rtx 5090": 25,
    "rtx 5080": 23,
    "rtx 5070 ti": 21,
    "rx 7900 xtx": 22,
    "rtx 5070": 17,
    "rx 9070 xt": 20,
    "rx 9070": 18,
    "rtx 5060 ti": 11,
    "rx 9060 xt": 14,
    "rtx 5060": 8,
    "rx 9060": 7,
    "rx 9050": 6,
    "rx 7800 xt": 16,
    "rx 7700 xt": 13,
}

GPU_FLOORS = {
    "rtx 5090": 300000,
    "rtx 5080": 240000,
    "rtx 5070 ti": 180000,
    "rx 7900 xtx": 240000,
    "rtx 5070": 150000,
    "rx 9070 xt": 160000,
    "rx 9070": 150000,
    "rtx 5060 ti": 120000,
    "rx 9060 xt": 110000,
    "rtx 5060": 100000,
    "rx 9060": 90000,
    "rx 9050": 80000,
    "rx 7800 xt": 140000,
    "rx 7700 xt": 120000,
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
    ("core ultra 7", 9),
    ("270k plus", 10),
    ("14700f", 10),
    ("ryzen 9", 9),
    ("ryzen 7 9700x", 10),
    ("ryzen 7 7700", 7),
    ("7800x3d", 11),
    ("9800x3d", 12),
    ("ryzen 5 4500", 4),
]

GPU_ORDER = (
    "rtx 5090",
    "rtx 5080",
    "rx 7900 xtx",
    "rtx 5070 ti",
    "rx 9070 xt",
    "rtx 5070",
    "rx 9070",
    "rtx 5060 ti",
    "rx 7800 xt",
    "rx 7700 xt",
    "rx 9060 xt",
    "rtx 5060",
    "rx 9060",
    "rx 9050",
)

PRICE_EXCLUDE_CONTEXT = (
    "月額", "月々", "分割", "円/月", "円／月", "1回", "２４回",
    "24回", "36回", "48回", "ポイント還元", "ポイント付与",
    "通常価格", "定価", "参考価格", "メーカー希望", "上限",
    "割引額", "値引き額", "円引き", "off", "ＯＦＦ", "discount",
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

def purchase_budget_policy():
    cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    peripherals = [x for x in (cfg.get("peripherals") or []) if isinstance(x, dict)]
    return {
        "total_budget_jpy": int(cfg.get("total_budget_jpy", TOTAL_BUDGET)),
        "peripheral_budget_jpy": int(cfg.get("peripheral_budget_jpy", PERIPHERAL_BUDGET)),
        "pc_target_jpy": int(cfg.get("pc_target_jpy", BUDGET)),
        "pc_budget_jpy": int(cfg.get("pc_budget_jpy", PC_BUDGET)),
        "minimum_ram_gb": int(cfg.get("minimum_ram_gb", MINIMUM_RAM_GB)),
        "minimum_ssd_gb": int(cfg.get("minimum_ssd_gb", MINIMUM_SSD_GB)),
        "desktop_preferred": bool(cfg.get("desktop_preferred", True)),
        "peripherals": peripherals,
    }

def _ssd_capacity_gb(value):
    text = norm_text(value).replace(",", "")
    tb = re.search(r"([0-9]+(?:[.][0-9]+)?)\s*tb", text, re.I)
    if tb:
        try:
            return int(float(tb.group(1)) * 1000)
        except (TypeError, ValueError):
            return 0
    gb = re.search(r"([0-9]+)\s*gb", text, re.I)
    if gb:
        try:
            return int(gb.group(1))
        except (TypeError, ValueError):
            return 0
    return 0

def configuration_readiness(item):
    policy = purchase_budget_policy()
    spec = item.get("spec") or item.get("parsed_spec") or {}
    try:
        ram = int(spec.get("ram_gb") or 0)
    except (TypeError, ValueError):
        ram = 0
    ssd_gb = _ssd_capacity_gb(spec.get("ssd") or "")
    reasons = []
    if ram < policy["minimum_ram_gb"]:
        reasons.append(f"RAM {ram}GB<{policy['minimum_ram_gb']}GB")
    if ssd_gb < policy["minimum_ssd_gb"]:
        reasons.append(f"SSD {ssd_gb}GB<{policy['minimum_ssd_gb']}GB")
    return not reasons, reasons

def peripheral_budget_projection():
    """Use live verified accessory prices when available; otherwise use target reserves."""
    policy = purchase_budget_policy()
    snapshot = load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {})
    snapshot_time = parse_dt(snapshot.get("generated_at"))
    now = now_jst()
    max_age = actionable_max_age_minutes(now)
    snapshot_fresh = bool(snapshot_time and 0 <= (now - snapshot_time).total_seconds() / 60.0 <= max_age)
    by_id = {str(x.get("id")): x for x in (snapshot.get("products") or []) if isinstance(x, dict) and x.get("id")}
    rows, total_projection, observed_total, unverified = [], 0, 0, []
    tracked = [p for p in policy["peripherals"] if p.get("track_current_price")]
    for target in policy["peripherals"]:
        if not target.get("mandatory", True):
            continue
        pid = str(target.get("id") or "")
        target_price = int(target.get("target_price_jpy") or 0)
        live = by_id.get(pid, {})
        price = live.get("current_price_jpy")
        stock = live.get("stock_status", "unknown")
        valid = bool(target.get("track_current_price") and live.get("price_verified")
                     and isinstance(price, int) and price > 0
                     and stock in ("in_stock", "low_stock") and snapshot_fresh)
        if valid:
            selected_cost = price
            observed_total += price
        else:
            selected_cost = target_price
            if target.get("track_current_price"):
                unverified.append(pid)
        total_projection += selected_cost
        rows.append({
            "id": pid, "name": target.get("name"), "target_price_jpy": target_price,
            "current_price_jpy": price if live.get("price_verified") else None,
            "stock_status": stock, "price_verified": bool(live.get("price_verified")),
            "budget_cost_jpy": selected_cost,
            "cost_basis": "observed_verified" if valid else "target_reserve_unverified",
            "purchase_url": target.get("purchase_url") or target.get("monitor_url"),
            "track_current_price": bool(target.get("track_current_price")),
        })
    cap = max(0, min(policy["pc_budget_jpy"], policy["total_budget_jpy"] - total_projection))
    return {
        "total_budget_jpy": policy["total_budget_jpy"], "peripheral_target_budget_jpy": policy["peripheral_budget_jpy"],
        "peripheral_projection_jpy": total_projection, "observed_verified_peripheral_total_jpy": observed_total,
        "pc_target_jpy": policy["pc_target_jpy"], "pc_planned_cap_jpy": policy["pc_budget_jpy"],
        "pc_dynamic_cap_jpy": cap, "snapshot_generated_at": snapshot.get("generated_at"),
        "snapshot_fresh": snapshot_fresh, "tracked_peripheral_count": len(tracked),
        "tracked_peripheral_verified_count": len(tracked) - len(set(unverified)),
        "tracked_peripheral_unverified_ids": sorted(set(unverified)),
        "budget_data_ready": bool(snapshot_fresh and not unverified and len(tracked) > 0),
        "peripherals": rows,
    }

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
    s = s.replace("radeon ", "")
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
    expected_form = norm_text(exp.get("form_factor"))
    parsed_cpu = norm_text(parsed.get("cpu"))
    parsed_gpu = normalize_gpu(parsed.get("gpu"))
    parsed_form = norm_text(parsed.get("form_factor"))
    cpu_conflict = bool(expected_cpu and parsed_cpu and expected_cpu not in parsed_cpu and parsed_cpu not in expected_cpu)
    gpu_conflict = bool(expected_gpu and parsed_gpu and normalize_gpu(expected_gpu) != parsed_gpu)
    form_conflict = bool(expected_form and parsed_form and expected_form != parsed_form)
    numeric_conflicts = []
    for key in ("tgp_w", "ram_gb", "vram_gb"):
        ev, pv = exp.get(key), parsed.get(key)
        if ev not in (None, "") and pv not in (None, ""):
            try:
                if int(ev) != int(pv):
                    numeric_conflicts.append(key)
            except Exception:
                pass
    ssd_conflict = bool(
        exp.get("ssd") and parsed.get("ssd") and
        norm_text(exp.get("ssd")).replace(" ", "") != norm_text(parsed.get("ssd")).replace(" ", "")
    )
    contradiction = cpu_conflict or gpu_conflict or form_conflict or bool(numeric_conflicts) or ssd_conflict
    cpu_ok = bool(expected_cpu and expected_cpu in blob)
    gpu_ok = bool(expected_gpu and normalize_gpu(expected_gpu) == gpu_key(item)) if expected_gpu else True
    form_ok = bool(not expected_form or not parsed_form or expected_form == parsed_form)
    if contradiction:
        variant = "ambiguous"
    elif exact_url and (cpu_ok and gpu_ok and form_ok):
        variant = "exact"
    elif exact_url and (cat.get("identity_confidence") == "high"):
        variant = "trusted_url"
    elif cpu_ok and gpu_ok and form_ok:
        variant = "strong"
    elif expected_gpu and normalize_gpu(expected_gpu) == gpu_key(item):
        variant = "gpu_only"
    else:
        variant = "ambiguous"
    if contradiction:
        out["variant_ambiguity_reason"] = "parsed_spec_contradicts_catalog"
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

def is_discount_amount_context(context, matched_text):
    c = norm_text(context)
    m = norm_text(matched_text)
    if re.search(r'¥?\s*' + re.escape(m) + r'\s*(?:円)?\s*(?:off|オフ|引き|円引き)', c, re.I):
        return True
    if re.search(r'(?:割引|値引き)\D{0,12}¥?\s*' + re.escape(m), c, re.I):
        return True
    return False

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
            if is_discount_amount_context(context, m.group(1)):
                score -= 60
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

def _int_or_none(value):
    try:
        if value in (None, ""):
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None

def cash_total_cost(item):
    price = _int_or_none(item.get("current_price_jpy"))
    if price is None:
        return None
    total = price
    for key in ("shipping_jpy", "mandatory_fee_jpy", "mandatory_fees_jpy"):
        value = _int_or_none(item.get(key))
        if value is not None and value >= 0:
            total += value
    return total

def confirmed_benefit_value(item):
    value = _int_or_none(
        item.get("confirmed_benefit_value_jpy")
        if item.get("confirmed_benefit_value_jpy") is not None
        else item.get("confirmed_cash_equivalent_benefit_jpy")
    )
    if value is None or value < 0:
        return 0
    confidence = norm_text(item.get("benefit_confidence") or "")
    if confidence not in ("confirmed", "verified", "high"):
        return 0
    return value

def effective_cost(item):
    cash = cash_total_cost(item)
    if cash is None:
        return None

    explicit = _int_or_none(item.get("effective_cost_jpy"))
    basis = norm_text(item.get("effective_cost_basis") or "")
    if explicit is not None and basis in ("confirmed", "verified"):
        return max(0, explicit)

    return max(0, cash - confirmed_benefit_value(item))

def noncash_benefit_value_jpy(item):
    """Stated non-cash benefit value for comparison only.

    This is never subtracted from the cash/effective cost. Only explicitly
    stated, confirmed bundle/configuration values are included.
    """
    total = 0
    for signal in item.get("benefit_signals") or []:
        if signal.get("certainty") != "confirmed":
            continue
        if signal.get("counts_toward_effective_cost"):
            continue
        if signal.get("kind") == "accessory_stated_value_jpy":
            value = _int_or_none(signal.get("value_jpy") or signal.get("value"))
            if value and value > 0:
                total += min(value, 150000)
    return min(total, 200000)

def value_equivalent_cost(item):
    """Reference-only value-equivalent cost; never used for purchase authorization.

    It subtracts only independently confirmed non-cash bundle/configuration value
    from the cash/effective cost. This is intentionally separate from effective_cost
    to prevent free peripherals or service value from masking the cash price.
    """
    eff = effective_cost(item)
    if eff is None:
        return None
    return max(0, eff - noncash_benefit_value_jpy(item))

def bundle_value_score(item):
    """Small ranking bonus for confirmed non-cash desktop/laptop bundle value."""
    signals = item.get("benefit_signals") or []
    stated = noncash_benefit_value_jpy(item)
    score = 0
    if stated >= 100000:
        score += 4
    elif stated >= 60000:
        score += 3
    elif stated >= 30000:
        score += 2
    elif stated >= 15000:
        score += 1

    if any(
        x.get("kind") == "accessory_bundle_percent"
        and x.get("certainty") == "confirmed"
        and int(x.get("value") or 0) >= 20
        for x in signals
    ):
        score += 1

    if any(
        x.get("kind") == "configuration_upgrade"
        and x.get("certainty") == "confirmed"
        for x in signals
    ):
        score += 1

    if any(
        x.get("kind") == "warranty_or_support_value"
        and x.get("certainty") == "confirmed"
        for x in signals
    ):
        score += 1

    if any(
        x.get("kind") == "included_peripheral"
        and x.get("certainty") == "confirmed"
        for x in signals
    ):
        score += 1

    return min(score, 5)

def price_value_score(item):
    """Price score plus a capped non-cash bundle-value bonus, max 20."""
    base = price_score(effective_cost(item))
    return min(20, base + bundle_value_score(item))

def required_discount(price, target=BUDGET):
    if not price or price <= 0:
        return None
    return max(0.0, (price - target) / float(price) * 100.0)

def required_effective_discount(item):
    eff = effective_cost(item)
    if eff is None:
        return None
    return required_discount(eff, EFFECTIVE_BUDGET)

def scenario_prices(price, target=BUDGET):
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

def actionable_max_age_minutes(now=None):
    now = now or now_jst()
    return ACTIONABLE_MAX_AGE_BF_MINUTES if season_phase(now) != "通常監視期間" else ACTIONABLE_MAX_AGE_NORMAL_MINUTES

def timing_score(item, now=None):
    price = effective_cost(item)
    d = required_discount(price, EFFECTIVE_BUDGET)
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
        f"PC目標価格 ¥{EFFECTIVE_BUDGET:,} 以下。次の値下げより在庫確保を優先" if d <= 0 else
        f"PC目標価格を超過。周辺機器の現行価格と総予算を再確認" if price <= EFFECTIVE_HARD_MAX else
        f"PC本体上限 ¥{EFFECTIVE_HARD_MAX:,} 超。大幅値下げが必要"
    )
    return base, guidance

def performance_score(item):
    g = gpu_key(item)
    gp = GPU_POINTS.get(g, 0)
    cp = cpu_key(item)
    spec = item.get("spec") or {}
    form_factor = norm_text(item.get("form_factor") or spec.get("form_factor"))
    tgp = int(spec.get("tgp_w") or 0)
    ram = int(spec.get("ram_gb") or 0)
    vram = int(spec.get("vram_gb") or 0)
    ssd = str(spec.get("ssd") or "")
    ram_bonus = 2 if ram >= 32 else 1 if ram >= 24 else 0
    ssd_bonus = 2 if re.search(r"1\s*TB", ssd, re.I) else 1 if re.search(r"[2-9]\s*TB", ssd, re.I) else 0
    tgp_bonus = 4 if tgp >= 130 else 3 if tgp >= 115 else 2 if tgp >= 100 else 0
    vram_bonus = 2 if vram >= 16 else 1 if vram >= 12 else 0
    desktop_bonus = 2 if form_factor == "desktop" and g else 0
    psu = int(spec.get("psu_w") or item.get("psu_w") or 0)
    cooler = norm_text(spec.get("cooler") or item.get("cooler"))
    desktop_hardware_bonus = 0
    if form_factor == "desktop":
        if psu >= 750:
            desktop_hardware_bonus += 1
        if re.search(r"(?:liquid|水冷)", cooler, re.I):
            desktop_hardware_bonus += 1
    return min(40, gp + cp + ram_bonus + ssd_bonus + tgp_bonus + vram_bonus + desktop_bonus + desktop_hardware_bonus), g

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
        cap = min(cap, 84)
    if variant == "ambiguous":
        cap = min(cap, 74)
    elif variant == "gpu_only":
        cap = min(cap, 82)
    if mode in ("search_snippet", "direct_meta"):
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
    cash_total = cash_total_cost(item)
    eff = effective_cost(item)
    prediction = item.get("prediction_time")
    available = item.get("available_at")
    retrieval = item.get("retrieval_time")
    available_dt = parse_dt(available)
    retrieval_dt = parse_dt(retrieval)
    prediction_dt = parse_dt(prediction)
    max_age = actionable_max_age_minutes(prediction_dt or now_jst())
    observation_age = None
    if retrieval_dt is not None and prediction_dt is not None:
        observation_age = (prediction_dt - retrieval_dt).total_seconds() / 60.0
    pit_invalid = (
        available_dt is None or retrieval_dt is None or prediction_dt is None
        or available_dt > retrieval_dt or retrieval_dt > prediction_dt
        or observation_age is None or observation_age < -5 or observation_age > max_age
    )
    if (
        price is None
        or eff is None
        or item.get("price_validation_status") in (None, "missing", "anomaly_rejected", "reference_only", "variant_ambiguous")
        or pit_invalid
    ):
        reason = "current_price_not_verified"
        if observation_age is not None and observation_age > max_age:
            reason = "stale_observation"
        elif retrieval_dt is None:
            reason = "retrieval_time_missing"
        elif available_dt is not None and available_dt > retrieval_dt:
            reason = "available_after_retrieval"
        elif retrieval_dt is not None and prediction_dt is not None and retrieval_dt > prediction_dt:
            reason = "retrieval_after_prediction"
        return None, {
            "status": "UNACTIONABLE",
            "reason": reason,
            "performance": 0,
            "price": 0,
            "history": 0,
            "stock": 0,
            "timing": 0,
            "score_cap": 0,
            "observation_age_minutes": round(observation_age, 1) if observation_age is not None else None,
            "max_actionable_age_minutes": max_age,
        }

    budget_projection = peripheral_budget_projection()
    dynamic_pc_cap = budget_projection["pc_dynamic_cap_jpy"]
    dynamic_soft_max = min(EFFECTIVE_SOFT_MAX, dynamic_pc_cap)
    config_ready, config_reasons = configuration_readiness(item)

    perf, gpu = performance_score(item)
    ps_base = price_score(eff)
    value_bonus = bundle_value_score(item)
    ps = min(20, ps_base + value_bonus)
    hs, matched = history_score(item, anchors)
    ss = stock_score(item, anchors)
    ts, guidance = timing_score(item, prediction_dt)
    trend = price_trend(item, events)
    total = min(100, perf + ps + hs + ss + ts)
    cap = data_quality_cap(item)
    score = min(total, cap)
    wr = wait_risk(item, trend)

    status = "WATCH"
    direct_verified = item.get("price_source_mode") == "direct_structured"
    identity_verified = item.get("variant_match") in ("exact", "trusted_url", "strong")
    stock_known = item.get("stock_status") in ("in_stock", "low_stock")
    if item.get("stock_status") == "out_of_stock":
        status = "UNAVAILABLE"
    elif item.get("price_source_mode") in ("search_snippet", "public_baseline", "stale_previous", "direct_text", "direct_meta"):
        status = "VERIFY_NOW"
    elif not config_ready:
        status = "NEEDS_CONFIGURATION"
    elif eff <= dynamic_soft_max and direct_verified and identity_verified and stock_known and score >= 90:
        status = "BUY_NOW"
    elif dynamic_soft_max < eff <= dynamic_pc_cap and direct_verified and identity_verified and item.get("stock_status") == "in_stock" and score >= 94 and perf >= 38:
        status = "BUY_NOW_NEAR_BUDGET"
    elif eff <= dynamic_soft_max and direct_verified and identity_verified and item.get("stock_status") == "low_stock" and score >= 85:
        status = "BUY_NOW_LOW_STOCK"
    elif (
        eff > dynamic_pc_cap
        and item.get("form_factor") == "desktop"
        and perf >= 30
        and value_bonus >= 2
        and eff <= 450000
    ):
        status = "VALUE_WATCH"
    elif eff > dynamic_pc_cap:
        status = "WAIT_FOR_DISCOUNT"
    elif score >= 85:
        status = "STRONG_WATCH"

    reason_bits = [
        f"現金支払 ¥{cash_total:,}" if cash_total is not None else "現金支払額未確認",
        f"実質コスト ¥{eff:,}" if eff is not None else "実質コスト未確認",
        f"特典・構成価値 ¥{noncash_benefit_value_jpy(item):,} / 加点 {value_bonus}",
        (
            f"PC目標価格 ¥{EFFECTIVE_BUDGET:,} まで必要値下げ {required_effective_discount(item):.1f}%"
            if config_ready and required_effective_discount(item) is not None and eff > EFFECTIVE_BUDGET
            else "完成構成未確認のため必要値下げ率未算出" if not config_ready
            else "PC目標価格内"
        ),
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
        "price_base": ps_base,
        "value_bonus": value_bonus,
        "noncash_benefit_value_jpy": noncash_benefit_value_jpy(item),
        "history": hs,
        "stock": ss,
        "timing": ts,
        "gpu": gpu,
        "required_discount_pct": round(required_discount(price), 1),
        "required_effective_discount_pct": (
            round(required_effective_discount(item), 1)
            if config_ready and required_effective_discount(item) is not None else None
        ),
        "discount_comparable_to_completed_build": config_ready,
        "cash_total_cost_jpy": cash_total,
        "confirmed_benefit_value_jpy": confirmed_benefit_value(item),
        "noncash_benefit_value_jpy": noncash_benefit_value_jpy(item),
        "bundle_value_score": value_bonus,
        "effective_cost_jpy": eff,
        "benefit_confidence": item.get("benefit_confidence"),
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
        "observation_age_minutes": round(observation_age, 1) if observation_age is not None else None,
        "max_actionable_age_minutes": max_age,
        "configuration_ready": config_ready,
        "configuration_reasons": config_reasons,
        "total_budget_jpy": budget_projection["total_budget_jpy"],
        "peripheral_projection_jpy": budget_projection["peripheral_projection_jpy"],
        "pc_dynamic_cap_jpy": dynamic_pc_cap,
        "budget_data_ready": budget_projection["budget_data_ready"],
        "peripheral_unverified_ids": budget_projection["tracked_peripheral_unverified_ids"],
    }
    return score, detail

def build_row(item, anchors, events=None, rank=None, prediction_time=None):
    out = dict(item)
    out["prediction_time"] = prediction_time or iso(now_jst())
    score, detail = decision_score(out, anchors, events)
    out["decision_score"] = score
    out["score_detail"] = detail
    out["rank"] = rank
    out["available_at"] = item.get("available_at")
    av = parse_dt(item.get("available_at"))
    rt = parse_dt(item.get("retrieval_time"))
    pr = parse_dt(out["prediction_time"])
    out["pit_valid"] = bool(av and rt and pr and av <= rt <= pr)
    return out
