import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import timing_analysis
from build_component_monitor import append_pit_change_event


class StrictChangeEventPitTests(unittest.TestCase):
    def test_legacy_event_with_missing_event_and_publication_times_is_excluded(self):
        event = {
            "id": "gpu-test",
            "observed_at": "2026-11-09T08:04:00+09:00",
            "event_time": None,
            "publication_time": None,
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            # Simulate the old false-positive producer.
            "pit_valid": True,
            "old_price_jpy": 100000,
            "new_price_jpy": 99000,
        }
        result = timing_analysis.dynamic_change_timing([event])
        self.assertEqual(result["sample_size"], 0)

    def test_complete_ordered_event_time_chain_is_eligible(self):
        event = {
            "id": "gpu-test",
            "observed_at": "2026-11-09T08:04:00+09:00",
            "event_time": "2026-11-09T08:00:00+09:00",
            "publication_time": "2026-11-09T08:01:00+09:00",
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            "pit_valid": True,
            "pit_status": "VALID",
            "pit_missing_fields": [],
            "pit_error": None,
            "old_price_jpy": 100000,
            "new_price_jpy": 99000,
        }
        result = timing_analysis.dynamic_change_timing([event])
        self.assertEqual(result["sample_size"], 1)

    def test_component_event_writer_marks_missing_source_times_unknown(self):
        events = []
        append_pit_change_event(events, {
            "id": "gpu-test",
            "observed_at": "2026-11-09T08:04:00+09:00",
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            "old_market_reference_price_jpy": 100000,
            "new_market_reference_price_jpy": 99000,
        })
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["pit_valid"])
        self.assertEqual(events[0]["pit_status"], "UNKNOWN")
        self.assertEqual(
            events[0]["pit_missing_fields"],
            ["event_time", "publication_time"],
        )


if __name__ == "__main__":
    unittest.main()
