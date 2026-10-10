import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import intelligence


class BudgetPolicyTests(unittest.TestCase):
    def setUp(self):
        with (ROOT / "config" / "targets.json").open(encoding="utf-8") as f:
            self.cfg = json.load(f)

    def test_all_in_budget_arithmetic(self):
        self.assertEqual(self.cfg["total_budget_jpy"], 370000)
        self.assertEqual(self.cfg["peripheral_budget_jpy"], 67800)
        self.assertEqual(self.cfg["pc_target_jpy"], 299800)
        self.assertEqual(self.cfg["pc_budget_jpy"], 302200)
        self.assertEqual(self.cfg["pc_budget_jpy"] + self.cfg["peripheral_budget_jpy"], self.cfg["total_budget_jpy"])

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
        self.assertEqual(intelligence.PERIPHERAL_BUDGET, 67800)
        self.assertEqual(intelligence.BUDGET, 299800)
        self.assertEqual(intelligence.PC_BUDGET, 302200)

    def test_incomplete_pc_base_config_is_not_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 16, "ssd": "500 GB"}})
        self.assertFalse(ready)
        self.assertEqual(len(reasons), 2)

    def test_full_pc_config_is_ready(self):
        ready, reasons = intelligence.configuration_readiness({"spec": {"ram_gb": 32, "ssd": "1 TB"}})
        self.assertTrue(ready)
        self.assertEqual(reasons, [])

    def test_unverified_peripheral_snapshot_fails_purchase_readiness(self):
        projection = intelligence.peripheral_budget_projection()
        self.assertFalse(projection["budget_data_ready"])
        self.assertTrue(projection["tracked_peripheral_unverified_ids"])
        self.assertGreaterEqual(projection["peripheral_projection_jpy"], 0)
        self.assertGreaterEqual(projection["pc_dynamic_cap_jpy"], 0)
        self.assertLessEqual(projection["pc_dynamic_cap_jpy"], projection["pc_planned_cap_jpy"])
        self.assertLessEqual(projection["pc_dynamic_cap_jpy"] + projection["peripheral_projection_jpy"], projection["total_budget_jpy"])


if __name__ == "__main__":
    unittest.main()
