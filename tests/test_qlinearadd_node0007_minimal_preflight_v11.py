from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_minimal_preflight_v11 import (
    validate_final_zip,
)


class QLinearAddNode0007MinimalPreflightV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_final_zip(write_report=False)

    def test_final_zip_current_rule_self_audit_passes(self) -> None:
        self.assertTrue(self.report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(self.report["errors"], [])

    def test_runtime_identity_has_one_manifest_source(self) -> None:
        receipt = self.report["manifest_single_source_identity"]
        self.assertTrue(receipt["passed"])
        self.assertTrue(receipt["runner_install_name_literal_absent"])
        self.assertEqual(receipt["manifest_value_binding_count"], 1)

    def test_real_runner_reaches_safe_compile_stub(self) -> None:
        receipt = self.report["runner_control_flow"][
            "safe_compile_stub_positive_control"
        ]
        self.assertTrue(receipt["passed"])
        self.assertTrue(receipt["compile_stub_reached"])
        self.assertTrue(receipt["actual_compile_argv_saved"])
        self.assertTrue(receipt["package_tree_unchanged"])

    def test_wrong_payload_identity_fails_before_compile(self) -> None:
        receipt = self.report["runner_control_flow"][
            "wrong_payload_identity_negative_control"
        ]
        self.assertTrue(receipt["passed"])
        self.assertFalse(receipt["compile_stub_reached"])


if __name__ == "__main__":
    unittest.main()
