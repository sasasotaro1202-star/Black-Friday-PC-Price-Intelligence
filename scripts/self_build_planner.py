"""Build a transparent DIY component plan; never authorize a buy from target/comparison prices."""
import hashlib
import html
import json
import os
import re
from urllib.parse import urlparse
from intelligence import ROOT, now_jst, iso, parse_dt, load_json, save_json

CONFIG_PATH = os.path.join(ROOT, "config", "build_components.json")
PRICE_PATH = os.path.join(ROOT, "data", "build_component_prices.json")
PLAN_PATH = os.path.join(ROOT, "data", "self_build_plan.json")
PLAN_REPORT_PATH = os.path.join(ROOT, "data", "reports", "self-build-ranking.md")
LATEST_REPORT_PATH = os.path.join(ROOT, "data", "reports", "latest.md")
START_MARKER = "<!-- SELF_BUILD_SECTION_START -->"
END_MARKER = "<!-- SELF_BUILD_SECTION_END -->"


def file_sha256(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def money(value):
    return "¥{:,.0f}".format(value) if isinstance(value, (int, float)) else "未確認"


def age_minutes(value, now):
    """Return None for missing or future-dated observations instead of hiding clock/PIT errors."""
    dt = parse_dt(value)
    if dt is None:
        return None
    age = (now - dt).total_seconds() / 60.0
    return age if age >= 0 else None


def trusted_market_reference(row, now, max_age):
    price = row.get("market_reference_price_jpy")
    age = age_minutes(row.get("retrieval_time"), now)
    available = parse_dt(row.get("available_at"))
    retrieved = parse_dt(row.get("retrieval_time"))
    return bool(
        isinstance(price, int) and not isinstance(price, bool) and price > 0
        and row.get("price_validation_status") == "verified_market_reference"
        and row.get("identity_match") is True and row.get("pit_valid") is True
        and row.get("source_role") == "comparison_site_reference"
        and row.get("bf_actual_authorized") is False
        and age is not None and age <= max_age
        and available is not None and retrieved is not None
        and available <= retrieved <= now
    )


def trusted_manual_reference(part, now, max_age):
    """Accept a manually maintained reference only with fresh, explicit evidence."""
    price = part.get("reference_price_jpy")
    checked_at = parse_dt(part.get("reference_price_checked_at"))
    age = age_minutes(part.get("reference_price_checked_at"), now)
    url = str(part.get("reference_price_url") or "")
    return bool(
        isinstance(price, int) and not isinstance(price, bool) and price > 0
        and part.get("price_source_role") == "official_store_manual_reference"
        and part.get("reference_price_is_current_verified") is True
        and part.get("reference_price_identity_verified") is True
        and url.startswith("https://")
        and checked_at is not None and checked_at <= now
        and age is not None and age <= max_age
    )


def trusted_retailer_listing_reference(row, now, max_age, allowed_domains=()):
    """Validate a fresh, directly parsed retailer listing separately from checkout offers."""
    offer = row.get("retailer_listing_offer") if isinstance(row, dict) else None
    price = row.get("retailer_listing_reference_price_jpy") if isinstance(row, dict) else None
    age = age_minutes(row.get("retrieval_time"), now) if isinstance(row, dict) else None
    available = parse_dt(row.get("available_at")) if isinstance(row, dict) else None
    retrieved = parse_dt(row.get("retrieval_time")) if isinstance(row, dict) else None
    offer_available = parse_dt((offer or {}).get("available_at")) if isinstance(offer, dict) else None
    offer_retrieved = parse_dt((offer or {}).get("retrieval_time")) if isinstance(offer, dict) else None
    url = str((offer or {}).get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    domains = tuple(str(x).lower() for x in (allowed_domains or ()))
    host_allowed = bool(host and any(host == d or host.endswith("." + d) for d in domains))
    comparison_host = host == "kakaku.com" or host.endswith(".kakaku.com")
    return bool(
        isinstance(price, int) and not isinstance(price, bool) and price > 0
        and row.get("price_validation_status") == "verified_retailer_listing_reference"
        and row.get("identity_match") is True and row.get("pit_valid") is True
        and row.get("bf_actual_authorized") is False
        and isinstance(offer, dict)
        and offer.get("source_role") == "direct_retailer_listing_reference"
        and offer.get("price_jpy") == price
        and offer.get("identity_match") is True and offer.get("identity_anchor")
        and offer.get("stock_status") == "in_stock"
        and offer.get("bf_actual_authorized") is False
        and offer.get("price_source_mode") in ("direct_structured", "direct_meta", "direct_text")
        and host_allowed and not comparison_host and url.startswith("https://")
        and age is not None and age <= max_age
        and available is not None and retrieved is not None and available <= retrieved <= now
        and offer_available is not None and offer_retrieved is not None
        and offer_available == available and offer_retrieved == retrieved
        and offer_available <= offer_retrieved <= now
    )


def direct_listing_offer_for_display(row, part, now, max_age, allowed_domains=()):
    """Keep fresh, identity-anchored detail-page prices visible when stock blocks trust.

    This is a display-only observation. It is never a trusted market estimate or
    a checkout offer; stock must separately be confirmed before promotion.
    """
    if not isinstance(row, dict):
        return None
    values = []
    raw_offers = [row.get("retailer_listing_offer")] + list(row.get("retailer_listing_offers") or [])
    for offer in raw_offers:
        if not isinstance(offer, dict):
            continue
        price = offer.get("price_jpy")
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            continue
        minimum = int(part.get("min_price_jpy") or 1)
        maximum = int(part.get("max_price_jpy") or 10**9)
        if not minimum <= price <= maximum:
            continue
        if offer.get("source_role") != "direct_retailer_listing_reference":
            continue
        if offer.get("identity_match") is not True or not offer.get("identity_anchor"):
            continue
        identity = re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]+", "", str(offer.get("identity_anchor") or "").lower())
        curated = [
            part.get("model_code"), part.get("name"),
            *(part.get("aliases") or []), *(part.get("identity_terms") or []),
        ]
        curated = {
            re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]+", "", str(term or "").lower())
            for term in curated if term
        }
        if not identity or identity not in curated:
            continue
        if offer.get("bf_actual_authorized") is not False or offer.get("pit_valid") is not True:
            continue
        if offer.get("price_source_mode") not in ("direct_structured", "direct_meta", "direct_text"):
            continue
        url = str(offer.get("url") or "")
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        allowed = tuple(str(domain or "").lower().strip(".") for domain in (allowed_domains or ()))
        if not url.startswith("https://") or not any(host == d or host.endswith("." + d) for d in allowed):
            continue
        if host == "kakaku.com" or host.endswith(".kakaku.com"):
            continue
        available = parse_dt(offer.get("available_at"))
        retrieved = parse_dt(offer.get("retrieval_time"))
        if not available or not retrieved or available > retrieved or retrieved > now:
            continue
        age = (now - retrieved).total_seconds() / 60.0
        if age < 0 or age > max_age:
            continue
        item = dict(offer)
        item["display_age_minutes"] = round(age, 1)
        values.append(item)

    if not values:
        return None
    stock_rank = {
        "in_stock": 0, "low_stock": 1, "preorder_or_backorder": 2,
        "unknown": 3, "out_of_stock": 4,
    }
    values.sort(key=lambda offer: (
        stock_rank.get(str(offer.get("stock_status") or "unknown"), 3),
        0 if offer.get("price_source_mode") == "direct_structured" else 1,
        offer.get("display_age_minutes", 10**9),
        offer.get("price_jpy", 10**12),
    ))
    return values[0]


