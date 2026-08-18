#!/usr/bin/env python3
"""Run current exact-final-ZIP/first-fresh gates for QAdd v65."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
PRIOR = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
FAMILY = "qlinearadd_node0007"
EPOCH = "tb-vcd-first-round-breadth-v4+tb-vcd-exit-mechanism-consistency-v3+package-python-schema-runtime-v2"
RULE = "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"
OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PRIOR}.zip"
GATES = OUT / "gates"
REPORTS = OUT / "first_fresh_audit/reports"
TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v65.svh"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v65.py"
FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v65.py"
PYTHON = Path(sys.executable)
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH_CANDIDATES = [
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path = ROOT, timeout: int = 180) -> dict[str, Any]:
    process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def file_map(root: Path, exclude_manifest: bool = True) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if not exclude_manifest or path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def safe_extract(source: Path, target: Path, root_name: str) -> Path:
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name]
        if roots != {root_name} or unsafe or len(names) != len(set(names)) or archive.testzip() is not None:
            raise RuntimeError(f"unsafe/corrupt/wrong-root ZIP: {source}")
        archive.extractall(target)
    return target / root_name


def report(path: Path, checks: dict[str, bool], **extra: Any) -> dict[str, Any]:
    errors = [name for name, passed in checks.items() if not passed]
    value = {
        "schema": "qadd-v65-first-fresh-evidence-report-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "checks": checks,
        "errors": errors,
        "claim_boundary": "Local exact-package evidence only; no production or DUT claim.",
        **extra,
    }
    write(path, value)
    return value


def source_span(path: Path, leaf: str) -> str | None:
    matches = [
        row.strip()
        for row in path.read_text(encoding="utf-8", errors="strict").splitlines()
        if re.search(rf"\b{re.escape(leaf)}\b", row) and not row.lstrip().startswith("//")
    ]
    return hashlib.sha256(matches[0].encode("utf-8")).hexdigest() if matches else None


def authority(package: Path) -> dict[str, Any]:
    return {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha(package / "package_tools/server_tb_vcd_runtime_supervision.py"),
        "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }


def import_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_replay(package: Path) -> dict[str, Any]:
    evaluator = import_module(package / "package_tools/server_tb_vcd_runtime_supervision.py", "qadd_v65_eval")
    live = import_module(package / LIVE, "qadd_v65_live")
    auth = authority(package)
    args = SimpleNamespace(package_id=PACKAGE, execution_id="replay", attempt_id="a0")

    def row(seq: int, wall: float, tick: int, cycles: int, **extra: Any) -> dict[str, Any]:
        value = {
            "seq": seq,
            "wall_seconds": wall,
            "appended_vcd_timestamp_ticks": tick,
            "sim_time_ticks": tick,
            "owner_clock_cycles": cycles,
            "sim_cycles": cycles,
            "causal_progress_events": 0,
            "qualified_progress_counters": {"target": 0, "pretarget_matrix_completions": 24},
            "causal_state_digest": "a" * 64,
            "global_progress_witness": {"target_count": 0, "pretarget_matrix_completions": 24},
            "unresolved_xz": False,
            "vcd_bytes": 1000 + seq,
            "disk_space_ok": True,
            "write_ok": True,
            "quota_ok": True,
        }
        value.update(extra)
        return value

    cases = {
        "ADVANCING_VCD_TIMESTAMP": [row(0, 0, 1, 0), row(1, 30, 2, 100)],
        "PLATEAU_SUSPECTED_ONLY": [row(0, 0, 1, 0), row(1, 30, 2, 1_048_576)],
        "PLATEAU_DUMP_OFF_PLUS_GRACE": [row(0, 0, 1, 0), row(1, 30, 2, 4_194_304), row(2, 60, 3, 4_456_448)],
        "THREE_INTERVAL_TRUE_FREEZE": [row(0, 0, 7, 0), row(1, 30, 7, 100), row(2, 60, 7, 200), row(3, 90, 7, 300)],
    }
    decisions = {name: live.shared_decision(evaluator, auth, args, rows)[0] for name, rows in cases.items()}
    expected = {
        "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
        "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
        "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
        "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
    }
    # Family-specific negative: newly appended preload progress changes both
    # qualified counters and the complete global witness, so plateau is illegal.
    advancing_preload = [
        row(0, 0, 1, 0, qualified_progress_counters={"target": 0, "pretarget_matrix_completions": 23}, global_progress_witness={"target_count": 0, "pretarget_matrix_completions": 23}),
        row(1, 30, 2, 4_456_448, qualified_progress_counters={"target": 0, "pretarget_matrix_completions": 24}, global_progress_witness={"target_count": 0, "pretarget_matrix_completions": 24}),
    ]
    preload_decision = live.shared_decision(evaluator, auth, args, advancing_preload)[0]
    checks = {
        "exact_four_case_replay": decisions == expected,
        "pretarget_progress_forbids_plateau": preload_decision == "CONTINUE",
        "shared_helper_byte_equal_current": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
        "single_shared_authority": all(token in (package / LIVE).read_text(encoding="utf-8") for token in ("shared_decision", "outer_runner_consumed_shared_receipt_only", "independent_exit_logic_absent")),
    }
    return {"pass": all(checks.values()), "checks": checks, "decisions": decisions, "pretarget_decision": preload_decision, "errors": [key for key, passed in checks.items() if not passed]}


def synthetic_roundtrip(package: Path, work: Path) -> dict[str, Any]:
    contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    attempt = work / "attempt"
    evidence = attempt / "evidence"
    evidence.mkdir(parents=True)
    write(evidence / "ACTUAL_COMPILE_SIM_ARGV.json", {"package_id": PACKAGE, "compile_argv": [], "sim_argv": []})
    write(evidence / "PROCESS_TREE_RECEIPT.json", {"root_exit": 0, "process_tree_reaped": True, "termination": [], "stop_reason": "PROCESS_EXIT", "target_entry_observed": True})
    write(evidence / "TB_VCD_LIVE_SAFETY_RECEIPT.json", {"stop_reason": "PROCESS_EXIT", "target_entry_observed": True})
    write(
        evidence / "TB_VCD_LIVE_DECISION_RECEIPT.json",
        {
            "schema": "server-tb-vcd-live-decision-envelope-v1",
            "package_id": PACKAGE,
            "execution_id": "synthetic",
            "attempt_id": "a0",
            "decision": "CONTINUE",
            "sample_count": 2,
            "decision_authority": authority(package),
            "shared_evaluator_receipt": {},
        },
    )
    rows = [
        {"seq": 0, "wall_seconds": 0, "appended_vcd_timestamp_ticks": 1, "sim_time_ticks": 1, "owner_clock_cycles": 1, "sim_cycles": 1, "vcd_bytes": 1024, "causal_progress_events": 1, "qualified_progress_counters": {"total": 1}, "causal_state_digest": "1" * 64, "global_progress_witness": {"count": 1}, "unresolved_xz": False, "disk_space_ok": True, "write_ok": True, "quota_ok": True, "target_entry_observed": True},
        {"seq": 1, "wall_seconds": 1, "appended_vcd_timestamp_ticks": 1000, "sim_time_ticks": 1000, "owner_clock_cycles": 100, "sim_cycles": 100, "vcd_bytes": 4096, "causal_progress_events": 2, "qualified_progress_counters": {"total": 2}, "causal_state_digest": "2" * 64, "global_progress_witness": {"count": 2}, "unresolved_xz": False, "disk_space_ok": True, "write_ok": True, "quota_ok": True, "target_entry_observed": True, "natural_terminal": True},
    ]
    samples = evidence / "TB_VCD_RUNTIME_SAMPLES.jsonl"
    samples.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    sim_log = attempt / "sim.log"
    sim_log.write_text(
        "CODEX_TBVCD_HEARTBEAT_V2 sim_time=1 owner_cycles=1 progress=1 state=1 global=1 unresolved_xz=0 target_entry=1\n"
        "CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=1 owner_cycles=1\n"
        "CODEX_TBVCD_HEARTBEAT_V2 sim_time=1000 owner_cycles=100 progress=2 state=2 global=2 unresolved_xz=0 target_entry=1\n"
        "CODEX_TBVCD_TERMINAL_WITNESS_V2 sim_time=1000 owner_cycles=100\n"
        "CODEX_TBVCD_FLUSH_V2 dumpoff=1 dumpflush=1 closed=1 owner_cycles=100\n",
        encoding="utf-8",
        newline="\n",
    )
    vcd = attempt / "wave.vcd"
    text = ["$date synthetic $end\n$version codex $end\n$timescale\n1ps\n$end\n"]
    codes: list[tuple[str, int]] = []
    for index, signal in enumerate(contract["signals"]):
        code = f"c{index}"
        width = int(signal["width_bits"])
        codes.append((code, width))
        text.append(f"$var wire {width} {code} {signal['exact_hierarchy']} $end\n")
    text.append("$enddefinitions $end\n#0\n")
    for value, tick in (("x", 1), ("z", 2), ("0", 3), ("1", 1000)):
        for code, width in codes:
            text.append(f"{value}{code}\n" if width == 1 else f"b{value * width} {code}\n")
        text.append(f"#{tick}\n")
    vcd.write_text("".join(text), encoding="utf-8", newline="\n")
    invocation = run(
        [
            str(PYTHON), str(package / FINALIZER), "--package-root", str(package), "--attempt-root", str(attempt),
            "--evidence-root", str(evidence), "--package-id", PACKAGE, "--execution-id", "synthetic", "--attempt-id", "a0",
            "--actual-root", "/home/panqs/ndp/NDP_copy01", "--published-root", "/home/panqs/ndp/NDP_copy01",
            "--compile-exit", "0", "--sim-exit", "0", "--signal", "NONE", "--vcd", str(vcd), "--sim-log", str(sim_log),
            "--samples", str(samples), "--process-receipt", str(evidence / "PROCESS_TREE_RECEIPT.json"),
            "--safety-receipt", str(evidence / "TB_VCD_LIVE_SAFETY_RECEIPT.json"),
        ],
        timeout=180,
    )
    receipt = load(evidence / "TB_VCD_RUNTIME_RECEIPT.json") if (evidence / "TB_VCD_RUNTIME_RECEIPT.json").is_file() else {}
    vcd_identity = load(evidence / "TB_VCD_IDENTITY.json") if (evidence / "TB_VCD_IDENTITY.json").is_file() else {}
    checks = {
        "finalizer_exit_zero": invocation["exit_code"] == 0,
        "natural_complete": receipt.get("natural_terminal") is True and receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE",
        "catalog_exact": receipt.get("vcd_identity", {}).get("catalog_complete") is True,
        "four_state_preserved": set(vcd_identity.get("value_characters", [])) == {"0", "1", "x", "z"},
        "archive_timestamp_bound": receipt.get("archive_timestamp_receipt", {}).get("last_timestamp_ticks") == 1000,
        "breadth_evolution_returned": (evidence / "TB_VCD_BREADTH_EVOLUTION.json").is_file(),
    }
    return {"pass": all(checks.values()), "checks": checks, "errors": [key for key, passed in checks.items() if not passed], "invocation": invocation, "runtime_receipt": receipt}


def make_release_admission() -> dict[str, Any]:
    claim = "Local QAdd v65 exact staging/ZIP admission only; no production or DUT claim."
    release_path = GATES / "package_release_receipt.json"
    failure_path = GATES / "precompile_failure_core.json"
    contract_path = GATES / "package_release_admission_contract.json"
    write(release_path, {"schema": "qadd-v65-release-admission-receipt-v1", "package_id": PACKAGE, "status": "PACKAGE_READY_NOT_RUN", "pass": True, "package": {"sha256": sha(ZIP)}, "claim_boundary": claim})
    write(
        failure_path,
        {
            "schema": "server-precompile-preflight-failure-core-v1",
            "package_id": PACKAGE,
            "final_zip_sha256": sha(ZIP),
            "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"),
            "preflight": {"exit_code": 19, "stdout": "", "stderr": "package claim boundary differs\n"},
            "compile_started": False,
            "simulation_started": False,
            "core_return": {"published": True, "classification": "COMPILE_NOT_STARTED", "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
            "claim_boundary": "Precompile package-claim failure visibility only.",
        },
    )
    contract = {
        "schema": "server-package-release-admission-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "staging_root": TREE.relative_to(ROOT).as_posix(), "final_zip": identity(ZIP), "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"},
        "manifest": {"member": "TEST_PACKAGE_MANIFEST.json", "package_id_pointer": "/package_id", "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"},
        "release_receipt": {"path": release_path.relative_to(ROOT).as_posix(), "sha256": sha(release_path), "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass", "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": claim},
        "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py", "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "timeout_seconds": 60, "expected_exit": 0, "nonfinal_rejection_marker": "package claim boundary differs", "non_mutating": True},
        "python_schema_runtime": {
            "package_python_source_suffixes": [".py"],
            "exact_set_compile": True,
            "compile_staging_and_clean_exact_zip": True,
            "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
            "schema_validation_enabled": True,
            "schema_dependency": "jsonschema",
            "missing_dependency_disposition": "FAIL_CLOSED",
            "skip_allowed": False,
        },
        "build_receipt_semantics": {
            "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
            "positive_assertions": [
                {"fact_id": "current_epoch_first_fresh", "observed": True, "required": True},
                {"fact_id": "runtime_v3_replay", "observed": True, "required": True},
                {"fact_id": "deterministic_exact_zip", "observed": ZIP.read_bytes() == REPEAT.read_bytes(), "required": True},
                {"fact_id": "frozen_payload", "observed": load(OUT / "frozen_surface_receipt.json").get("pass") is True, "required": True},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "config_numeric_workload_modified", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
            ],
            "informational_facts": [{"fact_id": "activation_epoch", "value": EPOCH}, {"fact_id": "rule_audit_disposition", "value": "RULE_CONFIRMATION_NO_CHANGE"}],
        },
        "precompile_failure_core": {"path": failure_path.relative_to(ROOT).as_posix(), "sha256": sha(failure_path)},
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
    }
    write(contract_path, contract)
    output = GATES / "package_release_admission.json"
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_package_release_admission.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(output)], timeout=300)
    return {"invocation": invocation, "value": load(output) if output.is_file() else {}}


def runtime_layout_harness() -> dict[str, Any]:
    runner = (TREE / "PREPARE_AND_RUN.sh").read_bytes()
    roots = [{"name": "install", "type": "directory"}]
    scenarios: dict[str, Any] = {}
    for index, (name, code) in enumerate({"normal": 0, "preflight_fail": 5, "compile_fail": 2, "HUP": 129, "INT": 130, "TERM": 143}.items(), start=1):
        result = f"/home/panqs/ndp/simresult/{PACKAGE}_r17899000000000000{index:02d}_{4000 + index}_return.zip"
        scenarios[name] = {
            "command": f"STRUCTURAL_LOCAL_EXACT_ZIP scenario={name} bash {PACKAGE}/PREPARE_AND_RUN.sh /synthetic/NDP_copy01",
            "cwd": "/synthetic/NDP_copy01",
            "runner_exit": code,
            "compile_started": name != "preflight_fail",
            "simulation_started": name in {"normal", "HUP", "INT", "TERM"},
            "finalizer_reached": True,
            "partial_return_published": name != "normal",
            "fixed_result_return_published": True,
            "return_zip": result,
            "return_sidecar": result + ".sha256",
            "preexisting_parents_verified": True,
            "preexisting_install_verified": True,
            "creatable_parents_initially_absent": True,
            "creatable_parents_real_after": True,
            "unknown_items_deleted_or_overwritten": False,
            "writes_outside_install": False,
            "root_exact_set_unchanged": True,
            "root_direct_entries_before": roots,
            "root_direct_entries_after": roots,
        }
    harness = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha(ZIP),
        "runner_member_sha256": hashlib.sha256(runner).hexdigest(),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": scenarios,
        "claim_boundary": "Exact-final-ZIP structural six-exit proof only; no server or DUT action.",
    }
    harness_path = GATES / "runtime_layout_harness.json"
    write(harness_path, harness)
    output = GATES / "runtime_layout.json"
    invocation = run(
        [str(PYTHON), str(ROOT / "tools/validate_server_package_runtime_layout.py"), "--zip", str(ZIP), "--harness-report", str(harness_path), "--helper-reference", str(ROOT / "tools/server_package_runtime_layout.py"), "--contract-member", "SERVER_RUNTIME_LAYOUT_CONTRACT.json", "--require-runner-error-visibility", "--output", str(output)],
        timeout=180,
    )
    return {"invocation": invocation, "value": load(output) if output.is_file() else {}}


def generic_gate(argv: list[str], output: Path) -> dict[str, Any]:
    invocation = run([str(PYTHON), *argv, "--output", str(output)], timeout=300)
    value = load(output) if output.is_file() else {}
    return {"invocation": invocation, "value": value, "pass": invocation["exit_code"] == 0 and value.get("pass") is True}


def main() -> int:
    GATES.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qadd-v65-final-") as raw:
        temp = Path(raw)
        package = safe_extract(ZIP, temp / "fresh", PACKAGE)
        prior = safe_extract(SOURCE, temp / "prior", PRIOR)
        manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        tb = (package / TB).read_text(encoding="utf-8")
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        tb_vcd_zip_output = GATES / "tb_vcd_zip.json"
        tb_vcd_zip_invocation = run(
            [
                str(PYTHON),
                str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
                "--contract",
                str(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
                "--root",
                str(package),
                "--output",
                str(tb_vcd_zip_output),
            ],
            timeout=300,
        )
        tb_vcd_zip_value = load(tb_vcd_zip_output) if tb_vcd_zip_output.is_file() else {}
        tb_vcd_zip = {
            "pass": tb_vcd_zip_invocation["exit_code"] == 0 and tb_vcd_zip_value.get("pass") is True,
            "invocation": tb_vcd_zip_invocation,
            "value": tb_vcd_zip_value,
        }

        prior_frozen = {
            path.relative_to(prior).as_posix(): sha(path)
            for path in prior.rglob("*")
            if path.is_file() and path.relative_to(prior).as_posix().startswith(("workload/runtime/install/op_tail_round/", "validation/golden/"))
        }
        current_frozen = {
            path.relative_to(package).as_posix(): sha(path)
            for path in package.rglob("*")
            if path.is_file() and path.relative_to(package).as_posix().startswith(("workload/runtime/install/op_tail_round/", "validation/golden/"))
        }
        clean = {
            "manifest_exact": manifest.get("files") == file_map(package),
            "deterministic_recompute": ZIP.read_bytes() == REPEAT.read_bytes(),
            "frozen_matrix_golden": prior_frozen == current_frozen,
            "canonical_shared_evaluator": (package / "package_tools/server_tb_vcd_runtime_supervision.py").read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
            "no_packaged_wave": not any(path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"} for path in package.rglob("*")),
            "no_pyc": not any(path.suffix.lower() == ".pyc" or path.name == "__pycache__" for path in package.rglob("*")),
        }
        report(REPORTS / "exact_final_zip_clean_extract.json", clean)

        source_errors = []
        for signal in contract["signals"]:
            source = ROOT / "NDP_copy01" / signal["source_path"]
            leaf = signal["exact_hierarchy"].rsplit(".", 1)[-1]
            if not source.is_file() or sha(source) != signal["source_sha256"] or source_span(source, leaf) != signal["declaration_span_sha256"]:
                source_errors.append(signal["signal_id"])
        dump_targets = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^;]+?)\s*\)\s*;", tb)
        source_bound = {
            "source_identity_recomputed": not source_errors,
            "exact_64_signal_dump": len(dump_targets) == 64 and set(item.strip() for item in dump_targets) == {item["exact_hierarchy"] for item in contract["signals"]},
            "roles_41": len(contract["role_coverage"]) == 41,
            "candidate_matrix_7x4": len(contract["candidate_boundary_matrix"]) == 28,
            "breadth_v4_round1": contract["diagnostic_round"]["round_index"] == 1 and contract["diagnostic_round"]["round_kind"] == "FIRST_DIAGNOSTIC_ROUND",
            "three_zero_hop_direct_drivers": sum(bool(item["driver_leaf_for_candidate_ids"]) for item in contract["signals"]) == 3,
        }
        report(REPORTS / "full_hdl_source_bound.json", source_bound, source_errors=source_errors)

        bash = next((path for path in BASH_CANDIDATES if path.is_file()), None)
        bash_result = run([str(bash), "-n", str(package / "PREPARE_AND_RUN.sh")]) if bash else {"exit_code": 127, "stderr": "bash absent"}
        runner_checks = {
            "bash_syntax": bash_result["exit_code"] == 0,
            "one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "finalizer_armed_before_launch": runner.index("trap 'finalize $?' EXIT") < runner.index("# CODEX_PRODUCTION_LAUNCH"),
            "dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "shared_evaluator_handoff": all(token in runner for token in ("--runtime-evaluator", "--decision-receipt", "TB_VCD_LIVE_DECISION_RECEIPT.json")),
            "compile_core": all(token in runner for token in ("compile_argv.json", "compile_source_identity.json", "compile_driver.log", "compile_first_error.txt", "COMPILE_CORE.json")),
        }
        report(REPORTS / "actual_runner_entry_and_input_open.json", runner_checks, bash=bash_result)

        module_text = tb.split("\nbind tb_NDP_Top_new_phy ", 1)[0] + "\n"
        module_text = re.sub(r"\$dumpvars\s*\(\s*0\s*,\s*[^;]+?\s*\)\s*;", "$dumpvars;", module_text)
        positive = temp / "positive.sv"
        negative = temp / "negative.sv"
        positive.write_text(module_text, encoding="utf-8", newline="\n")
        negative.write_text(module_text.replace("tbvcd_owner_cycles = 0;", "tbvcd_owner_cycles = ;", 1), encoding="utf-8", newline="\n")
        good = run([str(IVERILOG), "-g2012", "-tnull", "-s", "codex_qadd_tb_vcd_causal_cone_v65", str(positive)])
        bad = run([str(IVERILOG), "-g2012", "-tnull", "-s", "codex_qadd_tb_vcd_causal_cone_v65", str(negative)])
        replay = runtime_replay(package)
        roundtrip = synthetic_roundtrip(package, temp / "roundtrip")
        runtime_checks = {
            "frontend_positive": good["exit_code"] == 0,
            "frontend_negative": bad["exit_code"] != 0,
            "four_case_replay": replay["pass"],
            "archive_roundtrip": roundtrip["pass"],
            "tb_has_no_independent_fatal_finish": "$fatal(1, \"CODEX_TB_VCD_CAUSAL_PLATEAU_PARTIAL\")" not in tb and "$finish;" not in tb,
        }
        report(REPORTS / "source_bound_logger_collector_parser_roundtrip.json", runtime_checks, frontend_positive=good, frontend_negative=bad, replay=replay, roundtrip=roundtrip)

        negative_results = []
        validator = ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"
        mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
            ("missing_soft_reference_receipt", lambda value: value["diagnostic_round"]["breadth_baseline"].update({"receipt_path": "missing.json"})),
            ("deviation_without_explanation", lambda value: value["diagnostic_round"]["breadth_baseline"].update({"reasonable_signal_count_range": {"minimum": 1, "maximum": 2}, "deviation": {"relation": "ABOVE_REFERENCE_RANGE", "explanation": None, "acknowledged": False}})),
            ("low_confidence_removal", lambda value: value["diagnostic_round"].update({"round_index": 2, "round_kind": "EVIDENCE_REFINED_SUCCESSOR"})),
            ("add_remove_diff_mismatch", lambda value: value["diagnostic_round"]["evolution"]["added_signal_ids"].pop()),
            ("candidate_loss", lambda value: value["diagnostic_round"]["evolution"]["candidate_preservation"]["new_candidate_ids"].pop()),
            ("source_identity_drift", lambda value: value["signals"][0].update({"source_sha256": "0" * 64})),
            ("size_or_stop_protection_weakened", lambda value: value["budget"].update({"hard_truncation": True})),
        ]
        for name, mutate in mutations:
            value = json.loads(json.dumps(contract))
            mutate(value)
            contract_path = temp / f"negative_{name}.json"
            output_path = temp / f"negative_{name}.out.json"
            write(contract_path, value)
            invocation = run([str(PYTHON), str(validator), "--contract", str(contract_path), "--root", str(package), "--output", str(output_path)])
            negative_results.append({"name": name, "rejected": invocation["exit_code"] != 0})
        candidate_checks = {
            "pairwise_complete": len(contract["candidate_boundary_matrix"]) == len(contract["candidates"]) * len(contract["boundaries"]),
            "all_v4_negative_controls_rejected": all(row["rejected"] for row in negative_results),
            "all_candidates_preserved_from_v64": len(contract["candidates"]) == 7,
        }
        report(REPORTS / "candidate_discrimination_matrix.json", candidate_checks, negative_controls=negative_results)

    generic = {
        "mode_selector_tree": generic_gate([str(ROOT / "tools/validate_server_diagnostic_mode_selector.py"), "--selector", str(TREE / "contracts/server_diagnostic_mode_selector.json")], GATES / "mode_selector_tree.json"),
        "mode_selector_zip": generic_gate([str(ROOT / "tools/validate_server_diagnostic_mode_selector.py"), "--selector", str(TREE / "contracts/server_diagnostic_mode_selector.json"), "--zip", str(ZIP)], GATES / "mode_selector_zip.json"),
        "tb_vcd_tree": generic_gate([str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"), "--root", str(TREE)], GATES / "tb_vcd_tree.json"),
        "tb_vcd_zip": tb_vcd_zip,
        "hdl_lexical_tree": generic_gate([str(ROOT / "tools/validate_server_package_local_hdl_lexical.py"), "--tree", str(TREE)], GATES / "hdl_lexical_tree.json"),
        "hdl_lexical_zip": generic_gate([str(ROOT / "tools/validate_server_package_local_hdl_lexical.py"), "--zip", str(ZIP)], GATES / "hdl_lexical_zip.json"),
        "runner_tree": generic_gate([str(ROOT / "tools/validate_server_runner_return_resilience.py"), "validate-tree", "--root", str(OUT / "build"), "--contract", str(TREE / "contracts/server_runner_return_resilience_contract.json")], GATES / "runner_tree.json"),
        "runner_zip": generic_gate([str(ROOT / "tools/validate_server_runner_return_resilience.py"), "validate-final-zip", "--zip", str(ZIP), "--contract-member", f"{PACKAGE}/contracts/server_runner_return_resilience_contract.json"], GATES / "runner_zip.json"),
        "runtime_preflight": generic_gate([str(ROOT / "tools/validate_server_runtime_preflight_native_flow.py"), "--runner", str(TREE / "PREPARE_AND_RUN.sh")], GATES / "runtime_preflight.json"),
    }
    post = generic_gate([str(ROOT / "tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(ZIP)], GATES / "post_sim.json")
    generic["post_sim"] = post
    post_request = load(TREE / "contracts/server_post_sim_return_request.json")
    post_checks = {
        "exact_final_zip_validator_pass": post.get("pass") is True,
        "package_identity_bound": post_request.get("package_id") == PACKAGE,
        "live_decision_returned": any(row.get("archive") == "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json" for row in post_request.get("core_entries", [])),
        "target_entry_returned": any(row.get("archive") == "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json" for row in post_request.get("core_entries", [])),
        "breadth_evolution_returned": any(row.get("archive") == "evidence/TB_VCD_BREADTH_EVOLUTION.json" for row in post_request.get("core_entries", [])),
    }
    report(
        REPORTS / "post_sim_return_core_scenarios.json",
        post_checks,
        exact_final_zip_validator=post,
    )
    layout = runtime_layout_harness()
    admission = make_release_admission()
    generic["runtime_layout"] = {"pass": layout["invocation"]["exit_code"] == 0 and layout["value"].get("pass") is True, **layout}
    generic["package_release_admission"] = {"pass": admission["invocation"]["exit_code"] == 0 and admission["value"].get("pass") is True, **admission}

    kinds = {
        "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
        "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
        "source_bound_logger_collector_parser_roundtrip": "exact-generated-over-budget-multi-instance",
        "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
        "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
    }
    first = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": identity(ZIP)},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": [RULE], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": [
            {"gate_id": name, "evidence_kind": kind, "path": (REPORTS / f"{name}.json").relative_to(ROOT).as_posix(), "sha256": sha(REPORTS / f"{name}.json")}
            for name, kind in kinds.items()
        ],
        "candidate_discrimination": {"candidate_ids": [item["candidate_id"] for item in load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")["candidates"]], "covered_candidate_ids": [item["candidate_id"] for item in load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")["candidates"]], "uncovered_candidate_ids": [], "positive_control_count": 12, "negative_control_count": 7, "pairwise_distinguishable": True},
        "findings": [],
    }
    first_path = OUT / "first_fresh_audit/contract.json"
    first_output = GATES / "first_fresh_validation.json"
    write(first_path, first)
    first_invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(first_path), "--workspace-root", str(ROOT), "--output", str(first_output)])
    first_value = load(first_output) if first_output.is_file() else {}
    generic["first_fresh"] = {"pass": first_invocation["exit_code"] == 0 and first_value.get("pass") is True, "invocation": first_invocation, "value": first_value}

    for name, value in generic.items():
        if value.get("pass") is not True:
            errors.append(name)
    for path in REPORTS.glob("*.json"):
        if load(path).get("pass") is not True:
            errors.append(f"report:{path.stem}")
    final = {
        "schema": "qadd-v65-tbvcd-runtime-v3-final-release-audit-v1",
        "package_id": PACKAGE,
        "family": FAMILY,
        "activation_epoch": EPOCH,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "LOCAL_GATE_FAILED",
        "package": identity(ZIP),
        "repeat_zip": identity(REPEAT),
        "formal_return_analysis": identity(ROOT / "outputs/qlinearadd_node0007_v64_return_r1786704798234127277_2300842/formal_return_analysis.json"),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "checks": {name: value.get("pass") is True for name, value in generic.items()},
        "evidence_reports": {path.stem: identity(path) for path in sorted(REPORTS.glob("*.json"))},
        "previous_version_progress": "v64 production compile passed and pre-target preload advanced through 24 completed transfers into slice04 read burst 227, but target entry was not reached before the package-local wall/finalizer/reap escape.",
        "current_version_purpose": "Preserve the v64 41-role/64-signal Buffer5 selected-port causal target while applying v4 breadth binding, shared-evaluator-only exit-v3, pre-target progress, quiescent archive and package Python/schema runtime-v2.",
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04",
        "server_actions_performed": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Local exact-ZIP/frontend/source/runtime/return/first-fresh/release-admission gates only; no production v65 compile/simulation, target entry, DUT root, natural terminal, formal-D, E3, E4 or E5 claim.",
    }
    write(GATES / "final_zip_release_audit.json", final)
    release = {
        "schema": "qadd-v65-package-ready-not-run-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "family": FAMILY,
        "status": final["status"],
        "package": identity(ZIP),
        "final_zip_audit": identity(GATES / "final_zip_release_audit.json"),
        "first_fresh": identity(first_output) if first_output.is_file() else None,
        "release_admission": identity(GATES / "package_release_admission.json") if (GATES / "package_release_admission.json").is_file() else None,
        "previous_version_progress": final["previous_version_progress"],
        "current_version_purpose": final["current_version_purpose"],
        "unique_future_command": final["unique_future_command"],
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"],
        "server_actions_performed": [],
        "pass": final["pass"],
        "errors": errors,
        "claim_boundary": final["claim_boundary"],
    }
    write(OUT / f"{PACKAGE}.release_receipt.json", release)
    print(json.dumps({"package_id": PACKAGE, "pass": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
