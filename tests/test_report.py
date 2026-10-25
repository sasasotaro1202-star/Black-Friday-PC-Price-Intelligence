import importlib.util
import json
import pathlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report", ROOT / "scripts" / "report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportLinkTests(unittest.TestCase):
    def test_peripheral_purchase_evidence_score_rewards_only_fresh_complete_evidence(self):
        now = datetime(2026, 10, 17, 20, 0, tzinfo=timezone(timedelta(hours=9)))
        stamp = now.isoformat()
        target = {"purchase_channel": "compare_online_and_store"}
        observation = {
            "current_price_jpy": 20000,
            "price_verified": True,
            "identity_verified": True,
            "price_validation_status": "validated_exact_model_page",
            "price_source_mode": "direct_text",
            "retrieval_time": stamp,
            "available_at": stamp,
            "stock_status": "in_stock",
            "online_best_offer_stock_status": "in_stock",
            "online_shipping_cost_verified": True,
            "online_shipping_jpy": 0,
            "online_checkout_total_jpy": 20000,
            "online_checkout_total_verified": True,
            "online_checkout_total_checked_at": stamp,
            "channel_comparison_complete": True,
            "warranty_return_conditions_verified": True,
        }
        result = report.peripheral_purchase_evidence_score(target, observation, now=now)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["breakdown"], {
            "direct_price_identity_pit": 30,
            "sellable_stock": 25,
            "verified_checkout_total": 25,
            "route_comparison": 10,
            "warranty_and_returns": 10,
        })
        self.assertTrue(result["direct_price_verified_fresh"])
        self.assertTrue(result["sellable_stock_verified_fresh"])
        self.assertTrue(result["checkout_total_verified"])

    def test_peripheral_purchase_evidence_score_fails_closed_on_stale_or_ambiguous_data(self):
        now = datetime(2026, 10, 17, 20, 0, tzinfo=timezone(timedelta(hours=9)))
        old_stamp = (now - timedelta(hours=8)).isoformat()
        result = report.peripheral_purchase_evidence_score(
            {"purchase_channel": "compare_online_and_store"},
            {
                "current_price_jpy": 20000,
                "price_verified": True,
                "identity_verified": True,
                "price_validation_status": "validated_exact_model_page",
                "price_source_mode": "direct_text",
                "retrieval_time": old_stamp,
                "available_at": old_stamp,
                "stock_status": "in_stock",
                "online_best_offer_stock_status": "in_stock",
                "online_shipping_cost_verified": True,
                "online_shipping_jpy": 0,
                "channel_comparison_complete": True,
            },
            now=now,
        )
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["direct_price_verified_fresh"])
        self.assertFalse(result["sellable_stock_verified_fresh"])
        self.assertFalse(result["checkout_total_verified"])

        unknown = report.peripheral_purchase_evidence_score(
            {"purchase_channel": "online"},
            {
                "current_price_jpy": 20000,
                "price_verified": False,
                "identity_verified": False,
                "price_validation_status": "missing",
                "price_source_mode": "none",
                "retrieval_time": now.isoformat(),
                "available_at": None,
                "stock_status": "unknown",
            },
            now=now,
        )
        self.assertEqual(unknown["score"], 0)
        self.assertFalse(unknown["direct_price_verified_fresh"])
        self.assertFalse(unknown["sellable_stock_verified_fresh"])

    def test_peripheral_purchase_evidence_requires_verified_final_online_total(self):
        now = datetime(2026, 10, 17, 20, 0, tzinfo=timezone(timedelta(hours=9)))
        stamp = now.isoformat()
        target = {"purchase_channel": "compare_online_and_store"}
        observation = {
            "current_price_jpy": 20000,
            "price_verified": True, "identity_verified": True,
            "price_validation_status": "validated_exact_model_page",
            "price_source_mode": "direct_text",
            "retrieval_time": stamp, "available_at": stamp,
            "stock_status": "in_stock", "online_best_offer_stock_status": "in_stock",
            "online_shipping_cost_verified": True, "online_shipping_jpy": 0,
            "channel_comparison_complete": True,
        }
        result = report.peripheral_purchase_evidence_score(target, observation, now=now)
        self.assertEqual(result["breakdown"]["direct_price_identity_pit"], 30)
        self.assertEqual(result["breakdown"]["sellable_stock"], 25)
        self.assertEqual(result["breakdown"]["verified_checkout_total"], 0)
        observation.update({
            "online_checkout_total_jpy": 20000,
            "online_checkout_total_verified": True,
            "online_checkout_total_checked_at": stamp,
        })
        verified = report.peripheral_purchase_evidence_score(target, observation, now=now)
        self.assertEqual(verified["breakdown"]["verified_checkout_total"], 25)

    def test_peripheral_suitability_scorecards_match_all_product_targets_and_fail_closed(self):
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        entries = list(config.get("peripherals") or []) + list(config.get("peripheral_alternatives") or [])
        limits = {
            "workload_fit_points": 35,
            "budget_fit_points": 30,
            "feature_spec_points": 20,
            "substitution_risk_points": 15,
        }
        product_count = 0
        for target in entries:
            result = report.peripheral_suitability_score(target)
            if target.get("category") == "budget_reserve" or target.get("purchase_channel") == "conditional_need_only":
                self.assertIsNone(result["score"], target.get("id"))
                self.assertEqual(result["status"], "NOT_A_PRODUCT")
                continue
            product_count += 1
            self.assertTrue(result["scorecard_complete"], (target.get("id"), result["missing_or_invalid_fields"]))
            self.assertEqual(result["score"], target.get("ranking_score_100"), target.get("id"))
            self.assertEqual(sum(result["breakdown"].values()), result["score"], target.get("id"))
            for key, maximum in limits.items():
                self.assertGreaterEqual(result["breakdown"][key], 0, target.get("id"))
                self.assertLessEqual(result["breakdown"][key], maximum, target.get("id"))
            self.assertTrue(result["reason_ja"], target.get("id"))
            self.assertTrue(result["limitations_ja"], target.get("id"))
        self.assertEqual(product_count, 14)

        invalid = report.peripheral_suitability_score({
            "category": "mouse",
            "ranking_score_100": 90,
            "fit_scorecard": {
                "workload_fit_points": 34,
                "budget_fit_points": 29,
                "feature_spec_points": 20,
                "substitution_risk_points": 15,
                "rationale_ja": "reason",
                "limitations_ja": "limitation",
            },
        })
        self.assertIsNone(invalid["score"])
        self.assertFalse(invalid["scorecard_complete"])
        self.assertIn("ranking_score_100_mismatch", invalid["missing_or_invalid_fields"])

    def test_peripheral_rankings_exclude_conditional_cable_rule_and_budget_reserve(self):
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        entries = list(config.get("peripherals") or []) + list(config.get("peripheral_alternatives") or [])
        target_by_id = {str(x["id"]): x for x in entries}
        category_ids = {}
        for target in entries:
            category_ids.setdefault(str(target.get("category") or ""), []).append(str(target["id"]))
        cable_ids = report.peripheral_ranked_candidate_ids(category_ids, target_by_id, "cables", limit=3)
        self.assertEqual(len(cable_ids), 2)
        self.assertNotIn("cables", cable_ids)
        self.assertTrue(all(target_by_id[candidate_id].get("fit_scorecard") for candidate_id in cable_ids))
        mouse_ids = report.peripheral_ranked_candidate_ids(category_ids, target_by_id, "mouse", limit=3)
        self.assertEqual(mouse_ids[0], "mouse")
        self.assertIn("mouse_alt_logicool_g203", mouse_ids)
        self.assertEqual(
            report.peripheral_ranked_candidate_ids(category_ids, target_by_id, "budget_reserve", limit=3),
            [],
        )

    def test_peripheral_score_renderers_show_component_breakdown_and_limitations(self):
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = next(x for x in config["peripherals"] if x["id"] == "main_monitor")
        score = report.peripheral_suitability_score(target)
        self.assertEqual(score["score"], 94)
        fit_text = report.peripheral_fit_score_text(target)
        self.assertIn("**94/100**（用途34/35・予算28/30・仕様19/20・代替性13/15）", fit_text)
        reason = report.peripheral_fit_reason_text(target)
        self.assertIn("評価理由:", reason)
        self.assertIn("留意点:", reason)

        normalized_reason = report.peripheral_fit_reason_text({
            "category": "main_monitor",
            "ranking_score_100": 94,
            "fit_scorecard": {
                "workload_fit_points": 34,
                "budget_fit_points": 28,
                "feature_spec_points": 19,
                "substitution_risk_points": 13,
                "rationale_ja": "用途  と\tても | 理由",
                "limitations_ja": "留意点   あり",
            },
        })
        self.assertEqual(normalized_reason, "評価理由: 用途 と ても ／ 理由 / 留意点: 留意点 あり")
        self.assertNotIn("\t", normalized_reason)
        self.assertNotIn("  ", normalized_reason)
        evidence = {
            "score": 55,
            "breakdown": {
                "direct_price_identity_pit": 30,
                "sellable_stock": 25,
                "verified_checkout_total": 0,
                "route_comparison": 0,
                "warranty_and_returns": 0,
            },
        }
        evidence_text = report.peripheral_purchase_evidence_score_text(evidence)
        self.assertIn("**55/100**", evidence_text)
        self.assertIn("決済 0", evidence_text)
        self.assertEqual(report.peripheral_fit_score_text({"category":"budget_reserve"}), "対象外")

    def test_early_buy_amount_label_separates_listing_estimate_and_verified_checkout(self):
        estimated = {
            "observed_price_jpy": 20790,
            "estimated_checkout_total_jpy": 21790,
            "verified_checkout_total_jpy": None,
            "checkout_total_verified": False,
        }
        self.assertEqual(
            report.early_buy_amount_label(estimated),
            "掲載 ¥20,790 / 送料込概算 ¥21,790（決済未確認）",
        )
        verified = {
            "observed_price_jpy": 20790,
            "estimated_checkout_total_jpy": 21790,
            "verified_checkout_total_jpy": 21790,
            "checkout_total_verified": True,
        }
        self.assertEqual(report.early_buy_amount_label(verified), "決済総額確認済み ¥21,790")
        listing_only = {"observed_price_jpy": 20790}
        self.assertEqual(report.early_buy_amount_label(listing_only), "掲載 ¥20,790（決済未確認）")
        self.assertEqual(report.early_buy_amount_label({}), "未確認")

    def test_self_build_policy_ignores_assembly_time_and_keeps_bto_reference_only(self):
        policy = report.build_purchase_method_policy({
            "pc_build_method_preference": "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 30,
            "bto_role": "REFERENCE_BENCHMARK_ONLY",
            "selection_policy": "self-build first",
        })
        self.assertEqual(policy["primary_method"], "SELF_BUILD")
        self.assertFalse(policy["assembly_time_is_constraint"])
        self.assertEqual(policy["assembly_time_penalty_points"], 0)
        self.assertEqual(policy["bto_role"], "REFERENCE_BENCHMARK_ONLY")
        self.assertFalse(policy["completed_pc_purchase_actionable"])

    def test_completed_pc_gate_reason_is_scoped_away_from_diy(self):
        self_build_reason = report.purchase_gate_reason(
            self_build_primary=True,
            critical_unverified=[],
            peripheral_budget_ready=False,
            action=None,
            dynamic_pc_cap_jpy=0,
            purchase_gate_allowed=False,
        )
        self.assertEqual(self_build_reason, "completed_pc_candidates_reference_only")

    def test_completed_pc_gate_reports_actual_blocker_when_bto_is_in_scope(self):
        self.assertEqual(
            report.purchase_gate_reason(
                self_build_primary=False,
                critical_unverified=["gpu"],
                peripheral_budget_ready=False,
                action=None,
                dynamic_pc_cap_jpy=0,
                purchase_gate_allowed=False,
            ),
            "critical_candidates_not_fully_verified",
        )
        self.assertEqual(
            report.purchase_gate_reason(
                self_build_primary=False,
                critical_unverified=[],
                peripheral_budget_ready=False,
                action=None,
                dynamic_pc_cap_jpy=0,
                purchase_gate_allowed=False,
            ),
            "peripheral_prices_or_availability_unverified",
        )


    def test_completed_pc_gate_blocks_cheapest_channel_claim_until_routes_compared(self):
        reason = report.purchase_gate_reason(
            self_build_primary=False,
            critical_unverified=[],
            peripheral_budget_ready=True,
            action=None,
            dynamic_pc_cap_jpy=360000,
            purchase_gate_allowed=False,
            peripheral_channel_comparison_pending_count=4,
        )
        self.assertEqual(reason, "peripheral_purchase_channel_comparison_incomplete")


    def test_retrieval_issue_links_include_failed_pc_component_and_peripheral_pages(self):
        lines = report.retrieval_issue_link_lines(
            {
                "products": [{
                    "id": "pc-test", "name": "ASUS Test PC",
                    "url": "https://example.com/asus-test",
                    "fetch_status": "error", "last_fetch_error": "RuntimeError:curl_http_403",
                    "current_price_jpy": None, "stock_status": "unknown",
                }]
            },
            {
                "products": [{
                    "id": "gpu-test", "name": "Test GPU",
                    "purchase_url": "https://example.com/test-gpu",
                    "fetch_status": "error", "last_fetch_error": "timeout",
                    "price_validation_status": "missing",
                }]
            },
            {
                "products": [{
                    "id": "pad-test", "name": "Test Mousepad",
                    "purchase_url": "https://example.com/test-pad",
                    "status": "error", "error": "curl timeout",
                    "current_price_jpy": None, "stock_status": "unknown",
                }]
            },
        )
        text = "\n".join(lines)
        self.assertIn("[商品ページを開く](https://example.com/asus-test)", text)
        self.assertIn("[商品ページを開く](https://example.com/test-gpu)", text)
        self.assertIn("[商品ページを開く](https://example.com/test-pad)", text)
        self.assertIn("RuntimeError:curl_http_403", text)
        self.assertIn("取得エラーは売り切れを意味しません", text)

    def test_retrieval_issue_links_never_render_non_http_product_urls(self):
        lines = report.retrieval_issue_link_lines(
            {"products": [{
                "id": "bad-url", "name": "Bad URL PC",
                "url": "javascript:alert(1)", "fetch_status": "error",
                "last_fetch_error": "fetch failed", "current_price_jpy": None,
            }]},
            {"products": []},
            {"products": []},
        )
        text = "\n".join(lines)
        self.assertNotIn("](javascript:alert(1))", text)
        self.assertIn("商品URL未登録（要修正）", text)

    def test_retrieval_issue_links_encode_parentheses_in_product_urls(self):
        lines = report.retrieval_issue_link_lines(
            {"products": [{
                "id": "pc-parentheses-helper",
                "name": "Tracked PC",
                "url": "https://example.com/product(edition)",
                "fetch_status": "error",
                "last_fetch_error": "timeout",
                "current_price_jpy": None,
                "stock_status": "unknown",
            }]},
            {"products": []},
            {"products": []},
        )
        rendered = chr(10).join(lines)
        self.assertIn("[商品ページを開く](https://example.com/product%28edition%29)", rendered)

    def test_retrieval_issue_links_keep_real_peripherals_with_missing_urls_visible(self):
        lines = report.retrieval_issue_link_lines(
            {"products": []},
            {"products": []},
            {"products": [{
                "id": "monitor-missing-url",
                "name": "Tracked monitor missing source URL",
                "status": "error",
                "error": "timeout while fetching",
                "current_price_jpy": None,
                "stock_status": "unknown",
                "purchase_url": None,
                "monitor_url": None,
                "source_url": None,
            }]},
        )
        text = "\n".join(lines)
        self.assertIn("Tracked monitor missing source URL", text)
        self.assertIn("商品URL未登録（要修正）", text)
        self.assertIn("商品URL未登録", text)
        self.assertIn("timeout while fetching", text)
        self.assertNotIn("https://", text)

    def test_main_ranking_link_section_surfaces_peripheral_fetch_failure_with_cached_price(self):
        lines = report.retrieval_issue_link_section(
            {"products": []},
            {"products": []},
            {"products": [{
                "id": "mousepad-fetch-failed-cached-price",
                "name": "SteelSeries QcK Large",
                "purchase_url": "https://example.com/qck-large",
                "direct_listing_display_url": "https://example.com/qck-listing",
                "fetch_status": "error",
                "last_fetch_error": "HTTP 503",
                # A prior observation must not hide the latest failed retrieval.
                "price_verified": True,
                "current_price_jpy": 1490,
                "stock_status": "in_stock",
                "channel_comparison_status": "COMPLETE",
            }]},
        )
        rendered = "\\n".join(lines)
        self.assertIn("SteelSeries QcK Large", rendered)
        self.assertIn("取得エラー: HTTP 503", rendered)
        self.assertIn("[商品ページ](https://example.com/qck-large)", rendered)
        self.assertIn("[監視/比較ページ](https://example.com/qck-listing)", rendered)

    def test_main_ranking_link_section_marks_missing_or_malformed_product_urls(self):
        lines = report.retrieval_issue_link_section(
            {
                "products": [{
                    "id": "pc-no-valid-url",
                    "name": "Tracked GPU | model" + chr(10) + "revision",
                    "url": "https://",
                    "fetch_status": "error",
                    "last_fetch_error": "timeout | parse" + chr(10) + "failed",
                    "current_price_jpy": None,
                    "price_validation_status": "missing",
                    "stock_status": "unknown",
                }]
            },
            {"products": []},
            {"products": [{
                "id": "peripheral-no-url",
                "name": "Tracked keyboard",
                "purchase_url": "javascript:alert(1)",
                "monitor_url": "file:///etc/passwd",
                "status": "error",
                "error": "page" + chr(10) + "fetch failed",
                "current_price_jpy": None,
                "price_verified": False,
                "stock_status": "unknown",
            }]},
        )
        rendered = chr(10).join(lines)
        self.assertIn("Tracked GPU / model revision", rendered)
        self.assertIn("timeout / parse failed", rendered)
        self.assertIn("Tracked keyboard", rendered)
        self.assertGreaterEqual(rendered.count("商品URL未登録（要修正）"), 2)
        self.assertNotIn("javascript:alert(1)", rendered)
        self.assertNotIn("file:///etc/passwd", rendered)

    def test_main_ranking_link_section_encodes_parentheses_in_markdown_targets(self):
        lines = report.retrieval_issue_link_section(
            {"products": [{
                "id": "pc-parentheses",
                "name": "Tracked PC",
                "url": "https://example.com/product(edition)",
                "fetch_status": "error",
                "last_fetch_error": "timeout",
                "current_price_jpy": None,
                "stock_status": "unknown",
            }]},
            {"products": []},
            {"products": []},
        )
        rendered = chr(10).join(lines)
        self.assertIn("[商品ページ](https://example.com/product%28edition%29)", rendered)

    def test_main_ranking_link_section_surfaces_normalized_failure_states(self):
        lines = report.retrieval_issue_link_section(
            {"products": [{
                "id": "pc-failed-status",
                "name": "Tracked laptop with failed fetch status",
                "url": "https://example.com/tracked-laptop",
                "fetch_status": "failed",
                "last_fetch_error": "HTTP 503",
                "current_price_jpy": None,
                "stock_status": "unknown",
            }]},
            {"products": [{
                "id": "component-timeout-status",
                "name": "Tracked GPU with timeout status",
                "fetch_status": "timeout",
                "last_fetch_error": "socket timeout",
                "purchase_url": "https://example.com/tracked-gpu",
                "monitor_url": "https://compare.example.com/tracked-gpu",
                "price_validation_status": "missing",
            }]},
            {"products": []},
        )
        rendered = chr(10).join(lines)
        self.assertIn("取得エラー: HTTP 503", rendered)
        self.assertIn("[商品ページ](https://example.com/tracked-laptop)", rendered)
        self.assertIn("取得エラー: socket timeout", rendered)
        self.assertIn("[商品ページ](https://example.com/tracked-gpu)", rendered)

    def test_sales_url_accepts_http_url(self):
        self.assertEqual(
            report.sales_url({"url": "https://example.com/product"}),
            "https://example.com/product",
        )

    def test_sales_url_rejects_missing_non_http_or_malformed_urls(self):
        self.assertIsNone(report.sales_url({"url": ""}))
        self.assertIsNone(report.sales_url({"url": "javascript:alert(1)"}))
        self.assertIsNone(report.sales_url({"url": "https://"}))
        self.assertIsNone(report.sales_url({"url": "https:///path-without-host"}))
        self.assertIsNone(report.sales_url({"url": "https://user:password@example.com/product"}))
        self.assertIsNone(report.sales_url({}))

    def test_sales_url_strips_whitespace(self):
        self.assertEqual(
            report.sales_url({"url": "  https://example.com/product  "}),
            "https://example.com/product",
        )

    def test_retrieval_issue_link_section_links_each_unverified_item(self):
        latest = {
            "products": [
                {
                    "id": "pc-error",
                    "name": "PC retrieval failure",
                    "url": "https://shop.example.com/pc-error",
                    "fetch_status": "error",
                    "last_fetch_error": "HTTP 403",
                    "current_price_jpy": None,
                    "price_validation_status": "missing",
                    "stock_status": "unknown",
                },
                {
                    "id": "pc-variant",
                    "name": "PC ambiguous SKU",
                    "url": "https://shop.example.com/pc-variant",
                    "fetch_status": "ok",
                    "current_price_jpy": None,
                    "price_validation_status": "variant_ambiguous",
                    "variant_match": "ambiguous",
                    "stock_status": "unknown",
                },
            ]
        }
        parts = {
            "products": [
                {
                    "id": "gpu-error",
                    "name": "GPU direct listing failed",
                    "fetch_status": "error",
                    "last_fetch_error": "HTTP 500",
                    "price_validation_status": "missing",
                    "purchase_url": "https://parts.example.com/gpu",
                    "monitor_url": "https://compare.example.com/gpu",
                },
                {
                    "id": "gpu-ok",
                    "name": "GPU verified",
                    "price_validation_status": "verified_retailer_listing_reference",
                    "retailer_listing_offer": {
                        "url": "https://parts.example.com/gpu-ok",
                        "price_jpy": 120000,
                        "identity_match": True,
                        "pit_valid": True,
                        "stock_status": "in_stock",
                    },
                },
            ]
        }
        peripherals = {
            "products": [
                {
                    "id": "mouse",
                    "name": "Mouse no price",
                    "purchase_url": "https://store.example.com/mouse",
                    "monitor_url": "https://compare.example.com/mouse",
                    "price_verified": False,
                    "current_price_jpy": None,
                    "stock_status": "unknown",
                }
            ]
        }

        lines = report.retrieval_issue_link_section(latest, parts, peripherals)
        rendered = "\\n".join(lines)
        self.assertIn("[商品ページ](https://shop.example.com/pc-error)", rendered)
        self.assertIn("HTTP 403", rendered)
        self.assertIn("[商品ページ](https://shop.example.com/pc-variant)", rendered)
        self.assertIn("[商品ページ](https://parts.example.com/gpu)", rendered)
        self.assertIn("[監視/比較ページ](https://compare.example.com/gpu)", rendered)
        self.assertIn("[商品ページ](https://store.example.com/mouse)", rendered)
        self.assertNotIn("https://parts.example.com/gpu-ok", rendered)

    def test_peripheral_failed_alternative_retailer_urls_remain_visible(self):
        item = {
            "id": "multi-source-mouse",
            "name": "Multi-source mouse",
            "purchase_url": "https://www.yodobashi.com/product/verified-mouse/",
            "monitor_url": "https://www.yodobashi.com/product/verified-mouse/",
            "price_verified": True,
            "identity_verified": True,
            "price_validation_status": "validated_exact_model_page",
            "current_price_jpy": 5350,
            "stock_status": "in_stock",
            "status": "verified",
            "channel_comparison_status": "ONLINE_OPTIONS_COMPARED_STORE_PENDING",
            "retrieval_attempts": [
                {
                    "url": "https://www.yodobashi.com/product/verified-mouse/",
                    "status": "verified",
                    "price_jpy": 5350,
                    "stock_status": "in_stock",
                },
                {
                    "url": "https://www.biccamera.com/bc/item/12345/",
                    "status": "error",
                    "error": "RuntimeError: curl timeout",
                },
                {
                    "url": "https://item.rakuten.co.jp/store/mouse/",
                    "status": "price_unverified",
                    "error": "missing_or_implausible_price",
                },
            ],
        }
        snapshot = {"products": [item]}

        detailed = "\\n".join(report.retrieval_issue_link_lines(
            {"products": []}, {"products": []}, snapshot
        ))
        self.assertIn("[商品ページを開く](https://www.biccamera.com/bc/item/12345/)", detailed)
        self.assertIn("[商品ページを開く](https://item.rakuten.co.jp/store/mouse/)", detailed)
        self.assertIn("RuntimeError: curl timeout", detailed)
        self.assertIn("missing_or_implausible_price", detailed)
        self.assertIn("周辺機器の個別取得元", detailed)

        ranking_section = "\\n".join(report.retrieval_issue_link_section(
            {"products": []}, {"products": []}, snapshot
        ))
        self.assertIn("[商品ページ](https://www.biccamera.com/bc/item/12345/)", ranking_section)
        self.assertIn("[商品ページ](https://item.rakuten.co.jp/store/mouse/)", ranking_section)
        self.assertIn("販売元別の確認未完了", ranking_section)
        self.assertIn("curl timeout", ranking_section)

    def test_suppress_current_price_moves_value_to_reference_only(self):
        row = {"current_price_jpy": 299800, "last_valid_price_jpy": None, "price_jpy": 299800}
        out = report.suppress_current_price(row)
        self.assertIsNone(out["current_price_jpy"])
        self.assertIsNone(out["price_jpy"])
        self.assertEqual(out["last_valid_price_jpy"], 299800)
        self.assertTrue(out["current_price_suppressed"])

    def test_build_products_retains_uncatalogued_discovered_candidate(self):
        discovered = {
            "id": "discovered-a1b2c3d4",
            "name": "Outlet RTX 5070 desktop",
            "url": "https://example.com/pc",
            "form_factor": "desktop",
            "current_price_jpy": 249800,
            "stock_status": "in_stock",
            "price_source_mode": "direct_text",
            "price_validation_status": "validated",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
            "retrieval_time": "2026-10-10T10:00:00+09:00",
            "available_at": "2026-10-10T10:00:00+09:00",
        }
        rows = report.build_products({"products": [discovered]}, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], discovered["id"])
        self.assertTrue(rows[0]["dynamic_candidate"])
        self.assertEqual(rows[0]["current_price_jpy"], 249800)
        self.assertEqual(rows[0]["variant_match"], "ambiguous")

    def test_primary_plan_reports_upgrade_cost_ceiling_without_assuming_it(self):
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-i5g70-5070",
                "role": "primary_configuration_upgrade",
                "label": "DG-I5G70",
                "baseline_price_jpy": 279800,
                "baseline_ram_gb": 16,
                "baseline_ssd_gb": 500,
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-i5g70-5070",
            "name": "G TUNE DG-I5G70",
            "url": "https://example.com/dg-i5",
            "form_factor": "desktop",
            "current_price_jpy": 279800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070", "ram_gb": 16, "ssd": "500 GB"},
            "retrieval_time": "2026-10-10T18:00:00+09:00",
            "available_at": "2026-10-10T17:59:00+09:00",
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200}
        result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["status"], "PRE_BF_TARGET_MONITORING")
        self.assertEqual(row["max_upgrade_cost_to_bf_target_jpy"], 70200)
        self.assertEqual(row["max_upgrade_cost_to_bf_hard_cap_jpy"], 70200)
        self.assertEqual(row["black_friday_target_price_jpy"], 350000)
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertEqual(row["pre_black_friday_reference_price_jpy"], 279800)
        self.assertIn("BF価格ではありません", row["detail"])

    def test_outlet_plan_reports_target_and_live_cap_gaps_separately(self):
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "last_verified_listing_reference_jpy": 330000,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 330000,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
            "retrieval_time": "2026-10-10T18:00:00+09:00",
            "available_at": "2026-10-10T17:59:00+09:00",
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 320200, "pc_budget_jpy": 310200}
        projection = {"pc_dynamic_cap_jpy": 289240}
        result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["status"], "PRE_BF_TARGET_MONITORING")
        self.assertEqual(row["black_friday_target_price_jpy"], 320200)
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertEqual(row["pre_black_friday_reference_price_jpy"], 330000)
        self.assertEqual(row["black_friday_price_cap_jpy"], 310200)
        self.assertEqual(row["pre_bf_reference_gap_to_target_jpy"], 9800)
        self.assertEqual(row["pre_bf_reference_gap_to_planned_cap_jpy"], 19800)

    def test_rtx_5070_ti_outlier_requires_verified_complete_configuration(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "outlier-5070ti-incomplete",
            "name": "RTX 5070 Ti desktop",
            "url": "https://www.mouse-jp.co.jp/store/g/5070ti",
            "form_factor": "desktop",
            "current_price_jpy": 289800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070 Ti", "ram_gb": 16, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "CONFIRMED_MANUAL",
                    "start_jst": "2026-11-15T00:00:00+09:00",
                    "end_jst": "2026-11-30T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["role"], "rtx_5070_ti_outlier")
        self.assertEqual(row["status"], "NO_VERIFIED_COMPLETE_CONFIGURATION")
        self.assertFalse(row["configuration_ready"])
        self.assertEqual(row["verified_complete_candidate_count"], 0)

    def test_bf_price_requires_observation_inside_window(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "black_friday_target_price_jpy": 299800,
                "last_verified_listing_reference_jpy": 304800,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 299800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "retrieval_time": "2026-11-20T12:00:00+09:00",
            "available_at": "2026-11-20T11:59:00+09:00",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200, "budget_data_ready": True}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "CONFIRMED_MANUAL",
                    "start_jst": "2026-11-15T00:00:00+09:00",
                    "end_jst": "2026-11-30T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(result["pricing_phase"], "PROVISIONAL_BROAD_WATCH_WINDOW")
        self.assertTrue(row["black_friday_offer_verified"])
        self.assertEqual(row["black_friday_price_observed_jpy"], 299800)
        self.assertIsNone(row["pre_black_friday_reference_price_jpy"])
        self.assertEqual(row["status"], "MEETS_BF_PRICE_AND_CONFIGURATION")

    def test_watch_window_reference_is_not_mislabelled_pre_sale_or_official_bf(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "black_friday_target_price_jpy": 299800,
                "last_verified_listing_reference_jpy": 304800,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 299800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "retrieval_time": "2026-11-20T12:00:00+09:00",
            "available_at": "2026-11-20T11:59:00+09:00",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200, "budget_data_ready": True}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "UNCONFIRMED",
                    "start_jst": None,
                    "end_jst": None,
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(result["pricing_phase"], "PROVISIONAL_BROAD_WATCH_WINDOW")
        self.assertFalse(row["black_friday_offer_verified"])
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertIsNone(row["pre_black_friday_reference_price_jpy"])
        self.assertEqual(row["watch_window_reference_price_jpy"], 299800)
        self.assertEqual(row["status"], "WAIT_FOR_OFFICIAL_DATES")


    def test_file_sha256_is_stable_for_same_bytes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"
            p.write_bytes(b"black-friday")
            first = report.file_sha256(p)
            second = report.file_sha256(p)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)



    def test_branch_cash_prices_render_separately_with_their_own_timestamps(self):
        item = {
            "purchase_channel": "compare_online_and_store",
            "purchase_channel_options": ["online", "physical_store", "store_pickup"],
            "online_comparison_price_jpy": 20790,
            "store_price_confirmed": True,
            "store_price_jpy": 21980,
            "store_stock_status": "low_stock",
            "store_observation_store_id": "yodobashi_hakata",
            "store_observation_store_name": "ヨドバシカメラ マルチメディア博多",
            # Deliberately different aggregate inventory fields: the quote
            # renderer must use branch-specific cash-price evidence instead.
            "store_inventory_store_name": "誤った支店名",
            "store_inventory_status": "in_stock",
            "store_price_observations": [
                {
                    "store_price_confirmed": True,
                    "store_model_match": True,
                    "store_name": "ビックカメラ天神1号館",
                    "store_observation_store_id": "bic_camera_tenjin_1",
                    "store_price_jpy": 22980,
                    "store_stock_status": "in_stock",
                    "store_price_checked_at": "2026-10-18T10:00:00+09:00",
                    "store_observation_age_minutes": 5,
                },
                {
                    "store_price_confirmed": True,
                    "store_model_match": True,
                    "store_name": "ヨドバシカメラ マルチメディア博多",
                    "store_observation_store_id": "yodobashi_hakata",
                    "store_price_jpy": 21980,
                    "store_stock_status": "low_stock",
                    "store_price_checked_at": "2026-10-18T10:02:00+09:00",
                    "store_observation_age_minutes": 3,
                },
            ],
        }
        summary = report.peripheral_route_price_summary(item)
        self.assertIn("ビックカメラ天神1号館 店頭現金 ¥22,980", summary)
        self.assertIn("ヨドバシカメラ マルチメディア博多 店頭現金 ¥21,980", summary)
        self.assertIn("2026-10-18 10:00 JST", summary)
        self.assertIn("2026-10-18 10:02 JST", summary)
        self.assertNotIn("誤った支店名", summary)

    def test_store_pickup_stock_cannot_authorize_a_physical_cash_purchase(self):
        now = datetime(2026, 10, 18, 12, 0, tzinfo=timezone(timedelta(hours=9)))
        stamp = now.isoformat()
        observation = {
            "store_price_confirmed": True,
            "store_price_jpy": 21980,
            "store_model_match": True,
            "store_observation_store_id": "bic_camera_tenjin_1",
            "store_price_checked_at": stamp,
            "store_stock_status": "out_of_stock",
            "store_inventory_verified": True,
            "store_inventory_status": "in_stock",
            "store_inventory_store_id": "yodobashi_hakata",
            "store_inventory_checked_at": stamp,
            "store_inventory_observations": [
                {
                    "store_id": "yodobashi_hakata",
                    "store_name": "ヨドバシカメラ マルチメディア博多",
                    "status": "in_stock",
                    "checked_at": stamp,
                }
            ],
        }
        result = report.peripheral_purchase_evidence_score(
            {"purchase_channel": "compare_online_and_store"}, observation, now=now
        )
        self.assertEqual(result["breakdown"]["sellable_stock"], 0)
        self.assertFalse(result["checkout_total_verified"])
        self.assertFalse(result["purchase_route_ready"])

    def test_mixed_route_report_never_labels_online_price_as_store_cash_price(self):
        item = {
            "purchase_channel": "compare_online_and_store",
            "purchase_channel_options": ["online", "physical_store", "store_pickup"],
            "online_comparison_price_jpy": 20790,
            "estimated_online_cash_total_jpy": 21790,
            "online_shipping_reserve_jpy": 1000,
            "online_shipping_cost_verified": False,
            "store_price_confirmed": False,
            "channel_comparison_status": "ONLINE_OPTIONS_COMPARED_STORE_PENDING",
        }
        self.assertFalse(report.peripheral_is_physical_store(item, {}))
        self.assertEqual(report.peripheral_route_label(item), "ネット配送・実店舗・店舗受取を比較")
        summary = report.peripheral_route_price_summary(item)
        self.assertIn("ネット掲載 ¥20,790", summary)
        self.assertIn("送料込み推計 ¥21,790", summary)
        self.assertIn("店頭現金価格未確認", summary)
        self.assertIn("店舗受け取り: 決済額未確認", summary)
        self.assertIn("ONLINE_OPTIONS_COMPARED_STORE_PENDING", summary)


