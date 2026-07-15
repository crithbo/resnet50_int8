from __future__ import annotations

import json
import math
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
from .hashing import sha256_file
from .w5_conv_preflight import (
    _compare_ndp_target_config,
    _compare_tile,
    load_conv_instance_execution,
)


SCHEMA_VERSION = "0.1"
REPORT_KIND = "typed_conv_instance_candidate_preflight"


class ConvInstancePreflightError(ValueError):
    """A candidate Conv instance failed a required configuration/numerical gate."""


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
        != spec.requant_shard_count + 3
    ):
        raise ConvInstancePreflightError("candidate Conv config binding differs")
    encoder = report.get("official_encoder", {})
    if (
        encoder.get("connection_count") != 46
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
