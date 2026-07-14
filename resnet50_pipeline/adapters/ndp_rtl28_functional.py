"""Candidate-only RTL28 Conv bridge to the W2 NDP functional probe.

This module intentionally does not define a simulator/configuration contract.  It
adapts an existing :class:`QLinearConvPhysicalLayout` bundle to the already
validated NDP physical-image probe and keeps the target RTL28 owner formulas
visible.  The target DRAM geometry is too large for the probe's bounded in-memory
DRAM, so only the per-slice address prefix is compacted; slice identifiers and
within-slice offsets remain unchanged and are reversibly mapped below.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from ..conv28_layout import Conv28PhysicalBundle, QLinearConvPhysicalLayout
from ..conv_layout import ConvPhysicalBundle, PhysicalRegion
from ..errors import PipelineError
from ..memory import ByteProvenance, DramGeometry, SparsePhysicalImage
from ..profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    sample_to_group,
)
from ..topology28 import Direction, TOPOLOGY28
from .ndp_functional import (
    NdpFunctionalAdapter,
    NdpInt8DotProbe,
    NdpPhysicalProbeResult,
)


_PORT_TO_PROBE_REGION = {
    "A": "activation",
    "B": "weight",
    "bias": "bias",
    "w_scale": "w_scale",
    "w_zero_point": "w_zero_point",
    "x_scale": "x_scale",
    "x_zero_point": "x_zero_point",
    "y_scale": "y_scale",
    "y_zero_point": "y_zero_point",
    "P": "accumulator",
    "D": "output",
}


@dataclass(frozen=True)
class Rtl28ShadowAddressMap:
    """Reversible target-to-probe address compaction.

    The mapping changes only ``bytes_per_slice``.  Therefore the physical slice
    owner and byte offset within that owner are invariant.
    """

    target_geometry: DramGeometry
    shadow_geometry: DramGeometry

    def to_shadow(self, target_address: int) -> int:
        if not 0 <= target_address < self.target_geometry.total_bytes:
            raise ValueError("target address is outside RTL28 DRAM")
        owner, offset = divmod(target_address, self.target_geometry.bytes_per_slice)
        if offset >= self.shadow_geometry.bytes_per_slice:
            raise ValueError("target address is outside the compact probe prefix")
        return self.shadow_geometry.slice_base(owner) + offset

    def to_target(self, shadow_address: int) -> int:
        if not 0 <= shadow_address < self.shadow_geometry.total_bytes:
            raise ValueError("shadow address is outside compact probe DRAM")
        owner, offset = divmod(shadow_address, self.shadow_geometry.bytes_per_slice)
        return self.target_geometry.slice_base(owner) + offset


@dataclass(frozen=True)
class Rtl28ConvProbePlan:
    """One auditable output probe and its real RTL ring ownership."""

    probe: NdpInt8DotProbe
    profile_id: str
    ring_kind: str
    group_id: int | None
    destination_owner: int
    source_owners: tuple[int, ...]
    channel_ranges: tuple[tuple[int, int], ...]
    target_output_address: int


@dataclass(frozen=True)
class NdpRtl28ConvResult:
    """Candidate functional result; this is not a target-simulator result."""

    accumulator: np.ndarray
    output: np.ndarray
    inverse_output: np.ndarray
    probe_plans: tuple[Rtl28ConvProbePlan, ...]
    physical_probe: NdpPhysicalProbeResult
    address_map: Rtl28ShadowAddressMap
    updated_bundle: Conv28PhysicalBundle


@dataclass(frozen=True)
class NdpRtl28CoordinateResult:
    """Executed coordinate subset from the operator-confirmed Conv simulator."""

    coordinates: tuple[tuple[int, int, int, int], ...]
    accumulators: tuple[int, ...]
    outputs: tuple[int, ...]
    probe_plans: tuple[Rtl28ConvProbePlan, ...]
    physical_probe: NdpPhysicalProbeResult
    address_map: Rtl28ShadowAddressMap
    updated_bundle: Conv28PhysicalBundle


class NdpRtl28FunctionalAdapter:
    """Run RTL28 Conv candidate bytes through the existing NDP PE probe."""

    status = "operator_confirmed_conv_simulator_component"
    target_simulator_validated = False
    g6_validated = False

    def __init__(
        self,
        repository: Path,
        *,
        python_executable: Path | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self._ndp = NdpFunctionalAdapter(
            repository,
            python_executable=python_executable,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _require_layout(
        layout: QLinearConvPhysicalLayout,
        bundle: Conv28PhysicalBundle,
    ) -> None:
        if not isinstance(layout, QLinearConvPhysicalLayout):
            raise TypeError("layout must be QLinearConvPhysicalLayout")
        if layout.profile_id != bundle.plan.profile_id:
            raise ValueError("layout profile does not match the RTL28 bundle")
        if bundle.plan.status != "candidate" or bundle.plan.target_family != "rtl28":
            raise ValueError("adapter accepts only candidate RTL28 Conv bundles")

    @staticmethod
    def _shadow_map(bundle: Conv28PhysicalBundle) -> Rtl28ShadowAddressMap:
        target = bundle.plan.geometry
        bytes_per_row = target.col_count * target.subword_bytes
        rows = max(1, math.ceil(bundle.plan.per_slice_used_bytes / bytes_per_row))
        shadow = DramGeometry(
            slice_count=target.slice_count,
            bank_count=1,
            row_count=rows,
            col_count=target.col_count,
            subword_bytes=target.subword_bytes,
        )
        if shadow.bytes_per_slice < bundle.plan.per_slice_used_bytes:
            raise AssertionError("compact RTL28 probe geometry is too small")
        return Rtl28ShadowAddressMap(target, shadow)

    @staticmethod
    def _physical_probe_bundle(
        bundle: Conv28PhysicalBundle,
        address_map: Rtl28ShadowAddressMap,
        *,
        include_region_keys: set[tuple[str, int]] | None = None,
    ) -> ConvPhysicalBundle:
        image = SparsePhysicalImage(address_map.shadow_geometry)
        regions: list[PhysicalRegion] = []
        for source in bundle.regions:
            if (
                include_region_keys is not None
                and (source.port, source.slice_id) not in include_region_keys
            ):
                continue
            name = _PORT_TO_PROBE_REGION[source.port]
            payload = bundle.read(source.port, source.slice_id)
            provenance = tuple(
                ByteProvenance(
                    tensor_id=name,
                    logical_coordinate=None,
                    element_byte=0,
                    semantic=("data" if offset < source.payload_bytes else "alignment"),
                    note=("" if offset < source.payload_bytes else "RTL28 region alignment"),
                )
                for offset in range(source.size_bytes)
            )
            shadow_base = address_map.to_shadow(source.base_address)
            image.write(shadow_base, payload, provenance)
            regions.append(
                PhysicalRegion(
                    name=name,
                    tensor_id=name,
                    slice_id=source.slice_id,
                    base_address=shadow_base,
                    payload_bytes=source.payload_bytes,
                    size_bytes=source.size_bytes,
                    dtype=bundle.plan.port(source.port).dtype,
                    physical_shape=source.physical_shape,
                )
            )
        return ConvPhysicalBundle(
            geometry=address_map.shadow_geometry,
            image=image,
            regions=tuple(regions),
            metadata={
                "contract": "candidate_only_rtl28_ndp_shadow_v1",
                "status": "operator_confirmed_conv_simulator_component",
                "profile_id": bundle.plan.profile_id,
                "target_contract": bundle.plan.contract,
                "slice_count": bundle.plan.geometry.slice_count,
                "activation_shape": bundle.plan.activation_shape,
                "weight_shape": bundle.plan.weight_shape,
                "output_shape": bundle.plan.output_shape,
                "c_tile": bundle.plan.c_tile,
                "k_tile": bundle.plan.k_tile,
                "c_padded": bundle.plan.c_padded,
            },
        )

    @staticmethod
    def _target_element_address(
        layout: QLinearConvPhysicalLayout,
        bundle: Conv28PhysicalBundle,
        port: str,
        coordinate: tuple[int, ...],
        *,
        owner: int | None = None,
    ) -> int:
        explanations = layout.explain_coordinate(
            bundle, bundle.tensor_ids[port], coordinate
        )
        addresses = [
            int(item["address"])
            for item in explanations
            if int(item["element_byte"]) == 0
            and (owner is None or int(item["slice_id"]) == owner)
        ]
        if len(addresses) != 1:
            raise PipelineError(
                f"expected one RTL28 {port}{coordinate} byte on owner {owner}, "
                f"got {len(addresses)}"
            )
        return addresses[0]

    @staticmethod
    def _ring_owners(
        bundle: Conv28PhysicalBundle,
        sample: int,
        output_channel: int,
    ) -> tuple[str, int | None, int, tuple[int, ...]]:
        owner_step = output_channel // bundle.plan.k_tile
        if bundle.plan.profile_id == GROUP4X7_BATCH_CHANNEL28_PROFILE:
            group_id = sample_to_group(sample).group_id
            ring = TOPOLOGY28.high_ring_for_group(group_id)
            destination = ring.owners[owner_step]
            return (
                "HIGH",
                group_id,
                destination,
                ring.traverse(destination, Direction.PREV),
            )
        if bundle.plan.profile_id == GLOBAL_RING28_PROFILE:
            ring = TOPOLOGY28.low_ring
            destination = ring.owners[owner_step]
            return (
                "LOW",
                None,
                destination,
                ring.traverse(destination, Direction.PREV),
            )
        raise ValueError(f"unsupported RTL28 profile {bundle.plan.profile_id!r}")

    def build_probe_plans(
        self,
        layout: QLinearConvPhysicalLayout,
        bundle: Conv28PhysicalBundle,
        *,
        strides: tuple[int, int] | None = None,
        pads: tuple[int, int, int, int] | None = None,
        dilations: tuple[int, int] | None = None,
        address_map: Rtl28ShadowAddressMap | None = None,
        output_coordinates: tuple[tuple[int, int, int, int], ...] | None = None,
    ) -> tuple[Rtl28ConvProbePlan, ...]:
        """Build physical PE probes without defining target instruction semantics."""

        self._require_layout(layout, bundle)
        strides = bundle.plan.strides if strides is None else tuple(strides)
        pads = bundle.plan.pads if pads is None else tuple(pads)
        dilations = bundle.plan.dilations if dilations is None else tuple(dilations)
        if strides != bundle.plan.strides:
            raise ValueError("strides disagree with the frozen RTL28 bundle")
        if pads != bundle.plan.pads:
            raise ValueError("pads disagree with the frozen RTL28 bundle")
        if dilations != bundle.plan.dilations:
            raise ValueError("dilations disagree with the frozen RTL28 bundle")
        address_map = address_map or self._shadow_map(bundle)

        activation = layout.inverse_port(bundle, "A")
        weight = layout.inverse_port(bundle, "B")
        bias = layout.inverse_port(bundle, "bias")
        w_scale = layout.inverse_port(bundle, "w_scale")
        w_zero_point = layout.inverse_port(bundle, "w_zero_point")
        x_scale = layout.inverse_port(bundle, "x_scale")
        x_zero_point = layout.inverse_port(bundle, "x_zero_point")
        y_scale = layout.inverse_port(bundle, "y_scale")
        y_zero_point = layout.inverse_port(bundle, "y_zero_point")
        if np.any(w_zero_point != 0):
            raise PipelineError(
                "candidate NDP RTL28 PE probe requires symmetric int8 weights; "
                "nonzero weight zero points need an approved hardware rule"
            )

        n_count, channels, input_h, input_w = activation.shape
        output_channels, _, kernel_h, kernel_w = weight.shape
        _, _, output_h, output_w = bundle.plan.output_shape
        selected_coordinates: set[tuple[int, int, int, int]] | None = None
        selected_nk: set[tuple[int, int]] | None = None
        if output_coordinates is not None:
            normalized = tuple(
                tuple(int(item) for item in value) for value in output_coordinates
            )
            if not normalized:
                raise ValueError("output_coordinates must not be empty")
            if any(len(value) != 4 for value in normalized):
                raise ValueError("every output coordinate must have rank four")
            if len(set(normalized)) != len(normalized):
                raise ValueError("output_coordinates must be unique")
            for n, k, oh, ow in normalized:
                if not (
                    0 <= n < n_count
                    and 0 <= k < output_channels
                    and 0 <= oh < output_h
                    and 0 <= ow < output_w
                ):
                    raise ValueError(
                        "output coordinate is outside the Conv result: "
                        f"{(n, k, oh, ow)}"
                    )
            selected_coordinates = set(normalized)
            selected_nk = {(value[0], value[1]) for value in normalized}
        stride_h, stride_w = strides
        dilation_h, dilation_w = dilations
        pad_top, pad_left, _, _ = pads
        x_zp = int(x_zero_point[0])
        y_zp = int(y_zero_point[0])
        plans: list[Rtl28ConvProbePlan] = []
        for n in range(n_count):
            for k in range(output_channels):
                if selected_nk is not None and (n, k) not in selected_nk:
                    continue
                ring_kind, group_id, destination, source_owners = self._ring_owners(
                    bundle, n, k
                )
                fallback_a_target = self._target_element_address(
                    layout, bundle, "A", (n, 0, 0, 0)
                )
                fallback_b_target = self._target_element_address(
                    layout, bundle, "B", (k, 0, 0, 0), owner=destination
                )
                multiplier = float(
                    np.float32(x_scale[0])
                    * np.float32(w_scale[k])
                    / np.float32(y_scale[0])
                )
                for oh in range(output_h):
                    for ow in range(output_w):
                        coordinate = (n, k, oh, ow)
                        if (
                            selected_coordinates is not None
                            and coordinate not in selected_coordinates
                        ):
                            continue
                        activation_addresses: list[int] = []
                        weight_addresses: list[int] = []
                        branch_mask: list[bool] = []
                        segment_ends: list[int] = []
                        channel_ranges: list[tuple[int, int]] = []
                        valid_weight_sum = 0
                        for source_owner in source_owners:
                            region = bundle.region("A", source_owner)
                            c_start = region.logical_start
                            c_count = region.logical_count
                            channel_ranges.append((c_start, c_count))
                            segment_start = len(activation_addresses)
                            for c in range(c_start, c_start + c_count):
                                for kh in range(kernel_h):
                                    ih = oh * stride_h - pad_top + kh * dilation_h
                                    for kw in range(kernel_w):
                                        iw = ow * stride_w - pad_left + kw * dilation_w
                                        if not (0 <= ih < input_h and 0 <= iw < input_w):
                                            continue
                                        a_target = self._target_element_address(
                                            layout, bundle, "A", (n, c, ih, iw)
                                        )
                                        if (
                                            bundle.plan.geometry.decode(a_target).slice_id
                                            != source_owner
                                        ):
                                            raise PipelineError(
                                                "RTL28 activation owner disagrees with ring segment"
                                            )
                                        b_target = self._target_element_address(
                                            layout,
                                            bundle,
                                            "B",
                                            (k, c, kh, kw),
                                            owner=destination,
                                        )
                                        activation_addresses.append(
                                            address_map.to_shadow(a_target)
                                        )
                                        weight_addresses.append(
                                            address_map.to_shadow(b_target)
                                        )
                                        branch_mask.append(False)
                                        valid_weight_sum += int(weight[k, c, kh, kw])
                            segment_lanes = len(activation_addresses) - segment_start
                            masked_lanes = 2 if segment_lanes == 0 else segment_lanes % 2
                            for _ in range(masked_lanes):
                                activation_addresses.append(
                                    address_map.to_shadow(fallback_a_target)
                                )
                                weight_addresses.append(
                                    address_map.to_shadow(fallback_b_target)
                                )
                                branch_mask.append(True)
                            segment_ends.append(len(activation_addresses))

                        target_output = self._target_element_address(
                            layout, bundle, "D", coordinate
                        )
                        if (
                            bundle.plan.geometry.decode(target_output).slice_id
                            != destination
                        ):
                            raise PipelineError(
                                "RTL28 output coordinate disagrees with K destination owner"
                            )
                        probe = NdpInt8DotProbe(
                            name="rtl28_output_n{}_k{}_h{}_w{}".format(*coordinate),
                            activation_addresses=tuple(activation_addresses),
                            weight_addresses=tuple(weight_addresses),
                            bias=int(bias[k]) - x_zp * valid_weight_sum,
                            logical_output_coordinate=coordinate,
                            branch_mask=tuple(branch_mask),
                            ring_segment_ends=tuple(segment_ends),
                            output_address=address_map.to_shadow(target_output),
                            requant_multiplier=multiplier,
                            output_zero_point=y_zp,
                        )
                        plans.append(
                            Rtl28ConvProbePlan(
                                probe=probe,
                                profile_id=bundle.plan.profile_id,
                                ring_kind=ring_kind,
                                group_id=group_id,
                                destination_owner=destination,
                                source_owners=source_owners,
                                channel_ranges=tuple(channel_ranges),
                                target_output_address=target_output,
                            )
                        )
        if selected_coordinates is not None and len(plans) != len(selected_coordinates):
            raise PipelineError(
                "RTL28 coordinate selection did not produce every requested probe"
            )
        return tuple(plans)

    def run_qlinear_conv_coordinates(
        self,
        layout: QLinearConvPhysicalLayout,
        bundle: Conv28PhysicalBundle,
        output_coordinates: tuple[tuple[int, int, int, int], ...],
        *,
        strides: tuple[int, int] | None = None,
        pads: tuple[int, int, int, int] | None = None,
        dilations: tuple[int, int] | None = None,
    ) -> NdpRtl28CoordinateResult:
        """Execute only selected real output coordinates through NDPFuncModel.

        This is the bounded bridge used for the first real 1x1 Conv closure. It
        exercises real RTL28 addresses and HIGH/LOW ring segmentation without
        constructing millions of per-output probes for the whole tensor.
        """

        self._require_layout(layout, bundle)
        coordinates = tuple(
            tuple(int(item) for item in coordinate)
            for coordinate in output_coordinates
        )
        address_map = self._shadow_map(bundle)
        plans = self.build_probe_plans(
            layout,
            bundle,
            strides=strides,
            pads=pads,
            dilations=dilations,
            address_map=address_map,
            output_coordinates=coordinates,
        )
        included: set[tuple[str, int]] = set()
        for plan in plans:
            included.update(("A", owner) for owner in plan.source_owners)
            included.add(("B", plan.destination_owner))
            included.add(("D", plan.destination_owner))
        physical_bundle = self._physical_probe_bundle(
            bundle,
            address_map,
            include_region_keys=included,
        )
        physical_probe = self._ndp.probe_physical_bundle(
            physical_bundle,
            int8_dot_probes=tuple(plan.probe for plan in plans),
        )
        returned: dict[tuple[int, int, int, int], tuple[int, int]] = {}
        for item in physical_probe.int8_dot_probes:
            coordinate = tuple(int(value) for value in item["logical_output_coordinate"])
            if coordinate in returned:
                raise PipelineError(f"duplicate RTL28 NDP output coordinate {coordinate}")
            returned[coordinate] = (int(item["accumulator"]), int(item["output_after"]))
        if set(returned) != set(coordinates):
            raise PipelineError("RTL28 NDP coordinate probe coverage differs")

        updated_payloads = dict(bundle.payloads)
        for slice_id in {plan.destination_owner for plan in plans}:
            region = physical_bundle.region("output", slice_id)
            updated_payloads[("D", slice_id)] = physical_bundle.image.read(
                region.base_address, region.size_bytes
            )
        return NdpRtl28CoordinateResult(
            coordinates=coordinates,
            accumulators=tuple(returned[value][0] for value in coordinates),
            outputs=tuple(returned[value][1] for value in coordinates),
            probe_plans=plans,
            physical_probe=physical_probe,
            address_map=address_map,
            updated_bundle=replace(bundle, payloads=updated_payloads),
        )

    def run_qlinear_conv(
        self,
        layout: QLinearConvPhysicalLayout,
        bundle: Conv28PhysicalBundle,
        *,
        strides: tuple[int, int] | None = None,
        pads: tuple[int, int, int, int] | None = None,
        dilations: tuple[int, int] | None = None,
    ) -> NdpRtl28ConvResult:
        """Execute candidate accumulators/requantization in the NDP probe."""

        self._require_layout(layout, bundle)
        address_map = self._shadow_map(bundle)
        physical_bundle = self._physical_probe_bundle(bundle, address_map)
        plans = self.build_probe_plans(
            layout,
            bundle,
            strides=strides,
            pads=pads,
            dilations=dilations,
            address_map=address_map,
        )
        physical_probe = self._ndp.probe_physical_bundle(
            physical_bundle,
            int8_dot_probes=tuple(plan.probe for plan in plans),
        )
        output_shape = bundle.plan.output_shape
        accumulator = np.empty(output_shape, dtype=np.int32)
        output = np.empty(output_shape, dtype=np.uint8)
        seen: set[tuple[int, int, int, int]] = set()
        for item in physical_probe.int8_dot_probes:
            coordinate = tuple(int(value) for value in item["logical_output_coordinate"])
            if coordinate in seen:
                raise PipelineError(f"duplicate RTL28 NDP output coordinate {coordinate}")
            accumulator[coordinate] = np.int32(item["accumulator"])
            output[coordinate] = np.uint8(item["output_after"])
            seen.add(coordinate)
        if len(seen) != accumulator.size:
            raise PipelineError("RTL28 NDP probes did not cover every output coordinate")

        updated_payloads = dict(bundle.payloads)
        for slice_id in range(bundle.plan.geometry.slice_count):
            region = physical_bundle.region("output", slice_id)
            updated_payloads[("D", slice_id)] = physical_bundle.image.read(
                region.base_address, region.size_bytes
            )
        updated_bundle = replace(bundle, payloads=updated_payloads)
        inverse_output = layout.inverse_port(updated_bundle, "D")
        if not np.array_equal(output, inverse_output):
            raise PipelineError("RTL28 D inverse disagrees with NDP writeback")
        return NdpRtl28ConvResult(
            accumulator=accumulator,
            output=output,
            inverse_output=inverse_output,
            probe_plans=plans,
            physical_probe=physical_probe,
            address_map=address_map,
            updated_bundle=updated_bundle,
        )


__all__ = [
    "NdpRtl28CoordinateResult",
    "NdpRtl28ConvResult",
    "NdpRtl28FunctionalAdapter",
    "Rtl28ConvProbePlan",
    "Rtl28ShadowAddressMap",
]
