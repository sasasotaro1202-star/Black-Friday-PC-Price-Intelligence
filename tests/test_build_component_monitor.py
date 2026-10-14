import pathlib
import sys
import unittest
from datetime import timedelta
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_component_monitor as bcm
import self_build_planner
import timing_analysis
from intelligence import now_jst, iso


class BuildComponentMonitorTests(unittest.TestCase):
    def setUp(self):
        self.part = {
            "id": "gpu-rtx5070-12gb",
            "category": "gpu",
            "name": "PNY GeForce RTX 5070 12GB OC SLIM",
            "model_code": "VCG507012DFXPB1-O",
            "aliases": ["PNY GeForce RTX 5070 12GB OC", "VCG507012DFXPB1-O"],
            "identity_terms": ["PNY GeForce RTX 5070 12GB OC", "VCG507012DFXPB1-O", "RTX 5070 12GB"],
            "monitor_url": "https://kakaku.com/item/K0001798041/",
            "min_price_jpy": 100000,
            "max_price_jpy": 330000,
        }

    def test_search_queries_include_allowlisted_scoped_and_broad_fallbacks(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        domains = ("kakaku.com", "amazon.co.jp", "dospara.co.jp")
        fixed_now = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        queries = bcm.build_component_search_queries(self.part, domains, now=fixed_now)
        self.assertEqual(len(queries), 3)
        self.assertIn('site:kakaku.com/item/K0001798041', queries[0])
        self.assertIn('"PNY GeForce RTX 5070 12GB OC SLIM"', queries[0])
        self.assertIn('"PNY GeForce RTX 5070 12GB OC"', queries[1])
        self.assertTrue(queries[1].startswith("site:"))
        self.assertIn('"PNY GeForce RTX 5070 12GB OC" 価格', queries[1])
        seller_host = queries[1].split("site:", 1)[1].split()[0]
        self.assertIn(seller_host, domains)
        self.assertNotEqual(seller_host, "kakaku.com")
        self.assertNotIn("site:", queries[2])
        self.assertIn("価格 最安値", queries[2])
        self.assertFalse(any(" OR site:" in q for q in queries))
        self.assertFalse(any("site:untrusted.example" in q for q in queries))
        self.assertFalse(any("  " in q for q in queries))

    def test_broad_discovery_results_still_require_allowlisted_hosts(self):
        self.assertFalse(bcm.allowed_url("https://www.pny.com/", ("amazon.co.jp", "dospara.co.jp")))
        self.assertTrue(bcm.allowed_url("https://www.dospara.co.jp/item/123", ("dospara.co.jp",)))
        self.assertFalse(bcm.allowed_url("http://www.dospara.co.jp/item/123", ("dospara.co.jp",)))

    def test_kakaku_search_page_price_is_display_only_and_identity_anchored(self):
        html = (
            "<html><body><article><h2>PNY GeForce RTX 5070 12GB OC SLIM</h2>"
            "<p>最安価格(税込) ¥139,800</p></article></body></html>"
        )
        reference = bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY%20GeForce%20RTX%205070/"
        )
        self.assertIsNotNone(reference)
        self.assertEqual(reference["price_jpy"], 139800)
        self.assertEqual(reference["search_provider"], "kakaku_search_page")
        self.assertEqual(reference["source_role"], "comparison_site_search_snippet_reference")
        self.assertFalse(reference["bf_actual_authorized"])

    def test_kakaku_search_page_rejects_untrusted_host_wrong_identity_and_bad_price(self):
        html = (
            "<html><body><article><h2>Different graphics card</h2>"
            "<p>¥139,800</p></article></body></html>"
        )
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://untrusted.example/search/"
        ))
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/different/"
        ))
        bad_price = html.replace("Different graphics card", "PNY GeForce RTX 5070 12GB OC SLIM").replace("139,800", "39,800")
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, bad_price, "https://search.kakaku.com/PNY/"
        ))

    def test_kakaku_search_page_pairs_price_only_with_matching_structural_card(self):
        html = (
            "<html><body><div class='product-list'>"
            "<article><h2>Other GPU model</h2><p>最安価格 ¥129,800</p></article>"
            "<article><h2>PNY GeForce RTX 5070 12GB OC SLIM</h2><p>最安価格 ¥139,800</p></article>"
            "</div></body></html>"
        )
        diagnostic = {}
        reference = bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY/", diagnostic
        )
        self.assertIsNotNone(reference)
        self.assertEqual(reference["price_jpy"], 139800)
        self.assertEqual(reference["identity_anchor"], "PNY GeForce RTX 5070 12GB OC SLIM")
        self.assertEqual(diagnostic["extraction_reason"], "display_only_price_from_single_product_card")
        self.assertEqual(diagnostic["identity_card_count"], 1)

    def test_kakaku_search_page_recognizes_search_item_class_cards(self):
        html = (
            "<html><body><div class='search-results'>"
            "<div class='c-searchItem'><span>PNY GeForce RTX 5070 12GB OC SLIM</span>"
            "<span>最安価格 ¥139,800</span></div></div></body></html>"
        )
        reference = bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY/"
        )
        self.assertIsNotNone(reference)
        self.assertEqual(reference["price_jpy"], 139800)

    def test_kakaku_search_page_does_not_borrow_price_from_adjacent_card(self):
        html = (
            "<html><body><div class='product-list'>"
            "<article><h2>PNY GeForce RTX 5070 12GB OC SLIM</h2><p>在庫確認中</p></article>"
            "<article><h2>Other GPU model</h2><p>最安価格 ¥139,800</p></article>"
            "</div></body></html>"
        )
        diagnostic = {}
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY/", diagnostic
        ))
        self.assertEqual(diagnostic["extraction_reason"], "matching_product_card_has_no_in_range_price")

    def test_kakaku_search_page_rejects_multiple_distinct_prices_in_one_card(self):
        html = (
            "<html><body><article><h2>PNY GeForce RTX 5070 12GB OC SLIM</h2>"
            "<p>新品 ¥139,800 中古 ¥129,800</p></article></body></html>"
        )
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY/"
        ))

    def test_kakaku_search_page_requires_a_product_card_not_page_wide_proximity(self):
        html = (
            "<html><body><h2>PNY GeForce RTX 5070 12GB OC SLIM</h2>"
            "<p>最安価格 ¥139,800</p></body></html>"
        )
        self.assertIsNone(bcm.parse_kakaku_search_page_reference(
            self.part, html, "https://search.kakaku.com/PNY/"
        ))

    def test_retailer_search_urls_are_built_only_for_allowlisted_domains(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        urls = bcm.build_retailer_search_urls(
            self.part, ("kakaku.com", "amazon.co.jp", "rakuten.co.jp", "dospara.co.jp"),
            now=now, limit=2,
        )
        self.assertEqual(len(urls), 2)
        self.assertEqual(len({x["retailer_domain"] for x in urls}), 2)
        for item in urls:
            self.assertTrue(bcm.allowed_url(item["url"], (item["retailer_domain"],)))
            self.assertIn("VCG507012DFXPB1-O", item["url"])
        self.assertEqual(bcm.build_retailer_search_urls(self.part, ("kakaku.com",), now=now), [])

    def test_retailer_search_page_returns_same_card_allowlisted_detail_link(self):
        html = (
            "<html><body><ul class='product-list'>"
            "<li class='product-item'><a href='/item/other'>Other GPU item</a><span>¥129,800</span></li>"
            "<li class='product-item'><a href='/item/123'>PNY GeForce RTX 5070 12GB OC SLIM VCG507012DFXPB1-O</a>"
            "<span>最安価格 ¥139,800</span></li></ul></body></html>"
        )
        links, diag = bcm.parse_retailer_search_page(
            self.part, html, "https://www.dospara.co.jp/search?q=PNY",
            ("dospara.co.jp",), "dospara.co.jp",
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["url"], "https://www.dospara.co.jp/item/123")
        self.assertEqual(links[0]["card_price_jpy"], 139800)
        self.assertEqual(diag["extraction_reason"], "exact_identity_detail_link_found")

    def test_component_direct_text_parser_accepts_sub_50000_part_price_near_identity(self):
        part = {
            "id": "motherboard-test", "name": "ASRock B850M Pro RS WiFi",
            "model_code": "B850M Pro RS WiFi",
            "aliases": ["ASRock B850M Pro RS WiFi"],
            "identity_terms": ["B850M Pro RS WiFi"],
            "min_price_jpy": 12000, "max_price_jpy": 50000,
        }
        html = (
            "<html><body><h1>ASRock B850M Pro RS WiFi</h1>"
            "<div class='price-box'><span>販売価格（税込）</span><strong>23,780円</strong></div>"
            "<section><h2>関連商品</h2><p>別のGPU 190,800円</p></section></body></html>"
        )
        price = bcm.parse_component_direct_text_price(part, html)
        self.assertIsNotNone(price)
        self.assertEqual(price["price_jpy"], 23780)
        self.assertEqual(price["price_source_mode"], "direct_text")

    def test_component_direct_text_parser_rejects_missing_identity_and_ambiguous_prices(self):
        part = {
            "id": "motherboard-test", "name": "ASRock B850M Pro RS WiFi",
            "model_code": "B850M Pro RS WiFi",
            "aliases": ["ASRock B850M Pro RS WiFi"],
            "identity_terms": ["B850M Pro RS WiFi"],
            "min_price_jpy": 12000, "max_price_jpy": 50000,
        }
        self.assertIsNone(bcm.parse_component_direct_text_price(
            part, "<html><body><h1>Other motherboard</h1><p>23,780円</p></body></html>"
        ))
        ambiguous = (
            "<html><body><h1>ASRock B850M Pro RS WiFi</h1>"
            "<p>販売価格 23,780円</p><p>販売価格 21,980円</p></body></html>"
        )
        self.assertIsNone(bcm.parse_component_direct_text_price(part, ambiguous))

    def test_rotating_retailer_domain_is_deterministic_for_a_five_minute_slot(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        domains = ("kakaku.com", "amazon.co.jp", "rakuten.co.jp", "dospara.co.jp")
        first = datetime(2026, 10, 14, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        same_slot = datetime(2026, 10, 14, 12, 4, tzinfo=ZoneInfo("Asia/Tokyo"))
        next_slot = datetime(2026, 10, 14, 12, 5, tzinfo=ZoneInfo("Asia/Tokyo"))
        a = bcm.build_component_search_queries(self.part, domains, now=first)
        b = bcm.build_component_search_queries(self.part, domains, now=same_slot)
        c = bcm.build_component_search_queries(self.part, domains, now=next_slot)
        self.assertEqual(a, b)
        self.assertNotEqual(a[1], c[1])

    def test_direct_retailer_listing_requires_allowlisted_https_host(self):
        with patch.object(bcm, "fetch") as mocked:
            self.assertIsNone(
                bcm.verify_retailer_listing(self.part, "https://untrusted.example/item/1", ("dospara.co.jp",))
            )
            mocked.assert_not_called()

    def test_direct_retailer_listing_accepts_sub_50000_component_price(self):
        part = {
            "id": "motherboard-test", "category": "motherboard",
            "name": "ASRock B850M Pro RS WiFi", "model_code": "B850M Pro RS WiFi",
            "aliases": ["ASRock B850M Pro RS WiFi"],
            "identity_terms": ["B850M Pro RS WiFi"],
            "min_price_jpy": 12000, "max_price_jpy": 50000,
        }
        html = (
            "<html><body><h1>ASRock B850M Pro RS WiFi</h1>"
            "<div class='price-box'><span>販売価格（税込）</span><strong>23,780円</strong></div>"
            "<p>在庫あり</p></body></html>"
        )
        raw = {
            "name": "ASRock B850M Pro RS WiFi",
            "page_text_excerpt": "ASRock B850M Pro RS WiFi 販売価格（税込）23,780円 在庫あり",
            "price_jpy": None, "price_source_mode": "none", "stock_status": "in_stock",
        }
        with patch.object(bcm, "fetch", return_value=(html, "https://www.dospara.co.jp/item/1", {})), patch.object(bcm, "parse_page", return_value=raw):
            offer = bcm.verify_retailer_listing(
                part, "https://www.dospara.co.jp/item/1", ("dospara.co.jp",)
            )
        self.assertIsNotNone(offer)
        self.assertEqual(offer["price_jpy"], 23780)
        self.assertEqual(offer["price_source_mode"], "direct_text")
        self.assertEqual(offer["stock_status"], "in_stock")
        self.assertEqual(offer["source_role"], "direct_retailer_listing_reference")

    def test_direct_retailer_listing_requires_page_identity_and_plausible_price(self):
        html = "<html><title>PNY GeForce RTX 5070 12GB OC SLIM</title></html>"
        raw = {
            "name": "PNY GeForce RTX 5070 12GB OC SLIM",
            "page_text_excerpt": "VCG507012DFXPB1-O PNY GeForce RTX 5070 12GB OC SLIM",
            "price_jpy": 139900,
            "price_source_mode": "direct_structured",
            "stock_status": "in_stock",
        }
        with patch.object(bcm, "fetch", return_value=(html, "https://www.dospara.co.jp/item/1", {})), \
             patch.object(bcm, "parse_page", return_value=raw):
            offer = bcm.verify_retailer_listing(
                self.part, "https://www.dospara.co.jp/item/1", ("dospara.co.jp",)
            )
        self.assertIsNotNone(offer)
        self.assertEqual(offer["price_jpy"], 139900)
        self.assertEqual(offer["stock_status"], "in_stock")
        self.assertEqual(offer["source_role"], "direct_retailer_listing_reference")
        self.assertFalse(offer["bf_actual_authorized"])

    def test_direct_retailer_listing_rejects_page_with_wrong_product_identity(self):
        html = "<html><title>Other GPU</title></html>"
        raw = {
            "name": "Other GPU",
            "page_text_excerpt": "Generic GPU no PNY model code",
            "price_jpy": 139900,
            "price_source_mode": "direct_structured",
            "stock_status": "in_stock",
        }
        with patch.object(bcm, "fetch", return_value=(html, "https://www.dospara.co.jp/item/1", {})), \
             patch.object(bcm, "parse_page", return_value=raw):
            offer = bcm.verify_retailer_listing(
                self.part, "https://www.dospara.co.jp/item/1", ("dospara.co.jp",)
            )
        self.assertIsNone(offer)

    def test_timing_accepts_direct_listing_history_only_with_in_stock_signal(self):
        now = now_jst()
        stamp = iso(now - timedelta(minutes=5))
        base = {
            "id": self.part["id"],
            "market_reference_price_jpy": 139900,
            "source_role": "direct_retailer_listing_reference",
            "available_at": stamp,
            "retrieval_time": stamp,
            "pit_valid": True,
            "identity_match": True,
            "price_validation_status": "verified_retailer_listing_reference",
            "stock_signal": "in_stock",
            "bf_actual_authorized": False,
        }
        self.assertTrue(timing_analysis._valid_component_observation(base, now))
        self.assertFalse(timing_analysis._valid_component_observation(
            {**base, "stock_signal": "unknown"}, now
        ))
        self.assertFalse(timing_analysis._valid_component_observation(
            {**base, "bf_actual_authorized": True}, now
        ))

    def test_fresh_in_stock_direct_listing_can_be_reference_but_not_checkout_authorization(self):
        now = now_jst()
        retrieved = iso(now - timedelta(minutes=3))
        offer = {
            "url": "https://www.dospara.co.jp/item/1",
            "price_jpy": 139900,
            "price_source_mode": "direct_structured",
            "stock_status": "in_stock",
            "identity_anchor": "VCG507012DFXPB1-O",
            "identity_match": True,
            "source_role": "direct_retailer_listing_reference",
            "available_at": retrieved,
            "retrieval_time": retrieved,
            "pit_valid": True,
            "bf_actual_authorized": False,
        }
        row = {
            "id": self.part["id"],
            "price_validation_status": "verified_retailer_listing_reference",
            "retailer_listing_reference_price_jpy": 139900,
            "retailer_listing_offer": offer,
            "identity_match": True,
            "pit_valid": True,
            "bf_actual_authorized": False,
            "available_at": retrieved,
            "retrieval_time": retrieved,
        }
        self.assertTrue(self_build_planner.trusted_retailer_listing_reference(
            row, now, 360, ["dospara.co.jp"]
        ))
        self.assertFalse(self_build_planner.trusted_retailer_listing_reference(
            {**row, "bf_actual_authorized": True}, now, 360, ["dospara.co.jp"]
        ))
        self.assertFalse(self_build_planner.trusted_retailer_listing_reference(
            {**row, "retailer_listing_offer": {**offer, "stock_status": "unknown"}},
            now, 360, ["dospara.co.jp"]
        ))


if __name__ == "__main__":
    unittest.main()
