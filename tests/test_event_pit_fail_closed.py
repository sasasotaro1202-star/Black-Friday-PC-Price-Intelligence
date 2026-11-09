import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import timing_analysis
import report
from build_component_monitor import append_pit_change_event, normalize_component_event_log
from monitor import normalize_change_event_log
from observation_contract import normalize_point_in_time_event


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

    def test_normalizer_downgrades_legacy_valid_flag_without_source_timestamps(self):
        event = {
            "event_time": None,
            "publication_time": None,
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            "pit_valid": True,
        }
        normalized = normalize_point_in_time_event(event)
        self.assertFalse(normalized["pit_valid"])
        self.assertEqual(normalized["pit_status"], "UNKNOWN")
        self.assertEqual(normalized["pit_missing_fields"], ["event_time", "publication_time"])
        self.assertTrue(event["pit_valid"])

    def test_main_and_component_event_log_migrations_rewrite_legacy_flags(self):
        legacy = {
            "id": "gpu-test",
            "event_time": None,
            "publication_time": None,
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            "pit_valid": True,
        }
        for normalizer in (normalize_change_event_log, normalize_component_event_log):
            with tempfile.TemporaryDirectory() as temp_dir:
                path = pathlib.Path(temp_dir) / "events.jsonl"
                path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
                self.assertEqual(normalizer(str(path)), 1)
                migrated = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
                self.assertFalse(migrated["pit_valid"])
                self.assertEqual(migrated["pit_status"], "UNKNOWN")

    def test_report_does_not_use_legacy_unknown_events_as_evidence(self):
        legacy = {
            "id": "gpu-test",
            "event_time": None,
            "publication_time": None,
            "available_at": "2026-11-09T08:02:00+09:00",
            "retrieval_time": "2026-11-09T08:03:00+09:00",
            "prediction_time": "2026-11-09T08:04:00+09:00",
            "pit_valid": True,
            "old_price_jpy": 100000,
            "new_price_jpy": 99000,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = pathlib.Path(temp_dir) / "data"
            data_dir.mkdir()
            (data_dir / "change_events.jsonl").write_text(
                json.dumps(legacy) + "\n", encoding="utf-8"
            )
            with patch.object(report, "ROOT", temp_dir):
                self.assertEqual(report.read_events(), [])

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
