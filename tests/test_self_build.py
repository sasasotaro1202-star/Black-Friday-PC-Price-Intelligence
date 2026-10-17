import json
import pathlib
import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import self_build_planner as planner
import build_component_monitor as component_monitor

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=JST)


class SelfBuildPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "config" / "build_components.json").open(encoding="utf-8") as stream:
            cls.config = json.load(stream)
        cls.parts = {x["id"]: x for x in cls.config["parts"]}

    def test_component_early_buy_signal_reaches_ranked_build_table(self):
        signal = {
            "item_id": "cpu-ryzen7-9700x",
            "early_buy_threshold_jpy": 36000,
            "observed_price_jpy": 35000,
            "estimated_checkout_total_jpy": 35500,
            "verified_checkout_total_jpy": None,
            "checkout_total_verified": False,
            "status": "PRICE_TRIGGERED_CHECKOUT_REVIEW",
            "label_ja": "前倒し候補：決済総額確認待ち",
            "purchase_authorized": False,
            "next_step": "送料込みの決済総額・保証・返品条件・互換性を確認",
        }
        plan = planner.build_plan(
            self.config,
            {"generated_at": NOW.isoformat(), "products": [
                {"id": "cpu-ryzen7-9700x", "early_buy_review": signal}
            ]},
            now=NOW,
        )
        main = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        cpu = next(x for x in main["components"] if x["id"] == "cpu-ryzen7-9700x")
        self.assertEqual(cpu["early_buy_review"], signal)
        markdown = planner.render_plan_markdown(plan)
        self.assertIn("前倒し購入シグナル", markdown)
        self.assertIn("前倒し候補：決済総額確認待ち", markdown)
        self.assertFalse(plan["buy_now_authorized"])

    def test_build_scorecards_are_transparent_ranked_and_not_purchase_authorization(self):
        plan = planner.build_plan(self.config, {"products": []}, now=NOW)
        builds = plan["builds"]
        scores = [build["scorecard"]["overall_score"] for build in builds]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for build in builds:
            score = build["scorecard"]
            self.assertGreaterEqual(score["overall_score"], 0)
            self.assertLessEqual(score["overall_score"], 100)
            self.assertGreaterEqual(score["purchase_evidence_completeness_score_out_of_100"], 0)
            self.assertLessEqual(score["purchase_evidence_completeness_score_out_of_100"], 100)
            self.assertFalse(score["purchase_authorized"])
            self.assertEqual(score["required_component_count"], len(build["components"]))
            self.assertAlmostEqual(
                score["overall_score"],
                score["gaming_score"] + score["game_creation_score"] + score["analysis_ai_score"]
                + score["study_multitasking_score"] + score["price_efficiency_points_out_of_15"]
                + score["compatibility_points_out_of_10"],
                delta=0.01,
            )
            # Price-comparison coverage must not masquerade as checkout readiness.
            self.assertEqual(score["sellable_stock_coverage_pct"], 0)
            self.assertEqual(score["verified_checkout_total_coverage_pct"], 0)
            self.assertLess(score["purchase_evidence_completeness_score_out_of_100"], 30)
        by_gpu = {build["gpu_choice_id"]: build["scorecard"] for build in builds}
        self.assertEqual(by_gpu["gpu-rtx5070ti-16gb"]["gaming_score"], 25.0)
        self.assertEqual(by_gpu["gpu-rtx5070-12gb"]["gaming_score"], round(25 * 96.4 / 116.8, 1))
        self.assertEqual(by_gpu["gpu-rtx5060ti-16gb"]["gaming_score"], round(25 * 73.4 / 116.8, 1))
        self.assertGreater(
            by_gpu["gpu-rtx5070-12gb"]["gaming_score"],
            by_gpu["gpu-rtx5060ti-16gb"]["gaming_score"],
        )
        self.assertEqual(
            by_gpu["gpu-rtx5070ti-16gb"]["gaming_benchmark_reference"]["source_updated"],
            "2026-06-24",
        )
        self.assertFalse(by_gpu["gpu-rtx5070ti-16gb"]["gaming_benchmark_reference"]["user_game_specific"])
        rendered = planner.render_plan_markdown(plan)
        self.assertIn("100点方式の構成スコア", rendered)
        self.assertIn("購入根拠充足度/100", planner.section_from_plan(plan))
        self.assertIn("対象ゲームの実測FPSではありません", rendered)
        self.assertIn("Tom's Hardware GPU Benchmarks Hierarchy 2026", rendered)
        self.assertIn("https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html", rendered)
        self.assertFalse(plan["buy_now_authorized"])

    def test_verified_direct_price_stock_and_checkout_evidence_raise_completeness(self):
        plan = planner.build_plan(self.config, {"products": []}, now=NOW)
        for build in plan["builds"]:
            for part in build["components"]:
                part["early_buy_review"] = {
                    "observed_price_jpy": 10000,
                    "price_verified": True,
                    "identity_verified": True,
                    "pit_valid": True,
                    "stock_status": "in_stock",
                    "verified_checkout_total_jpy": 10500,
                    "checkout_total_verified": True,
                    "purchase_authorized": False,
                }
        rescored = planner.score_and_rank_builds(plan["builds"])
        for build in rescored:
            score = build["scorecard"]
            self.assertEqual(score["direct_price_identity_pit_coverage_pct"], 100.0)
            self.assertEqual(score["sellable_stock_coverage_pct"], 100.0)
            self.assertEqual(score["verified_checkout_total_coverage_pct"], 100.0)
            self.assertGreaterEqual(score["purchase_evidence_completeness_score_out_of_100"], 80.0)
            self.assertFalse(score["purchase_authorized"])

    def test_target_totals_and_all_in_budget(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        builds = {x["gpu_choice_id"]:x for x in plan["builds"]}
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_pc_total_jpy"], 300600)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_pc_total_jpy"], 280600)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_pc_total_jpy"], 324800)
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_all_in_jpy"], 340600)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_all_in_jpy"], 320600)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_all_in_jpy"], 364800)
        self.assertTrue(builds["gpu-rtx5070ti-16gb"]["target_within_pc_budget"])
        self.assertTrue(builds["gpu-rtx5070ti-16gb"]["target_within_total_budget"])
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_remaining_budget_jpy"], 35200)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["decision"], "WAIT_FOR_COMPATIBILITY_REVIEW")
        self.assertTrue(plan["budget_arithmetic_valid"])
        self.assertFalse(plan["buy_now_authorized"])

    def test_primary_build_selects_budget_fit_teamgroup_and_keeps_crucial_as_alternative(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        builds = {x["gpu_choice_id"]:x for x in plan["builds"]}
        main = builds["gpu-rtx5070-12gb"]
        memory = [x for x in main["components"] if x["category"] == "memory"]
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]["id"], "memory-teamgroup-ddr5-32gb-6000")
        self.assertEqual(memory[0]["target_price_jpy"], 40000)
        self.assertNotIn("memory-crucial-pro-ddr5-32gb-6000", [x["id"] for x in main["components"]])
        self.assertEqual(main["compatibility_status"], "REVIEW")
        self.assertIn("memory-teamgroup-ddr5-32gb-6000", {x["id"] for x in self.config["parts"]})
        self.assertEqual(
            next(x for x in self.config["parts"] if x["id"] == "memory-teamgroup-ddr5-32gb-6000")["role"],
            "primary_budget_fit",
        )

    def test_cheapest_fresh_verified_memory_reference_is_selected(self):
        rows = self._verified_hardware_rows(self.config)
        rows_by_id = {row["id"]: row for row in rows}
        crucial_id = "memory-crucial-pro-ddr5-32gb-6000"
        teamgroup_id = "memory-teamgroup-ddr5-32gb-6000"
        rows_by_id[crucial_id]["market_reference_price_jpy"] = 82000
        rows_by_id[teamgroup_id]["market_reference_price_jpy"] = 72000
        plan = planner.build_plan(
            self.config, {"generated_at": NOW.isoformat(), "products": rows}, now=NOW
        )
        main = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        components = {component["id"]: component for component in main["components"]}
        self.assertIn(teamgroup_id, components)
        self.assertNotIn(crucial_id, components)
        self.assertEqual(main["selected_memory_id"], teamgroup_id)
        self.assertEqual(main["memory_choice_method"], "lowest_fresh_verified_market_reference")
        self.assertEqual(main["target_pc_total_jpy"], 300600)
        self.assertEqual(main["target_all_in_jpy"], 340600)
        self.assertEqual(main["compatibility_status"], "REVIEW")
        self.assertFalse(main["buy_now_authorized"])

    def test_malformed_memory_choice_list_falls_back_to_valid_primary_not_missing_ram(self):
        bad_config = json.loads(json.dumps(self.config))
        bad_config["profile"]["memory_choice_ids"] = ["not-a-configured-memory-kit"]
        plan = planner.build_plan(bad_config, {"products":[]}, now=NOW)
        main = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        memory = [component for component in main["components"] if component["category"] == "memory"]
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]["id"], "memory-teamgroup-ddr5-32gb-6000")
        self.assertEqual(main["selected_memory_id"], "memory-teamgroup-ddr5-32gb-6000")
        self.assertEqual(main["target_pc_total_jpy"], 300600)

    def test_no_trusted_memory_reference_keeps_budget_fit_teamgroup_primary(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        main = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        self.assertEqual(main["selected_memory_id"], "memory-teamgroup-ddr5-32gb-6000")
        self.assertEqual(main["memory_choice_method"], "primary_memory_fallback_no_verified_market_reference")
        self.assertEqual(main["target_pc_total_jpy"], 300600)
        self.assertFalse(main["buy_now_authorized"])

    def test_diy_is_primary_and_assembly_time_has_zero_penalty(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        policy = plan["purchase_method_policy"]
        self.assertEqual(policy["primary_method"], "SELF_BUILD")
        self.assertFalse(policy["assembly_time_is_constraint"])
        self.assertEqual(policy["assembly_time_penalty_points"], 0)
        self.assertEqual(policy["bto_role"], "REFERENCE_BENCHMARK_ONLY")
        rendered = planner.render_plan_markdown(plan)
        self.assertIn("自作PCを正式な本命", rendered)
        self.assertIn("組み立て時間・作業時間は減点しません", rendered)

    def test_gpu_options_are_mutually_exclusive_and_categories_unique(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        for build in plan["builds"]:
            self.assertEqual([x["id"] for x in build["components"] if x["category"] == "gpu"], [build["gpu_choice_id"]])
            categories = [x["category"] for x in build["components"]]
            self.assertEqual(len(categories), len(set(categories)))
            self.assertTrue(set(self.config["profile"]["required_categories"]).issubset(categories))

    def test_direct_listing_with_unavailable_stock_is_displayed_but_not_trusted(self):
        part = self.parts["motherboard-asrock-b850m-pro-rs-wifi"]
        stamp = "2026-11-20T11:58:00+09:00"
        offer = {
            "url": "https://www.ark-pc.co.jp/i/12201558/",
            "title": "B850M Pro RS WiFi", "price_jpy": 21380,
            "price_source_mode": "direct_structured",
            "stock_status": "preorder_or_backorder",
            "identity_anchor": "B850M Pro RS WiFi", "identity_match": True,
            "source_role": "direct_retailer_listing_reference",
            "available_at": stamp, "retrieval_time": stamp,
            "pit_valid": True, "bf_actual_authorized": False,
        }
        row = {
            "id": part["id"], "price_validation_status": "search_snippet_reference",
            "source_role": "comparison_site_reference",
            "search_snippet_reference_price_jpy": 23780,
            "search_snippet_reference_url": "https://search.kakaku.com/B850M/",
            "search_snippet_reference_title": "ASRock B850M Pro RS WiFi",
            "search_snippet_identity_anchor": "B850M Pro RS WiFi",
            "identity_match": True, "pit_valid": True, "bf_actual_authorized": False,
            "available_at": stamp, "retrieval_time": stamp,
            "retailer_listing_offer": None, "retailer_listing_offers": [offer],
        }
        result = planner.component_price(
            part, {part["id"]: row}, NOW, 360, ["ark-pc.co.jp"]
        )
        self.assertIsNone(result["market_reference_price_jpy"])
        self.assertFalse(result["trusted_for_market_estimate"])
        self.assertEqual(result["display_reference_price_jpy"], 23780)
        self.assertEqual(result["direct_listing_display_price_jpy"], 21380)
        self.assertEqual(result["direct_listing_display_stock_status"], "preorder_or_backorder")
        self.assertEqual(result["direct_listing_display_stock_label"], "取寄せ/予約")
        self.assertFalse(result["direct_listing_display_is_estimate_eligible"])
        self.assertFalse(result["direct_listing_display_purchase_allowed"])

        plan = planner.build_plan(self.config, {"generated_at": stamp, "products": [row]}, now=NOW)
        build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        component = next(x for x in build["components"] if x["id"] == part["id"])
        self.assertEqual(component["direct_listing_display_price_jpy"], 21380)
        self.assertIsNone(build["market_reference_estimate_jpy"])
        self.assertFalse(build["buy_now_authorized"])
        report = planner.render_plan_markdown(plan)
        self.assertIn("直接掲載価格（在庫条件未達・推定不採用）", report)
        self.assertIn("21,380", report)
        self.assertIn("取寄せ/予約", report)

    def test_direct_listing_failure_diagnostics_are_visible_in_part_report(self):
        gpu = self.parts["gpu-rtx5070-12gb"]
        stamp = NOW.isoformat()
        row = {
            "id": gpu["id"],
            "price_validation_status": "search_snippet_reference",
            "source_role": "comparison_site_reference",
            "search_snippet_reference_price_jpy": 190800,
            "search_snippet_reference_url": "https://search.kakaku.com/PNY/",
            "search_snippet_reference_title": "VCG507012DFSXPB1-O",
            "search_snippet_identity_anchor": "VCG507012DFSXPB1-O",
            "identity_match": True,
            "pit_valid": True,
            "bf_actual_authorized": False,
            "available_at": stamp,
            "retrieval_time": stamp,
            "retailer_listing_offer": None,
            "retailer_listing_offers": [],
            "search_diagnostics": [{
                "provider": "configured_direct_retailer",
                "url": "https://joshinweb.jp/kaden/73259/0751492812151.html",
                "status": "unverified",
                "error": "fetch_error",
                "stock_status": "unknown",
                "validation": {
                    "reason_code": "fetch_error",
                    "error_type": "HTTPError",
                    "error_message": "HTTP 403 blocked",
                    "price_source_mode": "none",
                    "stock_status": "unknown",
                },
            }],
        }
        plan = planner.build_plan(self.config, {"generated_at": stamp, "products": [row]}, now=NOW)
        build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        component = next(x for x in build["components"] if x["id"] == gpu["id"])
        diag = component["direct_listing_validation_diagnostics"][0]
        self.assertEqual(diag["reason_code"], "fetch_error")
        self.assertEqual(diag["error_message"], "HTTP 403 blocked")
        report = planner.render_plan_markdown(plan)
        self.assertIn("直接取得診断", report)
        self.assertIn("fetch_error", report)
        self.assertIn("HTTP 403 blocked", report)
        self.assertIn("search_snippet_reference_only", report)
        self.assertFalse(build["buy_now_authorized"])

    def test_unknown_price_is_never_zero_filled_or_authorized(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        for build in plan["builds"]:
            self.assertIsNone(build["market_reference_estimate_jpy"])
            self.assertFalse(build["bf_actual_authorized"])
            self.assertFalse(build["buy_now_authorized"])
            for part in build["components"]:
                if part["track_price"]:
                    self.assertIsNone(part["market_reference_price_jpy"])

    def test_stale_and_unverified_reference_are_excluded(self):
        cpu = self.parts["cpu-ryzen7-9700x"]
        for extra, stamp in [
            ({"identity_match":True,"pit_valid":True},"2026-10-14T00:00:00+09:00"),
            ({"identity_match":False,"pit_valid":True},"2026-11-20T12:00:00+09:00"),
            ({"identity_match":True,"pit_valid":False},"2026-11-20T12:00:00+09:00"),
            ({"identity_match":True,"pit_valid":True},"2026-11-20T12:01:00+09:00")
        ]:
            row = {"id":cpu["id"],"market_reference_price_jpy":40000,
                "price_validation_status":"verified_market_reference","source_role":"comparison_site_reference",
                "bf_actual_authorized":False,"retrieval_time":stamp,"available_at":stamp,
                "identity_match":True,"pit_valid":True}
            row.update(extra)
            plan = planner.build_plan(self.config, {"products":[row]}, now=NOW)
            build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
            part = next(x for x in build["components"] if x["id"] == cpu["id"])
            self.assertFalse(part["trusted_for_market_estimate"])
            self.assertFalse(build["market_reference_coverage_complete"])

    def test_gaming_creation_study_and_analysis_are_all_explicit_workloads(self):
        plan = planner.build_plan(self.config, {"products": []}, now=NOW)
        profile = plan["workload_profile"]
        self.assertEqual(profile["game_development"]["priority"], "HIGH")
        self.assertEqual(profile["study_and_research"]["priority"], "HIGH")
        self.assertEqual(profile["analysis_and_automation"]["priority"], "HIGH")
        self.assertIn("school/study work", profile["study_and_research"]["targets"])
        self.assertIn("sports prediction systems", profile["analysis_and_automation"]["targets"])
        self.assertIn("stock/securities prediction", profile["analysis_and_automation"]["targets"])
        self.assertIn("BTC prediction", profile["analysis_and_automation"]["targets"])
        self.assertIn("local AI models when feasible", profile["analysis_and_automation"]["targets"])

        for build in plan["builds"]:
            fit = build["workload_fit"]
            self.assertEqual(fit["status"], "MEETS_BASELINE")
            self.assertEqual(fit["selected_hardware"]["system_ram_gb"], 32)
            self.assertGreaterEqual(fit["selected_hardware"]["dedicated_gpu_vram_gb"], 8)
            self.assertEqual(fit["selected_hardware"]["primary_ssd_gb"], 1000)
            self.assertFalse(fit["post_purchase_upgrade_assumption"])
            self.assertFalse(fit["purchase_authorized"])
            self.assertIn("study_and_research", fit)
            self.assertIn("analysis_automation_profile", fit["ai_and_data_analysis"])
            self.assertEqual(
                fit["game_development"]["unreal_engine_source_compile"]["status"],
                "TRADEOFF_BELOW_PRACTICAL_CORE_TARGET",
            )

        rendered = planner.render_plan_markdown(plan)
        self.assertIn("勉強・調査:", rendered)
        self.assertIn("データ分析・自動化・AI:", rendered)
        self.assertIn("ゲーム制作も主要要件", rendered)

    def _verified_hardware_rows(self, config, stamp=None):
        stamp = stamp or NOW.isoformat()
        return [
            {
                "id": part["id"],
                "market_reference_price_jpy": part["target_price_jpy"],
                "price_validation_status": "verified_market_reference",
                "source_role": "comparison_site_reference",
                "identity_match": True,
                "pit_valid": True,
                "bf_actual_authorized": False,
                "available_at": stamp,
                "retrieval_time": stamp,
            }
            for part in config["parts"] if part.get("track_price")
        ]

    def test_os_component_is_not_zero_filled_when_direct_price_is_missing(self):
        rows = [
            row for row in self._verified_hardware_rows(self.config)
            if row["id"] != "os-windows11-home"
        ]
        plan = planner.build_plan(
            self.config, {"generated_at": NOW.isoformat(), "products": rows}, now=NOW
        )
        build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        self.assertIsNone(build["market_reference_estimate_jpy"])
        self.assertFalse(build["market_reference_coverage_complete"])
        self.assertIn("os-windows11-home", build["missing_or_untrusted_market_reference_ids"])
        self.assertEqual(build["market_reference_coverage_count"], 8)
        os_row = next(x for x in build["components"] if x["id"] == "os-windows11-home")
        self.assertIsNone(os_row["market_reference_price_jpy"])
        self.assertIsNone(os_row["display_reference_price_jpy"])
        self.assertEqual(os_row["price_status"], "not_observed")
        self.assertFalse(os_row["trusted_for_market_estimate"])
        report = planner.render_plan_markdown(plan)
        self.assertIn("¥14,800", report)
        self.assertNotIn("19,360（手動参考・現行未確認）", report)

    def test_fresh_verified_os_retailer_reference_can_complete_estimate(self):
        rows = self._verified_hardware_rows(self.config)
        plan = planner.build_plan(
            self.config, {"generated_at": NOW.isoformat(), "products": rows}, now=NOW
        )
        build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        self.assertEqual(build["market_reference_estimate_jpy"], build["target_pc_total_jpy"])
        self.assertTrue(build["market_reference_coverage_complete"])
        self.assertEqual(build["market_reference_coverage_count"], 9)
        self.assertNotIn("os-windows11-home", build["missing_or_untrusted_market_reference_ids"])
        os_row = next(x for x in build["components"] if x["id"] == "os-windows11-home")
        self.assertEqual(os_row["price_status"], "verified_market_reference")
        self.assertTrue(os_row["trusted_for_market_estimate"])

    def test_future_dated_direct_retailer_listing_is_never_trusted(self):
        part = self.parts["motherboard-asrock-b850m-pro-rs-wifi"]
        future = "2026-11-20T12:01:00+09:00"
        offer = {
            "url": "https://www.ark-pc.co.jp/i/12201558/",
            "title": "B850M Pro RS WiFi",
            "price_jpy": 21380,
            "price_source_mode": "direct_structured",
            "stock_status": "in_stock",
            "identity_anchor": "B850M Pro RS WiFi",
            "identity_match": True,
            "source_role": "direct_retailer_listing_reference",
            "available_at": future,
            "retrieval_time": future,
            "pit_valid": True,
            "bf_actual_authorized": False,
        }
        row = {
            "id": part["id"],
            "price_validation_status": "verified_retailer_listing_reference",
            "source_role": "direct_retailer_listing_reference",
            "retailer_listing_offer": offer,
            "retailer_listing_offers": [offer],
            "retailer_listing_reference_price_jpy": 21380,
            "identity_match": True,
            "pit_valid": True,
            "bf_actual_authorized": False,
            "available_at": future,
            "retrieval_time": future,
        }
        result = planner.component_price(part, {part["id"]: row}, NOW, 360, ["ark-pc.co.jp"])
        self.assertFalse(result["trusted_for_market_estimate"])
        self.assertIsNone(result["market_reference_price_jpy"])
        self.assertIsNone(result["direct_listing_display_price_jpy"])

    def test_two_slot_gpus_pass_geometry_but_near_three_slot_dark_horse_needs_review(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        by_gpu = {x["gpu_choice_id"]:x for x in plan["builds"]}
        self.assertEqual(by_gpu["gpu-rtx5070-12gb"]["compatibility_status"], "REVIEW")
        self.assertEqual(by_gpu["gpu-rtx5060ti-16gb"]["compatibility_status"], "REVIEW")
        self.assertEqual(by_gpu["gpu-rtx5070ti-16gb"]["compatibility_status"], "REVIEW")
        for gpu_id in ("gpu-rtx5070-12gb", "gpu-rtx5060ti-16gb"):
            checks = {x["check"]: x["status"] for x in by_gpu[gpu_id]["compatibility_checks"]}
            self.assertEqual(checks["gpu_slot_thickness"], "PASS")
            self.assertEqual(checks["cpu_bios_support"], "REVIEW")
            self.assertEqual(checks["memory_qvl"], "REVIEW")
        dark_checks = {x["check"]: x["status"] for x in by_gpu["gpu-rtx5070ti-16gb"]["compatibility_checks"]}
        self.assertEqual(dark_checks["gpu_slot_thickness"], "REVIEW")
        self.assertEqual(dark_checks["cpu_bios_support"], "REVIEW")
        self.assertEqual(dark_checks["memory_qvl"], "REVIEW")

    def test_verified_bios_and_exact_memory_qvl_can_clear_the_review_checks(self):
        verified = json.loads(json.dumps(self.config))
        parts = {x["id"]: x for x in verified["parts"]}
        parts["motherboard-asrock-b850m-pro-rs-wifi"]["specs"]["observed_bios_version"] = "4.60"
        parts["memory-teamgroup-ddr5-32gb-6000"]["specs"]["qvl_verified_with_asrock_b850m_pro_rs_wifi"] = True
        plan = planner.build_plan(verified, {"products":[]}, now=NOW)
        builds = {x["gpu_choice_id"]:x for x in plan["builds"]}
        main = builds["gpu-rtx5070-12gb"]
        statuses = {x["check"]:x["status"] for x in main["compatibility_checks"]}
        self.assertEqual(statuses["cpu_bios_support"], "PASS")
        self.assertEqual(statuses["memory_qvl"], "PASS")
        self.assertEqual(main["compatibility_status"], "PASS")
        self.assertFalse(main["buy_now_authorized"])
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["compatibility_status"], "REVIEW")

    def test_socket_and_power_mismatches_fail_closed(self):
        bad = json.loads(json.dumps(self.config))
        by_id = {x["id"]:x for x in bad["parts"]}
        by_id["motherboard-asrock-b850m-pro-rs-wifi"]["specs"]["socket"] = "LGA1851"
        plan = planner.build_plan(bad, {"products":[]}, now=NOW)
        self.assertEqual(next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")["compatibility_status"], "FAIL")
        bad = json.loads(json.dumps(self.config))
        by_id = {x["id"]:x for x in bad["parts"]}
        by_id["psu-corsair-rm850e-2025"]["specs"]["wattage_w"] = 500
        plan = planner.build_plan(bad, {"products":[]}, now=NOW)
        self.assertEqual(next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")["compatibility_status"], "FAIL")

    def test_search_anchor_rejects_generic_gpu_class_without_selected_model_identity(self):
        part = self.parts["gpu-rtx5070-12gb"]
        generic = {"title": "GeForce RTX 5070 12GB", "snippet": "最安価格 ¥149,800"}
        branded = {"title": "PNY GeForce RTX 5070 12GB OC SLIM", "snippet": "VCG507012DFXPB1-O 最安価格 ¥149,800"}
        self.assertIsNone(component_monitor.component_search_identity_anchor(generic, part))
        self.assertIsNotNone(component_monitor.component_search_identity_anchor(branded, part))

    def test_search_snippet_requires_exact_model_and_exact_product_url(self):
        part = self.parts["cpu-ryzen7-9700x"]
        wrong_page = {"url":"https://kakaku.com/item/K0009999999/","title":"AMD Ryzen 7 9700X BOX","snippet":"最安価格 ¥39,980"}
        wrong_identity = {"url":part["monitor_url"],"title":"Generic CPU component","snippet":"最安価格 ¥39,980"}
        retailer_url = {"url":"https://example.com/item/K0001630332/","title":"AMD Ryzen 7 9700X BOX","snippet":"最安価格 ¥39,980"}
        self.assertIsNone(component_monitor.parse_search_snippet_reference(part,[wrong_page]))
        self.assertIsNone(component_monitor.parse_search_snippet_reference(part,[wrong_identity]))
        self.assertIsNone(component_monitor.parse_search_snippet_reference(part,[retailer_url]))
        valid = {"url":part["monitor_url"],"title":"AMD Ryzen 7 9700X BOX 価格比較","snippet":"型番 100-100001404WOF 最安価格 ¥39,980"}
        parsed = component_monitor.parse_search_snippet_reference(part,[valid])
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["price_jpy"],39980)
        self.assertFalse(parsed["bf_actual_authorized"])
        self.assertEqual(parsed["source_role"],"comparison_site_search_snippet_reference")

    def test_search_fallback_records_provider_errors_and_zero_exact_matches(self):
        part = dict(self.parts["cpu-ryzen7-9700x"])
        part["direct_retailer_urls"] = []
        with patch.object(component_monitor, "fetch", side_effect=TimeoutError("fixture: no live Kakaku page")), \
             patch.object(component_monitor, "ddg_search", side_effect=TimeoutError("blocked")), \
             patch.object(component_monitor, "bing_search", return_value=[]):
            result = component_monitor.search_comparison_snippet(part, ("kakaku.com",))
        self.assertIsNotNone(result)
        diagnostics = result["search_diagnostics"]
        providers = [item.get("provider") for item in diagnostics]
        self.assertIn("kakaku_search_page", providers)
        self.assertGreaterEqual(providers.count("bing"), 2)
        duck = [item for item in diagnostics if item.get("provider") == "duckduckgo"]
        self.assertEqual(len(duck), 1)
        self.assertEqual(duck[0]["status"], "error")
        self.assertTrue(all(item.get("result_count", 0) == 0 for item in diagnostics))
        self.assertNotIn("price_jpy", result)

    def test_fetch_part_passes_allowlisted_search_domains_to_fallback(self):
        part = self.parts["cpu-ryzen7-9700x"]
        html = "<html>fixture</html>"
        raw = {
            "name": part["name"],
            "page_text_excerpt": "100-100001404WOF",
            "price_jpy": None,
            "stock_status": "unknown",
            "price_source_mode": "none",
        }
        snippet = {
            "price_jpy": 39980,
            "url": part["monitor_url"],
            "title": "AMD Ryzen 7 9700X BOX",
            "identity_anchor": "100-100001404WOF",
            "search_provider": "duckduckgo",
            "query": "AMD Ryzen 7 9700X BOX 100-100001404WOF",
            "search_diagnostics": [{"provider": "duckduckgo", "result_count": 1}],
        }
        search_domains = ("kakaku.com", "dospara.co.jp")
        with patch.object(component_monitor, "fetch", return_value=(html, part["monitor_url"], {})), \
             patch.object(component_monitor, "parse_page", return_value=raw), \
             patch.object(component_monitor, "search_comparison_snippet", return_value=snippet) as search:
            result = component_monitor.fetch_part(part, ("kakaku.com",), search_domains)
        search.assert_called_once_with(part, search_domains)
        self.assertEqual(result["price_validation_status"], "search_snippet_reference")
        self.assertEqual(result["search_snippet_reference_price_jpy"], 39980)
        self.assertEqual(result["search_snippet_reference_url"], part["monitor_url"])
        self.assertFalse(result["bf_actual_authorized"])
        self.assertEqual(result["source_role"], "comparison_site_reference")

    def test_search_fallback_tries_alternate_query_and_preserves_display_only_source(self):
        part = dict(self.parts["cpu-ryzen7-9700x"])
        part["direct_retailer_urls"] = []
        result_row = {
            "url": part["monitor_url"],
            "title": "AMD Ryzen 7 9700X BOX 価格比較",
            "snippet": "型番 100-100001404WOF 最安価格 ¥39,980",
        }
        with patch.object(component_monitor, "fetch", side_effect=TimeoutError("fixture: no live Kakaku page")), \
             patch.object(component_monitor, "ddg_search", return_value=[result_row]), \
             patch.object(component_monitor, "bing_search", return_value=[]):
            result = component_monitor.search_comparison_snippet(part, ("kakaku.com",))
        self.assertEqual(result["price_jpy"], 39980)
        self.assertEqual(result["search_provider"], "duckduckgo")
        self.assertEqual(result["source_role"], "comparison_site_search_snippet_reference")
        self.assertFalse(result["bf_actual_authorized"])
        diagnostics = result["search_diagnostics"]
        providers = [item.get("provider") for item in diagnostics]
        self.assertIn("kakaku_search_page", providers)
        self.assertGreaterEqual(providers.count("bing"), 2)
        duck = [item for item in diagnostics if item.get("provider") == "duckduckgo"]
        self.assertEqual(len(duck), 1)
        self.assertEqual(duck[0]["result_count"], 1)
        self.assertIn("価格 最安値", duck[0]["query"])

    def test_search_snippet_can_reference_allowlisted_seller_with_exact_model_name(self):
        part = self.parts["cpu-ryzen7-9700x"]
        seller_result = {
            "url": "https://www.dospara.co.jp/TC30/MC12904.html",
            "title": "AMD Ryzen 7 9700X BOX",
            "snippet": "100-100001404WOF 最安価格 ¥39,980",
        }
        with patch.object(component_monitor, "fetch", side_effect=TimeoutError("fixture: no live Kakaku page")), \
             patch.object(component_monitor, "ddg_search", return_value=[seller_result]), \
             patch.object(component_monitor, "bing_search", return_value=[]), \
             patch.object(component_monitor, "verify_retailer_listing", return_value=None):
            found = component_monitor.search_comparison_snippet(part, ("kakaku.com", "dospara.co.jp"))
        self.assertEqual(found["price_jpy"], 39980)
        self.assertEqual(found["url"], seller_result["url"])
        self.assertFalse(found["bf_actual_authorized"])
        self.assertFalse(found["same_comparison_item_path"])
        self.assertEqual(found["source_role"], "comparison_site_search_snippet_reference")

    def test_search_snippet_price_outside_part_range_is_rejected(self):
        part = self.parts["cpu-ryzen7-9700x"]
        bad = {"url":part["monitor_url"],"title":"AMD Ryzen 7 9700X BOX 100-100001404WOF","snippet":"最安価格 ¥1,000"}
        self.assertIsNone(component_monitor.parse_search_snippet_reference(part,[bad]))

    def test_reference_prices_never_claim_to_be_bf_actual_or_buy_now(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        self.assertFalse(plan["bf_actual_authorized"])
        self.assertNotIn("BUY_NOW", json.dumps(plan))
        self.assertIn("比較サイト価格", planner.render_plan_markdown(plan))
        self.assertIn("公式BF実売価格ではありません", planner.render_plan_markdown(plan))

    def test_latest_section_insertion_is_idempotent(self):
        text = "# title\n\n## 監視中の最高スコア候補\n"
        section = planner.section_from_plan(planner.build_plan(self.config, {"products":[]}, now=NOW))
        once = planner.insert_section(text, section)
        twice = planner.insert_section(once, section)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(planner.START_MARKER), 1)
        self.assertEqual(once.count(planner.END_MARKER), 1)


if __name__ == "__main__":
    unittest.main()
