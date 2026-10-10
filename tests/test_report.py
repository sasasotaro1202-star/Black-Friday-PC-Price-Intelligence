import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report", ROOT / "scripts" / "report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportLinkTests(unittest.TestCase):
    def test_sales_url_accepts_http_url(self):
        self.assertEqual(
            report.sales_url({"url": "https://example.com/product"}),
            "https://example.com/product",
        )

    def test_sales_url_rejects_missing_or_non_http_url(self):
        self.assertIsNone(report.sales_url({"url": ""}))
        self.assertIsNone(report.sales_url({"url": "javascript:alert(1)"}))
        self.assertIsNone(report.sales_url({}))

    def test_sales_url_strips_whitespace(self):
        self.assertEqual(
            report.sales_url({"url": "  https://example.com/product  "}),
            "https://example.com/product",
        )

    def test_suppress_current_price_moves_value_to_reference_only(self):
        row = {"current_price_jpy": 299800, "last_valid_price_jpy": None, "price_jpy": 299800}
        out = report.suppress_current_price(row)
        self.assertIsNone(out["current_price_jpy"])
        self.assertIsNone(out["price_jpy"])
        self.assertEqual(out["last_valid_price_jpy"], 299800)
        self.assertTrue(out["current_price_suppressed"])

    def test_build_products_retains_uncatalogued_discovered_candidate(self):
        discovered = {
            "id": "discovered-a1b2c3d4",
            "name": "Outlet RTX 5070 desktop",
            "url": "https://example.com/pc",
            "form_factor": "desktop",
            "current_price_jpy": 249800,
            "stock_status": "in_stock",
            "price_source_mode": "direct_text",
            "price_validation_status": "validated",
            "spec": {"gpu": "RTX 5070", "ram_gb": 32, "ssd": "1 TB"},
            "retrieval_time": "2026-10-10T10:00:00+09:00",
            "available_at": "2026-10-10T10:00:00+09:00",
        }
        rows = report.build_products({"products": [discovered]}, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], discovered["id"])
        self.assertTrue(rows[0]["dynamic_candidate"])
        self.assertEqual(rows[0]["current_price_jpy"], 249800)
        self.assertEqual(rows[0]["variant_match"], "ambiguous")

    def test_file_sha256_is_stable_for_same_bytes(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"
            p.write_bytes(b"black-friday")
            first = report.file_sha256(p)
            second = report.file_sha256(p)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
