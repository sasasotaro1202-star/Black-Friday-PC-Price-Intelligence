import sys
import unittest

sys.path.insert(0, "scripts")
from official_campaign_dates import parse_explicit_2026_range
from sale_calendar import (
    campaign_entry_for_retailer,
    campaign_window_for_item,
    parse_calendar_dt,
    retailer_key_for_url,
)


class OfficialCampaignDateTests(unittest.TestCase):
    def test_parses_explicit_2026_japanese_date_range_on_bf_page(self):
        result = parse_explicit_2026_range(
            "ブラックフライデーセール 2026年11月20日（金）12:00～12月10日（木）11:59 開催",
            "https://shop.example.jp/black-friday/",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["start_jst"], "2026-11-20T12:00:00+09:00")
        self.assertEqual(result["end_jst"], "2026-12-10T11:59:59+09:00")
        self.assertIn("2026年11月20日", result["evidence"])

    def test_rejects_2025_dates_even_on_black_friday_page(self):
        result = parse_explicit_2026_range(
            "ブラックフライデー 2025年11月14日（金）～12月4日（木）",
            "https://shop.example.jp/black-friday/",
        )
        self.assertIsNone(result)

    def test_rejects_yearless_dates_even_if_bf_keyword_exists(self):
        result = parse_explicit_2026_range(
            "ブラックフライデーセール 11月14日～12月4日",
            "https://shop.example.jp/black-friday/",
        )
        self.assertIsNone(result)

    def test_does_not_infer_from_normal_page_without_bf_context(self):
        result = parse_explicit_2026_range(
            "新生活応援 2026年11月14日～12月4日",
            "https://shop.example.jp/campaign/",
        )
        self.assertIsNone(result)

    def test_rejects_invalid_or_overlong_date_range(self):
        self.assertIsNone(
            parse_explicit_2026_range(
                "Black Friday 2026年11月31日～12月4日",
                "https://shop.example.jp/black-friday/",
            )
        )
        self.assertIsNone(
            parse_explicit_2026_range(
                "Black Friday 2026年10月1日～12月20日",
                "https://shop.example.jp/black-friday/",
            )
        )

    def test_retailer_domain_mapping_is_exact_suffix_not_substring(self):
        self.assertEqual(retailer_key_for_url("https://www.mouse-jp.co.jp/store/g/sku"), "mouse_computer")
        self.assertEqual(retailer_key_for_url("https://www.lenovo.com/jp/ja/p/item"), "lenovo")
        self.assertIsNone(retailer_key_for_url("https://mouse-jp.co.jp.attacker.example/product"))
        self.assertIsNone(retailer_key_for_url("https://unknown.example/product"))

    def test_unconfirmed_calendar_never_counts_as_active_campaign(self):
        now = "2026-11-20T12:00:00+09:00"
        config = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "UNCONFIRMED",
                    "start_jst": None,
                    "end_jst": None,
                    "source_urls": ["https://www.mouse-jp.co.jp/"],
                }
            }
        }
        item = {
            "purchase_url": "https://www.mouse-jp.co.jp/store/g/test",
            "retrieval_time": now,
        }
        result = campaign_window_for_item(item, now, config, {"sources": {}})
        self.assertEqual(result["status"], "UNCONFIRMED")
        self.assertFalse(result["active_now"])
        self.assertFalse(result["active_at_observation"])

    def test_confirmed_campaign_requires_observation_inside_both_windows(self):
        config = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "CONFIRMED_MANUAL",
                    "start_jst": "2026-11-21T00:00:00+09:00",
                    "end_jst": "2026-12-04T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/",
                }
            }
        }
        item = {
            "purchase_url": "https://www.mouse-jp.co.jp/store/g/test",
            "retrieval_time": "2026-11-20T23:59:00+09:00",
        }
        result = campaign_window_for_item(item, "2026-11-22T12:00:00+09:00", config, {"sources": {}})
        self.assertEqual(result["status"], "CONFIRMED_NOT_ACTIVE")
        self.assertTrue(result["active_now"])
        self.assertFalse(result["active_at_observation"])

    def test_scraper_confirmed_source_entry_has_precedence_over_unconfirmed_config(self):
        config = {
            "official_2026_dates": {
                "mouse_computer": {
                    "status": "UNCONFIRMED",
                    "source_urls": ["https://www.mouse-jp.co.jp/"],
                }
            }
        }
        status_data = {
            "sources": {
                "mouse_computer": {
                    "status": "CONFIRMED",
                    "start_jst": "2026-11-14T00:00:00+09:00",
                    "end_jst": "2026-12-04T23:59:59+09:00",
                    "source_url": "https://www.mouse-jp.co.jp/campaign/black-friday/",
                    "evidence": "2026年11月14日～12月4日",
                }
            }
        }
        entry = campaign_entry_for_retailer("mouse_computer", config, status_data)
        self.assertEqual(entry["status"], "CONFIRMED")
        self.assertEqual(entry["start_jst"], "2026-11-14T00:00:00+09:00")

    def test_parse_calendar_naive_datetime_assumes_jst(self):
        self.assertEqual(parse_calendar_dt("2026-11-14T00:00:00").utcoffset().total_seconds(), 9 * 3600)


if __name__ == "__main__":
    unittest.main()
