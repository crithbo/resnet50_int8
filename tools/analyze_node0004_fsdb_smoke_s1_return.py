#!/usr/bin/env python3
"""Identity-bound analysis for the first formal node0004 FSDB smoke return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"
RETURN_ROOT = f"{PACKAGE_ID}_return"
PROBE_REL = "tb_probe/fsdb_smoke_event_probe.svh"
RETURN_PROBE_PATH = f"/home/panqs/ndp/{PACKAGE_ID}/{PROBE_REL}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ident(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha256(data)}


def read_json(zf: zipfile.ZipFile, relative: str) -> dict[str, object]:
    return json.loads(zf.read(f"{RETURN_ROOT}/{relative}"))


def safe_names(zf: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    names = zf.namelist()
    errors: list[str] = []
    if len(names) != len(set(names)):
        errors.append("duplicate_zip_member")
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            errors.append(f"unsafe_zip_member:{name}")
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if roots != {RETURN_ROOT}:
        errors.append(f"return_root_mismatch:{sorted(roots)}")
    return names, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", type=Path, required=True)
    ap.add_argument("--package-zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.return_zip) as rz:
        return_names, name_errors = safe_names(rz)
        errors.extend(name_errors)
        bad_crc = rz.testzip()
        checks["return_zip_crc_clean"] = bad_crc is None
        if bad_crc:
            errors.append(f"return_crc_failure:{bad_crc}")

        core_manifest = read_json(rz, "RETURN_CORE_MANIFEST.json")
        core_status = read_json(rz, "return_core/RETURN_CORE_STATUS.json")
        sim_exit = read_json(rz, "return_core/SIM_EXIT_RECEIPT.json")
        argv = read_json(rz, "evidence/compile_rootcause/compile_argv.json")
        sources = read_json(rz, "evidence/compile_rootcause/compile_source_identity.json")
        returned_manifest = read_json(rz, "evidence/returned_package_manifest.json")
        wave = read_json(rz, "waveforms/WAVEFORM_RUNTIME_RECEIPT.json")
        diagnostic = read_json(rz, "evidence/fsdb_smoke/DIAGNOSTIC_STATUS.json")
        driver = rz.read(f"{RETURN_ROOT}/evidence/compile_rootcause/compile_driver.log").decode("utf-8", "replace")
        first_error = rz.read(f"{RETURN_ROOT}/evidence/compile_rootcause/compile_first_error.txt").decode("utf-8", "replace").strip()
        compile_exit = rz.read(f"{RETURN_ROOT}/evidence/compile_rootcause/compile_exit.txt").decode().strip()
        run_exit = rz.read(f"{RETURN_ROOT}/evidence/run_exit_status.txt").decode().strip()

        receipt_mismatches: list[str] = []
        for row in core_manifest.get("core_entry_receipts", []):
            member = f"{RETURN_ROOT}/{row['path']}"
            if member not in return_names:
                receipt_mismatches.append(f"missing:{row['path']}")
                continue
            data = rz.read(member)
            if len(data) != row.get("bytes") or sha256(data) != row.get("sha256"):
                receipt_mismatches.append(f"identity:{row['path']}")
        checks["all_core_receipts_identity_match"] = not receipt_mismatches
        errors.extend(f"core_receipt_{item}" for item in receipt_mismatches)

        basename_match = re.fullmatch(
            rf"{re.escape(PACKAGE_ID)}_(r\d+_\d+)_return\.zip", args.return_zip.name
        )
        execution_id = str(sim_exit.get("execution_id", ""))
        checks["basename_execution_identity_match"] = bool(
            basename_match and basename_match.group(1) == execution_id
        )
        checks["package_identity_consistent"] = all(
            item.get("package_id") == PACKAGE_ID
            for item in (core_manifest, core_status, sim_exit, wave)
        )
        checks["compile_not_started_disposition_consistent"] = (
            compile_exit == "2"
            and run_exit == "125"
            and sim_exit.get("sim_started") is False
            and sim_exit.get("sim_exit_code") == 125
            and core_manifest.get("disposition") == "SIM_NOT_STARTED_RETURN"
            and core_status.get("disposition") == "SIM_NOT_STARTED_RETURN"
        )
        compile_args = argv.get("argv", [])
        checks["compile_profile_fsdb_only"] = all(
            token in compile_args for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")
        )
        checks["production_compiler_received_probe"] = (
            "-sverilog" in driver and RETURN_PROBE_PATH in driver and RETURN_PROBE_PATH in " ".join(compile_args)
        )
        checks["exact_first_error_is_package_probe_keyword"] = (
            first_error == "Error-[SE] Syntax error"
            and f'"{RETURN_PROBE_PATH}",' in driver
            and "3: token is 'sequence'" in driver
            and "integer sequence;" in driver
            and "SystemVerilog  keyword 'sequence'" in driver
        )
        checks["no_simulation_or_fsdb_claim"] = (
            wave.get("simulation_started") is False
            and wave.get("exit_kind") == "COMPILE_FAILURE"
            and wave.get("waveforms") == []
            and diagnostic.get("status") == "NOT_APPLICABLE_SIMULATION_NOT_STARTED"
        )

        source_rows = {row.get("path"): row for row in sources.get("selected_sources", [])}
        returned_probe_source = source_rows.get(RETURN_PROBE_PATH, {})
        manifest_rows = {row.get("path"): row for row in returned_manifest.get("files", [])}
        returned_probe_manifest = manifest_rows.get(PROBE_REL, {})

    with zipfile.ZipFile(args.package_zip) as pz:
        package_names = pz.namelist()
        package_member = f"{PACKAGE_ID}/{PROBE_REL}"
        probe_bytes = pz.read(package_member)
        package_crc = pz.testzip()
        checks["package_zip_crc_clean"] = package_crc is None
        checks["probe_source_identity_matches_pending_zip"] = (
            returned_probe_source.get("exists") is True
            and returned_probe_source.get("bytes") == len(probe_bytes)
            and returned_probe_source.get("sha256") == sha256(probe_bytes)
            and returned_probe_manifest.get("bytes") == len(probe_bytes)
            and returned_probe_manifest.get("sha256") == sha256(probe_bytes)
            and probe_bytes.decode("utf-8").splitlines()[2].strip() == "integer sequence;"
        )
        manifest_mismatches: list[str] = []
        for rel, row in manifest_rows.items():
            member = f"{PACKAGE_ID}/{rel}"
            if member not in package_names:
                manifest_mismatches.append(f"missing:{rel}")
                continue
            data = pz.read(member)
            if len(data) != row.get("bytes") or sha256(data) != row.get("sha256"):
                manifest_mismatches.append(f"identity:{rel}")
        checks["returned_package_manifest_matches_pending_zip"] = not manifest_mismatches
        errors.extend(f"package_manifest_{item}" for item in manifest_mismatches)

    for name, passed in checks.items():
        if not passed:
            errors.append(f"check_failed:{name}")

    report = {
        "schema": "node0004-fsdb-smoke-formal-return-analysis-v1",
        "package_id": PACKAGE_ID,
        "execution_id": execution_id,
        "return_identity": ident(args.return_zip.resolve()),
        "source_package_identity": ident(args.package_zip.resolve()),
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "compile": {
            "exit_code": 2,
            "run_exit_code": 125,
            "simulation_started": False,
            "disposition": "SIM_NOT_STARTED_RETURN",
            "first_error": first_error,
            "first_error_file": RETURN_PROBE_PATH,
            "first_error_line": 3,
            "first_error_token": "sequence",
            "classification": "PACKAGE_LOCAL_COMPILE_FAILURE",
        },
        "last_proven_good": "Package install/preflight, production make entry and VCS invocation reached design-file parsing.",
        "first_divergence": "Production VCS parsed the shipped FSDB smoke probe and rejected line 3 because 'sequence' is a reserved SystemVerilog keyword.",
        "fsdb_v3_adjudication": "NOT_PROVEN_COMPILE_FAILURE",
        "fresh_successor_scope": {
            "authorized": True,
            "identity": "r5_n4_hw_fsdbsmoke_s2",
            "allowed_change": "Rename only the package-local probe identifier and derived package identity; add an exact-final-ZIP lexical keyword gate for this observed failure class.",
            "formal_serialized_successor": False,
        },
        "frozen": {"functional_rtl": True, "config": True, "numeric": True, "workload": True, "golden": True},
        "claim_boundary": "This return proves only a package-local production compile failure. It proves no simulation time advance, FSDB writer, waveform/query completeness, repeat reset, or distinct second return.",
        "conflicts": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "pass": report["pass"], "errors": errors, "output": args.output.as_posix()}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
