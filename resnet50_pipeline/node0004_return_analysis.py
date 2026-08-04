from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_PACKAGE_SHA256 = (
    "335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989"
)
PACKAGE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.zip"
)
RETURN_ROOT = "r5_node0004_hw_v1_return"
PACKAGE_ROOT = "r5_node0004_hw_v1"


class Node0004ReturnAnalysisError(ValueError):
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
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or name in seen
        ):
            raise Node0004ReturnAnalysisError(f"unsafe ZIP member: {name}")
        mode = info.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise Node0004ReturnAnalysisError(f"ZIP symlink is forbidden: {name}")
        seen.add(name)
        if not info.is_dir():
            names.append(name)
    return names


def _json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise Node0004ReturnAnalysisError(
            f"cannot parse required JSON member: {name}"
        ) from error
    if not isinstance(value, dict):
        raise Node0004ReturnAnalysisError(f"JSON root must be object: {name}")
    return value


def _int_member(archive: zipfile.ZipFile, name: str) -> int:
    try:
        return int(archive.read(name).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise Node0004ReturnAnalysisError(
            f"cannot parse required status member: {name}"
        ) from error


def _first_compile_divergence(log_text: str) -> dict[str, Any]:
    lines = log_text.splitlines()
    syntax_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "Error-[SE] Syntax error" in line
        ),
        None,
    )
    marker_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().startswith("<<<<<<<")
        ),
        None,
    )
    source_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "SA_PE_Float_Control.v" in line
            and index > (syntax_index or 0)
        ),
        None,
    )
    if syntax_index is None or marker_index is None or source_index is None:
        raise Node0004ReturnAnalysisError(
            "compile failure is not the expected conflict-marker signature"
        )
    source_line = lines[source_index].strip().strip('",')
    source_match = re.search(r'"([^"]*SA_PE_Float_Control\.v)"', lines[source_index])
    source = source_match.group(1) if source_match else source_line
    return {
        "classification": "SERVER_SOURCE_MERGE_CONFLICT_COMPILE_FAILURE",
        "compile_log_line": syntax_index + 1,
        "source_report_line": source_index + 1,
        "marker_log_line": marker_index + 1,
        "source_path_reported_by_vcs": source,
        "source_line_reported_by_vcs": 1,
        "token_reported_by_vcs": "<<<",
        "conflict_marker": lines[marker_index].strip(),
        "simulation_started": False,
        "operator_numeric_evidence_produced": False,
    }


