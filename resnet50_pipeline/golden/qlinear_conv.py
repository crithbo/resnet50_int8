from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


@dataclass(frozen=True)
class QLinearConvGolden:
    bias_initial: np.ndarray
    tile_psums: tuple[np.ndarray, ...]
    accumulator: np.ndarray
    output: np.ndarray


@dataclass(frozen=True)
class _Parameters:
    x: np.ndarray
    w: np.ndarray
    bias: np.ndarray
    x_scale: np.float32
    x_zero_point: int
    w_scale: np.ndarray
    w_zero_point: np.ndarray
    y_scale: np.float32
    y_zero_point: int
    strides: tuple[int, int]
    pads: tuple[int, int, int, int]
    dilations: tuple[int, int]
    group: int
    output_shape: tuple[int, int, int, int]


def _pair(value: Sequence[int], name: str) -> tuple[int, int]:
    if len(value) != 2 or any(int(item) <= 0 for item in value):
        raise ValueError(f"{name} must contain two positive integers")
    return int(value[0]), int(value[1])


def _normalize_channel_parameter(
    value: np.ndarray | float | int,
    channels: int,
    dtype: np.dtype,
    name: str,
) -> np.ndarray:
    array = np.asarray(value, dtype=dtype).reshape(-1)
    if array.size == 1:
        array = np.repeat(array, channels)
    if array.size != channels:
        raise ValueError(f"{name} must be scalar or have {channels} elements")
    return array


def _parameters(
    x: np.ndarray,
    w: np.ndarray,
    *,
    x_scale: np.ndarray | float,
    x_zero_point: np.ndarray | int,
    w_scale: np.ndarray | float,
    w_zero_point: np.ndarray | int,
    y_scale: np.ndarray | float,
    y_zero_point: np.ndarray | int,
    bias: np.ndarray | None,
    strides: Sequence[int],
    pads: Sequence[int],
    dilations: Sequence[int],
    group: int,
) -> _Parameters:
    if x.dtype != np.uint8 or x.ndim != 4:
        raise TypeError("x must be a rank-4 uint8 NCHW array")
    if w.dtype != np.int8 or w.ndim != 4:
        raise TypeError("w must be a rank-4 int8 OIHW array")
    if len(pads) != 4 or any(int(item) < 0 for item in pads):
        raise ValueError("pads must be [top, left, bottom, right] with non-negative values")
    strides_pair = _pair(strides, "strides")
    dilations_pair = _pair(dilations, "dilations")
    pads_tuple = tuple(int(item) for item in pads)
    group = int(group)
    n, channels, height, width = x.shape
    outputs, channels_per_group, kernel_h, kernel_w = w.shape
    if group <= 0 or channels % group or outputs % group:
        raise ValueError("group must divide input and output channels")
    if channels_per_group != channels // group:
        raise ValueError("weight input channels do not match x channels/group")

    x_scale_scalar = np.asarray(x_scale, dtype=np.float32).reshape(-1)
    y_scale_scalar = np.asarray(y_scale, dtype=np.float32).reshape(-1)
    x_zp_scalar = np.asarray(x_zero_point, dtype=np.uint8).reshape(-1)
    y_zp_scalar = np.asarray(y_zero_point, dtype=np.uint8).reshape(-1)
    if any(item.size != 1 for item in (x_scale_scalar, y_scale_scalar, x_zp_scalar, y_zp_scalar)):
        raise ValueError("x/y scale and zero point must be scalar")
    if x_scale_scalar[0] <= 0 or y_scale_scalar[0] <= 0:
        raise ValueError("x/y scales must be positive")
    weight_scales = _normalize_channel_parameter(w_scale, outputs, np.float32, "w_scale")
    weight_zero_points = _normalize_channel_parameter(
        w_zero_point, outputs, np.int8, "w_zero_point"
    )
    if np.any(weight_scales <= 0):
        raise ValueError("w_scale values must be positive")

    if bias is None:
        bias_array = np.zeros(outputs, dtype=np.int32)
    else:
        bias_array = np.asarray(bias)
        if bias_array.dtype != np.int32 or bias_array.shape != (outputs,):
            raise TypeError(f"bias must be int32 with shape ({outputs},)")

    effective_h = (kernel_h - 1) * dilations_pair[0] + 1
    effective_w = (kernel_w - 1) * dilations_pair[1] + 1
    output_h = (height + pads_tuple[0] + pads_tuple[2] - effective_h) // strides_pair[0] + 1
    output_w = (width + pads_tuple[1] + pads_tuple[3] - effective_w) // strides_pair[1] + 1
    if output_h <= 0 or output_w <= 0:
        raise ValueError("kernel/padding/stride produce a non-positive output shape")
    return _Parameters(
        x=x,
        w=w,
        bias=bias_array,
        x_scale=x_scale_scalar[0],
        x_zero_point=int(x_zp_scalar[0]),
        w_scale=weight_scales,
        w_zero_point=weight_zero_points,
        y_scale=y_scale_scalar[0],
        y_zero_point=int(y_zp_scalar[0]),
        strides=strides_pair,
        pads=pads_tuple,
        dilations=dilations_pair,
        group=group,
        output_shape=(n, outputs, output_h, output_w),
    )


