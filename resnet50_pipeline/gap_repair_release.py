from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .gap_ga_rtl_repair import (
    REPAIR_ID,
    int32_feedback_allowed,
    repaired_outbuffer_count,
    repaired_sources,
)
from .gap_native_package import (
    OP_ID,
    OP_TYPE,
    SLICE_COUNT,
    TRANSPORT_REL,
    validate_gap_native_transport,
)
from .gap_repair_workload import (
    ADDRESS_BOUND_CONFIG_REL,
    derive_address_bound_d_index_config,
    validate_address_bound_d_index_config,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-gap-repair-release-gate-v1"
DEFAULT_EXECPLAN_REL = Path(
    "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "gap-hwop0071-sum-d-index-v4"
)
DEFAULT_RTL_REPAIR_REL = Path(
    "artifacts/operator_config_validation/r5-gap-ga-rtl-repair-v1"
)
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-gap-repair-release-v9"
)

RULE_D_COVERAGE = "CDA-GAP-D-READBACK-COVERAGE-001"
RULE_GA_OCCUPANCY = "CDA-GA-OUTBUFFER-OCCUPANCY-001"
RULE_GA_INVALID_SLOT = "CDA-GA-INVALID-SLOT-ISOLATION-001"
RULE_GA_CROSS_BLOCK = "CDA-GA-CROSS-BLOCK-INIT-001"
RULE_ORTHOGONAL = "CDA-GAP-ORTHOGONAL-DEFECTS-001"
RULE_MONITOR = "CDA-MSE4-MONITOR-EVIDENCE-001"
RULE_IDENTITY = "CDA-SERVER-FOCUSED-IDENTITY-001"


class GapRepairReleaseError(ValueError):
    pass


