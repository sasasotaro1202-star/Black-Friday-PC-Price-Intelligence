import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, "scripts")
import timing_analysis as timing

JST = timezone(timedelta(hours=9))
WATCH_START = "2026-11-01T00:00:00+09:00"
WATCH_END = "2026-12-11T23:59:59+09:00"
CAMPAIGN_START = "2026-11-15T00:00:00+09:00"
CAMPAIGN_END = "2026-11-30T23:59:59+09:00"


def fixture(now, price=280000, stock="in_stock", rank_status="BUY_NOW", gate_allowed=True, pit_valid=True, retrieved_at=None, budget_ready=True, official_campaign_confirmed=True, campaign_start=CAMPAIGN_START, campaign_end=CAMPAIGN_END):
    retrieved_dt = retrieved_at or now
    retrieved = timing.iso(retrieved_dt)
    item = {
        "id": "desktop-test",
        "name": "Test desktop RTX 5070",
        "form_factor": "desktop",
        "url": "https://www.mouse-jp.co.jp/store/g/test-product",
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
        "purchase_url": "https://www.mouse-jp.co.jp/store/g/test-product",
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
        "total_budget_jpy": 400000,
        "pc_target_jpy": 330200,
        "dynamic_pc_cap_jpy": 330200,
        "peripheral_projection_jpy": 69800,
        "peripheral_budget_data_ready": budget_ready,
        "purchase_gate": {
            "allowed": gate_allowed,
            "coverage_status": "COMPLETE",
            "reason": "all_test_gates_pass" if gate_allowed else "test_gate_blocked",
        },
        "products": [item],
        "unavailable_products": [],
    }
    config = {
        "monitor_window_start": WATCH_START,
        "monitor_window_end": WATCH_END,
        "monitor_window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
        "official_2026_dates": {
            "mouse_computer": {
                "start_jst": campaign_start if official_campaign_confirmed else None,
                "end_jst": campaign_end if official_campaign_confirmed else None,
                "status": "CONFIRMED_MANUAL" if official_campaign_confirmed else "UNCONFIRMED",
                "source_url": "https://www.mouse-jp.co.jp/",
                "evidence": "Test fixture: explicitly dated official 2026 range.",
            }
        },
    }
    return rankings, config


def observation(at, price, candidate_id="desktop-test", **overrides):
    result = {
        "id": candidate_id,
        "observed_at": at,
        "available_at": at,
        "retrieval_time": at,
        "price_jpy": price,
        "stock_status": "in_stock",
        "price_source_mode": "direct_structured",
        "price_validation_status": "validated",
        "variant_match": "exact",
        "pit_valid": True,
    }
    result.update(overrides)
    return result