def _checked_int32(accumulator: np.ndarray) -> np.ndarray:
    minimum = int(accumulator.min())
    maximum = int(accumulator.max())
    limits = np.iinfo(np.int32)
    if minimum < limits.min or maximum > limits.max:
        raise OverflowError(
            f"QLinearConv accumulator exceeds int32: min={minimum}, max={maximum}"
        )
    return accumulator.astype(np.int32)


def requantize_uint8(
    accumulator: np.ndarray,
    multiplier: np.ndarray | float,
    y_zero_point: np.ndarray | int,
) -> np.ndarray:
    if accumulator.ndim != 4:
        raise ValueError("accumulator must be rank-4 NCHW")
    channels = accumulator.shape[1]
    scales = _normalize_channel_parameter(multiplier, channels, np.float32, "multiplier")
    zero_point = np.asarray(y_zero_point, dtype=np.uint8).reshape(-1)
    if zero_point.size != 1:
        raise ValueError("y_zero_point must be scalar")
    scaled = accumulator.astype(np.float32) * scales.reshape(1, channels, 1, 1)
    rounded = np.rint(scaled).astype(np.int64)
    shifted = rounded + int(zero_point[0])
    return np.clip(shifted, 0, 255).astype(np.uint8)


def _result(parameters: _Parameters, accumulator: np.ndarray, tile_psums: list[np.ndarray]) -> QLinearConvGolden:
    accumulator_i32 = _checked_int32(accumulator)
    multiplier = (
        np.float32(parameters.x_scale)
        * parameters.w_scale.astype(np.float32)
        / np.float32(parameters.y_scale)
    ).astype(np.float32)
    output = requantize_uint8(accumulator_i32, multiplier, parameters.y_zero_point)
    bias_initial = np.broadcast_to(
        parameters.bias.reshape(1, -1, 1, 1), parameters.output_shape
    ).copy()
    return QLinearConvGolden(
        bias_initial=bias_initial,
        tile_psums=tuple(_checked_int32(item) for item in tile_psums),
        accumulator=accumulator_i32,
        output=output,
    )


