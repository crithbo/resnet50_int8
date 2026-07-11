from __future__ import annotations

import unittest

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper

from resnet50_pipeline.golden.qlinear_conv import (
    qlinear_conv_im2col,
    qlinear_conv_scalar,
    requantize_uint8,
)


def ort_qlinear_conv(
    x: np.ndarray,
    w: np.ndarray,
    *,
    x_scale: np.ndarray,
    x_zero_point: np.ndarray,
    w_scale: np.ndarray,
    w_zero_point: np.ndarray,
    y_scale: np.ndarray,
    y_zero_point: np.ndarray,
    bias: np.ndarray,
    strides: tuple[int, int],
    pads: tuple[int, int, int, int],
    dilations: tuple[int, int],
    group: int,
) -> np.ndarray:
    inputs = [
        helper.make_tensor_value_info("x", TensorProto.UINT8, list(x.shape)),
        helper.make_tensor_value_info("x_scale", TensorProto.FLOAT, list(x_scale.shape)),
        helper.make_tensor_value_info("x_zp", TensorProto.UINT8, list(x_zero_point.shape)),
        helper.make_tensor_value_info("w", TensorProto.INT8, list(w.shape)),
        helper.make_tensor_value_info("w_scale", TensorProto.FLOAT, list(w_scale.shape)),
        helper.make_tensor_value_info("w_zp", TensorProto.INT8, list(w_zero_point.shape)),
        helper.make_tensor_value_info("y_scale", TensorProto.FLOAT, list(y_scale.shape)),
        helper.make_tensor_value_info("y_zp", TensorProto.UINT8, list(y_zero_point.shape)),
        helper.make_tensor_value_info("bias", TensorProto.INT32, list(bias.shape)),
    ]
    effective_h = (w.shape[2] - 1) * dilations[0] + 1
    effective_w = (w.shape[3] - 1) * dilations[1] + 1
    output_h = (x.shape[2] + pads[0] + pads[2] - effective_h) // strides[0] + 1
    output_w = (x.shape[3] + pads[1] + pads[3] - effective_w) // strides[1] + 1
    output = helper.make_tensor_value_info(
        "y", TensorProto.UINT8, [x.shape[0], w.shape[0], output_h, output_w]
    )
    node = helper.make_node(
        "QLinearConv",
        [item.name for item in inputs],
        ["y"],
        strides=list(strides),
        pads=list(pads),
        dilations=list(dilations),
        group=group,
    )
    graph = helper.make_graph([node], "tiny_qlinear_conv", inputs, [output])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
    model.ir_version = 10
    onnx.checker.check_model(model)
    session = ort.InferenceSession(
        model.SerializeToString(), providers=["CPUExecutionProvider"]
    )
    feed = {
        "x": x,
        "x_scale": x_scale,
        "x_zp": x_zero_point,
        "w": w,
        "w_scale": w_scale,
        "w_zp": w_zero_point,
        "y_scale": y_scale,
        "y_zp": y_zero_point,
        "bias": bias,
    }
    return session.run(None, feed)[0]


