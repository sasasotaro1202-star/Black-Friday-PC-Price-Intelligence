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

    def test_monitor_limit_allows_full_discovered_watchlist(self):
        text = (ROOT / "scripts" / "monitor.py").read_text(encoding="utf-8")
        self.assertIn('MONITOR_MAX_URLS", "100"', text)

if __name__ == "__main__":
    unittest.main()
