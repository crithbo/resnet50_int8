from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .hashing import sha256_file
from .qlinearadd_node0007_full_e2 import (
    CONFIG_REL,
    CONTRACT_REL,
    LOCAL_BASES,
    LOCAL_ELEMENTS,
    NODE_ID,
    ROOT_REL,
    SCHEMA,
    _record,
)


QADD_RULE_REL = Path(".agents/rules/QLinearAdd算子配置规则.md")
QADD_RULE_SHA256 = (
    "dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269"
)
ADJUDICATION_REL = Path(
    ".agents/task_records/"
    "20260729_qlinearadd_node0007_row_boundary_mainline_adjudication.md"
)
ADJUDICATION_SHA256 = (
    "a2216d7e39ec09a0d902336c49553c0744231587c45ddd63259984f71f357e8b"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260729_qlinearadd_node0007_relocated_full_e2_package_ready.md"
)
EXPECTED_REQUEST_COUNT = 37_352_448
EXPECTED_UNIQUE_REQUEST_COUNT = 20_493_312
EXPECTED_UNIQUE_REQUEST_SHA256 = (
    "e933bb1cd4f9f163174c8375fcbed841b7258f11dae542bb9beb97b6c7830034"
)


class QLinearAddNode0007ClosureError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QLinearAddNode0007ClosureError(f"JSON root must be object: {path}")
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


def _leaf_diffs(left: Any, right: Any) -> list[dict[str, Any]]:
    a = dict(_leaves(left))
    b = dict(_leaves(right))
    paths = sorted(set(a) | set(b))
    return [
        {"path": path, "static": a.get(path), "final": b.get(path)}
        for path in paths
        if a.get(path) != b.get(path)
    ]


def _final_json(root: Path, op_id: str) -> Path:
    matches = sorted(
        (root / ROOT_REL / "execplan/pipeline_output/jsons").glob(
            f"{op_id}_*.json"
        )
    )
    if len(matches) != 1:
        raise QLinearAddNode0007ClosureError(
            f"expected one final JSON for {op_id}, got {len(matches)}"
        )
    return matches[0]


def _stream_summary(request: dict[str, Any]) -> dict[str, Any]:
    rows: dict[tuple[str, str], dict[str, int]] = {}
    for stage in request["facts"]["stages"]:
        op_id = str(stage["op_id"])
        for stream in stage["streams"]:
            key = (op_id, str(stream["resource"]))
            first = stream["first_request"]
            last = stream["last_request"]
            item = rows.setdefault(
                key,
                {
                    "min_row": 6144,
                    "max_row": -1,
                    "request_count": 0,
                    "valid_bytes": 0,
                    "logical_payload_bytes": 0,
                    "padding_masked_bytes": 0,
                },
            )
            item["min_row"] = min(item["min_row"], int(first["row"]))
            item["max_row"] = max(item["max_row"], int(last["row"]))
            item["request_count"] += int(
                stream["request_count_with_multiplicity"]
            )
            item["valid_bytes"] += int(
                stream["valid_byte_count_with_multiplicity"]
            )
            item["logical_payload_bytes"] += int(
                stream["logical_payload_byte_count_with_multiplicity"]
            )
            item["padding_masked_bytes"] += int(
                stream["padding_masked_byte_count_with_multiplicity"]
            )
    return {
        f"{op_id}:{resource}": value
        for (op_id, resource), value in sorted(rows.items())
    }


