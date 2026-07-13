from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .conv16_layout import _align, _canonical
from .memory import DramGeometry, LEGACY_DRAM_GEOMETRY16
from .records import LayoutRecord


Topology = Literal["batch", "ring"]


@dataclass(frozen=True)
class MatMulRegion:
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
class MatMulPhysicalBundle:
    geometry: DramGeometry
    alignment: int
    regions: tuple[MatMulRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    metadata: dict[str, Any]

    def region(self, port: str, slice_id: int) -> MatMulRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one MatMul {port} region on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        policies = {
            "batch": "one_batch_row_per_slice",
            "replicated": "replicated_on_every_slice",
            "k_partition": "contiguous_reduction_k_partition_across_ring",
            "o_partition": "contiguous_output_owner_partition_across_ring",
        }
        records: list[LayoutRecord] = []
        for port in self.metadata["port_order"]:
            spec = self.metadata["ports"][port]
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-matmul-{self.metadata['topology']}-{port.lower()}-"
                        f"{spec['tensor_id']}"
                    ),
                    tensor_id=spec["tensor_id"],
                    transform=self.metadata["contract"],
                    contract_status=self.metadata["status"],
                    port=port,
                    logical_shape=tuple(spec["logical_shape"]),
                    logical_dtype=spec["dtype"],
                    partition={
                        "axis": spec["partition_axis"],
                        "policy": policies[spec["placement"]],
                        "slice_count": 16,
                        "k_tile": self.metadata["k_tile"],
                        "o_tile": self.metadata["o_tile"],
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "tail_value": spec["tail_value"],
                        "input_alias_requested": port == "A"
                        and self.metadata["input_alias_requested"],
                        "psum_boundary": "final_int32_accumulator_after_full_K",
                    },
                    base_addresses=tuple(
                        self.region(port, slice_id).base_address
                        for slice_id in range(16)
                    ),
                    inverse_status="validated",
                    alias_of=(
                        spec["tensor_id"]
                        if port == "A" and self.metadata["input_alias_requested"]
                        else None
                    ),
                )
            )
        return tuple(records)