def direct_listing_stock_label(status):
    return {
        "in_stock": "在庫あり（直接掲載・購入ゲート別）",
        "low_stock": "在庫少（購入ゲート未通過）",
        "preorder_or_backorder": "取寄せ/予約",
        "out_of_stock": "在庫切れ",
        "unknown": "在庫未確認",
    }.get(str(status or "unknown"), "在庫未確認")


def component_price(part, by_id, now, max_age, allowed_domains=()):
    if not part.get("track_price"):
        ref = part.get("reference_price_jpy")
        trusted_manual = trusted_manual_reference(part, now, max_age)
        ref_is_positive = isinstance(ref, int) and not isinstance(ref, bool) and ref > 0
        checked_at = parse_dt(part.get("reference_price_checked_at")) if trusted_manual else None
        return {
            "market_reference_price_jpy": ref if trusted_manual else None,
            "display_reference_price_jpy": ref if ref_is_positive else None,
            "price_status": (
                "verified_manual_reference" if trusted_manual else
                "manual_reference_unverified" if ref_is_positive else "not_tracked"
            ),
            "trusted_for_market_estimate": trusted_manual,
            "source_role": part.get("price_source_role") or "manual_reference",
            "reference_source_url": part.get("reference_price_url") if trusted_manual else None,
            "reference_source_label": (
                "公式ストア手動参照（確認時刻・商品一致を検証）" if trusted_manual else
                "手動記録の参考価格（現行価格・商品一致は未確認）" if ref_is_positive else None
            ),
            "retrieval_time": iso(checked_at) if checked_at else None,
            "reference_age_minutes": age_minutes(part.get("reference_price_checked_at"), now),
            "purchase_url": part.get("reference_price_url") if trusted_manual else None,
            "direct_listing_validation_diagnostics": [],
        }
    row = by_id.get(str(part.get("id") or "")) or {}
    trusted_comparison = trusted_market_reference(row, now, max_age)
    trusted_retailer = trusted_retailer_listing_reference(row, now, max_age, allowed_domains)
    trusted = trusted_comparison or trusted_retailer
    age = age_minutes(row.get("retrieval_time"), now)
    retailer_offer = row.get("retailer_listing_offer") if trusted_retailer else None
    direct_display_offer = (
        direct_listing_offer_for_display(row, part, now, max_age, allowed_domains)
        if not trusted else None
    )
    reference_price = (
        row.get("market_reference_price_jpy") if trusted_comparison
        else row.get("retailer_listing_reference_price_jpy") if trusted_retailer else None
    )
    reference_source_url = (
        (row.get("final_url") or row.get("monitor_url")) if trusted_comparison
        else retailer_offer.get("url") if trusted_retailer else None
    )
    reference_source_role = (
        "comparison_site_reference" if trusted_comparison
        else "direct_retailer_listing_reference" if trusted_retailer
        else "comparison_site_reference"
    )
    snippet_price = row.get("search_snippet_reference_price_jpy")
    direct_diagnostics = []
    for item in (row.get("search_diagnostics") or []):
        if not isinstance(item, dict) or item.get("provider") != "configured_direct_retailer":
            continue
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        direct_diagnostics.append({
            "url": str(item.get("url") or "")[:240] or None,
            "status": str(item.get("status") or "unknown"),
            "reason_code": (
                item.get("error") or validation.get("reason_code")
                or ("exact_identity_direct_price_and_pit_verified" if item.get("status") == "verified" else None)
            ),
            "page_name": str(validation.get("page_name") or "")[:160] or None,
            "price_source_mode": validation.get("price_source_mode"),
            "parsed_price_jpy": validation.get("parsed_price_jpy"),
            "stock_status": item.get("stock_status") or validation.get("stock_status") or "unknown",
            "structured_stock_status": validation.get("structured_stock_status"),
            "text_stock_status": validation.get("text_stock_status"),
            "error_type": validation.get("error_type"),
            "error_message": str(validation.get("error_message") or "")[:180] or None,
        })
    snippet_only = bool(
        not trusted and row.get("price_validation_status") == "search_snippet_reference"
        and row.get("identity_match") is True and row.get("search_snippet_identity_anchor")
        and isinstance(snippet_price, int) and not isinstance(snippet_price, bool) and snippet_price > 0
        and age is not None and age <= max_age
        and row.get("source_role") == "comparison_site_reference"
        and row.get("bf_actual_authorized") is False
    )
    display = reference_price if trusted else snippet_price if snippet_only else None
    status = row.get("price_validation_status") if trusted else (
        "search_snippet_reference_only" if snippet_only else
        "stale_market_reference" if (
            row.get("market_reference_price_jpy") is not None
            or row.get("retailer_listing_reference_price_jpy") is not None
            or isinstance(snippet_price, int)
        )
        else row.get("price_validation_status") or "not_observed"
    )
    return {
        "market_reference_price_jpy": reference_price if trusted else None,
        "display_reference_price_jpy": display,
        "price_status": status,
        "trusted_for_market_estimate": trusted,
        "source_role": reference_source_role,
        "reference_source_url": reference_source_url,
        "reference_source_label": (
            "販売店ページ直接取得・掲載価格（決済未確認）" if trusted_retailer
            else "価格比較サイト参考値" if trusted_comparison else None
        ),
        "retrieval_time": row.get("retrieval_time"),
        "reference_age_minutes": age,
        "purchase_url": reference_source_url or part.get("purchase_url") or part.get("monitor_url"),
        "search_snippet_reference_url": row.get("search_snippet_reference_url") if snippet_only else None,
        "search_snippet_reference_title": row.get("search_snippet_reference_title") if snippet_only else None,
        "direct_listing_display_price_jpy": direct_display_offer.get("price_jpy") if direct_display_offer else None,
        "direct_listing_display_url": direct_display_offer.get("url") if direct_display_offer else None,
        "direct_listing_display_title": (direct_display_offer.get("title") or direct_display_offer.get("identity_anchor")) if direct_display_offer else None,
        "direct_listing_display_identity_anchor": direct_display_offer.get("identity_anchor") if direct_display_offer else None,
        "direct_listing_display_stock_status": (direct_display_offer.get("stock_status") or "unknown") if direct_display_offer else None,
        "direct_listing_display_stock_label": direct_listing_stock_label(direct_display_offer.get("stock_status")) if direct_display_offer else None,
        "direct_listing_display_source_mode": direct_display_offer.get("price_source_mode") if direct_display_offer else None,
        "direct_listing_display_observed_at": direct_display_offer.get("retrieval_time") if direct_display_offer else None,
        "direct_listing_display_age_minutes": direct_display_offer.get("display_age_minutes") if direct_display_offer else None,
        "direct_listing_display_price_context": direct_display_offer.get("price_context") if direct_display_offer else None,
        "direct_listing_display_is_estimate_eligible": False,
        "direct_listing_display_purchase_allowed": False,
        "direct_listing_validation_diagnostics": direct_diagnostics,
    }


