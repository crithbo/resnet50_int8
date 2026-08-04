from __future__ import annotations

import unittest

from tools import (
    validate_qlinearadd_node0007_d_buffer_supply_v15_server_package
    as validator,
)


class QLinearAddNode0007DBufferSupplyV15PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validator.validate_final_zip(write_report=False)

    def test_final_zip_self_audit_passes(self) -> None:
        self.assertTrue(self.report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(self.report["errors"], [])
        self.assertTrue(
            self.report["all_required_negative_controls_fail_closed"]
        )

    def test_supply_and_native_chain_are_bound(self) -> None:
        self.assertTrue(self.report["d_buffer_supply_proof"]["valid"])
        self.assertTrue(self.report["fresh_native_chain"]["valid"])
        self.assertTrue(
            self.report["checks"]["manifest_driven_preload_result_gate"]
        )

    def test_runner_and_runtime_feature_controls_pass(self) -> None:
        controls = self.report["runner_control_flow"]
        self.assertTrue(controls["safe_compile_stub_positive_control"]["passed"])
        self.assertTrue(
            controls["wrong_payload_identity_negative_control"]["passed"]
        )
        feature = self.report[
            "diagnostic_feature_runtime_enable_end_to_end"
        ]
        self.assertTrue(feature["passed"])
        self.assertTrue(
            all(
                item["failed_closed"]
                for item in feature["four_negative_controls"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
