import hashlib
import html
import json
import os
import re
from datetime import datetime
from urllib.parse import urlsplit

from intelligence import (
    ROOT, BUDGET, EFFECTIVE_SOFT_MAX, EFFECTIVE_HARD_MAX,
    load_json, save_json, load_catalog, load_anchors,
    build_row, cash_total_cost, confirmed_benefit_value, effective_cost, noncash_benefit_value_jpy, value_equivalent_cost,
    now_jst, iso, scenario_prices, purchase_budget_policy, peripheral_budget_projection,
    configuration_readiness, gpu_key
)
from sale_calendar import campaign_window_for_item

def early_buy_amount_label(review):
    """Display a product listing price separately from a shipping estimate or verified checkout total."""
    review = review if isinstance(review, dict) else {}
    observed = review.get("observed_price_jpy")
    estimate = review.get("estimated_checkout_total_jpy")
    verified_total = review.get("verified_checkout_total_jpy")
    verified = review.get("checkout_total_verified") is True
    if verified and isinstance(verified_total, int) and not isinstance(verified_total, bool) and verified_total > 0:
        return "決済総額確認済み ¥{:,}".format(verified_total)
    if isinstance(observed, int) and not isinstance(observed, bool) and observed > 0:
        if isinstance(estimate, int) and not isinstance(estimate, bool) and estimate > 0 and estimate != observed:
            return "掲載 ¥{:,} / 送料込概算 ¥{:,}（決済未確認）".format(observed, estimate)
        return "掲載 ¥{:,}（決済未確認）".format(observed)
    return "未確認"


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
    """Return only an absolute HTTP(S) URL with a hostname; never fabricate a purchase URL."""
    url = str(item.get("url") or "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ("https", "http") or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return url


def retrieval_issue_link_section(latest, build_components=None, peripherals=None):
    """Render explicit per-item links whenever retrieval, price, variant or stock evidence is incomplete."""
    latest = latest if isinstance(latest, dict) else {}
    build_components = build_components if isinstance(build_components, dict) else {}
    peripherals = peripherals if isinstance(peripherals, dict) else {}
    rows = {"PC候補": [], "自作PC部品": [], "周辺機器": []}

    def cell(value):
        # Keep each source field on one Markdown table row and prevent pipes/newlines
        # in untrusted page titles or errors from corrupting the report layout.
        text = " ".join(str(value or "未確認").split())
        return text.replace("|", "/").replace("[", "（").replace("]", "）")

    def product_url(item, *candidate_urls):
        for candidate in candidate_urls:
            url = sales_url({"url": candidate})
            if url:
                return url
        return None

    for item in latest.get("products") or []:
        if not isinstance(item, dict):
            continue
        problems = []
        fetch_state = str(item.get("fetch_status") or "").strip().lower()
        if fetch_state in ("error", "failed", "failure", "timeout", "exception"):
            problems.append("取得エラー: " + cell(item.get("last_fetch_error") or item.get("fetch_error") or item.get("price_validation_reason")))
        if item.get("variant_match") == "ambiguous" or item.get("price_validation_status") == "variant_ambiguous":
            problems.append("型番/構成不一致。価格は購入判断に不使用")
        if item.get("current_price_jpy") is None:
            problems.append("現行価格未確認 (" + cell(item.get("price_validation_status")) + ")")
        if item.get("stock_status") in (None, "", "unknown"):
            problems.append("在庫未確認")
        elif item.get("stock_status") == "out_of_stock":
            problems.append("在庫切れ信号あり。現在の販売可否を再確認")
        if problems:
            url = product_url(item, item.get("url"), item.get("purchase_url"), item.get("monitor_url"))
            rows["PC候補"].append((item.get("name") or item.get("id"), "; ".join(problems), url, None))

    for item in build_components.get("products") or []:
        if not isinstance(item, dict):
            continue
        offer = item.get("retailer_listing_offer") if isinstance(item.get("retailer_listing_offer"), dict) else {}
        offers = item.get("retailer_listing_offers") if isinstance(item.get("retailer_listing_offers"), list) else []
        direct_sellable = any(
            isinstance(o, dict)
            and isinstance(o.get("price_jpy"), int) and not isinstance(o.get("price_jpy"), bool) and o.get("price_jpy") > 0
            and o.get("identity_match") is True
            and o.get("pit_valid") is True
            and o.get("stock_status") in ("in_stock", "low_stock")
            for o in ([offer] if offer else []) + offers
        )
        errors = []
        fetch_state = str(item.get("fetch_status") or "").strip().lower()
        comparison_state = str(item.get("comparison_fetch_status") or "").strip().lower()
        retailer_state = str(item.get("retailer_search_status") or "").strip().lower()
        failure_states = ("error", "failed", "failure", "timeout", "exception")
        if fetch_state in failure_states:
            errors.append("取得エラー: " + cell(item.get("last_fetch_error") or item.get("fetch_error") or item.get("comparison_fetch_error") or item.get("retailer_search_error")))
        if comparison_state in failure_states or comparison_state == "configuration_error" or item.get("comparison_fetch_error"):
            errors.append("比較ページ取得失敗: " + cell(item.get("comparison_fetch_error")))
        if retailer_state in failure_states or retailer_state == "configuration_error" or item.get("retailer_search_error"):
            errors.append("販売店検索失敗: " + cell(item.get("retailer_search_error")))
        if not direct_sellable:
            errors.append("直接価格・型番・販売可能在庫の同時確認が未完了 (" + cell(item.get("price_validation_status")) + ")")
        if item.get("price_validation_status") == "search_snippet_reference":
            errors.append("検索スニペット参考値のみ。実売価格ではない")
        if item.get("price_validation_status") == "missing":
            errors.append("価格/在庫を確認できず")
        if errors:
            primary_url = product_url(
                item,
                offer.get("url"),
                item.get("retailer_listing_reference_url"),
                item.get("direct_listing_display_url"),
                item.get("purchase_url"),
                item.get("monitor_url"),
            )
            monitor_url = product_url(item, item.get("monitor_url"), item.get("purchase_url"))
            rows["自作PC部品"].append((item.get("name") or item.get("id"), "; ".join(dict.fromkeys(errors)), primary_url, monitor_url))

    for item in peripherals.get("products") or []:
        if not isinstance(item, dict):
            continue
        if item.get("category") in ("budget_reserve", "cables") or item.get("id") in ("store_price_buffer", "cables"):
            continue
        problems = []
        if item.get("error"):
            problems.append("取得エラー: " + cell(item.get("error")))
        if item.get("price_verified") is not True or item.get("current_price_jpy") is None:
            problems.append("価格未確認")
        stock = item.get("stock_status")
        store_stock_confirmed = item.get("store_inventory_verified") is True and item.get("store_inventory_status") in ("in_stock", "low_stock")
        if stock in (None, "", "unknown") and not store_stock_confirmed:
            problems.append("在庫未確認")
        elif stock == "out_of_stock":
            problems.append("在庫切れ信号あり。再確認が必要")
        if item.get("channel_comparison_status") and item.get("channel_comparison_status") not in ("COMPLETE", "ALL_ROUTES_VERIFIED"):
            problems.append("購入ルート比較未完了: " + cell(item.get("channel_comparison_status")))
        if problems:
            primary_url = product_url(item, item.get("purchase_url"), item.get("monitor_url"), item.get("source_url"), item.get("online_best_offer_url"))
            monitor_url = product_url(item, item.get("monitor_url"), item.get("source_url"))
            rows["周辺機器"].append((item.get("name") or item.get("id"), "; ".join(dict.fromkeys(problems)), primary_url, monitor_url))

    lines = [
        "## 取得エラー・価格/在庫未確認商品のリンク",
        "",
        "取得に失敗した商品や、価格・型番・在庫・購入ルートを確認しきれていない商品は、下記リンクから個別に再確認できます。エラーは売り切れを意味しません。リンク先の掲載価格も、最終決済額や購入許可を意味しません。",
        "",
    ]
    labels = [
        ("PC候補", "### 完成品PC・比較候補"),
        ("自作PC部品", "### 自作PCの部品"),
        ("周辺機器", "### 周辺機器"),
    ]
    rendered_any = False
    for key, heading in labels:
        group = rows[key]
        if not group:
            continue
        rendered_any = True
        lines.extend([
            heading,
            "",
            "|商品|問題・確認事項|商品/販売ページ|監視・比較ページ|",
            "|---|---|---|---|",
        ])
        for name, problem, primary_url, monitor_url in group:
            if primary_url:
                safe_target = primary_url.replace("(", "%28").replace(")", "%29")
                primary_link = "[商品ページ]({})".format(safe_target)
            else:
                primary_link = "商品URL未登録（要修正）"
            if monitor_url and monitor_url != primary_url:
                safe_monitor_target = monitor_url.replace("(", "%28").replace(")", "%29")
                monitor_link = "[監視/比較ページ]({})".format(safe_monitor_target)
            else:
                monitor_link = "—"
            lines.append("|{}|{}|{}|{}|".format(cell(name), cell(problem), primary_link, monitor_link))
        lines.append("")
    if not rendered_any:
        lines.extend(["現在、取得エラーまたは価格・在庫未確認の商品はありません。", ""])
    return lines




def _clean_issue_cell(value, limit=180):
    """Keep retrieval diagnostics readable and safe inside a Markdown table."""
    return re.sub(r"\s+", " ", str(value or "")).strip().replace("|", "/")[:limit]


def _first_http_product_url(item, keys):
    item = item if isinstance(item, dict) else {}
    for key in keys:
        value = str(item.get(key) or "").strip()
        url = sales_url({"url": value})
        if url:
            return url
    return None


def retrieval_issue_link_lines(latest=None, component_prices=None, peripheral_prices=None):
    """Render product links whenever retrieval, identity, price, or stock evidence is incomplete."""
    if latest is None:
        latest = load_json(os.path.join(ROOT, "data", "current_latest.json"), {})
    if component_prices is None:
        component_prices = load_json(os.path.join(ROOT, "data", "build_component_prices.json"), {})
    if peripheral_prices is None:
        peripheral_prices = load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {})

    rows = []

    def add_row(group, item, url_keys, status, reason):
        url = _first_http_product_url(item, url_keys)
        name = _clean_issue_cell(item.get("name") or item.get("model") or item.get("id") or "商品名未設定", 150)
        if url:
            link = "[商品ページを開く]({})".format(url.replace("(", "%28").replace(")", "%29"))
        else:
            link = "商品URL未登録（要修正）"
        rows.append((group, name, _clean_issue_cell(status, 70), _clean_issue_cell(reason, 190), link, url or ""))

    def error_text(item, keys):
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    for item in latest.get("products") or []:
        item = item if isinstance(item, dict) else {}
        fetch_status = str(item.get("fetch_status") or "").lower()
        validation = str(item.get("price_validation_status") or "missing").lower()
        price = item.get("current_price_jpy")
        stock = str(item.get("stock_status") or "unknown").lower()
        err = error_text(item, ("last_fetch_error", "fetch_error", "error"))
        failed = fetch_status in ("error", "failed", "timeout", "exception") or (not fetch_status and bool(err))
        unresolved = (
            failed or not isinstance(price, (int, float)) or price <= 0
            or stock not in ("in_stock", "low_stock")
            or validation in ("missing", "variant_ambiguous", "reference_only", "anomaly_rejected")
        )
        if not unresolved:
            continue
        if failed:
            status = "取得エラー"
            reason = err or ("fetch_status=" + fetch_status)
        elif validation == "variant_ambiguous":
            status, reason = "型番/構成不一致の疑い", "価格を購入判断から除外。商品ページで型番・GPU・仕様を確認"
        elif price is None or validation in ("missing", "reference_only", "anomaly_rejected"):
            status, reason = "価格未確認", err or ("price_validation_status=" + validation)
        else:
            status, reason = "在庫未確認", err or ("stock_status=" + stock)
        add_row("完成品PC候補", item, ("url", "purchase_url", "monitor_url"), status, reason)

    for item in component_prices.get("products") or []:
        item = item if isinstance(item, dict) else {}
        fetch_status = str(item.get("fetch_status") or "").lower()
        comparison_status = str(item.get("comparison_fetch_status") or "").lower()
        retailer_status = str(item.get("retailer_search_status") or "").lower()
        validation = str(item.get("price_validation_status") or "missing").lower()
        offer = item.get("retailer_listing_offer") if isinstance(item.get("retailer_listing_offer"), dict) else {}
        offers = item.get("retailer_listing_offers") if isinstance(item.get("retailer_listing_offers"), list) else []
        if not offers and offer:
            offers = [offer]
        sellable_offer = any(
            isinstance(candidate, dict)
            and isinstance(candidate.get("price_jpy"), (int, float))
            and candidate.get("price_jpy") > 0
            and candidate.get("stock_status") in ("in_stock", "low_stock")
            and candidate.get("identity_match") is True
            and candidate.get("pit_valid") is True
            for candidate in offers
        )
        err = error_text(item, ("last_fetch_error", "fetch_error", "comparison_fetch_error", "retailer_search_error"))
        failed = (
            fetch_status in ("error", "failed", "timeout", "exception")
            or comparison_status in ("error", "failed", "timeout", "configuration_error")
            or retailer_status in ("error", "failed", "timeout")
            or bool(item.get("retailer_search_error"))
        )
        unresolved = failed or not sellable_offer or validation in ("missing", "search_snippet_reference", "variant_ambiguous")
        if not unresolved:
            continue
        if failed:
            status = "取得/照合エラー"
            reason = err or "取得または販売店照合の状態がエラー"
        elif validation == "variant_ambiguous":
            status, reason = "型番/構成未確定", "同一型番・構成の直接掲載価格を確認できていない"
        elif validation == "search_snippet_reference":
            status, reason = "検索結果の参考値のみ", err or "検索スニペットは販売可能価格・在庫の根拠にしない"
        elif not sellable_offer:
            status, reason = "販売可能価格/在庫未確認", err or "直接掲載・型番一致・在庫あり/在庫少の条件を満たす掲載がない"
        else:
            status, reason = "価格/型番未確認", err or ("price_validation_status=" + validation)
        add_row("自作PCパーツ", item, (
            "retailer_listing_reference_url", "purchase_url", "monitor_url",
            "search_snippet_reference_url", "source_url"
        ), status, reason)

    for item in peripheral_prices.get("products") or []:
        item = item if isinstance(item, dict) else {}
        url = _first_http_product_url(item, ("purchase_url", "monitor_url", "source_url", "url"))
        # Exclude only non-product placeholders. Real products without a usable URL must
        # remain visible so the report can flag the missing link instead of hiding the item.
        if item.get("category") in ("budget_reserve", "cables") or item.get("id") in ("store_price_buffer", "cables"):
            continue
        status_value = str(item.get("status") or "").lower()
        validation = str(item.get("price_validation_status") or "missing").lower()
        price = item.get("current_price_jpy")
        stock = str(item.get("stock_status") or "unknown").lower()
        err = error_text(item, ("error", "last_fetch_error", "fetch_error"))
        failed = status_value in ("error", "failed", "timeout", "price_unverified") or bool(err)
        verified_offer = (
            isinstance(price, (int, float)) and price > 0
            and item.get("price_verified") is True
            and item.get("identity_verified") is True
            and validation == "validated_exact_model_page"
            and stock in ("in_stock", "low_stock")
        )
        if verified_offer and not failed and url:
            continue
        if not url:
            status = "商品URL未登録"
            reason = (err + "; " if err else "") + "正確な商品ページURLを設定する必要あり"
        elif failed:
            status = "取得/価格解析エラー"
            reason = err or ("status=" + status_value)
        elif validation == "variant_ambiguous":
            status, reason = "型番未確定", "正確な型番のページ/価格を確認できていない"
        elif price is None or not item.get("price_verified"):
            status, reason = "価格未確認", err or ("price_validation_status=" + validation)
        else:
            status, reason = "在庫未確認", err or ("stock_status=" + stock)
        add_row("周辺機器", item, ("purchase_url", "monitor_url", "source_url", "url"), status, reason)

    seen = set()
    unique_rows = []
    for row in rows:
        key = (row[0], row[1], row[5])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    if not unique_rows:
        return []
    lines = [
        "",
        "## 取得エラー・価格/在庫未確認の商品リンク",
        "",
        "ここにあるリンクは、取得に失敗した商品や価格・型番・在庫の確認が完了していない商品の販売/監視ページです。**取得エラーは売り切れを意味しません**。ページがシリーズ共通の場合は、商品名・型番も照合してください。",
        "",
        "|対象|商品|状態|取得エラー/未確認理由|確認用リンク|",
        "|---|---|---|---|---|",
    ]
    for group, name, status, reason, link, _url in unique_rows:
        lines.append("|{}|{}|{}|{}|{}|".format(group, name, status, reason, link))
    lines.extend(["", "未確認項目は在庫切れ・価格ゼロとみなさず、リンク先で直接確認するまで購入可否の根拠にしません。"])
    return lines



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


