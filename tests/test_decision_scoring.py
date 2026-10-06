import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("intelligence", ROOT / "scripts" / "intelligence.py")
intelligence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intelligence)

class DecisionScoringTests(unittest.TestCase):
    def candidate(
        self,
        price=280000,
        gpu="RTX 5070 Ti Laptop GPU",
        cpu="Ryzen 9 9955HX",
        tgp=115,
        ram=32,
        ssd="1 TB",
        stock="in_stock",
        source="direct_structured",
        variant="exact",
    ):
        return {
            "id": "test",
            "name": f"{cpu} {gpu}",
            "current_price_jpy": price,
            "price_jpy": price,
            "stock_status": stock,
            "price_source_mode": source,
            "price_validation_status": "validated",
            "data_confidence": "high",
            "variant_match": variant,
            "family": "Test",
            "spec": {
                "gpu": gpu,
                "cpu": cpu,
                "tgp_w": tgp,
                "ram_gb": ram,
                "ssd": ssd,
            },
            "retrieval_time": intelligence.iso(intelligence.now_jst()),
            "available_at": intelligence.iso(intelligence.now_jst()),
        }

    def test_budget_discount(self):
        self.assertEqual(intelligence.required_discount(280000), 0)
        self.assertAlmostEqual(intelligence.required_discount(350000), 20.0, places=6)

    def test_scenario_prices(self):
        s = intelligence.scenario_prices(400000)
        self.assertEqual(s[0]["price_jpy"], 360000)
        self.assertEqual(s[-1]["price_jpy"], 280000)

    def test_price_score_monotonic(self):
        self.assertGreater(intelligence.price_score(280000), intelligence.price_score(350000))
        self.assertGreater(intelligence.price_score(350000), intelligence.price_score(450000))

    def test_tgp_affects_performance(self):
        low = intelligence.performance_score(self.candidate(tgp=85))[0]
        high = intelligence.performance_score(self.candidate(tgp=140))[0]
        self.assertGreater(high, low)

    def test_5070ti_beats_5070(self):
        ti = intelligence.performance_score(self.candidate(gpu="RTX 5070 Ti Laptop GPU"))[0]
        base = intelligence.performance_score(self.candidate(gpu="RTX 5070 Laptop GPU"))[0]
        self.assertGreater(ti, base)

    def test_anomalous_price_rejected(self):
        item = self.candidate(price=90000, gpu="RTX 5070 Laptop GPU")
        result = intelligence.validate_price(90000, item, reference_price=329800, corroborated=False)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "anomaly_rejected")

    def test_anomalous_price_can_be_corroborated(self):
        item = self.candidate(price=90000, gpu="RTX 5070 Laptop GPU")
        result = intelligence.validate_price(90000, item, reference_price=329800, corroborated=True)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "anomaly_corroborated")

    def test_ambiguous_variant_is_capped(self):
        item = self.candidate(variant="ambiguous")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 74)
        self.assertEqual(detail["score_cap"], 74)

    def test_unknown_stock_is_capped(self):
        item = self.candidate(stock="unknown")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 89)

    def test_score_components_sum_within_100(self):
        item = self.candidate()
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 100)
        self.assertLessEqual(
            sum(detail[k] for k in ("performance","price","history","stock","timing")),
            100
        )

if __name__ == "__main__":
    unittest.main()
