from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_gemm_numeric import (
    CONTRACT_PATH,
    DeepSeekGemmNumericError,
    build_gemm_numeric_contract,
    validate_gemm_numeric_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekGemmNumericTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )

    def test_contract_matches_nonempty_payload(self) -> None:
        rebuilt = build_gemm_numeric_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_gemm_numeric_contract(self.checked, ROOT)
        coverage = self.checked["coverage"]
        self.assertEqual(coverage["physical_file_count"], 84)
        self.assertEqual(coverage["nonempty_file_count"], 88)
        self.assertEqual(
            coverage["per_slice_bytes"],
            {"A": 2048, "B": 114688, "D": 4096},
        )

    def test_all_ring_partials_and_relayout_are_closed(self) -> None:
        result = self.checked["numeric_result"]
        self.assertEqual(result["max_ring_partial_error"], 0.0)
        self.assertTrue(
            result["all_28_K_chunks_covered_per_output_slice"]
        )
        self.assertTrue(
            result["physical_payload_matches_native_relayout"]
        )
        self.assertTrue(result["stored_fp32_accumulator_exact"])
        self.assertTrue(result["stored_fp16_output_exact"])

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
        tampered["numeric_result"]["max_ring_partial_error"] = 1.0
        with self.assertRaisesRegex(
            DeepSeekGemmNumericError,
            "differs from current payload",
        ):
            validate_gemm_numeric_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
