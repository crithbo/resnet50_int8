"""Current RTL28 Quantize, Dequantize and zero-copy View layouts.

The default profile assigns the fixed batch of sixteen samples to seven HIGH
rings and partitions the feature/channel axis over each ring's four physical
owners.  The optional global profile partitions the feature axis over the
explicit 28-owner LOW ring.  Both mappings use the RTL lookup-table order;
numeric slice adjacency is never inferred.

The DRAM geometry and address order remain candidate evidence.  These classes
prove reversible software relayout and do not claim hardware approval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

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


Placement = Literal["feature_partition", "replicated"]

SIMPLE_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: "w4_simple_group4x7_28_candidate_v1",
    GLOBAL_RING28_PROFILE: "w4_simple_global_ring28_candidate_v1",
}
VIEW_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: (
        "w4_zero_copy_view_group4x7_28_candidate_v1"
    ),
    GLOBAL_RING28_PROFILE: "w4_zero_copy_view_global_ring28_candidate_v1",
}


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _little_endian(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


def _axis_order(rank: int) -> str:
    if rank == 2:
        return "NF-local"
    if rank == 4:
        return "NHWF-local"
    return "N-spatial-F-local"


@dataclass(frozen=True)
class Rtl28PortPlacement:
    port: str
    tensor_id: str
    logical_shape: tuple[int, ...]
    dtype: str
    placement: Placement
    feature_axis: int | None
    feature_tile: int | None
    physical_axis_order: str
    slot_payload_bytes: int
    padding_value: int | float


@dataclass(frozen=True)
class Rtl28PhysicalRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    physical_shape: tuple[int, ...]
    active: bool
    group_id: int | None
    owner_step: int | None
    sample_start: int
    sample_count: int
    storage_sample_count: int
    feature_start: int
    feature_count: int


@dataclass(frozen=True)
class Rtl28PhysicalBundle:
    operator: str
    contract: str
    status: str
    target_family: str
    profile_id: str
    geometry_status: str
    address_order_status: str
    geometry: DramGeometry
    alignment: int
    placements: tuple[Rtl28PortPlacement, ...]
    regions: tuple[Rtl28PhysicalRegion, ...]
    payloads: dict[tuple[str, int], bytes]

    def placement(self, tensor_id: str) -> Rtl28PortPlacement:
        matches = [item for item in self.placements if item.tensor_id == tensor_id]
        if len(matches) != 1:
            raise KeyError(f"expected one placement for tensor {tensor_id!r}")
        return matches[0]

    def region(self, port: str, slice_id: int) -> Rtl28PhysicalRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one region for port {port!r} on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        for placement in self.placements:
            bases = tuple(
                self.region(placement.port, slice_id).base_address
                for slice_id in range(self.geometry.slice_count)
            )
            if placement.placement == "replicated":
                partition = {
                    "axis": None,
                    "policy": "replicated_on_every_rtl28_slice",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                }
            elif self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                partition = {
                    "axis": 1,
                    "policy": "seven_high_groups_sample_and_feature_partition",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "batch_group_sample_counts": list(GROUP_SAMPLE_COUNTS),
                    "high_ring_owners": [list(item) for item in HIGH_RING_OWNERS],
                    "feature_tile": placement.feature_tile,
                    "storage_samples_per_owner": max(GROUP_SAMPLE_COUNTS),
                }
            else:
                partition = {
                    "axis": 1,
                    "policy": "global_low_ring_feature_partition",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "low_ring_owners": list(LOW_RING_OWNERS),
                    "feature_tile": placement.feature_tile,
                    "storage_samples_per_owner": BATCH_SIZE,
                }
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-{self.operator.lower()}-{placement.port.lower()}-"
                        f"{placement.tensor_id}"
                    ),
                    tensor_id=placement.tensor_id,
                    transform=self.contract,
                    contract_status=self.status,
                    port=placement.port,
                    logical_shape=placement.logical_shape,
                    logical_dtype=placement.dtype,
                    partition=partition,
                    packing={
                        "logical_order": "N,F,...",
                        "physical_order": placement.physical_axis_order,
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "subword_bytes": self.geometry.subword_bytes,
                        "padding_value": placement.padding_value,
                        "geometry_status": self.geometry_status,
                        "address_order_status": self.address_order_status,
                    },
                    base_addresses=bases,
                    inverse_status="validated",
                )
            )
        return tuple(records)


@dataclass(frozen=True)
class _PortInput:
    port: str
    tensor_id: str
    array: np.ndarray
    placement: Placement
    padding_value: int | float


class _Rtl28SimpleOperatorLayout:
    status = "candidate"
    target_family = "rtl28"
    geometry_status = "candidate_unapproved"
    address_order_status = "candidate_unapproved"

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE,
        geometry: DramGeometry | None = None,
        alignment: int = 16,
    ) -> None:
        self.profile_id = validate_profile_name(profile_id)
        self.geometry = geometry or TARGET_DRAM_GEOMETRY28
        if self.geometry != TARGET_DRAM_GEOMETRY28:
            raise ValueError("current simple layout requires TARGET_DRAM_GEOMETRY28")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment
        self.contract = SIMPLE_LAYOUT_IDS[self.profile_id]

    @staticmethod
    def _validate_feature_array(array: np.ndarray, port: str) -> None:
        if array.ndim < 2:
            raise ValueError(f"feature-partitioned port {port} must have rank >= 2")
        if array.shape[0] != BATCH_SIZE:
            raise ValueError(
                f"feature-partitioned port {port} requires batch={BATCH_SIZE}"
            )
        if any(int(value) <= 0 for value in array.shape):
            raise ValueError(f"feature-partitioned port {port} cannot have empty axes")

    def _feature_tile(self, feature_count: int) -> int:
        owners = 4 if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else 28
        return math.ceil(feature_count / owners)

    def _region_descriptor(
        self, placement: Rtl28PortPlacement, slice_id: int
    ) -> dict[str, int | tuple[int, ...] | bool | None]:
        if placement.placement == "replicated":
            return {
                "physical_shape": placement.logical_shape,
                "active": True,
                "group_id": None,
                "owner_step": None,
                "sample_start": 0,
                "sample_count": BATCH_SIZE,
                "storage_sample_count": BATCH_SIZE,
                "feature_start": 0,
                "feature_count": int(np.prod(placement.logical_shape)),
            }

        assert placement.feature_tile is not None
        feature_count = placement.logical_shape[1]
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id = TOPOLOGY28.group_for_slice(slice_id)
            ring = TOPOLOGY28.high_ring_for_group(group_id)
            owner_step = ring.owners.index(slice_id)
            sample_start = group_to_sample_range(group_id).start
            sample_count = GROUP_SAMPLE_COUNTS[group_id]
            storage_sample_count = max(GROUP_SAMPLE_COUNTS)
        else:
            group_id = None
            owner_step = LOW_RING_OWNERS.index(slice_id)
            sample_start = 0
            sample_count = BATCH_SIZE
            storage_sample_count = BATCH_SIZE
        feature_start = owner_step * placement.feature_tile
        valid_features = max(
            0, min(placement.feature_tile, feature_count - feature_start)
        )
        physical_shape = (
            storage_sample_count,
            *placement.logical_shape[2:],
            placement.feature_tile,
        )
        return {
            "physical_shape": physical_shape,
            "active": valid_features > 0,
            "group_id": group_id,
            "owner_step": owner_step,
            "sample_start": sample_start,
            "sample_count": sample_count,
            "storage_sample_count": storage_sample_count,
            "feature_start": feature_start,
            "feature_count": valid_features,
        }

    def _pack(
        self, operator: str, ports: tuple[_PortInput, ...]
    ) -> Rtl28PhysicalBundle:
        if not ports:
            raise ValueError("at least one port is required")
        if len({item.port for item in ports}) != len(ports):
            raise ValueError("port names must be unique")
        if len({item.tensor_id for item in ports}) != len(ports):
            raise ValueError("tensor IDs must be unique within an operator bundle")

        canonical: dict[str, np.ndarray] = {}
        placements: list[Rtl28PortPlacement] = []
        offsets: dict[str, int] = {}
        cursor = 0
        for item in ports:
            array = np.asarray(item.array)
            if array.dtype.hasobject:
                raise TypeError(f"port {item.port} cannot contain object values")
            if item.placement == "feature_partition":
                self._validate_feature_array(array, item.port)
                feature_tile = self._feature_tile(int(array.shape[1]))
                storage_samples = (
                    max(GROUP_SAMPLE_COUNTS)
                    if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                    else BATCH_SIZE
                )
                physical_shape = (
                    storage_samples,
                    *tuple(int(value) for value in array.shape[2:]),
                    feature_tile,
                )
                slot_payload_bytes = math.prod(physical_shape) * array.dtype.itemsize
                physical_axis_order = _axis_order(array.ndim)
            else:
                if array.size == 0:
                    raise ValueError(f"replicated port {item.port} cannot be empty")
                feature_tile = None
                slot_payload_bytes = int(array.nbytes)
                physical_axis_order = "replicated-scalar"
            canonical[item.port] = _little_endian(array)
            cursor = _align(cursor, self.alignment)
            offsets[item.port] = cursor
            cursor += _align(slot_payload_bytes, self.alignment)
            placements.append(
                Rtl28PortPlacement(
                    port=item.port,
                    tensor_id=item.tensor_id,
                    logical_shape=tuple(int(value) for value in array.shape),
                    dtype=str(array.dtype),
                    placement=item.placement,
                    feature_axis=1 if item.placement == "feature_partition" else None,
                    feature_tile=feature_tile,
                    physical_axis_order=physical_axis_order,
                    slot_payload_bytes=slot_payload_bytes,
                    padding_value=item.padding_value,
                )
            )
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("RTL28 simple-op physical regions exceed one slice capacity")

        regions: list[Rtl28PhysicalRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for item, placement in zip(ports, placements, strict=True):
            array = canonical[item.port]
            aligned_size = _align(placement.slot_payload_bytes, self.alignment)
            for slice_id in range(self.geometry.slice_count):
                descriptor = self._region_descriptor(placement, slice_id)
                physical_shape = tuple(descriptor["physical_shape"])
                if placement.placement == "replicated":
                    raw = array.tobytes(order="C")
                else:
                    local = np.full(
                        physical_shape,
                        placement.padding_value,
                        dtype=array.dtype,
                    )
                    sample_count = int(descriptor["sample_count"])
                    feature_count = int(descriptor["feature_count"])
                    if feature_count:
                        sample_start = int(descriptor["sample_start"])
                        feature_start = int(descriptor["feature_start"])
                        source = array[
                            sample_start : sample_start + sample_count,
                            feature_start : feature_start + feature_count,
                            ...,
                        ]
                        local[:sample_count, ..., :feature_count] = np.moveaxis(
                            source, 1, -1
                        )
                    raw = local.tobytes(order="C")
                if len(raw) != placement.slot_payload_bytes:
                    raise AssertionError("physical payload size calculation drifted")
                payload = raw + bytes(aligned_size - len(raw))
                payloads[(item.port, slice_id)] = payload
                regions.append(
                    Rtl28PhysicalRegion(
                        port=item.port,
                        tensor_id=item.tensor_id,
                        slice_id=slice_id,
                        base_address=self.geometry.slice_base(slice_id)
                        + offsets[item.port],
                        payload_bytes=placement.slot_payload_bytes,
                        size_bytes=aligned_size,
                        physical_shape=physical_shape,
                        active=bool(descriptor["active"]),
                        group_id=descriptor["group_id"],
                        owner_step=descriptor["owner_step"],
                        sample_start=int(descriptor["sample_start"]),
                        sample_count=int(descriptor["sample_count"]),
                        storage_sample_count=int(descriptor["storage_sample_count"]),
                        feature_start=int(descriptor["feature_start"]),
                        feature_count=int(descriptor["feature_count"]),
                    )
                )
        bundle = Rtl28PhysicalBundle(
            operator=operator,
            contract=self.contract,
            status=self.status,
            target_family=self.target_family,
            profile_id=self.profile_id,
            geometry_status=self.geometry_status,
            address_order_status=self.address_order_status,
            geometry=self.geometry,
            alignment=self.alignment,
            placements=tuple(placements),
            regions=tuple(regions),
            payloads=payloads,
        )
        self.validate(bundle)
        return bundle

    def inverse_port(
        self, bundle: Rtl28PhysicalBundle, tensor_id: str
    ) -> np.ndarray:
        placement = bundle.placement(tensor_id)
        dtype = np.dtype(placement.dtype).newbyteorder("<")
        if placement.placement == "replicated":
            arrays = [
                np.frombuffer(
                    bundle.read(placement.port, slice_id)[
                        : placement.slot_payload_bytes
                    ],
                    dtype=dtype,
                ).reshape(placement.logical_shape)
                for slice_id in range(bundle.geometry.slice_count)
            ]
            for candidate in arrays[1:]:
                if not np.array_equal(candidate, arrays[0]):
                    raise ValueError(f"replicated tensor {tensor_id} differs between slices")
            return arrays[0].astype(np.dtype(placement.dtype), copy=True)

        output = np.empty(placement.logical_shape, dtype=dtype)
        coverage = np.zeros(placement.logical_shape[:2], dtype=np.bool_)
        for slice_id in range(bundle.geometry.slice_count):
            region = bundle.region(placement.port, slice_id)
            if not region.feature_count:
                continue
            local = np.frombuffer(
                bundle.read(placement.port, slice_id)[: region.payload_bytes],
                dtype=dtype,
            ).reshape(region.physical_shape)
            block = np.moveaxis(
                local[: region.sample_count, ..., : region.feature_count], -1, 1
            )
            sample_stop = region.sample_start + region.sample_count
            feature_stop = region.feature_start + region.feature_count
            output[
                region.sample_start:sample_stop,
                region.feature_start:feature_stop,
                ...,
            ] = block
            if coverage[
                region.sample_start:sample_stop,
                region.feature_start:feature_stop,
            ].any():
                raise ValueError("feature owner ranges overlap")
            coverage[
                region.sample_start:sample_stop,
                region.feature_start:feature_stop,
            ] = True
        if not coverage.all():
            raise ValueError("feature owner ranges do not cover the logical tensor")
        return output.astype(np.dtype(placement.dtype), copy=True)

    def inverse(self, bundle: Rtl28PhysicalBundle) -> dict[str, np.ndarray]:
        return {
            placement.tensor_id: self.inverse_port(bundle, placement.tensor_id)
            for placement in bundle.placements
        }

    def _coordinate_owner(
        self, placement: Rtl28PortPlacement, coordinate: tuple[int, ...]
    ) -> tuple[int, tuple[int, ...]]:
        assert placement.feature_tile is not None
        sample_id, feature_id = coordinate[:2]
        owner_step = feature_id // placement.feature_tile
        local_feature = feature_id % placement.feature_tile
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            assignment = sample_to_group(sample_id)
            slice_id = HIGH_RING_OWNERS[assignment.group_id][owner_step]
            local_sample = assignment.local_slot
        else:
            slice_id = LOW_RING_OWNERS[owner_step]
            local_sample = sample_id
        return slice_id, (local_sample, *coordinate[2:], local_feature)

    def explain_coordinate(
        self,
        bundle: Rtl28PhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, object], ...]:
        placement = bundle.placement(tensor_id)
        if len(coordinate) != len(placement.logical_shape):
            raise ValueError("coordinate rank does not match logical tensor rank")
        if any(
            index < 0 or index >= size
            for index, size in zip(coordinate, placement.logical_shape, strict=True)
        ):
            raise IndexError("logical coordinate is out of range")
        dtype = np.dtype(placement.dtype)
        if placement.placement == "replicated":
            slice_ids = tuple(range(bundle.geometry.slice_count))
            local_coordinate = coordinate
        else:
            slice_id, local_coordinate = self._coordinate_owner(placement, coordinate)
            slice_ids = (slice_id,)
        element_index = int(
            np.ravel_multi_index(
                local_coordinate,
                bundle.region(placement.port, slice_ids[0]).physical_shape,
            )
        )
        byte_offset = element_index * dtype.itemsize
        explanations: list[dict[str, object]] = []
        for slice_id in slice_ids:
            region = bundle.region(placement.port, slice_id)
            for element_byte in range(dtype.itemsize):
                address = region.base_address + byte_offset + element_byte
                explanations.append(
                    {
                        "tensor_id": tensor_id,
                        "port": placement.port,
                        "logical_coordinate": coordinate,
                        "profile_id": self.profile_id,
                        "slice_id": slice_id,
                        "group_id": region.group_id,
                        "owner_step": region.owner_step,
                        "physical_coordinate": local_coordinate,
                        "address": address,
                        "dram_coordinate": bundle.geometry.decode(address),
                        "element_byte": element_byte,
                        "semantic": (
                            "replicated_qparam"
                            if placement.placement == "replicated"
                            else "data"
                        ),
                    }
                )
        return tuple(explanations)

    def validate(self, bundle: Rtl28PhysicalBundle) -> dict[str, int | str]:
        if (
            bundle.contract != self.contract
            or bundle.status != self.status
            or bundle.target_family != self.target_family
            or bundle.profile_id != self.profile_id
        ):
            raise ValueError("bundle identity does not match this RTL28 layout")
        if (
            bundle.geometry != self.geometry
            or bundle.alignment != self.alignment
            or bundle.geometry_status != self.geometry_status
            or bundle.address_order_status != self.address_order_status
        ):
            raise ValueError("bundle geometry or candidate status differs from layout")
        expected_regions = len(bundle.placements) * bundle.geometry.slice_count
        if len(bundle.regions) != expected_regions:
            raise ValueError("bundle does not contain one region per port and slice")

        tail_bytes = 0
        for slice_id in range(bundle.geometry.slice_count):
            previous_end = bundle.geometry.slice_base(slice_id)
            slice_end = previous_end + bundle.geometry.bytes_per_slice
            for placement in bundle.placements:
                region = bundle.region(placement.port, slice_id)
                payload = bundle.read(placement.port, slice_id)
                expected = self._region_descriptor(placement, slice_id)
                for field in (
                    "physical_shape",
                    "active",
                    "group_id",
                    "owner_step",
                    "sample_start",
                    "sample_count",
                    "storage_sample_count",
                    "feature_start",
                    "feature_count",
                ):
                    if getattr(region, field) != expected[field]:
                        raise ValueError(f"region {placement.port}:{slice_id} {field} drifted")
                if region.base_address % self.alignment:
                    raise ValueError(f"port {placement.port} is not aligned")
                if region.base_address < previous_end:
                    raise ValueError("RTL28 simple-op physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("physical region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("physical payload size differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("128-bit alignment padding is corrupted")
                if placement.placement == "feature_partition":
                    dtype = np.dtype(placement.dtype).newbyteorder("<")
                    local = np.frombuffer(
                        payload[: region.payload_bytes], dtype=dtype
                    ).reshape(region.physical_shape)
                    valid = np.zeros(region.physical_shape, dtype=np.bool_)
                    if region.feature_count:
                        valid[
                            : region.sample_count, ..., : region.feature_count
                        ] = True
                    padding = local[~valid]
                    if padding.size and not np.all(
                        padding == np.asarray(placement.padding_value, dtype=dtype)
                    ):
                        raise ValueError(
                            f"feature/sample tail for {placement.tensor_id} is corrupted"
                        )
                    tail_bytes += int(padding.nbytes)
                previous_end = region.base_address + region.size_bytes
        self.inverse(bundle)
        return {
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "slice_count": bundle.geometry.slice_count,
            "port_count": len(bundle.placements),
            "region_count": len(bundle.regions),
            "physical_bytes": sum(len(value) for value in bundle.payloads.values()),
            "tail_bytes": tail_bytes,
        }


class QuantizeLinearPhysicalLayout(_Rtl28SimpleOperatorLayout):
    def forward(
        self,
        *,
        input_tensor: np.ndarray,
        scale: np.ndarray,
        zero_point: np.ndarray,
        output_tensor: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
    ) -> Rtl28PhysicalBundle:
        ids = {
            "A": "quantize_input",
            "scale": "quantize_scale",
            "zero_point": "quantize_zero_point",
            "D": "quantize_output",
            **(tensor_ids or {}),
        }
        input_tensor = np.asarray(input_tensor)
        scale = np.asarray(scale)
        zero_point = np.asarray(zero_point)
        output_tensor = np.asarray(output_tensor)
        if input_tensor.dtype != np.float32:
            raise TypeError("QuantizeLinear input must be float32")
        if (
            scale.dtype != np.float32
            or scale.shape != (1,)
            or not np.isfinite(scale[0])
            or scale[0] <= 0
        ):
            raise TypeError("QuantizeLinear scale must be one positive finite float32")
        if zero_point.dtype != np.uint8 or zero_point.shape != (1,):
            raise TypeError("QuantizeLinear zero_point must be scalar uint8 with shape (1,)")
        if output_tensor.dtype != np.uint8 or output_tensor.shape != input_tensor.shape:
            raise TypeError("QuantizeLinear output must be uint8 with the input shape")
        return self._pack(
            "QuantizeLinear",
            (
                _PortInput("A", ids["A"], input_tensor, "feature_partition", 0.0),
                _PortInput("scale", ids["scale"], scale, "replicated", 0.0),
                _PortInput(
                    "zero_point", ids["zero_point"], zero_point, "replicated", 0
                ),
                _PortInput(
                    "D",
                    ids["D"],
                    output_tensor,
                    "feature_partition",
                    int(zero_point[0]),
                ),
            ),
        )


class DequantizeLinearPhysicalLayout(_Rtl28SimpleOperatorLayout):
    def forward(
        self,
        *,
        input_tensor: np.ndarray,
        scale: np.ndarray,
        zero_point: np.ndarray,
        output_tensor: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
    ) -> Rtl28PhysicalBundle:
        ids = {
            "A": "dequantize_input",
            "scale": "dequantize_scale",
            "zero_point": "dequantize_zero_point",
            "D": "dequantize_output",
            **(tensor_ids or {}),
        }
        input_tensor = np.asarray(input_tensor)
        scale = np.asarray(scale)
        zero_point = np.asarray(zero_point)
        output_tensor = np.asarray(output_tensor)
        if input_tensor.dtype != np.uint8:
            raise TypeError("DequantizeLinear input must be uint8")
        if (
            scale.dtype != np.float32
            or scale.shape != (1,)
            or not np.isfinite(scale[0])
            or scale[0] <= 0
        ):
            raise TypeError("DequantizeLinear scale must be one positive finite float32")
        if zero_point.dtype != np.uint8 or zero_point.shape != (1,):
            raise TypeError("DequantizeLinear zero_point must be scalar uint8 with shape (1,)")
        if output_tensor.dtype != np.float32 or output_tensor.shape != input_tensor.shape:
            raise TypeError("DequantizeLinear output must be float32 with the input shape")
        return self._pack(
            "DequantizeLinear",
            (
                _PortInput(
                    "A",
                    ids["A"],
                    input_tensor,
                    "feature_partition",
                    int(zero_point[0]),
                ),
                _PortInput("scale", ids["scale"], scale, "replicated", 0.0),
                _PortInput(
                    "zero_point", ids["zero_point"], zero_point, "replicated", 0
                ),
                _PortInput("D", ids["D"], output_tensor, "feature_partition", 0.0),
            ),
        )


@dataclass(frozen=True)
class ZeroCopyViewProof:
    source_bundle: Rtl28PhysicalBundle
    source_tensor_id: str
    output_tensor_id: str
    input_shape: tuple[int, ...]
    output_shape: tuple[int, ...]
    dtype: str
    axis: int
    profile_id: str
    contract: str
    status: str = "candidate"

    def layout_record(self) -> LayoutRecord:
        placement = self.source_bundle.placement(self.source_tensor_id)
        bases = tuple(
            self.source_bundle.region(placement.port, slice_id).base_address
            for slice_id in range(self.source_bundle.geometry.slice_count)
        )
        source = next(
            item
            for item in self.source_bundle.layout_records()
            if item.tensor_id == self.source_tensor_id
        )
        return LayoutRecord(
            layout_id=f"layout-view-{self.output_tensor_id}",
            tensor_id=self.output_tensor_id,
            transform=self.contract,
            contract_status=self.status,
            port=placement.port,
            logical_shape=self.output_shape,
            logical_dtype=self.dtype,
            partition={
                **source.partition,
                "policy": "zero_copy_alias_of_rtl28_feature_partition",
            },
            packing={
                **source.packing,
                "physical_order": "NF-local",
                "zero_copy": True,
            },
            base_addresses=bases,
            inverse_status="validated",
            alias_of=self.source_tensor_id,
        )


class ZeroCopyViewLayout:
    status = "candidate"

    def __init__(self, profile_id: str = DEFAULT_PROFILE) -> None:
        self.profile_id = validate_profile_name(profile_id)
        self.contract = VIEW_LAYOUT_IDS[self.profile_id]

    def forward(
        self,
        *,
        source_bundle: Rtl28PhysicalBundle,
        source_tensor_id: str,
        output_tensor_id: str,
        output_shape: tuple[int, ...],
        axis: int = 1,
    ) -> ZeroCopyViewProof:
        if source_bundle.profile_id != self.profile_id:
            raise ValueError("View profile must match its source bundle")
        placement = source_bundle.placement(source_tensor_id)
        if placement.placement != "feature_partition":
            raise ValueError("zero-copy View source must use feature partitioning")
        input_shape = placement.logical_shape
        rank = len(input_shape)
        normalized_axis = axis + rank if axis < 0 else axis
        if normalized_axis != 1:
            raise ValueError("RTL28 zero-copy View requires axis=1")
        if rank < 3 or any(size != 1 for size in input_shape[2:]):
            raise ValueError(
                "RTL28 zero-copy View only removes singleton spatial dimensions"
            )
        expected = (input_shape[0], input_shape[1])
        if tuple(output_shape) != expected:
            raise ValueError(f"View output shape must be {expected}, got {output_shape}")
        proof = ZeroCopyViewProof(
            source_bundle=source_bundle,
            source_tensor_id=source_tensor_id,
            output_tensor_id=output_tensor_id,
            input_shape=input_shape,
            output_shape=tuple(output_shape),
            dtype=placement.dtype,
            axis=normalized_axis,
            profile_id=self.profile_id,
            contract=self.contract,
        )
        self.validate(proof)
        return proof

    def inverse(self, proof: ZeroCopyViewProof) -> dict[str, np.ndarray]:
        helper = _Rtl28SimpleOperatorLayout(profile_id=proof.profile_id)
        source = helper.inverse_port(proof.source_bundle, proof.source_tensor_id)
        output = source.reshape(proof.output_shape)
        return {
            proof.source_tensor_id: output.reshape(proof.input_shape).copy(),
            proof.output_tensor_id: output.copy(),
        }

    def explain_coordinate(
        self, proof: ZeroCopyViewProof, coordinate: tuple[int, ...]
    ) -> tuple[dict[str, object], ...]:
        if len(coordinate) != 2:
            raise ValueError("Flatten output coordinate must have rank 2")
        if any(
            index < 0 or index >= size
            for index, size in zip(coordinate, proof.output_shape, strict=True)
        ):
            raise IndexError("Flatten output coordinate is out of range")
        source_coordinate = (
            coordinate[0],
            coordinate[1],
            *([0] * (len(proof.input_shape) - 2)),
        )
        helper = _Rtl28SimpleOperatorLayout(profile_id=proof.profile_id)
        result = helper.explain_coordinate(
            proof.source_bundle, proof.source_tensor_id, source_coordinate
        )
        return tuple(
            {
                **item,
                "tensor_id": proof.output_tensor_id,
                "logical_coordinate": coordinate,
                "source_tensor_id": proof.source_tensor_id,
                "source_coordinate": source_coordinate,
                "semantic": "zero_copy_alias",
            }
            for item in result
        )

    def validate(self, proof: ZeroCopyViewProof) -> dict[str, int | bool | str]:
        if (
            proof.contract != self.contract
            or proof.status != self.status
            or proof.profile_id != self.profile_id
        ):
            raise ValueError("unsupported zero-copy View contract")
        if proof.source_bundle.profile_id != self.profile_id or proof.axis != 1:
            raise ValueError("View proof is incompatible with the RTL28 source profile")
        placement = proof.source_bundle.placement(proof.source_tensor_id)
        if placement.placement != "feature_partition":
            raise ValueError("View proof source is not feature-partitioned")
        if (
            len(proof.input_shape) < 3
            or any(size != 1 for size in proof.input_shape[2:])
            or proof.output_shape != (proof.input_shape[0], proof.input_shape[1])
        ):
            raise ValueError("View changes non-singleton physical storage")
        helper = _Rtl28SimpleOperatorLayout(profile_id=proof.profile_id)
        helper.validate(proof.source_bundle)
        recovered = self.inverse(proof)
        if recovered[proof.source_tensor_id].tobytes(order="C") != recovered[
            proof.output_tensor_id
        ].tobytes(order="C"):
            raise ValueError("View alias changes the physical byte order")
        return {
            "zero_copy": True,
            "target_family": "rtl28",
            "profile_id": self.profile_id,
            "slice_count": proof.source_bundle.geometry.slice_count,
            "aliased_bytes": int(recovered[proof.output_tensor_id].nbytes),
        }


__all__ = [
    "DequantizeLinearPhysicalLayout",
    "QuantizeLinearPhysicalLayout",
    "Rtl28PhysicalBundle",
    "Rtl28PhysicalRegion",
    "Rtl28PortPlacement",
    "SIMPLE_LAYOUT_IDS",
    "VIEW_LAYOUT_IDS",
    "ZeroCopyViewLayout",
    "ZeroCopyViewProof",
]
