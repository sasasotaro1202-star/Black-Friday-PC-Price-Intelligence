"""Keep the human-facing plan, DIY profile, budget, and Actions cadence in sync.

These checks are deliberately network-independent. The machine-readable config is
the source of truth; stale prose must not silently reset the user's choices.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ProjectConfigurationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = read_json("config/targets.json")
        cls.build = read_json("config/build_components.json")
        cls.profile = cls.build["profile"]

    def test_all_in_budget_and_primary_peripheral_targets_balance(self):
        targets = self.targets
        self.assertEqual(
            targets["pc_target_jpy"] + targets["peripheral_budget_jpy"],
            targets["total_budget_jpy"],
        )
        self.assertEqual(targets["budget_jpy"], targets["pc_target_jpy"])
        mandatory_peripheral_target = sum(
            int(item["target_price_jpy"])
            for item in targets["peripherals"]
            if item.get("mandatory", True)
        )
        self.assertEqual(mandatory_peripheral_target, targets["peripheral_budget_jpy"])
        self.assertEqual(targets["total_budget_jpy"], 400000)
        self.assertEqual(targets["peripheral_budget_jpy"], 69800)
        self.assertEqual(targets["pc_target_jpy"], 330200)

    def test_diy_profile_matches_budget_and_never_penalizes_assembly_time(self):
        profile = self.profile
        self.assertEqual(profile["total_budget_jpy"], self.targets["total_budget_jpy"])
        self.assertEqual(profile["peripheral_budget_jpy"], self.targets["peripheral_budget_jpy"])
        self.assertEqual(profile["pc_budget_jpy"], self.targets["pc_target_jpy"])
        self.assertEqual(profile["minimum_ram_gb"], 32)
        self.assertEqual(profile["minimum_ssd_gb"], 1000)
        self.assertEqual(profile["assembly_time_is_constraint"], False)
        self.assertEqual(profile["assembly_time_penalty_points"], 0)
        self.assertEqual(
            profile["pc_build_method_preference"],
            "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION",
        )
        self.assertEqual(profile["bto_role"], "REFERENCE_BENCHMARK_ONLY")
        self.assertIn("shopping.yahoo.co.jp", profile["allowed_search_reference_domains"])

    def test_primary_build_subtotal_counts_one_gpu_only(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        selected_ids = list(self.profile["fixed_part_ids"]) + [
            self.profile["primary_gpu_choice_id"]
        ]
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertTrue(all(part_id in parts_by_id for part_id in selected_ids))
        components_subtotal = sum(
            int(parts_by_id[part_id]["target_price_jpy"]) for part_id in selected_ids
        )
        pc_total = (
            components_subtotal
            + int(self.profile["build_shipping_reserve_jpy"])
            + int(self.profile["small_parts_reserve_jpy"])
        )
        self.assertEqual(components_subtotal, 291600)
        self.assertEqual(pc_total, 300600)
        self.assertEqual(
            pc_total + int(self.profile["peripheral_budget_jpy"]),
            370400,
        )
        self.assertLessEqual(370400, int(self.profile["total_budget_jpy"]))

    def test_windows_retail_package_is_live_tracked_and_exact_model_identified(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        os = parts_by_id["os-windows11-home"]
        self.assertTrue(os["track_price"])
        self.assertEqual(os["model_code"], "HAJ-00094")
        self.assertEqual(os["target_price_jpy"], 14800)
        self.assertEqual(os["monitor_url"], "https://kakaku.com/item/K0001432816/")
        self.assertIn("yodobashi.com", os["direct_retailer_urls"][0])

    def test_gpu_skus_and_dimensions_are_source_backed_and_specific(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        main = parts_by_id["gpu-rtx5070-12gb"]
        self.assertEqual(main["model_code"], "VCG507012DFSXPB1-O")
        self.assertEqual(main["specs"]["card_length_mm"], 290)
        self.assertTrue(main.get("direct_retailer_urls"))
        self.assertEqual(len(main["direct_retailer_urls"]), 3)
        self.assertIn("joshinweb.jp", main["direct_retailer_urls"][0])
        self.assertIn("sofmap.com", main["direct_retailer_urls"][1])
        self.assertIn("tsukumo.co.jp", main["direct_retailer_urls"][2])
        self.assertIn("sofmap.com", self.profile["allowed_search_reference_domains"])
        self.assertIn("tsukumo.co.jp", self.profile["allowed_search_reference_domains"])
        self.assertIn("amazon.co.jp", self.profile["allowed_search_reference_domains"])

        for part_id, host in (
            ("cpu-ryzen7-9700x", "yodobashi.com"),
            ("motherboard-asrock-b850m-pro-rs-wifi", "yodobashi.com"),
            ("psu-corsair-rm850e-2025", "dospara.co.jp"),
            ("case-fractal-pop-air-tg", "yodobashi.com"),
            ("cooler-thermalright-pa120-se-v3", "dospara.co.jp"),
        ):
            self.assertTrue(parts_by_id[part_id].get("direct_retailer_urls"), part_id)
            self.assertIn(host, parts_by_id[part_id]["direct_retailer_urls"][0], part_id)

        self.assertEqual(len(parts_by_id["cpu-ryzen7-9700x"]["direct_retailer_urls"]), 2)
        self.assertIn("tsukumo.co.jp", parts_by_id["cpu-ryzen7-9700x"]["direct_retailer_urls"][1])
        self.assertIn("tsukumo.co.jp", self.profile["allowed_search_reference_domains"])
        self.assertEqual(len(parts_by_id["motherboard-asrock-b850m-pro-rs-wifi"]["direct_retailer_urls"]), 2)
        self.assertIn("pc4u.co.jp", parts_by_id["motherboard-asrock-b850m-pro-rs-wifi"]["direct_retailer_urls"][1])
        self.assertIn("pc4u.co.jp", self.profile["allowed_search_reference_domains"])
        self.assertIn("VCG507012DFSXPB1-O", main["spec_source_url"])

        vram = parts_by_id["gpu-rtx5060ti-16gb"]
        self.assertEqual(vram["model_code"], "VCG5060T16DFXPB1-O")
        self.assertEqual(vram["specs"]["card_length_mm"], 245)
        self.assertEqual(vram["specs"]["card_width_mm"], 120)
        self.assertEqual(vram["specs"]["card_thickness_mm"], 39.9)
        self.assertEqual(vram["specs"]["connector"], "8-pin PCIe")
        self.assertEqual(vram["specs"]["minimum_psu_w"], 600)
        self.assertIn("ask-corp.jp", vram["spec_source_url"])
        self.assertTrue(vram.get("direct_retailer_urls"))
        self.assertIn("dospara.co.jp", vram["direct_retailer_urls"][0])
        self.assertIn("dospara.co.jp", self.profile["allowed_search_reference_domains"])

        dark = parts_by_id["gpu-rtx5070ti-16gb"]
        self.assertEqual(dark["model_code"], "VCG5070T16TFXXPB1-O")
        self.assertEqual(dark["specs"]["card_length_mm"], 300)
        self.assertEqual(dark["specs"]["card_width_mm"], 120)
        self.assertEqual(dark["specs"]["card_thickness_mm"], 60)
        self.assertEqual(dark["specs"]["card_thickness_slots"], 2.98)
        self.assertTrue(dark.get("direct_retailer_urls"))
        self.assertIn("VCG5070T16TFXXPB1-O", dark["spec_source_url"])

        instructions = read_text(".github/copilot-instructions.md")
        self.assertIn("exact model/SKU evidence", instructions)
        self.assertIn("direct_retailer_urls", read_text("scripts/build_component_monitor.py"))
        self.assertIn("shopping.yahoo.co.jp", self.profile["allowed_search_reference_domains"])
        self.assertIn("ymall.jp", self.profile["allowed_search_reference_domains"])
        self.assertIn("ymall.jp", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["direct_retailer_urls"][0])
        self.assertIn("teamgroupinc.com", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["spec_source_url"])
        self.assertIn("CTCWD532G6000HC38ADC01", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["spec_source_url"])
        self.assertEqual(len(parts_by_id["ssd-crucial-p3-plus-1tb"]["direct_retailer_urls"]), 3)
        self.assertIn("tsukumo.co.jp", parts_by_id["ssd-crucial-p3-plus-1tb"]["direct_retailer_urls"][0])
        self.assertIn("dospara.co.jp", parts_by_id["ssd-crucial-p3-plus-1tb"]["direct_retailer_urls"][1])
        self.assertIn("kaago.com", parts_by_id["ssd-crucial-p3-plus-1tb"]["direct_retailer_urls"][2])
        self.assertIn("kaago.com", self.profile["allowed_search_reference_domains"])
        self.assertTrue(parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["direct_retailer_urls"][1].startswith("https://www.amazon.co.jp/"))
        self.assertIn("TEAMGROUP (旧称 Team) T-CREATE EXPERT DDR5 6000MHz 32GB (16GBx2枚) CL38 PC5-48000 デスクトップ用 メモリ ホワイト Intel XMP3.0 / AMD EXPO 両対応", parts_by_id["memory-teamgroup-ddr5-6000"]["aliases"])
        self.assertIn("CTCWD532G6000HC38ADC01", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["identity_terms"])
        self.assertEqual(len(parts_by_id["case-fractal-pop-air-tg"]["direct_retailer_urls"]), 2)
        self.assertIn("dospara.co.jp", parts_by_id["case-fractal-pop-air-tg"]["direct_retailer_urls"][1])

    def test_readme_copilot_instructions_and_peripheral_guide_match_current_plan(self):
        readme = read_text("README.md")
        instructions = read_text(".github/copilot-instructions.md")
        peripherals = read_text("docs/peripheral-rankings.md")

        for text in (readme, instructions, peripherals):
            with self.subTest(document="budget and speaker", text_length=len(text)):
                self.assertRegex(text, r"(?:¥\s?400,000|400,000円)")
                self.assertRegex(text, r"(?:¥\s?69,800|69,800円)")
                self.assertIn("EDIFIER MR4 MKII", text)

        self.assertIn("AOC Q27G40E/11", instructions)
        self.assertIn("LG 24MS500-B", instructions)
        self.assertIn("2026-11-01", instructions)
        self.assertIn("2026-12-11", instructions)
        self.assertIn("self-built DIY PC", instructions)
        self.assertNotIn("Total budget: JPY 370,000", instructions)
        self.assertNotIn("One monitor only; no secondary monitor", instructions)
        self.assertNotIn("Creative Pebble X at JPY 10,000", instructions)
        self.assertIn("2026-11-01 00:00 JST", peripherals)
        self.assertIn("2026-12-11 23:59 JST", peripherals)
        self.assertIn("公式開催日程", peripherals)

        # Explicit alternative-build totals and compatibility descriptions must
        # stay aligned with the authoritative component target configuration.
        self.assertIn("PC本体280,600円、周辺機器込み350,400円", readme)
        self.assertIn("PC本体324,800円、周辺機器込み394,600円", readme)
        self.assertNotIn("PC本体295,360円", readme)
        self.assertNotIn("PC本体329,360円", readme)
        guide = read_text("docs/self-build-assembly-guide.md")
        self.assertIn("| VRAM重視 | RTX 5060 Ti 16GB | ¥280,600 | ¥350,400 |", guide)
        self.assertIn("| 大穴 | RTX 5070 Ti 16GB | ¥324,800 | ¥394,600 |", guide)
        self.assertNotIn("正確なカード寸法・補助電源の確認が未完了", guide)
        self.assertNotIn("¥295,360", guide)
        self.assertNotIn("¥365,160", guide)
        self.assertNotIn("¥329,360", guide)
        self.assertNotIn("¥399,160", guide)

    def test_monitor_workflow_has_one_cadence_switch_and_fast_workflow_is_manual(self):
        regular = read_text(".github/workflows/pc-price-monitor.yml")
        fast = read_text(".github/workflows/pc-price-monitor-bf-fast.yml")
        self.assertIn('cron: "*/5 * * * *"', regular)
        self.assertIn('cron: "*/15 * * * *"', regular)
        self.assertIn(
            'expected_cron = "*/5 * * * *" if in_watch_window else "*/15 * * * *"',
            regular,
        )
        self.assertIn("workflow_dispatch:", fast)
        self.assertIsNone(re.search(r"(?m)^\s{2}schedule\s*:", fast))


if __name__ == "__main__":
    unittest.main()
