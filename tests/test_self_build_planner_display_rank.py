import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from self_build_planner import display_purchase_rank


def ready_candidate(**overrides):
    candidate = {
        "rank": 2,
        "compatibility_status": "PASS",
        "decision": "BUY_NOW",
        "current_sellable_listing_required_part_count": 8,
        "current_sellable_listing_part_count": 8,
        "current_listing_subtotal_is_checkout_price": True,
        "target_within_soft_total_budget": True,
    }
    candidate.update(overrides)
    return candidate


class DisplayPurchaseRankTests(unittest.TestCase):
    def test_unqualified_compatibility_hides_numeric_rank(self):
        self.assertEqual(
            display_purchase_rank(ready_candidate(compatibility_status="REVIEW")),
            "保留",
        )

    def test_non_buy_now_decision_hides_numeric_rank(self):
        self.assertEqual(
            display_purchase_rank(ready_candidate(decision="WAIT_FOR_COMPATIBILITY_REVIEW")),
            "保留",
        )

    def test_incomplete_sellable_stock_hides_numeric_rank(self):
        self.assertEqual(
            display_purchase_rank(ready_candidate(current_sellable_listing_part_count=7)),
            "保留",
        )

    def test_unverified_checkout_total_hides_numeric_rank(self):
        self.assertEqual(
            display_purchase_rank(ready_candidate(current_listing_subtotal_is_checkout_price=False)),
            "保留",
        )

    def test_over_budget_candidate_hides_numeric_rank(self):
        self.assertEqual(
            display_purchase_rank(ready_candidate(target_within_soft_total_budget=False)),
            "保留",
        )

    def test_fully_verified_buy_now_candidate_may_receive_rank(self):
        self.assertEqual(display_purchase_rank(ready_candidate()), 2)


if __name__ == "__main__":
    unittest.main()
