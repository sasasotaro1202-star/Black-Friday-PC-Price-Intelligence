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
        self.assertEqual(components_subtotal, 311360)
        self.assertEqual(pc_total, 320360)
        self.assertEqual(
            pc_total + int(self.profile["peripheral_budget_jpy"]),
            390160,
        )
        self.assertLessEqual(390160, int(self.profile["total_budget_jpy"]))

    def test_unknown_alternative_gpu_dimensions_remain_explicitly_unverified(self):
        parts_by_id = {item["id"]: item for item in self.build["parts"]}
        for part_id in ("gpu-rtx5060ti-16gb", "gpu-rtx5070ti-16gb"):
            specs = parts_by_id[part_id]["specs"]
            self.assertIsNone(specs.get("card_length_mm"), part_id)
            self.assertIsNone(specs.get("card_width_mm"), part_id)
            self.assertIsNone(specs.get("card_thickness_mm"), part_id)
        instructions = read_text(".github/copilot-instructions.md")
        self.assertIn("Do not inherit the RTX 5070's dimensions", instructions)
        self.assertIn("Unknown details mean REVIEW, not PASS", instructions)

    def test_readme_copilot_instructions_and_peripheral_guide_match_current_plan(self):
        readme = read_text("README.md")
        instructions = read_text(".github/copilot-instructions.md")
        peripherals = read_text("docs/peripheral-rankings.md")

        for text in (readme, instructions, peripherals):
            with self.subTest(document="budget and speaker", text_length=len(text)):
                self.assertRegex(text, r"(?:¥\\s?400,000|400,000円)")
                self.assertRegex(text, r"(?:¥\\s?69,800|69,800円)")
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
        self.assertIn("公式開催期間", peripherals)

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
