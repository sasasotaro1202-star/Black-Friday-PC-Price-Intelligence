"""Build a transparent DIY component plan; never authorize a buy from target/comparison prices."""
import hashlib
import json
import os
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
    dt = parse_dt(value)
    return max(0.0, (now - dt).total_seconds() / 60.0) if dt else None


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
        and available is not None and retrieved is not None and available <= retrieved
    )


def trusted_retailer_listing_reference(row, now, max_age, allowed_domains=()):
    """Validate a fresh, directly parsed retailer listing separately from checkout offers."""
    offer = row.get("retailer_listing_offer") if isinstance(row, dict) else None
    price = row.get("retailer_listing_reference_price_jpy") if isinstance(row, dict) else None
    age = age_minutes(row.get("retrieval_time"), now) if isinstance(row, dict) else None
    available = parse_dt(row.get("available_at")) if isinstance(row, dict) else None
    retrieved = parse_dt(row.get("retrieval_time")) if isinstance(row, dict) else None
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
        and available is not None and retrieved is not None and available <= retrieved
    )


def component_price(part, by_id, now, max_age, allowed_domains=()):
    if not part.get("track_price"):
        ref = part.get("reference_price_jpy")
        return {
            "market_reference_price_jpy": None,
            "display_reference_price_jpy": ref if isinstance(ref, int) else None,
            "price_status": "manual_official_store_reference" if isinstance(ref, int) else "not_tracked",
            "trusted_for_market_estimate": False,
            "source_role": part.get("price_source_role") or "manual_reference",
            "retrieval_time": None, "reference_age_minutes": None
        }
    row = by_id.get(str(part.get("id") or "")) or {}
    trusted_comparison = trusted_market_reference(row, now, max_age)
    trusted_retailer = trusted_retailer_listing_reference(row, now, max_age, allowed_domains)
    trusted = trusted_comparison or trusted_retailer
    age = age_minutes(row.get("retrieval_time"), now)
    retailer_offer = row.get("retailer_listing_offer") if trusted_retailer else None
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
        "search_snippet_reference_title": row.get("search_snippet_reference_title") if snippet_only else None
    }


