from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_softmax_numeric import (
    CONTRACT_PATH,
    DeepSeekSoftmaxNumericError,
    build_softmax_numeric_contract,
    validate_softmax_numeric_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekSoftmaxNumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )

    def test_contract_matches_nonempty_payload(self) -> None:
        rebuilt = build_softmax_numeric_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_softmax_numeric_contract(self.checked, ROOT)
        coverage = self.checked["coverage"]
        self.assertEqual(coverage["physical_file_count"], 196)
        self.assertEqual(coverage["nonempty_file_count"], 245)
        self.assertTrue(
            coverage["all_four_slice_replicas_bit_equal"]
        )

    def test_probability_and_layout_invariants_are_closed(self) -> None:
        result = self.checked["numeric_result"]
        self.assertLessEqual(
            result["max_fp16_row_sum_error"], 5.0e-4
        )
        self.assertEqual(result["max_masked_probability"], 0.0)
        self.assertTrue(
            result["logical_payload_matches_independent_formula"]
        )
        self.assertTrue(
            result["physical_payload_matches_native_relayout"]
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
        tampered["numeric_result"]["max_masked_probability"] = 1.0
        with self.assertRaisesRegex(
            DeepSeekSoftmaxNumericError,
            "differs from current payload",
        ):
            validate_softmax_numeric_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
