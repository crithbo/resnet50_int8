"""Reversible RTL28 physical layouts for the ResNet QLinearAdd nodes.

The current model needs exactly two broadcast modes: equal rank-2/rank-4
inputs for residual additions and ``[N,F] + [F]`` for the dense bias.  The
module deliberately rejects every other NumPy/ONNX broadcast.  Both input
qparam pairs stay independent, and simultaneous input aliases are accepted
only when their live physical ranges do not overlap on any slice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .conv28_layout import CONV28_LAYOUT_IDS, Conv28PhysicalBundle
from .matmul28_layout import MATMUL28_LAYOUT_IDS, MatMul28PhysicalBundle
from .memory import DramGeometry, TARGET_DRAM_GEOMETRY28
from .profile28 import (
    BATCH_SIZE,
    GROUP_SAMPLE_COUNTS,
    DEFAULT_PROFILE,
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    group_to_sample_range,
    sample_to_group,
    validate_profile_name,
)
from .records import LayoutRecord
from .simple_layout import Rtl28PhysicalRegion, Rtl28PortPlacement
from .topology28 import HIGH_RING_OWNERS, LOW_RING_OWNERS


ADD28_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: "w4_qlinearadd_group4x7_28_candidate_v1",
    GLOBAL_RING28_PROFILE: "w4_qlinearadd_global_ring28_candidate_v1",
}

PORT_ORDER = (
    "A",
    "a_scale",
    "a_zero_point",
    "B",
    "b_scale",
    "b_zero_point",
    "y_scale",
    "y_zero_point",
    "D",
)
INPUT_PORTS = ("A", "B")
DATA_PORTS = ("A", "B", "D")
SCALE_PORTS = ("a_scale", "b_scale", "y_scale")
ZERO_POINT_PORTS = ("a_zero_point", "b_zero_point", "y_zero_point")

BroadcastMode = Literal["same_shape", "dense_vector_broadcast"]


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _canonical(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _axis_order(shape: tuple[int, ...], *, broadcast: bool = False) -> str:
    if broadcast:
        return "F-local"
    if len(shape) == 2:
        return "NF-local"
    if len(shape) == 4:
        return "NHWF-local"
    raise ValueError("QLinearAdd data must be rank 2 or rank 4")


@dataclass(frozen=True)
class Add28PhysicalBundle:
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
            raise KeyError(f"expected one Add placement for {tensor_id!r}")
        return matches[0]

    def region(self, port: str, slice_id: int) -> Rtl28PhysicalRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one Add {port} region on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        broadcast_mode = self.metadata["broadcast_mode"]
        aliases = set(self.metadata["input_alias_ports"])
        for placement in self.placements:
            if placement.placement == "replicated":
                partition: dict[str, Any] = {
                    "axis": None,
                    "policy": "replicated_on_every_rtl28_slice",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                }
            elif self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                partition = {
                    "axis": placement.feature_axis,
                    "policy": (
                        "feature_partition_replicated_across_seven_high_groups"
                        if placement.port == "B"
                        and broadcast_mode == "dense_vector_broadcast"
                        else "seven_high_groups_sample_and_feature_partition"
                    ),
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "batch_group_sample_counts": list(GROUP_SAMPLE_COUNTS),
                    "high_ring_owners": [list(item) for item in HIGH_RING_OWNERS],
                    "feature_tile": placement.feature_tile,
                    "storage_samples_per_owner": (
                        0
                        if placement.port == "B"
                        and broadcast_mode == "dense_vector_broadcast"
                        else max(GROUP_SAMPLE_COUNTS)
                    ),
                }
            else:
                partition = {
                    "axis": placement.feature_axis,
                    "policy": "global_low_ring_feature_partition",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "low_ring_owners": list(LOW_RING_OWNERS),
                    "feature_tile": placement.feature_tile,
                    "storage_samples_per_owner": (
                        0
                        if placement.port == "B"
                        and broadcast_mode == "dense_vector_broadcast"
                        else BATCH_SIZE
                    ),
                }
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-add28-{placement.port.lower()}-"
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
                        "logical_order": (
                            "F"
                            if placement.port == "B"
                            and broadcast_mode == "dense_vector_broadcast"
                            else "N,F,..."
                        ),
                        "physical_order": placement.physical_axis_order,
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "subword_bytes": self.geometry.subword_bytes,
                        "padding_value": placement.padding_value,
                        "broadcast_mode": broadcast_mode,
                        "independent_input_qparams": True,
                        "input_alias_requested": placement.port in aliases,
                        "geometry_status": self.geometry_status,
                        "address_order_status": self.address_order_status,
                    },
                    base_addresses=tuple(
                        self.region(placement.port, slice_id).base_address
                        for slice_id in range(self.geometry.slice_count)
                    ),
                    inverse_status="validated",
                    alias_of=(
                        placement.tensor_id if placement.port in aliases else None
                    ),
                )
            )
        return tuple(records)


class QLinearAddPhysicalLayout:
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
            raise ValueError("current Add layout requires TARGET_DRAM_GEOMETRY28")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment
        self.contract = ADD28_LAYOUT_IDS[self.profile_id]

    @property
    def owner_count(self) -> int:
        return (
            len(HIGH_RING_OWNERS[0])
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else len(LOW_RING_OWNERS)
        )

    @staticmethod
    def _mode(a_shape: tuple[int, ...], b_shape: tuple[int, ...]) -> BroadcastMode:
        if a_shape == b_shape and len(a_shape) in {2, 4}:
            return "same_shape"
        if (
            len(a_shape) == 2
            and len(b_shape) == 1
            and a_shape[1] == b_shape[0]
        ):
            return "dense_vector_broadcast"
        raise ValueError(
            "formal RTL28 Add supports equal rank-2/rank-4 inputs or [N,F]+[F]"
        )

    @staticmethod
    def _data_shape(
        logical_shape: tuple[int, ...],
        storage_samples: int,
        feature_tile: int,
    ) -> tuple[int, ...]:
        if len(logical_shape) == 2:
            return storage_samples, feature_tile
        if len(logical_shape) == 4:
            return (
                storage_samples,
                logical_shape[2],
                logical_shape[3],
                feature_tile,
            )
        raise ValueError("Add data shape must be rank 2 or rank 4")

    def _base_offsets(
        self, addresses: dict[str, tuple[int, ...]] | None
    ) -> dict[str, int] | None:
        if addresses is None:
            return None
        unknown = set(addresses) - set(INPUT_PORTS)
        if unknown:
            raise ValueError(f"Add aliased bases only accept A/B, got {sorted(unknown)}")
        result: dict[str, int] = {}
        for port, values in addresses.items():
            if len(values) != self.geometry.slice_count:
                raise ValueError("Add aliased input bases must contain 28 addresses")
            offsets: list[int] = []
            for slice_id, raw_address in enumerate(values):
                address = int(raw_address)
                start = self.geometry.slice_base(slice_id)
                end = start + self.geometry.bytes_per_slice
                if not start <= address < end:
                    raise ValueError("Add aliased input base is outside its slice")
                offset = address - start
                if offset % self.alignment:
                    raise ValueError("Add aliased input base is not aligned")
                offsets.append(offset)
            if len(set(offsets)) != 1:
                raise ValueError("Add aliased bases need one common slice offset")
            result[port] = offsets[0]
        return result

    def plan(
        self,
        *,
        a_shape: tuple[int, ...],
        b_shape: tuple[int, ...],
        input_offsets: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        a_shape = tuple(int(value) for value in a_shape)
        b_shape = tuple(int(value) for value in b_shape)
        if any(value <= 0 for value in a_shape + b_shape):
            raise ValueError("Add dimensions must be positive")
        if len(a_shape) not in {2, 4} or a_shape[0] != BATCH_SIZE:
            raise ValueError(f"RTL28 Add requires rank-2/rank-4 batch={BATCH_SIZE} A")
        mode = self._mode(a_shape, b_shape)
        d_shape = a_shape
        features = a_shape[1]
        feature_tile = math.ceil(features / self.owner_count)
        storage_samples = (
            max(GROUP_SAMPLE_COUNTS)
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else BATCH_SIZE
        )
        physical_shapes = {
            "A": self._data_shape(a_shape, storage_samples, feature_tile),
            "a_scale": (1,),
            "a_zero_point": (1,),
            "B": (
                (feature_tile,)
                if mode == "dense_vector_broadcast"
                else self._data_shape(b_shape, storage_samples, feature_tile)
            ),
            "b_scale": (1,),
            "b_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "D": self._data_shape(d_shape, storage_samples, feature_tile),
        }
        dtypes = {
            "A": np.dtype("uint8"),
            "a_scale": np.dtype("float32"),
            "a_zero_point": np.dtype("uint8"),
            "B": np.dtype("uint8"),
            "b_scale": np.dtype("float32"),
            "b_zero_point": np.dtype("uint8"),
            "y_scale": np.dtype("float32"),
            "y_zero_point": np.dtype("uint8"),
            "D": np.dtype("uint8"),
        }
        raw_sizes = {
            port: math.prod(physical_shapes[port]) * dtypes[port].itemsize
            for port in PORT_ORDER
        }
        aligned_sizes = {
            port: _align(raw_sizes[port], self.alignment) for port in PORT_ORDER
        }

        offsets = dict(input_offsets or {})
        unknown = set(offsets) - set(INPUT_PORTS)
        if unknown:
            raise ValueError(f"Add input_offsets only accept A/B, got {sorted(unknown)}")
        explicit_ranges: dict[str, tuple[int, int]] = {}
        for port, raw_offset in offsets.items():
            offset = int(raw_offset)
            if offset < 0 or offset % self.alignment:
                raise ValueError("Add aliased input offset must be non-negative and aligned")
            stop = offset + aligned_sizes[port]
            if stop > self.geometry.bytes_per_slice:
                raise ValueError("Add aliased input region exceeds one slice")
            offsets[port] = offset
            explicit_ranges[port] = (offset, stop)
        if set(explicit_ranges) == set(INPUT_PORTS) and _ranges_overlap(
            explicit_ranges["A"], explicit_ranges["B"]
        ):
            raise ValueError("Add simultaneous A/B alias regions overlap")

        cursor = max((stop for _, stop in explicit_ranges.values()), default=0)
        for port in INPUT_PORTS:
            if port not in offsets:
                cursor = _align(cursor, self.alignment)
                offsets[port] = cursor
                cursor += aligned_sizes[port]
            else:
                cursor = max(cursor, offsets[port] + aligned_sizes[port])
        a_range = (offsets["A"], offsets["A"] + aligned_sizes["A"])
        b_range = (offsets["B"], offsets["B"] + aligned_sizes["B"])
        if _ranges_overlap(a_range, b_range):
            raise ValueError("Add A/B physical regions overlap")

        for port in PORT_ORDER:
            if port in INPUT_PORTS:
                continue
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += aligned_sizes[port]
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("RTL28 Add regions exceed one slice capacity")
        return {
            "profile_id": self.profile_id,
            "a_shape": a_shape,
            "b_shape": b_shape,
            "d_shape": d_shape,
            "broadcast_mode": mode,
            "features": features,
            "owner_count": self.owner_count,
            "owner_order": (
                HIGH_RING_OWNERS
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                else LOW_RING_OWNERS
            ),
            "storage_sample_count": storage_samples,
            "feature_tile": feature_tile,
            "feature_padded": feature_tile * self.owner_count,
            "physical_shapes": physical_shapes,
            "dtypes": {port: str(dtype) for port, dtype in dtypes.items()},
            "raw_sizes": raw_sizes,
            "aligned_sizes": aligned_sizes,
            "offsets": offsets,
            "input_offsets": {
                port: offsets[port]
                for port in INPUT_PORTS
                if input_offsets is not None and port in input_offsets
            },
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
            "capacity_margin_bytes": self.geometry.bytes_per_slice - cursor,
        }

    def capacity_report(
        self,
        *,
        a_shape: tuple[int, ...],
        b_shape: tuple[int, ...],
        input_offsets: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        plan = self.plan(
            a_shape=a_shape, b_shape=b_shape, input_offsets=input_offsets
        )
        return {
            "profile_id": self.profile_id,
            "a_shape": plan["a_shape"],
            "b_shape": plan["b_shape"],
            "d_shape": plan["d_shape"],
            "broadcast_mode": plan["broadcast_mode"],
            "feature_tile": plan["feature_tile"],
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_bytes": plan["capacity_bytes"],
            "capacity_margin_bytes": plan["capacity_margin_bytes"],
            "fits": True,
        }

    @staticmethod
    def _scalar(
        value: np.ndarray,
        dtype: np.dtype,
        name: str,
        *,
        positive: bool = False,
    ) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype or array.size != 1:
            raise TypeError(f"{name} must be scalar {dtype}")
        result = _canonical(array.reshape(1))
        if positive and (not np.isfinite(result[0]) or float(result[0]) <= 0):
            raise ValueError(f"{name} must be positive and finite")
        return result

    @staticmethod
    def _tensor_ids(overrides: dict[str, str] | None) -> dict[str, str]:
        unknown = set(overrides or {}) - set(PORT_ORDER)
        if unknown:
            raise ValueError(f"unknown Add tensor-id ports: {sorted(unknown)}")
        defaults = {
            "A": "add_input_a",
            "a_scale": "add_a_scale",
            "a_zero_point": "add_a_zero_point",
            "B": "add_input_b",
            "b_scale": "add_b_scale",
            "b_zero_point": "add_b_zero_point",
            "y_scale": "add_y_scale",
            "y_zero_point": "add_y_zero_point",
            "D": "add_output",
        }
        ids = {**defaults, **(overrides or {})}
        if any(not isinstance(value, str) or not value for value in ids.values()):
            raise ValueError("Add tensor IDs must be non-empty strings")
        if len(set(ids.values())) != len(ids):
            raise ValueError("Add tensor IDs must remain unique across all ports")
        return ids

    def _owner_location(self, slice_id: int) -> tuple[int | None, int]:
        if not 0 <= slice_id < self.geometry.slice_count:
            raise ValueError("slice_id is outside RTL28")
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            for group_id, owners in enumerate(HIGH_RING_OWNERS):
                if slice_id in owners:
                    return group_id, owners.index(slice_id)
            raise AssertionError("RTL28 slice is missing from HIGH groups")
        return None, LOW_RING_OWNERS.index(slice_id)

    def _descriptor(
        self, port: str, plan: dict[str, Any], slice_id: int
    ) -> dict[str, Any]:
        if port not in DATA_PORTS:
            return {
                "physical_shape": plan["physical_shapes"][port],
                "active": True,
                "group_id": None,
                "owner_step": None,
                "sample_start": 0,
                "sample_count": 0,
                "storage_sample_count": 0,
                "feature_start": 0,
                "feature_count": 0,
            }
        group_id, owner_step = self._owner_location(slice_id)
        feature_start = owner_step * plan["feature_tile"]
        feature_count = max(
            0, min(plan["feature_tile"], plan["features"] - feature_start)
        )
        is_broadcast = (
            port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast"
        )
        if is_broadcast:
            sample_start = 0
            sample_count = 0
            storage_samples = 0
        elif group_id is None:
            sample_start = 0
            sample_count = BATCH_SIZE
            storage_samples = BATCH_SIZE
        else:
            sample_range = group_to_sample_range(group_id)
            sample_start = sample_range.start
            sample_count = sample_range.sample_count
            storage_samples = max(GROUP_SAMPLE_COUNTS)
        return {
            "physical_shape": plan["physical_shapes"][port],
            "active": feature_count > 0 and (is_broadcast or sample_count > 0),
            "group_id": group_id,
            "owner_step": owner_step,
            "sample_start": sample_start,
            "sample_count": sample_count,
            "storage_sample_count": storage_samples,
            "feature_start": feature_start,
            "feature_count": feature_count,
        }

    def _placement(
        self,
        *,
        port: str,
        tensor_id: str,
        logical_shape: tuple[int, ...],
        dtype: str,
        plan: dict[str, Any],
        padding_value: int | float,
    ) -> Rtl28PortPlacement:
        if port not in DATA_PORTS:
            return Rtl28PortPlacement(
                port=port,
                tensor_id=tensor_id,
                logical_shape=logical_shape,
                dtype=dtype,
                placement="replicated",
                feature_axis=None,
                feature_tile=None,
                physical_axis_order="replicated-scalar",
                slot_payload_bytes=plan["raw_sizes"][port],
                padding_value=padding_value,
            )
        broadcast = (
            port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast"
        )
        return Rtl28PortPlacement(
            port=port,
            tensor_id=tensor_id,
            logical_shape=logical_shape,
            dtype=dtype,
            placement="feature_partition",
            feature_axis=0 if broadcast else 1,
            feature_tile=plan["feature_tile"],
            physical_axis_order=_axis_order(logical_shape, broadcast=broadcast),
            slot_payload_bytes=plan["raw_sizes"][port],
            padding_value=padding_value,
        )

    def forward(
        self,
        *,
        a: np.ndarray,
        a_scale: np.ndarray,
        a_zero_point: np.ndarray,
        b: np.ndarray,
        b_scale: np.ndarray,
        b_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        output: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
        input_base_addresses: dict[str, tuple[int, ...]] | None = None,
    ) -> Add28PhysicalBundle:
        a = np.asarray(a)
        b = np.asarray(b)
        output = np.asarray(output)
        if any(array.dtype != np.uint8 for array in (a, b, output)):
            raise TypeError("QLinearAdd A/B/D must be uint8")
        input_offsets = self._base_offsets(input_base_addresses)
        plan = self.plan(
            a_shape=tuple(a.shape),
            b_shape=tuple(b.shape),
            input_offsets=input_offsets,
        )
        if tuple(output.shape) != plan["d_shape"]:
            raise TypeError("QLinearAdd output shape differs from broadcast result")
        qparams = {
            "a_scale": self._scalar(
                a_scale, np.dtype("float32"), "a_scale", positive=True
            ),
            "a_zero_point": self._scalar(
                a_zero_point, np.dtype("uint8"), "a_zero_point"
            ),
            "b_scale": self._scalar(
                b_scale, np.dtype("float32"), "b_scale", positive=True
            ),
            "b_zero_point": self._scalar(
                b_zero_point, np.dtype("uint8"), "b_zero_point"
            ),
            "y_scale": self._scalar(
                y_scale, np.dtype("float32"), "y_scale", positive=True
            ),
            "y_zero_point": self._scalar(
                y_zero_point, np.dtype("uint8"), "y_zero_point"
            ),
        }
        arrays = {"A": _canonical(a), "B": _canonical(b), "D": _canonical(output), **qparams}
        tails: dict[str, int | float] = {
            "A": int(qparams["a_zero_point"][0]),
            "a_scale": 0.0,
            "a_zero_point": 0,
            "B": int(qparams["b_zero_point"][0]),
            "b_scale": 0.0,
            "b_zero_point": 0,
            "y_scale": 0.0,
            "y_zero_point": 0,
            "D": int(qparams["y_zero_point"][0]),
        }
        ids = self._tensor_ids(tensor_ids)
        logical_shapes = {
            "A": tuple(a.shape),
            "B": tuple(b.shape),
            "D": tuple(output.shape),
            **{port: (1,) for port in PORT_ORDER if port not in DATA_PORTS},
        }
        placements = tuple(
            self._placement(
                port=port,
                tensor_id=ids[port],
                logical_shape=logical_shapes[port],
                dtype=str(arrays[port].dtype),
                plan=plan,
                padding_value=tails[port],
            )
            for port in PORT_ORDER
        )

        payloads: dict[tuple[str, int], bytes] = {}
        regions: list[Rtl28PhysicalRegion] = []
        for port in PORT_ORDER:
            for slice_id in range(self.geometry.slice_count):
                descriptor = self._descriptor(port, plan, slice_id)
                if port not in DATA_PORTS:
                    local = arrays[port]
                else:
                    local = np.full(
                        descriptor["physical_shape"],
                        tails[port],
                        dtype=arrays[port].dtype,
                    )
                    count = descriptor["feature_count"]
                    start = descriptor["feature_start"]
                    if port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast":
                        if count:
                            local[:count] = arrays[port][start : start + count]
                    elif count:
                        sample_start = descriptor["sample_start"]
                        sample_count = descriptor["sample_count"]
                        logical = arrays[port][
                            sample_start : sample_start + sample_count,
                            start : start + count,
                        ]
                        if arrays[port].ndim == 4:
                            logical = np.transpose(logical, (0, 2, 3, 1))
                        local[:sample_count, ..., :count] = logical
                raw = _canonical(local).tobytes(order="C")
                if len(raw) != plan["raw_sizes"][port]:
                    raise AssertionError("Add physical payload-size calculation drifted")
                payload = raw + bytes(plan["aligned_sizes"][port] - len(raw))
                payloads[(port, slice_id)] = payload
                regions.append(
                    Rtl28PhysicalRegion(
                        port=port,
                        tensor_id=ids[port],
                        slice_id=slice_id,
                        base_address=(
                            self.geometry.slice_base(slice_id)
                            + plan["offsets"][port]
                        ),
                        payload_bytes=len(raw),
                        size_bytes=len(payload),
                        physical_shape=descriptor["physical_shape"],
                        active=descriptor["active"],
                        group_id=descriptor["group_id"],
                        owner_step=descriptor["owner_step"],
                        sample_start=descriptor["sample_start"],
                        sample_count=descriptor["sample_count"],
                        storage_sample_count=descriptor["storage_sample_count"],
                        feature_start=descriptor["feature_start"],
                        feature_count=descriptor["feature_count"],
                    )
                )
        aliases = tuple(
            port for port in INPUT_PORTS if input_base_addresses and port in input_base_addresses
        )
        bundle = Add28PhysicalBundle(
            operator="QLinearAdd",
            contract=self.contract,
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
                "plan": plan,
                "port_order": PORT_ORDER,
                "broadcast_mode": plan["broadcast_mode"],
                "tails": tails,
                "input_alias_requested": input_base_addresses is not None,
                "input_alias_ports": aliases,
                "independent_qparam_ports": {
                    "A": ("a_scale", "a_zero_point"),
                    "B": ("b_scale", "b_zero_point"),
                    "D": ("y_scale", "y_zero_point"),
                },
                "simultaneous_alias_policy": "reject_any_per_slice_live_range_overlap",
            },
        )
        self.validate(bundle)
        return bundle

    def _read_array(
        self, bundle: Add28PhysicalBundle, port: str, slice_id: int
    ) -> np.ndarray:
        placement = next(item for item in bundle.placements if item.port == port)
        region = bundle.region(port, slice_id)
        raw = bundle.read(port, slice_id)[: region.payload_bytes]
        return np.frombuffer(raw, dtype=np.dtype(placement.dtype).newbyteorder("<")).reshape(
            region.physical_shape
        )

    def _inverse_by_port(
        self, bundle: Add28PhysicalBundle, port: str
    ) -> np.ndarray:
        placement = next(item for item in bundle.placements if item.port == port)
        if port not in DATA_PORTS:
            first = self._read_array(bundle, port, 0).copy()
            for slice_id in range(1, self.geometry.slice_count):
                if not np.array_equal(first, self._read_array(bundle, port, slice_id)):
                    raise ValueError(f"Add replicated {port} differs across slices")
            return first

        plan = bundle.metadata["plan"]
        if port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast":
            result = np.empty(placement.logical_shape, dtype=np.dtype(placement.dtype))
            owners = HIGH_RING_OWNERS[0] if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE else LOW_RING_OWNERS
            for slice_id in owners:
                region = bundle.region(port, slice_id)
                if region.feature_count:
                    local = self._read_array(bundle, port, slice_id)
                    result[
                        region.feature_start : region.feature_start + region.feature_count
                    ] = local[: region.feature_count]
            return result

        result = np.empty(placement.logical_shape, dtype=np.dtype(placement.dtype))
        for slice_id in range(self.geometry.slice_count):
            region = bundle.region(port, slice_id)
            if not region.active:
                continue
            local = self._read_array(bundle, port, slice_id)
            sample = slice(
                region.sample_start, region.sample_start + region.sample_count
            )
            feature = slice(
                region.feature_start, region.feature_start + region.feature_count
            )
            valid = local[: region.sample_count, ..., : region.feature_count]
            if len(placement.logical_shape) == 4:
                valid = np.transpose(valid, (0, 3, 1, 2))
            result[sample, feature] = valid
        return result

    def inverse_port(
        self, bundle: Add28PhysicalBundle, tensor_id: str
    ) -> np.ndarray:
        placement = bundle.placement(tensor_id)
        return self._inverse_by_port(bundle, placement.port)

    def inverse(self, bundle: Add28PhysicalBundle) -> dict[str, np.ndarray]:
        return {
            placement.tensor_id: self._inverse_by_port(bundle, placement.port)
            for placement in bundle.placements
        }

    def _coordinate_record(
        self,
        bundle: Add28PhysicalBundle,
        placement: Rtl28PortPlacement,
        slice_id: int,
        physical_coordinate: tuple[int, ...],
        logical_coordinate: tuple[int, ...],
        semantic: str,
    ) -> dict[str, Any]:
        region = bundle.region(placement.port, slice_id)
        flat = int(np.ravel_multi_index(physical_coordinate, region.physical_shape))
        return {
            "tensor_id": placement.tensor_id,
            "port": placement.port,
            "profile_id": self.profile_id,
            "slice_id": slice_id,
            "group_id": region.group_id,
            "owner_step": region.owner_step,
            "logical_coordinate": logical_coordinate,
            "physical_coordinate": physical_coordinate,
            "byte_address": region.base_address + flat * np.dtype(placement.dtype).itemsize,
            "semantic": semantic,
        }

    def explain_coordinate(
        self,
        bundle: Add28PhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        placement = bundle.placement(tensor_id)
        coordinate = tuple(int(value) for value in coordinate)
        if len(coordinate) != len(placement.logical_shape) or any(
            value < 0 or value >= bound
            for value, bound in zip(coordinate, placement.logical_shape, strict=True)
        ):
            raise IndexError("Add logical coordinate is outside the tensor")
        if placement.port not in DATA_PORTS:
            return tuple(
                self._coordinate_record(
                    bundle,
                    placement,
                    slice_id,
                    (0,),
                    coordinate,
                    "replicated_independent_qparam",
                )
                for slice_id in range(self.geometry.slice_count)
            )

        plan = bundle.metadata["plan"]
        if placement.port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast":
            feature = coordinate[0]
            owner_step, local_feature = divmod(feature, plan["feature_tile"])
            slices = (
                tuple(owners[owner_step] for owners in HIGH_RING_OWNERS)
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
                else (LOW_RING_OWNERS[owner_step],)
            )
            return tuple(
                self._coordinate_record(
                    bundle,
                    placement,
                    slice_id,
                    (local_feature,),
                    coordinate,
                    "dense_vector_broadcast_replica",
                )
                for slice_id in slices
            )

        sample = coordinate[0]
        feature = coordinate[1]
        owner_step, local_feature = divmod(feature, plan["feature_tile"])
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            slot = sample_to_group(sample)
            slice_id = HIGH_RING_OWNERS[slot.group_id][owner_step]
            local_sample = slot.local_slot
        else:
            slice_id = LOW_RING_OWNERS[owner_step]
            local_sample = sample
        physical_coordinate = (
            (local_sample, local_feature)
            if len(coordinate) == 2
            else (local_sample, coordinate[2], coordinate[3], local_feature)
        )
        return (
            self._coordinate_record(
                bundle,
                placement,
                slice_id,
                physical_coordinate,
                coordinate,
                "owner_local_add_value",
            ),
        )

    @staticmethod
    def _valid_mask(
        region: Rtl28PhysicalRegion,
        *,
        broadcast: bool,
    ) -> np.ndarray:
        valid = np.zeros(region.physical_shape, dtype=np.bool_)
        if broadcast:
            valid[: region.feature_count] = True
        elif region.feature_count and region.sample_count:
            valid[: region.sample_count, ..., : region.feature_count] = True
        return valid

    def validate(self, bundle: Add28PhysicalBundle) -> dict[str, int | str]:
        if (
            bundle.operator != "QLinearAdd"
            or bundle.contract != self.contract
            or bundle.status != self.status
            or bundle.target_family != self.target_family
            or bundle.profile_id != self.profile_id
        ):
            raise ValueError("bundle identity does not match this RTL28 Add layout")
        if (
            bundle.geometry != self.geometry
            or bundle.alignment != self.alignment
            or bundle.geometry_status != self.geometry_status
            or bundle.address_order_status != self.address_order_status
        ):
            raise ValueError("Add bundle geometry or candidate status drifted")
        if tuple(item.port for item in bundle.placements) != PORT_ORDER:
            raise ValueError("Add placement port order drifted")
        if bundle.metadata.get("port_order") != PORT_ORDER:
            raise ValueError("Add metadata port order drifted")
        if len({item.tensor_id for item in bundle.placements}) != len(PORT_ORDER):
            raise ValueError("Add tensor IDs must remain unique")

        placements = {item.port: item for item in bundle.placements}
        plan = self.plan(
            a_shape=placements["A"].logical_shape,
            b_shape=placements["B"].logical_shape,
            input_offsets=bundle.metadata["plan"]["input_offsets"],
        )
        if bundle.metadata["plan"] != plan:
            raise ValueError("Add formal plan metadata drifted")
        if bundle.metadata.get("broadcast_mode") != plan["broadcast_mode"]:
            raise ValueError("Add broadcast metadata drifted")
        if bundle.metadata.get("independent_qparam_ports") != {
            "A": ("a_scale", "a_zero_point"),
            "B": ("b_scale", "b_zero_point"),
            "D": ("y_scale", "y_zero_point"),
        }:
            raise ValueError("Add independent qparam identity drifted")
        if bundle.metadata.get("simultaneous_alias_policy") != "reject_any_per_slice_live_range_overlap":
            raise ValueError("Add simultaneous alias policy drifted")
        aliases = bundle.metadata.get("input_alias_ports")
        if (
            not isinstance(bundle.metadata.get("input_alias_requested"), bool)
            or not isinstance(aliases, tuple)
            or any(port not in INPUT_PORTS for port in aliases)
            or len(set(aliases)) != len(aliases)
        ):
            raise ValueError("Add input alias metadata drifted")

        scalar_values = {
            port: self._inverse_by_port(bundle, port)
            for port in PORT_ORDER
            if port not in DATA_PORTS
        }
        for port in SCALE_PORTS:
            value = scalar_values[port][0]
            if not np.isfinite(value) or float(value) <= 0:
                raise ValueError(f"Add {port} must remain positive and finite")
        expected_tails: dict[str, int | float] = {
            "A": int(scalar_values["a_zero_point"][0]),
            "a_scale": 0.0,
            "a_zero_point": 0,
            "B": int(scalar_values["b_zero_point"][0]),
            "b_scale": 0.0,
            "b_zero_point": 0,
            "y_scale": 0.0,
            "y_zero_point": 0,
            "D": int(scalar_values["y_zero_point"][0]),
        }
        if bundle.metadata.get("tails") != expected_tails:
            raise ValueError("Add semantic tail metadata drifted")

        expected_shapes = {
            "A": plan["a_shape"],
            "B": plan["b_shape"],
            "D": plan["d_shape"],
            **{port: (1,) for port in PORT_ORDER if port not in DATA_PORTS},
        }
        for placement in bundle.placements:
            port = placement.port
            broadcast = port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast"
            expected_placement = "feature_partition" if port in DATA_PORTS else "replicated"
            expected_axis = (0 if broadcast else 1) if port in DATA_PORTS else None
            expected_tile = plan["feature_tile"] if port in DATA_PORTS else None
            expected_order = (
                _axis_order(expected_shapes[port], broadcast=broadcast)
                if port in DATA_PORTS
                else "replicated-scalar"
            )
            if (
                placement.logical_shape != expected_shapes[port]
                or placement.dtype != plan["dtypes"][port]
                or placement.placement != expected_placement
                or placement.feature_axis != expected_axis
                or placement.feature_tile != expected_tile
                or placement.physical_axis_order != expected_order
                or placement.slot_payload_bytes != plan["raw_sizes"][port]
                or placement.padding_value != expected_tails[port]
            ):
                raise ValueError(f"Add placement {port} drifted")

        if len(bundle.regions) != len(PORT_ORDER) * self.geometry.slice_count:
            raise ValueError("Add must contain one region per port and RTL28 slice")
        tail_bytes = 0
        for slice_id in range(self.geometry.slice_count):
            slice_start = self.geometry.slice_base(slice_id)
            slice_end = slice_start + self.geometry.bytes_per_slice
            slice_regions: list[Rtl28PhysicalRegion] = []
            for port in PORT_ORDER:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                descriptor = self._descriptor(port, plan, slice_id)
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
                    if getattr(region, field) != descriptor[field]:
                        raise ValueError(f"Add region {port}:{slice_id} {field} drifted")
                expected_base = slice_start + plan["offsets"][port]
                if region.base_address != expected_base or region.base_address % self.alignment:
                    raise ValueError(f"Add region {port}:{slice_id} base drifted")
                if (
                    region.payload_bytes != plan["raw_sizes"][port]
                    or region.size_bytes != plan["aligned_sizes"][port]
                    or len(payload) != region.size_bytes
                ):
                    raise ValueError("Add physical payload size drifted")
                if region.base_address < slice_start or region.base_address + region.size_bytes > slice_end:
                    raise ValueError("Add region crosses an RTL28 slice boundary")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("Add 128-bit alignment padding is corrupted")
                if port in DATA_PORTS:
                    local = self._read_array(bundle, port, slice_id)
                    broadcast = port == "B" and plan["broadcast_mode"] == "dense_vector_broadcast"
                    mask = self._valid_mask(region, broadcast=broadcast)
                    tail = local[~mask]
                    expected_tail = np.asarray(expected_tails[port], dtype=local.dtype)
                    if tail.size and not np.all(tail == expected_tail):
                        raise ValueError(f"Add {port} sample/feature tail is corrupted")
                    tail_bytes += int(tail.nbytes)
                slice_regions.append(region)
            ordered = sorted(slice_regions, key=lambda item: item.base_address)
            for left, right in zip(ordered, ordered[1:]):
                if left.base_address + left.size_bytes > right.base_address:
                    raise ValueError("Add physical regions overlap")

        if (
            plan["broadcast_mode"] == "dense_vector_broadcast"
            and self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
        ):
            for owner_step in range(len(HIGH_RING_OWNERS[0])):
                reference = bundle.read("B", HIGH_RING_OWNERS[0][owner_step])
                for group_id in range(1, len(HIGH_RING_OWNERS)):
                    if bundle.read("B", HIGH_RING_OWNERS[group_id][owner_step]) != reference:
                        raise ValueError("Add dense broadcast B replicas differ across HIGH groups")

        for port in PORT_ORDER:
            self._inverse_by_port(bundle, port)
        return {
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "port_count": len(PORT_ORDER),
            "region_count": len(bundle.regions),
            "broadcast_mode": plan["broadcast_mode"],
            "tail_bytes": tail_bytes,
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_margin_bytes": plan["capacity_margin_bytes"],
        }

    @staticmethod
    def _producer_contract(producer_bundle: Any) -> str:
        if isinstance(producer_bundle, Conv28PhysicalBundle):
            return producer_bundle.plan.contract
        contract = getattr(producer_bundle, "contract", None)
        if not isinstance(contract, str):
            raise ValueError("producer bundle has no current RTL28 layout contract")
        return contract

    @staticmethod
    def _region_feature_range(region: Any) -> tuple[int, int]:
        if hasattr(region, "feature_start") and hasattr(region, "feature_count"):
            return int(region.feature_start), int(region.feature_count)
        if hasattr(region, "logical_start") and hasattr(region, "logical_count"):
            return int(region.logical_start), int(region.logical_count)
        raise ValueError("producer D region does not expose a feature-owner range")

    def _validate_producer(self, producer_bundle: Any) -> None:
        if isinstance(producer_bundle, Conv28PhysicalBundle):
            from .conv28_layout import QLinearConvPhysicalLayout

            QLinearConvPhysicalLayout(self.profile_id).validate(producer_bundle)
        elif isinstance(producer_bundle, MatMul28PhysicalBundle):
            from .matmul28_layout import QLinearMatMulPhysicalLayout

            QLinearMatMulPhysicalLayout(self.profile_id).validate(producer_bundle)
        elif isinstance(producer_bundle, Add28PhysicalBundle):
            self.validate(producer_bundle)
        else:
            raise ValueError("unsupported RTL28 producer bundle for Add input")

    def prove_input_compatibility(
        self,
        producer_bundle: Any,
        add_bundle: Add28PhysicalBundle,
        port: Literal["A", "B"],
        *,
        require_same_base: bool = False,
    ) -> dict[str, Any]:
        if port not in INPUT_PORTS:
            raise ValueError("Add producer compatibility only accepts A/B")
        self._validate_producer(producer_bundle)
        self.validate(add_bundle)
        producer_contract = self._producer_contract(producer_bundle)
        expected_contracts = {
            CONV28_LAYOUT_IDS[self.profile_id],
            ADD28_LAYOUT_IDS[self.profile_id],
            MATMUL28_LAYOUT_IDS[self.profile_id],
        }
        if producer_contract not in expected_contracts:
            raise ValueError("producer profile or family does not match RTL28 Add")
        producer_region0 = producer_bundle.region("D", 0)
        producer_placement = producer_bundle.placement(producer_region0.tensor_id)
        consumer = next(item for item in add_bundle.placements if item.port == port)
        if producer_placement.tensor_id != consumer.tensor_id:
            raise ValueError("producer D and Add input tensor IDs differ")
        if (
            tuple(producer_placement.logical_shape) != consumer.logical_shape
            or producer_placement.dtype != consumer.dtype
        ):
            raise ValueError("producer D logical shape or dtype differs from Add input")

        same_bases = True
        for slice_id in range(self.geometry.slice_count):
            producer = producer_bundle.region("D", slice_id)
            consumer_region = add_bundle.region(port, slice_id)
            producer_feature = self._region_feature_range(producer)
            consumer_feature = (
                consumer_region.feature_start,
                consumer_region.feature_count,
            )
            for field in (
                "payload_bytes",
                "size_bytes",
                "physical_shape",
                "active",
                "group_id",
                "owner_step",
                "sample_start",
                "sample_count",
                "storage_sample_count",
            ):
                if getattr(producer, field) != getattr(consumer_region, field):
                    raise ValueError(
                        f"producer D and Add {port} region {field} differ"
                    )
            if producer_feature != consumer_feature:
                raise ValueError("producer D and Add input feature ownership differs")
            if producer_bundle.read("D", slice_id) != add_bundle.read(port, slice_id):
                raise ValueError("producer D and Add input physical bytes differ")
            same_bases &= producer.base_address == consumer_region.base_address
        if require_same_base and not same_bases:
            raise ValueError("producer D and Add input require an explicit base transition")
        return {
            "compatible": True,
            "producer_contract": producer_contract,
            "consumer_contract": self.contract,
            "profile_id": self.profile_id,
            "port": port,
            "shared_tensor_id": consumer.tensor_id,
            "slice_count": self.geometry.slice_count,
            "all_physical_bytes_equal": True,
            "all_base_addresses_equal": same_bases,
            "exact_alias": same_bases,
            "memory_plan_rebase_required": not same_bases,
            "candidate_unapproved": True,
        }

    def prove_simultaneous_alias_safety(
        self,
        producer_a: Any,
        producer_b: Any,
        add_bundle: Add28PhysicalBundle,
    ) -> dict[str, Any]:
        proof_a = self.prove_input_compatibility(
            producer_a, add_bundle, "A", require_same_base=True
        )
        proof_b = self.prove_input_compatibility(
            producer_b, add_bundle, "B", require_same_base=True
        )
        if proof_a["shared_tensor_id"] == proof_b["shared_tensor_id"]:
            raise ValueError("simultaneous Add branches must have distinct tensor IDs")
        checked: list[dict[str, int]] = []
        for slice_id in range(self.geometry.slice_count):
            left = producer_a.region("D", slice_id)
            right = producer_b.region("D", slice_id)
            left_range = (left.base_address, left.base_address + left.size_bytes)
            right_range = (right.base_address, right.base_address + right.size_bytes)
            if _ranges_overlap(left_range, right_range):
                raise ValueError(
                    f"simultaneous Add producer D ranges overlap on slice {slice_id}"
                )
            checked.append(
                {
                    "slice_id": slice_id,
                    "a_start": left_range[0],
                    "a_stop": left_range[1],
                    "b_start": right_range[0],
                    "b_stop": right_range[1],
                }
            )
        return {
            "compatible": True,
            "exact_alias_A": True,
            "exact_alias_B": True,
            "simultaneously_live": True,
            "distinct_tensor_ids": True,
            "all_slice_ranges_non_overlapping": True,
            "slice_count": self.geometry.slice_count,
            "checked_ranges": tuple(checked),
            "candidate_unapproved": True,
        }


__all__ = [
    "ADD28_LAYOUT_IDS",
    "PORT_ORDER",
    "Add28PhysicalBundle",
    "QLinearAddPhysicalLayout",
]
