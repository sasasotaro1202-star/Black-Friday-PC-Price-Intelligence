import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pc-price-monitor.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_monitor_cron_runs_every_five_minutes(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "*/5 * * * *"', text)

    def test_workflow_keeps_normal_15_minute_gate(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("regular_due = now.minute % 15 == 0", text)
        self.assertIn('run_now = event != "schedule" or in_bf or regular_due', text)

    def test_primary_workflow_runs_peripheral_observer(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python scripts/peripheral_monitor.py", text)

    def test_fast_workflow_has_no_duplicate_schedule(self):
        text = (ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn('MONITOR_MAX_URLS: "100"', text)

    def test_primary_workflow_does_not_cancel_in_progress_collection(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cancel-in-progress: false", text)

    def test_watchlist_discovery_runs_after_remote_reset_before_collection(self):
        for path in (
            ROOT / ".github" / "workflows" / "pc-price-monitor.yml",
            ROOT / ".github" / "workflows" / "pc-price-monitor-bf-fast.yml",
        ):
            text = path.read_text(encoding="utf-8")
            reset_at = text.index("git reset --hard origin/main")
            discovery_at = text.index("python scripts/discover.py", reset_at)
            monitor_at = text.index("python scripts/monitor.py", reset_at)
            self.assertLess(reset_at, discovery_at, str(path))
            self.assertLess(discovery_at, monitor_at, str(path))

    def test_monitor_limit_allows_full_discovered_watchlist(self):
        text = (ROOT / "scripts" / "monitor.py").read_text(encoding="utf-8")
        self.assertIn('MONITOR_MAX_URLS", "100"', text)

if __name__ == "__main__":
    unittest.main()
