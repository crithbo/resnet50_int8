from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.gap_d_index_schedule import (
    CONTRACT_PATH,
    GapDIndexScheduleError,
    build_gap_d_index_schedule_contract,
    d_index_release_decision,
    derive_gap_d_index_config,
    validate_gap_d_index_schedule_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class GapDIndexScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config, cls.request, cls.analysis = derive_gap_d_index_config(ROOT)
        cls.contract = build_gap_d_index_schedule_contract(ROOT)

    def test_exact_four_field_change_makes_lc2_an_independent_numeric_root(
        self,
    ) -> None:
        self.assertEqual(
            self.analysis["differences"],
            [
                {
                    "json_path": "$.dram_loop_configs.LC2.end",
                    "before": 1,
                    "after": 256,
                    "reason": "leaf_value_changed",
                },
                {
                    "json_path": "$.dram_loop_configs.LC2.last_index",
                    "before": 1,
                    "after": 0,
                    "reason": "leaf_value_changed",
                },
                {
                    "json_path": "$.dram_loop_configs.LC2.outmost_loop",
                    "before": 0,
                    "after": 1,
                    "reason": "leaf_value_changed",
                },
                {
                    "json_path": "$.dram_loop_configs.LC2.src_id",
                    "before": "DRAM_LC.LC0",
                    "after": None,
                    "reason": "leaf_value_changed",
                }
            ],
        )
        self.assertEqual(
            self.config["lc_pe_configs"]["PE1"]["inport0"]["src_id"],
            "DRAM_LC.LC2",
        )
        self.assertEqual(
            self.config["dram_loop_configs"]["LC2"]["end"],
            256,
        )
        self.assertEqual(
            self.config["dram_loop_configs"]["LC2"]["outmost_loop"], 1
        )
        self.assertIsNone(
            self.config["dram_loop_configs"]["LC2"]["src_id"]
        )
        self.assertEqual(
            self.config["dram_loop_configs"]["LC2"]["last_index"], 0
        )

    def test_exact_typed_output_coverage_is_256_contiguous_transactions(
        self,
    ) -> None:
        coverage = self.analysis["coverage"]
        self.assertEqual(coverage["classification"], "RTL_PROVEN")
        self.assertEqual(coverage["required_distinct_transaction_bases"], 256)
        self.assertEqual(coverage["derived_distinct_transaction_bases"], 256)
        self.assertEqual(coverage["transaction_bytes"], 32)
        self.assertEqual(
            self.analysis["all_output_biases_bytes"],
            list(range(0, 8192, 32)),
        )

    def test_tag_terminal_and_release_boundary_are_explicit(self) -> None:
        chain = self.contract["trigger_and_tag_chain"]
        self.assertEqual(chain["last_index"], 0)
        self.assertIn(
            0, chain["completion"]["possible_last_indices"]
        )
        self.assertEqual(chain["completion"]["write_target"], "D")
        self.assertEqual(
            self.contract["release"]["resolved_blocker"],
            "B_GAP_D_INDEX_CARRIER_SEMANTICS",
        )
        self.assertFalse(
            self.contract["release"]["candidate_json_allowed"]
        )
        self.assertIn(
            "B_GAP_GA_ACCUM_STATE",
            self.contract["release"]["remaining_blockers"],
        )
        self.assertFalse(
            self.contract["release"]["server_d_index_gate"][
                "release_allowed"
            ]
        )

    def test_d_index_release_requires_full_per_slice_coverage_and_golden(
        self,
    ) -> None:
        failed = d_index_release_decision(
            slice_count=16,
            expected_lines_per_slice=512,
            unique_lines_per_slice=[2] * 16,
            golden_pass_per_slice=[False] * 16,
        )
        self.assertFalse(failed["release_allowed"])
        self.assertFalse(failed["request_count_alone_is_sufficient"])
        passed = d_index_release_decision(
            slice_count=16,
            expected_lines_per_slice=512,
            unique_lines_per_slice=[512] * 16,
            golden_pass_per_slice=[True] * 16,
        )
        self.assertTrue(passed["release_allowed"])

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
        validate_gap_d_index_schedule_contract(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["numeric_carrier"]["distinct_bias_count"] = 255
        with self.assertRaises(GapDIndexScheduleError):
            validate_gap_d_index_schedule_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
