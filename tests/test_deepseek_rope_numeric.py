from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_rope_numeric import (
    CONTRACT_PATH,
    DeepSeekRopeNumericError,
    build_rope_numeric_contract,
    validate_rope_numeric_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekRopeNumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )

    def test_contract_matches_complete_nonempty_payload(self) -> None:
        rebuilt = build_rope_numeric_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_rope_numeric_contract(self.checked, ROOT)
        coverage = self.checked["coverage"]
        self.assertEqual(coverage["logical_file_count"], 49)
        self.assertEqual(coverage["physical_file_count"], 252)
        self.assertEqual(coverage["nonempty_file_count"], 301)
        self.assertTrue(coverage["all_stage_inputs_outputs_covered"])
        self.assertTrue(
            coverage[
                "op0_op1_external_activation_payloads_bit_equal"
            ]
        )

    def test_canonical_pairing_sign_and_layout_are_unique(self) -> None:
        choice = self.checked["implementation_choice"]
        self.assertEqual(choice["name"], "CANONICAL_CROSS_SLICE_XOR2")
        self.assertFalse(choice["activation_pre_swapped"])
        self.assertEqual(choice["sin_sign_by_half"], [1, -1])
        self.assertFalse(choice["global_relayout_negation"])
        result = self.checked["numeric_result"]
        self.assertEqual(result["route_mismatch_count"], 0)
        self.assertTrue(result["logical_payload_matches_equation"])
        self.assertTrue(
            result[
                "physical_payload_matches_native_relayout_primitive"
            ]
        )

    def test_synthetic_payload_does_not_claim_model_or_hardware(self) -> None:
        boundary = self.checked["identity_boundary"]
        self.assertEqual(
            boundary["payload_kind"], "DETERMINISTIC_SYNTHETIC"
        )
        self.assertFalse(boundary["onnx_original_weight_payload"])
        self.assertFalse(boundary["hardware_readback"])
        self.assertFalse(self.checked["candidate_release"])

    def test_tamper_fails_closed(self) -> None:
        tampered = deepcopy(self.checked)
        tampered["numeric_result"]["route_mismatch_count"] = 1
        with self.assertRaisesRegex(
            DeepSeekRopeNumericError,
            "differs from current payload",
        ):
            validate_rope_numeric_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
