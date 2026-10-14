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
    def evaluate(self, now, price_observations=None, official_campaign_dates=None, **kwargs):
        rankings, config = fixture(now, **kwargs)
        with patch.object(timing, "now_jst", return_value=now):
            return timing.build_buy_now_decision(
                rankings, [], config, price_observations, official_campaign_dates
            )

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
        self.assertEqual(result["status"], "WAIT_FOR_CAMPAIGN_WINDOW")
        self.assertFalse(row["retailer_campaign_active"])
        self.assertFalse(row["price_verified_for_bf"])
        self.assertFalse(row["qualified_to_buy"])

    def test_confirmed_active_campaign_with_pre_campaign_price_waits_for_fresh_price(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        retrieved_at = datetime(2026, 11, 14, 12, 0, tzinfo=JST)
        result = self.evaluate(now, retrieved_at=retrieved_at)
        row = result["chosen_candidate"]
        self.assertTrue(row["retailer_campaign_dates_confirmed"])
        self.assertTrue(row["retailer_campaign_active"])
        self.assertFalse(row["retailer_campaign_active_at_observation"])
        self.assertEqual(row["status"], "VERIFY_PRICE_OR_PIT")
        self.assertNotEqual(result["status"], "WAIT_FOR_OFFICIAL_DATES")
        self.assertFalse(row["qualified_to_buy"])

    def test_official_date_fetch_errors_are_separate_from_unconfirmed_dates(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        calendar = {
            "sources": {
                "mouse_computer": {"status": "UNCONFIRMED"},
                "acer": {"status": "FETCH_ERROR"},
                "amazon_japan": {
                    "status": "CONFIRMED",
                    "start_jst": CAMPAIGN_START,
                    "end_jst": CAMPAIGN_END,
                    "source_url": "https://www.amazon.co.jp/blackfriday",
                },
            }
        }
        result = self.evaluate(
            now,
            official_campaign_dates=calendar,
            official_campaign_confirmed=False,
        )
        summary = result["official_campaign_dates_summary"]
        self.assertEqual(summary["retailer_count"], 3)
        self.assertEqual(summary["confirmed_count"], 1)
        self.assertEqual(summary["unconfirmed_count"], 1)
        self.assertEqual(summary["fetch_error_count"], 1)
        text = timing.render_buy_now_markdown(result)
        self.assertIn("取得エラー: 1", text)
        self.assertIn("公式期間が確認できない店舗: 1", text)

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

    def test_self_build_policy_blocks_bto_buy_now_even_if_legacy_gate_says_allowed(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        rankings, config = fixture(now, gate_allowed=True)
        rankings["purchase_method_policy"] = {
            "primary_method": "SELF_BUILD",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 0,
            "bto_role": "REFERENCE_BENCHMARK_ONLY",
        }
        result = timing.build_buy_now_decision(rankings, [], config)
        self.assertFalse(result["purchase_gate_allowed"])
        self.assertEqual(result["purchase_method_policy"]["primary_method"], "SELF_BUILD")
        self.assertFalse(result["purchase_method_policy"]["completed_pc_purchase_actionable"])

    def test_self_build_timing_does_not_authorize_from_targets_or_reference_prices(self):
        plan = {
            "total_budget_jpy": 400000, "pc_budget_jpy": 330200,
            "peripheral_budget_jpy": 69800,
            "purchase_method_policy": {
                "primary_method": "SELF_BUILD",
                "assembly_time_is_constraint": False,
                "assembly_time_penalty_points": 0,
            },
            "builds": [{
                "rank": 1, "id": "diy-primary", "gpu_choice_id": "gpu-rtx5070-12gb",
                "name": "DIY Ryzen + RTX 5070",
                "target_pc_total_jpy": 320000, "target_all_in_jpy": 389800,
                "target_remaining_budget_jpy": 10200, "target_within_total_budget": True,
                "target_parts_subtotal_jpy": 311000,
                "compatibility_status": "PASS",
                "market_reference_estimate_jpy": None,
                "market_reference_all_in_estimate_jpy": None,
                "missing_or_untrusted_market_reference_ids": ["cpu-x"],
                "components": [{
                    "id": "cpu-x", "track_price": True,
                    "trusted_for_market_estimate": False, "market_reference_price_jpy": None,
                    "source_role": "comparison_site_reference",
                }],
            }],
        }
        config = {"profile": {
            "primary_gpu_choice_id": "gpu-rtx5070-12gb",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 0,
        }}
        result = timing.build_self_build_timing_summary(plan, config)
        self.assertEqual(result["primary_method"], "SELF_BUILD")
        self.assertEqual(result["status"], "WAIT_FOR_COMPONENT_REFERENCES")
        self.assertFalse(result["purchase_allowed"])
        self.assertFalse(result["bf_actual_authorized"])
        self.assertEqual(result["target_all_in_jpy"], 389800)
        self.assertEqual(result["verified_market_reference_count"], 0)
        self.assertEqual(result["verified_checkout_offer_count"], 0)
        self.assertFalse(result["assembly_time_is_constraint"])
        self.assertEqual(result["assembly_time_penalty_points"], 0)

    def test_display_only_search_reference_is_visible_but_never_used_for_estimate_or_buy_gate(self):
        now = datetime(2026, 10, 14, 12, 0, tzinfo=JST)
        plan = {
            "total_budget_jpy": 400000, "pc_budget_jpy": 330200,
            "peripheral_budget_jpy": 69800,
            "purchase_method_policy": {
                "primary_method": "SELF_BUILD",
                "assembly_time_is_constraint": False,
                "assembly_time_penalty_points": 0,
            },
            "builds": [{
                "rank": 1, "id": "diy-primary", "gpu_choice_id": "g1", "name": "DIY test build",
                "target_pc_total_jpy": 320000, "target_all_in_jpy": 389800,
                "target_remaining_budget_jpy": 10200, "target_within_total_budget": True,
                "target_parts_subtotal_jpy": 311000, "compatibility_status": "PASS",
                "market_reference_estimate_jpy": None, "market_reference_all_in_estimate_jpy": None,
                "missing_or_untrusted_market_reference_ids": ["cpu-x"],
                "components": [{
                    "id": "cpu-x", "name": "CPU test", "category": "cpu", "model_code": "CPU-12345",
                    "track_price": True, "target_price_jpy": 40000,
                    "trusted_for_market_estimate": False, "market_reference_price_jpy": None,
                    "display_reference_price_jpy": 39980,
                    "price_status": "search_snippet_reference_only",
                    "source_role": "comparison_site_reference",
                    "reference_age_minutes": 2,
                    "search_snippet_reference_url": "https://search.kakaku.com/CPU-12345/",
                    "search_snippet_reference_title": "CPU-12345",
                    "purchase_url": "https://kakaku.com/item/K0001234567/",
                }],
            }],
        }
        config = {"profile": {"primary_gpu_choice_id": "g1"}}
        result = timing.build_self_build_timing_summary(plan, config, now=now)
        self.assertEqual(result["status"], "WAIT_FOR_COMPONENT_REFERENCES")
        self.assertEqual(result["verified_market_reference_count"], 0)
        self.assertEqual(result["display_only_search_reference_count"], 1)
        row = result["component_timing"][0]
        self.assertIsNone(row["current_market_reference_price_jpy"])
        self.assertEqual(row["display_only_reference_price_jpy"], 39980)
        self.assertEqual(row["status"], "DISPLAY_ONLY_SEARCH_REFERENCE")
        self.assertEqual(row["status_label"], "検索ページ表示値のみ（検証価格なし）")
        self.assertFalse(row["display_only_reference_is_estimate_eligible"])
        self.assertIsNone(row["target_gap_jpy"])
        self.assertFalse(result["purchase_allowed"])

        report = timing.render_buy_now_markdown({
            "generated_at": timing.iso(now),
            "label": "事前監視継続", "status": "PRE_BF_MONITORING",
            "watch_window_start_jst": WATCH_START, "watch_window_end_jst": WATCH_END,
            "official_campaign_dates_summary": {"confirmed_count": 0, "retailer_count": 0,
                                                "unconfirmed_count": 0, "fetch_error_count": 0},
            "purchase_method_policy": {"primary_method": "SELF_BUILD"},
            "self_build_purchase_timing": result,
        })
        self.assertIn("検索ページ表示専用値（不採用）", report)
        self.assertIn("39,980", report)
        self.assertIn("近傍テキストから得た参考情報", report)

    def test_self_build_waits_for_checkout_offers_even_when_reference_prices_are_complete(self):
        plan = {
            "total_budget_jpy": 400000, "pc_budget_jpy": 330200, "peripheral_budget_jpy": 69800,
            "purchase_method_policy": {"assembly_time_is_constraint": False, "assembly_time_penalty_points": 0},
            "builds": [{
                "rank": 1, "id": "diy-primary", "gpu_choice_id": "g1", "name": "DIY build",
                "target_pc_total_jpy": 320000, "target_all_in_jpy": 389800,
                "target_remaining_budget_jpy": 10200, "target_within_total_budget": True,
                "target_parts_subtotal_jpy": 311000, "compatibility_status": "PASS",
                "market_reference_estimate_jpy": 300000, "market_reference_all_in_estimate_jpy": 369800,
                "missing_or_untrusted_market_reference_ids": [],
                "components": [{
                    "id": "cpu-x", "track_price": True, "trusted_for_market_estimate": True,
                    "market_reference_price_jpy": 40000, "source_role": "comparison_site_reference",
                }],
            }],
        }
        result = timing.build_self_build_timing_summary(plan, {"profile": {"primary_gpu_choice_id": "g1"}})
        self.assertEqual(result["status"], "WAIT_FOR_OFFICIAL_COMPONENT_OFFERS")
        self.assertEqual(result["verified_market_reference_count"], 1)
        self.assertEqual(result["verified_checkout_offer_count"], 0)
        self.assertFalse(result["purchase_allowed"])

    def test_component_timing_uses_pit_valid_reference_history_and_calculates_target_gap(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        part = {
            "id": "cpu-test", "name": "CPU test", "category": "cpu", "model_code": "CPU-12345",
            "target_price_jpy": 40000, "track_price": True,
            "market_reference_price_jpy": 45000, "trusted_for_market_estimate": True,
            "price_status": "verified_market_reference", "reference_age_minutes": 3,
            "purchase_url": "https://kakaku.com/item/K0001234567/",
        }
        def obs(price, at):
            return {
                "id": "cpu-test", "market_reference_price_jpy": price,
                "price_validation_status": "verified_market_reference",
                "source_role": "comparison_site_reference", "identity_match": True,
                "pit_valid": True, "bf_actual_authorized": False,
                "available_at": at, "retrieval_time": at, "observed_at": at,
            }
        history = [
            obs(50000, "2026-11-02T12:00:00+09:00"),
            obs(45000, "2026-11-15T12:00:00+09:00"),
        ]
        rows = timing.build_component_timing_rows(
            [part], history,
            {"monitor_window_start": WATCH_START, "monitor_window_end": WATCH_END},
            now=now,
        )
        row = rows[0]
        self.assertEqual(row["current_market_reference_price_jpy"], 45000)
        self.assertEqual(row["target_gap_jpy"], 5000)
        self.assertEqual(row["required_drop_pct"], 11.1)
        self.assertEqual(row["history_low_reference_price_jpy"], 45000)
        self.assertEqual(row["history_sample_count"], 2)
        self.assertEqual(row["watch_window_sample_count"], 2)
        self.assertEqual(row["status"], "WAIT_FOR_TARGET")
        self.assertFalse(row["purchase_allowed"])
        self.assertFalse(row["bf_actual_authorized"])

    def test_component_timing_rejects_snippet_only_reference_as_live_price(self):
        now = datetime(2026, 11, 20, 12, 0, tzinfo=JST)
        part = {
            "id": "gpu-test", "name": "GPU test", "category": "gpu",
            "target_price_jpy": 120000, "track_price": True,
            "market_reference_price_jpy": None, "display_reference_price_jpy": 125000,
            "trusted_for_market_estimate": False, "price_status": "search_snippet_reference_only",
            "purchase_url": "https://kakaku.com/item/K0001234567/",
        }
        rows = timing.build_component_timing_rows([part], [], {
            "monitor_window_start": WATCH_START, "monitor_window_end": WATCH_END,
        }, now=now)
        self.assertIsNone(rows[0]["current_market_reference_price_jpy"])
        self.assertIsNone(rows[0]["target_gap_jpy"])
        self.assertEqual(rows[0]["status"], "REFERENCE_UNVERIFIED")
        self.assertFalse(rows[0]["purchase_allowed"])

    def test_buy_now_report_shows_diy_first_policy_and_component_gate(self):
        now = datetime(2026, 10, 14, 12, 0, tzinfo=JST)
        result = self.evaluate(now)
        result["purchase_method_policy"] = {
            "primary_method": "SELF_BUILD",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 0,
            "bto_role": "REFERENCE_BENCHMARK_ONLY",
            "completed_pc_purchase_actionable": False,
        }
        result["self_build_purchase_timing"] = {
            "selected_build_name": "自作 Ryzen 7 9700X + RTX 5070",
            "target_pc_total_jpy": 320360, "target_all_in_jpy": 390160,
            "target_remaining_budget_jpy": 9840, "compatibility_status": "PASS",
            "verified_market_reference_count": 0, "tracked_component_count": 9,
            "verified_checkout_offer_count": 0, "component_count": 9,
            "status": "WAIT_FOR_COMPONENT_REFERENCES",
            "blockers": ["部品参考価格が不足", "最終決済価格を未確認"],
        }
        rendered = timing.render_buy_now_markdown(result)
        self.assertIn("自作PC本命の買い時", rendered)
        self.assertIn("組み立て時間を考慮するか: いいえ（減点なし）", rendered)
        self.assertIn("320,360", rendered)
        self.assertIn("WAIT_FOR_COMPONENT_REFERENCES", rendered)
        self.assertIn("BTOの位置付け: 価格・性能・部品品質・保証の比較ベンチマークのみ", rendered)

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
