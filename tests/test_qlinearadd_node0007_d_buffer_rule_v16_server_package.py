from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_d_buffer_rule_v16_server_package import (
    NEW_RULE_ID,
    validate_final_zip,
)


class TestQLinearAddNode0007DBufferRuleV16ServerPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_final_zip(write_report=False)

    def test_final_zip_current_rule_self_audit(self) -> None:
        self.assertTrue(self.report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(self.report["errors"], [])
        self.assertEqual(self.report["error_count"], 0)
        self.assertTrue(
            self.report["all_required_negative_controls_fail_closed"]
        )

    def test_current_qadd_rule_and_payload_freeze(self) -> None:
        receipt = self.report["current_qlinearadd_rule_receipt"]
        self.assertEqual(receipt["rule_id"], NEW_RULE_ID)
        self.assertTrue(receipt["current_match"])
        self.assertFalse(
            self.report["content_neutral_external_receipt_allowed"]
        )
        self.assertTrue(
            self.report["functional_payload_equivalence"]["valid"]
        )

    def test_supply_equation_and_negative_controls(self) -> None:
        self.assertTrue(self.report["final_json_supply_proof"]["valid"])
        self.assertTrue(
            self.report[
                "final_bitstream_decode_and_rtl_consumer_equation"
            ]["valid"]
        )
        self.assertTrue(
            all(
                item["failed_closed"]
                for item in self.report[
                    "new_rule_negative_controls"
                ].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
