from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.gap_ga_accumulator_state import (
    CONTRACT_PATH,
    GapGaAccumulatorStateError,
    build_gap_ga_accumulator_state_contract,
    feedback_operand_is_legal,
    int32_noncalculate_operand_decision,
    outbuffer_occupancy_transition,
    validate_gap_ga_accumulator_state_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class GapGaAccumulatorStateTests(unittest.TestCase):
    def test_invalid_noncalculate_slot_is_reused_without_valid_guard(self) -> None:
        decision = int32_noncalculate_operand_decision(
            matched=True,
            transout_initial=3,
            calculate=False,
            outbuffer_valid=False,
            outbuffer_data=0x12AB3,
        )
        self.assertEqual(decision["input_c"], 0x12AB3)
        self.assertEqual(
            decision["input_c_source"],
            "outbuffer_data_without_valid_guard",
        )
        self.assertTrue(decision["invalid_slot_reused_as_c"])

    def test_calculate_path_has_guard_but_noncalculate_path_does_not(self) -> None:
        calculate = int32_noncalculate_operand_decision(
            matched=True,
            transout_initial=3,
            calculate=True,
            outbuffer_valid=False,
            outbuffer_data=0x12AB3,
        )
        first = int32_noncalculate_operand_decision(
            matched=True,
            transout_initial=0,
            calculate=False,
            outbuffer_valid=False,
            outbuffer_data=0x12AB3,
        )
        self.assertEqual(calculate["input_c"], 0)
        self.assertEqual(first["input_c"], 0)
        self.assertFalse(calculate["invalid_slot_reused_as_c"])
        self.assertFalse(first["invalid_slot_reused_as_c"])

    def test_v7_occupancy_underflow_and_feedback_rules_fail_closed(self) -> None:
        transition = outbuffer_occupancy_transition(
            before_count=1,
            after_count=3,
            depth=2,
            removed_valid_count=2,
            accepted_write_count=0,
        )
        self.assertFalse(transition["valid"])
        self.assertIn("remove_exceeds_occupancy", transition["violations"])
        self.assertIn("after_count_out_of_range", transition["violations"])
        self.assertFalse(
            feedback_operand_is_legal(
                outbuffer_valid=False,
                new_partial_valid=False,
                input_c=0xA6,
            )
        )
        self.assertTrue(
            feedback_operand_is_legal(
                outbuffer_valid=False,
                new_partial_valid=False,
                input_c=0,
            )
        )

    def test_contract_accepts_v7_dynamic_root_cause(self) -> None:
        contract = build_gap_ga_accumulator_state_contract(ROOT)
        self.assertEqual(
            contract["state_transition_counterexample"]["classification"],
            "CONTRADICTED",
        )
        self.assertFalse(contract["release"]["blocker_resolved"])
        self.assertFalse(contract["release"]["functional_rtl_modified"])
        self.assertEqual(
            contract["server_test"]["status"],
            "generated_frozen_server_return_accepted",
        )
        self.assertEqual(
            contract["server_return"]["classification"],
            "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse",
        )
        self.assertEqual(
            contract["server_return"]["ga"]["underflow_transition_count"], 8
        )
        self.assertEqual(
            contract["server_return"]["ga"]["invalid_slot_c_reuse_count"], 217
        )
        self.assertFalse(
            contract["server_return"]["independent_config_failure"][
                "passed_slice_count"
            ]
        )
        self.assertFalse(
            contract["server_test"]["functional_rtl_included"]
        )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
        validate_gap_ga_accumulator_state_contract(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["release"]["blocker_resolved"] = True
        with self.assertRaises(GapGaAccumulatorStateError):
            validate_gap_ga_accumulator_state_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
