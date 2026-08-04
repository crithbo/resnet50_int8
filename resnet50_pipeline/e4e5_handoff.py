from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from .hashing import sha256_file
from .maxpool_server_candidate import validate_maxpool_server_candidate
from .node0004_server_candidate import validate_node0004_server_candidate
from .r5_lowering_bundle import validate_r5_lowering_bundle


READINESS_SCHEMA = "resnet50-e4e5-handoff-readiness-v1"
PROTOCOL_SCHEMA = "resnet50-server-execution-protocol-v1"
PHASE_NAMES = ("load", "start", "wait", "readback")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

PREFERRED_REPRESENTATIVES = {
    "QuantizeLinear": "hwop-0000-00",
    "ConvInt32Accumulate": "hwop-0004-00",
    "RequantizeUint8": "hwop-0004-01",
    "MaxPoolUint8": "hwop-0002-00",
    "QLinearAddUint8": "hwop-0007-00",
    "GlobalAverageSumInt32": "hwop-0071-00",
    "AverageRequantizeUint8": "hwop-0071-01",
    "View": "hwop-0073-00",
    "MatMulInt32Accumulate": "hwop-0075-00",
    "DequantizeLinear": "hwop-0077-00",
}


class E4E5HandoffError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E4E5HandoffError(f"JSON root must be an object: {path}")
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise E4E5HandoffError(f"required handoff input is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _safe_relative(value: Any, *, label: str) -> str:
    raw = str(value)
    if label == "phase cwd" and raw == ".":
        return raw
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw
        or "\\" in raw
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.anchor)
        or any(part in {"", ".", ".."} for part in posix.parts)
        or posix.as_posix() != raw
    ):
        raise E4E5HandoffError(f"unsafe {label}: {raw!r}")
    return raw


def validate_server_execution_protocol(value: Mapping[str, Any]) -> None:
    if value.get("schema") != PROTOCOL_SCHEMA or value.get("status") != "approved":
        raise E4E5HandoffError("server execution protocol is not approved")
    server_id = value.get("server_id")
    if not isinstance(server_id, str) or not server_id.strip():
        raise E4E5HandoffError("server execution protocol has no server_id")
    rtl = value.get("rtl_identity")
    if (
        not isinstance(rtl, Mapping)
        or not isinstance(rtl.get("repository"), str)
        or not rtl["repository"]
        or COMMIT_RE.fullmatch(str(rtl.get("commit", ""))) is None
        or SHA256_RE.fullmatch(str(rtl.get("filelist_sha256", ""))) is None
    ):
        raise E4E5HandoffError("server RTL identity is incomplete")
    phases = value.get("phases")
    if not isinstance(phases, list) or [item.get("name") for item in phases] != list(
        PHASE_NAMES
    ):
        raise E4E5HandoffError("server protocol must contain load/start/wait/readback")
    for phase in phases:
        if not isinstance(phase, Mapping):
            raise E4E5HandoffError("server protocol phase is not an object")
        _safe_relative(phase.get("cwd", "."), label="phase cwd")
        argv = phase.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or not item for item in argv)
            or any("REQUIRED_USER_VALUE" in item for item in argv)
        ):
            raise E4E5HandoffError(f"server phase argv is incomplete: {phase.get('name')}")
        timeout = phase.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout <= 0 or timeout > 7 * 24 * 3600:
            raise E4E5HandoffError(f"server phase timeout is invalid: {phase.get('name')}")
    returns = value.get("return_paths")
    if not isinstance(returns, list) or not returns:
        raise E4E5HandoffError("server protocol has no return_paths")
    seen: set[str] = set()
    for item in returns:
        if not isinstance(item, Mapping):
            raise E4E5HandoffError("server return path is not an object")
        path = _safe_relative(item.get("path"), label="return path")
        if path in seen:
            raise E4E5HandoffError(f"duplicate server return path: {path}")
        seen.add(path)
        if item.get("kind") not in {"log", "metadata", "readback", "config"}:
            raise E4E5HandoffError(f"server return kind is invalid: {path}")
        if item.get("required") is not True:
            raise E4E5HandoffError(f"all declared server returns must be required: {path}")


