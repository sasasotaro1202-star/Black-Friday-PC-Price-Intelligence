"""Regression tests for complete links in the DIY PC configuration rankings."""
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("self_build_planner_under_test", SCRIPTS / "self_build_planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class ComponentLinkRenderingTests(unittest.TestCase):
    def test_component_links_include_product_and_distinct_comparison_pages(self):
        links = planner.component_links_markdown([
            {"id": "cpu-test", "category": "cpu", "name": "Test CPU",
             "url": "https://shop.example.com/test-cpu",
             "monitor_url": "https://compare.example.com/test-cpu"},
            {"id": "gpu-test", "category": "gpu", "name": "Test GPU (OC)",
             "purchase_url": "https://shop.example.com/test-gpu(oc)",
             "monitor_url": "https://shop.example.com/test-gpu(oc)"},
            {"id": "os-test", "category": "os_license", "name": "Test OS",
             "purchase_url": "javascript:alert(1)"},
        ])
        self.assertIn("[商品ページ：Test CPU](https://shop.example.com/test-cpu)", links)
        self.assertIn("[価格比較](https://compare.example.com/test-cpu)", links)
        self.assertIn("[商品ページ：Test GPU （OC）](https://shop.example.com/test-gpu%28oc%29)", links)
        self.assertIn("OS Test OS：商品URL未登録（要修正）", links)
        self.assertNotIn("javascript:", links)

    def test_latest_ranking_section_lists_every_part_for_each_build(self):
        rendered = planner.section_from_plan({
            "pc_planned_budget_jpy": 360000,
            "pc_budget_jpy": 395000,
            "builds": [
                {"rank": 1, "name": "Build A",
                 "scorecard": {"overall_score": 80, "purchase_evidence_completeness_score_out_of_100": 50},
                 "target_pc_total_jpy": 340000, "target_all_in_jpy": 380000,
                 "target_remaining_budget_jpy": 20000, "compatibility_status": "REVIEW",
                 "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
                 "components": [
                     {"id": "cpu-a", "category": "cpu", "name": "CPU A", "url": "https://shop.example.com/cpu-a"},
                     {"id": "gpu-a", "category": "gpu", "name": "GPU A", "url": "https://shop.example.com/gpu-a"},
                 ]},
                {"rank": 2, "name": "Build B",
                 "scorecard": {"overall_score": 75, "purchase_evidence_completeness_score_out_of_100": 40},
                 "target_pc_total_jpy": 320000, "target_all_in_jpy": 360000,
                 "target_remaining_budget_jpy": 40000, "compatibility_status": "REVIEW",
                 "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
                 "components": [
                     {"id": "cpu-b", "category": "cpu", "name": "CPU B", "url": "https://shop.example.com/cpu-b"},
                 ]},
            ],
        })
        self.assertIn("### ランキング構成別・全パーツ商品リンク", rendered)
        self.assertIn("[商品ページ：CPU A](https://shop.example.com/cpu-a)", rendered)
        self.assertIn("[商品ページ：GPU A](https://shop.example.com/gpu-a)", rendered)
        self.assertIn("[商品ページ：CPU B](https://shop.example.com/cpu-b)", rendered)

    def test_budget_scenario_details_include_each_component_link(self):
        components = [
            {"id": "cpu-test", "name": "Test CPU", "category": "cpu",
             "purchase_url": "https://shop.example.com/test-cpu",
             "monitor_url": "https://compare.example.com/test-cpu", "target_price_jpy": 45000},
            {"id": "gpu-test", "name": "Test GPU", "category": "gpu",
             "purchase_url": "https://shop.example.com/test-gpu",
             "monitor_url": "https://shop.example.com/test-gpu", "target_price_jpy": 120000},
        ]
        rendered = planner.render_plan_markdown({
            "generated_at": "2026-10-20T00:00:00+09:00",
            "pc_target_jpy": 360000, "pc_planned_budget_jpy": 380000,
            "pc_budget_jpy": 395000, "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000, "total_budget_jpy": 400000,
            "soft_ceiling_total_jpy": 420000, "workload_profile": {},
            "memory_choice_selection": {"selected_name": "Test RAM", "selection_method": "test", "candidates": []},
            "storage_choice_selection": {"candidates": []},
            "cooler_choice_selection": {"candidates": []},
            "gpu_fallback_candidates_by_choice": {}, "builds": [],
            "budget_scenarios": [{
                "id": "budget_400k", "total_budget_jpy": 400000,
                "soft_ceiling_total_jpy": 420000, "description_ja": "Test scenario",
                "builds": [{
                    "display_rank_within_tier": 1, "name": "Test scenario build",
                    "components": components, "target_pc_total_jpy": 300000,
                    "target_peripheral_budget_jpy": 35000, "target_contingency_jpy": 5000,
                    "target_all_in_jpy": 340000, "target_remaining_budget_jpy": 60000,
                    "target_remaining_soft_budget_jpy": 80000, "target_overrun_jpy": 0,
                    "within_soft_band": True, "overall_score_100": 80,
                    "current_sellable_stock_part_count": 0,
                    "compatibility_status": "REVIEW", "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
                }],
            }],
        })
        self.assertIn("商品リンク（各構成パーツ）", rendered)
        self.assertIn("[商品ページ：Test CPU](https://shop.example.com/test-cpu)", rendered)
        self.assertIn("[価格比較](https://compare.example.com/test-cpu)", rendered)
        self.assertIn("[商品ページ：Test GPU](https://shop.example.com/test-gpu)", rendered)


if __name__ == "__main__":
    unittest.main()
