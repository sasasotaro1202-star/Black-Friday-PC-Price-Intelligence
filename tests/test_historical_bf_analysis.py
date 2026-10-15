import importlib.util, json, os, sys, unittest
from urllib.parse import urlparse

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
        self.assertGreaterEqual(len(campaigns["campaigns"]), 20)
        self.assertGreaterEqual(len(deals), 35)
        out = MOD.summarize(campaigns, deals)
        self.assertIn(2025, out["campaign_years_covered"])
        self.assertIn(2022, out["campaign_years_covered"])
        self.assertEqual(out["historical_deal_record_count"], len(deals))
        self.assertEqual(len(out["price_observations"]), len(deals))
        for row in deals:
            self.assertTrue(row["source_url"].startswith("https://"))
            self.assertGreater(row["sale_price_jpy"], 0)
        self.assertFalse(out["forecast_policy"]["probability_model_enabled"])
        self.assertIsNone(out["categories"]["monitor"]["comparable_discount_median_pct"])


    def test_purchase_channel_and_budget_contract(self):
        with open(os.path.join(ROOT, "config", "targets.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(set(cfg["purchase_channels"]["physical_store_categories"]),
                         {"main_monitor", "mouse", "keyboard", "speakers"})
        self.assertEqual(set(cfg["purchase_channels"]["online_categories"]),
                         {"secondary_monitor", "mousepad", "power_strip", "cables"})
        self.assertEqual(cfg["purchase_channels"]["pc_body"]["channel"], "online")
        items = cfg["peripherals"]
        self.assertEqual(sum(int(p.get("target_price_jpy") or 0) for p in items if p.get("mandatory", True)),
                         cfg["peripheral_budget_jpy"])
        self.assertEqual(cfg["pc_budget_jpy"] + cfg["peripheral_budget_jpy"], cfg["total_budget_jpy"])
        for p in items:
            if p.get("purchase_channel") == "physical_store":
                self.assertTrue(p.get("store_inventory_required_before_purchase"))
                self.assertTrue(p.get("online_price_is_comparison_only"))
                self.assertTrue(p.get("physical_store_candidate_ids"))
            for url in p.get("monitor_urls") or []:
                self.assertIn(urlparse(url).netloc, p.get("allowed_hosts") or [],
                              msg=f"Configured monitoring URL host not allowed for {p.get('id')}: {url}")

    def test_pc_koubou_sale_does_not_meet_required_ram(self):
        campaigns, deals = MOD.load_records()
        row = next(d for d in deals if d["model"] == "LEVEL-M5A6-R97X-TKX")
        self.assertEqual(row["ram_gb"], 16)
        self.assertEqual(row["comparability_group"], "not_eligible_ram16")

if __name__ == "__main__":
    unittest.main()
