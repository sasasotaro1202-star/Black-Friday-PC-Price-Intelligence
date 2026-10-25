import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

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

    @patch.object(planner, "peripheral_budget_projection", return_value={
        "pc_dynamic_cap_jpy": 355900,
        "peripheral_projection_jpy": 39100,
        "budget_data_ready": False,
        "tracked_peripheral_unverified_ids": ["monitor", "mouse"],
        "channel_comparison_pending_count": 4,
    })
    def test_section_distinguishes_target_cap_dynamic_cap_and_soft_cap(self, _projection):
        plan = {
            "total_budget_jpy": 400000,
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "pc_budget_jpy": 395000,
            "pc_target_jpy": 360000,
            "soft_ceiling_total_jpy": 420000,
            "pc_planned_budget_jpy": 380000,
            "builds": [],
        }
        rendered = planner.section_from_plan(plan)
        self.assertIn("40万円の基準総額に基づくPC本体上限は ¥360,000", rendered)
        self.assertIn("最新の周辺機器コスト試算は ¥39,100", rendered)
        self.assertIn("動的上限は ¥355,900", rendered)
        self.assertIn("比較用PC本体上限は ¥380,000", rendered)
        self.assertIn("周辺機器の価格・購入ルート検証は 未完了", rendered)
        self.assertIn("未確認対象 2 件", rendered)
        self.assertIn("購入許可も意味しません", rendered)

    @patch.object(planner, "peripheral_budget_projection", return_value={})
    def test_section_never_substitutes_zero_when_current_projection_is_missing(self, _projection):
        rendered = planner.section_from_plan({"builds": []})
        self.assertIn("PC本体の動的上限は 未確認", rendered)
        self.assertIn("最新の周辺機器コスト試算は 未確認", rendered)
        self.assertNotIn("動的上限は ¥0", rendered)

    def test_section_warns_when_stored_soft_cap_disagrees_with_budget_arithmetic(self):
        with patch.object(planner, "peripheral_budget_projection", return_value={}):
            rendered = planner.section_from_plan({
                "total_budget_jpy": 400000,
                "peripheral_budget_jpy": 35000,
                "unallocated_contingency_jpy": 5000,
                "pc_budget_jpy": 395000,
                "soft_ceiling_total_jpy": 410000,
                "pc_planned_budget_jpy": 380000,
                "builds": [],
            })
        self.assertIn("保存済み許容帯上限 ¥380,000", rendered)
        self.assertIn("算式による再計算値 ¥370,000", rendered)

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
