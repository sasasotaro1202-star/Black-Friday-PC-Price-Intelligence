import importlib.util
import pathlib
import unittest
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pc_price_watchdog_under_test", ROOT / "scripts" / "watchdog.py")
watchdog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watchdog)
JST = timezone(timedelta(hours=9))


class ConfiguredWatchWindowTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "monitor_window_start": "2026-11-01T00:00:00+09:00",
            "monitor_window_end": "2026-12-11T23:59:59+09:00",
            "monitor_window_type": "PROVISIONAL_BROAD_WATCH_WINDOW",
        }

    def test_configured_start_and_end_are_inclusive(self):
        start = datetime(2026, 11, 1, 0, 0, 0, tzinfo=JST)
        end = datetime(2026, 12, 11, 23, 59, 59, tzinfo=JST)
        self.assertTrue(watchdog.configured_watch_window(start, self.config))
        self.assertTrue(watchdog.configured_watch_window(end, self.config))

    def test_dates_outside_configured_window_are_outside(self):
        before = datetime(2026, 10, 31, 23, 59, 59, tzinfo=JST)
        after = datetime(2026, 12, 12, 0, 0, 0, tzinfo=JST)
        self.assertFalse(watchdog.configured_watch_window(before, self.config))
        self.assertFalse(watchdog.configured_watch_window(after, self.config))

    def test_invalid_or_reversed_window_is_unknown(self):
        self.assertIsNone(watchdog.configured_watch_window(datetime(2026, 11, 1, tzinfo=JST), {}))
        invalid = dict(self.config, monitor_window_start="bad date")
        self.assertIsNone(watchdog.configured_watch_window(datetime(2026, 11, 1, tzinfo=JST), invalid))
        reversed_window = dict(self.config, monitor_window_start="2026-12-12T00:00:00+09:00")
        self.assertIsNone(watchdog.configured_watch_window(datetime(2026, 11, 1, tzinfo=JST), reversed_window))


if __name__ == "__main__":
    unittest.main()
