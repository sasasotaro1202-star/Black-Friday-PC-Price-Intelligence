import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sanitize


class SanitizeFetchStatsTests(unittest.TestCase):
    def test_monitor_provider_and_host_diagnostics_survive_sanitize(self):
        monitor_stats = {
            "total": 3,
            "direct_verified": 1,
            "search_corrob": 1,
            "stale_previous": 0,
            "baseline_only": 1,
            "anomaly_rejected": 0,
            "errors": 1,
            "search_fallback_attempts": 2,
            "search_fallback_successes": 1,
            "search_fallback_failures": 1,
            "search_identity_rejections": 4,
            "errors_by_host_reason": {"example.com|curl_exit_35": 1},
        }
        final = [
            {"current_price_jpy": 100000, "price_source_mode": "direct_structured",
             "fetch_status": "ok", "price_validation_status": "validated"},
            {"current_price_jpy": 120000, "price_source_mode": "search_snippet",
             "fetch_status": "error", "price_validation_status": "validated"},
            {"current_price_jpy": None, "price_source_mode": "public_baseline",
             "fetch_status": "error", "price_validation_status": "reference_only"},
        ]
        result = sanitize.final_fetch_stats(final, monitor_stats)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["direct_verified"], 1)
        self.assertEqual(result["search_corrob"], 1)
        self.assertEqual(result["errors"], 2)
        self.assertEqual(result["search_fallback_attempts"], 2)
        self.assertEqual(result["search_fallback_successes"], 1)
        self.assertEqual(result["search_fallback_failures"], 1)
        self.assertEqual(result["search_identity_rejections"], 4)
        self.assertEqual(result["errors_by_host_reason"], {"example.com|curl_exit_35": 1})


class NavigationPriceSanitizationTests(unittest.TestCase):
    def test_navigation_filter_price_is_removed_from_actionable_fields(self):
        item = {
            "id": "desktop-test",
            "current_price_jpy": 300001,
            "price_jpy": 300001,
            "last_valid_price_jpy": 304800,
            "price_source_mode": "direct_text",
            "price_context": "G TUNE HOME 価格から探す 300,001円～ グラフィックスから探す",
            "price_validation_status": "validated",
            "stock_status": "in_stock",
            "data_confidence": "medium",
        }
        rejected = sanitize.reject_navigation_filter_price(
            item, 300001, reference=304800
        )
        self.assertTrue(rejected)
        self.assertIsNone(item["current_price_jpy"])
        self.assertIsNone(item["price_jpy"])
        self.assertEqual(item["last_valid_price_jpy"], 304800)
        self.assertEqual(item["reference_price_jpy"], 304800)
        self.assertEqual(item["rejected_price_candidate_jpy"], 300001)
        self.assertEqual(
            item["price_validation_reason"],
            "price_from_navigation_filter_not_sku_offer",
        )
        self.assertEqual(item["stock_status"], "in_stock")

    def test_real_product_price_context_is_not_rejected(self):
        item = {
            "price_source_mode": "direct_text",
            "price_context": "G TUNE DG-A7G70 販売価格 304,800円（税込）",
            "current_price_jpy": 304800,
            "price_jpy": 304800,
        }
        self.assertFalse(
            sanitize.reject_navigation_filter_price(
                item, 304800, reference=304800
            )
        )
        self.assertEqual(item["current_price_jpy"], 304800)
        self.assertEqual(item["price_jpy"], 304800)

    def test_structured_product_prices_are_not_changed_by_text_navigation_guard(self):
        item = {
            "price_source_mode": "direct_structured",
            "price_context": "価格から探す 300,001円～",
            "current_price_jpy": 304800,
            "price_jpy": 304800,
        }
        self.assertFalse(
            sanitize.reject_navigation_filter_price(
                item, 304800, reference=304800
            )
        )
        self.assertEqual(item["current_price_jpy"], 304800)


if __name__ == "__main__":
    unittest.main()