def compatibility_checks(parts, profile, gpu_id, memory_part_id=None):
    """Checks known socket/memory/storage/size/power constraints, fail-closed."""
    checks = []
    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    def spec(part_id):
        return (parts.get(part_id) or {}).get("specs") or {}

    cpu = spec("cpu-ryzen7-9700x")
    board = spec("motherboard-asrock-b850m-pro-rs-wifi")
    fixed_ids = profile.get("fixed_part_ids") or []
    memory_part_id = memory_part_id or profile.get("primary_memory_choice_id") or next(
        (
            str(part_id) for part_id in fixed_ids
            if (parts.get(str(part_id)) or {}).get("category") == "memory"
        ),
        "memory-teamgroup-ddr5-32gb-6000",
    )
    memory = spec(memory_part_id)
    storage = spec("ssd-crucial-p3-plus-1tb")
    psu = spec("psu-corsair-rm850e-2025")
    case = spec("case-fractal-pop-air-tg")
    cooler = spec("cooler-thermalright-pa120-se-v3")
    gpu = spec(gpu_id)

    add("cpu_motherboard_socket", "PASS" if cpu.get("socket") and cpu.get("socket") == board.get("socket") else "FAIL",
        "CPU socket {} / board socket {}".format(cpu.get("socket", "unknown"), board.get("socket", "unknown")))

    minimum_bios = board.get("minimum_bios_for_ryzen7_9700x")
    observed_bios = board.get("observed_bios_version")
    cpu_support_verified = board.get("cpu_support_list_verified_for_ryzen7_9700x") is True
    def version_tuple(value):
        pieces = re.findall(r"\d+", str(value or ""))
        return tuple(int(piece) for piece in pieces) if pieces else None
    required_bios_tuple = version_tuple(minimum_bios)
    observed_bios_tuple = version_tuple(observed_bios)
    if not cpu_support_verified or required_bios_tuple is None:
        bios_status = "REVIEW"
        bios_detail = "Exact CPU support-list entry or minimum BIOS version has not been verified from the manufacturer."
    elif observed_bios_tuple is None:
        bios_status = "REVIEW"
        bios_detail = "ASRock support list requires BIOS {}; the exact board's shipped/installed BIOS is unobserved. Verify it and use BIOS Flashback/update if needed.".format(minimum_bios)
    elif observed_bios_tuple < required_bios_tuple:
        bios_status = "REVIEW"
        bios_detail = "Observed BIOS {} is older than the required {}; update before using this CPU.".format(observed_bios, minimum_bios)
    else:
        bios_status = "PASS"
        bios_detail = "Observed BIOS {} meets the manufacturer minimum {} for Ryzen 7 9700X.".format(observed_bios, minimum_bios)
    add("cpu_bios_support", bios_status, bios_detail)

    memory_ok = (
        memory.get("memory_type") == board.get("memory_type")
        and isinstance(memory.get("capacity_gb"), int) and memory["capacity_gb"] >= int(profile.get("minimum_ram_gb", 32))
        and isinstance(memory.get("modules"), int) and memory["modules"] >= int(profile.get("minimum_memory_modules", 2))
    )
    add("memory_type_capacity_dual_channel", "PASS" if memory_ok else "FAIL",
        "DDR type, >= {}GB, >= {} DIMMs".format(profile.get("minimum_ram_gb", 32), profile.get("minimum_memory_modules", 2)))
    qvl_verified = memory.get("qvl_verified_with_asrock_b850m_pro_rs_wifi") is True
    add(
        "memory_qvl",
        "PASS" if qvl_verified else "REVIEW",
        "Exact kit {} QVL entry for ASRock B850M Pro RS WiFi: {}".format(
            memory_part_id,
            "verified" if qvl_verified else "unconfirmed; DDR5/EXPO support alone is not proof of exact-kit QVL compatibility",
        ),
    )
    storage_ok = isinstance(storage.get("capacity_gb"), int) and storage["capacity_gb"] >= int(profile.get("minimum_ssd_gb", 1000)) and "NVMe" in str(storage.get("interface", ""))
    add("storage_capacity_interface", "PASS" if storage_ok else "FAIL",
        "NVMe SSD {}GB / minimum {}GB".format(storage.get("capacity_gb", "unknown"), profile.get("minimum_ssd_gb", 1000)))
    supported = case.get("supported_motherboard_form_factors") or []
    board_form = board.get("form_factor")
    add("motherboard_case_form_factor", "PASS" if board_form and board_form in supported else "FAIL",
        "Board {} / case supports {}".format(board_form or "unknown", ", ".join(supported) or "unknown"))

    gpu_length, gpu_clearance = gpu.get("card_length_mm"), case.get("gpu_clearance_mm")
    if not isinstance(gpu_length, (int, float)) or not isinstance(gpu_clearance, (int, float)):
        add("gpu_case_clearance", "REVIEW", "Exact GPU retail-card length or case clearance must be verified before ordering")
    else:
        add("gpu_case_clearance", "PASS" if gpu_length <= gpu_clearance else "FAIL",
            "GPU {}mm / case limit {}mm".format(gpu_length, gpu_clearance))

    # The case publishes maximum card length but not an explicit thickness-slot
    # limit. Standard 2-slot cards can be planned against the normal expansion
    # layout; near-3-slot cards need a manual adjacent-slot/header/cable clearance
    # check rather than inheriting a PASS from length alone.
    gpu_slots = gpu.get("card_thickness_slots")
    if not isinstance(gpu_slots, (int, float)):
        add("gpu_slot_thickness", "REVIEW", "Exact GPU slot thickness is not source-backed")
    elif gpu_slots > 2.5:
        add("gpu_slot_thickness", "REVIEW",
            "GPU occupies {} slots; confirm case expansion-slot, motherboard-header and cable clearance".format(gpu_slots))
    else:
        add("gpu_slot_thickness", "PASS", "GPU occupies {} slots; no additional adjacent-card requirement is configured".format(gpu_slots))

    sockets = cooler.get("supported_sockets") or []
    cooler_height, case_height = cooler.get("cooler_height_mm"), case.get("cooler_clearance_mm")
    if "AM5" not in sockets:
        add("cooler_socket", "FAIL", "AM5 mounting compatibility not proven")
    else:
        add("cooler_socket", "PASS", "AM5 mounting support declared")
    if not isinstance(cooler_height, int) or not isinstance(case_height, int):
        add("cooler_case_clearance", "REVIEW", "Cooler/case heights are unverified")
    else:
        add("cooler_case_clearance", "PASS" if cooler_height <= case_height else "FAIL",
            "Cooler {}mm / case limit {}mm".format(cooler_height, case_height))

    gpu_psu = gpu.get("minimum_psu_w")
    psu_w = psu.get("wattage_w")
    add("psu_wattage", "PASS" if isinstance(psu_w, int) and isinstance(gpu_psu, int) and psu_w >= gpu_psu else "FAIL",
        "PSU {}W / GPU recommendation {}W".format(psu_w or "unknown", gpu_psu or "unknown"))
    connector = str(gpu.get("connector") or "model_specific")
    if connector == "model_specific":
        add("gpu_power_connector", "REVIEW", "Confirm exact GPU auxiliary connector and included PSU cable against the exact model")
    elif connector == "12V-2x6":
        connector_ok = psu.get("connector_12v2x6") is True
        add("gpu_power_connector", "PASS" if connector_ok else "FAIL",
            "PSU ATX 3.1 native 12V-2x6 cable")
    elif connector in ("8-pin PCIe", "PCIe 8-pin", "8-pin"):
        connector_ok = psu.get("connector_pcie_8pin") is True
        add("gpu_power_connector", "PASS" if connector_ok else "FAIL",
            "PSU PCIe 8-pin (6+2) cable available")
    else:
        add("gpu_power_connector", "REVIEW",
            "Unrecognized GPU connector type {}; verify exact cable and manufacturer requirement".format(connector))
    add("os_license", "PASS" if "os-windows11-home" in parts else "FAIL",
        "Windows 11 Home license budgeted unless an existing transferable license is confirmed")

    statuses = [x["status"] for x in checks]
    overall = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
    return overall, checks


