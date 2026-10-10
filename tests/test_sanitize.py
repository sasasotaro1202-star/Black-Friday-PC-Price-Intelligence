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
            "alternate_url_attempts": 3,
            "alternate_url_successes": 1,
            "alternate_url_failures": 2,
            "alternate_url_identity_rejections": 1,
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
        self.assertEqual(result["alternate_url_attempts"], 3)
        self.assertEqual(result["alternate_url_successes"], 1)
        self.assertEqual(result["alternate_url_failures"], 2)
        self.assertEqual(result["alternate_url_identity_rejections"], 1)


if __name__ == "__main__":
    unittest.main()
