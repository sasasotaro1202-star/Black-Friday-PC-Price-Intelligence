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
    def test_component_snapshot_coverage_counts_verified_retailer_and_market_prices_separately(self):
        parts = [
            {"id": "cpu", "track_price": True},
            {"id": "board", "track_price": True},
            {"id": "gpu", "track_price": True},
            {"id": "ram", "track_price": True},
            {"id": "excluded", "track_price": False},
        ]
        stamp = "2026-11-02T08:00:00+09:00"
        rows = [
            {
                "id": "cpu", "price_validation_status": "verified_market_reference",
                "identity_match": True, "bf_actual_authorized": False,
                "market_reference_price_jpy": 47800, "pit_valid": True,
                "available_at": stamp, "retrieval_time": stamp,
            },
            {
                "id": "board", "price_validation_status": "verified_retailer_listing_reference",
                "identity_match": True, "bf_actual_authorized": False,
                "retailer_listing_reference_price_jpy": 19980,
                "retailer_listing_offer": {
                    "source_role": "direct_retailer_listing_reference",
                    "identity_match": True, "bf_actual_authorized": False,
                    "pit_valid": True, "price_source_mode": "direct_structured",
                    "price_jpy": 19980, "available_at": stamp, "retrieval_time": stamp,
                },
            },
            {
                "id": "gpu", "price_validation_status": "search_snippet_reference",
                "identity_match": True, "bf_actual_authorized": False,
                "search_snippet_identity_anchor": "VCG507012DFSXPB1-O",
                "search_snippet_reference_price_jpy": 138800,
            },
            {
                "id": "ram", "price_validation_status": "identity_unverified",
                "identity_match": False, "fetch_status": "error",
            },
        ]
        with patch.object(planner, "file_sha256", return_value="snapshot-hash"):
            coverage = planner.component_snapshot_coverage(
                parts, rows, {"generated_at": stamp, "source_role": "comparison_site_reference"}
            )
        self.assertEqual(coverage["configured_component_count"], 5)
        self.assertEqual(coverage["tracked_hardware_part_count"], 4)
        self.assertEqual(coverage["snapshot_verified_count"], 2)
        self.assertEqual(coverage["snapshot_verified_market_reference_count"], 1)
        self.assertEqual(coverage["snapshot_verified_retailer_listing_reference_count"], 1)
        self.assertEqual(coverage["snapshot_search_snippet_reference_count"], 1)
        self.assertEqual(coverage["snapshot_unverified_or_missing_count"], 1)
        self.assertEqual(coverage["snapshot_identity_unverified_count"], 1)
        self.assertEqual(coverage["snapshot_fetch_error_count"], 1)
        self.assertEqual(coverage["snapshot_sha256"], "snapshot-hash")

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

    def test_budget_tier_ceilings_match_explicit_350_400_450_policy(self):
        profile = {
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "soft_overrun_allowance_jpy": 20000,
            "budget_scenarios": [
                {"id": "budget_350k", "total_budget_jpy": 350000,
                 "soft_overrun_allowance_jpy": 0, "soft_ceiling_total_jpy": 350000},
                {"id": "budget_400k", "total_budget_jpy": 400000,
                 "soft_overrun_allowance_jpy": 20000, "soft_ceiling_total_jpy": 420000},
                {"id": "budget_450k", "total_budget_jpy": 450000,
                 "soft_overrun_allowance_jpy": 0, "soft_ceiling_total_jpy": 450000},
            ],
            "budget_build_candidates": [],
        }
        with patch.object(planner, "score_and_rank_builds", return_value=[]):
            result = planner.build_budget_scenarios(profile, {}, {}, None, 360)
        by_id = {row["id"]: row for row in result}
        self.assertEqual(by_id["budget_350k"]["soft_ceiling_total_jpy"], 350000)
        self.assertEqual(by_id["budget_400k"]["soft_ceiling_total_jpy"], 420000)
        self.assertEqual(by_id["budget_450k"]["soft_ceiling_total_jpy"], 450000)
        self.assertEqual(by_id["budget_350k"]["soft_overrun_allowance_jpy"], 0)
        self.assertEqual(by_id["budget_400k"]["soft_overrun_allowance_jpy"], 20000)
        self.assertEqual(by_id["budget_450k"]["soft_overrun_allowance_jpy"], 0)

    def test_unconfigured_budget_tier_does_not_inherit_global_400k_allowance(self):
        profile = {
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "soft_overrun_allowance_jpy": 20000,
            "budget_scenarios": [{"id": "budget_300k", "total_budget_jpy": 300000}],
            "budget_build_candidates": [],
        }
        with patch.object(planner, "score_and_rank_builds", return_value=[]):
            result = planner.build_budget_scenarios(profile, {}, {}, None, 360)
        self.assertEqual(result[0]["soft_overrun_allowance_jpy"], 0)
        self.assertEqual(result[0]["soft_ceiling_total_jpy"], 300000)

    def test_candidate_above_350k_ceiling_remains_visible_as_over_budget_only(self):
        part_ids = ["cpu", "board", "gpu", "ram", "ssd", "psu", "case", "os"]
        categories = {
            "cpu": "cpu", "board": "motherboard", "gpu": "gpu", "ram": "memory",
            "ssd": "storage", "psu": "psu", "case": "case", "os": "os_license",
        }
        parts = {
            part_id: {
                "id": part_id,
                "category": categories[part_id],
                "name": part_id.upper(),
                "target_price_jpy": 39625,
                "track_price": True,
                "specs": {},
                "purchase_url": "https://shop.example/" + part_id,
                "monitor_url": "https://shop.example/" + part_id,
            }
            for part_id in part_ids
        }
        parts["cpu"]["specs"] = {"cores": 8, "threads": 16, "cooler_included": True}
        parts["gpu"]["specs"] = {"vram_gb": 16}
        parts["ram"]["specs"] = {"capacity_gb": 32, "modules": 2}
        parts["ssd"]["specs"] = {"capacity_gb": 1000}
        profile = {
            "minimum_ram_gb": 32,
            "minimum_ssd_gb": 1000,
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "soft_overrun_allowance_jpy": 20000,
            "budget_scenarios": [{
                "id": "budget_350k",
                "total_budget_jpy": 350000,
                "soft_overrun_allowance_jpy": 0,
                "soft_ceiling_total_jpy": 350000,
            }],
            "budget_build_candidates": [{
                "id": "350k-over",
                "budget_tier_jpy": 350000,
                "part_ids": part_ids,
                "cpu_part_id": "cpu",
                "motherboard_part_id": "board",
                "gpu_choice_id": "gpu",
                "memory_part_id": "ram",
                "storage_part_id": "ssd",
                "psu_part_id": "psu",
                "case_part_id": "case",
                "cooler_included_by_cpu": True,
                "peripheral_budget_jpy": 35000,
                "unallocated_contingency_jpy": 5000,
                "build_shipping_reserve_jpy": 6000,
                "small_parts_reserve_jpy": 3000,
                "name": "35万円比較用の超過案",
            }],
        }
        empty_price = {
            "market_reference_price_jpy": None,
            "display_reference_price_jpy": None,
            "price_status": "missing",
            "trusted_for_market_estimate": False,
            "retrieval_time": None,
            "reference_source_url": None,
            "purchase_url": None,
            "early_buy_review": {},
            "direct_listing_display_price_jpy": None,
            "direct_listing_display_url": None,
            "direct_listing_display_title": None,
            "direct_listing_display_stock_status": "unknown",
            "direct_listing_sellable_price_jpy": None,
            "direct_listing_sellable_stock_status": "unknown",
            "direct_listing_stock_counts": {},
        }
        with (
            patch.object(planner, "component_price", return_value=empty_price),
            patch.object(planner, "compatibility_checks", return_value=("PASS", [])),
            patch.object(planner, "assess_workload_fit", return_value={}),
            patch.object(planner, "score_and_rank_builds", return_value=[]),
        ):
            result = planner.build_budget_scenarios(profile, parts, {}, None, 360)
        candidates = result[0]["builds"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["target_all_in_jpy"], 366000)
        self.assertFalse(candidates[0]["within_scenario_target"])
        self.assertFalse(candidates[0]["within_soft_band"])
        self.assertEqual(candidates[0]["decision"], "OVER_SOFT_BUDGET_BAND")
        self.assertEqual(candidates[0]["target_soft_overrun_jpy"], 16000)

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
