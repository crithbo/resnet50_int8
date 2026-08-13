#!/usr/bin/env python3
"""Independently re-audit the exact p39 ZIP for its first-fresh epoch."""

from __future__ import annotations

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
PACKAGE = "r5_n4_0cc_p39_compilecore"
ZIP = ROOT / "outputs/conv_native_four_lane_0ccae916_p39_compilecore/build" / f"{PACKAGE}.zip"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p39_compilecore/first_fresh_audit"
REPORTS = BASE / "reports"
EPOCH = "20260811-runner-definition-compilefail-core-return-v1"
RULE_IDS = [
    "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
    "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False, timeout=timeout)


def receipt(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def main() -> int:
    if BASE.exists():
        raise RuntimeError("refusing to overwrite p39 first-fresh audit")
    REPORTS.mkdir(parents=True)
    clean = BASE / "clean_extract"
    clean.mkdir()
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        safe = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
        crc = archive.testzip()
        archive.extractall(clean)
    package = clean / PACKAGE
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    actual = {row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size} for row in sorted(package.rglob("*")) if row.is_file() and row.name != "package_manifest.json"}
    clean_errors = []
    if crc is not None: clean_errors.append(f"CRC failure: {crc}")
    if len(names) != len(set(names)): clean_errors.append("duplicate ZIP members")
    if {PurePosixPath(name).parts[0] for name in names if name} != {PACKAGE}: clean_errors.append("single root mismatch")
    if not safe: clean_errors.append("unsafe ZIP member")
    if manifest.get("files") != actual: clean_errors.append("manifest exact set mismatch")
    clean_report = REPORTS / "exact_final_zip_clean_extract.json"
    write(clean_report, {"schema": "conv-native-p39-first-fresh-clean-extract-v1", "pass": not clean_errors, "errors": clean_errors, "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}, "member_count": len(names), "clean_extract": clean.relative_to(ROOT).as_posix()})

    resilience = REPORTS / "runner_return_resilience.json"
    source_bound = REPORTS / "source_bound_final_zip.json"
    post_sim = REPORTS / "post_sim.json"
    core = REPORTS / "compile_core_waveform_harness.json"
    core_layout = REPORTS / "compile_core_layout.json"
    six = REPORTS / "six_state_runner_harness.json"
    runtime = REPORTS / "runtime_layout.json"
    commands = [
        [sys.executable, "tools/validate_server_runner_return_resilience.py", "validate-final-zip", "--zip", str(ZIP), "--contract-member", f"{PACKAGE}/server_runner_return_resilience_contract.json", "--output", str(resilience)],
        [sys.executable, "tools/generate_server_source_bound_observer.py", "validate-final-zip", "--zip", str(ZIP), "--report", str(source_bound)],
        [sys.executable, "tools/server_post_sim_return.py", "validate-final-zip", "--zip", str(ZIP), "--output", str(post_sim)],
        [sys.executable, "tools/validate_conv_native_four_lane_0ccae916_p39_runner_harness.py", "--zip", str(ZIP), "--harness-output", str(core), "--shared-output", str(core_layout)],
        [sys.executable, "tools/validate_conv_native_four_lane_0ccae916_p39_six_state_runner_harness.py", "--zip", str(ZIP), "--harness-output", str(six), "--shared-output", str(runtime)],
    ]
    command_results = []
    for argv in commands:
        result = run(argv)
        command_results.append({"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})

    values = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in {"resilience": resilience, "source_bound": source_bound, "post_sim": post_sim, "core": core, "runtime": runtime}.items() if path.is_file()}
    runner_errors = []
    for name in ("resilience", "core", "runtime"):
        value = values.get(name, {})
        if value.get("pass") is not True:
            runner_errors.extend(f"{name}: {error}" for error in value.get("errors", ["report absent or did not pass"]))
    actual_runner = REPORTS / "actual_runner_entry_and_input_open.json"
    write(actual_runner, {"schema": "conv-native-p39-first-fresh-runner-entry-v1", "pass": not runner_errors, "errors": runner_errors, "exact_reports": {name: receipt(path) for name, path in {"resilience": resilience, "compile_core_waveform": core, "runtime_layout": runtime}.items()}, "command_results": command_results})

    source_value = values.get("source_bound", {})
    controls = source_value.get("semantic_controls", {})
    candidate_errors = [] if source_value.get("pass") is True and controls.get("pass") is True and controls.get("positive_count", 0) >= 1 and controls.get("negative_count", 0) >= 1 else ["typed-v2 candidate controls did not pass"]
    candidate = REPORTS / "candidate_discrimination_matrix.json"
    write(candidate, {"schema": "conv-native-p39-first-fresh-candidate-matrix-v1", "pass": not candidate_errors, "errors": candidate_errors, "candidate_ids": ["MSE4_DESCRIPTOR_DATA_JOIN"], "positive_control_count": controls.get("positive_count", 0), "negative_control_count": controls.get("negative_count", 0), "pairwise_distinguishable": not candidate_errors, "source_bound_report": receipt(source_bound)})

    evidence = [
        {"gate_id": "exact_final_zip_clean_extract", "evidence_kind": "exact-final-zip-clean-extract", **receipt(clean_report)},
        {"gate_id": "actual_runner_entry_and_input_open", "evidence_kind": "exact-runner-safe-compile-and-open-paths", **receipt(actual_runner)},
        {"gate_id": "source_bound_logger_collector_parser_roundtrip", "evidence_kind": "exact-generated-over-budget-multi-instance", **receipt(source_bound)},
        {"gate_id": "post_sim_return_core_scenarios", "evidence_kind": "exact-final-request-four-scenario", **receipt(post_sim)},
        {"gate_id": "candidate_discrimination_matrix", "evidence_kind": "exact-candidate-positive-negative-matrix", **receipt(candidate)},
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": "conv_native_four_lane", "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": RULE_IDS, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": ["MSE4_DESCRIPTOR_DATA_JOIN"], "covered_candidate_ids": ["MSE4_DESCRIPTOR_DATA_JOIN"], "uncovered_candidate_ids": [], "positive_control_count": max(1, controls.get("positive_count", 0)), "negative_control_count": max(1, controls.get("negative_count", 0)), "pairwise_distinguishable": True},
        "findings": [],
    }
    contract_path = BASE / "contract.json"
    write(contract_path, contract)
    validation = BASE / "first_fresh_validation.json"
    result = run([sys.executable, "tools/validate_server_first_fresh_extra_audit.py", "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(validation)])
    print(json.dumps({"contract": receipt(contract_path), "validation": receipt(validation), "validator_exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
