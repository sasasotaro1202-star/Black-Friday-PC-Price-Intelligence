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

    def test_target_totals_and_all_in_budget(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        builds = {x["gpu_choice_id"]:x for x in plan["builds"]}
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_pc_total_jpy"], 305160)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_pc_total_jpy"], 285160)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_pc_total_jpy"], 329360)
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_all_in_jpy"], 374960)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_all_in_jpy"], 354960)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_all_in_jpy"], 399160)
        self.assertTrue(plan["budget_arithmetic_valid"])
        self.assertFalse(plan["buy_now_authorized"])

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

    def test_manual_os_reference_cannot_be_mixed_into_live_market_estimate(self):
        rows = self._verified_hardware_rows(self.config)
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
        self.assertEqual(os_row["display_reference_price_jpy"], 19360)
        self.assertEqual(os_row["price_status"], "manual_reference_unverified")
        self.assertFalse(os_row["trusted_for_market_estimate"])
        report = planner.render_plan_markdown(plan)
        self.assertIn("19,360（手動参考・現行未確認）", report)

    def test_fresh_identity_verified_manual_reference_can_complete_estimate(self):
        config = json.loads(json.dumps(self.config))
        os_part = next(x for x in config["parts"] if x["id"] == "os-windows11-home")
        os_part.update({
            "reference_price_is_current_verified": True,
            "reference_price_identity_verified": True,
            "reference_price_checked_at": NOW.isoformat(),
            "reference_price_url": "https://www.microsoft.com/ja-jp/store/",
        })
        rows = self._verified_hardware_rows(config)
        plan = planner.build_plan(
            config, {"generated_at": NOW.isoformat(), "products": rows}, now=NOW
        )
        build = next(x for x in plan["builds"] if x["gpu_choice_id"] == "gpu-rtx5070-12gb")
        self.assertEqual(build["market_reference_estimate_jpy"], build["target_pc_total_jpy"])
        self.assertTrue(build["market_reference_coverage_complete"])
        self.assertEqual(build["market_reference_coverage_count"], 9)
        self.assertNotIn("os-windows11-home", build["missing_or_untrusted_market_reference_ids"])
        os_row = next(x for x in build["components"] if x["id"] == "os-windows11-home")
        self.assertEqual(os_row["price_status"], "verified_manual_reference")
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
        self.assertEqual(by_gpu["gpu-rtx5070-12gb"]["compatibility_status"], "PASS")
        self.assertEqual(by_gpu["gpu-rtx5060ti-16gb"]["compatibility_status"], "PASS")
        self.assertEqual(by_gpu["gpu-rtx5070ti-16gb"]["compatibility_status"], "REVIEW")
        for gpu_id in ("gpu-rtx5070-12gb", "gpu-rtx5060ti-16gb"):
            checks = {x["check"]: x["status"] for x in by_gpu[gpu_id]["compatibility_checks"]}
            self.assertEqual(checks["gpu_slot_thickness"], "PASS")
        dark_checks = {x["check"]: x["status"] for x in by_gpu["gpu-rtx5070ti-16gb"]["compatibility_checks"]}
        self.assertEqual(dark_checks["gpu_slot_thickness"], "REVIEW")

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
