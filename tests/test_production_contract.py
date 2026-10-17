import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from observation_contract import observation_metadata_schema_errors


def valid_snapshot():
    return {
        "products": [{"id": "sample"}],
        "coverage": {
            "watchlist_count": 1,
            "processed_count": 1,
            "skipped_count": 0,
            "max_urls": 100,
            "processing_rate_pct": 100.0,
            "transport_success_rate_pct": 100.0,
            "price_verified_rate_pct": 100.0,
            "skipped_ids": [],
        },
        "fetch_stats": {
            "total": 1,
            "direct_verified": 1,
            "search_corrob": 0,
            "stale_previous": 0,
            "baseline_only": 0,
            "anomaly_rejected": 0,
            "errors": 0,
        },
    }


class ProductionObservationContractTests(unittest.TestCase):
    def test_complete_metadata_passes(self):
        self.assertEqual(observation_metadata_schema_errors(valid_snapshot()), [])

    def test_missing_coverage_fails_closed(self):
        snapshot = valid_snapshot()
        del snapshot["coverage"]
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("coverage is missing or is not an object", errors)

    def test_empty_coverage_and_fetch_stats_fail_closed(self):
        snapshot = valid_snapshot()
        snapshot["coverage"] = {}
        snapshot["fetch_stats"] = {}
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("coverage is missing or is not an object", errors)
        self.assertIn("fetch_stats is missing or is not an object", errors)

    def test_boolean_counter_is_not_accepted_as_integer(self):
        snapshot = valid_snapshot()
        snapshot["coverage"]["processed_count"] = True
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("coverage.processed_count is missing or invalid", errors)

    def test_invalid_rate_and_duplicate_skipped_ids_are_rejected(self):
        snapshot = valid_snapshot()
        snapshot["coverage"]["transport_success_rate_pct"] = 101.0
        snapshot["coverage"]["skipped_ids"] = ["missing", "missing"]
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("coverage.transport_success_rate_pct is missing or invalid", errors)
        self.assertIn("coverage.skipped_ids contains duplicates", errors)

    def test_fetch_total_must_match_product_count(self):
        snapshot = valid_snapshot()
        snapshot["fetch_stats"]["total"] = 2
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("fetch_stats.total does not match products length", errors)

    def test_missing_fetch_counter_is_rejected(self):
        snapshot = valid_snapshot()
        del snapshot["fetch_stats"]["errors"]
        errors = observation_metadata_schema_errors(snapshot)
        self.assertIn("fetch_stats.errors is missing or invalid", errors)


if __name__ == "__main__":
    unittest.main()
