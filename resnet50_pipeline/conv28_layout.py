"""Reversible RTL28 candidate layout for ResNet-50 ``QLinearConv``.

This module freezes software-side physical formulas only.  The geometry and
address order are still ``candidate_unapproved`` and therefore are not a
hardware approval or a W5 authorization.

The default profile assigns the fixed batch of sixteen to seven HIGH rings.
Within every ring, A is partitioned by C and B/bias/weight-qparams/P/D are
partitioned by K.  Static K-owned data is copied to the corresponding owner
step in all seven rings.  The global profile instead partitions C or K over
the explicit LOW-ring owner sequence and keeps all sixteen samples local.
No slice mapping in this file is derived from numeric adjacency or ``% 28``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .memory import DramGeometry, TARGET_DRAM_GEOMETRY28
from .profile28 import (
    BATCH_SIZE,
    DEFAULT_PROFILE,
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    GROUP_SAMPLE_COUNTS,
    group_to_sample_range,
    sample_to_group,
    validate_profile_name,
)
from .records import LayoutRecord
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS, TOPOLOGY28


CONV28_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: "w4_conv_group4x7_28_candidate_v1",
    GLOBAL_RING28_PROFILE: "w4_conv_global_ring28_candidate_v1",
}

PORT_ORDER = (
    "A",
    "B",
    "bias",
    "w_scale",
    "w_zero_point",
    "x_scale",
    "x_zero_point",
    "y_scale",
    "y_zero_point",
    "P",
    "D",
)

OwnerAxis = Literal["C", "K", "replicated"]


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _pair(value: tuple[int, int], label: str) -> tuple[int, int]:
    if len(value) != 2 or any(int(item) <= 0 for item in value):
        raise ValueError(f"{label} must contain two positive integers")
    return tuple(int(item) for item in value)


def _little(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


@dataclass(frozen=True)
class Conv28PortPlan:
    port: str
    logical_shape: tuple[int, ...]
    dtype: str
    owner_axis: OwnerAxis
    physical_shape: tuple[int, ...]
    physical_axis_order: str
    payload_bytes: int
    offset_bytes: int
    tail_rule: str


@dataclass(frozen=True)
class Conv28PhysicalPlan:
    contract: str
    status: str
    target_family: str
    profile_id: str
    geometry_status: str
    address_order_status: str
    geometry: DramGeometry
    alignment: int
    activation_shape: tuple[int, int, int, int]
    weight_shape: tuple[int, int, int, int]
    output_shape: tuple[int, int, int, int]
    strides: tuple[int, int]
    pads: tuple[int, int, int, int]
    dilations: tuple[int, int]
    group: int
    c_tile: int
    k_tile: int
    c_padded: int
    storage_sample_count: int
    ports: tuple[Conv28PortPlan, ...]
    per_slice_used_bytes: int
    per_slice_capacity_bytes: int

    def port(self, name: str) -> Conv28PortPlan:
        matches = [item for item in self.ports if item.port == name]
        if len(matches) != 1:
            raise KeyError(f"expected one Conv28 plan for port {name!r}")
        return matches[0]

    def capacity_report(self) -> dict[str, int | str | bool]:
        return {
            "contract": self.contract,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "per_slice_used_bytes": self.per_slice_used_bytes,
            "per_slice_capacity_bytes": self.per_slice_capacity_bytes,
            "per_slice_headroom_bytes": (
                self.per_slice_capacity_bytes - self.per_slice_used_bytes
            ),
            "total_candidate_bytes": (
                self.per_slice_used_bytes * self.geometry.slice_count
            ),
            "fits": self.per_slice_used_bytes <= self.per_slice_capacity_bytes,
            "geometry_status": self.geometry_status,
            "address_order_status": self.address_order_status,
        }


@dataclass(frozen=True)
class Conv28PortPlacement:
    port: str
    tensor_id: str
    logical_shape: tuple[int, ...]
    dtype: str
    owner_axis: OwnerAxis
    physical_axis_order: str
    tail_rule: str


@dataclass(frozen=True)
class Conv28PhysicalRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    physical_shape: tuple[int, ...]
    owner_axis: OwnerAxis
    active: bool
    group_id: int | None
    owner_step: int | None
    sample_start: int
    sample_count: int
    storage_sample_count: int
    logical_start: int
    logical_count: int


@dataclass(frozen=True)
class Conv28PhysicalBundle:
    plan: Conv28PhysicalPlan
    placements: tuple[Conv28PortPlacement, ...]
    regions: tuple[Conv28PhysicalRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    tensor_ids: dict[str, str]

    def placement(self, tensor_id: str) -> Conv28PortPlacement:
        matches = [item for item in self.placements if item.tensor_id == tensor_id]
        if len(matches) != 1:
            raise KeyError(f"expected one Conv28 placement for {tensor_id!r}")
        return matches[0]

    def region(self, port: str, slice_id: int) -> Conv28PhysicalRegion:
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
        for placement in self.placements:
            port_plan = self.plan.port(placement.port)
            bases = tuple(
                self.region(placement.port, slice_id).base_address
                for slice_id in range(self.plan.geometry.slice_count)
            )
            if placement.owner_axis == "replicated":
                partition: dict[str, Any] = {
                    "axis": None,
                    "policy": "replicated_on_every_rtl28_slice",
                    "slice_count": 28,
                    "profile_id": self.plan.profile_id,
                }
            elif self.plan.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                logical_axis = (
                    1 if placement.port in {"A", "P", "D"} else 0
                )
                partition = {
                    "axis": logical_axis,
                    "owner_axis": placement.owner_axis,
                    "policy": "seven_high_rings_batch_and_owner_axis_partition",
                    "slice_count": 28,
                    "profile_id": self.plan.profile_id,
                    "high_ring_owners": [list(item) for item in HIGH_RING_OWNERS],
                    "batch_group_sample_counts": list(GROUP_SAMPLE_COUNTS),
                    "owner_tile": (
                        self.plan.c_tile
                        if placement.owner_axis == "C"
                        else self.plan.k_tile
                    ),
                    "static_k_data_replicated_across_groups": placement.port
                    in {"B", "bias", "w_scale", "w_zero_point"},
                }
            else:
                logical_axis = (
                    1 if placement.port in {"A", "P", "D"} else 0
                )
                partition = {
                    "axis": logical_axis,
                    "owner_axis": placement.owner_axis,
                    "policy": "global_low_ring_owner_axis_partition",
                    "slice_count": 28,
                    "profile_id": self.plan.profile_id,
                    "low_ring_owners": list(LOW_RING_OWNERS),
                    "owner_tile": (
                        self.plan.c_tile
                        if placement.owner_axis == "C"
                        else self.plan.k_tile
                    ),
                }
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-conv28-{placement.port.lower()}-"
                        f"{placement.tensor_id}"
                    ),
                    tensor_id=placement.tensor_id,
                    transform=self.plan.contract,
                    contract_status=self.plan.status,
                    port=placement.port,
                    logical_shape=placement.logical_shape,
                    logical_dtype=placement.dtype,
                    partition=partition,
                    packing={
                        "logical_order": (
                            "NCHW" if placement.port in {"A", "P", "D"}
                            else "OIHW" if placement.port == "B" else "vector/scalar"
                        ),
                        "physical_order": placement.physical_axis_order,
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.plan.alignment,
                        "subword_bytes": self.plan.geometry.subword_bytes,
                        "tail_rule": placement.tail_rule,
                        "geometry_status": self.plan.geometry_status,
                        "address_order_status": self.plan.address_order_status,
                    },
                    base_addresses=bases,
                    inverse_status="validated",
                )
            )
        return tuple(records)


class QLinearConvPhysicalLayout:
    """Candidate reversible Conv relayout for the selected RTL28 profiles."""

    status = "candidate"
    target_family = "rtl28"
    geometry_status = "candidate_unapproved"
    address_order_status = "candidate_unapproved"

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
    ) -> None:
        self.profile_id = validate_profile_name(profile_id)
        self.geometry = geometry or TARGET_DRAM_GEOMETRY28
        if self.geometry != TARGET_DRAM_GEOMETRY28:
            raise ValueError("current Conv layout requires TARGET_DRAM_GEOMETRY28")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment
        self.contract = CONV28_LAYOUT_IDS[self.profile_id]

    @staticmethod
    def _output_shape(
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
    ) -> Conv28PhysicalPlan:
        if len(activation_shape) != 4 or len(weight_shape) != 4:
            raise ValueError("Conv activation and weight shapes must both be rank 4")
        activation_shape = tuple(int(value) for value in activation_shape)
        weight_shape = tuple(int(value) for value in weight_shape)
        if any(value <= 0 for value in (*activation_shape, *weight_shape)):
            raise ValueError("Conv tensor dimensions must be positive")
        n, channels, height, width = activation_shape
        outputs, weight_channels, kernel_h, kernel_w = weight_shape
        if n != BATCH_SIZE:
            raise ValueError(f"current RTL28 Conv profile requires batch={BATCH_SIZE}")
        if group != 1:
            raise ValueError("current ResNet RTL28 Conv candidate supports group=1 only")
        if channels != weight_channels:
            raise ValueError("weight input channels do not match activation channels")
        strides = _pair(strides, "strides")
        dilations = _pair(dilations, "dilations")
        if len(pads) != 4 or any(int(value) < 0 for value in pads):
            raise ValueError("pads must contain four non-negative integers")
        pads = tuple(int(value) for value in pads)
        output_shape = self._output_shape(
            activation_shape, weight_shape, strides, pads, dilations
        )
        _, _, output_h, output_w = output_shape
        owner_count = (
            4
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else self.geometry.slice_count
        )
        storage_samples = (
            max(GROUP_SAMPLE_COUNTS)
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else BATCH_SIZE
        )
        c_tile = math.ceil(channels / owner_count)
        k_tile = math.ceil(outputs / owner_count)
        # B always carries a complete input-channel row for every local K.  The
        # 16-element storage rounding gives C-tail bytes an explicit per-K
        # zero-point meaning instead of hiding them in anonymous alignment.
        c_padded = _align(channels, 16)
        physical_shapes = {
            "A": (storage_samples, height, width, c_tile),
            "B": (kernel_h, kernel_w, k_tile, c_padded),
            "bias": (k_tile,),
            "w_scale": (k_tile,),
            "w_zero_point": (k_tile,),
            "x_scale": (1,),
            "x_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "P": (storage_samples, output_h, output_w, k_tile),
            "D": (storage_samples, output_h, output_w, k_tile),
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
            "P": "int32",
            "D": "uint8",
        }
        logical_shapes = {
            "A": activation_shape,
            "B": weight_shape,
            "bias": (outputs,),
            "w_scale": (outputs,),
            "w_zero_point": (outputs,),
            "x_scale": (1,),
            "x_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "P": output_shape,
            "D": output_shape,
        }
        owner_axes: dict[str, OwnerAxis] = {
            "A": "C",
            "B": "K",
            "bias": "K",
            "w_scale": "K",
            "w_zero_point": "K",
            "x_scale": "replicated",
            "x_zero_point": "replicated",
            "y_scale": "replicated",
            "y_zero_point": "replicated",
            "P": "K",
            "D": "K",
        }
        physical_orders = {
            "A": "NHWC-local",
            "B": "RSK-localC-global-padded",
            "bias": "K-local",
            "w_scale": "K-local",
            "w_zero_point": "K-local",
            "x_scale": "replicated-scalar",
            "x_zero_point": "replicated-scalar",
            "y_scale": "replicated-scalar",
            "y_zero_point": "replicated-scalar",
            "P": "NHWK-local",
            "D": "NHWK-local",
        }
        tail_rules = {
            "A": "inactive N/C slots equal x_zero_point",
            "B": (
                "valid-K C-tail equals that K's w_zero_point; invalid-K rows "
                "equal int8 zero"
            ),
            "bias": "invalid K slots equal int32 zero",
            "w_scale": "invalid K slots equal float32 zero",
            "w_zero_point": "invalid K slots equal int8 zero",
            "x_scale": "alignment tail zero; scalar copied to every slice",
            "x_zero_point": "alignment tail zero; scalar copied to every slice",
            "y_scale": "alignment tail zero; scalar copied to every slice",
            "y_zero_point": "alignment tail zero; scalar copied to every slice",
            "P": "inactive N/K slots equal int32 zero",
            "D": "inactive N/K slots equal y_zero_point",
        }
        cursor = 0
        ports: list[Conv28PortPlan] = []
        for port in PORT_ORDER:
            cursor = _align(cursor, self.alignment)
            payload_bytes = math.prod(physical_shapes[port]) * np.dtype(
                dtypes[port]
            ).itemsize
            ports.append(
                Conv28PortPlan(
                    port=port,
                    logical_shape=logical_shapes[port],
                    dtype=dtypes[port],
                    owner_axis=owner_axes[port],
                    physical_shape=physical_shapes[port],
                    physical_axis_order=physical_orders[port],
                    payload_bytes=payload_bytes,
                    offset_bytes=cursor,
                    tail_rule=tail_rules[port],
                )
            )
            cursor += _align(payload_bytes, self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError(
                f"RTL28 Conv regions need {cursor} bytes per slice, capacity is "
                f"{self.geometry.bytes_per_slice}"
            )
        return Conv28PhysicalPlan(
            contract=self.contract,
            status=self.status,
            target_family=self.target_family,
            profile_id=self.profile_id,
            geometry_status=self.geometry_status,
            address_order_status=self.address_order_status,
            geometry=self.geometry,
            alignment=self.alignment,
            activation_shape=activation_shape,
            weight_shape=weight_shape,
            output_shape=output_shape,
            strides=strides,
            pads=pads,
            dilations=dilations,
            group=group,
            c_tile=c_tile,
            k_tile=k_tile,
            c_padded=c_padded,
            storage_sample_count=storage_samples,
            ports=tuple(ports),
            per_slice_used_bytes=cursor,
            per_slice_capacity_bytes=self.geometry.bytes_per_slice,
        )

    def capacity(self, **shape_and_attributes: Any) -> dict[str, int | str | bool]:
        """Return a no-payload capacity report for a formal Conv shape."""

        return self.plan(**shape_and_attributes).capacity_report()

    formal_plan = plan

    @staticmethod
    def _scalar(value: np.ndarray, dtype: np.dtype, name: str) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype or array.size != 1:
            raise TypeError(f"{name} must be scalar {dtype}")
        return _little(array.reshape(1))

    @staticmethod
    def _channel_parameter(
        value: np.ndarray,
        outputs: int,
        dtype: np.dtype,
        name: str,
    ) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype:
            raise TypeError(f"{name} must have dtype {dtype}")
        array = array.reshape(-1)
        if array.size == 1:
            array = np.repeat(array, outputs)
        if array.shape != (outputs,):
            raise ValueError(f"{name} must be scalar or have {outputs} values")
        return _little(array)

    def _owner_descriptor(
        self,
        plan: Conv28PhysicalPlan,
        port: Conv28PortPlan,
        slice_id: int,
    ) -> dict[str, int | bool | None]:
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id = TOPOLOGY28.group_for_slice(slice_id)
            owner_step = HIGH_RING_OWNERS[group_id].index(slice_id)
            sample_range = group_to_sample_range(group_id)
            sample_start = sample_range.start
            sample_count = sample_range.sample_count
        else:
            group_id = None
            owner_step = LOW_RING_OWNERS.index(slice_id)
            sample_start = 0
            sample_count = BATCH_SIZE
        if port.owner_axis == "C":
            logical_extent = plan.activation_shape[1]
            tile = plan.c_tile
        elif port.owner_axis == "K":
            logical_extent = plan.weight_shape[0]
            tile = plan.k_tile
        else:
            return {
                "active": True,
                "group_id": group_id,
                "owner_step": owner_step,
                "sample_start": 0,
                "sample_count": BATCH_SIZE,
                "logical_start": 0,
                "logical_count": 1,
            }
        logical_start = owner_step * tile
        logical_count = max(0, min(tile, logical_extent - logical_start))
        return {
            "active": logical_count > 0,
            "group_id": group_id,
            "owner_step": owner_step,
            "sample_start": sample_start,
            "sample_count": sample_count,
            "logical_start": logical_start,
            "logical_count": logical_count,
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
    ) -> Conv28PhysicalBundle:
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
        outputs = plan.weight_shape[0]
        if bias.dtype != np.int32 or bias.shape != (outputs,):
            raise TypeError(f"bias must be int32 with shape ({outputs},)")
        if accumulator.dtype != np.int32 or tuple(accumulator.shape) != plan.output_shape:
            raise TypeError("accumulator must be int32 with inferred NCHW output shape")
        if output.dtype != np.uint8 or tuple(output.shape) != plan.output_shape:
            raise TypeError("output must be uint8 with inferred NCHW output shape")
        canonical = {
            "A": _little(activation),
            "B": _little(weight),
            "bias": _little(bias),
            "w_scale": self._channel_parameter(
                w_scale, outputs, np.dtype("float32"), "w_scale"
            ),
            "w_zero_point": self._channel_parameter(
                w_zero_point, outputs, np.dtype("int8"), "w_zero_point"
            ),
            "x_scale": self._scalar(x_scale, np.dtype("float32"), "x_scale"),
            "x_zero_point": self._scalar(
                x_zero_point, np.dtype("uint8"), "x_zero_point"
            ),
            "y_scale": self._scalar(y_scale, np.dtype("float32"), "y_scale"),
            "y_zero_point": self._scalar(
                y_zero_point, np.dtype("uint8"), "y_zero_point"
            ),
            "P": _little(accumulator),
            "D": _little(output),
        }
        for name in ("w_scale", "x_scale", "y_scale"):
            scale = canonical[name]
            if not np.all(np.isfinite(scale)) or np.any(scale <= 0):
                raise ValueError(f"{name} values must be positive and finite")
        ids = {port: f"conv_{port.lower()}" for port in PORT_ORDER}
        ids.update(tensor_ids or {})
        if set(ids) != set(PORT_ORDER) or len(set(ids.values())) != len(ids):
            raise ValueError("Conv tensor_ids must define unique IDs for known ports")
        placements = tuple(
            Conv28PortPlacement(
                port=port.port,
                tensor_id=ids[port.port],
                logical_shape=port.logical_shape,
                dtype=port.dtype,
                owner_axis=port.owner_axis,
                physical_axis_order=port.physical_axis_order,
                tail_rule=port.tail_rule,
            )
            for port in plan.ports
        )
        x_zp = int(canonical["x_zero_point"][0])
        y_zp = int(canonical["y_zero_point"][0])
        regions: list[Conv28PhysicalRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for slice_id in range(self.geometry.slice_count):
            for port in plan.ports:
                descriptor = self._owner_descriptor(plan, port, slice_id)
                sample_start = int(descriptor["sample_start"])
                sample_count = int(descriptor["sample_count"])
                logical_start = int(descriptor["logical_start"])
                logical_count = int(descriptor["logical_count"])
                shape = port.physical_shape
                dtype = np.dtype(port.dtype).newbyteorder("<")
                if port.port == "A":
                    local = np.full(shape, x_zp, dtype=dtype)
                    if logical_count:
                        source = canonical["A"][
                            sample_start : sample_start + sample_count,
                            logical_start : logical_start + logical_count,
                            ...,
                        ]
                        local[:sample_count, ..., :logical_count] = np.moveaxis(
                            source, 1, -1
                        )
                elif port.port == "B":
                    local = np.zeros(shape, dtype=dtype)
                    for local_k in range(logical_count):
                        global_k = logical_start + local_k
                        local[:, :, local_k, :] = canonical["w_zero_point"][global_k]
                        local[:, :, local_k, : plan.weight_shape[1]] = np.transpose(
                            canonical["B"][global_k], (1, 2, 0)
                        )
                elif port.port in {"bias", "w_scale", "w_zero_point"}:
                    local = np.zeros(shape, dtype=dtype)
                    if logical_count:
                        local[:logical_count] = canonical[port.port][
                            logical_start : logical_start + logical_count
                        ]
                elif port.owner_axis == "replicated":
                    local = canonical[port.port].copy()
                elif port.port in {"P", "D"}:
                    fill = 0 if port.port == "P" else y_zp
                    local = np.full(shape, fill, dtype=dtype)
                    if logical_count:
                        source = canonical[port.port][
                            sample_start : sample_start + sample_count,
                            logical_start : logical_start + logical_count,
                            ...,
                        ]
                        local[:sample_count, ..., :logical_count] = np.moveaxis(
                            source, 1, -1
                        )
                else:
                    raise AssertionError(f"unhandled Conv port {port.port}")
                raw = np.ascontiguousarray(local).tobytes(order="C")
                if len(raw) != port.payload_bytes:
                    raise AssertionError("Conv28 physical size calculation drifted")
                size_bytes = _align(port.payload_bytes, self.alignment)
                payloads[(port.port, slice_id)] = raw + bytes(
                    size_bytes - len(raw)
                )
                regions.append(
                    Conv28PhysicalRegion(
                        port=port.port,
                        tensor_id=ids[port.port],
                        slice_id=slice_id,
                        base_address=(
                            self.geometry.slice_base(slice_id) + port.offset_bytes
                        ),
                        payload_bytes=port.payload_bytes,
                        size_bytes=size_bytes,
                        physical_shape=shape,
                        owner_axis=port.owner_axis,
                        active=bool(descriptor["active"]),
                        group_id=descriptor["group_id"],
                        owner_step=descriptor["owner_step"],
                        sample_start=sample_start,
                        sample_count=sample_count,
                        storage_sample_count=plan.storage_sample_count,
                        logical_start=logical_start,
                        logical_count=logical_count,
                    )
                )
        bundle = Conv28PhysicalBundle(
            plan=plan,
            placements=placements,
            regions=tuple(regions),
            payloads=payloads,
            tensor_ids=ids,
        )
        self.validate(bundle)
        return bundle

    def _read_array(
        self, bundle: Conv28PhysicalBundle, port: str, slice_id: int
    ) -> np.ndarray:
        region = bundle.region(port, slice_id)
        dtype = np.dtype(bundle.plan.port(port).dtype).newbyteorder("<")
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes], dtype=dtype
        ).reshape(region.physical_shape)

    def _canonical_k_owners(self) -> tuple[int, ...]:
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            return HIGH_RING_OWNERS[0]
        return LOW_RING_OWNERS

    def inverse_port(self, bundle: Conv28PhysicalBundle, port: str) -> np.ndarray:
        spec = bundle.plan.port(port)
        dtype = np.dtype(spec.dtype)
        if spec.owner_axis == "replicated":
            copies = [
                self._read_array(bundle, port, slice_id)
                for slice_id in range(self.geometry.slice_count)
            ]
            for copy in copies[1:]:
                if not np.array_equal(copy, copies[0]):
                    raise ValueError(f"replicated Conv scalar {port} differs between slices")
            return copies[0].astype(dtype, copy=True)

        logical = np.empty(spec.logical_shape, dtype=dtype)
        if port == "A":
            coverage = np.zeros(spec.logical_shape[:2], dtype=np.bool_)
            owners = range(self.geometry.slice_count)
            for slice_id in owners:
                region = bundle.region(port, slice_id)
                if not region.logical_count:
                    continue
                local = self._read_array(bundle, port, slice_id)
                block = np.moveaxis(
                    local[
                        : region.sample_count,
                        ...,
                        : region.logical_count,
                    ],
                    -1,
                    1,
                )
                n_stop = region.sample_start + region.sample_count
                c_stop = region.logical_start + region.logical_count
                if coverage[
                    region.sample_start:n_stop, region.logical_start:c_stop
                ].any():
                    raise ValueError("Conv A owner coverage overlaps")
                logical[
                    region.sample_start:n_stop, region.logical_start:c_stop, ...
                ] = block
                coverage[
                    region.sample_start:n_stop, region.logical_start:c_stop
                ] = True
        elif port == "B":
            coverage = np.zeros(spec.logical_shape[0], dtype=np.bool_)
            for slice_id in self._canonical_k_owners():
                region = bundle.region(port, slice_id)
                if not region.logical_count:
                    continue
                stop = region.logical_start + region.logical_count
                if coverage[region.logical_start:stop].any():
                    raise ValueError("Conv B K-owner coverage overlaps")
                local = self._read_array(bundle, port, slice_id)
                logical[region.logical_start:stop] = np.transpose(
                    local[
                        :,
                        :,
                        : region.logical_count,
                        : bundle.plan.weight_shape[1],
                    ],
                    (2, 3, 0, 1),
                )
                coverage[region.logical_start:stop] = True
        elif port in {"bias", "w_scale", "w_zero_point"}:
            coverage = np.zeros(spec.logical_shape[0], dtype=np.bool_)
            for slice_id in self._canonical_k_owners():
                region = bundle.region(port, slice_id)
                if not region.logical_count:
                    continue
                stop = region.logical_start + region.logical_count
                if coverage[region.logical_start:stop].any():
                    raise ValueError(f"Conv {port} K-owner coverage overlaps")
                logical[region.logical_start:stop] = self._read_array(
                    bundle, port, slice_id
                )[: region.logical_count]
                coverage[region.logical_start:stop] = True
        elif port in {"P", "D"}:
            coverage = np.zeros(spec.logical_shape[:2], dtype=np.bool_)
            for slice_id in range(self.geometry.slice_count):
                region = bundle.region(port, slice_id)
                if not region.logical_count:
                    continue
                local = self._read_array(bundle, port, slice_id)
                block = np.moveaxis(
                    local[
                        : region.sample_count,
                        ...,
                        : region.logical_count,
                    ],
                    -1,
                    1,
                )
                n_stop = region.sample_start + region.sample_count
                k_stop = region.logical_start + region.logical_count
                if coverage[
                    region.sample_start:n_stop, region.logical_start:k_stop
                ].any():
                    raise ValueError(f"Conv {port} owner coverage overlaps")
                logical[
                    region.sample_start:n_stop, region.logical_start:k_stop, ...
                ] = block
                coverage[
                    region.sample_start:n_stop, region.logical_start:k_stop
                ] = True
        else:
            raise KeyError(f"unknown Conv28 port {port!r}")
        if not coverage.all():
            raise ValueError(f"Conv {port} owner coverage is incomplete")
        return logical.astype(dtype, copy=False)

    def inverse(self, bundle: Conv28PhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.tensor_ids[port]: self.inverse_port(bundle, port)
            for port in PORT_ORDER
        }

    def explain_coordinate(
        self,
        bundle: Conv28PhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        placement = bundle.placement(tensor_id)
        if len(coordinate) != len(placement.logical_shape):
            raise ValueError("coordinate rank does not match logical tensor")
        if any(
            index < 0 or index >= size
            for index, size in zip(
                coordinate, placement.logical_shape, strict=True
            )
        ):
            raise IndexError("logical coordinate is out of range")
        port = placement.port
        plan = bundle.plan
        if port == "A":
            n, c, h, w = coordinate
            owner_step = c // plan.c_tile
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                assignment = sample_to_group(n)
                slice_ids = (HIGH_RING_OWNERS[assignment.group_id][owner_step],)
                local_n = assignment.local_slot
            else:
                slice_ids = (LOW_RING_OWNERS[owner_step],)
                local_n = n
            physical = (local_n, h, w, c % plan.c_tile)
            semantic = "data"
        elif port == "B":
            k, c, r, s = coordinate
            owner_step = k // plan.k_tile
            slice_ids = (
                tuple(ring[owner_step] for ring in HIGH_RING_OWNERS)
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                else (LOW_RING_OWNERS[owner_step],)
            )
            physical = (r, s, k % plan.k_tile, c)
            semantic = (
                "replicated_static_weight"
                if len(slice_ids) > 1
                else "partitioned_static_weight"
            )
        elif port in {"bias", "w_scale", "w_zero_point"}:
            k = coordinate[0]
            owner_step = k // plan.k_tile
            slice_ids = (
                tuple(ring[owner_step] for ring in HIGH_RING_OWNERS)
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                else (LOW_RING_OWNERS[owner_step],)
            )
            physical = (k % plan.k_tile,)
            semantic = (
                "replicated_static_k_parameter"
                if len(slice_ids) > 1
                else "partitioned_static_k_parameter"
            )
        elif placement.owner_axis == "replicated":
            slice_ids = tuple(range(self.geometry.slice_count))
            physical = coordinate
            semantic = "replicated_scalar_qparam"
        else:
            n, k, h, w = coordinate
            owner_step = k // plan.k_tile
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                assignment = sample_to_group(n)
                slice_ids = (HIGH_RING_OWNERS[assignment.group_id][owner_step],)
                local_n = assignment.local_slot
            else:
                slice_ids = (LOW_RING_OWNERS[owner_step],)
                local_n = n
            physical = (local_n, h, w, k % plan.k_tile)
            semantic = "data"
        first = bundle.region(port, slice_ids[0])
        element_index = int(np.ravel_multi_index(physical, first.physical_shape))
        itemsize = np.dtype(placement.dtype).itemsize
        explanations: list[dict[str, Any]] = []
        for slice_id in slice_ids:
            region = bundle.region(port, slice_id)
            for element_byte in range(itemsize):
                address = (
                    region.base_address + element_index * itemsize + element_byte
                )
                explanations.append(
                    {
                        "tensor_id": tensor_id,
                        "port": port,
                        "logical_coordinate": coordinate,
                        "physical_coordinate": physical,
                        "profile_id": self.profile_id,
                        "slice_id": slice_id,
                        "group_id": region.group_id,
                        "owner_step": region.owner_step,
                        "address": address,
                        "dram_coordinate": self.geometry.decode(address),
                        "element_byte": element_byte,
                        "semantic": semantic,
                    }
                )
        return tuple(explanations)

    def _validate_tail(
        self, bundle: Conv28PhysicalBundle, port: str, slice_id: int
    ) -> int:
        region = bundle.region(port, slice_id)
        local = self._read_array(bundle, port, slice_id)
        plan = bundle.plan
        tail_elements = 0
        if port == "A":
            valid = np.zeros(region.physical_shape, dtype=np.bool_)
            if region.logical_count:
                valid[: region.sample_count, ..., : region.logical_count] = True
            tail = local[~valid]
            expected = self._read_array(bundle, "x_zero_point", slice_id)[0]
        elif port == "B":
            valid_k = region.logical_count
            if valid_k < plan.k_tile and np.any(local[:, :, valid_k:, :] != 0):
                raise ValueError("Conv B invalid-K tail is corrupted")
            wzp = self._read_array(bundle, "w_zero_point", slice_id)
            for local_k in range(valid_k):
                c_tail = local[:, :, local_k, plan.weight_shape[1] :]
                if c_tail.size and np.any(c_tail != wzp[local_k]):
                    raise ValueError("Conv B per-channel C-tail is corrupted")
                tail_elements += int(c_tail.size)
            return tail_elements + int(local[:, :, valid_k:, :].size)
        elif port in {"bias", "w_scale", "w_zero_point"}:
            tail = local[region.logical_count :]
            expected = 0
        elif port in {"P", "D"}:
            valid = np.zeros(region.physical_shape, dtype=np.bool_)
            if region.logical_count:
                valid[: region.sample_count, ..., : region.logical_count] = True
            tail = local[~valid]
            expected = (
                0
                if port == "P"
                else self._read_array(bundle, "y_zero_point", slice_id)[0]
            )
        else:
            return 0
        if tail.size and np.any(tail != expected):
            raise ValueError(f"Conv {port} semantic tail is corrupted")
        return int(tail.size)

    def validate(self, bundle: Conv28PhysicalBundle) -> dict[str, int | str]:
        plan = bundle.plan
        if (
            plan.contract != self.contract
            or plan.status != self.status
            or plan.target_family != self.target_family
            or plan.profile_id != self.profile_id
        ):
            raise ValueError("bundle identity does not match this RTL28 Conv layout")
        if (
            plan.geometry != self.geometry
            or plan.alignment != self.alignment
            or plan.geometry_status != self.geometry_status
            or plan.address_order_status != self.address_order_status
        ):
            raise ValueError("bundle geometry or candidate status differs from layout")
        expected_plan = self.plan(
            activation_shape=plan.activation_shape,
            weight_shape=plan.weight_shape,
            strides=plan.strides,
            pads=plan.pads,
            dilations=plan.dilations,
            group=plan.group,
        )
        if plan != expected_plan:
            raise ValueError("Conv physical plan differs from the frozen formula")
        if tuple(item.port for item in plan.ports) != PORT_ORDER:
            raise ValueError("Conv port order differs from the frozen interface")
        if len(bundle.placements) != len(PORT_ORDER):
            raise ValueError("Conv bundle placement count is invalid")
        if set(bundle.tensor_ids) != set(PORT_ORDER) or len(
            set(bundle.tensor_ids.values())
        ) != len(PORT_ORDER):
            raise ValueError("Conv tensor ID map is incomplete or ambiguous")
        for placement, port in zip(bundle.placements, plan.ports, strict=True):
            if (
                placement.port != port.port
                or placement.tensor_id != bundle.tensor_ids[port.port]
                or placement.logical_shape != port.logical_shape
                or placement.dtype != port.dtype
                or placement.owner_axis != port.owner_axis
                or placement.physical_axis_order != port.physical_axis_order
                or placement.tail_rule != port.tail_rule
            ):
                raise ValueError("Conv port placement differs from its plan")
        if len(bundle.regions) != len(PORT_ORDER) * self.geometry.slice_count:
            raise ValueError("Conv bundle must contain one region per port and slice")
        semantic_tail_elements = 0
        for slice_id in range(self.geometry.slice_count):
            previous_end = self.geometry.slice_base(slice_id)
            slice_end = previous_end + self.geometry.bytes_per_slice
            for port in plan.ports:
                region = bundle.region(port.port, slice_id)
                expected = self._owner_descriptor(plan, port, slice_id)
                for field in (
                    "active",
                    "group_id",
                    "owner_step",
                    "sample_start",
                    "sample_count",
                    "logical_start",
                    "logical_count",
                ):
                    if getattr(region, field) != expected[field]:
                        raise ValueError(
                            f"Conv region {port.port}:{slice_id} {field} drifted"
                        )
                if region.physical_shape != port.physical_shape:
                    raise ValueError("Conv region physical shape drifted")
                if (
                    region.tensor_id != bundle.tensor_ids[port.port]
                    or region.owner_axis != port.owner_axis
                    or region.payload_bytes != port.payload_bytes
                    or region.size_bytes != _align(port.payload_bytes, self.alignment)
                    or region.storage_sample_count != plan.storage_sample_count
                ):
                    raise ValueError("Conv region port metadata drifted")
                if region.base_address != self.geometry.slice_base(
                    slice_id
                ) + port.offset_bytes:
                    raise ValueError("Conv region base address drifted")
                if region.base_address % self.alignment:
                    raise ValueError(f"Conv port {port.port} is not aligned")
                if region.base_address < previous_end:
                    raise ValueError("Conv physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("Conv physical region crosses a slice boundary")
                if self.geometry.decode(region.base_address).slice_id != slice_id:
                    raise ValueError("Conv physical region decodes to another slice")
                payload = bundle.read(port.port, slice_id)
                if len(payload) != region.size_bytes:
                    raise ValueError("Conv payload length differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("Conv 128-bit alignment padding is corrupted")
                semantic_tail_elements += self._validate_tail(
                    bundle, port.port, slice_id
                )
                previous_end = region.base_address + region.size_bytes

        # Static K-owned data is intentionally copied to all seven HIGH rings.
        # Comparing raw payloads makes any single-copy corruption fail closed.
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            for port in ("B", "bias", "w_scale", "w_zero_point"):
                for owner_step in range(4):
                    copies = [
                        bundle.read(port, ring[owner_step])
                        for ring in HIGH_RING_OWNERS
                    ]
                    if any(candidate != copies[0] for candidate in copies[1:]):
                        raise ValueError(
                            f"Conv replicated static port {port} differs across groups"
                        )
        # Scalar comparison and all coverage checks are performed by inverse.
        self.inverse(bundle)
        return {
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "port_count": len(PORT_ORDER),
            "region_count": len(bundle.regions),
            "per_slice_used_bytes": plan.per_slice_used_bytes,
            "physical_bytes": sum(len(value) for value in bundle.payloads.values()),
            "semantic_tail_elements": semantic_tail_elements,
        }


__all__ = [
    "CONV28_LAYOUT_IDS",
    "PORT_ORDER",
    "Conv28PhysicalBundle",
    "Conv28PhysicalPlan",
    "Conv28PhysicalRegion",
    "Conv28PortPlacement",
    "Conv28PortPlan",
    "QLinearConvPhysicalLayout",
]