def validate_closure(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    evidence_root = root / ROOT_REL
    exec_root = evidence_root / "execplan"
    request = _load(exec_root / "request_address_validation_report.json")
    exec_validation = _load(exec_root / "execplan_validation_report.json")
    double_run = _load(exec_root / "double_run_comparison.json")
    simulator = _load(evidence_root / "config_bound_simulator.json")
    record = _record(root)

    if sha256_file(root / QADD_RULE_REL) != QADD_RULE_SHA256:
        errors.append("active QLinearAdd rule SHA drifted")
    if sha256_file(root / ADJUDICATION_REL) != ADJUDICATION_SHA256:
        errors.append("mainline row-boundary adjudication SHA drifted")
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

    streams = _stream_summary(request)
    if any(item["max_row"] >= 6144 for item in streams.values()):
        errors.append("at least one final request row is outside DDR row space")
    if any(
        item["valid_bytes"] != item["logical_payload_bytes"]
        or item["padding_masked_bytes"] != 0
        for item in streams.values()
    ):
        errors.append("request byte coverage or padding mask differs")

    expected_rows = {
        "op_a_dequant:READ_STREAM0": (0, 587),
        "op_a_dequant:WRITE_STREAM0": (588, 2939),
        "op_b_dequant:READ_STREAM0": (2940, 3527),
        "op_b_dequant:WRITE_STREAM0": (3528, 5879),
        "op_relocation_pad:READ_STREAM0": (5880, 6011),
        "op_relocation_pad:WRITE_STREAM0": (6012, 6143),
        "op_fp32_add:READ_STREAM0": (588, 2939),
        "op_fp32_add:READ_STREAM1": (3528, 5879),
        "op_fp32_add:WRITE_STREAM0": (0, 2351),
        "op_tail_mul:READ_STREAM0": (0, 2351),
        "op_tail_mul:WRITE_STREAM0": (2352, 4703),
        "op_tail_round:READ_STREAM0": (2352, 4703),
        "op_tail_round:WRITE_STREAM0": (4704, 5291),
    }
    for key, (minimum, maximum) in expected_rows.items():
        item = streams.get(key)
        if item is None or (item["min_row"], item["max_row"]) != (
            minimum,
            maximum,
        ):
            errors.append(f"row proof differs: {key}")

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
    for op_id in LOCAL_BASES:
        static = _load(root / CONFIG_REL / f"{op_id}.json")
        final = _load(_final_json(root, op_id))
        for diff in _leaf_diffs(static, final):
            diff["operator_id"] = op_id
            diffs.append(diff)
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
    ):
        errors.append("config-bound golden comparison is not exact")

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

    report = {
        "schema": "qlinearadd-node0007-relocated-full-e2-closure-report-v2",
        "valid": not errors,
        "status": "E2_LOCAL_COMPLETE" if not errors else "E2_FAILED",
        "candidate_release": False,
        "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE" if not errors else None,
        "node_id": NODE_ID,
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
        "final_request_facts": expected_request_facts,
        "stream_address_coverage": streams,
        "per_slice_nonalias_ranges": [
            {"tensor": name, "start": f"0x{start:08x}", "end": f"0x{end:08x}"}
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
        "relocation_mechanism": {
            "reason": "move the complete 2,408,448-byte SUM_F32 scratch to a legal bank interval",
            "mechanism": "hardware FP32 zero multiply-by-1 spacer fills [0x005be000,0x00600000), forcing the next output to 0x00800000",
            "host_precomputed_internal_tensor": False,
            "qlinearadd_internal_tensor": False,
            "arithmetic_semantics_changed": False,
            "input_replay_changed": False,
            "tail_semantics_changed": False,
        },
        "provenance": {
            "schema": SCHEMA,
            "qlinearadd_rule": {
                "path": QADD_RULE_REL.as_posix(),
                "sha256": QADD_RULE_SHA256,
            },
            "row_boundary_adjudication": {
                "path": ADJUDICATION_REL.as_posix(),
                "sha256": ADJUDICATION_SHA256,
            },
            "execplan_bundle_manifest": {
                "path": (ROOT_REL / "execplan/bundle_manifest.json").as_posix(),
                "sha256": sha256_file(exec_root / "bundle_manifest.json"),
            },
        },
    }
    return report


def materialize_closure(root: Path) -> dict[str, Any]:
    report = validate_closure(root)
    _write(root / ROOT_REL / "closure_report.json", report)
    contract = {
        **report,
        "schema": "qlinearadd-node0007-relocated-full-e2-contract-v2",
        "contract_path": CONTRACT_REL.as_posix(),
        "package_release": {
            "status": "PENDING_PACKAGE_BUILD"
            if report["valid"]
            else "NOT_GENERATED_E2_FAILED",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
        },
    }
    _write(root / CONTRACT_REL, contract)
    return contract


__all__ = [
    "ADJUDICATION_SHA256",
    "CONTRACT_REL",
    "QADD_RULE_SHA256",
    "TASK_RECORD_REL",
    "materialize_closure",
    "validate_closure",
]
