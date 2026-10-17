import json
import math
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _initial_budget_settings():
    """Read the total ceiling, a soft peripheral reference, and the dynamic PC ceiling."""
    path = os.path.join(ROOT, "config", "targets.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    try:
        total = int(cfg.get("total_budget_jpy", 400000))
        peripherals = int(cfg.get("peripheral_budget_jpy", 35000))
        pc_cap = int(cfg.get("pc_budget_jpy", 395000))
        pc_target = int(cfg.get("pc_target_jpy", min(360000, pc_cap)))
        contingency = int(cfg.get("unallocated_contingency_jpy", max(0, total - peripherals - pc_cap)))
        mode = str(cfg.get("peripheral_budget_mode") or "").upper()
        dynamic_peripherals = mode == "DYNAMIC_WITHIN_TOTAL_SYSTEM_BUDGET" or cfg.get("peripheral_budget_is_hard_cap") is False
    except (TypeError, ValueError):
        total, peripherals, pc_cap, pc_target, contingency, dynamic_peripherals = 400000, 35000, 395000, 360000, 5000, True
    invalid = (
        min(total, peripherals, pc_cap, pc_target, contingency) < 0
        or pc_target > pc_cap
        or (pc_cap + contingency > total if dynamic_peripherals else pc_cap + peripherals + contingency != total)
    )
    if invalid:
        total, peripherals, pc_cap, pc_target, contingency, dynamic_peripherals = 400000, 35000, 395000, 360000, 5000, True
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

# Navigation facets such as "価格から探す 300,001円～" describe a filter
# boundary, not the price of the requested SKU. Never promote such numbers to
# current-price evidence, even when they look numerically plausible.
PRICE_NAVIGATION_CONTEXT = (
    "価格から探す",
    "価格から絞り込む",
    "価格帯から探す",
    "価格帯から絞り込む",
    "価格で絞り込む",
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
        "peripheral_budget_mode": str(cfg.get("peripheral_budget_mode") or "FIXED_TARGET_BUDGET"),
        "peripheral_budget_is_hard_cap": bool(cfg.get("peripheral_budget_is_hard_cap", True)),
        "pc_target_jpy": int(cfg.get("pc_target_jpy", BUDGET)),
        "pc_budget_jpy": int(cfg.get("pc_budget_jpy", PC_BUDGET)),
        "unallocated_contingency_jpy": int(cfg.get("unallocated_contingency_jpy", 0)),
        "minimum_ram_gb": int(cfg.get("minimum_ram_gb", MINIMUM_RAM_GB)),
        "minimum_ssd_gb": int(cfg.get("minimum_ssd_gb", MINIMUM_SSD_GB)),
        "desktop_preferred": bool(cfg.get("desktop_preferred", True)),
        "peripherals": peripherals,
        "purchase_timing_policy": cfg.get("purchase_timing_policy") or {},
    }

def early_buy_review_assessment(
    item_id, observed_price_jpy=None, price_verified=False, identity_verified=False,
    stock_status="unknown", pit_valid=False, checkout_total_verified=False,
    estimated_checkout_total_jpy=None, verified_checkout_total_jpy=None,
):
    """Return a cautious early-buy review signal; this function never authorizes purchase."""
    policy = purchase_budget_policy().get("purchase_timing_policy") or {}
    thresholds = policy.get("early_buy_thresholds_jpy") or {}
    threshold = thresholds.get(str(item_id))
    valid_observed_price = isinstance(observed_price_jpy, int) and not isinstance(observed_price_jpy, bool) and observed_price_jpy > 0
    valid_estimated_total = isinstance(estimated_checkout_total_jpy, int) and not isinstance(estimated_checkout_total_jpy, bool) and estimated_checkout_total_jpy > 0
    valid_verified_total = isinstance(verified_checkout_total_jpy, int) and not isinstance(verified_checkout_total_jpy, bool) and verified_checkout_total_jpy > 0
    checkout_total_is_verified = bool(checkout_total_verified is True and valid_verified_total)
    result = {
        "item_id": str(item_id),
        "early_buy_threshold_jpy": int(threshold) if isinstance(threshold, int) and not isinstance(threshold, bool) else None,
        "observed_price_jpy": observed_price_jpy if valid_observed_price else None,
        "estimated_checkout_total_jpy": estimated_checkout_total_jpy if valid_estimated_total else None,
        "verified_checkout_total_jpy": verified_checkout_total_jpy if checkout_total_is_verified else None,
        "checkout_total_verified": checkout_total_is_verified,
        "price_verified": bool(price_verified is True and valid_observed_price),
        "identity_verified": bool(identity_verified is True),
        "stock_status": stock_status if stock_status in ("in_stock", "low_stock", "out_of_stock", "unknown", "preorder_or_backorder") else "unknown",
        "pit_valid": bool(pit_valid is True),
        "status": "NOT_CONFIGURED",
        "label_ja": "前倒し購入基準なし",
        "purchase_authorized": False,
        "next_step": "ブラックフライデー目標で監視を継続",
    }
    if result["early_buy_threshold_jpy"] is None or result["early_buy_threshold_jpy"] <= 0:
        return result
    if not isinstance(observed_price_jpy, int) or isinstance(observed_price_jpy, bool) or observed_price_jpy <= 0 or not price_verified:
        result.update(status="PRICE_NOT_VERIFIED", label_ja="価格未検証", next_step="直接価格と送料・必須費用を確認")
        return result
    if not identity_verified:
        result.update(status="IDENTITY_NOT_VERIFIED", label_ja="型番未検証", next_step="正確な型番・容量・仕様を確認")
        return result
    if not pit_valid:
        result.update(status="PIT_NOT_VERIFIED", label_ja="取得時刻未検証", next_step="新しい取得時刻・価格の有効時刻を再確認")
        return result
    if stock_status == "out_of_stock":
        result.update(status="UNAVAILABLE", label_ja="在庫切れ", next_step="同一型番の別販売店・再入荷を確認")
        return result
    if stock_status not in ("in_stock", "low_stock"):
        result.update(status="STOCK_NOT_VERIFIED", label_ja="在庫未確認", next_step="購入可能な在庫を直接確認")
        return result
    threshold_jpy = result["early_buy_threshold_jpy"]
    if observed_price_jpy > threshold_jpy:
        gap = observed_price_jpy - threshold_jpy
        result.update(
            status="WAIT_FOR_EARLY_BUY_THRESHOLD",
            label_ja="前倒し購入価格に未到達",
            price_gap_to_threshold_jpy=gap,
            next_step=f"前倒し検討価格まであと{gap:,}円。ブラックフライデーを含め監視継続",
        )
        return result
    if not checkout_total_is_verified:
        result.update(
            status="PRICE_TRIGGERED_CHECKOUT_REVIEW",
            label_ja="前倒し候補：決済総額確認待ち",
            next_step="送料込みの決済総額・保証・返品条件・互換性・全体予算を確認",
        )
        return result
    result.update(
        status="EARLY_BUY_REVIEW_ONLY",
        label_ja="前倒し候補：総額・返品条件の最終確認",
        next_step="40万円総額・保証/返品・互換性を人手で最終確認。自動購入許可は出さない",
    )
    return result

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

def validate_live_store_inventory(target, live, now=None):
    """Validate branch stock evidence independently of cash price evidence."""
    channel_options = target.get("purchase_channel_options") or []
    supports_store_route = (
        target.get("purchase_channel") in ("physical_store", "compare_online_and_store")
        or "physical_store" in channel_options
        or "store_pickup" in channel_options
    )
    required = bool(
        supports_store_route
        and target.get("store_inventory_required_before_purchase")
    )
    empty = {
        "store_inventory_status": "unknown",
        "store_inventory_verified": False,
        "store_inventory_checked_at": None,
        "store_inventory_source_url": None,
        "store_inventory_store_id": None,
        "store_inventory_store_name": None,
        "store_inventory_evidence_notes": None,
        "store_inventory_age_minutes": None,
        "store_inventory_store_ids_available": [],
        "store_inventory_observations": [],
    }
    if not required:
        return empty
    current = parse_dt(now) if isinstance(now, str) else now
    current = current or now_jst()
    max_age = actionable_max_age_minutes(current)
    candidate_ids = {str(x) for x in (target.get("physical_store_candidate_ids") or [])}
    checks = {
        (str(x.get("store_id") or ""), str(x.get("url") or "")): x
        for x in (target.get("store_inventory_checks") or [])
        if isinstance(x, dict)
    }
    cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    store_rows = (cfg.get("purchase_channels") or {}).get("physical_store_candidates") or []
    stores = {str(x.get("id")): x for x in store_rows if isinstance(x, dict) and x.get("id")}
    status_order = {"in_stock": 0, "low_stock": 1, "preorder_or_backorder": 2, "unknown": 3, "out_of_stock": 4}
    valid = []
    for obs in live.get("store_inventory_observations") or []:
        if not isinstance(obs, dict):
            continue
        store_id = str(obs.get("store_id") or "")
        check_url = str(obs.get("check_url") or "")
        check = checks.get((store_id, check_url))
        store = stores.get(store_id)
        source_url = str(obs.get("source_url") or "")
        source = urlparse(source_url)
        checked = parse_dt(obs.get("checked_at"))
        age_minutes = (current - checked).total_seconds() / 60.0 if checked else None
        check_hosts = [str(x).lower() for x in (check or {}).get("allowed_hosts", [])]
        official_host = urlparse(str((store or {}).get("official_store_url") or "")).netloc.lower()
        page_host_ok = bool(
            source.scheme == "https"
            and source.netloc.lower() in check_hosts
            and source.netloc.lower() == official_host
        )
        status = str(obs.get("status") or "unknown")
        if (
            not check
            or store_id not in candidate_ids
            or not store
            or not page_host_ok
            or obs.get("verified") is not True
            or obs.get("branch_match") is not True
            or obs.get("model_match") is not True
            or checked is None
            or age_minutes is None
            or age_minutes < 0
            or age_minutes > max_age
            or status not in status_order
        ):
            continue
        valid.append({
            "store_id": store_id,
            "store_name": str(obs.get("store_name") or (store or {}).get("name") or store_id),
            "checked_at": str(obs.get("checked_at")),
            "source_url": source_url,
            "status": status,
            "evidence_notes": str(obs.get("evidence_notes") or ""),
            "age_minutes": round(age_minutes, 1),
        })
    available_ids = sorted({x["store_id"] for x in valid if x["status"] in ("in_stock", "low_stock")})
    if not valid:
        return empty
    # Prefer an explicitly available branch. Never infer out-of-stock from a missing page/row.
    valid.sort(key=lambda x: status_order.get(x["status"], 3))
    usable = [x for x in valid if x["status"] != "unknown"]
    chosen = usable[0] if usable else valid[0]
    return {
        "store_inventory_status": chosen["status"],
        "store_inventory_verified": chosen["status"] != "unknown",
        "store_inventory_checked_at": chosen["checked_at"],
        "store_inventory_source_url": chosen["source_url"],
        "store_inventory_store_id": chosen["store_id"],
        "store_inventory_store_name": chosen["store_name"],
        "store_inventory_evidence_notes": chosen["evidence_notes"],
        "store_inventory_age_minutes": chosen["age_minutes"],
        "store_inventory_store_ids_available": available_ids,
        "store_inventory_observations": valid,
    }


def store_observation_validation(target, now=None):
    """Validate each physical branch's cash price independently and fail closed.

    Multiple branches may have different shelf prices or stock. A single summary
    row is retained for compatibility, while store_price_observations preserves
    branch-specific evidence so one store's stock is never paired with another
    store's price.
    """
    channel_options = target.get("purchase_channel_options") or []
    supports_store_route = (
        target.get("purchase_channel") in ("physical_store", "compare_online_and_store")
        or "physical_store" in channel_options
        or "store_pickup" in channel_options
    )
    required = bool(
        supports_store_route
        and target.get("store_inventory_required_before_purchase")
    )
    empty = {
        "store_price_jpy": None,
        "store_price_checked_at": None,
        "store_price_confirmed": False,
        "store_stock_status": "unknown" if required else None,
        "store_confirmation_url": None,
        "store_model_match": False,
        "store_observation_store_id": None,
        "store_evidence_type": None,
        "store_evidence_notes": None,
        "store_observation_status": "UNCONFIRMED" if required else "NOT_REQUIRED",
        "store_observation_age_minutes": None,
        "store_price_observations": [],
        "store_price_observation_count": 0,
        "store_price_verified_store_ids": [],
    }
    if not required:
        return empty

    current = parse_dt(now) if isinstance(now, str) else now
    current = current or now_jst()
    cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    configured_stores = (
        (cfg.get("purchase_channels") or {}).get("physical_store_candidates") or []
    )
    stores_by_id = {
        str(item.get("id")): item
        for item in configured_stores
        if isinstance(item, dict) and item.get("id")
    }
    candidate_ids = {str(x) for x in (target.get("physical_store_candidate_ids") or [])}
    allowed_evidence_types = {
        "in_store_check",
        "store_phone_confirmation",
        "official_branch_stock_page",
        "official_branch_price_page",
    }
    max_age = actionable_max_age_minutes(current)

    raw_observations = target.get("store_price_observations")
    observations = list(raw_observations) if isinstance(raw_observations, list) else []
    # Backward compatibility for existing single-branch fields. Do not manufacture
    # a legacy observation from the default unknown-stock marker alone.
    legacy_keys = (
        "store_price_jpy", "store_price_checked_at", "store_confirmation_url",
        "store_observation_store_id", "store_evidence_type", "store_evidence_notes",
        "store_model_match",
    )
    legacy_present = any(target.get(key) not in (None, "") for key in legacy_keys)
    if not observations and legacy_present:
        observations = [{
            "store_id": target.get("store_observation_store_id"),
            "price_jpy": target.get("store_price_jpy"),
            "checked_at": target.get("store_price_checked_at"),
            "stock_status": target.get("store_stock_status") or "unknown",
            "confirmation_url": target.get("store_confirmation_url"),
            "model_match": target.get("store_model_match") is True,
            "evidence_type": target.get("store_evidence_type"),
            "evidence_notes": target.get("store_evidence_notes"),
            "_legacy_single_branch": True,
        }]

    checked_rows = []
    for raw in observations:
        if not isinstance(raw, dict):
            checked_rows.append({
                "store_observation_store_id": None, "store_name": None, "store_price_jpy": None,
                "store_price_checked_at": None, "store_stock_status": "unknown",
                "store_confirmation_url": None, "store_model_match": False,
                "store_evidence_type": None, "store_evidence_notes": None,
                "store_observation_status": "OBSERVATION_NOT_AN_OBJECT",
                "store_observation_age_minutes": None, "store_price_confirmed": False,
            })
            continue

        store_id = str(raw.get("store_id") or raw.get("store_observation_store_id") or "")
        store = stores_by_id.get(store_id)
        price = raw.get("price_jpy", raw.get("store_price_jpy"))
        checked_raw = raw.get("checked_at", raw.get("store_price_checked_at"))
        checked = parse_dt(checked_raw)
        age_minutes = (current - checked).total_seconds() / 60.0 if checked else None
        evidence_type = str(raw.get("evidence_type") or raw.get("store_evidence_type") or "")
        evidence_notes = str(raw.get("evidence_notes") or raw.get("store_evidence_notes") or "").strip()
        confirmation_url = str(raw.get("confirmation_url") or raw.get("store_confirmation_url") or "")
        stock = str(raw.get("stock_status") or raw.get("store_stock_status") or "unknown")
        model_match = raw.get("model_match", raw.get("store_model_match")) is True
        price_basis = str(raw.get("price_basis") or "")
        official_store_url = str((store or {}).get("official_store_url") or "")
        expected_host = urlparse(official_store_url).netloc.lower()
        source = urlparse(confirmation_url)
        source_host_matches = bool(
            confirmation_url
            and source.scheme == "https"
            and source.netloc
            and expected_host
            and source.netloc.lower() == expected_host
        )

        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            reason = "MISSING_OR_INVALID_PRICE"
        elif checked is None or age_minutes is None:
            reason = "MISSING_OR_INVALID_TIMESTAMP"
        elif age_minutes < 0 or age_minutes > max_age:
            reason = "FUTURE_OR_STALE"
        elif not store or store_id not in candidate_ids:
            reason = "BRANCH_UNVERIFIED"
        elif evidence_type not in allowed_evidence_types:
            reason = "EVIDENCE_TYPE_UNVERIFIED"
        elif not evidence_notes:
            reason = "EVIDENCE_NOTES_MISSING"
        elif not model_match:
            reason = "EXACT_MODEL_UNVERIFIED"
        elif not source_host_matches:
            reason = "SOURCE_URL_UNVERIFIED"
        elif not raw.get("_legacy_single_branch") and price_basis != "tax_inclusive_cash":
            reason = "PRICE_BASIS_UNVERIFIED"
        else:
            reason = "PRICE_VERIFIED"

        verified = reason == "PRICE_VERIFIED"
        valid_stock = stock if stock in {
            "in_stock", "low_stock", "out_of_stock", "unknown", "preorder_or_backorder"
        } else "unknown"
        checked_rows.append({
            "store_observation_store_id": store_id or None,
            "store_name": str((store or {}).get("name") or store_id or "") or None,
            "store_price_jpy": int(price) if verified else None,
            "store_price_checked_at": str(checked_raw) if verified else None,
            "store_stock_status": valid_stock if verified else "unknown",
            "store_confirmation_url": confirmation_url if verified else None,
            "store_model_match": bool(model_match and verified),
            "store_evidence_type": evidence_type if verified else None,
            "store_evidence_notes": evidence_notes if verified else None,
            "store_observation_status": reason,
            "store_observation_age_minutes": round(age_minutes, 1) if verified else None,
            "store_price_confirmed": verified,
            "price_basis": price_basis or ("legacy_untyped_cash_quote" if raw.get("_legacy_single_branch") else None),
        })

    stock_priority = {
        "in_stock": 0, "low_stock": 1, "unknown": 2,
        "preorder_or_backorder": 3, "out_of_stock": 4,
    }
    verified_rows = [row for row in checked_rows if row.get("store_price_confirmed")]
    verified_rows.sort(key=lambda row: (
        stock_priority.get(str(row.get("store_stock_status") or "unknown"), 2),
        int(row.get("store_price_jpy") or 10**12),
        -(float(row.get("store_observation_age_minutes") or 0)),
        str(row.get("store_observation_store_id") or ""),
    ))
    empty["store_price_observations"] = checked_rows
    empty["store_price_observation_count"] = len(checked_rows)
    empty["store_price_verified_store_ids"] = sorted({
        str(row["store_observation_store_id"])
        for row in verified_rows if row.get("store_observation_store_id")
    })
    if not verified_rows:
        invalid = next((row for row in checked_rows if row.get("store_observation_status")), None)
        if invalid:
            empty["store_observation_status"] = invalid["store_observation_status"]
        elif required:
            empty["store_observation_status"] = "MISSING_OR_INVALID_PRICE"
        return empty

    chosen = verified_rows[0]
    return {
        "store_price_jpy": chosen["store_price_jpy"],
        "store_price_checked_at": chosen["store_price_checked_at"],
        "store_price_confirmed": True,
        "store_stock_status": chosen["store_stock_status"],
        "store_confirmation_url": chosen["store_confirmation_url"],
        "store_model_match": chosen["store_model_match"],
        "store_observation_store_id": chosen["store_observation_store_id"],
        "store_evidence_type": chosen["store_evidence_type"],
        "store_evidence_notes": chosen["store_evidence_notes"],
        "store_observation_status": chosen["store_observation_status"],
        "store_observation_age_minutes": chosen["store_observation_age_minutes"],
        "store_price_observations": checked_rows,
        "store_price_observation_count": len(checked_rows),
        "store_price_verified_store_ids": empty["store_price_verified_store_ids"],
    }



def store_pickup_quote_validation(target, now=None):
    """Validate an exact item/variant's checkout total when online-ordered for branch pickup.

    The regular web listing price and a branch inventory result are not a pickup
    checkout quote. A quote must separately record the final cash total, branch,
    checked-at time, exact-model match, evidence note and official retailer URL.
    """
    options = target.get("purchase_channel_options") or []
    required = "store_pickup" in options
    empty = {
        "store_pickup_checkout_total_jpy": None,
        "store_pickup_checkout_total_confirmed": False,
        "store_pickup_route_actionable": False,
        "store_pickup_stock_status": "unknown",
        "store_pickup_store_id": None,
        "store_pickup_checkout_url": None,
        "store_pickup_evidence_type": None,
        "store_pickup_evidence_notes": None,
        "store_pickup_quote_status": "UNCONFIRMED" if required else "NOT_REQUIRED",
        "store_pickup_quote_age_minutes": None,
    }
    if not required:
        return empty

    current = parse_dt(now) if isinstance(now, str) else now
    current = current or now_jst()
    price = target.get("store_pickup_checkout_total_jpy")
    checkout_total_attested = target.get("store_pickup_checkout_total_verified") is True
    checked_raw = target.get("store_pickup_quote_checked_at")
    checked = parse_dt(checked_raw)
    age_minutes = (current - checked).total_seconds() / 60.0 if checked else None
    store_id = str(target.get("store_pickup_store_id") or "")
    candidate_ids = {str(x) for x in (target.get("physical_store_candidate_ids") or [])}
    store_cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    store_rows = (store_cfg.get("purchase_channels") or {}).get("physical_store_candidates") or []
    stores_by_id = {str(x.get("id")): x for x in store_rows if isinstance(x, dict) and x.get("id")}
    store = stores_by_id.get(store_id)
    evidence_type = str(target.get("store_pickup_evidence_type") or "")
    evidence_notes = str(target.get("store_pickup_evidence_notes") or "").strip()
    confirmation_url = str(target.get("store_pickup_checkout_url") or "")
    model_match = target.get("store_pickup_model_match") is True
    stock = str(target.get("store_pickup_stock_status") or "unknown")
    source = urlparse(confirmation_url)
    expected_host = urlparse(str((store or {}).get("official_store_url") or "")).netloc.lower()
    target_allowed_hosts = {str(x).lower() for x in (target.get("allowed_hosts") or [])}
    source_host_matches = bool(
        confirmation_url and source.scheme == "https" and source.netloc
        and source.netloc.lower() == expected_host
        and source.netloc.lower() in target_allowed_hosts
    )
    allowed_evidence_types = {
        "online_checkout_with_store_pickup",
        "official_online_pickup_quote",
        "store_pickup_checkout_screen",
    }
    max_age = actionable_max_age_minutes(current)

    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        reason = "PICKUP_CHECKOUT_TOTAL_MISSING_OR_INVALID"
    elif not checkout_total_attested:
        reason = "PICKUP_CHECKOUT_TOTAL_NOT_ATTESTED"
    elif checked is None or age_minutes is None:
        reason = "PICKUP_QUOTE_TIMESTAMP_MISSING_OR_INVALID"
    elif age_minutes < 0 or age_minutes > max_age:
        reason = "PICKUP_QUOTE_FUTURE_OR_STALE"
    elif not store or store_id not in candidate_ids:
        reason = "PICKUP_BRANCH_UNVERIFIED"
    elif evidence_type not in allowed_evidence_types:
        reason = "PICKUP_EVIDENCE_TYPE_UNVERIFIED"
    elif not evidence_notes:
        reason = "PICKUP_EVIDENCE_NOTES_MISSING"
    elif not model_match:
        reason = "PICKUP_EXACT_MODEL_UNVERIFIED"
    elif stock not in ("in_stock", "low_stock", "out_of_stock"):
        reason = "PICKUP_STOCK_UNVERIFIED"
    elif not source_host_matches:
        reason = "PICKUP_CHECKOUT_URL_UNVERIFIED"
    else:
        reason = "PICKUP_QUOTE_VERIFIED"

    verified = reason == "PICKUP_QUOTE_VERIFIED"
    return {
        "store_pickup_checkout_total_jpy": int(price) if verified else None,
        "store_pickup_checkout_total_confirmed": verified,
        "store_pickup_route_actionable": bool(verified and stock in ("in_stock", "low_stock")),
        "store_pickup_stock_status": stock if verified else "unknown",
        "store_pickup_store_id": store_id if verified else None,
        "store_pickup_checkout_url": confirmation_url if verified else None,
        "store_pickup_evidence_type": evidence_type if verified else None,
        "store_pickup_evidence_notes": evidence_notes if verified else None,
        "store_pickup_quote_status": reason,
        "store_pickup_quote_age_minutes": round(age_minutes, 1) if verified else None,
    }


def peripheral_budget_projection():
    """Compare actionable online, in-store and store-pickup routes per exact peripheral.

    Online listings are never labelled as store cash prices. If the local-store offer
    is still unverified, a valid in-stock online offer can still be used as a
    purchase option, but the overall cheapest-channel comparison remains pending.
    """
    policy = purchase_budget_policy()
    snapshot = load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {})
    snapshot_time = parse_dt(snapshot.get("generated_at"))
    now = now_jst()
    max_age = actionable_max_age_minutes(now)
    snapshot_fresh = bool(snapshot_time and 0 <= (now - snapshot_time).total_seconds() / 60.0 <= max_age)
    by_id = {str(x.get("id")): x for x in (snapshot.get("products") or []) if isinstance(x, dict) and x.get("id")}
    rows, total_projection, observed_total, unverified = [], 0, 0, []
    channel_pending = []
    tracked = [p for p in policy["peripherals"] if p.get("track_current_price")]

    def valid_money(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def stocked(value):
        return value in ("in_stock", "low_stock")

    for target in policy["peripherals"]:
        if not target.get("mandatory", True):
            continue
        pid = str(target.get("id") or "")
        target_price = int(target.get("target_price_jpy") or 0)
        live = by_id.get(pid, {})
        price = live.get("current_price_jpy")
        online_stock = live.get("stock_status", "unknown")
        identity_matches = bool(
            str(live.get("name") or "").strip()
            and str(live.get("name") or "").strip() == str(target.get("name") or "").strip()
        )
        online_price_verified = bool(
            target.get("track_current_price") and identity_matches and live.get("price_verified")
            and isinstance(price, int) and not isinstance(price, bool) and price > 0
            and snapshot_fresh and live.get("identity_verified", True)
        )

        channel_options = set(target.get("purchase_channel_options") or [])
        compare_channels = bool(
            target.get("purchase_channel") == "compare_online_and_store"
            or ("online" in channel_options and bool({"physical_store", "store_pickup"} & channel_options))
        )
        store_route = bool(
            target.get("purchase_channel") == "physical_store"
            or compare_channels
            or "physical_store" in channel_options
            or "store_pickup" in channel_options
        )
        online_shipping_reserve = int(target.get("online_shipping_reserve_jpy") or 0)
        actual_shipping = live.get("online_shipping_jpy")
        shipping_verified = bool(
            live.get("online_shipping_cost_verified") is True
            and valid_money(actual_shipping)
        )
        estimated_shipping = int(actual_shipping) if shipping_verified else online_shipping_reserve
        online_cash_estimate = int(price) + estimated_shipping if online_price_verified else None
        online_route_actionable = bool(online_price_verified and stocked(online_stock))

        store_observation = store_observation_validation(target, now)
        live_store_inventory = validate_live_store_inventory(target, live, now) if store_route else {
            "store_inventory_status": "unknown", "store_inventory_verified": False,
            "store_inventory_checked_at": None, "store_inventory_source_url": None,
            "store_inventory_store_id": None, "store_inventory_store_name": None,
            "store_inventory_evidence_notes": None, "store_inventory_age_minutes": None,
            "store_inventory_store_ids_available": [],
        }
        # Reconcile cash quotes and stock only within the same named branch.
        # A lower price at one branch must never inherit another branch's stock.
        store_price_observations = [
            dict(row) for row in (store_observation.get("store_price_observations") or [])
            if isinstance(row, dict) and row.get("store_price_confirmed") is True
            and valid_money(row.get("store_price_jpy")) and row.get("store_model_match") is True
        ]
        inventory_by_store = {
            str(row.get("store_id")): row
            for row in (live_store_inventory.get("store_inventory_observations") or [])
            if isinstance(row, dict) and row.get("store_id")
        }
        for quote in store_price_observations:
            quote_store_id = str(quote.get("store_observation_store_id") or "")
            quote_stock = quote.get("store_stock_status") or "unknown"
            inventory = inventory_by_store.get(quote_store_id)
            if quote_stock not in ("in_stock", "low_stock") and inventory:
                branch_status = inventory.get("status")
                if inventory.get("status") in ("in_stock", "low_stock"):
                    quote["store_stock_status"] = branch_status
                    quote["stock_evidence_source_url"] = inventory.get("source_url")
                    quote["stock_evidence_checked_at"] = inventory.get("checked_at")

        stocked_quotes = [
            quote for quote in store_price_observations
            if quote.get("store_stock_status") in ("in_stock", "low_stock")
        ]
        stock_priority = {"in_stock": 0, "low_stock": 1, "unknown": 2,
                          "preorder_or_backorder": 3, "out_of_stock": 4}
        if stocked_quotes:
            chosen_store_quote = min(
                stocked_quotes,
                key=lambda quote: (
                    int(quote.get("store_price_jpy") or 10**12),
                    stock_priority.get(quote.get("store_stock_status"), 2),
                    str(quote.get("store_observation_store_id") or ""),
                ),
            )
        elif store_price_observations:
            chosen_store_quote = min(
                store_price_observations,
                key=lambda quote: (
                    stock_priority.get(quote.get("store_stock_status") or "unknown", 2),
                    int(quote.get("store_price_jpy") or 10**12),
                    str(quote.get("store_observation_store_id") or ""),
                ),
            )
        else:
            chosen_store_quote = None

        store_price = (
            chosen_store_quote.get("store_price_jpy") if chosen_store_quote
            else store_observation["store_price_jpy"]
        )
        store_checked_at = (
            chosen_store_quote.get("store_price_checked_at") if chosen_store_quote
            else store_observation["store_price_checked_at"]
        )
        store_stock = (
            chosen_store_quote.get("store_stock_status") if chosen_store_quote
            else store_observation["store_stock_status"]
        )
        store_url = (
            chosen_store_quote.get("store_confirmation_url") if chosen_store_quote
            else store_observation["store_confirmation_url"]
        )
        store_model_match = (
            chosen_store_quote.get("store_model_match") if chosen_store_quote
            else store_observation["store_model_match"]
        )
        store_price_verified = bool(
            chosen_store_quote.get("store_price_confirmed") if chosen_store_quote
            else store_observation["store_price_confirmed"]
        )
        store_observation_store_id = (
            chosen_store_quote.get("store_observation_store_id") if chosen_store_quote
            else store_observation.get("store_observation_store_id")
        )
        store_route_actionable = bool(store_price_verified and stocked(store_stock))
        store_route_known = bool(
            store_price_verified
            and store_stock in ("in_stock", "low_stock", "out_of_stock", "preorder_or_backorder")
        )
        store_pickup_observation = store_pickup_quote_validation(target, now)
        store_pickup_price = store_pickup_observation["store_pickup_checkout_total_jpy"]
        store_pickup_stock = store_pickup_observation["store_pickup_stock_status"]
        store_pickup_quote_confirmed = bool(store_pickup_observation["store_pickup_checkout_total_confirmed"])
        store_pickup_route_actionable = bool(store_pickup_observation["store_pickup_route_actionable"])
        store_pickup_route_known = bool(
            store_pickup_quote_confirmed
            and store_pickup_stock in ("in_stock", "low_stock", "out_of_stock")
        )
        online_route_known = bool(
            online_price_verified
            and (
                online_stock == "out_of_stock"
                or (stocked(online_stock) and shipping_verified)
            )
        )

        if compare_channels:
            channel_options_available = []
            if online_route_actionable:
                channel_options_available.append({
                    "channel": "online", "cash_total_jpy": int(online_cash_estimate),
                    "stock_status": online_stock,
                    "shipping_jpy": estimated_shipping,
                    "shipping_verified": shipping_verified,
                    "url": live.get("online_best_offer_url") or live.get("purchase_url") or target.get("purchase_url") or target.get("monitor_url"),
                })
            if store_route_actionable:
                channel_options_available.append({
                    "channel": "physical_store", "cash_total_jpy": int(store_price),
                    "stock_status": store_stock, "shipping_jpy": 0,
                    "shipping_verified": True,
                    "url": store_url,
                    "store_id": store_observation.get("store_observation_store_id"),
                })
            if store_pickup_route_actionable:
                channel_options_available.append({
                    "channel": "store_pickup", "cash_total_jpy": int(store_pickup_price),
                    "stock_status": store_pickup_stock, "shipping_jpy": 0,
                    "shipping_verified": True,
                    "url": store_pickup_observation.get("store_pickup_checkout_url"),
                    "store_id": store_pickup_observation.get("store_pickup_store_id"),
                })
            channel_comparison_complete = bool(
                online_route_known and store_route_known and store_pickup_route_known
            )
            if not channel_comparison_complete:
                channel_pending.append(pid)
            if channel_options_available:
                chosen = min(channel_options_available, key=lambda x: (
                    int(x["cash_total_jpy"]),
                    0 if x["channel"] == "online" and x["shipping_verified"] else 1,
                    str(x.get("url") or ""),
                ))
                selected_cost = int(chosen["cash_total_jpy"])
                exposed_price = int(price) if online_price_verified else None
                exposed_price_verified = bool(online_route_actionable)
                stock = chosen["stock_status"]
                cost_basis = "verified_channel_choice_" + chosen["channel"]
                purchase_channel_selected = chosen["channel"]
                if chosen["channel"] == "physical_store":
                    observed_total += int(store_price)
                elif chosen["channel"] == "store_pickup":
                    observed_total += int(store_pickup_price)
                else:
                    observed_total += int(online_cash_estimate)
                if not channel_comparison_complete:
                    channel_status = {
                        "online": "ONLINE_ROUTE_SELECTED_OTHER_ROUTES_PENDING",
                        "physical_store": "STORE_CASH_ROUTE_SELECTED_OTHER_ROUTES_PENDING",
                        "store_pickup": "STORE_PICKUP_ROUTE_SELECTED_OTHER_ROUTES_PENDING",
                    }[chosen["channel"]]
                else:
                    channel_status = "ALL_PURCHASE_ROUTES_VERIFIED"
            elif online_price_verified or store_price_verified or store_pickup_quote_confirmed:
                route_estimates = []
                if online_price_verified:
                    route_estimates.append(int(online_cash_estimate))
                if store_price_verified and valid_money(store_price):
                    route_estimates.append(int(store_price))
                if store_pickup_quote_confirmed and store_pickup_stock in ("in_stock", "low_stock"):
                    route_estimates.append(int(store_pickup_price))
                selected_cost = max(target_price, min(route_estimates)) if route_estimates else target_price
                exposed_price = int(price) if online_price_verified else None
                exposed_price_verified = False
                stock = "unknown"
                purchase_channel_selected = "unconfirmed"
                cost_basis = "price_only_stock_or_route_unconfirmed"
                channel_status = "NO_ACTIONABLE_CHANNEL"
                unverified.append(pid)
            else:
                selected_cost = target_price
                exposed_price = None
                exposed_price_verified = False
                stock = "unknown"
                purchase_channel_selected = "unconfirmed"
                cost_basis = "target_reserve_unverified"
                channel_status = "NO_VERIFIED_PRICE_OR_STOCK"
                unverified.append(pid)
            online_comparison_price = int(price) if online_price_verified else None
            online_price_is_comparison_only = False
        elif target.get("purchase_channel") == "physical_store" and target.get("store_inventory_required_before_purchase"):
            stock = store_stock if store_price_verified else (
                live_store_inventory["store_inventory_status"] if live_store_inventory.get("store_inventory_verified") else "unknown"
            )
            if store_price_verified and stocked(stock):
                selected_cost = int(store_price)
                exposed_price = int(store_price)
                exposed_price_verified = True
                cost_basis = "verified_store_price_stock_confirmed"
                observed_total += int(store_price)
            else:
                price_plus_shipping = int(online_cash_estimate) if online_cash_estimate is not None else target_price
                selected_cost = max(target_price, price_plus_shipping)
                exposed_price = None
                exposed_price_verified = False
                cost_basis = "online_reference_store_price_unconfirmed" if online_price_verified else "target_reserve_store_price_unconfirmed"
                unverified.append(pid)
            purchase_channel_selected = "physical_store" if store_price_verified and stocked(stock) else "unconfirmed"
            channel_comparison_complete = False
            channel_status = "LEGACY_STORE_ONLY_PRICE_OR_STOCK_UNCONFIRMED" if purchase_channel_selected == "unconfirmed" else "STORE_PRICE_VERIFIED"
            online_comparison_price = int(price) if online_price_verified else None
            online_price_is_comparison_only = True
            channel_pending.append(pid)
        else:
            # Online-only and conditional-need items. Include a shipping estimate
            # unless the listing proves the final shipping cost; do not treat the
            # BF target as a verified offer.
            if online_route_actionable:
                selected_cost = int(online_cash_estimate)
                exposed_price = int(price)
                exposed_price_verified = True
                cost_basis = "observed_online_cash_total_estimate"
                observed_total += int(online_cash_estimate)
                stock = online_stock
            elif online_price_verified:
                selected_cost = max(target_price, int(online_cash_estimate))
                exposed_price = int(price)
                exposed_price_verified = True
                cost_basis = "observed_price_stock_unconfirmed"
                stock = online_stock
                unverified.append(pid)
            else:
                selected_cost = target_price
                exposed_price = None
                exposed_price_verified = False
                cost_basis = "target_reserve_unverified"
                stock = "unknown"
                if target.get("track_current_price"):
                    unverified.append(pid)
            purchase_channel_selected = "online" if online_route_actionable else "unconfirmed"
            channel_comparison_complete = True
            channel_status = "ONLINE_VERIFIED" if online_route_actionable else "ONLINE_PRICE_OR_STOCK_UNCONFIRMED"
            online_comparison_price = int(price) if online_price_verified else None
            online_price_is_comparison_only = False

        if target.get("requires_exact_model_before_purchase"):
            exact_model_selected = bool(
                str(target.get("model_code") or "").strip()
                and str(target.get("name") or "").strip()
                and list(target.get("identity_terms") or [])
            )
            if not exact_model_selected:
                unverified.append(pid)

        online_shipping_in_budget = 0
        if online_price_verified and online_cash_estimate is not None:
            if purchase_channel_selected == "online" or (
                purchase_channel_selected == "unconfirmed"
                and selected_cost == online_cash_estimate
            ):
                online_shipping_in_budget = estimated_shipping

        total_projection += selected_cost
        # A listed product price, an estimated delivered total, and a verified checkout total are different facts.
        early_observed_price = None
        early_estimated_total = None
        early_verified_total = None
        early_price_verified = False
        early_identity_verified = False
        early_stock_status = "unknown"
        early_pit_valid = False
        early_checkout_verified = False
        if purchase_channel_selected == "online" or (purchase_channel_selected == "unconfirmed" and online_price_verified):
            early_observed_price = price if online_price_verified else None
            early_estimated_total = online_cash_estimate if online_price_verified else None
            early_price_verified = bool(online_price_verified)
            early_identity_verified = bool(identity_matches and live.get("identity_verified", True))
            early_stock_status = online_stock
            available_dt = parse_dt(live.get("available_at"))
            retrieval_dt = parse_dt(live.get("retrieval_time"))
            early_pit_valid = bool(
                snapshot_fresh and available_dt is not None and retrieval_dt is not None
                and available_dt <= retrieval_dt <= now
            )
            early_checkout_verified = bool(online_route_actionable and shipping_verified)
            early_verified_total = online_cash_estimate if early_checkout_verified else None
        elif purchase_channel_selected == "physical_store":
            early_observed_price = store_price if valid_money(store_price) else None
            early_estimated_total = store_price if valid_money(store_price) else None
            early_price_verified = bool(store_price_verified)
            early_identity_verified = bool(store_model_match)
            early_stock_status = store_stock
            store_dt = parse_dt(store_checked_at)
            early_pit_valid = bool(
                store_dt is not None and 0 <= (now - store_dt).total_seconds() / 60.0 <= max_age
            )
            early_checkout_verified = bool(store_route_actionable)
            early_verified_total = store_price if early_checkout_verified and valid_money(store_price) else None
        elif purchase_channel_selected == "store_pickup":
            early_observed_price = store_pickup_price if valid_money(store_pickup_price) else None
            early_estimated_total = store_pickup_price if valid_money(store_pickup_price) else None
            early_price_verified = bool(store_pickup_quote_confirmed)
            early_identity_verified = bool(store_pickup_quote_confirmed)
            early_stock_status = store_pickup_stock
            early_pit_valid = bool(
                store_pickup_quote_confirmed
                and store_pickup_observation.get("store_pickup_quote_age_minutes") is not None
            )
            early_checkout_verified = bool(store_pickup_route_actionable)
            early_verified_total = store_pickup_price if early_checkout_verified and valid_money(store_pickup_price) else None
        early_buy_review = early_buy_review_assessment(
            pid,
            observed_price_jpy=early_observed_price,
            price_verified=early_price_verified,
            identity_verified=early_identity_verified,
            stock_status=early_stock_status,
            pit_valid=early_pit_valid,
            checkout_total_verified=early_checkout_verified,
            estimated_checkout_total_jpy=early_estimated_total,
            verified_checkout_total_jpy=early_verified_total,
        )
        rows.append({
            "id": pid, "name": target.get("name"), "target_price_jpy": target_price,
            "early_buy_review": early_buy_review,
            "current_price_jpy": exposed_price, "price_verified": exposed_price_verified,
            "online_comparison_price_jpy": online_comparison_price,
            "online_reference_price_verified": bool(online_price_verified),
            "online_shipping_reserve_jpy": online_shipping_reserve,
            "online_shipping_jpy": int(actual_shipping) if shipping_verified else None,
            "online_shipping_cost_verified": shipping_verified,
            "estimated_online_cash_total_jpy": online_cash_estimate,
            "online_shipping_cost_in_budget_jpy": online_shipping_in_budget,
            "online_offer_count": int(live.get("online_offer_count") or (1 if online_price_verified else 0)),
            "online_actionable_offer_count": int(live.get("online_actionable_offer_count") or (1 if online_route_actionable else 0)),
            "online_best_offer_url": live.get("online_best_offer_url"),
            "store_pickup_checkout_total_jpy": store_pickup_observation["store_pickup_checkout_total_jpy"],
            "store_pickup_checkout_total_confirmed": store_pickup_quote_confirmed,
            "store_pickup_route_actionable": store_pickup_route_actionable,
            "store_pickup_quote_stock_status": store_pickup_observation["store_pickup_stock_status"],
            "store_pickup_quote_status": store_pickup_observation["store_pickup_quote_status"],
            "store_pickup_checkout_url": store_pickup_observation["store_pickup_checkout_url"],
            "store_pickup_store_id": store_pickup_observation["store_pickup_store_id"],
            "store_pickup_evidence_type": store_pickup_observation["store_pickup_evidence_type"],
            "store_pickup_evidence_notes": store_pickup_observation["store_pickup_evidence_notes"],
            "store_pickup_quote_age_minutes": store_pickup_observation["store_pickup_quote_age_minutes"],
            "store_pickup_branch_inventory_status": live_store_inventory["store_inventory_status"],
            "store_pickup_branch_inventory_verified": live_store_inventory["store_inventory_verified"],
            "purchase_channel": target.get("purchase_channel", "online"),
            "purchase_channel_options": target.get("purchase_channel_options") or [],
            "selected_purchase_channel": purchase_channel_selected,
            "channel_comparison_complete": channel_comparison_complete,
            "channel_comparison_status": channel_status,
            "channel_comparison_pending": bool(store_route and not channel_comparison_complete),
            "online_price_is_comparison_only": online_price_is_comparison_only,
            "physical_store_candidate_ids": target.get("physical_store_candidate_ids") or [],
            "store_price_jpy": int(store_price) if store_price_verified else None,
            "store_price_checked_at": store_checked_at if store_price_verified else None,
            "store_price_confirmed": bool(store_price_verified),
            "store_model_match": bool(store_model_match),
            "store_stock_status": store_stock if store_route else None,
            "store_confirmation_url": store_url if store_price_verified else None,
            "store_observation_store_id": store_observation.get("store_observation_store_id"),
            "store_evidence_type": store_observation.get("store_evidence_type"),
            "store_evidence_notes": store_observation.get("store_evidence_notes"),
            "store_observation_status": store_observation.get("store_observation_status"),
            "store_observation_age_minutes": store_observation.get("store_observation_age_minutes"),
            "store_inventory_status": live_store_inventory["store_inventory_status"],
            "store_inventory_verified": live_store_inventory["store_inventory_verified"],
            "store_inventory_checked_at": live_store_inventory["store_inventory_checked_at"],
            "store_inventory_source_url": live_store_inventory["store_inventory_source_url"],
            "store_inventory_store_id": live_store_inventory["store_inventory_store_id"],
            "store_inventory_store_name": live_store_inventory["store_inventory_store_name"],
            "store_inventory_evidence_notes": live_store_inventory["store_inventory_evidence_notes"],
            "store_inventory_age_minutes": live_store_inventory["store_inventory_age_minutes"],
            "store_inventory_store_ids_available": live_store_inventory["store_inventory_store_ids_available"],
            "stock_status": stock, "online_stock_status": online_stock,
            "budget_cost_jpy": selected_cost, "cost_basis": cost_basis,
            "purchase_url": (
                live.get("online_best_offer_url") if purchase_channel_selected == "online"
                else store_url if purchase_channel_selected == "physical_store"
                else store_pickup_observation.get("store_pickup_checkout_url") if purchase_channel_selected == "store_pickup"
                else None
            ) or target.get("purchase_url") or target.get("monitor_url"),
            "track_current_price": bool(target.get("track_current_price")),
        })

    # Shipping reserve is a use of the flexible peripheral reserve, not a second
    # contingency line. Verified shipping replaces the reserve estimate; unverified
    # online delivery uses the configured guard amount until checkout is checked.
    flexible_shipping_buffer_used = sum(
        int(row.get("online_shipping_cost_in_budget_jpy") or 0)
        for row in rows
        if row.get("online_comparison_price_jpy") is not None
    )
    flexible_buffer = next((row for row in rows if row.get("id") == "store_price_buffer"), None)
    flexible_buffer_used = min(
        flexible_shipping_buffer_used,
        int(flexible_buffer.get("budget_cost_jpy") or 0)
    ) if flexible_buffer else 0
    if flexible_buffer and flexible_buffer_used:
        flexible_buffer["budget_cost_jpy"] = max(0, int(flexible_buffer["budget_cost_jpy"]) - flexible_buffer_used)
        flexible_buffer["shipping_reserve_offset_jpy"] = flexible_buffer_used
        total_projection -= flexible_buffer_used
    if flexible_buffer and not flexible_buffer_used:
        flexible_buffer["shipping_reserve_offset_jpy"] = 0

    cap = max(0, min(policy["pc_budget_jpy"], policy["total_budget_jpy"] - total_projection - policy.get("unallocated_contingency_jpy", 0)))
    unverified_ids = set(unverified)
    verified_tracked_count = sum(1 for p in tracked if str(p.get("id") or "") not in unverified_ids)
    channel_comparison_required_ids = {
        str(p.get("id") or "")
        for p in tracked
        if p.get("purchase_channel") == "compare_online_and_store"
        or (
            "online" in (p.get("purchase_channel_options") or [])
            and bool({"physical_store", "store_pickup"} & set(p.get("purchase_channel_options") or []))
        )
    }
    channel_comparison_complete_ids = {
        str(row.get("id") or "")
        for row in rows
        if str(row.get("id") or "") in channel_comparison_required_ids
        and row.get("channel_comparison_complete")
    }
    return {
        "total_budget_jpy": policy["total_budget_jpy"],
        "peripheral_target_budget_jpy": policy["peripheral_budget_jpy"],
        "peripheral_budget_mode": policy["peripheral_budget_mode"],
        "peripheral_budget_is_hard_cap": policy["peripheral_budget_is_hard_cap"],
        "peripheral_projection_jpy": total_projection,
        "observed_verified_peripheral_total_jpy": observed_total,
        "pc_target_jpy": policy["pc_target_jpy"], "pc_planned_cap_jpy": policy["pc_budget_jpy"],
        "pc_dynamic_cap_jpy": cap, "snapshot_generated_at": snapshot.get("generated_at"),
        "snapshot_fresh": snapshot_fresh, "tracked_peripheral_count": len(tracked),
        "tracked_peripheral_verified_count": verified_tracked_count,
        "tracked_peripheral_unverified_ids": sorted(unverified_ids),
        "channel_comparison_pending_ids": sorted(set(channel_pending)),
        "channel_comparison_pending_count": len(set(channel_pending)),
        "online_delivery_cost_reserve_required_jpy": flexible_shipping_buffer_used,
        "online_delivery_cost_absorbed_by_flexible_buffer_jpy": flexible_buffer_used,
        "uncovered_online_delivery_cost_jpy": max(0, flexible_shipping_buffer_used - flexible_buffer_used),
        "flexible_reserve_offset_for_shipping_jpy": flexible_buffer_used,
        "channel_comparison_required_count": len(channel_comparison_required_ids),
        "channel_comparison_complete_count": len(channel_comparison_complete_ids),
        "budget_data_ready": bool(snapshot_fresh and not unverified_ids and len(tracked) > 0),
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
            normalized_context = norm_text(context)
            if any(phrase in normalized_context for phrase in PRICE_NAVIGATION_CONTEXT):
                continue
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
    """Describe the broad watch phase without inferring retailer campaign dates."""
    now = now or now_jst()
    cfg = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    start = parse_dt(cfg.get("monitor_window_start")) or datetime(now.year, 11, 1, tzinfo=JST)
    end = parse_dt(cfg.get("monitor_window_end")) or datetime(now.year, 12, 11, 23, 59, 59, tzinfo=JST)
    if not (start <= now <= end):
        return "通常監視期間"
    # These are only reporting buckets for the broad watch window. They are not
    # claims that any retailer has started a promotion or changed prices.
    if now.month == 11 and now.day < 27:
        return "広域監視前半（各店の公式日程は未確認）"
    if now.month == 11 and now.day <= 30:
        return "Black Friday暦週（各店の公式日程は別確認）"
    return "延長セール観測（各店の公式終了日は別確認）"

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
    # Do not boost a product merely because a speculative calendar bucket says
    # "early sale" or "main sale"; timing is determined from verified price/stock evidence.
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
