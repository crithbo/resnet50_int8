from __future__ import annotations

import unittest

from tools.analyze_qlinearadd_node0007_return import DEFAULT_RETURN, analyze


class QLinearAddNode0007ReturnAnalysisTest(unittest.TestCase):
    def test_return_is_bound_and_first_stage_lc_wrap_hang_is_proven(self) -> None:
        if not DEFAULT_RETURN.is_file():
            self.skipTest("user-provided return is not available")
        report = analyze(DEFAULT_RETURN)
        self.assertFalse(report["formal_receipt_valid"])
        self.assertTrue(
            report["source_package_binding"]["manifest_three_way_equal"]
        )
        self.assertTrue(report["return_integrity"]["crc_clean"])
        self.assertTrue(report["return_integrity"]["zip_exact_set"])
        self.assertTrue(report["return_integrity"]["allowlist_exact"])
        self.assertTrue(report["preflight"]["valid"])
        self.assertEqual(report["result_gate"]["compile_exit_status"], 0)
        self.assertEqual(report["result_gate"]["simulation_exit_status"], 124)
        self.assertTrue(report["result_gate"]["simulation_started"])
        self.assertTrue(report["result_gate"]["preload_count_exact"])
        self.assertTrue(report["result_gate"]["register_started"])
        self.assertTrue(report["result_gate"]["slice_started"])
        self.assertFalse(report["result_gate"]["natural_terminal"])
        self.assertEqual(report["result_gate"]["observed_readback_count"], 0)
        self.assertEqual(report["result_gate"]["missing_count"], 28)
        self.assertEqual(report["result_gate"]["mismatch_byte_count"], 0)
        self.assertFalse(report["result_gate"]["mismatch_is_evaluable"])
        self.assertFalse(
            report["result_gate"][
                "zero_mismatch_with_all_missing_is_numeric_pass"
            ]
        )
        self.assertEqual(
            report["first_divergence"]["execution"]["code"],
            "QADD_DRAM_LC_SIGNED_FEEDBACK_WRAP_HANG",
        )
        self.assertTrue(
            report["first_divergence"]["execution"][
                "package_side_fix_required"
            ]
        )
        self.assertEqual(
            report["deadlock_adjudication"]["status"],
            "HANG_PROVEN_PACKAGE_CONFIG",
        )
        proof = report["static_hang_proof"]
        self.assertEqual(proof["status"], "PROVEN_UNREACHABLE_LC_LAST")
        self.assertTrue(proof["rtl_semantics_bound"])
        self.assertEqual(proof["feedback_width_bits"], 16)
        self.assertEqual(proof["safe_positive_end_max"], 32_768)
        self.assertEqual(
            (
                proof["first_offender"]["stage_index"],
                proof["first_offender"]["operator_id"],
                proof["first_offender"]["loop"],
                proof["first_offender"]["end"],
            ),
            (0, "op_a_dequant", "LC1", 37_632),
        )
        self.assertEqual(proof["offender_count"], 7)
        self.assertFalse(
            proof["config_only_fix_geometry"]["materialized"]
        )
        self.assertFalse(report["package_release"]["run_ready"])
        self.assertEqual(
            report["package_release"]["status"],
            "QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX",
        )
        self.assertEqual(
            report["workload_scale"]["request_count_with_multiplicity"],
            37_352_448,
        )
        self.assertFalse(report["evidence_adjudication"]["E3"]["pass"])
        self.assertFalse(report["evidence_adjudication"]["E4"]["pass"])
        self.assertFalse(report["evidence_adjudication"]["E5"]["pass"])
        self.assertFalse(report["numeric_analysis"]["repeated"])


if __name__ == "__main__":
    unittest.main()
