from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .conv16_layout import _align, _canonical
from .memory import DramGeometry
from .records import LayoutRecord


Topology = Literal["batch", "channel"]


@dataclass(frozen=True)
class AddRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    physical_shape: tuple[int, ...]
    placement: str
    active: bool


@dataclass(frozen=True)
class AddPhysicalBundle:
    geometry: DramGeometry
    alignment: int
    regions: tuple[AddRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    metadata: dict[str, Any]

    def region(self, port: str, slice_id: int) -> AddRegion:
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
        for port in self.metadata["port_order"]:
            spec = self.metadata["ports"][port]
            policy = {
                "batch": "one_batch_item_per_slice",
                "channel": "contiguous_feature_partition_across_slices",
                "replicated": "replicated_on_every_slice",
            }[spec["placement"]]
            records.append(
                LayoutRecord(
                    layout_id=f"layout-add-{self.metadata['topology']}-{port.lower()}-{spec['tensor_id']}",
                    tensor_id=spec["tensor_id"],
                    transform=self.metadata["contract"],
                    contract_status=self.metadata["status"],
                    port=port,
                    logical_shape=tuple(spec["logical_shape"]),
                    logical_dtype=spec["dtype"],
                    partition={
                        "axis": spec["partition_axis"],
                        "policy": policy,
                        "slice_count": 16,
                        "feature_tile": self.metadata["feature_tile"],
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "tail_value": spec["tail_value"],
                        "broadcast_mode": self.metadata["broadcast_mode"],
                        "input_alias_requested": port
                        in self.metadata["input_alias_ports"],
                    },
                    base_addresses=tuple(
                        self.region(port, slice_id).base_address for slice_id in range(16)
                    ),
                    inverse_status="validated",
                    alias_of=(
                        spec["tensor_id"]
                        if port in self.metadata["input_alias_ports"]
                        else None
                    ),
                )
            )
        return tuple(records)


class QLinearAdd16PhysicalLayout:
    status = "candidate"

    def __init__(
        self,
        topology: Topology,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
        feature_alignment: int = 8,
    ):
        if topology not in {"batch", "channel"}:
            raise ValueError("Add topology must be batch or channel")
        self.topology = topology
        self.contract = f"w4_qlinearadd_{topology}16_candidate_v1"
        self.geometry = geometry or DramGeometry()
        if self.geometry.slice_count != 16:
            raise ValueError("Add candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        if feature_alignment <= 0:
            raise ValueError("feature_alignment must be positive")
        self.alignment = alignment
        self.feature_alignment = feature_alignment

    @staticmethod
    def _mode(a_shape: tuple[int, ...], b_shape: tuple[int, ...]) -> str:
        if a_shape == b_shape and len(a_shape) in {2, 4}:
            return "same_shape"
        if len(a_shape) == 2 and len(b_shape) == 1 and a_shape[-1] == b_shape[0]:
            return "dense_vector_broadcast"
        raise ValueError("formal Add supports equal rank-2/rank-4 inputs or [N,F]+[F]")

    @staticmethod
    def _physical_shape(shape: tuple[int, ...], feature_tile: int, topology: str):
        if len(shape) == 4:
            n, _, height, width = shape
            return (
                (height, width, feature_tile)
                if topology == "batch"
                else (n, height, width, feature_tile)
            )
        n, _ = shape
        return (feature_tile,) if topology == "batch" else (n, feature_tile)

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
        if a_shape[0] > 16:
            raise ValueError("Add candidate supports batch <= 16")
        mode = self._mode(a_shape, b_shape)
        d_shape = a_shape
        features = a_shape[1]
        if self.topology == "batch":
            feature_tile = _align(features, self.feature_alignment)
        else:
            feature_tile = math.ceil(features / 16)
        shapes = {
            "A": self._physical_shape(a_shape, feature_tile, self.topology),
            "D": self._physical_shape(d_shape, feature_tile, self.topology),
        }
        if mode == "same_shape":
            shapes["B"] = self._physical_shape(b_shape, feature_tile, self.topology)
            b_placement = self.topology
        elif self.topology == "batch":
            shapes["B"] = (feature_tile,)
            b_placement = "replicated"
        else:
            shapes["B"] = (feature_tile,)
            b_placement = "channel"
        raw_sizes = {
            "A": int(np.prod(shapes["A"], dtype=np.int64)),
            "B": int(np.prod(shapes["B"], dtype=np.int64)),
            "a_scale": 4,
            "a_zero_point": 1,
            "b_scale": 4,
            "b_zero_point": 1,
            "y_scale": 4,
            "y_zero_point": 1,
            "D": int(np.prod(shapes["D"], dtype=np.int64)),
        }
        offsets = dict(input_offsets or {})
        if any(name not in {"A", "B"} for name in offsets):
            raise ValueError("Add input_offsets only accepts A/B")
        cursor = 0
        for port in ("A", "B"):
            if port in offsets:
                if offsets[port] < 0 or offsets[port] % self.alignment:
                    raise ValueError("Add aliased input offset must be aligned")
            else:
                offsets[port] = _align(cursor, self.alignment)
            cursor = max(cursor, offsets[port] + _align(raw_sizes[port], self.alignment))
        a_range = (offsets["A"], offsets["A"] + _align(raw_sizes["A"], self.alignment))
        b_range = (offsets["B"], offsets["B"] + _align(raw_sizes["B"], self.alignment))
        if max(a_range[0], b_range[0]) < min(a_range[1], b_range[1]):
            raise ValueError("Add A/B physical regions overlap")
        for port in ("a_scale", "a_zero_point", "b_scale", "b_zero_point", "y_scale", "y_zero_point", "D"):
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(raw_sizes[port], self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("Add regions exceed one slice capacity")
        return {
            "a_shape": a_shape,
            "b_shape": b_shape,
            "d_shape": d_shape,
            "broadcast_mode": mode,
            "features": features,
            "feature_tile": feature_tile,
            "physical_shapes": shapes,
            "b_placement": b_placement,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
        }

    def _base_offsets(self, addresses: dict[str, tuple[int, ...]] | None):
        if addresses is None:
            return None
        if any(port not in {"A", "B"} for port in addresses):
            raise ValueError("Add aliased input bases only accept A/B")
        result: dict[str, int] = {}
        for port, values in addresses.items():
            if len(values) != 16:
                raise ValueError("Add aliased input bases must contain 16 addresses")
            offsets: list[int] = []
            for slice_id, address in enumerate(values):
                start = self.geometry.slice_base(slice_id)
                end = start + self.geometry.bytes_per_slice
                if not start <= int(address) < end:
                    raise ValueError("Add aliased input base is outside its slice")
                offsets.append(int(address) - start)
            if len(set(offsets)) != 1:
                raise ValueError("Add aliased bases need one common slice offset")
            result[port] = offsets[0]
        return result

    @staticmethod
    def _scalar(value: np.ndarray, dtype: np.dtype, name: str) -> np.ndarray:
        array = np.asarray(value)
        if array.dtype != dtype or array.size != 1:
            raise TypeError(f"{name} must be scalar {dtype}")
        return _canonical(array.reshape(1))

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
        input_tail_values: dict[str, int] | None = None,
        input_base_addresses: dict[str, tuple[int, ...]] | None = None,
    ) -> AddPhysicalBundle:
        a, b, output = np.asarray(a), np.asarray(b), np.asarray(output)
        if any(array.dtype != np.uint8 for array in (a, b, output)):
            raise TypeError("QLinearAdd A/B/D must be uint8")
        offsets = self._base_offsets(input_base_addresses)
        plan = self.plan(a_shape=a.shape, b_shape=b.shape, input_offsets=offsets)
        if tuple(output.shape) != plan["d_shape"]:
            raise TypeError("QLinearAdd output shape differs from broadcast result")
        qparams = {
            "a_scale": self._scalar(a_scale, np.dtype("float32"), "a_scale"),
            "a_zero_point": self._scalar(a_zero_point, np.dtype("uint8"), "a_zero_point"),
            "b_scale": self._scalar(b_scale, np.dtype("float32"), "b_scale"),
            "b_zero_point": self._scalar(b_zero_point, np.dtype("uint8"), "b_zero_point"),
            "y_scale": self._scalar(y_scale, np.dtype("float32"), "y_scale"),
            "y_zero_point": self._scalar(y_zero_point, np.dtype("uint8"), "y_zero_point"),
        }
        if any(float(qparams[name][0]) <= 0 for name in ("a_scale", "b_scale", "y_scale")):
            raise ValueError("QLinearAdd scales must be positive")
        tails = {
            "A": int(qparams["a_zero_point"][0]),
            "B": int(qparams["b_zero_point"][0]),
            "D": int(qparams["y_zero_point"][0]),
        }
        if any(port not in {"A", "B"} for port in (input_tail_values or {})):
            raise ValueError("Add input_tail_values only accepts A/B")
        tails.update(input_tail_values or {})
        if any(not 0 <= int(value) <= 255 for value in tails.values()):
            raise ValueError("Add tail values must fit uint8")
        ids = {
            "A": "add_input_a",
            "B": "add_input_b",
            "a_scale": "add_a_scale",
            "a_zero_point": "add_a_zero_point",
            "b_scale": "add_b_scale",
            "b_zero_point": "add_b_zero_point",
            "y_scale": "add_y_scale",
            "y_zero_point": "add_y_zero_point",
            "D": "add_output",
            **(tensor_ids or {}),
        }
        if len(set(ids.values())) != len(ids):
            raise ValueError("Add port tensor IDs must be unique")
        n, features = plan["a_shape"][:2]
        feature_tile = int(plan["feature_tile"])
        per_slice: list[dict[str, np.ndarray]] = []
        for slice_id in range(16):
            data: dict[str, np.ndarray] = {}
            for port, logical in (("A", a), ("D", output)):
                if self.topology == "batch":
                    physical = np.full(plan["physical_shapes"][port], tails[port], np.uint8)
                    if slice_id < n:
                        if logical.ndim == 4:
                            physical[..., :features] = np.transpose(logical[slice_id], (1, 2, 0))
                        else:
                            physical[:features] = logical[slice_id]
                else:
                    start = slice_id * feature_tile
                    valid = max(0, min(feature_tile, features - start))
                    physical = np.full(plan["physical_shapes"][port], tails[port], np.uint8)
                    if valid:
                        if logical.ndim == 4:
                            physical[..., :valid] = np.transpose(
                                logical[:, start : start + valid], (0, 2, 3, 1)
                            )
                        else:
                            physical[..., :valid] = logical[:, start : start + valid]
                data[port] = physical
            if plan["broadcast_mode"] == "same_shape":
                logical = b
                if self.topology == "batch":
                    physical = np.full(plan["physical_shapes"]["B"], tails["B"], np.uint8)
                    if slice_id < n:
                        if b.ndim == 4:
                            physical[..., :features] = np.transpose(b[slice_id], (1, 2, 0))
                        else:
                            physical[:features] = b[slice_id]
                else:
                    start = slice_id * feature_tile
                    valid = max(0, min(feature_tile, features - start))
                    physical = np.full(plan["physical_shapes"]["B"], tails["B"], np.uint8)
                    if valid:
                        if b.ndim == 4:
                            physical[..., :valid] = np.transpose(
                                b[:, start : start + valid], (0, 2, 3, 1)
                            )
                        else:
                            physical[..., :valid] = b[:, start : start + valid]
                data["B"] = physical
            elif self.topology == "batch":
                physical = np.full((feature_tile,), tails["B"], np.uint8)
                physical[:features] = b
                data["B"] = physical
            else:
                start = slice_id * feature_tile
                valid = max(0, min(feature_tile, features - start))
                physical = np.full((feature_tile,), tails["B"], np.uint8)
                if valid:
                    physical[:valid] = b[start : start + valid]
                data["B"] = physical
            data.update(qparams)
            per_slice.append(data)
        port_order = tuple(plan["raw_sizes"].keys())
        placements = {
            "A": self.topology,
            "D": self.topology,
            "B": plan["b_placement"],
            **{name: "replicated" for name in qparams},
        }
        logical_shapes = {
            "A": a.shape,
            "B": b.shape,
            "D": output.shape,
            **{name: (1,) for name in qparams},
        }
        dtypes = {
            "A": "uint8",
            "B": "uint8",
            "D": "uint8",
            **{name: str(value.dtype) for name, value in qparams.items()},
        }
        regions: list[AddRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for slice_id, data in enumerate(per_slice):
            for port in port_order:
                raw = _canonical(data[port]).tobytes(order="C")
                size = _align(len(raw), self.alignment)
                payloads[(port, slice_id)] = raw + bytes(size-len(raw))
                placement = placements[port]
                active = True if placement == "replicated" else (slice_id < n if placement == "batch" else slice_id*feature_tile < features)
                regions.append(
                    AddRegion(
                        port,
                        ids[port],
                        slice_id,
                        self.geometry.slice_base(slice_id) + plan["offsets"][port],
                        len(raw),
                        size,
                        tuple(data[port].shape),
                        placement,
                        active,
                    )
                )

        def axis_order(port: str) -> str:
            if port in qparams:
                return "scalar"
            if port == "B" and plan["broadcast_mode"] != "same_shape":
                return "F_padded" if self.topology == "batch" else "F_local"
            if a.ndim == 4:
                return "HWC_padded" if self.topology == "batch" else "NHWC_local"
            return "F_padded" if self.topology == "batch" else "NF_local"

        ports = {
            port: {
                "tensor_id": ids[port],
                "logical_shape": tuple(logical_shapes[port]),
                "dtype": dtypes[port],
                "placement": placements[port],
                "partition_axis": (
                    0
                    if placements[port] == "batch"
                    else 1
                    if placements[port] == "channel"
                    else None
                ),
                "physical_axis_order": axis_order(port),
                "tail_value": tails.get(port),
            }
            for port in port_order
        }
        bundle = AddPhysicalBundle(
            self.geometry,
            self.alignment,
            tuple(regions),
            payloads,
            {
                "contract": self.contract,
                "status": self.status,
                "topology": self.topology,
                "port_order": port_order,
                "tails": tails,
                "input_alias_requested": input_base_addresses is not None,
                "input_alias_ports": tuple((input_base_addresses or {}).keys()),
                "ports": ports,
                **plan,
            },
        )
        self.validate(bundle)
        return bundle

    def _read(self, bundle: AddPhysicalBundle, port: str, slice_id: int) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(bundle.read(port, slice_id)[:region.payload_bytes], dtype=np.dtype(bundle.metadata["ports"][port]["dtype"])).reshape(region.physical_shape)

    def inverse_port(self, bundle: AddPhysicalBundle, port: str) -> np.ndarray:
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if spec["placement"] == "replicated":
            arrays = [self._read(bundle, port, slice_id) for slice_id in range(16)]
            if any(not np.array_equal(arrays[0], item) for item in arrays[1:]):
                raise ValueError(f"replicated Add port {port} differs")
            if (
                port == "B"
                and bundle.metadata["broadcast_mode"] == "dense_vector_broadcast"
            ):
                return arrays[0][: shape[0]].copy()
            return arrays[0].reshape(shape).copy()
        n, features = bundle.metadata["a_shape"][:2]
        tile = int(bundle.metadata["feature_tile"])
        if port == "B" and bundle.metadata["broadcast_mode"] == "dense_vector_broadcast":
            logical = np.empty(features, np.uint8)
            for slice_id in range(16):
                start = slice_id * tile
                valid = max(0, min(tile, features - start))
                if valid:
                    logical[start : start + valid] = self._read(
                        bundle, port, slice_id
                    )[:valid]
            return logical
        logical = np.empty(shape, np.uint8)
        if self.topology == "batch":
            for slice_id in range(n):
                physical = self._read(bundle, port, slice_id)
                logical[slice_id] = (
                    np.transpose(physical[..., :features], (2, 0, 1))
                    if len(shape) == 4
                    else physical[:features]
                )
        else:
            for slice_id in range(16):
                start = slice_id * tile
                valid = max(0, min(tile, features - start))
                if valid:
                    physical = self._read(bundle, port, slice_id)
                    logical[:, start : start + valid] = (
                        np.transpose(physical[..., :valid], (0, 3, 1, 2))
                        if len(shape) == 4
                        else physical[..., :valid]
                    )
        return logical

    def inverse(self, bundle: AddPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(
                bundle, port
            )
            for port in bundle.metadata["port_order"]
        }

    def explain_coordinate(self,bundle:AddPhysicalBundle,tensor_id:str,coordinate:tuple[int,...])->dict[str,Any]:
        ports = [
            port
            for port in bundle.metadata["port_order"]
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(ports) != 1:
            raise KeyError(f"expected one Add port for {tensor_id}")
        port = ports[0]
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if len(coordinate) != len(shape) or any(
            index < 0 or index >= dimension
            for index, dimension in zip(coordinate, shape, strict=True)
        ):
            raise IndexError("Add coordinate out of range")
        tile = int(bundle.metadata["feature_tile"])
        if spec["placement"] == "replicated":
            slices = tuple(range(16))
            physical_coordinate = coordinate
        elif port == "B" and bundle.metadata["broadcast_mode"] == "dense_vector_broadcast":
            slices = (coordinate[0] // tile,)
            physical_coordinate = (coordinate[0] % tile,)
        elif self.topology == "batch":
            slices = (coordinate[0],)
            physical_coordinate = (
                (coordinate[2], coordinate[3], coordinate[1])
                if len(shape) == 4
                else (coordinate[1],)
            )
        else:
            slices = (coordinate[1] // tile,)
            physical_coordinate = (
                (coordinate[0], coordinate[2], coordinate[3], coordinate[1] % tile)
                if len(shape) == 4
                else (coordinate[0], coordinate[1] % tile)
            )
        region = bundle.region(port, slices[0])
        index = int(np.ravel_multi_index(physical_coordinate, region.physical_shape))
        itemsize = np.dtype(spec["dtype"]).itemsize
        addresses = []
        for slice_id in slices:
            base = bundle.region(port, slice_id).base_address + index * itemsize
            addresses.extend(base + byte for byte in range(itemsize))
        return {
            "port": port,
            "logical_coordinate": coordinate,
            "physical_coordinate": physical_coordinate,
            "slice_ids": slices,
            "addresses": tuple(addresses),
        }

    def validate(self, bundle: AddPhysicalBundle) -> dict[str, int]:
        if (
            bundle.metadata["contract"] != self.contract
            or bundle.metadata["status"] != self.status
        ):
            raise ValueError("Add bundle contract does not match this layout")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("Add bundle geometry/alignment mismatch")
        ports = tuple(bundle.metadata["port_order"])
        if len(bundle.regions) != len(ports) * 16:
            raise ValueError("Add region count mismatch")
        n, features = bundle.metadata["a_shape"][:2]
        tile = int(bundle.metadata["feature_tile"])
        for slice_id in range(16):
            ranges = []
            slice_start = bundle.geometry.slice_base(slice_id)
            slice_end = slice_start + bundle.geometry.bytes_per_slice
            for port in ports:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError("Add region is not aligned")
                if not (
                    slice_start <= region.base_address
                    and region.base_address + region.size_bytes <= slice_end
                ):
                    raise ValueError("Add region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("Add payload length differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("Add alignment padding is corrupted")
                ranges.append(
                    (region.base_address, region.base_address + region.size_bytes, port)
                )
            ranges.sort()
            if any(
                ranges[index][1] > ranges[index + 1][0]
                for index in range(len(ranges) - 1)
            ):
                raise ValueError("Add regions overlap")

            for port in ports:
                region = bundle.region(port, slice_id)
                placement = bundle.metadata["ports"][port]["placement"]
                expected_active = (
                    True
                    if placement == "replicated"
                    else slice_id < n
                    if placement == "batch"
                    else slice_id * tile < features
                )
                if region.active != expected_active:
                    raise ValueError("Add activity mask is inconsistent")

            for port in ("A", "B", "D"):
                spec = bundle.metadata["ports"][port]
                placement = spec["placement"]
                tail = int(spec["tail_value"])
                array = self._read(bundle, port, slice_id)
                if placement == "batch":
                    if slice_id >= n and np.any(array != tail):
                        raise ValueError(f"Add inactive {port} slice is corrupted")
                    if features < tile and np.any(array[..., features:] != tail):
                        raise ValueError(f"Add {port} feature tail is corrupted")
                elif placement == "channel":
                    valid = max(0, min(tile, features - slice_id * tile))
                    if valid < tile and np.any(array[..., valid:] != tail):
                        raise ValueError(f"Add {port} feature tail is corrupted")
                elif port == "B" and features < tile:
                    if np.any(array[features:] != tail):
                        raise ValueError("Add B broadcast tail is corrupted")

        for port in ports:
            self.inverse_port(bundle, port)
        return {
            "slice_count": 16,
            "port_count": len(ports),
            "region_count": len(bundle.regions),
            "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        }

    def prove_input_compatibility(
        self,
        producer_bundle,
        add_bundle: AddPhysicalBundle,
        port: Literal["A", "B"],
        *,
        require_same_base: bool = False,
    ) -> dict[str, Any]:
        """Prove a producer D and one Add input have the same physical layout.

        Layout compatibility is independent from W7 allocation.  If the layouts and
        bytes match but the bases differ, the result explicitly requests a memory-plan
        rebase instead of claiming a zero-copy alias.
        """
        if port not in {"A", "B"}:
            raise ValueError("Add producer compatibility only accepts A/B")
        producer_contract = producer_bundle.metadata["contract"]
        expected_contracts = {
            "batch": {
                "w4_conv_batch16_candidate_v1",
                "w4_maxpool_batch16_candidate_v1",
                "w4_qlinearadd_batch16_candidate_v1",
            },
            "channel": {
                "w4_conv_ring16_candidate_v1",
                "w4_maxpool_channel16_candidate_v1",
                "w4_qlinearadd_channel16_candidate_v1",
            },
        }[self.topology]
        if producer_contract not in expected_contracts:
            raise ValueError("producer topology does not match Add topology")
        producer_spec = producer_bundle.metadata["ports"]["D"]
        consumer_spec = add_bundle.metadata["ports"][port]
        if tuple(producer_spec["logical_shape"]) != tuple(
            consumer_spec["logical_shape"]
        ):
            raise ValueError("producer D logical shape differs from Add input")
        if producer_spec.get("logical_dtype", producer_spec.get("dtype")) != consumer_spec[
            "dtype"
        ]:
            raise ValueError("producer D dtype differs from Add input")
        shared_tensor_id = consumer_spec["tensor_id"]
        if producer_bundle.region("D", 0).tensor_id != shared_tensor_id:
            raise ValueError("producer D and Add input tensor IDs differ")

        same_bases = True
        for slice_id in range(16):
            producer = producer_bundle.region("D", slice_id)
            consumer = add_bundle.region(port, slice_id)
            if producer.payload_bytes != consumer.payload_bytes:
                raise ValueError("producer D and Add input payload sizes differ")
            if tuple(producer.physical_shape) != tuple(consumer.physical_shape):
                raise ValueError("producer D and Add input physical shapes differ")
            if producer_bundle.read("D", slice_id) != add_bundle.read(port, slice_id):
                raise ValueError("producer D and Add input physical bytes differ")
            same_bases &= producer.base_address == consumer.base_address
        if require_same_base and not same_bases:
            raise ValueError("producer D and Add input base addresses differ")
        return {
            "compatible": True,
            "producer_contract": producer_contract,
            "consumer_contract": self.contract,
            "port": port,
            "slice_count": 16,
            "shared_tensor_id": shared_tensor_id,
            "all_physical_bytes_equal": True,
            "all_base_addresses_equal": same_bases,
            "exact_alias": same_bases,
            "memory_plan_rebase_required": not same_bases,
        }


class QLinearAddBatch16PhysicalLayout(QLinearAdd16PhysicalLayout):
    def __init__(
        self, geometry: DramGeometry | None = None, *, alignment: int = 16
    ):
        super().__init__("batch", geometry, alignment=alignment)


class QLinearAddChannel16PhysicalLayout(QLinearAdd16PhysicalLayout):
    def __init__(
        self, geometry: DramGeometry | None = None, *, alignment: int = 16
    ):
        super().__init__("channel", geometry, alignment=alignment)