class QLinearConvGoldenTests(unittest.TestCase):
    def _compare_case(
        self,
        *,
        x: np.ndarray,
        w: np.ndarray,
        x_scale: np.ndarray,
        x_zp: np.ndarray,
        w_scale: np.ndarray,
        w_zp: np.ndarray,
        y_scale: np.ndarray,
        y_zp: np.ndarray,
        bias: np.ndarray,
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
        group: int = 1,
    ) -> None:
        kwargs = dict(
            x_scale=x_scale,
            x_zero_point=x_zp,
            w_scale=w_scale,
            w_zero_point=w_zp,
            y_scale=y_scale,
            y_zero_point=y_zp,
            bias=bias,
            strides=strides,
            pads=pads,
            dilations=dilations,
            group=group,
        )
        scalar = qlinear_conv_scalar(x, w, reduction_tile=5, **kwargs)
        im2col = qlinear_conv_im2col(x, w, **kwargs)
        runtime = ort_qlinear_conv(
            x,
            w,
            x_scale=x_scale,
            x_zero_point=x_zp,
            w_scale=w_scale,
            w_zero_point=w_zp,
            y_scale=y_scale,
            y_zero_point=y_zp,
            bias=bias,
            strides=strides,
            pads=pads,
            dilations=dilations,
            group=group,
        )
        np.testing.assert_array_equal(scalar.accumulator, im2col.accumulator)
        np.testing.assert_array_equal(scalar.output, im2col.output)
        np.testing.assert_array_equal(scalar.output, runtime)
        np.testing.assert_array_equal(scalar.tile_psums[-1], scalar.accumulator)
        expected_bias = np.broadcast_to(
            bias.reshape(1, -1, 1, 1), scalar.accumulator.shape
        )
        np.testing.assert_array_equal(scalar.bias_initial, expected_bias)

    def test_per_channel_padding_negative_weights_and_saturation(self) -> None:
        rng = np.random.default_rng(20260711)
        self._compare_case(
            x=rng.integers(0, 256, size=(1, 2, 4, 5), dtype=np.uint8),
            w=rng.integers(-128, 128, size=(3, 2, 3, 3), dtype=np.int16).astype(np.int8),
            x_scale=np.array(0.03125, dtype=np.float32),
            x_zp=np.array(127, dtype=np.uint8),
            w_scale=np.array([0.015625, 0.025, 0.0625], dtype=np.float32),
            w_zp=np.array([0, 0, 0], dtype=np.int8),
            y_scale=np.array(0.02, dtype=np.float32),
            y_zp=np.array(113, dtype=np.uint8),
            bias=np.array([-500, 0, 700], dtype=np.int32),
            pads=(1, 1, 1, 1),
        )

    def test_group_stride_and_dilation(self) -> None:
        rng = np.random.default_rng(7)
        self._compare_case(
            x=rng.integers(0, 256, size=(1, 4, 7, 8), dtype=np.uint8),
            w=rng.integers(-20, 21, size=(4, 2, 2, 2), dtype=np.int16).astype(np.int8),
            x_scale=np.array(0.02, dtype=np.float32),
            x_zp=np.array(111, dtype=np.uint8),
            w_scale=np.array([0.03, 0.04, 0.05, 0.06], dtype=np.float32),
            w_zp=np.zeros(4, dtype=np.int8),
            y_scale=np.array(0.04, dtype=np.float32),
            y_zp=np.array(99, dtype=np.uint8),
            bias=np.array([10, -20, 30, -40], dtype=np.int32),
            strides=(2, 1),
            pads=(1, 0, 0, 1),
            dilations=(2, 1),
            group=2,
        )

    def test_round_to_nearest_even_and_uint8_saturation(self) -> None:
        accumulator = np.array(
            [[[[-3, -1, 1, 3, 5, 1000, -1000]]]], dtype=np.int32
        )
        output = requantize_uint8(accumulator, np.float32(0.5), np.uint8(128))
        expected = np.array([[[[126, 128, 128, 130, 130, 255, 0]]]], dtype=np.uint8)
        np.testing.assert_array_equal(output, expected)

    def test_dtype_and_group_validation(self) -> None:
        x = np.ones((1, 2, 2, 2), dtype=np.uint8)
        w = np.ones((1, 2, 1, 1), dtype=np.int8)
        kwargs = dict(
            x_scale=0.1,
            x_zero_point=0,
            w_scale=0.1,
            w_zero_point=0,
            y_scale=0.1,
            y_zero_point=0,
        )
        with self.assertRaisesRegex(TypeError, "uint8"):
            qlinear_conv_scalar(x.astype(np.int8), w, **kwargs)
        with self.assertRaisesRegex(ValueError, "group"):
            qlinear_conv_scalar(x, w, group=2, **kwargs)


if __name__ == "__main__":
    unittest.main()