def build_plan(config=None, price_snapshot=None, now=None):
    config = config or load_json(CONFIG_PATH, {})
    profile = config.get("profile") or {}
    parts_list = [x for x in (config.get("parts") or []) if isinstance(x, dict) and x.get("id")]
    parts = {str(x["id"]): x for x in parts_list}
    snapshot = price_snapshot if isinstance(price_snapshot, dict) else load_json(PRICE_PATH, {})
    rows = snapshot.get("products") or []
    by_id = {str(x.get("id")): x for x in rows if isinstance(x, dict) and x.get("id")}
    now = now or now_jst()
    max_age = int(profile.get("market_reference_max_age_minutes", 360))
    fixed_ids = list(profile.get("fixed_part_ids") or [])
    gpu_ids = list(profile.get("gpu_choice_ids") or [])
    memory_choice_ids = [
        str(mid) for mid in (profile.get("memory_choice_ids") or [])
        if str(mid) in parts and (parts[str(mid)].get("category") == "memory")
    ]
    if not memory_choice_ids:
        memory_choice_ids = [
            str(cid) for cid in fixed_ids
            if (parts.get(str(cid)) or {}).get("category") == "memory"
        ]
    # If a new/malformed memory-choice list omits every candidate, retain the
    # configured primary only when its exact part ID exists and is a memory kit.
    # Never produce a complete PC plan with RAM silently omitted.
    if not memory_choice_ids:
        configured_primary_id = str(profile.get("primary_memory_choice_id") or "")
        if configured_primary_id in parts and parts[configured_primary_id].get("category") == "memory":
            memory_choice_ids = [configured_primary_id]
    primary_memory_id = profile.get("primary_memory_choice_id")
    if primary_memory_id not in memory_choice_ids:
        primary_memory_id = memory_choice_ids[0] if memory_choice_ids else None
    fixed_ids = [str(cid) for cid in fixed_ids if str(cid) not in memory_choice_ids]
    allowed_price_domains = profile.get("allowed_search_reference_domains") or profile.get("allowed_comparison_domains") or []
    memory_price_by_id = {}
    memory_candidates = []
    for memory_id in memory_choice_ids:
        memory_part = parts.get(memory_id) or {}
        memory_price = component_price(
            memory_part, by_id, now, max_age, allowed_domains=allowed_price_domains
        )
        memory_price_by_id[memory_id] = memory_price
        trusted = bool(
            memory_price.get("trusted_for_market_estimate")
            and isinstance(memory_price.get("market_reference_price_jpy"), int)
        )
        memory_candidates.append({
            "id": memory_id,
            "name": memory_part.get("name"),
            "model_code": memory_part.get("model_code"),
            "target_price_jpy": memory_part.get("target_price_jpy"),
            "market_reference_price_jpy": memory_price.get("market_reference_price_jpy"),
            "price_status": memory_price.get("price_status"),
            "trusted_for_market_estimate": trusted,
            "purchase_url": memory_price.get("purchase_url") or memory_part.get("purchase_url") or memory_part.get("monitor_url"),
        })
    trusted_memory_candidates = [
        candidate for candidate in memory_candidates
        if candidate["trusted_for_market_estimate"]
        and isinstance(candidate["market_reference_price_jpy"], int)
    ]
    if trusted_memory_candidates:
        chosen_memory = min(
            trusted_memory_candidates,
            key=lambda candidate: (
                candidate["market_reference_price_jpy"],
                candidate["target_price_jpy"] if isinstance(candidate["target_price_jpy"], int) else 10**12,
                candidate["id"],
            ),
        )
        selected_memory_id = chosen_memory["id"]
        memory_selection_method = "lowest_fresh_verified_market_reference"
    else:
        selected_memory_id = primary_memory_id
        memory_selection_method = "primary_memory_fallback_no_verified_market_reference"
    selected_memory = parts.get(selected_memory_id) or {}
    memory_choice_selection = {
        "selected_id": selected_memory_id,
        "selected_name": selected_memory.get("name"),
        "selection_method": memory_selection_method,
        "candidates": memory_candidates,
        "rule": "Choose the lowest fresh, exact-item trusted market reference among available candidates. If no candidate has a trusted reference, retain the memory kit configured as the primary planning fallback. Market references are not checkout prices and never authorize purchase."
    }
    pc_budget = int(profile.get("pc_budget_jpy", 350000))
    all_budget = int(profile.get("total_budget_jpy", 400000))
    peripheral_budget = int(profile.get("peripheral_budget_jpy", 45000))
    shipping = int(profile.get("build_shipping_reserve_jpy", 0))
    small_parts = int(profile.get("small_parts_reserve_jpy", 0))
    builds = []

    for rank, gpu_id in enumerate(gpu_ids, 1):
        selected_ids = fixed_ids + ([selected_memory_id] if selected_memory_id else []) + [gpu_id]
        components, missing, market_subtotal = [], [], 0
        all_parts_referenced = True
        target_parts = 0
        for cid in selected_ids:
            part = parts.get(cid)
            if not part:
                missing.append(cid)
                all_parts_referenced = False
                continue
            target = part.get("target_price_jpy")
            if isinstance(target, int) and not isinstance(target, bool):
                target_parts += target
            price = memory_price_by_id[cid] if cid in memory_price_by_id else component_price(
                part, by_id, now, max_age, allowed_domains=allowed_price_domains
            )
            component = {
                "id": cid, "category": part.get("category"), "name": part.get("name"),
                "model_code": part.get("model_code"), "role": part.get("role"),
                "target_price_jpy": target,
                "market_reference_price_jpy": price["market_reference_price_jpy"],
                "display_reference_price_jpy": price["display_reference_price_jpy"],
                "price_status": price["price_status"],
                "trusted_for_market_estimate": price["trusted_for_market_estimate"],
                "source_role": price["source_role"], "retrieval_time": price["retrieval_time"],
                "reference_age_minutes": price["reference_age_minutes"],
                "monitor_url": part.get("monitor_url"), "purchase_url": price.get("purchase_url") or part.get("purchase_url") or part.get("monitor_url"),
                "reference_source_url": price.get("reference_source_url"),
                "reference_source_label": price.get("reference_source_label"),
                "search_snippet_reference_url": price.get("search_snippet_reference_url"),
                "search_snippet_reference_title": price.get("search_snippet_reference_title"),
                "direct_listing_display_price_jpy": price.get("direct_listing_display_price_jpy"),
                "direct_listing_display_url": price.get("direct_listing_display_url"),
                "direct_listing_display_title": price.get("direct_listing_display_title"),
                "direct_listing_display_identity_anchor": price.get("direct_listing_display_identity_anchor"),
                "direct_listing_display_stock_status": price.get("direct_listing_display_stock_status"),
                "direct_listing_display_stock_label": price.get("direct_listing_display_stock_label"),
                "direct_listing_display_source_mode": price.get("direct_listing_display_source_mode"),
                "direct_listing_display_observed_at": price.get("direct_listing_display_observed_at"),
                "direct_listing_display_age_minutes": price.get("direct_listing_display_age_minutes"),
                "direct_listing_display_price_context": price.get("direct_listing_display_price_context"),
                "direct_listing_validation_diagnostics": price.get("direct_listing_validation_diagnostics") or [],
                "direct_listing_display_is_estimate_eligible": False,
                "direct_listing_display_purchase_allowed": False,
                "track_price": bool(part.get("track_price")), "specs": part.get("specs") or {},
                "image_url": part.get("image_url"), "image_source_url": part.get("image_source_url"),
                "image_note": part.get("image_note"), "image_checked_at": part.get("image_checked_at"),
                "notes": part.get("notes"), "bf_actual_authorized": False
            }
            components.append(component)
            if part.get("track_price"):
                if price["trusted_for_market_estimate"] and isinstance(price["market_reference_price_jpy"], int):
                    market_subtotal += price["market_reference_price_jpy"]
                else:
                    all_parts_referenced = False
                    missing.append(cid)
            else:
                # A configured/manual price remains display-only unless it has
                # a fresh timestamp, exact-item identity evidence, and an HTTPS
                # source URL. Never blend a static sticker price into a live
                # market subtotal.
                if price["trusted_for_market_estimate"] and isinstance(price["market_reference_price_jpy"], int):
                    market_subtotal += price["market_reference_price_jpy"]
                else:
                    all_parts_referenced = False
                    missing.append(cid)

        compat, checks = compatibility_checks(parts, profile, gpu_id, selected_memory_id)
        target_pc = target_parts + shipping + small_parts
        target_all_in = target_pc + peripheral_budget
        market_estimate = market_subtotal + shipping + small_parts if all_parts_referenced and not missing else None
        all_in_market = market_estimate + peripheral_budget if market_estimate is not None else None
        gpu_part = parts.get(gpu_id) or {}
        gpu_live = by_id.get(gpu_id) or {}
        live_gpu_price = gpu_live.get("market_reference_price_jpy")
        gpu_target = gpu_part.get("target_price_jpy")
        reduction = round((live_gpu_price - gpu_target) * 100.0 / live_gpu_price, 1) if isinstance(live_gpu_price, int) and isinstance(gpu_target, int) and live_gpu_price > gpu_target else None

        if compat == "FAIL":
            decision = "BLOCKED_COMPATIBILITY"
        elif target_pc > pc_budget or target_all_in > all_budget:
            decision = "OVER_BUDGET_TARGET"
        elif compat == "REVIEW":
            decision = "WAIT_FOR_COMPATIBILITY_REVIEW"
        elif market_estimate is None:
            decision = "WAIT_FOR_MARKET_REFERENCE"
        else:
            decision = "WAIT_FOR_BF_OFFICIAL_PRICES"
        name = {
            "gpu-rtx5070-12gb": "自作本命：Ryzen 7 9700X + RTX 5070 12GB",
            "gpu-rtx5060ti-16gb": "自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB",
            "gpu-rtx5070ti-16gb": "自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB"
        }.get(gpu_id, "DIY build " + gpu_id)
        builds.append({
            "rank": rank, "id": "self-build-" + gpu_id, "name": name, "gpu_choice_id": gpu_id,
            "selected_memory_id": selected_memory_id,
            "memory_choice_method": memory_selection_method,
            "memory_choice_candidates": memory_candidates,
            "components": components, "target_parts_subtotal_jpy": target_parts,
            "build_shipping_reserve_jpy": shipping, "small_parts_reserve_jpy": small_parts,
            "target_pc_total_jpy": target_pc, "pc_budget_jpy": pc_budget,
            "target_pc_budget_delta_jpy": target_pc - pc_budget,
            "target_peripheral_budget_jpy": peripheral_budget, "target_all_in_jpy": target_all_in,
            "total_budget_jpy": all_budget, "target_remaining_budget_jpy": all_budget-target_all_in,
            "target_within_pc_budget": target_pc <= pc_budget, "target_within_total_budget": target_all_in <= all_budget,
            "market_reference_estimate_jpy": market_estimate,
            "market_reference_all_in_estimate_jpy": all_in_market,
            "market_reference_estimate_is_checkout_price": False,
            "market_reference_coverage_complete": market_estimate is not None,
            "missing_or_untrusted_market_reference_ids": sorted(set(missing)),
            "market_reference_coverage_count": len(selected_ids)-len(set(missing)),
            "market_reference_required_count": len(selected_ids),
            "target_gpu_required_reduction_pct_from_market_reference": reduction,
            "compatibility_status": compat, "compatibility_checks": checks,
            "decision": decision, "bf_actual_authorized": False, "buy_now_authorized": False,
            "notes": [
                "BF目標額は未確認の購入目標で、確認済み実売価格ではない。",
                "比較サイト価格は市場参考値であり、店頭の決済価格・在庫を保証しない。",
                "購入直前に部品型番、寸法、端子、BIOS、QVL、送料、返品条件を再確認する。"
            ]
        })

    return {
        "generated_at": iso(now), "schema_version": 1, "project": "DIY_PC",
        "source_policy": "Comparison-site prices are market references only. This plan never authorizes a purchase; official seller-specific BF price evidence is missing.",
        "purchase_method_policy": {
            "primary_method": "SELF_BUILD",
            "assembly_time_is_constraint": bool(profile.get("assembly_time_is_constraint", False)),
            "assembly_time_penalty_points": int(profile.get("assembly_time_penalty_points", 0)),
            "bto_role": profile.get("bto_role", "REFERENCE_BENCHMARK_ONLY"),
            "selection_policy": profile.get("selection_policy") or "Prioritize self-build; do not penalize assembly time."
        },
        "selection_factors": profile.get("purchase_decision_factors") or [],
        "total_budget_jpy": all_budget, "peripheral_budget_jpy": peripheral_budget, "pc_budget_jpy": pc_budget,
        "build_shipping_reserve_jpy": shipping, "small_parts_reserve_jpy": small_parts,
        "budget_arithmetic_valid": pc_budget + peripheral_budget + int(profile.get("unallocated_contingency_jpy", 0)) == all_budget,
        "required_categories": profile.get("required_categories") or [],
        "memory_choice_selection": memory_choice_selection,
        "component_coverage": {
            "configured_component_count": len(parts_list),
            "tracked_hardware_part_count": sum(1 for x in parts_list if x.get("track_price")),
            "snapshot_verified_count": sum(1 for x in rows if x.get("price_validation_status") == "verified_market_reference" and x.get("identity_match") is True and x.get("bf_actual_authorized") is False),
            "snapshot_generated_at": snapshot.get("generated_at"),
            "snapshot_source_role": snapshot.get("source_role") or "missing_snapshot",
            "snapshot_sha256": file_sha256(PRICE_PATH)
        },
        "builds": builds, "bf_actual_authorized": False, "buy_now_authorized": False
    }


