import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

from intelligence import (
    ROOT, BUDGET, load_json, load_catalog, load_anchors,
    scenario_prices, required_discount, now_jst, iso, purchase_budget_policy,
    actionable_max_age_minutes, parse_dt, configuration_readiness, gpu_key
)

JST = timezone(timedelta(hours=9))
BF_DISCOUNT_BANDS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]


def _price_is_trusted(item, now):
    price = item.get("current_price_jpy")
    retrieved = parse_dt(item.get("retrieval_time"))
    available = parse_dt(item.get("available_at"))
    if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
        return False
    if item.get("price_source_mode") != "direct_structured":
        return False
    if item.get("price_validation_status") not in ("validated", "validated_exact_model_page", "anomaly_corroborated"):
        return False
    if item.get("variant_match") not in ("exact", "trusted_url", "strong"):
        return False
    if item.get("stock_status") not in ("in_stock", "low_stock"):
        return False
    if not retrieved or not available or available > retrieved or retrieved > now:
        return False
    age_minutes = (now - retrieved).total_seconds() / 60
    return 0 <= age_minutes <= actionable_max_age_minutes(now)


def _price_bands(base_price):
    return [
        {"discount_pct": pct, "price_jpy": int(round(base_price * (100-pct) / 100))}
        for pct in BF_DISCOUNT_BANDS
    ]


def _inside_window(value, start, end):
    dt = parse_dt(value) if not isinstance(value, datetime) else value
    return bool(dt and start and end and start <= dt <= end)


