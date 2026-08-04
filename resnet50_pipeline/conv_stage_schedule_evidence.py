from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .node0004_semantic_contract import validate_node0004_semantic_contract
from .operator_config_validator import OperatorConfigValidator
from .r5_lowering_bundle import validate_r5_lowering_bundle


SCHEMA = "resnet50-conv-stage-schedule-evidence-v1"
REQUEST_ID = "r5:hwop-0004-00"
OP_TYPE = "node0004_accumulate_wave0_nopp_r1"


class ConvStageScheduleEvidenceError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConvStageScheduleEvidenceError(
            f"cannot parse JSON evidence: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ConvStageScheduleEvidenceError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ConvStageScheduleEvidenceError(f"missing Conv evidence: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _only(items: list[Any], *, label: str) -> Mapping[str, Any]:
    matches = [item for item in items if isinstance(item, Mapping)]
    if len(matches) != 1:
        raise ConvStageScheduleEvidenceError(f"expected exactly one {label}")
    return matches[0]


def _stream_summary(stage: Mapping[str, Any]) -> dict[str, Any]:
    streams = stage.get("streams")
    if not isinstance(streams, list):
        raise ConvStageScheduleEvidenceError("request-address stream facts are missing")
    expected = {
        "A": ("READ_STREAM0", "read", 64, 1_024),
        "B": ("READ_STREAM1", "read", 12_544, 200_704),
        "C": ("READ_STREAM3", "read", 1_568, 25_088),
        "D": ("WRITE_STREAM0", "write", 12_544, 200_704),
    }
    result: dict[str, Any] = {}
    for target, (
        resource,
        mode,
        requests_per_slice,
        payload_bytes_with_multiplicity,
    ) in expected.items():
        records = [
            item
            for item in streams
            if isinstance(item, Mapping) and item.get("target") == target
        ]
        if len(records) != 28:
            raise ConvStageScheduleEvidenceError(
                f"expected 28 request-address records for target {target}"
            )
        for item in records:
            if (
                item.get("resource") != resource
                or item.get("mode") != mode
                or item.get("request_count_with_multiplicity")
                != requests_per_slice
                or item.get("logical_payload_byte_count_with_multiplicity")
                != payload_bytes_with_multiplicity
                or item.get("padding_masked_byte_count_with_multiplicity") != 0
            ):
                raise ConvStageScheduleEvidenceError(
                    f"request-address facts differ for target {target}"
                )
        result[target] = {
            "resource": resource,
            "mode": mode,
            "slice_record_count": len(records),
            "request_count_per_slice_with_multiplicity": requests_per_slice,
            "logical_payload_bytes_per_slice_with_multiplicity": (
                payload_bytes_with_multiplicity
            ),
            "padding_masked_bytes_per_slice_with_multiplicity": 0,
            "unique_request_counts": sorted(
                {int(item["unique_request_count"]) for item in records}
            ),
        }
    if len(streams) != 28 * len(expected):
        raise ConvStageScheduleEvidenceError("unexpected Conv request-address stream")
    return result


def build_conv_stage_schedule_evidence(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_rel = "contracts/resnet50_r5_lowering_bundle.json"
    strict_rel = (
        "configs/native_ndp_sim/"
        "node0004_accumulate_wave0_nopp_r1_strict_v1/config.json"
    )
    semantic_rel = "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"
    graph_rel = (
        "ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph/"
        "node0004_accumulate_wave0_nopp_r1_graph_withbaseaddr.json"
    )
    mapping_rel = (
        "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1"
    )
    execplan_rel = (
        "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "node0004-nopp-r1-v2"
    )
    input_rel = (
        "artifacts/operator_config_validation/r5-server-candidates/"
        "node0004-nopp-r1-v2/node0004_accumulate_wave0_nopp_r1_input_manifest.json"
    )
    hardware_rel = "contracts/operator_config/ndpsim_json_hardware_evidence_v1.json"

    lowering = _load(root / lowering_rel)
    validate_r5_lowering_bundle(lowering, root)
    requests = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == REQUEST_ID
    ]
    request = _only(requests, label=REQUEST_ID)
    resolutions = [
        item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping) and item.get("request_id") == REQUEST_ID
    ]
    resolution = _only(resolutions, label=f"{REQUEST_ID} effective resolution")
    expected_geometry = {
        "attributes": {
            "auto_pad": "NOTSET",
            "dilations": [1, 1],
            "group": 1,
            "kernel_shape": [1, 1],
            "pads": [0, 0, 0, 0],
            "strides": [1, 1],
        },
        "input_dtypes": ["uint8", "uint8", "int8", "int8", "int32"],
        "input_shapes": [
            [16, 64, 56, 56],
            [1],
            [64, 64, 1, 1],
            [64],
            [64],
        ],
        "output_dtypes": ["int32"],
        "output_shapes": [[16, 64, 56, 56]],
    }
    if (
        request.get("identity", {}).get("hw_op_type") != "ConvInt32Accumulate"
        or request.get("identity", {}).get("node_id") != "node-0004"
        or request.get("logical_geometry") != expected_geometry
    ):
        raise ConvStageScheduleEvidenceError(
            "node-0004 lowering request signature differs"
        )

    strict_path = root / strict_rel
    config = _load(strict_path)
    strict_report = OperatorConfigValidator().validate(
        config,
        source=str(strict_path),
        development_mode=True,
        expected_sa_transpose=False,
    )
    if not strict_report.valid:
        raise ConvStageScheduleEvidenceError(
            f"strict Conv seed differs: {strict_report.to_dict()['first_error']}"
        )
    special = config.get("special_array")
    if not isinstance(special, Mapping):
        raise ConvStageScheduleEvidenceError("Conv special_array is missing")
    if (
        special.get("mode") != "gemm"
        or special.get("data_type") != "int8"
        or special.get("bias_enable") != 1
        or special.get("outport", {}).get("mode") != "col"
    ):
        raise ConvStageScheduleEvidenceError("Conv special-array mode differs")
    sa_inports: dict[str, Any] = {}
    for name in ("inport0", "inport1", "inport2"):
        item = special.get(name)
        if (
            not isinstance(item, Mapping)
            or item.get("enable") != 1
            or item.get("pingpong_en") != 0
            or item.get("pingpong_last_index") is not None
        ):
            raise ConvStageScheduleEvidenceError(f"Conv {name} topology differs")
        sa_inports[name] = deepcopy(dict(item))

    streams = config.get("stream_engine")
    if not isinstance(streams, Mapping):
        raise ConvStageScheduleEvidenceError("Conv stream_engine is missing")
    expected_streams = {
        "A": ("stream0", "read", 1_024),
        "B": ("stream1", "read", 200_704),
        "C": ("stream3", "read", 64),
        "D": ("stream4", "write", 200_704),
    }
    stream_contract: dict[str, Any] = {}
    for target, (name, mode, logical_bytes) in expected_streams.items():
        item = streams.get(name)
        if (
            not isinstance(item, Mapping)
            or item.get("target") != target
            or item.get("mode") != mode
            or item.get("ping_pong") != 0
        ):
            raise ConvStageScheduleEvidenceError(
                f"Conv stream binding differs for target {target}"
            )
        stream_contract[target] = {
            "stream": name,
            "mode": mode,
            "logical_tensor_bytes_per_tile": logical_bytes,
            "relative_base_addr": item.get("base_addr"),
            "idx": deepcopy(item.get("idx")),
            "idx_size_encoded": deepcopy(item.get("idx_size")),
            "dim_stride_bytes": deepcopy(item.get("dim_stride")),
            "buffer_index_mode": deepcopy(item.get("buf_idx_mode")),
            "buffer_spatial_size": item.get("buf_spatial_size"),
            "ping_pong": item.get("ping_pong"),
        }
    if len(streams) != 4:
        raise ConvStageScheduleEvidenceError("unexpected Conv stream topology")

    semantic = _load(root / semantic_rel)
    validate_node0004_semantic_contract(
        semantic,
        root,
        graph_withbaseaddr=root / graph_rel,
        mapping_bundle=root / mapping_rel,
    )
    mapping = _load(root / mapping_rel / "bundle_manifest.json")
    if (
        mapping.get("summary", {}).get("valid") is not True
        or mapping.get("summary", {}).get("penalty") != 0.0
        or mapping.get("summary", {}).get("fallback_used") is not False
    ):
        raise ConvStageScheduleEvidenceError(
            "Conv mapping evidence is not exact zero penalty"
        )

    execplan = _load(root / execplan_rel / "bundle_manifest.json")
    address_report = _load(
        root / execplan_rel / "request_address_validation_report.json"
    )
    if (
        execplan.get("double_run", {}).get("equal") is not True
        or execplan.get("validation_report", {}).get("valid") is not True
        or execplan.get("package_validation_report", {}).get("valid") is not True
        or execplan.get("request_address_validation_report", {}).get("valid")
        is not True
        or address_report.get("valid") is not True
        or execplan.get("request_address_validation_report", {}).get("sha256")
        != sha256_file(
            root / execplan_rel / "request_address_validation_report.json"
        )
    ):
        raise ConvStageScheduleEvidenceError("Conv execplan evidence differs")
    stages = address_report.get("facts", {}).get("stages")
    stage = _only(stages if isinstance(stages, list) else [], label="Conv stage")
    enabled_slices = stage.get("enabled_slices")
    if (
        stage.get("op_type") != OP_TYPE
        or enabled_slices != list(range(28))
        or address_report.get("facts", {}).get("request_count_with_multiplicity")
        != 748_160
        or address_report.get("facts", {}).get("unique_request_address_count")
        != 704_368
    ):
        raise ConvStageScheduleEvidenceError("Conv request-address summary differs")
    request_streams = _stream_summary(stage)

    input_manifest = _load(root / input_rel)
    records = input_manifest.get("records")
    if (
        input_manifest.get("operator_type") != OP_TYPE
        or input_manifest.get("wave_index") != 0
        or input_manifest.get("used_slices") != 28
        or input_manifest.get("logical_samples") != [0, 3, 6, 8, 10, 12, 14]
        or not isinstance(records, list)
        or len(records) != 28
    ):
        raise ConvStageScheduleEvidenceError("Conv wave-0 input manifest differs")
    assignments = []
    group_counts: Counter[int] = Counter()
    for slice_id, item in enumerate(records):
        if not isinstance(item, Mapping) or item.get("slice_id") != slice_id:
            raise ConvStageScheduleEvidenceError("Conv slice assignment differs")
        group_id = int(item["group_id"])
        group_counts[group_id] += 1
        assignments.append(
            {
                "slice_id": slice_id,
                "group_id": group_id,
                "owner_step": int(item["owner_step"]),
                "logical_sample": int(item["logical_sample"]),
                "local_sample_slot": int(item["local_sample_slot"]),
            }
        )
    if group_counts != Counter({index: 4 for index in range(7)}):
        raise ConvStageScheduleEvidenceError(
            "Conv wave-0 must cover four K16 tiles for each of seven samples"
        )

    hardware = _load(root / hardware_rel)
    hardware_records = [
        item
        for item in hardware.get("records", [])
        if isinstance(item, Mapping)
        and item.get("path")
        == "ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json"
    ]
    hardware_record = _only(hardware_records, label="node-0004 hardware audit")
    exact = hardware_record.get("exact_config_evidence")
    reference_correctness = hardware_record.get(
        "reference_configuration_correctness"
    )
    if (
        not isinstance(exact, Mapping)
        or exact.get("evidence_level") != "hardware-attempt-invalid"
        or exact.get("positive_hardware_test") is not False
        or exact.get("numeric_hardware_test") is not False
        or not isinstance(reference_correctness, Mapping)
        or reference_correctness.get("accepted_as_correct_reference") is not False
    ):
        raise ConvStageScheduleEvidenceError(
            "node-0004 hardware evidence boundary differs"
        )

    logical_tile_count = 16 * (64 // 16)
    evidenced_tile_count = len(assignments)
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "project_added_wave0_static_evidence_full_conv_schedule_blocked",
        "request": {
            "request_id": REQUEST_ID,
            "request_sha256": request["request_sha256"],
            "identity": deepcopy(request["identity"]),
            "logical_geometry": deepcopy(request["logical_geometry"]),
        },
        "evidence": {
            "lowering_bundle": _binding(root, lowering_rel),
            "strict_config": _binding(root, strict_rel),
            "semantic_contract": _binding(root, semantic_rel),
            "mapping_bundle": _binding(root, f"{mapping_rel}/bundle_manifest.json"),
            "execplan_bundle": _binding(root, f"{execplan_rel}/bundle_manifest.json"),
            "request_address_report": _binding(
                root, f"{execplan_rel}/request_address_validation_report.json"
            ),
            "wave0_input_manifest": _binding(root, input_rel),
            "hardware_evidence_audit": _binding(root, hardware_rel),
        },
        "logical_schedule": {
            "batch_count": 16,
            "input_channels": 64,
            "output_channels": 64,
            "kernel": [1, 1],
            "output_spatial": [56, 56],
            "output_channel_tile": 16,
            "output_channel_tile_count": 4,
            "full_logical_tile_count": logical_tile_count,
            "evidenced_wave_index": 0,
            "evidenced_logical_samples": deepcopy(
                input_manifest["logical_samples"]
            ),
            "evidenced_tile_count": evidenced_tile_count,
            "unevidenced_tile_count": logical_tile_count - evidenced_tile_count,
            "full_three_wave_schedule_proven": False,
        },
        "wave0_slice_assignments": assignments,
        "physical_contract": {
            "layout": {
                "A": "signed int8 weights; K16 x C64; K-major/C-minor",
                "B": "unsigned uint8 activation; one logical sample; HWC C64",
                "C": "int32 bias; local K16",
                "D": "int32 partial sum; one logical sample; HWK-local K16",
            },
            "special_array": {
                "mode": special["mode"],
                "data_type": special["data_type"],
                "bias_enable": special["bias_enable"],
                "outport_mode_json_label": special["outport"]["mode"],
                "inports": sa_inports,
            },
            "streams": stream_contract,
            "request_address_facts": {
                "enabled_slice_count": len(enabled_slices),
                "request_count_with_multiplicity": address_report["facts"][
                    "request_count_with_multiplicity"
                ],
                "unique_request_address_count": address_report["facts"][
                    "unique_request_address_count"
                ],
                "per_target": request_streams,
            },
            "mapping": {
                "valid": mapping["summary"]["valid"],
                "penalty": mapping["summary"]["penalty"],
                "fallback_used": mapping["summary"]["fallback_used"],
                "unpadded_bits": mapping["summary"]["unpadded_bits"],
            },
        },
        "emission_gate": {
            "candidate_config_emission_allowed": False,
            "reference_wave0_config_accepted_correct": False,
            "reference_configuration_evidence_class": reference_correctness[
                "evidence_class"
            ],
            "authority_resolves_reference_template_semantics": [],
            "lowering_overlay_update_pending": False,
            "effective_unresolved_blockers": deepcopy(
                resolution.get("unresolved_blockers", [])
            ),
            "additional_backend_blockers": [
                "B_CONV_FULL_3WAVE_SCHEDULE",
                "B_CONV_DERIVED_WAVES_VALIDATION",
            ],
            "hardware_attempt_status": exact["status"],
            "positive_hardware_test_proven": False,
            "numeric_hardware_test_proven": False,
            "claim_boundary": (
                "This node0004 config was added after the pinned upstream commit "
                "and is not covered by the upstream-tested authority. Its static "
                "28-of-64 schedule and layout facts are useful diagnostic evidence, "
                "but its correctness and the remaining waves both require validation."
            ),
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def validate_conv_stage_schedule_evidence(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_conv_stage_schedule_evidence(project_root):
        raise ConvStageScheduleEvidenceError(
            "Conv stage schedule evidence differs from current inputs"
        )


def write_conv_stage_schedule_evidence(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "ConvStageScheduleEvidenceError",
    "SCHEMA",
    "build_conv_stage_schedule_evidence",
    "validate_conv_stage_schedule_evidence",
    "write_conv_stage_schedule_evidence",
]
