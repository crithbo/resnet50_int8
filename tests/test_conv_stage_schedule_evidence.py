from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_stage_schedule_evidence import (
    build_conv_stage_schedule_evidence,
    validate_conv_stage_schedule_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "contracts/operator_config/node0004_conv_schedule_evidence_v1.json"
)


class ConvStageScheduleEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_conv_stage_schedule_evidence(ROOT)

    def test_wave0_scope_does_not_claim_full_conv(self) -> None:
        schedule = self.value["logical_schedule"]
        self.assertEqual(schedule["full_logical_tile_count"], 64)
        self.assertEqual(schedule["evidenced_tile_count"], 28)
        self.assertEqual(schedule["unevidenced_tile_count"], 36)
        self.assertFalse(schedule["full_three_wave_schedule_proven"])

    def test_asymmetric_ports_bias_and_psum_are_explicit(self) -> None:
        physical = self.value["physical_contract"]
        self.assertIn("signed int8 weights", physical["layout"]["A"])
        self.assertIn("unsigned uint8 activation", physical["layout"]["B"])
        self.assertIn("int32 bias", physical["layout"]["C"])
        self.assertIn("int32 partial sum", physical["layout"]["D"])
        self.assertEqual(
            physical["special_array"]["data_type"],
            "int8",
        )
        self.assertEqual(physical["special_array"]["bias_enable"], 1)
        self.assertEqual(
            set(physical["streams"]),
            {"A", "B", "C", "D"},
        )

    def test_invalid_server_attempt_keeps_emitter_blocked(self) -> None:
        gate = self.value["emission_gate"]
        self.assertFalse(gate["candidate_config_emission_allowed"])
        self.assertFalse(gate["reference_wave0_config_accepted_correct"])
        self.assertFalse(gate["positive_hardware_test_proven"])
        self.assertFalse(gate["numeric_hardware_test_proven"])
        self.assertIn("B_CONV_BIAS_PSUM", gate["effective_unresolved_blockers"])
        self.assertIn("B_CONV_INT8_SA", gate["effective_unresolved_blockers"])
        self.assertEqual(
            gate["authority_resolves_reference_template_semantics"], []
        )
        self.assertIn(
            "B_CONV_FULL_3WAVE_SCHEDULE",
            gate["additional_backend_blockers"],
        )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_conv_stage_schedule_evidence(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["logical_schedule"]["evidenced_tile_count"] = 64
        with self.assertRaises(ValueError):
            validate_conv_stage_schedule_evidence(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
