import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("report",ROOT/"scripts"/"report.py")
report=importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

class DecisionScoringTests(unittest.TestCase):
    def candidate(self, price=280000, gpu="RTX 5070 Ti Laptop GPU", cpu="Ryzen 9 9955HX", tgp=115, ram=32, ssd="1 TB"):
        return {
            "name": f"{cpu} {gpu}",
            "price_jpy": price,
            "fetch_status": "ok",
            "stock_status": "in_stock",
            "spec": {"gpu":gpu,"cpu":cpu,"tgp_w":tgp,"ram_gb":ram,"ssd":ssd}
        }

    def test_budget_discount(self):
        self.assertEqual(report.required_discount(280000),0)
        self.assertAlmostEqual(report.required_discount(350000),20.0,places=6)

    def test_price_score_monotonic(self):
        self.assertGreater(report.price_score(280000),report.price_score(350000))
        self.assertGreater(report.price_score(350000),report.price_score(450000))

    def test_tgp_affects_performance(self):
        low=report.performance_score(self.candidate(tgp=85))[0]
        high=report.performance_score(self.candidate(tgp=140))[0]
        self.assertGreater(high,low)

    def test_5070ti_beats_5070(self):
        ti=report.performance_score(self.candidate(gpu="RTX 5070 Ti Laptop GPU"))[0]
        base=report.performance_score(self.candidate(gpu="RTX 5070 Laptop GPU"))[0]
        self.assertGreater(ti,base)

    def test_score_components_sum_to_100(self):
        total,_=report.decision_score(self.candidate(price=280000),[])
        self.assertLessEqual(total,100)
        self.assertGreater(total,0)

if __name__=="__main__":
    unittest.main()
