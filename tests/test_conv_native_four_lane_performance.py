from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.conv_native_four_lane_performance import (
    INT32_MIN,
    _scan_exact_pairs,
)


class ConvNativeFourLanePerformanceTest(unittest.TestCase):
    def test_negative_five_plus_five_is_reachable(self) -> None:
        report = _scan_exact_pairs(
            patches_u8=np.array([[1, 1, 1, 2]], dtype=np.uint8),
            packed_weight_s8=np.array([[1, 1, 1, 1]], dtype=np.int8),
            corrected_bias_s32=np.array([-5], dtype=np.int32),
            logical_k=4,
            output_shape=(1, 1, 1, 1),
        )
        self.assertEqual(report["counterexample_hit_counts"]["NEG5_PLUS5"], 1)
        self.assertEqual(
            report["first_hits"]["NEG5_PLUS5"]["result_s32"], 0
        )

    def test_int32_min_plus_zero_is_reachable(self) -> None:
        report = _scan_exact_pairs(
            patches_u8=np.zeros((1, 4), dtype=np.uint8),
            packed_weight_s8=np.zeros((1, 4), dtype=np.int8),
            corrected_bias_s32=np.array([INT32_MIN], dtype=np.int32),
            logical_k=4,
            output_shape=(1, 1, 1, 1),
        )
        self.assertEqual(
            report["counterexample_hit_counts"]["INT32_MIN_PLUS0"], 1
        )
        self.assertEqual(
            report["first_hits"]["INT32_MIN_PLUS0"]["result_s32"], INT32_MIN
        )

    def test_nonmatching_control_is_unreachable(self) -> None:
        report = _scan_exact_pairs(
            patches_u8=np.array([[1, 2, 3, 4]], dtype=np.uint8),
            packed_weight_s8=np.array([[1, -1, 1, -1]], dtype=np.int8),
            corrected_bias_s32=np.array([17], dtype=np.int32),
            logical_k=4,
            output_shape=(1, 1, 1, 1),
        )
        self.assertEqual(
            sum(report["counterexample_hit_counts"].values()), 0
        )
        self.assertTrue(report["complete_enumeration"])


if __name__ == "__main__":
    unittest.main()
