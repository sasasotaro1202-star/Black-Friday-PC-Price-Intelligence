"""Build a transparent DIY component plan; never authorize a buy from target/comparison prices."""
import hashlib
import html
import json
import os
import re
from urllib.parse import urlparse
from intelligence import ROOT, now_jst, iso, parse_dt, load_json, save_json
from report import retrieval_issue_link_lines

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


def direct_listing_stock_max_age_minutes(now):
    """Use stricter stock freshness while the provisional intensive watch window is active."""
    config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    start = parse_dt(config.get("monitor_window_start"))
    end = parse_dt(config.get("monitor_window_end"))
    if start is not None and end is not None and start <= now <= end:
        return 30
    return 60


def direct_listing_offers_for_display(row, part, now, max_age, allowed_domains=()):
    """Return fresh, identity-anchored direct retailer observations with stock kept per seller.

    These are listing references, not verified checkout offers. Unknown stock and
    sold-out listings remain visible for auditing, but only in_stock/low_stock
    entries may contribute to the sellable-listing subtotal.
    """
    if not isinstance(row, dict):
        return []
    values = []
    raw_offers = [row.get("retailer_listing_offer")] + list(row.get("retailer_listing_offers") or [])
    seen = set()
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
        stock_signal_max_age = min(int(max_age), direct_listing_stock_max_age_minutes(now))
        stock_signal_fresh = age <= stock_signal_max_age
        stock = str(offer.get("stock_status") or "unknown")
        if stock not in ("in_stock", "low_stock", "preorder_or_backorder", "unknown", "out_of_stock"):
            stock = "unknown"
        key = (url, price, stock, iso(retrieved))
        if key in seen:
            continue
        seen.add(key)
        item = dict(offer)
        item["stock_status"] = stock
        item["stock_signal_fresh"] = bool(stock_signal_fresh)
        item["stock_signal_max_age_minutes"] = stock_signal_max_age
        item["display_age_minutes"] = round(age, 1)
        values.append(item)

    stock_rank = {
        "in_stock": 0, "low_stock": 1, "unknown": 2,
        "preorder_or_backorder": 3, "out_of_stock": 4,
    }
    values.sort(key=lambda offer: (
        0 if offer.get("stock_signal_fresh") is True else 1,
        stock_rank.get(str(offer.get("stock_status") or "unknown"), 2),
        offer.get("price_jpy", 10**12),
        0 if offer.get("price_source_mode") == "direct_structured" else 1,
        offer.get("display_age_minutes", 10**9),
    ))
    return values


def direct_listing_offer_for_display(row, part, now, max_age, allowed_domains=()):
    """Select one best-status direct retailer listing for the existing summary fields."""
    values = direct_listing_offers_for_display(row, part, now, max_age, allowed_domains)
    return values[0] if values else None


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
    # Retain every fresh seller-specific direct offer so sold-out and unknown-stock
    # stores are not hidden by a single "best" listing.
    direct_display_offers = direct_listing_offers_for_display(
        row, part, now, max_age, allowed_domains
    )
    sellable_offers = [
        offer for offer in direct_display_offers
        if offer.get("stock_signal_fresh") is True
        and offer.get("stock_status") in ("in_stock", "low_stock")
    ]
    sellable_offers.sort(key=lambda offer: (
        0 if offer.get("stock_status") == "in_stock" else 1,
        offer.get("price_jpy", 10**12),
        offer.get("display_age_minutes", 10**9),
    ))
    sellable_offer = sellable_offers[0] if sellable_offers else None
    stock_counts = {
        status: sum(
            1 for offer in direct_display_offers
            if offer.get("stock_signal_fresh") is True and offer.get("stock_status") == status
        )
        for status in ("in_stock", "low_stock", "preorder_or_backorder", "unknown", "out_of_stock")
    }
    stock_counts["stale"] = sum(1 for offer in direct_display_offers if offer.get("stock_signal_fresh") is not True)
    direct_display_offer = (
        direct_display_offers[0] if direct_display_offers and not trusted else None
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
        "early_buy_review": row.get("early_buy_review") if isinstance(row.get("early_buy_review"), dict) else None,
        "direct_listing_display_age_minutes": direct_display_offer.get("display_age_minutes") if direct_display_offer else None,
        "direct_listing_display_price_context": direct_display_offer.get("price_context") if direct_display_offer else None,
        "direct_listing_display_offers": [
            {
                "url": offer.get("url"),
                "retailer_domain": offer.get("retailer_domain") or (
                    (urlparse(str(offer.get("url") or "")).hostname or "").removeprefix("www.")
                ),
                "seller_name": offer.get("seller_name") or offer.get("merchant") or offer.get("seller"),
                "title": offer.get("title") or offer.get("identity_anchor"),
                "price_jpy": offer.get("price_jpy"),
                "stock_status": offer.get("stock_status") or "unknown",
                "stock_signal_fresh": offer.get("stock_signal_fresh") is True,
                "stock_signal_max_age_minutes": offer.get("stock_signal_max_age_minutes"),
                "price_source_mode": offer.get("price_source_mode"),
                "retrieval_time": offer.get("retrieval_time"),
                "display_age_minutes": offer.get("display_age_minutes"),
            }
            for offer in direct_display_offers
        ],
        "direct_listing_sellable_price_jpy": sellable_offer.get("price_jpy") if sellable_offer else None,
        "direct_listing_sellable_url": sellable_offer.get("url") if sellable_offer else None,
        "direct_listing_sellable_stock_status": sellable_offer.get("stock_status") if sellable_offer else None,
        "direct_listing_sellable_retrieval_time": sellable_offer.get("retrieval_time") if sellable_offer else None,
        "direct_listing_stock_counts": stock_counts,
        "direct_listing_offer_count": len(direct_display_offers),
        "direct_listing_sellable_offer_count": len(sellable_offers),
        "direct_listing_display_is_estimate_eligible": False,
        "direct_listing_display_purchase_allowed": False,
        "direct_listing_validation_diagnostics": direct_diagnostics,
    }


