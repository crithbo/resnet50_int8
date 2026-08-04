from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .hashing import sha256_file
from .qlinearadd_node0007_closure import (
    EXPECTED_REQUEST_COUNT,
    EXPECTED_UNIQUE_REQUEST_COUNT,
    EXPECTED_UNIQUE_REQUEST_SHA256,
    _leaf_diffs,
    _stream_summary,
)
from .qlinearadd_node0007_full_e2 import LOCAL_BASES, _record
from .qlinearadd_node0007_nested_lc_v4 import (
    CONFIG_REL,
    CONTRACT_REL,
    HARDWARE_RULE_REL,
    HARDWARE_RULE_SHA256,
    QADD_RULE_REL,
    QADD_RULE_SHA256,
    ROOT_REL,
    SCHEMA,
    build_configs,
    geometry_equivalence_proof,
    validate_signed_feedback_bounds,
)


FROZEN_ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-relocated-full-e2-v2"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260730_qlinearadd_node0007_nested_lc_v4_package_ready.md"
)


class QLinearAddNode0007NestedLCClosureError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QLinearAddNode0007NestedLCClosureError(
            f"JSON root must be object: {path}"
        )
    return value


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _leaves(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            yield from _leaves(value[key], f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _final_json(root: Path, op_id: str) -> Path:
    matches = sorted(
        (root / ROOT_REL / "execplan/pipeline_output/jsons").glob(
            f"{op_id}_*.json"
        )
    )
    if len(matches) != 1:
        raise QLinearAddNode0007NestedLCClosureError(
            f"expected one final JSON for {op_id}, got {len(matches)}"
        )
    return matches[0]


def _stream_signatures(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for stage in report["facts"]["stages"]:
        for stream in stage["streams"]:
            key = (
                f"{stage['op_id']}:slice{stream['execution_slice']:02d}:"
                f"{stream['resource']}"
            )
            result[key] = {
                name: stream[name]
                for name in (
                    "target",
                    "mode",
                    "base_addr",
                    "transaction_size_bytes",
                    "index_tuple_count",
                    "request_count_with_multiplicity",
                    "unique_request_count",
                    "unique_request_addresses_sha256",
                    "valid_byte_count_with_multiplicity",
                    "padding_masked_byte_count_with_multiplicity",
                    "logical_payload_byte_count_with_multiplicity",
                    "first_request",
                    "last_request",
                )
            }
    return result


def validate_closure(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    evidence_root = root / ROOT_REL
    exec_root = evidence_root / "execplan"
    request = _load(exec_root / "request_address_validation_report.json")
    frozen_request = _load(
        root
        / FROZEN_ROOT_REL
        / "execplan/request_address_validation_report.json"
    )
    exec_validation = _load(exec_root / "execplan_validation_report.json")
    double_run = _load(exec_root / "double_run_comparison.json")
    simulator = _load(evidence_root / "config_bound_simulator.json")
    record = _record(root)

    if sha256_file(root / HARDWARE_RULE_REL) != HARDWARE_RULE_SHA256:
        errors.append("active hardware-field rule SHA drifted")
    if sha256_file(root / QADD_RULE_REL) != QADD_RULE_SHA256:
        errors.append("active QLinearAdd rule SHA drifted")
    if not request.get("valid") or request.get("issues"):
        errors.append("request-address validator is not clean")
    if not exec_validation.get("valid") or exec_validation.get("issues"):
        errors.append("execplan validator is not clean")
    if double_run.get("equal") is not True:
        errors.append("native execplan double-run is not deterministic")

    facts = request.get("facts", {})
    expected_request_facts = {
        "operator_count": 6,
        "request_count_with_multiplicity": EXPECTED_REQUEST_COUNT,
        "unique_request_address_count": EXPECTED_UNIQUE_REQUEST_COUNT,
        "unique_request_addresses_sha256": EXPECTED_UNIQUE_REQUEST_SHA256,
        "issue_count": 0,
    }
    for key, expected in expected_request_facts.items():
        if facts.get(key) != expected:
            errors.append(f"request fact differs: {key}")

    signatures = _stream_signatures(request)
    frozen_signatures = _stream_signatures(frozen_request)
    if signatures != frozen_signatures:
        errors.append("final per-slice request address signatures differ")

    streams = _stream_summary(request)
    if any(item["max_row"] >= 6144 for item in streams.values()):
        errors.append("at least one final request row is outside DDR row space")
    if any(
        item["valid_bytes"] != item["logical_payload_bytes"]
        or item["padding_masked_bytes"] != 0
        for item in streams.values()
    ):
        errors.append("request byte coverage or padding mask differs")

    configs = build_configs(root)
    bounds = validate_signed_feedback_bounds(configs)
    geometry = geometry_equivalence_proof()
    if not geometry["valid"]:
        errors.append("ordered logical occurrence equivalence differs")

    mapping: dict[str, Any] = {}
    for op_id in LOCAL_BASES:
        manifest = _load(evidence_root / f"mapping/{op_id}/bundle_manifest.json")
        summary = manifest.get("summary", {})
        mapping[op_id] = summary
        if (
            summary.get("valid") is not True
            or float(summary.get("penalty", -1)) != 0.0
            or summary.get("fallback_used") is not False
            or summary.get("cache_loaded_origin") != "none"
        ):
            errors.append(f"mapping evidence differs: {op_id}")

    diffs: list[dict[str, Any]] = []
    final_bounds: list[dict[str, Any]] = []
    for op_id in LOCAL_BASES:
        static = _load(root / CONFIG_REL / f"{op_id}.json")
        final = _load(_final_json(root, op_id))
        for diff in _leaf_diffs(static, final):
            diff["operator_id"] = op_id
            diffs.append(diff)
        for loop_name, loop in sorted(final["dram_loop_configs"].items()):
            row = {
                "operator_id": op_id,
                "loop": loop_name,
                "start": int(loop["start"]),
                "end": int(loop["end"]),
                "stride": int(loop["stride"]),
            }
            row["valid"] = (
                row["stride"] <= 0 or row["end"] <= 32_768
            )
            final_bounds.append(row)
            if not row["valid"]:
                errors.append(
                    f"final signed feedback bound differs: "
                    f"{op_id}.{loop_name}"
                )
    non_base = [
        item
        for item in diffs
        if not item["path"].endswith(".base_addr")
    ]
    if len(diffs) != 13 or non_base:
        errors.append(
            f"static-to-final leaf ownership differs: total={len(diffs)} "
            f"non_base={len(non_base)}"
        )

    if (
        simulator.get("physical_mismatch_count") != 0
        or simulator.get("logical_mismatch_count") != 0
        or simulator.get("padding_mismatch_count") != 0
        or simulator.get("host_precomputed_internal_tensor") is not False
        or simulator.get("numeric_analysis_repeated") is not False
    ):
        errors.append("config-bound frozen golden comparison is not exact")

    qparams = record["qparams"]
    ranges = [
        ("A", 0x000000, 0x093000),
        ("A_SCALED", 0x093000, 0x2DF000),
        ("B", 0x2DF000, 0x372000),
        ("B_SCALED", 0x372000, 0x5BE000),
        ("RELOCATION_PAD_INPUT", 0x5BE000, 0x5DF000),
        ("RELOCATION_PAD_OUTPUT", 0x5DF000, 0x600000),
        ("SUM_F32", 0x800000, 0xA4C000),
        ("TAIL_F32", 0xA4C000, 0xC98000),
        ("Y_UINT8", 0xC98000, 0xD2B000),
    ]
    for (_, _a0, a1), (_, b0, _b1) in zip(ranges, ranges[1:]):
        if a1 > b0:
            errors.append("per-slice allocation ranges alias")

    return {
        "schema": "qlinearadd-node0007-nested-lc-full-e2-closure-v4",
        "valid": not errors,
        "status": "E2_LOCAL_COMPLETE" if not errors else "E2_FAILED",
        "candidate_release": False,
        "claim": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE" if not errors else None
        ),
        "node_id": "node-0007",
        "hw_op_id": "hwop-0007-00",
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "errors": errors,
        "first_error": errors[0] if errors else None,
        "six_qparams": {
            name: qparams[name]["value"]
            for name in (
                "a_scale",
                "a_zero_point",
                "b_scale",
                "b_zero_point",
                "y_scale",
                "y_zero_point",
            )
        },
        "bypass_annotation": {
            "bypass_reason": (
                "native add_dequant terminates at FP32 and the prior flat "
                "positive-stride LC domains wrap signed feedback"
            ),
            "contradicted_or_missing_native_path": (
                "native fused QLinearAdd with exact UINT8 tail is absent; "
                "flat dequant/add DRAM LC end 37632 is dynamically contradicted"
            ),
            "exact_equivalence_scope": (
                "node0007 frozen six-qparam W3 order, all 28 slices, complete "
                "UINT8 Y and zero padding"
            ),
            "materialized_configuration_mechanism": (
                "six native stages; dequant 4x9408 and add 8x18816 nested "
                "DRAM loops with explicit FP32 scratch and exact UINT8 tail"
            ),
            "performance_and_resource_cost": (
                "six serialized stages, two full FP32 activation scratches, "
                "one FP32 relocation spacer and completion barriers"
            ),
            "unresolved_production_blocker": (
                "no performance qualification and no bound final server RTL "
                "identity or dynamic E4/E5 result"
            ),
            "claim_boundary": (
                "CONFIG_ONLY_CORRECTNESS_BASELINE; candidate_release=false; "
                "E2 local only"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_QADD_NODE0007_DRAM_LC_SIGNED_FEEDBACK_WRAP"
            ]
            if not errors
            else [],
            "open": [] if not errors else ["B_QADD_NODE0007_NESTED_LC_E2"],
        },
        "final_request_facts": expected_request_facts,
        "stream_address_coverage": streams,
        "per_slice_stream_signatures_match_frozen_logical_domain": (
            signatures == frozen_signatures
        ),
        "nested_lc_ordered_equivalence": geometry,
        "static_signed_feedback_bounds": bounds,
        "final_signed_feedback_bounds": final_bounds,
        "per_slice_nonalias_ranges": [
            {
                "tensor": name,
                "start": f"0x{start:08x}",
                "end": f"0x{end:08x}",
            }
            for name, start, end in ranges
        ],
        "accepted_lifetimes_and_barriers": [
            "A_SCALED: stage0 accepted write through stage3 last accepted read",
            "B_SCALED: stage1 accepted write through stage3 last accepted read",
            "RELOCATION_PAD: stage2 only; hardware output is not consumed",
            "SUM_F32: stage3 accepted write through stage4 last accepted read",
            "TAIL_F32: stage4 accepted write through stage5 last accepted read",
            "Y_UINT8: fresh stage5 terminal output",
            "native sequential execplan completion is the inter-stage barrier",
        ],
        "mapping_from_empty_state": mapping,
        "static_to_final_leaf_diff": {
            "total_count": len(diffs),
            "base_only_count": len(diffs) - len(non_base),
            "non_base_count": len(non_base),
            "owner": "native execplan base-address allocator",
            "authorization": "base_addr-only materialization",
            "records": diffs,
        },
        "config_bound_simulator": simulator,
        "provenance": {
            "schema": SCHEMA,
            "hardware_rule": {
                "path": HARDWARE_RULE_REL.as_posix(),
                "sha256": HARDWARE_RULE_SHA256,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE_REL.as_posix(),
                "sha256": QADD_RULE_SHA256,
            },
            "execplan_bundle_manifest": {
                "path": (ROOT_REL / "execplan/bundle_manifest.json").as_posix(),
                "sha256": sha256_file(exec_root / "bundle_manifest.json"),
            },
        },
    }


def materialize_closure(root: Path) -> dict[str, Any]:
    report = validate_closure(root)
    _write(root / ROOT_REL / "closure_report.json", report)
    contract = {
        **report,
        "schema": "qlinearadd-node0007-nested-lc-full-e2-contract-v4",
        "contract_path": CONTRACT_REL.as_posix(),
        "package_release": {
            "status": (
                "PENDING_PACKAGE_BUILD"
                if report["valid"]
                else "NOT_GENERATED_E2_FAILED"
            ),
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
        },
    }
    _write(root / CONTRACT_REL, contract)
    return contract


__all__ = [
    "CONTRACT_REL",
    "TASK_RECORD_REL",
    "materialize_closure",
    "validate_closure",
]