class BuyNowDecisionTests(unittest.TestCase):
    def evaluate(self, now, price_observations=None, **kwargs):
        rankings, config = fixture(now, **kwargs)
        with patch.object(timing, "now_jst", return_value=now):
            return timing.build_buy_now_decision(rankings, [], config, price_observations)

    def test_before_sale_never_calls_pre_sale_price_a_buy_now(self):
        now = datetime(2026, 10, 12, 20, 0, tzinfo=JST)
        result = self.evaluate(now)
        row = result["chosen_candidate"]
        self.assertEqual(result["status"], "PRE_BF_MONITORING")
        self.assertEqual(row["pre_bf_reference_price_jpy"], 280000)
        self.assertIsNone(row["price_jpy"])
        self.assertFalse(row["qualified_to_buy"])

    def test_verified_in_budget_offer_can_be_buy_now(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now)
        self.assertEqual(result["status"], "BUY_NOW")
        self.assertTrue(result["chosen_candidate"]["qualified_to_buy"])
        self.assertEqual(result["chosen_candidate"]["price_jpy"], 280000)

    def test_provisional_watch_window_alone_never_authorizes_buy_now(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now, official_campaign_confirmed=False)
        row = result["chosen_candidate"]
        self.assertEqual(result["status"], "WAIT_FOR_OFFICIAL_DATES")
        self.assertEqual(row["status"], "WAIT_FOR_OFFICIAL_DATES")
        self.assertFalse(row["price_verified_for_bf"])
        self.assertFalse(row["qualified_to_buy"])
        self.assertEqual(row["watch_window_observed_price_jpy"], 280000)
        self.assertEqual(row["retailer_key"], "mouse_computer")

    def test_confirmed_future_sale_is_not_active_early(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(
            now,
            campaign_start="2026-11-21T00:00:00+09:00",
            campaign_end=CAMPAIGN_END,
        )
        row = result["chosen_candidate"]
        self.assertEqual(result["status"], "WAIT_FOR_OFFICIAL_DATES")
        self.assertFalse(row["retailer_campaign_active"])
        self.assertFalse(row["price_verified_for_bf"])
        self.assertFalse(row["qualified_to_buy"])

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
        result = self.evaluate(now, price=340000, rank_status="WAIT_FOR_DISCOUNT")
        self.assertEqual(result["status"], "WAIT_FOR_DISCOUNT")
        self.assertFalse(result["chosen_candidate"]["qualified_to_buy"])

    def test_sold_out_candidate_is_never_authorized(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        result = self.evaluate(now, stock="out_of_stock")
        self.assertNotEqual(result["status"], "BUY_NOW")
        self.assertEqual(result["chosen_candidate"]["status"], "OUT_OF_STOCK")
        self.assertFalse(result["chosen_candidate"]["qualified_to_buy"])

    def test_stale_price_observation_is_not_authorized(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        old = datetime(2026, 11, 20, 10, 0, tzinfo=JST)
        result = self.evaluate(now, retrieved_at=old)
        self.assertNotEqual(result["status"], "BUY_NOW")
        self.assertFalse(result["chosen_candidate"]["price_verified_for_bf"])
        self.assertIn("価格観測が古いか取得時刻が未確認", result["chosen_candidate"]["blockers"])

    def test_sale_window_low_uses_verified_observations_and_timestamp(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        prices = [
            observation("2026-11-18T12:00:00+09:00", 270000),
            observation("2026-11-19T12:00:00+09:00", 275000),
            observation("2026-11-19T13:00:00+09:00", 99999, pit_valid=False),
            observation("2026-11-19T14:00:00+09:00", 250000, stock_status="out_of_stock"),
            observation("2026-11-19T15:00:00+09:00", 260000, price_source_mode="search_snippet"),
        ]
        result = self.evaluate(now, price_observations=prices)
        row = result["chosen_candidate"]
        self.assertEqual(row["watch_window_low_observed_jpy"], 270000)
        self.assertEqual(row["watch_window_low_observed_at"], "2026-11-18T12:00:00+09:00")
        self.assertEqual(row["watch_window_price_observation_count"], 3)  # two history points + current snapshot
        self.assertGreater(row["gap_from_watch_window_low_pct"], 0)

    def test_after_sale_price_is_never_mislabeled_as_pre_sale(self):
        now = datetime(2026, 12, 12, 12, 0, tzinfo=JST)
        result = self.evaluate(now)
        row = result["chosen_candidate"]
        self.assertEqual(result["status"], "SALE_WINDOW_CLOSED")
        self.assertIsNone(row["pre_bf_reference_price_jpy"])
        self.assertEqual(row["post_bf_reference_price_jpy"], 280000)
        self.assertFalse(row["qualified_to_buy"])

    def test_observation_ledger_only_records_verified_buyable_offers_in_window(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        rankings, config = fixture(now)
        snapshot = rankings["products"][0]
        invalid = dict(snapshot, id="not-verified", price_source_mode="search_snippet")
        with tempfile.TemporaryDirectory() as root:
            with patch.object(timing, "ROOT", root):
                count = timing.append_buy_now_observations({"products": [snapshot, invalid]}, config, now=now)
                path = os.path.join(root, "data", "buy_now_observations.jsonl")
                self.assertEqual(count, 1)
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()
                self.assertEqual(len(lines), 1)
                saved = json.loads(lines[0])
                self.assertEqual(saved["price_jpy"], 280000)
                self.assertTrue(saved["pit_valid"])
                outside = datetime(2026, 10, 12, 12, 0, tzinfo=JST)
                self.assertEqual(timing.append_buy_now_observations({"products": [snapshot]}, config, now=outside), 0)


if __name__ == "__main__":
    unittest.main()
