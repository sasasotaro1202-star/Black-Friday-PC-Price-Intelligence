import hashlib
import html
import json
import os
from datetime import datetime

from intelligence import (
    ROOT, BUDGET, EFFECTIVE_SOFT_MAX, EFFECTIVE_HARD_MAX,
    load_json, save_json, load_catalog, load_anchors,
    build_row, cash_total_cost, confirmed_benefit_value, effective_cost, noncash_benefit_value_jpy, value_equivalent_cost,
    now_jst, iso, scenario_prices, purchase_budget_policy, peripheral_budget_projection,
    configuration_readiness, gpu_key
)
from sale_calendar import campaign_window_for_item

def peripheral_monitor_section_heading(target_config):
    """Describe the primary peripheral purchase set from the active target config."""
    primary = [
        item for item in (target_config.get("peripherals") or [])
        if isinstance(item, dict) and item.get("mandatory", True)
    ]
    main_count = sum(
        1 for item in primary
        if str(item.get("id") or "") == "main_monitor"
        or str(item.get("category") or "") == "main_monitor"
    )
    has_secondary = any(
        str(item.get("id") or "") == "secondary_monitor"
        or str(item.get("category") or "") == "secondary_monitor"
        for item in primary
    )
    has_headset = any(
        str(item.get("id") or "") == "headset"
        or str(item.get("category") or "") == "headset"
        for item in primary
    )
    secondary_label = "あり" if has_secondary else "なし"
    headset_label = "あり" if has_headset else "なし"
    return (
        f"## 周辺機器の価格監視（メインモニター{main_count}台・"
        f"サブモニター{secondary_label}・ヘッドセット{headset_label}）"
    )


def sales_url(item):
    """Return only a real HTTP(S) product URL; never fabricate a purchase URL."""
    url = str(item.get("url") or "").strip()
    return url if url.startswith(("https://", "http://")) else None


def image_markup(item, fallback_url=None, width=88):
    """Render only explicitly configured HTTPS product images; never guess image URLs."""
    item = item if isinstance(item, dict) else {}
    image_url = str(item.get("image_url") or "").strip()
    if not image_url.startswith("https://"):
        return "画像未確認"
    source_url = str(item.get("image_source_url") or fallback_url or "#").strip()
    if not source_url.startswith("https://"):
        source_url = "#"
    alt = html.escape(str(item.get("name") or "商品画像"), quote=True)
    return '<a href="{}"><img src="{}" alt="{}" width="{}"></a>'.format(
        html.escape(source_url, quote=True), html.escape(image_url, quote=True), alt, int(width)
    )


def peripheral_is_physical_store(item, target_config):
    """True only when the selected purchase route is a physical-store cash purchase."""
    item = item if isinstance(item, dict) else {}
    return item.get("purchase_channel") == "physical_store"


def peripheral_route_label(item):
    """Human-readable route options; do not equate a web listing with a store cash quote."""
    item = item if isinstance(item, dict) else {}
    channel = str(item.get("purchase_channel") or "online")
    if channel == "compare_online_and_store":
        return "ネット配送・実店舗・店舗受取を比較"
    if channel == "physical_store":
        return "実店舗（現金価格・在庫を確認）"
    if channel == "conditional_need_only":
        return "付属ケーブル不足時のみ"
    if channel == "budget_reserve":
        return "予備枠（商品ではない）"
    return "ネット注文"


def peripheral_route_price_summary(item):
    """Separate online listing, shipping, store cash quote and route completeness."""
    item = item if isinstance(item, dict) else {}
    channel = str(item.get("purchase_channel") or "online")
    price = item.get("online_comparison_price_jpy")
    shipping = item.get("online_shipping_jpy")
    reserve = item.get("online_shipping_reserve_jpy")
    online_total = item.get("estimated_online_cash_total_jpy")
    store_price = item.get("store_price_jpy") if item.get("store_price_confirmed") else None
    parts = []
    if isinstance(price, int) and not isinstance(price, bool):
        if isinstance(online_total, int) and not isinstance(online_total, bool):
            fee_text = f"（送料込み推計 ¥{online_total:,}"
            if not item.get("online_shipping_cost_verified"):
                fee_text += f"・送料予備 ¥{int(reserve or 0):,}"
            fee_text += "）"
        else:
            fee_text = ""
        parts.append(f"ネット掲載 ¥{price:,}{fee_text}")
    else:
        parts.append("ネット価格未確認")
    if isinstance(store_price, int) and not isinstance(store_price, bool):
        stock = str(item.get("store_stock_status") or "unknown")
        store_name = item.get("store_inventory_store_name") or "対象店"
        parts.append(f"{store_name} 店頭 ¥{store_price:,}・在庫 {stock}")
    elif channel in ("compare_online_and_store", "physical_store") or "physical_store" in (item.get("purchase_channel_options") or []):
        parts.append("店頭現金価格未確認")
    route_status = item.get("channel_comparison_status")
    if route_status:
        parts.append(f"比較状態 {route_status}")
    return " / ".join(parts)


def inventory_status_label(item):
    item = item if isinstance(item, dict) else {}
    if item.get("store_inventory_verified"):
        status = item.get("store_inventory_status")
        store_name = item.get("store_inventory_store_name") or "指定店舗"
        labels = {
            "in_stock": "取置き在庫あり（確認時点）",
            "low_stock": "取置き在庫少（確認時点）",
            "out_of_stock": "在庫なし（確認時点）",
            "preorder_or_backorder": "取寄せ表示（即時在庫ではない）",
        }
        if status in labels:
            return f"{store_name}: {labels[status]}"
    if item.get("store_inventory_status") == "unknown":
        return "支店別在庫未確認"
    return "支店別在庫未確認"


def build_purchase_method_policy(profile):
    """Make the intended PC purchase method explicit and testable."""
    profile = profile if isinstance(profile, dict) else {}
    self_build_primary = (
        profile.get("pc_build_method_preference")
        == "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION"
    )
    try:
        assembly_penalty = max(0, int(profile.get("assembly_time_penalty_points", 0)))
    except (TypeError, ValueError):
        assembly_penalty = 0
    assembly_time_is_constraint = bool(profile.get("assembly_time_is_constraint", False))
    if not assembly_time_is_constraint:
        assembly_penalty = 0
    return {
        "primary_method": "SELF_BUILD" if self_build_primary else "RANKED_COMPLETE_PC",
        "assembly_time_is_constraint": assembly_time_is_constraint,
        "assembly_time_penalty_points": assembly_penalty,
        "bto_role": profile.get("bto_role", "REFERENCE_BENCHMARK_ONLY"),
        "selection_policy": profile.get("selection_policy") or (
            "Prioritize self-build; assembly time is not a negative factor."
        ),
        "completed_pc_purchase_actionable": not self_build_primary,
    }


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def purchase_gate_reason(
    self_build_primary,
    critical_unverified,
    peripheral_budget_ready,
    action,
    dynamic_pc_cap_jpy,
    purchase_gate_allowed,
):
    """Explain the completed-PC shortlist gate without conflating it with DIY authorization."""
    if self_build_primary:
        return "completed_pc_candidates_reference_only"
    if critical_unverified:
        return "critical_candidates_not_fully_verified"
    if not peripheral_budget_ready:
        return "peripheral_prices_or_availability_unverified"
    if action and action.get("effective_cost_jpy", 10**12) > (dynamic_pc_cap_jpy or 0):
        return "all_in_cost_exceeds_total_budget"
    if not purchase_gate_allowed:
        return "no_buy_now_candidate"
    return "all_critical_and_peripheral_candidates_verified"


def suppress_current_price(row):
    """Convert a non-actionable row into reference-only evidence."""
    out = dict(row)
    if out.get("current_price_jpy") is not None:
        out["last_valid_price_jpy"] = (
            out.get("last_valid_price_jpy")
            or out.get("current_price_jpy")
        )
    out["reference_price_jpy"] = (
        out.get("reference_price_jpy")
        or out.get("last_valid_price_jpy")
    )
    out["current_price_jpy"] = None
    out["price_jpy"] = None
    out["current_price_suppressed"] = True
    return out


def _trusted_live_offer(item):
    price = item.get("current_price_jpy")
    return bool(
        isinstance(price, int) and not isinstance(price, bool) and price > 0
        and item.get("price_source_mode") == "direct_structured"
        and item.get("price_validation_status") not in (
            None, "missing", "anomaly_rejected", "reference_only", "variant_ambiguous"
        )
        and item.get("variant_match") in ("exact", "trusted_url", "strong")
        and item.get("pit_valid") is True
    )


