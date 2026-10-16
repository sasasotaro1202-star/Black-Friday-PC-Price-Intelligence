import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report", ROOT / "scripts" / "report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportLinkTests(unittest.TestCase):
    def test_self_build_policy_ignores_assembly_time_and_keeps_bto_reference_only(self):
        policy = report.build_purchase_method_policy({
            "pc_build_method_preference": "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION",
            "assembly_time_is_constraint": False,
            "assembly_time_penalty_points": 30,
            "bto_role": "REFERENCE_BENCHMARK_ONLY",
            "selection_policy": "self-build first",
        })
        self.assertEqual(policy["primary_method"], "SELF_BUILD")
        self.assertFalse(policy["assembly_time_is_constraint"])
        self.assertEqual(policy["assembly_time_penalty_points"], 0)
        self.assertEqual(policy["bto_role"], "REFERENCE_BENCHMARK_ONLY")
        self.assertFalse(policy["completed_pc_purchase_actionable"])

    def test_completed_pc_gate_reason_is_scoped_away_from_diy(self):
        self_build_reason = report.purchase_gate_reason(
            self_build_primary=True,
            critical_unverified=[],
            peripheral_budget_ready=False,
            action=None,
            dynamic_pc_cap_jpy=0,
            purchase_gate_allowed=False,
        )
        self.assertEqual(self_build_reason, "completed_pc_candidates_reference_only")

    def test_completed_pc_gate_reports_actual_blocker_when_bto_is_in_scope(self):
        self.assertEqual(
            report.purchase_gate_reason(
                self_build_primary=False,
                critical_unverified=["gpu"],
                peripheral_budget_ready=False,
                action=None,
                dynamic_pc_cap_jpy=0,
                purchase_gate_allowed=False,
            ),
            "critical_candidates_not_fully_verified",
        )
        self.assertEqual(
            report.purchase_gate_reason(
                self_build_primary=False,
                critical_unverified=[],
                peripheral_budget_ready=False,
                action=None,
                dynamic_pc_cap_jpy=0,
                purchase_gate_allowed=False,
            ),
            "peripheral_prices_or_availability_unverified",
        )


    def test_completed_pc_gate_blocks_cheapest_channel_claim_until_routes_compared(self):
        reason = report.purchase_gate_reason(
            self_build_primary=False,
            critical_unverified=[],
            peripheral_budget_ready=True,
            action=None,
            dynamic_pc_cap_jpy=360000,
            purchase_gate_allowed=False,
            peripheral_channel_comparison_pending_count=4,
        )
        self.assertEqual(reason, "peripheral_purchase_channel_comparison_incomplete")


    def test_sales_url_accepts_http_url(self):
        self.assertEqual(
            report.sales_url({"url": "https://example.com/product"}),
            "https://example.com/product",
        )

    def test_sales_url_rejects_missing_or_non_http_url(self):
        self.assertIsNone(report.sales_url({"url": ""}))
        self.assertIsNone(report.sales_url({"url": "javascript:alert(1)"}))
        self.assertIsNone(report.sales_url({}))

    def test_sales_url_strips_whitespace(self):
        self.assertEqual(
            report.sales_url({"url": "  https://example.com/product  "}),
            "https://example.com/product",
        )

    def test_suppress_current_price_moves_value_to_reference_only(self):
        row = {"current_price_jpy": 299800, "last_valid_price_jpy": None, "price_jpy": 299800}
        out = report.suppress_current_price(row)
        self.assertIsNone(out["current_price_jpy"])
        self.assertIsNone(out["price_jpy"])
        self.assertEqual(out["last_valid_price_jpy"], 299800)
        self.assertTrue(out["current_price_suppressed"])

    def test_build_products_retains_uncatalogued_discovered_candidate(self):
        discovered = {
            "id": "discovered-a1b2c3d4",
            "name": "Outlet RTX 5070 desktop",
            "url": "https://example.com/pc",
            "form_factor": "desktop",
            "current_price_jpy": 249800,
            "stock_status": "in_stock",
            "price_source_mode": "direct_text",
            "price_validation_status": "validated",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
            "retrieval_time": "2026-10-10T10:00:00+09:00",
            "available_at": "2026-10-10T10:00:00+09:00",
        }
        rows = report.build_products({"products": [discovered]}, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], discovered["id"])
        self.assertTrue(rows[0]["dynamic_candidate"])
        self.assertEqual(rows[0]["current_price_jpy"], 249800)
        self.assertEqual(rows[0]["variant_match"], "ambiguous")

    def test_primary_plan_reports_upgrade_cost_ceiling_without_assuming_it(self):
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-i5g70-5070",
                "role": "primary_configuration_upgrade",
                "label": "DG-I5G70",
                "baseline_price_jpy": 279800,
                "baseline_ram_gb": 16,
                "baseline_ssd_gb": 500,
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-i5g70-5070",
            "name": "G TUNE DG-I5G70",
            "url": "https://example.com/dg-i5",
            "form_factor": "desktop",
            "current_price_jpy": 279800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070", "ram_gb": 16, "ssd": "500 GB"},
            "retrieval_time": "2026-10-10T18:00:00+09:00",
            "available_at": "2026-10-10T17:59:00+09:00",
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200}
        result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["status"], "PRE_BF_TARGET_MONITORING")
        self.assertEqual(row["max_upgrade_cost_to_bf_target_jpy"], 70200)
        self.assertEqual(row["max_upgrade_cost_to_bf_hard_cap_jpy"], 70200)
        self.assertEqual(row["black_friday_target_price_jpy"], 350000)
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertEqual(row["pre_black_friday_reference_price_jpy"], 279800)
        self.assertIn("BF価格ではありません", row["detail"])

    def test_outlet_plan_reports_target_and_live_cap_gaps_separately(self):
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "last_verified_listing_reference_jpy": 330000,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 330000,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
            "retrieval_time": "2026-10-10T18:00:00+09:00",
            "available_at": "2026-10-10T17:59:00+09:00",
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 320200, "pc_budget_jpy": 310200}
        projection = {"pc_dynamic_cap_jpy": 289240}
        result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["status"], "PRE_BF_TARGET_MONITORING")
        self.assertEqual(row["black_friday_target_price_jpy"], 320200)
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertEqual(row["pre_black_friday_reference_price_jpy"], 330000)
        self.assertEqual(row["black_friday_price_cap_jpy"], 310200)
        self.assertEqual(row["pre_bf_reference_gap_to_target_jpy"], 9800)
        self.assertEqual(row["pre_bf_reference_gap_to_planned_cap_jpy"], 19800)

    def test_rtx_5070_ti_outlier_requires_verified_complete_configuration(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "outlier-5070ti-incomplete",
            "name": "RTX 5070 Ti desktop",
            "url": "https://www.mouse-jp.co.jp/store/g/5070ti",
            "form_factor": "desktop",
            "current_price_jpy": 289800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "spec": {"gpu": "RTX 5070 Ti", "ram_gb": 16, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "CONFIRMED_MANUAL",
                    "start_jst": "2026-11-15T00:00:00+09:00",
                    "end_jst": "2026-11-30T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(row["role"], "rtx_5070_ti_outlier")
        self.assertEqual(row["status"], "NO_VERIFIED_COMPLETE_CONFIGURATION")
        self.assertFalse(row["configuration_ready"])
        self.assertEqual(row["verified_complete_candidate_count"], 0)

    def test_bf_price_requires_observation_inside_window(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "black_friday_target_price_jpy": 299800,
                "last_verified_listing_reference_jpy": 304800,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 299800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "retrieval_time": "2026-11-20T12:00:00+09:00",
            "available_at": "2026-11-20T11:59:00+09:00",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200, "budget_data_ready": True}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "CONFIRMED_MANUAL",
                    "start_jst": "2026-11-15T00:00:00+09:00",
                    "end_jst": "2026-11-30T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(result["pricing_phase"], "PROVISIONAL_BROAD_WATCH_WINDOW")
        self.assertTrue(row["black_friday_offer_verified"])
        self.assertEqual(row["black_friday_price_observed_jpy"], 299800)
        self.assertIsNone(row["pre_black_friday_reference_price_jpy"])
        self.assertEqual(row["status"], "MEETS_BF_PRICE_AND_CONFIGURATION")

    def test_watch_window_reference_is_not_mislabelled_pre_sale_or_official_bf(self):
        from datetime import datetime
        strategy = {
            "price_semantics": {
                "window_start_jst": "2026-11-01T00:00:00+09:00",
                "window_end_jst": "2026-12-11T23:59:59+09:00",
                "window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
            },
            "priority_plans": [{
                "candidate_id": "desktop-gtune-dg-a7g70-5070",
                "role": "secondary_outlet_complete_configuration",
                "label": "DG-A7G70 outlet",
                "target_ram_gb": 32,
                "target_ssd_gb": 1000,
                "black_friday_target_price_jpy": 299800,
                "last_verified_listing_reference_jpy": 304800,
            }],
            "outlier_rule": {"gpu": "RTX 5070 Ti", "form_factor": "desktop",
                             "minimum_ram_gb": 32, "minimum_ssd_gb": 1000},
        }
        candidate = {
            "id": "desktop-gtune-dg-a7g70-5070",
            "name": "G TUNE DG-A7G70",
            "url": "https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/",
            "form_factor": "desktop",
            "current_price_jpy": 299800,
            "price_source_mode": "direct_structured",
            "price_validation_status": "validated",
            "variant_match": "exact",
            "stock_status": "in_stock",
            "pit_valid": True,
            "retrieval_time": "2026-11-20T12:00:00+09:00",
            "available_at": "2026-11-20T11:59:00+09:00",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
        }
        policy = {"total_budget_jpy": 400000, "peripheral_budget_jpy": 35000,
                  "pc_target_jpy": 350000, "pc_budget_jpy": 350000}
        projection = {"pc_dynamic_cap_jpy": 322200, "budget_data_ready": True}
        official_calendar = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "UNCONFIRMED",
                    "start_jst": None,
                    "end_jst": None,
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        def fake_load_json(path, fallback=None):
            return official_calendar if str(path).endswith("config/targets.json") else {"sources": {}}
        with patch.object(report, "load_json", side_effect=fake_load_json):
            with patch.object(report, "now_jst", return_value=datetime.fromisoformat("2026-11-20T12:01:00+09:00")):
                result = report.build_purchase_strategy_status([candidate], strategy, policy, projection)
        row = result["rows"][0]
        self.assertEqual(result["pricing_phase"], "PROVISIONAL_BROAD_WATCH_WINDOW")
        self.assertFalse(row["black_friday_offer_verified"])
        self.assertIsNone(row["black_friday_price_observed_jpy"])
        self.assertIsNone(row["pre_black_friday_reference_price_jpy"])
        self.assertEqual(row["watch_window_reference_price_jpy"], 299800)
        self.assertEqual(row["status"], "WAIT_FOR_OFFICIAL_DATES")


    def test_file_sha256_is_stable_for_same_bytes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"
            p.write_bytes(b"black-friday")
            first = report.file_sha256(p)
            second = report.file_sha256(p)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)



    def test_mixed_route_report_never_labels_online_price_as_store_cash_price(self):
        item = {
            "purchase_channel": "compare_online_and_store",
            "purchase_channel_options": ["online", "physical_store", "store_pickup"],
            "online_comparison_price_jpy": 20790,
            "estimated_online_cash_total_jpy": 21790,
            "online_shipping_reserve_jpy": 1000,
            "online_shipping_cost_verified": False,
            "store_price_confirmed": False,
            "channel_comparison_status": "ONLINE_OPTIONS_COMPARED_STORE_PENDING",
        }
        self.assertFalse(report.peripheral_is_physical_store(item, {}))
        self.assertEqual(report.peripheral_route_label(item), "ネット配送・実店舗・店舗受取を比較")
        summary = report.peripheral_route_price_summary(item)
        self.assertIn("ネット掲載 ¥20,790", summary)
        self.assertIn("送料込み推計 ¥21,790", summary)
        self.assertIn("店頭現金価格未確認", summary)
        self.assertIn("店舗受け取り: 決済額未確認", summary)
        self.assertIn("ONLINE_OPTIONS_COMPARED_STORE_PENDING", summary)


if __name__ == "__main__":
    unittest.main()
