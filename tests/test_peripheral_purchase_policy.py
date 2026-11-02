import pathlib
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence


class PeripheralStoreBranchGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 3, 8, 30, tzinfo=timezone(timedelta(hours=9)))
        self.target = {
            "id": "main_monitor",
            "name": "AOC Q27G40E/11 27-inch WQHD 180Hz",
            "purchase_channel": "compare_online_and_store",
            "purchase_channel_options": ["online", "physical_store", "store_pickup"],
            "store_inventory_required_before_purchase": True,
            "require_all_store_branches_before_purchase": True,
            "online_purchase_allowed_when_store_price_unconfirmed": False,
            "online_price_is_comparison_only": True,
            "purchase_channel_preference": "best_verified_total_after_all_store_branches_confirmed",
            "physical_store_candidate_ids": ["biccamera_tenjin_1", "yodobashi_hakata"],
            "target_price_jpy": 1000,
            "track_current_price": True,
            "online_shipping_reserve_jpy": 0,
            "purchase_url": "https://www.yodobashi.com/product/example/",
            "monitor_url": "https://www.yodobashi.com/product/example/",
        }
        self.live = {
            "id": self.target["id"],
            "name": self.target["name"],
            "current_price_jpy": 900,
            "price_verified": True,
            "identity_verified": True,
            "stock_status": "in_stock",
            "online_shipping_cost_verified": True,
            "online_shipping_jpy": 0,
            "retrieval_time": self.now.isoformat(),
            "available_at": self.now.isoformat(),
            "online_best_offer_url": "https://online.example/product",
            "online_offer_count": 1,
            "online_actionable_offer_count": 1,
        }
        self.policy = {
            "total_budget_jpy": 400000,
            "peripheral_budget_jpy": 35000,
            "peripheral_budget_mode": "DYNAMIC_WITHIN_TOTAL_SYSTEM_BUDGET",
            "peripheral_budget_is_hard_cap": False,
            "pc_target_jpy": 360000,
            "pc_budget_jpy": 395000,
            "unallocated_contingency_jpy": 5000,
            "minimum_ram_gb": 32,
            "minimum_ssd_gb": 1000,
            "desktop_preferred": True,
            "peripherals": [self.target],
            "purchase_timing_policy": {},
        }
        self.snapshot = {
            "generated_at": self.now.isoformat(),
            "products": [self.live],
        }

    def _quote(self, store_id, price, stock):
        return {
            "store_id": store_id,
            "store_observation_store_id": store_id,
            "store_name": store_id,
            "store_price_confirmed": True,
            "store_model_match": True,
            "store_price_jpy": price,
            "store_stock_status": stock,
            "store_price_checked_at": self.now.isoformat(),
            "store_confirmation_url": f"https://store.example/{store_id}",
            "store_evidence_type": "store_phone_confirmation",
            "store_evidence_notes": "Exact model, tax-inclusive cash price and same-branch stock checked.",
            "store_observation_status": "PRICE_VERIFIED",
            "store_observation_age_minutes": 1,
        }

    def _run_projection(self, quotes, shipping_verified=True):
        live = dict(self.live)
        live["online_shipping_cost_verified"] = shipping_verified
        live["online_shipping_jpy"] = 0 if shipping_verified else None
        snapshot = {"generated_at": self.now.isoformat(), "products": [live]}
        available = [q for q in quotes if q["store_stock_status"] in ("in_stock", "low_stock")]
        chosen = min(available or quotes, key=lambda q: q["store_price_jpy"]) if quotes else None
        store_observation = {
            "store_price_observations": quotes,
            "store_price_jpy": chosen["store_price_jpy"] if chosen else None,
            "store_price_checked_at": chosen["store_price_checked_at"] if chosen else None,
            "store_stock_status": chosen["store_stock_status"] if chosen else "unknown",
            "store_confirmation_url": chosen["store_confirmation_url"] if chosen else None,
            "store_model_match": bool(chosen),
            "store_price_confirmed": bool(chosen),
            "store_observation_store_id": chosen["store_observation_store_id"] if chosen else None,
            "store_observation_store_name": chosen["store_name"] if chosen else None,
            "store_evidence_type": chosen["store_evidence_type"] if chosen else None,
            "store_evidence_notes": chosen["store_evidence_notes"] if chosen else None,
            "store_observation_status": "PRICE_VERIFIED" if chosen else "UNCONFIRMED",
            "store_observation_age_minutes": 1 if chosen else None,
            "store_price_observation_count": len(quotes),
            "store_price_verified_store_ids": [q["store_observation_store_id"] for q in quotes],
        }
        live_inventory = {
            "store_inventory_status": "unknown",
            "store_inventory_verified": False,
            "store_inventory_checked_at": None,
            "store_inventory_source_url": None,
            "store_inventory_store_id": None,
            "store_inventory_store_name": None,
            "store_inventory_evidence_notes": None,
            "store_inventory_age_minutes": None,
            "store_inventory_store_ids_available": [],
            "store_inventory_observations": [],
        }
        pickup = {
            "store_pickup_checkout_total_jpy": None,
            "store_pickup_checkout_total_confirmed": False,
            "store_pickup_stock_status": "unknown",
            "store_pickup_route_actionable": False,
            "store_pickup_quote_status": "PICKUP_CHECKOUT_TOTAL_MISSING_OR_INVALID",
            "store_pickup_checkout_url": None,
            "store_pickup_store_id": None,
            "store_pickup_evidence_type": None,
            "store_pickup_evidence_notes": None,
            "store_pickup_quote_age_minutes": None,
        }
        with (
            patch.object(intelligence, "purchase_budget_policy", return_value=self.policy),
            patch.object(intelligence, "load_json", return_value=snapshot),
            patch.object(intelligence, "now_jst", return_value=self.now),
            patch.object(intelligence, "actionable_max_age_minutes", return_value=60),
            patch.object(intelligence, "store_observation_validation", return_value=store_observation),
            patch.object(intelligence, "validate_live_store_inventory", return_value=live_inventory),
            patch.object(intelligence, "store_pickup_quote_validation", return_value=pickup),
        ):
            return intelligence.peripheral_budget_projection()

    def test_online_delivery_is_not_selected_while_one_required_branch_is_unverified(self):
        result = self._run_projection([
            self._quote("biccamera_tenjin_1", 850, "in_stock"),
        ])
        row = result["peripherals"][0]
        self.assertEqual(row["selected_purchase_channel"], "unconfirmed")
        self.assertEqual(row["channel_comparison_status"], "STORE_BRANCH_COMPARISON_REQUIRED")
        self.assertTrue(row["online_price_is_comparison_only"])
        self.assertFalse(row["price_verified"])
        self.assertEqual(result["channel_comparison_pending_ids"], ["main_monitor"])
        self.assertFalse(result["budget_data_ready"])
        self.assertFalse(row["early_buy_review"]["purchase_authorized"])

    def test_online_delivery_is_considered_only_after_both_branch_quotes_and_stock_are_known(self):
        result = self._run_projection([
            self._quote("biccamera_tenjin_1", 1100, "in_stock"),
            self._quote("yodobashi_hakata", 1200, "out_of_stock"),
        ])
        row = result["peripherals"][0]
        self.assertTrue(row["store_route_all_branches_confirmed"])
        self.assertEqual(row["selected_purchase_channel"], "online")
        self.assertFalse(row["online_price_is_comparison_only"])
        self.assertEqual(row["channel_comparison_status"], "ONLINE_ROUTE_SELECTED_OTHER_ROUTES_PENDING")

    def test_online_delivery_is_not_selected_when_shipping_total_is_unverified(self):
        result = self._run_projection([
            self._quote("biccamera_tenjin_1", 1100, "in_stock"),
            self._quote("yodobashi_hakata", 1200, "in_stock"),
        ], shipping_verified=False)
        row = result["peripherals"][0]
        self.assertTrue(row["store_route_all_branches_confirmed"])
        self.assertEqual(row["selected_purchase_channel"], "physical_store")
        self.assertEqual(row["channel_comparison_status"], "STORE_CASH_ROUTE_SELECTED_OTHER_ROUTES_PENDING")


if __name__ == "__main__":
    unittest.main()
