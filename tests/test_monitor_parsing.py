import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence
import monitor


class MonitorParsingTests(unittest.TestCase):
    def test_curl_http_000_preserves_transport_exit_and_stderr(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from urllib.error import URLError
        fake = SimpleNamespace(
            stdout=b"page\n__BF_STATUS__:000\n__BF_URL__:https://example.com/product",
            stderr=b"SSL connect error",
            returncode=35,
        )
        with patch.object(monitor, "urlopen", side_effect=URLError("blocked")), \
             patch.object(monitor.time, "sleep"), \
             patch.object(monitor.subprocess, "run", return_value=fake) as run_mock:
            with self.assertRaisesRegex(RuntimeError, "curl_exit_35.*SSL connect error"):
                monitor.fetch("https://example.com/product", timeout=1)
        self.assertIn("--http1.1", run_mock.call_args.args[0])

    def test_http_transport_uses_http11_after_http2_stream_errors(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from urllib.error import URLError
        fake = SimpleNamespace(
            stdout=b"page\n__BF_STATUS__:000\n__BF_URL__:https://example.com/product",
            stderr=b"HTTP/2 stream error",
            returncode=92,
        )
        with patch.object(monitor, "urlopen", side_effect=URLError("blocked")), \
             patch.object(monitor.time, "sleep"), \
             patch.object(monitor.subprocess, "run", return_value=fake) as run_mock:
            with self.assertRaisesRegex(RuntimeError, "curl_exit_92"):
                monitor.fetch("https://example.com/product", timeout=1)
        self.assertIn("--http1.1", run_mock.call_args.args[0])

    def test_candidate_fetch_uses_curated_exact_model_alternate_after_http_failure(self):
        from unittest.mock import patch
        cat = {
            "id": "test-exact",
            "name": "Test Exact Desktop MODEL-EXACT",
            "aliases": ["MODEL-EXACT"],
            "model_code": "MODEL-EXACT",
            "form_factor": "desktop",
            "gpu": "RTX 5070",
            "cpu": "Ryzen 7 9700X",
            "ram_gb": 32,
            "ssd": "1 TB",
            "url_is_exact": True,
            "identity_confidence": "high",
            "alternate_price_urls": ["https://kakaku.com/item/K0000000000/"],
        }
        parsed = {
            "url": "https://kakaku.com/item/K0000000000/",
            "name": "Test Exact Desktop MODEL-EXACT",
            "price_jpy": 299800,
            "stock_status": "in_stock",
            "parsed_spec": {"cpu": "Ryzen 7 9700X", "gpu": "RTX 5070",
                            "ram_gb": 32, "ssd": "1 TB", "form_factor": "desktop"},
            "page_text_excerpt": "MODEL-EXACT Ryzen 7 9700X RTX 5070 32GB 1TB 299,800円 在庫あり",
            "price_source_mode": "direct_text",
            "data_confidence": "medium",
        }
        with patch.object(monitor, "fetch", side_effect=[
            RuntimeError("RuntimeError:curl_http_403"),
            ("html", "https://kakaku.com/item/K0000000000/", {}),
        ]) as fetch_mock, patch.object(monitor, "parse_page", return_value=parsed):
            cid, result, error = monitor.fetch_candidate_with_alternates(
                {"id": "test-exact", "url": "https://store.example.com/product", "query": "MODEL-EXACT"},
                cat,
            )
        self.assertEqual(cid, "test-exact")
        self.assertIsNone(error)
        self.assertEqual(result["price_jpy"], 299800)
        self.assertTrue(result["alternate_url_used"])
        self.assertEqual(result["price_source_url"], "https://kakaku.com/item/K0000000000/")
        self.assertEqual(result["alternate_url_identity_anchor"], "MODEL-EXACT")
        self.assertEqual(len(fetch_mock.call_args_list), 2)

    def test_candidate_fetch_rejects_alternate_page_without_catalogued_model_alias(self):
        from unittest.mock import patch
        cat = {
            "id": "test-exact", "name": "Test Exact Desktop MODEL-EXACT",
            "aliases": ["MODEL-EXACT"], "model_code": "MODEL-EXACT",
            "form_factor": "desktop", "gpu": "RTX 5070", "cpu": "Ryzen 7 9700X",
            "ram_gb": 32, "ssd": "1 TB", "url_is_exact": True, "identity_confidence": "high",
            "alternate_price_urls": ["https://kakaku.com/item/K0000000000/"],
        }
        parsed = {
            "name": "Another Desktop SKU-OTHER", "price_jpy": 229800,
            "stock_status": "in_stock", "parsed_spec": {"cpu":"Ryzen 7 9700X","gpu":"RTX 5070",
            "ram_gb":32,"ssd":"1 TB","form_factor":"desktop"},
            "page_text_excerpt": "Another Desktop SKU-OTHER Ryzen 7 9700X RTX 5070 32GB 1TB 229,800円",
            "price_source_mode": "direct_text", "data_confidence": "medium",
        }
        with patch.object(monitor, "fetch", side_effect=[
            RuntimeError("RuntimeError:curl_http_403"),
            ("html", "https://kakaku.com/item/K0000000000/", {}),
        ]), patch.object(monitor, "parse_page", return_value=parsed):
            cid, result, error = monitor.fetch_candidate_with_alternates(
                {"id":"test-exact","url":"https://store.example.com/product","query":"MODEL-EXACT"}, cat
            )
        self.assertIsNone(result.get("price_jpy"))
        self.assertIn("identity_rejected", error)

    def test_bing_parser_extracts_organic_model_and_snippet(self):
        html = """
        <ol id="b_results">
          <li class="b_algo">
            <h2><a href="https://www.biccamera.com/bc/item/9242996/">Logicool G213r ゲーミングキーボード</a></h2>
            <div class="b_caption"><p>G213R 7,330円 在庫あり</p></div>
          </li>
        </ol>
        """
        parser = monitor.BingSearchParser()
        parser.feed(html)
        self.assertEqual(len(parser.results), 1)
        self.assertEqual(parser.results[0]["url"], "https://www.biccamera.com/bc/item/9242996/")
        self.assertIn("G213r", parser.results[0]["title"])
        self.assertIn("7,330円", parser.results[0]["snippet"])

    def test_search_result_identity_requires_curated_model_anchor(self):
        expected = {"name": "G TUNE DG-A7G70", "aliases": ["DGA7G70B5BBDW101DECWA"]}
        valid = {"title": "G TUNE DG-A7G70 DGA7G70B5BBDW101DECWA", "snippet": "304,800円 RTX 5070"}
        wrong_sku = {"title": "G TUNE DG-A7G70 other configuration", "snippet": "229,800円 RTX 5060"}
        self.assertEqual(monitor.search_identity_anchor(valid, expected), "DGA7G70B5BBDW101DECWA")
        self.assertIsNone(monitor.search_identity_anchor(wrong_sku, expected))

    def test_search_fallback_tries_bing_after_ddg_fails_and_requires_model_identity(self):
        expected = {"name": "G TUNE DG-A7G70", "aliases": ["DGA7G70B5BBDW101DECWA"]}
        bing = [{
            "url": "https://www.biccamera.com/bc/item/9242996/",
            "title": "G TUNE DG-A7G70 DGA7G70B5BBDW101DECWA デスクトップPC",
            "snippet": "Ryzen 7 5700X RTX 5070 32GB SSD 1TB 304,800円 在庫あり",
        }]
        diagnostic = []
        from unittest.mock import patch
        with patch.object(monitor, "ddg_search", side_effect=RuntimeError("blocked")), \
             patch.object(monitor, "bing_search", return_value=bing):
            result = monitor.search_fallback("G TUNE DG-A7G70", "https://www.biccamera.com/bc/item/9242996/",
                                             expected=expected, diagnostics=diagnostic)
        self.assertIsNotNone(result)
        self.assertEqual(result["provider"], "bing")
        self.assertEqual(result["identity_anchor"], "DGA7G70B5BBDW101DECWA")
        self.assertEqual(result["price_jpy"], 304800)
        self.assertEqual(diagnostic[0]["provider"], "duckduckgo")
        self.assertEqual(diagnostic[0]["status"], "error")

    def test_search_fallback_diagnostics_report_both_provider_outcomes(self):
        expected = {"name": "G213r", "aliases": ["G213r"]}
        diagnostic = []
        from unittest.mock import patch
        with patch.object(monitor, "ddg_search", side_effect=RuntimeError("temporarily blocked")), \
             patch.object(monitor, "bing_search", return_value=[]):
            result = monitor.search_fallback("G213r", "https://www.biccamera.com/bc/item/9242996/",
                                             expected=expected, diagnostics=diagnostic)
        self.assertIsNone(result)
        self.assertEqual([x["provider"] for x in diagnostic], ["duckduckgo", "bing"])
        self.assertTrue(all("status" in x for x in diagnostic))

    def test_search_fallback_rejects_prices_without_exact_identity_even_on_allowed_host(self):
        expected = {"name": "G213r", "aliases": ["G213r", "9242996"]}
        ddg = [{
            "url": "https://www.biccamera.com/bc/item/other/",
            "title": "Gaming keyboard model XYZ",
            "snippet": "7,330円 在庫あり",
        }]
        from unittest.mock import patch
        with patch.object(monitor, "ddg_search", return_value=ddg), \
             patch.object(monitor, "bing_search", return_value=[]):
            result = monitor.search_fallback("G213r", "https://www.biccamera.com/bc/item/9242996/",
                                             expected=expected)
        self.assertIsNone(result)

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

    def test_exact_jsonld_offer_beats_related_product_offer(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"G TUNE DG-A7G70","offers":{"priceCurrency":"JPY","price":"459800","availability":"https://schema.org/InStock"}}
        </script>
        <script type="application/ld+json">
        {"@type":"Product","name":"G TUNE DG-A7G70 [DGA7G70B5BBDW101DEC]","offers":{"priceCurrency":"JPY","price":"304800","availability":"https://schema.org/InStock"}}
        </script>
        <div>G TUNE DG-A7G70 DGA7G70B5BBDW101DEC Ryzen 7 5700X RTX 5070 32GB 1TB デスクトップ</div>
        """
        expected = {
            "name": "G TUNE DG-A7G70",
            "aliases": ["DGA7G70B5BBDW101DEC"],
            "form_factor": "desktop",
        }
        parsed = monitor.parse_page("https://example.com", html, expected=expected)
        self.assertEqual(parsed["price_jpy"], 304800)
        self.assertEqual(parsed["parsed_spec"]["form_factor"], "desktop")
        self.assertEqual(parsed["parsed_spec"]["cpu"], "Ryzen 7 5700X")

    def test_exact_variant_core_specs_beat_related_specs(self):
        html = """
        <div>
          G TUNE DG-A5G60 関連製品 G TUNE DG-A7G70 Ryzen 7 5700X RTX 5070 32GB
          G TUNE DG-A5G60 DGA5G60B5BADW102DECWA
          CPU AMD Ryzen™ 5 4500 プロセッサ グラフィックス NVIDIA GeForce RTX 5060
          メモリ 16GB M.2 SSD 500GB デスクトップPC
        </div>
        """
        expected = {
            "name": "G TUNE DG-A5G60",
            "aliases": ["DGA5G60B5BADW102DECWA"],
            "form_factor": "desktop",
            "gpu": "RTX 5060",
            "cpu": "Ryzen 5 4500",
        }
        parsed = monitor.parse_page("https://example.com", html, expected=expected)
        self.assertEqual(parsed["parsed_spec"]["cpu"], "Ryzen 5 4500")
        self.assertEqual(parsed["parsed_spec"]["gpu"], "RTX 5060")
        self.assertEqual(parsed["parsed_spec"]["form_factor"], "desktop")

    def test_desktop_form_factor_is_parsed(self):
        html = """
        <div>G TUNE DG-I5G70 DGI5G70B8BGDW102DECRISE
        Windows 11 デスクトップPC Intel Core Ultra 5 プロセッサー 250K Plus
        GeForce RTX 5070 16GB 500GB
        </div>
        """
        parsed = monitor.parse_page(
            "https://example.com",
            html,
            expected={"name":"G TUNE DG-I5G70","aliases":["DGI5G70B8BGDW102DECRISE"]},
        )
        self.assertEqual(parsed["parsed_spec"]["form_factor"], "desktop")

    def test_meta_price_is_distinct_source(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="279800">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["price_source_mode"], "direct_meta")

    def test_real_included_peripheral_is_detected(self):
        html = """
        <div>
          ゲーミングモニターをプレゼント
          キーボード・マウス同梱
        </div>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertGreaterEqual(
            sum(1 for x in parsed["benefit_signals"] if x["kind"] == "included_peripheral"),
            1,
        )

    def test_mouse_computer_brand_is_not_a_bundled_mouse(self):
        html = """
        <div>
          マウスは3年保証で送料無料
          マウスコンピューター公式 G TUNE デスクトップPC
          付属品 ディスプレイ ー キーボード ー マウス ー
        </div>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertFalse(any(
            x["kind"] == "included_peripheral"
            for x in parsed["benefit_signals"]
        ))
        self.assertFalse(any(
            x["kind"] == "warranty_or_support_value"
            for x in parsed["benefit_signals"]
        ))

    def test_additional_coupon_discount_is_confirmed_cash_benefit(self):
        html = """
        <div>
          販売価格 399,800円
          PC本体 クーポンコード入力で30,000円OFF
          在庫あり
        </div>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["confirmed_benefit_value_jpy"], 30000)
        self.assertEqual(parsed["benefit_confidence"], "confirmed")
        self.assertTrue(any(
            x["kind"] == "additional_cash_discount_jpy"
            and x["counts_toward_effective_cost"]
            for x in parsed["benefit_signals"]
        ))

    def test_generic_discount_is_not_double_counted(self):
        html = """
        <div>
          G TUNE PC 30,000円OFF 販売価格 369,800円
          在庫あり
        </div>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["confirmed_benefit_value_jpy"], 0)

    def test_accessory_value_is_separate_from_effective_cost(self):
        html = """
        <div>
          販売価格 399,800円
          27,800円相当のゲーミングモニターをプレゼント
          在庫あり
        </div>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["confirmed_benefit_value_jpy"], 0)
        self.assertEqual(parsed["benefit_confidence"], "unconfirmed")
        self.assertTrue(any(
            x["kind"] == "accessory_stated_value_jpy" and x["value_jpy"] == 27800
            for x in parsed["benefit_signals"]
        ))

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
