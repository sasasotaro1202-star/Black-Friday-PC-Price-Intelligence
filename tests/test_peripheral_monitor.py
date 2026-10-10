import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import peripheral_monitor


class PeripheralMonitorTests(unittest.TestCase):
    def setUp(self):
        self.target = {
            "id": "main_monitor",
            "name": "AOC Q27G40E/11 27-inch WQHD 180Hz",
            "monitor_url": "https://www.yodobashi.com/product/example/",
            "purchase_url": "https://www.yodobashi.com/product/example/",
            "identity_terms": ["Q27G40E/11", "Q27G40E"],
            "allowed_hosts": ["www.yodobashi.com"],
            "min_price_jpy": 10000,
            "max_price_jpy": 60000,
            "target_price_jpy": 17500,
        }

    def test_g213r_is_a_tracked_bf_target_with_exact_retail_url(self):
        config = __import__("json").loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = next(x for x in config["peripherals"] if x["id"] == "keyboard")
        self.assertTrue(target["track_current_price"])
        self.assertEqual(target["monitor_url"], "https://www.biccamera.com/bc/item/9242996/")
        self.assertEqual(target["target_price_jpy"], 5500)
        self.assertIn("G213r", target["identity_terms"])
        self.assertIn("www.biccamera.com", target["allowed_hosts"])

    def test_exact_model_context_resolves_price_and_low_stock(self):
        excerpt = (
            "AOC Q27G40E/11 ゲーミングモニター ￥20,790 2,079ゴールドポイント "
            "在庫残少 ご注文はお早めに 関連商品 お取り寄せ"
        )
        parsed = {
            "page_text_excerpt": excerpt,
            "price_jpy": None,
            "price_source_mode": "none",
            "price_context": None,
            "stock_status": "preorder_or_backorder",
            "name": "AOC Q27G40E/11",
        }
        with patch.object(peripheral_monitor, "fetch", return_value=("<html></html>", self.target["monitor_url"], {})), \
             patch.object(peripheral_monitor, "parse_page", return_value=parsed) as parse:
            row = peripheral_monitor.run_one(self.target, {}, "2026-10-10T15:00:00+09:00")
        expected = parse.call_args.kwargs["expected"]
        self.assertIn("Q27G40E/11", expected["aliases"])
        self.assertTrue(row["identity_verified"])
        self.assertTrue(row["price_verified"])
        self.assertEqual(row["current_price_jpy"], 20790)
        self.assertEqual(row["price_source_mode"], "direct_text")
        self.assertEqual(row["stock_status"], "low_stock")

    def test_exact_product_window_does_not_read_global_page_status(self):
        context = "AOC Q27G40E/11 ￥20,790 在庫あり 関連商品 取り寄せ"
        stock = peripheral_monitor.local_product_stock(context, "preorder_or_backorder")
        self.assertEqual(stock, "in_stock")

    def test_second_exact_model_url_is_tried_when_first_transport_fails(self):
        target = dict(self.target)
        target["monitor_urls"] = [
            "https://www.biccamera.com/bc/item/9242996/",
            "https://item.rakuten.co.jp/logicool/g213r/",
        ]
        target["allowed_hosts"] = ["www.biccamera.com", "item.rakuten.co.jp"]
        target["identity_terms"] = ["G213r", "G213R", "9242996"]
        target["min_price_jpy"] = 3000
        target["max_price_jpy"] = 15000
        parsed = {
            "page_text_excerpt": "Logicool G213r 型番 G213R ￥7,330 在庫あり",
            "price_jpy": 7330,
            "price_source_mode": "direct_structured",
            "price_context": None,
            "stock_status": "in_stock",
            "name": "Logicool G213r",
        }
        with patch.object(peripheral_monitor, "fetch", side_effect=[
            RuntimeError("curl_exit_35:curl_http_000:SSL connect error"),
            ("<html></html>", "https://item.rakuten.co.jp/logicool/g213r/", {}),
        ]), patch.object(peripheral_monitor, "parse_page", return_value=parsed):
            row = peripheral_monitor.run_one(target, {}, "2026-10-10T15:00:00+09:00")
        self.assertTrue(row["price_verified"])
        self.assertEqual(row["current_price_jpy"], 7330)
        self.assertTrue(row["fallback_url_used"])
        self.assertEqual(row["monitor_url_used"], "https://item.rakuten.co.jp/logicool/g213r/")
        self.assertEqual(row["purchase_url"], row["monitor_url_used"])
        self.assertIn("curl_exit_35", row["retrieval_attempts"][0]["error"])

    def test_price_outside_configured_range_remains_unverified(self):
        excerpt = "AOC Q27G40E/11 特価 ￥7,000 在庫あり"
        parsed = {
            "page_text_excerpt": excerpt,
            "price_jpy": None,
            "price_source_mode": "none",
            "price_context": None,
            "stock_status": "in_stock",
            "name": "AOC Q27G40E/11",
        }
        with patch.object(peripheral_monitor, "fetch", return_value=("<html></html>", self.target["monitor_url"], {})), \
             patch.object(peripheral_monitor, "parse_page", return_value=parsed):
            row = peripheral_monitor.run_one(self.target, {}, "2026-10-10T15:00:00+09:00")
        self.assertFalse(row["price_verified"])
        self.assertIsNone(row["current_price_jpy"])
        self.assertEqual(row["unverified_price_candidate_jpy"], 7000)


if __name__ == "__main__":
    unittest.main()
