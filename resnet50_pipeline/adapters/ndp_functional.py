from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..conv_layout import ConvPhysicalBundle
from ..errors import PipelineError


@dataclass(frozen=True)
class NdpPhysicalProbeResult:
    per_slice: int
    total_bytes: int
    regions: tuple[dict[str, Any], ...]
    int8_dot_probes: tuple[dict[str, Any], ...]
    target_config_binding: dict[str, Any] | None = None
    requant_config_binding: dict[str, Any] | None = None
    int8_conv_1x1_jobs: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class NdpConvAccumulatorResult:
    accumulator: np.ndarray
    output: np.ndarray
    physical_probe: NdpPhysicalProbeResult


@dataclass(frozen=True)
class NdpInt8DotProbe:
    name: str
    activation_addresses: tuple[int, ...]
    weight_addresses: tuple[int, ...]
    bias: int
    logical_output_coordinate: tuple[int, int, int, int] | None = None
    branch_mask: tuple[bool, ...] = ()
    ring_segment_ends: tuple[int, ...] = ()
    output_address: int | None = None
    requant_multiplier: float | None = None
    output_zero_point: int | None = None


class NdpFunctionalAdapter:
    def __init__(
        self,
        repository: Path,
        *,
        python_executable: Path | None = None,
        timeout_seconds: int = 30,
    ):
        self.repository = repository.resolve()
        self.python_executable = Path(python_executable or sys.executable).resolve()
        self.timeout_seconds = timeout_seconds
        bridge = self.repository / "tools" / "physical_image_probe.py"
        if not bridge.is_file():
            raise PipelineError(f"NDP physical-image bridge is missing: {bridge}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def probe_physical_bundle(
        self,
        bundle: ConvPhysicalBundle,
        *,
        int8_dot_probes: tuple[NdpInt8DotProbe, ...] = (),
        target_config_binding: dict[str, Any] | None = None,
        requant_config_binding: dict[str, Any] | None = None,
        int8_conv_1x1_jobs: tuple[dict[str, Any], ...] = (),
    ) -> NdpPhysicalProbeResult:
        geometry = bundle.geometry
        if int8_conv_1x1_jobs and target_config_binding is None:
            raise ValueError("bulk Conv jobs require a target config binding")
        if requant_config_binding is not None and (
            target_config_binding is None or not int8_conv_1x1_jobs
        ):
            raise ValueError("requant config binding requires accumulate binding and bulk jobs")
        schema_version = (
            "0.3"
            if requant_config_binding is not None
            else "0.2"
            if target_config_binding is not None
            else "0.1"
        )
        request = {
            "schema_version": schema_version,
            "geometry": {
                "slice_count": geometry.slice_count,
                "bank_count": geometry.bank_count,
                "row_count": geometry.row_count,
                "col_count": geometry.col_count,
                "subword_bytes": geometry.subword_bytes,
            },
            "regions": [],
            "int8_dot_probes": [],
        }
        if target_config_binding is not None:
            request["target_config_binding"] = target_config_binding
            request["int8_conv_1x1_jobs"] = list(int8_conv_1x1_jobs)
        if requant_config_binding is not None:
            request["requant_config_binding"] = requant_config_binding
        expected: dict[tuple[str, int], str] = {}
        for region in bundle.regions:
            payload = bundle.image.read(region.base_address, region.size_bytes)
            digest = hashlib.sha256(payload).hexdigest()
            request["regions"].append(
                {
                    "name": region.name,
                    "slice_id": region.slice_id,
                    "base_address": region.base_address,
                    "data_hex": payload.hex(),
                    "sha256": digest,
                }
            )
            expected[(region.name, region.slice_id)] = digest
        expected_dots: dict[str, int] = {}
        expected_dot_metadata: dict[
            str, tuple[tuple[int, int, int, int] | None, tuple[int, ...]]
        ] = {}
        expected_requant: dict[str, tuple[int, int, int] | None] = {}
        for probe in int8_dot_probes:
            if probe.name in expected_dots:
                raise ValueError(f"duplicate int8 dot probe name: {probe.name}")
            if len(probe.activation_addresses) != len(probe.weight_addresses):
                raise ValueError("activation and weight address counts differ")
            if not probe.activation_addresses or len(probe.activation_addresses) % 2:
                raise ValueError("int8 dot probes require a positive even lane count")
            branch_mask = probe.branch_mask or (False,) * len(probe.activation_addresses)
            if len(branch_mask) != len(probe.activation_addresses):
                raise ValueError("int8 dot probe branch mask length differs")
            segment_ends = probe.ring_segment_ends
            if segment_ends and (
                tuple(sorted(segment_ends)) != segment_ends
                or segment_ends[-1] != len(probe.activation_addresses)
                or any(item <= 0 or item % 2 for item in segment_ends)
            ):
                raise ValueError(
                    "ring segment ends must be sorted, even, and cover every lane"
                )
            activation = np.array(
                [bundle.image.read(address, 1)[0] for address in probe.activation_addresses],
                dtype=np.uint8,
            )
            activation[np.asarray(branch_mask, dtype=bool)] = 0
            weight = np.array(
                [bundle.image.read(address, 1)[0] for address in probe.weight_addresses],
                dtype=np.uint8,
            ).view(np.int8)
            expected_accumulator = int(probe.bias) + int(
                np.sum(activation.astype(np.int32) * weight.astype(np.int32), dtype=np.int64)
            )
            if not np.iinfo(np.int32).min <= expected_accumulator <= np.iinfo(np.int32).max:
                raise OverflowError(f"int8 dot probe {probe.name} exceeds int32")
            expected_dots[probe.name] = expected_accumulator
            expected_dot_metadata[probe.name] = (
                probe.logical_output_coordinate,
                segment_ends,
            )
            requant_fields = (
                probe.output_address,
                probe.requant_multiplier,
                probe.output_zero_point,
            )
            if any(item is not None for item in requant_fields) and not all(
                item is not None for item in requant_fields
            ):
                raise ValueError(
                    "requantization requires output address, multiplier, and zero point"
                )
            if probe.output_address is None:
                expected_requant[probe.name] = None
            else:
                output_address = int(probe.output_address)
                output_before = bundle.image.read(output_address, 1)[0]
                scaled = np.float32(expected_accumulator) * np.float32(
                    probe.requant_multiplier
                )
                requantized = int(
                    np.clip(
                        int(np.rint(scaled)) + int(probe.output_zero_point), 0, 255
                    )
                )
                expected_requant[probe.name] = (
                    output_address,
                    output_before,
                    requantized,
                )
            request["int8_dot_probes"].append(
                {
                    "name": probe.name,
                    "activation_addresses": list(probe.activation_addresses),
                    "weight_addresses": list(probe.weight_addresses),
                    "bias": int(probe.bias),
                    "logical_output_coordinate": (
                        None
                        if probe.logical_output_coordinate is None
                        else list(probe.logical_output_coordinate)
                    ),
                    "branch_mask": list(branch_mask),
                    "ring_segment_ends": list(segment_ends),
                    "output_address": probe.output_address,
                    "requant_multiplier": probe.requant_multiplier,
                    "output_zero_point": probe.output_zero_point,
                }
            )

        with tempfile.TemporaryDirectory(prefix="ndp-physical-probe-") as directory:
            request_path = Path(directory) / "request.json"
            request_path.write_text(
                json.dumps(request, sort_keys=True), encoding="utf-8"
            )
            try:
                completed = subprocess.run(
                    [
                        str(self.python_executable),
                        "-m",
                        "tools.physical_image_probe",
                        str(request_path),
                    ],
                    cwd=self.repository,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
            except subprocess.TimeoutExpired as error:
                raise PipelineError(
                    f"NDP physical-image probe timed out after {self.timeout_seconds}s"
                ) from error
        if completed.returncode != 0:
            raise PipelineError(
                "NDP physical-image probe failed: "
                + (completed.stderr.strip() or completed.stdout.strip())
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise PipelineError("NDP physical-image probe returned invalid JSON") from error
        if response.get("schema_version") != schema_version:
            raise PipelineError("NDP physical-image probe returned an unsupported schema")
        if int(response.get("total_bytes", -1)) != geometry.total_bytes:
            raise PipelineError("NDP physical-image probe returned the wrong DRAM capacity")
        if len(response.get("regions", [])) != len(expected):
            raise PipelineError("NDP physical-image probe returned the wrong region count")
        seen: set[tuple[str, int]] = set()
        for region in response["regions"]:
            key = (region["name"], int(region["slice_id"]))
            if key not in expected:
                raise PipelineError(f"NDP probe returned an unexpected region: {key}")
            if not region["hash_matches"] or region["sha256"] != expected[key]:
                raise PipelineError(f"NDP probe corrupted physical bytes for region: {key}")
            if (
                int(region["start_coordinate"][0]) != key[1]
                or int(region["end_coordinate"][0]) != key[1]
            ):
                raise PipelineError(f"NDP probe mapped region to the wrong slice: {key}")
            seen.add(key)
        if seen != set(expected):
            raise PipelineError("NDP probe did not return every physical region")
        if int(response["per_slice"]) != geometry.bytes_per_slice:
            raise PipelineError("NDP DRAM per_slice disagrees with the W2 geometry")
        dot_response = response.get("int8_dot_probes", [])
        if len(dot_response) != len(expected_dots):
            raise PipelineError("NDP probe returned the wrong int8 dot count")
        seen_dots: set[str] = set()
        pending_writes: dict[int, int] = {}
        for dot in dot_response:
            name = dot["name"]
            if name not in expected_dots or name in seen_dots:
                raise PipelineError(f"NDP probe returned an unexpected int8 dot: {name}")
            if int(dot["accumulator"]) != expected_dots[name]:
                raise PipelineError(f"NDP PEA accumulator mismatch for int8 dot: {name}")
            expected_coordinate, expected_segments = expected_dot_metadata[name]
            returned_coordinate = dot.get("logical_output_coordinate")
            if returned_coordinate is not None:
                returned_coordinate = tuple(int(item) for item in returned_coordinate)
            if returned_coordinate != expected_coordinate:
                raise PipelineError(f"NDP probe returned the wrong coordinate for: {name}")
            if tuple(int(item) for item in dot.get("ring_segment_ends", [])) != expected_segments:
                raise PipelineError(f"NDP probe returned the wrong ring segments for: {name}")
            if expected_segments and len(dot.get("partial_accumulators", [])) != len(
                expected_segments
            ):
                raise PipelineError(f"NDP probe omitted ring partial sums for: {name}")
            if expected_segments:
                ring_states = dot.get("ring_loop_states", [])
                if len(ring_states) != len(expected_segments) or [
                    int(item["last"]) for item in ring_states
                ] != [0] * (len(expected_segments) - 1) + [1]:
                    raise PipelineError(f"NDP probe returned invalid ring LC state for: {name}")
                if dot.get("execution_path") != [
                    "DRAM",
                    "input_buffer",
                    "SpecialPEA",
                    "ActivationUnit",
                    "output_buffer",
                    "DRAM",
                ]:
                    raise PipelineError(f"NDP probe bypassed the candidate runner for: {name}")
            expected_output = expected_requant[name]
            if expected_output is None:
                if dot.get("requantized_output") is not None:
                    raise PipelineError(f"NDP probe unexpectedly requantized: {name}")
            else:
                output_address, output_before, requantized = expected_output
                if (
                    int(dot.get("output_address", -1)) != output_address
                    or int(dot.get("output_before", -1)) != output_before
                    or int(dot.get("requantized_output", -1)) != requantized
                    or int(dot.get("output_after", -1)) != requantized
                ):
                    raise PipelineError(f"NDP requant/writeback mismatch for: {name}")
                if output_address in pending_writes:
                    raise PipelineError(
                        f"multiple NDP outputs target physical address: {output_address}"
                    )
                pending_writes[output_address] = requantized
            seen_dots.add(name)
        for output_address, value in pending_writes.items():
            bundle.image.overwrite(output_address, bytes([value]))
        returned_binding = response.get("target_config_binding")
        returned_requant_binding = response.get("requant_config_binding")
        bulk_response = response.get("int8_conv_1x1_jobs", [])
        if target_config_binding is None:
            if returned_binding is not None or returned_requant_binding is not None or bulk_response:
                raise PipelineError("NDP probe returned an unexpected target config result")
        else:
            if (
                not isinstance(returned_binding, dict)
                or returned_binding.get("status") != "validated"
                or returned_binding.get("config_sha256")
                != target_config_binding.get("config_sha256")
                or returned_binding.get("semantic_contract_sha256")
                != target_config_binding.get("semantic_contract_sha256")
                or returned_binding.get("n2n_mem_loop") != 4
                or returned_binding.get("n2n_src_slice_sel") != 1
                or returned_binding.get("n2n_dst_slice_sel") != 1
            ):
                raise PipelineError("NDP target config binding validation differs")
            requested_names = [item.get("name") for item in int8_conv_1x1_jobs]
            returned_names = [item.get("name") for item in bulk_response]
            if returned_names != requested_names:
                raise PipelineError("NDP bulk Conv job order differs")
            for job in bulk_response:
                if job.get("status") != "passed":
                    raise PipelineError(f"NDP bulk Conv mismatch: {job.get('name')}")
                for comparison in job.get("comparisons", []):
                    if any(
                        comparison.get(port, {}).get("mismatch_count") != 0
                        for port in ("P", "D")
                    ):
                        raise PipelineError(
                            f"NDP bulk Conv comparison differs: {comparison.get('name')}"
                        )
            if requant_config_binding is None:
                if returned_requant_binding is not None:
                    raise PipelineError("NDP returned an unexpected requant binding")
            elif (
                not isinstance(returned_requant_binding, dict)
                or returned_requant_binding.get("status") != "validated"
                or returned_requant_binding.get("manifest_sha256")
                != requant_config_binding.get("manifest_sha256")
                or returned_requant_binding.get("channel_count") != 64
                or returned_requant_binding.get("shard_count") != 8
                or returned_requant_binding.get("unique_flush_count") != 64
                or returned_requant_binding.get("flush_count_per_logical_output") != 1
                or returned_requant_binding.get("staged_d_offsets") != [904400, 979664]
            ):
                raise PipelineError("NDP requant config binding validation differs")
        return NdpPhysicalProbeResult(
            per_slice=int(response["per_slice"]),
            total_bytes=int(response["total_bytes"]),
            regions=tuple(response["regions"]),
            int8_dot_probes=tuple(dot_response),
            target_config_binding=returned_binding,
            requant_config_binding=returned_requant_binding,
            int8_conv_1x1_jobs=tuple(bulk_response),
        )

    @staticmethod
    def _read_logical_bytes(
        bundle: ConvPhysicalBundle,
        tensor_id: str,
        logical_coordinate: tuple[int, ...],
    ) -> bytes:
        addresses = bundle.addresses_for(tensor_id, logical_coordinate)
        if not addresses:
            raise PipelineError(
                f"physical bundle has no bytes for {tensor_id}{logical_coordinate}"
            )
        return bytes(bundle.image.read(address, 1)[0] for address in addresses)

    def build_qlinear_conv_accumulator_probes(
        self,
        bundle: ConvPhysicalBundle,
        *,
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
    ) -> tuple[NdpInt8DotProbe, ...]:
        """Build candidate ring probes for every group=1 QLinearConv output.

        The probes exercise physical DRAM address provenance and the NDP PE's
        INT8 dot path. Padding and empty/odd ring segments are represented by
        branch-masked lanes, not by fabricated logical tensor coordinates.
        """
        if len(strides) != 2 or any(item <= 0 for item in strides):
            raise ValueError("strides must contain two positive integers")
        if len(dilations) != 2 or any(item <= 0 for item in dilations):
            raise ValueError("dilations must contain two positive integers")
        if len(pads) != 4 or any(item < 0 for item in pads):
            raise ValueError("pads must contain four non-negative integers")
        activation_shape = tuple(int(item) for item in bundle.metadata["activation_shape"])
        weight_shape = tuple(int(item) for item in bundle.metadata["weight_shape"])
        n_count, channels, input_h, input_w = activation_shape
        output_channels, weight_channels, kernel_h, kernel_w = weight_shape
        if weight_channels != channels:
            raise PipelineError("candidate NDP Conv probes only support group=1")
        slice_count = int(bundle.metadata["slice_count"])
        c_tile = int(bundle.metadata["c_tile"])
        k_tile = int(bundle.metadata["k_tile"])
        stride_h, stride_w = strides
        dilation_h, dilation_w = dilations
        pad_top, pad_left, pad_bottom, pad_right = pads
        output_h = (
            input_h
            + pad_top
            + pad_bottom
            - dilation_h * (kernel_h - 1)
            - 1
        ) // stride_h + 1
        output_w = (
            input_w
            + pad_left
            + pad_right
            - dilation_w * (kernel_w - 1)
            - 1
        ) // stride_w + 1
        if output_h <= 0 or output_w <= 0:
            raise ValueError("Conv parameters produce a non-positive output shape")
        recorded_output_shape = bundle.metadata.get("output_shape")
        expected_output_shape = (n_count, output_channels, output_h, output_w)
        if recorded_output_shape is not None and tuple(recorded_output_shape) != expected_output_shape:
            raise PipelineError("physical bundle output shape disagrees with Conv parameters")
        if recorded_output_shape is None:
            raise PipelineError("Conv requant/writeback probes require an output region")

        x_zero_points = self._read_logical_bytes(bundle, "x_zero_point", ())
        if not x_zero_points or any(item != x_zero_points[0] for item in x_zero_points):
            raise PipelineError("replicated activation zero points differ between slices")
        x_zero_point = x_zero_points[0]
        x_scale_bytes = self._read_logical_bytes(bundle, "x_scale", ())
        y_scale_bytes = self._read_logical_bytes(bundle, "y_scale", ())
        scalar_copies = slice_count
        if len(x_scale_bytes) != 4 * scalar_copies or len(y_scale_bytes) != 4 * scalar_copies:
            raise PipelineError("replicated x/y scales have the wrong physical size")
        x_scales = tuple(
            struct.unpack("<f", x_scale_bytes[index : index + 4])[0]
            for index in range(0, len(x_scale_bytes), 4)
        )
        y_scales = tuple(
            struct.unpack("<f", y_scale_bytes[index : index + 4])[0]
            for index in range(0, len(y_scale_bytes), 4)
        )
        if any(value != x_scales[0] for value in x_scales) or any(
            value != y_scales[0] for value in y_scales
        ):
            raise PipelineError("replicated x/y scales differ between slices")
        if x_scales[0] <= 0 or y_scales[0] <= 0:
            raise PipelineError("x/y scales must be positive")
        y_zero_points = self._read_logical_bytes(bundle, "y_zero_point", ())
        if not y_zero_points or any(item != y_zero_points[0] for item in y_zero_points):
            raise PipelineError("replicated output zero points differ between slices")
        output_zero_point = y_zero_points[0]
        weight_zero_points = []
        requant_multipliers = []
        for output_channel in range(output_channels):
            raw = self._read_logical_bytes(bundle, "w_zero_point", (output_channel,))
            if len(raw) != 1:
                raise PipelineError("weight zero point must map to exactly one physical byte")
            weight_zero_points.append(int(np.array([raw[0]], dtype=np.uint8).view(np.int8)[0]))
            w_scale_bytes = self._read_logical_bytes(bundle, "w_scale", (output_channel,))
            if len(w_scale_bytes) != 4:
                raise PipelineError("weight scale must map to exactly four physical bytes")
            weight_scale = struct.unpack("<f", w_scale_bytes)[0]
            if weight_scale <= 0:
                raise PipelineError("weight scales must be positive")
            requant_multipliers.append(
                float(
                    np.float32(x_scales[0])
                    * np.float32(weight_scale)
                    / np.float32(y_scales[0])
                )
            )
        if any(weight_zero_points):
            raise PipelineError(
                "candidate NDP PE path currently requires symmetric int8 weights (w_zero_point=0)"
            )

        fallback_activation = bundle.addresses_for("activation", (0, 0, 0, 0))[0]
        probes: list[NdpInt8DotProbe] = []
        for n in range(n_count):
            for output_channel in range(output_channels):
                owner_slice = output_channel // k_tile
                bias_bytes = self._read_logical_bytes(bundle, "bias", (output_channel,))
                if len(bias_bytes) != 4:
                    raise PipelineError("bias must map to exactly four physical bytes")
                physical_bias = int.from_bytes(bias_bytes, "little", signed=True)
                fallback_weight = bundle.addresses_for(
                    "weight", (output_channel, 0, 0, 0)
                )[0]
                for output_y in range(output_h):
                    for output_x in range(output_w):
                        activation_addresses: list[int] = []
                        weight_addresses: list[int] = []
                        branch_mask: list[bool] = []
                        segment_ends: list[int] = []
                        valid_weight_sum = 0
                        for ring_step in range(slice_count):
                            source_slice = (owner_slice - ring_step) % slice_count
                            segment_start = len(activation_addresses)
                            channel_start = source_slice * c_tile
                            channel_end = min(channel_start + c_tile, channels)
                            for channel in range(channel_start, channel_end):
                                for kernel_y in range(kernel_h):
                                    input_y = (
                                        output_y * stride_h
                                        - pad_top
                                        + kernel_y * dilation_h
                                    )
                                    for kernel_x in range(kernel_w):
                                        input_x = (
                                            output_x * stride_w
                                            - pad_left
                                            + kernel_x * dilation_w
                                        )
                                        if not (0 <= input_y < input_h and 0 <= input_x < input_w):
                                            continue
                                        activation_addresses.append(
                                            bundle.addresses_for(
                                                "activation", (n, channel, input_y, input_x)
                                            )[0]
                                        )
                                        weight_coordinate = (
                                            output_channel,
                                            channel,
                                            kernel_y,
                                            kernel_x,
                                        )
                                        weight_address = bundle.addresses_for(
                                            "weight", weight_coordinate
                                        )[0]
                                        weight_addresses.append(weight_address)
                                        branch_mask.append(False)
                                        weight_byte = bundle.image.read(weight_address, 1)[0]
                                        valid_weight_sum += int(
                                            np.array([weight_byte], dtype=np.uint8).view(np.int8)[0]
                                        )
                            segment_lanes = len(activation_addresses) - segment_start
                            padding_lanes = 2 if segment_lanes == 0 else segment_lanes % 2
                            for _ in range(padding_lanes):
                                activation_addresses.append(fallback_activation)
                                weight_addresses.append(fallback_weight)
                                branch_mask.append(True)
                            segment_ends.append(len(activation_addresses))
                        corrected_bias = physical_bias - x_zero_point * valid_weight_sum
                        coordinate = (n, output_channel, output_y, output_x)
                        probes.append(
                            NdpInt8DotProbe(
                                name="output_n{}_k{}_h{}_w{}".format(*coordinate),
                                activation_addresses=tuple(activation_addresses),
                                weight_addresses=tuple(weight_addresses),
                                bias=corrected_bias,
                                logical_output_coordinate=coordinate,
                                branch_mask=tuple(branch_mask),
                                ring_segment_ends=tuple(segment_ends),
                                output_address=bundle.addresses_for(
                                    "output", coordinate
                                )[0],
                                requant_multiplier=requant_multipliers[output_channel],
                                output_zero_point=output_zero_point,
                            )
                        )
        return tuple(probes)

    def run_qlinear_conv_accumulators(
        self,
        bundle: ConvPhysicalBundle,
        *,
        strides: tuple[int, int] = (1, 1),
        pads: tuple[int, int, int, int] = (0, 0, 0, 0),
        dilations: tuple[int, int] = (1, 1),
    ) -> NdpConvAccumulatorResult:
        probes = self.build_qlinear_conv_accumulator_probes(
            bundle, strides=strides, pads=pads, dilations=dilations
        )
        physical_probe = self.probe_physical_bundle(bundle, int8_dot_probes=probes)
        coordinates = [probe.logical_output_coordinate for probe in probes]
        if any(coordinate is None for coordinate in coordinates):
            raise AssertionError("generated Conv probes must have output coordinates")
        output_shape = tuple(max(coordinate[axis] for coordinate in coordinates) + 1 for axis in range(4))
        accumulator = np.empty(output_shape, dtype=np.int32)
        output = np.empty(output_shape, dtype=np.uint8)
        seen: set[tuple[int, int, int, int]] = set()
        for dot in physical_probe.int8_dot_probes:
            coordinate = tuple(int(item) for item in dot["logical_output_coordinate"])
            if coordinate in seen:
                raise PipelineError(f"duplicate NDP Conv output coordinate: {coordinate}")
            accumulator[coordinate] = np.int32(dot["accumulator"])
            output[coordinate] = np.uint8(dot["output_after"])
            seen.add(coordinate)
        expected = set(coordinates)
        if seen != expected or len(seen) != accumulator.size:
            raise PipelineError("NDP Conv probes did not cover every output coordinate")
        return NdpConvAccumulatorResult(
            accumulator=accumulator,
            output=output,
            physical_probe=physical_probe,
        )