def compatibility_checks(parts, profile, gpu_id, memory_part_id=None, storage_part_id=None, cooler_part_id=None, cpu_part_id=None, motherboard_part_id=None, psu_part_id=None, case_part_id=None, selected_part_ids=None, cooler_included=False):
    """Checks known socket/memory/storage/size/power constraints, fail-closed."""
    checks = []
    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    def spec(part_id):
        return (parts.get(part_id) or {}).get("specs") or {}

    fixed_ids = profile.get("fixed_part_ids") or []
    cpu_part_id = cpu_part_id or next(
        (str(part_id) for part_id in fixed_ids if (parts.get(str(part_id)) or {}).get("category") == "cpu"),
        "cpu-ryzen7-9700x",
    )
    cpu = spec(cpu_part_id)
    motherboard_part_id = motherboard_part_id or next(
        (str(part_id) for part_id in fixed_ids if (parts.get(str(part_id)) or {}).get("category") == "motherboard"),
        "motherboard-asrock-b850m-pro-rs-wifi",
    )
    psu_part_id = psu_part_id or next(
        (str(part_id) for part_id in fixed_ids if (parts.get(str(part_id)) or {}).get("category") == "psu"),
        "psu-corsair-rm850e-2025",
    )
    case_part_id = case_part_id or next(
        (str(part_id) for part_id in fixed_ids if (parts.get(str(part_id)) or {}).get("category") == "case"),
        "case-fractal-pop-air-tg",
    )
    board = spec(motherboard_part_id)
    memory_part_id = memory_part_id or profile.get("primary_memory_choice_id") or next(
        (
            str(part_id) for part_id in fixed_ids
            if (parts.get(str(part_id)) or {}).get("category") == "memory"
        ),
        "memory-teamgroup-ddr5-32gb-6000",
    )
    memory = spec(memory_part_id)
    storage = spec(storage_part_id or "ssd-crucial-p3-plus-1tb")
    psu = spec(psu_part_id)
    case = spec(case_part_id)
    cooler = spec(cooler_part_id or "cooler-thermalright-pa120-se-v3") if not cooler_included else {}
    gpu = spec(gpu_id)
    selected_ids = set(str(x) for x in (selected_part_ids or (fixed_ids + [gpu_id, memory_part_id, storage_part_id] + ([cooler_part_id] if cooler_part_id else []))))

    add("cpu_motherboard_socket", "PASS" if cpu.get("socket") and cpu.get("socket") == board.get("socket") else "FAIL",
        "CPU socket {} / board socket {}".format(cpu.get("socket", "unknown"), board.get("socket", "unknown")))

    observed_bios = board.get("observed_bios_version")
    def version_tuple(value):
        pieces = re.findall(r"\d+", str(value or ""))
        return tuple(int(piece) for piece in pieces) if pieces else None
    if cpu_part_id == "cpu-ryzen7-9700x":
        minimum_bios = board.get("minimum_bios_for_ryzen7_9700x")
        cpu_support_verified = board.get("cpu_support_list_verified_for_ryzen7_9700x") is True
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
    elif cpu.get("series") in (board.get("supported_cpu_series") or []):
        bios_status = "REVIEW"
        bios_detail = "The motherboard manufacturer lists the Ryzen 9000 series as supported, but the exact minimum BIOS for {} and the shipped BIOS are not confirmed in this plan. Verify the exact CPU row and update BIOS if required.".format((parts.get(cpu_part_id) or {}).get("name") or cpu_part_id)
    else:
        bios_status = "REVIEW"
        bios_detail = "Exact motherboard support-list entry and minimum BIOS for {} remain unverified.".format((parts.get(cpu_part_id) or {}).get("name") or cpu_part_id)
    add("cpu_bios_support", bios_status, bios_detail)

    cooler_guidance = str(cpu.get("recommended_cooler_guidance") or "")
    if cooler_included and cpu.get("cooler_included") is True:
        add("cpu_cooling_headroom", "REVIEW", "CPU BOX includes a bundled stock cooler; check noise/temperature under long game builds and analysis loads.")
    elif cpu.get("cooler_guidance_review") is True and cooler.get("cooling_type") != "liquid":
        add(
            "cpu_cooling_headroom", "REVIEW",
            "{}; currently configured CPU cooler is not the liquid-cooling setup described by the manufacturer. Sustained build/analysis thermal performance and any cooler replacement cost are not verified.".format(cooler_guidance),
        )

    memory_ok = (
        memory.get("memory_type") == board.get("memory_type")
        and isinstance(memory.get("capacity_gb"), int) and memory["capacity_gb"] >= int(profile.get("minimum_ram_gb", 32))
        and isinstance(memory.get("modules"), int) and memory["modules"] >= int(profile.get("minimum_memory_modules", 2))
    )
    add("memory_type_capacity_dual_channel", "PASS" if memory_ok else "FAIL",
        "DDR type, >= {}GB, >= {} DIMMs".format(profile.get("minimum_ram_gb", 32), profile.get("minimum_memory_modules", 2)))
    board_qvl_key = "qvl_verified_with_" + motherboard_part_id.removeprefix("motherboard-").replace("-", "_")
    qvl_verified = memory.get(board_qvl_key) is True
    board_name = (parts.get(motherboard_part_id) or {}).get("name") or motherboard_part_id
    add(
        "memory_qvl",
        "PASS" if qvl_verified else "REVIEW",
        "Exact kit {} QVL entry for {}: {}".format(
            memory_part_id, board_name,
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

    if cooler_included and cpu.get("cooler_included") is True:
        add("cooler_socket", "PASS", "CPU BOX includes its bundled stock cooler; preserve the exact boxed SKU.")
        add("cooler_case_clearance", "REVIEW", "Confirm exact boxed SKU and airflow before purchase.")
    else:
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
    selected_has_os = any((parts.get(item_id) or {}).get("category") == "os_license" for item_id in selected_ids)
    add("os_license", "PASS" if selected_has_os else "FAIL",
        "Windows 11 Home license included in this exact build unless a transferable existing license is verified")

    statuses = [x["status"] for x in checks]
    overall = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
    return overall, checks


def assess_workload_fit(profile, parts, selected_ids, gpu_id, memory_id):
    """Assess the configured build against gaming, game-creation and AI/data workloads."""
    profile = profile if isinstance(profile, dict) else {}
    workload = profile.get("workload_profile") or {}
    game_dev = workload.get("game_development") or {}
    baseline = game_dev.get("baseline_requirements") or {}
    preferred = game_dev.get("preferred_if_budget_allows") or {}
    selected = [parts.get(str(cid)) or {} for cid in selected_ids]
    by_category = {str(item.get("category")): item for item in selected if item.get("category")}

    gpu = parts.get(str(gpu_id)) or {}
    memory = parts.get(str(memory_id)) or {}
    storage = by_category.get("storage") or {}
    cpu = by_category.get("cpu") or {}
    gpu_specs = gpu.get("specs") or {}
    memory_specs = memory.get("specs") or {}
    storage_specs = storage.get("specs") or {}
    cpu_specs = cpu.get("specs") or {}

    def as_positive_int(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    ram_gb = as_positive_int(memory_specs.get("capacity_gb"))
    vram_gb = as_positive_int(gpu_specs.get("vram_gb"))
    ssd_gb = as_positive_int(storage_specs.get("capacity_gb"))
    cpu_cores = as_positive_int(cpu_specs.get("cores"))
    cpu_threads = as_positive_int(cpu_specs.get("threads"))

    def metric(actual, required, preferred_value, unit):
        required = as_positive_int(required)
        preferred_value = as_positive_int(preferred_value)
        if actual is None or required is None:
            status = "REVIEW"
        elif actual < required:
            status = "FAIL"
        elif preferred_value is not None and actual < preferred_value:
            status = "MEETS_BASELINE_BELOW_PREFERENCE"
        elif preferred_value is not None:
            status = "MEETS_PREFERENCE"
        else:
            status = "MEETS_BASELINE"
        return {
            "actual": actual,
            "required_baseline": required,
            "preferred_if_budget_allows": preferred_value,
            "unit": unit,
            "status": status,
        }

    ram = metric(ram_gb, baseline.get("system_ram_gb"), preferred.get("system_ram_gb"), "GB")
    vram = metric(vram_gb, baseline.get("dedicated_gpu_vram_gb"), preferred.get("dedicated_gpu_vram_gb"), "GB VRAM")
    ssd = metric(ssd_gb, baseline.get("primary_ssd_gb"), preferred.get("primary_ssd_gb"), "GB")
    required_statuses = [ram["status"], vram["status"], ssd["status"]]
    if "FAIL" in required_statuses:
        status = "FAIL_BASELINE_REQUIREMENT"
        summary = "制作向けの基準を満たさない"
    elif "REVIEW" in required_statuses:
        status = "REVIEW_MISSING_SPEC"
        summary = "仕様の確認が必要"
    else:
        status = "MEETS_BASELINE"
        summary = "制作ベースライン適合"

    roles = workload.get("gpu_candidate_roles") or {}
    gpu_role = roles.get(str(gpu_id), "役割未定義。個別GPUの実測と仕様を確認する。")
    source_compile_target = as_positive_int(game_dev.get("preferred_cpu_cores_for_unreal_source_build"))
    engines = list(game_dev.get("target_engines") or [])
    if source_compile_target is None or "Unreal Engine 5" not in engines:
        unreal_source_compile = {
            "status": "NOT_CONFIGURED",
            "cpu_cores": cpu_cores,
            "practical_core_target": source_compile_target,
            "note": "Unreal Engineのソースからのフルビルドは個別要件として評価していない。",
        }
    elif cpu_cores is None:
        unreal_source_compile = {
            "status": "REVIEW_CPU_CORE_COUNT",
            "cpu_cores": None,
            "practical_core_target": source_compile_target,
            "note": "正確なCPUコア数の確認が必要。",
        }
    elif cpu_cores < source_compile_target:
        unreal_source_compile = {
            "status": "TRADEOFF_BELOW_PRACTICAL_CORE_TARGET",
            "cpu_cores": cpu_cores,
            "cpu_threads": cpu_threads,
            "practical_core_target": source_compile_target,
            "note": "Epicは分散ビルドを使わないUnreal Engineソースのローカルコンパイルについて12～16コアを実用的な目安として案内。通常のゲームプロジェクト制作全般が不可という意味ではない。",
        }
    else:
        unreal_source_compile = {
            "status": "MEETS_LOWER_PRACTICAL_CORE_TARGET",
            "cpu_cores": cpu_cores,
            "cpu_threads": cpu_threads,
            "practical_core_target": source_compile_target,
            "note": "コア数の目安を満たす。ビルド時間はプロジェクト、設定、ストレージ等で変わる。",
        }

    return {
        "status": status,
        "summary_label": summary,
        "target_engines": engines,
        "target_project_types": list(game_dev.get("target_project_types") or []),
        "target_games": list((workload.get("gaming") or {}).get("targets") or []),
        "selected_hardware": {
            "cpu_name": cpu.get("name"),
            "cpu_cores": cpu_cores,
            "cpu_threads": cpu_threads,
            "system_ram_gb": ram_gb,
            "gpu_name": gpu.get("name"),
            "dedicated_gpu_vram_gb": vram_gb,
            "primary_ssd_gb": ssd_gb,
        },
        "game_development": {
            "status": status,
            "system_ram": ram,
            "dedicated_gpu_vram": vram,
            "primary_ssd": ssd,
            "gpu_candidate_role": gpu_role,
            "unreal_engine_source_compile": unreal_source_compile,
            "preferred_capacity_note": game_dev.get("preference_note"),
            "official_reference_urls": list(game_dev.get("official_reference_urls") or []),
        },
        "gaming": {
            "targets": list((workload.get("gaming") or {}).get("targets") or []),
            "display_target": (workload.get("gaming") or {}).get("target_display"),
            "assessment_note": (workload.get("gaming") or {}).get("evaluation_note"),
            "gpu_candidate_role": gpu_role,
        },
        "ai_and_data_analysis": {
            "targets": list((workload.get("ai_and_data_analysis") or {}).get("targets") or []),
            "assessment_note": (workload.get("ai_and_data_analysis") or {}).get("note"),
            "analysis_automation_profile": workload.get("analysis_and_automation") or {},
        },
        "study_and_research": workload.get("study_and_research") or {
            "status": "NOT_CONFIGURED",
            "note": "勉強・文書閲覧・調査の要件は未設定。",
        },
        "post_purchase_upgrade_assumption": False,
        "purchase_authorized": False,
    }


def score_and_rank_builds(builds):
    """Rank complete target builds by workload fit and target-price efficiency.

    The score is a planning rubric, not measured FPS/benchmark data. Evidence
    completeness is separate from performance and never authorizes purchase.
    """
    # Tom's Hardware GPU Hierarchy 2026, 1440p Ultra rasterization benchmark.
    # Parenthesized values from the source table are the reference mean FPS/index.
    # This is a broad benchmark proxy, not a measurement for the user's exact games.
    gpu_raster_1440p_fps = {
        "gpu-rtx5070ti-16gb": 116.8,
        "gpu-rtx5070-12gb": 96.4,
        "gpu-rtx5060ti-16gb": 73.4,
    }
    gpu_benchmark_source = "https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html"
    gpu_benchmark_updated = "2026-06-24"

    def positive_number(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else 0.0

    scored = []
    for build in builds:
        fit = build.get("workload_fit") or {}
        hw = fit.get("selected_hardware") or {}
        ram = positive_number(hw.get("system_ram_gb"))
        vram = positive_number(hw.get("dedicated_gpu_vram_gb"))
        ssd = positive_number(hw.get("primary_ssd_gb"))
        cores = positive_number(hw.get("cpu_cores"))
        gpu_fps = gpu_raster_1440p_fps.get(str(build.get("gpu_choice_id")))

        # The four workload scores add to 75 points. These are rubric scores,
        # not measured FPS, compile time, or AI throughput.
        workload_scores = {
            "gaming_score": round(25.0 * gpu_fps / max(gpu_raster_1440p_fps.values()) if gpu_fps else 0.0, 1),
            "game_creation_score": round(
                min(vram / 16.0, 1.0) * 8.0
                + min(ram / 32.0, 1.0) * 4.0 + (1.0 if ram >= 64 else 0.0)
                + min(ssd / 1000.0, 1.0) * 2.0 + (1.0 if ssd >= 2000 else 0.0)
                + min(cores / 12.0, 1.0) * 4.0, 1
            ),
            "analysis_ai_score": round(
                min(cores / 16.0, 1.0) * 7.0
                + min(ram / 32.0, 1.0) * 3.0 + (3.0 if ram >= 64 else 0.0)
                + min(vram / 16.0, 1.0) * 5.0
                + min(ssd / 1000.0, 1.0) + (1.0 if ssd >= 2000 else 0.0), 1
            ),
            "study_multitasking_score": round(
                min(ram / 32.0, 1.0) * 4.0 + (1.0 if ram >= 64 else 0.0)
                + min(cores / 8.0, 1.0) * 3.0
                + min(ssd / 1000.0, 1.0) + (1.0 if ssd >= 2000 else 0.0), 1
            ),
        }
        workload_points = sum(workload_scores.values())

        checks = build.get("compatibility_checks") or []
        status_points = {"PASS": 1.0, "REVIEW": 0.5, "FAIL": 0.0}
        compatibility_ratio = (
            sum(status_points.get(str(check.get("status")), 0.0) for check in checks) / len(checks)
            if checks else 0.0
        )
        compatibility_points = round(compatibility_ratio * 10.0, 1)

        # Price-source coverage is useful for research, but it is not the same
        # as a verified retailer checkout. Keep these distinct in the scorecard.
        required_refs = int(positive_number(build.get("market_reference_required_count")))
        covered_refs = int(positive_number(build.get("market_reference_coverage_count")))
        market_reference_coverage = min(covered_refs / required_refs, 1.0) if required_refs else 0.0

        components = [part for part in (build.get("components") or []) if isinstance(part, dict)]
        component_count = len(components)
        direct_price_verified = 0
        stock_verified = 0
        checkout_verified = 0
        for part in components:
            signal = part.get("early_buy_review")
            if not isinstance(signal, dict):
                continue
            observed = signal.get("observed_price_jpy")
            exact_fresh_price = (
                isinstance(observed, int) and not isinstance(observed, bool) and observed > 0
                and signal.get("price_verified") is True
                and signal.get("identity_verified") is True
                and signal.get("pit_valid") is True
            )
            stock_confirmed = exact_fresh_price and signal.get("stock_status") in ("in_stock", "low_stock")
            checkout_total = signal.get("verified_checkout_total_jpy")
            total_confirmed = (
                stock_confirmed
                and signal.get("checkout_total_verified") is True
                and isinstance(checkout_total, int) and not isinstance(checkout_total, bool) and checkout_total > 0
            )
            direct_price_verified += int(exact_fresh_price)
            stock_verified += int(stock_confirmed)
            checkout_verified += int(total_confirmed)

        denominator = component_count or 1
        direct_price_coverage = direct_price_verified / denominator
        stock_coverage = stock_verified / denominator
        checkout_coverage = checkout_verified / denominator
        # Evidence completeness: direct exact price/PIT 30, sellable stock 25,
        # verified checkout total 25, compatibility status 20. This is not an
        # authorization gate or guarantee that returns/warranty are acceptable.
        evidence_completeness = round(
            30.0 * direct_price_coverage
            + 25.0 * stock_coverage
            + 25.0 * checkout_coverage
            + 20.0 * (compatibility_points / 10.0), 1
        )

        target_total = positive_number(build.get("target_all_in_jpy"))
        value_ratio = workload_points / target_total if target_total else 0.0
        scored.append({
            "build": build,
            "workload_scores": workload_scores,
            "workload_points": workload_points,
            "compatibility_points": compatibility_points,
            "market_reference_coverage": market_reference_coverage,
            "required_refs": required_refs,
            "covered_refs": covered_refs,
            "direct_price_verified": direct_price_verified,
            "stock_verified": stock_verified,
            "checkout_verified": checkout_verified,
            "component_count": component_count,
            "direct_price_coverage": direct_price_coverage,
            "stock_coverage": stock_coverage,
            "checkout_coverage": checkout_coverage,
            "evidence_completeness": evidence_completeness,
            "value_ratio": value_ratio,
            "gpu_reference_fps": gpu_fps,
        })

    best_value_ratio = max((row["value_ratio"] for row in scored), default=0.0)
    result = []
    for row in scored:
        build = row["build"]
        value_score = round(
            15.0 * row["value_ratio"] / best_value_ratio if best_value_ratio > 0 else 0.0, 1
        )
        visible_components = list(row["workload_scores"].values()) + [
            value_score, row["compatibility_points"]
        ]
        total_score = round(min(100.0, sum(visible_components)), 1)
        build["scorecard"] = {
            "overall_score": total_score,
            **row["workload_scores"],
            "workload_fit_points_out_of_75": round(row["workload_points"], 1),
            "price_efficiency_points_out_of_15": value_score,
            "compatibility_points_out_of_10": row["compatibility_points"],
            "market_reference_coverage_pct": round(row["market_reference_coverage"] * 100.0, 1),
            "market_reference_component_count": row["covered_refs"],
            "market_reference_required_count": row["required_refs"],
            "direct_price_identity_pit_coverage_pct": round(row["direct_price_coverage"] * 100.0, 1),
            "sellable_stock_coverage_pct": round(row["stock_coverage"] * 100.0, 1),
            "verified_checkout_total_coverage_pct": round(row["checkout_coverage"] * 100.0, 1),
            "direct_price_verified_component_count": row["direct_price_verified"],
            "sellable_stock_verified_component_count": row["stock_verified"],
            "verified_checkout_total_component_count": row["checkout_verified"],
            "required_component_count": row["component_count"],
            "purchase_evidence_completeness_score_out_of_100": row["evidence_completeness"],
            "score_basis": "BF目標総額ベースの構成ルーブリック。GPUゲーム点はTom's Hardwareの1440p Ultraラスタライズ階層を25点満点に正規化した代理指標で、対象ゲームの実測FPSではない。",
            "gaming_benchmark_reference": {"source_url": gpu_benchmark_source, "source_updated": gpu_benchmark_updated, "resolution": "1440p Ultra", "method": "rasterization hierarchy", "reference_mean_fps": row["gpu_reference_fps"], "user_game_specific": False},
            "purchase_authorized": False,
        }
        result.append(build)

    result.sort(
        key=lambda item: (
            -(item.get("scorecard") or {}).get("overall_score", 0.0),
            item.get("target_all_in_jpy") if isinstance(item.get("target_all_in_jpy"), int) else 10**12,
            str(item.get("gpu_choice_id") or ""),
        )
    )
    for rank, build in enumerate(result, 1):
        build["rank"] = rank
    return result



def build_budget_scenarios(profile, parts, by_id, now, max_age):
    """Return itemized 350k/400k/450k configurations. Target arithmetic never authorizes a purchase."""
    candidates = []
    allowed_domains = profile.get("allowed_search_reference_domains") or profile.get("allowed_comparison_domains") or ["kakaku.com"]
    default_peripherals = int(profile.get("peripheral_budget_jpy", 35000))
    default_reserve = int(profile.get("unallocated_contingency_jpy", 5000))
    default_soft_overrun = max(0, int(profile.get("soft_overrun_allowance_jpy", 20000)))

    for cfg in profile.get("budget_build_candidates") or []:
        if not isinstance(cfg, dict):
            continue
        tier = cfg.get("budget_tier_jpy")
        ids = [str(x) for x in (cfg.get("part_ids") or [])]
        if not isinstance(tier, int) or isinstance(tier, bool) or tier <= 0 or not ids or len(ids) != len(set(ids)):
            continue
        if any(item_id not in parts for item_id in ids):
            continue

        cpu_id = str(cfg.get("cpu_part_id") or "")
        board_id = str(cfg.get("motherboard_part_id") or "")
        gpu_id = str(cfg.get("gpu_choice_id") or "")
        memory_id = str(cfg.get("memory_part_id") or "")
        storage_id = str(cfg.get("storage_part_id") or "")
        cooler_id = str(cfg.get("cooler_part_id") or "") or None
        cooler_included = cfg.get("cooler_included_by_cpu") is True
        peripherals = int(cfg.get("peripheral_budget_jpy", default_peripherals))
        reserve = int(cfg.get("unallocated_contingency_jpy", default_reserve))
        tier_policy = next((x for x in (profile.get("budget_scenarios") or [])
                            if isinstance(x, dict) and x.get("total_budget_jpy") == tier), {})
        soft_allowance = max(0, int(tier_policy.get("soft_overrun_allowance_jpy", profile.get("soft_overrun_allowance_jpy", default_soft_overrun))))
        soft_ceiling = max(tier, int(cfg.get("soft_ceiling_total_jpy", tier_policy.get("soft_ceiling_total_jpy", tier + soft_allowance))))
        shipping = int(cfg.get("build_shipping_reserve_jpy", profile.get("build_shipping_reserve_jpy", 0)))
        small_parts = int(cfg.get("small_parts_reserve_jpy", profile.get("small_parts_reserve_jpy", 0)))

        components = []
        target_parts = 0
        missing_target_ids = []
        exact_price_count = 0
        sellable_count = 0
        checkout_count = 0
        market_reference_count = 0
        market_reference_required = 0
        for item_id in ids:
            part = parts[item_id]
            price = component_price(part, by_id, now, max_age, allowed_domains=allowed_domains)
            target = part.get("target_price_jpy")
            if isinstance(target, int) and not isinstance(target, bool) and target > 0:
                target_parts += target
            else:
                missing_target_ids.append(item_id)
            if part.get("track_price"):
                market_reference_required += 1
                if price.get("trusted_for_market_estimate") is True and isinstance(price.get("market_reference_price_jpy"), int):
                    market_reference_count += 1

            signal = price.get("early_buy_review") if isinstance(price.get("early_buy_review"), dict) else {}
            observed = signal.get("observed_price_jpy")
            exact_fresh_price = (
                isinstance(observed, int) and not isinstance(observed, bool) and observed > 0
                and signal.get("price_verified") is True
                and signal.get("identity_verified") is True
                and signal.get("pit_valid") is True
            )
            stock = str(signal.get("stock_status") or price.get("direct_listing_sellable_stock_status") or "unknown")
            stock_verified = exact_fresh_price and stock in ("in_stock", "low_stock")
            checkout_verified = (
                stock_verified and signal.get("checkout_total_verified") is True
                and isinstance(signal.get("verified_checkout_total_jpy"), int)
                and not isinstance(signal.get("verified_checkout_total_jpy"), bool)
                and signal.get("verified_checkout_total_jpy") > 0
            )
            exact_price_count += int(exact_fresh_price)
            sellable_count += int(stock_verified)
            checkout_count += int(checkout_verified)
            components.append({
                "id": item_id, "category": part.get("category"), "name": part.get("name"),
                "model_code": part.get("model_code"), "target_price_jpy": target,
                "market_reference_price_jpy": price.get("market_reference_price_jpy"),
                "display_reference_price_jpy": price.get("display_reference_price_jpy"),
                "price_status": price.get("price_status"),
                "trusted_for_market_estimate": bool(price.get("trusted_for_market_estimate")),
                "retrieval_time": price.get("retrieval_time"),
                "reference_source_url": price.get("reference_source_url"),
                "monitor_url": part.get("monitor_url"),
                "purchase_url": price.get("purchase_url") or part.get("purchase_url") or part.get("monitor_url"),
                "early_buy_review": signal or None,
                "direct_listing_display_price_jpy": price.get("direct_listing_display_price_jpy"),
                "direct_listing_display_url": price.get("direct_listing_display_url"),
                "direct_listing_display_stock_status": price.get("direct_listing_display_stock_status") or "unknown",
                "direct_listing_sellable_price_jpy": price.get("direct_listing_sellable_price_jpy"),
                "direct_listing_sellable_stock_status": price.get("direct_listing_sellable_stock_status") or "unknown",
                "direct_listing_stock_counts": price.get("direct_listing_stock_counts") or {},
                "specs": part.get("specs") or {},
                "fit_scorecard": part.get("fit_scorecard"),
            })

        categories = [str((parts.get(item_id) or {}).get("category") or "") for item_id in ids]
        category_counts = {category: categories.count(category) for category in set(categories)}
        required_categories = ("cpu", "gpu", "motherboard", "memory", "storage", "psu", "case", "os_license")
        missing_categories = [category for category in required_categories if category_counts.get(category, 0) != 1]
        if cooler_included and not (parts.get(cpu_id) or {}).get("specs", {}).get("cooler_included"):
            missing_categories.append("cpu_box_cooler_not_verified")
        if not cooler_included and category_counts.get("cpu_cooler", 0) != 1:
            missing_categories.append("cpu_cooler")

        pc_total = target_parts + shipping + small_parts
        all_in = pc_total + peripherals + reserve
        pc_cap = max(0, tier - peripherals - reserve)
        soft_pc_cap = max(0, soft_ceiling - peripherals - reserve)
        remaining = tier - all_in
        overrun = max(0, all_in - tier)
        remaining_soft = soft_ceiling - all_in
        soft_overrun = max(0, all_in - soft_ceiling)
        within_target = all_in <= tier and pc_total <= pc_cap
        within_soft_band = all_in <= soft_ceiling and pc_total <= soft_pc_cap

        cpu_specs = (parts.get(cpu_id) or {}).get("specs") or {}
        gpu_specs = (parts.get(gpu_id) or {}).get("specs") or {}
        memory_specs = (parts.get(memory_id) or {}).get("specs") or {}
        storage_specs = (parts.get(storage_id) or {}).get("specs") or {}
        ram_gb = memory_specs.get("capacity_gb")
        vram_gb = gpu_specs.get("vram_gb")
        ssd_gb = storage_specs.get("capacity_gb")
        baseline_ok = (
            isinstance(ram_gb, int) and ram_gb >= int(profile.get("minimum_ram_gb", 32))
            and isinstance(vram_gb, int) and vram_gb >= 8
            and isinstance(ssd_gb, int) and ssd_gb >= int(profile.get("minimum_ssd_gb", 1000))
        )
        config_valid = not missing_target_ids and not missing_categories and baseline_ok

        compatibility, checks = compatibility_checks(
            parts, profile, gpu_id, memory_id, storage_id, cooler_id,
            cpu_part_id=cpu_id, motherboard_part_id=board_id,
            psu_part_id=cfg.get("psu_part_id"), case_part_id=cfg.get("case_part_id"),
            selected_part_ids=ids, cooler_included=cooler_included,
        )
        workload = assess_workload_fit(profile, parts, ids, gpu_id, memory_id)
        if not config_valid:
            decision = "BLOCKED_INCOMPLETE_OR_BELOW_WORKLOAD_BASELINE"
        elif all_in > soft_ceiling or pc_total > soft_pc_cap:
            decision = "OVER_SOFT_BUDGET_BAND"
        elif compatibility == "FAIL":
            decision = "BLOCKED_COMPATIBILITY"
        elif compatibility == "REVIEW":
            decision = "WAIT_FOR_COMPATIBILITY_REVIEW"
        else:
            decision = "WAIT_FOR_DIRECT_PRICE_STOCK_CHECKOUT_AND_BF_EVIDENCE"

        candidates.append({
            "id": str(cfg.get("id") or (str(tier) + "_" + gpu_id)),
            "budget_tier_jpy": tier, "budget_tier_label": str(cfg.get("budget_tier_label") or "{}万円".format(tier // 10000)),
            "name": str(cfg.get("name") or "自作PCシナリオ"), "scenario_role": str(cfg.get("scenario_role") or "comparison"),
            "purpose_note_ja": str(cfg.get("purpose_note_ja") or ""), "tradeoff_note_ja": str(cfg.get("tradeoff_note_ja") or ""),
            "target_budget_jpy": tier, "soft_ceiling_total_jpy": soft_ceiling, "target_peripheral_budget_jpy": peripherals, "target_contingency_jpy": reserve,
            "target_pc_budget_jpy": pc_cap, "target_pc_soft_budget_jpy": soft_pc_cap,
            "soft_overrun_allowance_jpy": soft_allowance, "soft_ceiling_total_jpy": soft_ceiling,
            "target_parts_subtotal_jpy": target_parts,
            "build_shipping_reserve_jpy": shipping, "small_parts_reserve_jpy": small_parts,
            "target_pc_total_jpy": pc_total, "target_all_in_jpy": all_in,
            "target_remaining_budget_jpy": remaining, "target_overrun_jpy": overrun,
            "target_remaining_soft_budget_jpy": remaining_soft, "target_soft_overrun_jpy": soft_overrun,
            "target_within_total_budget": within_target,
            "target_within_soft_total_budget": within_soft_band,
            "within_scenario_target": within_target,
            "within_soft_band": within_soft_band,
            "target_prices_complete": not missing_target_ids, "configuration_valid": config_valid,
            "missing_price_part_ids": missing_target_ids, "missing_category_checks": missing_categories,
            "workload_baseline_met": baseline_ok, "selected_part_ids": ids,
            "cpu_part_id": cpu_id, "motherboard_part_id": board_id, "gpu_choice_id": gpu_id,
            "memory_part_id": memory_id, "storage_part_id": storage_id, "cooler_part_id": cooler_id,
            "cooler_included_by_cpu": cooler_included, "ram_gb": ram_gb, "gpu_vram_gb": vram_gb, "ssd_gb": ssd_gb,
            "cpu_cores": cpu_specs.get("cores"), "cpu_threads": cpu_specs.get("threads"),
            "components": components, "compatibility_status": compatibility, "compatibility_checks": checks,
            "workload_fit": workload, "current_exact_price_evidence_part_count": exact_price_count,
            "current_sellable_stock_part_count": sellable_count, "current_verified_checkout_part_count": checkout_count,
            "current_sellable_stock_coverage_pct": round(100 * sellable_count / len(ids), 1) if ids else 0.0,
            "current_verified_checkout_coverage_pct": round(100 * checkout_count / len(ids), 1) if ids else 0.0,
            "current_market_reference_coverage_count": market_reference_count,
            "required_market_reference_count": market_reference_required,
            "current_checkout_total_verified_jpy": None, "decision": decision,
            "price_basis": "BF_TARGET_ARITHMETIC_ONLY_NOT_FORECAST_OR_VERIFIED_CHECKOUT",
            "bf_actual_authorized": False, "buy_now_authorized": False, "purchase_authorized": False,
            "target_all_in_jpy_is_verified_checkout_price": False,
        })

    grouped = []
    for tier in profile.get("budget_scenarios") or []:
        if not isinstance(tier, dict):
            continue
        ceiling = tier.get("total_budget_jpy")
        tier_items = [item for item in candidates if item["budget_tier_jpy"] == ceiling]
        score_inputs = [{
            "id": item["id"], "name": item["name"], "gpu_choice_id": item["gpu_choice_id"],
            "target_all_in_jpy": item["target_all_in_jpy"], "target_pc_total_jpy": item["target_pc_total_jpy"],
            "components": item["components"], "workload_fit": item["workload_fit"],
            "compatibility_checks": item["compatibility_checks"],
            "market_reference_required_count": item["required_market_reference_count"],
            "market_reference_coverage_count": item["current_market_reference_coverage_count"],
        } for item in tier_items]
        scored = score_and_rank_builds(score_inputs)
        scoremap = {item["id"]: item for item in scored}
        for item in tier_items:
            result = scoremap.get(item["id"]) or {}
            item["budget_tier_rank"] = result.get("rank")
            item["scorecard"] = result.get("scorecard") or {}
            item["overall_score_100"] = (item.get("scorecard") or {}).get("overall_score")
            item["purchase_evidence_completeness_score_100"] = (item.get("scorecard") or {}).get("purchase_evidence_completeness_score_out_of_100")
        tier_items.sort(key=lambda item: (
            not item["within_soft_band"], not item["target_within_total_budget"],
            -(item.get("overall_score_100") or 0), item["target_all_in_jpy"], item["id"],
        ))
        for rank, item in enumerate(tier_items, 1):
            item["display_rank_within_tier"] = rank
        tier_soft_allowance = max(0, int(tier.get("soft_overrun_allowance_jpy", profile.get("soft_overrun_allowance_jpy", default_soft_overrun))))
        tier_soft_ceiling = max(ceiling, int(tier.get("soft_ceiling_total_jpy", ceiling + tier_soft_allowance)))
        target_pc_ceiling = max(0, ceiling - default_peripherals - default_reserve)
        soft_pc_ceiling = max(0, tier_soft_ceiling - default_peripherals - default_reserve)
        grouped.append({
            "id": str(tier.get("id") or "budget_" + str(ceiling)), "total_budget_jpy": ceiling,
            "soft_overrun_allowance_jpy": tier_soft_allowance, "soft_ceiling_total_jpy": tier_soft_ceiling,
            "description_ja": str(tier.get("description_ja") or ""),
            "peripheral_target_jpy": default_peripherals, "contingency_jpy": default_reserve,
            "target_pc_ceiling_jpy": target_pc_ceiling, "pc_planned_ceiling_jpy": soft_pc_ceiling,
            "arithmetic_valid": soft_pc_ceiling + default_peripherals + default_reserve == tier_soft_ceiling,
            "target_arithmetic_valid": target_pc_ceiling + default_peripherals + default_reserve == ceiling,
            "scenario_count": len(tier_items), "builds": tier_items, "purchase_authorized": False,
            "score_comparison_scope": "within_this_budget_tier_only",
        })
    return grouped

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
    storage_choice_ids = [
        str(sid) for sid in (profile.get("storage_choice_ids") or [])
        if str(sid) in parts and (parts[str(sid)].get("category") == "storage")
    ]
    if not storage_choice_ids:
        storage_choice_ids = [str(cid) for cid in fixed_ids if (parts.get(str(cid)) or {}).get("category") == "storage"]
    primary_storage_id = str(profile.get("primary_storage_choice_id") or "")
    if primary_storage_id not in storage_choice_ids:
        primary_storage_id = storage_choice_ids[0] if storage_choice_ids else None

    cooler_choice_ids = [
        str(cid) for cid in (profile.get("cooler_choice_ids") or [])
        if str(cid) in parts and (parts[str(cid)].get("category") == "cpu_cooler")
    ]
    if not cooler_choice_ids:
        cooler_choice_ids = [str(cid) for cid in fixed_ids if (parts.get(str(cid)) or {}).get("category") == "cpu_cooler"]
    primary_cooler_id = str(profile.get("primary_cooler_choice_id") or "")
    if primary_cooler_id not in cooler_choice_ids:
        primary_cooler_id = cooler_choice_ids[0] if cooler_choice_ids else None

    choice_ids_to_remove = set(memory_choice_ids + storage_choice_ids + cooler_choice_ids)
    fixed_ids = [str(cid) for cid in fixed_ids if str(cid) not in choice_ids_to_remove]
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
            "capacity_gb": (memory_part.get("specs") or {}).get("capacity_gb"),
            "role": memory_part.get("role"),
            "target_price_jpy": memory_part.get("target_price_jpy"),
            "fit_scorecard": memory_part.get("fit_scorecard"),
            "market_reference_price_jpy": memory_price.get("market_reference_price_jpy"),
            "price_status": memory_price.get("price_status"),
            "trusted_for_market_estimate": trusted,
            "direct_listing_sellable_price_jpy": memory_price.get("direct_listing_sellable_price_jpy"),
            "direct_listing_sellable_stock_status": memory_price.get("direct_listing_sellable_stock_status"),
            "sellable_listing_price_jpy": memory_price.get("direct_listing_sellable_price_jpy"),
            "stock_status": memory_price.get("direct_listing_sellable_stock_status") or "unknown",
            "direct_listing_offer_count": memory_price.get("direct_listing_offer_count", 0),
            "direct_listing_stock_counts": memory_price.get("direct_listing_stock_counts") or {},
            "direct_listing_display_offers": memory_price.get("direct_listing_display_offers") or [],
            "purchase_url": memory_price.get("purchase_url") or memory_part.get("purchase_url") or memory_part.get("monitor_url"),
        })
    primary_memory_specs = (parts.get(primary_memory_id) or {}).get("specs") or {}
    primary_memory_capacity_gb = primary_memory_specs.get("capacity_gb")
    sellable_memory_candidates = [
        candidate for candidate in memory_candidates
        # Only substitute like-for-like baseline-capacity RAM in the base PC
        # plan. Conditional 64GB replacements are displayed/tracked separately;
        # they must not silently displace the 32GB kit when the full-system
        # target would exceed the user's all-in budget.
        if primary_memory_capacity_gb is not None
        and candidate.get("capacity_gb") == primary_memory_capacity_gb
        and isinstance(candidate.get("sellable_listing_price_jpy"), int)
        and candidate.get("stock_status") in ("in_stock", "low_stock")
    ]
    if sellable_memory_candidates:
        chosen_memory = min(
            sellable_memory_candidates,
            key=lambda candidate: (
                candidate["sellable_listing_price_jpy"],
                0 if candidate["stock_status"] == "in_stock" else 1,
                candidate["id"],
            ),
        )
        selected_memory_id = chosen_memory["id"]
        memory_selection_method = "lowest_fresh_verified_in_stock_direct_seller_price"
    else:
        selected_memory_id = primary_memory_id
        memory_selection_method = "primary_memory_fallback_no_verified_in_stock_alternative"
    selected_memory = parts.get(selected_memory_id) or {}
    memory_choice_selection = {
        "selected_id": selected_memory_id,
        "selected_name": selected_memory.get("name"),
        "selection_method": memory_selection_method,
        "candidates": memory_candidates,
        "rule": "For base builds, choose the lowest fresh exact-SKU direct-seller offer only among candidates matching the configured primary memory capacity. Conditional higher-capacity kits remain visible as alternatives but cannot replace the baseline across all GPU builds unless a separate complete-system budget calculation proves the configuration fits. Comparison-site references are not checkout prices and never authorize purchase."
    }
    def choice_candidate(part_id, price):
        part = parts.get(part_id) or {}
        # A comparison-site reference is never proof that a specific retailer has stock.
        # Only fresh, exact-SKU direct seller offers may qualify a fallback as available.
        sellable_price = price.get("direct_listing_sellable_price_jpy")
        sellable_status = price.get("direct_listing_sellable_stock_status")
        if sellable_status not in ("in_stock", "low_stock"):
            signal = price.get("early_buy_review") if isinstance(price.get("early_buy_review"), dict) else {}
            sellable_status = signal.get("stock_status") or price.get("direct_listing_display_stock_status") or "unknown"
        if not isinstance(sellable_price, int) or isinstance(sellable_price, bool) or sellable_price <= 0:
            sellable_price = None
        return {
            "id": part_id,
            "name": part.get("name"),
            "model_code": part.get("model_code"),
            "target_price_jpy": part.get("target_price_jpy"),
            "fit_scorecard": part.get("fit_scorecard"),
            "market_reference_price_jpy": price.get("market_reference_price_jpy"),
            "display_reference_price_jpy": price.get("display_reference_price_jpy"),
            "sellable_listing_price_jpy": sellable_price,
            "stock_status": sellable_status or "unknown",
            "price_status": price.get("price_status"),
            "trusted_for_market_estimate": bool(price.get("trusted_for_market_estimate")),
            "direct_listing_stock_counts": price.get("direct_listing_stock_counts") or {},
            "direct_listing_offers": price.get("direct_listing_display_offers") or [],
            "purchase_url": price.get("purchase_url") or part.get("purchase_url") or part.get("monitor_url"),
        }

    storage_price_by_id = {}
    storage_candidates = []
    for storage_id in storage_choice_ids:
        storage_part = parts.get(storage_id) or {}
        storage_price = component_price(storage_part, by_id, now, max_age, allowed_domains=allowed_price_domains)
        storage_price_by_id[storage_id] = storage_price
        storage_candidates.append(choice_candidate(storage_id, storage_price))
    sellable_storage_candidates = [
        item for item in storage_candidates
        if isinstance(item.get("sellable_listing_price_jpy"), int)
        and item.get("stock_status") in ("in_stock", "low_stock")
    ]
    if primary_storage_id and any(item["id"] == primary_storage_id for item in sellable_storage_candidates):
        selected_storage_id = primary_storage_id
        storage_selection_method = "keep_primary_if_fresh_in_stock"
    elif sellable_storage_candidates:
        selected_storage_id = min(
            sellable_storage_candidates,
            key=lambda item: (item["sellable_listing_price_jpy"], 0 if item["stock_status"] == "in_stock" else 1, item["id"]),
        )["id"]
        storage_selection_method = "stockout_fallback_lowest_verified_in_stock_price"
    else:
        selected_storage_id = primary_storage_id
        storage_selection_method = "primary_fallback_no_verified_in_stock_alternative"
    storage_choice_selection = {
        "selected_id": selected_storage_id,
        "selection_method": storage_selection_method,
        "candidates": storage_candidates,
        "rule": "Keep the preferred 1TB NVMe SSD when the exact SKU is freshly verified in stock; otherwise use the least-cost freshly verified in-stock 1TB NVMe alternative. If none is verified, keep the baseline in the plan but block purchase."
    }

    cooler_price_by_id = {}
    cooler_candidates = []
    for cooler_id in cooler_choice_ids:
        cooler_part = parts.get(cooler_id) or {}
        cooler_price = component_price(cooler_part, by_id, now, max_age, allowed_domains=allowed_price_domains)
        cooler_price_by_id[cooler_id] = cooler_price
        cooler_candidates.append(choice_candidate(cooler_id, cooler_price))
    sellable_cooler_candidates = [
        item for item in cooler_candidates
        if isinstance(item.get("sellable_listing_price_jpy"), int)
        and item.get("stock_status") in ("in_stock", "low_stock")
    ]
    if primary_cooler_id and any(item["id"] == primary_cooler_id for item in sellable_cooler_candidates):
        selected_cooler_id = primary_cooler_id
        cooler_selection_method = "keep_primary_if_fresh_in_stock"
    elif sellable_cooler_candidates:
        selected_cooler_id = min(
            sellable_cooler_candidates,
            key=lambda item: (item["sellable_listing_price_jpy"], 0 if item["stock_status"] == "in_stock" else 1, item["id"]),
        )["id"]
        cooler_selection_method = "stockout_fallback_lowest_verified_in_stock_price"
    else:
        selected_cooler_id = primary_cooler_id
        cooler_selection_method = "primary_fallback_no_verified_in_stock_alternative"
    cooler_choice_selection = {
        "selected_id": selected_cooler_id,
        "selection_method": cooler_selection_method,
        "candidates": cooler_candidates,
        "rule": "Keep the preferred cooler when its exact SKU is freshly verified in stock; otherwise use a compatible alternative with a verified in-stock listing. Cooling capacity remains a trade-off to review, not an assumed equivalence."
    }

    gpu_fallbacks = profile.get("gpu_fallback_candidates_by_choice") or {}
    gpu_price_by_id = {}
    gpu_candidate_prices = {}
    for base_gpu_id in gpu_ids:
        candidate_ids = [str(base_gpu_id)] + [
            str(x) for x in (gpu_fallbacks.get(str(base_gpu_id)) or [])
            if str(x) in parts and (parts[str(x)].get("category") == "gpu")
        ]
        candidate_records = []
        for candidate_id in dict.fromkeys(candidate_ids):
            price = component_price(parts.get(candidate_id) or {}, by_id, now, max_age, allowed_domains=allowed_price_domains)
            gpu_price_by_id[candidate_id] = price
            candidate_records.append(choice_candidate(candidate_id, price))
        gpu_candidate_prices[str(base_gpu_id)] = candidate_records

    # All amounts are JPY. The configured PC ceiling is a fallback maximum, not
    # an amount that can be spent in addition to peripherals and contingency.
    pc_budget = int(profile.get("pc_budget_jpy", 395000))
    all_budget = int(profile.get("total_budget_jpy", 400000))
    peripheral_budget = int(profile.get("peripheral_budget_jpy", 35000))
    contingency = int(profile.get("unallocated_contingency_jpy", 0))
    pc_target = int(profile.get("pc_target_jpy", 360000))
    soft_overrun_allowance = int(profile.get("soft_overrun_allowance_jpy", 20000))
    soft_ceiling_total = int(profile.get("soft_ceiling_total_jpy", all_budget + soft_overrun_allowance))
    pc_planned_budget = max(0, min(pc_budget, soft_ceiling_total - peripheral_budget - contingency))
    shipping = int(profile.get("build_shipping_reserve_jpy", 0))
    small_parts = int(profile.get("small_parts_reserve_jpy", 0))
    builds = []

    for rank, gpu_id in enumerate(gpu_ids, 1):
        gpu_fallback_ids = [
            str(x) for x in (gpu_fallbacks.get(str(gpu_id)) or [])
            if str(x) in parts and (parts[str(x)].get("category") == "gpu")
        ]
        gpu_candidate_ids = list(dict.fromkeys([str(gpu_id)] + gpu_fallback_ids))
        sellable_gpu_ids = [
            candidate_id for candidate_id in gpu_candidate_ids
            if isinstance(gpu_price_by_id.get(candidate_id, {}).get("direct_listing_sellable_price_jpy"), int)
            and gpu_price_by_id.get(candidate_id, {}).get("direct_listing_sellable_stock_status") in ("in_stock", "low_stock")
        ]
        if str(gpu_id) in sellable_gpu_ids:
            selected_gpu_id = str(gpu_id)
            gpu_selection_method = "keep_primary_exact_sku_if_fresh_in_stock"
        elif sellable_gpu_ids:
            selected_gpu_id = min(
                sellable_gpu_ids,
                key=lambda candidate_id: (
                    gpu_price_by_id[candidate_id]["direct_listing_sellable_price_jpy"],
                    (parts.get(candidate_id) or {}).get("target_price_jpy", 10**12),
                    candidate_id,
                ),
            )
            gpu_selection_method = "same_gpu_tier_stockout_fallback_lowest_verified_in_stock_price"
        else:
            selected_gpu_id = str(gpu_id)
            gpu_selection_method = "primary_exact_sku_fallback_no_verified_in_stock_alternative"

        selected_ids = fixed_ids + ([selected_memory_id] if selected_memory_id else []) + ([selected_storage_id] if selected_storage_id else []) + ([selected_cooler_id] if selected_cooler_id else []) + [selected_gpu_id]
        components, missing, market_subtotal = [], [], 0
        all_parts_referenced = True
        target_parts = 0
        current_sellable_listing_subtotal = 0
        current_sellable_part_ids = []
        current_low_stock_part_ids = []
        current_confirmed_out_of_stock_part_ids = []
        current_unconfirmed_availability_part_ids = []
        current_stock_counts = {
            "in_stock": 0, "low_stock": 0, "preorder_or_backorder": 0,
            "unknown": 0, "out_of_stock": 0, "stale": 0,
        }
        current_listing_offer_counts = {
            "in_stock": 0, "low_stock": 0, "preorder_or_backorder": 0,
            "unknown": 0, "out_of_stock": 0, "stale": 0,
        }
        for cid in selected_ids:
            part = parts.get(cid)
            if not part:
                missing.append(cid)
                all_parts_referenced = False
                continue
            target = part.get("target_price_jpy")
            if isinstance(target, int) and not isinstance(target, bool):
                target_parts += target
            if cid in memory_price_by_id:
                price = memory_price_by_id[cid]
            elif cid in storage_price_by_id:
                price = storage_price_by_id[cid]
            elif cid in cooler_price_by_id:
                price = cooler_price_by_id[cid]
            elif cid in gpu_price_by_id:
                price = gpu_price_by_id[cid]
            else:
                price = component_price(part, by_id, now, max_age, allowed_domains=allowed_price_domains)
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
                "early_buy_review": price.get("early_buy_review") if isinstance(price.get("early_buy_review"), dict) else None,
                "direct_listing_display_age_minutes": price.get("direct_listing_display_age_minutes"),
                "direct_listing_display_price_context": price.get("direct_listing_display_price_context"),
                "direct_listing_display_offers": price.get("direct_listing_display_offers") or [],
                "direct_listing_sellable_price_jpy": price.get("direct_listing_sellable_price_jpy"),
                "direct_listing_sellable_url": price.get("direct_listing_sellable_url"),
                "direct_listing_sellable_stock_status": price.get("direct_listing_sellable_stock_status"),
                "direct_listing_sellable_retrieval_time": price.get("direct_listing_sellable_retrieval_time"),
                "direct_listing_stock_counts": price.get("direct_listing_stock_counts") or {},
                "direct_listing_offer_count": price.get("direct_listing_offer_count", 0),
                "direct_listing_sellable_offer_count": price.get("direct_listing_sellable_offer_count", 0),
                "direct_listing_validation_diagnostics": price.get("direct_listing_validation_diagnostics") or [],
                "direct_listing_display_is_estimate_eligible": False,
                "direct_listing_display_purchase_allowed": False,
                "track_price": bool(part.get("track_price")), "specs": part.get("specs") or {},
                "fit_scorecard": part.get("fit_scorecard"),
                "image_url": part.get("image_url"), "image_source_url": part.get("image_source_url"),
                "image_note": part.get("image_note"), "image_checked_at": part.get("image_checked_at"),
                "notes": part.get("notes"), "bf_actual_authorized": False
            }
            components.append(component)
            sellable_price = price.get("direct_listing_sellable_price_jpy")
            sellable_status = price.get("direct_listing_sellable_stock_status")
            observed_counts = price.get("direct_listing_stock_counts") or {}
            if isinstance(sellable_price, int) and not isinstance(sellable_price, bool) and sellable_price > 0 and sellable_status in ("in_stock", "low_stock"):
                current_sellable_listing_subtotal += sellable_price
                current_sellable_part_ids.append(cid)
                if sellable_status == "low_stock":
                    current_low_stock_part_ids.append(cid)
            else:
                has_sold_out = int(observed_counts.get("out_of_stock") or 0) > 0
                has_unknown = int(observed_counts.get("unknown") or 0) > 0 or int(observed_counts.get("stale") or 0) > 0
                has_preorder = int(observed_counts.get("preorder_or_backorder") or 0) > 0
                has_sellable_status = (
                    int(observed_counts.get("in_stock") or 0) > 0
                    or int(observed_counts.get("low_stock") or 0) > 0
                )
                if has_sold_out and not has_unknown and not has_preorder and not has_sellable_status:
                    current_confirmed_out_of_stock_part_ids.append(cid)
                else:
                    current_unconfirmed_availability_part_ids.append(cid)
            for status, count in (price.get("direct_listing_stock_counts") or {}).items():
                if status in current_stock_counts and isinstance(count, int) and not isinstance(count, bool):
                    current_listing_offer_counts[status] += max(0, count)
                    if count > 0:
                        current_stock_counts[status] += 1
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

        selected_cpu_id = next(
            (str(cid) for cid in selected_ids if (parts.get(str(cid)) or {}).get("category") == "cpu"),
            None,
        )
        compat, checks = compatibility_checks(
            parts, profile, selected_gpu_id, selected_memory_id, selected_storage_id, selected_cooler_id,
            cpu_part_id=selected_cpu_id,
        )
        workload_fit = assess_workload_fit(profile, parts, selected_ids, selected_gpu_id, selected_memory_id)
        target_pc = target_parts + shipping + small_parts
        target_all_in = target_pc + peripheral_budget + contingency
        market_estimate = market_subtotal + shipping + small_parts if all_parts_referenced and not missing else None
        all_in_market = market_estimate + peripheral_budget + contingency if market_estimate is not None else None
        gpu_part = parts.get(selected_gpu_id) or {}
        selected_gpu_price = gpu_price_by_id.get(selected_gpu_id) or {}
        live_gpu_price = selected_gpu_price.get("market_reference_price_jpy")
        gpu_target = gpu_part.get("target_price_jpy")
        reduction = round((live_gpu_price - gpu_target) * 100.0 / live_gpu_price, 1) if isinstance(live_gpu_price, int) and isinstance(gpu_target, int) and live_gpu_price > gpu_target else None

        if compat == "FAIL":
            decision = "COMPATIBILITY_FAIL"
        elif target_all_in > soft_ceiling_total:
            decision = "OVER_SOFT_BUDGET_BAND"
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
            "selected_gpu_part_id": selected_gpu_id,
            "gpu_selection_method": gpu_selection_method,
            "gpu_selection_candidates": gpu_candidate_prices.get(str(gpu_id), []),
            "selected_memory_id": selected_memory_id,
            "memory_choice_method": memory_selection_method,
            "memory_choice_candidates": memory_candidates,
            "selected_storage_id": selected_storage_id,
            "storage_selection_method": storage_selection_method,
            "storage_choice_candidates": storage_candidates,
            "selected_cooler_id": selected_cooler_id,
            "cooler_selection_method": cooler_selection_method,
            "cooler_choice_candidates": cooler_candidates,
            "components": components, "workload_fit": workload_fit, "target_parts_subtotal_jpy": target_parts,
            "build_shipping_reserve_jpy": shipping, "small_parts_reserve_jpy": small_parts,
            "target_pc_total_jpy": target_pc, "pc_budget_jpy": pc_budget,
            "pc_planned_budget_jpy": pc_planned_budget,
            "target_pc_budget_delta_jpy": target_pc - pc_budget,
            "target_planned_pc_budget_delta_jpy": target_pc - pc_planned_budget,
            "target_peripheral_budget_jpy": peripheral_budget, "target_all_in_jpy": target_all_in,
            "total_budget_jpy": all_budget, "target_remaining_budget_jpy": all_budget-target_all_in,
            "soft_ceiling_total_jpy": soft_ceiling_total,
            "soft_overrun_allowance_jpy": soft_overrun_allowance,
            "target_remaining_soft_budget_jpy": soft_ceiling_total-target_all_in,
            "target_contingency_jpy": contingency,
            "target_within_pc_budget": target_pc <= pc_budget,
            "target_within_planned_pc_budget": target_pc <= pc_planned_budget,
            "target_within_total_budget": target_all_in <= all_budget,
            "target_within_soft_total_budget": target_all_in <= soft_ceiling_total,
            "current_sellable_listing_subtotal_jpy": current_sellable_listing_subtotal,
            "current_sellable_listing_part_count": len(current_sellable_part_ids),
            "current_sellable_listing_required_part_count": len(selected_ids),
            "current_sellable_listing_coverage_pct": round(100.0 * len(current_sellable_part_ids) / len(selected_ids), 1) if selected_ids else 0.0,
            "current_sellable_listing_part_ids": current_sellable_part_ids,
            "current_parts_without_sellable_listing": [cid for cid in selected_ids if cid not in set(current_sellable_part_ids)],
            "current_low_stock_part_ids": current_low_stock_part_ids,
            "current_confirmed_out_of_stock_part_ids": current_confirmed_out_of_stock_part_ids,
            "current_unconfirmed_availability_part_ids": current_unconfirmed_availability_part_ids,
            "current_stock_confirmed_component_count": current_stock_counts,
            "current_retailer_listing_offer_count_by_status": current_listing_offer_counts,
            "current_listing_subtotal_is_complete_build_price": False,
            "current_listing_subtotal_is_checkout_price": False,
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

    # Add one like-for-like CPU alternative while preserving three primary GPU-tier builds.
    # Recursion uses a copied config with the alternative list emptied, so it is bounded.
    cpu_alternative_scenarios = []
    primary_gpu_for_cpu_comparison = str(
        profile.get("cpu_comparison_gpu_choice_id")
        or profile.get("primary_gpu_choice_id")
        or (gpu_ids[0] if gpu_ids else "")
    )
    primary_gpu_build = next(
        (build for build in builds if str(build.get("gpu_choice_id")) == primary_gpu_for_cpu_comparison),
        None,
    )
    base_cpu_id = next(
        (str(cid) for cid in fixed_ids if (parts.get(str(cid)) or {}).get("category") == "cpu"),
        "cpu-ryzen7-9700x",
    )
    for alternative_cpu_id in profile.get("cpu_alternative_choice_ids") or []:
        alternative_cpu_id = str(alternative_cpu_id)
        alternative_cpu = parts.get(alternative_cpu_id) or {}
        if alternative_cpu.get("category") != "cpu" or primary_gpu_build is None or alternative_cpu_id == base_cpu_id:
            continue
        alternate_config = json.loads(json.dumps(config))
        alternate_profile = alternate_config.get("profile") or {}
        original_fixed_ids = [str(cid) for cid in (alternate_profile.get("fixed_part_ids") or [])]
        alternate_profile["fixed_part_ids"] = [
            cid for cid in original_fixed_ids if (parts.get(cid) or {}).get("category") != "cpu"
        ] + [alternative_cpu_id]
        alternate_profile["cpu_alternative_choice_ids"] = []
        alternate_profile["gpu_choice_ids"] = [primary_gpu_for_cpu_comparison]
        alternate_plan = build_plan(alternate_config, snapshot, now=now)
        if not alternate_plan.get("builds"):
            continue
        alternative_build = alternate_plan["builds"][0]
        alternative_build["cpu_alternative_candidate"] = True
        alternative_build["cpu_choice_id"] = alternative_cpu_id
        alternative_build["id"] = "self-build-cpu-comparison-" + alternative_cpu_id
        alternative_build["name"] = "CPU比較案：" + str(alternative_cpu.get("name") or alternative_cpu_id) + " + " + str((parts.get(primary_gpu_for_cpu_comparison) or {}).get("name") or primary_gpu_for_cpu_comparison)
        base_cpu_target = int((parts.get(base_cpu_id) or {}).get("target_price_jpy") or 0)
        alternative_cpu_target = int(alternative_cpu.get("target_price_jpy") or 0)
        alternative_build["target_cpu_delta_vs_base_jpy"] = alternative_cpu_target - base_cpu_target
        alternative_build["target_all_in_delta_vs_base_jpy"] = int(alternative_build.get("target_all_in_jpy") or 0) - int(primary_gpu_build.get("target_all_in_jpy") or 0)
        alternative_build["cpu_comparison_gpu_id"] = primary_gpu_for_cpu_comparison
        alternative_build["cpu_comparison_is_purchase_authorization"] = False
        cpu_alternative_scenarios.append({
            "cpu_choice_id": alternative_cpu_id,
            "cpu_name": alternative_cpu.get("name"),
            "cpu_cores": (alternative_cpu.get("specs") or {}).get("cores"),
            "cpu_threads": (alternative_cpu.get("specs") or {}).get("threads"),
            "cpu_target_price_jpy": alternative_cpu.get("target_price_jpy"),
            "target_cpu_delta_vs_base_jpy": alternative_build["target_cpu_delta_vs_base_jpy"],
            "target_pc_total_jpy": alternative_build.get("target_pc_total_jpy"),
            "target_all_in_jpy": alternative_build.get("target_all_in_jpy"),
            "target_all_in_delta_vs_base_jpy": alternative_build["target_all_in_delta_vs_base_jpy"],
            "compatibility_status": alternative_build.get("compatibility_status"),
            "decision": alternative_build.get("decision"),
            "build": alternative_build,
            "purchase_authorized": False,
        })

    # Score primary GPU candidates and CPU comparison builds together so their
    # 100-point scores use the same price-efficiency denominator.
    all_candidate_builds = score_and_rank_builds(
        builds + [item["build"] for item in cpu_alternative_scenarios]
    )
    for overall_rank, item in enumerate(all_candidate_builds, 1):
        item["overall_comparison_rank"] = overall_rank
    builds = [item for item in all_candidate_builds if not item.get("cpu_alternative_candidate")]
    builds.sort(key=lambda item: (
        -(item.get("scorecard") or {}).get("overall_score", 0.0),
        item.get("target_all_in_jpy") if isinstance(item.get("target_all_in_jpy"), int) else 10**12,
        str(item.get("gpu_choice_id") or ""),
    ))
    for rank, build in enumerate(builds, 1):
        build["rank"] = rank
    for item in cpu_alternative_scenarios:
        item["overall_comparison_rank"] = item["build"].get("overall_comparison_rank")
        item["scorecard"] = item["build"].get("scorecard") or {}

    cpu_dark_horse_candidates = []
    primary_cpu = parts.get(base_cpu_id) or {}
    base_cpu_target = int(primary_cpu.get("target_price_jpy") or 0)
    base_all_in = int(primary_gpu_build.get("target_all_in_jpy") or 0) if primary_gpu_build else None
    for dark_horse_id in profile.get("cpu_dark_horse_ids") or []:
        dark_cpu = parts.get(str(dark_horse_id)) or {}
        if dark_cpu.get("category") != "cpu":
            continue
        dark_target = dark_cpu.get("target_price_jpy")
        increment = int(dark_target) - base_cpu_target if isinstance(dark_target, int) else None
        target_all_in_floor = base_all_in + increment if isinstance(base_all_in, int) and isinstance(increment, int) else None
        cpu_dark_horse_candidates.append({
            "cpu_choice_id": str(dark_horse_id),
            "cpu_name": dark_cpu.get("name"),
            "cpu_cores": (dark_cpu.get("specs") or {}).get("cores"),
            "cpu_threads": (dark_cpu.get("specs") or {}).get("threads"),
            "cpu_tdp_w": (dark_cpu.get("specs") or {}).get("package_power_w"),
            "cpu_target_price_jpy": dark_target,
            "target_cpu_delta_vs_base_jpy": increment,
            "target_all_in_floor_with_current_cooler_jpy": target_all_in_floor,
            "over_budget_before_cooling_change_jpy": max(0, target_all_in_floor - soft_ceiling_total) if isinstance(target_all_in_floor, int) else None,
            "over_reference_target_before_cooling_change_jpy": max(0, target_all_in_floor - all_budget) if isinstance(target_all_in_floor, int) else None,
            "manufacturer_cooling_guidance": (dark_cpu.get("specs") or {}).get("recommended_cooler_guidance"),
            "complete_build_price_verified": False,
            "cooling_cost_included": False,
            "purchase_authorized": False,
            "note_ja": "高コア数大穴。参考下限はCPU目標額の差分のみを現行構成に置き換えた値で、冷却変更費用を含まない。完全構成のランキング・購入価格として扱わない。",
            "source_url": dark_cpu.get("image_source_url") or dark_cpu.get("monitor_url"),
        })



    budget_scenarios = build_budget_scenarios(profile, parts, by_id, now, max_age)

    return {
        "generated_at": iso(now), "schema_version": 1, "project": "DIY_PC",
        "budget_scenarios": budget_scenarios,
        "budget_scenario_policy": profile.get("budget_scenario_policy") or config.get("budget_scenario_policy") or {},
        "source_policy": "Comparison-site prices are market references only. This plan never authorizes a purchase; official seller-specific BF price evidence is missing.",
        "purchase_method_policy": {
            "primary_method": "SELF_BUILD",
            "assembly_time_is_constraint": bool(profile.get("assembly_time_is_constraint", False)),
            "assembly_time_penalty_points": int(profile.get("assembly_time_penalty_points", 0)),
            "bto_role": profile.get("bto_role", "REFERENCE_BENCHMARK_ONLY"),
            "selection_policy": profile.get("selection_policy") or "Prioritize self-build; do not penalize assembly time."
        },
        "selection_factors": profile.get("purchase_decision_factors") or [],
        "score_policy": {
            "overall_score": "ゲーム25 + ゲーム制作20 + 分析/AI20 + 勉強/同時利用10 + BF目標総額ベースの相対価格効率15 + 互換性10 = 100点",
            "purchase_evidence_completeness_score": "直接価格/型番/PIT 30% + 販売可能在庫 25% + 検証済み決済総額 25% + 互換性ステータス 20%; 購入許可ではない",
            "gpu_1440p_ultra_raster_reference_mean_fps": {"gpu-rtx5070ti-16gb": 116.8, "gpu-rtx5070-12gb": 96.4, "gpu-rtx5060ti-16gb": 73.4},
            "gpu_gaming_benchmark_source_url": "https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html",
            "gpu_gaming_benchmark_source_updated": "2026-06-24",
            "benchmark_or_fps_measurement": False,
            "purchase_authorization_automatic": False
        },
        "workload_profile": profile.get("workload_profile") or {},
        "cpu_alternative_scenarios": cpu_alternative_scenarios,
        "cpu_dark_horse_candidates": cpu_dark_horse_candidates,
        "total_budget_jpy": all_budget, "peripheral_budget_jpy": peripheral_budget,
        "soft_ceiling_total_jpy": soft_ceiling_total,
        "soft_overrun_allowance_jpy": soft_overrun_allowance,
        "pc_budget_jpy": pc_budget, "pc_planned_budget_jpy": pc_planned_budget,
        "pc_target_jpy": pc_target,
        "unallocated_contingency_jpy": contingency,
        "build_shipping_reserve_jpy": shipping, "small_parts_reserve_jpy": small_parts,
        "budget_arithmetic_valid": pc_planned_budget + peripheral_budget + contingency == soft_ceiling_total,
        "required_categories": profile.get("required_categories") or [],
        "memory_choice_selection": memory_choice_selection,
        "storage_choice_selection": storage_choice_selection,
        "cooler_choice_selection": cooler_choice_selection,
        "gpu_fallback_candidates_by_choice": {
            base_id: [
                candidate for candidate in gpu_candidate_prices.get(base_id, [])
                if candidate.get("id") != base_id
            ]
            for base_id in gpu_candidate_prices
        },
        "stockout_policy": {
            "direct_stock_signals_required": True,
            "sold_out_and_fetch_error_are_distinct": True,
            "never_count_sold_out_or_unknown_listings_as_buyable": True,
            "fallback_selection_requires_fresh_exact_sku_in_stock_listing": True,
            "low_stock_is_a_risk_flag_not_a_guaranteed_order": True,
            "partial_listing_subtotal_is_not_a_complete_build_or_checkout_price": True,
        },
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


COMPONENT_FIT_SCORE_WEIGHTS = {
    "workload_fit_points": 40,
    "headroom_points": 25,
    "quality_reliability_points": 20,
    "integration_flexibility_points": 15,
}


def component_suitability_score(part):
    """Return a transparent curated fit score; never infer missing component qualities.

    This score is intentionally distinct from purchase evidence and the complete-build
    score. It is profile-specific expert rubric input, not a hardware benchmark.
    """
    part = part if isinstance(part, dict) else {}
    rubric = part.get("fit_scorecard") if isinstance(part.get("fit_scorecard"), dict) else {}
    points = {}
    for key, maximum in COMPONENT_FIT_SCORE_WEIGHTS.items():
        value = rubric.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
            return {
                "score": None,
                "out_of": 100,
                "breakdown": {},
                "scorecard_complete": False,
                "missing_or_invalid_fields": [
                    field for field, limit in COMPONENT_FIT_SCORE_WEIGHTS.items()
                    if not isinstance(rubric.get(field), int)
                    or isinstance(rubric.get(field), bool)
                    or not 0 <= rubric.get(field) <= limit
                ],
                "rationale_ja": str(rubric.get("rationale_ja") or ""),
                "limitations_ja": str(rubric.get("limitations_ja") or ""),
                "score_basis": "curated profile-fit rubric; incomplete inputs fail closed",
                "purchase_authorized": False,
            }
        points[key] = value
    return {
        "score": sum(points.values()),
        "out_of": 100,
        "breakdown": points,
        "scorecard_complete": True,
        "missing_or_invalid_fields": [],
        "rationale_ja": str(rubric.get("rationale_ja") or ""),
        "limitations_ja": str(rubric.get("limitations_ja") or ""),
        "score_basis": "curated profile-fit rubric; not a measured benchmark or purchase-readiness score",
        "purchase_authorized": False,
    }


def component_purchase_evidence_score(part, build, now=None):
    """Score whether this exact PC component is ready to purchase, not its performance.

    30 direct exact-SKU price/PIT, 25 sellable stock (18 when low), 25 verified
    checkout total, 10 relevant compatibility checks, 10 explicit warranty/return
    evidence. A comparison-site price never earns direct-price or stock points.
    """
    part = part if isinstance(part, dict) else {}
    build = build if isinstance(build, dict) else {}
    now = now or now_jst()
    points = {
        "direct_price_identity_pit": 0,
        "sellable_stock": 0,
        "verified_checkout_total": 0,
        "compatibility": 0,
        "warranty_and_returns": 0,
    }

    def positive_int(value):
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    direct_offers = [
        offer for offer in (part.get("direct_listing_display_offers") or [])
        if isinstance(offer, dict)
        and offer.get("stock_signal_fresh") is True
        and positive_int(offer.get("price_jpy"))
        and offer.get("price_source_mode") in ("direct_structured", "direct_meta", "direct_text")
        and str(offer.get("url") or "").startswith("https://")
    ]
    if direct_offers:
        points["direct_price_identity_pit"] = 30
        statuses = {str(offer.get("stock_status") or "unknown") for offer in direct_offers}
        if "in_stock" in statuses:
            points["sellable_stock"] = 25
        elif "low_stock" in statuses:
            points["sellable_stock"] = 18

    signal = part.get("early_buy_review") if isinstance(part.get("early_buy_review"), dict) else {}
    checkout_total = signal.get("verified_checkout_total_jpy")
    checkout_valid = (
        bool(direct_offers) and points["sellable_stock"] > 0
        and positive_int(checkout_total)
        and signal.get("checkout_total_verified") is True
        and signal.get("price_verified") is True
        and signal.get("identity_verified") is True
        and signal.get("pit_valid") is True
        and signal.get("stock_status") in ("in_stock", "low_stock")
    )
    if checkout_valid:
        points["verified_checkout_total"] = 25

    compatibility_checks = {
        str(item.get("check")): str(item.get("status") or "REVIEW")
        for item in (build.get("compatibility_checks") or [])
        if isinstance(item, dict) and item.get("check")
    }
    category = str(part.get("category") or "")
    relevant_checks = {
        "cpu": ("cpu_motherboard_socket", "cpu_bios_support"),
        "gpu": ("gpu_case_clearance", "gpu_slot_thickness", "psu_wattage", "gpu_power_connector"),
        "motherboard": ("cpu_motherboard_socket", "cpu_bios_support", "memory_type_capacity_dual_channel",
                        "storage_capacity_interface", "motherboard_case_form_factor"),
        "memory": ("memory_type_capacity_dual_channel", "memory_qvl"),
        "storage": ("storage_capacity_interface",),
        "psu": ("psu_wattage", "gpu_power_connector"),
        "case": ("motherboard_case_form_factor", "gpu_case_clearance", "gpu_slot_thickness", "cooler_case_clearance"),
        "cpu_cooler": ("cooler_socket", "cooler_case_clearance"),
        "os_license": ("os_license",),
    }.get(category, ())
    status_value = {"PASS": 1.0, "REVIEW": 0.5, "FAIL": 0.0}
    matched = [compatibility_checks[key] for key in relevant_checks if key in compatibility_checks]
    # Missing required checks are zero, not silently removed from the denominator.
    # This prevents one passing check from earning full compatibility evidence credit.
    if relevant_checks:
        all_relevant_statuses = [compatibility_checks.get(key, "MISSING") for key in relevant_checks]
        points["compatibility"] = round(
            10 * sum(status_value.get(status, 0.0) for status in all_relevant_statuses)
            / len(relevant_checks)
        )

    terms_verified = bool(
        signal.get("warranty_return_conditions_verified") is True
        or part.get("warranty_return_conditions_verified") is True
        or (
            signal.get("warranty_verified") is True and signal.get("return_policy_verified") is True
        )
    )
    points["warranty_and_returns"] = 10 if terms_verified else 0
    return {
        "score": sum(points.values()),
        "out_of": 100,
        "breakdown": points,
        "direct_price_verified_fresh": bool(direct_offers),
        "sellable_stock_verified_fresh": points["sellable_stock"] > 0,
        "checkout_total_verified": points["verified_checkout_total"] == 25,
        "compatibility_checks_used": list(matched),
        "compatibility_checks_required": list(relevant_checks),
        "missing_compatibility_checks": [key for key in relevant_checks if key not in compatibility_checks],
        "warranty_return_terms_verified": terms_verified,
    }


def component_markdown_link(part):
    """Render a safe, explicit product link for every configured build component."""
    part = part if isinstance(part, dict) else {}
    name = re.sub(r"\s+", " ", str(part.get("name") or part.get("id") or "商品名未設定")).strip()
    name = name.replace("|", "／").replace("[", "（").replace("]", "）")
    url = None
    for key in ("purchase_url", "url", "monitor_url", "source_url"):
        candidate = str(part.get(key) or "").strip()
        try:
            parsed = urlparse(candidate)
        except ValueError:
            continue
        if parsed.scheme.lower() in ("https", "http") and parsed.hostname and not parsed.username and not parsed.password:
            url = candidate
            break
    if not url:
        return name + "（商品URL未登録・要修正）"
    target = url.replace("(", "%28").replace(")", "%29")
    return "[{}]({})".format(name, target)


def render_plan_markdown(plan):
    workload_profile = plan.get("workload_profile") or {}
    game_dev = workload_profile.get("game_development") or {}
    workload_summary_lines = [
        "## 用途評価：ゲームを遊ぶだけでなく、ゲーム制作も主要要件",
        "",
        "制作対象エンジン: " + "、".join(game_dev.get("target_engines") or ["未設定"]),
        "想定プロジェクト: " + "、".join(game_dev.get("target_project_types") or ["未設定"]),
        "制作ベースラインはRAM 32GB・専用GPU VRAM 8GB以上・SSD 1TB以上。64GB RAM・2TB SSDは、大きなアセット、ビルド、AI/分析ツールの同時利用に備える本プロジェクト上の優先目標です。予算・価格証拠を満たし、購入時の構成に含まれる場合だけ達成とし、後からの増設は想定しません。",
        "Unreal Engine自体をソースからローカルでフルビルドする用途は別扱いです。Epicの12～16コアという実用的な目安に対し、8コアのRyzen 7 9700Xはここでは妥協点であり、通常のゲームプロジェクト制作が不可という意味ではありません。",
        "",
        "|GPU候補|制作評価|RAM|GPU VRAM|SSD|Unreal Engineソースフルビルド|",
        "|---|---|---:|---:|---:|---|",
    ]
    for build in plan.get("builds") or []:
        fit = build.get("workload_fit") or {}
        hw = fit.get("selected_hardware") or {}
        dev = fit.get("game_development") or {}
        compile_fit = dev.get("unreal_engine_source_compile") or {}
        workload_summary_lines.append("|{}|{}|{}GB|{}GB|{}GB|{}|".format(
            build.get("name") or build.get("id"),
            fit.get("summary_label") or "仕様未確認",
            hw.get("system_ram_gb") if hw.get("system_ram_gb") is not None else "未確認",
            hw.get("dedicated_gpu_vram_gb") if hw.get("dedicated_gpu_vram_gb") is not None else "未確認",
            hw.get("primary_ssd_gb") if hw.get("primary_ssd_gb") is not None else "未確認",
            compile_fit.get("status") or "未確認",
        ))
    workload_summary_lines.extend([
        "",
        "評価対象ゲーム: " + "、".join((workload_profile.get("gaming") or {}).get("targets") or ["未設定"]),
        "勉強・調査: " + "、".join((workload_profile.get("study_and_research") or {}).get("targets") or ["未設定"]),
        "データ分析・自動化・AI: " + "、".join((workload_profile.get("analysis_and_automation") or workload_profile.get("ai_and_data_analysis") or {}).get("targets") or ["未設定"]),
        "同時利用想定: IDE/ゲームエンジン/Python/テスト/資料閲覧/ブラウザー/AIツール。CPU・RAM・VRAM・SSD・冷却を用途別に確認し、すべての分析処理がGPUで速くなるとは仮定しません。",
    ])
    lines = [
        "# 自作PCパーツ構成・価格監視", "",
        "更新: " + str(plan.get("generated_at")),
        "予算（すべて日本円）: PC本体基準目標 " + money(plan.get("pc_target_jpy")) +
        " / PC本体計画上限 " + money(plan.get("pc_planned_budget_jpy")) +
        " / PC本体単体の比較上限（総額上限ではない） " + money(plan.get("pc_budget_jpy")) +
        " / 周辺機器計画枠 " + money(plan.get("peripheral_budget_jpy")) +
        " / 総額予備費 " + money(plan.get("unallocated_contingency_jpy")) +
        " / 総額目標 " + money(plan.get("total_budget_jpy")) +
        " / 比較検討帯上限 " + money(plan.get("soft_ceiling_total_jpy")),
        "",
        "**購入方式:** 自作PCを正式な本命として最適化します。組み立て時間・作業時間は減点しません。BTOは同等仕様での総額・部品品質・保証のベンチマークとして比較し、便利さだけを理由に自作から切り替えません。",
        "",
        "**注意:** BF購入目標は購入希望額です。比較サイト価格は市場参考値であり、店舗の決済価格・在庫・公式BF実売価格ではありません。現在のデータから購入許可は出しません。",
        "",
        *workload_summary_lines,
        "",
        "**メモリ選択:** " + str((plan.get("memory_choice_selection") or {}).get("selected_name") or "未選定"),
        "選定方法: " + str((plan.get("memory_choice_selection") or {}).get("selection_method") or "未確認"),
        "基本構成では、既定の32GB容量を満たす販売可能な完全一致キットだけを代替比較します。64GBは条件付き置換候補として表示し、全構成へ一律に入れません。40万円は総額目標で、用途上の改善が明確なら42万円までの許容帯を比較し、さらに超える案は45万円シナリオで別評価します。",
        "価格比較では、型番一致・鮮度・PIT条件を満たす直接販売店の掲載価格と在庫を確認します。比較サイト価格は決済価格ではなく、購入許可も意味しません。",
        "",
        *(["- {} / BF目標 {} / 比較参考 {} / 状態 {} / {}".format(
            item.get("name"), money(item.get("target_price_jpy")),
            money(item.get("market_reference_price_jpy")) if item.get("trusted_for_market_estimate") else "未検証",
            item.get("price_status"),
            "[商品ページ]({})".format(item.get("purchase_url")) if item.get("purchase_url") else "リンク未確認"
        ) for item in (plan.get("memory_choice_selection") or {}).get("candidates", [])]),
        "",
        "## 現時点の販売店掲載価格・在庫（BF目標とは別集計）",
        "",
        "以下は、商品型番・取得時刻が検証できた直接販売店ページのうち、在庫あり／在庫少と明示された掲載価格だけの部分小計です。注文カートの最終価格ではなく、在庫不明・売り切れ・未取得の部品は合計に埋めません。必須部品すべてに販売可能な掲載価格がそろわない構成は、PC本体価格を算定できません。",
        "",
        "|構成|販売可能掲載価格が確認できた部品|部品数カバー率|確認済み掲載価格の部分小計|在庫切れ掲載（売り切れ）|在庫不明掲載|鮮度切れ掲載|販売可能価格が未確認の部品|",
        "|---|---|---:|---:|---:|---:|---:|---|"
    ]
    for build in plan.get("builds") or []:
        counts = build.get("current_retailer_listing_offer_count_by_status") or {}
        names = {str(part.get("id")): str(part.get("name") or part.get("id")) for part in (build.get("components") or [])}
        missing_names = [names.get(str(cid), str(cid)) for cid in (build.get("current_parts_without_sellable_listing") or [])]
        sellable_count = int(build.get("current_sellable_listing_part_count") or 0)
        required_count = int(build.get("current_sellable_listing_required_part_count") or 0)
        lines.append("|{}|{}/{}|{}%|{}|{}|{}|{}|{}|".format(
            build.get("name"), sellable_count, required_count,
            build.get("current_sellable_listing_coverage_pct", 0),
            money(build.get("current_sellable_listing_subtotal_jpy")),
            int(counts.get("out_of_stock") or 0), int(counts.get("unknown") or 0),
            int(counts.get("stale") or 0),
            "、".join(missing_names) if missing_names else "直接掲載上は全点に在庫シグナルあり（決済未確認）"
        ))
    lines.extend([
        "",
        "**重要:** 「確認済み掲載価格の部分小計」は全構成の現在価格ではありません。部品ごとの価格時刻・売り切れ状態は下の部品表を確認してください。価格や在庫を取得できないことを「売り切れ」とは推定しません。",
        "",
        "## 100点方式の構成スコア（BF目標構成ベース）",
        "",
        "構成点は用途適性・目標総額ベースの相対価格効率・互換性で採点。ゲーム点は[Tom's Hardware GPU Benchmarks Hierarchy 2026](https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html)の1440p Ultraラスタライズ値を25点満点に正規化した代理指標で、対象ゲームの実測FPSではありません。参照表の最終更新日は2026-06-24です。GPU参照FPSも各構成に対応させて表示します。",
        "購入根拠充足度は直接価格・型番・取得時刻・販売可能在庫・検証済み決済総額・互換性を別計算し、購入許可とは切り離します。",
        "",
        "|順位|構成|GPU参照FPS (1440p Ultra)|総合点/100|ゲーム/25|制作/20|分析・AI/20|勉強・同時利用/10|価格効率/15|互換性/10|購入根拠充足度/100|直接価格・在庫・決済確認率|市場参考値|",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"
    ])
    for build in plan.get("builds") or []:
        score = build.get("scorecard") or {}
        benchmark = score.get("gaming_benchmark_reference") or {}
        lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            build.get("rank"), build.get("name"), benchmark.get("reference_mean_fps", "—"),
            score.get("overall_score", "—"), score.get("gaming_score", "—"),
            score.get("game_creation_score", "—"), score.get("analysis_ai_score", "—"),
            score.get("study_multitasking_score", "—"),
            score.get("price_efficiency_points_out_of_15", "—"),
            score.get("compatibility_points_out_of_10", "—"),
            score.get("purchase_evidence_completeness_score_out_of_100", "—"),
            "価格{}%・在庫{}%・決済{}%".format(
                score.get("direct_price_identity_pit_coverage_pct", 0),
                score.get("sellable_stock_coverage_pct", 0),
                score.get("verified_checkout_total_coverage_pct", 0)
            ),
            "{}/{}".format(
                score.get("market_reference_component_count", 0),
                score.get("market_reference_required_count", 0)
            )
        ))
    cpu_alternatives = plan.get("cpu_alternative_scenarios") or []
    cpu_dark_horses = plan.get("cpu_dark_horse_candidates") or []
    lines.extend([
        "",
        "## 高コア数CPUの比較（補助候補。購入認定ではない）",
        "",
        "主ランキングのRyzen 7 9700Xはゲームと一般的な制作・分析を両立する基準構成です。次のCPU案はRTX 5070 12GBを共通GPUとしてCPU差分を比較します。100点スコアは主ランキングと同じ式・価格効率の比較母集団で再計算していますが、互換性・冷却・販売価格の未確認が解消されたことを意味しません。",
        "",
        "|全候補順位|CPU比較案|コア/スレッド|CPU BF目標|PC本体BF目標|周辺機器込みBF目標|基準案からの総額差|制作スコア/20|分析スコア/20|総合点/100|互換性|判定|",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for item in cpu_alternatives:
        build = item.get("build") or {}
        score = item.get("scorecard") or {}
        fit = build.get("scorecard") or {}
        lines.append("|{}|{}|{}/{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            item.get("overall_comparison_rank", "—"),
            item.get("cpu_name") or item.get("cpu_choice_id"),
            item.get("cpu_cores", "—"), item.get("cpu_threads", "—"),
            money(item.get("cpu_target_price_jpy")),
            money(item.get("target_pc_total_jpy")),
            money(item.get("target_all_in_jpy")),
            money(item.get("target_all_in_delta_vs_base_jpy")),
            fit.get("game_creation_score", "—"),
            fit.get("analysis_ai_score", "—"),
            fit.get("overall_score", "—"),
            item.get("compatibility_status", "REVIEW"),
            item.get("decision", "REVIEW"),
        ))
    if not cpu_alternatives:
        lines.append("|—|CPU高コア数比較は未設定|—|—|—|—|—|—|—|—|未確認|未確認|")
    lines.extend([
        "",
        "この補助案でもCPUの目標価格だけを使って実売価格を作り出しません。購入前にCPUの正確なSKU・最新の販売可能価格・BIOS・RAM QVL/EXPO・冷却性能・送料・保証を確認します。",
        "",
        "|高コア数の大穴|コア/スレッド|CPU BF目標|現行クーラーのままCPU差額だけを置換した総額下限|40万円上限超過（冷却変更前）|冷却・価格の状態|",
        "|---|---:|---:|---:|---:|---|",
    ])
    for item in cpu_dark_horses:
        cooling = item.get("manufacturer_cooling_guidance") or "要確認"
        total_floor = money(item.get("target_all_in_floor_with_current_cooler_jpy"))
        overrun = money(item.get("over_budget_before_cooling_change_jpy"))
        lines.append("|{}|{}/{}|{}|{}|{}|{}|".format(
            item.get("cpu_name") or item.get("cpu_choice_id"),
            item.get("cpu_cores", "—"), item.get("cpu_threads", "—"),
            money(item.get("cpu_target_price_jpy")),
            total_floor, overrun, cooling + "。冷却費用未算入・完全構成未確認"
        ))
    if cpu_dark_horses:
        lines.extend([
            "",
            "上記の総額下限は完全な購入構成ではありません。メーカー推奨の冷却を採用する場合の追加費用を含まず、予算内と誤認しないために別枠で表示しています。",
        ])
    lines.extend([
        "",
        "## 目標総額と購入ゲート",
        "",
        "|順位|構成|部品目標小計|PC本体目標総額|周辺機器込み目標|目標残額|比較参考合計|互換性|判定|全パーツ商品リンク|",
        "|---:|---|---:|---:|---:|---:|---:|---|---|---|"
    ])
    for build in plan.get("builds") or []:
        component_links = " / ".join(
            component_markdown_link(part) for part in (build.get("components") or [])
        ) or "パーツ未登録"
        lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
            build.get("rank"), build.get("name"), money(build.get("target_parts_subtotal_jpy")),
            money(build.get("target_pc_total_jpy")), money(build.get("target_all_in_jpy")),
            money(build.get("target_remaining_budget_jpy")), money(build.get("market_reference_estimate_jpy")),
            build.get("compatibility_status"), build.get("decision"), component_links
        ))

    budget_scenarios = plan.get("budget_scenarios") or []
    if budget_scenarios:
        lines.extend(["", "## 35万円・40万円・45万円の一式予算比較（BF目標価格の計画値）", "",
            "各予算にはPC本体・OS・送料/小物・メインモニター1台と入力機器・必要送料・5,000円予備費を含みます。通常目標と20,000円の検討帯を分けて表示し、検討帯内でも購入許可は出しません。BF目標価格は現行決済価格ではありません。",
            "", "**用途要件:** Cities: Skylines IIとFPS、Unreal Engine/Unity/Godotによるゲーム制作、Python・スポーツ/株式/BTC分析、可能な範囲のローカルAI、勉強・調査。購入時RAM32GB/SSD1TB/専用VRAM8GB以上を下回る案は採用しません。"])
        for tier in budget_scenarios:
            lines.extend(["", "### {}（総額目標 {} / 許容帯上限 {}）".format(
                    tier.get("id"), money(tier.get("total_budget_jpy")), money(tier.get("soft_ceiling_total_jpy"))), "",
                str(tier.get("description_ja") or ""), "",
                "|順位|構成案|CPU|GPU / VRAM|RAM|SSD|PC本体目標|周辺機器|予備費|一式目標|目標との差/残額|目標超過額|許容帯残額/超過|許容帯内|総合点/100|販売可能在庫信号|互換性|購入判定|",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|"])
            for candidate in tier.get("builds") or []:
                cats={str(part.get("category")):part for part in (candidate.get("components") or []) if part.get("category")}
                cpu=cats.get("cpu") or {}; gpu=cats.get("gpu") or {}; ram=cats.get("memory") or {}; ssd=cats.get("storage") or {}
                rem=candidate.get("target_remaining_budget_jpy")
                rem_text=("残り "+money(rem)) if isinstance(rem,int) and rem>=0 else ("超過 "+money(abs(rem))) if isinstance(rem,int) else "未計算"
                soft_rem=candidate.get("target_remaining_soft_budget_jpy")
                soft_rem_text=("残り "+money(soft_rem)) if isinstance(soft_rem,int) and soft_rem>=0 else ("超過 "+money(abs(soft_rem))) if isinstance(soft_rem,int) else "未計算"
                band_status="はい" if candidate.get("within_soft_band") is True else "いいえ"
                row=[
                    str(candidate.get("display_rank_within_tier")),str(candidate.get("name")),str(cpu.get("name") or "未確認"),
                    "{} / {}GB".format(gpu.get("name") or "未確認",(gpu.get("specs") or {}).get("vram_gb","未確認")),
                    "{}GB".format((ram.get("specs") or {}).get("capacity_gb","未確認")),
                    "{}GB".format((ssd.get("specs") or {}).get("capacity_gb","未確認")),
                    money(candidate.get("target_pc_total_jpy")),money(candidate.get("target_peripheral_budget_jpy")),
                    money(candidate.get("target_contingency_jpy")),money(candidate.get("target_all_in_jpy")),rem_text,
                    money(candidate.get("target_overrun_jpy")),soft_rem_text,band_status,
                    str(candidate.get("overall_score_100","未採点")),
                    "{}/{}部品".format(candidate.get("current_sellable_stock_part_count",0),len(candidate.get("components") or [])),
                    str(candidate.get("compatibility_status")),str(candidate.get("decision")),
                ]
                lines.append("|" + "|".join(row) + "|")
            lines.extend(["","#### 部品内訳・用途のトレードオフ",""])
            for candidate in tier.get("builds") or []:
                details="、".join("{} {}".format(component_markdown_link(part), money(part.get("target_price_jpy"))) for part in (candidate.get("components") or []))
                lines.append("**{} — {}点/100**".format(candidate.get("name"),candidate.get("overall_score_100","未採点")))
                lines.append("- 一式目標 {}。{}".format(money(candidate.get("target_all_in_jpy")),candidate.get("purpose_note_ja") or "総合用途を対象。"))
                lines.append("- 部品目標の内訳: "+(details or "未登録")+"。")
                lines.append("- 留意点: "+str(candidate.get("tradeoff_note_ja") or "現行価格・互換性・最終決済額は未確認。"))
                lines.append("- 販売可能在庫信号: {}/{}部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性={}。購入許可=false。".format(candidate.get("current_sellable_stock_part_count",0),len(candidate.get("components") or []),candidate.get("compatibility_status")))
                lines.append("")

    lines.extend([
        "",
        "## 現在の在庫・売り切れリスク（購入可能総額ではない）",
        "",
        "この表は最新スナップショットの、型番一致した販売店掲載の観測です。価格・在庫は注文時に変わる可能性があります。売り切れ価格は販売可能額に加算せず、取得失敗・在庫不明は売り切れと断定しません。",
        "",
        "|構成|販売可能掲載を確認|うち在庫少|監視先すべて売切れ|在庫未確認/未取得|販売可能掲載の部分合計|完成総額|",
        "|---|---:|---:|---:|---:|---:|---|"
    ])
    for build in plan.get("builds") or []:
        component_by_id = {str(part.get("id")): part for part in (build.get("components") or [])}
        sellable_n = build.get("current_sellable_listing_part_count", 0)
        required_n = build.get("current_sellable_listing_required_part_count", 0)
        low_ids = build.get("current_low_stock_part_ids") or []
        oos_ids = build.get("current_confirmed_out_of_stock_part_ids") or []
        unknown_ids = build.get("current_unconfirmed_availability_part_ids") or []
        partial = money(build.get("current_sellable_listing_subtotal_jpy"))
        complete_total = "未算出（全パーツ・送料・決済条件の確認が必要）"
        lines.append("|{}|{}/{}|{}|{}|{}|{}|{}|".format(
            build.get("name"), sellable_n, required_n, len(low_ids), len(oos_ids),
            len(unknown_ids), partial + "（掲載価格のみ）", complete_total
        ))
        def names_for(ids):
            return "、".join(
                str(component_by_id.get(str(cid), {}).get("name") or cid)
                for cid in ids
            ) or "なし"
        lines.append("")
        lines.append("- {} — 在庫少: {} / 監視先すべて売切れ: {} / 在庫未確認・未取得: {}".format(
            build.get("name"), names_for(low_ids), names_for(oos_ids), names_for(unknown_ids)
        ))
        lines.append("- 販売可能掲載の部分合計は{}部品分。完成PC価格でも、送料・一括決済済み金額でもありません。".format(sellable_n))

    lines.extend([
        "",
        "## 売り切れ時の代替候補（自動注文なし・型番別に再検証）",
        "",
        "代替SKUへの切り替えは、同じ規格/クラスか、正確な型番、最新の直接価格、販売可能在庫、互換性が検証できた場合だけ計画上で行います。低在庫は売り切れリスクとして別途示し、在庫不明を在庫ありと扱いません。",
        "",
        "|カテゴリ|候補|部品適合点/100（内訳）|適合の理由・留意点|目標価格|販売可能な直接掲載|在庫信号|比較サイト参考（在庫・購入可否の根拠ではない）|選定ルール|商品ページ|",
        "|---|---|---:|---|---:|---:|---|---|---|---|"
    ])
    fallback_groups = [
        ("メモリ", (plan.get("memory_choice_selection") or {}).get("candidates") or [],
         (plan.get("memory_choice_selection") or {}).get("selected_id"), "検証済み在庫あり候補の価格比較"),
        ("SSD", (plan.get("storage_choice_selection") or {}).get("candidates") or [],
         (plan.get("storage_choice_selection") or {}).get("selected_id"), "優先SSDが買えなければ、在庫確認済みの1TB NVMeへ切替"),
        ("CPUクーラー", (plan.get("cooler_choice_selection") or {}).get("candidates") or [],
         (plan.get("cooler_choice_selection") or {}).get("selected_id"), "優先クーラーが買えなければ、互換性を確認した代替へ切替"),
    ]
    for base_gpu_id, candidates in (plan.get("gpu_fallback_candidates_by_choice") or {}).items():
        fallback_groups.append(("GPU代替", candidates, None, "同じGPUクラスの別SKU。寸法・端子・冷却を再確認"))
    stock_labels = {
        "in_stock": "在庫あり（再確認必須）", "low_stock": "在庫少（急変リスク）",
        "out_of_stock": "売切れ", "unknown": "在庫未確認",
        "preorder_or_backorder": "取寄せ/予約", "stale": "鮮度切れ",
    }
    for category, candidates, selected_id, rule in fallback_groups:
        for candidate in candidates:
            cprice = candidate.get("sellable_listing_price_jpy")
            if cprice is None:
                cprice = candidate.get("direct_listing_sellable_price_jpy")
            stock = candidate.get("stock_status") or candidate.get("direct_listing_sellable_stock_status") or "unknown"
            market_reference = candidate.get("market_reference_price_jpy")
            market_reference_text = (
                money(market_reference) + "（比較参考のみ・在庫証拠ではない）"
                if candidate.get("trusted_for_market_estimate") is True
                and isinstance(market_reference, int) and not isinstance(market_reference, bool)
                else "未検証/未取得"
            )
            page = candidate.get("purchase_url") or "—"
            name = candidate.get("name") or candidate.get("id")
            if selected_id and candidate.get("id") == selected_id:
                name = str(name) + "（選定中）"
            fit = component_suitability_score(candidate)
            if fit.get("score") is None:
                fit_text = "未採点"
                fit_notes = "ルーブリック不足のため適合点を付与しない"
            else:
                fb = fit["breakdown"]
                fit_text = "{}/100（用途{}/40・余裕{}/25・品質{}/20・構成{}/15）".format(
                    fit["score"], fb["workload_fit_points"], fb["headroom_points"],
                    fb["quality_reliability_points"], fb["integration_flexibility_points"]
                )
                fit_notes = "根拠: " + fit.get("rationale_ja", "")
                if fit.get("limitations_ja"):
                    fit_notes += " / 留意: " + fit["limitations_ja"]
            fit_notes = re.sub(r"\\s+", " ", fit_notes).replace("|", "／")
            lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
                category, name, fit_text, fit_notes, money(candidate.get("target_price_jpy")),
                money(cprice) if isinstance(cprice, int) and not isinstance(cprice, bool) else "販売可能価格なし",
                stock_labels.get(str(stock), str(stock)), market_reference_text, rule,
                "[商品ページ]({})".format(page) if str(page).startswith("https://") else page
            ))
    lines.extend(["", "## 構成別の詳細", ""])
    for build in plan.get("builds") or []:
        component_names = {str(part.get("id")): str(part.get("name") or part.get("id")) for part in (build.get("components") or [])}
        lines.extend(["", "### " + build.get("name", "自作PC"), "",
          "- BF目標総額（計画値）: " + money(build.get("target_all_in_jpy")) + "。値下がり予測・実売の確定額ではない。",
          "- 現時点の販売可能掲載: {}/{}部品 / 部分合計 {}（掲載額だけ。完成価格・注文カート合計ではない）。".format(
              build.get("current_sellable_listing_part_count", 0),
              build.get("current_sellable_listing_required_part_count", 0),
              money(build.get("current_sellable_listing_subtotal_jpy"))),
          "- 採用GPU SKU: {}（{}）".format(component_names.get(str(build.get("selected_gpu_part_id")), str(build.get("selected_gpu_part_id"))), build.get("gpu_selection_method")),
          "- 採用RAM: {}（{}）".format(component_names.get(str(build.get("selected_memory_id")), str(build.get("selected_memory_id"))), build.get("memory_choice_method")),
          "- 採用SSD: {}（{}）".format(component_names.get(str(build.get("selected_storage_id")), str(build.get("selected_storage_id"))), build.get("storage_selection_method")),
          "- 採用CPUクーラー: {}（{}）".format(component_names.get(str(build.get("selected_cooler_id")), str(build.get("selected_cooler_id"))), build.get("cooler_selection_method")),
          "- 現在の比較参考合計: " + (money(build.get("market_reference_estimate_jpy")) + "（各店の参考掲載値の合算で、決済見積ではない）" if build.get("market_reference_estimate_jpy") is not None else "未算出。価格・型番・在庫条件を満たさない部品を0円補完しない"),
          "- 互換性: " + str(build.get("compatibility_status")) + " / 判定: " + str(build.get("decision")), "",
          "部品適合点/100は用途適合40・性能/容量余裕25・品質/信頼性20・構成/拡張性15点のルーブリックから計算します。理由と制約を併記し、未入力・範囲外は未採点です。構成全体の点数や実測ベンチマークではありません。", 
          "部品購入根拠点/100は直接価格・在庫・決済総額・その部品に関係する互換性確認・保証/返品条件から動的計算します。適合点とは別で、比較サイト価格や未確認の在庫では加点しません。どちらの点数も購入許可ではありません。", "",
          "|画像|部品|部品適合点/100（内訳）|部品購入根拠点/100|型番|適合評価の理由・制約|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|",
          "|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|"])
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
            direct_price = part.get("direct_listing_sellable_price_jpy")
            direct_stock = part.get("direct_listing_sellable_stock_status")
            direct_text = (
                "販売可能掲載 " + money(direct_price) + "（" + str(direct_stock) + "）"
                if isinstance(direct_price, int) and not isinstance(direct_price, bool) else
                "販売可能な直接掲載価格なし"
            )
            stock_counts = part.get("direct_listing_stock_counts") or {}
            sold_out_count = int(stock_counts.get("out_of_stock") or 0)
            unknown_count = int(stock_counts.get("unknown") or 0)
            preorder_count = int(stock_counts.get("preorder_or_backorder") or 0)
            stale_count = int(stock_counts.get("stale") or 0)
            if sold_out_count or unknown_count or preorder_count or stale_count:
                direct_text += " / 売切れ{}・在庫不明{}・取寄せ/予約{}・鮮度切れ{}".format(
                    sold_out_count, unknown_count, preorder_count, stale_count
                )
            # Link to each vetted seller-specific offer with its own stock label;
            # never blend an out-of-stock sticker price into the sellable subtotal.
            url = part.get("purchase_url")
            links = ["[価格比較ページ](" + url + ")"] if url else []
            stock_labels = {
                "in_stock": "在庫あり", "low_stock": "在庫少",
                "out_of_stock": "売切れ", "unknown": "在庫不明",
                "preorder_or_backorder": "取寄せ/予約",
            }
            for offer in (part.get("direct_listing_display_offers") or []):
                offer_url = str(offer.get("url") or "")
                if not offer_url or any("(" + offer_url + ")" in link for link in links):
                    continue
                offer_price = offer.get("price_jpy")
                offer_status = stock_labels.get(str(offer.get("stock_status") or "unknown"), "在庫不明")
                if offer.get("stock_signal_fresh") is not True:
                    offer_status += "（在庫情報が古い）"
                retailer = str(
                    offer.get("retailer_domain")
                    or (urlparse(offer_url).hostname or "販売店").removeprefix("www.")
                )
                seller = str(offer.get("seller_name") or "").strip()
                offer_label = retailer + (" / " + seller if seller else "")
                retrieved_at = str(offer.get("retrieval_time") or "").strip()
                retrieval_label = ""
                # Every seller listing has its own point-in-time observation.
                # Display it beside the price so users do not confuse listings
                # fetched at different times or treat an old price as current.
                if len(retrieved_at) >= 16 and retrieved_at[10:11] == "T":
                    retrieval_label = "（取得 {} JST".format(
                        retrieved_at[:16].replace("T", " ")
                    )
                    age_minutes = offer.get("display_age_minutes")
                    if isinstance(age_minutes, (int, float)) and not isinstance(age_minutes, bool):
                        retrieval_label += "・{:.0f}分前".format(max(0, age_minutes))
                    retrieval_label += "）"
                label = "{} {} {}{}".format(
                    offer_label[:48], offer_status, money(offer_price), retrieval_label
                )
                links.append("[" + label.replace("]", ")") + "](" + offer_url + ")")
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
            early_signal = part.get("early_buy_review") if isinstance(part.get("early_buy_review"), dict) else {}
            early_label = str(early_signal.get("label_ja") or "未判定")
            part_fit = component_suitability_score(part)
            if part_fit.get("score") is None:
                part_fit_text = "未採点（ルーブリック不足）"
            else:
                breakdown = part_fit["breakdown"]
                part_fit_text = "{}/100（用途{}/40・余裕{}/25・品質{}/20・構成{}/15）".format(
                    part_fit["score"], breakdown["workload_fit_points"], breakdown["headroom_points"],
                    breakdown["quality_reliability_points"], breakdown["integration_flexibility_points"]
                )
            fit_notes = "根拠: " + (part_fit.get("rationale_ja") or "説明未設定")
            if part_fit.get("limitations_ja"):
                fit_notes += " / 留意: " + part_fit["limitations_ja"]
            fit_notes = re.sub(r"\\s+", " ", fit_notes).replace("|", "／")
            part_evidence = component_purchase_evidence_score(part, build)
            part_evidence_text = "{}/100".format(part_evidence["score"])
            lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(
                image_html, part.get("name"), part_fit_text, part_evidence_text,
                part.get("model_code") or "—", fit_notes, money(part.get("target_price_jpy")),
                price_text, direct_text, part.get("price_status"), early_label, diagnostic_text, link
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
    lines.extend(retrieval_issue_link_lines())
    return "\n".join(lines)


def section_from_plan(plan):
    lines = [START_MARKER, "## 最優先：PC本体は自作構成", "",
        "BTO完成品は価格比較用の参考枠に下げ、部品ごとの価格・互換性・送料を合算します。" +
        "PC本体の計画上限は " + money(plan.get("pc_planned_budget_jpy")) +
        "（周辺機器計画枠と総額予備費を先に確保。PC本体単体の比較上限（総額上限ではない）は " +
        money(plan.get("pc_budget_jpy")) + "）。", "",
        "|順位|自作構成|構成点/100|購入根拠充足度/100|PC本体目標|周辺機器込み|目標残額|互換性|判定|全パーツ商品リンク|",
        "|---:|---|---:|---:|---:|---:|---:|---|---|---|"]
    for build in plan.get("builds") or []:
        score = build.get("scorecard") or {}
        component_links = " / ".join(
            component_markdown_link(part) for part in (build.get("components") or [])
        ) or "パーツ未登録"
        lines.append("|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|".format(build.get("rank"), build.get("name"),
            score.get("overall_score", "—"), score.get("purchase_evidence_completeness_score_out_of_100", "—"),
            money(build.get("target_pc_total_jpy")), money(build.get("target_all_in_jpy")),
            money(build.get("target_remaining_budget_jpy")), build.get("compatibility_status"),
            build.get("decision"), component_links))
    cpu_alternatives = plan.get("cpu_alternative_scenarios") or []
    if cpu_alternatives:
        lines.extend(["", "CPU高コア数の補助比較（RTX 5070 12GBを固定）："])
        for item in cpu_alternatives:
            lines.append("- {} / {}コア{}スレッド / CPU目標 {} / 周辺機器込み目標 {} / 総合点 {} / 互換性 {}（購入許可ではない）".format(
                item.get("cpu_name"), item.get("cpu_cores"), "/" + str(item.get("cpu_threads")) + "T",
                money(item.get("cpu_target_price_jpy")), money(item.get("target_all_in_jpy")),
                (item.get("scorecard") or {}).get("overall_score", "—"), item.get("compatibility_status", "REVIEW")))
    cpu_dark_horses = plan.get("cpu_dark_horse_candidates") or []
    for item in cpu_dark_horses:
        lines.append("- CPU大穴：{} / {}コア{}スレッド / 冷却費用を含まない総額下限 {}（40万円上限超過 {}、完全構成未確認）".format(
            item.get("cpu_name"), item.get("cpu_cores"), "/" + str(item.get("cpu_threads")) + "T",
            money(item.get("target_all_in_floor_with_current_cooler_jpy")),
            money(item.get("over_budget_before_cooling_change_jpy"))))
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
        "cpu_alternative_count":len(plan.get("cpu_alternative_scenarios") or []),
        "cpu_dark_horse_count":len(plan.get("cpu_dark_horse_candidates") or []),
        "target_pc_totals":{x["id"]:x["target_pc_total_jpy"] for x in plan["builds"]},
        "all_in_targets":{x["id"]:x["target_all_in_jpy"] for x in plan["builds"]},
        "buy_now_authorized":False,
        "compatibility":{x["id"]:x["compatibility_status"] for x in plan["builds"]}},ensure_ascii=False))


if __name__ == "__main__":
    main()