_RELEASE_GATE_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapRepairReleaseError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = resolved.as_posix()
    return {
        "path": relative,
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def _line_count_128bit(path: Path) -> int:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or b"\r" in raw:
        raise GapRepairReleaseError(f"128-bit payload is not LF-only: {path}")
    lines = raw[:-1].split(b"\n")
    if not lines:
        raise GapRepairReleaseError(f"128-bit payload is empty: {path}")
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise GapRepairReleaseError(
                f"invalid 128-bit payload line: {path}:{index}"
            )
    return len(lines)


def _validate_repair_receipt(root: Path, repair_root: Path) -> dict[str, Any]:
    manifest_path = repair_root / "RTL_PATCH_MANIFEST.json"
    manifest = _load(manifest_path)
    receipt = manifest.pop("manifest_sha256", None)
    if receipt != sha256_bytes(canonical_json_bytes(manifest)):
        raise GapRepairReleaseError("RTL repair manifest receipt differs")
    manifest["manifest_sha256"] = receipt
    expected_sources = repaired_sources(root)
    if (
        manifest.get("repair_id") != REPAIR_ID
        or manifest.get("local_syntax_check", {}).get("passed") is not True
        or set(manifest.get("files", {}))
        != {path.as_posix() for path in expected_sources}
    ):
        raise GapRepairReleaseError("RTL repair identity or syntax receipt differs")
    for relative, expected_text in expected_sources.items():
        patched = repair_root / relative
        record = manifest["files"][relative.as_posix()]
        if (
            patched.read_text(encoding="utf-8") != expected_text
            or record.get("patched_sha256") != sha256_file(patched)
            or record.get("source_sha256") != sha256_file(root / "NDP_copy01" / relative)
        ):
            raise GapRepairReleaseError(f"RTL repair file differs: {relative}")
    return manifest


def _write_streams(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    stages = report.get("facts", {}).get("stages")
    if not isinstance(stages, list) or len(stages) != 1:
        raise GapRepairReleaseError("GAP request report must contain one stage")
    stage = stages[0]
    if (
        not isinstance(stage, Mapping)
        or stage.get("op_id") != OP_ID
        or stage.get("op_type") != OP_TYPE
        or stage.get("enabled_slices") != list(range(SLICE_COUNT))
    ):
        raise GapRepairReleaseError("GAP request stage identity differs")
    streams = stage.get("streams")
    if not isinstance(streams, list):
        raise GapRepairReleaseError("GAP request streams are missing")
    writes = [
        dict(item)
        for item in streams
        if isinstance(item, Mapping)
        and item.get("resource") == "WRITE_STREAM0"
        and item.get("target") == "D"
        and item.get("mode") == "write"
    ]
    if len(writes) != SLICE_COUNT:
        raise GapRepairReleaseError(
            f"GAP request report has {len(writes)} D streams, expected {SLICE_COUNT}"
        )
    return sorted(writes, key=lambda item: int(item["execution_slice"]))


def build_gap_repair_release_gate(
    project_root: Path,
    *,
    execplan_root: Path | None = None,
    rtl_repair_root: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    exec_root = (
        execplan_root.resolve()
        if execplan_root is not None
        else (root / DEFAULT_EXECPLAN_REL).resolve()
    )
    repair_root = (
        rtl_repair_root.resolve()
        if rtl_repair_root is not None
        else (root / DEFAULT_RTL_REPAIR_REL).resolve()
    )
    cache_key = (root.as_posix(), exec_root.as_posix(), repair_root.as_posix())
    cached = _RELEASE_GATE_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    config_root = root / ADDRESS_BOUND_CONFIG_REL
    config_manifest = validate_address_bound_d_index_config(root, config_root)
    config, config_analysis = derive_address_bound_d_index_config(root)
    repair = _validate_repair_receipt(root, repair_root)
    transport = validate_gap_native_transport(root, root / TRANSPORT_REL)

    exec_manifest_path = exec_root / "bundle_manifest.json"
    exec_manifest = _load(exec_manifest_path)
    request_path = exec_root / "request_address_validation_report.json"
    request = _load(request_path)
    pipeline = exec_root / "pipeline_output"
    graph_paths = list(pipeline.glob("*_withbaseaddr.json"))
    if len(graph_paths) != 1:
        raise GapRepairReleaseError("rebuilt GAP execplan must have one bound graph")
    graph_path = graph_paths[0]
    pipeline_config_path = pipeline / "jsons" / f"{OP_ID}_{OP_TYPE}.json"
    if _load(pipeline_config_path) != config:
        raise GapRepairReleaseError(
            "rebuilt planner did not consume the exact repaired address-bound config"
        )
    mapping_source = exec_root / "mapping_evidence" / OP_ID / "source_config.json"
    if _load(mapping_source) != config:
        raise GapRepairReleaseError("execplan mapping source differs from repaired config")
    if (
        exec_manifest.get("schema")
        != "operator-config-execplan-evidence-bundle-v1"
        or exec_manifest.get("double_run", {}).get("equal") is not True
        or exec_manifest.get("package_validation_report", {}).get("valid") is not True
        or exec_manifest.get("request_address_validation_report", {}).get("valid")
        is not True
        or request.get("valid") is not True
        or request.get("issues") != []
    ):
        raise GapRepairReleaseError(
            "rebuilt planner/encoder/execplan/SCA evidence is not closed"
        )
    if (
        exec_manifest.get("operator_mapping_bundles", {})
        .get(OP_ID, {})
        .get("source_config_sha256")
        != sha256_file(config_root / "config.json")
    ):
        raise GapRepairReleaseError("execplan manifest config binding differs")

    coverage = config_analysis["coverage"]
    if (
        coverage.get("derived_distinct_transaction_bases") != 256
        or coverage.get("classification") != "RTL_PROVEN"
    ):
        raise GapRepairReleaseError("GAP D-index transaction-base coverage differs")

    sca_d_path = pipeline / "sca_cfg_D.json"
    sca_d = _load(sca_d_path)
    write_streams = _write_streams(request)
    per_slice: list[dict[str, Any]] = []
    for slice_id, stream in enumerate(write_streams):
        if stream.get("execution_slice") != slice_id:
            raise GapRepairReleaseError("GAP D stream slice ordering differs")
        key = f"{OP_ID}_matrixD_slice{slice_id}"
        item = sca_d.get(key)
        expected_region = [key]
        expected_first = (slice_id << 25) + 0x18840
        expected_last = expected_first + 8192 - 16
        if (
            not isinstance(item, Mapping)
            or item.get("length") != 512
            or stream.get("transaction_size_bytes") != 32
            or stream.get("index_tuple_count") != 256
            or stream.get("request_count_with_multiplicity") != 512
            or stream.get("unique_request_count") != 512
            or stream.get("valid_byte_count_with_multiplicity") != 8192
            or stream.get("padding_masked_byte_count_with_multiplicity") != 0
            or stream.get("logical_payload_byte_count_with_multiplicity") != 8192
            or stream.get("first_request", {}).get("byte_addr_30b")
            != f"0x{expected_first:08X}"
            or stream.get("last_request", {}).get("byte_addr_30b")
            != f"0x{expected_last:08X}"
            or stream.get("first_request", {}).get("region_hits") != expected_region
            or stream.get("last_request", {}).get("region_hits") != expected_region
        ):
            raise GapRepairReleaseError(
                f"GAP D request coverage differs on slice {slice_id}"
            )
        golden_path = (
            root
            / TRANSPORT_REL
            / "data"
            / OP_ID
            / f"slice{slice_id:02d}"
            / "matrix_D_linearized_128bit.txt"
        )
        golden_lines = _line_count_128bit(golden_path)
        if golden_lines != 512:
            raise GapRepairReleaseError(
                f"GAP D golden length differs on slice {slice_id}: {golden_lines}"
            )
        per_slice.append(
            {
                "slice": slice_id,
                "transaction_base_count_32byte": 256,
                "request_count_128bit": 512,
                "unique_request_count_128bit": 512,
                "ordered_request_address_sha256": stream[
                    "unique_request_addresses_sha256"
                ],
                "first_byte_address": f"0x{expected_first:08X}",
                "last_byte_address": f"0x{expected_last:08X}",
                "sca_d_length_128bit": item["length"],
                "golden_line_count_128bit": golden_lines,
                "golden_sha256": sha256_file(golden_path),
                "server_readback_golden_result": "PENDING_SERVER_RETURN",
            }
        )

    occupancy_cases = [
        repaired_outbuffer_count(
            count,
            compaction=compaction,
            result_last=result_last,
            write=write,
            read=read,
        )
        for count in range(3)
        for compaction, result_last in ((True, False), (False, True))
        for write in (False, True)
        for read in (False, True)
    ]
    if any(value != 0 for value in occupancy_cases):
        raise GapRepairReleaseError("repaired outbuffer micro-model is not bounded")
    if int32_feedback_allowed(
        transout=True,
        int32_mode=True,
        calculating=False,
        initialization_done=True,
        outbuffer_valid=False,
    ):
        raise GapRepairReleaseError("invalid INT32 feedback is still allowed")

    semantic_patches = config_analysis["semantic_patches"]
    expected_patch_values = {
        "$.dram_loop_configs.LC2.src_id": (config_analysis["semantic_patches"][3]["before"], None),
        "$.dram_loop_configs.LC2.outmost_loop": (0, 1),
        "$.dram_loop_configs.LC2.end": (1, 256),
        "$.dram_loop_configs.LC2.last_index": (1, 0),
    }
    actual_patch_values = {
        item["json_path"]: (item["before"], item["after"]) for item in semantic_patches
    }
    if actual_patch_values != expected_patch_values:
        raise GapRepairReleaseError(
            f"GAP LC2 four-field diff differs: {actual_patch_values}"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "local_release_preconditions_passed_server_dynamic_gates_pending",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "rules_read_before_rebuild": [
            ".agents/rules/算子配置规则.md",
            ".agents/rules/GAP_probe_v7_validator_rules.md",
            ".agents/rules/服务器测试包生成规则.md",
            "ndp-sim-ref/model_execplan/readme.md",
        ],
        "rule_ids": [
            RULE_ORTHOGONAL,
            RULE_D_COVERAGE,
            RULE_GA_OCCUPANCY,
            RULE_GA_INVALID_SLOT,
            RULE_GA_CROSS_BLOCK,
            RULE_MONITOR,
            RULE_IDENTITY,
        ],
        "config_semantics": {
            "blocker": "B_GAP_D_INDEX_CARRIER_SEMANTICS",
            "local_status": "CLOSED_FOR_THIS_NEW_IDENTITY",
            "lc2_exact_four_field_diff": semantic_patches,
            "distinct_transaction_bases_32byte_per_slice": 256,
            "distinct_write_addresses_128bit_per_slice": 512,
            "address_bound_config": _binding(root, config_root / "config.json"),
            "config_manifest": _binding(root, config_root / "manifest.json"),
        },
        "full_rebuild": {
            "planner_encoder_bitstream_execplan_sca_regenerated": True,
            "double_run_equal": True,
            "execplan_evidence": _binding(root, exec_manifest_path),
            "request_address_report": _binding(root, request_path),
            "graph_withbaseaddr": _binding(root, graph_path),
            "pipeline_config": _binding(root, pipeline_config_path),
            "execplan": _binding(root, pipeline / "install" / "execplan.txt"),
            "sca_cfg": _binding(root, pipeline / "sca_cfg.json"),
            "sca_cfg_D": _binding(root, sca_d_path),
            "mapping_penalty": 0.0,
            "mapping_fallback_used": False,
        },
        "d_static_coverage": {
            "rule_id": RULE_D_COVERAGE,
            "local_status": "STATIC_PRECONDITIONS_PASSED",
            "server_dynamic_status": "PENDING_16_SLICE_READBACK_AND_GOLDEN",
            "per_slice": per_slice,
        },
        "rtl_control": {
            "blocker": "B_GAP_GA_ACCUM_STATE",
            "repair_id": repair["repair_id"],
            "local_status": "RTL_PATCH_SYNTAX_AND_MICROMODEL_PASSED",
            "server_dynamic_status": "PENDING_ALL_8_ORDINARY_PE_ASSERTIONS",
            "repair_manifest": _binding(
                root, repair_root / "RTL_PATCH_MANIFEST.json"
            ),
            "required_server_assertions": {
                RULE_GA_OCCUPANCY: "all_cycles_all_8_PE_count_in_0_to_2",
                RULE_GA_INVALID_SLOT: "zero_invalid_slot_reuse_events",
                RULE_GA_CROSS_BLOCK: "C_zero_until_new_partial_valid",
            },
        },
        "orthogonal_release": {
            "rule_id": RULE_ORTHOGONAL,
            "config_semantics_and_rtl_control_checked_separately": True,
        },
        "transport": {
            "manifest": _binding(root, root / TRANSPORT_REL / "manifest.json"),
            "slice_count": transport["summary"]["slice_count"],
            "independent_mismatch_count": transport["summary"][
                "independent_mismatch_count"
            ],
        },
        "remaining_blockers": [
            "SERVER_GAP_D_READBACK_16x512_AND_GOLDEN",
            "SERVER_GA_OCCUPANCY_ALL_8_PE",
            "SERVER_GA_INVALID_SLOT_ISOLATION_ALL_8_PE",
            "SERVER_GA_CROSS_BLOCK_INIT_ALL_8_PE",
            "SERVER_SAME_CLOCK_OR_FORMAL_READBACK_EVIDENCE",
            "SERVER_FOCUSED_IDENTITY_PRE_POST_POSTRUN_POSTRESTORE",
            "E5_REPEAT_RUN",
        ],
    }
    payload["gate_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    _RELEASE_GATE_CACHE[cache_key] = copy.deepcopy(payload)
    return payload


def validate_gap_repair_release_gate(
    project_root: Path,
    value: Mapping[str, Any],
    *,
    execplan_root: Path | None = None,
    rtl_repair_root: Path | None = None,
) -> None:
    expected = build_gap_repair_release_gate(
        project_root,
        execplan_root=execplan_root,
        rtl_repair_root=rtl_repair_root,
    )
    if dict(value) != expected:
        raise GapRepairReleaseError("GAP repair release gate differs")


__all__ = [
    "DEFAULT_EXECPLAN_REL",
    "DEFAULT_OUTPUT_REL",
    "DEFAULT_RTL_REPAIR_REL",
    "GapRepairReleaseError",
    "SCHEMA",
    "build_gap_repair_release_gate",
    "validate_gap_repair_release_gate",
]
