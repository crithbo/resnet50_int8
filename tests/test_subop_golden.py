from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.golden.subops import (
    _qlinear_add,
    _requantize,
    conv_accumulator,
    global_average_sum,
    matmul_accumulator,
)


class SubopGoldenTests(unittest.TestCase):
    def test_conv_accumulator_and_requant(self) -> None:
        x = np.array([[[[5, 7], [9, 11]]]], dtype=np.uint8)
        w = np.array([[[[-2]]], [[[3]]]], dtype=np.int8)
        bias = np.array([4, -5], dtype=np.int32)
        result = conv_accumulator(x, w, bias, 7, np.zeros(2, dtype=np.int8), {})
        expected = np.stack(((x.astype(np.int32) - 7) * -2 + 4, (x.astype(np.int32) - 7) * 3 - 5), axis=1).reshape(1, 2, 2, 2)
        np.testing.assert_array_equal(result, expected)
        output = _requantize(result, np.array([0.5, 0.25], dtype=np.float32), 100)
        self.assertEqual(output.dtype, np.uint8)

    def test_matmul_accumulator(self) -> None:
        left = np.array([[5, 7]], dtype=np.uint8)
        right = np.array([[2, -1], [3, 4]], dtype=np.int8)
        result = matmul_accumulator(left, right, 5, np.array(0, dtype=np.int8))
        np.testing.assert_array_equal(result, np.array([[6, 8]], dtype=np.int32))

    def test_global_average_sum_is_centered(self) -> None:
        value = np.array([[[[4, 5], [6, 7]]]], dtype=np.uint8)
        np.testing.assert_array_equal(
            global_average_sum(value, 5), np.array([[[[2]]]], dtype=np.int32)
        )

    def test_qlinear_add_requantizes_two_affine_inputs(self) -> None:
        inputs = [
            np.array([0, 10], dtype=np.uint8),
            np.array(0.5, dtype=np.float32),
            np.array(2, dtype=np.uint8),
            np.array([4, 8], dtype=np.uint8),
            np.array(0.25, dtype=np.float32),
            np.array(4, dtype=np.uint8),
            np.array(0.5, dtype=np.float32),
            np.array(100, dtype=np.uint8),
        ]
        np.testing.assert_array_equal(
            _qlinear_add(inputs), np.array([98, 110], dtype=np.uint8)
        )


if __name__ == "__main__":
    unittest.main()
