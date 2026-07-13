from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .conv16_layout import (
    ConvBatch16PhysicalLayout,
    ConvBatchRegion,
    _align,
    _canonical,
    _pair,
)
from .memory import DramGeometry, LEGACY_DRAM_GEOMETRY16
from .records import LayoutRecord


@dataclass(frozen=True)
class ConvRingPhysicalBundle:
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
            if spec["placement"] == "c_partition":
                policy = "contiguous_c_partition_across_ring"
                axis = 1
            elif spec["placement"] == "k_partition":
                policy = "contiguous_k_owner_partition_across_ring"
                axis = spec["logical_k_axis"]
            else:
                policy = "replicated_on_every_slice"
                axis = None
            records.append(
                LayoutRecord(
                    layout_id=f"layout-conv-ring16-{port.lower()}-{spec['tensor_id']}",
                    tensor_id=spec["tensor_id"],
                    transform=self.metadata["contract"],
                    contract_status=self.metadata["status"],
                    port=port,
                    logical_shape=tuple(spec["logical_shape"]),
                    logical_dtype=spec["logical_dtype"],
                    partition={
                        "axis": axis,
                        "policy": policy,
                        "slice_count": self.geometry.slice_count,
                        "c_tile": self.metadata["c_tile"],
                        "k_tile": self.metadata["k_tile"],
                        "ring_steps": self.metadata["ring_steps"],
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
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


class ConvRing16PhysicalLayout(ConvBatch16PhysicalLayout):
    """Candidate W4 Conv layout using 16-slice C/K ring partitioning.

    A owns contiguous C chunks. B, per-channel qparams, P and D own contiguous
    K chunks. Scalar x/y qparams are replicated. For an output K owner, ring
    traversal starts at that owner and visits all 16 activation C owners.
    """

    contract = "w4_conv_ring16_candidate_v1"
    status = "candidate"

    def __init__(self, geometry: DramGeometry | None = None, *, alignment: int = 16):
        self.geometry = geometry or LEGACY_DRAM_GEOMETRY16
        if self.geometry.slice_count != 16:
            raise ValueError("Conv ring16 candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment

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
        if n > 16:
            raise ValueError("current ring16 candidate supports batch <= 16")
        if group != 1:
            raise ValueError("current ResNet Conv ring candidate supports group=1 only")
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
        c_tile = math.ceil(channels / 16)
        k_tile = math.ceil(outputs / 16)
        c_padded = c_tile * 16
        k_padded = k_tile * 16
        raw_sizes = {
            "A": n * height * width * c_tile,
            "B": kernel_h * kernel_w * k_tile * c_padded,
            "bias": k_tile * 4,
            "w_scale": k_tile * 4,
            "w_zero_point": k_tile,
            "x_scale": 4,
            "x_zero_point": 1,
            "y_scale": 4,
            "y_zero_point": 1,
            "multiplier": k_tile * 4,
            "P": n * output_h * output_w * k_tile * 4,
            "D": n * output_h * output_w * k_tile,
        }
        offsets: dict[str, int] = {}
        cursor = 0
        for port, size in raw_sizes.items():
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(size, self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError(
                f"ring16 Conv regions need {cursor} bytes per slice, capacity is "
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
            "c_tile": c_tile,
            "k_tile": k_tile,
            "c_padded": c_padded,
            "k_padded": k_padded,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
        }

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
    ) -> ConvRingPhysicalBundle:
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
        c_tile = int(plan["c_tile"])
        k_tile = int(plan["k_tile"])
        c_padded = int(plan["c_padded"])
        per_slice: list[dict[str, np.ndarray]] = []
        for slice_id in range(16):
            c_start = slice_id * c_tile
            k_start = slice_id * k_tile
            valid_c = max(0, min(c_tile, channels - c_start))
            valid_k = max(0, min(k_tile, outputs - k_start))
            a = np.full((n, height, width, c_tile), int(x_zero_point[0]), dtype=np.uint8)
            if valid_c:
                a[..., :valid_c] = np.transpose(
                    activation[:, c_start : c_start + valid_c], (0, 2, 3, 1)
                )
            b = np.zeros((kernel_h, kernel_w, k_tile, c_padded), dtype=np.int8)
            for local_k in range(valid_k):
                global_k = k_start + local_k
                b[:, :, local_k, :] = int(w_zero_point[global_k])
                b[:, :, local_k, :channels] = np.transpose(
                    weight[global_k], (1, 2, 0)
                )
            p = np.zeros((n, output_h, output_w, k_tile), dtype="<i4")
            d = np.full(
                (n, output_h, output_w, k_tile), int(y_zero_point[0]), dtype=np.uint8
            )
            if valid_k:
                p[..., :valid_k] = np.transpose(
                    accumulator[:, k_start : k_start + valid_k], (0, 2, 3, 1)
                )
                d[..., :valid_k] = np.transpose(
                    output[:, k_start : k_start + valid_k], (0, 2, 3, 1)
                )
            vectors = {
                "bias": np.zeros(k_tile, dtype="<i4"),
                "w_scale": np.zeros(k_tile, dtype="<f4"),
                "w_zero_point": np.zeros(k_tile, dtype=np.int8),
                "multiplier": np.zeros(k_tile, dtype="<f4"),
            }
            if valid_k:
                vectors["bias"][:valid_k] = bias[k_start : k_start + valid_k]
                vectors["w_scale"][:valid_k] = w_scale[k_start : k_start + valid_k]
                vectors["w_zero_point"][:valid_k] = w_zero_point[
                    k_start : k_start + valid_k
                ]
                vectors["multiplier"][:valid_k] = multiplier[
                    k_start : k_start + valid_k
                ]
            per_slice.append(
                {
                    "A": a,
                    "B": b,
                    **vectors,
                    "x_scale": x_scale,
                    "x_zero_point": x_zero_point,
                    "y_scale": y_scale,
                    "y_zero_point": y_zero_point,
                    "P": p,
                    "D": d,
                }
            )

        port_order = tuple(plan["raw_sizes"].keys())
        physical_shapes = {
            port: tuple(per_slice[0][port].shape) for port in port_order
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
        placements = {
            "A": "c_partition",
            "B": "k_partition",
            "bias": "k_partition",
            "w_scale": "k_partition",
            "w_zero_point": "k_partition",
            "x_scale": "replicated",
            "x_zero_point": "replicated",
            "y_scale": "replicated",
            "y_zero_point": "replicated",
            "multiplier": "k_partition",
            "P": "k_partition",
            "D": "k_partition",
        }
        axis_orders = {
            "A": "NHWC_local",
            "B": "RSK_localC_global_padded",
            "bias": "K_local",
            "w_scale": "K_local",
            "w_zero_point": "K_local",
            "x_scale": "scalar",
            "x_zero_point": "scalar",
            "y_scale": "scalar",
            "y_zero_point": "scalar",
            "multiplier": "K_local",
            "P": "NHWK_local",
            "D": "NHWK_local",
        }
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
            port: {
                "tensor_id": ids[port],
                "logical_shape": tuple(int(value) for value in logical_shapes[port]),
                "logical_dtype": dtypes[port],
                "physical_shape": physical_shapes[port],
                "physical_axis_order": axis_orders[port],
                "placement": placements[port],
                "logical_k_axis": 0 if port in {"B", "bias", "w_scale", "w_zero_point", "multiplier"} else 1,
                "tail_value": tail_values[port],
            }
            for port in port_order
        }
        regions: list[ConvBatchRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for slice_id, arrays in enumerate(per_slice):
            valid_c = max(0, min(c_tile, channels - slice_id * c_tile))
            valid_k = max(0, min(k_tile, outputs - slice_id * k_tile))
            for port in port_order:
                raw = _canonical(arrays[port]).tobytes(order="C")
                payload_bytes = int(plan["raw_sizes"][port])
                size_bytes = _align(payload_bytes, self.alignment)
                payloads[(port, slice_id)] = raw + bytes(size_bytes - len(raw))
                placement = placements[port]
                active = (
                    valid_c > 0
                    if placement == "c_partition"
                    else valid_k > 0
                    if placement == "k_partition"
                    else True
                )
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
                        physical_shape=physical_shapes[port],
                        placement=placement,
                        active=active,
                    )
                )
        bundle = ConvRingPhysicalBundle(
            geometry=self.geometry,
            alignment=self.alignment,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                "contract": self.contract,
                "status": self.status,
                "im2col_mode": "address_generator",
                "producer_transition": "NCHW_to_ring_C_partitioned_NHWC_explicit_relayout",
                "slice_topology": "ring_C_activation_K_output_partition",
                "ring_steps": 16,
                "neighbor_transfer_count": 15,
                "ring_order_formula": "(k_owner_slice + step) % 16",
                "port_order": port_order,
                "ports": ports,
                **plan,
                "x_zero_point": int(x_zero_point[0]),
                "y_zero_point": int(y_zero_point[0]),
            },
        )
        self.validate(bundle)
        return bundle

    def _read_array(self, bundle: ConvRingPhysicalBundle, port: str, slice_id: int) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes],
            dtype=np.dtype(region.dtype),
        ).reshape(region.physical_shape)

    def inverse_port(self, bundle: ConvRingPhysicalBundle, port: str) -> np.ndarray:
        n, channels, height, width = bundle.metadata["activation_shape"]
        outputs, _, kernel_h, kernel_w = bundle.metadata["weight_shape"]
        _, _, output_h, output_w = bundle.metadata["output_shape"]
        c_tile = int(bundle.metadata["c_tile"])
        k_tile = int(bundle.metadata["k_tile"])
        if port in {"x_scale", "x_zero_point", "y_scale", "y_zero_point"}:
            arrays = [self._read_array(bundle, port, slice_id) for slice_id in range(16)]
            for candidate in arrays[1:]:
                if not np.array_equal(candidate, arrays[0]):
                    raise ValueError(f"replicated scalar port {port} differs between slices")
            return arrays[0].copy()
        if port == "A":
            logical = np.empty((n, channels, height, width), dtype=np.uint8)
            for slice_id in range(16):
                c_start = slice_id * c_tile
                valid_c = max(0, min(c_tile, channels - c_start))
                if valid_c:
                    physical = self._read_array(bundle, port, slice_id)
                    logical[:, c_start : c_start + valid_c] = np.transpose(
                        physical[..., :valid_c], (0, 3, 1, 2)
                    )
            return logical
        if port == "B":
            logical = np.empty((outputs, channels, kernel_h, kernel_w), dtype=np.int8)
            for slice_id in range(16):
                k_start = slice_id * k_tile
                valid_k = max(0, min(k_tile, outputs - k_start))
                if valid_k:
                    physical = self._read_array(bundle, port, slice_id)
                    logical[k_start : k_start + valid_k] = np.transpose(
                        physical[:, :, :valid_k, :channels], (2, 3, 0, 1)
                    )
            return logical
        if port in {"bias", "w_scale", "w_zero_point", "multiplier"}:
            dtype = np.dtype(bundle.region(port, 0).dtype)
            logical = np.empty(outputs, dtype=dtype)
            for slice_id in range(16):
                k_start = slice_id * k_tile
                valid_k = max(0, min(k_tile, outputs - k_start))
                if valid_k:
                    logical[k_start : k_start + valid_k] = self._read_array(
                        bundle, port, slice_id
                    )[:valid_k]
            return logical
        if port in {"P", "D"}:
            dtype = np.dtype(bundle.region(port, 0).dtype)
            logical = np.empty((n, outputs, output_h, output_w), dtype=dtype)
            for slice_id in range(16):
                k_start = slice_id * k_tile
                valid_k = max(0, min(k_tile, outputs - k_start))
                if valid_k:
                    physical = self._read_array(bundle, port, slice_id)
                    logical[:, k_start : k_start + valid_k] = np.transpose(
                        physical[..., :valid_k], (0, 3, 1, 2)
                    )
            return logical
        raise KeyError(f"unknown ring Conv port {port}")

    def inverse(self, bundle: ConvRingPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(bundle, port)
            for port in bundle.metadata["port_order"]
        }

    def explain_coordinate(
        self,
        bundle: ConvRingPhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        matches = [
            port
            for port in bundle.metadata["port_order"]
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one ring Conv port for tensor {tensor_id!r}")
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
        c_tile = int(bundle.metadata["c_tile"])
        k_tile = int(bundle.metadata["k_tile"])
        if port == "A":
            slice_ids = (coordinate[1] // c_tile,)
            physical_coordinate = (
                coordinate[0],
                coordinate[2],
                coordinate[3],
                coordinate[1] % c_tile,
            )
        elif port == "B":
            slice_ids = (coordinate[0] // k_tile,)
            physical_coordinate = (
                coordinate[2],
                coordinate[3],
                coordinate[0] % k_tile,
                coordinate[1],
            )
        elif port in {"bias", "w_scale", "w_zero_point", "multiplier"}:
            slice_ids = (coordinate[0] // k_tile,)
            physical_coordinate = (coordinate[0] % k_tile,)
        elif port in {"P", "D"}:
            slice_ids = (coordinate[1] // k_tile,)
            physical_coordinate = (
                coordinate[0],
                coordinate[2],
                coordinate[3],
                coordinate[1] % k_tile,
            )
        else:
            slice_ids = tuple(range(16))
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
                        "semantic": (
                            "replicated_data" if len(slice_ids) == 16 else "partitioned_data"
                        ),
                    }
                )
        return tuple(result)

    def explain_window(
        self,
        bundle: ConvRingPhysicalBundle,
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
            "slice_id": explanation[0]["slice_id"],
            "physical_coordinate": explanation[0]["physical_coordinate"],
        }

    def explain_ring_step(
        self,
        bundle: ConvRingPhysicalBundle,
        *,
        output_channel: int,
        step: int,
    ) -> dict[str, Any]:
        outputs = int(bundle.metadata["weight_shape"][0])
        channels = int(bundle.metadata["activation_shape"][1])
        if not 0 <= output_channel < outputs:
            raise IndexError("output_channel is out of range")
        if not 0 <= step < 16:
            raise IndexError("ring step is out of range")
        k_tile = int(bundle.metadata["k_tile"])
        c_tile = int(bundle.metadata["c_tile"])
        owner = output_channel // k_tile
        activation_slice = (owner + step) % 16
        c_start = activation_slice * c_tile
        range_start = min(channels, c_start)
        c_end = min(channels, c_start + c_tile)
        return {
            "output_channel": output_channel,
            "k_owner_slice": owner,
            "ring_step": step,
            "activation_slice": activation_slice,
            "channel_range": (range_start, c_end),
            "has_data": c_start < channels,
            "last": step == 15,
        }

    def validate(self, bundle: ConvRingPhysicalBundle) -> dict[str, int]:
        if bundle.metadata["contract"] != self.contract or bundle.metadata["status"] != self.status:
            raise ValueError("bundle contract does not match this ring layout")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("bundle geometry/alignment does not match this ring layout")
        ports = tuple(bundle.metadata["port_order"])
        if len(bundle.regions) != len(ports) * 16:
            raise ValueError("ring bundle must contain one region per port and slice")
        for slice_id in range(16):
            previous_end = bundle.geometry.slice_base(slice_id)
            slice_end = previous_end + bundle.geometry.bytes_per_slice
            for port in ports:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError(f"ring port {port} is not aligned")
                if region.base_address < previous_end:
                    raise ValueError("ring Conv physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("ring Conv region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("ring Conv payload length differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("ring Conv alignment padding is corrupted")
                previous_end = region.base_address + region.size_bytes
        for port in ports:
            self.inverse_port(bundle, port)
        _, channels, _, _ = bundle.metadata["activation_shape"]
        outputs = int(bundle.metadata["weight_shape"][0])
        c_tile = int(bundle.metadata["c_tile"])
        k_tile = int(bundle.metadata["k_tile"])
        c_padded = int(bundle.metadata["c_padded"])
        for slice_id in range(16):
            c_start = slice_id * c_tile
            k_start = slice_id * k_tile
            valid_c = max(0, min(c_tile, channels - c_start))
            valid_k = max(0, min(k_tile, outputs - k_start))
            expected_active_c = valid_c > 0
            expected_active_k = valid_k > 0
            for port in ports:
                region = bundle.region(port, slice_id)
                expected = (
                    expected_active_c
                    if region.placement == "c_partition"
                    else expected_active_k
                    if region.placement == "k_partition"
                    else True
                )
                if region.active != expected:
                    raise ValueError("ring Conv activity mask is inconsistent")
            a = self._read_array(bundle, "A", slice_id)
            if valid_c < c_tile and np.any(
                a[..., valid_c:] != bundle.metadata["x_zero_point"]
            ):
                raise ValueError("ring Conv activation C tail is corrupted")
            b = self._read_array(bundle, "B", slice_id)
            wzp = self._read_array(bundle, "w_zero_point", slice_id)
            for local_k in range(valid_k):
                if channels < c_padded and np.any(
                    b[:, :, local_k, channels:] != wzp[local_k]
                ):
                    raise ValueError("ring Conv weight C tail is corrupted")
            if valid_k < k_tile and np.any(b[:, :, valid_k:, :] != 0):
                raise ValueError("ring Conv weight K tail is corrupted")
            p = self._read_array(bundle, "P", slice_id)
            d = self._read_array(bundle, "D", slice_id)
            if valid_k < k_tile and np.any(p[..., valid_k:] != 0):
                raise ValueError("ring Conv accumulator K tail is corrupted")
            if valid_k < k_tile and np.any(
                d[..., valid_k:] != bundle.metadata["y_zero_point"]
            ):
                raise ValueError("ring Conv output K tail is corrupted")
            for port in ("bias", "w_scale", "w_zero_point", "multiplier"):
                if valid_k < k_tile and np.any(
                    self._read_array(bundle, port, slice_id)[valid_k:] != 0
                ):
                    raise ValueError(f"ring Conv {port} K tail is corrupted")
        return {
            "slice_count": 16,
            "port_count": len(ports),
            "region_count": len(bundle.regions),
            "ring_steps": 16,
            "per_slice_used_bytes": int(bundle.metadata["per_slice_used_bytes"]),
        }
