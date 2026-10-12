import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, "scripts")
import timing_analysis as timing

JST = timezone(timedelta(hours=9))


def fixture(now, price=280000, stock="in_stock", rank_status="BUY_NOW", gate_allowed=True, pit_valid=True):
    retrieved = timing.iso(now)
    item = {
        "id": "desktop-test",
        "name": "Test desktop RTX 5070",
        "form_factor": "desktop",
        "current_price_jpy": price,
        "cash_total_cost_jpy": price,
        "effective_cost_jpy": price,
        "stock_status": stock,
        "price_source_mode": "direct_structured",
        "price_validation_status": "validated",
        "variant_match": "exact",
        "retrieval_time": retrieved,
        "available_at": retrieved,
        "prediction_time": retrieved,
        "pit_valid": pit_valid,
        "purchase_url": "https://example.com/product",
        "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB", "form_factor": "desktop"},
        "score_detail": {
            "status": rank_status,
            "configuration_ready": True,
            "configuration_reasons": [],
            "wait_risk": "HIGH" if stock == "low_stock" else "LOW",
        },
        "decision_score": 80,
    }
    rankings = {
        "generated_at": retrieved,
        "prediction_time": retrieved,
        "source_snapshot_generated_at": retrieved,
        "source_snapshot_sha256": "test-snapshot",
        "total_budget_jpy": 370000,
        "pc_target_jpy": 300200,
        "dynamic_pc_cap_jpy": 300200,
        "peripheral_projection_jpy": 69800,
        "peripheral_budget_data_ready": True,
        "purchase_gate": {
            "allowed": gate_allowed,
            "coverage_status": "COMPLETE",
            "reason": "all_test_gates_pass",
        },
        "products": [item],
        "unavailable_products": [],
    }
    config = {
        "monitor_window_start": "2026-11-14T00:00:00+09:00",
        "monitor_window_end": "2026-12-04T23:59:59+09:00",
    }
    return rankings, config


class BuyNowDecisionTests(unittest.TestCase):
    def evaluate(self, now, **kwargs):
        rankings, config = fixture(now, **kwargs)
        with patch.object(timing, "now_jst", return_value=now):
            return timing.build_buy_now_decision(rankings, [], config)

    def test_before_sale_never_calls_pre_sale_price_a_buy_now(self):
        now = datetime(2026, 10, 12, 20, 0, tzinfo=JST)
        result = self.evaluate(now)
        self.assertEqual(result["status"], "PRE_BF_MONITORING")
        self.assertIsNotNone(result["chosen_candidate"]["pre_bf_reference_price_jpy"])
        self.assertIsNone(result["chosen_candidate"]["price_jpy"])
        self.assertFalse(result["chosen_candidate"]["qualified_to_buy"])

    def test_verified_in_budget_offer_can_be_buy_now(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now)
        self.assertEqual(result["status"], "BUY_NOW")
        self.assertTrue(result["chosen_candidate"]["qualified_to_buy"])
        self.assertEqual(result["chosen_candidate"]["price_jpy"], 280000)

    def test_unknown_pit_never_qualifies(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now, pit_valid=False)
        row = result["chosen_candidate"]
        self.assertNotEqual(result["status"], "BUY_NOW")
        self.assertFalse(row["price_verified_for_bf"])
        self.assertFalse(row["qualified_to_buy"])

    def test_low_stock_with_blocked_gate_warns_without_authorizing_purchase(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now, stock="low_stock", gate_allowed=False)
        self.assertEqual(result["status"], "URGENT_BUT_GATE_BLOCKED")
        self.assertFalse(result["chosen_candidate"]["qualified_to_buy"])

    def test_over_budget_offer_is_not_authorized(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now, price=320000, rank_status="WAIT_FOR_DISCOUNT")
        self.assertEqual(result["status"], "WAIT_FOR_DISCOUNT")
        self.assertFalse(result["chosen_candidate"]["qualified_to_buy"])


if __name__ == "__main__":
    unittest.main()
