import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import intelligence


class BudgetPolicyTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / "config" / "targets.json").open(encoding="utf-8") as f:
            self.cfg = json.load(f)

    def test_all_in_budget_arithmetic(self):
        self.assertEqual(self.cfg["total_budget_jpy"], 370000)
        self.assertEqual(self.cfg["peripheral_budget_jpy"], 45800)
        self.assertEqual(self.cfg["pc_target_jpy"], 321800)
        self.assertEqual(self.cfg["pc_budget_jpy"], 324200)
        self.assertEqual(self.cfg["pc_budget_jpy"] + self.cfg["peripheral_budget_jpy"], self.cfg["total_budget_jpy"])

    def test_purchase_strategy_matches_37man_budget_and_speaker_goal(self):
        strategy = self.cfg["purchase_strategy"]
        self.assertEqual(self.cfg["total_budget_jpy"], 370000)
        self.assertEqual(self.cfg["peripheral_budget_jpy"], 45800)
        self.assertEqual(self.cfg["pc_target_jpy"], 321800)
        self.assertEqual(self.cfg["pc_budget_jpy"], 324200)
        self.assertEqual(self.cfg["pc_target_jpy"] - 279800, 42000)
        self.assertEqual(self.cfg["pc_budget_jpy"] - 279800, 44400)
        self.assertEqual(next(x for x in self.cfg["peripherals"] if x["id"] == "speakers")["target_price_jpy"], 10000)
        self.assertEqual(strategy["priority_plans"][0]["candidate_id"], "desktop-gtune-dg-i5g70-5070")
        self.assertEqual(strategy["priority_plans"][1]["last_verified_listing_reference_jpy"], 304800)
        self.assertFalse(strategy["outlier_rule"]["zero_cost_upgrade_assumption_allowed"])

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

    def test_tracked_peripherals_have_identity_and_host_guard(self):
        tracked = [x for x in self.cfg["peripherals"] if x.get("track_current_price")]
        self.assertGreaterEqual(len(tracked), 4)
        for p in tracked:
            self.assertTrue(p.get("monitor_url"))
            self.assertTrue(p.get("identity_terms"))
            self.assertTrue(p.get("allowed_hosts"))
            self.assertTrue(p["monitor_url"].startswith("https://"))

    def test_intelligence_uses_pc_only_budget(self):
        self.assertEqual(intelligence.TOTAL_BUDGET, 370000)
        self.assertEqual(intelligence.PERIPHERAL_BUDGET, 45800)
        self.assertEqual(intelligence.BUDGET, 321800)
        self.assertEqual(intelligence.PC_BUDGET, 324200)

    def test_incomplete_pc_base_config_is_not_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 16, "ssd": "500 GB"}})
        self.assertFalse(ready)
        self.assertEqual(len(reasons), 2)

    def test_full_pc_config_is_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 32, "ssd": "1 TB"}})
        self.assertTrue(ready)
        self.assertEqual(reasons, [])

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
        self.assertEqual(projection["peripheral_projection_jpy"], 45800)
        self.assertEqual(projection["pc_dynamic_cap_jpy"], 324200)
        self.assertLessEqual(
            projection["pc_dynamic_cap_jpy"] + projection["peripheral_projection_jpy"],
            projection["total_budget_jpy"],
        )


if __name__ == "__main__":
    unittest.main()
