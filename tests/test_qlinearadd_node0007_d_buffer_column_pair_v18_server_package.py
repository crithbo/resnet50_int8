from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_d_buffer_column_pair_v18_server_package import (
    validate_final_zip,
)


class QLinearAddNode0007DBufferColumnPairV18PackageTests(unittest.TestCase):
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

    def test_window_proof_and_current_receipts(self) -> None:
        self.assertTrue(all(self.report["current_rule_receipts"].values()))
        for record in self.report["d_buffer_window_proof"][
            "candidate_values"
        ].values():
            self.assertEqual(record["accepted_row_col_pairs"], [[0, 0], [0, 16]])
            self.assertEqual(record["window_union"], [[0, 16], [16, 32]])
            self.assertEqual(record["buf_end_row"], 0)

    def test_diagnostics_and_runner_positive_control(self) -> None:
        self.assertTrue(
            self.report["stage_scoped_canonical_parser"]["passed"]
        )
        self.assertTrue(
            self.report["checks"][
                "runner_preflight_to_compile_positive_control"
            ]
        )
        self.assertTrue(
            self.report["checks"][
                "diagnostic_feature_runtime_enable_end_to_end"
            ]
        )


if __name__ == "__main__":
    unittest.main()