class QLinearMatMul16PhysicalLayout:
    status = "candidate"

    def __init__(
        self,
        topology: Topology,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
        tile_alignment: int = 8,
    ):
        if topology not in {"batch", "ring"}:
            raise ValueError("MatMul topology must be batch or ring")
        self.topology = topology
        self.contract = f"w4_qlinearmatmul_{topology}16_candidate_v1"
        self.geometry = geometry or LEGACY_DRAM_GEOMETRY16
        if self.geometry.slice_count != 16:
            raise ValueError("MatMul candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        if tile_alignment <= 0:
            raise ValueError("tile_alignment must be positive")
        self.alignment = alignment
        self.tile_alignment = tile_alignment

    def plan(
        self,
        *,
        activation_shape: tuple[int, int],
        weight_shape: tuple[int, int],
        input_offset: int = 0,
    ) -> dict[str, Any]:
        if len(activation_shape) != 2 or len(weight_shape) != 2:
            raise ValueError("MatMul candidate requires rank-2 A and B")
        n, reduction = tuple(int(value) for value in activation_shape)
        weight_k, outputs = tuple(int(value) for value in weight_shape)
        if any(value <= 0 for value in (n, reduction, weight_k, outputs)):
            raise ValueError("MatMul dimensions must be positive")
        if reduction != weight_k:
            raise ValueError("MatMul A reduction dimension differs from B")
        if n > 16:
            raise ValueError("MatMul candidate supports batch <= 16")
        if input_offset < 0 or input_offset % self.alignment:
            raise ValueError("MatMul input_offset must be aligned")

        if self.topology == "batch":
            k_tile = _align(reduction, self.tile_alignment)
            o_tile = _align(outputs, self.tile_alignment)
            k_padded, o_padded = k_tile, o_tile
            physical_shapes = {
                "A": (k_padded,),
                "B": (k_padded, o_padded),
                "P": (o_padded,),
                "D": (o_padded,),
            }
        else:
            k_tile = math.ceil(reduction / 16)
            o_tile = math.ceil(outputs / 16)
            k_padded, o_padded = k_tile * 16, o_tile * 16
            physical_shapes = {
                "A": (n, k_tile),
                "B": (k_padded, o_tile),
                "P": (n, o_tile),
                "D": (n, o_tile),
            }
        raw_sizes = {
            "A": int(np.prod(physical_shapes["A"], dtype=np.int64)),
            "x_scale": 4,
            "x_zero_point": 1,
            "B": int(np.prod(physical_shapes["B"], dtype=np.int64)),
            "w_scale": 4,
            "w_zero_point": 1,
            "y_scale": 4,
            "y_zero_point": 1,
            "multiplier": 4,
            "P": int(np.prod(physical_shapes["P"], dtype=np.int64)) * 4,
            "D": int(np.prod(physical_shapes["D"], dtype=np.int64)),
        }
        offsets = {"A": input_offset}
        cursor = input_offset + _align(raw_sizes["A"], self.alignment)
        for port in tuple(raw_sizes)[1:]:
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(raw_sizes[port], self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("MatMul regions exceed one slice capacity")
        return {
            "activation_shape": (n, reduction),
            "weight_shape": (weight_k, outputs),
            "output_shape": (n, outputs),
            "k_tile": k_tile,
            "o_tile": o_tile,
            "k_padded": k_padded,
            "o_padded": o_padded,
            "physical_shapes": physical_shapes,
            "raw_sizes": raw_sizes,
            "offsets": offsets,
            "per_slice_used_bytes": cursor,
            "capacity_bytes": self.geometry.bytes_per_slice,
        }

    def _alias_offset(self, addresses: tuple[int, ...] | None) -> int:
        if addresses is None:
            return 0
        if len(addresses) != 16:
            raise ValueError("MatMul input_base_addresses must contain 16 addresses")
        offsets: list[int] = []
        for slice_id, address in enumerate(addresses):
            start = self.geometry.slice_base(slice_id)
            end = start + self.geometry.bytes_per_slice
            if not start <= int(address) < end:
                raise ValueError("MatMul aliased input base is outside its slice")
            offsets.append(int(address) - start)
        if len(set(offsets)) != 1:
            raise ValueError("MatMul aliased bases need one common slice offset")
        return offsets[0]

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
        x_scale: np.ndarray,
        x_zero_point: np.ndarray,
        w_scale: np.ndarray,
        w_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        accumulator: np.ndarray,
        output: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
        input_base_addresses: tuple[int, ...] | None = None,
    ) -> MatMulPhysicalBundle:
        activation, weight = np.asarray(activation), np.asarray(weight)
        accumulator, output = np.asarray(accumulator), np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 2:
            raise TypeError("MatMul activation must be rank-2 uint8")
        if weight.dtype != np.int8 or weight.ndim != 2:
            raise TypeError("MatMul weight must be rank-2 int8")
        plan = self.plan(
            activation_shape=tuple(activation.shape),
            weight_shape=tuple(weight.shape),
            input_offset=self._alias_offset(input_base_addresses),
        )
        if accumulator.dtype != np.int32 or tuple(accumulator.shape) != plan["output_shape"]:
            raise TypeError("MatMul accumulator must be int32 [N,O]")
        if output.dtype != np.uint8 or tuple(output.shape) != plan["output_shape"]:
            raise TypeError("MatMul output must be uint8 [N,O]")
        qparams = {
            "x_scale": self._scalar(x_scale, np.dtype("float32"), "x_scale"),
            "x_zero_point": self._scalar(
                x_zero_point, np.dtype("uint8"), "x_zero_point"
            ),
            "w_scale": self._scalar(w_scale, np.dtype("float32"), "w_scale"),
            "w_zero_point": self._scalar(
                w_zero_point, np.dtype("int8"), "w_zero_point"
            ),
            "y_scale": self._scalar(y_scale, np.dtype("float32"), "y_scale"),
            "y_zero_point": self._scalar(
                y_zero_point, np.dtype("uint8"), "y_zero_point"
            ),
        }
        if any(
            float(qparams[port][0]) <= 0
            for port in ("x_scale", "w_scale", "y_scale")
        ):
            raise ValueError("MatMul scales must be positive")
        multiplier = np.array(
            [
                np.float32(qparams["x_scale"][0])
                * np.float32(qparams["w_scale"][0])
                / np.float32(qparams["y_scale"][0])
            ],
            dtype=np.float32,
        )
        ids = {
            "A": "matmul_input",
            "x_scale": "matmul_x_scale",
            "x_zero_point": "matmul_x_zero_point",
            "B": "matmul_weight",
            "w_scale": "matmul_w_scale",
            "w_zero_point": "matmul_w_zero_point",
            "y_scale": "matmul_y_scale",
            "y_zero_point": "matmul_y_zero_point",
            "multiplier": "matmul_multiplier",
            "P": "matmul_accumulator",
            "D": "matmul_output",
            **(tensor_ids or {}),
        }
        if len(set(ids.values())) != len(ids):
            raise ValueError("MatMul port tensor IDs must be unique")

        n, reduction = plan["activation_shape"]
        _, outputs = plan["weight_shape"]
        k_tile, o_tile = int(plan["k_tile"]), int(plan["o_tile"])
        arrays: list[dict[str, np.ndarray]] = []
        for slice_id in range(16):
            if self.topology == "batch":
                a = np.full(
                    plan["physical_shapes"]["A"],
                    int(qparams["x_zero_point"][0]),
                    dtype=np.uint8,
                )
                p = np.zeros(plan["physical_shapes"]["P"], dtype=np.int32)
                d = np.full(
                    plan["physical_shapes"]["D"],
                    int(qparams["y_zero_point"][0]),
                    dtype=np.uint8,
                )
                if slice_id < n:
                    a[:reduction] = activation[slice_id]
                    p[:outputs] = accumulator[slice_id]
                    d[:outputs] = output[slice_id]
                b = np.full(
                    plan["physical_shapes"]["B"],
                    int(qparams["w_zero_point"][0]),
                    dtype=np.int8,
                )
                b[:reduction, :outputs] = weight
            else:
                k_start = slice_id * k_tile
                valid_k = max(0, min(k_tile, reduction - k_start))
                o_start = slice_id * o_tile
                valid_o = max(0, min(o_tile, outputs - o_start))
                a = np.full(
                    plan["physical_shapes"]["A"],
                    int(qparams["x_zero_point"][0]),
                    dtype=np.uint8,
                )
                if valid_k:
                    a[:, :valid_k] = activation[:, k_start : k_start + valid_k]
                b = np.full(
                    plan["physical_shapes"]["B"],
                    int(qparams["w_zero_point"][0]),
                    dtype=np.int8,
                )
                if valid_o:
                    b[:reduction, :valid_o] = weight[:, o_start : o_start + valid_o]
                p = np.zeros(plan["physical_shapes"]["P"], dtype=np.int32)
                d = np.full(
                    plan["physical_shapes"]["D"],
                    int(qparams["y_zero_point"][0]),
                    dtype=np.uint8,
                )
                if valid_o:
                    p[:, :valid_o] = accumulator[:, o_start : o_start + valid_o]
                    d[:, :valid_o] = output[:, o_start : o_start + valid_o]
            arrays.append(
                {
                    "A": a,
                    "B": b,
                    **qparams,
                    "multiplier": multiplier,
                    "P": p,
                    "D": d,
                }
            )

        port_order = tuple(plan["raw_sizes"].keys())
        if self.topology == "batch":
            placements = {
                "A": "batch",
                "P": "batch",
                "D": "batch",
                "B": "replicated",
            }
            axis_orders = {"A": "K_padded", "B": "KO_padded", "P": "O_padded", "D": "O_padded"}
        else:
            placements = {
                "A": "k_partition",
                "B": "o_partition",
                "P": "o_partition",
                "D": "o_partition",
            }
            axis_orders = {
                "A": "NK_local",
                "B": "K_global_paddedO_local",
                "P": "NO_local",
                "D": "NO_local",
            }
        for port in qparams | {"multiplier": multiplier}:
            placements[port] = "replicated"
            axis_orders[port] = "scalar"
        logical_shapes = {
            "A": activation.shape,
            "B": weight.shape,
            "P": accumulator.shape,
            "D": output.shape,
            **{port: (1,) for port in qparams | {"multiplier": multiplier}},
        }
        dtypes = {
            "A": "uint8",
            "B": "int8",
            "P": "int32",
            "D": "uint8",
            **{port: str(value.dtype) for port, value in qparams.items()},
            "multiplier": "float32",
        }
        tails: dict[str, Any] = {
            "A": int(qparams["x_zero_point"][0]),
            "B": int(qparams["w_zero_point"][0]),
            "P": 0,
            "D": int(qparams["y_zero_point"][0]),
            **{port: None for port in qparams | {"multiplier": multiplier}},
        }
        regions: list[MatMulRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for slice_id, per_slice in enumerate(arrays):
            for port in port_order:
                raw = _canonical(per_slice[port]).tobytes(order="C")
                size = _align(len(raw), self.alignment)
                payloads[(port, slice_id)] = raw + bytes(size - len(raw))
                placement = placements[port]
                active = (
                    True
                    if placement == "replicated"
                    else slice_id < n
                    if placement == "batch"
                    else slice_id * k_tile < reduction
                    if placement == "k_partition"
                    else slice_id * o_tile < outputs
                )
                regions.append(
                    MatMulRegion(
                        port=port,
                        tensor_id=ids[port],
                        slice_id=slice_id,
                        base_address=self.geometry.slice_base(slice_id)
                        + int(plan["offsets"][port]),
                        payload_bytes=len(raw),
                        size_bytes=size,
                        physical_shape=tuple(per_slice[port].shape),
                        placement=placement,
                        active=active,
                    )
                )
        partition_axes = {"A": 0 if self.topology == "batch" else 1, "B": None if self.topology == "batch" else 1, "P": 0 if self.topology == "batch" else 1, "D": 0 if self.topology == "batch" else 1}
        ports = {
            port: {
                "tensor_id": ids[port],
                "logical_shape": tuple(logical_shapes[port]),
                "dtype": dtypes[port],
                "placement": placements[port],
                "partition_axis": partition_axes.get(port),
                "physical_axis_order": axis_orders[port],
                "tail_value": tails[port],
            }
            for port in port_order
        }
        bundle = MatMulPhysicalBundle(
            geometry=self.geometry,
            alignment=self.alignment,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                "contract": self.contract,
                "status": self.status,
                "topology": self.topology,
                "slice_topology": (
                    "batch_parallel_one_row_per_slice"
                    if self.topology == "batch"
                    else "ring_K_activation_O_output_partition"
                ),
                "ring_steps": 1 if self.topology == "batch" else 16,
                "neighbor_transfer_count": 0 if self.topology == "batch" else 15,
                "ring_order_formula": (
                    None if self.topology == "batch" else "(o_owner_slice + step) % 16"
                ),
                "port_order": port_order,
                "ports": ports,
                "tails": tails,
                "input_alias_requested": input_base_addresses is not None,
                "input_transition": (
                    "batch_quantize_D_zero_copy_candidate"
                    if self.topology == "batch"
                    else "batch_quantize_D_to_ring_K_partition_explicit_relayout"
                ),
                "multiplier": float(multiplier[0]),
                **plan,
            },
        )
        self.validate(bundle)
        return bundle

    def _read(self, bundle: MatMulPhysicalBundle, port: str, slice_id: int) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes],
            dtype=np.dtype(bundle.metadata["ports"][port]["dtype"]),
        ).reshape(region.physical_shape)

    def inverse_port(self, bundle: MatMulPhysicalBundle, port: str) -> np.ndarray:
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if spec["placement"] == "replicated":
            arrays = [self._read(bundle, port, slice_id) for slice_id in range(16)]
            if any(not np.array_equal(arrays[0], item) for item in arrays[1:]):
                raise ValueError(f"replicated MatMul port {port} differs")
            if port == "B":
                return arrays[0][: shape[0], : shape[1]].copy()
            return arrays[0].reshape(shape).copy()
        n, reduction = bundle.metadata["activation_shape"]
        _, outputs = bundle.metadata["weight_shape"]
        k_tile, o_tile = int(bundle.metadata["k_tile"]), int(bundle.metadata["o_tile"])
        logical = np.empty(shape, dtype=np.dtype(spec["dtype"]))
        if self.topology == "batch":
            for slice_id in range(n):
                logical[slice_id] = self._read(bundle, port, slice_id)[: shape[1]]
        elif port == "A":
            for slice_id in range(16):
                start = slice_id * k_tile
                valid = max(0, min(k_tile, reduction - start))
                if valid:
                    logical[:, start : start + valid] = self._read(
                        bundle, port, slice_id
                    )[:, :valid]
        elif port == "B":
            for slice_id in range(16):
                start = slice_id * o_tile
                valid = max(0, min(o_tile, outputs - start))
                if valid:
                    logical[:, start : start + valid] = self._read(
                        bundle, port, slice_id
                    )[:reduction, :valid]
        else:
            for slice_id in range(16):
                start = slice_id * o_tile
                valid = max(0, min(o_tile, outputs - start))
                if valid:
                    logical[:, start : start + valid] = self._read(
                        bundle, port, slice_id
                    )[:, :valid]
        return logical

    def inverse(self, bundle: MatMulPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(bundle, port)
            for port in bundle.metadata["port_order"]
        }

    def explain_coordinate(
        self, bundle: MatMulPhysicalBundle, tensor_id: str, coordinate: tuple[int, ...]
    ) -> dict[str, Any]:
        ports = [
            port
            for port in bundle.metadata["port_order"]
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(ports) != 1:
            raise KeyError(f"expected one MatMul port for {tensor_id}")
        port = ports[0]
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if len(coordinate) != len(shape) or any(
            index < 0 or index >= dimension
            for index, dimension in zip(coordinate, shape, strict=True)
        ):
            raise IndexError("MatMul coordinate is out of range")
        k_tile, o_tile = int(bundle.metadata["k_tile"]), int(bundle.metadata["o_tile"])
        if spec["placement"] == "replicated":
            slice_ids = tuple(range(16))
            physical_coordinate = coordinate
        elif self.topology == "batch":
            slice_ids = (coordinate[0],)
            physical_coordinate = (coordinate[1],)
        elif port == "A":
            slice_ids = (coordinate[1] // k_tile,)
            physical_coordinate = (coordinate[0], coordinate[1] % k_tile)
        elif port == "B":
            slice_ids = (coordinate[1] // o_tile,)
            physical_coordinate = (coordinate[0], coordinate[1] % o_tile)
        else:
            slice_ids = (coordinate[1] // o_tile,)
            physical_coordinate = (coordinate[0], coordinate[1] % o_tile)
        region = bundle.region(port, slice_ids[0])
        index = int(np.ravel_multi_index(physical_coordinate, region.physical_shape))
        itemsize = np.dtype(spec["dtype"]).itemsize
        addresses: list[int] = []
        for slice_id in slice_ids:
            base = bundle.region(port, slice_id).base_address + index * itemsize
            addresses.extend(base + byte for byte in range(itemsize))
        return {
            "tensor_id": tensor_id,
            "port": port,
            "logical_coordinate": coordinate,
            "physical_coordinate": physical_coordinate,
            "slice_ids": slice_ids,
            "addresses": tuple(addresses),
        }

    def explain_ring_step(
        self, bundle: MatMulPhysicalBundle, *, output_feature: int, step: int
    ) -> dict[str, Any]:
        if self.topology != "ring":
            raise ValueError("MatMul ring steps exist only in the ring profile")
        reduction = int(bundle.metadata["activation_shape"][1])
        outputs = int(bundle.metadata["weight_shape"][1])
        if not 0 <= output_feature < outputs or not 0 <= step < 16:
            raise IndexError("MatMul ring coordinate is out of range")
        owner = output_feature // int(bundle.metadata["o_tile"])
        input_slice = (owner + step) % 16
        start = input_slice * int(bundle.metadata["k_tile"])
        end = min(reduction, start + int(bundle.metadata["k_tile"]))
        return {
            "output_feature": output_feature,
            "output_owner_slice": owner,
            "ring_step": step,
            "input_slice": input_slice,
            "reduction_range": (min(reduction, start), end),
            "has_data": start < reduction,
            "last": step == 15,
        }

    def prove_batch_quantize_input_alias(
        self, producer_bundle, matmul_bundle: MatMulPhysicalBundle
    ) -> dict[str, Any]:
        if self.topology != "batch":
            raise ValueError("ring MatMul requires explicit batch-to-K relayout")
        if producer_bundle.contract != "w4_batch_slice_candidate_v1":
            raise ValueError("MatMul input producer is not the W4 batch-slice contract")
        producer_specs = [
            placement for placement in producer_bundle.placements if placement.port == "D"
        ]
        if len(producer_specs) != 1:
            raise ValueError("Quantize producer does not contain exactly one D port")
        producer_spec = producer_specs[0]
        consumer_spec = matmul_bundle.metadata["ports"]["A"]
        if tuple(producer_spec.logical_shape) != tuple(consumer_spec["logical_shape"]):
            raise ValueError("Quantize D logical shape differs from MatMul A")
        tensor_id = consumer_spec["tensor_id"]
        if producer_bundle.region("D", 0).tensor_id != tensor_id:
            raise ValueError("Quantize D and MatMul A tensor IDs differ")
        for slice_id in range(16):
            producer = producer_bundle.region("D", slice_id)
            consumer = matmul_bundle.region("A", slice_id)
            if producer.base_address != consumer.base_address:
                raise ValueError("Quantize D and MatMul A base addresses differ")
            if producer.payload_bytes != consumer.payload_bytes:
                raise ValueError("Quantize D and MatMul A payload sizes differ")
            if producer_bundle.read("D", slice_id) != matmul_bundle.read("A", slice_id):
                raise ValueError("Quantize D and MatMul A physical bytes differ")
        return {
            "compatible": True,
            "exact_alias": True,
            "producer_contract": producer_bundle.contract,
            "consumer_contract": self.contract,
            "shared_tensor_id": tensor_id,
            "slice_count": 16,
            "all_physical_bytes_equal": True,
        }

    def validate(self, bundle: MatMulPhysicalBundle) -> dict[str, int]:
        if bundle.metadata["contract"] != self.contract or bundle.metadata["status"] != self.status:
            raise ValueError("MatMul bundle contract mismatch")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("MatMul bundle geometry/alignment mismatch")
        ports = tuple(bundle.metadata["port_order"])
        if len(bundle.regions) != len(ports) * 16:
            raise ValueError("MatMul region count mismatch")
        n, reduction = bundle.metadata["activation_shape"]
        _, outputs = bundle.metadata["weight_shape"]
        k_tile, o_tile = int(bundle.metadata["k_tile"]), int(bundle.metadata["o_tile"])
        for slice_id in range(16):
            slice_start = bundle.geometry.slice_base(slice_id)
            slice_end = slice_start + bundle.geometry.bytes_per_slice
            ranges = []
            for port in ports:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError("MatMul region is not aligned")
                if not (slice_start <= region.base_address and region.base_address + region.size_bytes <= slice_end):
                    raise ValueError("MatMul region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("MatMul payload length differs from region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("MatMul alignment padding is corrupted")
                ranges.append((region.base_address, region.base_address + region.size_bytes))
                expected_active = (
                    True
                    if region.placement == "replicated"
                    else slice_id < n
                    if region.placement == "batch"
                    else slice_id * k_tile < reduction
                    if region.placement == "k_partition"
                    else slice_id * o_tile < outputs
                )
                if region.active != expected_active:
                    raise ValueError("MatMul activity mask is inconsistent")
            ranges.sort()
            if any(ranges[index][1] > ranges[index + 1][0] for index in range(len(ranges) - 1)):
                raise ValueError("MatMul regions overlap")

            a, b = self._read(bundle, "A", slice_id), self._read(bundle, "B", slice_id)
            p, d = self._read(bundle, "P", slice_id), self._read(bundle, "D", slice_id)
            if self.topology == "batch":
                if slice_id >= n:
                    if np.any(a != bundle.metadata["tails"]["A"]):
                        raise ValueError("MatMul inactive A slice is corrupted")
                    if np.any(p != 0) or np.any(d != bundle.metadata["tails"]["D"]):
                        raise ValueError("MatMul inactive P/D slice is corrupted")
                if reduction < bundle.metadata["k_padded"] and np.any(a[reduction:] != bundle.metadata["tails"]["A"]):
                    raise ValueError("MatMul A K tail is corrupted")
                if outputs < bundle.metadata["o_padded"]:
                    if np.any(b[:, outputs:] != bundle.metadata["tails"]["B"]):
                        raise ValueError("MatMul B O tail is corrupted")
                    if np.any(p[outputs:] != 0) or np.any(d[outputs:] != bundle.metadata["tails"]["D"]):
                        raise ValueError("MatMul P/D O tail is corrupted")
                if reduction < bundle.metadata["k_padded"] and np.any(b[reduction:, :] != bundle.metadata["tails"]["B"]):
                    raise ValueError("MatMul B K tail is corrupted")
            else:
                valid_k = max(0, min(k_tile, reduction - slice_id * k_tile))
                valid_o = max(0, min(o_tile, outputs - slice_id * o_tile))
                if valid_k < k_tile and np.any(a[:, valid_k:] != bundle.metadata["tails"]["A"]):
                    raise ValueError("MatMul A K tail is corrupted")
                if reduction < bundle.metadata["k_padded"] and np.any(b[reduction:, :] != bundle.metadata["tails"]["B"]):
                    raise ValueError("MatMul B K tail is corrupted")
                if valid_o < o_tile:
                    if np.any(b[:, valid_o:] != bundle.metadata["tails"]["B"]):
                        raise ValueError("MatMul B O tail is corrupted")
                    if np.any(p[:, valid_o:] != 0) or np.any(d[:, valid_o:] != bundle.metadata["tails"]["D"]):
                        raise ValueError("MatMul P/D O tail is corrupted")
        for port in ports:
            self.inverse_port(bundle, port)
        expected_multiplier = np.float32(
            self.inverse_port(bundle, "x_scale")[0]
            * self.inverse_port(bundle, "w_scale")[0]
            / self.inverse_port(bundle, "y_scale")[0]
        )
        if self.inverse_port(bundle, "multiplier")[0] != expected_multiplier:
            raise ValueError("MatMul multiplier is inconsistent")
        return {
            "slice_count": 16,
            "port_count": len(ports),
            "region_count": len(bundle.regions),
            "ring_steps": bundle.metadata["ring_steps"],
            "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        }


class QLinearMatMulBatch16PhysicalLayout(QLinearMatMul16PhysicalLayout):
    def __init__(self, geometry: DramGeometry | None = None, *, alignment: int = 16):
        super().__init__("batch", geometry, alignment=alignment, tile_alignment=8)


class QLinearMatMulRing16PhysicalLayout(QLinearMatMul16PhysicalLayout):
    def __init__(self, geometry: DramGeometry | None = None, *, alignment: int = 16):
        super().__init__("ring", geometry, alignment=alignment, tile_alignment=1)
