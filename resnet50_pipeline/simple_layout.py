from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .memory import DramGeometry
from .records import LayoutRecord


Placement = Literal["batch", "replicated"]


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _little_endian(array: np.ndarray) -> np.ndarray:
    dtype = array.dtype.newbyteorder("<")
    return np.ascontiguousarray(array.astype(dtype, copy=False))


@dataclass(frozen=True)
class PortPlacement:
    port: str
    tensor_id: str
    logical_shape: tuple[int, ...]
    dtype: str
    placement: Placement
    slot_shape: tuple[int, ...]
    slot_payload_bytes: int
    padding_byte: int


@dataclass(frozen=True)
class SimplePhysicalRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    active: bool


@dataclass(frozen=True)
class SimplePhysicalBundle:
    operator: str
    contract: str
    status: str
    geometry: DramGeometry
    alignment: int
    placements: tuple[PortPlacement, ...]
    regions: tuple[SimplePhysicalRegion, ...]
    payloads: dict[tuple[str, int], bytes]

    def placement(self, tensor_id: str) -> PortPlacement:
        matches = [item for item in self.placements if item.tensor_id == tensor_id]
        if len(matches) != 1:
            raise KeyError(f"expected one placement for tensor {tensor_id!r}")
        return matches[0]

    def region(self, port: str, slice_id: int) -> SimplePhysicalRegion:
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
            base_addresses = tuple(
                self.region(placement.port, slice_id).base_address
                for slice_id in range(self.geometry.slice_count)
            )
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
                    partition={
                        "axis": 0 if placement.placement == "batch" else None,
                        "policy": (
                            "one_batch_item_per_slice"
                            if placement.placement == "batch"
                            else "replicated_on_every_slice"
                        ),
                        "slice_count": self.geometry.slice_count,
                    },
                    packing={
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "subword_bytes": self.geometry.subword_bytes,
                    },
                    base_addresses=base_addresses,
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
    padding_byte: int = 0


