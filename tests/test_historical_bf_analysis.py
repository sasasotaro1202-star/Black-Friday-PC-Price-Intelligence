import importlib.util, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "historical_bf_analysis.py")
SPEC = importlib.util.spec_from_file_location("historical_bf_analysis", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

class HistoricalBFAnalysisTests(unittest.TestCase):
    def test_discount_math(self):
        self.assertEqual(MOD.pct_discount(14800, 9980), 32.6)
        self.assertEqual(MOD.pct_discount(5500, 3999), 27.3)
        self.assertIsNone(MOD.pct_discount(None, 10000))

    def test_curated_history_validates_and_avoids_false_typical_discount(self):
        campaigns, deals = MOD.load_records()
        self.assertGreaterEqual(len(campaigns["campaigns"]), 15)
        self.assertGreaterEqual(len(deals), 20)
        out = MOD.summarize(campaigns, deals)
        self.assertIn(2025, out["campaign_years_covered"])
        self.assertFalse(out["forecast_policy"]["probability_model_enabled"])
        self.assertIsNone(out["categories"]["monitor"]["comparable_discount_median_pct"])

    def test_pc_koubou_sale_does_not_meet_required_ram(self):
        campaigns, deals = MOD.load_records()
        row = next(d for d in deals if d["model"] == "LEVEL-M5A6-R97X-TKX")
        self.assertEqual(row["ram_gb"], 16)
        self.assertEqual(row["comparability_group"], "not_eligible_ram16")

if __name__ == "__main__":
    unittest.main()
