from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "bda071d8cfdf96f8ec55369f91d16833ed1dee8e51c511de20af20be123fedb3"
)
EXPECTED_SOURCE_SHA256 = (
    "4bc0be9903e877b79cb11a82997ad5d6b5c6eed36666ec5a47771e83eb339446"
)
SOURCE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v2_failclosed.zip"
)
RETURN_ROOT = "r5_node0004_hw_v2_failclosed_return"
SOURCE_ROOT = "r5_node0004_hw_v2_failclosed"
EXPECTED_RETURN_MEMBERS = {
    f"{RETURN_ROOT}/RETURN_ALLOWLIST.json",
    f"{RETURN_ROOT}/evidence/SERVER_RESULT_GATE.json",
    f"{RETURN_ROOT}/evidence/compile_exit_status.txt",
    f"{RETURN_ROOT}/evidence/install_preflight.json",
    f"{RETURN_ROOT}/evidence/package_preflight.json",
    f"{RETURN_ROOT}/evidence/run_exit_status.txt",
    f"{RETURN_ROOT}/runs/compile/sim_results/compile.log",
    f"{RETURN_ROOT}/runs/compile/sim_results/compile_driver.log",
}


class Node0004V2ReturnAnalysisError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> list[str]:
    members: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
            or (mode and stat.S_ISLNK(mode))
        ):
            raise Node0004V2ReturnAnalysisError(f"unsafe ZIP member: {name}")
        seen.add(name)
        if not info.is_dir():
            members.append(name)
    return members


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise Node0004V2ReturnAnalysisError(
            f"cannot parse required JSON member: {name}"
        ) from error
    if not isinstance(value, dict):
        raise Node0004V2ReturnAnalysisError(f"JSON root must be object: {name}")
    return value


def _status(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise Node0004V2ReturnAnalysisError(
            f"cannot parse required status member: {name}"
        ) from error


def _compile_divergence(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    error_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "Error-[SFCOR] Source file cannot be opened" in line
        ),
        None,
    )
    include_index = next(
        (
            index
            for index, line in enumerate(lines)
            if '`include "native_return_observer.svh"' in line
        ),
        None,
    )
    missing_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "'No such file or directory'." in line
        ),
        None,
    )
    tb_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "tb_NDP_Top_new_phy.sv" in line
            and re.search(r"\b5854\b", line)
        ),
        None,
    )
    if None in (error_index, include_index, missing_index, tb_index):
        raise Node0004V2ReturnAnalysisError(
            "compile log lacks the exact missing-observer signature"
        )
    return {
        "classification": "PACKAGE_COMPILE_INCLUDE_PATH_MISSING",
        "compile_log_error_line": int(error_index) + 1,
        "compile_log_missing_file_line": int(missing_index) + 1,
        "compile_log_tb_location_line": int(tb_index) + 1,
        "compile_log_include_line": int(include_index) + 1,
        "reported_tb_path": lines[int(tb_index)].strip().strip('",'),
        "reported_tb_line": 5854,
        "missing_include": "native_return_observer.svh",
        "simulation_started": False,
        "terminal_observed": False,
        "formal_readback_produced": False,
    }