PERIPHERAL_FIT_SCORE_MAXIMA = {
    "workload_fit_points": 35,
    "budget_fit_points": 30,
    "feature_spec_points": 20,
    "substitution_risk_points": 15,
}


def peripheral_suitability_score(target):
    """Validate the curated product-fit rubric separately from live purchase evidence."""
    target = target if isinstance(target, dict) else {}
    category = str(target.get("category") or "")
    exclusion = target.get("score_exclusion_reason_ja")
    if category == "budget_reserve" or target.get("purchase_channel") == "conditional_need_only" or exclusion:
        return {
            "score": None, "out_of": 100, "breakdown": {},
            "scorecard_complete": False, "status": "NOT_A_PRODUCT",
            "reason_ja": str(exclusion or "商品ではないため用途適合点の対象外"),
            "limitations_ja": "", "missing_or_invalid_fields": [],
        }

    card = target.get("fit_scorecard") if isinstance(target.get("fit_scorecard"), dict) else {}
    points, invalid = {}, []
    for key, maximum in PERIPHERAL_FIT_SCORE_MAXIMA.items():
        value = card.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
            invalid.append(key)
        else:
            points[key] = value
    score = sum(points.values()) if not invalid else None
    registered_score = target.get("ranking_score_100")
    if score is not None and (
        not isinstance(registered_score, int) or isinstance(registered_score, bool)
        or registered_score != score
    ):
        invalid.append("ranking_score_100_mismatch")
        score = None
    reason = str(card.get("rationale_ja") or "")
    limitations = str(card.get("limitations_ja") or "")
    if not reason:
        invalid.append("rationale_ja")
    if not limitations:
        invalid.append("limitations_ja")
    if invalid:
        score = None
    return {
        "score": score,
        "out_of": 100,
        "breakdown": points,
        "scorecard_complete": not invalid,
        "status": "VALID" if not invalid else "UNSCORED_INVALID_RUBRIC",
        "reason_ja": reason,
        "limitations_ja": limitations,
        "missing_or_invalid_fields": list(dict.fromkeys(invalid)),
    }