def _parse_strategy_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _price_relation(amount, benchmark, label):
    difference = int(amount) - int(benchmark)
    if difference > 0:
        return f"{label}を¥{difference:,}上回っています"
    if difference < 0:
        return f"{label}を¥{-difference:,}下回っています"
    return f"{label}と同額です"


def build_purchase_strategy_status(products, strategy, budget, peripheral_projection):
    """Report BF targets separately from pre-sale reference observations."""
    now = now_jst()
    phase = strategy.get("price_semantics") or {}
    bf_start = _parse_strategy_dt(phase.get("window_start_jst"))
    bf_end = _parse_strategy_dt(phase.get("window_end_jst"))
    in_watch_window = bool(bf_start and bf_end and bf_start <= now <= bf_end)
    watch_config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    official_dates = load_json(os.path.join(ROOT, "data", "official_campaign_dates_status.json"), {})
    budget_ready = bool(peripheral_projection.get("budget_data_ready"))
    live_cap = int(peripheral_projection.get("pc_dynamic_cap_jpy") or 0)
    planned_bf_cap = min(
        int(budget["pc_budget_jpy"]),
        int(budget["total_budget_jpy"])
        - int(budget["peripheral_budget_jpy"])
        - int(budget.get("unallocated_contingency_jpy", 0)),
    )
    bf_cap = min(int(budget["pc_budget_jpy"]), live_cap) if in_watch_window and budget_ready else planned_bf_cap
    by_id = {str(x.get("id")): x for x in products if x.get("id")}
    rows = []

    for plan in strategy.get("priority_plans", []):
        cid = str(plan.get("candidate_id") or "")
        item = by_id.get(cid, {})
        verified = _trusted_live_offer(item)
        observed_price = item.get("current_price_jpy") if verified else None
        observed_at = _parse_strategy_dt(item.get("retrieval_time"))
        campaign = campaign_window_for_item(item, now, watch_config, official_dates)
        campaign_dates_confirmed = bool(
            campaign.get("date_status") in ("CONFIRMED", "CONFIRMED_MANUAL")
            and campaign.get("start_jst") and campaign.get("end_jst")
        )
        campaign_active_now = bool(campaign.get("active_now"))
        inside_watch_observation = bool(
            verified and in_watch_window and observed_at and bf_start <= observed_at <= bf_end
        )
        observation_is_bf = bool(inside_watch_observation and campaign.get("active_at_observation"))
        bf_target = int(plan.get("black_friday_target_price_jpy") or budget["pc_target_jpy"])
        ready, reasons = configuration_readiness(item) if item else (False, ["候補の構成未確認"])
        stock = item.get("stock_status", "unknown")
        role = plan.get("role")
        row = {
            "candidate_id": cid, "role": role, "label": plan.get("label") or item.get("name") or cid,
            "url": sales_url(item) or plan.get("purchase_url"),
            "black_friday_target_price_jpy": bf_target, "black_friday_price_cap_jpy": bf_cap,
            "black_friday_price_observed_jpy": observed_price if observation_is_bf else None,
            "black_friday_offer_verified": observation_is_bf,
            "watch_window_reference_price_jpy": observed_price if verified and inside_watch_observation and not observation_is_bf else None,
            "watch_window_reference_at": item.get("retrieval_time") if verified and inside_watch_observation and not observation_is_bf else None,
            "pre_black_friday_reference_price_jpy": observed_price if verified and observed_at and bf_start and observed_at < bf_start else None,
            "pre_black_friday_reference_at": item.get("retrieval_time") if verified and observed_at and bf_start and observed_at < bf_start else None,
            "post_black_friday_reference_price_jpy": observed_price if verified and observed_at and bf_end and observed_at > bf_end else None,
            "post_black_friday_reference_at": item.get("retrieval_time") if verified and observed_at and bf_end and observed_at > bf_end else None,
            "observed_price_jpy": observed_price,
            "observed_price_phase": (
                "OFFICIAL_BLACK_FRIDAY_WINDOW" if observation_is_bf else
                "PROVISIONAL_WATCH_WINDOW_REFERENCE" if verified and inside_watch_observation else
                "PRE_BLACK_FRIDAY_REFERENCE" if verified and observed_at and bf_start and observed_at < bf_start else
                "POST_BLACK_FRIDAY_REFERENCE" if verified and observed_at and bf_end and observed_at > bf_end else
                "TIMESTAMP_UNVERIFIED_REFERENCE" if verified else "UNVERIFIED"
            ),
            "retailer_key": campaign.get("retailer_key"),
            "retailer_campaign_status": campaign.get("status"),
            "retailer_campaign_date_status": campaign.get("date_status"),
            "retailer_campaign_dates_confirmed": campaign_dates_confirmed,
            "retailer_campaign_start_jst": campaign.get("start_jst"),
            "retailer_campaign_end_jst": campaign.get("end_jst"),
            "retailer_campaign_source_url": campaign.get("source_url"),
            "retailer_campaign_active": campaign_active_now,
            "retailer_campaign_active_at_observation": bool(campaign.get("active_at_observation")),
            "price_verified": verified, "stock_status": stock, "configuration_ready": ready,
            "configuration_reasons": reasons, "target_ram_gb": plan.get("target_ram_gb"),
            "target_ssd_gb": plan.get("target_ssd_gb"),
            "current_live_pc_budget_cap_reference_jpy": live_cap,
            "bf_budget_cap_is_final": bool(in_watch_window and budget_ready),
            "status": (
                "PRE_BF_TARGET_MONITORING" if not in_watch_window else
                "WAIT_FOR_OFFICIAL_DATES" if not campaign_dates_confirmed else
                "WAIT_FOR_CAMPAIGN_WINDOW" if not campaign_active_now else
                "BF_PRICE_UNVERIFIED"
            ),
            "detail": "",
        }
        if role in ("primary_configuration_upgrade", "higher_cpu_configuration_upgrade"):
            baseline = int(plan.get("baseline_price_jpy") or 0)
            # A sale may change the base configuration price before BF. Use the
            # latest verified listing to calculate upgrade headroom, but never
            # treat that base price as a completed 32GB/1TB configuration.
            headroom_basis = int(observed_price) if observed_price is not None else baseline
            headroom_phase = row["observed_price_phase"] if observed_price is not None else "CONFIGURED_BASELINE_REFERENCE"
            row.update({
                "baseline_price_reference_jpy": baseline,
                "baseline_price_reference_phase": "PRE_BLACK_FRIDAY_BASE_CONFIGURATION",
                "upgrade_headroom_basis_price_jpy": headroom_basis,
                "upgrade_headroom_basis_phase": headroom_phase,
                "baseline_ram_gb": plan.get("baseline_ram_gb"), "baseline_ssd_gb": plan.get("baseline_ssd_gb"),
                "max_upgrade_cost_to_bf_target_jpy": max(0, bf_target-headroom_basis),
                "max_upgrade_cost_to_bf_hard_cap_jpy": max(0, bf_cap-headroom_basis),
                "max_upgrade_cost_to_target_jpy": max(0, bf_target-headroom_basis),
                "max_upgrade_cost_to_hard_cap_jpy": max(0, bf_cap-headroom_basis),
                "max_upgrade_cost_to_dynamic_cap_jpy": max(0, bf_cap-headroom_basis),
            })
            if not in_watch_window:
                row["detail"] = (
                    f"BF完成構成の目標は¥{bf_target:,}、計画上限は¥{bf_cap:,}。"
                    f"¥{baseline:,}は16GB/500GB基本構成の事前参考価格でありBF価格ではありません。"
                    f"余地計算の基準は¥{headroom_basis:,}（{headroom_phase}）。"
                    f"構成変更費は目標まで¥{row['max_upgrade_cost_to_bf_target_jpy']:,}以内、"
                    f"計画上限まで¥{row['max_upgrade_cost_to_bf_hard_cap_jpy']:,}以内が条件です。"
                    "これは構成変更費の見積ではありません。32GB/1TB完成構成の確定価格を別途確認します。"
                )
            elif not campaign_dates_confirmed:
                row["status"], row["detail"] = "WAIT_FOR_OFFICIAL_DATES", "この広域監視窓は公式開催日ではありません。販売店の2026年公式日付範囲が確認できるまで、観測価格をBF実売として扱いません。"
            elif not campaign_active_now:
                row["status"], row["detail"] = "WAIT_FOR_CAMPAIGN_WINDOW", "公式日程は確認済みですが、現在はその販売店の公式開催期間外です。開催期間に入るまで待ちます。"
            elif not observation_is_bf:
                row["status"], row["detail"] = "BF_PRICE_UNVERIFIED", "公式期間内の完成構成価格を直接確認できていません。事前価格をBF価格に流用しません。"
            elif stock == "out_of_stock":
                row["status"], row["detail"] = "OUT_OF_STOCK", "BF期間中の商品ページで在庫切れを確認。"
            elif stock not in ("in_stock", "low_stock"):
                row["status"], row["detail"] = "STOCK_UNCONFIRMED", "BF期間中の在庫を直接確認できていません。"
            elif not ready:
                row["status"], row["detail"] = "NEEDS_CONFIGURATION", "BF期間中に観測した価格も構成要件未達です。32GB RAM/1TB SSD完成構成の最終価格が必要です。"
            elif observed_price <= bf_cap:
                row["status"], row["detail"] = "MEETS_BF_PRICE_AND_CONFIGURATION", "BF期間内の直接観測価格・在庫・完成構成が条件内。全体購入ゲートは別途必要です。"
            else:
                row["status"], row["detail"] = "WAIT_FOR_DISCOUNT", f"BF観測価格から本体上限まで¥{observed_price-bf_cap:,}の値下げが必要です。"
        elif role == "secondary_outlet_complete_configuration":
            reference = int(plan.get("last_verified_listing_reference_jpy") or 0)
            row["listing_reference_price_jpy"] = reference
            if not in_watch_window:
                row["pre_bf_reference_gap_to_target_jpy"] = max(0, reference - bf_target) if reference else None
                row["pre_bf_reference_gap_to_planned_cap_jpy"] = max(0, reference - bf_cap) if reference else None
                row["detail"] = (
                    f"BF目標は¥{bf_target:,}、完成構成の計画上限は¥{bf_cap:,}。"
                    f"¥{reference:,}は事前の参考掲載額でBF価格ではありません。"
                    + (
                        f" 参考額は{_price_relation(reference, bf_target, 'BF目標')}。"
                        f"{_price_relation(reference, bf_cap, '計画上限')}。"
                        if reference else ""
                    )
                )
            elif not campaign_dates_confirmed:
                row["status"], row["detail"] = "WAIT_FOR_OFFICIAL_DATES", "広域監視窓だけではBF開催中とみなしません。公式の2026年開催日程を確認します。"
            elif not campaign_active_now:
                row["status"], row["detail"] = "WAIT_FOR_CAMPAIGN_WINDOW", "公式日程は確認済みですが、現在はその販売店の公式開催期間外です。開催期間に入るまで待ちます。"
            elif not observation_is_bf:
                row["status"], row["detail"] = "BF_PRICE_UNVERIFIED", "公式期間内の価格・在庫・SKUを直接確認できていません。"
            elif stock == "out_of_stock":
                row["status"], row["detail"] = "OUT_OF_STOCK", "BF期間中の商品ページで在庫切れを確認。"
            elif stock not in ("in_stock", "low_stock"):
                row["status"], row["detail"] = "STOCK_UNCONFIRMED", "BF期間中の在庫を直接確認できていません。"
            elif not ready:
                row["status"], row["detail"] = "NEEDS_CONFIGURATION", "BF期間中の価格を確認しましたが、32GB/1TB完成構成ではありません。"
            elif not budget_ready:
                row["status"], row["detail"] = "BF_BUDGET_UNVERIFIED", f"PC価格・構成は確認できましたが、BF周辺機器の実売価格/在庫が揃わず、{budget['total_budget_jpy']:,}円総額の本体上限が未確定です。"
            elif observed_price <= bf_cap:
                row["status"], row["detail"] = "MEETS_BF_PRICE_AND_CONFIGURATION", "BF期間内の直接観測価格・在庫・完成構成が条件内。全体購入ゲートは別途必要です。"
            else:
                row["status"] = "WAIT_FOR_DISCOUNT"
                row["bf_price_target_gap_jpy"] = max(0, observed_price-bf_target)
                row["bf_price_cap_gap_jpy"] = max(0, observed_price-bf_cap)
                row["detail"] = f"BF観測価格から理想目標まで¥{row['bf_price_target_gap_jpy']:,}、BF本体上限まで¥{row['bf_price_cap_gap_jpy']:,}の値下げが必要です。"
        rows.append(row)

    outlier = strategy.get("outlier_rule") or {}
    token = str(outlier.get("gpu") or "RTX 5070 Ti").lower().replace("rtx ", "")
    candidates = [x for x in products if x.get("form_factor") == outlier.get("form_factor", "desktop") and token in gpu_key(x).lower()]
    observed_complete, bf_complete, eligible = [], [], []
    outlier_official_campaign_active = False
    outlier_campaign_dates_confirmed = False
    for item in candidates:
        campaign = campaign_window_for_item(item, now, watch_config, official_dates)
        if (
            campaign.get("date_status") in ("CONFIRMED", "CONFIRMED_MANUAL")
            and campaign.get("start_jst") and campaign.get("end_jst")
        ):
            outlier_campaign_dates_confirmed = True
        if campaign.get("active_now"):
            outlier_official_campaign_active = True
        if not _trusted_live_offer(item) or item.get("stock_status") not in ("in_stock", "low_stock"):
            continue
        ready, _ = configuration_readiness(item)
        if not ready:
            continue
        observed_complete.append(item)
        observed_at = _parse_strategy_dt(item.get("retrieval_time"))
        if in_watch_window and observed_at and bf_start <= observed_at <= bf_end and campaign.get("active_at_observation"):
            bf_complete.append(item)
            if budget_ready and int(item["current_price_jpy"]) <= bf_cap:
                eligible.append(item)
    eligible.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    bf_complete.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    observed_complete.sort(key=lambda x: (x["current_price_jpy"], x.get("id", "")))
    if not in_watch_window:
        best = observed_complete[0] if observed_complete else None
        status, detail = "PRE_BF_TARGET_MONITORING", "事前価格は比較用参考情報のみ。ブラックフライデー販売価格として扱いません。"
    elif eligible:
        best = eligible[0]
        status, detail = "MEETS_BF_PRICE_AND_CONFIGURATION", "条件を満たすBF期間内の完成構成を検出。全体購入ゲート通過前は購入許可ではありません。"
    elif bf_complete and not budget_ready:
        best = bf_complete[0]
        status, detail = "BF_BUDGET_UNVERIFIED", f"BF期間中の完成構成を確認しましたが、周辺機器の価格/在庫が未確認で本体上限は未確定。参考の確認価格は¥{best['current_price_jpy']:,}です。"
    elif bf_complete:
        best = bf_complete[0]
        status, detail = "WAIT_FOR_DISCOUNT", f"BF期間中の完成構成を確認しましたが、本体上限を超過。最安確認価格は¥{best['current_price_jpy']:,}です。"
    elif in_watch_window and not outlier_campaign_dates_confirmed:
        best = observed_complete[0] if observed_complete else (candidates[0] if candidates else None)
        status, detail = "WAIT_FOR_OFFICIAL_DATES", "RTX 5070 Ti大穴候補について販売店の2026年公式セール期間が未確認です。暫定監視窓の価格はBF実売として扱いません。"
    elif in_watch_window and not outlier_official_campaign_active:
        best = observed_complete[0] if observed_complete else (candidates[0] if candidates else None)
        status, detail = "WAIT_FOR_CAMPAIGN_WINDOW", "RTX 5070 Ti大穴候補の公式日程は確認済みですが、現在はその販売店の公式開催期間外です。"
    elif in_watch_window and not bf_complete:
        best = observed_complete[0] if observed_complete else None
        if best:
            status, detail = "VERIFY_PRICE_OR_PIT", "公式開催期間は現在有効ですが、確認できた完成構成価格の観測時刻がその期間内ではありません。最新の価格・在庫・PITを取り直します。"
        else:
            status, detail = "NO_VERIFIED_COMPLETE_CONFIGURATION", "販売店の公式2026年期間内に価格・在庫・SKU・PITを直接確認できた32GB/1TB以上のRTX 5070 Tiデスクトップは未発見。"
    else:
        best = observed_complete[0] if observed_complete else None
        status, detail = "NO_VERIFIED_COMPLETE_CONFIGURATION", "販売店の公式2026年期間内に価格・在庫・SKU・PITを直接確認できた32GB/1TB以上のRTX 5070 Tiデスクトップは未発見。"
    rows.append({
        "candidate_id": None, "role": "rtx_5070_ti_outlier", "label": outlier.get("label") or "RTX 5070 Ti 大穴",
        "black_friday_target_price_jpy": int(outlier.get("black_friday_target_cap_jpy") or budget["pc_budget_jpy"]),
        "black_friday_price_observed_jpy": best.get("current_price_jpy") if best and bf_complete else None,
        "watch_window_reference_price_jpy": best.get("current_price_jpy") if (
            best and in_watch_window and not bf_complete
            and _parse_strategy_dt(best.get("retrieval_time"))
            and bf_start <= _parse_strategy_dt(best.get("retrieval_time")) <= bf_end
        ) else None,
        "pre_black_friday_reference_price_jpy": best.get("current_price_jpy") if (
            best and _parse_strategy_dt(best.get("retrieval_time"))
            and bf_start and _parse_strategy_dt(best.get("retrieval_time")) < bf_start
        ) else None,
        "post_black_friday_reference_price_jpy": best.get("current_price_jpy") if (
            best and _parse_strategy_dt(best.get("retrieval_time"))
            and bf_end and _parse_strategy_dt(best.get("retrieval_time")) > bf_end
        ) else None,
        "retailer_campaign_dates_confirmed": outlier_campaign_dates_confirmed,
        "retailer_campaign_active": outlier_official_campaign_active,
        "black_friday_offer_verified": bool(best and bf_complete), "price_verified": bool(best),
        "stock_status": best.get("stock_status", "unknown") if best else "unknown",
        "configuration_ready": bool(eligible), "configuration_reasons": [],
        "target_ram_gb": int(outlier.get("minimum_ram_gb") or 32), "target_ssd_gb": int(outlier.get("minimum_ssd_gb") or 1000),
        "bf_price_cap_jpy": bf_cap, "current_live_pc_budget_cap_reference_jpy": live_cap,
        "bf_budget_cap_is_final": bool(in_watch_window and budget_ready), "status": status, "detail": detail,
        "eligible_candidate_ids": [x.get("id") for x in eligible],
        "verified_complete_candidate_count": len(bf_complete if in_watch_window else observed_complete),
        "monitored_candidate_count": len(candidates), "url": sales_url(best) if best else None,
    })
    return {
        "generated_at": iso(now_jst()),
        "pricing_phase": "PROVISIONAL_BROAD_WATCH_WINDOW" if in_watch_window else ("PRE_BLACK_FRIDAY_REFERENCE" if now < (bf_start or now) else "POST_BLACK_FRIDAY_REFERENCE"),
        "black_friday_window_start_jst": phase.get("window_start_jst"),
        "black_friday_window_end_jst": phase.get("window_end_jst"),
        "watch_window_start_jst": phase.get("window_start_jst"),
        "watch_window_end_jst": phase.get("window_end_jst"),
        "watch_window_type": phase.get("window_type", "PROVISIONAL_BROAD_WATCH_WINDOW"),
        "official_campaign_dates_required": True,
        "future_black_friday_prices_known": bool(bf_complete),
        "total_budget_jpy": budget["total_budget_jpy"],
        "peripheral_target_budget_jpy": budget["peripheral_budget_jpy"],
        "pc_target_jpy": budget["pc_target_jpy"],
        "pc_planned_cap_jpy": budget["pc_budget_jpy"],
        "black_friday_pc_price_cap_jpy": bf_cap,
        "black_friday_pc_price_cap_final": bool(in_watch_window and budget_ready),
        "current_live_pc_budget_cap_reference_jpy": live_cap,
        "rows": rows,
        "score_policy_note": strategy.get("score_policy", "Actual scores are evidence-derived; no target score is hardcoded."),
        "price_semantics_note": "暫定の広域監視窓と販売店の公式2026年セール期間は別物です。BF実売とするには、公式日付範囲・商品SKU・直接価格・在庫・PITの確認が必要です。",
    }