def qlinear_conv_scalar(
    x: np.ndarray,
    w: np.ndarray,
    *,
    x_scale: np.ndarray | float,
    x_zero_point: np.ndarray | int,
    w_scale: np.ndarray | float,
    w_zero_point: np.ndarray | int,
    y_scale: np.ndarray | float,
    y_zero_point: np.ndarray | int,
    bias: np.ndarray | None = None,
    strides: Sequence[int] = (1, 1),
    pads: Sequence[int] = (0, 0, 0, 0),
    dilations: Sequence[int] = (1, 1),
    group: int = 1,
    reduction_tile: int | None = None,
) -> QLinearConvGolden:
    p = _parameters(
        x,
        w,
        x_scale=x_scale,
        x_zero_point=x_zero_point,
        w_scale=w_scale,
        w_zero_point=w_zero_point,
        y_scale=y_scale,
        y_zero_point=y_zero_point,
        bias=bias,
        strides=strides,
        pads=pads,
        dilations=dilations,
        group=group,
    )
    if reduction_tile is not None and reduction_tile <= 0:
        raise ValueError("reduction_tile must be positive")
    n_size, output_channels, output_h, output_w = p.output_shape
    input_channels = p.x.shape[1]
    channels_per_group = input_channels // p.group
    outputs_per_group = output_channels // p.group
    kernel_h, kernel_w = p.w.shape[2:]
    reduction_size = channels_per_group * kernel_h * kernel_w
    snapshot_count = 0 if reduction_tile is None else (reduction_size + reduction_tile - 1) // reduction_tile
    snapshots = [np.empty(p.output_shape, dtype=np.int64) for _ in range(snapshot_count)]
    accumulator = np.empty(p.output_shape, dtype=np.int64)

    for n in range(n_size):
        for m in range(output_channels):
            group_index = m // outputs_per_group
            input_start = group_index * channels_per_group
            weight_zp = int(p.w_zero_point[m])
            for oh in range(output_h):
                for ow in range(output_w):
                    total = int(p.bias[m])
                    reduction_index = 0
                    snapshot_index = 0
                    for local_c in range(channels_per_group):
                        c = input_start + local_c
                        for kh in range(kernel_h):
                            ih = oh * p.strides[0] + kh * p.dilations[0] - p.pads[0]
                            for kw in range(kernel_w):
                                iw = ow * p.strides[1] + kw * p.dilations[1] - p.pads[1]
                                if 0 <= ih < p.x.shape[2] and 0 <= iw < p.x.shape[3]:
                                    activation = int(p.x[n, c, ih, iw]) - p.x_zero_point
                                else:
                                    activation = 0
                                weight = int(p.w[m, local_c, kh, kw]) - weight_zp
                                total += activation * weight
                                reduction_index += 1
                                if reduction_tile is not None and (
                                    reduction_index % reduction_tile == 0
                                    or reduction_index == reduction_size
                                ):
                                    snapshots[snapshot_index][n, m, oh, ow] = total
                                    snapshot_index += 1
                    accumulator[n, m, oh, ow] = total
    return _result(p, accumulator, snapshots)


def qlinear_conv_im2col(
    x: np.ndarray,
    w: np.ndarray,
    *,
    x_scale: np.ndarray | float,
    x_zero_point: np.ndarray | int,
    w_scale: np.ndarray | float,
    w_zero_point: np.ndarray | int,
    y_scale: np.ndarray | float,
    y_zero_point: np.ndarray | int,
    bias: np.ndarray | None = None,
    strides: Sequence[int] = (1, 1),
    pads: Sequence[int] = (0, 0, 0, 0),
    dilations: Sequence[int] = (1, 1),
    group: int = 1,
) -> QLinearConvGolden:
    p = _parameters(
        x,
        w,
        x_scale=x_scale,
        x_zero_point=x_zero_point,
        w_scale=w_scale,
        w_zero_point=w_zero_point,
        y_scale=y_scale,
        y_zero_point=y_zero_point,
        bias=bias,
        strides=strides,
        pads=pads,
        dilations=dilations,
        group=group,
    )
    centered_x = p.x.astype(np.int32) - p.x_zero_point
    padded = np.pad(
        centered_x,
        ((0, 0), (0, 0), (p.pads[0], p.pads[2]), (p.pads[1], p.pads[3])),
        mode="constant",
    )
    kernel_h, kernel_w = p.w.shape[2:]
    effective_h = (kernel_h - 1) * p.dilations[0] + 1
    effective_w = (kernel_w - 1) * p.dilations[1] + 1
    windows = sliding_window_view(padded, (effective_h, effective_w), axis=(2, 3))
    windows = windows[
        :,
        :,
        :: p.strides[0],
        :: p.strides[1],
        :: p.dilations[0],
        :: p.dilations[1],
    ]
    windows = windows[:, :, : p.output_shape[2], : p.output_shape[3], :, :]
    accumulator = np.empty(p.output_shape, dtype=np.int64)
    channels_per_group = p.x.shape[1] // p.group
    outputs_per_group = p.w.shape[0] // p.group
    for group_index in range(p.group):
        c0 = group_index * channels_per_group
        c1 = c0 + channels_per_group
        m0 = group_index * outputs_per_group
        m1 = m0 + outputs_per_group
        centered_w = (
            p.w[m0:m1].astype(np.int32)
            - p.w_zero_point[m0:m1].astype(np.int32).reshape(-1, 1, 1, 1)
        )
        accumulator[:, m0:m1] = np.einsum(
            "nchwkl,mckl->nmhw",
            windows[:, c0:c1],
            centered_w,
            dtype=np.int64,
            optimize=True,
        )
    accumulator += p.bias.reshape(1, -1, 1, 1).astype(np.int64)
    return _result(p, accumulator, [])