def analyze_node0004_return(
    project_root: Path,
    return_zip: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    supplied = return_zip.resolve()
    if not supplied.is_file():
        raise Node0004ReturnAnalysisError(f"return ZIP is missing: {supplied}")

    package_zip = root / PACKAGE_REL
    if not package_zip.is_file():
        raise Node0004ReturnAnalysisError(
            f"bound original package is missing: {package_zip}"
        )
    package_sha = sha256_file(package_zip)
    if package_sha != EXPECTED_PACKAGE_SHA256:
        raise Node0004ReturnAnalysisError(
            f"original package identity drifted: {package_sha}"
        )

    return_sha = sha256_file(supplied)
    with zipfile.ZipFile(supplied) as returned:
        return_members = _safe_members(returned)
        bad_member = returned.testzip()
        if bad_member is not None:
            raise Node0004ReturnAnalysisError(
                f"return ZIP CRC failure: {bad_member}"
            )
        prefix = f"{RETURN_ROOT}/"
        if any(not name.startswith(prefix) for name in return_members):
            raise Node0004ReturnAnalysisError("return ZIP has an unexpected root")

        evidence = f"{RETURN_ROOT}/evidence"
        compile_status = _int_member(
            returned, f"{evidence}/compile_exit_status.txt"
        )
        run_status = _int_member(returned, f"{evidence}/run_exit_status.txt")
        preflight = _json_member(returned, f"{evidence}/package_preflight.json")
        gate = _json_member(returned, f"{evidence}/SERVER_RESULT_GATE.json")
        compile_log_name = (
            f"{RETURN_ROOT}/runs/compile/sim_results/compile.log"
        )
        compile_log = returned.read(compile_log_name).decode("utf-8", "replace")
        first_divergence = _first_compile_divergence(compile_log)

        checks = gate.get("checks")
        if not isinstance(checks, list):
            raise Node0004ReturnAnalysisError("result gate checks are missing")

        with zipfile.ZipFile(package_zip) as packaged:
            package_members = set(_safe_members(packaged))
            manifest = _json_member(
                packaged, f"{PACKAGE_ROOT}/package_manifest.json"
            )
            readback_records = manifest.get("readback_checks")
            if not isinstance(readback_records, list):
                raise Node0004ReturnAnalysisError(
                    "bound package readback checks are missing"
                )
            if len(readback_records) != len(checks):
                raise Node0004ReturnAnalysisError(
                    "return/package readback check counts differ"
                )

            preloaded = 0
            returned_actual_matches_preload = 0
            returned_golden_matches_package = 0
            for record, check in zip(readback_records, checks, strict=True):
                runtime = str(record["runtime_path"])
                golden = str(record["golden_path"])
                runtime_member = (
                    f"{PACKAGE_ROOT}/workload/runtime/{runtime}"
                )
                golden_member = f"{PACKAGE_ROOT}/{golden}"
                if runtime_member in package_members:
                    preloaded += 1
                if (
                    runtime_member in package_members
                    and check.get("actual_sha256")
                    == sha256_bytes(packaged.read(runtime_member))
                ):
                    returned_actual_matches_preload += 1
                if (
                    golden_member in package_members
                    and check.get("golden_sha256")
                    == sha256_bytes(packaged.read(golden_member))
                ):
                    returned_golden_matches_package += 1

    compile_failed = compile_status != 0
    run_not_started = run_status == 125
    stale_gate_pass = gate.get("status") == "THREE_PHASE_NODE0004_PASS"
    fail_open_confirmed = (
        compile_failed
        and run_not_started
        and stale_gate_pass
        and preloaded == len(checks)
        and returned_actual_matches_preload == len(checks)
    )
    if not fail_open_confirmed:
        raise Node0004ReturnAnalysisError(
            "return does not close the expected package fail-open proof"
        )

    return {
        "schema": "resnet50-node0004-server-return-first-divergence-v1",
        "status": "COMPILE_FAILED_NO_DYNAMIC_CONV_EVIDENCE",
        "return_identity": {
            "path": str(supplied),
            "size_bytes": supplied.stat().st_size,
            "sha256": return_sha,
            "sidecar_supplied": False,
            "zip_crc_valid": True,
            "file_count": len(return_members),
        },
        "bound_package_identity": {
            "path": PACKAGE_REL.as_posix(),
            "sha256": package_sha,
            "expected_sha256": EXPECTED_PACKAGE_SHA256,
            "identity_match": True,
        },
        "execution_status": {
            "package_preflight": preflight,
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "compile_succeeded": False,
            "simulation_started": False,
            "terminal_observed": False,
            "formal_dynamic_readback_count": 0,
            "e4_e5_claim_allowed": False,
        },
        "first_divergence": first_divergence,
        "result_gate_adjudication": {
            "returned_status": gate.get("status"),
            "returned_readback_count": gate.get("readback_count"),
            "returned_missing_count": gate.get("missing_count"),
            "returned_mismatch_byte_count": gate.get("mismatch_byte_count"),
            "package_readback_check_count": len(checks),
            "runtime_targets_preloaded_in_package": preloaded,
            "returned_actual_hashes_matching_package_preloads": (
                returned_actual_matches_preload
            ),
            "returned_golden_hashes_matching_package_goldens": (
                returned_golden_matches_package
            ),
            "classification": "PACKAGE_RESULT_GATE_FAIL_OPEN",
            "proof": (
                "All declared runtime D targets were shipped pre-populated. "
                "The compile failed before simulation, yet analyze compared "
                "those untouched files with package goldens and emitted PASS."
            ),
            "returned_pass_is_dynamic_evidence": False,
        },
        "repair_scope": {
            "functional_rtl_modified": False,
            "server_rtl_conflict_marker_package_fixable": False,
            "package_fix_required": [
                "do not ship any declared runtime D target",
                "require compile_exit_status=0 and run_exit_status=0",
                "return only allowlisted logs, evidence, and produced readbacks",
            ],
            "rerun_precondition": (
                "The server owner must resolve the merge conflict marker in "
                "the active SA_PE_Float_Control.v before a rerun can compile."
            ),
        },
        "claim_boundary": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "non_conv_retested": False,
            "server_inspection_performed_outside_return": False,
        },
    }


__all__ = [
    "Node0004ReturnAnalysisError",
    "analyze_node0004_return",
    "sha256_file",
]
