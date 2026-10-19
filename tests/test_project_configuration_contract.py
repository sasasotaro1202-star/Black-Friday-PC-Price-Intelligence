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

    def test_three_complete_budget_scenarios_include_350k_400k_450k(self):
        scenarios = self.targets.get("budget_scenarios") or []
        self.assertEqual(
            [(item["id"], item["total_budget_jpy"]) for item in scenarios],
            [("budget_350k", 350000), ("budget_400k", 400000), ("budget_450k", 450000)],
        )
        policy = self.targets.get("budget_scenario_policy") or {}
        self.assertTrue(policy.get("hard_ceiling_per_scenario"))
        self.assertTrue(policy.get("peripherals_included"))
        self.assertEqual(policy.get("unallocated_contingency_jpy"), 5000)
        excluded = policy.get("excluded", "")
        for item in ("Speakers", "secondary monitor", "headset", "power strip"):
            self.assertIn(item, excluded)
        self.assertIn("64GB RAM", " ".join(policy.get("upgrade_preference_order_if_complete_total_fits", [])))
        self.assertIn("2TB NVMe SSD", " ".join(policy.get("upgrade_preference_order_if_complete_total_fits", [])))


    @classmethod
    def setUpClass(cls):
        cls.targets = read_json("config/targets.json")
        cls.build = read_json("config/build_components.json")
        cls.profile = cls.build["profile"]

    def test_all_in_budget_and_primary_peripheral_targets_balance(self):
        targets = self.targets
        self.assertLessEqual(targets["pc_target_jpy"], targets["pc_budget_jpy"])
        self.assertEqual(targets["pc_budget_jpy"] + targets["unallocated_contingency_jpy"], targets["total_budget_jpy"])
        self.assertEqual(
            max(0, min(targets["pc_budget_jpy"], targets["total_budget_jpy"] - targets["peripheral_budget_jpy"] - targets["unallocated_contingency_jpy"])),
            360000,
        )
        self.assertEqual(targets["budget_jpy"], targets["pc_target_jpy"])
        mandatory_peripheral_target = sum(
            int(item["target_price_jpy"])
            for item in targets["peripherals"]
            if item.get("mandatory", True)
        )
        self.assertEqual(mandatory_peripheral_target, targets["peripheral_budget_jpy"])
        self.assertEqual(targets["total_budget_jpy"], 400000)
        self.assertEqual(targets["peripheral_budget_jpy"], 35000)
        self.assertEqual(targets["pc_target_jpy"], 360000)

    def test_cpu_core_alternatives_are_present_for_compile_and_analysis_workloads(self):
        profile = self.build["profile"]
        parts = {item["id"]: item for item in self.build["parts"]}
        self.assertEqual(profile["cpu_alternative_choice_ids"], ["cpu-ryzen9-9900x"])
        self.assertEqual(profile["cpu_dark_horse_ids"], ["cpu-ryzen9-9950x"])
        self.assertEqual(parts["cpu-ryzen9-9900x"]["specs"]["cores"], 12)
        self.assertEqual(parts["cpu-ryzen9-9900x"]["specs"]["threads"], 24)
        self.assertEqual(parts["cpu-ryzen9-9950x"]["specs"]["cores"], 16)
        self.assertTrue(parts["cpu-ryzen9-9900x"]["track_price"])
        self.assertTrue(parts["cpu-ryzen9-9950x"]["track_price"])
        self.assertIn("game_development", profile["workload_profile"])
        self.assertIn("cpu_comparison_policy", profile["workload_profile"]["game_development"])

    def test_peripheral_shipping_and_excluded_device_scope_are_consistent(self):
        scope = self.targets["budget_scope_note"]
        shipping = self.targets["peripheral_shipping_policy"]
        self.assertNotIn("周辺機器の送料は計上しない", scope)
        self.assertIn("オンライン配送", scope)
        self.assertIn("実店舗", scope)
        self.assertIn("最終支払額", scope)
        self.assertEqual(shipping["mode"], "CHANNEL_SPECIFIC")
        self.assertIn("never assume zero", shipping["online_delivery"])
        self.assertIn("Do not add delivery shipping", shipping["physical_store_cash"])
        self.assertIn("branch inventory", shipping["store_pickup"])
        self.assertIn("do not subtract points", shipping["points_and_rewards"].lower())

        primary = self.targets["peripherals"]
        self.assertEqual(sum(1 for item in primary if item.get("id") == "main_monitor"), 1)
        candidate_rows = primary + self.targets.get("peripheral_alternatives", [])
        candidate_identity_text = " ".join(
            str(item.get(key, ""))
            for item in candidate_rows
            for key in ("id", "category", "name", "best_for")
        ).lower()
        for excluded in ("speaker", "スピーカー", "sub_monitor", "sub-monitor", "サブモニター", "headset", "ヘッドセット"):
            self.assertNotIn(excluded.lower(), candidate_identity_text)

        # DIY is the primary purchase route; BTO remains a comparison benchmark only.
        self.assertEqual(self.profile["pc_build_method_preference"], "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION")
        self.assertEqual(self.profile["bto_role"], "REFERENCE_BENCHMARK_ONLY")

    def test_diy_profile_matches_budget_and_never_penalizes_assembly_time(self):
        profile = self.profile
        self.assertEqual(profile["total_budget_jpy"], self.targets["total_budget_jpy"])
        self.assertEqual(profile["peripheral_budget_jpy"], self.targets["peripheral_budget_jpy"])
        self.assertEqual(profile["pc_target_jpy"], self.targets["pc_target_jpy"])
        self.assertEqual(profile["pc_budget_jpy"], self.targets["pc_budget_jpy"])
        self.assertTrue(profile["budget_is_approximate"])
        self.assertEqual(profile["soft_overrun_allowance_jpy"], 20000)
        self.assertEqual(profile["soft_ceiling_total_jpy"], 420000)
        self.assertFalse(profile["budget_scenario_policy"]["hard_ceiling_per_scenario"])
        self.assertEqual(
            [(item["total_budget_jpy"], item["soft_ceiling_total_jpy"]) for item in profile["budget_scenarios"]],
            [(350000, 370000), (400000, 420000), (450000, 470000)],
        )
        self.assertEqual(profile["minimum_ram_gb"], 32)
        self.assertEqual(profile["minimum_ssd_gb"], 1000)
        board_specs = next(x for x in self.build["parts"] if x["id"] == "motherboard-asrock-b850m-pro-rs-wifi")["specs"]
        self.assertTrue(board_specs["cpu_support_list_verified_for_ryzen7_9700x"])
        self.assertEqual(board_specs["minimum_bios_for_ryzen7_9700x"], "3.12")
        self.assertIsNone(board_specs["observed_bios_version"])
        selected_memory = next(x for x in self.build["parts"] if x["id"] == profile["primary_memory_choice_id"])
        self.assertFalse(selected_memory["specs"]["qvl_verified_with_asrock_b850m_pro_rs_wifi"])
        self.assertEqual(selected_memory["specs"]["qvl_verification_status"], "UNCONFIRMED")
        self.assertEqual(profile["assembly_time_is_constraint"], False)
        self.assertEqual(profile["assembly_time_penalty_points"], 0)
        self.assertEqual(
            profile["pc_build_method_preference"],
            "SELF_BUILD_REQUIRED_FOR_PRIMARY_RECOMMENDATION",
        )
        self.assertEqual(profile["bto_role"], "REFERENCE_BENCHMARK_ONLY")
        self.assertIn("shopping.yahoo.co.jp", profile["allowed_search_reference_domains"])

    def test_user_workload_profile_covers_games_creation_study_and_analysis(self):
        targets_profile = self.targets["user_workload_profile"]
        build_workloads = self.profile["workload_profile"]
        target_ids = {item["id"] for item in targets_profile["priorities"]}
        self.assertTrue({
            "gaming",
            "game_development",
            "ai_data_analysis",
            "study_research_multitasking",
            "data_analysis_automation_ai",
        }.issubset(target_ids))

        game_dev = build_workloads["game_development"]
        self.assertTrue(game_dev["engine_agnostic"])
        self.assertEqual(set(game_dev["target_engines"]), {"Unreal Engine 5", "Unity", "Godot"})
        self.assertEqual(game_dev["baseline_requirements"]["system_ram_gb"], 32)
        self.assertEqual(game_dev["baseline_requirements"]["dedicated_gpu_vram_gb"], 8)
        self.assertEqual(game_dev["baseline_requirements"]["primary_ssd_gb"], 1000)
        self.assertEqual(game_dev["preferred_cpu_cores_for_unreal_source_build"], 12)
        self.assertIn("large datasets and simulations", build_workloads["analysis_and_automation"]["targets"])
        self.assertIn("school/study work", build_workloads["study_and_research"]["targets"])

        for relative_path in (
            "README.md",
            "docs/chatgpt-on-demand-analysis.md",
            ".github/copilot-instructions.md",
        ):
            text = read_text(relative_path)
            self.assertIn("勉強", text, relative_path)
            self.assertTrue("データ分析" in text or "Python" in text, relative_path)
            self.assertTrue("ゲーム制作" in text or "ゲームを作る" in text, relative_path)

    def test_optional_memory_and_storage_scenarios_follow_current_targets(self):
        parts = {item["id"]: item for item in self.build["parts"]}
        profile = self.profile

        def pc_target(gpu_id, memory_id, storage_id):
            selected = (
                list(profile["fixed_part_ids"])
                + [gpu_id, memory_id, storage_id, profile["primary_cooler_choice_id"]]
            )
            subtotal = sum(int(parts[item_id]["target_price_jpy"]) for item_id in selected)
            return subtotal + profile["build_shipping_reserve_jpy"] + profile["small_parts_reserve_jpy"]

        def all_in(pc):
            return pc + profile["peripheral_budget_jpy"] + profile["unallocated_contingency_jpy"]

        storage = profile["storage_upgrade_policy"]
        storage_base = int(parts[storage["baseline_item_id"]]["target_price_jpy"])
        storage_2tb = int(parts[storage["optional_item_id"]]["target_price_jpy"])
        self.assertEqual(storage["baseline_target_jpy"], storage_base)
        self.assertEqual(storage["budget_target_jpy"] - storage_base, storage["incremental_budget_target_jpy"])
        storage_scenario = storage["full_system_scenario"]
        expected_storage_base_pc = pc_target(
            storage_scenario["gpu_id"], profile["primary_memory_choice_id"], storage["baseline_item_id"]
        )
        expected_storage_pc = expected_storage_base_pc + storage_2tb - storage_base
        self.assertEqual(storage_scenario["base_pc_target_jpy"], expected_storage_base_pc)
        self.assertEqual(storage_scenario["pc_target_with_2tb_ssd_jpy"], expected_storage_pc)
        self.assertEqual(storage_scenario["all_in_target_jpy"], all_in(expected_storage_pc))
        self.assertEqual(
            storage_scenario["remaining_to_hard_ceiling_jpy"],
            profile["total_budget_jpy"] - all_in(expected_storage_pc),
        )
        self.assertGreater(storage_scenario["all_in_target_jpy"], profile["total_budget_jpy"])

        memory = profile["memory_upgrade_policy"]
        memory_scenario = memory["full_system_scenario"]
        base_memory = int(parts[memory["baseline_part_id"]]["target_price_jpy"])
        memory64 = int(parts[memory["conditional_replacement_id"]]["target_price_jpy"])
        self.assertEqual(memory_scenario["base_memory_target_jpy"], base_memory)
        self.assertEqual(memory_scenario["memory64_target_jpy"], memory64)
        expected_memory_base_pc = pc_target(
            memory_scenario["gpu_id"], memory["baseline_part_id"], profile["primary_storage_choice_id"]
        )
        expected_memory_pc = expected_memory_base_pc + memory64 - base_memory
        self.assertEqual(memory_scenario["base_pc_target_jpy"], expected_memory_base_pc)
        self.assertEqual(memory_scenario["pc_target_with_64gb_jpy"], expected_memory_pc)
        self.assertEqual(memory_scenario["all_in_target_jpy"], all_in(expected_memory_pc))
        self.assertEqual(
            memory_scenario["remaining_to_hard_ceiling_jpy"],
            profile["total_budget_jpy"] - all_in(expected_memory_pc),
        )
        self.assertGreater(memory_scenario["all_in_target_jpy"], profile["total_budget_jpy"])

    def test_primary_build_subtotal_counts_one_gpu_only(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        selected_ids = list(self.profile["fixed_part_ids"]) + [
            self.profile["primary_memory_choice_id"],
            self.profile["primary_storage_choice_id"],
            self.profile["primary_cooler_choice_id"],
            self.profile["primary_gpu_choice_id"],
        ]
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertTrue(all(part_id in parts_by_id for part_id in selected_ids))
        selected_categories = [parts_by_id[part_id]["category"] for part_id in selected_ids]
        self.assertEqual(selected_categories.count("gpu"), 1)
        self.assertEqual(set(selected_categories), set(self.profile["required_categories"]))
        components_subtotal = sum(
            int(parts_by_id[part_id]["target_price_jpy"]) for part_id in selected_ids
        )
        pc_total = (
            components_subtotal
            + int(self.profile["build_shipping_reserve_jpy"])
            + int(self.profile["small_parts_reserve_jpy"])
        )
        all_in_target = (
            pc_total
            + int(self.profile["peripheral_budget_jpy"])
            + int(self.profile["unallocated_contingency_jpy"])
        )
        self.assertEqual(pc_total, components_subtotal + 9000)
        self.assertLessEqual(pc_total, int(self.profile["pc_budget_jpy"]))
        self.assertLessEqual(all_in_target, int(self.profile["total_budget_jpy"]))

    def test_windows_retail_package_is_live_tracked_and_exact_model_identified(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        os = parts_by_id["os-windows11-home"]
        self.assertTrue(os["track_price"])
        self.assertEqual(os["model_code"], "HAJ-00094")
        self.assertIsInstance(os["target_price_jpy"], int)
        self.assertGreater(os["target_price_jpy"], 0)
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
        self.assertEqual(len(parts_by_id["motherboard-asrock-b850m-pro-rs-wifi"]["direct_retailer_urls"]), 3)
        self.assertIn("pc4u.co.jp", parts_by_id["motherboard-asrock-b850m-pro-rs-wifi"]["direct_retailer_urls"][1])
        self.assertIn("sofmap.com/product_detail.aspx?sku=101393495", parts_by_id["motherboard-asrock-b850m-pro-rs-wifi"]["direct_retailer_urls"][2])
        self.assertIn("pc4u.co.jp", self.profile["allowed_search_reference_domains"])
        self.assertIn("sofmap.com", self.profile["allowed_search_reference_domains"])
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
        self.assertIn("TEAMGROUP (旧称 Team) T-CREATE EXPERT DDR5 6000MHz 32GB (16GBx2枚) CL38 PC5-48000 デスクトップ用 メモリ ホワイト Intel XMP3.0 / AMD EXPO 両対応", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["aliases"])
        self.assertIn("CTCWD532G6000HC38ADC01", parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["identity_terms"])
        primary_memory = parts_by_id["memory-crucial-pro-ddr5-32gb-6000"]
        self.assertEqual(primary_memory["model_code"], "CP2K16G60C36U5W")
        self.assertEqual(primary_memory["target_price_jpy"], 60000)
        self.assertEqual(primary_memory["specs"]["capacity_gb"], 32)
        self.assertEqual(primary_memory["specs"]["modules"], 2)
        self.assertEqual(primary_memory["specs"]["speed_mts"], 6000)
        self.assertEqual(primary_memory["monitor_url"], "https://kakaku.com/item/K0001633533/")
        self.assertEqual(
            primary_memory["direct_retailer_urls"],
            [
                "https://shop.tsukumo.co.jp/goods/0649528943019/",
                "https://www.dospara.co.jp/SBR1534/IC512079.html",
                "https://www.pc4u.co.jp/view/item/000000090356?category_page_id=ct824",
                "https://www.yodobashi.com/product/100000001009315413/",
            ],
        )
        for retailer_url in primary_memory["direct_retailer_urls"]:
            self.assertTrue(retailer_url.startswith("https://"))

        self.assertEqual(
            self.profile["primary_memory_choice_id"],
            "memory-teamgroup-ddr5-32gb-6000",
        )
        self.assertEqual(
            set(self.profile["memory_choice_ids"]),
            {"memory-crucial-pro-ddr5-32gb-6000", "memory-teamgroup-ddr5-32gb-6000", "memory-lexar-thor-ddr5-64gb-6000", "memory-corsair-vengeance-ddr5-32gb-6000"},
        )
        self.assertNotIn("memory-crucial-pro-ddr5-32gb-6000", self.profile["fixed_part_ids"])
        self.assertNotIn("memory-teamgroup-ddr5-32gb-6000", self.profile["fixed_part_ids"])
        self.assertEqual(
            parts_by_id["memory-teamgroup-ddr5-32gb-6000"]["role"],
            "primary_budget_fit",
        )
        self.assertEqual(
            parts_by_id["memory-crucial-pro-ddr5-32gb-6000"]["role"],
            "price_monitored_alternative",
        )
        self.assertEqual(len(parts_by_id["case-fractal-pop-air-tg"]["direct_retailer_urls"]), 2)
        self.assertIn("dospara.co.jp", parts_by_id["case-fractal-pop-air-tg"]["direct_retailer_urls"][1])

    def test_copilot_bom_target_prices_match_machine_readable_source_of_truth(self):
        build = json.loads((ROOT / "config" / "build_components.json").read_text(encoding="utf-8"))
        instructions = read_text(".github/copilot-instructions.md")
        parts = {item["id"]: item for item in build["parts"]}
        self.assertIn(
            f"AMD Ryzen 7 9700X BOX — ¥{parts['cpu-ryzen7-9700x']['target_price_jpy']:,}.",
            instructions,
        )
        self.assertIn(
            f"Windows 11 Home Japanese retail package — ¥{parts['os-windows11-home']['target_price_jpy']:,}.",
            instructions,
        )
        self.assertEqual(
            sum(parts[item_id]["target_price_jpy"] for item_id in (
                "cpu-ryzen7-9700x", "gpu-rtx5070-12gb",
                "motherboard-asrock-b850m-pro-rs-wifi", "memory-teamgroup-ddr5-32gb-6000",
                "ssd-crucial-p3-plus-1tb", "psu-corsair-rm850e-2025",
                "case-fractal-pop-air-tg", "cooler-thermalright-pa120-se-v3",
                "os-windows11-home",
            )) + int(build["profile"]["build_shipping_reserve_jpy"]) + int(build["profile"]["small_parts_reserve_jpy"]),
            342000,
        )

    def test_report_budget_labels_distinguish_target_absolute_ceiling_and_dynamic_cap(self):
        source = read_text("scripts/report.py")
        self.assertIn("PC本体の基準目標", source)
        self.assertIn("PC本体の絶対上限", source)
        self.assertIn("PC本体の動的上限", source)
        self.assertNotIn("PC本体の計画上限（周辺機器が目標価格の場合）", source)
        self.assertIn("総額予備費を控除後", source)

    def test_excluded_peripherals_never_enter_purchase_or_monitoring_targets(self):
        targets = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        build = json.loads((ROOT / "config" / "build_components.json").read_text(encoding="utf-8"))
        peripheral_snapshot = json.loads((ROOT / "data" / "peripheral_prices.json").read_text(encoding="utf-8"))

        def product_identity(item):
            return " ".join(str(item.get(key) or "") for key in ("id", "name", "category", "product_type")).lower()

        forbidden = re.compile(
            r"speaker|headset|sub[-_ ]?monitor|secondary[-_ ]?monitor|second[-_ ]?monitor|"
            r"power[-_ ]?strip|スピーカー|ヘッドセット|サブモニター|サブモニタ|電源タップ|予備モニター",
            re.IGNORECASE,
        )
        purchase_surfaces = {
            "primary_peripherals": targets.get("peripherals") or [],
            "peripheral_alternatives": targets.get("peripheral_alternatives") or [],
            "pc_bom": build.get("parts") or [],
            "saved_peripheral_snapshot": peripheral_snapshot.get("products") or [],
        }
        for surface_name, items in purchase_surfaces.items():
            for item in items:
                with self.subTest(surface=surface_name, item_id=item.get("id")):
                    self.assertIsNone(
                        forbidden.search(product_identity(item)),
                        f"Excluded item entered {surface_name}: {product_identity(item)}",
                    )

        primary = targets["peripherals"]
        for category in ("main_monitor", "keyboard", "mouse", "mousepad"):
            with self.subTest(required_category=category):
                self.assertEqual(
                    sum(1 for item in primary if item.get("mandatory") and item.get("category") == category),
                    1,
                    f"Exactly one mandatory {category} belongs in the setup.",
                )
        main_monitor = next(item for item in primary if item.get("mandatory") and item.get("category") == "main_monitor")
        self.assertIn("27-inch", main_monitor.get("name", ""))
        self.assertIn("WQHD", main_monitor.get("name", ""))
        self.assertFalse(any(item.get("id") == "power-strip" for item in primary))

    def test_primary_ranked_products_have_explicit_image_sources_or_documented_absence(self):
        targets = json.loads((ROOT / "config" / "targets.json").read_text(encoding="utf-8"))
        build = json.loads((ROOT / "config" / "build_components.json").read_text(encoding="utf-8"))
        peripheral_by_id = {item["id"]: item for item in targets["peripherals"]}
        for item_id in ("main_monitor", "keyboard", "mouse", "mousepad"):
            item = peripheral_by_id[item_id]
            image_url = str(item.get("image_url") or "")
            image_source_url = str(item.get("image_source_url") or "")
            if image_url or image_source_url:
                self.assertTrue(image_url.startswith("https://"), item_id)
                self.assertTrue(image_source_url.startswith("https://"), item_id)
            else:
                # Do not reintroduce foreign retailer image sources simply to make
                # the UI look complete. An explicit "image unavailable" note is valid.
                self.assertIn("画像未確認", item.get("image_note", ""), item_id)
        build_by_id = {item["id"]: item for item in build["parts"]}
        for item_id in ("gpu-rtx5070-12gb", "gpu-rtx5060ti-16gb", "gpu-rtx5070ti-16gb",
                        "cpu-ryzen7-9700x", "motherboard-asrock-b850m-pro-rs-wifi",
                        "memory-teamgroup-ddr5-32gb-6000", "ssd-crucial-p3-plus-1tb",
                        "psu-corsair-rm850e-2025", "case-fractal-pop-air-tg",
                        "cooler-thermalright-pa120-se-v3", "os-windows11-home"):
            item = build_by_id[item_id]
            self.assertTrue(str(item.get("image_url", "")).startswith("https://"), item_id)
            self.assertTrue(str(item.get("image_source_url", "")).startswith("https://"), item_id)

    def test_readme_copilot_instructions_and_peripheral_guide_match_current_plan(self):
        readme = read_text("README.md")
        instructions = read_text(".github/copilot-instructions.md")
        peripherals = read_text("docs/peripheral-rankings.md")
        completion_gates = read_text("docs/PROJECT_COMPLETION_GATES_2026.md")

        for text in (readme, instructions, peripherals, completion_gates):
            with self.subTest(document="budget and route policy", text_length=len(text)):
                self.assertRegex(text, r"(?:¥\s?400,000|400,000円)")
                self.assertTrue("35,000円" in text or "35,000" in text or "35000" in text)
                self.assertTrue("ネット" in text or "online" in text.lower())
                self.assertFalse("Creative Pebble X at JPY 10,000" in text)

        self.assertIn("AOC Q27G40E/11", instructions)
        self.assertIn("No secondary monitor", instructions)
        self.assertIn("2026-11-01", instructions)
        self.assertIn("2026-12-11", instructions)
        self.assertIn("self-built DIY PC", instructions)
        self.assertNotIn("Total budget: JPY 370,000", instructions)
        self.assertIn("one main monitor only", instructions)
        self.assertNotIn("Creative Pebble X at JPY 10,000", instructions)
        self.assertIn("2026-11-01 00:00 JST", peripherals)
        self.assertIn("2026-12-11 23:59 JST", peripherals)
        self.assertIn("公式開催日程", peripherals)

        # The completion-gates document is a human-readable contract too: it
        # must stay aligned with the current target config and must not retain
        # the older accessory allocation or superseded build totals.
        self.assertIn("周辺機器の柔軟な計画配分：**35,000円**。", completion_gates)
        self.assertIn("| 本命：RTX 5070 12GB | 342,000円 | 382,000円 | 18,000円 |", completion_gates)
        self.assertIn("| VRAM重視：RTX 5060 Ti 16GB | 324,000円 | 364,000円 | 36,000円 |", completion_gates)
        self.assertIn("| 大穴：RTX 5070 Ti 16GB | 362,000円 | 402,000円 | -2,000円 |", completion_gates)
        self.assertIn("ネット配送では送料の実額を総額に反映", completion_gates)
        self.assertNotIn("周辺機器36,000円", completion_gates)
        self.assertNotIn("周辺機器の送料は計上しない", completion_gates)
        self.assertNotIn("300,600円", completion_gates)
        self.assertNotIn("280,600円", completion_gates)
        self.assertNotIn("324,800円", completion_gates)

        # Explicit alternative-build totals and compatibility descriptions must
        # stay aligned with the authoritative component target configuration.
        self.assertIn("| バランス本命 | Ryzen 7 9700X + RTX 5070 12GB | 341,500〜342,000円 | **381,500〜382,000円** |", readme)
        self.assertIn("| 性能重視の大穴 | Ryzen 7 9700X + RTX 5070 Ti 16GB | 361,500〜362,000円 | **401,500〜402,000円** |", readme)
        self.assertNotIn("PC本体295,360円", readme)
        self.assertNotIn("PC本体329,360円", readme)
        guide = read_text("docs/self-build-assembly-guide.md")
        self.assertIn("| VRAM重視 | RTX 5060 Ti 16GB＋TeamGroup 32GB | ¥324,000 | ¥364,000 |", guide)
        self.assertIn("| 大穴（ストレッチ） | RTX 5070 Ti 16GB＋TeamGroup 32GB | ¥362,000 | ¥402,000 |", guide)
        self.assertNotIn("正確なカード寸法・補助電源の確認が未完了", guide)
        self.assertNotIn("¥295,360", guide)
        self.assertNotIn("¥365,160", guide)
        self.assertNotIn("¥329,360", guide)
        self.assertNotIn("¥399,160", guide)

        # Human-facing target totals must be recalculated from the component config,
        # including OS, a single GPU, chosen RAM/SSD/cooler, shipping and contingency.
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        selected_common = list(self.profile["fixed_part_ids"]) + [
            self.profile["primary_memory_choice_id"],
            self.profile["primary_storage_choice_id"],
            self.profile["primary_cooler_choice_id"],
        ]
        gpu_rows = [
            ("gpu-rtx5070-12gb", "バランス本命", "本命"),
            ("gpu-rtx5060ti-16gb", "VRAM重視", "VRAM重視"),
            ("gpu-rtx5070ti-16gb", "性能重視の大穴", "大穴（ストレッチ）"),
        ]
        for gpu_id, readme_label, guide_label in gpu_rows:
            with self.subTest(gpu=gpu_id):
                subtotal = sum(int(parts_by_id[item]["target_price_jpy"]) for item in selected_common)
                subtotal += int(parts_by_id[gpu_id]["target_price_jpy"])
                pc_target = subtotal + int(self.profile["build_shipping_reserve_jpy"]) + int(self.profile["small_parts_reserve_jpy"])
                all_in_target = pc_target + int(self.profile["peripheral_budget_jpy"]) + int(self.profile["unallocated_contingency_jpy"])
                readme_row = next(line for line in readme.splitlines() if f"| {readme_label} |" in line)
                guide_row = next(line for line in guide.splitlines() if line.startswith(f"| {guide_label} |"))
                self.assertIn(f"{pc_target:,}円", readme_row)
                self.assertIn(f"{all_in_target:,}円", readme_row)
                self.assertIn(f"¥{pc_target:,}", guide_row)
                self.assertIn(f"¥{all_in_target:,}", guide_row)
                self.assertEqual(all_in_target > int(self.profile["total_budget_jpy"]), gpu_id == "gpu-rtx5070ti-16gb")

        memory_scenario = self.profile["memory_upgrade_policy"]["full_system_scenario"]
        self.assertEqual(memory_scenario["base_pc_target_jpy"], 324000)
        self.assertEqual(memory_scenario["base_memory_target_jpy"], 58000)
        self.assertEqual(memory_scenario["pc_target_with_64gb_jpy"], 366000)
        self.assertEqual(memory_scenario["all_in_target_jpy"], 406000)
        self.assertEqual(memory_scenario["remaining_to_hard_ceiling_jpy"], -6000)

        storage_policy = self.profile["storage_upgrade_policy"]
        self.assertEqual(storage_policy["baseline_target_jpy"], 24000)
        self.assertEqual(storage_policy["incremental_budget_target_jpy"], 21000)
        storage_scenario = storage_policy["full_system_scenario"]
        self.assertEqual(storage_scenario["base_pc_target_jpy"], 362000)
        self.assertEqual(storage_scenario["pc_target_with_2tb_ssd_jpy"], 383000)
        self.assertEqual(storage_scenario["all_in_target_jpy"], 423000)
        self.assertEqual(storage_scenario["remaining_to_hard_ceiling_jpy"], -23000)

    def test_github_is_collector_and_chatgpt_produces_final_on_demand_ranking(self):
        readme = read_text("README.md")
        instructions = read_text(".github/copilot-instructions.md")
        guide = read_text("docs/chatgpt-on-demand-analysis.md")
        for text in (readme, instructions, guide):
            self.assertRegex(text.lower(), r"chatgpt")
            self.assertRegex(text, r"(?i)(internal diagnostic|診断情報|中間的な診断)")
            self.assertRegex(text, r"(?i)(freshest|latest|最新)")
        self.assertIn("最終的なおすすめ順位", readme)
        self.assertIn("The final ranking is produced in ChatGPT only when the user asks.", instructions)
        self.assertIn("data/build_component_observations.jsonl", guide)
        self.assertIn("data/peripheral_change_events.jsonl", guide)
        self.assertIn("公式キャンペーン期間内の確認済み価格", guide)
        for required in (
            "ランキング依頼時の必須出力契約",
            "確認時刻（JST）",
            "RTX 5070 Ti 16GB",
            "電源タップ",
            "BF期間内の確認済み価格",
            "最終決済額",
            "候補としての比較を分けます",
            "画像",
        ):
            self.assertIn(required, guide)
        for path in (
            ".github/workflows/pc-price-monitor.yml",
            ".github/workflows/pc-price-monitor-bf-fast.yml",
        ):
            workflow = read_text(path)
            self.assertIn("Collect, preserve, quality-check and publish evidence", workflow)
            self.assertIn("internal indexes and quality diagnostics only", workflow)

    def test_monitor_workflow_has_one_cadence_switch_and_fast_workflow_is_manual(self):
        regular = read_text(".github/workflows/pc-price-monitor.yml")
        fast = read_text(".github/workflows/pc-price-monitor-bf-fast.yml")
        self.assertIn('cron: "3-59/5 * * * *"', regular)
        self.assertIn('cron: "7,22,37,52 * * * *"', regular)
        self.assertIn(
            'expected_cron = "3-59/5 * * * *" if in_watch_window else "7,22,37,52 * * * *"',
            regular,
        )
        self.assertIn("workflow_dispatch:", fast)
        self.assertIsNone(re.search(r"(?m)^\s{2}schedule\s*:", fast))


if __name__ == "__main__":
    unittest.main()
