import pathlib
import re
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pc-price-monitor.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_primary_workflow_runs_full_regression_gate_before_every_collection(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        smoke_at = text.index("Production syntax and fail-closed smoke gate")
        regression_at = text.index("Full regression gate before every production collection")
        gate_at = text.index("Check whether regular monitoring should run")
        monitor_at = text.index("python scripts/monitor.py")
        self.assertLess(smoke_at, regression_at)
        self.assertLess(regression_at, gate_at)
        self.assertLess(gate_at, monitor_at)
        self.assertIn('python -m unittest discover -s tests -p "test_production_contract.py" -v', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py" -v', text)
        self.assertNotIn("if: github.event_name != 'schedule'", text)

    def test_fast_workflow_has_full_regression_gate_before_monitoring(self):
        path = ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml"
        text = path.read_text(encoding="utf-8")
        gate_at = text.index("Production syntax and regression gate")
        window_at = text.index("Check provisional broad watch window")
        monitor_at = text.index("python scripts/monitor.py")
        self.assertLess(gate_at, window_at)
        self.assertLess(window_at, monitor_at)
        self.assertIn('python -m py_compile scripts/*.py', text)
        self.assertIn('python -m unittest discover -s tests -p "test_*.py" -v', text)

    def test_monitor_cron_has_five_and_fifteen_minute_schedules(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "3-59/5 * * * *"', text)
        self.assertIn('cron: "7,22,37,52 * * * *"', text)

    def test_schedule_gate_uses_cron_expression_not_runner_start_minute(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SCHEDULE_CRON: ${{ github.event.schedule }}", text)
        self.assertIn('expected_cron = "3-59/5 * * * *" if in_watch_window else "7,22,37,52 * * * *"', text)
        self.assertIn("run_now = schedule_cron == expected_cron", text)
        self.assertNotIn("regular_due = now.minute % 15 == 0", text)

    def test_campaign_calendar_runs_before_price_strategy_reports(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        calendar_at = text.index("python scripts/official_campaign_dates.py")
        report_at = text.index("python scripts/report.py")
        timing_at = text.index("python scripts/timing_analysis.py")
        self.assertLess(calendar_at, report_at)
        self.assertLess(calendar_at, timing_at)

    def test_watch_window_does_not_hardcode_2026_campaign_dates(self):
        paths = (
            WORKFLOW,
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
            ROOT / "scripts" / "watchdog.py",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("datetime(2026, 11, 14", text, str(path))
            self.assertNotIn("datetime(2026,11,14", text, str(path))
            self.assertNotIn("datetime(2026, 12, 4", text, str(path))
            self.assertNotIn("datetime(2026,12,4", text, str(path))
        fast = paths[1].read_text(encoding="utf-8")
        watchdog = paths[2].read_text(encoding="utf-8")
        self.assertIn('cfg["monitor_window_start"]', fast)
        self.assertIn('cfg["monitor_window_end"]', fast)
        self.assertIn("monitor_window_start", watchdog)
        self.assertIn("monitor_window_end", watchdog)

    def test_fast_workflow_refreshes_official_dates_before_decision_reports(self):
        text = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("provisional broad watch window", text)
        self.assertIn("sale_dates_inferred=false", text)
        calendar_at = text.index("python scripts/official_campaign_dates.py")
        report_at = text.index("python scripts/report.py")
        timing_at = text.index("python scripts/timing_analysis.py")
        self.assertLess(calendar_at, report_at)
        self.assertLess(calendar_at, timing_at)

    def test_primary_workflow_runs_peripheral_observer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python scripts/peripheral_monitor.py", text)

    def test_diy_planner_runs_before_derived_timing_and_scenarios(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
            ROOT / ".github" / "workflows" / "pc-price-tests.yml",
        ):
            text = path.read_text(encoding="utf-8")
            planner_at = text.index("python scripts/self_build_planner.py")
            timing_at = text.index("python scripts/timing_analysis.py")
            scenario_at = text.index("python scripts/scenario_analysis.py")
            self.assertLess(planner_at, timing_at, str(path))
            self.assertLess(planner_at, scenario_at, str(path))

    def test_fast_workflow_has_no_duplicate_schedule(self):
        text = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn('MONITOR_MAX_URLS: "100"', text)

    def test_embedded_python_blocks_are_syntactically_valid(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            snippets = []
            lines = text.splitlines()
            index = 0
            while index < len(lines):
                if lines[index].strip().startswith("python - <<'PY'"):
                    index += 1
                    block = []
                    while index < len(lines) and lines[index].strip() != "PY":
                        block.append(lines[index])
                        index += 1
                    self.assertTrue(block, f"{path}: embedded block is empty")
                    snippets.append(textwrap.dedent(chr(10).join(block)))
                index += 1
            self.assertTrue(snippets, str(path))
            for number, snippet in enumerate(snippets, start=1):
                compile(snippet, f"{path}:embedded-python-{number}", "exec")

    def test_watchlist_refresh_detects_missing_catalog_candidates(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("missing_catalog_ids=catalog_ids - watch_ids", text)
            self.assertIn("or bool(missing_catalog_ids)", text)

    def test_watchlist_refresh_detects_catalog_url_mismatches(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("catalog_url_mismatch_ids", text)
            self.assertIn("or bool(catalog_url_mismatch_ids)", text)

    def test_primary_and_fast_workflows_share_current_writer_lock_without_cancelling_active_collection(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        fast = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("group: pc-price-intelligence-writer-v3", text)
        self.assertIn("group: pc-price-intelligence-writer-v3", fast)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("cancel-in-progress: false", fast)

    def test_main_sync_is_revalidated_before_every_collection_attempt(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            reset_at = text.index("git reset --hard origin/main")
            syntax_at = text.index("python -m py_compile scripts/*.py", reset_at)
            focused_tests_at = text.index('python -m unittest discover -s tests -p "test_production_contract.py" -v', reset_at)
            regression_at = text.index('python -m unittest discover -s tests -p "test_*.py" -v', reset_at)
            monitor_at = text.index("python scripts/monitor.py", reset_at)
            self.assertLess(reset_at, syntax_at, str(path))
            self.assertLess(syntax_at, focused_tests_at, str(path))
            self.assertLess(focused_tests_at, regression_at, str(path))
            self.assertLess(regression_at, monitor_at, str(path))

    def test_monitor_limit_allows_full_discovered_watchlist(self):
        text = (ROOT / "scripts" / "monitor.py").read_text(encoding="utf-8")
        self.assertIn('MONITOR_MAX_URLS", "100"', text)

    def test_watchdog_checks_freshness_and_recovers_default_branch_failures(self):
        watchdog = (ROOT / ".github" / "workflows" / "pc-price-watchdog.yml").read_text(encoding="utf-8")
        primary = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "*/5 * * * *"', watchdog)
        self.assertIn("workflow_run:", watchdog)
        self.assertIn('"PC Price Intelligence"', watchdog)
        self.assertIn('"PC Price Intelligence - Tests"', watchdog)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", watchdog)
        self.assertIn("github.event.workflow_run.run_attempt == 1", watchdog)
        # A collector can conclude success yet leave stale snapshots; this is
        # still an unhealthy run and must trigger one bounded recovery.
        self.assertIn("github.event.workflow_run.conclusion == 'success'", watchdog)
        self.assertIn("!contains(github.event.workflow_run.display_title, '[watchdog-recovery]')", watchdog)
        self.assertEqual(watchdog.count("gh workflow run pc-price-monitor.yml --ref main -f watchdog_recovery=true"), 2)
        # The recovery marker is part of the run title so its completion cannot
        # trigger a recursive chain of recovery dispatches.
        self.assertIn("inputs.watchdog_recovery == true && ' [watchdog-recovery]'", primary)
        self.assertIn("watchdog_recovery:", primary)
        self.assertNotIn('cron: "12,27,42,57 * * * *"', watchdog)

if __name__ == "__main__":
    unittest.main()
