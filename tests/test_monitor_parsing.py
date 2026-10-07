import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence
import monitor


class MonitorParsingTests(unittest.TestCase):
    def test_discount_amount_is_not_selected_as_price(self):
        picked = intelligence.pick_price("90,000円OFF / 販売価格 329,800円(税込)")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["price_jpy"], 329800)

    def test_multiple_structured_prices_fail_closed(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Test PC","offers":[
          {"price":"329800","priceCurrency":"JPY","availability":"https://schema.org/InStock"},
          {"price":"289800","priceCurrency":"JPY","availability":"https://schema.org/InStock"}
        ]}
        </script>
        販売価格 329,800円
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_ambiguity"], "multiple_structured_prices")

    def test_multiple_availability_states_fail_closed(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","offers":[
          {"price":"329800","priceCurrency":"JPY","availability":"https://schema.org/InStock"},
          {"price":"289800","priceCurrency":"JPY","availability":"https://schema.org/OutOfStock"}
        ]}
        </script>
        在庫あり
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["stock_status"], "unknown")
        self.assertEqual(parsed["stock_ambiguity"], "multiple_offer_availability")

    def test_meta_price_is_distinct_source(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="279800">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["price_source_mode"], "direct_meta")

    def test_benefit_signals_are_recorded_but_not_counted_as_cash(self):
        html = """
        <html><body>
        販売価格 289,800円
        5,000円分ポイント還元
        周辺機器同時購入で30%OFF
        在庫あり
        </body></html>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        kinds = {x["kind"] for x in parsed["benefit_signals"]}
        self.assertIn("point_value_jpy", kinds)
        self.assertIn("accessory_bundle_percent", kinds)
        self.assertEqual(parsed["confirmed_benefit_value_jpy"], 0)
        self.assertEqual(parsed["benefit_confidence"], "unconfirmed")
        self.assertTrue(all(not x["counts_toward_effective_cost"] for x in parsed["benefit_signals"]))


if __name__ == "__main__":
    unittest.main()
