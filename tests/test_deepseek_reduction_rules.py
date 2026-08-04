from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.deepseek_reduction_rules import (
    DeepSeekReductionRuleError,
    build_deepseek_reduction_rules,
    validate_deepseek_reduction_rules,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/deepseek_reduction_rules_v1.json"
)


class DeepSeekReductionRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_deepseek_reduction_rules(ROOT)

    def test_rmsnorm_proves_local_to_remote_stage_selection(self) -> None:
        dag = self.value["deepseek_reduction_stage_dag"]
        self.assertEqual(
            dag["stage_types"][:2],
            [
                "prefill_summac_fp32MN_fp32MN",
                "prefill_remote_sum_fp32MN_fp32MN",
            ],
        )
        self.assertEqual(dag["local_to_remote_dependency"], "op0->op1")

    def test_every_reference_reduction_has_terminal_zero(self) -> None:
        for item in self.value["reference_reduction_templates"].values():
            completion = item["strict_terminal_evidence"]["completion"]
            self.assertIn(0, completion["possible_last_indices"])
            self.assertEqual(completion["write_target"], "D")

    def test_gap_exact_schedule_needs_no_cross_slice_reduction(self) -> None:
        gap = self.value["gap_resolution"]
        schedule = gap["exact_schedule"]
        self.assertEqual(schedule["active_slice_count"], 16)
        self.assertEqual(schedule["wave_active_slice_counts"], [16])
        self.assertEqual(schedule["output_channels_covered_per_slice"], 2048)
        self.assertEqual(schedule["output_bytes_per_slice"], 8192)
        self.assertFalse(gap["cross_slice_classification"]["required"])

    def test_gap_zero_point_is_explicitly_consumed(self) -> None:
        binding = self.value["gap_resolution"][
            "typed_parameter_consumption"
        ]
        self.assertEqual(binding["parameter"], "x_zero_point")
        self.assertEqual(binding["value"], 0)
        self.assertEqual(binding["mode"], "compile_time_specialization")
        self.assertFalse(binding["runtime_parameter_transport_required"])
        self.assertEqual(
            self.value["gap_resolution"]["resolved_local_blockers"],
            [
                "B_EXECPLAN_TYPED_TRANSPORT",
                "B_SUM_COMPLETION",
                "B_SUM_CROSS_SLICE",
            ],
        )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_deepseek_reduction_rules(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["gap_resolution"]["exact_schedule"][
            "active_slice_count"
        ] = 15
        with self.assertRaises(DeepSeekReductionRuleError):
            validate_deepseek_reduction_rules(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