def build_e4e5_handoff_readiness(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_path = root / "contracts/resnet50_r5_lowering_bundle.json"
    closure_path = root / "contracts/resnet50_project_closure.json"
    lowering = _load(lowering_path)
    closure = _load(closure_path)
    validate_r5_lowering_bundle(lowering, root)
    if closure.get("schema") != "resnet50-project-closure-v1":
        raise E4E5HandoffError("project closure identity differs")

    by_id = {
        request["identity"]["hw_op_id"]: request
        for request in lowering["requests"]
    }
    effective_by_id = {
        item["hw_op_id"]: item for item in lowering["effective_resolutions"]
    }
    maxpool_candidate_root = (
        root
        / "artifacts/operator_config_validation/r5-server-candidates/"
        "maxpool-node0002-guarded-wave0-v1"
    )
    node0004_candidate_root = (
        root
        / "artifacts/operator_config_validation/r5-server-candidates/"
        "node0004-nopp-r1-v2"
    )
    validate_maxpool_server_candidate(root, maxpool_candidate_root)
    validate_node0004_server_candidate(root, node0004_candidate_root)
    candidate_specs = {
        "hwop-0002-00": {
            "kind": "matrix_complete_locally_resolved_config",
            "root": maxpool_candidate_root,
        },
        "hwop-0004-00": {
            "kind": "matrix_complete_experimental_liveness_smoke",
            "root": node0004_candidate_root,
        },
    }
    representatives: list[dict[str, Any]] = []
    for hw_op_type, hw_op_id in PREFERRED_REPRESENTATIVES.items():
        request = by_id.get(hw_op_id)
        if request is None or request["identity"]["hw_op_type"] != hw_op_type:
            raise E4E5HandoffError(
                f"representative lowering request differs: {hw_op_type} -> {hw_op_id}"
            )
        ready = bool(request["emission_policy"]["formal_target_instance_allowed"])
        effective = effective_by_id.get(hw_op_id)
        if not isinstance(effective, Mapping):
            raise E4E5HandoffError(
                f"representative effective resolution is missing: {hw_op_id}"
            )
        candidate = candidate_specs.get(hw_op_id)
        candidate_present = candidate is not None
        candidate_ready = (
            candidate_present
            and effective.get("candidate_config_emission_allowed") is True
            and effective.get("readiness_axes", {}).get(
                "rtl_semantics_compatible"
            )
            is True
        )
        zero_copy = effective.get("candidate_zero_copy_binding_allowed") is True
        representatives.append(
            {
                "hw_op_type": hw_op_type,
                "hw_op_id": hw_op_id,
                "node_id": request["identity"]["node_id"],
                "stage": request["identity"]["stage"],
                "lowering_request_sha256": request["request_sha256"],
                "formal_target_config_ready": ready,
                "historical_unresolved_blockers": request["emission_policy"][
                    "unresolved_blockers"
                ],
                "effective_resolved_blockers": effective["resolved_blockers"],
                "effective_unresolved_blockers": effective["unresolved_blockers"],
                "rtl_semantic_blockers": effective["rtl_semantic_blockers"],
                "effective_blockers": effective["effective_blockers"],
                "local_lowering_resolved": effective["local_lowering_resolved"],
                "readiness_axes": effective["readiness_axes"],
                "local_disposition": effective["disposition"],
                "historical_candidate_package_present": candidate_present,
                "server_test_candidate_ready": candidate_ready,
                "candidate_kind": (
                    candidate["kind"]
                    if candidate_ready
                    else f"historical_{candidate['kind']}_semantics_blocked"
                    if candidate_present
                    else "zero_copy_no_standalone_operator_package"
                    if zero_copy
                    else None
                ),
                "candidate_manifest": (
                    _binding(
                        root,
                        (
                            candidate["root"] / "candidate_manifest.json"
                        ).relative_to(root).as_posix(),
                    )
                    if candidate_present
                    else None
                ),
                "e4": (
                    "candidate_ready_requires_approved_protocol"
                    if candidate_ready
                    else "historical_package_blocked_by_current_semantic_gates"
                    if candidate_present
                    else "not_applicable_as_standalone_zero_copy"
                    if zero_copy
                    else "blocked_before_package"
                ),
                "e5": (
                    "requires_two_valid_candidate_runs"
                    if candidate_ready
                    else "blocked_before_e4_by_current_semantic_gates"
                    if candidate_present
                    else "requires_full_network_alias_validation"
                    if zero_copy
                    else "blocked_before_e4"
                ),
            }
        )
    ready_count = sum(item["formal_target_config_ready"] for item in representatives)
    candidate_ready_count = sum(
        item["server_test_candidate_ready"] for item in representatives
    )
    return {
        "schema": READINESS_SCHEMA,
        "status": (
            "formal_representative_handoffs_ready"
            if ready_count == len(representatives)
            else "historical_packages_present_current_semantic_gates_block_e4"
        ),
        "inputs": {
            "project_closure": _binding(
                root, "contracts/resnet50_project_closure.json"
            ),
            "lowering_bundle": _binding(
                root, "contracts/resnet50_r5_lowering_bundle.json"
            ),
            "runtime_golden": _binding(
                root, "artifacts/w3/golden_batch16/manifest.json"
            ),
            "subop_golden": _binding(
                root, "artifacts/w3/subop_batch16/manifest.json"
            ),
            "protocol_template": _binding(
                root, "contracts/server_execution_protocol.template.json"
            ),
            "node0004_server_candidate": _binding(
                root,
                "artifacts/operator_config_validation/r5-server-candidates/"
                "node0004-nopp-r1-v2/candidate_manifest.json",
            ),
            "maxpool_server_candidate": _binding(
                root,
                "artifacts/operator_config_validation/r5-server-candidates/"
                "maxpool-node0002-guarded-wave0-v1/candidate_manifest.json",
            ),
        },
        "coverage": {
            "representative_count": len(representatives),
            "ready_package_count": ready_count,
            "blocked_package_count": len(representatives) - ready_count,
            "server_test_candidate_ready_count": candidate_ready_count,
            "server_test_candidate_blocked_count": len(representatives)
            - candidate_ready_count,
            "historical_server_test_candidate_package_count": sum(
                item["historical_candidate_package_present"]
                for item in representatives
            ),
            "zero_copy_standalone_not_applicable_count": sum(
                item["candidate_kind"] == "zero_copy_no_standalone_operator_package"
                for item in representatives
            ),
            "formal_target_stage_count": closure["coverage"][
                "formal_target_config_ready_count"
            ],
            "formal_e4_pass_count": closure["coverage"]["formal_e4_pass_count"],
            "formal_e5_pass_count": closure["coverage"]["formal_e5_pass_count"],
        },
        "representatives": representatives,
        "server_protocol": {
            "schema": PROTOCOL_SCHEMA,
            "template": "contracts/server_execution_protocol.template.json",
            "approved_protocol_present": False,
            "runner": "tools/run_e4e5_server_protocol.py",
            "required_phase_order": list(PHASE_NAMES),
            "command_policy": "only user-supplied approved argv; no inferred server commands",
        },
        "run_matrix": [
            {
                "run_id": "run1",
                "gate": "E4",
                "requirements": [
                    "formal target package hashes validated before execution",
                    "server RTL identity matches approved protocol",
                    "natural completion and raw readback returned",
                    "inverse-layout result matches independent W3/subop golden",
                ],
            },
            {
                "run_id": "run2",
                "gate": "E5",
                "requirements": [
                    "same package, RTL identity and execution protocol as run1",
                    "independent second natural completion and raw readback",
                    "run1/run2 logical result and environment receipts agree",
                    "boundary case covers the representative family semantics",
                ],
            },
        ],
        "execution_command_templates": [],
        "blocked_historical_command_templates": [
            {
                "candidate": "node0004-nopp-r1-v2",
                "scope": (
                    "historical liveness smoke only; execution is blocked by "
                    "current SA INT8 numeric semantics"
                ),
                "blockers": ["B_SA_INT8_CSA_NUMERIC"],
                "e4": (
                    "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                    "--package artifacts/operator_config_validation/r5-server-candidates/"
                    "node0004-nopp-r1-v2 --output <fresh-node0004-run1> --run-id run1"
                ),
                "e5": (
                    "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                    "--package artifacts/operator_config_validation/r5-server-candidates/"
                    "node0004-nopp-r1-v2 --output <fresh-node0004-run2> --run-id run2"
                ),
            },
            {
                "candidate": "maxpool-node0002-guarded-wave0-v1",
                "scope": (
                    "historical node0002 wave0 package; execution is blocked by "
                    "current GA INT8 max numeric/flow semantics"
                ),
                "blockers": [
                    "B_GA_INT8_MAX_NUMERIC",
                    "B_GA_INT8_MAX_FLOW",
                ],
                "e4": (
                    "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                    "--package artifacts/operator_config_validation/r5-server-candidates/"
                    "maxpool-node0002-guarded-wave0-v1 "
                    "--output <fresh-maxpool-run1> --run-id run1"
                ),
                "e5": (
                    "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                    "--package artifacts/operator_config_validation/r5-server-candidates/"
                    "maxpool-node0002-guarded-wave0-v1 "
                    "--output <fresh-maxpool-run2> --run-id run2"
                ),
            },
        ],
        "prohibited_substitutions": [
            "local formula mismatch=0 is not E4",
            "server process completion without raw readback is not E4",
            "one E4 run is not repeated E5",
            "candidate config files are not formal target packages",
            "a matrix-complete local candidate is not an E4 pass until the approved server protocol returns raw readback",
            "historical packages with contradicted RTL semantics must not be submitted as current E4 candidates",
        ],
    }


def validate_e4e5_handoff_readiness(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_e4e5_handoff_readiness(project_root)
    if value != expected:
        raise E4E5HandoffError("E4/E5 handoff readiness differs from current inputs")


def file_tree_receipt(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    records = []
    for path in sorted(resolved.rglob("*")):
        if path.is_symlink():
            raise E4E5HandoffError(f"handoff tree contains symlink: {path}")
        if path.is_file():
            relative = path.relative_to(resolved).as_posix()
            records.append(
                {
                    "path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    digest = hashlib.sha256()
    for record in records:
        digest.update(
            f"{record['path']}\0{record['size_bytes']}\0{record['sha256']}\n".encode(
                "utf-8"
            )
        )
    return {"files": records, "tree_sha256": digest.hexdigest()}


__all__ = [
    "E4E5HandoffError",
    "PHASE_NAMES",
    "PROTOCOL_SCHEMA",
    "READINESS_SCHEMA",
    "build_e4e5_handoff_readiness",
    "file_tree_receipt",
    "validate_e4e5_handoff_readiness",
    "validate_server_execution_protocol",
]