def peripheral_ranked_candidate_ids(category_ids, target_by_id, category, limit=3):
    """Return purchasable product candidates only, ordered by curated fit score."""
    target_by_id = target_by_id if isinstance(target_by_id, dict) else {}
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 3
    candidates = []
    for candidate_id in dict.fromkeys(category_ids.get(str(category), []) if isinstance(category_ids, dict) else []):
        target = target_by_id.get(str(candidate_id))
        if not isinstance(target, dict):
            continue
        if target.get("category") == "budget_reserve":
            continue
        if target.get("purchase_channel") == "conditional_need_only":
            continue
        if target.get("score_exclusion_reason_ja"):
            continue
        result = peripheral_suitability_score(target)
        score = result.get("score")
        candidates.append((candidate_id, score if isinstance(score, int) else None))
    candidates.sort(key=lambda item: (item[1] is None, -(item[1] if isinstance(item[1], int) else -1), item[0]))
    return [candidate_id for candidate_id, _score in candidates[:limit]]


def peripheral_fit_score_text(target):
    result = peripheral_suitability_score(target)
    if result.get("score") is None:
        return "対象外" if result.get("status") == "NOT_A_PRODUCT" else "未採点（採点表の不足/不一致）"
    p = result["breakdown"]
    return "**{}/100**（用途{}/35・予算{}/30・仕様{}/20・代替性{}/15）".format(
        result["score"], p["workload_fit_points"], p["budget_fit_points"],
        p["feature_spec_points"], p["substitution_risk_points"]
    )