def read_events():
    path = os.path.join(ROOT, "data", "change_events.jsonl")
    events = []
    if not os.path.exists(path):
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events

def build_products(latest, catalog):
    live = {str(x.get("id")): x for x in latest.get("products", []) if x.get("id")}
    out = []

    for cid, cat in catalog.items():
        if cid in live:
            out.append(live[cid])
            continue
        out.append({
            "id": cid,
            "url": cat.get("url"),
            "name": cat.get("name"),
            "family": cat.get("family"),
            "form_factor": cat.get("form_factor", "unknown"),
            "stock_status": cat.get("stock_status", "unknown"),
            "current_price_jpy": None,
            "last_valid_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
            "reference_price_jpy": cat.get("reference_price_jpy", cat.get("price_jpy")),
            "price_source_mode": "public_baseline",
            "price_validation_status": "reference_only",
            "data_confidence": "low",
            "spec": {k: cat.get(k) for k in ("gpu","cpu","tgp_w","ram_gb","ssd","vram_gb") if cat.get(k) not in (None, "")},
            "variant_match": "trusted_url" if cat.get("url_is_exact") else "ambiguous",
        })

    for cid, item in live.items():
        if cid in catalog:
            continue
        dynamic = dict(item)
        dynamic["dynamic_candidate"] = True
        dynamic.setdefault("variant_match", "ambiguous")
        dynamic.setdefault("data_confidence", "medium" if dynamic.get("current_price_jpy") is not None else "low")
        out.append(dynamic)

    return out

