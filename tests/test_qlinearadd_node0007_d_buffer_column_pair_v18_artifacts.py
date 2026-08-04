from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_d_buffer_column_pair_v18 import validate


class QLinearAddNode0007DBufferColumnPairV18ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate(write_report=False)

    def test_local_candidate_chain_is_valid(self) -> None:
        self.assertTrue(self.report["local_candidate_valid"])
        self.assertEqual(self.report["errors"], [])
        self.assertTrue(
            self.report["checks"]["native_execplan_validation_pass"]
        )
        self.assertTrue(self.report["checks"]["native_double_run_equal"])

    def test_only_three_bitstreams_change_and_addresses_do_not(self) -> None:
        changed = {
            stage
            for stage, record in self.report["bitstream_records"].items()
            if record["changed"]
        }
        self.assertEqual(
            changed, {"op_relocation_pad", "op_tail_mul", "op_tail_round"}
        )
        self.assertTrue(
            self.report["checks"][
                "execplan_sca_addresses_occurrence_unchanged"
            ]
        )

    def test_current_rule_window_proof_and_negatives(self) -> None:
        match = self.report["current_rule_match"]
        self.assertFalse(match["active_blocker"])
        self.assertTrue(match["package_generation_allowed"])
        self.assertTrue(self.report["checks"]["current_rule_window_proof"])
        self.assertTrue(
            self.report["checks"][
                "buffer_ag_row_col_pair_consumer_equations_valid"
            ]
        )
        self.assertTrue(
            self.report["checks"][
                "all_required_negative_controls_fail_closed"
            ]
        )
        self.assertEqual(
            self.report["package_release"],
            "LOCAL_VALIDATED_READY_FOR_FRESH_PACKAGING",
        )


if __name__ == "__main__":
    unittest.main()
