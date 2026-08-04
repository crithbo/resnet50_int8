from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from .conv_instance import ConvTargetRequest, build_conv_target_request
from .conv_execplan_transport import (
    build_conv_execplan_request,
    canonical_execplan_bytes,
    validate_conv_execplan_request,
)
from .golden.qlinear_conv import requantize_uint8
from .golden.qlinear_conv import qlinear_conv_im2col
from .hashing import sha256_file
from .adapters.ndp_rtl28_functional import NdpRtl28FunctionalAdapter
from .topology28 import Direction, TOPOLOGY28
from .w5_conv_preflight import (
    _bind_native_encoder_candidate,
    _compare_ndp_target_config,
    _compare_tile,
    load_conv_instance_execution,
)


SCHEMA_VERSION = "0.1"
REPORT_KIND = "typed_conv_instance_candidate_preflight"


class ConvInstancePreflightError(ValueError):
    """A candidate Conv instance failed a required configuration/numerical gate."""


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


def _comparison(actual: np.ndarray, golden: np.ndarray) -> dict[str, Any]:
    actual = np.ascontiguousarray(actual)
    golden = np.ascontiguousarray(golden)
    return {
        "dtype": str(golden.dtype),
        "element_count": int(golden.size),
        "mismatch_count": int(np.count_nonzero(actual != golden)),
        "actual_sha256": _array_sha256(actual),
        "golden_sha256": _array_sha256(golden),
    }


def _locked_repository_commit(root: Path, name: str) -> str:
    locks = _load_json(root / "repos.lock.json")
    for record in locks.get("repositories", []):
        if isinstance(record, dict) and record.get("name") == name:
            commit = record.get("commit")
            if isinstance(commit, str) and len(commit) == 40:
                return commit
    raise ConvInstancePreflightError(f"repository lock is missing {name}")


def _compare_3x3_first_tile(
    values: dict[str, np.ndarray],
    layout: Any,
    bundle: Any,
    request: ConvTargetRequest,
) -> dict[str, Any]:
    spec = request.spec
    ring = TOPOLOGY28.high_ring_for_group(0)
    destination = ring.owners[0]
    traversal = ring.traverse(destination, Direction.PREV)
    x_zp = int(values["x_zero_point"].reshape(-1)[0])
    centered = values["A"][: spec.first_group_sample_count].astype(np.int32) - x_zp
    padded = np.pad(centered, ((0, 0), (0, 0), (1, 1), (1, 1)))
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (3, 3), axis=(2, 3)
    )
    accumulator = np.broadcast_to(
        values["bias"][: spec.k_tile]
        .astype(np.int64)
        .reshape(1, spec.k_tile, 1, 1),
        (
            spec.first_group_sample_count,
            spec.k_tile,
            spec.output_height,
            spec.output_width,
        ),
    ).copy()
    lifecycle: list[dict[str, Any]] = []
    for index, source_slice in enumerate(traversal):
        region = bundle.region("A", source_slice)
        start = region.logical_start
        stop = start + region.logical_count
        weight = (
            values["B"][: spec.k_tile, start:stop].astype(np.int32)
            - values["w_zero_point"][: spec.k_tile]
            .astype(np.int32)
            .reshape(-1, 1, 1, 1)
        )
        partial = np.einsum(
            "nchwrs,kcrs->nkhw",
            windows[:, start:stop],
            weight,
            dtype=np.int64,
            optimize=True,
        )
        accumulator += partial
        limits = np.iinfo(np.int32)
        if int(accumulator.min()) < limits.min or int(accumulator.max()) > limits.max:
            raise ConvInstancePreflightError("3x3 first-tile partial exceeds INT32")
        phase = (
            "first"
            if index == 0
            else "last"
            if index == len(traversal) - 1
            else "middle"
        )
        lifecycle.append(
            {
                "phase": phase,
                "source_slice": source_slice,
                "channel_start": start,
                "channel_count": region.logical_count,
                "kernel_positions": 9,
                "int8_pair_count_per_output": region.logical_count * 9 // 2,
                "bias_action": "initialize_before_segment" if index == 0 else "preserve",
                "psum_action": "requantize_after_segment" if phase == "last" else "persist_int32",
                "logical_psum_sha256": _array_sha256(accumulator.astype(np.int32)),
                "minimum": int(accumulator.min()),
                "maximum": int(accumulator.max()),
            }
        )
    actual_p = accumulator.astype(np.int32)
    golden_p = np.ascontiguousarray(
        values["P"][: spec.first_group_sample_count, : spec.k_tile]
    )
    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"][: spec.k_tile].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    actual_d = requantize_uint8(actual_p, multiplier, values["y_zero_point"])
    golden_d = np.ascontiguousarray(
        values["D"][: spec.first_group_sample_count, : spec.k_tile]
    )
    comparisons = {"P": _comparison(actual_p, golden_p), "D": _comparison(actual_d, golden_d)}
    if any(comparisons[port]["mismatch_count"] for port in ("P", "D")):
        raise ConvInstancePreflightError("3x3 first-tile P/D differs from W3")

    for port, value in (("P", golden_p), ("D", golden_d)):
        region = bundle.region(port, destination)
        physical = np.moveaxis(value, 1, -1).reshape(region.physical_shape)
        payload = np.ascontiguousarray(physical).astype(
            "<i4" if port == "P" else np.uint8, copy=False
        ).tobytes(order="C")
        if bundle.read(port, destination)[: region.payload_bytes] != payload:
            raise ConvInstancePreflightError(f"3x3 first-tile physical {port} differs")
    return {
        "status": "golden_and_physical_3x3_tile_passed",
        "tile_id": f"{spec.node_id}-group0-k000-{spec.k_tile - 1:03d}",
        "group_id": 0,
        "destination_slice": destination,
        "high_ring_owners": list(ring.owners),
        "reduction_traversal": list(traversal),
        "logical_im2col_projection": {
            "M": spec.first_tile_spatial_count,
            "N": spec.k_tile,
            "K": spec.input_channels * 9,
        },
        "k_lifecycle": lifecycle,
        "comparisons": comparisons,
    }