def render_plan_markdown(plan):
    lines = [
        "# 自作PCパーツ構成・価格監視", "",
        "更新: " + str(plan.get("generated_at")),
        "予算: PC本体 " + money(plan.get("pc_budget_jpy")) + " / 周辺機器 " + money(plan.get("peripheral_budget_jpy")) + " / 総額 " + money(plan.get("total_budget_jpy")),
        "",
        "**購入方式:** 自作PCを正式な本命として最適化します。組み立て時間・作業時間は減点しません。BTOは同等仕様での総額・部品品質・保証のベンチマークとして比較し、便利さだけを理由に自作から切り替えません。",
        "",
        "**注意:** BF購入目標は購入希望額です。比較サイト価格は市場参考値であり、店舗の決済価格・在庫・公式BF実売価格ではありません。現在のデータから購入許可は出しません。",
        "",
        "**メモリ選択:** " + str((plan.get("memory_choice_selection") or {}).get("selected_name") or "未選定"),
        "選定方法: " + str((plan.get("memory_choice_selection") or {}).get("selection_method") or "未確認"),
        "価格比較では、型番一致・鮮度・PIT条件を満たす市場参考値がある候補のうち、価格が最も低いものを優先します。どの候補にも信頼できる参考値がない場合は、設定ファイルで指定した既定メモリを計画上の候補として維持します。市場参考値は決済価格ではなく、購入許可も意味しません。",
        "",
        *(["- {} / BF目標 {} / 比較参考 {} / 状態 {} / {}".format(
            item.get("name"), money(item.get("target_price_jpy")),
            money(item.get("market_reference_price_jpy")) if item.get("trusted_for_market_estimate") else "未検証",
            item.get("price_status"),
            "[商品ページ]({})".format(item.get("purchase_url")) if item.get("purchase_url") else "リンク未確認"
        ) for item in (plan.get("memory_choice_selection") or {}).get("candidates", [])]),
        "",
        "|順位|構成|部品目標小計|PC本体目標総額|周辺機器込み目標|目標残額|比較参考合計|互換性|判定|",
        "|---:|---|---:|---:|---:|---:|---:|---|---|"
    ]
    for build in plan.get("builds") or []:
        lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            build.get("rank"), build.get("name"), money(build.get("target_parts_subtotal_jpy")),
            money(build.get("target_pc_total_jpy")), money(build.get("target_all_in_jpy")),
            money(build.get("target_remaining_budget_jpy")), money(build.get("market_reference_estimate_jpy")),
            build.get("compatibility_status"), build.get("decision")
        ))
    for build in plan.get("builds") or []:
        lines.extend(["", "## " + build.get("name", "自作PC"), "",
          "- PC本体目標（送料・小物予備費込み）: " + money(build.get("target_pc_total_jpy")),
          "- 周辺機器込み目標: " + money(build.get("target_all_in_jpy")) + " / 残額 " + money(build.get("target_remaining_budget_jpy")),
          "- 現在の比較参考合計: " + (money(build.get("market_reference_estimate_jpy")) + "（決済見積ではない）" if build.get("market_reference_estimate_jpy") is not None else "未算出。部品価格の欠落・不一致・古さを0円補完しない"),
          "- 互換性: " + str(build.get("compatibility_status")) + " / 判定: " + str(build.get("decision")), "",
          "|画像|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|直接取得診断|リンク|",
          "|---|---|---|---:|---:|---|---|---|---|---|"])
        for part in build.get("components") or []:
            p = part.get("display_reference_price_jpy")
            if part.get("price_status") == "manual_reference_unverified":
                price_text = money(p) + "（手動参考・現行未確認）" if isinstance(p, int) else "未確認"
            elif part.get("track_price") and part.get("market_reference_price_jpy") is None and p is None:
                price_text = "未取得"
            elif part.get("price_status") == "search_snippet_reference_only":
                price_text = money(p) + "（検索スニペット参考のみ）"
            else:
                price_text = money(p)
            direct_price = part.get("direct_listing_display_price_jpy")
            direct_text = money(direct_price) if isinstance(direct_price, int) else "—"
            stock_label = part.get("direct_listing_display_stock_label")
            if stock_label:
                direct_text += "（" + str(stock_label) + "）"
            url = part.get("purchase_url")
            links = ["[価格比較ページ](" + url + ")"] if url else []
            direct_url = part.get("direct_listing_display_url")
            if direct_url:
                links.append("[直接掲載ページ](" + str(direct_url) + ")")
            search_url = part.get("search_snippet_reference_url")
            if search_url and search_url != url:
                links.append("[検索ページ参考元](" + search_url + ")")
            link = " / ".join(links) if links else "—"
            image_url = part.get("image_url")
            image_source_url = part.get("image_source_url")
            image_alt = html.escape(str(part.get("name") or "PCパーツ画像"), quote=True)
            image_html = (
                '<a href="{}"><img src="{}" alt="{}" width="92"></a>'.format(
                    html.escape(str(image_source_url or url or "#"), quote=True),
                    html.escape(str(image_url), quote=True), image_alt
                )
                if isinstance(image_url, str) and image_url.startswith("https://") else "画像未確認"
            )
            diagnostic_texts = []
            for diagnostic in part.get("direct_listing_validation_diagnostics") or []:
                status = str(diagnostic.get("status") or "unknown")
                reason = str(diagnostic.get("reason_code") or "reason_unavailable")
                detail = status + ": " + reason
                stock = diagnostic.get("stock_status")
                if stock:
                    detail += " / stock=" + str(stock)
                if diagnostic.get("error_type"):
                    detail += " / " + str(diagnostic["error_type"])
                if diagnostic.get("error_message"):
                    detail += " / " + str(diagnostic["error_message"])
                # Keep the Markdown table valid and mobile-readable.
                diagnostic_texts.append(
                    re.sub(r"\\s+", " ", detail).replace("|", "/")[:260]
                )
            diagnostic_text = "; ".join(diagnostic_texts) if diagnostic_texts else "—"
            lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
                image_html, part.get("name"), part.get("model_code") or "—",
                money(part.get("target_price_jpy")), price_text, direct_text,
                part.get("price_status"), diagnostic_text, link
            ))
        lines.extend(["", "互換性チェック:", ""])
        for check in build.get("compatibility_checks") or []:
            lines.append("- **{}**: {} — {}".format(check.get("status"), check.get("check"), check.get("detail")))
    lines.extend(["", "## 注文直前の確認", "",
        "- CPUソケット／BIOS／マザーボード対応、メモリ規格・QVL・EXPO安定性。",
        "- GPUの正確な小売型番・カード寸法・厚さ・補助電源とケース干渉。",
        "- 電源容量・規格・付属ケーブル、クーラー高とRAM干渉、ファン配置。",
        "- 個別店の決済価格・送料・在庫・返品期限・保証・OSライセンス。",
        "- 比較サイト参考価格は公式BF価格ではない。公式日程・店舗価格が確認できるまで買い時判定は保留。", ""])
    return "\n".join(lines)


