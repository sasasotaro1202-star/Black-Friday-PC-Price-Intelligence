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
        self.assertEqual(target["target_price_jpy"], 4500)
        self.assertIn("G213r", target["identity_terms"])
        self.assertIn("www.biccamera.com", target["allowed_hosts"])
        self.assertIn("www.yodobashi.com", target["allowed_hosts"])

    def test_mouse_and_mousepad_do_not_use_foreign_retail_images(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        items = {x["id"]: x for x in (config["peripherals"] + config.get("peripheral_alternatives", []))}
        for item_id in ("mouse", "mousepad"):
            with self.subTest(item_id=item_id):
                self.assertIsNone(items[item_id].get("image_url"))
                self.assertIsNone(items[item_id].get("image_source_url"))
                self.assertIn("画像未確認", items[item_id].get("image_note", ""))

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

    def test_all_configured_exact_model_offers_are_compared(self):
        target = dict(self.target)
        target["monitor_urls"] = [
            "https://www.yodobashi.com/product/example/",
            "https://www.biccamera.com/bc/item/example/",
        ]
        target["allowed_hosts"] = ["www.yodobashi.com", "www.biccamera.com"]
        target["purchase_channel"] = "compare_online_and_store"
        target["purchase_channel_options"] = ["online", "physical_store", "store_pickup"]
        target["store_inventory_required_before_purchase"] = False
        parsed_by_url = {
            target["monitor_urls"][0]: {
                "page_text_excerpt": "AOC Q27G40E/11 20,790円 在庫残少",
                "price_jpy": 20790, "price_source_mode": "direct_structured",
                "price_context": None, "stock_status": "low_stock", "name": "AOC Q27G40E/11",
            },
            target["monitor_urls"][1]: {
                "page_text_excerpt": "AOC Q27G40E/11 19,990円 在庫あり",
                "price_jpy": 19990, "price_source_mode": "direct_structured",
                "price_context": None, "stock_status": "in_stock", "name": "AOC Q27G40E/11",
            },
        }
        def parsed_page(final_url, html, expected):
            return parsed_by_url[final_url]
        with patch.object(peripheral_monitor, "fetch", side_effect=[
            ("<html>store one</html>", target["monitor_urls"][0], {}),
            ("<html>store two</html>", target["monitor_urls"][1], {}),
        ]) as fetch, patch.object(peripheral_monitor, "parse_page", side_effect=parsed_page):
            row = peripheral_monitor.run_one(target, {}, "2026-10-10T15:00:00+09:00")
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(row["online_offer_count"], 2)
        self.assertEqual(row["online_actionable_offer_count"], 2)
        self.assertEqual(row["current_price_jpy"], 19990)
        self.assertEqual(row["online_best_offer_url"], target["monitor_urls"][1])
        self.assertEqual(row["purchase_url"], target["monitor_urls"][1])
        self.assertFalse(row["store_price_confirmed"])
        self.assertEqual(row["channel_comparison_status"], "ONLINE_OPTIONS_COMPARED_STORE_PENDING")

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
            "id": "mouse",
            "name": "Logicool G304",
            "monitor_url": "https://www.yodobashi.com/product/100000001004334450/",
            "purchase_url": "https://www.yodobashi.com/product/100000001004334450/",
            "identity_terms": ["G304"],
            "model_code": "G304",
            "allowed_hosts": ["www.yodobashi.com"],
            "min_price_jpy": 1000,
            "max_price_jpy": 15000,
            "target_price_jpy": 5000,
        }
        previous = {
            "id": "mouse",
            "name": "Logicool G203 LIGHTSYNC",
            "monitor_url": "https://www.yodobashi.com/product/100000001005593918/",
            "current_price_jpy": 3720,
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
        attempts = [x for x in row["retrieval_attempts"] if x.get("status") == "price_unverified"]
        self.assertTrue(attempts)
        self.assertEqual(attempts[0]["price_candidate_jpy"], 7000)


    def test_each_accessory_category_has_rubric_scored_real_products(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        items = [
            x for x in (config.get("peripherals", []) + config.get("peripheral_alternatives", []))
            if isinstance(x, dict)
        ]
        policy = config.get("peripheral_ranking_policy", {})
        groups = policy.get("category_order", [])
        categories = {x["category"] for x in groups}
        self.assertNotIn("speakers", categories)
        self.assertNotIn("power_strip", categories)
        all_ids = [x.get("id") for x in items]
        self.assertEqual(len(all_ids), len(set(all_ids)), "peripheral candidate IDs must be unique")
        limits = {
            "workload_fit_points": 35,
            "budget_fit_points": 30,
            "feature_spec_points": 20,
            "substitution_risk_points": 15,
        }
        for group in groups:
            category = group["category"]
            with self.subTest(category=category):
                members = [x for x in items if x.get("category") == category]
                products = [
                    x for x in members
                    if x.get("category") != "budget_reserve"
                    and x.get("purchase_channel") != "conditional_need_only"
                    and not x.get("score_exclusion_reason_ja")
                ]
                self.assertEqual(len(products), 2 if category == "cables" else 3)
                self.assertEqual(len({x["id"] for x in products}), len(products))
                scores = []
                for candidate in products:
                    score = candidate.get("ranking_score_100")
                    self.assertIsInstance(score, int)
                    self.assertTrue(0 <= score <= 100)
                    card = candidate.get("fit_scorecard") or {}
                    for key, maximum in limits.items():
                        self.assertIsInstance(card.get(key), int, f"{candidate['id']}:{key}")
                        self.assertTrue(0 <= card[key] <= maximum, f"{candidate['id']}:{key}")
                    self.assertEqual(sum(card[key] for key in limits), score)
                    self.assertTrue(card.get("rationale_ja"))
                    self.assertTrue(card.get("limitations_ja"))
                    self.assertTrue(candidate.get("purchase_url") or candidate.get("monitor_url"))
                    scores.append(score)
        cable_rule = next(x for x in config["peripherals"] if x["id"] == "cables")
        self.assertIsNone(cable_rule.get("ranking_score_100"))
        self.assertIn("条件付き購入ルール", cable_rule.get("score_exclusion_reason_ja", ""))
        mandatory_total = sum(int(x.get("target_price_jpy", 0)) for x in config["peripherals"] if x.get("mandatory", True))
        self.assertEqual(mandatory_total, config["peripheral_budget_jpy"])
        self.assertEqual(config["pc_budget_jpy"] + config["unallocated_contingency_jpy"], config["total_budget_jpy"])


    def test_store_observation_requires_branch_exact_model_freshness_and_audit_evidence(self):
        import json
        from intelligence import store_observation_validation

        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = dict(next(x for x in config["peripherals"] if x["id"] == "main_monitor"))
        stores = {x["id"]: x for x in config["purchase_channels"]["physical_store_candidates"]}
        target.update({
            "store_price_jpy": 19980,
            "store_price_basis": "tax_inclusive_cash",
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
            ({"store_evidence_type": "official_branch_stock_page"}, "EVIDENCE_TYPE_UNVERIFIED"),
            ({"store_price_basis": None}, "PRICE_BASIS_UNVERIFIED"),
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

    def test_empty_branch_price_matrix_does_not_create_a_fake_quote(self):
        import json
        from intelligence import store_observation_validation

        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = dict(next(x for x in config["peripherals"] if x["id"] == "main_monitor"))
        result = store_observation_validation(target, "2026-10-15T12:00:00+09:00")
        self.assertEqual(result["store_price_observations"], [])
        self.assertEqual(result["store_price_observation_count"], 0)
        self.assertEqual(result["store_price_verified_store_ids"], [])
        self.assertFalse(result["store_price_confirmed"])
        self.assertEqual(result["store_observation_status"], "UNCONFIRMED")

    def test_multiple_branch_cash_quotes_are_validated_and_compared_independently(self):
        import json
        from intelligence import store_observation_validation

        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        target = dict(next(x for x in config["peripherals"] if x["id"] == "main_monitor"))
        stores = {x["id"]: x for x in config["purchase_channels"]["physical_store_candidates"]}
        now = "2026-10-15T12:00:00+09:00"
        target["store_price_observations"] = [
            {
                "store_id": "biccamera_tenjin_1",
                "price_jpy": 22980,
                "checked_at": "2026-10-15T11:55:00+09:00",
                "stock_status": "in_stock",
                "confirmation_url": stores["biccamera_tenjin_1"]["official_store_url"],
                "model_match": True,
                "evidence_type": "store_phone_confirmation",
                "evidence_notes": "型番Q27G40E/11、税込の店頭現金価格、在庫を確認。ポイントは差し引いていない。",
                "price_basis": "tax_inclusive_cash",
            },
            {
                "store_id": "yodobashi_hakata",
                "price_jpy": 21980,
                "checked_at": "2026-10-15T11:56:00+09:00",
                "stock_status": "low_stock",
                "confirmation_url": stores["yodobashi_hakata"]["official_store_url"],
                "model_match": True,
                "evidence_type": "store_phone_confirmation",
                "evidence_notes": "型番Q27G40E/11、税込の店頭現金価格、在庫を確認。ポイントは差し引いていない。",
                "price_basis": "tax_inclusive_cash",
            },
            {
                "store_id": "yodobashi_hakata",
                "price_jpy": 19980,
                "checked_at": "2026-10-15T11:57:00+09:00",
                "stock_status": "in_stock",
                "confirmation_url": stores["yodobashi_hakata"]["official_store_url"],
                "model_match": True,
                "evidence_type": "store_phone_confirmation",
                "evidence_notes": "誤った価格基準の負例。ポイント相当額を差し引いている。",
                "price_basis": "points_deducted",
            },
        ]

        result = store_observation_validation(target, now)
        self.assertTrue(result["store_price_confirmed"])
        self.assertEqual(result["store_price_jpy"], 21980)
        self.assertEqual(result["store_observation_store_id"], "yodobashi_hakata")
        self.assertEqual(result["store_price_observation_count"], 3)
        self.assertEqual(
            set(result["store_price_verified_store_ids"]),
            {"biccamera_tenjin_1", "yodobashi_hakata"},
        )
        by_status = {
            (row["store_observation_store_id"], row["store_observation_status"], row.get("store_price_jpy"))
            for row in result["store_price_observations"]
        }
        self.assertIn(("yodobashi_hakata", "PRICE_BASIS_UNVERIFIED", None), by_status)
        self.assertIn(("biccamera_tenjin_1", "PRICE_VERIFIED", 22980), by_status)
        self.assertIn(("yodobashi_hakata", "PRICE_VERIFIED", 21980), by_status)

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


    def test_store_inventory_check_ids_must_belong_to_each_peripherals_candidate_branches(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        for target in config["peripherals"]:
            candidates = set(target.get("physical_store_candidate_ids") or [])
            for check in target.get("store_inventory_checks") or []:
                with self.subTest(item=target["id"], store_id=check.get("store_id")):
                    self.assertIn(check.get("store_id"), candidates)
                    self.assertTrue(check.get("url", "").startswith("https://"))
                    self.assertTrue(check.get("allowed_hosts"))
                    self.assertTrue(check.get("branch_match_terms"))

    def test_primary_peripherals_monitor_both_fukuoka_store_candidates_without_inventing_stock(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        peripherals = {x["id"]: x for x in config["peripherals"]}
        expected_yodobashi_urls = {
            "main_monitor": "https://www.yodobashi.com/product/100000001009314680/",
            "keyboard": "https://www.yodobashi.com/product/100000001006099089/",
            "mouse": "https://www.yodobashi.com/product/100000001004334450/",
            "mousepad": "https://www.yodobashi.com/product/100000001001488658/",
        }
        for item_id, yodobashi_url in expected_yodobashi_urls.items():
            with self.subTest(item_id=item_id):
                target = peripherals[item_id]
                checks = {x["store_id"]: x for x in target["store_inventory_checks"]}
                self.assertIn("biccamera_tenjin_1", checks)
                self.assertIn("yodobashi_hakata", checks)
                check = checks["yodobashi_hakata"]
                self.assertEqual(check["url"], yodobashi_url)
                self.assertEqual(check["source_type"], "official_product_page_pickup_information")
                self.assertIn("unknown", check.get("notes", ""))
                self.assertTrue(target["store_price_is_separate_evidence"])
                self.assertFalse(target["online_purchase_allowed_when_store_price_unconfirmed"])
                self.assertTrue(target["online_price_is_comparison_only"])
                self.assertEqual(target["purchase_channel_preference"], "physical_store_first")

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


    def test_all_configured_fallback_urls_are_allowlisted(self):
        import json
        config = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        targets = config.get("peripherals", []) + config.get("peripheral_alternatives", [])
        for target in targets:
            if not target.get("track_current_price"):
                continue
            urls = target.get("monitor_urls") or [target.get("monitor_url")]
            with self.subTest(target=target.get("id")):
                self.assertTrue(urls)
                for url in urls:
                    self.assertTrue(
                        peripheral_monitor.allowed_host(url, target.get("allowed_hosts")),
                        f"{target.get('id')} has an unapproved fallback URL: {url}",
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