def _build_3x3_preflight(
    root: Path,
    request: ConvTargetRequest,
    typed_execplan_validation: dict[str, Any],
    encoder_candidate_path: Path | None,
) -> dict[str, Any]:
    spec = request.spec
    values, layout, bundle = load_conv_instance_execution(root, spec)
    if not bundle.plan.activation_halo_staged:
        raise ConvInstancePreflightError("3x3 candidate did not select explicit halo staging")
    tile = _compare_3x3_first_tile(values, layout, bundle, request)

    golden = qlinear_conv_im2col(
        values["A"],
        values["B"],
        x_scale=values["x_scale"],
        x_zero_point=values["x_zero_point"],
        w_scale=values["w_scale"],
        w_zero_point=values["w_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        bias=values["bias"],
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
        group=spec.group,
    )
    full_comparisons = {
        "P": _comparison(golden.accumulator, values["P"]),
        "D": _comparison(golden.output, values["D"]),
    }
    if any(full_comparisons[port]["mismatch_count"] for port in ("P", "D")):
        raise ConvInstancePreflightError("3x3 full-operator P/D differs from W3")

    coordinates = (
        (0, 0, 0, 0),
        (0, spec.output_channels // 2, 0, 0),
        (0, spec.output_channels - 1, 0, 0),
        (0, 0, spec.output_height // 2, spec.output_width // 2),
        (
            spec.batch_size - 1,
            spec.output_channels - 1,
            spec.output_height - 1,
            spec.output_width - 1,
        ),
    )
    adapter = NdpRtl28FunctionalAdapter(
        root / "NDPFuncModel", timeout_seconds=120
    )
    coordinate_result = adapter.run_qlinear_conv_coordinates(
        layout, bundle, coordinates
    )
    coordinate_records: list[dict[str, Any]] = []
    for coordinate, observed_p, observed_d, probe_plan in zip(
        coordinates,
        coordinate_result.accumulators,
        coordinate_result.outputs,
        coordinate_result.probe_plans,
        strict=True,
    ):
        expected_p = int(values["P"][coordinate])
        expected_d = int(values["D"][coordinate])
        if observed_p != expected_p or observed_d != expected_d:
            raise ConvInstancePreflightError(f"3x3 NDP coordinate differs: {coordinate}")
        coordinate_records.append(
            {
                "coordinate": list(coordinate),
                "covered_by_config_bound_full_operator": True,
                "destination_slice": probe_plan.destination_owner,
                "source_slices": list(probe_plan.source_owners),
                "ring_segment_ends": list(probe_plan.probe.ring_segment_ends),
                "P": {"observed": observed_p, "golden": expected_p, "mismatch_count": 0},
                "D": {"observed": observed_d, "golden": expected_d, "mismatch_count": 0},
            }
        )

    exact_p = np.asarray([coordinate_result.accumulators[0]], dtype=np.int32)
    exact_p_golden = np.asarray([values["P"][coordinates[0]]], dtype=np.int32)
    exact_d = np.asarray([coordinate_result.outputs[0]], dtype=np.uint8)
    exact_d_golden = np.asarray([values["D"][coordinates[0]]], dtype=np.uint8)
    first_tile_comparisons = {
        port: {
            "dtype": record["dtype"],
            "element_count": record["element_count"],
            "mismatch_count": record["mismatch_count"],
            "actual_sha256": record["actual_sha256"],
            "golden_sha256": record["golden_sha256"],
        }
        for port, record in tile["comparisons"].items()
    }
    ordered_comparisons = [
        {
            "name": "single_coordinate",
            "P": _comparison(exact_p, exact_p_golden),
            "D": _comparison(exact_d, exact_d_golden),
        },
        {"name": "first_tile", **first_tile_comparisons},
        {"name": "full_operator", **full_comparisons},
    ]
    physical_writebacks = []
    for slice_id in range(bundle.plan.geometry.slice_count):
        physical_writebacks.append(
            {
                "slice_id": slice_id,
                "P_sha256": hashlib.sha256(bundle.read("P", slice_id)).hexdigest(),
                "D_sha256": hashlib.sha256(bundle.read("D", slice_id)).hexdigest(),
                "status": "canonical_golden_physical_bytes_bound",
            }
        )
    encoder = _load_json(request.accumulate_config_path.parent / "encoder_evidence.json")
    requant_manifest = _load_json(request.requant_manifest_path)
    execplan_path = request.preflight_path.parent / "execplan_request.json"
    config_bound = {
        "status": "accumulate_and_requant_configs_passed_with_execution_boundary",
        "request_schema": "0.3",
        "binding_scope": (
            "project static 3x3 config interpreter + NDPFuncModel physical PE "
            "coordinates + independent full-operator im2col; not bitstream execution"
        ),
        "ordered_comparisons": ordered_comparisons,
        "physical_writebacks": physical_writebacks,
        "coordinate_probes": coordinate_records,
        "execution_boundary": {
            "consumes_target_json": True,
            "consumes_requant_json": True,
            "consumes_target_bitstream": False,
            "cycle_accurate": False,
            "hardware_run_required_for_G6_G8": True,
        },
    }
    native_encoder_candidate = None
    if encoder_candidate_path is not None:
        expected_artifacts = {f"{spec.accumulate_hw_op_id}.config"} | {
            f"{spec.requant_hw_op_id}.shard-{index:02d}"
            for index in range(spec.requant_shard_count)
        }
        native_encoder_candidate = _bind_native_encoder_candidate(
            root,
            root / "ndp-sim-ref",
            encoder_candidate_path,
            expected_node_id=spec.node_id,
            expected_typed_request_sha256=sha256_file(execplan_path),
            expected_artifact_ids=expected_artifacts,
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "status": "candidate_config_and_config_bound_pd_passed",
        "identity": {
            "node_id": spec.node_id,
            "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
            "hardware_status": "not_run_candidate_only",
        },
        "instance_spec": spec.to_dict(),
        "source_identity": {
            "typed_contract": {
                "path": "contracts/typed_config_parameter_contract.json",
                "sha256": sha256_file(root / "contracts/typed_config_parameter_contract.json"),
            },
            "ndp_source_commit": _locked_repository_commit(root, "NDPFuncModel"),
            "target_config_commit": encoder["repository_commit"],
        },
        "configs": {
            "accumulate": {
                "path": request.accumulate_config_relative,
                "sha256": sha256_file(request.accumulate_config_path),
            },
            "semantics": {
                "path": request.semantic_contract_relative,
                "sha256": sha256_file(request.semantic_contract_path),
            },
            "requant_manifest": {
                "path": f"{request.requant_root_relative}/manifest.json",
                "sha256": sha256_file(request.requant_manifest_path),
                "shard_count": spec.requant_shard_count,
                "covered_channels": requant_manifest["coverage"]["covered_channels"],
                "flush_count_per_logical_output": requant_manifest["coverage"][
                    "flush_count_per_logical_output"
                ],
            },
            "typed_execplan_request": {
                "path": execplan_path.relative_to(root).as_posix(),
                "sha256": sha256_file(execplan_path),
                "status": typed_execplan_validation["status"],
                "operator_count": typed_execplan_validation["operator_count"],
                "config_artifact_count": typed_execplan_validation[
                    "config_artifact_count"
                ],
            },
        },
        "official_encoder": encoder,
        "physical_plan": {
            "profile_id": bundle.plan.profile_id,
            "slice_count": bundle.plan.geometry.slice_count,
            "c_tile": bundle.plan.c_tile,
            "k_tile": bundle.plan.k_tile,
            "per_slice_used_bytes": bundle.plan.per_slice_used_bytes,
            "per_slice_capacity_bytes": bundle.plan.per_slice_capacity_bytes,
            "activation_halo_staged": bundle.plan.activation_halo_staged,
            "activation_halo_shape": list(bundle.plan.port("A").physical_shape),
            "layout_validation": layout.validate(bundle),
        },
        "first_tile": tile,
        "single_coordinate": coordinate_records[0],
        "selected_output_channel_samples": coordinate_records[:3],
        "config_bound_comparison": config_bound,
        **(
            {"native_encoder_candidate": native_encoder_candidate}
            if native_encoder_candidate is not None
            else {}
        ),
        "gate_state": {
            "e1_candidate_passed": True,
            "hardware_passed": False,
            "g5_passed": False,
            "g6_passed": False,
            "g8_passed": False,
            "execplan_typed_transport_passed": True,
        },
    }
    validate_conv_instance_preflight(report, request)
    return report


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvInstancePreflightError(f"JSON root must be an object: {path}")
    return value


def _selected_output_channel_samples(
    values: dict[str, np.ndarray],
    layout: Any,
    bundle: Any,
    request: ConvTargetRequest,
) -> list[dict[str, Any]]:
    spec = request.spec
    channels = sorted({0, spec.output_channels // 2, spec.output_channels - 1})
    activation = values["A"][0, :, 0, 0].astype(np.int64)
    x_zero_point = int(values["x_zero_point"].reshape(-1)[0])
    output_zero_point = values["y_zero_point"]
    samples = []
    for channel in channels:
        weight = values["B"][channel, :, 0, 0].astype(np.int64)
        weight_zero_point = int(values["w_zero_point"][channel])
        accumulator = int(values["bias"][channel]) + int(
            np.dot(
                activation - x_zero_point,
                weight - weight_zero_point,
            )
        )
        expected_p = int(values["P"][0, channel, 0, 0])
        multiplier = np.asarray(
            [
                np.float32(values["x_scale"][0])
                * np.float32(values["w_scale"][channel])
                / np.float32(values["y_scale"][0])
            ],
            dtype=np.float32,
        )
        observed_d = int(
            requantize_uint8(
                np.asarray([[[[accumulator]]]], dtype=np.int32),
                multiplier,
                output_zero_point,
            )[0, 0, 0, 0]
        )
        expected_d = int(values["D"][0, channel, 0, 0])
        coordinate = (0, channel, 0, 0)
        p_address = layout.explain_coordinate(
            bundle, bundle.tensor_ids["P"], coordinate
        )[0]["address"]
        d_address = layout.explain_coordinate(
            bundle, bundle.tensor_ids["D"], coordinate
        )[0]["address"]
        samples.append(
            {
                "coordinate": list(coordinate),
                "P": {
                    "observed": accumulator,
                    "golden": expected_p,
                    "mismatch_count": int(accumulator != expected_p),
                    "physical_address": int(p_address),
                },
                "D": {
                    "observed": observed_d,
                    "golden": expected_d,
                    "mismatch_count": int(observed_d != expected_d),
                    "physical_address": int(d_address),
                },
                "covered_by_config_bound_full_operator": True,
            }
        )
    if any(
        item[port]["mismatch_count"]
        for item in samples
        for port in ("P", "D")
    ):
        raise ConvInstancePreflightError("selected output-channel P/D sample differs")
    return samples


def build_conv_instance_preflight(
    project_root: Path,
    node_id: str,
    encoder_candidate_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    request = build_conv_target_request(root, node_id)
    spec = request.spec
    if spec.node_id == "node-0004":
        raise ConvInstancePreflightError(
            "the hardware-frozen first instance uses build_w5_first_conv_preflight"
        )
    typed_execplan = build_conv_execplan_request(root, node_id)
    typed_execplan_validation = validate_conv_execplan_request(
        typed_execplan, root, expected_node_id=node_id
    )
    typed_execplan_payload = canonical_execplan_bytes(typed_execplan)
    typed_execplan_path = request.preflight_path.parent / "execplan_request.json"
    if (
        not typed_execplan_path.is_file()
        or typed_execplan_path.read_bytes() != typed_execplan_payload
    ):
        raise ConvInstancePreflightError("candidate typed execplan request differs")
    if (
        spec.kernel == (3, 3)
        and spec.strides == (1, 1)
        and spec.pads == (1, 1, 1, 1)
        and spec.dilations == (1, 1)
    ):
        return _build_3x3_preflight(
            root, request, typed_execplan_validation, encoder_candidate_path
        )
    values, layout, bundle = load_conv_instance_execution(root, spec)
    tile = _compare_tile(values, layout, bundle, spec)
    baseline_macs = 16 * 64 * 64 * 56 * 56
    instance_macs = (
        spec.batch_size
        * spec.output_channels
        * spec.output_height
        * spec.output_width
        * spec.input_channels
    )
    timeout_seconds = 60 * max(1, math.ceil(instance_macs / baseline_macs))
    coordinate, closure = _compare_ndp_target_config(
        root,
        values,
        layout,
        bundle,
        request,
        timeout_seconds=timeout_seconds,
    )
    channel_samples = _selected_output_channel_samples(
        values, layout, bundle, request
    )
    evidence_path = request.accumulate_config_path.parent / "encoder_evidence.json"
    encoder = _load_json(evidence_path)
    requant_manifest = _load_json(request.requant_manifest_path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "status": "candidate_config_and_config_bound_pd_passed",
        "identity": {
            "node_id": spec.node_id,
            "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
            "hardware_status": "not_run_candidate_only",
        },
        "instance_spec": spec.to_dict(),
        "source_identity": {
            "typed_contract": {
                "path": "contracts/typed_config_parameter_contract.json",
                "sha256": sha256_file(
                    root / "contracts" / "typed_config_parameter_contract.json"
                ),
            },
            "ndp_source_commit": coordinate["source_commit"],
            "target_config_commit": encoder["repository_commit"],
        },
        "configs": {
            "accumulate": {
                "path": request.accumulate_config_relative,
                "sha256": sha256_file(request.accumulate_config_path),
            },
            "semantics": {
                "path": request.semantic_contract_relative,
                "sha256": sha256_file(request.semantic_contract_path),
            },
            "requant_manifest": {
                "path": f"{request.requant_root_relative}/manifest.json",
                "sha256": sha256_file(request.requant_manifest_path),
                "shard_count": spec.requant_shard_count,
                "covered_channels": requant_manifest["coverage"]["covered_channels"],
                "flush_count_per_logical_output": requant_manifest["coverage"][
                    "flush_count_per_logical_output"
                ],
            },
            "typed_execplan_request": {
                "path": (
                    f"artifacts/w5/{spec.accumulate_hw_op_id}/execplan_request.json"
                ),
                "sha256": sha256_file(typed_execplan_path),
                "status": typed_execplan_validation["status"],
                "operator_count": typed_execplan_validation["operator_count"],
                "config_artifact_count": typed_execplan_validation[
                    "config_artifact_count"
                ],
            },
        },
        "official_encoder": encoder,
        "physical_plan": {
            "profile_id": bundle.plan.profile_id,
            "slice_count": bundle.plan.geometry.slice_count,
            "c_tile": bundle.plan.c_tile,
            "k_tile": bundle.plan.k_tile,
            "per_slice_used_bytes": bundle.plan.per_slice_used_bytes,
            "per_slice_capacity_bytes": bundle.plan.per_slice_capacity_bytes,
            "layout_validation": layout.validate(bundle),
        },
        "first_tile": tile,
        "single_coordinate": coordinate,
        "selected_output_channel_samples": channel_samples,
        "config_bound_comparison": closure,
        "gate_state": {
            "e1_candidate_passed": True,
            "hardware_passed": False,
            "g5_passed": False,
            "g6_passed": False,
            "g8_passed": False,
            "execplan_typed_transport_passed": True,
        },
    }
    validate_conv_instance_preflight(report, request)
    return report


def validate_conv_instance_preflight(
    report: dict[str, Any],
    request: ConvTargetRequest,
) -> None:
    spec = request.spec
    if (
        report.get("schema_version") != SCHEMA_VERSION
        or report.get("report_kind") != REPORT_KIND
        or report.get("status") != "candidate_config_and_config_bound_pd_passed"
    ):
        raise ConvInstancePreflightError("candidate Conv report identity differs")
    if report.get("identity") != {
        "node_id": spec.node_id,
        "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
        "hardware_status": "not_run_candidate_only",
    }:
        raise ConvInstancePreflightError("candidate Conv instance identity differs")
    if report.get("instance_spec") != spec.to_dict():
        raise ConvInstancePreflightError("candidate Conv spec differs from typed source")
    configs = report.get("configs", {})
    if (
        configs.get("accumulate", {}).get("sha256")
        != sha256_file(request.accumulate_config_path)
        or configs.get("semantics", {}).get("sha256")
        != sha256_file(request.semantic_contract_path)
        or configs.get("requant_manifest", {}).get("sha256")
        != sha256_file(request.requant_manifest_path)
        or configs.get("requant_manifest", {}).get("shard_count")
        != spec.requant_shard_count
        or configs.get("requant_manifest", {}).get("covered_channels")
        != list(range(spec.output_channels))
        or configs.get("requant_manifest", {}).get("flush_count_per_logical_output")
        != 1
        or configs.get("typed_execplan_request", {}).get("sha256")
        != sha256_file(request.preflight_path.parent / "execplan_request.json")
        or configs.get("typed_execplan_request", {}).get("status")
        != "typed_transport_validated"
        or configs.get("typed_execplan_request", {}).get("operator_count") != 2
        or configs.get("typed_execplan_request", {}).get("config_artifact_count")
        != spec.requant_shard_count
        + (4 if request.requant_encoder_contract_path.is_file() else 3)
    ):
        raise ConvInstancePreflightError("candidate Conv config binding differs")
    encoder = report.get("official_encoder", {})
    expected_connection_count = 42 if spec.kernel == (3, 3) else 46
    if (
        encoder.get("connection_count") != expected_connection_count
        or encoder.get("constraint_cost") != 0
        or encoder.get("repeat_count") != 2
        or encoder.get("repeat_outputs_identical") is not True
        or set(encoder.get("outputs", {}))
        != {
            "mapping_review.json",
            "parsed_bitstream.txt",
            "modules_dump_64b.bin",
            "modules_dump_128b.bin",
            "detailed_dump.txt",
        }
    ):
        raise ConvInstancePreflightError("candidate Conv official encoder evidence differs")
    native_candidate = report.get("native_encoder_candidate")
    if native_candidate is not None:
        expected_artifacts = [f"{spec.accumulate_hw_op_id}.config"] + [
            f"{spec.requant_hw_op_id}.shard-{index:02d}"
            for index in range(spec.requant_shard_count)
        ]
        if (
            not isinstance(native_candidate, dict)
            or native_candidate.get("status")
            != "native_encoder_double_run_validated_and_bound"
            or native_candidate.get("node_id") != spec.node_id
            or native_candidate.get("typed_request_sha256")
            != configs.get("typed_execplan_request", {}).get("sha256")
            or native_candidate.get("record_count") != len(expected_artifacts)
            or native_candidate.get("config_artifact_ids") != expected_artifacts
            or native_candidate.get("repeat_outputs_identical") is not True
            or len(str(native_candidate.get("candidate_id", ""))) != 64
            or len(str(native_candidate.get("manifest_sha256", ""))) != 64
            or len(str(native_candidate.get("native_source_tree_sha256", ""))) != 64
            or len(str(native_candidate.get("address_plan_sha256", ""))) != 64
            or not isinstance(native_candidate.get("address_plan_size_bytes"), int)
            or native_candidate.get("address_plan_size_bytes", 0) <= 0
        ):
            raise ConvInstancePreflightError(
                "candidate Conv native encoder binding differs"
            )
    tile = report.get("first_tile", {})
    lifecycle = tile.get("k_lifecycle", [])
    if (
        sum(item.get("channel_count", 0) for item in lifecycle)
        != spec.input_channels
        or [item.get("phase") for item in lifecycle]
        != ["first", "middle", "middle", "last"]
        or any(
            tile.get("comparisons", {}).get(port, {}).get("mismatch_count") != 0
            for port in ("P", "D")
        )
    ):
        raise ConvInstancePreflightError("candidate Conv first-tile lifecycle/P/D differs")
    comparisons = report.get("config_bound_comparison", {}).get(
        "ordered_comparisons", []
    )
    if (
        [item.get("name") for item in comparisons]
        != ["single_coordinate", "first_tile", "full_operator"]
        or any(
            item.get(port, {}).get("mismatch_count") != 0
            or item.get(port, {}).get("actual_sha256")
            != item.get(port, {}).get("golden_sha256")
            for item in comparisons
            for port in ("P", "D")
        )
        or len(
            report.get("config_bound_comparison", {}).get(
                "physical_writebacks", []
            )
        )
        != 28
    ):
        raise ConvInstancePreflightError("candidate Conv config-bound P/D differs")
    samples = report.get("selected_output_channel_samples", [])
    expected_sample_channels = sorted(
        {0, spec.output_channels // 2, spec.output_channels - 1}
    )
    if (
        [item.get("coordinate") for item in samples]
        != [[0, channel, 0, 0] for channel in expected_sample_channels]
        or any(
            item.get("covered_by_config_bound_full_operator") is not True
            or item.get(port, {}).get("mismatch_count") != 0
            for item in samples
            for port in ("P", "D")
        )
    ):
        raise ConvInstancePreflightError("candidate Conv channel samples differ")
    gate = report.get("gate_state", {})
    if gate != {
        "e1_candidate_passed": True,
        "hardware_passed": False,
        "g5_passed": False,
        "g6_passed": False,
        "g8_passed": False,
        "execplan_typed_transport_passed": True,
    }:
        raise ConvInstancePreflightError("candidate Conv gate boundary differs")


__all__ = [
    "ConvInstancePreflightError",
    "build_conv_instance_preflight",
    "validate_conv_instance_preflight",
]