def section_from_plan(plan):
    lines = [START_MARKER, "## 最優先：PC本体は自作構成", "",
        "BTO完成品は価格比較用の参考枠に下げ、部品ごとの価格・互換性・送料を合算します。PC本体の計画上限は " + money(plan.get("pc_budget_jpy")) + "。", "",
        "|順位|自作構成|PC本体目標|周辺機器込み|目標残額|互換性|判定|",
        "|---:|---|---:|---:|---:|---|---|"]
    for build in plan.get("builds") or []:
        lines.append("|{}|{}|{}|{}|{}|{}|{}|".format(build.get("rank"), build.get("name"),
            money(build.get("target_pc_total_jpy")), money(build.get("target_all_in_jpy")),
            money(build.get("target_remaining_budget_jpy")), build.get("compatibility_status"), build.get("decision")))
    lines.extend(["", "RTX 5070 12GBを本命、RTX 5060 Ti 16GBをVRAM重視の代替、RTX 5070 Ti 16GBを大穴として分離します。",
        "", "BF目標額は値下げ希望額であり、現時点で購入許可はありません。比較サイト価格はBF実売に数えません。",
        "", "[自作PCの部品別価格・互換性レポート](self-build-ranking.md)", END_MARKER])
    return "\n".join(lines)


def insert_section(report, section):
    start, end = report.find(START_MARKER), report.find(END_MARKER)
    if start >= 0 and end >= start:
        # Strip the generated block and normalize surrounding newlines.
        left = report[:start].rstrip()
        right = report[end + len(END_MARKER):].lstrip("\n")
        report = left + ("\n\n" if left and right else "\n" if left else "") + right
    heading = "## 監視中の最高スコア候補"
    if heading in report:
        at = report.index(heading)
        return report[:at] + section + "\n\n" + report[at:]
    first_h2 = report.find("\n## ")
    return report[:first_h2+1] + section + "\n\n" + report[first_h2+1:] if first_h2 >= 0 else report.rstrip()+"\n\n"+section+"\n"

