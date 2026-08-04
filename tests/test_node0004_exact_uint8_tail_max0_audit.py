from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from resnet50_pipeline.node0004_exact_uint8_tail_max0_audit import (
    CONTRACT_PATH,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class Node0004ExactUint8TailMax0AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_all_hard_semantic_sources_match(self) -> None:
        self.assertTrue(self.report["source_identities_current_match"])
        self.assertGreaterEqual(self.report["source_identity_count"], 32)
        self.assertFalse(self.report["numeric_analysis_repeated"])
        self.assertTrue(self.report["conclusion_unchanged"])
        with patch(
            "resnet50_pipeline.node0004_exact_uint8_tail_max0_audit.np.load",
            side_effect=AssertionError("receipt validation must not load W3"),
        ):
            repeated = validate_contract(CONTRACT, ROOT)
        self.assertFalse(repeated["numeric_analysis_repeated"])

    def test_real_qparams_and_full_frozen_w3(self) -> None:
        self.assertEqual(
            self.report["multiplier_sha256"],
            "e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2",
        )
        self.assertEqual(self.report["y_zero_point"], 0)
        self.assertEqual(self.report["w3_element_count"], 3211264)
        self.assertEqual(self.report["w3_negative_count"], 1262480)
        self.assertEqual(self.report["w3_original_vs_max0_mismatch_count"], 0)
        self.assertEqual(self.report["w3_max0_vs_golden_mismatch_count"], 0)

    def test_no_raw_signed_int32_max_encoding(self) -> None:
        self.assertEqual(self.report["opcode_intersection"], [])
        self.assertEqual(
            self.report["first_unavoidable_capability"],
            "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE",
        )
        self.assertFalse(self.report["exact_path_exists"])

    def test_fail_closed_generation_boundary(self) -> None:
        self.assertFalse(self.report["tail_config_generated"])
        self.assertFalse(self.report["target_json_generated"])
        self.assertFalse(self.report["server_package_generated"])
        self.assertFalse(self.report["full_conv_assembled"])

    def test_no_package_release(self) -> None:
        self.assertEqual(self.report["package_release"], "NONE")


if __name__ == "__main__":
    unittest.main()