class _SimpleOperatorLayout:
    contract = "w4_batch_slice_candidate_v1"
    status = "candidate"

    def __init__(self, geometry: DramGeometry | None = None, alignment: int = 16):
        self.geometry = geometry or DramGeometry()
        if self.geometry.slice_count != 16:
            raise ValueError("W4 simple-op candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        self.alignment = alignment

    def _pack(self, operator: str, ports: tuple[_PortInput, ...]) -> SimplePhysicalBundle:
        if not ports:
            raise ValueError("at least one port is required")
        if len({item.port for item in ports}) != len(ports):
            raise ValueError("port names must be unique")
        if len({item.tensor_id for item in ports}) != len(ports):
            raise ValueError("tensor IDs must be unique within an operator bundle")

        placements: list[PortPlacement] = []
        canonical: dict[str, np.ndarray] = {}
        offsets: dict[str, int] = {}
        cursor = 0
        for item in ports:
            array = np.asarray(item.array)
            if array.dtype.hasobject:
                raise TypeError(f"port {item.port} cannot contain object values")
            if not 0 <= item.padding_byte <= 255:
                raise ValueError("padding_byte must fit uint8")
            if item.placement == "batch":
                if array.ndim < 1:
                    raise ValueError(f"batch port {item.port} must have rank >= 1")
                if not 1 <= array.shape[0] <= self.geometry.slice_count:
                    raise ValueError(
                        f"batch port {item.port} must contain 1..16 batch items"
                    )
                slot_shape = tuple(int(value) for value in array.shape[1:])
                slot_payload_bytes = int(array[0].nbytes)
            else:
                if array.size == 0:
                    raise ValueError(f"replicated port {item.port} cannot be empty")
                slot_shape = tuple(int(value) for value in array.shape)
                slot_payload_bytes = int(array.nbytes)
            canonical[item.port] = _little_endian(array)
            cursor = _align(cursor, self.alignment)
            offsets[item.port] = cursor
            cursor += _align(slot_payload_bytes, self.alignment)
            placements.append(
                PortPlacement(
                    port=item.port,
                    tensor_id=item.tensor_id,
                    logical_shape=tuple(int(value) for value in array.shape),
                    dtype=str(array.dtype),
                    placement=item.placement,
                    slot_shape=slot_shape,
                    slot_payload_bytes=slot_payload_bytes,
                    padding_byte=item.padding_byte,
                )
            )
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("simple-op physical regions exceed one slice capacity")

        regions: list[SimplePhysicalRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for item, placement in zip(ports, placements, strict=True):
            array = canonical[item.port]
            aligned_size = _align(placement.slot_payload_bytes, self.alignment)
            for slice_id in range(self.geometry.slice_count):
                active = item.placement == "replicated" or slice_id < array.shape[0]
                if item.placement == "replicated":
                    raw = array.tobytes(order="C")
                elif active:
                    raw = np.ascontiguousarray(array[slice_id]).tobytes(order="C")
                else:
                    raw = bytes([item.padding_byte]) * placement.slot_payload_bytes
                payload = raw + bytes(aligned_size - len(raw))
                payloads[(item.port, slice_id)] = payload
                regions.append(
                    SimplePhysicalRegion(
                        port=item.port,
                        tensor_id=item.tensor_id,
                        slice_id=slice_id,
                        base_address=(
                            self.geometry.slice_base(slice_id) + offsets[item.port]
                        ),
                        payload_bytes=placement.slot_payload_bytes,
                        size_bytes=aligned_size,
                        active=active,
                    )
                )
        bundle = SimplePhysicalBundle(
            operator=operator,
            contract=self.contract,
            status=self.status,
            geometry=self.geometry,
            alignment=self.alignment,
            placements=tuple(placements),
            regions=tuple(regions),
            payloads=payloads,
        )
        self.validate(bundle)
        return bundle

    def inverse_port(self, bundle: SimplePhysicalBundle, tensor_id: str) -> np.ndarray:
        placement = bundle.placement(tensor_id)
        dtype = np.dtype(placement.dtype)
        if placement.placement == "replicated":
            arrays = [
                np.frombuffer(
                    bundle.read(placement.port, slice_id)[: placement.slot_payload_bytes],
                    dtype=dtype,
                ).reshape(placement.slot_shape)
                for slice_id in range(bundle.geometry.slice_count)
            ]
            for candidate in arrays[1:]:
                if not np.array_equal(candidate, arrays[0]):
                    raise ValueError(f"replicated tensor {tensor_id} differs between slices")
            return arrays[0].copy()

        batch = placement.logical_shape[0]
        items = [
            np.frombuffer(
                bundle.read(placement.port, slice_id)[: placement.slot_payload_bytes],
                dtype=dtype,
            ).reshape(placement.slot_shape)
            for slice_id in range(batch)
        ]
        return np.stack(items, axis=0).copy()

    def inverse(self, bundle: SimplePhysicalBundle) -> dict[str, np.ndarray]:
        return {
            placement.tensor_id: self.inverse_port(bundle, placement.tensor_id)
            for placement in bundle.placements
        }

    def explain_coordinate(
        self,
        bundle: SimplePhysicalBundle,
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
        if placement.placement == "batch":
            slice_ids = (coordinate[0],)
            local_coordinate = coordinate[1:]
        else:
            slice_ids = tuple(range(bundle.geometry.slice_count))
            local_coordinate = coordinate
        element_index = (
            0
            if not placement.slot_shape
            else int(np.ravel_multi_index(local_coordinate, placement.slot_shape))
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
                        "slice_id": slice_id,
                        "address": address,
                        "dram_coordinate": bundle.geometry.decode(address),
                        "element_byte": element_byte,
                        "semantic": (
                            "data"
                            if placement.placement == "batch"
                            else "replicated_data"
                        ),
                    }
                )
        return tuple(explanations)

    def validate(self, bundle: SimplePhysicalBundle) -> dict[str, int]:
        if bundle.contract != self.contract or bundle.status != self.status:
            raise ValueError("bundle contract does not match this layout")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("bundle geometry/alignment does not match this layout")
        expected_regions = len(bundle.placements) * bundle.geometry.slice_count
        if len(bundle.regions) != expected_regions:
            raise ValueError("bundle does not contain one region per port and slice")
        for slice_id in range(bundle.geometry.slice_count):
            previous_end = bundle.geometry.slice_base(slice_id)
            slice_end = previous_end + bundle.geometry.bytes_per_slice
            for placement in bundle.placements:
                region = bundle.region(placement.port, slice_id)
                payload = bundle.read(placement.port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError(f"port {placement.port} is not aligned")
                if region.base_address < previous_end:
                    raise ValueError("simple-op physical regions overlap")
                if region.base_address + region.size_bytes > slice_end:
                    raise ValueError("simple-op physical region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("physical payload size differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("128-bit alignment padding is corrupted")
                if placement.placement == "batch":
                    batch = placement.logical_shape[0]
                    if region.active != (slice_id < batch):
                        raise ValueError("batch activity mask is inconsistent")
                    if not region.active and payload[: region.payload_bytes] != bytes(
                        [placement.padding_byte]
                    ) * region.payload_bytes:
                        raise ValueError("inactive batch slice padding is corrupted")
                elif not region.active:
                    raise ValueError("replicated region cannot be inactive")
                previous_end = region.base_address + region.size_bytes
        self.inverse(bundle)
        return {
            "slice_count": bundle.geometry.slice_count,
            "port_count": len(bundle.placements),
            "region_count": len(bundle.regions),
            "physical_bytes": sum(len(value) for value in bundle.payloads.values()),
        }


class QuantizeLinearPhysicalLayout(_SimpleOperatorLayout):
    def forward(
        self,
        *,
        input_tensor: np.ndarray,
        scale: np.ndarray,
        zero_point: np.ndarray,
        output_tensor: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
    ) -> SimplePhysicalBundle:
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
        if scale.dtype != np.float32 or scale.shape != (1,):
            raise TypeError("QuantizeLinear scale must be scalar float32 with shape (1,)")
        if zero_point.dtype != np.uint8 or zero_point.shape != (1,):
            raise TypeError("QuantizeLinear zero_point must be scalar uint8 with shape (1,)")
        if output_tensor.dtype != np.uint8 or output_tensor.shape != input_tensor.shape:
            raise TypeError("QuantizeLinear output must be uint8 with the input shape")
        return self._pack(
            "QuantizeLinear",
            (
                _PortInput("A", ids["A"], input_tensor, "batch"),
                _PortInput("scale", ids["scale"], scale, "replicated"),
                _PortInput("zero_point", ids["zero_point"], zero_point, "replicated"),
                _PortInput("D", ids["D"], output_tensor, "batch"),
            ),
        )


class DequantizeLinearPhysicalLayout(_SimpleOperatorLayout):
    def forward(
        self,
        *,
        input_tensor: np.ndarray,
        scale: np.ndarray,
        zero_point: np.ndarray,
        output_tensor: np.ndarray,
        tensor_ids: dict[str, str] | None = None,
    ) -> SimplePhysicalBundle:
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
        if scale.dtype != np.float32 or scale.shape != (1,):
            raise TypeError("DequantizeLinear scale must be scalar float32 with shape (1,)")
        if zero_point.dtype != np.uint8 or zero_point.shape != (1,):
            raise TypeError("DequantizeLinear zero_point must be scalar uint8 with shape (1,)")
        if output_tensor.dtype != np.float32 or output_tensor.shape != input_tensor.shape:
            raise TypeError("DequantizeLinear output must be float32 with the input shape")
        return self._pack(
            "DequantizeLinear",
            (
                _PortInput("A", ids["A"], input_tensor, "batch"),
                _PortInput("scale", ids["scale"], scale, "replicated"),
                _PortInput("zero_point", ids["zero_point"], zero_point, "replicated"),
                _PortInput("D", ids["D"], output_tensor, "batch"),
            ),
        )


@dataclass(frozen=True)
class ZeroCopyViewProof:
    source_bundle: SimplePhysicalBundle
    source_tensor_id: str
    output_tensor_id: str
    input_shape: tuple[int, ...]
    output_shape: tuple[int, ...]
    dtype: str
    axis: int
    contract: str = "w4_zero_copy_view_candidate_v1"
    status: str = "candidate"

    def layout_record(self) -> LayoutRecord:
        placement = self.source_bundle.placement(self.source_tensor_id)
        bases = tuple(
            self.source_bundle.region(placement.port, slice_id).base_address
            for slice_id in range(self.source_bundle.geometry.slice_count)
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
                "axis": 0,
                "policy": "alias_existing_batch_partition",
                "slice_count": self.source_bundle.geometry.slice_count,
            },
            packing={
                "element_order": "C",
                "byte_order": "little",
                "alignment_bytes": self.source_bundle.alignment,
                "zero_copy": True,
            },
            base_addresses=bases,
            inverse_status="validated",
            alias_of=self.source_tensor_id,
        )


class ZeroCopyViewLayout:
    def forward(
        self,
        *,
        source_bundle: SimplePhysicalBundle,
        source_tensor_id: str,
        output_tensor_id: str,
        output_shape: tuple[int, ...],
        axis: int = 1,
    ) -> ZeroCopyViewProof:
        placement = source_bundle.placement(source_tensor_id)
        if placement.placement != "batch":
            raise ValueError("zero-copy View source must use batch partitioning")
        input_shape = placement.logical_shape
        rank = len(input_shape)
        normalized_axis = axis + rank if axis < 0 else axis
        if normalized_axis != 1:
            raise ValueError("W4 batch-slice zero-copy View currently requires axis=1")
        expected = (
            math.prod(input_shape[:normalized_axis]),
            math.prod(input_shape[normalized_axis:]),
        )
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
        )
        self.validate(proof)
        return proof

    def inverse(self, proof: ZeroCopyViewProof) -> dict[str, np.ndarray]:
        helper = _SimpleOperatorLayout(
            proof.source_bundle.geometry, proof.source_bundle.alignment
        )
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
        source_coordinate = np.unravel_index(
            np.ravel_multi_index(coordinate, proof.output_shape), proof.input_shape
        )
        helper = _SimpleOperatorLayout(
            proof.source_bundle.geometry, proof.source_bundle.alignment
        )
        result = helper.explain_coordinate(
            proof.source_bundle,
            proof.source_tensor_id,
            tuple(int(value) for value in source_coordinate),
        )
        return tuple(
            {
                **item,
                "tensor_id": proof.output_tensor_id,
                "logical_coordinate": coordinate,
                "source_tensor_id": proof.source_tensor_id,
                "source_coordinate": tuple(int(value) for value in source_coordinate),
                "semantic": "zero_copy_alias",
            }
            for item in result
        )

    def validate(self, proof: ZeroCopyViewProof) -> dict[str, int | bool]:
        if proof.contract != "w4_zero_copy_view_candidate_v1" or proof.status != "candidate":
            raise ValueError("unsupported zero-copy View contract")
        placement = proof.source_bundle.placement(proof.source_tensor_id)
        if placement.placement != "batch" or proof.axis != 1:
            raise ValueError("View proof is incompatible with batch-slice storage")
        if math.prod(proof.input_shape) != math.prod(proof.output_shape):
            raise ValueError("View changes the tensor element count")
        helper = _SimpleOperatorLayout(
            proof.source_bundle.geometry, proof.source_bundle.alignment
        )
        helper.validate(proof.source_bundle)
        recovered = self.inverse(proof)
        if recovered[proof.source_tensor_id].tobytes(order="C") != recovered[
            proof.output_tensor_id
        ].tobytes(order="C"):
            raise ValueError("View alias changes the physical byte order")
        return {
            "zero_copy": True,
            "slice_count": proof.source_bundle.geometry.slice_count,
            "aliased_bytes": int(recovered[proof.output_tensor_id].nbytes),
        }
