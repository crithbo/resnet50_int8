from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .conv16_layout import _align, _canonical, _pair
from .memory import DramGeometry, LEGACY_DRAM_GEOMETRY16
from .records import LayoutRecord


Topology = Literal["batch", "channel"]


@dataclass(frozen=True)
class MaxPoolRegion:
    port: str
    tensor_id: str
    slice_id: int
    base_address: int
    payload_bytes: int
    size_bytes: int
    physical_shape: tuple[int, ...]
    active: bool


@dataclass(frozen=True)
class MaxPoolPhysicalBundle:
    geometry: DramGeometry
    alignment: int
    regions: tuple[MaxPoolRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    metadata: dict[str, Any]

    def region(self, port: str, slice_id: int) -> MaxPoolRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one MaxPool {port} region on slice {slice_id}")
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        for port in ("A", "D"):
            spec = self.metadata["ports"][port]
            bases = tuple(
                self.region(port, slice_id).base_address
                for slice_id in range(self.geometry.slice_count)
            )
            records.append(
                LayoutRecord(
                    layout_id=f"layout-maxpool-{self.metadata['topology']}-{port.lower()}-{spec['tensor_id']}",
                    tensor_id=spec["tensor_id"],
                    transform=self.metadata["contract"],
                    contract_status=self.metadata["status"],
                    port=port,
                    logical_shape=tuple(spec["logical_shape"]),
                    logical_dtype="uint8",
                    partition={
                        "axis": 0 if self.metadata["topology"] == "batch" else 1,
                        "policy": (
                            "one_batch_item_per_slice"
                            if self.metadata["topology"] == "batch"
                            else "contiguous_channel_partition_across_slices"
                        ),
                        "slice_count": 16,
                        "channel_tile": self.metadata["channel_tile"],
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "element_order": "C",
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "channel_tail_value": spec["tail_value"],
                        "spatial_padding_value": self.metadata["spatial_padding_value"],
                        "window_mode": "address_generator",
                        "input_alias_requested": self.metadata["input_alias_requested"],
                    },
                    base_addresses=bases,
                    inverse_status="validated",
                    alias_of=(
                        spec["tensor_id"]
                        if port == "A" and self.metadata["input_alias_requested"]
                        else None
                    ),
                )
            )
        return tuple(records)


class MaxPool16PhysicalLayout:
    status = "candidate"

    def __init__(
        self,
        topology: Topology,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
        channel_tile: int = 8,
    ):
        if topology not in {"batch", "channel"}:
            raise ValueError("MaxPool topology must be batch or channel")
        self.topology = topology
        self.contract = f"w4_maxpool_{topology}16_candidate_v1"
        self.geometry = geometry or LEGACY_DRAM_GEOMETRY16
        if self.geometry.slice_count != 16:
            raise ValueError("MaxPool candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        if channel_tile <= 0:
            raise ValueError("channel_tile must be positive")
        self.alignment = alignment
        self.channel_tile = channel_tile

    def _output_shape(
        self,
        input_shape: tuple[int, int, int, int],
        kernel_shape: tuple[int, int],
        strides: tuple[int, int],
        pads: tuple[int, int, int, int],
        dilations: tuple[int, int],
    ) -> tuple[int, int, int, int]:
        n, channels, height, width = input_shape
        effective_h = (kernel_shape[0] - 1) * dilations[0] + 1
        effective_w = (kernel_shape[1] - 1) * dilations[1] + 1
        output_h = (height + pads[0] + pads[2] - effective_h) // strides[0] + 1
        output_w = (width + pads[1] + pads[3] - effective_w) // strides[1] + 1
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
        input_offset: int = 0,
    ) -> dict[str, Any]:
        kernel_shape = _pair(kernel_shape, "kernel_shape")
        strides = _pair(strides, "strides")
        dilations = _pair(dilations, "dilations")
        if len(pads) != 4 or any(int(value) < 0 for value in pads):
            raise ValueError("pads must contain four non-negative integers")
        pads = tuple(int(value) for value in pads)
        if int(ceil_mode) != 0:
            raise ValueError("current MaxPool candidate supports ceil_mode=0 only")
        if int(storage_order) != 0:
            raise ValueError("current MaxPool candidate supports storage_order=0 only")
        n, channels, height, width = tuple(int(value) for value in input_shape)
        if any(value <= 0 for value in (n, channels, height, width)):
            raise ValueError("MaxPool input dimensions must be positive")
        if n > 16:
            raise ValueError("MaxPool candidate supports batch <= 16")
        output_shape = self._output_shape(
            (n, channels, height, width), kernel_shape, strides, pads, dilations
        )
        _, _, output_h, output_w = output_shape
        if self.topology == "batch":
            channel_tile = _align(channels, self.channel_tile)
            input_physical_shape = (height, width, channel_tile)
            output_physical_shape = (output_h, output_w, channel_tile)
        else:
            channel_tile = math.ceil(channels / 16)
            input_physical_shape = (n, height, width, channel_tile)
            output_physical_shape = (n, output_h, output_w, channel_tile)
        input_bytes = int(np.prod(input_physical_shape, dtype=np.int64))
        output_bytes = int(np.prod(output_physical_shape, dtype=np.int64))
        if input_offset < 0 or input_offset % self.alignment:
            raise ValueError("MaxPool input_offset must be non-negative and aligned")
        output_offset = _align(input_offset + _align(input_bytes, self.alignment), self.alignment)
        used_bytes = output_offset + _align(output_bytes, self.alignment)
        if used_bytes > self.geometry.bytes_per_slice:
            raise ValueError(
                f"MaxPool regions need {used_bytes} bytes per slice, capacity is "
                f"{self.geometry.bytes_per_slice}"
            )
        return {
            "input_shape": (n, channels, height, width),
            "output_shape": output_shape,
            "kernel_shape": kernel_shape,
            "strides": strides,
            "pads": pads,
            "dilations": dilations,
            "ceil_mode": 0,
            "storage_order": 0,
            "channel_tile": channel_tile,
            "input_physical_shape": input_physical_shape,
            "output_physical_shape": output_physical_shape,
            "input_bytes": input_bytes,
            "output_bytes": output_bytes,
            "input_offset": input_offset,
            "output_offset": output_offset,
            "per_slice_used_bytes": used_bytes,
            "capacity_bytes": self.geometry.bytes_per_slice,
        }

    def _alias_offset(self, input_base_addresses: tuple[int, ...] | None) -> int:
        if input_base_addresses is None:
            return 0
        if len(input_base_addresses) != 16:
            raise ValueError("input_base_addresses must contain 16 addresses")
        offsets: list[int] = []
        for slice_id, address in enumerate(input_base_addresses):
            start = self.geometry.slice_base(slice_id)
            end = start + self.geometry.bytes_per_slice
            if not start <= int(address) < end:
                raise ValueError("MaxPool aliased input base is outside its slice")
            offsets.append(int(address) - start)
        if len(set(offsets)) != 1:
            raise ValueError("MaxPool aliased input bases need one common slice offset")
        return offsets[0]

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
        input_base_addresses: tuple[int, ...] | None = None,
    ) -> MaxPoolPhysicalBundle:
        activation = np.asarray(activation)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("MaxPool activation must be rank-4 uint8 NCHW")
        if output.dtype != np.uint8 or output.ndim != 4:
            raise TypeError("MaxPool output must be rank-4 uint8 NCHW")
        for value, name in (
            (spatial_padding_value, "spatial_padding_value"),
            (input_tail_value, "input_tail_value"),
        ):
            if not 0 <= int(value) <= 255:
                raise ValueError(f"{name} must fit uint8")
        if output_tail_value is None:
            output_tail_value = input_tail_value
        if not 0 <= int(output_tail_value) <= 255:
            raise ValueError("output_tail_value must fit uint8")
        input_offset = self._alias_offset(input_base_addresses)
        plan = self.plan(
            input_shape=tuple(activation.shape),
            kernel_shape=kernel_shape,
            strides=strides,
            pads=pads,
            dilations=dilations,
            ceil_mode=ceil_mode,
            storage_order=storage_order,
            input_offset=input_offset,
        )
        if tuple(output.shape) != plan["output_shape"]:
            raise TypeError("MaxPool output shape does not match inferred NCHW shape")
        ids = {"A": "maxpool_input", "D": "maxpool_output", **(tensor_ids or {})}
        if ids["A"] == ids["D"]:
            raise ValueError("MaxPool input and output tensor IDs must differ")
        n, channels, height, width = activation.shape
        _, _, output_h, output_w = output.shape
        channel_tile = int(plan["channel_tile"])
        arrays: list[dict[str, np.ndarray]] = []
        for slice_id in range(16):
            if self.topology == "batch":
                a = np.full(
                    plan["input_physical_shape"], int(input_tail_value), dtype=np.uint8
                )
                d = np.full(
                    plan["output_physical_shape"], int(output_tail_value), dtype=np.uint8
                )
                valid = slice_id < n
                if valid:
                    a[..., :channels] = np.transpose(activation[slice_id], (1, 2, 0))
                    d[..., :channels] = np.transpose(output[slice_id], (1, 2, 0))
            else:
                c_start = slice_id * channel_tile
                valid_c = max(0, min(channel_tile, channels - c_start))
                a = np.full(
                    (n, height, width, channel_tile),
                    int(input_tail_value),
                    dtype=np.uint8,
                )
                d = np.full(
                    (n, output_h, output_w, channel_tile),
                    int(output_tail_value),
                    dtype=np.uint8,
                )
                valid = valid_c > 0
                if valid_c:
                    a[..., :valid_c] = np.transpose(
                        activation[:, c_start : c_start + valid_c], (0, 2, 3, 1)
                    )
                    d[..., :valid_c] = np.transpose(
                        output[:, c_start : c_start + valid_c], (0, 2, 3, 1)
                    )
            arrays.append({"A": a, "D": d, "active": valid})
        regions: list[MaxPoolRegion] = []
        payloads: dict[tuple[str, int], bytes] = {}
        for slice_id, per_slice in enumerate(arrays):
            for port, offset_key, bytes_key, shape_key in (
                ("A", "input_offset", "input_bytes", "input_physical_shape"),
                ("D", "output_offset", "output_bytes", "output_physical_shape"),
            ):
                raw = _canonical(per_slice[port]).tobytes(order="C")
                payload_bytes = int(plan[bytes_key])
                size_bytes = _align(payload_bytes, self.alignment)
                payloads[(port, slice_id)] = raw + bytes(size_bytes - len(raw))
                regions.append(
                    MaxPoolRegion(
                        port=port,
                        tensor_id=ids[port],
                        slice_id=slice_id,
                        base_address=self.geometry.slice_base(slice_id)
                        + int(plan[offset_key]),
                        payload_bytes=payload_bytes,
                        size_bytes=size_bytes,
                        physical_shape=tuple(plan[shape_key]),
                        active=bool(per_slice["active"]),
                    )
                )
        bundle = MaxPoolPhysicalBundle(
            geometry=self.geometry,
            alignment=self.alignment,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                "contract": self.contract,
                "status": self.status,
                "topology": self.topology,
                "spatial_padding_value": int(spatial_padding_value),
                "input_tail_value": int(input_tail_value),
                "output_tail_value": int(output_tail_value),
                "input_alias_requested": input_base_addresses is not None,
                "ports": {
                    "A": {
                        "tensor_id": ids["A"],
                        "logical_shape": tuple(activation.shape),
                        "physical_axis_order": (
                            "HWC_padded" if self.topology == "batch" else "NHWC_local"
                        ),
                        "tail_value": int(input_tail_value),
                    },
                    "D": {
                        "tensor_id": ids["D"],
                        "logical_shape": tuple(output.shape),
                        "physical_axis_order": (
                            "HWC_padded" if self.topology == "batch" else "NHWC_local"
                        ),
                        "tail_value": int(output_tail_value),
                    },
                },
                **plan,
            },
        )
        self.validate(bundle)
        return bundle

    def _read_array(
        self, bundle: MaxPoolPhysicalBundle, port: str, slice_id: int
    ) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes], dtype=np.uint8
        ).reshape(region.physical_shape)

    def inverse_port(self, bundle: MaxPoolPhysicalBundle, port: str) -> np.ndarray:
        if port not in {"A", "D"}:
            raise KeyError(f"unknown MaxPool port {port}")
        shape = tuple(bundle.metadata["ports"][port]["logical_shape"])
        n, channels, height, width = shape
        channel_tile = int(bundle.metadata["channel_tile"])
        if self.topology == "batch":
            return np.stack(
                [
                    np.transpose(
                        self._read_array(bundle, port, slice_id)[..., :channels],
                        (2, 0, 1),
                    )
                    for slice_id in range(n)
                ]
            )
        logical = np.empty((n, channels, height, width), dtype=np.uint8)
        for slice_id in range(16):
            c_start = slice_id * channel_tile
            valid_c = max(0, min(channel_tile, channels - c_start))
            if valid_c:
                logical[:, c_start : c_start + valid_c] = np.transpose(
                    self._read_array(bundle, port, slice_id)[..., :valid_c],
                    (0, 3, 1, 2),
                )
        return logical

    def inverse(self, bundle: MaxPoolPhysicalBundle) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(bundle, port)
            for port in ("A", "D")
        }

    def explain_coordinate(
        self,
        bundle: MaxPoolPhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, int, int, int],
    ) -> dict[str, Any]:
        ports = [
            port
            for port in ("A", "D")
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(ports) != 1:
            raise KeyError(f"expected one MaxPool port for tensor {tensor_id!r}")
        port = ports[0]
        shape = tuple(bundle.metadata["ports"][port]["logical_shape"])
        if any(
            index < 0 or index >= size
            for index, size in zip(coordinate, shape, strict=True)
        ):
            raise IndexError("MaxPool logical coordinate is out of range")
        n, channel, height, width = coordinate
        if self.topology == "batch":
            slice_id = n
            physical_coordinate = (height, width, channel)
        else:
            channel_tile = int(bundle.metadata["channel_tile"])
            slice_id = channel // channel_tile
            physical_coordinate = (n, height, width, channel % channel_tile)
        region = bundle.region(port, slice_id)
        element_index = int(
            np.ravel_multi_index(physical_coordinate, region.physical_shape)
        )
        address = region.base_address + element_index
        return {
            "tensor_id": tensor_id,
            "port": port,
            "logical_coordinate": coordinate,
            "physical_coordinate": physical_coordinate,
            "slice_id": slice_id,
            "address": address,
            "dram_coordinate": bundle.geometry.decode(address),
            "semantic": "data",
        }

    def explain_window(
        self,
        bundle: MaxPoolPhysicalBundle,
        *,
        batch: int,
        channel: int,
        output_h: int,
        output_w: int,
        kernel_h: int,
        kernel_w: int,
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["input_shape"]
        _, _, output_height, output_width = bundle.metadata["output_shape"]
        bounds = (
            (batch, n, "batch"),
            (channel, channels, "channel"),
            (output_h, output_height, "output_h"),
            (output_w, output_width, "output_w"),
            (kernel_h, bundle.metadata["kernel_shape"][0], "kernel_h"),
            (kernel_w, bundle.metadata["kernel_shape"][1], "kernel_w"),
        )
        for value, size, name in bounds:
            if not 0 <= value < size:
                raise IndexError(f"{name} is out of range")
        input_h = (
            output_h * bundle.metadata["strides"][0]
            + kernel_h * bundle.metadata["dilations"][0]
            - bundle.metadata["pads"][0]
        )
        input_w = (
            output_w * bundle.metadata["strides"][1]
            + kernel_w * bundle.metadata["dilations"][1]
            - bundle.metadata["pads"][1]
        )
        if not (0 <= input_h < height and 0 <= input_w < width):
            return {
                "semantic": "spatial_padding",
                "value": bundle.metadata["spatial_padding_value"],
                "logical_coordinate": None,
                "address": None,
            }
        tensor_id = bundle.metadata["ports"]["A"]["tensor_id"]
        return self.explain_coordinate(
            bundle, tensor_id, (batch, channel, input_h, input_w)
        )

    def validate(self, bundle: MaxPoolPhysicalBundle) -> dict[str, int]:
        if bundle.metadata["contract"] != self.contract:
            raise ValueError("MaxPool bundle contract does not match this layout")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("MaxPool bundle geometry/alignment mismatch")
        if len(bundle.regions) != 32:
            raise ValueError("MaxPool bundle must contain A/D on 16 slices")
        n, channels, _, _ = bundle.metadata["input_shape"]
        channel_tile = int(bundle.metadata["channel_tile"])
        for slice_id in range(16):
            a = bundle.region("A", slice_id)
            d = bundle.region("D", slice_id)
            if a.base_address % self.alignment or d.base_address % self.alignment:
                raise ValueError("MaxPool region is not aligned")
            slice_start = bundle.geometry.slice_base(slice_id)
            slice_end = slice_start + bundle.geometry.bytes_per_slice
            if not (
                slice_start <= a.base_address
                and a.base_address + a.size_bytes <= d.base_address
                and d.base_address + d.size_bytes <= slice_end
            ):
                raise ValueError("MaxPool regions overlap or cross a slice boundary")
            for region in (a, d):
                payload = bundle.read(region.port, slice_id)
                if len(payload) != region.size_bytes:
                    raise ValueError("MaxPool payload length differs from its region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("MaxPool alignment padding is corrupted")
            expected_active = (
                slice_id < n
                if self.topology == "batch"
                else slice_id * channel_tile < channels
            )
            if a.active != expected_active or d.active != expected_active:
                raise ValueError("MaxPool activity mask is inconsistent")
            a_array = self._read_array(bundle, "A", slice_id)
            d_array = self._read_array(bundle, "D", slice_id)
            if self.topology == "batch":
                if slice_id >= n:
                    if np.any(a_array != bundle.metadata["input_tail_value"]):
                        raise ValueError("MaxPool inactive input slice is corrupted")
                    if np.any(d_array != bundle.metadata["output_tail_value"]):
                        raise ValueError("MaxPool inactive output slice is corrupted")
                if channels < channel_tile:
                    if np.any(
                        a_array[..., channels:] != bundle.metadata["input_tail_value"]
                    ):
                        raise ValueError("MaxPool input channel tail is corrupted")
                    if np.any(
                        d_array[..., channels:] != bundle.metadata["output_tail_value"]
                    ):
                        raise ValueError("MaxPool output channel tail is corrupted")
            else:
                valid_c = max(0, min(channel_tile, channels - slice_id * channel_tile))
                if valid_c < channel_tile:
                    if np.any(
                        a_array[..., valid_c:] != bundle.metadata["input_tail_value"]
                    ):
                        raise ValueError("MaxPool input channel tail is corrupted")
                    if np.any(
                        d_array[..., valid_c:] != bundle.metadata["output_tail_value"]
                    ):
                        raise ValueError("MaxPool output channel tail is corrupted")
        self.inverse_port(bundle, "A")
        self.inverse_port(bundle, "D")
        return {
            "slice_count": 16,
            "region_count": 32,
            "per_slice_used_bytes": int(bundle.metadata["per_slice_used_bytes"]),
        }

    def prove_conv_input_alias(
        self, producer_bundle, pool_bundle: MaxPoolPhysicalBundle
    ) -> dict[str, Any]:
        expected_contract = (
            "w4_conv_batch16_candidate_v1"
            if self.topology == "batch"
            else "w4_conv_ring16_candidate_v1"
        )
        if producer_bundle.metadata["contract"] != expected_contract:
            raise ValueError("Conv producer topology does not match MaxPool topology")
        if tuple(producer_bundle.metadata["output_shape"]) != tuple(
            pool_bundle.metadata["input_shape"]
        ):
            raise ValueError("Conv D logical shape differs from MaxPool A")
        shared_tensor_id = pool_bundle.metadata["ports"]["A"]["tensor_id"]
        if producer_bundle.region("D", 0).tensor_id != shared_tensor_id:
            raise ValueError("Conv D and MaxPool A tensor IDs differ")
        for slice_id in range(16):
            producer = producer_bundle.region("D", slice_id)
            consumer = pool_bundle.region("A", slice_id)
            if producer.base_address != consumer.base_address:
                raise ValueError("Conv D and MaxPool A base addresses differ")
            if producer.payload_bytes != consumer.payload_bytes:
                raise ValueError("Conv D and MaxPool A payload sizes differ")
            if tuple(producer.physical_shape) != tuple(consumer.physical_shape):
                raise ValueError("Conv D and MaxPool A physical shapes differ")
            if producer_bundle.read("D", slice_id) != pool_bundle.read("A", slice_id):
                raise ValueError("Conv D and MaxPool A physical bytes differ")
        return {
            "compatible": True,
            "producer_contract": expected_contract,
            "consumer_contract": self.contract,
            "slice_count": 16,
            "shared_tensor_id": shared_tensor_id,
            "base_addresses": [
                pool_bundle.region("A", slice_id).base_address
                for slice_id in range(16)
            ],
            "all_physical_bytes_equal": True,
        }


class MaxPoolBatch16PhysicalLayout(MaxPool16PhysicalLayout):
    def __init__(self, geometry: DramGeometry | None = None, *, alignment: int = 16):
        super().__init__("batch", geometry, alignment=alignment, channel_tile=8)


class MaxPoolChannel16PhysicalLayout(MaxPool16PhysicalLayout):
    def __init__(self, geometry: DramGeometry | None = None, *, alignment: int = 16):
        super().__init__("channel", geometry, alignment=alignment, channel_tile=1)