def analyze_node0004_v2_return(
    project_root: Path, return_zip: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    supplied = return_zip.resolve()
    source = root / SOURCE_REL
    if not supplied.is_file() or not source.is_file():
        raise Node0004V2ReturnAnalysisError("source or return ZIP is missing")
    return_sha = sha256_file(supplied)
    source_sha = sha256_file(source)
    if return_sha != EXPECTED_RETURN_SHA256:
        raise Node0004V2ReturnAnalysisError("return ZIP identity differs")
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise Node0004V2ReturnAnalysisError("source ZIP identity differs")

    with zipfile.ZipFile(supplied) as returned:
        members = _safe_members(returned)
        if returned.testzip() is not None:
            raise Node0004V2ReturnAnalysisError("return ZIP CRC failed")
        if set(members) != EXPECTED_RETURN_MEMBERS:
            raise Node0004V2ReturnAnalysisError("return ZIP exact allowlist differs")

        allowlist_name = f"{RETURN_ROOT}/RETURN_ALLOWLIST.json"
        allowlist = _json(returned, allowlist_name)
        records = allowlist.get("records")
        if not isinstance(records, list) or len(records) != 7:
            raise Node0004V2ReturnAnalysisError("return allowlist record count differs")
        declared: set[str] = set()
        for record in records:
            if not isinstance(record, dict) or not isinstance(
                record.get("path"), str
            ):
                raise Node0004V2ReturnAnalysisError("invalid allowlist record")
            relative = record["path"]
            member = f"{RETURN_ROOT}/{relative}"
            if member == allowlist_name or member not in EXPECTED_RETURN_MEMBERS:
                raise Node0004V2ReturnAnalysisError("allowlist path differs")
            payload = returned.read(member)
            if (
                len(payload) != record.get("size_bytes")
                or sha256_bytes(payload) != record.get("sha256")
            ):
                raise Node0004V2ReturnAnalysisError(
                    f"allowlist receipt differs: {relative}"
                )
            declared.add(member)
        if declared != EXPECTED_RETURN_MEMBERS - {allowlist_name}:
            raise Node0004V2ReturnAnalysisError("allowlist exact-set differs")

        evidence = f"{RETURN_ROOT}/evidence"
        package_preflight = _json(
            returned, f"{evidence}/package_preflight.json"
        )
        install_preflight = _json(
            returned, f"{evidence}/install_preflight.json"
        )
        compile_status = _status(
            returned, f"{evidence}/compile_exit_status.txt"
        )
        run_status = _status(returned, f"{evidence}/run_exit_status.txt")
        gate = _json(returned, f"{evidence}/SERVER_RESULT_GATE.json")
        compile_log = returned.read(
            f"{RETURN_ROOT}/runs/compile/sim_results/compile.log"
        ).decode("utf-8", "replace")
        divergence = _compile_divergence(compile_log)

        checks = gate.get("checks")
        if not isinstance(checks, list) or len(checks) != 320:
            raise Node0004V2ReturnAnalysisError("result-gate checks differ")
        missing = sum(record.get("status") == "missing" for record in checks)
        preloaded = sum(
            record.get("runtime_target_preloaded") is True for record in checks
        )
        if missing != 320 or preloaded != 0:
            raise Node0004V2ReturnAnalysisError(
                "fail-closed readback evidence differs"
            )

    with zipfile.ZipFile(source) as packaged:
        source_members = _safe_members(packaged)
        if packaged.testzip() is not None:
            raise Node0004V2ReturnAnalysisError("source ZIP CRC failed")
        manifest = _json(packaged, f"{SOURCE_ROOT}/package_manifest.json")
        source_runtime_targets = [
            name
            for name in source_members
            if re.search(
                r"/workload/runtime/runs/.+/matrix_D_linearized_128bit\.txt$",
                name,
            )
        ]
        observer_members = [
            name
            for name in source_members
            if PurePosixPath(name).name == "native_return_observer.svh"
        ]

    execution_gate = gate.get("execution_gate")
    expected_gate = {
        "compile_exit_status": 2,
        "run_exit_status": 125,
        "compile_succeeded": False,
        "all_simulations_exited_zero": False,
        "terminal_and_readback_gate_satisfied": False,
    }
    gate_pass = (
        gate.get("status") == "NODE0004_SERVER_FAILURE"
        and execution_gate == expected_gate
        and gate.get("readback_count") == 320
        and gate.get("missing_count") == 320
        and gate.get("mismatch_byte_count") == 0
    )
    if (
        package_preflight.get("valid") is not True
        or package_preflight.get("preloaded_readback_target_count") != 0
        or install_preflight.get("valid") is not True
        or install_preflight.get("preloaded_readback_target_count") != 0
        or compile_status != 2
        or run_status != 125
        or not gate_pass
        or source_runtime_targets
    ):
        raise Node0004V2ReturnAnalysisError("v2 fail-closed conjunction differs")

    return {
        "schema": "resnet50-node0004-v2-server-return-analysis-v1",
        "status": "COMPILE_FAILED_NO_DYNAMIC_CONV_EVIDENCE",
        "return_identity": {
            "path": str(supplied),
            "size_bytes": supplied.stat().st_size,
            "sha256": return_sha,
            "expected_sha256": EXPECTED_RETURN_SHA256,
            "identity_match": True,
            "sidecar_supplied": False,
            "zip_crc_valid": True,
            "file_count": len(members),
            "strict_allowlist_valid": True,
        },
        "bound_source_package": {
            "path": SOURCE_REL.as_posix(),
            "sha256": source_sha,
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "identity_match": True,
            "install_name": manifest.get("install_name"),
            "source_zip_runtime_d_target_count": len(source_runtime_targets),
            "source_zip_observer_entry_count": len(observer_members),
        },
        "execution_status": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "compile_succeeded": False,
            "simulation_started": False,
            "terminal_observed": False,
            "formal_dynamic_readback_count": 0,
            "e4_e5_claim_allowed": False,
        },
        "first_divergence": divergence,
        "fail_closed_adjudication": {
            "classification": "V2_RESULT_GATE_FAIL_CLOSED_CONFIRMED",
            "returned_status": gate.get("status"),
            "readback_check_count": len(checks),
            "missing_count": missing,
            "preloaded_target_count": preloaded,
            "mismatch_byte_count": gate.get("mismatch_byte_count"),
            "compile_run_terminal_readback_conjunction_exact": True,
            "v1_false_pass_regression_closed": True,
            "returned_pass_is_dynamic_evidence": False,
        },
        "repair_adjudication": {
            "package_side_legal_fix_confirmed": True,
            "classification": "PACKAGE_LOCAL_OBSERVER_INCLUDE_BINDING_MISSING",
            "proof": (
                "The server TB reported an unconditional relative include of "
                "native_return_observer.svh, while the bound source package "
                "contains no observer entry and the compile command supplies "
                "no package-local observer include directory."
            ),
            "legal_fix": [
                "ship the read-only observer under package-local tb_probe/",
                "hash-check the exact package-local observer before compile",
                "pass +incdir+<package_root>/tb_probe through VCS_EXTRA_OPTS",
                "return the observer precompile receipt through the allowlist",
            ],
            "server_file_write_required": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_tb_or_observer_install_required": False,
            "v3_package_authorized_by_return_evidence": True,
        },
        "blocker_delta": {
            "close": [
                "B_NODE0004_PACKAGE_GATE_FAIL_OPEN",
                "B_NODE0004_SERVER_SOURCE_MERGE_CONFLICT",
            ],
            "add": ["B_NODE0004_PACKAGE_OBSERVER_INCLUDE_PATH"],
            "keep": [
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
                "B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND",
            ],
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "non_conv_retested": False,
            "server_inspection_outside_return_performed": False,
            "compile_failure_is_not_operator_numeric_evidence": True,
        },
    }


__all__ = [
    "Node0004V2ReturnAnalysisError",
    "analyze_node0004_v2_return",
]
