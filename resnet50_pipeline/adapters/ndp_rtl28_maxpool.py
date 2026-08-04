"""Config-bound NDP functional execution for the real ResNet-50 MaxPool."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from ..conv_layout import ConvPhysicalBundle, PhysicalRegion
from ..errors import PipelineError
from ..maxpool_instance import MaxPoolInstance
from ..memory import DramGeometry
from ..pool28_layout import MaxPoolPhysicalLayout, PoolPhysicalBundle
from .ndp_functional import NdpFunctionalAdapter, NdpPhysicalProbeResult
from .ndp_rtl28_functional import Rtl28ShadowAddressMap


class _PoolShadowImage:
    """Small region-backed image implementing the probe adapter's byte API."""

    def __init__(self, regions: list[tuple[int, bytearray]]) -> None:
        self._regions = regions

    def _span(self, address: int, size: int) -> tuple[bytearray, int]:
        for base, payload in self._regions:
            offset = address - base
            if 0 <= offset and offset + size <= len(payload):
                return payload, offset
        raise ValueError(f"unmapped Pool shadow span: address={address}, size={size}")

    def read(self, address: int, size: int) -> bytes:
        payload, offset = self._span(address, size)
        return bytes(payload[offset : offset + size])

    def overwrite(self, address: int, payload: bytes) -> None:
        region, offset = self._span(address, len(payload))
        region[offset : offset + len(payload)] = payload


@dataclass(frozen=True)
class NdpRtl28MaxPoolResult:
    output: np.ndarray
    inverse_output: np.ndarray
    physical_probe: NdpPhysicalProbeResult
    address_map: Rtl28ShadowAddressMap
    updated_bundle: PoolPhysicalBundle
    config_sha256: tuple[str, ...]
    status: str = "config_bound_functional_passed"
    target_simulator_validated: bool = False
    g6_validated: bool = False


