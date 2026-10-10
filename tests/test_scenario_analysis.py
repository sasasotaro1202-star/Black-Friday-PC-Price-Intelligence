import json
import pathlib
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scenario_analysis


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def offer(candidate, price, retrieved_at, available_at, stock="in_stock"):
    return {
        "id": candidate["id"],
        "name": candidate["name"],
        "url": candidate["url"],
        "form_factor": candidate["form_factor"],
        "current_price_jpy": price,
        "price_source_mode": "direct_structured",
        "price_validation_status": "validated",
        "variant_match": "exact",
        "stock_status": stock,
        "retrieval_time": retrieved_at,
        "available_at": available_at,
        "spec": {
            "gpu": candidate.get("gpu"),
            "ram_gb": candidate.get("ram_gb"),
            "ssd": candidate.get("ssd"),
            "cpu": candidate.get("cpu"),
            "form_factor": candidate.get("form_factor"),
        },
    }


class BlackFridayScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = read_json("config/targets.json")
        cls.catalog_data = read_json("config/candidate_catalog.json")
        cls.catalog = {x["id"]: x for x in cls.catalog_data["candidates"]}

    def test_pre_bf_prices_are_reference_only_and_targets_sum_to_37man(self):
        now = datetime.fromisoformat("2026-10-10T18:00:00+09:00")
        ts = "2026-10-10T17:59:00+09:00"
        outlier = self.catalog["desktop-gtune-fg-a7g7t-5070ti"]
        dg_i5 = self.catalog["desktop-gtune-dg-i5g70-5070"]
        latest = {"generated_at": ts, "products": [
            offer(outlier, 399800, ts, "2026-10-10T17:58:00+09:00"),
            offer(dg_i5, 279800, ts, "2026-10-10T17:58:00+09:00"),
        ]}
        peripheral_products = []
        for item in self.targets["peripherals"]:
            peripheral_products.append({
                "id": item["id"],
                "current_price_jpy": item["target_price_jpy"] + 100,
                "price_verified": bool(item.get("track_current_price")),
                "identity_verified": bool(item.get("track_current_price")),
                "stock_status": "in_stock" if item.get("track_current_price") else "unknown",
                "retrieval_time": ts if item.get("track_current_price") else None,
                "available_at": "2026-10-10T17:58:00+09:00" if item.get("track_current_price") else None,
            })
        peripheral_snapshot = {"generated_at": ts, "products": peripheral_products}

        result = scenario_analysis.build_black_friday_price_plan(
            self.targets, self.catalog_data, latest, peripheral_snapshot, now=now
        )
        self.assertEqual(result["pricing_phase"], "PRE_BLACK_FRIDAY_REFERENCE")
        self.assertFalse(result["black_friday_prices_known"])
        self.assertEqual(result["total_budget_jpy"], 370000)
        self.assertEqual(result["peripheral_target_total_jpy"], 67800)
        self.assertEqual(result["black_friday_ideal_bundle_target_jpy"], 367600)
        self.assertEqual(result["black_friday_target_buffer_jpy"], 2400)
        self.assertEqual(result["black_friday_hard_cap_bundle_jpy"], 370000)
        self.assertFalse(result["all_in_checkout_total_final"])

        speaker = next(x for x in result["peripherals"] if x["id"] == "speakers")
        self.assertEqual(speaker["black_friday_target_price_jpy"], 32000)
        self.assertIsNone(speaker["black_friday_price_observed_jpy"])
        self.assertEqual(speaker["pre_black_friday_reference_price_jpy"], 32100)

        outlier_row = next(x for x in result["rtx_5070_ti_desktop_outliers"]
                           if x["id"] == outlier["id"])
        self.assertEqual(outlier_row["black_friday_target_price_jpy"], 302200)
        self.assertEqual(outlier_row["pre_black_friday_reference_price_jpy"], 399800)
        self.assertIsNone(outlier_row["black_friday_price_observed_jpy"])
        self.assertEqual(outlier_row["discount_needed_to_bf_target_jpy"], 97600)
        self.assertEqual(outlier_row["discount_needed_to_bf_target_pct"], 24.4)
        bands = {x["discount_pct"]: x["price_jpy"] for x in outlier_row["scenario_prices"]}
        self.assertEqual(bands[25], 299850)
        self.assertFalse(outlier_row["configuration_ready"])
        self.assertTrue(outlier_row["catalog_configuration_ready"])

        i5_row = next(x for x in result["pc_candidates"] if x["id"] == dg_i5["id"])
        self.assertEqual(i5_row["pre_black_friday_reference_price_jpy"], 279800)
        self.assertFalse(i5_row["complete_build_target_comparable"])
        self.assertIsNone(i5_row["discount_needed_to_bf_target_jpy"])

    def test_bf_price_requires_fresh_verified_observation_inside_window(self):
        now = datetime.fromisoformat("2026-11-20T12:01:00+09:00")
        retrieved = "2026-11-20T12:00:00+09:00"
        available = "2026-11-20T11:59:00+09:00"
        outlet = self.catalog["desktop-gtune-dg-a7g70-5070"]
        latest = {"generated_at": retrieved, "products": [
            offer(outlet, 299800, retrieved, available),
        ]}
        peripheral_products = []
        for item in self.targets["peripherals"]:
            is_tracked = bool(item.get("track_current_price"))
            peripheral_products.append({
                "id": item["id"],
                "current_price_jpy": 30000 if item["id"] == "speakers" else item["target_price_jpy"],
                "price_verified": is_tracked,
                "identity_verified": is_tracked,
                "stock_status": "in_stock" if is_tracked else "unknown",
                "retrieval_time": retrieved if is_tracked else None,
                "available_at": available if is_tracked else None,
            })
        snapshot = {"generated_at": retrieved, "products": peripheral_products}

        result = scenario_analysis.build_black_friday_price_plan(
            self.targets, self.catalog_data, latest, snapshot, now=now
        )
        self.assertEqual(result["pricing_phase"], "BLACK_FRIDAY_WINDOW")
        self.assertTrue(result["black_friday_prices_known"])
        self.assertTrue(result["black_friday_pc_price_cap_final"])
        self.assertFalse(result["all_in_checkout_total_final"])
        row = next(x for x in result["pc_candidates"] if x["id"] == outlet["id"])
        self.assertTrue(row["black_friday_offer_verified"])
        self.assertEqual(row["black_friday_price_observed_jpy"], 299800)
        self.assertIsNone(row["pre_black_friday_reference_price_jpy"])
        speaker = next(x for x in result["peripherals"] if x["id"] == "speakers")
        self.assertTrue(speaker["black_friday_price_verified"])
        self.assertEqual(speaker["black_friday_price_observed_jpy"], 30000)
        self.assertIsNone(speaker["pre_black_friday_reference_price_jpy"])

    def test_unavailable_or_stale_data_never_becomes_bf_observed_price(self):
        now = datetime.fromisoformat("2026-11-20T12:10:00+09:00")
        old = "2026-11-20T09:00:00+09:00"
        outlet = self.catalog["desktop-gtune-dg-a7g70-5070"]
        latest = {"generated_at": old, "products": [
            offer(outlet, 299800, old, "2026-11-20T08:59:00+09:00"),
        ]}
        snapshot = {"generated_at": old, "products": []}
        result = scenario_analysis.build_black_friday_price_plan(
            self.targets, self.catalog_data, latest, snapshot, now=now
        )
        row = next(x for x in result["pc_candidates"] if x["id"] == outlet["id"])
        self.assertFalse(row["black_friday_offer_verified"])
        self.assertIsNone(row["black_friday_price_observed_jpy"])


if __name__ == "__main__":
    unittest.main()