def build_black_friday_price_plan(target_config, catalog_data, latest, peripheral_snapshot, now=None):
    """Build BF target-price scenarios separately from observed sale prices.

    Before the configured window, live listings are only reference evidence.
    Discount bands are arithmetic what-if scenarios, never probabilities or price
    promises. Actual BF prices require fresh, verified observations retrieved
    inside the configured BF window.
    """
    now = now or now_jst()
    policy = purchase_budget_policy()
    strategy = target_config.get("purchase_strategy") or {}
    semantics = strategy.get("price_semantics") or {}
    start = parse_dt(semantics.get("window_start_jst"))
    end = parse_dt(semantics.get("window_end_jst"))
    in_bf_window = bool(start and end and start <= now <= end)
    phase = "BLACK_FRIDAY_WINDOW" if in_bf_window else ("PRE_BLACK_FRIDAY_REFERENCE" if start and now < start else "POST_BLACK_FRIDAY_REFERENCE")

    live_by_id = {str(x.get("id")): x for x in (latest.get("products") or []) if x.get("id")}
    catalog_by_id = {str(x.get("id")): x for x in (catalog_data.get("candidates") or []) if x.get("id")}
    all_products = dict(catalog_by_id)
    for cid, item in live_by_id.items():
        if cid not in all_products:
            all_products[cid] = item

    pc_rows = []
    outlier_rule = strategy.get("outlier_rule") or {}
    outlier_gpu = str(outlier_rule.get("gpu") or "RTX 5070 Ti").lower().replace("rtx ", "")
    for cid, cat in all_products.items():
        live = live_by_id.get(cid, {})
        trusted = _price_is_trusted(live, now)
        retrieved_at = parse_dt(live.get("retrieval_time")) if trusted else None
        is_bf_observation = bool(in_bf_window and retrieved_at and start <= retrieved_at <= end and trusted)
        live_price = live.get("current_price_jpy") if trusted else None
        reference = cat.get("reference_price_jpy", cat.get("price_jpy"))
        if reference is None:
            reference = live.get("reference_price_jpy") or live.get("last_valid_price_jpy")
        if is_bf_observation:
            scenario_base = live_price
            scenario_source = "BLACK_FRIDAY_OBSERVED_PRICE"
        elif live_price is not None:
            scenario_base = live_price
            scenario_source = "PRE_BLACK_FRIDAY_REFERENCE"
        else:
            scenario_base = reference
            scenario_source = "CATALOG_REFERENCE_ONLY" if reference is not None else "NO_PRICE_REFERENCE"

        gpu = str((live.get("spec") or {}).get("gpu") or (live.get("parsed_spec") or {}).get("gpu") or cat.get("gpu") or "")
        form_factor = live.get("form_factor") or cat.get("form_factor") or "unknown"
        is_ti_desktop = form_factor == "desktop" and outlier_gpu in gpu_key({"spec": {"gpu": gpu}}).lower()
        bf_target = int(outlier_rule.get("black_friday_target_cap_jpy") or policy["pc_budget_jpy"]) if is_ti_desktop else int(policy["pc_target_jpy"])
        if scenario_base is not None:
            scenario_base = int(scenario_base)
            price_bands = _price_bands(scenario_base)
            discount_target = max(0, scenario_base - bf_target)
            discount_cap = max(0, scenario_base - int(policy["pc_budget_jpy"]))
            discount_target_pct = round(100 * discount_target / scenario_base, 1) if scenario_base else None
            discount_cap_pct = round(100 * discount_cap / scenario_base, 1) if scenario_base else None
        else:
            price_bands, discount_target, discount_cap = [], None, None
            discount_target_pct = discount_cap_pct = None
        ready, config_reasons = configuration_readiness(live) if live else (False, ["現行構成未確認"])
        pc_rows.append({
            "id": cid,
            "name": live.get("name") or cat.get("name"),
            "form_factor": form_factor,
            "gpu": gpu or None,
            "ram_gb": (live.get("spec") or {}).get("ram_gb", cat.get("ram_gb")),
            "ssd": (live.get("spec") or {}).get("ssd", cat.get("ssd")),
            "black_friday_target_price_jpy": bf_target,
            "black_friday_price_observed_jpy": live_price if is_bf_observation else None,
            "black_friday_offer_verified": is_bf_observation,
            "pre_black_friday_reference_price_jpy": live_price if trusted and not is_bf_observation else reference,
            "pre_black_friday_reference_at": live.get("retrieval_time") if trusted and not is_bf_observation else None,
            "price_reference_kind": scenario_source,
            "scenario_base_price_jpy": scenario_base,
            "scenario_base_note": (
                "観測済みBF価格を基準にした算術シナリオ"
                if is_bf_observation else
                "事前参考額を基準にした仮想割引。BF実売価格・値下げ確率ではない"
            ),
            "scenario_prices": price_bands,
            "discount_needed_to_bf_target_jpy": discount_target,
            "discount_needed_to_bf_target_pct": discount_target_pct,
            "discount_needed_to_planned_cap_jpy": discount_cap,
            "discount_needed_to_planned_cap_pct": discount_cap_pct,
            "is_rtx_5070_ti_outlier": is_ti_desktop,
            "configuration_ready": ready,
            "configuration_reasons": config_reasons,
            "stock_status": live.get("stock_status", "unknown"),
            "purchase_url": live.get("url") or cat.get("url"),
        })
    pc_rows.sort(key=lambda x: (
        not x["is_rtx_5070_ti_outlier"],
        x["discount_needed_to_bf_target_pct"] if x["discount_needed_to_bf_target_pct"] is not None else 9999,
        x["name"] or "",
    ))

    snapshot_time = parse_dt(peripheral_snapshot.get("generated_at"))
    max_age = actionable_max_age_minutes(now)
    snapshot_fresh = bool(snapshot_time and 0 <= (now-snapshot_time).total_seconds()/60 <= max_age)
    peripheral_live = {str(x.get("id")): x for x in (peripheral_snapshot.get("products") or []) if x.get("id")}
    peripheral_rows = []
    total_target = 0
    bf_observed_tracked_total = 0
    tracked_count = 0
    tracked_bf_verified = 0
    projected_bf_cost = 0
    for target in target_config.get("peripherals") or []:
        if not target.get("mandatory", True):
            continue
        pid = str(target.get("id") or "")
        goal = int(target.get("target_price_jpy") or 0)
        total_target += goal
        live = peripheral_live.get(pid, {})
        price = live.get("current_price_jpy")
        retrieved_at = parse_dt(live.get("retrieval_time"))
        available_at = parse_dt(live.get("available_at"))
        trusted = bool(
            target.get("track_current_price")
            and live.get("price_verified") is True
            and live.get("identity_verified") is not False
            and isinstance(price, int) and not isinstance(price, bool) and price > 0
            and live.get("stock_status") in ("in_stock", "low_stock")
            and snapshot_fresh and retrieved_at and available_at
            and available_at <= retrieved_at <= now
            and 0 <= (now-retrieved_at).total_seconds()/60 <= max_age
        )
        is_bf = bool(trusted and in_bf_window and start <= retrieved_at <= end)
        if target.get("track_current_price"):
            tracked_count += 1
            if is_bf:
                tracked_bf_verified += 1
                bf_observed_tracked_total += price
        estimated_cost = price if is_bf else goal
        projected_bf_cost += estimated_cost
        peripheral_rows.append({
            "id": pid, "name": target.get("name"), "purchase_url": target.get("purchase_url") or target.get("monitor_url"),
            "black_friday_target_price_jpy": goal,
            "black_friday_price_observed_jpy": price if is_bf else None,
            "black_friday_price_verified": is_bf,
            "pre_black_friday_reference_price_jpy": price if trusted and not is_bf else None,
            "pre_black_friday_reference_at": live.get("retrieval_time") if trusted and not is_bf else None,
            "price_reference_kind": "BLACK_FRIDAY_OBSERVED_PRICE" if is_bf else ("PRE_BLACK_FRIDAY_REFERENCE" if trusted else "TARGET_ONLY_UNVERIFIED"),
            "stock_status": live.get("stock_status", "unknown"),
            "target_gap_vs_pre_bf_reference_jpy": max(0, price-goal) if trusted and not is_bf else None,
            "discount_needed_to_target_pct": round(max(0, (price-goal)/price*100), 1) if trusted and not is_bf and price else None,
            "planning_cost_jpy": estimated_cost,
            "cost_basis": "observed_bf_price" if is_bf else "black_friday_target_reserve",
            "track_current_price": bool(target.get("track_current_price")),
        })

    tracked_all_bf_verified = bool(tracked_count and tracked_bf_verified == tracked_count)
    bf_pc_cap = min(int(policy["pc_budget_jpy"]), int(policy["total_budget_jpy"])-projected_bf_cost)
    target_sum_matches = total_target == int(policy["peripheral_budget_jpy"])
    return {
        "pricing_phase": phase,
        "black_friday_window_start_jst": semantics.get("window_start_jst"),
        "black_friday_window_end_jst": semantics.get("window_end_jst"),
        "black_friday_prices_known": bool(in_bf_window),
        "future_black_friday_prices_confirmed": False if not in_bf_window else None,
        "all_configured_prices_are_bf_targets": True,
        "targets_are_estimates_not_promises": True,
        "discount_scenarios_are_probabilities": False,
        "total_budget_jpy": int(policy["total_budget_jpy"]),
        "pc_target_price_jpy": int(policy["pc_target_jpy"]),
        "pc_planned_hard_cap_jpy": int(policy["pc_budget_jpy"]),
        "peripheral_target_total_jpy": total_target,
        "black_friday_ideal_bundle_target_jpy": int(policy["pc_target_jpy"])+total_target,
        "black_friday_target_buffer_jpy": int(policy["total_budget_jpy"])-int(policy["pc_target_jpy"])-total_target,
        "black_friday_hard_cap_bundle_jpy": int(policy["pc_budget_jpy"])+total_target,
        "black_friday_pc_price_cap_jpy": bf_pc_cap,
        "black_friday_pc_price_cap_final": bool(in_bf_window and snapshot_fresh and tracked_all_bf_verified),
        "peripheral_snapshot_fresh": snapshot_fresh,
        "tracked_peripheral_count": tracked_count,
        "tracked_peripheral_bf_price_verified_count": tracked_bf_verified,
        "tracked_peripheral_all_bf_prices_verified": tracked_all_bf_verified,
        "all_in_checkout_total_final": False,
        "peripherals": peripheral_rows,
        "pc_candidates": pc_rows,
        "rtx_5070_ti_desktop_outliers": [x for x in pc_rows if x["is_rtx_5070_ti_outlier"]],
        "rules": [
            "Before the Black Friday window, all live listings are reference prices, not BF prices.",
            "Only a fresh verified observation retrieved inside the BF window can populate black_friday_price_observed_jpy.",
            "Discount bands are arithmetic what-if scenarios; they are not probabilities or promises.",
            "A baseline build that misses RAM/SSD requirements must include a quoted upgrade cost before budget qualification.",
            "No purchase is authorized until full configuration, stock, PIT, peripheral budget and checkout terms pass the main purchase gate.",
        ],
    }

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    latest_path=os.path.join(ROOT,"data","current_latest.json")
    latest=load_json(latest_path,{"products":[]})
    source_snapshot_generated_at=latest.get("generated_at")
    source_snapshot_sha256=file_sha256(latest_path) if os.path.exists(latest_path) else None
    catalog=load_catalog()
    catalog_data=load_json(os.path.join(ROOT,"config","candidate_catalog.json"), {"candidates":[]})
    target_config=load_json(os.path.join(ROOT,"config","targets.json"), {})
    peripheral_snapshot=load_json(os.path.join(ROOT,"data","peripheral_prices.json"), {})
    anchors=load_anchors()
    live={str(x.get("id")):x for x in latest.get("products",[]) if x.get("id")}
    bf_plan=build_black_friday_price_plan(target_config,catalog_data,latest,peripheral_snapshot,now=now_jst())

    products=dict(live)
    for cid,cat in catalog.items():
        products.setdefault(cid,{
            "id":cid,
            "name":cat.get("name"),
            "family":cat.get("family"),
            "form_factor":cat.get("form_factor"),
            "stock_status":cat.get("stock_status","unknown"),
            "current_price_jpy":None,
            "reference_price_jpy":cat.get("reference_price_jpy",cat.get("price_jpy")),
            "price_source_mode":"public_baseline",
        })

    rows=[]
    for cid,p in products.items():
        cat=catalog.get(cid,{})
        current=p.get("current_price_jpy")
        reference=p.get("reference_price_jpy",cat.get("reference_price_jpy",cat.get("price_jpy")))
        base=current if current is not None else reference
        if base is None:
            continue

        family=str(p.get("family") or cat.get("family") or "").lower()
        gpu=str((p.get("spec") or {}).get("gpu") or cat.get("gpu") or "").lower()
        floor=None
        floor_strength="none"
        for a in anchors:
            af=str(a.get("family","")).lower()
            ag=str(a.get("gpu","")).lower()
            ap=a.get("historical_price_jpy")
            if not ap:
                continue
            same_family=bool(family and af and af in family)
            same_gpu=bool(gpu and ag and gpu in ag)
            if same_family and same_gpu:
                strength="same_family_same_gpu"
            elif same_family:
                strength="same_family"
            elif same_gpu:
                strength="same_gpu"
            else:
                continue
            priority={"same_family_same_gpu":3,"same_family":2,"same_gpu":1}[strength]
            cur_priority={"same_family_same_gpu":3,"same_family":2,"same_gpu":1,"none":0}[floor_strength]
            if floor is None or priority>cur_priority or (priority==cur_priority and ap<floor):
                floor=ap
                floor_strength=strength

        scenarios=scenario_prices(base)
        first=next((x for x in scenarios if x["price_jpy"]<=BUDGET),None)
        rows.append({
            "id":cid,
            "name":p.get("name") or cat.get("name"),
            "form_factor":p.get("form_factor") or cat.get("form_factor"),
            "current_price_jpy":current,
            "reference_price_jpy":reference,
            "reference_only":current is None,
            "required_discount_pct":round(required_discount(base),1),
            "historical_floor_jpy":floor,
            "historical_floor_strength":floor_strength,
            "scenario_prices":scenarios,
            "first_pc_target_scenario":first,
            "stock_status":p.get("stock_status") or cat.get("stock_status","unknown"),
            "price_source_mode":p.get("price_source_mode") or "public_baseline",
            "price_validation_status":p.get("price_validation_status"),
            "dynamic_candidate":bool(p.get("dynamic_candidate")),
        })

    rows.sort(key=lambda x:(x["reference_only"],x["required_discount_pct"],x["historical_floor_jpy"] or 999999999))
    out={"generated_at":iso(now_jst()),
         "source_snapshot_generated_at":source_snapshot_generated_at,
         "source_snapshot_sha256":source_snapshot_sha256,
         "budget_jpy":BUDGET,
         "budget_scope":"pc_only_excluding_peripherals",
         "total_budget_jpy":purchase_budget_policy()["total_budget_jpy"],
         "peripheral_budget_jpy":purchase_budget_policy()["peripheral_budget_jpy"],
         "pc_budget_jpy":purchase_budget_policy()["pc_budget_jpy"],
         "black_friday_purchase_plan":bf_plan,
         "note":"BF purchase targets, pre-BF references, observed BF prices, and arithmetic discount scenarios are separate. Scenario bands are not probabilities.",
         "rows":rows}
    os.makedirs(os.path.join(ROOT,"data","reports"),exist_ok=True)
    with open(os.path.join(ROOT,"data","scenario_analysis.json"),"w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)

    lines=["# ブラックフライデー価格・一式購入シナリオ","",f"更新: {out['generated_at']}",
           f"価格フェーズ: **{bf_plan['pricing_phase']}**",
           f"BF監視窓: {bf_plan['black_friday_window_start_jst']} ～ {bf_plan['black_friday_window_end_jst']}",
           f"総予算: ¥{bf_plan['total_budget_jpy']:,}",
           f"BF PC理想目標: ¥{bf_plan['pc_target_price_jpy']:,} / 計画上限: ¥{bf_plan['pc_planned_hard_cap_jpy']:,}",
           f"BF周辺機器目標合計: ¥{bf_plan['peripheral_target_total_jpy']:,}",
           f"BF PC理想目標＋周辺機器目標: ¥{bf_plan['black_friday_ideal_bundle_target_jpy']:,} (予算残 ¥{bf_plan['black_friday_target_buffer_jpy']:,})",
           f"BF PC計画上限＋周辺機器目標: ¥{bf_plan['black_friday_hard_cap_bundle_jpy']:,}",
           "",
           "**重要:** BF目標額は購入目標であって実売の保証ではありません。期間前の観測価格は参考値、BF価格は期間中の新しい観測でのみ確定します。割引シナリオは算術上の仮定であり確率ではありません。",
           "",
           "## 全周辺機器のBF購入目標",
           "",
           "|項目|BF購入目標|BF期間内の確認済み価格|BF前参考価格|在庫|費用の扱い|購入ページ|",
           "|---|---:|---:|---:|---|---|---|"]
    for p in bf_plan["peripherals"]:
        bf_price = p.get("black_friday_price_observed_jpy")
        ref_price = p.get("pre_black_friday_reference_price_jpy")
        link = f"[商品ページ]({p['purchase_url']})" if p.get("purchase_url") else "予算枠/見積確認"
        lines.append(
            f"|{p['name']}|¥{p['black_friday_target_price_jpy']:,}|"
            f"{('¥'+format(bf_price,',')) if bf_price is not None else '未確認'}|"
            f"{('¥'+format(ref_price,',')) if ref_price is not None else '—'}|"
            f"{p.get('stock_status','unknown')}|{p['cost_basis']}|{link}|"
        )
    lines += [
        "",
        "## 大穴候補（RTX 5070 Ti デスクトップ）",
        "",
        "|候補|BF目標上限|参照価格/シナリオ基準|BF期間内価格|32GB/1TB|上限まで必要値下げ|必要割引率|シナリオ|状態|購入ページ|",
        "|---|---:|---:|---:|---|---:|---:|---|---|---|",
    ]
    for r in bf_plan["rtx_5070_ti_desktop_outliers"]:
        base = r.get("scenario_base_price_jpy")
        bf_price = r.get("black_friday_price_observed_jpy")
        bands = {x["discount_pct"]:x["price_jpy"] for x in r.get("scenario_prices",[])}
        band_text = " / ".join(f"{pct}% ¥{bands[pct]:,}" for pct in (20,25,30) if pct in bands) or "基準価格なし"
        lines.append(
            f"|{r['name']}|¥{r['black_friday_target_price_jpy']:,}|"
            f"{('¥'+format(base,',')) if base is not None else '未確認'}|"
            f"{('¥'+format(bf_price,',')) if bf_price is not None else '未確認'}|"
            f"{('達成' if r['configuration_ready'] else '未達/未確認')}|"
            f"{('¥'+format(r['discount_needed_to_bf_target_jpy'],',')) if r.get('discount_needed_to_bf_target_jpy') is not None else '—'}|"
            f"{(format(r['discount_needed_to_bf_target_pct'],'.1f')+'%') if r.get('discount_needed_to_bf_target_pct') is not None else '—'}|"
            f"{band_text}|{r['price_reference_kind']}|"
            f"{('[商品ページ]('+r['purchase_url']+')') if r.get('purchase_url') else '未確認'}|"
        )
    lines += [
        "",
        "## BF目標価格に対する全PC候補の割引シナリオ",
        "",
        "|候補|フォーム|GPU|BF価格目標|参考/計算基準|BF内観測価格|目標まで必要値下げ|必要割引率|20%|25%|30%|構成条件|価格の根拠|購入リンク|",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for r in bf_plan["pc_candidates"]:
        bands={x["discount_pct"]:x["price_jpy"] for x in r.get("scenario_prices",[])}
        ref=r.get("pre_black_friday_reference_price_jpy")
        base=r.get("scenario_base_price_jpy")
        bf_price=r.get("black_friday_price_observed_jpy")
        gap=r.get("discount_needed_to_bf_target_jpy")
        pct=r.get("discount_needed_to_bf_target_pct")
        link=f"[販売ページ]({r['purchase_url']})" if r.get("purchase_url") else "未確認"
        lines.append(
            f"|{(r.get('name') or r['id'])[:48]}|{r['form_factor']}|{r.get('gpu') or '—'}|"
            f"¥{r['black_friday_target_price_jpy']:,}|"
            f"{('¥'+format(ref,',')) if ref is not None else (('¥'+format(base,',')) if base is not None else '未確認')}|"
            f"{('¥'+format(bf_price,',')) if bf_price is not None else '未確認'}|"
            f"{('¥'+format(gap,',')) if gap is not None else '—'}|"
            f"{(format(pct,'.1f')+'%') if pct is not None else '—'}|"
            f"{('¥'+format(bands[20],',')) if 20 in bands else '—'}|"
            f"{('¥'+format(bands[25],',')) if 25 in bands else '—'}|"
            f"{('¥'+format(bands[30],',')) if 30 in bands else '—'}|"
            f"{('達成' if r['configuration_ready'] else '未達/未確認')}|{r['price_reference_kind']}|{link}|"
        )
    lines += ["", "## 既存の参照価格シナリオ（比較用・確率ではない）", "",
              "以下の参考価格ベースの値引率シナリオは、将来のブラックフライデー実売価格を保証するものではありません。"]
    lines.append("")
    lines.append("|商品|参考基準価格|参考基準から必要な値下げ|10%|15%|20%|25%|30%|PC目標価格到達|過去最安根拠|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        s={x["discount_pct"]:x["price_jpy"] for x in r["scenario_prices"]}
        first=r["first_pc_target_scenario"]
        lines.append(
            f"|{r['name'][:50]}|"
            f"{('¥'+format(r['reference_price_jpy'],',')) if r['reference_price_jpy'] else '—'}|"
            f"{r['required_discount_pct']:.1f}%|"
            f"¥{s[10]:,}|¥{s[15]:,}|¥{s[20]:,}|¥{s[25]:,}|¥{s[30]:,}|"
            f"{str(first['discount_pct'])+'%' if first else '未到達'}|{r['historical_floor_strength']}|"
        )
    lines += ["","## ケース","",
              "- A: PC目標価格到達＋在庫あり → 即時再評価。",
              "- B: PC目標価格到達＋低在庫 → 最安値待ちを避ける。",
              "- C: 大幅値下げだが未達 → 性能・在庫・次の値下げ余地を再評価。",
              "- D: 売り切れ → 代替候補へ。",
              "- E: 取得不能 → 売り切れとはみなさず、別ソース再確認。",
              "- F: 異常価格 → 独立確認なしでは現行価格に採用しない。"]
    with open(os.path.join(ROOT,"data","reports","scenario_analysis.md"),"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__=="__main__":
    main()
