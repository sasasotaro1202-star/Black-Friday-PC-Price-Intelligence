import importlib.util
import os
import subprocess
import json
import pathlib
import unittest
import tempfile
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


    def _write_self_build_fixture(self, root, *, generated_at="2026-11-20T12:00:00+09:00",
                                   selected_memory_id="ram32", all_in=(399500, 379500, 361500),
                                   report_generated_at="2026-11-20T12:00:00+09:00",
                                   pc_planned_budget_jpy=360000, soft_ceiling_total_jpy=400000,
                                   target_soft_ceiling_total_jpy=400000):
        data = pathlib.Path(root) / "data"
        config = pathlib.Path(root) / "config"
        (data / "reports").mkdir(parents=True)
        config.mkdir(parents=True)
        (data / "build_component_prices.json").write_text(
            json.dumps({"generated_at": generated_at}), encoding="utf-8"
        )
        build_ids = ["gpu5070ti", "gpu5070", "gpu5060ti"]
        builds = [
            {
                "id": build_id,
                "selected_memory_id": selected_memory_id,
                "target_pc_total_jpy": total - 40000,
                "target_all_in_jpy": total,
            }
            for build_id, total in zip(build_ids, all_in)
        ]
        (data / "self_build_plan.json").write_text(json.dumps({
            "generated_at": generated_at,
            "total_budget_jpy": 400000,
            "pc_budget_jpy": 395000,
            "pc_planned_budget_jpy": pc_planned_budget_jpy,
            "soft_ceiling_total_jpy": soft_ceiling_total_jpy,
            "peripheral_budget_jpy": 35000,
            "unallocated_contingency_jpy": 5000,
            "budget_arithmetic_valid": True,
            "builds": builds,
        }), encoding="utf-8")
        (config / "targets.json").write_text(json.dumps({
            "total_budget_jpy": 400000,
            "peripheral_budget_jpy": 35000,
            "soft_ceiling_total_jpy": target_soft_ceiling_total_jpy,
        }), encoding="utf-8")
        (config / "build_components.json").write_text(json.dumps({
            "profile": {"primary_memory_choice_id": "ram32"},
            "parts": [
                {"id": "ram32", "specs": {"capacity_gb": 32}},
                {"id": "ram64", "specs": {"capacity_gb": 64}},
            ],
        }), encoding="utf-8")
        for relative in ("reports/latest.md", "reports/self-build-ranking.md"):
            (data / relative).write_text(
                "# Ranking\n\n更新: " + report_generated_at + "\n",
                encoding="utf-8",
            )

    def test_self_build_artifact_audit_accepts_fresh_budget_consistent_32gb_baseline(self):
        now = datetime(2026, 11, 20, 12, 1, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_self_build_fixture(temp_dir)
            problems = watchdog.self_build_artifact_problems(
                temp_dir, now, timedelta(minutes=45)
            )
        self.assertEqual(problems, [])

    def test_self_build_artifact_audit_uses_soft_ceiling_for_dynamic_pc_budget(self):
        now = datetime(2026, 11, 20, 12, 1, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_self_build_fixture(
                temp_dir,
                pc_planned_budget_jpy=380000,
                soft_ceiling_total_jpy=420000,
                target_soft_ceiling_total_jpy=420000,
            )
            problems = watchdog.self_build_artifact_problems(
                temp_dir, now, timedelta(minutes=45)
            )
        self.assertEqual(problems, [])

    def test_self_build_artifact_audit_flags_soft_ceiling_config_drift(self):
        now = datetime(2026, 11, 20, 12, 1, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_self_build_fixture(
                temp_dir,
                pc_planned_budget_jpy=380000,
                soft_ceiling_total_jpy=420000,
                target_soft_ceiling_total_jpy=400000,
            )
            problems = watchdog.self_build_artifact_problems(
                temp_dir, now, timedelta(minutes=45)
            )
        self.assertIn("self_build_soft_ceiling_differs_from_target_config", problems)

    def test_self_build_artifact_audit_flags_stale_plan_and_reports(self):
        now = datetime(2026, 11, 20, 13, 0, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_self_build_fixture(
                temp_dir,
                generated_at="2026-11-20T12:00:00+09:00",
                report_generated_at="2026-11-20T12:00:00+09:00",
            )
            problems = watchdog.self_build_artifact_problems(
                temp_dir, now, timedelta(minutes=45)
            )
        self.assertIn("build_component_prices_stale", problems)
        self.assertIn("self_build_plan_stale", problems)
        self.assertIn("latest_report_stale", problems)
        self.assertIn("self_build_report_stale", problems)

    def test_self_build_artifact_audit_flags_memory_and_budget_regressions(self):
        now = datetime(2026, 11, 20, 12, 1, tzinfo=JST)
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_self_build_fixture(
                temp_dir,
                selected_memory_id="ram64",
                all_in=(441500, 421500, 403500),
            )
            problems = watchdog.self_build_artifact_problems(
                temp_dir, now, timedelta(minutes=45)
            )
        self.assertIn("no_self_build_target_fits_total_budget", problems)
        self.assertEqual(
            sum(1 for problem in problems if problem.startswith("self_build_base_memory_capacity_mismatch:")),
            3,
        )


class SnapshotInputFreshnessTests(unittest.TestCase):
    def _git(self, root, *args, env=None):
        return subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def _commit(self, root, timestamp, message):
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = timestamp
        env["GIT_COMMITTER_DATE"] = timestamp
        self._git(root, "add", ".")
        self._git(root, "commit", "-m", message, env=env)

    def test_snapshot_older_than_inputs_is_detected(self):
        self.assertTrue(watchdog.snapshot_predates_inputs(
            "2026-10-28T17:56:23+09:00",
            "2026-10-28T18:05:48+09:00",
        ))

    def test_snapshot_newer_than_inputs_is_not_stale_by_revision(self):
        self.assertFalse(watchdog.snapshot_predates_inputs(
            "2026-10-28T18:10:00+09:00",
            "2026-10-28T18:05:48+09:00",
        ))

    def test_latest_input_timestamp_ignores_newer_data_only_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            self._git(root, "init", "-q", "-b", "main")
            self._git(root, "config", "user.name", "Watchdog Test")
            self._git(root, "config", "user.email", "watchdog-test@example.invalid")
            (root / "config").mkdir()
            (root / "data").mkdir()
            (root / "config" / "targets.json").write_text("{}", encoding="utf-8")
            source_timestamp = "2026-10-28T09:05:00+00:00"
            self._commit(root, source_timestamp, "config: initial runtime input")
            (root / "data" / "current_latest.json").write_text("{}", encoding="utf-8")
            self._commit(root, "2026-10-28T12:00:00+00:00", "data: newer observation")
            observed = watchdog.latest_input_change_at(str(root))
            self.assertEqual(observed, watchdog.parse_dt(source_timestamp))

    def test_missing_git_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(watchdog.latest_input_change_at(temp_dir))


if __name__ == "__main__":
    unittest.main()
