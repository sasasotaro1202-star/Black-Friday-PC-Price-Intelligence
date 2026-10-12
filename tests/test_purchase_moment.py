import pathlib
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import purchase_moment

START = "2026-11-14T00:00:00+09:00"
END = "2026-12-04T23:59:59+09:00"
NOW = "2026-11-20T12:00:00+09:00"
POLICY = {
    "total_budget_jpy": 400000, "peripheral_budget_jpy": 69800,
    "pc_target_jpy": 330200, "pc_budget_jpy": 330200,
    "minimum_ram_gb": 32, "minimum_ssd_gb": 1000,
    "desktop_preferred": True, "peripherals": [],
}
CONFIG = {
    "monitor_window_start": START, "monitor_window_end": END,
    "purchase_strategy": {
        "price_semantics": {"window_start_jst": START, "window_end_jst": END},
        "priority_plans": [{"candidate_id": "pc1", "black_friday_target_price_jpy": 330200}],
        "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                         "black_friday_target_cap_jpy": 330200},
    },
}


def pc(**updates):
    item = {
        "id": "pc1", "name": "RTX 5070 desktop", "url": "https://example.com/pc1",
        "form_factor": "desktop", "decision_score": 90, "current_price_jpy": 320000,
        "price_source_mode": "direct_structured", "price_validation_status": "validated",
        "variant_match": "exact", "stock_status": "in_stock",
        "available_at": "2026-11-20T11:58:00+09:00",
        "retrieval_time": "2026-11-20T11:59:00+09:00", "prediction_time": NOW,
        "spec": {"gpu": "RTX 5070", "cpu": "Ryzen 7", "ram_gb": 32,
                 "ssd": "1 TB", "form_factor": "desktop"},
    }
    item.update(updates)
    return item


def projection(ready=True, cap=330200):
    return {"pc_dynamic_cap_jpy": cap, "peripheral_projection_jpy": 69800,
            "budget_data_ready": ready,
            "tracked_peripheral_unverified_ids": [] if ready else ["speakers"]}


class PurchaseMomentTests(unittest.TestCase):
    def evaluate(self, item, now=NOW, accessories_ready=True):
        with patch.object(purchase_moment, "purchase_budget_policy", return_value=POLICY):
            return purchase_moment.build_decision(
                datetime.fromisoformat(now), CONFIG, {"products": [item]},
                {"candidates": [{"id": "pc1", "name": item["name"], "url": item["url"]}]},
                [], [], projection(accessories_ready),
            )

    def test_pre_bf_price_is_reference_only(self):
        result = self.evaluate(pc(), "2026-11-13T12:00:00+09:00")
        self.assertEqual(result["current_action"]["action"], "MONITOR_PRE_BF")
        self.assertFalse(result["current_action"]["should_buy_now"])

    def test_complete_verified_bf_offer_can_be_buy_now(self):
        result = self.evaluate(pc())
        self.assertEqual(result["current_action"]["action"], "BUY_NOW")
        self.assertTrue(result["current_action"]["should_buy_now"])

    def test_out_of_stock_and_incomplete_build_never_buy(self):
        sold = self.evaluate(pc(stock_status="out_of_stock"))
        self.assertNotEqual(sold["current_action"]["action"], "BUY_NOW")
        incomplete = self.evaluate(pc(spec={"gpu": "RTX 5070", "ram_gb": 16, "ssd": "500 GB"}))
        self.assertNotEqual(incomplete["current_action"]["action"], "BUY_NOW")
        self.assertEqual(incomplete["ranking"][0]["candidate_action"], "CONFIGURATION_REQUIRED")

    def test_budget_and_accessory_gates_are_enforced(self):
        over = self.evaluate(pc(current_price_jpy=340000))
        self.assertEqual(over["ranking"][0]["candidate_action"], "WAIT_FOR_BUDGET_PRICE")
        pending = self.evaluate(pc(), accessories_ready=False)
        self.assertEqual(pending["current_action"]["action"], "VERIFY_BUNDLE_THEN_BUY")
        self.assertFalse(pending["current_action"]["should_buy_now"])


if __name__ == "__main__":
    unittest.main()
