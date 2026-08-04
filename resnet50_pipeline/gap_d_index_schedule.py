from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_operator_semantics_audit import (
    GAP_REQUEST_ID,
    require_gap_d_index_coverage,
)


SCHEMA = "resnet50-gap-d-index-schedule-v1"
SOURCE_CONFIG = (
    "configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1/config.json"
)
LOWERING_BUNDLE = "contracts/resnet50_r5_lowering_bundle.json"
OUTPUT_ROOT = "configs/stage_codegen/hwop-0071-00-d-index-v1"
OUTPUT_CONFIG = f"{OUTPUT_ROOT}/config.json"
OUTPUT_MANIFEST = f"{OUTPUT_ROOT}/manifest.json"
CONTRACT_PATH = "contracts/operator_config/gap_d_index_schedule_v1.json"
MAPPING_EVIDENCE_ROOT = (
    "artifacts/operator_config_validation/r5-gap-d-index-mapping-v1"
)
PATCH_PATHS = (
    "$.dram_loop_configs.LC2.src_id",
    "$.dram_loop_configs.LC2.outmost_loop",
    "$.dram_loop_configs.LC2.end",
    "$.dram_loop_configs.LC2.last_index",
)


class GapDIndexScheduleError(ValueError):
    pass


def d_index_release_decision(
    *,
    slice_count: int,
    expected_lines_per_slice: int,
    unique_lines_per_slice: list[int],
    golden_pass_per_slice: list[bool],
) -> dict[str, Any]:
    if (
        slice_count <= 0
        or expected_lines_per_slice <= 0
        or len(unique_lines_per_slice) != slice_count
        or len(golden_pass_per_slice) != slice_count
    ):
        raise GapDIndexScheduleError(
            "D-index release evidence has inconsistent dimensions"
        )
    coverage_complete = all(
        count == expected_lines_per_slice
        for count in unique_lines_per_slice
    )
    golden_complete = all(golden_pass_per_slice)
    return {
        "rule_id": "CDA-GAP-D-READBACK-COVERAGE-001",
        "slice_count": slice_count,
        "expected_lines_per_slice": expected_lines_per_slice,
        "unique_lines_per_slice": unique_lines_per_slice,
        "coverage_complete": coverage_complete,
        "golden_complete": golden_complete,
        "release_allowed": coverage_complete and golden_complete,
        "request_count_alone_is_sufficient": False,
    }


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GapDIndexScheduleError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise GapDIndexScheduleError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise GapDIndexScheduleError(f"required input is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _request(root: Path) -> dict[str, Any]:
    bundle = _load(root / LOWERING_BUNDLE)
    validate_r5_lowering_bundle(bundle, root)
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == GAP_REQUEST_ID
    ]
    if len(matches) != 1:
        raise GapDIndexScheduleError("exact typed GAP request is missing")
    request = copy.deepcopy(dict(matches[0]))
    geometry = request.get("logical_geometry")
    if (
        request.get("identity", {}).get("hw_op_type") != "GlobalAverageSumInt32"
        or geometry
        != {
            "attributes": {"channels_last": 0},
            "input_dtypes": ["uint8", "uint8"],
            "input_shapes": [[16, 2048, 7, 7], [1]],
            "output_dtypes": ["int32"],
            "output_shapes": [[16, 2048, 1, 1]],
            "reduction": {
                "axes": [2, 3],
                "keepdims": True,
                "spatial_element_count": 49,
            },
        }
    ):
        raise GapDIndexScheduleError("typed GAP signature differs")
    return request


def _leaf_differences(
    before: Any, after: Any, path: str = "$"
) -> list[dict[str, Any]]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        if set(before) != set(after):
            return [
                {
                    "json_path": path,
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(after),
                    "reason": "object_key_set_changed",
                }
            ]
        result: list[dict[str, Any]] = []
        for key in sorted(before):
            result.extend(
                _leaf_differences(before[key], after[key], f"{path}.{key}")
            )
        return result
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [
                {
                    "json_path": path,
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(after),
                    "reason": "array_length_changed",
                }
            ]
        result = []
        for index, (left, right) in enumerate(zip(before, after)):
            result.extend(
                _leaf_differences(left, right, f"{path}[{index}]")
            )
        return result
    if before == after:
        return []
    return [
        {
            "json_path": path,
            "before": copy.deepcopy(before),
            "after": copy.deepcopy(after),
            "reason": "leaf_value_changed",
        }
    ]


