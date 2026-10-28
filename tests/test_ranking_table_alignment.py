import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("self_build_planner_alignment_test", SCRIPTS / "self_build_planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class RankingTableAlignmentTests(unittest.TestCase):
    def test_primary_build_ranking_table_columns_align(self):
        rendered = planner.section_from_plan({
            "pc_planned_budget_jpy": 360000,
            "pc_budget_jpy": 395000,
            "builds": [{
                "rank": 1,
                "name": "Balanced build",
                "scorecard": {
                    "overall_score": 80,
                    "purchase_evidence_completeness_score_out_of_100": 45,
                },
                "target_pc_total_jpy": 300000,
                "target_all_in_jpy": 340000,
                "target_remaining_budget_jpy": 60000,
                "compatibility_status": "REVIEW",
                "decision": "WAIT_FOR_COMPATIBILITY_REVIEW",
                "components": [
                    {"name": "CPU test", "purchase_url": "https://shop.example/cpu"},
                    {"name": "GPU test", "purchase_url": "https://shop.example/gpu"},
                ],
            }],
        })
        rows = rendered.splitlines()
        header_index = next(i for i, line in enumerate(rows) if line.startswith("|購入順位|自作構成|"))
        header_cells = rows[header_index].strip("|").split("|")
        separator_cells = rows[header_index + 1].strip("|").split("|")
        ranking_row = next(line for line in rows if line.startswith("|保留|Balanced build|"))
        self.assertEqual(len(header_cells), len(separator_cells))
        self.assertEqual(len(header_cells), len(ranking_row.strip("|").split("|")))
        self.assertIn("[CPU test](https://shop.example/cpu)", ranking_row)
        self.assertIn("[GPU test](https://shop.example/gpu)", ranking_row)


if __name__ == "__main__":
    unittest.main()
