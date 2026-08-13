#!/usr/bin/env python3
"""Analyze the exact QAdd v59 formal return without mutating it.

The analyzer safely extracts the supplied return and the exact pending source
package into a family-owned output tree, reproduces only the package-local
preflight, and records lifecycle/waveform/portable evidence boundaries.  It
never uploads, leases, compiles with VCS, or runs a DUT simulation.
"""

from __future__ import annotations

import collections
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v59_portable_vcd_query"
EXECUTION = "r1786512340238213703_1421299"
ATTEMPT = "a1421299"
RETURN_ZIP = Path(
    "C:/Users/15383/Downloads/"
    "r5_qadd_n7_tailround_lanephase_qual_v59_portable_vcd_query_"
    "r1786512340238213703_1421299_return.zip"
)
RETURN_BYTES = 47887
RETURN_SHA256 = "1ed82490ebbb58e8f71f777a2a16cffcfd12ff955b1b291516bb87ed05fba4f6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)
SOURCE_BYTES = 70752607
SOURCE_SHA256 = "b9bee4ac932fbb5b198ca2c6da5cdacb7598356a59a8e55c909b9694255164a0"
OUT = ROOT / "outputs/qlinearadd_v59r1421299"
RETURN_ROOT = f"{PACKAGE}_return"
PREVIOUS_ANALYSIS = (
    ROOT
    / "outputs/qlinearadd_node0007_v57h_formal_return_1113452"
    / "formal_return_analysis.json"
)


class AnalysisError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def safe_extract(zip_path: Path, destination: Path, expected_root: str) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise AnalysisError(f"ZIP CRC failure: {zip_path}")
        names: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                info.filename in names
                or member.is_absolute()
                or any(part in {"", ".", ".."} for part in member.parts)
                or "\\" in info.filename
                or mode == stat.S_IFLNK
            ):
                raise AnalysisError(f"unsafe or duplicate ZIP member: {info.filename}")
            names.add(info.filename)
            roots.add(member.parts[0])
            if info.is_dir():
                continue
            target = destination.joinpath(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, length=1024 * 1024)
    if roots != {expected_root}:
        raise AnalysisError(f"ZIP root differs: {sorted(roots)}")
    return destination / expected_root