def compatibility_checks(parts, profile, gpu_id):
    """Checks known socket/memory/storage/size/power constraints, fail-closed."""
    checks = []
    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    def spec(part_id):
        return (parts.get(part_id) or {}).get("specs") or {}

    cpu = spec("cpu-ryzen7-9700x")
    board = spec("motherboard-asrock-b850m-pro-rs-wifi")
    memory = spec("memory-teamgroup-ddr5-32gb-6000")
    storage = spec("ssd-crucial-p3-plus-1tb")
    psu = spec("psu-corsair-rm850e-2025")
    case = spec("case-fractal-pop-air-tg")
    cooler = spec("cooler-thermalright-pa120-se-v3")
    gpu = spec(gpu_id)

    add("cpu_motherboard_socket", "PASS" if cpu.get("socket") and cpu.get("socket") == board.get("socket") else "FAIL",
        "CPU socket {} / board socket {}".format(cpu.get("socket", "unknown"), board.get("socket", "unknown")))
    memory_ok = (
        memory.get("memory_type") == board.get("memory_type")
        and isinstance(memory.get("capacity_gb"), int) and memory["capacity_gb"] >= int(profile.get("minimum_ram_gb", 32))
        and isinstance(memory.get("modules"), int) and memory["modules"] >= int(profile.get("minimum_memory_modules", 2))
    )
    add("memory_type_capacity_dual_channel", "PASS" if memory_ok else "FAIL",
        "DDR type, >= {}GB, >= {} DIMMs".format(profile.get("minimum_ram_gb", 32), profile.get("minimum_memory_modules", 2)))
    storage_ok = isinstance(storage.get("capacity_gb"), int) and storage["capacity_gb"] >= int(profile.get("minimum_ssd_gb", 1000)) and "NVMe" in str(storage.get("interface", ""))
    add("storage_capacity_interface", "PASS" if storage_ok else "FAIL",
        "NVMe SSD {}GB / minimum {}GB".format(storage.get("capacity_gb", "unknown"), profile.get("minimum_ssd_gb", 1000)))
    supported = case.get("supported_motherboard_form_factors") or []
    board_form = board.get("form_factor")
    add("motherboard_case_form_factor", "PASS" if board_form and board_form in supported else "FAIL",
        "Board {} / case supports {}".format(board_form or "unknown", ", ".join(supported) or "unknown"))

    gpu_length, gpu_clearance = gpu.get("card_length_mm"), case.get("gpu_clearance_mm")
    if not isinstance(gpu_length, int) or not isinstance(gpu_clearance, int):
        add("gpu_case_clearance", "REVIEW", "Exact GPU retail-card length or case clearance must be verified before ordering")
    else:
        add("gpu_case_clearance", "PASS" if gpu_length <= gpu_clearance else "FAIL",
            "GPU {}mm / case limit {}mm".format(gpu_length, gpu_clearance))

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
    if gpu.get("connector") == "model_specific":
        add("gpu_power_connector", "REVIEW", "Confirm exact GPU auxiliary connector and included PSU cable against the exact model")
    else:
        add("gpu_power_connector", "PASS" if psu.get("connector_12v2x6") and gpu.get("connector") == "12V-2x6" else "FAIL",
            "PSU ATX 3.1 native 12V-2x6 cable")
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
    pc_budget = int(profile.get("pc_budget_jpy", 330200))
    all_budget = int(profile.get("total_budget_jpy", 400000))
    peripheral_budget = int(profile.get("peripheral_budget_jpy", 69800))
    shipping = int(profile.get("build_shipping_reserve_jpy", 0))
    small_parts = int(profile.get("small_parts_reserve_jpy", 0))
    builds = []

    for rank, gpu_id in enumerate(gpu_ids, 1):
        selected_ids = fixed_ids + [gpu_id]
        components, missing, market_subtotal = [], [], 0
        all_tracked_fresh = True
        target_parts = 0
        for cid in selected_ids:
            part = parts.get(cid)
            if not part:
                missing.append(cid)
                all_tracked_fresh = False
                continue
            target = part.get("target_price_jpy")
            if isinstance(target, int) and not isinstance(target, bool):
                target_parts += target
            price = component_price(
                part, by_id, now, max_age,
                allowed_domains=profile.get("allowed_search_reference_domains") or profile.get("allowed_comparison_domains") or []
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
                "track_price": bool(part.get("track_price")), "specs": part.get("specs") or {},
                "notes": part.get("notes"), "bf_actual_authorized": False
            }
            components.append(component)
            if part.get("track_price"):
                if price["trusted_for_market_estimate"] and isinstance(price["market_reference_price_jpy"], int):
                    market_subtotal += price["market_reference_price_jpy"]
                else:
                    all_tracked_fresh = False
                    missing.append(cid)
            else:
                reference = part.get("reference_price_jpy")
                if isinstance(reference, int) and reference > 0:
                    market_subtotal += reference
                else:
                    all_tracked_fresh = False
                    missing.append(cid)

        compat, checks = compatibility_checks(parts, profile, gpu_id)
        target_pc = target_parts + shipping + small_parts
        target_all_in = target_pc + peripheral_budget
        market_estimate = market_subtotal + shipping + small_parts if all_tracked_fresh and not missing else None
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
        "budget_arithmetic_valid": pc_budget + peripheral_budget == all_budget,
        "required_categories": profile.get("required_categories") or [],
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
          "|部品|型番|BF目標|比較サイト参考価格|確認状態|リンク|",
          "|---|---|---:|---:|---|---|"])
        for part in build.get("components") or []:
            p = part.get("display_reference_price_jpy")
            if part.get("track_price") and part.get("market_reference_price_jpy") is None and p is None:
                price_text = "未取得"
            elif part.get("price_status") == "search_snippet_reference_only":
                price_text = money(p) + "（検索スニペット参考のみ）"
            else:
                price_text = money(p)
            url = part.get("purchase_url")
            links = ["[価格比較ページ](" + url + ")"] if url else []
            search_url = part.get("search_snippet_reference_url")
            if search_url and search_url != url:
                links.append("[検索スニペット参考元](" + search_url + ")")
            link = " / ".join(links) if links else "—"
            lines.append("|{}|{}|{}|{}|{}|{}|".format(part.get("name"), part.get("model_code") or "—", money(part.get("target_price_jpy")), price_text, part.get("price_status"), link))
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
