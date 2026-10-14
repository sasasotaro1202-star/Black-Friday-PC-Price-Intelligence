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

    def test_search_queries_scope_two_variants_to_allowlisted_sites(self):
        domains = ("kakaku.com", "amazon.co.jp", "dospara.co.jp")
        queries = bcm.build_component_search_queries(self.part, domains)
        self.assertEqual(len(queries), 2)
        self.assertTrue(any("VCG507012DFXPB1-O" in q for q in queries))
        self.assertTrue(any("PNY GeForce RTX 5070 12GB OC SLIM" in q for q in queries))
        self.assertTrue(all("site:kakaku.com" in q for q in queries))
        self.assertTrue(all("site:amazon.co.jp" in q for q in queries))
        self.assertTrue(all("site:dospara.co.jp" in q for q in queries))
        self.assertFalse(any("/item/K0001798041" in q for q in queries))
        self.assertFalse(any("site:untrusted.example" in q for q in queries))

    def test_direct_retailer_listing_requires_allowlisted_https_host(self):
        with patch.object(bcm, "fetch") as mocked:
            self.assertIsNone(
                bcm.verify_retailer_listing(self.part, "https://untrusted.example/item/1", ("dospara.co.jp",))
            )
            mocked.assert_not_called()

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
