from __future__ import annotations

import itertools
import unittest
from pathlib import Path

from resnet50_pipeline.int8_sa_dot_product_adjudication import (
    build_int8_sa_dot_product_adjudication,
    conventional_dot,
    stock_rtl_sa_chunk,
    stock_rtl_sa_dot,
)


class Int8SaDotProductAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.report = build_int8_sa_dot_product_adjudication(cls.root)

    def test_first_divergence_is_duplicate_carry_shift(self) -> None:
        witness = stock_rtl_sa_chunk([1, 1, 1, 1], [1, 1, 1, 1])
        self.assertEqual(witness["sum17"], 2)
        self.assertEqual(witness["carry17"], 2)
        self.assertEqual(witness["sum17"] + witness["carry17"], 4)
        self.assertEqual(witness["result"], 6)

    def test_one_product_serialization_is_exact_on_small_exhaustive_domain(self) -> None:
        weight_values = (-3, 0, 3)
        activation_values = (0, 1, 7)
        for length in (1, 2, 3, 4):
            for weights in itertools.product(weight_values, repeat=length):
                for activations in itertools.product(activation_values, repeat=length):
                    expected = conventional_dot(weights, activations, bias=-11)
                    actual = stock_rtl_sa_dot(
                        weights,
                        activations,
                        bias=-11,
                        serialize_one_product_per_occurrence=True,
                    )
                    self.assertEqual(actual, expected)
        expected = conventional_dot([3, -1, 0, -3, 1], [7, 2, 1, 3, 5], bias=-11)
        actual = stock_rtl_sa_dot(
            [3, -1, 0, -3, 1],
            [7, 2, 1, 3, 5],
            bias=-11,
            serialize_one_product_per_occurrence=True,
        )
        self.assertEqual(actual, expected)

    def test_nonzero_zero_point_static_correction_is_exact_when_serialized(self) -> None:
        for weights in ([1], [-3, 2, 1], [127, -128, 3, -4, 5]):
            activations = [5 + index for index in range(len(weights))]
            expected = conventional_dot(weights, activations, x_zero_point=5, bias=17)
            actual = stock_rtl_sa_dot(
                weights,
                activations,
                x_zero_point=5,
                bias=17,
                apply_static_xzp_bias_correction=True,
                serialize_one_product_per_occurrence=True,
            )
            self.assertEqual(actual, expected)

    def test_full_range_requires_more_than_signed17(self) -> None:
        self.assertGreater(4 * 127 * 255, 65535)
        self.assertLess(4 * -128 * 255, -65536)
        cases = {
            item["case_id"]: item for item in self.report["counterexample_matrix"]
        }
        self.assertFalse(cases["positive_range_overflow17"]["four_lane_matches"])
        self.assertFalse(cases["negative_range_overflow17"]["four_lane_matches"])

    def test_conv_and_matmul_share_fail_closed_gate(self) -> None:
        scope = self.report["scope"]
        self.assertEqual(scope["qlinearconv_accumulate_stage_count"], 53)
        self.assertEqual(scope["qlinearmatmul_accumulate_stage_count"], 1)
        self.assertFalse(self.report["candidate_release"])
        self.assertFalse(self.report["server_package_allowed"])


if __name__ == "__main__":
    unittest.main()
