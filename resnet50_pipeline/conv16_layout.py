from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .memory import DramGeometry
from .records import LayoutRecord


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _canonical(array: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<"), copy=False))


def _pair(values: tuple[int, int], name: str) -> tuple[int, int]:
    if len(values) != 2 or any(int(value) <= 0 for value in values):
        raise ValueError(f"{name} must contain two positive integers")
    return int(values[0]), int(values[1])


@dataclass(frozen=True)
class ConvBatchRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    dtype: str
    physical_shape: tuple[int, ...]
    placement: str
    active: bool


@dataclass(frozen=True)
class ConvBatchPhysicalBundle:
    geometry: DramGeometry
    alignment: int
    regions: tuple[ConvBatchRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    metadata: dict[str, Any]

    def region(self, port: str, slice_id: int) -> ConvBatchRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one {port} region on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        for port in self.metadata["port_order"]:
            spec = self.metadata["ports"][port]
            bases = tuple(
                self.region(port, slice_id).base_address
                for slice_id in range(self.geometry.slice_count)
            )
            records.append(
                LayoutRecord(
                    layout_id=f"layout-conv-batch16-{port.lower()}-{spec['tensor_id']}",
                    tensor_id=spec["tensor_id"],
                    transform=self.metadata["contract"],
                    contract_status=self.metadata["status"],
                    port=port,
                    logical_shape=tuple(spec["logical_shape"]),
                    logical_dtype=spec["logical_dtype"],
                    partition={
                        "axis": 0 if spec["placement"] == "batch" else None,
                        "policy": (
                            "one_batch_item_per_slice"
                            if spec["placement"] == "batch"
                            else "replicated_on_every_slice"
                        ),
                        "slice_count": self.geometry.slice_count,
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "channel_tile": self.metadata["channel_tile"],
                        "output_channel_tile": self.metadata["output_channel_tile"],
                        "tail_value": spec["tail_value"],
                        "im2col_mode": self.metadata["im2col_mode"] if port == "A" else None,
                        "producer_transition": (
                            self.metadata["producer_transition"] if port == "A" else None
                        ),
                    },
                    base_addresses=bases,
                    inverse_status="validated",
                )
            )
        return tuple(records)


class ConvBatch16PhysicalLayout:
    """Candidate W4 Conv layout with one batch item owned by each slice.

    A is stored as HWC with a padded C tail. The convolution window is not
    materialized; the address generator derives it from output/kernel
    coordinates. B is replicated as RSKC, while bias/qparams are replicated
    K-vectors. P and D are stored as HWK with a padded K tail.
    """

    contract = "w4_conv_batch16_candidate_v1"
    status = "candidate"

    def __init__(
        self,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
        channel_tile: int = 8,
        output_channel_tile: int = 8,
    ):
        self.geometry = geometry or DramGeometry()
        if self.geometry.slice_count != 16:
            raise ValueError("Conv batch16 candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        if channel_tile <= 0 or output_channel_tile <= 0:
            raise ValueError("channel tiles must be positive")
        self.alignment = alignment
        self.channel_tile = channel_tile
        self.output_channel_tile = output_channel_tile

    def _output_shape(
        self,
        activation_shape: tuple[int, int, int, int],
        weight_shape: tuple[int, int, int, int],
        strides: tuple[int, int],
        pads: tuple[int, int, int, int],
        dilations: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        n, _, height, width = activation_shape
        outputs, _, kernel_h, kernel_w = weight_shape
        effective_h = (kernel_h - 1) * dilations[0] + 1
        effective_w = (kernel_w - 1) * dilations[1] + 1
        output_h = (height + pads[0] + pads[2] - effective_h) // strides[0] + 1
        output_w = (width + pads[1] + pads[3] - effective_w) // strides[1] + 1
        if output_h <= 0 or output_w <= 0:
            raise ValueError("Conv attributes produce a non-positive output shape")
        return n, outputs, output_h, output_w

    def plan(
        self,
        *,
        activation_shape: tuple[int, int, int, int],
        weight_shape: tuple[int, int, int, int],
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
        group: int = 1,
    ) -> dict[str, Any]:
        strides = _pair(strides, "strides")
        dilations = _pair(dilations, "dilations")
        if len(pads) != 4 or any(int(value) < 0 for value in pads):
            raise ValueError("pads must contain four non-negative integers")
        pads = tuple(int(value) for value in pads)
        n, channels, height, width = tuple(int(value) for value in activation_shape)
        outputs, weight_channels, kernel_h, kernel_w = tuple(
            int(value) for value in weight_shape
        )
        if any(
            value <= 0
            for value in (
                n,
                channels,
                height,
                width,
                outputs,
                weight_channels,
                kernel_h,
                kernel_w,
            )
        ):
            raise ValueError("Conv tensor dimensions must be positive")
        if not 1 <= n <= self.geometry.slice_count:
            raise ValueError("batch must contain 1..16 items")
        if group != 1:
            raise ValueError("current ResNet Conv candidate supports group=1 only")
        if channels != weight_channels:
            raise ValueError("weight input channels do not match activation channels")
        output_shape = self._output_shape(
            (n, channels, height, width),
            (outputs, weight_channels, kernel_h, kernel_w),
            strides,
            pads,
            dilations,
        )
        _, _, output_h, output_w = output_shape
        c_padded = _align(channels, self.channel_tile)
        k_padded = _align(outputs, self.output_channel_tile)
        raw_sizes = {
            "A": height * width * c_padded,
            "B": kernel_h * kernel_w * k_padded * c_padded,
            "bias": k_padded * 4,
            "w_scale": k_padded * 4,
            "w_zero_point": k_padded,
            "x_scale": 4,
            "x_zero_point": 1,
            "y_scale": 4,
            "y_zero_point": 1,
            "multiplier": k_padded * 4,
            "P": output_h * output_w * k_padded * 4,
            "D": output_h * output_w * k_padded,
        }
        offsets: dict[str, int] = {}
        cursor = 0
        for port, size in raw_sizes.items():
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(size, self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError(
                f"Conv regions need {cursor} bytes per slice, capacity is "
                f"{self.geometry.bytes_per_slice}"
            )
        return {
            "activation_shape": (n, channels, height, width),
            "weight_shape": (outputs, weight_channels, kernel_h, kernel_w),
            "output_shape": output_shape,
            "strides": strides,
            "pads": pads,
            "dilations": dilations,
            "group": group,
            "c_padded": c_padded,
            "k_padded": k_padded,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
        }

    @staticmethod
    def _channel_parameter(
        value: np.ndarray, outputs: int, dtype: np.dtype, name: str
    ) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype:
            raise TypeError(f"{name} must have dtype {dtype}")
        array = array.reshape(-1)
        if array.size == 1:
            array = np.repeat(array, outputs)
        if array.shape != (outputs,):
            raise ValueError(f"{name} must be scalar or have {outputs} values")
        return _canonical(array)

    @staticmethod
    def _scalar(value: np.ndarray, dtype: np.dtype, name: str) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype or array.size != 1:
            raise TypeError(f"{name} must be scalar {dtype}")
        return _canonical(array.reshape(1))

    def forward(
        self,
        *,
        activation: np.ndarray,
        weight: np.ndarray,
        bias: np.ndarray,
        w_scale: np.ndarray,
        w_zero_point: np.ndarray,
        x_scale: np.ndarray,
        x_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        accumulator: np.ndarray,
        output: np.ndarray,
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
        group: int = 1,
        tensor_ids: dict[str, str] | None = None,
    ) -> ConvBatchPhysicalBundle:
        activation = np.asarray(activation)
        weight = np.asarray(weight)
        bias = np.asarray(bias)
        accumulator = np.asarray(accumulator)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("activation must be rank-4 uint8 NCHW")
        if weight.dtype != np.int8 or weight.ndim != 4:
            raise TypeError("weight must be rank-4 int8 OIHW")
        plan = self.plan(
            activation_shape=tuple(activation.shape),
            weight_shape=tuple(weight.shape),
            strides=strides,
            pads=pads,
            dilations=dilations,
            group=group,
        )
        outputs = weight.shape[0]
        if bias.dtype != np.int32 or bias.shape != (outputs,):
            raise TypeError(f"bias must be int32 with shape ({outputs},)")
        if accumulator.dtype != np.int32 or tuple(accumulator.shape) != plan["output_shape"]:
            raise TypeError("accumulator must be int32 with the inferred NCHW output shape")
        if output.dtype != np.uint8 or tuple(output.shape) != plan["output_shape"]:
            raise TypeError("output must be uint8 with the inferred NCHW output shape")
        w_scale = self._channel_parameter(w_scale, outputs, np.dtype("float32"), "w_scale")
        w_zero_point = self._channel_parameter(
            w_zero_point, outputs, np.dtype("int8"), "w_zero_point"
        )
        bias = _canonical(bias)
        x_scale = self._scalar(x_scale, np.dtype("float32"), "x_scale")
        x_zero_point = self._scalar(
            x_zero_point, np.dtype("uint8"), "x_zero_point"
        )
        y_scale = self._scalar(y_scale, np.dtype("float32"), "y_scale")
        y_zero_point = self._scalar(
            y_zero_point, np.dtype("uint8"), "y_zero_point"
        )
        if float(x_scale[0]) <= 0 or float(y_scale[0]) <= 0 or np.any(w_scale <= 0):
            raise ValueError("all quantization scales must be positive")
        multiplier = _canonical(
            (np.float32(x_scale[0]) * w_scale / np.float32(y_scale[0])).astype(
                np.float32
            )
        )
        ids = {
            "A": "conv_activation",
            "B": "conv_weight",
            "bias": "conv_bias",
            "w_scale": "conv_w_scale",
            "w_zero_point": "conv_w_zero_point",
            "x_scale": "conv_x_scale",
            "x_zero_point": "conv_x_zero_point",
            "y_scale": "conv_y_scale",
            "y_zero_point": "conv_y_zero_point",
            "multiplier": "conv_multiplier",
            "P": "conv_accumulator",
            "D": "conv_output",
            **(tensor_ids or {}),
        }
        if len(set(ids.values())) != len(ids):
            raise ValueError("Conv port tensor IDs must be unique")

        n, channels, height, width = activation.shape
        outputs, _, kernel_h, kernel_w = weight.shape
        _, _, output_h, output_w = accumulator.shape
        c_padded = int(plan["c_padded"])
        k_padded = int(plan["k_padded"])
        batch_arrays: dict[str, list[np.ndarray]] = {"A": [], "P": [], "D": []}
        for batch_index in range(n):
            a = np.full((height, width, c_padded), int(x_zero_point[0]), dtype=np.uint8)
            a[..., :channels] = np.transpose(activation[batch_index], (1, 2, 0))
            p = np.zeros((output_h, output_w, k_padded), dtype="<i4")
            p[..., :outputs] = np.transpose(accumulator[batch_index], (1, 2, 0))
            d = np.full((output_h, output_w, k_padded), int(y_zero_point[0]), dtype=np.uint8)
            d[..., :outputs] = np.transpose(output[batch_index], (1, 2, 0))
            batch_arrays["A"].append(a)
            batch_arrays["P"].append(p)
            batch_arrays["D"].append(d)

        b = np.zeros((kernel_h, kernel_w, k_padded, c_padded), dtype=np.int8)
        for output_channel in range(outputs):
            b[:, :, output_channel, :] = int(w_zero_point[output_channel])
            b[:, :, output_channel, :channels] = np.transpose(
                weight[output_channel], (1, 2, 0)
            )
        vectors: dict[str, np.ndarray] = {
            "bias": np.pad(bias, (0, k_padded - outputs)),
            "w_scale": np.pad(w_scale, (0, k_padded - outputs)),
            "w_zero_point": np.pad(w_zero_point, (0, k_padded - outputs)),
            "multiplier": np.pad(multiplier, (0, k_padded - outputs)),
        }
        replicated = {
            "B": _canonical(b),
            **{name: _canonical(value) for name, value in vectors.items()},
            "x_scale": x_scale,
            "x_zero_point": x_zero_point,
            "y_scale": y_scale,
            "y_zero_point": y_zero_point,
        }
        port_order = tuple(plan["raw_sizes"].keys())
        physical_shapes = {
            "A": (height, width, c_padded),
            "B": b.shape,
            "bias": (k_padded,),
            "w_scale": (k_padded,),
            "w_zero_point": (k_padded,),
            "x_scale": (1,),
            "x_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "multiplier": (k_padded,),
            "P": (output_h, output_w, k_padded),
            "D": (output_h, output_w, k_padded),
        }
        logical_shapes = {
            "A": activation.shape,
            "B": weight.shape,
            "bias": bias.shape,
            "w_scale": w_scale.shape,
            "w_zero_point": w_zero_point.shape,
            "x_scale": (1,),
            "x_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "multiplier": multiplier.shape,
            "P": accumulator.shape,
            "D": output.shape,
        }
        dtypes = {
            "A": "uint8",
            "B": "int8",
            "bias": "int32",
            "w_scale": "float32",
            "w_zero_point": "int8",
            "x_scale": "float32",
            "x_zero_point": "uint8",
            "y_scale": "float32",
            "y_zero_point": "uint8",
            "multiplier": "float32",
            "P": "int32",
            "D": "uint8",
        }
        axis_orders = {
            "A": "HWC_padded",
            "B": "RSK_paddedC_padded",
            "P": "HWK_padded",
            "D": "HWK_padded",
        }
        for name in port_order:
            axis_orders.setdefault(name, "K_padded" if name in vectors else "scalar")
        tail_values: dict[str, Any] = {
            "A": int(x_zero_point[0]),
            "B": "per_output_w_zero_point",
            "bias": 0,
            "w_scale": 0.0,
            "w_zero_point": 0,
            "x_scale": 0.0,
            "x_zero_point": 0,
            "y_scale": 0.0,
            "y_zero_point": 0,
            "multiplier": 0.0,
            "P": 0,
            "D": int(y_zero_point[0]),
        }
        ports = {
            name: {
                "tensor_id": ids[name],
                "logical_shape": tuple(int(value) for value in logical_shapes[name]),
                "logical_dtype": dtypes[name],
                "physical_shape": tuple(int(value) for value in physical_shapes[name]),
                "physical_axis_order": axis_orders[name],
                "placement": "batch" if name in batch_arrays else "replicated",
                "tail_value": tail_values[name],
            }
            for name in port_order
        }

        regions: list[ConvBatchRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        inactive_payloads: dict[str, bytes] = {}
        replicated_payloads = {
            name: value.tobytes(order="C") for name, value in replicated.items()
        }
        for port in port_order:
            payload_bytes = int(plan["raw_sizes"][port])
            size_bytes = _align(payload_bytes, self.alignment)
            if port in batch_arrays:
                if port == "A":
                    fill_byte = int(x_zero_point[0])
                elif port == "D":
                    fill_byte = int(y_zero_point[0])
                else:
                    fill_byte = 0
                inactive_payloads[port] = bytes([fill_byte]) * payload_bytes + bytes(
                    size_bytes - payload_bytes
                )
            for slice_id in range(self.geometry.slice_count):
                active = port not in batch_arrays or slice_id < n
                if port in batch_arrays and active:
                    raw = _canonical(batch_arrays[port][slice_id]).tobytes(order="C")
                elif port in batch_arrays:
                    payloads[(port, slice_id)] = inactive_payloads[port]
                    raw = b""
                else:
                    raw = replicated_payloads[port]
                if raw:
                    payloads[(port, slice_id)] = raw + bytes(size_bytes - len(raw))
                regions.append(
                    ConvBatchRegion(
                        port=port,
                        tensor_id=ids[port],
                        slice_id=slice_id,
                        base_address=self.geometry.slice_base(slice_id)
                        + int(plan["offsets"][port]),
                        payload_bytes=payload_bytes,
                        size_bytes=size_bytes,
                        dtype=dtypes[port],
                        physical_shape=tuple(physical_shapes[port]),
                        placement="batch" if port in batch_arrays else "replicated",
                        active=active,
                    )
                )
        bundle = ConvBatchPhysicalBundle(
            geometry=self.geometry,
            alignment=self.alignment,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                "contract": self.contract,
                "status": self.status,
                "im2col_mode": "address_generator",
                "producer_transition": "NCHW_to_HWC_padded_explicit_relayout",
                "slice_topology": "batch_parallel_one_item_per_slice",
                "weight_policy": "replicated_on_every_slice",
                "qparams_policy": "replicated_on_every_slice",
                "channel_tile": self.channel_tile,
                "output_channel_tile": self.output_channel_tile,
                "port_order": port_order,
                "ports": ports,
                **plan,
                "x_zero_point": int(x_zero_point[0]),
                "y_zero_point": int(y_zero_point[0]),
            },
        )
        self.validate(bundle)
        return bundle

    def _read_array(self, bundle: ConvBatchPhysicalBundle, port: str, slice_id: int) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes],
            dtype=np.dtype(region.dtype),
        ).reshape(region.physical_shape)

    def inverse_port(self, bundle: ConvBatchPhysicalBundle, port: str) -> np.ndarray:
        spec = bundle.metadata["ports"][port]
        logical_shape = tuple(spec["logical_shape"])
        n = int(bundle.metadata["activation_shape"][0])
        channels = int(bundle.metadata["activation_shape"][1])
        outputs = int(bundle.metadata["weight_shape"][0])
        if spec["placement"] == "replicated":
            arrays = [self._read_array(bundle, port, slice_id) for slice_id in range(16)]
            for candidate in arrays[1:]:
                if not np.array_equal(candidate, arrays[0]):
                    raise ValueError(f"replicated port {port} differs between slices")
            physical = arrays[0]
            if port == "B":
                return np.transpose(physical[:, :, :outputs, :channels], (2, 3, 0, 1)).copy()
            if port in {"bias", "w_scale", "w_zero_point", "multiplier"}:
                return physical[:outputs].copy()
            return physical.reshape(logical_shape).copy()
        arrays = [self._read_array(bundle, port, slice_id) for slice_id in range(n)]
        if port == "A":
            return np.stack(
                [np.transpose(array[..., :channels], (2, 0, 1)) for array in arrays]
            )
        if port in {"P", "D"}:
            return np.stack(
                [np.transpose(array[..., :outputs], (2, 0, 1)) for array in arrays]
            )
        raise KeyError(f"unknown batch port {port}")

    def inverse(self, bundle: ConvBatchPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(bundle, port)
            for port in bundle.metadata["port_order"]
        }

    def explain_coordinate(
        self,
        bundle: ConvBatchPhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        matches = [
            port
            for port in bundle.metadata["port_order"]
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one Conv port for tensor {tensor_id!r}")
        port = matches[0]
        spec = bundle.metadata["ports"][port]
        logical_shape = tuple(spec["logical_shape"])
        if len(coordinate) != len(logical_shape):
            raise ValueError("coordinate rank does not match logical tensor")
        if any(
            index < 0 or index >= size
            for index, size in zip(coordinate, logical_shape, strict=True)
        ):
            raise IndexError("logical coordinate is out of range")
        if spec["placement"] == "batch":
            slice_ids = (coordinate[0],)
            if port == "A":
                physical_coordinate = (coordinate[2], coordinate[3], coordinate[1])
            else:
                physical_coordinate = (coordinate[2], coordinate[3], coordinate[1])
        else:
            slice_ids = tuple(range(16))
            if port == "B":
                physical_coordinate = (coordinate[2], coordinate[3], coordinate[0], coordinate[1])
            else:
                physical_coordinate = coordinate
        region0 = bundle.region(port, slice_ids[0])
        element_index = int(np.ravel_multi_index(physical_coordinate, region0.physical_shape))
        itemsize = np.dtype(region0.dtype).itemsize
        result: list[dict[str, Any]] = []
        for slice_id in slice_ids:
            region = bundle.region(port, slice_id)
            for element_byte in range(itemsize):
                address = region.base_address + element_index * itemsize + element_byte
                result.append(
                    {
                        "tensor_id": tensor_id,
                        "port": port,
                        "logical_coordinate": coordinate,
                        "physical_coordinate": physical_coordinate,
                        "slice_id": slice_id,
                        "address": address,
                        "dram_coordinate": bundle.geometry.decode(address),
                        "element_byte": element_byte,
                        "semantic": "data" if len(slice_ids) == 1 else "replicated_data",
                    }
                )
        return tuple(result)

    def explain_window(
        self,
        bundle: ConvBatchPhysicalBundle,
        *,
        batch: int,
        output_h: int,
        output_w: int,
        kernel_h: int,
        kernel_w: int,
        channel: int,
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["activation_shape"]
        _, _, output_height, output_width = bundle.metadata["output_shape"]
        _, _, kernel_height, kernel_width = bundle.metadata["weight_shape"]
        bounds = (
            (batch, n, "batch"),
            (output_h, output_height, "output_h"),
            (output_w, output_width, "output_w"),
            (kernel_h, kernel_height, "kernel_h"),
            (kernel_w, kernel_width, "kernel_w"),
            (channel, channels, "channel"),
        )
        for value, size, name in bounds:
            if not 0 <= value < size:
                raise IndexError(f"{name} is out of range")
        strides = bundle.metadata["strides"]
        pads = bundle.metadata["pads"]
        dilations = bundle.metadata["dilations"]
        input_h = output_h * strides[0] + kernel_h * dilations[0] - pads[0]
        input_w = output_w * strides[1] + kernel_w * dilations[1] - pads[1]
        if not (0 <= input_h < height and 0 <= input_w < width):
            return {
                "semantic": "padding",
                "value": bundle.metadata["x_zero_point"],
                "logical_coordinate": None,
                "address": None,
            }
        tensor_id = bundle.metadata["ports"]["A"]["tensor_id"]
        explanation = self.explain_coordinate(
            bundle, tensor_id, (batch, channel, input_h, input_w)
        )
        return {
            "semantic": "data",
            "logical_coordinate": (batch, channel, input_h, input_w),
            "address": explanation[0]["address"],
            "physical_coordinate": explanation[0]["physical_coordinate"],
        }

    def validate(self, bundle: ConvBatchPhysicalBundle) -> dict[str, int]:
        if bundle.metadata["contract"] != self.contract or bundle.metadata["status"] != self.status:
            raise ValueError("bundle contract does not match this layout")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("bundle geometry/alignment does not match this layout")
        ports = tuple(bundle.metadata["port_order"])
        if len(bundle.regions) != len(ports) * 16:
            raise ValueError("bundle must contain one region per port and slice")
        n = int(bundle.metadata["activation_shape"][0])
        for slice_id in range(16):
            previous_end = bundle.geometry.slice_base(slice_id)
            slice_end = previous_end + bundle.geometry.bytes_per_slice
            for port in ports:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError(f"port {port} is not aligned")
                if region.base_address < previous_end:
                    raise ValueError("Conv physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("Conv physical region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("Conv payload length differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("Conv alignment padding is corrupted")
                if region.placement == "batch" and region.active != (slice_id < n):
                    raise ValueError("Conv batch activity mask is inconsistent")
                previous_end = region.base_address + region.size_bytes
        recovered = {port: self.inverse_port(bundle, port) for port in ports}
        channels = int(bundle.metadata["activation_shape"][1])
        outputs = int(bundle.metadata["weight_shape"][0])
        c_padded = int(bundle.metadata["c_padded"])
        k_padded = int(bundle.metadata["k_padded"])
        for slice_id in range(16):
            a = self._read_array(bundle, "A", slice_id)
            p = self._read_array(bundle, "P", slice_id)
            d = self._read_array(bundle, "D", slice_id)
            if slice_id >= n:
                if np.any(a != bundle.metadata["x_zero_point"]):
                    raise ValueError("Conv inactive activation slice is corrupted")
                if np.any(p != 0):
                    raise ValueError("Conv inactive accumulator slice is corrupted")
                if np.any(d != bundle.metadata["y_zero_point"]):
                    raise ValueError("Conv inactive output slice is corrupted")
            if channels < c_padded and np.any(
                a[..., channels:] != bundle.metadata["x_zero_point"]
            ):
                raise ValueError("Conv activation C tail is corrupted")
            if outputs < k_padded and np.any(p[..., outputs:] != 0):
                raise ValueError("Conv accumulator K tail is corrupted")
            if outputs < k_padded and np.any(
                d[..., outputs:] != bundle.metadata["y_zero_point"]
            ):
                raise ValueError("Conv output K tail is corrupted")
        b = self._read_array(bundle, "B", 0)
        wzp = recovered["w_zero_point"]
        if channels < c_padded:
            for output_channel in range(outputs):
                if np.any(b[:, :, output_channel, channels:] != wzp[output_channel]):
                    raise ValueError("Conv weight C tail is corrupted")
        if outputs < k_padded and np.any(b[:, :, outputs:, :] != 0):
            raise ValueError("Conv weight K tail is corrupted")
        if outputs < k_padded:
            for port in ("bias", "w_scale", "w_zero_point", "multiplier"):
                if np.any(self._read_array(bundle, port, 0)[outputs:] != 0):
                    raise ValueError(f"Conv {port} K tail is corrupted")
        return {
            "slice_count": 16,
            "port_count": len(ports),
            "region_count": len(bundle.regions),
            "per_slice_used_bytes": int(bundle.metadata["per_slice_used_bytes"]),
        }