def main():
    config = load_json(CONFIG_PATH, {})
    snapshot = load_json(PRICE_PATH, {})
    plan = build_plan(config, snapshot)
    save_json(PLAN_PATH, plan)
    os.makedirs(os.path.dirname(PLAN_REPORT_PATH), exist_ok=True)
    with open(PLAN_REPORT_PATH, "w", encoding="utf-8") as stream:
        stream.write(render_plan_markdown(plan))
    if os.path.exists(LATEST_REPORT_PATH):
        with open(LATEST_REPORT_PATH, encoding="utf-8") as stream:
            original = stream.read()
        updated = insert_section(original, section_from_plan(plan))
        if updated != original:
            with open(LATEST_REPORT_PATH, "w", encoding="utf-8") as stream:
                stream.write(updated)
    print(json.dumps({"status":"OK","generated_at":plan["generated_at"],
        "build_count":len(plan["builds"]),
        "target_pc_totals":{x["id"]:x["target_pc_total_jpy"] for x in plan["builds"]},
        "all_in_targets":{x["id"]:x["target_all_in_jpy"] for x in plan["builds"]},
        "buy_now_authorized":False,
        "compatibility":{x["id"]:x["compatibility_status"] for x in plan["builds"]}},ensure_ascii=False))


if __name__ == "__main__":
    main()
