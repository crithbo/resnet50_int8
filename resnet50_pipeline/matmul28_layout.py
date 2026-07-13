"""Reversible RTL28 candidate layout for the ResNet-50 QLinearMatMul.

This module freezes software evidence, not an approved hardware address map.
The group profile executes the fixed batch in seven HIGH rings: A owns K
chunks, while B/P/D own O chunks and B is copied once into every group.  The
global profile uses the explicit LOW-ring owner order for the same K/O split.
No physical owner is derived from numeric adjacency or ``slice_id % 28``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

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
from .simple_layout import (
    SIMPLE_LAYOUT_IDS,
    QuantizeLinearPhysicalLayout,
    Rtl28PhysicalRegion,
    Rtl28PortPlacement,
)
from .topology28 import Direction, HIGH_RING_OWNERS, LOW_RING_OWNERS, TOPOLOGY28


MATMUL28_LAYOUT_IDS = {
    GROUP4X7_BATCH_CHANNEL28_PROFILE: (
        "w4_qlinearmatmul_group4x7_28_candidate_v1"
    ),
    GLOBAL_RING28_PROFILE: "w4_qlinearmatmul_global_ring28_candidate_v1",
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
    "multiplier",
    "P",
    "D",
)

DEFAULT_TENSOR_IDS = {
    "A": "matmul_input",
    "a_scale": "matmul_a_scale",
    "a_zero_point": "matmul_a_zero_point",
    "B": "matmul_weight",
    "b_scale": "matmul_b_scale",
    "b_zero_point": "matmul_b_zero_point",
    "y_scale": "matmul_y_scale",
    "y_zero_point": "matmul_y_zero_point",
    "multiplier": "matmul_multiplier",
    "P": "matmul_accumulator",
    "D": "matmul_output",
}


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _canonical(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


def _scalar(
    value: np.ndarray,
    dtype: np.dtype,
    name: str,
    *,
    positive: bool = False,
) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype != dtype or array.shape != (1,):
        raise TypeError(f"{name} must have dtype {dtype} and shape (1,)")
    if positive and (not np.isfinite(array[0]) or array[0] <= 0):
        raise TypeError(f"{name} must contain one positive finite value")
    return _canonical(array)


@dataclass(frozen=True)
class MatMul28PhysicalBundle:
    """Physical bytes plus public C1 placement/region records."""

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
            raise KeyError(f"expected one region for port {port!r} on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        plan = self.metadata["plan"]
        specs = self.metadata["port_specs"]
        records: list[LayoutRecord] = []
        for placement in self.placements:
            spec = specs[placement.port]
            if spec["role"] == "replicated":
                partition = {
                    "axis": None,
                    "policy": "replicated_on_every_rtl28_slice",
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                }
            else:
                partition = {
                    "axis": 1,
                    "policy": spec["partition_policy"],
                    "slice_count": self.geometry.slice_count,
                    "profile_id": self.profile_id,
                    "tile": spec["tile"],
                    "owner_order": plan["owner_order"],
                    "batch_group_sample_counts": (
                        GROUP_SAMPLE_COUNTS
                        if self.profile_id
                        == GROUP4X7_BATCH_CHANNEL28_PROFILE
                        else None
                    ),
                }
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-matmul28-{placement.port.lower()}-"
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
                        "physical_axis_order": placement.physical_axis_order,
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "subword_bytes": self.geometry.subword_bytes,
                        "tail_value": placement.padding_value,
                        "geometry_status": self.geometry_status,
                        "address_order_status": self.address_order_status,
                        "psum_boundary": (
                            "final_int32_accumulator_after_complete_K"
                            if placement.port == "P"
                            else None
                        ),
                    },
                    base_addresses=tuple(
                        self.region(placement.port, slice_id).base_address
                        for slice_id in range(self.geometry.slice_count)
                    ),
                    inverse_status="validated",
                    alias_of=(
                        placement.tensor_id
                        if placement.port == "A"
                        and self.metadata["input_alias_requested"]
                        else None
                    ),
                )
            )
        return tuple(records)


class QLinearMatMulPhysicalLayout:
    """Current 28-slice software candidate for QLinearMatMul."""

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
            raise ValueError("current MatMul layout requires TARGET_DRAM_GEOMETRY28")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment
        self.contract = MATMUL28_LAYOUT_IDS[self.profile_id]

    @property
    def owner_count(self) -> int:
        return (
            len(HIGH_RING_OWNERS[0])
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else len(LOW_RING_OWNERS)
        )

    @property
    def owner_order(self) -> tuple[tuple[int, ...], ...] | tuple[int, ...]:
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            return HIGH_RING_OWNERS
        return LOW_RING_OWNERS

    def _alias_offset(self, addresses: tuple[int, ...] | None) -> int:
        if addresses is None:
            return 0
        if len(addresses) != self.geometry.slice_count:
            raise ValueError("MatMul input_base_addresses must contain 28 addresses")
        offsets: list[int] = []
        for slice_id, raw_address in enumerate(addresses):
            address = int(raw_address)
            start = self.geometry.slice_base(slice_id)
            end = start + self.geometry.bytes_per_slice
            if not start <= address < end:
                raise ValueError("MatMul aliased input base is outside its slice")
            offset = address - start
            if offset % self.alignment:
                raise ValueError("MatMul aliased input base is not aligned")
            offsets.append(offset)
        if len(set(offsets)) != 1:
            raise ValueError("MatMul aliased bases need one common slice offset")
        return offsets[0]

    def plan(
        self,
        *,
        activation_shape: tuple[int, int],
        weight_shape: tuple[int, int],
        weight_dtype: np.dtype | str = np.dtype("int8"),
        input_offset: int = 0,
    ) -> dict[str, Any]:
        """Return a deterministic per-slice allocation and capacity plan."""

        if len(activation_shape) != 2 or len(weight_shape) != 2:
            raise ValueError("RTL28 MatMul requires rank-2 A and B")
        n, reduction = tuple(int(value) for value in activation_shape)
        weight_k, outputs = tuple(int(value) for value in weight_shape)
        if any(value <= 0 for value in (n, reduction, weight_k, outputs)):
            raise ValueError("MatMul dimensions must be positive")
        if n != BATCH_SIZE:
            raise ValueError(f"RTL28 MatMul requires batch={BATCH_SIZE}")
        if reduction != weight_k:
            raise ValueError("MatMul A reduction dimension differs from B")
        parsed_weight_dtype = np.dtype(weight_dtype)
        if parsed_weight_dtype not in (np.dtype("int8"), np.dtype("uint8")):
            raise TypeError("MatMul B must have dtype int8 or uint8")
        if input_offset < 0 or input_offset % self.alignment:
            raise ValueError("MatMul input_offset must be non-negative and aligned")

        k_tile = math.ceil(reduction / self.owner_count)
        o_tile = math.ceil(outputs / self.owner_count)
        storage_samples = (
            max(GROUP_SAMPLE_COUNTS)
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else BATCH_SIZE
        )
        physical_shapes = {
            "A": (storage_samples, k_tile),
            "a_scale": (1,),
            "a_zero_point": (1,),
            "B": (reduction, o_tile),
            "b_scale": (1,),
            "b_zero_point": (1,),
            "y_scale": (1,),
            "y_zero_point": (1,),
            "multiplier": (1,),
            "P": (storage_samples, o_tile),
            "D": (storage_samples, o_tile),
        }
        dtypes = {
            "A": np.dtype("uint8"),
            "a_scale": np.dtype("float32"),
            "a_zero_point": np.dtype("uint8"),
            "B": parsed_weight_dtype,
            "b_scale": np.dtype("float32"),
            "b_zero_point": parsed_weight_dtype,
            "y_scale": np.dtype("float32"),
            "y_zero_point": np.dtype("uint8"),
            "multiplier": np.dtype("float32"),
            "P": np.dtype("int32"),
            "D": np.dtype("uint8"),
        }
        raw_sizes = {
            port: math.prod(physical_shapes[port]) * dtypes[port].itemsize
            for port in PORT_ORDER
        }
        aligned_sizes = {
            port: _align(raw_sizes[port], self.alignment) for port in PORT_ORDER
        }
        offsets = {"A": input_offset}
        cursor = input_offset + aligned_sizes["A"]
        for port in PORT_ORDER[1:]:
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += aligned_sizes[port]
        capacity = self.geometry.bytes_per_slice
        if cursor > capacity:
            raise ValueError("RTL28 MatMul regions exceed one slice capacity")
        return {
            "profile_id": self.profile_id,
            "activation_shape": (n, reduction),
            "weight_shape": (weight_k, outputs),
            "output_shape": (n, outputs),
            "weight_dtype": str(parsed_weight_dtype),
            "owner_count": self.owner_count,
            "owner_order": self.owner_order,
            "storage_sample_count": storage_samples,
            "k_tile": k_tile,
            "o_tile": o_tile,
            "k_padded": k_tile * self.owner_count,
            "o_padded": o_tile * self.owner_count,
            "physical_shapes": physical_shapes,
            "raw_sizes": raw_sizes,
            "aligned_sizes": aligned_sizes,
            "offsets": offsets,
            "input_offset": input_offset,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": capacity,
            "capacity_margin_bytes": capacity - cursor,
            "ring_steps": self.owner_count,
            "neighbor_transfers": self.owner_count - 1,
        }

    def capacity_report(
        self,
        *,
        activation_shape: tuple[int, int],
        weight_shape: tuple[int, int],
        weight_dtype: np.dtype | str = np.dtype("int8"),
        input_offset: int = 0,
    ) -> dict[str, Any]:
        plan = self.plan(
            activation_shape=activation_shape,
            weight_shape=weight_shape,
            weight_dtype=weight_dtype,
            input_offset=input_offset,
        )
        return {
            "profile_id": self.profile_id,
            "shape": {
                "A": plan["activation_shape"],
                "B": plan["weight_shape"],
                "P": plan["output_shape"],
                "D": plan["output_shape"],
            },
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_bytes": plan["capacity_bytes"],
            "capacity_margin_bytes": plan["capacity_margin_bytes"],
            "fits": True,
            "candidate_unapproved": True,
        }

    def _slice_owner(self, slice_id: int) -> tuple[int | None, int]:
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id = TOPOLOGY28.group_for_slice(slice_id)
            owners = HIGH_RING_OWNERS[group_id]
            return group_id, owners.index(slice_id)
        return None, LOW_RING_OWNERS.index(slice_id)

    def _descriptor(
        self, port: str, plan: dict[str, Any], slice_id: int
    ) -> dict[str, Any]:
        if port not in {"A", "B", "P", "D"}:
            return {
                "physical_shape": (1,),
                "active": True,
                "group_id": None,
                "owner_step": None,
                "sample_start": 0,
                "sample_count": BATCH_SIZE,
                "storage_sample_count": BATCH_SIZE,
                "feature_start": 0,
                "feature_count": 1,
            }

        group_id, owner_step = self._slice_owner(slice_id)
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            assert group_id is not None
            sample_range = group_to_sample_range(group_id)
            sample_start = sample_range.start
            sample_count = sample_range.sample_count
            storage_samples = max(GROUP_SAMPLE_COUNTS)
        else:
            sample_start = 0
            sample_count = BATCH_SIZE
            storage_samples = BATCH_SIZE

        if port == "A":
            logical_features = plan["activation_shape"][1]
            tile = plan["k_tile"]
            physical_shape = (storage_samples, tile)
        else:
            logical_features = plan["output_shape"][1]
            tile = plan["o_tile"]
            physical_shape = (
                (plan["weight_shape"][0], tile)
                if port == "B"
                else (storage_samples, tile)
            )
        feature_start = owner_step * tile
        feature_count = max(0, min(tile, logical_features - feature_start))
        return {
            "physical_shape": physical_shape,
            "active": feature_count > 0,
            "group_id": group_id,
            "owner_step": owner_step,
            "sample_start": 0 if port == "B" else sample_start,
            "sample_count": 0 if port == "B" else sample_count,
            "storage_sample_count": 0 if port == "B" else storage_samples,
            "feature_start": feature_start,
            "feature_count": feature_count,
        }

    def _port_specs(self, plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
        grouped = self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
        specs = {
            "A": {
                "role": "A_K_partition",
                "tile": plan["k_tile"],
                "physical_axis_order": "NK-local",
                "partition_policy": (
                    "seven_high_groups_sample_and_K_partition"
                    if grouped
                    else "global_low_ring_K_partition"
                ),
            },
            "B": {
                "role": "B_O_partition",
                "tile": plan["o_tile"],
                "physical_axis_order": "K-global,O-local",
                "partition_policy": (
                    "O_partition_replicated_across_seven_high_groups"
                    if grouped
                    else "global_low_ring_O_partition"
                ),
            },
            "P": {
                "role": "P_O_partition",
                "tile": plan["o_tile"],
                "physical_axis_order": "NO-local",
                "partition_policy": (
                    "seven_high_groups_sample_and_O_partition"
                    if grouped
                    else "global_low_ring_O_partition"
                ),
            },
            "D": {
                "role": "D_O_partition",
                "tile": plan["o_tile"],
                "physical_axis_order": "NO-local",
                "partition_policy": (
                    "seven_high_groups_sample_and_O_partition"
                    if grouped
                    else "global_low_ring_O_partition"
                ),
            },
        }
        for port in PORT_ORDER:
            if port not in specs:
                specs[port] = {
                    "role": "replicated",
                    "tile": None,
                    "physical_axis_order": "replicated-scalar",
                    "partition_policy": "replicated_on_every_rtl28_slice",
                }
        return specs

    @staticmethod
    def _tensor_ids(overrides: dict[str, str] | None) -> dict[str, str]:
        unknown = set(overrides or {}) - set(PORT_ORDER)
        if unknown:
            raise ValueError(f"unknown MatMul tensor-id ports: {sorted(unknown)}")
        ids = {**DEFAULT_TENSOR_IDS, **(overrides or {})}
        if any(not isinstance(value, str) or not value for value in ids.values()):
            raise ValueError("MatMul tensor IDs must be non-empty strings")
        if len(set(ids.values())) != len(ids):
            raise ValueError("MatMul tensor IDs must be unique within the bundle")
        return ids

    def forward(
        self,
        *,
        activation: np.ndarray,
        weight: np.ndarray,
        a_scale: np.ndarray,
        a_zero_point: np.ndarray,
        b_scale: np.ndarray,
        b_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        accumulator: np.ndarray,
        output: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
        input_base_addresses: tuple[int, ...] | None = None,
    ) -> MatMul28PhysicalBundle:
        activation = np.asarray(activation)
        weight = np.asarray(weight)
        accumulator = np.asarray(accumulator)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 2:
            raise TypeError("MatMul A must be rank-2 uint8")
        if weight.dtype not in (np.dtype("int8"), np.dtype("uint8")) or weight.ndim != 2:
            raise TypeError("MatMul B must be rank-2 int8 or uint8")
        plan = self.plan(
            activation_shape=tuple(activation.shape),
            weight_shape=tuple(weight.shape),
            weight_dtype=weight.dtype,
            input_offset=self._alias_offset(input_base_addresses),
        )
        if accumulator.dtype != np.int32 or tuple(accumulator.shape) != plan["output_shape"]:
            raise TypeError("MatMul P must be int32 [N,O]")
        if output.dtype != np.uint8 or tuple(output.shape) != plan["output_shape"]:
            raise TypeError("MatMul D must be uint8 [N,O]")

        scalars = {
            "a_scale": _scalar(
                a_scale, np.dtype("float32"), "a_scale", positive=True
            ),
            "a_zero_point": _scalar(
                a_zero_point, np.dtype("uint8"), "a_zero_point"
            ),
            "b_scale": _scalar(
                b_scale, np.dtype("float32"), "b_scale", positive=True
            ),
            "b_zero_point": _scalar(
                b_zero_point, weight.dtype, "b_zero_point"
            ),
            "y_scale": _scalar(
                y_scale, np.dtype("float32"), "y_scale", positive=True
            ),
            "y_zero_point": _scalar(
                y_zero_point, np.dtype("uint8"), "y_zero_point"
            ),
        }
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            multiplier_value = np.float32(
                scalars["a_scale"][0]
                * scalars["b_scale"][0]
                / scalars["y_scale"][0]
            )
        if not np.isfinite(multiplier_value) or multiplier_value <= 0:
            raise ValueError("MatMul derived requant multiplier must be positive and finite")
        multiplier = np.array([multiplier_value], dtype=np.float32)
        arrays = {
            "A": _canonical(activation),
            "B": _canonical(weight),
            "P": _canonical(accumulator),
            "D": _canonical(output),
            **scalars,
            "multiplier": _canonical(multiplier),
        }
        ids = self._tensor_ids(tensor_ids)
        tails: dict[str, int | float] = {
            "A": int(scalars["a_zero_point"][0]),
            "B": int(scalars["b_zero_point"][0]),
            "P": 0,
            "D": int(scalars["y_zero_point"][0]),
            "a_scale": 0.0,
            "a_zero_point": 0,
            "b_scale": 0.0,
            "b_zero_point": 0,
            "y_scale": 0.0,
            "y_zero_point": 0,
            "multiplier": 0.0,
        }
        port_specs = self._port_specs(plan)

        logical_shapes = {
            "A": tuple(activation.shape),
            "B": tuple(weight.shape),
            "P": tuple(accumulator.shape),
            "D": tuple(output.shape),
            **{port: (1,) for port in PORT_ORDER if port not in {"A", "B", "P", "D"}},
        }
        placements = tuple(
            Rtl28PortPlacement(
                port=port,
                tensor_id=ids[port],
                logical_shape=logical_shapes[port],
                dtype=str(arrays[port].dtype),
                placement=(
                    "feature_partition"
                    if port in {"A", "B", "P", "D"}
                    else "replicated"
                ),
                feature_axis=1 if port in {"A", "B", "P", "D"} else None,
                feature_tile=port_specs[port]["tile"],
                physical_axis_order=port_specs[port]["physical_axis_order"],
                slot_payload_bytes=plan["raw_sizes"][port],
                padding_value=tails[port],
            )
            for port in PORT_ORDER
        )

        payloads: dict[tuple[str, int], bytes] = {}
        regions: list[Rtl28PhysicalRegion] = []
        for port in PORT_ORDER:
            placement = next(item for item in placements if item.port == port)
            for slice_id in range(self.geometry.slice_count):
                descriptor = self._descriptor(port, plan, slice_id)
                if port not in {"A", "B", "P", "D"}:
                    local = arrays[port]
                else:
                    local = np.full(
                        descriptor["physical_shape"],
                        tails[port],
                        dtype=arrays[port].dtype,
                    )
                    count = descriptor["feature_count"]
                    start = descriptor["feature_start"]
                    if count:
                        if port == "B":
                            local[:, :count] = arrays[port][:, start : start + count]
                        else:
                            sample_start = descriptor["sample_start"]
                            sample_count = descriptor["sample_count"]
                            local[:sample_count, :count] = arrays[port][
                                sample_start : sample_start + sample_count,
                                start : start + count,
                            ]
                raw = _canonical(local).tobytes(order="C")
                if len(raw) != plan["raw_sizes"][port]:
                    raise AssertionError("MatMul physical payload-size calculation drifted")
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

        bundle = MatMul28PhysicalBundle(
            operator="QLinearMatMul",
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
                "port_specs": port_specs,
                "tails": tails,
                "input_alias_requested": input_base_addresses is not None,
                "formal_qparams": "scalar_per_tensor",
                "accumulator_scope": "final_int32_after_complete_K",
            },
        )
        self.validate(bundle)
        return bundle

    def _read_array(
        self, bundle: MatMul28PhysicalBundle, port: str, slice_id: int
    ) -> np.ndarray:
        placement = next(item for item in bundle.placements if item.port == port)
        region = bundle.region(port, slice_id)
        dtype = np.dtype(placement.dtype).newbyteorder("<")
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes], dtype=dtype
        ).reshape(region.physical_shape)

    def _inverse_by_port(
        self, bundle: MatMul28PhysicalBundle, port: str
    ) -> np.ndarray:
        placement = next(item for item in bundle.placements if item.port == port)
        native_dtype = np.dtype(placement.dtype)
        if port not in {"A", "B", "P", "D"}:
            copies = [
                self._read_array(bundle, port, slice_id)
                for slice_id in range(self.geometry.slice_count)
            ]
            if any(not np.array_equal(copies[0], item) for item in copies[1:]):
                raise ValueError(f"replicated MatMul port {port} differs between slices")
            return copies[0].astype(native_dtype, copy=True)

        output = np.empty(placement.logical_shape, dtype=native_dtype)
        if port == "B":
            output_coverage = np.zeros(placement.logical_shape[1], dtype=np.bool_)
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                for owner_step in range(self.owner_count):
                    slice_ids = tuple(
                        owners[owner_step] for owners in HIGH_RING_OWNERS
                    )
                    copies = [
                        self._read_array(bundle, port, slice_id)
                        for slice_id in slice_ids
                    ]
                    if any(
                        not np.array_equal(copies[0], item) for item in copies[1:]
                    ):
                        raise ValueError(
                            f"MatMul B owner {owner_step} differs across HIGH groups"
                        )
                    region = bundle.region(port, slice_ids[0])
                    source = copies[0]
                    if region.feature_count:
                        start = region.feature_start
                        stop = start + region.feature_count
                        if output_coverage[start:stop].any():
                            raise ValueError("MatMul B O-owner ranges overlap")
                        output[:, start:stop] = source[:, : region.feature_count]
                        output_coverage[start:stop] = True
            else:
                for slice_id in LOW_RING_OWNERS:
                    region = bundle.region(port, slice_id)
                    if region.feature_count:
                        start = region.feature_start
                        stop = start + region.feature_count
                        if output_coverage[start:stop].any():
                            raise ValueError("MatMul B O-owner ranges overlap")
                        output[:, start:stop] = self._read_array(
                            bundle, port, slice_id
                        )[:, : region.feature_count]
                        output_coverage[start:stop] = True
            if not output_coverage.all():
                raise ValueError("MatMul B O-owner ranges do not cover the tensor")
            return output

        coverage = np.zeros(placement.logical_shape, dtype=np.bool_)
        owner_sequence = (
            tuple(owner for owners in HIGH_RING_OWNERS for owner in owners)
            if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE
            else LOW_RING_OWNERS
        )
        for slice_id in owner_sequence:
            region = bundle.region(port, slice_id)
            if not region.feature_count:
                continue
            sample_stop = region.sample_start + region.sample_count
            feature_stop = region.feature_start + region.feature_count
            destination = coverage[
                region.sample_start:sample_stop,
                region.feature_start:feature_stop,
            ]
            if destination.any():
                raise ValueError(f"MatMul {port} owner ranges overlap")
            local = self._read_array(bundle, port, slice_id)
            output[
                region.sample_start:sample_stop,
                region.feature_start:feature_stop,
            ] = local[: region.sample_count, : region.feature_count]
            destination[:] = True
        if not coverage.all():
            raise ValueError(f"MatMul {port} owner ranges do not cover the tensor")
        return output

    def inverse_port(
        self, bundle: MatMul28PhysicalBundle, tensor_id: str
    ) -> np.ndarray:
        return self._inverse_by_port(bundle, bundle.placement(tensor_id).port)

    def inverse(self, bundle: MatMul28PhysicalBundle) -> dict[str, np.ndarray]:
        return {
            placement.tensor_id: self._inverse_by_port(bundle, placement.port)
            for placement in bundle.placements
        }

    def explain_coordinate(
        self,
        bundle: MatMul28PhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        placement = bundle.placement(tensor_id)
        if len(coordinate) != len(placement.logical_shape):
            raise ValueError("coordinate rank does not match MatMul tensor rank")
        if any(
            index < 0 or index >= size
            for index, size in zip(coordinate, placement.logical_shape, strict=True)
        ):
            raise IndexError("MatMul logical coordinate is out of range")
        port = placement.port
        if port not in {"A", "B", "P", "D"}:
            slice_ids = tuple(range(self.geometry.slice_count))
            local_coordinate = coordinate
        else:
            tile = int(placement.feature_tile)
            feature = coordinate[1]
            owner_step = feature // tile
            local_feature = feature - owner_step * tile
            if port == "B":
                local_coordinate = (coordinate[0], local_feature)
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                    slice_ids = tuple(
                        owners[owner_step] for owners in HIGH_RING_OWNERS
                    )
                else:
                    slice_ids = (LOW_RING_OWNERS[owner_step],)
            else:
                if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
                    assignment = sample_to_group(coordinate[0])
                    slice_ids = (
                        HIGH_RING_OWNERS[assignment.group_id][owner_step],
                    )
                    local_sample = assignment.local_slot
                else:
                    slice_ids = (LOW_RING_OWNERS[owner_step],)
                    local_sample = coordinate[0]
                local_coordinate = (local_sample, local_feature)

        dtype = np.dtype(placement.dtype)
        first_region = bundle.region(port, slice_ids[0])
        element_index = int(
            np.ravel_multi_index(local_coordinate, first_region.physical_shape)
        )
        byte_offset = element_index * dtype.itemsize
        explanations: list[dict[str, Any]] = []
        for slice_id in slice_ids:
            region = bundle.region(port, slice_id)
            for element_byte in range(dtype.itemsize):
                address = region.base_address + byte_offset + element_byte
                explanations.append(
                    {
                        "tensor_id": tensor_id,
                        "port": port,
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
                            if port not in {"A", "B", "P", "D"}
                            else "final_accumulator"
                            if port == "P"
                            else "data"
                        ),
                    }
                )
        return tuple(explanations)

    def explain_reduction_step(
        self,
        bundle: MatMul28PhysicalBundle,
        *,
        sample_id: int,
        output_feature: int,
        step: int,
    ) -> dict[str, Any]:
        plan = bundle.metadata["plan"]
        if not 0 <= sample_id < BATCH_SIZE:
            raise IndexError("MatMul sample_id is out of range")
        if not 0 <= output_feature < plan["output_shape"][1]:
            raise IndexError("MatMul output_feature is out of range")
        if not 0 <= step < self.owner_count:
            raise IndexError("MatMul reduction step is out of range")
        output_owner_step = output_feature // plan["o_tile"]
        if self.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id = sample_to_group(sample_id).group_id
            ring = TOPOLOGY28.high_ring_for_group(group_id)
            output_owner = HIGH_RING_OWNERS[group_id][output_owner_step]
        else:
            group_id = None
            ring = TOPOLOGY28.low_ring
            output_owner = LOW_RING_OWNERS[output_owner_step]
        input_owner = ring.walk(output_owner, Direction.NEXT, step)
        input_owner_step = ring.owners.index(input_owner)
        reduction_start = input_owner_step * plan["k_tile"]
        reduction_stop = min(
            plan["activation_shape"][1], reduction_start + plan["k_tile"]
        )
        return {
            "profile_id": self.profile_id,
            "group_id": group_id,
            "sample_id": sample_id,
            "output_feature": output_feature,
            "output_owner_slice": output_owner,
            "step": step,
            "input_owner_slice": input_owner,
            "reduction_range": (
                min(plan["activation_shape"][1], reduction_start),
                reduction_stop,
            ),
            "has_data": reduction_start < plan["activation_shape"][1],
            "last": step == self.owner_count - 1,
            "route_source": "explicit_RTL_HIGH_or_LOW_next_map",
        }

    def classify_quantize_input_transition(
        self,
        producer_bundle: Any,
        matmul_bundle: MatMul28PhysicalBundle,
        *,
        producer_tensor_id: str,
        require_same_base: bool = False,
    ) -> dict[str, Any]:
        if producer_bundle.profile_id != self.profile_id:
            if (
                producer_bundle.profile_id
                == GROUP4X7_BATCH_CHANNEL28_PROFILE
                and self.profile_id == GLOBAL_RING28_PROFILE
            ):
                return {
                    "compatible": False,
                    "exact_alias": False,
                    "transition_required": True,
                    "transition": (
                        "group4x7_to_global_low_relayout_after_GAP_before_MatMul"
                    ),
                    "source_profile": producer_bundle.profile_id,
                    "target_profile": self.profile_id,
                    "candidate_unapproved": True,
                }
            raise ValueError("unsupported Quantize-to-MatMul profile transition")
        proof = self.prove_quantize_input_compatibility(
            producer_bundle,
            matmul_bundle,
            producer_tensor_id=producer_tensor_id,
            require_same_base=require_same_base,
        )
        return {**proof, "transition_required": False, "transition": None}

    def prove_quantize_input_compatibility(
        self,
        producer_bundle: Any,
        matmul_bundle: MatMul28PhysicalBundle,
        *,
        producer_tensor_id: str,
        require_same_base: bool = False,
    ) -> dict[str, Any]:
        if (
            producer_bundle.operator != "QuantizeLinear"
            or producer_bundle.contract != SIMPLE_LAYOUT_IDS[self.profile_id]
            or producer_bundle.status != "candidate"
            or producer_bundle.target_family != "rtl28"
            or producer_bundle.profile_id != self.profile_id
            or matmul_bundle.profile_id != self.profile_id
            or producer_bundle.geometry != self.geometry
            or matmul_bundle.geometry != self.geometry
        ):
            raise ValueError("Quantize D and MatMul A must use the same RTL28 profile")
        QuantizeLinearPhysicalLayout(self.profile_id).validate(producer_bundle)
        self.validate(matmul_bundle)
        producer = producer_bundle.placement(producer_tensor_id)
        consumer = next(
            item for item in matmul_bundle.placements if item.port == "A"
        )
        if producer.port != "D":
            raise ValueError("MatMul input producer must be a Quantize D port")
        if producer.tensor_id != consumer.tensor_id:
            raise ValueError("Quantize D and MatMul A tensor IDs differ")
        for field in (
            "logical_shape",
            "dtype",
            "placement",
            "feature_axis",
            "feature_tile",
            "slot_payload_bytes",
            "padding_value",
        ):
            if getattr(producer, field) != getattr(consumer, field):
                raise ValueError(f"Quantize D and MatMul A {field} differ")

        same_bases = True
        for slice_id in range(self.geometry.slice_count):
            source_region = producer_bundle.region("D", slice_id)
            target_region = matmul_bundle.region("A", slice_id)
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
                "feature_start",
                "feature_count",
            ):
                if getattr(source_region, field) != getattr(target_region, field):
                    raise ValueError(
                        f"Quantize D and MatMul A region {field} differ"
                    )
            if producer_bundle.read("D", slice_id) != matmul_bundle.read(
                "A", slice_id
            ):
                raise ValueError("Quantize D and MatMul A physical bytes differ")
            same_bases &= source_region.base_address == target_region.base_address
        if require_same_base and not same_bases:
            raise ValueError("Quantize D and MatMul A require an explicit base transition")
        return {
            "compatible": True,
            "byte_compatible": True,
            "exact_alias": same_bases,
            "shared_tensor_id": consumer.tensor_id,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "candidate_unapproved": True,
        }

    @staticmethod
    def _tail_mask(region: Rtl28PhysicalRegion) -> np.ndarray:
        valid = np.zeros(region.physical_shape, dtype=np.bool_)
        if region.port == "B":
            if region.feature_count:
                valid[:, : region.feature_count] = True
        elif region.feature_count:
            valid[: region.sample_count, : region.feature_count] = True
        return valid

    def validate(
        self, bundle: MatMul28PhysicalBundle
    ) -> dict[str, int | str]:
        if (
            bundle.operator != "QLinearMatMul"
            or bundle.contract != self.contract
            or bundle.status != self.status
            or bundle.target_family != self.target_family
            or bundle.profile_id != self.profile_id
        ):
            raise ValueError("bundle identity does not match this RTL28 MatMul layout")
        if (
            bundle.geometry != self.geometry
            or bundle.alignment != self.alignment
            or bundle.geometry_status != self.geometry_status
            or bundle.address_order_status != self.address_order_status
        ):
            raise ValueError("MatMul bundle geometry or candidate status drifted")
        if tuple(item.port for item in bundle.placements) != PORT_ORDER:
            raise ValueError("MatMul placement port order drifted")
        if bundle.metadata["port_order"] != PORT_ORDER:
            raise ValueError("MatMul metadata port order drifted")

        a_placement = next(item for item in bundle.placements if item.port == "A")
        b_placement = next(item for item in bundle.placements if item.port == "B")
        plan = self.plan(
            activation_shape=a_placement.logical_shape,
            weight_shape=b_placement.logical_shape,
            weight_dtype=b_placement.dtype,
            input_offset=bundle.metadata["plan"]["input_offset"],
        )
        if bundle.metadata["plan"] != plan:
            raise ValueError("MatMul formal plan metadata drifted")
        expected_specs = self._port_specs(plan)
        if bundle.metadata["port_specs"] != expected_specs:
            raise ValueError("MatMul port-spec metadata drifted")
        if (
            bundle.metadata["formal_qparams"] != "scalar_per_tensor"
            or bundle.metadata["accumulator_scope"]
            != "final_int32_after_complete_K"
            or not isinstance(bundle.metadata["input_alias_requested"], bool)
        ):
            raise ValueError("MatMul lowering metadata drifted")

        expected_shapes = {
            "A": plan["activation_shape"],
            "B": plan["weight_shape"],
            "P": plan["output_shape"],
            "D": plan["output_shape"],
            **{
                port: (1,)
                for port in PORT_ORDER
                if port not in {"A", "B", "P", "D"}
            },
        }
        expected_dtypes = {
            "A": "uint8",
            "a_scale": "float32",
            "a_zero_point": "uint8",
            "B": plan["weight_dtype"],
            "b_scale": "float32",
            "b_zero_point": plan["weight_dtype"],
            "y_scale": "float32",
            "y_zero_point": "uint8",
            "multiplier": "float32",
            "P": "int32",
            "D": "uint8",
        }
        if len({item.tensor_id for item in bundle.placements}) != len(PORT_ORDER):
            raise ValueError("MatMul tensor IDs must remain unique")
        for placement in bundle.placements:
            port = placement.port
            is_data = port in {"A", "B", "P", "D"}
            if (
                placement.logical_shape != expected_shapes[port]
                or placement.dtype != expected_dtypes[port]
                or placement.placement
                != ("feature_partition" if is_data else "replicated")
                or placement.feature_axis != (1 if is_data else None)
                or placement.feature_tile != expected_specs[port]["tile"]
                or placement.physical_axis_order
                != expected_specs[port]["physical_axis_order"]
                or placement.slot_payload_bytes != plan["raw_sizes"][port]
            ):
                raise ValueError(f"MatMul placement {port} drifted")

        scalar_values = {
            port: self._inverse_by_port(bundle, port)
            for port in PORT_ORDER
            if port not in {"A", "B", "P", "D"}
        }
        expected_tails: dict[str, int | float] = {
            "A": int(scalar_values["a_zero_point"][0]),
            "B": int(scalar_values["b_zero_point"][0]),
            "P": 0,
            "D": int(scalar_values["y_zero_point"][0]),
            "a_scale": 0.0,
            "a_zero_point": 0,
            "b_scale": 0.0,
            "b_zero_point": 0,
            "y_scale": 0.0,
            "y_zero_point": 0,
            "multiplier": 0.0,
        }
        if bundle.metadata["tails"] != expected_tails:
            raise ValueError("MatMul semantic tail metadata drifted")
        for placement in bundle.placements:
            if placement.padding_value != expected_tails[placement.port]:
                raise ValueError(f"MatMul placement {placement.port} tail drifted")
        if len(bundle.regions) != len(PORT_ORDER) * self.geometry.slice_count:
            raise ValueError("MatMul must contain one region per port and slice")

        tail_bytes = 0
        for slice_id in range(self.geometry.slice_count):
            slice_start = self.geometry.slice_base(slice_id)
            slice_end = slice_start + self.geometry.bytes_per_slice
            previous_end = slice_start
            for placement in bundle.placements:
                port = placement.port
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
                        raise ValueError(f"MatMul region {port}:{slice_id} {field} drifted")
                expected_base = slice_start + plan["offsets"][port]
                if region.base_address != expected_base or region.base_address % self.alignment:
                    raise ValueError(f"MatMul region {port}:{slice_id} base drifted")
                if region.base_address < previous_end:
                    raise ValueError("MatMul physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("MatMul physical region crosses a slice boundary")
                if (
                    region.payload_bytes != plan["raw_sizes"][port]
                    or region.size_bytes != plan["aligned_sizes"][port]
                    or len(payload) != region.size_bytes
                ):
                    raise ValueError("MatMul physical payload size drifted")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("MatMul 128-bit alignment padding is corrupted")
                if port in {"A", "B", "P", "D"}:
                    local = self._read_array(bundle, port, slice_id)
                    tail = local[~self._tail_mask(region)]
                    expected_tail = np.asarray(
                        expected_tails[port], dtype=local.dtype
                    )
                    if tail.size and not np.all(tail == expected_tail):
                        raise ValueError(f"MatMul {port} feature/sample tail is corrupted")
                    tail_bytes += int(tail.nbytes)
                previous_end = region.base_address + region.size_bytes

        recovered = {
            port: self._inverse_by_port(bundle, port) for port in PORT_ORDER
        }
        expected_multiplier = np.array(
            [
                recovered["a_scale"][0]
                * recovered["b_scale"][0]
                / recovered["y_scale"][0]
            ],
            dtype=np.float32,
        )
        if not np.array_equal(recovered["multiplier"], expected_multiplier):
            raise ValueError("MatMul multiplier is inconsistent with scalar qparams")
        return {
            "target_family": self.target_family,
            "profile_id": self.profile_id,
            "slice_count": self.geometry.slice_count,
            "port_count": len(PORT_ORDER),
            "region_count": len(bundle.regions),
            "physical_bytes": sum(len(value) for value in bundle.payloads.values()),
            "tail_bytes": tail_bytes,
            "per_slice_used_bytes": plan["per_slice_used_bytes"],
            "capacity_margin_bytes": plan["capacity_margin_bytes"],
        }


__all__ = [
    "MATMUL28_LAYOUT_IDS",
    "MatMul28PhysicalBundle",
    "QLinearMatMulPhysicalLayout",
]
