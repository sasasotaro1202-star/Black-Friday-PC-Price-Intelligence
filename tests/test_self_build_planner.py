import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("self_build_planner", SCRIPTS / "self_build_planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class SelfBuildRankingLinkTests(unittest.TestCase):
    def test_component_link_uses_purchase_page_and_encodes_parentheses(self):
        rendered = planner.component_markdown_link({
            "name": "GPU test",
            "purchase_url": "https://shop.example/item(model)",
            "monitor_url": "https://compare.example/item",
        })
        self.assertEqual(rendered, "[GPU test](https://shop.example/item%28model%29)")

    def test_component_link_falls_back_to_valid_monitor_url(self):
        rendered = planner.component_markdown_link({
            "name": "RAM test",
            "purchase_url": "javascript:alert(1)",
            "monitor_url": "https://compare.example/ram",
        })
        self.assertEqual(rendered, "[RAM test](https://compare.example/ram)")
        self.assertNotIn("javascript:", rendered)

    def test_component_without_valid_link_remains_visible_and_flagged(self):
        rendered = planner.component_markdown_link({
            "name": "Unlinked component",
            "purchase_url": "file:///etc/passwd",
            "monitor_url": None,
        })
        self.assertEqual(rendered, "Unlinked component（商品URL未登録・要修正）")

    def test_primary_ranking_row_includes_links_for_every_component(self):
        plan = {
            "builds": [{
                "rank": 1,
                "name": "Balanced build",
                "scorecard": {
                    "overall_score": 80.0,
                    "purchase_evidence_completeness_score_out_of_100": 45,
                },
                "target_pc_total_jpy": 300000,
                "target_all_in_jpy": 340000,
                "target_remaining_budget_jpy": 60000,
                "compatibility_status": "REVIEW",
                "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
                "components": [
                    {"name": "CPU test", "purchase_url": "https://shop.example/cpu"},
                    {"name": "GPU test", "purchase_url": "https://shop.example/gpu"},
                ],
            }],
        }
        rendered = planner.section_from_plan(plan)
        self.assertIn("|判定|全パーツ商品リンク|", rendered)
        self.assertIn("[CPU test](https://shop.example/cpu)", rendered)
        self.assertIn("[GPU test](https://shop.example/gpu)", rendered)

    def test_budget_scenario_component_breakdown_links_every_part(self):
        candidate = {
            "id": "test-build",
            "name": "Test build",
            "display_rank_within_tier": 1,
            "target_pc_total_jpy": 20000,
            "target_peripheral_budget_jpy": 35000,
            "target_contingency_jpy": 5000,
            "target_all_in_jpy": 60000,
            "target_remaining_budget_jpy": 340000,
            "target_overrun_jpy": 0,
            "target_remaining_soft_budget_jpy": 360000,
            "within_soft_band": True,
            "overall_score_100": 77.0,
            "current_sellable_stock_part_count": 0,
            "compatibility_status": "REVIEW",
            "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
            "purpose_note_ja": "test",
            "tradeoff_note_ja": "not a purchase quote",
            "components": [
                {"id": "cpu", "name": "CPU test", "category": "cpu",
                 "target_price_jpy": 10000, "purchase_url": "https://shop.example/cpu"},
                {"id": "gpu", "name": "GPU test", "category": "gpu",
                 "target_price_jpy": 10000, "purchase_url": "https://shop.example/gpu"},
            ],
        }
        plan = {
            "generated_at": "2026-10-20T00:00:00+09:00",
            "pc_target_jpy": 360000,
            "pc_planned_budget_jpy": 380000,
            "pc_budget_jpy": 395000,
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "total_budget_jpy": 400000,
            "soft_ceiling_total_jpy": 420000,
            "workload_profile": {},
            "builds": [],
            "budget_scenarios": [{
                "id": "budget_test",
                "total_budget_jpy": 400000,
                "soft_ceiling_total_jpy": 420000,
                "description_ja": "test",
                "builds": [candidate],
            }],
        }
        plan["builds"] = [{
            "rank": 1,
            "name": "Primary test build",
            "target_parts_subtotal_jpy": 20000,
            "target_pc_total_jpy": 30000,
            "target_all_in_jpy": 70000,
            "target_remaining_budget_jpy": 330000,
            "market_reference_estimate_jpy": None,
            "compatibility_status": "REVIEW",
            "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
            "components": candidate["components"],
        }]
        rendered = planner.render_plan_markdown(plan)
        self.assertIn("|判定|全パーツ商品リンク|", rendered)
        self.assertIn("[CPU test](https://shop.example/cpu)", rendered)
        self.assertIn("[GPU test](https://shop.example/gpu)", rendered)
        self.assertIn("- 部品目標の内訳: [CPU test](https://shop.example/cpu) ¥10,000", rendered)
        self.assertIn("[GPU test](https://shop.example/gpu) ¥10,000", rendered)


if __name__ == "__main__":
    unittest.main()
