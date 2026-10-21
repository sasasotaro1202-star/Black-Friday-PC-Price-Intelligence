import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import intelligence
import monitor


class MonitorParsingTests(unittest.TestCase):
    def test_monitor_output_separates_purchase_page_from_spec_monitor_page(self):
        monitor_url = "https://www.asus.com/jp/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a16-2025/techspec/"
        purchase_url = "https://store.asus.com/jp/90nr0md1-m001v0-asus-tuf-gaming-a16-2025.html"
        item = monitor.apply_observation(
            {
                "id": "tuf-a16-test",
                "url": monitor_url,
                "query": "FA608PP",
                "priority": "high",
            },
            None,
            {},
            {
                "name": "ASUS TUF Gaming A16 FA608PP",
                "family": "TUF Gaming A16",
                "aliases": ["FA608PP"],
                "url_is_exact": False,
                "purchase_url": purchase_url,
            },
            "2026-10-21T04:00:00+09:00",
        )
        self.assertEqual(item["url"], monitor_url)
        self.assertEqual(item["monitor_url"], monitor_url)
        self.assertEqual(item["purchase_url"], purchase_url)

    def test_windows_31j_charset_alias_decodes_japanese_inventory_text(self):
        original = "ビックカメラ 天神1号館 店舗在庫"
        raw = original.encode("cp932")
        self.assertEqual(monitor.decode_response_body(raw, "windows-31j"), original)

    def test_unknown_charset_falls_back_without_aborting_collection(self):
        raw = "inventory unavailable".encode("utf-8")
        self.assertEqual(monitor.decode_response_body(raw, "unknown-retailer-charset"), "inventory unavailable")

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
             patch.object(monitor.subprocess, "run", return_value=fake) as mocked_run:
            with self.assertRaisesRegex(RuntimeError, "curl_exit_35.*SSL connect error"):
                monitor.fetch("https://example.com/product", timeout=1)
        self.assertIn("--http1.1", mocked_run.call_args.args[0])

    def test_bing_redirect_unpack_handles_a1_base64_url(self):
        import base64
        target = "https://www.dospara.co.jp/TC30/MC12904.html"
        encoded = "a1" + base64.urlsafe_b64encode(target.encode("utf-8")).decode("ascii").rstrip("=")
        url = "https://www.bing.com/ck/a?u=" + encoded
        self.assertEqual(monitor._unpack_bing_url(url), target)

    def test_bing_redirect_unpack_handles_plain_base64_destination(self):
        import base64
        target = "https://www.tsukumo.co.jp/bto/pc/"
        encoded = base64.urlsafe_b64encode(target.encode("utf-8")).decode("ascii").rstrip("=")
        url = "https://www.bing.com/ck/a?u=" + encoded
        self.assertEqual(monitor._unpack_bing_url(url), target)

    def test_bing_redirect_unpack_handles_url_encoded_target_and_rejects_bing_loop(self):
        from urllib.parse import quote
        target = "https://www.yodobashi.com/product/100000001008/"
        url = "https://www.bing.com/redirect?url=" + quote(target, safe="")
        self.assertEqual(monitor._unpack_bing_url(url), target)
        unresolved = "https://www.bing.com/ck/a?u=unknown"
        self.assertEqual(monitor._unpack_bing_url(unresolved), unresolved)

    def test_duckduckgo_parser_keeps_result_without_snippet(self):
        html = """
          <div class="result">
            <a class="result__a" href="https://www.dospara.co.jp/item/123">Ryzen 7 9700X BOX</a>
          </div>
        """
        results = monitor.parse_duckduckgo_results(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://www.dospara.co.jp/item/123")
        self.assertEqual(results[0]["title"], "Ryzen 7 9700X BOX")
        self.assertEqual(results[0]["snippet"], "")

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

    def test_conflicting_catalog_variant_does_not_expose_price_or_stock(self):
        url = "https://www.lenovo.com/jp/ja/p/laptops/legion-laptops/legion-5-series/legion-pro-5i-gen-10-16-inch-intel/len101g0040"
        entry = {
            "id": "candidate-4",
            "url": url,
            "query": "Lenovo Legion Pro 5i Gen 10 Core Ultra 9 275HX RTX 5070 Ti",
            "priority": "critical",
        }
        raw = {
            "name": "Lenovo Legion Pro 5i Gen 10",
            "price_jpy": 337240,
            "price_source_mode": "direct_structured",
            "data_confidence": "high",
            "stock_status": "in_stock",
            "parsed_spec": {
                "gpu": "RTX 5080",
                "cpu": "Core Ultra 9 275HX",
                "tgp_w": 115,
                "ram_gb": 32,
                "ssd": "1 TB",
                "vram_gb": 12,
                "form_factor": "laptop",
            },
            "page_text_excerpt": "Lenovo Legion Pro 5i Gen 10 Core Ultra 9 275HX RTX 5080",
        }
        catalog_item = {
            "id": "candidate-4",
            "name": "Lenovo Legion Pro 5i Gen 10",
            "family": "Legion Pro 5i Gen 10",
            "form_factor": "laptop",
            "gpu": "RTX 5070 Ti Laptop GPU",
            "cpu": "Core Ultra 9 275HX",
            "tgp_w": 115,
            "ram_gb": 32,
            "ssd": "1 TB",
            "vram_gb": 12,
            "url": url,
            "url_is_exact": True,
            "identity_confidence": "high",
            "aliases": ["Legion Pro 5i Gen 10"],
            "reference_price_jpy": 359800,
        }

        # The previous snapshot contains the same untrusted variant as a
        # formerly "validated" current price. It must not become a historical
        # baseline after the identity contradiction is detected.
        previous = {
            "current_price_jpy": 337240,
            "price_jpy": 337240,
            "last_valid_price_jpy": 337240,
            "price_validation_status": "validated",
            "variant_match": "ambiguous",
            "price_source_mode": "direct_structured",
        }
        result = monitor.apply_observation(
            entry, raw, previous, catalog_item, "2026-10-20T18:00:00+09:00"
        )

        self.assertEqual(result["variant_match"], "ambiguous")
        self.assertEqual(
            result["variant_ambiguity_reason"], "parsed_spec_contradicts_catalog"
        )
        self.assertIsNone(result["current_price_jpy"])
        self.assertIsNone(result["price_jpy"])
        self.assertIsNone(result["available_at"])
        self.assertEqual(result["stock_status"], "unknown")
        self.assertEqual(result["price_validation_status"], "variant_ambiguous")
        self.assertEqual(
            result["observed_price_source_mode"], "direct_structured"
        )
        self.assertIsNone(result["last_valid_price_jpy"])

    def test_previous_navigation_filter_price_is_not_retained_as_last_valid(self):
        entry = {
            "id": "desktop-test",
            "url": "https://www.mouse-jp.co.jp/store/g/test/",
            "query": "G TUNE test desktop RTX 5070",
            "priority": "critical",
        }
        previous = {
            "current_price_jpy": 300001,
            "price_jpy": 300001,
            "last_valid_price_jpy": 300001,
            "price_source_mode": "direct_text",
            "price_validation_status": "validated",
            "price_context": "G TUNE HOME 価格から探す 300,001円～ グラフィックスから探す",
        }
        raw = {
            "name": "G TUNE test desktop",
            "price_jpy": None,
            "price_source_mode": "none",
            "price_context": None,
            "stock_status": "unknown",
            "parsed_spec": {"form_factor": "desktop"},
            "page_text_excerpt": "G TUNE test desktop",
        }
        catalog_item = {
            "id": "desktop-test",
            "name": "G TUNE test desktop",
            "url_is_exact": True,
            "identity_confidence": "high",
            "reference_price_jpy": 304800,
            "gpu": "RTX 5070",
            "form_factor": "desktop",
        }
        result = monitor.apply_observation(
            entry,
            raw,
            previous,
            catalog_item,
            "2026-10-18T00:00:00+09:00",
        )
        self.assertIsNone(result["current_price_jpy"])
        self.assertIsNone(result["price_jpy"])
        self.assertIsNone(result["last_valid_price_jpy"])
        self.assertEqual(result["price_source_mode"], "none")
        self.assertEqual(result["price_validation_status"], "missing")

    def test_navigation_price_filter_range_is_not_selected_as_product_price(self):
        for text in (
            "商品一覧 価格から探す 300,001円～ CPUから探す",
            "スペック・パーツ別 価格から絞り込む 300,001円～ グラフィックスから探す",
            "価格帯から探す 300,001円～ G TUNE DG-A7G70",
        ):
            with self.subTest(text=text):
                self.assertIsNone(intelligence.pick_price(text))

    def test_direct_product_price_still_parses_after_navigation_filter_changes(self):
        picked = intelligence.pick_price("G TUNE DG-A7G70 販売価格 304,800円（税込）")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["price_jpy"], 304800)

    def test_discount_amount_is_not_selected_as_price(self):
        picked = intelligence.pick_price("90,000円OFF / 販売価格 329,800円(税込)")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["price_jpy"], 329800)

    def test_matching_jsonld_offer_preserves_seller_name(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"TeamGroup T-CREATE DDR5-6000 32GB",
         "offers":{"price":"11980","priceCurrency":"JPY",
                   "availability":"https://schema.org/InStock",
                   "seller":{"@type":"Organization","name":"Example Retailer Japan"}}}
        </script>
        """
        expected = {
            "name": "TeamGroup T-CREATE DDR5-6000 32GB",
            "model_code": "CTCWD532G6000HC38ADC01",
            "aliases": ["TeamGroup T-CREATE DDR5-6000 32GB"],
        }
        parsed = monitor.parse_page("https://shop.example.jp/product", html, expected=expected)
        self.assertEqual(parsed["price_jpy"], 11980)
        self.assertEqual(parsed["seller_name"], "Example Retailer Japan")

    def test_structured_offer_requires_explicit_jpy_currency_or_yen_symbol(self):
        for currency, raw_price in (("USD", "11980"), ("", "11980"), ("USD", "¥11980")):
            with self.subTest(currency=currency, raw_price=raw_price):
                html = """
                <script type="application/ld+json">
                {"@type":"Product","name":"Example GPU",
                 "offers":{"price":"%s","priceCurrency":"%s",
                           "availability":"https://schema.org/InStock"}}
                </script>
                <h1>Example GPU</h1>
                """ % (raw_price, currency)
                parsed = monitor.parse_page(
                    "https://shop.example.jp/product",
                    html,
                    expected={"name": "Example GPU", "aliases": ["Example GPU"], "model_code": "EG-1"},
                )
                self.assertIsNone(parsed["price_jpy"])
                self.assertEqual(parsed["price_source_mode"], "none")

    def test_structured_jpy_price_does_not_truncate_fractional_yen(self):
        for raw_price in ("11980.5", "11980.99"):
            with self.subTest(raw_price=raw_price):
                html = """
                <script type="application/ld+json">
                {"@type":"Product","name":"Example GPU",
                 "offers":{"price":"%s","priceCurrency":"JPY",
                           "availability":"https://schema.org/InStock"}}
                </script>
                <h1>Example GPU</h1>
                """ % raw_price
                parsed = monitor.parse_page(
                    "https://shop.example.jp/product",
                    html,
                    expected={"name": "Example GPU", "aliases": ["Example GPU"], "model_code": "EG-1"},
                )
                self.assertIsNone(parsed["price_jpy"])
                self.assertEqual(parsed["price_source_mode"], "none")

    def test_structured_jpy_price_with_zero_decimal_tail_is_exact(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Example GPU",
         "offers":{"price":"11980.00","priceCurrency":"JPY",
                   "availability":"https://schema.org/InStock"}}
        </script>
        <h1>Example GPU</h1>
        """
        parsed = monitor.parse_page(
            "https://shop.example.jp/product",
            html,
            expected={"name": "Example GPU", "aliases": ["Example GPU"], "model_code": "EG-1"},
        )
        self.assertEqual(parsed["price_jpy"], 11980)

    def test_jpy_currency_code_does_not_override_conflicting_foreign_symbol(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Example GPU",
         "offers":{"price":"$11980","priceCurrency":"JPY",
                   "availability":"https://schema.org/InStock"}}
        </script>
        <h1>Example GPU</h1>
        """
        parsed = monitor.parse_page(
            "https://shop.example.jp/product",
            html,
            expected={"name": "Example GPU", "aliases": ["Example GPU"], "model_code": "EG-1"},
        )
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")

    def test_structured_offer_with_explicit_yen_symbol_is_accepted_without_currency_code(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Example GPU",
         "offers":{"price":"¥ 11,980",
                   "availability":"https://schema.org/InStock"}}
        </script>
        <h1>Example GPU</h1>
        """
        parsed = monitor.parse_page(
            "https://shop.example.jp/product",
            html,
            expected={"name": "Example GPU", "aliases": ["Example GPU"], "model_code": "EG-1"},
        )
        self.assertEqual(parsed["price_jpy"], 11980)

    def test_amazon_seller_profile_markup_is_used_without_guessing_from_host(self):
        html = """
        <h1>TeamGroup T-CREATE DDR5-6000 32GB</h1>
        <span class="a-price"><span class="a-offscreen">￥11,980</span></span>
        <a id="sellerProfileTriggerId" href="/sp?seller=A1">Third-Party PC Store</a>
        <div>発送元 Amazon.co.jp</div>
        """
        expected = {
            "name": "TeamGroup T-CREATE DDR5-6000 32GB",
            "model_code": "CTCWD532G6000HC38ADC01",
            "aliases": ["TeamGroup T-CREATE DDR5-6000 32GB"],
        }
        parsed = monitor.parse_page("https://www.amazon.co.jp/dp/B0CHF9TH1B", html, expected=expected)
        self.assertEqual(parsed["seller_name"], "Third-Party PC Store")

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

    def test_exact_jsonld_stock_overrides_unrelated_store_level_out_of_stock_text(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"PNY GeForce RTX 5070 Ti 16GB ARGB Overclocked Triple Fan VCG5070T16TFXXPB1-O",
         "sku":"VCG5070T16TFXXPB1-O",
         "offers":{"price":"207700","priceCurrency":"JPY","availability":"https://schema.org/InStock"}}
        </script>
        <h1>PNY GeForce RTX 5070 Ti 16GB ARGB Overclocked Triple Fan VCG5070T16TFXXPB1-O</h1>
        <div>オンライン在庫あり カートに入れる 207,700円</div>
        <section>店舗在庫: 天神店 在庫なし / 博多店 在庫切れ</section>
        """
        expected = {
            "name": "PNY GeForce RTX 5070 Ti 16GB ARGB",
            "aliases": ["VCG5070T16TFXXPB1-O"],
            "model_code": "VCG5070T16TFXXPB1-O",
        }
        parsed = monitor.parse_page("https://www.dospara.co.jp/SBR1892/IC634895.html", html, expected=expected)
        self.assertEqual(parsed["price_jpy"], 207700)
        self.assertEqual(parsed["structured_stock_status"], "in_stock")
        self.assertEqual(parsed["text_stock_status"], "out_of_stock")
        self.assertEqual(parsed["stock_status"], "in_stock")

    def test_expected_model_does_not_borrow_jsonld_offer_from_related_product(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"Requested product without offer"}
        </script>
        <script type="application/ld+json">
        {"@type":"Product","name":"Other unrelated product",
         "offers":{"price":"207700","priceCurrency":"JPY","availability":"https://schema.org/InStock"}}
        </script>
        <h1>Requested product without offer</h1>
        """
        parsed = monitor.parse_page(
            "https://example.com/product",
            html,
            expected={"name":"Requested product without offer","aliases":[],"model_code":"requested-123"},
        )
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")
        self.assertEqual(parsed["structured_stock_status"], "unknown")
        self.assertEqual(parsed["structured_identity_match"], True)

    def test_matching_jsonld_product_without_offer_fails_closed_without_exception(self):
        html = """
        <script type="application/ld+json">
        {"@type":"Product","name":"EDIFIER MR3","description":"Powered speakers"}
        </script>
        <div>EDIFIER MR3 Bluetoothスピーカー 在庫あり</div>
        """
        parsed = monitor.parse_page(
            "https://www.edifier.jp/products/mr3",
            html,
            expected={"name":"EDIFIER MR3","aliases":["MR3"],"model_code":"MR3"},
        )
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")
        self.assertEqual(parsed["stock_status"], "in_stock")

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

    def test_meta_price_without_explicit_jpy_currency_is_rejected(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="279800">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")

    def test_meta_price_is_accepted_only_with_explicit_jpy_currency(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="279800">
        <meta property="product:price:currency" content="JPY">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://example.com/test", html)
        self.assertEqual(parsed["price_jpy"], 279800)
        self.assertEqual(parsed["price_source_mode"], "direct_meta")

    def test_meta_jpy_currency_code_does_not_override_dollar_symbol(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="$279800">
        <meta property="product:price:currency" content="JPY">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://shop.example.jp/test", html)
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")

    def test_meta_price_with_usd_currency_is_rejected_even_on_japanese_url(self):
        html = """
        <html><head>
        <meta property="product:price:amount" content="279800">
        <meta property="product:price:currency" content="USD">
        </head><body>在庫あり</body></html>
        """
        parsed = monitor.parse_page("https://shop.example.jp/test", html)
        self.assertIsNone(parsed["price_jpy"])
        self.assertEqual(parsed["price_source_mode"], "none")

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


    def test_identity_only_specification_page_never_creates_live_price_or_stock(self):
        monitor_url = "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/"
        purchase_url = "https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html"
        raw = {
            "url": monitor_url,
            "name": "ROG Strix G16 (G614)",
            "price_jpy": 359800,
            "stock_status": "in_stock",
            "price_source_mode": "direct_text",
            "parsed_spec": {"gpu": "RTX 5070 Ti Laptop GPU", "ram_gb": 16, "ssd": "512 GB"},
            "page_text_excerpt": "G614PR-R9R5070TI Ryzen 9 8940HX RTX 5070 Ti Laptop GPU",
            "page_role": "identity_only_specification",
            "observation_route": "monitor_url",
        }
        item = monitor.apply_observation(
            {"id": "rog-g16-test", "url": monitor_url, "query": "G614PR-R9R5070TI"},
            raw,
            {"current_price_jpy": 359800, "variant_match": "trusted_url", "price_validation_status": "validated"},
            {
                "id": "rog-g16-test",
                "name": "ROG Strix G16 G614PR-R9R5070TI",
                "family": "ROG Strix G16",
                "cpu": "Ryzen 9 8940HX",
                "gpu": "RTX 5070 Ti Laptop GPU",
                "ram_gb": 32,
                "ssd": "1 TB",
                "aliases": ["G614PR-R9R5070TI"],
                "url_is_exact": False,
                "identity_confidence": "high",
                "monitor_page_type": "official_model_specification",
                "purchase_url": purchase_url,
                "purchase_url_is_exact": True,
            },
            "2026-10-21T13:00:00+09:00",
        )
        self.assertIsNone(item["current_price_jpy"])
        self.assertIsNone(item["last_valid_price_jpy"])
        self.assertEqual(item["stock_status"], "unknown")
        self.assertEqual(item["price_source_mode"], "none")
        self.assertEqual(item["page_role"], "identity_only_specification")
        self.assertEqual(item["name"], "ROG Strix G16 G614PR-R9R5070TI")

    def test_verified_sku_purchase_url_overrides_broad_spec_parser_conflicts(self):
        monitor_url = "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/"
        purchase_url = "https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html"
        item = monitor.apply_observation(
            {"id": "rog-g16-test", "url": monitor_url, "query": "G614PR-R9R5070TI300"},
            {
                "url": purchase_url,
                "name": "ROG Strix G16 (G614PR)",
                "price_jpy": 549800,
                "stock_status": "in_stock",
                "price_source_mode": "direct_structured",
                "parsed_spec": {"gpu": "RTX 5070 Ti Laptop GPU", "ram_gb": 16, "ssd": "512 GB"},
                "page_text_excerpt": "G614PR-R9R5070TI300 Ryzen 9 8940HX RTX 5070 Ti Laptop GPU 549800 yen",
                "observation_route": "purchase_url",
                "purchase_page_fetch_status": "ok",
                "page_role": "sku_purchase_page",
            },
            {},
            {
                "id": "rog-g16-test",
                "name": "ROG Strix G16 G614PR-R9R5070TI300",
                "family": "ROG Strix G16",
                "cpu": "Ryzen 9 8940HX",
                "gpu": "RTX 5070 Ti Laptop GPU",
                "ram_gb": 32,
                "ssd": "1 TB",
                "reference_price_jpy": 549800,
                "aliases": ["G614PR-R9R5070TI300"],
                "url_is_exact": False,
                "identity_confidence": "high",
                "purchase_url": purchase_url,
                "purchase_url_is_exact": True,
            },
            "2026-10-21T13:00:00+09:00",
        )
        self.assertEqual(item["current_price_jpy"], 549800)
        self.assertIn(item["variant_match"], ("exact", "trusted_url", "strong"))
        self.assertEqual(item["parsed_spec"], {})
        self.assertEqual(item["observation_url"], purchase_url)
        self.assertEqual(item["purchase_page_fetch_status"], "ok")
        self.assertEqual(item["purchase_url"], purchase_url)


if __name__ == "__main__":
    unittest.main()