def peripheral_fit_reason_text(target):
    result = peripheral_suitability_score(target)
    if result.get("status") == "NOT_A_PRODUCT":
        return result.get("reason_ja") or "商品ではないため採点対象外"
    if result.get("score") is None:
        return "採点不能: " + ", ".join(result.get("missing_or_invalid_fields") or ["scorecard_invalid"])
    text = "評価理由: " + result["reason_ja"] + " / 留意点: " + result["limitations_ja"]
    return re.sub(r"\s+", " ", text).replace("|", "／").strip()


def peripheral_purchase_evidence_score_text(result):
    """Render purchase-evidence subscores, separately from product suitability."""
    result = result if isinstance(result, dict) else {}
    p = result.get("breakdown") if isinstance(result.get("breakdown"), dict) else {}
    return "**{}/100**（価格/PIT {}・在庫 {}・決済 {}・購入先比較 {}・保証/返品 {}）".format(
        int(result.get("score") or 0),
        int(p.get("direct_price_identity_pit") or 0),
        int(p.get("sellable_stock") or 0),
        int(p.get("verified_checkout_total") or 0),
        int(p.get("route_comparison") or 0),
        int(p.get("warranty_and_returns") or 0),
    )


def peripheral_purchase_evidence_score(target, observation, now=None, max_age_minutes=360, stock_max_age_minutes=30):
    """Score purchase evidence, not product quality; incomplete evidence earns no credit.

    30 direct exact-model price/PIT, 25 fresh sellable stock, 25 verified checkout
    total, 10 completed route comparison, 10 verified warranty/returns terms.
    For online purchases, the checkout subtotal must be an explicit positive final
    total with a true verification flag and a fresh checked-at timestamp; a known
    shipping amount alone is not checkout-total evidence. Store cash quotes and
    store-pickup checkout totals use their own exact-model evidence gates.
    Product suitability is a separate curated score stored in the target config.
    """
    target = target if isinstance(target, dict) else {}
    observation = observation if isinstance(observation, dict) else {}
    now = now or now_jst()

    def as_time(value):
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else None
        except (TypeError, ValueError):
            return None

    def positive_int(value):
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    def nonnegative_int(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    def fresh_timestamp(checked_value, available_value=None, age_limit=max_age_minutes):
        checked = as_time(checked_value)
        available = as_time(available_value) if available_value else checked
        if checked is None or available is None or checked > now or available > checked:
            return False
        age = (now - checked).total_seconds() / 60.0
        return 0 <= age <= max(0, int(age_limit))

    retrieved = as_time(observation.get("retrieval_time"))
    available = as_time(observation.get("available_at"))
    price = observation.get("current_price_jpy")
    direct_price_verified = bool(
        positive_int(price)
        and observation.get("price_verified") is True
        and observation.get("identity_verified") is True
        and observation.get("price_validation_status") == "validated_exact_model_page"
        and observation.get("price_source_mode") in ("direct_text", "direct_structured", "direct_meta")
        and retrieved is not None and available is not None
        and fresh_timestamp(retrieved.isoformat(), available.isoformat(), max_age_minutes)
    )

    points = {
        "direct_price_identity_pit": 30 if direct_price_verified else 0,
        "sellable_stock": 0,
        "verified_checkout_total": 0,
        "route_comparison": 0,
        "warranty_and_returns": 0,
    }

    online_stock = str(
        observation.get("online_best_offer_stock_status")
        or observation.get("stock_status") or "unknown"
    )
    online_stock_fresh = bool(
        observation.get("identity_verified") is True
        and retrieved is not None and available is not None
        and fresh_timestamp(retrieved.isoformat(), available.isoformat(), stock_max_age_minutes)
    )
    stock_score = 0
    online_sellable = online_stock_fresh and online_stock in ("in_stock", "low_stock")
    if online_sellable:
        stock_score = 25 if online_stock == "in_stock" else 18

    # A physical-store cash quote must use stock evidence from that same cash-purchase
    # observation. Web store-pickup availability belongs to a different purchase route.
    store_status = str(observation.get("store_stock_status") or "unknown")
    store_checked = observation.get("store_price_checked_at")
    store_stock_fresh = bool(
        observation.get("store_price_confirmed") is True
        and observation.get("store_model_match") is True
        and observation.get("store_observation_store_id")
        and fresh_timestamp(store_checked, None, stock_max_age_minutes)
    )
    if store_stock_fresh and store_status in ("in_stock", "low_stock"):
        stock_score = max(stock_score, 25 if store_status == "in_stock" else 18)
    points["sellable_stock"] = stock_score

    online_shipping = observation.get("online_shipping_jpy")
    online_total = observation.get("online_checkout_total_jpy")
    online_total_checked = observation.get("online_checkout_total_checked_at")
    online_checkout = bool(
        direct_price_verified and online_sellable
        and observation.get("online_shipping_cost_verified") is True
        and nonnegative_int(online_shipping)
        and observation.get("online_checkout_total_verified") is True
        and positive_int(online_total)
        and fresh_timestamp(online_total_checked, None, max_age_minutes)
    )
    store_checkout = bool(
        observation.get("store_price_confirmed") is True
        and positive_int(observation.get("store_price_jpy"))
        and observation.get("store_model_match") is True
        and observation.get("store_observation_store_id")
        and store_stock_fresh and store_status in ("in_stock", "low_stock")
        and fresh_timestamp(observation.get("store_price_checked_at"), None, max_age_minutes)
    )
    pickup_total = observation.get("store_pickup_checkout_total_jpy")
    pickup_stock = str(observation.get("store_pickup_quote_stock_status") or observation.get("store_pickup_branch_inventory_status") or "unknown")
    pickup_checkout = bool(
        (observation.get("store_pickup_checkout_total_confirmed") is True
         or observation.get("store_pickup_checkout_total_verified") is True)
        and positive_int(pickup_total)
        and pickup_stock in ("in_stock", "low_stock")
        and fresh_timestamp(observation.get("store_pickup_quote_checked_at"), None, max_age_minutes)
    )
    checkout_verified = online_checkout or store_checkout or pickup_checkout
    points["verified_checkout_total"] = 25 if checkout_verified else 0

    channel = str(target.get("purchase_channel") or observation.get("purchase_channel") or "online")
    channel_complete = (
        observation.get("channel_comparison_complete") is True
        or observation.get("channel_comparison_status") in ("CHANNEL_COMPARISON_COMPLETE", "ALL_PURCHASE_ROUTES_VERIFIED")
    )
    if channel == "compare_online_and_store":
        route_ready = channel_complete and (direct_price_verified or store_checkout or pickup_checkout)
    elif channel == "physical_store":
        route_ready = store_checkout
    elif channel == "conditional_need_only":
        # This category is deliberately not promoted until the item is required.
        route_ready = False
    else:
        route_ready = online_checkout
    points["route_comparison"] = 10 if route_ready else 0

    terms_verified = bool(
        observation.get("warranty_return_conditions_verified") is True
        or (
            observation.get("warranty_verified") is True
            and observation.get("return_policy_verified") is True
        )
    )
    points["warranty_and_returns"] = 10 if terms_verified else 0
    return {
        "score": sum(points.values()),
        "out_of": 100,
        "breakdown": points,
        "direct_price_verified_fresh": direct_price_verified,
        "sellable_stock_verified_fresh": bool(stock_score),
        "checkout_total_verified": checkout_verified,
        "purchase_route_ready": route_ready,
        "warranty_return_terms_verified": terms_verified,
        "maximum_price_age_minutes": int(max_age_minutes),
        "maximum_stock_age_minutes": int(stock_max_age_minutes),
    }


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


def positive_jpy_amount(value):
    """Validate a positive integer yen amount, excluding booleans."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def physical_store_cash_price_labels(item):
    """Format each independently verified branch cash quote without mixing routes."""
    item = item if isinstance(item, dict) else {}
    quotes = [
        quote for quote in (item.get("store_price_observations") or [])
        if isinstance(quote, dict)
        and quote.get("store_price_confirmed") is True
        and quote.get("store_model_match") is True
        and positive_jpy_amount(quote.get("store_price_jpy"))
    ]
    # Backward compatibility for older snapshots that only contain a single
    # verified branch-price summary row.
    if not quotes and item.get("store_price_confirmed") is True \
        and item.get("store_model_match") is True \
        and positive_jpy_amount(item.get("store_price_jpy")):
        quotes = [{
            "store_name": item.get("store_observation_store_name"),
            "store_observation_store_id": item.get("store_observation_store_id"),
            "store_price_jpy": item.get("store_price_jpy"),
            "store_stock_status": item.get("store_stock_status") or "unknown",
            "store_price_checked_at": item.get("store_price_checked_at"),
            "store_observation_age_minutes": item.get("store_observation_age_minutes"),
        }]
    labels = []
    for quote in quotes:
        store_name = str(
            quote.get("store_name")
            or quote.get("store_observation_store_id")
            or "対象店"
        )
        price = int(quote["store_price_jpy"])
        stock = str(quote.get("store_stock_status") or "unknown")
        checked_at = str(quote.get("store_price_checked_at") or "").strip()
        checked_label = (
            "・確認 " + checked_at[:16].replace("T", " ") + " JST"
            if len(checked_at) >= 16 and checked_at[10:11] == "T" else
            "・確認時刻未記録"
        )
        age = quote.get("store_observation_age_minutes")
        age_label = (
            "（{:.0f}分前）".format(max(0, age))
            if isinstance(age, (int, float)) and not isinstance(age, bool) else ""
        )
        labels.append(
            f"{store_name} 店頭現金 ¥{price:,}・在庫 {stock}{checked_label}{age_label}"
        )
    return labels


def peripheral_route_price_summary(item):
    """Separate online listing, shipping, store cash quote and route completeness."""
    item = item if isinstance(item, dict) else {}
    channel = str(item.get("purchase_channel") or "online")
    price = item.get("online_comparison_price_jpy")
    shipping = item.get("online_shipping_jpy")
    reserve = item.get("online_shipping_reserve_jpy")
    online_total = item.get("estimated_online_cash_total_jpy")
    store_price_labels = physical_store_cash_price_labels(item)
    pickup_price = item.get("store_pickup_checkout_total_jpy") if item.get("store_pickup_checkout_total_confirmed") else None
    pickup_branch_status = item.get("store_pickup_branch_inventory_status") or "unknown"
    pickup_quote_status = item.get("store_pickup_quote_status") or "UNCONFIRMED"
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
    if store_price_labels:
        parts.append("支店別価格: " + " / ".join(store_price_labels))
    elif channel in ("compare_online_and_store", "physical_store") or "physical_store" in (item.get("purchase_channel_options") or []):
        parts.append("店頭現金価格未確認")
    if isinstance(pickup_price, int) and not isinstance(pickup_price, bool):
        parts.append(f"店舗受け取り決済額 ¥{pickup_price:,}・受取在庫 {item.get('store_pickup_quote_stock_status') or 'unknown'}")
    elif "store_pickup" in (item.get("purchase_channel_options") or []):
        parts.append(f"店舗受け取り: 決済額未確認・支店在庫 {pickup_branch_status}・{pickup_quote_status}")
    route_status = item.get("channel_comparison_status")
    if route_status:
        parts.append(f"比較状態 {route_status}")
    return " / ".join(parts)


def inventory_status_label(item):
    item = item if isinstance(item, dict) else {}
    stock_labels = {
        "in_stock": "在庫あり（確認時点）",
        "low_stock": "在庫少（確認時点）",
        "out_of_stock": "在庫なし（確認時点）",
        "preorder_or_backorder": "取寄せ表示（即時在庫ではない）",
        "unknown": "在庫不明（確認時点）",
    }
    # Prefer the same-branch cash-price observation, if present.
    if item.get("store_price_confirmed") is True and item.get("store_observation_store_id"):
        status = str(item.get("store_stock_status") or "unknown")
        store_name = (
            item.get("store_observation_store_name")
            or item.get("store_observation_store_id")
            or "対象店"
        )
        label = stock_labels.get(status, "在庫不明")
        return f"{store_name}: 店頭現金購入 {label}"

    # Online pickup/hold inventory is useful, but must be shown as a separate route
    # and never used as evidence that a shelf-price quote is available for cash purchase.
    branch_rows = [
        row for row in (item.get("store_inventory_observations") or [])
        if isinstance(row, dict) and row.get("store_id")
    ]
    branch_labels = []
    for row in branch_rows:
        name = str(row.get("store_name") or row.get("store_id") or "支店")
        status = stock_labels.get(str(row.get("status") or "unknown"), "在庫不明")
        checked = str(row.get("checked_at") or "").strip()
        checked_label = (
            "・確認 " + checked[:16].replace("T", " ") + " JST"
            if len(checked) >= 16 and checked[10:11] == "T" else ""
        )
        branch_labels.append(f"{name}: Web取置き/店舗受取 {status}{checked_label}")
    if branch_labels:
        return " / ".join(branch_labels)

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
    peripheral_channel_comparison_pending_count=0,
):
    """Explain the completed-PC shortlist gate without conflating it with DIY authorization."""
    if self_build_primary:
        return "completed_pc_candidates_reference_only"
    if critical_unverified:
        return "critical_candidates_not_fully_verified"
    if not peripheral_budget_ready:
        return "peripheral_prices_or_availability_unverified"
    if int(peripheral_channel_comparison_pending_count or 0) > 0:
        return "peripheral_purchase_channel_comparison_incomplete"
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
        and peripheral_projection.get("channel_comparison_pending_count", 0) == 0
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
        f"PC本体の基準目標: ¥{budget['pc_target_jpy']:,}",
        f"PC本体の絶対上限（周辺機器費用を加算する前の単体上限。総額上限ではない）: ¥{budget['pc_budget_jpy']:,}",
        f"PC本体の動的上限（周辺機器の実費試算と総額予備費を控除後）: ¥{peripheral_projection['pc_dynamic_cap_jpy']:,}",
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
        "## 前倒し購入の再検討シグナル",
        "",
        "ブラックフライデーを基本に待ちます。前倒し価格は購入許可ではなく、同一型番の直接価格・在庫・取得時刻が検証された場合に再確認を始める目安です。",
        "",
        "|商品|前倒し価格|観測価格・決済総額の確認状況|判定|次の確認|",
        "|---|---:|---:|---|---|",
        *[
            "|{}|{}|{}|{}|{}|".format(
                str(p.get("name") or p.get("id") or "不明").replace("|", "/"),
                ("¥{:,}".format((p.get("early_buy_review") or {}).get("early_buy_threshold_jpy"))
                 if isinstance((p.get("early_buy_review") or {}).get("early_buy_threshold_jpy"), int) else "—"),
                early_buy_amount_label(p.get("early_buy_review")),
                str((p.get("early_buy_review") or {}).get("label_ja") or "未判定").replace("|", "/"),
                str((p.get("early_buy_review") or {}).get("next_step") or "価格・在庫を確認").replace("|", "/"),
            )
            for p in peripheral_projection["peripherals"]
            if isinstance((p.get("early_buy_review") or {}).get("early_buy_threshold_jpy"), int)
        ],
        "",
        "このシグナルは購入許可ではありません。送料・保証/返品・互換性・PC全体40万円上限を注文前に再確認します。",
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
        "各カテゴリから**1商品だけ**選びます。代替候補は価格監視対象ですが、選択しない限り必須周辺機器の総予算には加算しません。付属ケーブル不足時だけ検討する条件付き購入ルールと、商品ではない予備費は製品ランキングから除外します。",
        "用途適合点/100は4軸の明示的な事前ルーブリックです（用途35、予算30、仕様・機能20、代替性・購入リスク15）。製品ごとに内訳、評価理由、留意点を表示します。ライブ価格・在庫を自動的に織り込む点数ではなく、実測ベンチマークでもありません。",
        "購入根拠点/100は最新の観測から動的に計算します（直接価格・型番・時刻/PIT 30、販売可能在庫25、決済総額25、購入ルート確認10、保証/返品条件確認10）。内訳も行ごとに表示します。オンライン購入の決済点には送料額だけでなく、最終決済総額・確認フラグ・確認時刻が必要です。未確認・古い観測は加点しません。BF購入目標・BF前の観測価格・在庫・送料込み決済額を分け、取得失敗は売り切れと見なしません。",
        "購入ルート：PC本体（自作パーツ）はネット注文。周辺機器は福岡の指定実店舗での現金購入を既定ルートとし、同一型番・色の店頭現金価格と同一支店在庫を別々に確認します。ネット価格（送料・必須費用込み）と店舗受け取り決済は比較参考/例外ルートです。店頭証拠が未確認なら購入先を確定せず、ユーザーの明示承認なくオンラインへ自動切替しません。ポイント・保証・返品条件も別々に記録します。電源タップは所有済み、スピーカー・サブモニター・ヘッドセットは購入対象外です。",
        "",
    ]
    for group in category_order:
        category = str(group.get("category") or "")
        group_name = str(group.get("label") or category)
        candidate_ids = peripheral_ranked_candidate_ids(
            category_ids, all_peripheral_targets, category, limit=3
        )
        if not candidate_ids:
            continue
        peripheral_category_lines += [
            f"### {group_name}",
            "",
            "|順位|用途適合点/100（内訳）|購入根拠点/100（内訳）|画像|商品|購入方法|BF購入目標|観測価格（BF前は参考）|在庫（購入先）|価格確認|適合評価の理由・留意点|商品ページ|",
            "|---:|---:|---:|---|---|---|---:|---:|---|---|---|---|",
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
                pickup_price = observation.get("store_pickup_checkout_total_jpy") if observation.get("store_pickup_checkout_total_confirmed") else None
                pickup_stock = observation.get("store_pickup_quote_stock_status") or "unknown"
                pickup_branch_status = observation.get("store_pickup_branch_inventory_status") or "unknown"
                pickup_quote_status = observation.get("store_pickup_quote_status") or "UNCONFIRMED"
                price_parts = []
                if online_price is not None:
                    online_part = f"ネット掲載 ¥{online_price:,}"
                    reserve = int(target.get("online_shipping_reserve_jpy") or 0)
                    if reserve and not observation.get("online_shipping_cost_verified"):
                        online_part += f"（送料未確認・予備枠¥{reserve:,}）"
                    price_parts.append(online_part)
                else:
                    price_parts.append("ネット価格未確認")
                store_price_labels = physical_store_cash_price_labels(observation)
                if store_price_labels:
                    price_parts.append("支店別店頭現金: " + " / ".join(store_price_labels))
                else:
                    price_parts.append("店頭現金価格未確認")
                if isinstance(pickup_price, int) and not isinstance(pickup_price, bool):
                    price_parts.append(f"店舗受け取り決済 ¥{pickup_price:,}")
                else:
                    price_parts.append(f"店舗受け取り決済額未確認（支店在庫:{pickup_branch_status}）")
                price_text = " / ".join(price_parts)
                online_stock = str(observation.get("stock_status") or "unknown")
                store_stock = inventory_status_label(observation)
                stock_text = f"ネット:{online_stock} / 店頭:{store_stock} / 店舗受け取り:{pickup_stock if isinstance(pickup_price, int) else pickup_branch_status}"
                verified_text = (
                    "ネット配送・店頭現金・店舗受け取りの全ルートを確認済み"
                    if observation.get("channel_comparison_complete")
                    else "購入先比較未完了（ネット価格・店頭見積・店舗受取決済を分離）"
                    if online_price is not None or isinstance(store_price, int) or isinstance(pickup_price, int)
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
            score_text = peripheral_fit_score_text(target)
            max_price_age = int(target_config.get("peripheral_price_max_age_minutes", 360))
            max_stock_age = int(target_config.get("peripheral_stock_max_age_minutes", 30))
            evidence = peripheral_purchase_evidence_score(
                target, observation, now=now_jst(),
                max_age_minutes=max_price_age, stock_max_age_minutes=max_stock_age,
            )
            evidence_text = peripheral_purchase_evidence_score_text(evidence)
            reason = peripheral_fit_reason_text(target)
            peripheral_category_lines.append(
                f"|{rank}|{score_text}|{evidence_text}|{image_html}|{target.get('name', candidate_id)}{suffix}|{purchase_method_text}|¥{target_price:,}|{price_text}|{stock_text}|{verified_text}|{reason}|{product_link}|"
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
        *retrieval_issue_link_section(
            latest,
            load_json(os.path.join(ROOT, "data", "build_component_prices.json"), {"products": []}),
            load_json(os.path.join(ROOT, "data", "peripheral_prices.json"), {"products": []}),
        ),
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