class NdpRtl28MaxPoolAdapter:
    """Execute all 28 physical owner tiles through configured GeneralPEA max."""

    status = "config_bound_functional_component"
    target_simulator_validated = False
    g6_validated = False

    def __init__(
        self,
        repository: Path,
        *,
        python_executable: Path | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        self._ndp = NdpFunctionalAdapter(
            repository,
            python_executable=python_executable,
            timeout_seconds=timeout_seconds,
            bridge_module="tools.maxpool_physical_image_probe",
        )

    @staticmethod
    def _require_layout(
        layout: MaxPoolPhysicalLayout, bundle: PoolPhysicalBundle
    ) -> None:
        if not isinstance(layout, MaxPoolPhysicalLayout):
            raise TypeError("layout must be MaxPoolPhysicalLayout")
        if bundle.operator != "MaxPool" or bundle.profile_id != layout.profile_id:
            raise ValueError("adapter requires a matching RTL28 MaxPool bundle")
        if bundle.status != "candidate" or bundle.target_family != "rtl28":
            raise ValueError("adapter accepts only candidate RTL28 MaxPool bundles")
        if bundle.metadata.get("spatial_padding_value") != 0:
            raise ValueError("the frozen ResNet MaxPool target instance requires zero padding")

    @staticmethod
    def _shadow_bundle(
        bundle: PoolPhysicalBundle,
    ) -> tuple[ConvPhysicalBundle, Rtl28ShadowAddressMap]:
        target = bundle.geometry
        required = int(bundle.metadata["per_slice_used_bytes"])
        rows = max(1, math.ceil(required / target.bytes_per_row))
        shadow = DramGeometry(
            slice_count=target.slice_count,
            bank_count=1,
            row_count=rows,
            col_count=target.col_count,
            subword_bytes=target.subword_bytes,
        )
        address_map = Rtl28ShadowAddressMap(target, shadow)
        regions: list[PhysicalRegion] = []
        image_regions: list[tuple[int, bytearray]] = []
        for source in bundle.regions:
            name = {"A": "activation", "D": "output"}.get(source.port)
            if name is None:
                raise ValueError(f"unexpected MaxPool physical port: {source.port}")
            shadow_base = address_map.to_shadow(source.base_address)
            payload = bytearray(bundle.read(source.port, source.slice_id))
            image_regions.append((shadow_base, payload))
            regions.append(
                PhysicalRegion(
                    name=name,
                    tensor_id=source.tensor_id,
                    slice_id=source.slice_id,
                    base_address=shadow_base,
                    payload_bytes=source.payload_bytes,
                    size_bytes=source.size_bytes,
                    dtype=bundle.placement(source.tensor_id).dtype,
                    physical_shape=source.physical_shape,
                )
            )
        probe_bundle = ConvPhysicalBundle(
            geometry=shadow,
            image=_PoolShadowImage(image_regions),  # type: ignore[arg-type]
            regions=tuple(regions),
            metadata={
                "contract": "rtl28_maxpool_ndp_shadow_v1",
                "status": "config_bound_functional_component",
                "profile_id": bundle.profile_id,
                "slice_count": target.slice_count,
            },
        )
        return probe_bundle, address_map

    @staticmethod
    def _job(
        bundle: PoolPhysicalBundle,
        address_map: Rtl28ShadowAddressMap,
        instance: MaxPoolInstance,
    ) -> dict[str, Any]:
        logical = instance.manifest["logical"]
        physical = instance.manifest["physical"]
        slices = []
        for slice_id in range(bundle.geometry.slice_count):
            a_region = bundle.region("A", slice_id)
            d_region = bundle.region("D", slice_id)
            if (
                list(a_region.physical_shape) != physical["input_physical_shape"]
                or list(d_region.physical_shape) != physical["output_physical_shape"]
            ):
                raise PipelineError("MaxPool physical bundle shape differs from the instance")
            slice_base = address_map.shadow_geometry.slice_base(slice_id)
            slices.append(
                {
                    "slice_id": slice_id,
                    "slice_base": slice_base,
                    "activation_base": address_map.to_shadow(a_region.base_address),
                    "output_base": address_map.to_shadow(d_region.base_address),
                    "input_physical_shape": list(a_region.physical_shape),
                    "output_physical_shape": list(d_region.physical_shape),
                    "sample_count": a_region.sample_count,
                }
            )
        return {
            "name": instance.manifest["identity"]["hwop_id"],
            "local_channels": physical["local_channels"],
            "input_shape": logical["input_shape"][2:],
            "output_shape": logical["output_shape"][2:],
            "kernel_shape": logical["kernel_shape"],
            "strides": logical["strides"],
            "pads": logical["pads"],
            "dilations": logical["dilations"],
            "padding_value": logical["spatial_padding_value"],
            "slices": slices,
            "waves": [
                {
                    "wave_index": item["wave_index"],
                    "input_offset": item["input_offset"],
                    "output_offset": item["output_offset"],
                    "active_slices": item["active_slices"],
                }
                for item in instance.manifest["waves"]
            ],
        }

    def run(
        self,
        layout: MaxPoolPhysicalLayout,
        bundle: PoolPhysicalBundle,
        *,
        instance: MaxPoolInstance,
    ) -> NdpRtl28MaxPoolResult:
        self._require_layout(layout, bundle)
        probe_bundle, address_map = self._shadow_bundle(bundle)
        job = self._job(bundle, address_map, instance)
        physical_probe = self._ndp.probe_physical_bundle(
            probe_bundle,
            maxpool_config_binding=instance.functional_binding(),
            uint8_maxpool_jobs=(job,),
        )
        if len(physical_probe.uint8_maxpool_jobs) != 1:
            raise PipelineError("NDP MaxPool result count differs")
        outputs = physical_probe.uint8_maxpool_jobs[0]["outputs"]
        payloads = dict(bundle.payloads)
        for output in outputs:
            slice_id = int(output["slice_id"])
            region = bundle.region("D", slice_id)
            raw = bytes.fromhex(output["data_hex"])
            if len(raw) != region.payload_bytes:
                raise PipelineError("NDP MaxPool returned the wrong physical payload size")
            if hashlib.sha256(raw).hexdigest() != output["sha256"]:
                raise PipelineError("NDP MaxPool physical payload hash differs")
            payloads[("D", slice_id)] = raw + bytes(region.size_bytes - len(raw))
        updated = replace(bundle, payloads=payloads)
        output_tensor_id = instance.manifest["identity"]["output_tensor_id"]
        inverse = layout.inverse_port(updated, output_tensor_id)
        return NdpRtl28MaxPoolResult(
            output=inverse.copy(),
            inverse_output=inverse,
            physical_probe=physical_probe,
            address_map=address_map,
            updated_bundle=updated,
            config_sha256=tuple(
                item["config_sha256"] for item in instance.manifest["waves"]
            ),
        )
