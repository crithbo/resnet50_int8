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
class GlobalAveragePoolRegion:
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
class GlobalAveragePoolPhysicalBundle:
    geometry: DramGeometry
    alignment: int
    regions: tuple[GlobalAveragePoolRegion, ...]
    payloads: dict[tuple[str, int], bytes]
    metadata: dict[str, Any]

    def region(self, port: str, slice_id: int) -> GlobalAveragePoolRegion:
        matches = [
            item
            for item in self.regions
            if item.port == port and item.slice_id == slice_id
        ]
        if len(matches) != 1:
            raise KeyError(
                f"expected one GlobalAveragePool {port} region on slice {slice_id}"
            )
        return matches[0]

    def read(self, port: str, slice_id: int) -> bytes:
        return self.payloads[(port, slice_id)]

    def layout_records(self) -> tuple[LayoutRecord, ...]:
        records: list[LayoutRecord] = []
        for port in self.metadata["port_order"]:
            spec = self.metadata["ports"][port]
            policy = {
                "batch": "one_batch_item_per_slice",
                "channel": "contiguous_channel_partition_across_slices",
                "replicated": "replicated_on_every_slice",
            }[spec["placement"]]
            records.append(
                LayoutRecord(
                    layout_id=(
                        f"layout-globalavgpool-{self.metadata['topology']}-"
                        f"{port.lower()}-{spec['tensor_id']}"
                    ),
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
                        "channel_tile": self.metadata["channel_tile"],
                    },
                    packing={
                        "physical_axis_order": spec["physical_axis_order"],
                        "byte_order": "little",
                        "alignment_bytes": self.alignment,
                        "tail_value": spec["tail_value"],
                        "spatial_reduction": "sum_centered_then_requantize",
                        "spatial_size": self.metadata["spatial_size"],
                        "input_alias_requested": port == "A"
                        and self.metadata["input_alias_requested"],
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


class GlobalAveragePool16PhysicalLayout:
    status = "candidate"

    def __init__(
        self,
        topology: Topology,
        geometry: DramGeometry | None = None,
        *,
        alignment: int = 16,
        channel_alignment: int = 8,
    ):
        if topology not in {"batch", "channel"}:
            raise ValueError("GlobalAveragePool topology must be batch or channel")
        self.topology = topology
        self.contract = f"w4_globalavgpool_{topology}16_candidate_v1"
        self.geometry = geometry or DramGeometry()
        if self.geometry.slice_count != 16:
            raise ValueError("GlobalAveragePool candidate requires exactly 16 slices")
        if alignment <= 0 or alignment % self.geometry.subword_bytes:
            raise ValueError("alignment must be a positive multiple of subword_bytes")
        if channel_alignment <= 0:
            raise ValueError("channel_alignment must be positive")
        self.alignment = alignment
        self.channel_alignment = channel_alignment

    def plan(
        self,
        *,
        input_shape: tuple[int, int, int, int],
        channels_last: int = 0,
        input_offset: int = 0,
    ) -> dict[str, Any]:
        if int(channels_last) != 0:
            raise ValueError("current GlobalAveragePool candidate requires channels_last=0")
        if len(input_shape) != 4:
            raise ValueError("GlobalAveragePool input must be rank-4 NCHW")
        n, channels, height, width = tuple(int(value) for value in input_shape)
        if any(value <= 0 for value in (n, channels, height, width)):
            raise ValueError("GlobalAveragePool dimensions must be positive")
        if n > 16:
            raise ValueError("GlobalAveragePool candidate supports batch <= 16")
        if input_offset < 0 or input_offset % self.alignment:
            raise ValueError("GlobalAveragePool input_offset must be aligned")

        output_shape = (n, channels, 1, 1)
        if self.topology == "batch":
            channel_tile = _align(channels, self.channel_alignment)
            physical_shapes = {
                "A": (height, width, channel_tile),
                "P": (1, 1, channel_tile),
                "D": (1, 1, channel_tile),
            }
        else:
            channel_tile = math.ceil(channels / 16)
            physical_shapes = {
                "A": (n, height, width, channel_tile),
                "P": (n, 1, 1, channel_tile),
                "D": (n, 1, 1, channel_tile),
            }
        raw_sizes = {
            "A": int(np.prod(physical_shapes["A"], dtype=np.int64)),
            "x_scale": 4,
            "x_zero_point": 1,
            "y_scale": 4,
            "y_zero_point": 1,
            "multiplier": 4,
            "P": int(np.prod(physical_shapes["P"], dtype=np.int64)) * 4,
            "D": int(np.prod(physical_shapes["D"], dtype=np.int64)),
        }
        offsets = {"A": input_offset}
        cursor = input_offset + _align(raw_sizes["A"], self.alignment)
        for port in (
            "x_scale",
            "x_zero_point",
            "y_scale",
            "y_zero_point",
            "multiplier",
            "P",
            "D",
        ):
            cursor = _align(cursor, self.alignment)
            offsets[port] = cursor
            cursor += _align(raw_sizes[port], self.alignment)
        if cursor > self.geometry.bytes_per_slice:
            raise ValueError("GlobalAveragePool regions exceed one slice capacity")
        return {
            "input_shape": (n, channels, height, width),
            "output_shape": output_shape,
            "channels_last": 0,
            "spatial_size": height * width,
            "channel_tile": channel_tile,
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
            raise ValueError("input_base_addresses must contain 16 addresses")
        offsets: list[int] = []
        for slice_id, address in enumerate(addresses):
            start = self.geometry.slice_base(slice_id)
            end = start + self.geometry.bytes_per_slice
            if not start <= int(address) < end:
                raise ValueError("GlobalAveragePool aliased input base is outside its slice")
            offsets.append(int(address) - start)
        if len(set(offsets)) != 1:
            raise ValueError("GlobalAveragePool aliased bases need one common slice offset")
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
        x_scale: np.ndarray,
        x_zero_point: np.ndarray,
        y_scale: np.ndarray,
        y_zero_point: np.ndarray,
        accumulator: np.ndarray,
        output: np.ndarray,
        channels_last: int = 0,
        tensor_ids: dict[str, str] | None = None,
        input_base_addresses: tuple[int, ...] | None = None,
    ) -> GlobalAveragePoolPhysicalBundle:
        activation = np.asarray(activation)
        accumulator = np.asarray(accumulator)
        output = np.asarray(output)
        if activation.dtype != np.uint8 or activation.ndim != 4:
            raise TypeError("GlobalAveragePool activation must be rank-4 uint8 NCHW")
        input_offset = self._alias_offset(input_base_addresses)
        plan = self.plan(
            input_shape=tuple(activation.shape),
            channels_last=channels_last,
            input_offset=input_offset,
        )
        if accumulator.dtype != np.int32 or tuple(accumulator.shape) != plan["output_shape"]:
            raise TypeError("GlobalAveragePool accumulator must be int32 NCHW [N,C,1,1]")
        if output.dtype != np.uint8 or tuple(output.shape) != plan["output_shape"]:
            raise TypeError("GlobalAveragePool output must be uint8 NCHW [N,C,1,1]")
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
        if float(qparams["x_scale"][0]) <= 0 or float(qparams["y_scale"][0]) <= 0:
            raise ValueError("GlobalAveragePool scales must be positive")
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
            "P": "globalavgpool_sum",
            "D": "globalavgpool_output",
            **(tensor_ids or {}),
        }
        if len(set(ids.values())) != len(ids):
            raise ValueError("GlobalAveragePool port tensor IDs must be unique")

        n, channels, _, _ = plan["input_shape"]
        tile = int(plan["channel_tile"])
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
                    a[..., :channels] = np.transpose(activation[slice_id], (1, 2, 0))
                    p[..., :channels] = np.transpose(
                        accumulator[slice_id], (1, 2, 0)
                    )
                    d[..., :channels] = np.transpose(output[slice_id], (1, 2, 0))
            else:
                start = slice_id * tile
                valid = max(0, min(tile, channels - start))
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
                if valid:
                    a[..., :valid] = np.transpose(
                        activation[:, start : start + valid], (0, 2, 3, 1)
                    )
                    p[..., :valid] = np.transpose(
                        accumulator[:, start : start + valid], (0, 2, 3, 1)
                    )
                    d[..., :valid] = np.transpose(
                        output[:, start : start + valid], (0, 2, 3, 1)
                    )
            arrays.append(
                {
                    "A": a,
                    **qparams,
                    "multiplier": multiplier,
                    "P": p,
                    "D": d,
                }
            )

        port_order = tuple(plan["raw_sizes"].keys())
        placements = {
            "A": self.topology,
            "P": self.topology,
            "D": self.topology,
            **{
                port: "replicated"
                for port in (
                    "x_scale",
                    "x_zero_point",
                    "y_scale",
                    "y_zero_point",
                    "multiplier",
                )
            },
        }
        logical_shapes = {
            "A": activation.shape,
            "P": accumulator.shape,
            "D": output.shape,
            **{
                port: (1,)
                for port in (
                    "x_scale",
                    "x_zero_point",
                    "y_scale",
                    "y_zero_point",
                    "multiplier",
                )
            },
        }
        dtypes = {
            "A": "uint8",
            "P": "int32",
            "D": "uint8",
            "x_scale": "float32",
            "x_zero_point": "uint8",
            "y_scale": "float32",
            "y_zero_point": "uint8",
            "multiplier": "float32",
        }
        tails: dict[str, Any] = {
            "A": int(qparams["x_zero_point"][0]),
            "P": 0,
            "D": int(qparams["y_zero_point"][0]),
            "x_scale": None,
            "x_zero_point": None,
            "y_scale": None,
            "y_zero_point": None,
            "multiplier": None,
        }
        physical_axis_orders = {
            "A": "HWC_padded" if self.topology == "batch" else "NHWC_local",
            "P": "11C_padded" if self.topology == "batch" else "N11C_local",
            "D": "11C_padded" if self.topology == "batch" else "N11C_local",
            "x_scale": "scalar",
            "x_zero_point": "scalar",
            "y_scale": "scalar",
            "y_zero_point": "scalar",
            "multiplier": "scalar",
        }
        regions: list[GlobalAveragePoolRegion] = []
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
                    else slice_id * tile < channels
                )
                regions.append(
                    GlobalAveragePoolRegion(
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
                "physical_axis_order": physical_axis_orders[port],
                "tail_value": tails[port],
            }
            for port in port_order
        }
        bundle = GlobalAveragePoolPhysicalBundle(
            geometry=self.geometry,
            alignment=self.alignment,
            regions=tuple(regions),
            payloads=payloads,
            metadata={
                "contract": self.contract,
                "status": self.status,
                "topology": self.topology,
                "port_order": port_order,
                "ports": ports,
                "tails": tails,
                "input_alias_requested": input_base_addresses is not None,
                "multiplier": float(multiplier[0]),
                **plan,
            },
        )
        self.validate(bundle)
        return bundle

    def _read(
        self, bundle: GlobalAveragePoolPhysicalBundle, port: str, slice_id: int
    ) -> np.ndarray:
        region = bundle.region(port, slice_id)
        return np.frombuffer(
            bundle.read(port, slice_id)[: region.payload_bytes],
            dtype=np.dtype(bundle.metadata["ports"][port]["dtype"]),
        ).reshape(region.physical_shape)

    def inverse_port(
        self, bundle: GlobalAveragePoolPhysicalBundle, port: str
    ) -> np.ndarray:
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if spec["placement"] == "replicated":
            arrays = [self._read(bundle, port, slice_id) for slice_id in range(16)]
            if any(not np.array_equal(arrays[0], item) for item in arrays[1:]):
                raise ValueError(f"replicated GlobalAveragePool port {port} differs")
            return arrays[0].reshape(shape).copy()
        n, channels, _, _ = shape
        tile = int(bundle.metadata["channel_tile"])
        dtype = np.dtype(spec["dtype"])
        logical = np.empty(shape, dtype=dtype)
        if self.topology == "batch":
            for slice_id in range(n):
                logical[slice_id] = np.transpose(
                    self._read(bundle, port, slice_id)[..., :channels], (2, 0, 1)
                )
        else:
            for slice_id in range(16):
                start = slice_id * tile
                valid = max(0, min(tile, channels - start))
                if valid:
                    logical[:, start : start + valid] = np.transpose(
                        self._read(bundle, port, slice_id)[..., :valid],
                        (0, 3, 1, 2),
                    )
        return logical

    def inverse(
        self, bundle: GlobalAveragePoolPhysicalBundle
    ) -> dict[str, np.ndarray]:
        return {
            bundle.metadata["ports"][port]["tensor_id"]: self.inverse_port(
                bundle, port
            )
            for port in bundle.metadata["port_order"]
        }

    def explain_coordinate(
        self,
        bundle: GlobalAveragePoolPhysicalBundle,
        tensor_id: str,
        coordinate: tuple[int, ...],
    ) -> dict[str, Any]:
        ports = [
            port
            for port in bundle.metadata["port_order"]
            if bundle.metadata["ports"][port]["tensor_id"] == tensor_id
        ]
        if len(ports) != 1:
            raise KeyError(f"expected one GlobalAveragePool port for {tensor_id}")
        port = ports[0]
        spec = bundle.metadata["ports"][port]
        shape = tuple(spec["logical_shape"])
        if len(coordinate) != len(shape) or any(
            index < 0 or index >= dimension
            for index, dimension in zip(coordinate, shape, strict=True)
        ):
            raise IndexError("GlobalAveragePool coordinate is out of range")
        tile = int(bundle.metadata["channel_tile"])
        if spec["placement"] == "replicated":
            slice_ids = tuple(range(16))
            physical_coordinate = coordinate
        elif self.topology == "batch":
            slice_ids = (coordinate[0],)
            physical_coordinate = (coordinate[2], coordinate[3], coordinate[1])
        else:
            slice_ids = (coordinate[1] // tile,)
            physical_coordinate = (
                coordinate[0],
                coordinate[2],
                coordinate[3],
                coordinate[1] % tile,
            )
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

    def explain_reduction(
        self,
        bundle: GlobalAveragePoolPhysicalBundle,
        *,
        batch: int,
        channel: int,
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["input_shape"]
        if not 0 <= batch < n or not 0 <= channel < channels:
            raise IndexError("GlobalAveragePool reduction coordinate is out of range")
        tensor_id = bundle.metadata["ports"]["A"]["tensor_id"]
        elements = []
        for h in range(height):
            for w in range(width):
                explanation = self.explain_coordinate(
                    bundle, tensor_id, (batch, channel, h, w)
                )
                elements.append(
                    {
                        "logical_coordinate": (batch, channel, h, w),
                        "slice_id": explanation["slice_ids"][0],
                        "address": explanation["addresses"][0],
                    }
                )
        p_id = bundle.metadata["ports"]["P"]["tensor_id"]
        p = self.explain_coordinate(bundle, p_id, (batch, channel, 0, 0))
        return {
            "batch": batch,
            "channel": channel,
            "spatial_size": height * width,
            "input_zero_point": bundle.metadata["tails"]["A"],
            "formula": "sum(A-x_zero_point) over H,W",
            "input_elements": tuple(elements),
            "sum_slice_id": p["slice_ids"][0],
            "sum_addresses": p["addresses"],
        }

    def prove_input_compatibility(
        self,
        producer_bundle,
        pool_bundle: GlobalAveragePoolPhysicalBundle,
        *,
        require_same_base: bool = False,
    ) -> dict[str, Any]:
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
        producer_contract = producer_bundle.metadata["contract"]
        if producer_contract not in expected_contracts:
            raise ValueError("producer topology does not match GlobalAveragePool topology")
        producer_spec = producer_bundle.metadata["ports"]["D"]
        consumer_spec = pool_bundle.metadata["ports"]["A"]
        if tuple(producer_spec["logical_shape"]) != tuple(
            consumer_spec["logical_shape"]
        ):
            raise ValueError("producer D logical shape differs from GlobalAveragePool A")
        if producer_spec.get("logical_dtype", producer_spec.get("dtype")) != consumer_spec[
            "dtype"
        ]:
            raise ValueError("producer D dtype differs from GlobalAveragePool A")
        tensor_id = consumer_spec["tensor_id"]
        if producer_bundle.region("D", 0).tensor_id != tensor_id:
            raise ValueError("producer D and GlobalAveragePool A tensor IDs differ")
        same_bases = True
        for slice_id in range(16):
            producer = producer_bundle.region("D", slice_id)
            consumer = pool_bundle.region("A", slice_id)
            if producer.payload_bytes != consumer.payload_bytes:
                raise ValueError("producer D and GlobalAveragePool A payload sizes differ")
            if tuple(producer.physical_shape) != tuple(consumer.physical_shape):
                raise ValueError("producer D and GlobalAveragePool A physical shapes differ")
            if producer_bundle.read("D", slice_id) != pool_bundle.read("A", slice_id):
                raise ValueError("producer D and GlobalAveragePool A physical bytes differ")
            same_bases &= producer.base_address == consumer.base_address
        if require_same_base and not same_bases:
            raise ValueError("producer D and GlobalAveragePool A base addresses differ")
        return {
            "compatible": True,
            "producer_contract": producer_contract,
            "consumer_contract": self.contract,
            "shared_tensor_id": tensor_id,
            "slice_count": 16,
            "all_physical_bytes_equal": True,
            "all_base_addresses_equal": same_bases,
            "exact_alias": same_bases,
            "memory_plan_rebase_required": not same_bases,
        }

    def prove_flatten_output_alias(
        self,
        bundle: GlobalAveragePoolPhysicalBundle,
        *,
        output_shape: tuple[int, int],
        axis: int = 1,
    ) -> dict[str, Any]:
        n, channels, height, width = bundle.metadata["output_shape"]
        if axis != 1 or (height, width) != (1, 1):
            raise ValueError("GlobalAveragePool zero-copy Flatten requires axis=1 and H=W=1")
        if tuple(output_shape) != (n, channels):
            raise ValueError("Flatten output shape differs from [N,C]")
        tile = int(bundle.metadata["channel_tile"])
        physical_after = (
            (tile,) if self.topology == "batch" else (n, tile)
        )
        for slice_id in range(16):
            region = bundle.region("D", slice_id)
            if int(np.prod(region.physical_shape)) != int(np.prod(physical_after)):
                raise ValueError("Flatten would change per-slice physical element count")
        return {
            "compatible": True,
            "zero_copy": True,
            "source_tensor_id": bundle.metadata["ports"]["D"]["tensor_id"],
            "input_shape": list(bundle.metadata["output_shape"]),
            "output_shape": list(output_shape),
            "physical_axis_before": bundle.metadata["ports"]["D"][
                "physical_axis_order"
            ],
            "physical_shape_after": list(physical_after),
            "base_addresses": [
                bundle.region("D", slice_id).base_address for slice_id in range(16)
            ],
            "byte_order_unchanged": True,
        }

    def validate(self, bundle: GlobalAveragePoolPhysicalBundle) -> dict[str, int]:
        if (
            bundle.metadata["contract"] != self.contract
            or bundle.metadata["status"] != self.status
        ):
            raise ValueError("GlobalAveragePool bundle contract mismatch")
        if bundle.geometry != self.geometry or bundle.alignment != self.alignment:
            raise ValueError("GlobalAveragePool bundle geometry/alignment mismatch")
        ports = tuple(bundle.metadata["port_order"])
        if len(bundle.regions) != len(ports) * 16:
            raise ValueError("GlobalAveragePool region count mismatch")
        n, channels, _, _ = bundle.metadata["input_shape"]
        tile = int(bundle.metadata["channel_tile"])
        for slice_id in range(16):
            slice_start = bundle.geometry.slice_base(slice_id)
            slice_end = slice_start + bundle.geometry.bytes_per_slice
            ranges = []
            for port in ports:
                region = bundle.region(port, slice_id)
                payload = bundle.read(port, slice_id)
                if region.base_address % self.alignment:
                    raise ValueError("GlobalAveragePool region is not aligned")
                if not (
                    slice_start <= region.base_address
                    and region.base_address + region.size_bytes <= slice_end
                ):
                    raise ValueError("GlobalAveragePool region crosses a slice boundary")
                if len(payload) != region.size_bytes:
                    raise ValueError("GlobalAveragePool payload length differs from region")
                if any(payload[region.payload_bytes :]):
                    raise ValueError("GlobalAveragePool alignment padding is corrupted")
                ranges.append(
                    (region.base_address, region.base_address + region.size_bytes)
                )
                placement = bundle.metadata["ports"][port]["placement"]
                expected_active = (
                    True
                    if placement == "replicated"
                    else slice_id < n
                    if placement == "batch"
                    else slice_id * tile < channels
                )
                if region.active != expected_active:
                    raise ValueError("GlobalAveragePool activity mask is inconsistent")
            ranges.sort()
            if any(
                ranges[index][1] > ranges[index + 1][0]
                for index in range(len(ranges) - 1)
            ):
                raise ValueError("GlobalAveragePool regions overlap")

            for port in ("A", "P", "D"):
                array = self._read(bundle, port, slice_id)
                tail = bundle.metadata["tails"][port]
                if self.topology == "batch":
                    if slice_id >= n and np.any(array != tail):
                        raise ValueError(
                            f"GlobalAveragePool inactive {port} slice is corrupted"
                        )
                    if channels < tile and np.any(array[..., channels:] != tail):
                        raise ValueError(
                            f"GlobalAveragePool {port} channel tail is corrupted"
                        )
                else:
                    valid = max(0, min(tile, channels - slice_id * tile))
                    if valid < tile and np.any(array[..., valid:] != tail):
                        raise ValueError(
                            f"GlobalAveragePool {port} channel tail is corrupted"
                        )

        for port in ports:
            self.inverse_port(bundle, port)
        expected_multiplier = np.float32(
            np.float32(self.inverse_port(bundle, "x_scale")[0])
            / (
                np.float32(self.inverse_port(bundle, "y_scale")[0])
                * np.float32(bundle.metadata["spatial_size"])
            )
        )
        if self.inverse_port(bundle, "multiplier")[0] != expected_multiplier:
            raise ValueError("GlobalAveragePool multiplier is inconsistent")
        return {
            "slice_count": 16,
            "port_count": len(ports),
            "region_count": len(bundle.regions),
            "spatial_size": bundle.metadata["spatial_size"],
            "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        }


class GlobalAveragePoolBatch16PhysicalLayout(GlobalAveragePool16PhysicalLayout):
    def __init__(
        self, geometry: DramGeometry | None = None, *, alignment: int = 16
    ):
        super().__init__("batch", geometry, alignment=alignment, channel_alignment=8)


class GlobalAveragePoolChannel16PhysicalLayout(GlobalAveragePool16PhysicalLayout):
    def __init__(
        self, geometry: DramGeometry | None = None, *, alignment: int = 16
    ):
        super().__init__("channel", geometry, alignment=alignment, channel_alignment=1)