def validate_receipts(return_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    rows = list(manifest.get("core_entry_receipts", []))
    rows.extend(manifest.get("waveform_entry_receipts", []))
    errors: list[str] = []
    checked: set[str] = set()
    for row in rows:
        path_text = row.get("path")
        if not isinstance(path_text, str) or path_text in checked:
            continue
        checked.add(path_text)
        pure = PurePosixPath(path_text)
        if pure.is_absolute() or ".." in pure.parts:
            errors.append(f"unsafe receipt path: {path_text}")
            continue
        path = return_root.joinpath(*pure.parts)
        if not path.is_file():
            errors.append(f"receipt member absent: {path_text}")
            continue
        if path.stat().st_size != row.get("bytes"):
            errors.append(f"receipt bytes differ: {path_text}")
        if sha256_file(path) != row.get("sha256"):
            errors.append(f"receipt SHA differs: {path_text}")
    return {
        "pass": not errors,
        "errors": errors,
        "unique_receipt_count": len(checked),
    }


def package_file_records(package_root: Path) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
        name = path.relative_to(package_root).as_posix()
        if name == "TEST_PACKAGE_MANIFEST.json":
            continue
        records[name] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return records


def run_local_preflight(package_root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        str(
            package_root
            / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
        ),
        "preflight",
        "--package-root",
        str(package_root),
    ]
    process = subprocess.run(
        command,
        cwd=package_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "schema": "qlinearadd-node0007-v59-local-preflight-reproduction-v1",
        "pass": process.returncode == 0,
        "exit_code": process.returncode,
        "command": command,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "server_action": False,
        "claim_boundary": "Exact package-local preflight reproduction only.",
    }


def main() -> int:
    if OUT.exists():
        raise AnalysisError(f"fresh analysis root required: {OUT}")
    if (
        not RETURN_ZIP.is_file()
        or RETURN_ZIP.stat().st_size != RETURN_BYTES
        or sha256_file(RETURN_ZIP) != RETURN_SHA256
    ):
        raise AnalysisError("supplied return identity differs")
    if (
        not SOURCE_ZIP.is_file()
        or SOURCE_ZIP.stat().st_size != SOURCE_BYTES
        or sha256_file(SOURCE_ZIP) != SOURCE_SHA256
    ):
        raise AnalysisError("exact pending v59 source package identity differs")
    OUT.mkdir(parents=True)
    return_root = safe_extract(RETURN_ZIP, OUT / "return_extract", RETURN_ROOT)
    package_root = safe_extract(SOURCE_ZIP, OUT / "package_extract", PACKAGE)

    manifest = load_json(return_root / "RETURN_CORE_MANIFEST.json")
    core = load_json(return_root / "return_core/RETURN_CORE_STATUS.json")
    sim_exit = load_json(return_root / "return_core/SIM_EXIT_RECEIPT.json")
    raw = load_json(return_root / "waveforms/WAVEFORM_RUNTIME_RECEIPT.json")
    portable_status = load_json(return_root / "waveforms/PORTABLE_WAVEFORM_STATUS.json")
    portable_request = load_json(return_root / "waveforms/PORTABLE_RUNTIME_REQUEST.json")
    portable_allowlist = load_json(return_root / "waveforms/PORTABLE_RETURN_ALLOWLIST.json")
    package_manifest = load_json(package_root / "TEST_PACKAGE_MANIFEST.json")
    returned_package_manifest = load_json(
        return_root / "source_package/TEST_PACKAGE_MANIFEST.json"
    )
    previous = load_json(PREVIOUS_ANALYSIS)

    preflight = run_local_preflight(package_root)
    preflight_path = OUT / "local_package_preflight_reproduction.json"
    write_json(preflight_path, preflight)

    plan = package_root / "contracts/server_waveform_mandatory_plan.json"
    waveform_inspection_path = OUT / "waveform_return_inspection.json"
    inspect_process = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "tools/server_waveform_mandatory_return.py"),
            "inspect-return",
            "--zip",
            str(RETURN_ZIP),
            "--plan",
            str(plan),
            "--output",
            str(waveform_inspection_path),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    waveform_inspection = (
        load_json(waveform_inspection_path)
        if waveform_inspection_path.is_file()
        else {"pass": False, "errors": [inspect_process.stderr or inspect_process.stdout]}
    )

    receipt_validation = validate_receipts(return_root, manifest)
    source_manifest_exact = (
        (return_root / "source_package/TEST_PACKAGE_MANIFEST.json").read_bytes()
        == (package_root / "TEST_PACKAGE_MANIFEST.json").read_bytes()
    )
    package_exact_set = package_manifest.get("files") == package_file_records(package_root)
    sca = load_json(package_root / "workload/runtime/sca_cfg.json")
    sca_d = load_json(package_root / "workload/runtime/sca_cfg_D.json")
    sca_paths = [
        str(value["path"])
        for value in [*sca.values(), *sca_d.values()]
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    v59_namespace = f"/{PACKAGE}/"
    namespace_checks = {
        "manifest_package_id_is_v59": package_manifest.get("package_id") == PACKAGE,
        "manifest_install_name_is_v58": package_manifest.get("install_name")
        == "r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd",
        "all_sca_paths_use_v59": bool(sca_paths)
        and all(v59_namespace in f"/{path}" for path in sca_paths),
        "local_preflight_reproduced_namespace_failure": (
            preflight["exit_code"] == 1
            and "SCA input namespace/count differs" in preflight["stderr"]
        ),
    }

    execution_ids = {
        manifest.get("execution_id"),
        core.get("execution_id"),
        sim_exit.get("execution_id"),
        raw.get("execution_id"),
        portable_request.get("execution_id"),
    }
    attempt_ids = {
        portable_request.get("attempt_id"),
        load_json(return_root / "evidence/runtime_layout_receipt.json").get("attempt"),
    }
    portable_members = {
        path.name
        for path in (return_root / "waveforms").iterdir()
        if path.is_file()
    }
    lifecycle_checks = {
        "return_package_identity": manifest.get("package_id") == PACKAGE,
        "return_basename_identity": manifest.get("return_basename")
        == RETURN_ZIP.name,
        "execution_identity_same": execution_ids == {EXECUTION},
        "attempt_identity_same": attempt_ids == {ATTEMPT},
        "return_receipts_exact": receipt_validation["pass"],
        "source_manifest_exact": source_manifest_exact,
        "package_manifest_exact_set": package_exact_set,
        "compile_not_started_default_125": (
            (return_root / "evidence/compile_exit_status.txt")
            .read_text(encoding="ascii")
            .strip()
            == "125"
        ),
        "simulation_not_started": (
            sim_exit.get("sim_started") is False
            and sim_exit.get("sim_exit_code") == 125
            and sim_exit.get("signal") == "NONE"
        ),
        "natural_terminal_absent": sim_exit.get("natural_terminal_observed") is False,
        "raw_compile_before_start_exception_valid": (
            raw.get("simulation_started") is False
            and raw.get("waveforms") == []
            and raw.get("pass") is True
            and raw.get("no_size_limit") is True
        ),
        "portable_evidence_incomplete": portable_status.get("diagnostic_status")
        == "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "portable_failure_preserves_return": (
            portable_status.get("return_must_publish") is True
            and portable_status.get("raw_core_return_preserved") is True
        ),
        "direct_vcd_absent": "wave.vcd" not in portable_members,
        "registered_query_absent": "SIGNAL_QUERY_RECEIPT.json" not in portable_members,
        "formal_d_absent": core.get("sim_exit", {}).get("sim_started") is False,
        "shared_waveform_inspection_pass": waveform_inspection.get("pass") is True,
    }
    shared_escape_signature = {
        "compile_exit_zero": False,
        "simv_exit_zero": False,
        "no_time0_or_progress_marker": True,
        "no_dut_rows": True,
        "direct_vcd_absent": True,
        "query_event_count_zero": True,
        "raw_vpd_partial": False,
    }
    shared_escape_signature_present = all(shared_escape_signature.values())

    errors = [
        name
        for name, passed in {**namespace_checks, **lifecycle_checks}.items()
        if passed is not True
    ]
    analysis = {
        "schema": "qlinearadd-node0007-v59-formal-return-analysis-v1",
        "status": "FORMAL_ANALYSIS_COMPLETE_SUCCESSOR_HOLD_SHARED_RUNTIME_FIX",
        "pass": not errors,
        "errors": errors,
        "family": "qlinearadd_node0007",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "formal_return": receipt(RETURN_ZIP),
        "source_package": receipt(SOURCE_ZIP),
        "integrity": {
            "safe_single_root": True,
            "crc_pass": True,
            "no_duplicate_or_escape_members": True,
            "receipt_validation": receipt_validation,
            "source_manifest_exact": source_manifest_exact,
            "package_manifest_exact_set": package_exact_set,
        },
        "previous_version_progress": (
            "v57h localized FIRST_DIVERGENCE to selected ping-pong port 0 "
            "required lanes not becoming ready between Buffer5 request decode and "
            "read accept; v58 preserved that causal target under mandatory raw VPD."
        ),
        "current_version_purpose": (
            "v59 was intended to add same-attempt direct portable VCD and complete "
            "source-bound query/event evidence for local producer/clear/selected-"
            "port/bank-lane readiness adjudication."
        ),
        "execution": {
            "compile_started": False,
            "compile_exit_status_field": 125,
            "simulation_started": False,
            "simulation_exit_status_field": 125,
            "signal": "NONE",
            "termination": "PACKAGE_PREFLIGHT_FAILURE_BEFORE_COMPILE",
            "natural_terminal": False,
            "formal_D": "NOT_FORMED",
            "E3": "NOT_REACHED",
            "E4": "NOT_REACHED",
            "E5": "NOT_REACHED",
            "missing_compile_core": manifest.get("missing_required_entries", []),
        },
        "waveform_and_query": {
            "raw_vpd": "LEGITIMATELY_ABSENT_BECAUSE_SIMULATION_NOT_STARTED",
            "direct_vcd": "ABSENT",
            "registered_query": "ABSENT",
            "portable_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "same_attempt_metadata_binding": execution_ids == {EXECUTION}
            and attempt_ids == {ATTEMPT},
            "same_attempt_signal_evidence_available": False,
            "prior_decoder_gap_closed": False,
            "allowlist": portable_allowlist,
            "shared_waveform_inspection": receipt(waveform_inspection_path),
            "cross_family_shared_runtime_escape_signature": {
                "checks": shared_escape_signature,
                "present": shared_escape_signature_present,
                "classification": (
                    "SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE"
                    if shared_escape_signature_present
                    else "NOT_OBSERVED_QADD_DID_NOT_REACH_COMPILE_OR_SIMULATION"
                ),
                "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            },
        },
        "local_reproduction": {
            "report": receipt(preflight_path),
            "namespace_checks": namespace_checks,
            "root_cause": (
                "TEST_PACKAGE_MANIFEST.install_name remains v58 while package_id, "
                "runner and every SCA input/output namespace are v59. The exact "
                "package-local runtime therefore rejects SCA input namespace/count "
                "during preflight before compile argv/core evidence is created."
            ),
        },
        "LAST_PROVEN_GOOD": previous["LAST_PROVEN_GOOD"],
        "FIRST_DIVERGENCE": previous["FIRST_DIVERGENCE"],
        "execution_first_divergence": {
            "boundary": "PACKAGE_MANIFEST_INSTALL_NAME_TO_SCA_NAMESPACE_PREFLIGHT",
            "classification": "PACKAGE_LOCAL_PREFLIGHT_IDENTITY_MISMATCH",
            "functional_DUT_root_claimed": False,
        },
        "root_classification": "PACKAGE_LOCAL_PREFLIGHT_IDENTITY_MISMATCH",
        "successor_directive": {
            "justified": True,
            "fresh_identity_required": True,
            "status": "HOLD_CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_REQUIRED",
            "build_authorized_now": False,
            "resume_condition": "CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY",
            "allowed_changes": [
                "fresh package identity",
                "manifest install_name/package_id binding",
                "identity-bound runner/contracts/SCA paths",
                "runtime/formal-return provenance",
            ],
            "must_retain": [
                "authoritative unbounded raw VPD",
                "same-attempt direct unbounded VCD",
                "registered complete source-bound query",
                "v58/v59 tail-round lane-phase diagnostic exact bytes",
            ],
            "frozen": [
                "config semantics",
                "numeric",
                "workload",
                "golden",
                "functional RTL",
                "target diagnostic",
            ],
            "shared_tool_patch_by_family": False,
        },
        "server_action": False,
        "claim_boundary": (
            "Return/package integrity and package-local preflight root cause only; "
            "no new DUT signal, natural-terminal, formal-D, E3, E4 or E5 claim."
        ),
    }
    analysis_path = OUT / "formal_return_analysis.json"
    write_json(analysis_path, analysis)
    hold_receipt = {
        "schema": "qlinearadd-node0007-v59-formal-return-hold-receipt-v1",
        "status": analysis["status"],
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "formal_analysis": receipt(analysis_path),
        "formal_return": receipt(RETURN_ZIP),
        "source_package": receipt(SOURCE_ZIP),
        "root_classification": analysis["root_classification"],
        "cross_family_shared_runtime_escape_signature_present": (
            shared_escape_signature_present
        ),
        "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "LAST_PROVEN_GOOD": analysis["LAST_PROVEN_GOOD"],
        "FIRST_DIVERGENCE": analysis["FIRST_DIVERGENCE"],
        "prior_decoder_gap_closed": False,
        "successor": analysis["successor_directive"],
        "storage_mutation": False,
        "shared_tool_mutation": False,
        "server_action": False,
    }
    hold_receipt_path = OUT / "qadd_formal_return_hold_receipt.json"
    write_json(hold_receipt_path, hold_receipt)
    print(
        json.dumps(
            {
                "status": analysis["status"],
                "pass": analysis["pass"],
                "root_classification": analysis["root_classification"],
                "compile_started": False,
                "simulation_started": False,
                "prior_decoder_gap_closed": False,
                "analysis": receipt(analysis_path),
                "hold_receipt": receipt(hold_receipt_path),
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
