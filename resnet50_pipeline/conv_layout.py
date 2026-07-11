from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .memory import ByteProvenance, DramGeometry, SparsePhysicalImage


def _align(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


@dataclass(frozen=True)
class PhysicalRegion:
    name: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    dtype: str
    physical_shape: tuple[int, ...]


@dataclass
class ConvPhysicalBundle:
    geometry: DramGeometry
    image: SparsePhysicalImage
    regions: tuple[PhysicalRegion, ...]
    metadata: dict[str, object]

    def region(self, name: str, slice_id: int) -> PhysicalRegion:
        matches = [item for item in self.regions if item.name == name and item.slice_id == slice_id]
        if len(matches) != 1:
            raise KeyError(f"expected one region {name!r} on slice {slice_id}")
        return matches[0]

    def read_array(self, name: str, slice_id: int) -> np.ndarray:
        region = self.region(name, slice_id)
        payload = self.image.read(region.base_address, region.payload_bytes)
        return np.frombuffer(payload, dtype=np.dtype(region.dtype)).reshape(region.physical_shape)

    def explain_address(self, address: int):
        return self.image.explain(address)

    def addresses_for(self, tensor_id: str, logical_coordinate: tuple[int, ...]) -> tuple[int, ...]:
        return self.image.addresses_for(tensor_id, logical_coordinate)


class SmallConvPhysicalLayout:
    """Candidate W2 Conv layout derived from the NDPFuncModel ring intent.

    Activation channels are split contiguously over slices and stored NHWC with
    C fastest. Output channels are split contiguously; weight is stored
    [R,S,K_local,C_padded], and output is [N,H,W,K_local]. This is a reversible
    software contract for W2, not an approved target-hardware layout.
    """

    def __init__(self, geometry: DramGeometry, slice_count: int, alignment: int = 16):
        if not 1 <= slice_count <= geometry.slice_count:
            raise ValueError("slice_count must fit the DRAM geometry")
        if alignment <= 0:
            raise ValueError("alignment must be positive")
        self.geometry = geometry
        self.slice_count = slice_count
        self.alignment = alignment

    def _pack_array(
        self,
        array: np.ndarray,
        tensor_id: str,
        coordinate: Callable[[tuple[int, ...]], tuple[int, ...] | None],
        padding_note: str,
    ) -> tuple[bytes, tuple[ByteProvenance, ...], str]:
        dtype = array.dtype.newbyteorder("<")
        canonical = np.ascontiguousarray(array.astype(dtype, copy=False))
        payload = canonical.tobytes(order="C")
        itemsize = dtype.itemsize
        provenance: list[ByteProvenance] = []
        for physical_coordinate in np.ndindex(canonical.shape):
            logical_coordinate = coordinate(physical_coordinate)
            semantic = "data" if logical_coordinate is not None else "tensor_padding"
            note = "" if logical_coordinate is not None else padding_note
            for element_byte in range(itemsize):
                provenance.append(
                    ByteProvenance(
                        tensor_id=tensor_id,
                        logical_coordinate=logical_coordinate,
                        element_byte=element_byte,
                        semantic=semantic,
                        note=note,
                    )
                )
        return payload, tuple(provenance), dtype.str

    def _with_alignment(
        self,
        payload: bytes,
        provenance: tuple[ByteProvenance, ...],
        tensor_id: str,
    ) -> tuple[bytes, tuple[ByteProvenance, ...]]:
        aligned_size = _align(len(payload), self.alignment)
        padding = aligned_size - len(payload)
        if not padding:
            return payload, provenance
        aligned_provenance = provenance + tuple(
            ByteProvenance(tensor_id, None, 0, "alignment", "region alignment")
            for _ in range(padding)
        )
        return payload + bytes(padding), aligned_provenance

    def forward(
        self,
        *,
        activation: np.ndarray,
        weight: np.ndarray,
        bias: np.ndarray,
        w_scale: np.ndarray,
        w_zero_point: np.ndarray,
        x_scale: np.float32,
        x_zero_point: np.uint8,
        y_scale: np.float32,
        y_zero_point: np.uint8,
        output: np.ndarray | None = None,
    ) -> ConvPhysicalBundle:
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("activation must be uint8 NCHW")
        if weight.dtype != np.int8 or weight.ndim != 4:
            raise TypeError("weight must be int8 OIHW")
        n, channels, height, width = activation.shape
        output_channels, weight_channels, kernel_h, kernel_w = weight.shape
        if weight_channels != channels:
            raise ValueError("W2 candidate physical layout currently supports group=1 only")
        if bias.dtype != np.int32 or bias.shape != (output_channels,):
            raise TypeError("bias must be int32 with one value per output channel")
        w_scale = np.asarray(w_scale, dtype=np.float32).reshape(-1)
        w_zero_point = np.asarray(w_zero_point, dtype=np.int8).reshape(-1)
        if w_scale.size == 1:
            w_scale = np.repeat(w_scale, output_channels)
        if w_zero_point.size == 1:
            w_zero_point = np.repeat(w_zero_point, output_channels)
        if w_scale.shape != (output_channels,) or w_zero_point.shape != (output_channels,):
            raise ValueError("weight qparams must be scalar or per-output-channel")
        if output is not None:
            if output.dtype != np.uint8 or output.ndim != 4:
                raise TypeError("output must be uint8 NCHW")
            if output.shape[0] != n or output.shape[1] != output_channels:
                raise ValueError("output N/K dimensions do not match activation/weight")

        c_tile = math.ceil(channels / self.slice_count)
        k_tile = math.ceil(output_channels / self.slice_count)
        c_padded = c_tile * self.slice_count
        slice_payloads: list[dict[str, tuple[bytes, tuple[ByteProvenance, ...], str, tuple[int, ...]]]] = []

        for slice_id in range(self.slice_count):
            c_start = slice_id * c_tile
            k_start = slice_id * k_tile
            by_name: dict[str, tuple[bytes, tuple[ByteProvenance, ...], str, tuple[int, ...]]] = {}

            activation_physical = np.full(
                (n, height, width, c_tile), int(x_zero_point), dtype=np.uint8
            )
            valid_c = max(0, min(c_tile, channels - c_start))
            if valid_c:
                activation_physical[..., :valid_c] = np.transpose(
                    activation[:, c_start : c_start + valid_c], (0, 2, 3, 1)
                )
            packed = self._pack_array(
                activation_physical,
                "activation",
                lambda pc, start=c_start: (
                    (pc[0], start + pc[3], pc[1], pc[2])
                    if start + pc[3] < channels
                    else None
                ),
                "activation C tail filled with x_zero_point",
            )
            by_name["activation"] = (*packed, activation_physical.shape)

            weight_physical = np.empty(
                (kernel_h, kernel_w, k_tile, c_padded), dtype=np.int8
            )
            for local_k in range(k_tile):
                global_k = k_start + local_k
                fill = int(w_zero_point[global_k]) if global_k < output_channels else 0
                weight_physical[:, :, local_k, :] = fill
                if global_k < output_channels:
                    weight_physical[:, :, local_k, :channels] = np.transpose(
                        weight[global_k], (1, 2, 0)
                    )
            packed = self._pack_array(
                weight_physical,
                "weight",
                lambda pc, start=k_start: (
                    (start + pc[2], pc[3], pc[0], pc[1])
                    if start + pc[2] < output_channels and pc[3] < channels
                    else None
                ),
                "weight K/C tail filled with the corresponding weight zero point",
            )
            by_name["weight"] = (*packed, weight_physical.shape)

            bias_physical = np.zeros(k_tile, dtype="<i4")
            scale_physical = np.zeros(k_tile, dtype="<f4")
            wzp_physical = np.zeros(k_tile, dtype=np.int8)
            valid_k = max(0, min(k_tile, output_channels - k_start))
            if valid_k:
                bias_physical[:valid_k] = bias[k_start : k_start + valid_k]
                scale_physical[:valid_k] = w_scale[k_start : k_start + valid_k]
                wzp_physical[:valid_k] = w_zero_point[k_start : k_start + valid_k]
            mapper = lambda pc, start=k_start: ((start + pc[0],) if start + pc[0] < output_channels else None)
            for name, tensor_id, array in (
                ("bias", "bias", bias_physical),
                ("w_scale", "w_scale", scale_physical),
                ("w_zero_point", "w_zero_point", wzp_physical),
            ):
                packed = self._pack_array(array, tensor_id, mapper, f"{name} K tail")
                by_name[name] = (*packed, array.shape)

            scalar_payload = struct.pack(
                "<fB3xfB3x",
                float(np.float32(x_scale)),
                int(np.uint8(x_zero_point)),
                float(np.float32(y_scale)),
                int(np.uint8(y_zero_point)),
            )
            scalar_provenance: list[ByteProvenance] = []
            scalar_provenance.extend(
                ByteProvenance("x_scale", (), byte, "data") for byte in range(4)
            )
            scalar_provenance.append(ByteProvenance("x_zero_point", (), 0, "data"))
            scalar_provenance.extend(
                ByteProvenance("scalar_qparams", None, 0, "alignment", "struct padding")
                for _ in range(3)
            )
            scalar_provenance.extend(
                ByteProvenance("y_scale", (), byte, "data") for byte in range(4)
            )
            scalar_provenance.append(ByteProvenance("y_zero_point", (), 0, "data"))
            scalar_provenance.extend(
                ByteProvenance("scalar_qparams", None, 0, "alignment", "struct padding")
                for _ in range(3)
            )
            by_name["scalar_qparams"] = (
                scalar_payload,
                tuple(scalar_provenance),
                "|u1",
                (16,),
            )

            if output is not None:
                output_h, output_w = output.shape[2:]
                output_physical = np.full(
                    (n, output_h, output_w, k_tile), int(y_zero_point), dtype=np.uint8
                )
                if valid_k:
                    output_physical[..., :valid_k] = np.transpose(
                        output[:, k_start : k_start + valid_k], (0, 2, 3, 1)
                    )
                packed = self._pack_array(
                    output_physical,
                    "output",
                    lambda pc, start=k_start: (
                        (pc[0], start + pc[3], pc[1], pc[2])
                        if start + pc[3] < output_channels
                        else None
                    ),
                    "output K tail filled with y_zero_point",
                )
                by_name["output"] = (*packed, output_physical.shape)
            slice_payloads.append(by_name)

        order = ["activation", "weight", "bias", "w_scale", "w_zero_point", "scalar_qparams"]
        if output is not None:
            order.append("output")
        offsets: dict[str, int] = {}
        cursor = 0
        for name in order:
            cursor = _align(cursor, self.alignment)
            offsets[name] = cursor
            cursor += _align(len(slice_payloads[0][name][0]), self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("Conv physical regions exceed one slice capacity")

        image = SparsePhysicalImage(self.geometry)
        regions: list[PhysicalRegion] = []
        for slice_id, by_name in enumerate(slice_payloads):
            for name in order:
                payload, provenance, dtype, shape = by_name[name]
                aligned_payload, aligned_provenance = self._with_alignment(
                    payload, provenance, name
                )
                base_address = self.geometry.slice_base(slice_id) + offsets[name]
                image.write(base_address, aligned_payload, aligned_provenance)
                regions.append(
                    PhysicalRegion(
                        name=name,
                        tensor_id=name,
                        slice_id=slice_id,
                        base_address=base_address,
                        payload_bytes=len(payload),
                        size_bytes=len(aligned_payload),
                        dtype=dtype,
                        physical_shape=tuple(shape),
                    )
                )

        return ConvPhysicalBundle(
            geometry=self.geometry,
            image=image,
            regions=tuple(regions),
            metadata={
                "contract": "w2_ndp_ring_candidate_v1",
                "status": "candidate",
                "slice_count": self.slice_count,
                "activation_shape": activation.shape,
                "weight_shape": weight.shape,
                "output_shape": None if output is None else output.shape,
                "c_tile": c_tile,
                "k_tile": k_tile,
                "c_padded": c_padded,
                "x_zero_point": int(x_zero_point),
                "y_zero_point": int(y_zero_point),
                "per_slice_used_bytes": cursor,
            },
        )

    def inverse_activation(self, bundle: ConvPhysicalBundle) -> np.ndarray:
        n, channels, height, width = bundle.metadata["activation_shape"]
        c_tile = int(bundle.metadata["c_tile"])
        x_zero_point = int(bundle.metadata["x_zero_point"])
        logical = np.empty((n, channels, height, width), dtype=np.uint8)
        for slice_id in range(self.slice_count):
            physical = bundle.read_array("activation", slice_id)
            c_start = slice_id * c_tile
            valid_c = max(0, min(c_tile, channels - c_start))
            if valid_c:
                logical[:, c_start : c_start + valid_c] = np.transpose(
                    physical[..., :valid_c], (0, 3, 1, 2)
                )
            if valid_c < c_tile and np.any(physical[..., valid_c:] != x_zero_point):
                raise ValueError("activation tail padding is corrupted")
        return logical

    def inverse_weight(self, bundle: ConvPhysicalBundle) -> np.ndarray:
        output_channels, channels, kernel_h, kernel_w = bundle.metadata["weight_shape"]
        k_tile = int(bundle.metadata["k_tile"])
        c_padded = int(bundle.metadata["c_padded"])
        logical = np.empty((output_channels, channels, kernel_h, kernel_w), dtype=np.int8)
        for slice_id in range(self.slice_count):
            physical = bundle.read_array("weight", slice_id)
            wzp = bundle.read_array("w_zero_point", slice_id)
            k_start = slice_id * k_tile
            valid_k = max(0, min(k_tile, output_channels - k_start))
            for local_k in range(valid_k):
                logical[k_start + local_k] = np.transpose(
                    physical[:, :, local_k, :channels], (2, 0, 1)
                )
                if channels < c_padded and np.any(
                    physical[:, :, local_k, channels:] != wzp[local_k]
                ):
                    raise ValueError("weight C tail padding is corrupted")
            if valid_k < k_tile and np.any(physical[:, :, valid_k:, :] != 0):
                raise ValueError("weight K tail padding is corrupted")
        return logical

    def inverse_channel_vector(
        self, bundle: ConvPhysicalBundle, name: str, dtype: np.dtype
    ) -> np.ndarray:
        output_channels = bundle.metadata["weight_shape"][0]
        k_tile = int(bundle.metadata["k_tile"])
        logical = np.empty(output_channels, dtype=dtype)
        for slice_id in range(self.slice_count):
            physical = bundle.read_array(name, slice_id)
            k_start = slice_id * k_tile
            valid_k = max(0, min(k_tile, output_channels - k_start))
            if valid_k:
                logical[k_start : k_start + valid_k] = physical[:valid_k]
            if valid_k < k_tile and np.any(physical[valid_k:] != 0):
                raise ValueError(f"{name} K tail padding is corrupted")
        return logical

    def inverse_output(self, bundle: ConvPhysicalBundle) -> np.ndarray:
        shape = bundle.metadata["output_shape"]
        if shape is None:
            raise ValueError("bundle has no output region")
        n, output_channels, height, width = shape
        k_tile = int(bundle.metadata["k_tile"])
        y_zero_point = int(bundle.metadata["y_zero_point"])
        logical = np.empty(shape, dtype=np.uint8)
        for slice_id in range(self.slice_count):
            physical = bundle.read_array("output", slice_id)
            k_start = slice_id * k_tile
            valid_k = max(0, min(k_tile, output_channels - k_start))
            if valid_k:
                logical[:, k_start : k_start + valid_k] = np.transpose(
                    physical[..., :valid_k], (0, 3, 1, 2)
                )
            if valid_k < k_tile and np.any(physical[..., valid_k:] != y_zero_point):
                raise ValueError("output K tail padding is corrupted")
        return logical

    def inverse_scalar_qparams(
        self, bundle: ConvPhysicalBundle, slice_id: int = 0
    ) -> tuple[np.float32, np.uint8, np.float32, np.uint8]:
        region = bundle.region("scalar_qparams", slice_id)
        payload = bundle.image.read(region.base_address, region.payload_bytes)
        x_scale, x_zero_point, y_scale, y_zero_point = struct.unpack("<fB3xfB3x", payload)
        return (
            np.float32(x_scale),
            np.uint8(x_zero_point),
            np.float32(y_scale),
            np.uint8(y_zero_point),
        )

    def inverse(self, bundle: ConvPhysicalBundle) -> dict[str, object]:
        recovered: dict[str, object] = {
            "activation": self.inverse_activation(bundle),
            "weight": self.inverse_weight(bundle),
            "bias": self.inverse_channel_vector(bundle, "bias", np.dtype("<i4")),
            "w_scale": self.inverse_channel_vector(bundle, "w_scale", np.dtype("<f4")),
            "w_zero_point": self.inverse_channel_vector(
                bundle, "w_zero_point", np.dtype("i1")
            ),
            "scalar_qparams": self.inverse_scalar_qparams(bundle),
        }
        if bundle.metadata["output_shape"] is not None:
            recovered["output"] = self.inverse_output(bundle)
        return recovered

    def explain_coordinate(
        self,
        bundle: ConvPhysicalBundle,
        tensor_id: str,
        logical_coordinate: tuple[int, ...],
    ) -> tuple[dict[str, object], ...]:
        addresses = bundle.addresses_for(tensor_id, logical_coordinate)
        if not addresses:
            raise KeyError(
                f"no physical bytes for {tensor_id}{logical_coordinate}"
            )
        explained: list[dict[str, object]] = []
        for address in addresses:
            coordinate, provenance = bundle.explain_address(address)
            explained.append(
                {
                    "address": address,
                    "dram_coordinate": coordinate,
                    "element_byte": provenance.element_byte,
                    "semantic": provenance.semantic,
                    "note": provenance.note,
                }
            )
        return tuple(explained)

    def validate(self, bundle: ConvPhysicalBundle) -> dict[str, int]:
        if bundle.geometry != self.geometry:
            raise ValueError("bundle DRAM geometry does not match this layout")
        if int(bundle.metadata["slice_count"]) != self.slice_count:
            raise ValueError("bundle slice_count does not match this layout")
        total_region_bytes = 0
        for region in bundle.regions:
            if region.base_address % self.alignment:
                raise ValueError(f"region {region.name} is not aligned")
            slice_start = self.geometry.slice_base(region.slice_id)
            slice_end = slice_start + self.geometry.bytes_per_slice
            if not (
                slice_start <= region.base_address
                and region.base_address + region.size_bytes <= slice_end
            ):
                raise ValueError(f"region {region.name} crosses a slice boundary")
            bundle.image.read(region.base_address, region.size_bytes)
            total_region_bytes += region.size_bytes
        if total_region_bytes != bundle.image.written_byte_count:
            raise ValueError("physical image contains bytes outside declared regions")

        recovered = self.inverse(bundle)
        reference_qparams = recovered["scalar_qparams"]
        for slice_id in range(1, self.slice_count):
            if self.inverse_scalar_qparams(bundle, slice_id) != reference_qparams:
                raise ValueError("replicated scalar qparams differ between slices")
        return {
            "region_count": len(bundle.regions),
            "written_byte_count": bundle.image.written_byte_count,
            "slice_count": self.slice_count,
        }
