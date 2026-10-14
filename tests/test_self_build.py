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
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_pc_total_jpy"], 320360)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_pc_total_jpy"], 295360)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_pc_total_jpy"], 329360)
        self.assertEqual(builds["gpu-rtx5070-12gb"]["target_all_in_jpy"], 390160)
        self.assertEqual(builds["gpu-rtx5060ti-16gb"]["target_all_in_jpy"], 365160)
        self.assertEqual(builds["gpu-rtx5070ti-16gb"]["target_all_in_jpy"], 399160)
        self.assertTrue(plan["budget_arithmetic_valid"])
        self.assertFalse(plan["buy_now_authorized"])

    def test_gpu_options_are_mutually_exclusive_and_categories_unique(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        for build in plan["builds"]:
            self.assertEqual([x["id"] for x in build["components"] if x["category"] == "gpu"], [build["gpu_choice_id"]])
            categories = [x["category"] for x in build["components"]]
            self.assertEqual(len(categories), len(set(categories)))
            self.assertTrue(set(self.config["profile"]["required_categories"]).issubset(categories))

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
            ({"identity_match":True,"pit_valid":False},"2026-11-20T12:00:00+09:00")
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

    def test_primary_known_geometry_passes_but_other_gpu_sizes_need_review(self):
        plan = planner.build_plan(self.config, {"products":[]}, now=NOW)
        by_gpu = {x["gpu_choice_id"]:x for x in plan["builds"]}
        self.assertEqual(by_gpu["gpu-rtx5070-12gb"]["compatibility_status"], "PASS")
        self.assertEqual(by_gpu["gpu-rtx5060ti-16gb"]["compatibility_status"], "REVIEW")
        self.assertEqual(by_gpu["gpu-rtx5070ti-16gb"]["compatibility_status"], "REVIEW")

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
        part = self.parts["cpu-ryzen7-9700x"]
        with patch.object(component_monitor, "ddg_search", side_effect=TimeoutError("blocked")), patch.object(component_monitor, "bing_search", return_value=[]):
            result = component_monitor.search_comparison_snippet(part, ("kakaku.com",))
        self.assertIsNotNone(result)
        diagnostics = result["search_diagnostics"]
        self.assertEqual(len(diagnostics), 4)
        self.assertEqual(diagnostics[0]["status"], "error")
        self.assertEqual(diagnostics[0]["provider"], "duckduckgo")
        self.assertEqual(diagnostics[1]["result_count"], 0)
        self.assertNotIn("price_jpy", result)

    def test_search_fallback_tries_alternate_query_and_preserves_display_only_source(self):
        part = self.parts["cpu-ryzen7-9700x"]
        result_row = {
            "url": part["monitor_url"],
            "title": "AMD Ryzen 7 9700X BOX 価格比較",
            "snippet": "型番 100-100001404WOF 最安価格 ¥39,980",
        }
        with patch.object(component_monitor, "ddg_search", side_effect=[[], [result_row]]), patch.object(component_monitor, "bing_search", return_value=[]):
            result = component_monitor.search_comparison_snippet(part, ("kakaku.com",))
        self.assertEqual(result["price_jpy"], 39980)
        self.assertEqual(result["search_provider"], "duckduckgo")
        self.assertEqual(result["source_role"], "comparison_site_search_snippet_reference")
        self.assertFalse(result["bf_actual_authorized"])
        self.assertEqual(len(result["search_diagnostics"]), 2)
        self.assertEqual(result["search_diagnostics"][0]["result_count"], 0)

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
