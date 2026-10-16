import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import intelligence
import report


class BudgetPolicyTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / "config" / "targets.json").open(encoding="utf-8") as f:
            self.cfg = json.load(f)

    def test_peripheral_report_heading_matches_configured_purchase_items(self):
        heading = report.peripheral_monitor_section_heading(self.cfg)
        self.assertIn("メインモニター1台", heading)
        self.assertIn("サブモニターなし", heading)
        self.assertIn("ヘッドセットなし", heading)

        with_secondary = dict(self.cfg)
        with_secondary["peripherals"] = list(self.cfg["peripherals"]) + [{
            "id": "secondary_monitor",
            "category": "secondary_monitor",
            "mandatory": True,
        }]
        self.assertIn(
            "サブモニターあり",
            report.peripheral_monitor_section_heading(with_secondary),
        )

    def test_all_in_budget_arithmetic(self):
        self.assertEqual(self.cfg["total_budget_jpy"], 400000)
        self.assertEqual(self.cfg["peripheral_budget_jpy"], 45000)
        self.assertEqual(self.cfg["pc_target_jpy"], 350000)
        self.assertEqual(self.cfg["pc_budget_jpy"], 350000)
        self.assertEqual(self.cfg["pc_budget_jpy"] + self.cfg["peripheral_budget_jpy"] + self.cfg["unallocated_contingency_jpy"], self.cfg["total_budget_jpy"])

    def test_purchase_strategy_matches_40man_target_and_speaker_goal(self):
        strategy = self.cfg["purchase_strategy"]
        self.assertEqual(self.cfg["total_budget_jpy"], 400000)
        self.assertEqual(self.cfg["peripheral_budget_jpy"], 45000)
        self.assertEqual(self.cfg["pc_target_jpy"], 350000)
        self.assertEqual(self.cfg["pc_budget_jpy"], 350000)
        self.assertEqual(self.cfg["pc_target_jpy"] - 279800, 70200)
        self.assertEqual(self.cfg["pc_budget_jpy"] - 279800, 70200)
        self.assertEqual(next(x for x in self.cfg["peripherals"] if x["id"] == "speakers")["target_price_jpy"], 12000)
        self.assertNotIn("secondary_monitor", {x["id"] for x in self.cfg["peripherals"]})
        self.assertEqual(strategy["priority_plans"][0]["candidate_id"], "desktop-gtune-dg-i5g70-5070")
        self.assertEqual(strategy["priority_plans"][1]["last_verified_listing_reference_jpy"], 304800)
        self.assertFalse(strategy["outlier_rule"]["zero_cost_upgrade_assumption_allowed"])

    def test_budget_notes_and_dark_horse_caps_match_40man_policy(self):
        strategy = self.cfg["purchase_strategy"]
        self.assertIn("40万円", strategy["purpose"])
        self.assertNotIn("38万円", strategy["purpose"])
        self.assertEqual(strategy["outlier_rule"]["black_friday_target_cap_jpy"], self.cfg["pc_target_jpy"])
        self.assertEqual(strategy["ai_vram_outlier_rule"]["black_friday_target_cap_jpy"], self.cfg["pc_target_jpy"])
        for plan in strategy["priority_plans"]:
            self.assertEqual(plan["black_friday_target_price_jpy"], self.cfg["pc_target_jpy"])
            self.assertEqual(plan["black_friday_planned_hard_cap_jpy"], self.cfg["pc_target_jpy"])
            self.assertIn("350,000円", plan["black_friday_target_note"])
            self.assertNotIn("310,200円", plan["black_friday_target_note"])
        notes_by_candidate = {x["candidate_id"]: x["black_friday_target_note"] for x in strategy["priority_plans"]}
        self.assertIn("目標との差額45,200円", notes_by_candidate["desktop-gtune-dg-a7g70-5070"])
        self.assertIn("余地は50,200円", notes_by_candidate["desktop-gtune-dg-i7g70-5070"])
        self.assertIn("差は40,200円", notes_by_candidate["desktop-gtune-fg-a7g6t-5060ti16"])

    def test_dg_i7g70_high_cpu_outlier_is_explicitly_tracked(self):
        strategy = self.cfg["purchase_strategy"]
        plan = next(x for x in strategy["priority_plans"] if x["candidate_id"] == "desktop-gtune-dg-i7g70-5070")
        self.assertEqual(plan["role"], "higher_cpu_configuration_upgrade")
        self.assertEqual(plan["baseline_price_jpy"], 299800)
        self.assertEqual((plan["baseline_ram_gb"], plan["baseline_ssd_gb"]), (16, 500))
        self.assertEqual((plan["target_ram_gb"], plan["target_ssd_gb"]), (32, 1000))
        self.assertEqual(plan["black_friday_target_price_jpy"], 350000)
        self.assertEqual(plan["black_friday_planned_hard_cap_jpy"], 350000)
        self.assertIn("確定価格", plan["required_quote"])

    def test_upgrade_headroom_recalculates_from_latest_verified_base_price(self):
        strategy = self.cfg["purchase_strategy"]
        item = {
            "id": "desktop-gtune-dg-i7g70-5070",
            "name": "G TUNE DG-I7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dgi7g70b8bgdw102decrise/",
            "form_factor": "desktop",
            "current_price_jpy": 260000,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "pit_valid": True,
            "stock_status": "in_stock",
            "retrieval_time": "2026-10-10T10:00:00+09:00",
            "available_at": "2026-10-10T10:00:00+09:00",
            "spec": {"ram_gb": 16, "ssd": "500 GB", "gpu": "RTX 5070", "cpu": "Core Ultra 7"},
        }
        result = report.build_purchase_strategy_status(
            [item],
            strategy,
            {
                "total_budget_jpy": 400000,
                "peripheral_budget_jpy": 45000,
                "pc_target_jpy": 350000,
                "pc_budget_jpy": 350000,
            },
            {"budget_data_ready": False, "pc_dynamic_cap_jpy": 0},
        )
        row = next(x for x in result["rows"] if x.get("candidate_id") == "desktop-gtune-dg-i7g70-5070")
        self.assertEqual(row["upgrade_headroom_basis_price_jpy"], 260000)
        self.assertEqual(row["max_upgrade_cost_to_bf_target_jpy"], 90000)
        self.assertEqual(row["max_upgrade_cost_to_bf_hard_cap_jpy"], 90000)
        self.assertFalse(row["configuration_ready"])

    def test_dg_a7g70_catalog_uses_exact_outlet_model_and_completed_specs(self):
        with (ROOT / "config" / "candidate_catalog.json").open(encoding="utf-8") as f:
            catalog = json.load(f)["candidates"]
        candidate = next(x for x in catalog if x["id"] == "desktop-gtune-dg-a7g70-5070")
        self.assertEqual(candidate["url"], "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/")
        self.assertIn("DGA7G70B5BBDW101DECWA", candidate["aliases"])
        self.assertEqual(candidate["ram_gb"], 32)
        self.assertEqual(candidate["ssd"], "1 TB")
        self.assertEqual(candidate["reference_price_jpy"], 304800)

    def test_peripheral_targets_sum_to_budget_and_no_unwanted_devices(self):
        self.assertEqual(sum(int(x["target_price_jpy"]) for x in self.cfg["peripherals"] if x.get("mandatory", True)), self.cfg["peripheral_budget_jpy"])
        ids = {x["id"] for x in self.cfg["peripherals"]}
        self.assertNotIn("headset", ids)
        self.assertNotIn("secondary_monitor", ids)
        self.assertEqual(len([x for x in self.cfg["peripherals"] if x["id"] == "main_monitor"]), 1)
        self.assertEqual(len([x for x in self.cfg["peripherals"] if x["id"] == "main_monitor"]), 1)

    def test_each_accessory_category_has_three_scored_distinct_options(self):
        primary = self.cfg.get("peripherals", [])
        alternatives = self.cfg.get("peripheral_alternatives", [])
        all_items = primary + alternatives
        categories = self.cfg.get("peripheral_ranking_policy", {}).get("category_order", [])
        self.assertGreaterEqual(len(categories), 6)
        all_ids = [str(x.get("id")) for x in all_items if x.get("id")]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        for group in categories:
            category = group["category"]
            rows = [x for x in all_items if x.get("category") == category]
            self.assertGreaterEqual(len(rows), 3, category)
            scores = [x.get("ranking_score_100") for x in rows]
            self.assertTrue(all(isinstance(s, int) and 0 <= s <= 100 for s in scores), category)
        g304x = next(x for x in alternatives if x.get("id") == "mouse_alt_logicool_g304_x_superlight")
        self.assertIn("59g", g304x.get("ranking_reason", ""))
        g640 = next(x for x in alternatives if x.get("id") == "mousepad_alt_logicool_g640s")
        self.assertEqual(g640.get("model_code"), "G640")
        self.assertIn("gaming.logicool.co.jp/ja-jp/shop/p/g640-cloth-gaming-mouse-pad", g640.get("purchase_url", ""))

    def test_tracked_peripherals_have_identity_and_host_guard(self):
        tracked = [x for x in self.cfg["peripherals"] if x.get("track_current_price")]
        self.assertGreaterEqual(len(tracked), 4)
        for p in tracked:
            self.assertTrue(p.get("monitor_url"))
            self.assertTrue(p.get("identity_terms"))
            self.assertTrue(p.get("allowed_hosts"))
            self.assertTrue(p["monitor_url"].startswith("https://"))

    def test_intelligence_uses_pc_only_budget(self):
        self.assertEqual(intelligence.TOTAL_BUDGET, 400000)
        self.assertEqual(intelligence.PERIPHERAL_BUDGET, 45000)
        self.assertEqual(intelligence.BUDGET, 350000)
        self.assertEqual(intelligence.PC_BUDGET, 350000)

    def test_incomplete_pc_base_config_is_not_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 16, "ssd": "500 GB"}})
        self.assertFalse(ready)
        self.assertEqual(len(reasons), 2)

    def test_full_pc_config_is_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 32, "ssd": "1 TB"}})
        self.assertTrue(ready)
        self.assertEqual(reasons, [])

    def test_outlet_reference_above_target_is_not_reported_as_negative_discount(self):
        from datetime import datetime
        strategy = self.cfg["purchase_strategy"]
        policy = {
            "total_budget_jpy": 400000,
            "peripheral_budget_jpy": 45000,
            "pc_target_jpy": 350000,
            "pc_budget_jpy": 350000,
        }
        with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-10-10T10:00:00+09:00")):
            result = report.build_purchase_strategy_status(
                [],
                strategy,
                policy,
                {"budget_data_ready": False, "pc_dynamic_cap_jpy": 0},
            )
        row = next(x for x in result["rows"] if x.get("role") == "secondary_outlet_complete_configuration")
        self.assertIn("BF目標を¥45,200下回っています", row["detail"])
        self.assertNotIn("¥-", row["detail"])

    def test_verified_price_with_unknown_stock_is_budgeted_but_not_actionable(self):
        now_text = intelligence.iso(intelligence.now_jst())
        products = []
        for target in self.cfg["peripherals"]:
            if not target.get("track_current_price"):
                continue
            products.append({
                "id": target["id"],
                "name": target["name"],
                "current_price_jpy": target["target_price_jpy"],
                "last_valid_price_jpy": target["target_price_jpy"],
                "price_verified": True,
                "identity_verified": True,
                "stock_status": "in_stock",
                "retrieval_time": now_text,
                "available_at": now_text,
            })
        speaker = next(x for x in products if x["id"] == "speakers")
        speaker["current_price_jpy"] = 14980
        speaker["last_valid_price_jpy"] = 14980
        speaker["stock_status"] = "unknown"
        snapshot = {"generated_at": now_text, "products": products}
        original_load_json = intelligence.load_json

        def deterministic_load_json(path, default):
            if str(path).endswith("data/peripheral_prices.json"):
                return snapshot
            return original_load_json(path, default)

        with patch.object(intelligence, "load_json", side_effect=deterministic_load_json):
            projection = intelligence.peripheral_budget_projection()

        speaker_row = next(x for x in projection["peripherals"] if x["id"] == "speakers")
        self.assertEqual(projection["peripheral_projection_jpy"], 47980)
        self.assertEqual(projection["pc_dynamic_cap_jpy"], 347020)
        self.assertIn("speakers", projection["tracked_peripheral_unverified_ids"])
        self.assertFalse(projection["budget_data_ready"])
        self.assertIsNone(speaker_row["current_price_jpy"])
        self.assertEqual(speaker_row["online_comparison_price_jpy"], 14980)
        self.assertFalse(speaker_row["store_price_confirmed"])
        self.assertEqual(speaker_row["budget_cost_jpy"], 14980)
        self.assertEqual(speaker_row["cost_basis"], "online_reference_store_price_unconfirmed")

    def test_branch_inventory_is_separate_from_verified_store_cash_price(self):
        now_text = intelligence.iso(intelligence.now_jst())
        main_target = next(x for x in self.cfg["peripherals"] if x["id"] == "main_monitor")
        check = main_target["store_inventory_checks"][0]
        product_rows = []
        for target in self.cfg["peripherals"]:
            if not target.get("track_current_price"):
                continue
            product = {
                "id": target["id"],
                "name": target["name"],
                "current_price_jpy": target["target_price_jpy"],
                "last_valid_price_jpy": target["target_price_jpy"],
                "price_verified": True,
                "identity_verified": True,
                "stock_status": "in_stock",
                "retrieval_time": now_text,
                "available_at": now_text,
                "store_inventory_observations": [],
            }
            if target["id"] == "main_monitor":
                product["current_price_jpy"] = 20790
                product["last_valid_price_jpy"] = 20790
                product["store_inventory_observations"] = [{
                    "store_id": "biccamera_tenjin_1",
                    "store_name": "ビックカメラ天神1号館",
                    "checked_at": now_text,
                    "check_url": check["url"],
                    "source_url": check["url"],
                    "source_type": "official_branch_stock_page",
                    "status": "low_stock",
                    "verified": True,
                    "branch_match": True,
                    "model_match": True,
                    "evidence_notes": "Example fixture: branch pickup inventory only; no store cash price.",
                }]
            product_rows.append(product)
        snapshot = {"generated_at": now_text, "products": product_rows}
        original_load_json = intelligence.load_json

        def deterministic_load_json(path, default):
            if str(path).endswith("data/peripheral_prices.json"):
                return snapshot
            return original_load_json(path, default)

        with patch.object(intelligence, "load_json", side_effect=deterministic_load_json):
            projection = intelligence.peripheral_budget_projection()
        row = next(x for x in projection["peripherals"] if x["id"] == "main_monitor")
        self.assertEqual(row["store_inventory_status"], "low_stock")
        self.assertTrue(row["store_inventory_verified"])
        self.assertIsNone(row["current_price_jpy"])
        self.assertEqual(row["online_comparison_price_jpy"], 20790)
        self.assertFalse(row["store_price_confirmed"])
        self.assertFalse(projection["budget_data_ready"])

    def test_cached_price_for_previous_speaker_model_is_not_reused(self):
        now_text = intelligence.iso(intelligence.now_jst())
        products = []
        for target in self.cfg["peripherals"]:
            if not target.get("track_current_price"):
                continue
            products.append({
                "id": target["id"],
                "name": target["name"],
                "current_price_jpy": target["target_price_jpy"],
                "last_valid_price_jpy": target["target_price_jpy"],
                "price_verified": True,
                "identity_verified": True,
                "stock_status": "in_stock",
                "retrieval_time": now_text,
                "available_at": now_text,
            })
        speaker = next(x for x in products if x["id"] == "speakers")
        speaker["name"] = "Creative Pebble (classic) compact 2.0 USB-powered speakers"
        speaker["current_price_jpy"] = 2500
        speaker["last_valid_price_jpy"] = 2500
        snapshot = {"generated_at": now_text, "products": products}
        original_load_json = intelligence.load_json

        def deterministic_load_json(path, default):
            if str(path).endswith("data/peripheral_prices.json"):
                return snapshot
            return original_load_json(path, default)

        with patch.object(intelligence, "load_json", side_effect=deterministic_load_json):
            projection = intelligence.peripheral_budget_projection()

        speaker_row = next(x for x in projection["peripherals"] if x["id"] == "speakers")
        self.assertEqual(projection["peripheral_projection_jpy"], 45000)
        self.assertIn("speakers", projection["tracked_peripheral_unverified_ids"])
        self.assertFalse(projection["budget_data_ready"])
        self.assertIsNone(speaker_row["current_price_jpy"])
        self.assertFalse(speaker_row["price_verified"])
        self.assertEqual(speaker_row["budget_cost_jpy"], 12000)
        self.assertEqual(speaker_row["cost_basis"], "target_reserve_store_price_unconfirmed")

    def test_unverified_peripheral_snapshot_fails_purchase_readiness(self):
        tracked_ids = [
            p["id"] for p in self.cfg["peripherals"] if p.get("track_current_price")
        ]
        unknown_snapshot = {
            "generated_at": None,
            "products": [
                {
                    "id": pid,
                    "current_price_jpy": None,
                    "price_verified": False,
                    "stock_status": "unknown",
                }
                for pid in tracked_ids
            ],
        }
        original_load_json = intelligence.load_json

        def deterministic_load_json(path, default):
            if str(path).endswith("data/peripheral_prices.json"):
                return unknown_snapshot
            return original_load_json(path, default)

        with patch.object(intelligence, "load_json", side_effect=deterministic_load_json):
            projection = intelligence.peripheral_budget_projection()

        self.assertFalse(projection["budget_data_ready"])
        self.assertEqual(projection["tracked_peripheral_unverified_ids"], sorted(tracked_ids))
        self.assertEqual(projection["peripheral_projection_jpy"], 45000)
        self.assertEqual(projection["pc_dynamic_cap_jpy"], 350000)
        self.assertLessEqual(
            projection["pc_dynamic_cap_jpy"] + projection["peripheral_projection_jpy"],
            projection["total_budget_jpy"],
        )


    def test_every_tracked_peripheral_has_rank_score_reason_and_unique_identity(self):
        all_targets = self.cfg["peripherals"] + self.cfg.get("peripheral_alternatives", [])
        ids = [x.get("id") for x in all_targets]
        self.assertEqual(len(ids), len(set(ids)))
        tracked = [x for x in all_targets if x.get("track_current_price")]
        self.assertGreaterEqual(len(tracked), 10)
        for item in tracked:
            self.assertTrue(0 <= int(item.get("ranking_score_100", -1)) <= 100, item.get("id"))
            self.assertTrue(item.get("ranking_reason"), item.get("id"))
            self.assertTrue(item.get("purchase_url") or item.get("monitor_url"), item.get("id"))
        policy = self.cfg.get("peripheral_ranking_policy", {})
        self.assertEqual(sum(int(x["weight_pct"]) for x in policy.get("factors", [])), 100)
        self.assertFalse(next(x for x in self.cfg["peripheral_alternatives"] if x["id"] == "cables_alt_sanwa_kc_dp1420")["mandatory"])

    def test_configured_peripheral_targets_sum_to_all_in_budget_allocation(self):
        mandatory = [
            p for p in self.cfg["peripherals"]
            if p.get("mandatory", True)
        ]
        target_sum = sum(int(p.get("target_price_jpy") or 0) for p in mandatory)
        self.assertEqual(target_sum, int(self.cfg["peripheral_budget_jpy"]))
        self.assertEqual(
            int(self.cfg["pc_target_jpy"]) + int(self.cfg["peripheral_budget_jpy"]) + int(self.cfg["unallocated_contingency_jpy"]),
            int(self.cfg["total_budget_jpy"]),
        )
        self.assertEqual(int(self.cfg["pc_budget_jpy"]), int(self.cfg["pc_target_jpy"]))


if __name__ == "__main__":
    unittest.main()
