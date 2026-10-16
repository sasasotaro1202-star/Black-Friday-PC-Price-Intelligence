import pathlib
import sys
import threading
import time
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
        self.assertEqual(target["monitor_url"], "https://www.yodobashi.com/product/100000001006099089/")
        self.assertEqual(target["purchase_url"], "https://www.biccamera.com/bc/item/9242996/")
        self.assertIn("https://www.biccamera.com/bc/item/9242996/", target["monitor_urls"])
        self.assertEqual(target["target_price_jpy"], 5500)
        self.assertIn("G213r", target["identity_terms"])
        self.assertIn("www.biccamera.com", target["allowed_hosts"])
        self.assertIn("www.yodobashi.com", target["allowed_hosts"])

    def test_ranked_alternatives_are_monitored_separately_from_budget_targets(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        primary = {x["id"] for x in config["peripherals"]}
        alternatives = config.get("peripheral_alternatives", [])
        self.assertGreaterEqual(len(alternatives), 5)
        self.assertFalse(primary.intersection(x["id"] for x in alternatives))
        for item in alternatives:
            self.assertFalse(item.get("mandatory", False))
            self.assertTrue(item.get("track_current_price"))
            self.assertTrue(item.get("monitor_url", "").startswith("https://"))
            self.assertTrue(item.get("identity_terms"))
            self.assertTrue(item.get("allowed_hosts"))

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

    def test_old_price_is_not_inherited_after_product_replacement(self):
        target = {
            "id": "speakers",
            "name": "Creative Pebble (classic) compact 2.0 USB-powered speakers",
            "monitor_url": "https://jp.creative.com/p/speakers/creative-pebble",
            "purchase_url": "https://jp.creative.com/p/speakers/creative-pebble",
            "identity_terms": ["Creative Pebble"],
            "model_code": "Creative Pebble classic",
            "allowed_hosts": ["jp.creative.com"],
            "min_price_jpy": 1500,
            "max_price_jpy": 10000,
            "target_price_jpy": 2500,
        }
        previous = {
            "id": "speakers",
            "name": "Edifier MR5 studio monitors",
            "monitor_url": "https://www.edifier.jp/products/mr5",
            "current_price_jpy": 39980,
            "last_valid_price_jpy": 39980,
            "stock_status": "in_stock",
        }
        with patch.object(peripheral_monitor, "fetch", side_effect=RuntimeError("temporary fetch failure")):
            row = peripheral_monitor.run_one(target, previous, "2026-10-10T23:30:00+09:00")
        self.assertIsNone(row["current_price_jpy"])
        self.assertIsNone(row["last_valid_price_jpy"])
        self.assertFalse(row["price_verified"])

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


    def test_each_accessory_category_has_three_scored_ranked_options(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        items = [
            x for x in (config.get("peripherals", []) + config.get("peripheral_alternatives", []))
            if isinstance(x, dict)
        ]
        policy = config.get("peripheral_ranking_policy", {})
        groups = policy.get("category_order", [])
        self.assertEqual(len(groups), 8)
        all_ids = [x.get("id") for x in items]
        self.assertEqual(len(all_ids), len(set(all_ids)), "peripheral candidate IDs must be unique")
        for group in groups:
            category = group["category"]
            with self.subTest(category=category):
                members = [x for x in items if x.get("category") == category]
                self.assertEqual(len(members), 3, f"{category} must have exactly three candidates")
                scores = [x.get("ranking_score_100") for x in members]
                self.assertTrue(all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 100 for x in scores))
                self.assertEqual(len({x["id"] for x in members}), 3)
                for candidate in members:
                    # The first cable option is intentionally a no-purchase policy:
                    # use the cable included in the monitor box unless it is missing.
                    if candidate.get("id") != "cables":
                        self.assertTrue(candidate.get("purchase_url") or candidate.get("monitor_url"))
                    else:
                        self.assertEqual(category, "cables")
                    self.assertTrue(candidate.get("ranking_reason"))
                sorted_members = sorted(members, key=lambda x: x["ranking_score_100"], reverse=True)
                self.assertEqual(sorted(scores, reverse=True), [x["ranking_score_100"] for x in sorted_members])
        mandatory_total = sum(int(x.get("target_price_jpy", 0)) for x in config["peripherals"] if x.get("mandatory", True))
        self.assertEqual(mandatory_total, config["peripheral_budget_jpy"])
        self.assertEqual(config["pc_budget_jpy"] + config["peripheral_budget_jpy"], config["total_budget_jpy"])


    def test_store_observation_requires_branch_exact_model_freshness_and_audit_evidence(self):
        import json
        from intelligence import store_observation_validation

        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = dict(next(x for x in config["peripherals"] if x["id"] == "main_monitor"))
        stores = {x["id"]: x for x in config["purchase_channels"]["physical_store_candidates"]}
        target.update({
            "store_price_jpy": 19980,
            "store_price_checked_at": "2026-10-15T11:50:00+09:00",
            "store_stock_status": "in_stock",
            "store_confirmation_url": stores["biccamera_tenjin_1"]["official_store_url"],
            "store_model_match": True,
            "store_observation_store_id": "biccamera_tenjin_1",
            "store_evidence_type": "store_phone_confirmation",
            "store_evidence_notes": "店頭担当者に型番Q27G40E/11、税込価格、在庫を確認した。",
        })
        now = "2026-10-15T12:00:00+09:00"
        valid = store_observation_validation(target, now)
        self.assertTrue(valid["store_price_confirmed"])
        self.assertEqual(valid["store_price_jpy"], 19980)
        self.assertEqual(valid["store_observation_status"], "PRICE_VERIFIED")
        self.assertEqual(valid["store_stock_status"], "in_stock")

        invalid_variants = [
            ({"store_observation_store_id": "unlisted_store"}, "BRANCH_UNVERIFIED"),
            ({"store_evidence_type": None}, "EVIDENCE_TYPE_UNVERIFIED"),
            ({"store_evidence_notes": ""}, "EVIDENCE_NOTES_MISSING"),
            ({"store_model_match": False}, "EXACT_MODEL_UNVERIFIED"),
            ({"store_confirmation_url": "https://example.com/store"}, "SOURCE_URL_UNVERIFIED"),
            ({"store_price_checked_at": "2026-10-15T10:00:00+09:00"}, "FUTURE_OR_STALE"),
        ]
        for changes, expected_status in invalid_variants:
            with self.subTest(expected_status=expected_status):
                candidate = dict(target)
                candidate.update(changes)
                result = store_observation_validation(candidate, now)
                self.assertFalse(result["store_price_confirmed"])
                self.assertIsNone(result["store_price_jpy"])
                self.assertEqual(result["store_observation_status"], expected_status)

    def test_online_listing_for_store_purchase_is_never_mislabelled_as_store_price(self):
        target = dict(self.target)
        target.update({
            "purchase_channel": "physical_store",
            "store_inventory_required_before_purchase": True,
            "online_price_is_comparison_only": True,
            "physical_store_candidate_ids": ["biccamera_tenjin_1", "yodobashi_hakata"],
        })
        parsed = {
            "page_text_excerpt": "AOC Q27G40E/11 ￥20,790 在庫あり",
            "price_jpy": None,
            "price_source_mode": "none",
            "price_context": None,
            "stock_status": "in_stock",
            "name": "AOC Q27G40E/11",
        }
        with patch.object(peripheral_monitor, "fetch", return_value=("<html></html>", self.target["monitor_url"], {})), patch.object(peripheral_monitor, "parse_page", return_value=parsed):
            row = peripheral_monitor.run_one(target, {}, "2026-10-15T12:00:00+09:00")
        self.assertTrue(row["price_verified"])
        self.assertEqual(row["online_comparison_price_jpy"], 20790)
        self.assertTrue(row["online_reference_price_verified"])
        self.assertIsNone(row["store_price_jpy"])
        self.assertFalse(row["store_price_confirmed"])
        self.assertEqual(row["store_stock_status"], "unknown")


    def test_official_tenjin_inventory_page_separates_branch_stock_from_cash_price(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = next(x for x in config["peripherals"] if x["id"] == "keyboard")
        check = target["store_inventory_checks"][0]
        page = """
        <html><body>
          <h1>Logicool ゲーミング キーボード G213r</h1>
          <div>福岡県 ビックカメラ 天神１号館</div>
          <div>○ 在庫残少 ○ 60分以内にご用意</div>
        </body></html>
        """
        with patch.object(
            peripheral_monitor, "fetch",
            return_value=(page, check["url"], {})
        ):
            result = peripheral_monitor.observe_store_inventory(target, "2026-10-15T10:00:00+09:00")
        self.assertTrue(result["store_inventory_verified"])
        self.assertEqual(result["store_inventory_status"], "low_stock")
        self.assertEqual(result["store_inventory_store_id"], "biccamera_tenjin_1")
        self.assertIn(check["url"], result["store_inventory_source_url"])
        # Stock/online pickup status must never become a store cash price.
        self.assertNotIn("store_price_jpy", result)

    def test_missing_branch_or_stock_phrase_never_becomes_out_of_stock(self):
        target = dict(self.target)
        target.update({
            "purchase_channel": "physical_store",
            "store_inventory_required_before_purchase": True,
            "physical_store_candidate_ids": ["biccamera_tenjin_1"],
            "store_inventory_checks": [{
                "store_id": "biccamera_tenjin_1",
                "store_name": "ビックカメラ天神1号館",
                "url": "https://www.biccamera.com/bc/tenpo/SfrBcToriokiList.jsp?GOODS_NO=9242996",
                "allowed_hosts": ["www.biccamera.com"],
                "branch_match_terms": ["ビックカメラ 天神１号館"],
                "source_type": "official_branch_stock_page",
            }],
        })
        target["allowed_hosts"] = ["www.yodobashi.com"]
        page = "<html><body>Logicool G213r 別の店舗 在庫状況確認中</body></html>"
        with patch.object(
            peripheral_monitor, "fetch",
            return_value=(page, target["store_inventory_checks"][0]["url"], {})
        ):
            result = peripheral_monitor.observe_store_inventory(target, "2026-10-15T10:00:00+09:00")
        self.assertFalse(result["store_inventory_verified"])
        self.assertEqual(result["store_inventory_status"], "unknown")
        self.assertEqual(result["store_inventory_store_ids_available"], [])

    def test_visible_text_normalizes_unicode_and_collapses_whitespace(self):
        html = "<html><body>ビックカメラ　 天神１号館<br>在庫あり</body></html>"
        normalized = peripheral_monitor.normalized_visible_text(html)
        self.assertEqual(normalized, "ビックカメラ 天神1号館 在庫あり")

    def test_compact_removes_whitespace_and_normalizes_full_width_digits(self):
        self.assertEqual(
            peripheral_monitor._compact(" ビックカメラ　天神１号館 "),
            "ビックカメラ天神1号館",
        )

    def test_branch_stock_status_survives_whitespace_between_tokens(self):
        self.assertEqual(
            peripheral_monitor._branch_stock_status("在庫　あり"),
            "in_stock",
        )


    def test_observe_targets_uses_bounded_parallelism_and_preserves_input_order(self):
        targets = [
            {"id": f"item_{i}", "name": f"Item {i}", "track_current_price": True}
            for i in range(8)
        ]
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        def fake_run_one(target, previous, observed_at):
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.03)
            with lock:
                state["active"] -= 1
            return {"id": target["id"], "retrieval_time": observed_at}

        with patch.object(peripheral_monitor, "run_one", side_effect=fake_run_one):
            rows = peripheral_monitor.observe_targets(
                targets, {}, "2026-10-16T16:00:00+09:00", max_workers=50
            )

        self.assertEqual([row["id"] for row in rows], [target["id"] for target in targets])
        self.assertGreaterEqual(state["max_active"], 2)
        self.assertLessEqual(state["max_active"], 3)

    def test_observe_targets_handles_empty_target_list(self):
        self.assertEqual(peripheral_monitor.observe_targets([], {}, "2026-10-16T16:00:00+09:00"), [])


if __name__ == "__main__":
    unittest.main()
