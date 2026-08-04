from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.node0004_exact_uint8_tail_fresh_c1 import (
    CONTRACT_PATH,
    FORBIDDEN_SOURCE_FRAGMENTS,
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class Node0004ExactUint8TailFreshC1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_fresh_source_policy_and_identities(self) -> None:
        self.assertEqual(self.report["source_identity_count"], 23)
        self.assertTrue(
            all(item["matched"] for item in self.report["source_identities"])
        )
        for item in self.report["source_identities"]:
            normalized = item["path"].replace("\\", "/").lower()
            self.assertFalse(
                any(
                    fragment.lower() in normalized
                    for fragment in FORBIDDEN_SOURCE_FRAGMENTS
                )
            )

    def test_real_qparam_identity_and_fresh_w3_replay(self) -> None:
        self.assertEqual(
            self.report["qparam_identity"]["multiplier_sha256"],
            "e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2",
        )
        self.assertEqual(self.report["qparam_identity"]["y_zero_point"], 0)
        self.assertEqual(self.report["formal_w3_mismatch_count"], 0)
        self.assertEqual(self.report["formal_w3_minus_one_count"], 128)

    def test_first_unavoidable_capability_is_signed_ingress(self) -> None:
        self.assertEqual(
            self.report["first_unavoidable_capability"],
            "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
        )
        self.assertFalse(
            self.report["pure_configuration_decision"]["exact_path_exists"]
        )
        self.assertEqual(
            self.report["typed_transport_status"], "PLACEHOLDER_BLOCKED"
        )

    def test_physical_and_c0_dependencies_remain_fail_closed(self) -> None:
        self.assertEqual(
            self.report["physical_layout_status"], "B_LAYOUT_APPROVAL"
        )
        self.assertEqual(self.report["c0_status"], "PENDING")
        self.assertFalse(self.report["target_json_generated"])
        self.assertFalse(self.report["full_conv_assembled"])

    def test_no_package_or_release(self) -> None:
        self.assertFalse(self.report["server_package_generated"])
        self.assertEqual(self.report["package_release"], "NONE")


if __name__ == "__main__":
    unittest.main()