def derive_gap_d_index_config(
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = project_root.resolve()
    request = _request(root)
    source = _load(root / SOURCE_CONFIG)
    derived = copy.deepcopy(source)
    try:
        lc2 = derived["dram_loop_configs"]["LC2"]
        port = derived["lc_pe_configs"]["PE1"]["inport0"]
    except (KeyError, TypeError) as error:
        raise GapDIndexScheduleError("GAP PE1 carrier topology differs") from error
    if (
        lc2
        != {
            "src_id": "DRAM_LC.LC0",
            "outmost_loop": 0,
            "start": 0,
            "end": 1,
            "stride": 1,
            "last_index": 1,
        }
        or port.get("mode") != "buffer"
        or port.get("src_id") != "DRAM_LC.LC2"
        or derived["lc_pe_configs"]["PE1"].get("alu_opcode") != "mul"
        or derived["lc_pe_configs"]["PE1"]["inport1"].get("mode")
        != "constant"
        or derived["lc_pe_configs"]["PE1"]["inport1"].get("constant") != 1
    ):
        raise GapDIndexScheduleError("GAP PE1 identity carrier differs")
    lc2["src_id"] = None
    lc2["outmost_loop"] = 1
    lc2["end"] = 256
    lc2["last_index"] = 0

    differences = _leaf_differences(source, derived)
    expected_differences = [
        {
            "json_path": "$.dram_loop_configs.LC2.end",
            "before": 1,
            "after": 256,
            "reason": "leaf_value_changed",
        },
        {
            "json_path": "$.dram_loop_configs.LC2.last_index",
            "before": 1,
            "after": 0,
            "reason": "leaf_value_changed",
        },
        {
            "json_path": "$.dram_loop_configs.LC2.outmost_loop",
            "before": 0,
            "after": 1,
            "reason": "leaf_value_changed",
        },
        {
            "json_path": "$.dram_loop_configs.LC2.src_id",
            "before": "DRAM_LC.LC0",
            "after": None,
            "reason": "leaf_value_changed",
        },
    ]
    if differences != expected_differences:
        raise GapDIndexScheduleError(
            f"GAP D-index patch is not the exact four-field root patch: "
            f"{differences}"
        )
    report = OperatorConfigValidator().validate(
        derived, source=OUTPUT_CONFIG, development_mode=True
    ).to_dict()
    if report.get("valid") is not True or report.get("facts", {}).get(
        "issue_count"
    ) != 0:
        raise GapDIndexScheduleError(
            "derived GAP D-index config fails strict validation: "
            + str(report.get("first_error"))
        )
    coverage = require_gap_d_index_coverage(derived, request)
    expected_biases = list(range(0, 8192, 32))
    if (
        coverage.get("classification") != "RTL_PROVEN"
        or coverage.get("derived_distinct_transaction_bases") != 256
        or coverage.get("required_distinct_transaction_bases") != 256
        or coverage.get("transaction_bytes") != 32
        or coverage.get("first_derived_biases_bytes") != expected_biases[:16]
    ):
        raise GapDIndexScheduleError("derived GAP D-index coverage differs")
    return derived, request, {
        "differences": differences,
        "validator": report,
        "coverage": coverage,
        "all_output_biases_bytes": expected_biases,
    }


def _require_source_snippets(root: Path) -> dict[str, Any]:
    sources = {
        "lc_connect": (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/"
            "IGA_LC/IGA_LC_Connect.sv",
            (
                "assign iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post;",
                "iga_lc_inport_bp_pre[IGA_LC_SRC_IDX] = "
                "(iga_lc_enable & !iga_lc_outmost_loop",
            ),
        ),
        "pe_connect": (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/"
            "IGA_PE/IGA_PE_Connect.sv",
            (
                "assign iga_pe_connect2ob_bp_post = &iga_pe_outport_bp_post;",
                "iga_pe_inport_tag[IGA_PE_INPORT_IDX]",
                "iga_pe_inport_data[IGA_PE_INPORT_IDX]",
            ),
        ),
        "pe": (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE.sv",
            (
                "assign iga_pe_alu_result_tag = iga_pe_inbuffer2alu_tag;",
                "assign iga_pe_outport = iga_pe_outbuffer_port;",
            ),
        ),
        "stream_connect": (
            "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
            "Stream_Engine_Connect.sv",
            (
                "assign mse_mem_queue_idx[MSE_IDX][MEM_INPORT_IDX]",
                "assign mse_mem_queue_tag[MSE_IDX][MEM_INPORT_IDX]",
                "assign se2iga_mem_bp_pre[MSE_IDX][SRC_ID][MEM_INPORT_IDX]",
            ),
        ),
    }
    bindings: dict[str, Any] = {}
    for name, (relative, snippets) in sources.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            raise GapDIndexScheduleError(
                f"RTL equation differs in {relative}: {missing}"
            )
        bindings[name] = _binding(root, relative)
    return bindings


def _mapping_evidence(root: Path) -> dict[str, Any]:
    evidence_root = root / MAPPING_EVIDENCE_ROOT
    manifest_path = evidence_root / "bundle_manifest.json"
    report_path = evidence_root / "artifact_validation_report.json"
    review_path = evidence_root / "mapping_review.json"
    if not all(path.is_file() for path in (manifest_path, report_path, review_path)):
        return {
            "status": "not_generated",
            "required_before_server_candidate": True,
            "path": MAPPING_EVIDENCE_ROOT,
        }
    manifest = _load(manifest_path)
    report = _load(report_path)
    review = _load(review_path)
    penalty = manifest.get("summary", {}).get("penalty")
    if (
        report.get("valid") is not True
        or penalty not in (0, 0.0)
        or manifest.get("source_config_sha256")
        != sha256_file(root / OUTPUT_CONFIG)
    ):
        raise GapDIndexScheduleError(
            "GAP D-index native mapping evidence is not zero-penalty or "
            "does not bind the derived config"
        )
    return {
        "status": "zero_penalty_mapping_and_bitstream_generated",
        "required_before_server_candidate": True,
        "path": MAPPING_EVIDENCE_ROOT,
        "bundle_manifest": _binding(
            root, f"{MAPPING_EVIDENCE_ROOT}/bundle_manifest.json"
        ),
        "validation_report": _binding(
            root, f"{MAPPING_EVIDENCE_ROOT}/artifact_validation_report.json"
        ),
        "mapping_review": _binding(
            root, f"{MAPPING_EVIDENCE_ROOT}/mapping_review.json"
        ),
        "total_penalty": penalty,
    }


def build_gap_d_index_schedule_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    derived, request, analysis = derive_gap_d_index_config(root)
    source = _load(root / SOURCE_CONFIG)
    lc0 = derived["dram_loop_configs"]["LC0"]
    lc2 = derived["dram_loop_configs"]["LC2"]
    pe1 = derived["lc_pe_configs"]["PE1"]
    stream = derived["stream_engine"]["stream1"]
    completion = analysis["validator"]["facts"]["completion"]
    if (
        lc0
        != {
            "src_id": None,
            "outmost_loop": 1,
            "start": 0,
            "end": 256,
            "stride": 1,
            "last_index": 0,
        }
        or lc2.get("src_id") is not None
        or lc2.get("outmost_loop") != 1
        or [lc2.get("start"), lc2.get("end"), lc2.get("stride")]
        != [0, 256, 1]
        or lc2.get("last_index") != 0
        or pe1["inport0"].get("src_id") != "DRAM_LC.LC2"
        or stream.get("idx") != ["LC_PE.PE1", None, None]
        or stream.get("idx_size") != [31, None, None]
        or stream.get("dim_stride") != [32, None, None]
        or 0 not in completion.get("possible_last_indices", [])
        or completion.get("write_target") != "D"
    ):
        raise GapDIndexScheduleError("GAP D-index terminal topology differs")

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "d_index_static_and_native_mapping_closed_ga_accumulator_blocked"
            if _mapping_evidence(root)["status"]
            == "zero_penalty_mapping_and_bitstream_generated"
            else "d_index_static_closed_native_mapping_pending_ga_accumulator_blocked"
        ),
        "request": {
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "output_shape": request["logical_geometry"]["output_shapes"][0],
            "output_dtype": "int32",
        },
        "inputs": {
            "lowering_bundle": _binding(root, LOWERING_BUNDLE),
            "authorized_strict_config": _binding(root, SOURCE_CONFIG),
            "rtl": _require_source_snippets(root),
        },
        "derived_config": {
            "path": OUTPUT_CONFIG,
            "canonical_sha256": sha256_bytes(canonical_json_bytes(derived)),
            "source_canonical_sha256": sha256_bytes(
                canonical_json_bytes(source)
            ),
            "semantic_patch_count": 4,
            "semantic_patches": analysis["differences"],
            "address_binding": "late_bound_unchanged_from_template_placeholder",
            "formal_target_config": False,
        },
        "numeric_carrier": {
            "root": "DRAM_LC.LC2",
            "root_equation": "value(k)=0+k for 0<=k<256",
            "root_domain": [0, 255],
            "root_count": 256,
            "identity_pe": "LC_PE.PE1",
            "identity_equation": "PE1=uint16(LC2)*uint16(1)=LC2",
            "write_index": "stream1.idx[0]=LC_PE.PE1",
            "address_bias_equation": "bias(k)=low30(uint16(k)*uint20(32))",
            "first_bias_bytes": analysis["all_output_biases_bytes"][:16],
            "last_bias_bytes": analysis["all_output_biases_bytes"][-1],
            "distinct_bias_count": len(
                analysis["all_output_biases_bytes"]
            ),
            "coverage": analysis["coverage"],
        },
        "trigger_and_tag_chain": {
            "root_trigger": "slice_start_run because LC2.outmost_loop=1",
            "fanout_rule": (
                "LC2 advances only when the AND of every configured destination "
                "backpressure input is ready; PE1 and GROUP1.ROW_LC therefore "
                "observe the same accepted D-index occurrence"
            ),
            "buffer_loop_trigger": (
                "LC2 is an independent numeric root and also drives GROUP1 "
                "buffer addressing; the memory index and buffer read request "
                "therefore share one occurrence and one backpressure boundary"
            ),
            "tag_rule": (
                "LC2 valid/last/last_index tag is selected by PE1, copied to "
                "iga_pe_alu_result_tag, buffered with the PE result and then "
                "queued by stream1 together with the numeric index"
            ),
            "last_index": 0,
            "completion": copy.deepcopy(completion),
            "ordering": (
                "accepted root values are monotonically 0..255; stream1 is "
                "backpressured through PE1 and LC2 fanout, so no later root "
                "value can overtake an earlier write-index occurrence"
            ),
        },
        "strict_validation": {
            "valid": True,
            "issue_count": 0,
            "development_mode": True,
        },
        "native_mapping": _mapping_evidence(root),
        "release": {
            "resolved_blocker": "B_GAP_D_INDEX_CARRIER_SEMANTICS",
            "remaining_blockers": [
                "B_GAP_GA_ACCUM_STATE",
                "B_ADDRESS_MAPPING_EXECPLAN_SCA",
                "B_SERVER_E4_E5",
            ],
            "candidate_json_allowed": False,
            "server_d_index_gate": d_index_release_decision(
                slice_count=16,
                expected_lines_per_slice=512,
                unique_lines_per_slice=[2] * 16,
                golden_pass_per_slice=[False] * 16,
            ),
            "reason": (
                "D indexing is locally closed, but active GA int32_sum can "
                "reuse stale invalid outbuffer data across channel blocks; "
                "the read-only v7 observer return must adjudicate the exact "
                "state transition before a server candidate is emitted"
            ),
        },
    }
    payload["contract_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_gap_d_index_schedule_artifacts(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    derived, request, analysis = derive_gap_d_index_config(root)
    output_root = root / OUTPUT_ROOT
    output_root.mkdir(parents=True, exist_ok=True)
    config_path = root / OUTPUT_CONFIG
    config_path.write_text(
        json.dumps(derived, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "diagnostic_address_unbound_config_not_server_candidate",
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "source": _binding(root, SOURCE_CONFIG),
        "config": _binding(root, OUTPUT_CONFIG),
        "semantic_patches": analysis["differences"],
        "strict_validation": {
            "valid": True,
            "issue_count": 0,
        },
        "d_index_coverage": analysis["coverage"],
        "formal_target_config": False,
        "server_candidate": False,
        "remaining_blockers": [
            "B_GAP_GA_ACCUM_STATE",
            "B_ADDRESS_MAPPING_EXECPLAN_SCA",
            "B_SERVER_E4_E5",
        ],
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    (root / OUTPUT_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    contract = build_gap_d_index_schedule_contract(root)
    contract_path = root / CONTRACT_PATH
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return contract


def validate_gap_d_index_schedule_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_gap_d_index_schedule_contract(project_root)
    if value != expected:
        raise GapDIndexScheduleError(
            "GAP D-index schedule contract differs from hash-bound inputs"
        )


__all__ = [
    "CONTRACT_PATH",
    "GapDIndexScheduleError",
    "OUTPUT_CONFIG",
    "OUTPUT_ROOT",
    "SCHEMA",
    "build_gap_d_index_schedule_contract",
    "d_index_release_decision",
    "derive_gap_d_index_config",
    "validate_gap_d_index_schedule_contract",
    "write_gap_d_index_schedule_artifacts",
]
