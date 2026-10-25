import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import report


class ReportProductLinkTests(unittest.TestCase):
    def test_discovery_diagnostics_show_freshness_counts_and_search_failures(self):
        lines = report.discovery_diagnostics_lines({
            "generated_at": "2026-10-25T22:00:00+09:00",
            "discovered_count": 23,
            "last_discovery_attempt_at": "2026-10-25T22:00:00+09:00",
            "last_discovery_attempt_status": "partial",
            "discovery_search_stats": {
                "query_count": 3,
                "successful_query_count": 2,
                "failed_query_count": 1,
                "returned_url_count": 12,
                "failures": [{
                    "query": "RTX 5070 official product",
                    "error_type": "HTTPError",
                }],
            },
            "discovery_stats": {
                "newly_discovered_count": 2,
                "retained_count": 20,
                "removed_count": 1,
            },
        })
        rendered = "\\n".join(lines)
        self.assertIn("最終探索試行時刻（JST）: 2026-10-25T22:00:00+09:00", rendered)
        self.assertIn("探索クエリ成功/失敗: 2/1", rendered)
        self.assertIn("新規追加/維持/削除候補: 2/20/1", rendered)
        self.assertIn("RTX 5070 official product (HTTPError)", rendered)

    def test_discovery_diagnostics_do_not_treat_missing_metrics_as_zero(self):
        rendered = "\\n".join(report.discovery_diagnostics_lines({"urls": []}))
        self.assertIn("探索クエリ成功/失敗: 未記録", rendered)
        self.assertIn("新規追加/維持/削除候補: 未記録", rendered)
        self.assertNotIn("探索クエリ成功/失敗: 0/0", rendered)

    def test_pc_candidate_issue_links_prefer_verified_purchase_url(self):
        monitor_url = "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/"
        purchase_url = "https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html"
        item = {
            "id": "sku-sample",
            "name": "ROG Strix G16 exact SKU",
            "url": monitor_url,
            "monitor_url": monitor_url,
            "purchase_url": purchase_url,
            "fetch_status": "ok",
            "current_price_jpy": None,
            "stock_status": "unknown",
            "price_validation_status": "missing",
            "price_validation_reason": "not verified",
        }
        lines = report.retrieval_issue_link_lines(
            latest={"products": [item]},
            component_prices={"products": []},
            peripheral_prices={"products": []},
        )
        matching = next(line for line in lines if "ROG Strix G16 exact SKU" in line)
        self.assertIn(purchase_url, matching)
        self.assertNotIn(monitor_url, matching)

    def test_purchase_page_fetch_failure_is_visible_even_when_monitor_page_was_read(self):
        report_text = "\n".join(report.retrieval_issue_link_lines(
            latest={"products": [{
                "id": "sku-sample",
                "name": "Product with blocked checkout page",
                "url": "https://example.com/spec",
                "monitor_url": "https://example.com/spec",
                "purchase_url": "https://store.example.com/exact-sku",
                "purchase_page_fetch_status": "error",
                "purchase_page_fetch_error": "HTTPError:403",
                "fetch_status": "ok",
                "current_price_jpy": None,
                "stock_status": "unknown",
                "price_validation_status": "missing",
            }]},
            component_prices={"products": []},
            peripheral_prices={"products": []},
        ))
        self.assertIn("購入ページ取得エラー", report_text)
        self.assertIn("https://store.example.com/exact-sku", report_text)

    def test_legacy_retrieval_section_shows_purchase_link_first_and_monitor_link_separately(self):
        monitor_url = "https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025-g614/spec/"
        purchase_url = "https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html"
        lines = report.retrieval_issue_link_section(
            {"products": [{
                "id": "sku-sample",
                "name": "ROG Strix G16 exact SKU",
                "url": monitor_url,
                "monitor_url": monitor_url,
                "purchase_url": purchase_url,
                "fetch_status": "ok",
                "current_price_jpy": None,
                "stock_status": "unknown",
                "price_validation_status": "missing",
            }]},
            build_components={"products": []},
            peripherals={"products": []},
        )
        matching = next(line for line in lines if "ROG Strix G16 exact SKU" in line)
        self.assertIn("[商品ページ](" + purchase_url + ")", matching)
        self.assertIn("[監視/比較ページ](" + monitor_url + ")", matching)


if __name__ == "__main__":
    unittest.main()