def main():
    latest_path = os.path.join(ROOT, "data", "current_latest.json")
    latest = load_json(latest_path, {"products": []})
    anchors = load_anchors()
    catalog = load_catalog()
    events = read_events()
    budget = purchase_budget_policy()
    peripheral_projection = peripheral_budget_projection()
    target_config = load_json(os.path.join(ROOT, "config", "targets.json"), {})
    strategy_config = target_config.get("purchase_strategy") or {}
    build_config = load_json(os.path.join(ROOT, "config", "build_components.json"), {})
    build_profile = build_config.get("profile") or {}
    method_policy = build_purchase_method_policy(build_profile)
    self_build_primary_method = method_policy["primary_method"] == "SELF_BUILD"

    source_snapshot_generated_at = latest.get("generated_at")
    source_snapshot_sha256 = file_sha256(latest_path) if os.path.exists(latest_path) else None

    products = build_products(latest, catalog)
    generated = iso(now_jst())
    watch = load_json(os.path.join(ROOT, "data", "watchlist.json"), {"urls": []})
    priority_by_id = {
        str(x.get("id")): str(x.get("priority") or "normal").lower()
        for x in (watch.get("urls") or [])
        if isinstance(x, dict) and x.get("id")
    }
    scored = []
    reference_only = []

    for product in products:
        row = build_row(product, anchors, events, prediction_time=generated)
        row["cash_total_cost_jpy"] = cash_total_cost(product)
        row["confirmed_benefit_value_jpy"] = confirmed_benefit_value(product)
        row["effective_cost_jpy"] = effective_cost(product)
        row["noncash_benefit_value_jpy"] = noncash_benefit_value_jpy(product)
        row["value_equivalent_cost_jpy"] = value_equivalent_cost(product)
        row["benefit_confidence"] = product.get("benefit_confidence")
        row["purchase_url"] = sales_url(product)
        row["source_snapshot_generated_at"] = source_snapshot_generated_at
        row["source_snapshot_sha256"] = source_snapshot_sha256
        if row.get("decision_score") is None:
            reference_only.append(suppress_current_price(row))
        else:
            scored.append(row)

    # Never let an out-of-stock product become the purchase recommendation.
    available = [x for x in scored if x.get("stock_status") != "out_of_stock"]
    unavailable = [x for x in scored if x.get("stock_status") == "out_of_stock"]
    available.sort(key=lambda x: (
        -x.get("decision_score", -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        x.get("id", ""),
    ))
    unavailable.sort(key=lambda x: (
        -x.get("decision_score", -1),
        x.get("current_price_jpy") if x.get("current_price_jpy") is not None else 10**12,
        x.get("id", ""),
    ))
    for i, row in enumerate(available, 1):
        row["rank"] = i
    for row in unavailable:
        row["rank"] = None

    scored = available
    action = scored[0] if scored else None

    partition = scored + unavailable + reference_only
    purchase_strategy_status = build_purchase_strategy_status(
        partition, strategy_config, budget, peripheral_projection
    )
    critical_ids = [cid for cid, priority in priority_by_id.items() if priority == "critical"]
    by_id = {str(x.get("id")): x for x in partition if x.get("id")}
    critical_unverified = [
        cid for cid in critical_ids
        if not (
            by_id.get(cid, {}).get("current_price_jpy") is not None
            and by_id.get(cid, {}).get("price_source_mode") == "direct_structured"
            and by_id.get(cid, {}).get("variant_match") in ("exact", "trusted_url", "strong")
            and by_id.get(cid, {}).get("stock_status") in ("in_stock", "low_stock", "out_of_stock")
        )
    ]
    coverage_status = "COMPLETE" if not critical_unverified else "PARTIAL"
    purchase_gate_allowed = bool(
        method_policy["completed_pc_purchase_actionable"]
        and action
        and coverage_status == "COMPLETE"
        and peripheral_projection.get("budget_data_ready")
        and action.get("score_detail", {}).get("status") in ("BUY_NOW", "BUY_NOW_LOW_STOCK", "BUY_NOW_NEAR_BUDGET")
        and action.get("effective_cost_jpy") is not None
        and action.get("effective_cost_jpy") <= peripheral_projection.get("pc_dynamic_cap_jpy", 0)
    )

    quality = {
        "candidate_count": len(partition),
        "critical_candidate_count": len(critical_ids),
        "critical_unverified_count": len(critical_unverified),
        "coverage_status": coverage_status,
        "actionable_count": len(scored),
        "reference_only_count": len(reference_only),
        "dynamic_candidate_count": sum(1 for x in partition if x.get("dynamic_candidate")),
        "direct_verified": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") in ("direct_structured", "direct_page", "direct_text")
        ),
        "search_verified": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("price_source_mode") == "search_snippet"
        ),
        "anomaly_rejected": sum(
            1 for x in partition if x.get("price_validation_status") == "anomaly_rejected"
        ),
        "variant_ambiguous": sum(
            1 for x in partition if x.get("variant_match") == "ambiguous"
        ),
        "unknown_stock": sum(
            1 for x in partition if x.get("stock_status") == "unknown"
        ),
        "out_of_stock": sum(
            1 for x in partition if x.get("stock_status") == "out_of_stock"
        ),
        "pit_unknown": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None and not x.get("available_at")
        ),
        "pit_failures": sum(
            1 for x in partition
            if x.get("current_price_jpy") is not None
            and x.get("available_at")
            and x.get("prediction_time")
            and not x.get("pit_valid", False)
        ),
    }

    out = {
        "generated_at": generated,
        "prediction_time": generated,
        "source_snapshot_generated_at": source_snapshot_generated_at,
        "source_snapshot_sha256": source_snapshot_sha256,
        "budget_jpy": BUDGET,
        "budget_scope": "pc_only_excluding_peripherals",
        "total_budget_jpy": budget["total_budget_jpy"],
        "peripheral_budget_jpy": budget["peripheral_budget_jpy"],
        "pc_target_jpy": budget["pc_target_jpy"],
        "pc_budget_jpy": budget["pc_budget_jpy"],
        "dynamic_pc_cap_jpy": peripheral_projection["pc_dynamic_cap_jpy"],
        "peripheral_projection_jpy": peripheral_projection["peripheral_projection_jpy"],
        "peripheral_budget_data_ready": peripheral_projection["budget_data_ready"],
        "peripheral_prices_unverified_ids": peripheral_projection["tracked_peripheral_unverified_ids"],
        "peripheral_channel_comparison_required_count": peripheral_projection["channel_comparison_required_count"],
        "peripheral_channel_comparison_complete_count": peripheral_projection["channel_comparison_complete_count"],
        "peripheral_channel_comparison_pending_ids": peripheral_projection["channel_comparison_pending_ids"],
        "peripherals": peripheral_projection["peripherals"],
        "effective_budget_jpy": BUDGET,
        "effective_soft_max_jpy": EFFECTIVE_SOFT_MAX,
        "effective_hard_max_jpy": EFFECTIVE_HARD_MAX,
        "season_phase": __import__("intelligence").season_phase(),
        "purchase_gate": {
            "allowed": purchase_gate_allowed,
            "coverage_status": coverage_status,
            "critical_unverified_ids": critical_unverified,
            "scope": "completed_pc_candidates_only",
            "reason": purchase_gate_reason(
                self_build_primary_method,
                critical_unverified,
                peripheral_projection.get("budget_data_ready") is True,
                action,
                peripheral_projection.get("pc_dynamic_cap_jpy", 0),
                purchase_gate_allowed,
            ),
        },
        "purchase_method_policy": method_policy,
        "top_recommendation": {
            "id": action.get("id") if action else None,
            "name": action.get("name") if action else None,
            "decision_score": action.get("decision_score") if action else None,
            "status": action.get("score_detail", {}).get("status") if action else "NO_VERIFIED_CANDIDATE",
            "purchase_url": sales_url(action) if action else None,
            "role": "REFERENCE_BENCHMARK_ONLY" if self_build_primary_method else "RANKED_PURCHASE_CANDIDATE",
            "purchase_actionable": bool(action and purchase_gate_allowed and method_policy["completed_pc_purchase_actionable"]),
        },
        "quality": quality,
        "coverage": latest.get("coverage") or {},
        "products": scored,
        "unavailable_products": unavailable,
        "reference_only": reference_only,
        "purchase_strategy": purchase_strategy_status,
        "method": {
            "total": 100,
            "performance_max": 40,
            "price_max": 20,
            "historical_evidence_max": 15,
            "stock_max": 15,
            "timing_max": 10,
            "note": "100点は購入判断の優先度であり、確率ではない。未確認情報はscore capまたはランキング除外で安全側に処理する。",
        }
    }
    save_json(os.path.join(ROOT, "data", "decision_rankings.json"), out)

    fetch_stats = latest.get("fetch_stats") or {}
    error_breakdown = fetch_stats.get("errors_by_host_reason") or {}
    error_breakdown_text = ", ".join(
        "{}={}".format(k, v) for k, v in sorted(error_breakdown.items())
    ) or "なし"

    lines = [
        "# ブラックフライデー期間通算・購入ランキング",
        "",
        f"更新: {generated}",
        f"観測スナップショット: {source_snapshot_generated_at or '未確認'}",
        f"観測スナップショットSHA256: {source_snapshot_sha256 or '未確認'}",
        f"総予算（PC＋周辺機器）: ¥{budget['total_budget_jpy']:,}",
        f"周辺機器の目標予算: ¥{budget['peripheral_budget_jpy']:,}",
        f"PC本体の目標価格: ¥{budget['pc_target_jpy']:,}",
        f"PC本体の計画上限（周辺機器が目標価格の場合）: ¥{budget['pc_budget_jpy']:,}",
        f"PC本体の動的上限（選択可能な周辺機器ルートの送料・価格を反映。未確認項目は予備額で保守的に試算）: ¥{peripheral_projection['pc_dynamic_cap_jpy']:,}",
        f"周辺機器の予算試算（ネット掲載価格と店頭現金価格は別項目。ネット配送は送料実額または送料予備額を反映）: ¥{peripheral_projection['peripheral_projection_jpy']:,}",
        f"周辺機器の価格・ネット在庫の確認: {peripheral_projection['tracked_peripheral_verified_count']}/{peripheral_projection['tracked_peripheral_count']}",
        f"周辺機器の全ルート比較: {peripheral_projection['channel_comparison_complete_count']}/{peripheral_projection['channel_comparison_required_count']}。比較保留: {', '.join(peripheral_projection['channel_comparison_pending_ids']) or 'なし'}",
        f"完成品PC参考候補の購入ゲート: **{'通過' if purchase_gate_allowed else '保留'}**（{out['purchase_gate']['reason']}）。自作PCの購入判定は別途、部品別互換性・実売・在庫・総額で評価します。",
        f"フェーズ: **{out['season_phase']}**",
        "",
    ]

    if action:
        d = action["score_detail"]
        price = action["current_price_jpy"]
        purchase_ready_now = bool(
            not self_build_primary_method
            and purchase_gate_allowed
            and d.get("configuration_ready")
            and d.get("status") in ("BUY_NOW", "BUY_NOW_NEAR_BUDGET", "BUY_NOW_LOW_STOCK")
        )
        summary_heading = (
            "## 完成品PCの参考ベンチマーク（自作PC本命とは別枠）"
            if self_build_primary_method
            else "## 現時点の最優先候補" if purchase_ready_now
            else "## 監視中の最高スコア候補（購入許可とは別判定）"
        )
        lines += [
            summary_heading,
            "",
            (
                "自作PCを正式な購入方式として最適化しています。組み立て時間・作業時間は減点しません。この完成品PCは同等仕様の価格・性能・部品品質・保証を比較するための参考候補であり、購入推薦ではありません。"
                if self_build_primary_method
                else "購入ゲートを通過した候補です。決済前に構成・在庫・最終支払額を再確認してください。"
                if purchase_ready_now
                else "これは現行データでスコアが最も高い監視候補であり、購入推奨や購入許可を意味しません。構成・総額・在庫・重要候補と周辺機器の確認が揃うまで、購入判断は保留です。"
            ),
            "",
            f"**スコア順位1位: [{action.get('form_factor','unknown')}] {action.get('name','')} — {action['decision_score']}/100**",
            f"- 現在価格: ¥{price:,}",
            f"- 必須費用込み現金総額: ¥{action.get('cash_total_cost_jpy'):,}" if action.get("cash_total_cost_jpy") is not None else "- 必須費用込み現金総額: 未確認",
            f"- 確定特典価値: ¥{action.get('confirmed_benefit_value_jpy', 0):,}",
            f"- 実質コスト（PC単体）: ¥{action.get('effective_cost_jpy'):,}" if action.get("effective_cost_jpy") is not None else "- 実質コスト（PC単体）: 未確認",
            (
                f"- PC＋周辺機器の参考試算総額（構成変更費未含む）: ¥{(action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']:,}"
                if action.get("effective_cost_jpy") is not None and not d.get("configuration_ready")
                else f"- PC＋周辺機器の試算総額: ¥{(action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']:,}"
                if action.get("effective_cost_jpy") is not None
                else "- PC＋周辺機器の試算総額: 未確認"
            ),
            (
                f"- 参考残額（構成変更費未含む）: ¥{budget['total_budget_jpy'] - ((action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']):,}"
                if action.get("effective_cost_jpy") is not None and not d.get("configuration_ready")
                else f"- 総予算の残額（試算）: ¥{budget['total_budget_jpy'] - ((action.get('effective_cost_jpy') or 0) + peripheral_projection['peripheral_projection_jpy']):,}"
                if action.get("effective_cost_jpy") is not None
                else "- 総予算の残額: 未確認"
            ),
            f"- PC構成要件: {'達成' if d.get('configuration_ready') else '未達/未確認 (' + ', '.join(d.get('configuration_reasons') or []) + ')'}",
            f"- 参考総価値換算額: ¥{action.get('value_equivalent_cost_jpy'):,}（購入許可には不使用）" if action.get("value_equivalent_cost_jpy") is not None else "- 参考総価値換算額: 未確認",
            f"- 判定: **{d['status']}**",
            (f"- 購入リンク: [販売ページ]({sales_url(action)})" if sales_url(action) else "- 購入リンク: 未確認"),
            f"- 買い判断: {d['reason']}",
            f"- 待つリスク: **{d['wait_risk']}**",
            f"- PC目標価格まで必要値下げ: {d['required_effective_discount_pct']:.1f}%" if d.get("required_effective_discount_pct") is not None else "- PC目標価格まで必要値下げ: 未算出（完成構成の価格・変更費用が未確認）" if not d.get("configuration_ready") else "- PC目標価格まで必要値下げ: 未確認",
            f"- 構成判定: **{d.get('variant_match')}**",
            f"- 価格情報: **{d.get('price_source_mode')} / {d.get('data_confidence')}**",
            "",
        ]
    else:
        lines += [
            "## 現時点の最優先候補",
            "",
            "**購入判断に使える現行価格が未確認です。**",
            "価格取得失敗・構成不一致・異常価格は安全側に除外しています。",
            "",
        ]

    lines += [
        f"## ¥{budget['total_budget_jpy']:,}・ブラックフライデー購入目標の監視（暫定の広域監視窓）",
        "",
        f"- 価格フェーズ: **{purchase_strategy_status['pricing_phase']}**",
        "- 監視窓はセールの公式開催日ではありません。販売店ごとの2026年日付範囲を公式ページで確認するまで、観測価格をBF実売に認定しません。",
        "- 以下のBF購入目標価格は開催期間の目標。開催前の表示価格は参考であり、BF価格の確定値ではありません。",
        f"- 暫定の広域監視窓（公式セール開催期間ではない）: {purchase_strategy_status['watch_window_start_jst']} ～ {purchase_strategy_status['watch_window_end_jst']}",
        f"- BF本体計画上限: ¥{purchase_strategy_status['pc_planned_cap_jpy']:,}",
        f"- 本体動的上限（追跡中の周辺機器価格を反映）: ¥{purchase_strategy_status['black_friday_pc_price_cap_jpy']:,}"
        + ("（確定）" if purchase_strategy_status["black_friday_pc_price_cap_final"] else "（目標予算からの計画値。BF実売ではない）"),
        "- 暫定監視窓内の価格は「監視窓内参考価格」、監視窓より前/後の価格はそれぞれセール前/後参考として表示します。公式日付・SKU・直接価格・在庫・PITが揃わない価格はBF実売に数えません。",
        "",
        "|優先方針|BF購入目標価格|公式期間内の確認価格|暫定監視窓内参考価格|セール前参考価格|セール後参考価格|判定|必要条件・値下げ額|",
        "|---|---:|---:|---:|---:|---:|---|---|",
        *[
            f"|{r['label']}|"
            f"{('¥'+format(r['black_friday_target_price_jpy'],',')) if r.get('black_friday_target_price_jpy') is not None else '動的上限'}|"
            f"{('¥'+format(r['black_friday_price_observed_jpy'],',')) if r.get('black_friday_offer_verified') and r.get('black_friday_price_observed_jpy') is not None else '未確認'}|"
            f"{('¥'+format(r['watch_window_reference_price_jpy'],',')) if r.get('watch_window_reference_price_jpy') is not None else '—'}|"
            f"{('¥'+format(r['pre_black_friday_reference_price_jpy'],',')) if r.get('pre_black_friday_reference_price_jpy') is not None else '—'}|"
            f"{('¥'+format(r['post_black_friday_reference_price_jpy'],',')) if r.get('post_black_friday_reference_price_jpy') is not None else '—'}|"
            f"**{r['status']}**|{r.get('detail','')}|"
            for r in purchase_strategy_status["rows"]
        ],
        "",
        purchase_strategy_status["score_policy_note"],
        "",
        peripheral_monitor_section_heading(target_config),
        "",
        "|画像|項目|購入方法|BF購入目標価格|観測価格（BF前は参考）|在庫（購入先）|価格確認|商品/比較ページ|",
        "|---|---|---|---:|---|---|---|---|",
        *[
            f"|{image_markup(next((t for t in (target_config.get('peripherals') or []) if str(t.get('id')) == str(p.get('id'))), {}), p.get('purchase_url'), 84)}|{p['name']}|{peripheral_route_label(p)}|¥{p['target_price_jpy']:,}|{peripheral_route_price_summary(p)}|{'店頭価格・支店在庫を別途確認' if p.get('purchase_channel') == 'compare_online_and_store' else inventory_status_label(p) if p.get('purchase_channel') == 'physical_store' else p.get('stock_status','unknown')}|{'店頭価格確認済み' if p.get('store_price_confirmed') else '店頭価格未確認' if p.get('purchase_channel') in ('physical_store','compare_online_and_store') else ('オンライン価格確認済み' if p.get('price_verified') else '未確認')}|{('[商品/比較ページ]('+p['purchase_url']+')') if p.get('purchase_url') else '予算枠のみ'}|"
            for p in peripheral_projection["peripherals"]
        ],
        "",
        f"周辺機器価格確認: {peripheral_projection['tracked_peripheral_verified_count']}/{peripheral_projection['tracked_peripheral_count']}。未確認項目は目標額を試算に使用し、自作PCを含む総額の購入判断は保留します。",
        "",
        "## 100点ランキング",
        "",
        "|順位|タイプ|商品|観測価格（BF前は参考）|現金総額|確定現金特典|実質コスト|非現金価値|価値加点|PC目標まで|性能|価格価値|過去根拠|在庫|時期|総合|判定|購入リンク|",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    # Insert an explicit, independently ranked accessory comparison before the PC score table.
    # Alternatives are monitored but do not add to the mandatory all-in budget.
    peripheral_snapshot = load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {})
    peripheral_live = {
        str(item.get("id")): item
        for item in (peripheral_snapshot.get("products") or [])
        if isinstance(item, dict) and item.get("id")
    }
    primary_targets = target_config.get("peripherals") or []
    alternative_targets = target_config.get("peripheral_alternatives") or []
    all_peripheral_items = [
        item for item in (primary_targets + alternative_targets)
        if isinstance(item, dict) and item.get("id")
    ]
    all_peripheral_targets = {str(item.get("id")): item for item in all_peripheral_items}
    mandatory_ids = {str(item.get("id")) for item in primary_targets}
    ranking_policy = target_config.get("peripheral_ranking_policy") or {}
    category_order = ranking_policy.get("category_order") or [
        {"category": "main_monitor", "label": "メインモニター（27インチ・WQHD）"},
        {"category": "keyboard", "label": "キーボード"},
        {"category": "mouse", "label": "マウス（FPS向け）"},
        {"category": "mousepad", "label": "マウスパッド"},
        {"category": "cables", "label": "映像ケーブル（必要な場合のみ）"},
    ]
    category_ids = {}
    for item in all_peripheral_items:
        category = item.get("category")
        if not category and item.get("family") == "display_cable":
            category = "cables"
        if category:
            category_ids.setdefault(str(category), []).append(str(item.get("id")))
    peripheral_category_lines = [
        "",
        "## 周辺機器カテゴリ別ランキング（カテゴリ別・最大3候補）",
        "",
        "各カテゴリから**1商品だけ**選びます。代替候補は価格監視対象ですが、選択しない限り必須周辺機器の総予算には加算しません。",
        "100点は用途適合35%、予算適合30%、仕様・機能20%、代替性・購入リスク15%のユーザー条件別評価であり、独立した実機ベンチマークではありません。",
        "BF購入目標・BF前の観測価格・在庫・送料込み決済額を分けて扱います。取得失敗は売り切れと見なしません。",
        "購入ルート：PC本体（自作パーツ）はネット注文。メインモニター・キーボード・マウス・マウスパッドはネット配送・実店舗・ネット注文の店舗受け取りを同一型番で比較します。ネット価格・送料・店頭現金価格・支店在庫・ポイント・保証・返品条件を別々に記録し、ネット価格を店頭価格として扱いません。電源タップは所有済み、スピーカー・サブモニター・ヘッドセットは購入対象外です。",
        "",
    ]
    for group in category_order:
        category = str(group.get("category") or "")
        group_name = str(group.get("label") or category)
        candidate_ids = list(dict.fromkeys(category_ids.get(category, [])))
        candidate_ids = [
            candidate_id for candidate_id in candidate_ids
            if candidate_id in all_peripheral_targets
        ]
        candidate_ids.sort(
            key=lambda candidate_id: (
                int(all_peripheral_targets[candidate_id].get("ranking_score_100", -1))
                if isinstance(all_peripheral_targets[candidate_id].get("ranking_score_100"), (int, float))
                   and not isinstance(all_peripheral_targets[candidate_id].get("ranking_score_100"), bool)
                else -1
            ),
            reverse=True,
        )
        candidate_ids = candidate_ids[:3]
        if not candidate_ids:
            continue
        peripheral_category_lines += [
            f"### {group_name}",
            "",
            "|順位|総合点|画像|商品|購入方法|BF購入目標|観測価格（BF前は参考）|在庫（購入先）|価格確認|選ぶ理由|商品ページ|",
            "|---:|---:|---|---|---|---:|---:|---|---|---|---|",
        ]
        for rank, candidate_id in enumerate(candidate_ids, 1):
            target = all_peripheral_targets[candidate_id]
            observation = peripheral_live.get(candidate_id, {})
            physical_store = peripheral_is_physical_store(target, target_config)
            comparison_route = bool(
                target.get("purchase_channel") == "compare_online_and_store"
                or {"physical_store", "store_pickup"}.intersection(target.get("purchase_channel_options") or [])
            )
            observed_price = observation.get("current_price_jpy") if observation.get("price_verified") else None
            if comparison_route:
                online_price = observed_price if isinstance(observed_price, int) and not isinstance(observed_price, bool) else None
                store_price = observation.get("store_price_jpy") if observation.get("store_price_confirmed") else None
                price_parts = []
                if online_price is not None:
                    online_part = f"ネット掲載 ¥{online_price:,}"
                    reserve = int(target.get("online_shipping_reserve_jpy") or 0)
                    if reserve and not observation.get("online_shipping_cost_verified"):
                        online_part += f"（送料未確認・予備枠¥{reserve:,}）"
                    price_parts.append(online_part)
                else:
                    price_parts.append("ネット価格未確認")
                if isinstance(store_price, int) and not isinstance(store_price, bool):
                    price_parts.append(f"店頭現金 ¥{store_price:,}")
                else:
                    price_parts.append("店頭現金価格未確認")
                price_text = " / ".join(price_parts)
                online_stock = str(observation.get("stock_status") or "unknown")
                store_stock = inventory_status_label(observation)
                stock_text = f"ネット:{online_stock} / 店頭:{store_stock}"
                verified_text = (
                    "ネット・店頭の両方を比較済み"
                    if online_price is not None and isinstance(store_price, int) and observation.get("store_stock_status") in ("in_stock", "low_stock")
                    else "ネット掲載のみ確認・購入先比較未完了"
                    if online_price is not None
                    else "価格・在庫未確認"
                )
            elif physical_store:
                observed_price = observation.get("online_comparison_price_jpy") if observation.get("online_comparison_price_jpy") is not None else None
                price_text = f"Web参考 ¥{int(observed_price):,}（店頭価格未確認）" if isinstance(observed_price, int) and not isinstance(observed_price, bool) else "店頭価格未確認"
                stock_text = inventory_status_label(observation)
                verified_text = "店頭価格未確認"
            else:
                price_text = f"¥{int(observed_price):,}" if isinstance(observed_price, int) and not isinstance(observed_price, bool) else "未確認"
                stock_text = str(observation.get("stock_status") or "unknown")
                verified_text = "確認済み" if observation.get("price_verified") and observed_price is not None else "未確認"
            purchase_method_text = peripheral_route_label(target)
            target_price = int(target.get("target_price_jpy") or 0)
            url = target.get("purchase_url") or target.get("monitor_url")
            product_link = f"[商品ページ]({url})" if isinstance(url, str) and url.startswith("https://") else "リンク未設定"
            image_html = image_markup(target, url, 88)
            suffix = "（主予算候補）" if candidate_id in mandatory_ids else "（代替候補）"
            score = target.get("ranking_score_100")
            score_text = f"**{int(score)}/100**" if isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= score <= 100 else "未評価"
            reason = str(target.get("ranking_reason") or target.get("target_price_note") or "").replace("|", "/").replace("\\n", " ").strip()
            peripheral_category_lines.append(
                f"|{rank}|{score_text}|{image_html}|{target.get('name', candidate_id)}{suffix}|{purchase_method_text}|¥{target_price:,}|{price_text}|{stock_text}|{verified_text}|{reason}|{product_link}|"
            )
        peripheral_category_lines.append("")
    peripheral_category_lines += [
        "### 予算・配線の実用項目",
        "",
        "- 電源タップは所有済みのため買い足さず、必要なケーブルは付属品を確認してから不足時だけ購入する。",
        "- DisplayPort/HDMIケーブルは付属品を確認してから、不足分だけ買う。",
        "- ポイントは現金支払額から控除せず、クーポンも決済画面で適用と最終支払額を確認できた場合だけ反映する。",
        "",
    ]
    # Surface historical BF evidence in the main report, but never turn sparse,
    # heterogeneous observations into a fake discount probability.
    historical = load_json(os.path.join(ROOT, "data", "historical_bf_analysis.json"), {})
    historical_observations = historical.get("price_observations") or []
    same_tier_rtx5070_bto = [
        item for item in historical_observations
        if item.get("category") == "desktop_bto"
        and "rtx 5070" in str(item.get("gpu") or "").lower()
        and "5070 ti" not in str(item.get("gpu") or "").lower()
        and isinstance(item.get("ram_gb"), int) and item.get("ram_gb") >= 32
        and isinstance(item.get("ssd_gb"), int) and item.get("ssd_gb") >= 1000
        and isinstance(item.get("sale_price_jpy"), int) and item.get("sale_price_jpy") > 0
    ]
    history_lines = [
        "",
        "## 過去のブラックフライデー実績（参考資料）",
        "",
        f"開催期間の記録：**{int(historical.get('campaign_record_count') or 0)}件**（{', '.join(str(y) for y in (historical.get('campaign_years_covered') or [])) or '年未集計'}） / "
        f"商品価格の観測：**{int(historical.get('historical_deal_record_count') or 0)}件**。",
        "[過去BFの詳細レポート](historical-bf-analysis.md) ・ "
        "[開催日程データ](../historical_bf_campaigns.json) ・ "
        "[商品価格CSV](../historical_bf_deals.csv)",
        "",
        "この資料は公開記事・公式告知で確認できた事例の集合であり、各店・各日の全価格履歴ではありません。過去の割引率は同じ型番・同等構成の2026年値下がり確率を意味しません。",
        "2026年のBF実売として採用するには、販売元の2026年公式キャンペーン期間と、期間内の同一商品の確認価格が必要です。BTO実績は自作PCパーツの合計額と分けて扱います。",
        "",
    ]
    if same_tier_rtx5070_bto:
        best_example = min(same_tier_rtx5070_bto, key=lambda x: int(x["sale_price_jpy"]))
        source_url = str(best_example.get("source_url") or "")
        source_grade = str(best_example.get("source_grade") or "source quality unknown")
        product_name = str(best_example.get("product") or best_example.get("model") or "model unknown")
        history_lines += [
            f"記録内で見つかった条件近似のBTO例（RTX 5070・RAM 32GB以上・SSD 1TB以上）："
            f"**¥{int(best_example['sale_price_jpy']):,}** — {product_name}（{source_grade}）。",
            f"[出典]({source_url})。BTO実例であり、自作PCの同額達成や2026年の値下がりを保証しません。",
            "",
        ]
    else:
        history_lines += [
            "記録内に、RTX 5070・RAM 32GB以上・SSD 1TB以上の価格比較に使えるBTO実例はありません。構成要件が欠ける価格を同条件の実績に流用しません。",
            "",
        ]
    if historical.get("forecast_policy", {}).get("probability_model_enabled") is not True:
        history_lines += [
            "**値下げ確率：未算出。** 同じ商品/構成の独立した履歴が不足しているため、見せかけの確率や平均値は出しません。",
            "",
        ]

    if "## 100点ランキング" in lines:
        insert_index = lines.index("## 100点ランキング")
        lines[insert_index:insert_index] = history_lines
        insert_index = lines.index("## 100点ランキング")
        lines[insert_index:insert_index] = peripheral_category_lines
    else:
        lines.extend(history_lines)
        lines.extend(peripheral_category_lines)

    for row in scored[:20]:
        d = row["score_detail"]
        lines.append(
            f"|{row['rank']}|{row.get('form_factor','unknown')}|{row.get('name','')[:55]}|¥{row['current_price_jpy']:,}|"
            f"¥{row.get('cash_total_cost_jpy'):,}|¥{row.get('confirmed_benefit_value_jpy', 0):,}|¥{row.get('effective_cost_jpy'):,}|"
            f"¥{row.get('noncash_benefit_value_jpy', 0):,}|+{d.get('value_bonus', 0)}|"
            f"{(format(d['required_effective_discount_pct'], '.1f') + '%') if d.get('required_effective_discount_pct') is not None else '未算出'}|"
            f"{d['performance']}/40|{d['price']}/20|"
            f"{d['history']}/15|{d['stock']}/15|{d['timing']}/10|"
            f"**{row['decision_score']}/100**|{d['status']}|"
            + (f"[販売ページ]({sales_url(row)})" if sales_url(row) else "未確認")
            + "|"
        )

    lines += [
        "",
        "## データ品質",
        "",
        f"- 候補総数: {quality['candidate_count']}",
        f"- デスクトップ候補: {sum(1 for x in products if x.get('form_factor') == 'desktop')}",
        f"- ノート候補: {sum(1 for x in products if x.get('form_factor') == 'laptop')}",
        f"- PC本体の目標価格: ¥{BUDGET:,}",
        f"- 実質ソフト上限: ¥{EFFECTIVE_SOFT_MAX:,}",
        f"- 実質ハード上限: ¥{EFFECTIVE_HARD_MAX:,}",
        f"- 重要候補: {quality['critical_candidate_count']}",
        f"- 重要候補の未確認: {quality['critical_unverified_count']}",
        f"- カバレッジ: {quality['coverage_status']}",
        f"- 現行価格を使える候補: {quality['actionable_count']}",
        f"- 参照情報のみ: {quality['reference_only_count']}",
        f"- 自動発見候補: {quality['dynamic_candidate_count']}",
        f"- 直接確認: {quality['direct_verified']}",
        f"- 検索補完: {quality['search_verified']}",
        f"- 異常価格棄却: {quality['anomaly_rejected']}",
        f"- 構成不明: {quality['variant_ambiguous']}",
        f"- 在庫不明: {quality['unknown_stock']}",
        f"- 売り切れ確認: {quality['out_of_stock']}",
        f"- PIT失敗: {quality['pit_failures']}",
        f"- 処理対象: {(latest.get('coverage') or {}).get('processed_count', len(products))} / {(latest.get('coverage') or {}).get('watchlist_count', len(products))}",
        f"- 処理率: {(latest.get('coverage') or {}).get('processing_rate_pct', 100.0):.1f}%",
        f"- 取得成功率: {(latest.get('coverage') or {}).get('transport_success_rate_pct', 0.0):.1f}%",
        f"- 価格確認率: {(latest.get('coverage') or {}).get('price_verified_rate_pct', 0.0):.1f}%",
        f"- 検索補完（成功/試行）: {fetch_stats.get('search_fallback_successes', 0)}/{fetch_stats.get('search_fallback_attempts', 0)}",
        f"- 検索SKU不一致による除外: {fetch_stats.get('search_identity_rejections', 0)}",
        f"- 取得エラー内訳（host|reason）: {error_breakdown_text}",
        f"- 未処理候補: {', '.join((latest.get('coverage') or {}).get('skipped_ids', [])) or 'なし'}",
        "",
        "## 価格シナリオ",
        "",
    ]

    for row in scored[:10]:
        price = row["current_price_jpy"]
        scenarios = scenario_prices(price)
        first = next((x for x in scenarios if x["price_jpy"] <= BUDGET), None)
        lines.append(f"### {row['rank']}. {row.get('name','')}")
        lines.append(
            " / ".join(f"{x['discount_pct']}%→¥{x['price_jpy']:,}" for x in scenarios)
            + (f" / PC目標価格到達→{first['discount_pct']}%" if first else " / 30%でもPC目標価格未到達")
        )
        lines.append("")

    lines += [
        "## 判定ルール",
        "",
        "- BUY_NOW: PC本体の実質コストが、現在の周辺機器予算を反映した動的上限以下で、構成・在庫・データ品質を通過。",
        "- BUY_NOW_NEAR_BUDGET: 動的上限付近でも、性能・在庫・構成一致・データ品質が特に強い場合だけ許可。",
        "- BUY_NOW_LOW_STOCK: PC本体の動的上限内かつ低在庫。最安値待ちを避ける。",
        "- NEEDS_CONFIGURATION: RAM32GBまたはSSD1TBを満たさない基本構成。変更後価格が確認できるまで購入不可。",
        "- STRONG_WATCH: 未到達でも性能・価格距離・過去根拠が強い。",
        "- VALUE_WATCH: PC本体の上限超でも、高性能候補として値下げを監視。購入許可ではない。",
        "- WAIT_FOR_DISCOUNT: 大幅値下げ待ち。",
        "- VERIFY_NOW: 検索補完など。購入前に販売ページで再確認。",
        "- UNACTIONABLE: 現行価格を確認できない、または異常値・構成不一致。",
        "",
        "## Fail-closedルール",
        "",
        "- 取得失敗は売り切れではない。",
        "- 月額、分割、ポイント等の数字を販売価格として採用しない。",
        "- 一般的な「X円OFF」は表示価格に既に反映済みの可能性があるため、実質コストから二重控除しない。",
        "- 追加クーポン/カート値引きだけを confirmed cash benefit として実質コストに反映する。",
        "- モニター等の周辺機器価値、無料アップグレード、保証延長は実質コストから控除せず、別の価値加点・参考総価値換算として扱う。",
        "- 異常な激安価格は独立確認なしでは採用しない。",
        "- 参照価格は現在価格ではない。",
        "- 共有商品ページは exact variant とみなさない。",
        "- 過去価格は同一構成 > 同GPU同シリーズ > 同シリーズの順で証拠力を下げる。",
        "- PIT不明・違反データから購入判断を作らない。",
    ]

    os.makedirs(os.path.join(ROOT, "data", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "reports", "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
