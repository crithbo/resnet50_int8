from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.node0075_negative_psum_reachability import (
    build_report,
    scan_arrays,
)


ROOT = Path(__file__).resolve().parents[1]


class Node0075NegativePsumReachabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_report(ROOT)

    def test_frozen_instance_hits_current_rtl_boundary(self) -> None:
        scan = self.report["exact_occurrence_scan"]
        self.assertEqual(scan["enumerated_occurrence_count"], 8_192_000)
        self.assertEqual(scan["boundary_hit_count"], 272)
        self.assertEqual(scan["negative_to_zero_count"], 272)
        self.assertEqual(scan["negative_to_int32_min_count"], 0)

    def test_first_witness_is_exact(self) -> None:
        first = self.report["exact_occurrence_scan"]["first_stream_order_hit"]
        self.assertEqual(
            (first["m"], first["n"], first["k_group"]), (0, 65, 3)
        )
        self.assertEqual(first["a_u8_lanes"], [28, 13, 1, 0])
        self.assertEqual(first["b_s8_lanes"], [1, -2, 17, -2])
        self.assertEqual(first["psum_in_s32"], -19)
        self.assertEqual(first["dot4_s32"], 19)
        self.assertEqual(first["current_split_rtl_result_bits"], "0x80000000")

    def test_formal_accumulator_is_the_scanned_recurrence(self) -> None:
        scan = self.report["exact_occurrence_scan"]
        self.assertTrue(scan["formal_final_accumulator_match"])
        self.assertEqual(scan["formal_final_accumulator_mismatch_count"], 0)
        self.assertEqual(scan["formal_final_zero_count"], 0)

    def test_synthetic_exact_cancellation_is_detected(self) -> None:
        activation = np.zeros((16, 2048), dtype=np.uint8)
        weight = np.zeros((2048, 1000), dtype=np.int8)
        activation[0, 0] = 19
        activation[0, 4] = 19
        weight[0, 0] = -1
        weight[4, 0] = 1
        scan = scan_arrays(activation, weight, group_chunk=16)
        self.assertEqual(scan["boundary_hit_count"], 1)
        self.assertEqual(scan["first_stream_order_hit"]["psum_in_s32"], -19)
        self.assertEqual(scan["first_stream_order_hit"]["dot4_s32"], 19)

    def test_terminal_gate_prevents_downstream_outputs(self) -> None:
        self.assertEqual(self.report["status"], "HARDWARE_CAPABILITY_BLOCKED")
        self.assertEqual(self.report["package_release"], "NONE")
        self.assertFalse(any(self.report["outputs"].values()))
        accounting = self.report["materializer_and_reload_accounting"]
        self.assertEqual(accounting["actual_materialized_reload_passes"], 0)
        self.assertEqual(
            accounting["actual_materialized_accepted_a_traffic_bytes"], 0
        )


if __name__ == "__main__":
    unittest.main()
