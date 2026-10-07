import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("intelligence", ROOT / "scripts" / "intelligence.py")
intelligence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intelligence)
sys.modules["intelligence"] = intelligence

monitor_spec = importlib.util.spec_from_file_location("monitor", ROOT / "scripts" / "monitor.py")
monitor = importlib.util.module_from_spec(monitor_spec)
monitor_spec.loader.exec_module(monitor)

class DecisionScoringTests(unittest.TestCase):
    def candidate(self, price=280000, gpu="RTX 5070 Ti Laptop GPU", cpu="Ryzen 9 9955HX",
                  tgp=115, ram=32, ssd="1 TB", stock="in_stock",
                  source="direct_structured", variant="exact"):
        now = intelligence.iso(intelligence.now_jst())
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
            "spec": {"gpu": gpu, "cpu": cpu, "tgp_w": tgp, "ram_gb": ram, "ssd": ssd},
            "retrieval_time": now,
            "available_at": now,
            "prediction_time": now,
        }

    def test_budget_discount(self):
        self.assertEqual(intelligence.required_discount(280000), 0)
        self.assertAlmostEqual(intelligence.required_discount(350000), 20.0, places=6)

    def test_effective_cost_uses_confirmed_benefit_only(self):
        item = self.candidate(price=289000)
        item["shipping_jpy"] = 1000
        item["mandatory_fee_jpy"] = 0
        item["confirmed_benefit_value_jpy"] = 5000
        item["benefit_confidence"] = "confirmed"
        self.assertEqual(intelligence.cash_total_cost(item), 290000)
        self.assertEqual(intelligence.effective_cost(item), 285000)

    def test_unconfirmed_benefit_is_not_subtracted(self):
        item = self.candidate(price=289000)
        item["confirmed_benefit_value_jpy"] = 50000
        item["benefit_confidence"] = "conditional"
        self.assertEqual(intelligence.effective_cost(item), 289000)

    def test_near_budget_can_be_buy_now_when_effective_cost_is_strong(self):
        item = self.candidate(price=289000)
        item["confirmed_benefit_value_jpy"] = 4000
        item["benefit_confidence"] = "confirmed"
        anchors = [{"key": "test", "family": "Test", "gpu": "RTX 5070 Ti", "historical_price_jpy": 250000}]
        score, detail = intelligence.decision_score(item, anchors, [])
        self.assertEqual(detail["effective_cost_jpy"], 285000)
        self.assertEqual(detail["status"], "BUY_NOW")
        self.assertGreaterEqual(score, 90)
        self.assertLessEqual(detail["effective_cost_jpy"], intelligence.EFFECTIVE_SOFT_MAX)

    def test_over_290k_effective_cost_waits(self):
        item = self.candidate(price=300000)
        score, detail = intelligence.decision_score(item, [], [])
        self.assertEqual(detail["status"], "WAIT_FOR_DISCOUNT")

    def test_scenario_prices(self):
        s = intelligence.scenario_prices(400000)
        self.assertEqual(s[0]["price_jpy"], 360000)
        self.assertEqual(s[-1]["price_jpy"], 280000)

    def test_price_parser_rejects_monthly_context(self):
        picked = intelligence.pick_price("月々9,000円 / 販売価格 289,800円(税込)")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["price_jpy"], 289800)

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

    def test_build_row_uses_one_supplied_prediction_snapshot(self):
        snapshot = "2026-10-07T08:00:00+09:00"
        item = self.candidate()
        item["retrieval_time"] = snapshot
        item["available_at"] = snapshot
        row = intelligence.build_row(item, [], [], prediction_time=snapshot)
        self.assertEqual(row["prediction_time"], snapshot)
        self.assertEqual(
            row["score_detail"]["observation_age_minutes"],
            0.0,
        )

    def test_missing_pit_is_unactionable(self):
        item = self.candidate()
        item["available_at"] = None
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNone(score)
        self.assertEqual(detail["status"], "UNACTIONABLE")

    def test_shared_family_variant_is_never_exact(self):
        item = {"id":"x","url":"https://example.com/family","name":"ROG Strix G16",
                "page_text_excerpt":"ROG Strix G16","parsed_spec":{}}
        cat = {"id":"x","url":"https://example.com/family","url_is_exact":False,
               "name":"ROG Strix G16","family":"ROG Strix G16",
               "cpu":"Ryzen 9 9955HX3D","gpu":"RTX 5070 Ti","identity_confidence":"high"}
        out = intelligence.enrich_identity(item, cat)
        self.assertEqual(out["variant_match"], "ambiguous")

    def test_history_exact_beats_family(self):
        item = {"id":"exact-id","name":"TUF Gaming A16 FA608PP-R9R5070S",
                "family":"TUF Gaming A16","spec":{"gpu":"RTX 5070 Laptop GPU"}}
        anchors=[{"key":"TUF Gaming A16 FA608PP","family":"TUF Gaming A16",
                  "gpu":"RTX 5070","historical_price_jpy":219800}]
        score,_=intelligence.history_score(item,anchors)
        self.assertGreaterEqual(score,12)

    def test_dynamic_candidate_is_capped(self):
        item = self.candidate()
        item["dynamic_candidate"]=True
        score,detail=intelligence.decision_score(item,[],[])
        self.assertLessEqual(score,74)

    def test_ambiguous_variant_is_capped(self):
        item = self.candidate(variant="ambiguous")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 74)
        self.assertEqual(detail["score_cap"], 74)

    def test_out_of_stock_is_not_buy_now(self):
        item = self.candidate(price=250000, stock="out_of_stock")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertEqual(detail["status"], "UNAVAILABLE")

    def test_direct_text_is_verify_only(self):
        item = self.candidate(price=250000, source="direct_text")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertEqual(detail["status"], "VERIFY_NOW")

    def test_meta_price_is_verify_only(self):
        item = self.candidate(price=250000, source="direct_meta")
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNotNone(score)
        self.assertEqual(detail["status"], "VERIFY_NOW")

    def test_stale_observation_is_unactionable(self):
        item = self.candidate()
        old = intelligence.now_jst() - intelligence.timedelta(minutes=61)
        item["retrieval_time"] = intelligence.iso(old)
        item["available_at"] = intelligence.iso(old)
        item["prediction_time"] = intelligence.iso(intelligence.now_jst())
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNone(score)
        self.assertEqual(detail["reason"], "stale_observation")

    def test_pit_requires_retrieval_before_prediction(self):
        item = self.candidate()
        future = intelligence.now_jst() + intelligence.timedelta(minutes=1)
        item["retrieval_time"] = intelligence.iso(future)
        score, detail = intelligence.decision_score(item, [], [])
        self.assertIsNone(score)
        self.assertEqual(detail["reason"], "retrieval_after_prediction")

    def test_exact_catalog_cannot_override_parsed_conflict(self):
        item = {
            "id":"x","url":"https://example.com/exact","name":"Expected",
            "page_text_excerpt":"Expected RTX 5070 Ti Core Ultra 9 275HX",
            "parsed_spec":{"gpu":"RTX 5070 Laptop GPU","cpu":"Core Ultra 9 275HX","ram_gb":32,"ssd":"1 TB","tgp_w":115}
        }
        cat = {
            "id":"x","url":"https://example.com/exact","url_is_exact":True,
            "name":"Expected","family":"Expected","cpu":"Core Ultra 9 275HX",
            "gpu":"RTX 5070 Ti Laptop GPU","ram_gb":32,"ssd":"1 TB","tgp_w":115,
            "identity_confidence":"high"
        }
        out = intelligence.enrich_identity(item, cat)
        self.assertEqual(out["variant_match"], "ambiguous")

    def test_stock_text_overrides_conflicting_structured_stock(self):
        self.assertEqual(monitor.stock_from_text("在庫あり 品切れ中"), "out_of_stock")

    def test_explicit_sold_out_text_overrides_jsonld_instock(self):
        html = """<script type="application/ld+json">
        {"@type":"Product","name":"Test PC","offers":{"priceCurrency":"JPY","price":"250000","availability":"https://schema.org/InStock"}}
        </script><div>販売価格 ¥250,000 品切れ中</div>"""
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["stock_status"], "out_of_stock")

    def test_score_arithmetic_matches_cap(self):
        item = self.candidate()
        score, detail = intelligence.decision_score(item, [], [])
        components = sum(detail[k] for k in ("performance", "price", "history", "stock", "timing"))
        self.assertEqual(detail["score_before_cap"], min(100, components))
        self.assertEqual(score, min(detail["score_before_cap"], detail["score_cap"]))

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
        self.assertLessEqual(sum(detail[k] for k in ("performance","price","history","stock","timing")), 100)

if __name__ == "__main__":
    unittest.main()
