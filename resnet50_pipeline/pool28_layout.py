"""Reversible RTL28 MaxPool and quantized GlobalAveragePool layouts.

The layouts in this module are software candidates.  They use the explicit
RTL HIGH/LOW owner sequences and the frozen 28-slice geometry, but neither the
geometry nor the address order is presented as hardware-approved.
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
from .simple_layout import Rtl28PhysicalRegion, Rtl28PortPlacement
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


Placement = Literal["feature_partition", "replicated"]

MAXPOOL_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: "w4_maxpool_group4x7_28_candidate_v1",
    GLOBAL_RING28_PROFILE: "w4_maxpool_global_ring28_candidate_v1",
}
GLOBAL_AVERAGE_POOL_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: (
        "w4_globalavgpool_group4x7_28_candidate_v1"
    ),
    GLOBAL_RING28_PROFILE: "w4_globalavgpool_global_ring28_candidate_v1",
}

_HIGH_OWNER_LOCATION = {
    slice_id: (group_id, owner_step)
    for group_id, owners in enumerate(HIGH_RING_OWNERS)
    for owner_step, slice_id in enumerate(owners)
}


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _plain_positive_pair(value: object, label: str) -> tuple[int, int]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{label} must contain two integers") from exc
    if len(items) != 2 or any(
        isinstance(item, bool) or not isinstance(item, (int, np.integer))
        for item in items
    ):
        raise TypeError(f"{label} must contain two integers")
    result = tuple(int(item) for item in items)
    if any(item <= 0 for item in result):
        raise ValueError(f"{label} values must be positive")
    return result  # type: ignore[return-value]


def _pads(value: object) -> tuple[int, int, int, int]:
    try:
        items = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("pads must contain four integers") from exc
    if len(items) != 4 or any(
        isinstance(item, bool) or not isinstance(item, (int, np.integer))
        for item in items
    ):
        raise TypeError("pads must contain four integers")
    result = tuple(int(item) for item in items)
    if any(item < 0 for item in result):
        raise ValueError("pads values must be non-negative")
    return result  # type: ignore[return-value]


def _shape4(value: object, label: str) -> tuple[int, int, int, int]:
    try:
        shape = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{label} must be a rank-4 shape") from exc
    if len(shape) != 4 or any(
        isinstance(item, bool) or not isinstance(item, (int, np.integer))
        for item in shape
    ):
        raise TypeError(f"{label} must be a rank-4 integer shape")
    result = tuple(int(item) for item in shape)
    if any(item <= 0 for item in result):
        raise ValueError(f"{label} dimensions must be positive")
    if result[0] != BATCH_SIZE:
        raise ValueError(f"{label} requires batch={BATCH_SIZE}")
    return result  # type: ignore[return-value]


def _little_endian(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


def _physical_axis_order(rank: int) -> str:
    if rank == 2:
        return "NF-local"
    if rank == 4:
        return "NHWF-local"
    return "N-spatial-F-local"


@dataclass(frozen=True)
class PoolPhysicalBundle:
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
    metadata: dict[str, Any]

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
            raise KeyError(f"expected one {port!r} region on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        for placement in self.placements:
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
                    "policy": "seven_high_groups_sample_and_channel_partition",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "batch_group_sample_counts": list(GROUP_SAMPLE_COUNTS),
                    "high_ring_owners": [list(item) for item in HIGH_RING_OWNERS],
                    "channel_tile": placement.feature_tile,
                    "storage_samples_per_owner": max(GROUP_SAMPLE_COUNTS),
                }
            else:
                partition = {
                    "axis": 1,
                    "policy": "global_low_ring_channel_partition",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "low_ring_owners": list(LOW_RING_OWNERS),
                    "channel_tile": placement.feature_tile,
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
                        "logical_order": "N,C,...",
                        "physical_order": placement.physical_axis_order,
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "padding_value": placement.padding_value,
                        "geometry_status": self.geometry_status,
                        "address_order_status": self.address_order_status,
                        "pool_semantics": self.metadata["semantics"],
                    },
                    base_addresses=tuple(
                        self.region(placement.port, slice_id).base_address
                        for slice_id in range(self.geometry.slice_count)
                    ),
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


class _Rtl28PoolLayout:
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
            raise ValueError("current Pool layout requires TARGET_DRAM_GEOMETRY28")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment

    def _channel_tile(self, channels: int) -> int:
        owners = 4 if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else 28
        return math.ceil(channels / owners)

    def _storage_samples(self) -> int:
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            return max(GROUP_SAMPLE_COUNTS)
        return BATCH_SIZE

    def _descriptor(
        self, placement: Rtl28PortPlacement, slice_id: int
    ) -> dict[str, Any]:
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
        channels = placement.logical_shape[1]
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id, owner_step = _HIGH_OWNER_LOCATION[slice_id]
            sample_range = group_to_sample_range(group_id)
            sample_start = sample_range.start
            sample_count = sample_range.sample_count
            storage_sample_count = max(GROUP_SAMPLE_COUNTS)
        else:
            group_id = None
            owner_step = LOW_RING_OWNERS.index(slice_id)
            sample_start = 0
            sample_count = BATCH_SIZE
            storage_sample_count = BATCH_SIZE
        feature_start = owner_step * placement.feature_tile
        feature_count = max(
            0, min(placement.feature_tile, channels - feature_start)
        )
        return {
            "physical_shape": (
                storage_sample_count,
                *placement.logical_shape[2:],
                placement.feature_tile,
            ),
            "active": feature_count > 0,
            "group_id": group_id,
            "owner_step": owner_step,
            "sample_start": sample_start,
            "sample_count": sample_count,
            "storage_sample_count": storage_sample_count,
            "feature_start": feature_start,
            "feature_count": feature_count,
        }

    def _placement_for(self, item: _PortInput) -> Rtl28PortPlacement:
        array = np.asarray(item.array)
        if array.dtype.hasobject:
            raise TypeError(f"port {item.port} cannot contain object values")
        if item.placement == "feature_partition":
            if array.ndim not in {2, 4}:
                raise ValueError(f"port {item.port} must be rank-2 or rank-4")
            if array.shape[0] != BATCH_SIZE or any(
                int(value) <= 0 for value in array.shape
            ):
                raise ValueError(
                    f"port {item.port} requires non-empty batch={BATCH_SIZE}"
                )
            tile = self._channel_tile(int(array.shape[1]))
            physical_shape = (
                self._storage_samples(), *array.shape[2:], tile
            )
            payload_bytes = math.prod(physical_shape) * array.dtype.itemsize
            axis_order = _physical_axis_order(array.ndim)
        else:
            if array.size == 0:
                raise ValueError(f"replicated port {item.port} cannot be empty")
            tile = None
            payload_bytes = int(array.nbytes)
            axis_order = "replicated-scalar"
        return Rtl28PortPlacement(
            port=item.port,
            tensor_id=item.tensor_id,
            logical_shape=tuple(int(value) for value in array.shape),
            dtype=str(array.dtype),
            placement=item.placement,
            feature_axis=1 if item.placement == "feature_partition" else None,
            feature_tile=tile,
            physical_axis_order=axis_order,
            slot_payload_bytes=payload_bytes,
            padding_value=item.padding_value,
        )

    def _offsets(
        self, placements: tuple[Rtl28PortPlacement, ...], input_offset: int = 0
    ) -> tuple[dict[str, int], int]:
        if input_offset < 0 or input_offset % self.alignment:
            raise ValueError("input_offset must be non-negative and aligned")
        offsets: dict[str, int] = {}
        cursor = input_offset
        for placement in placements:
            cursor = _align(cursor, self.alignment)
            offsets[placement.port] = cursor
            cursor += _align(placement.slot_payload_bytes, self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError(
                f"RTL28 Pool regions need {cursor} bytes per slice, capacity is "
                f"{self.geometry.bytes_per_slice}"
            )
        return offsets, cursor

    def _pack(
        self,
        *,
        operator: str,
        contract: str,
        ports: tuple[_PortInput, ...],
        metadata: dict[str, Any],
    ) -> PoolPhysicalBundle:
        if not ports:
            raise ValueError("at least one Pool port is required")
        if len({item.port for item in ports}) != len(ports):
            raise ValueError("Pool port names must be unique")
        if len({item.tensor_id for item in ports}) != len(ports):
            raise ValueError("Pool tensor IDs must be unique")
        placements = tuple(self._placement_for(item) for item in ports)
        offsets, used_bytes = self._offsets(placements)
        canonical = {item.port: _little_endian(np.asarray(item.array)) for item in ports}
        regions: list[Rtl28PhysicalRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for item, placement in zip(ports, placements, strict=True):
            array = canonical[item.port]
            aligned_size = _align(placement.slot_payload_bytes, self.alignment)
            for slice_id in range(self.geometry.slice_count):
                descriptor = self._descriptor(placement, slice_id)
                physical_shape = tuple(descriptor["physical_shape"])
                if placement.placement == "replicated":
                    raw = array.tobytes(order="C")
                else:
                    local = np.full(
                        physical_shape, placement.padding_value, dtype=array.dtype
                    )
                    if descriptor["feature_count"]:
                        n0 = descriptor["sample_start"]
                        nc = descriptor["sample_count"]
                        c0 = descriptor["feature_start"]
                        cc = descriptor["feature_count"]
                        source = array[n0 : n0 + nc, c0 : c0 + cc, ...]
                        local[:nc, ..., :cc] = np.moveaxis(source, 1, -1)
                    raw = local.tobytes(order="C")
                if len(raw) != placement.slot_payload_bytes:
                    raise AssertionError("Pool payload size calculation drifted")
                payloads[(item.port, slice_id)] = raw + bytes(
                    aligned_size - len(raw)
                )
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
                        storage_sample_count=int(
                            descriptor["storage_sample_count"]
                        ),
                        feature_start=int(descriptor["feature_start"]),
                        feature_count=int(descriptor["feature_count"]),
                    )
                )
        bundle = PoolPhysicalBundle(
            operator=operator,
            contract=contract,
            status=self.status,
            target_family=self.target_family,
            profile_id=self.profile_id,
            geometry_status=self.geometry_status,
            address_order_status=self.address_order_status,
            geometry=self.geometry,
            alignment=self.alignment,
            placements=placements,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                **metadata,
                "port_order": tuple(item.port for item in ports),
                "offsets": offsets,
                "per_slice_used_bytes": used_bytes,
                "capacity_bytes": self.geometry.bytes_per_slice,
            },
        )
        self.validate(bundle)
        return bundle

    def inverse_port(self, bundle: PoolPhysicalBundle, tensor_id: str) -> np.ndarray:
        placement = bundle.placement(tensor_id)
        dtype = np.dtype(placement.dtype).newbyteorder("<")
        if placement.placement == "replicated":
            values = [
                np.frombuffer(
                    bundle.read(placement.port, slice_id)[
                        : placement.slot_payload_bytes
                    ],
                    dtype=dtype,
                ).reshape(placement.logical_shape)
                for slice_id in range(bundle.geometry.slice_count)
            ]
            for candidate in values[1:]:
                if not np.array_equal(candidate, values[0]):
                    raise ValueError(
                        f"replicated Pool port {placement.port} differs between slices"
                    )
            return values[0].astype(np.dtype(placement.dtype), copy=True)

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
            n1 = region.sample_start + region.sample_count
            c1 = region.feature_start + region.feature_count
            logical_range = np.s_[
                region.sample_start:n1, region.feature_start:c1, ...
            ]
            coverage_range = np.s_[
                region.sample_start:n1, region.feature_start:c1
            ]
            if coverage[coverage_range].any():
                raise ValueError("Pool owner ranges overlap")
            output[logical_range] = block
            coverage[coverage_range] = True
        if not coverage.all():
            raise ValueError("Pool owner ranges do not cover the logical tensor")
        return output.astype(np.dtype(placement.dtype), copy=True)

    def inverse(self, bundle: PoolPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            placement.tensor_id: self.inverse_port(bundle, placement.tensor_id)
            for placement in bundle.placements
        }

    def explain_coordinate(
        self,
        bundle: PoolPhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        placement = bundle.placement(tensor_id)
        if len(coordinate) != len(placement.logical_shape):
            raise ValueError("coordinate rank does not match Pool tensor rank")
        if any(
            index < 0 or index >= size
            for index, size in zip(
                coordinate, placement.logical_shape, strict=True
            )
        ):
            raise IndexError("Pool logical coordinate is out of range")
        if placement.placement == "replicated":
            slice_ids = tuple(range(bundle.geometry.slice_count))
            physical_coordinate = coordinate
        else:
            assert placement.feature_tile is not None
            sample_id, channel_id = coordinate[:2]
            owner_step = channel_id // placement.feature_tile
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                assignment = sample_to_group(sample_id)
                slice_id = HIGH_RING_OWNERS[assignment.group_id][owner_step]
                local_sample = assignment.local_slot
            else:
                slice_id = LOW_RING_OWNERS[owner_step]
                local_sample = sample_id
            slice_ids = (slice_id,)
            physical_coordinate = (
                local_sample, *coordinate[2:], channel_id % placement.feature_tile
            )
        dtype = np.dtype(placement.dtype)
        first_region = bundle.region(placement.port, slice_ids[0])
        element_index = int(
            np.ravel_multi_index(
                physical_coordinate, first_region.physical_shape
            )
        )
        explanations: list[dict[str, Any]] = []
        for slice_id in slice_ids:
            region = bundle.region(placement.port, slice_id)
            for element_byte in range(dtype.itemsize):
                address = (
                    region.base_address
                    + element_index * dtype.itemsize
                    + element_byte
                )
                explanations.append(
                    {
                        "tensor_id": tensor_id,
                        "port": placement.port,
                        "logical_coordinate": coordinate,
                        "profile_id": self.profile_id,
                        "slice_id": slice_id,
                        "group_id": region.group_id,
                        "owner_step": region.owner_step,
                        "physical_coordinate": physical_coordinate,
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

    def validate(self, bundle: PoolPhysicalBundle) -> dict[str, int | str]:
        if (
            bundle.status != self.status
            or bundle.target_family != self.target_family
            or bundle.profile_id != self.profile_id
            or bundle.geometry_status != self.geometry_status
            or bundle.address_order_status != self.address_order_status
        ):
            raise ValueError("Pool bundle identity or candidate status drifted")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("Pool bundle does not use the frozen RTL28 geometry")
        port_order = tuple(bundle.metadata.get("port_order", ()))
        if port_order != tuple(item.port for item in bundle.placements):
            raise ValueError("Pool port order differs from its placements")
        if len(bundle.regions) != len(bundle.placements) * 28:
            raise ValueError("Pool bundle requires one region per port and RTL28 slice")
        offsets, used_bytes = self._offsets(bundle.placements)
        if (
            bundle.metadata.get("offsets") != offsets
            or bundle.metadata.get("per_slice_used_bytes") != used_bytes
            or bundle.metadata.get("capacity_bytes") != self.geometry.bytes_per_slice
        ):
            raise ValueError("Pool capacity plan differs from physical regions")

        tail_bytes = 0
        for slice_id in range(28):
            previous_end = self.geometry.slice_base(slice_id)
            slice_end = previous_end + self.geometry.bytes_per_slice
            for placement in bundle.placements:
                region = bundle.region(placement.port, slice_id)
                expected = self._descriptor(placement, slice_id)
                payload = bundle.read(placement.port, slice_id)
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
                        raise ValueError(
                            f"Pool region {placement.port}:{slice_id} {field} drifted"
                        )
                expected_base = self.geometry.slice_base(slice_id) + offsets[
                    placement.port
                ]
                if region.base_address != expected_base or (
                    region.base_address % self.alignment
                ):
                    raise ValueError("Pool region address or alignment drifted")
                if region.base_address < previous_end:
                    raise ValueError("Pool physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("Pool physical region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("Pool payload size differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("Pool 128-bit alignment padding is corrupted")
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
                    expected_padding = np.asarray(
                        placement.padding_value, dtype=dtype
                    )
                    if padding.size and not np.all(padding == expected_padding):
                        raise ValueError(
                            f"Pool tail for port {placement.port} is corrupted"
                        )
                    tail_bytes += int(padding.nbytes)
                previous_end = region.base_address + region.size_bytes
        self.inverse(bundle)
        return {
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "port_count": len(bundle.placements),
            "region_count": len(bundle.regions),
            "per_slice_used_bytes": used_bytes,
            "capacity_bytes": self.geometry.bytes_per_slice,
            "tail_bytes": tail_bytes,
        }


class MaxPoolPhysicalLayout(_Rtl28PoolLayout):
    """UINT8 MaxPool with owner-preserving A/D layouts."""

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE,
        geometry: DramGeometry | None = None,
        alignment: int = 16,
    ) -> None:
        super().__init__(profile_id, geometry, alignment)
        self.contract = MAXPOOL_LAYOUT_IDS[self.profile_id]

    @staticmethod
    def _output_shape(
        input_shape: tuple[int, int, int, int],
        kernel_shape: tuple[int, int],
        strides: tuple[int, int],
        pads: tuple[int, int, int, int],
        dilations: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        n, channels, height, width = input_shape
        effective_h = (kernel_shape[0] - 1) * dilations[0] + 1
        effective_w = (kernel_shape[1] - 1) * dilations[1] + 1
        output_h = (
            height + pads[0] + pads[2] - effective_h
        ) // strides[0] + 1
        output_w = (
            width + pads[1] + pads[3] - effective_w
        ) // strides[1] + 1
        if output_h <= 0 or output_w <= 0:
            raise ValueError("MaxPool attributes produce a non-positive output shape")
        return n, channels, output_h, output_w

    def plan(
        self,
        *,
        input_shape: tuple[int, int, int, int],
        kernel_shape: tuple[int, int],
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
        ceil_mode: int = 0,
        storage_order: int = 0,
    ) -> dict[str, Any]:
        input_shape = _shape4(input_shape, "MaxPool input_shape")
        kernel_shape = _plain_positive_pair(kernel_shape, "kernel_shape")
        strides = _plain_positive_pair(strides, "strides")
        dilations = _plain_positive_pair(dilations, "dilations")
        pads = _pads(pads)
        if isinstance(ceil_mode, bool) or int(ceil_mode) != 0:
            raise ValueError("current RTL28 MaxPool supports ceil_mode=0 only")
        if isinstance(storage_order, bool) or int(storage_order) != 0:
            raise ValueError("current RTL28 MaxPool supports storage_order=0 only")
        output_shape = self._output_shape(
            input_shape, kernel_shape, strides, pads, dilations
        )
        tile = self._channel_tile(input_shape[1])
        storage_samples = self._storage_samples()
        physical_shapes = {
            "A": (storage_samples, input_shape[2], input_shape[3], tile),
            "D": (storage_samples, output_shape[2], output_shape[3], tile),
        }
        raw_sizes = {
            port: math.prod(shape) for port, shape in physical_shapes.items()
        }
        offsets = {"A": 0, "D": _align(raw_sizes["A"], self.alignment)}
        used_bytes = offsets["D"] + _align(raw_sizes["D"], self.alignment)
        if used_bytes > self.geometry.bytes_per_slice:
            raise ValueError("RTL28 MaxPool formal plan exceeds one slice")
        return {
            "contract": self.contract,
            "status": self.status,
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "geometry_status": self.geometry_status,
            "address_order_status": self.address_order_status,
            "input_shape": input_shape,
            "output_shape": output_shape,
            "kernel_shape": kernel_shape,
            "strides": strides,
            "pads": pads,
            "dilations": dilations,
            "ceil_mode": 0,
            "storage_order": 0,
            "channel_tile": tile,
            "storage_sample_count": storage_samples,
            "physical_shapes": physical_shapes,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": used_bytes,
            "capacity_bytes": self.geometry.bytes_per_slice,
            "fits": used_bytes <= self.geometry.bytes_per_slice,
            "owner_order": (
                [list(item) for item in HIGH_RING_OWNERS]
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                else list(LOW_RING_OWNERS)
            ),
            "a_d_owner_compatible": True,
            "hardware_approval": False,
        }

    def capacity_report(self, **plan_kwargs: Any) -> dict[str, Any]:
        plan = self.plan(**plan_kwargs)
        return {
            "profile_id": self.profile_id,
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_bytes": plan["capacity_bytes"],
            "margin_bytes": plan["capacity_bytes"] - plan["per_slice_used_bytes"],
            "fits": plan["fits"],
            "candidate_unapproved": True,
        }

    def forward(
        self,
        *,
        activation: np.ndarray,
        output: np.ndarray,
        kernel_shape: tuple[int, int],
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
        ceil_mode: int = 0,
        storage_order: int = 0,
        spatial_padding_value: int = 0,
        input_tail_value: int = 0,
        output_tail_value: int | None = None,
        tensor_ids: dict[str, str] | None = None,
    ) -> PoolPhysicalBundle:
        activation = np.asarray(activation)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("MaxPool activation must be rank-4 uint8 NCHW")
        if output.dtype != np.uint8 or output.ndim != 4:
            raise TypeError("MaxPool output must be rank-4 uint8 NCHW")
        plan = self.plan(
            input_shape=tuple(activation.shape),
            kernel_shape=kernel_shape,
            strides=strides,
            pads=pads,
            dilations=dilations,
            ceil_mode=ceil_mode,
            storage_order=storage_order,
        )
        if tuple(output.shape) != plan["output_shape"]:
            raise TypeError("MaxPool output shape differs from its inferred shape")
        for value, label in (
            (spatial_padding_value, "spatial_padding_value"),
            (input_tail_value, "input_tail_value"),
        ):
            if isinstance(value, bool) or not 0 <= int(value) <= 255:
                raise ValueError(f"{label} must fit uint8")
        if output_tail_value is None:
            output_tail_value = input_tail_value
        if isinstance(output_tail_value, bool) or not 0 <= int(
            output_tail_value
        ) <= 255:
            raise ValueError("output_tail_value must fit uint8")
        ids = {"A": "maxpool_input", "D": "maxpool_output", **(tensor_ids or {})}
        if ids["A"] == ids["D"]:
            raise ValueError("MaxPool A and D tensor IDs must differ")
        return self._pack(
            operator="MaxPool",
            contract=self.contract,
            ports=(
                _PortInput(
                    "A", ids["A"], activation, "feature_partition", int(input_tail_value)
                ),
                _PortInput(
                    "D", ids["D"], output, "feature_partition", int(output_tail_value)
                ),
            ),
            metadata={
                **plan,
                "spatial_padding_value": int(spatial_padding_value),
                "semantics": {
                    "window": "address_generator_not_materialized",
                    "kernel_shape": list(plan["kernel_shape"]),
                    "strides": list(plan["strides"]),
                    "pads": list(plan["pads"]),
                    "dilations": list(plan["dilations"]),
                    "spatial_boundary": (
                        "explicit_uint8_constant_candidate_unapproved"
                    ),
                    "spatial_padding_value": int(spatial_padding_value),
                    "input_tail_value": int(input_tail_value),
                    "output_tail_value": int(output_tail_value),
                    "tail_is_not_spatial_boundary": True,
                    "hardware_approval": False,
                },
            },
        )

    def prove_a_d_compatibility(self, bundle: PoolPhysicalBundle) -> dict[str, Any]:
        a = next(item for item in bundle.placements if item.port == "A")
        d = next(item for item in bundle.placements if item.port == "D")
        conditions = {
            "same_profile": bundle.profile_id == self.profile_id,
            "same_batch_group_policy": True,
            "same_channel_tile": a.feature_tile == d.feature_tile,
            "same_physical_axis": a.physical_axis_order == d.physical_axis_order,
            "same_dtype": a.dtype == d.dtype == "uint8",
            "same_channel_count": a.logical_shape[1] == d.logical_shape[1],
            "owner_ranges_equal": all(
                (
                    bundle.region("A", slice_id).group_id,
                    bundle.region("A", slice_id).owner_step,
                    bundle.region("A", slice_id).sample_start,
                    bundle.region("A", slice_id).sample_count,
                    bundle.region("A", slice_id).feature_start,
                    bundle.region("A", slice_id).feature_count,
                )
                == (
                    bundle.region("D", slice_id).group_id,
                    bundle.region("D", slice_id).owner_step,
                    bundle.region("D", slice_id).sample_start,
                    bundle.region("D", slice_id).sample_count,
                    bundle.region("D", slice_id).feature_start,
                    bundle.region("D", slice_id).feature_count,
                )
                for slice_id in range(28)
            ),
        }
        return {
            "compatible": all(conditions.values()),
            "conditions": conditions,
            "exact_alias": False,
            "reason": "spatial shape changes, while N/C ownership and axis order remain direct-chain compatible",
            "hardware_approval": False,
        }

    def explain_window(
        self,
        bundle: PoolPhysicalBundle,
        *,
        batch: int,
        channel: int,
        output_h: int,
        output_w: int,
        kernel_h: int,
        kernel_w: int,
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["input_shape"]
        _, _, out_h, out_w = bundle.metadata["output_shape"]
        kh, kw = bundle.metadata["kernel_shape"]
        if not (
            0 <= batch < n
            and 0 <= channel < channels
            and 0 <= output_h < out_h
            and 0 <= output_w < out_w
            and 0 <= kernel_h < kh
            and 0 <= kernel_w < kw
        ):
            raise IndexError("MaxPool window coordinate is out of range")
        ih = (
            output_h * bundle.metadata["strides"][0]
            + kernel_h * bundle.metadata["dilations"][0]
            - bundle.metadata["pads"][0]
        )
        iw = (
            output_w * bundle.metadata["strides"][1]
            + kernel_w * bundle.metadata["dilations"][1]
            - bundle.metadata["pads"][1]
        )
        if not (0 <= ih < height and 0 <= iw < width):
            return {
                "semantic": "spatial_padding",
                "value": bundle.metadata["spatial_padding_value"],
                "logical_coordinate": None,
                "hardware_approval": False,
            }
        coordinate = (batch, channel, ih, iw)
        explanation = self.explain_coordinate(
            bundle, bundle.region("A", 0).tensor_id, coordinate
        )[0]
        return {
            "semantic": "data",
            "value": int(self.inverse_port(bundle, explanation["tensor_id"])[coordinate]),
            "logical_coordinate": coordinate,
            "slice_id": explanation["slice_id"],
            "address": explanation["address"],
            "hardware_approval": False,
        }

    def validate(self, bundle: PoolPhysicalBundle) -> dict[str, int | str]:
        if bundle.operator != "MaxPool" or bundle.contract != self.contract:
            raise ValueError("MaxPool bundle contract differs from this layout")
        if tuple(item.port for item in bundle.placements) != ("A", "D"):
            raise ValueError("MaxPool bundle must contain exactly A and D")
        if any(
            item.placement != "feature_partition"
            or item.dtype != "uint8"
            or item.feature_axis != 1
            for item in bundle.placements
        ):
            raise ValueError("MaxPool A/D placement or dtype is invalid")
        plan = self.plan(
            input_shape=tuple(bundle.metadata["input_shape"]),
            kernel_shape=tuple(bundle.metadata["kernel_shape"]),
            strides=tuple(bundle.metadata["strides"]),
            pads=tuple(bundle.metadata["pads"]),
            dilations=tuple(bundle.metadata["dilations"]),
            ceil_mode=bundle.metadata["ceil_mode"],
            storage_order=bundle.metadata["storage_order"],
        )
        for key in (
            "output_shape",
            "channel_tile",
            "storage_sample_count",
            "physical_shapes",
            "raw_sizes",
        ):
            if bundle.metadata.get(key) != plan[key]:
                raise ValueError(f"MaxPool metadata {key} differs from formal plan")
        semantics = bundle.metadata.get("semantics", {})
        for value in (
            semantics.get("spatial_padding_value"),
            semantics.get("input_tail_value"),
            semantics.get("output_tail_value"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError("MaxPool UINT8 boundary/tail semantics are invalid")
        expected_semantics = {
            "window": "address_generator_not_materialized",
            "kernel_shape": list(plan["kernel_shape"]),
            "strides": list(plan["strides"]),
            "pads": list(plan["pads"]),
            "dilations": list(plan["dilations"]),
            "spatial_boundary": "explicit_uint8_constant_candidate_unapproved",
            "spatial_padding_value": bundle.metadata.get("spatial_padding_value"),
            "input_tail_value": bundle.placements[0].padding_value,
            "output_tail_value": bundle.placements[1].padding_value,
            "tail_is_not_spatial_boundary": True,
            "hardware_approval": False,
        }
        if semantics != expected_semantics:
            raise ValueError("MaxPool boundary/tail semantic contract drifted")
        report = super().validate(bundle)
        proof = self.prove_a_d_compatibility(bundle)
        if not proof["compatible"]:
            raise ValueError("MaxPool A/D owner layouts are not direct compatible")
        return {**report, "a_d_owner_compatible": "true"}


class GlobalAveragePoolPhysicalLayout(_Rtl28PoolLayout):
    """QLinearGlobalAveragePool with owner-local centered INT32 sums."""

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE,
        geometry: DramGeometry | None = None,
        alignment: int = 16,
    ) -> None:
        super().__init__(profile_id, geometry, alignment)
        self.contract = GLOBAL_AVERAGE_POOL_LAYOUT_IDS[self.profile_id]

    @staticmethod
    def _output_shape(
        input_shape: tuple[int, int, int, int], output_rank: int
    ) -> tuple[int, ...]:
        if output_rank == 4:
            return input_shape[0], input_shape[1], 1, 1
        if output_rank == 2:
            return input_shape[0], input_shape[1]
        raise ValueError("GlobalAveragePool output_rank must be 2 or 4")

    def plan(
        self,
        *,
        input_shape: tuple[int, int, int, int],
        output_rank: int = 4,
        channels_last: int = 0,
    ) -> dict[str, Any]:
        input_shape = _shape4(input_shape, "GlobalAveragePool input_shape")
        if isinstance(channels_last, bool) or int(channels_last) != 0:
            raise ValueError("current RTL28 GlobalAveragePool requires channels_last=0")
        output_shape = self._output_shape(input_shape, int(output_rank))
        tile = self._channel_tile(input_shape[1])
        storage_samples = self._storage_samples()
        physical_shapes = {
            "A": (storage_samples, input_shape[2], input_shape[3], tile),
            "x_scale": (1,),
            "x_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "multiplier": (1,),
            "P": (
                (storage_samples, 1, 1, tile)
                if output_rank == 4
                else (storage_samples, tile)
            ),
            "D": (
                (storage_samples, 1, 1, tile)
                if output_rank == 4
                else (storage_samples, tile)
            ),
        }
        dtypes = {
            "A": np.dtype("uint8"),
            "x_scale": np.dtype("float32"),
            "x_zero_point": np.dtype("uint8"),
            "y_scale": np.dtype("float32"),
            "y_zero_point": np.dtype("uint8"),
            "multiplier": np.dtype("float32"),
            "P": np.dtype("int32"),
            "D": np.dtype("uint8"),
        }
        raw_sizes = {
            port: math.prod(shape) * dtypes[port].itemsize
            for port, shape in physical_shapes.items()
        }
        offsets: dict[str, int] = {}
        cursor = 0
        for port in physical_shapes:
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(raw_sizes[port], self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("RTL28 GlobalAveragePool formal plan exceeds one slice")
        return {
            "contract": self.contract,
            "status": self.status,
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "geometry_status": self.geometry_status,
            "address_order_status": self.address_order_status,
            "input_shape": input_shape,
            "output_shape": output_shape,
            "output_rank": int(output_rank),
            "channels_last": 0,
            "spatial_size": input_shape[2] * input_shape[3],
            "channel_tile": tile,
            "storage_sample_count": storage_samples,
            "physical_shapes": physical_shapes,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
            "fits": cursor <= self.geometry.bytes_per_slice,
            "channel_owner_path": "A->centered_INT32_P->D",
            "cross_group_reduction": False,
            "hardware_approval": False,
        }

    def capacity_report(self, **plan_kwargs: Any) -> dict[str, Any]:
        plan = self.plan(**plan_kwargs)
        return {
            "profile_id": self.profile_id,
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_bytes": plan["capacity_bytes"],
            "margin_bytes": plan["capacity_bytes"] - plan["per_slice_used_bytes"],
            "fits": plan["fits"],
            "candidate_unapproved": True,
        }

    @staticmethod
    def _scalar(value: np.ndarray, dtype: np.dtype, label: str) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype or array.shape != (1,):
            raise TypeError(f"{label} must have dtype {dtype} and shape (1,)")
        return array

    def forward(
        self,
        *,
        activation: np.ndarray,
        x_scale: np.ndarray,
        x_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        accumulator: np.ndarray,
        output: np.ndarray,
        channels_last: int = 0,
        tensor_ids: dict[str, str] | None = None,
    ) -> PoolPhysicalBundle:
        activation = np.asarray(activation)
        accumulator = np.asarray(accumulator)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("GlobalAveragePool activation must be rank-4 uint8 NCHW")
        if accumulator.dtype != np.int32 or accumulator.ndim not in {2, 4}:
            raise TypeError("GlobalAveragePool accumulator must be rank-2/4 int32")
        if output.dtype != np.uint8 or output.ndim != accumulator.ndim:
            raise TypeError("GlobalAveragePool output must match accumulator rank as uint8")
        plan = self.plan(
            input_shape=tuple(activation.shape),
            output_rank=output.ndim,
            channels_last=channels_last,
        )
        if tuple(accumulator.shape) != plan["output_shape"]:
            raise TypeError("GlobalAveragePool accumulator shape is invalid")
        if tuple(output.shape) != plan["output_shape"]:
            raise TypeError("GlobalAveragePool output shape is invalid")
        qparams = {
            "x_scale": self._scalar(x_scale, np.dtype("float32"), "x_scale"),
            "x_zero_point": self._scalar(
                x_zero_point, np.dtype("uint8"), "x_zero_point"
            ),
            "y_scale": self._scalar(y_scale, np.dtype("float32"), "y_scale"),
            "y_zero_point": self._scalar(
                y_zero_point, np.dtype("uint8"), "y_zero_point"
            ),
        }
        if (
            not np.isfinite(qparams["x_scale"][0])
            or not np.isfinite(qparams["y_scale"][0])
            or qparams["x_scale"][0] <= 0
            or qparams["y_scale"][0] <= 0
        ):
            raise ValueError("GlobalAveragePool scales must be positive and finite")
        multiplier = np.array(
            [
                np.float32(qparams["x_scale"][0])
                / (
                    np.float32(qparams["y_scale"][0])
                    * np.float32(plan["spatial_size"])
                )
            ],
            dtype=np.float32,
        )
        ids = {
            "A": "globalavgpool_input",
            "x_scale": "globalavgpool_x_scale",
            "x_zero_point": "globalavgpool_x_zero_point",
            "y_scale": "globalavgpool_y_scale",
            "y_zero_point": "globalavgpool_y_zero_point",
            "multiplier": "globalavgpool_multiplier",
            "P": "globalavgpool_centered_sum",
            "D": "globalavgpool_output",
            **(tensor_ids or {}),
        }
        if len(set(ids.values())) != len(ids):
            raise ValueError("GlobalAveragePool tensor IDs must be unique")
        ports = (
            _PortInput(
                "A",
                ids["A"],
                activation,
                "feature_partition",
                int(qparams["x_zero_point"][0]),
            ),
            _PortInput(
                "x_scale", ids["x_scale"], qparams["x_scale"], "replicated", 0.0
            ),
            _PortInput(
                "x_zero_point",
                ids["x_zero_point"],
                qparams["x_zero_point"],
                "replicated",
                0,
            ),
            _PortInput(
                "y_scale", ids["y_scale"], qparams["y_scale"], "replicated", 0.0
            ),
            _PortInput(
                "y_zero_point",
                ids["y_zero_point"],
                qparams["y_zero_point"],
                "replicated",
                0,
            ),
            _PortInput(
                "multiplier", ids["multiplier"], multiplier, "replicated", 0.0
            ),
            _PortInput("P", ids["P"], accumulator, "feature_partition", 0),
            _PortInput(
                "D",
                ids["D"],
                output,
                "feature_partition",
                int(qparams["y_zero_point"][0]),
            ),
        )
        return self._pack(
            operator="QLinearGlobalAveragePool",
            contract=self.contract,
            ports=ports,
            metadata={
                **plan,
                "multiplier": float(multiplier[0]),
                "semantics": {
                    "reduction": "sum(A-x_zero_point) over H,W",
                    "intermediate": "owner-local centered INT32 sum",
                    "requantize": "round(P*x_scale/(y_scale*H*W))+y_zero_point",
                    "channel_owner_path": "A->P->D",
                    "cross_group_reduction": False,
                    "scalar_qparams": "replicated_on_all_28_slices",
                    "input_tail_value": int(qparams["x_zero_point"][0]),
                    "sum_tail_value": 0,
                    "output_tail_value": int(qparams["y_zero_point"][0]),
                    "hardware_approval": False,
                },
            },
        )

    def prove_owner_local_reduction(
        self, bundle: PoolPhysicalBundle
    ) -> dict[str, Any]:
        conditions: dict[str, bool] = {}
        for left, right in (("A", "P"), ("P", "D")):
            conditions[f"{left}_{right}_same_owner"] = all(
                (
                    bundle.region(left, slice_id).group_id,
                    bundle.region(left, slice_id).owner_step,
                    bundle.region(left, slice_id).sample_start,
                    bundle.region(left, slice_id).sample_count,
                    bundle.region(left, slice_id).feature_start,
                    bundle.region(left, slice_id).feature_count,
                )
                == (
                    bundle.region(right, slice_id).group_id,
                    bundle.region(right, slice_id).owner_step,
                    bundle.region(right, slice_id).sample_start,
                    bundle.region(right, slice_id).sample_count,
                    bundle.region(right, slice_id).feature_start,
                    bundle.region(right, slice_id).feature_count,
                )
                for slice_id in range(28)
            )
        conditions["no_cross_group_reduction"] = not bundle.metadata[
            "cross_group_reduction"
        ]
        return {
            "compatible": all(conditions.values()),
            "conditions": conditions,
            "path": "A->owner-local centered INT32 P->D",
            "hardware_approval": False,
        }

    def explain_reduction(
        self, bundle: PoolPhysicalBundle, *, batch: int, channel: int
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["input_shape"]
        if not 0 <= batch < n or not 0 <= channel < channels:
            raise IndexError("GlobalAveragePool reduction coordinate is out of range")
        a_id = next(item.tensor_id for item in bundle.placements if item.port == "A")
        p_id = next(item.tensor_id for item in bundle.placements if item.port == "P")
        input_elements = []
        for h in range(height):
            for w in range(width):
                item = self.explain_coordinate(
                    bundle, a_id, (batch, channel, h, w)
                )[0]
                input_elements.append(
                    {
                        "logical_coordinate": (batch, channel, h, w),
                        "slice_id": item["slice_id"],
                        "address": item["address"],
                    }
                )
        p_coordinate = (
            (batch, channel, 0, 0)
            if bundle.metadata["output_rank"] == 4
            else (batch, channel)
        )
        sum_bytes = self.explain_coordinate(bundle, p_id, p_coordinate)
        return {
            "batch": batch,
            "channel": channel,
            "spatial_size": bundle.metadata["spatial_size"],
            "formula": "sum(A-x_zero_point) over H,W",
            "input_elements": tuple(input_elements),
            "sum_slice_id": sum_bytes[0]["slice_id"],
            "sum_addresses": tuple(item["address"] for item in sum_bytes),
            "cross_group_reduction": False,
            "hardware_approval": False,
        }

    def validate(self, bundle: PoolPhysicalBundle) -> dict[str, int | str]:
        if (
            bundle.operator != "QLinearGlobalAveragePool"
            or bundle.contract != self.contract
        ):
            raise ValueError("GlobalAveragePool contract differs from this layout")
        expected_ports = (
            "A",
            "x_scale",
            "x_zero_point",
            "y_scale",
            "y_zero_point",
            "multiplier",
            "P",
            "D",
        )
        if tuple(item.port for item in bundle.placements) != expected_ports:
            raise ValueError("GlobalAveragePool port contract drifted")
        expected_dtypes = {
            "A": "uint8",
            "x_scale": "float32",
            "x_zero_point": "uint8",
            "y_scale": "float32",
            "y_zero_point": "uint8",
            "multiplier": "float32",
            "P": "int32",
            "D": "uint8",
        }
        for placement in bundle.placements:
            expected_placement = (
                "replicated"
                if placement.port in expected_ports[1:6]
                else "feature_partition"
            )
            if (
                placement.dtype != expected_dtypes[placement.port]
                or placement.placement != expected_placement
            ):
                raise ValueError("GlobalAveragePool placement or dtype drifted")
        plan = self.plan(
            input_shape=tuple(bundle.metadata["input_shape"]),
            output_rank=int(bundle.metadata["output_rank"]),
            channels_last=int(bundle.metadata["channels_last"]),
        )
        for key in (
            "output_shape",
            "spatial_size",
            "channel_tile",
            "storage_sample_count",
            "physical_shapes",
            "raw_sizes",
        ):
            if bundle.metadata.get(key) != plan[key]:
                raise ValueError(
                    f"GlobalAveragePool metadata {key} differs from formal plan"
                )
        semantics = bundle.metadata.get("semantics", {})
        expected_semantics = {
            "reduction": "sum(A-x_zero_point) over H,W",
            "intermediate": "owner-local centered INT32 sum",
            "requantize": "round(P*x_scale/(y_scale*H*W))+y_zero_point",
            "channel_owner_path": "A->P->D",
            "cross_group_reduction": False,
            "scalar_qparams": "replicated_on_all_28_slices",
            "input_tail_value": bundle.placements[0].padding_value,
            "sum_tail_value": bundle.placements[6].padding_value,
            "output_tail_value": bundle.placements[7].padding_value,
            "hardware_approval": False,
        }
        if semantics != expected_semantics:
            raise ValueError("GlobalAveragePool reduction semantic contract drifted")
        report = super().validate(bundle)
        recovered = {
            placement.port: self.inverse_port(bundle, placement.tensor_id)
            for placement in bundle.placements
        }
        expected_multiplier = np.float32(recovered["x_scale"][0]) / (
            np.float32(recovered["y_scale"][0])
            * np.float32(bundle.metadata["spatial_size"])
        )
        if recovered["multiplier"][0] != expected_multiplier:
            raise ValueError("GlobalAveragePool multiplier is inconsistent")
        centered = recovered["A"].astype(np.int32) - int(
            recovered["x_zero_point"][0]
        )
        expected_sum = np.sum(
            centered, axis=(2, 3), keepdims=True, dtype=np.int64
        )
        if bundle.metadata["output_rank"] == 2:
            expected_sum = expected_sum.reshape(BATCH_SIZE, -1)
        if expected_sum.min() < np.iinfo(np.int32).min or expected_sum.max() > np.iinfo(np.int32).max:
            raise OverflowError("GlobalAveragePool centered sum exceeds int32")
        if not np.array_equal(recovered["P"], expected_sum.astype(np.int32)):
            raise ValueError("GlobalAveragePool centered INT32 sum is inconsistent")
        expected_d = np.clip(
            np.rint(recovered["P"].astype(np.float32) * expected_multiplier).astype(
                np.int64
            )
            + int(recovered["y_zero_point"][0]),
            0,
            255,
        ).astype(np.uint8)
        if not np.array_equal(recovered["D"], expected_d):
            raise ValueError("GlobalAveragePool requantized D is inconsistent")
        proof = self.prove_owner_local_reduction(bundle)
        if not proof["compatible"]:
            raise ValueError("GlobalAveragePool A/P/D owner path is inconsistent")
        return {
            **report,
            "spatial_size": bundle.metadata["spatial_size"],
            "owner_local_reduction": "true",
        }


__all__ = [
    "MAXPOOL_LAYOUT_IDS",
    "GLOBAL_AVERAGE_POOL_LAYOUT_IDS",
    "PoolPhysicalBundle",
    "MaxPoolPhysicalLayout",
    "GlobalAveragePoolPhysicalLayout",
]
