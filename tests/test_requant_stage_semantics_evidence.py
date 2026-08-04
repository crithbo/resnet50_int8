from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.requant_stage_semantics_evidence import (
    build_requant_stage_semantics_evidence,
    validate_requant_stage_semantics_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "contracts/operator_config/node0004_requant_semantics_evidence_v1.json"
)


class RequantStageSemanticsEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_requant_stage_semantics_evidence(ROOT)

    def test_formula_and_channel_placement_are_exact(self) -> None:
        formula = self.value["operator_formula"]
        placement = self.value["parameter_placement"]
        self.assertEqual(formula["multiplier_count"], 64)
        self.assertEqual(formula["output_zero_point"], 0)
        self.assertEqual(formula["subtract_magic_int32"], 0x4B400000)
        self.assertEqual(placement["shard_count"], 8)
        covered = [
            channel
            for group in placement["channel_groups"]
            for channel in group["channels"]
        ]
        self.assertEqual(covered, list(range(64)))

    def test_w3_local_numeric_replay_is_exact_but_not_hardware(self) -> None:
        replay = self.value["independent_local_numeric_replay"]
        gate = self.value["emission_gate"]
        self.assertEqual(replay["element_count"], 16 * 64 * 56 * 56)
        self.assertEqual(replay["mismatch_count"], 0)
        self.assertFalse(gate["candidate_config_emission_allowed"])
        self.assertTrue(
            gate["reference_template_configuration_correctness_authorized"]
        )
        self.assertFalse(gate["positive_hardware_test_proven"])
        self.assertFalse(gate["numeric_hardware_test_proven"])
        self.assertFalse(gate["legacy_ndp_sim_ref_outputs_used"])

    def test_ga_template_has_eight_mac_sub_lanes(self) -> None:
        ga = self.value["ga_template_topology"]
        self.assertEqual(ga["lane_count"], 8)
        self.assertEqual(ga["input_conversion"], "int32_to_fp32")
        self.assertEqual(ga["output_conversion"], "int32_to_uint8_saturating")

    def test_bit_accurate_rtl_replay_hits_minus_one_counterexample(self) -> None:
        replay = self.value["bit_accurate_rtl_replay"]
        domain = replay["accumulator_domain"]
        conversion = replay["int32_to_fp32"]
        verdict = replay["verdict"]
        self.assertEqual(domain["minus_one_count"], 128)
        self.assertEqual(domain["int_min_count"], 0)
        self.assertEqual(conversion["mismatch_values"], [-1])
        self.assertEqual(conversion["element_conversion_mismatch_count"], 128)
        self.assertEqual(
            replay["post_conversion_pipeline"]["final_uint8_mismatch_count"],
            0,
        )
        self.assertTrue(verdict["exact_input_hits_known_rtl_counterexample"])
        self.assertFalse(verdict["intermediate_conversion_equivalent"])
        self.assertFalse(verdict["rtl_semantics_compatible"])

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_requant_stage_semantics_evidence(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["independent_local_numeric_replay"]["mismatch_count"] = 1
        with self.assertRaises(ValueError):
            validate_requant_stage_semantics_evidence(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