class PeripheralRouteCoverageTests(unittest.TestCase):
    def test_store_first_quote_coverage_is_not_hidden_by_zero_explicit_comparison_count(self):
        projection = {
            "channel_comparison_required_count": 0,
            "channel_comparison_complete_count": 0,
            "peripherals": [
                {
                    "id": "main_monitor",
                    "name": "AOC Q27G40E/11",
                    "track_current_price": True,
                    "purchase_channel": "physical_store",
                    "store_candidate_branch_ids": ["biccamera_tenjin_1", "yodobashi_hakata"],
                    "store_price_verified_store_ids": [],
                    "store_route_all_branches_confirmed": False,
                    "online_reference_price_verified": True,
                },
                {
                    "id": "keyboard",
                    "name": "Logicool G213r",
                    "track_current_price": True,
                    "purchase_channel": "physical_store",
                    "store_candidate_branch_ids": ["biccamera_tenjin_1", "yodobashi_hakata"],
                    "store_price_verified_store_ids": ["biccamera_tenjin_1"],
                    "store_route_all_branches_confirmed": False,
                    "online_reference_price_verified": False,
                },
            ],
        }
        summary = report.peripheral_route_coverage_summary(projection)
        self.assertEqual(summary["online_price_verified_count"], 1)
        self.assertEqual(summary["online_price_total_count"], 2)
        self.assertEqual(summary["store_branch_confirmed_count"], 1)
        self.assertEqual(summary["store_branch_expected_count"], 4)
        self.assertEqual(summary["store_product_confirmed_count"], 0)
        self.assertEqual(summary["store_product_total_count"], 2)
        self.assertEqual(summary["store_product_pending_names"], ["AOC Q27G40E/11", "Logicool G213r"])
        self.assertEqual(summary["all_route_comparison_required_count"], 0)

    def test_missing_peripheral_projection_is_not_reported_as_zero_coverage(self):
        summary = report.peripheral_route_coverage_summary(None)
        self.assertIsNone(summary["online_price_total_count"])
        self.assertIsNone(summary["store_branch_expected_count"])
        self.assertIsNone(summary["all_route_comparison_required_count"])


if __name__ == "__main__":
    unittest.main()
