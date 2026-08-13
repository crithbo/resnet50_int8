#!/usr/bin/env python3
"""Validate and classify the formal p5 c0-diagnostic server return.

This analyzer is intentionally read-only with respect to the returned archive
and the source package.  It distinguishes a production compile failure from a
simulation/c0 diagnostic result and therefore never treats absent formal-D
payloads as a correctness failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_n4_e1f_p5_c0diag_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n4_e1f_p5_c0diag.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_e1fb0f7_p5_return_analysis"
    / "report.json"
)
EXPECTED_RETURN_SHA = (
    "bcebec2837fdf3398d2786bf7c75dc6bf5b4c6012d136911e9d998844232aeb0"
)
EXPECTED_RETURN_BYTES = 41417
EXPECTED_SOURCE_SHA = (
    "393428f1ac860d89daa56543a8e27521c79e0965d5eaa197c074d81219cc6cb8"
)
INSTALL_NAME = "r5_n4_e1f_p5_c0diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or not pure.parts
            or pure.parts[0] != expected_root
        ):
            errors.append(f"unsafe_path:{name}")
            continue
        if name in seen:
            errors.append(f"duplicate:{name}")
            continue
        seen.add(name)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            errors.append(f"symlink:{name}")
        if info.is_dir():
            continue
        payload = archive.read(info)
        relative = PurePosixPath(*pure.parts[1:]).as_posix()
        records[relative] = {
            "size_bytes": len(payload),
            "sha256": digest(payload),
        }
    return records, errors


def git_head(repo: Path) -> str | None:
    safe = str(repo.resolve()).replace("\\", "/")
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(repo),
            "rev-parse",
            "HEAD",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return process.stdout.strip() if process.returncode == 0 else None


def analyze(return_zip: Path) -> dict[str, Any]:
    source_identity = {
        "path": str(SOURCE_ZIP),
        "exists": SOURCE_ZIP.is_file(),
        "size_bytes": SOURCE_ZIP.stat().st_size if SOURCE_ZIP.is_file() else None,
        "sha256": sha256(SOURCE_ZIP) if SOURCE_ZIP.is_file() else None,
        "expected_sha256": EXPECTED_SOURCE_SHA,
    }
    outer_identity = {
        "path": str(return_zip),
        "exists": return_zip.is_file(),
        "size_bytes": return_zip.stat().st_size if return_zip.is_file() else None,
        "sha256": sha256(return_zip) if return_zip.is_file() else None,
        "expected_size_bytes": EXPECTED_RETURN_BYTES,
        "expected_sha256": EXPECTED_RETURN_SHA,
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "transport_sidecar_waiver_only": True,
    }
    if not return_zip.is_file() or not SOURCE_ZIP.is_file():
        return {
            "schema": "conv-native-four-lane-p5-return-analysis-v1",
            "valid": False,
            "outer_return_identity": outer_identity,
            "source_package_identity": source_identity,
            "errors": ["missing_return_or_source_zip"],
        }

    with zipfile.ZipFile(return_zip) as archive:
        return_records, return_zip_errors = safe_records(archive, RETURN_ROOT)
        contents = {
            relative: archive.read(f"{RETURN_ROOT}/{relative}")
            for relative in return_records
        }
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_zip_errors = safe_records(archive, INSTALL_NAME)
        source_manifest_bytes = archive.read(
            f"{INSTALL_NAME}/package_manifest.json"
        )

    return_manifest = json.loads(contents["RETURN_MANIFEST.json"])
    return_allowlist = json.loads(contents["RETURN_ALLOWLIST.json"])
    package_manifest_bytes = contents["source_package/package_manifest.json"]
    package_manifest = json.loads(package_manifest_bytes)
    result_gate = json.loads(contents["evidence/SERVER_RESULT_GATE.json"])
    package_preflight = json.loads(contents["evidence/package_preflight.json"])
    install_preflight = json.loads(contents["evidence/install_preflight.json"])
    observer_guard = json.loads(contents["evidence/observer_precompile.json"])
    compile_argv = contents["evidence/compile_argv.txt"].decode(
        errors="replace"
    ).strip()
    compile_status = contents["evidence/compile_exit_status.txt"].decode().strip()
    run_status = contents["evidence/run_exit_status.txt"].decode().strip()
    signal_status = contents["evidence/signal_status.txt"].decode().strip()
    compile_log = contents["runs/compile/compile.log"].decode(errors="replace")
    driver_log = contents["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )

    declared = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in return_manifest["records_excluding_this_manifest"]
    }
    exact_expected = set(declared) | {
        "RETURN_MANIFEST.json",
        "RETURN_ALLOWLIST.json",
    }
    exact_actual = set(return_records)
    record_mismatches = {
        path: {
            "expected": declared[path],
            "observed": return_records.get(path),
        }
        for path in sorted(declared)
        if return_records.get(path) != declared[path]
    }
    allowlist_record = next(
        item
        for item in return_allowlist["records"]
        if item["path"] == "RETURN_MANIFEST.json"
    )
    allowlist_binding = {
        "return_manifest": (
            allowlist_record["size_bytes"]
            == return_records["RETURN_MANIFEST.json"]["size_bytes"]
            and allowlist_record["sha256"]
            == return_records["RETURN_MANIFEST.json"]["sha256"]
        ),
        "declared_allowlist_equal": (
            return_allowlist["declared_allowlist"]
            == return_manifest["declared_allowlist"]
        ),
    }

    xmre_locations = [
        {
            "file": match.group("file"),
            "line": int(match.group("line")),
            "token": match.group("token"),
        }
        for match in re.finditer(
            r"Error-\[XMRE\][^\n]*\n"
            r"(?P<file>[^,\n]+), (?P<line>\d+)\n.*?"
            r"token '(?P<token>[^']+)'",
            driver_log,
            flags=re.DOTALL,
        )
    ]
    xmre_count = len(re.findall(r"Error-\[XMRE\]", driver_log))
    error_limit_reached = "Maximum error count reached" in driver_log
    dynamic_paths = sorted(
        path
        for path in return_records
        if path.startswith("runs/c0/")
        or path.startswith("evidence/feature_binding/")
        or path.startswith("evidence/natural_terminal/")
    )

    local_repo = ROOT / "Trassic2.0_RTL"
    local_leaf = (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster"
        / "Array_Request_Manager.sv"
    )
    if not local_leaf.is_file():
        matches = list(
            (ROOT / "NDP_copy01/rtl").rglob("Array_Request_Manager.sv")
        )
        local_leaf = matches[0] if matches else local_leaf

    receipt_checks = {
        "outer_return_identity_exact": (
            outer_identity["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer_identity["sha256"] == EXPECTED_RETURN_SHA
        ),
        "source_package_identity_exact": (
            source_identity["sha256"] == EXPECTED_SOURCE_SHA
        ),
        "return_zip_safe": not return_zip_errors,
        "source_zip_safe": not source_zip_errors,
        "return_exact_set": exact_actual == exact_expected,
        "return_record_hashes_exact": not record_mismatches,
        "allowlist_binding_exact": all(allowlist_binding.values()),
        "source_manifest_return_binding": (
            package_manifest_bytes == source_manifest_bytes
            and digest(package_manifest_bytes)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_manifest_files_exact": (
            package_manifest["files"]
            == {
                path: record
                for path, record in source_records.items()
                if path != "package_manifest.json"
            }
        ),
        "package_preflight_valid": package_preflight.get("valid") is True,
        "install_preflight_valid": install_preflight.get("valid") is True,
        "observer_precompile_guard_valid": observer_guard.get("valid") is True,
        "compile_argv_observer_enabled": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv
            and "+incdir+" in compile_argv
            and "tb_probe" in compile_argv
        ),
        "compile_failed_before_simulation": (
            compile_status == "2"
            and run_status == "125"
            and signal_status == "NONE"
            and xmre_count > 0
            and not dynamic_paths
        ),
        "formal_d_not_claimed": (
            package_manifest.get("formal_readback_count") == 0
            and result_gate.get("execution_gate", {}).get("formal_D_claimed")
            is False
        ),
    }
    valid = all(receipt_checks.values())
    return {
        "schema": "conv-native-four-lane-p5-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE" if valid else "FAIL",
        "valid": valid,
        "classification": "P5_PRODUCTION_COMPILE_FAILURE_CONSUMABLE",
        "outer_return_identity": outer_identity,
        "source_package_identity": source_identity,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(return_records),
            "return_manifest_sha256": return_records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": return_records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "source_package_manifest_sha256": digest(package_manifest_bytes),
            "return_zip_errors": return_zip_errors,
            "source_zip_errors": source_zip_errors,
            "exact_set_missing": sorted(exact_expected - exact_actual),
            "exact_set_extra": sorted(exact_actual - exact_expected),
            "record_mismatches": record_mismatches,
            "allowlist_binding": allowlist_binding,
            "checks": receipt_checks,
        },
        "actual_execution": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile_guard": observer_guard,
            "compile_argv": compile_argv,
            "compile_exit_status": int(compile_status),
            "run_exit_status": int(run_status),
            "signal_status": signal_status,
            "server_result_gate": result_gate,
            "dynamic_c0_artifacts": dynamic_paths,
            "simulation_started": False,
            "formal_320d_scope_in_package": False,
            "formal_320d_result": "NOT_APPLICABLE_TO_P5_C0_DIAGNOSTIC",
        },
        "actual_compile_identity": {
            "receipt_present": "evidence/production_rtl_identity.json"
            in return_records,
            "match_claim_allowed": False,
            "classification": "UNAVAILABLE_COMPILE_DID_NOT_COMPLETE",
            "compile_path_provenance_only": (
                "/home/panqs/ndp/NDP_copy02" in compile_argv
            ),
            "warning": (
                "A path in compile_argv is not a production RTL byte-identity "
                "receipt and cannot be promoted to one."
            ),
        },
        "failure_localization": {
            "LPG": [
                "outer return/source package identities exact",
                "return exact-set, internal hashes, and manifest binding exact",
                "package/install/observer precompile guards valid",
                "production VCS invoked with package observer define/include",
                "VCS parsed package observer and entered elaboration",
            ],
            "FD": (
                "production VCS cross-module reference resolution at "
                "tb_probe/native_return_observer.svh:350"
            ),
            "HANG_ROOT_CAUSE": (
                "NOT_REACHED_SIMULATION_PACKAGE_OBSERVER_PRIVATE_XMR_FAILURE"
            ),
            "vcs_error_class": "XMRE",
            "xmre_count": xmre_count,
            "error_limit_reached": error_limit_reached,
            "xmre_locations": xmre_locations,
            "private_token": "buf2arm_valid_hold",
            "compile_log_sha256": digest(
                contents["runs/compile/compile.log"]
            ),
            "compile_driver_log_sha256": digest(
                contents["runs/compile/compile_driver.log"]
            ),
        },
        "blocker_delta": {
            "closed": [
                "p5 delivery, extraction, exact-set, and precompile guards",
                "production compiler invocation with the observer enabled",
            ],
            "new": [
                "B_P5_OBSERVER_PRIVATE_XMR_PRODUCTION_RESOLUTION",
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_EXEC_TO_SLICE_FINISH_UNDIAGNOSED",
                "B_CONV_NATIVE4_NATURAL_TERMINAL_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_NOT_IN_P5_SCOPE",
                "B_CONV_NATIVE4_ACTUAL_PRODUCTION_RTL_IDENTITY_UNAVAILABLE",
            ],
        },
        "claim_boundary": {
            "c0_boundary_diagnostic_result": "NONE_COMPILE_FAILED",
            "historical_c0_hang_root_cause": "NOT_ADJUDICATED_BY_P5",
            "formal_d_pass_or_failure_claim_allowed": False,
            "performance_e3_e4_e5_claim_allowed": False,
            "successor_required": True,
            "successor_scope": (
                "fresh package-local observer-only replacement of the private "
                "hold-state XMR by an interface-derived hold-set-pressure witness"
            ),
        },
        "current_local_context_not_actual_compile_identity": {
            "rtl_repo_head": git_head(local_repo),
            "array_request_manager_path": str(local_leaf),
            "array_request_manager_sha256": (
                sha256(local_leaf) if local_leaf.is_file() else None
            ),
            "private_token_present": (
                "buf2arm_valid_hold"
                in local_leaf.read_text(encoding="utf-8", errors="replace")
                if local_leaf.is_file()
                else None
            ),
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "statement": (
                "The current server-package rule correctly keeps production-only "
                "elaboration evidence below simulation/320D claims and requires "
                "a fresh successor; no non-synonymous public-rule delta is proven."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve())
    write_json(args.output.resolve(), result)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
