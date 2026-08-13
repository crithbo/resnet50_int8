#!/usr/bin/env python3
"""Validate p46 bootstrap-safe native-flow compile-core evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PACKAGE = "r5_n4_0cc_p46_nativeflow"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--canonical-helper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="native-p46-compile-core-") as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(args.zip) as archive:
            helper_data = archive.read(f"{PACKAGE}/package_tools/compile_core_evidence.py")
            runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
            source_a = archive.read(f"{PACKAGE}/tb_probe/source_bound_causal_observer.svh")
            source_b = archive.read(f"{PACKAGE}/tb_probe/observer_only_wide_causal.svh")
        if helper_data != args.canonical_helper.read_bytes():
            errors.append("exact ZIP compile helper differs from canonical p46 helper")
        helper = temp / "compile_core_evidence.py"
        helper.write_bytes(helper_data)
        package = temp / PACKAGE
        probes = package / "tb_probe"
        probes.mkdir(parents=True)
        source_a_path = probes / "source_bound_causal_observer.svh"
        source_b_path = probes / "observer_only_wide_causal.svh"
        source_a_path.write_bytes(source_a)
        source_b_path.write_bytes(source_b)
        server = temp / "NDP_copy01"
        run_root = server / f"install/codex_runs/{PACKAGE}/a0"
        bootstrap = run_root / "evidence/compile_bootstrap"
        sca = server / f"install/cfg_pkg/{PACKAGE}/runs/c0/sca_cfg.json"
        sca_d = server / f"install/cfg_pkg/{PACKAGE}/runs/c0/sca_cfg_D.json"
        chunk = run_root / "evidence/observer/chunks/events-000000.jsonl"
        prepare = subprocess.run([
            sys.executable, str(helper), "prepare", "--output-root", str(bootstrap),
            "--package-id", PACKAGE, "--execution-id", "rsynthetic", "--attempt-id", "a0",
            "--cwd", str(server), "--makefile-name", "Makefile.tb_NDP_Top_new_phy",
            "--source", str(source_a_path), "--source", str(source_b_path),
            "--package-root", str(package), "--run-dir", str(run_root / "compile"),
            "--attempt-root", str(run_root), "--sca-cfg", str(sca), "--sca-cfg-d", str(sca_d),
            "--observer-chunk", str(chunk), "--repeat-num", "1",
        ], capture_output=True, text=True, check=False)
        if prepare.returncode != 0:
            errors.append("compile helper prepare failed: " + prepare.stderr[-1000:])
        payload = b"compile banner\n" + b"A" * 70000 + b"\nError-[SE] Syntax error at observer line\n" + b"B" * 70000 + b"\ncompile tail\n"
        (bootstrap / "compile_driver.log").write_bytes(payload)
        finalize = subprocess.run([
            sys.executable, str(helper), "finalize", "--output-root", str(bootstrap), "--exit-code", "2"
        ], capture_output=True, text=True, check=False)
        returned = subprocess.run([
            sys.executable, str(helper), "return-core", "--output-root", str(bootstrap),
            "--package-id", PACKAGE, "--execution-id", "rsynthetic", "--attempt-id", "a0",
            "--compile-exit", "2", "--sim-exit", "125", "--signal", "NONE",
        ], capture_output=True, text=True, check=False)
        if finalize.returncode != 0 or returned.returncode != 0:
            errors.append("compile helper finalize/return-core failed")
        argv = json.loads((bootstrap / "ACTUAL_COMPILE_SIM_ARGV.json").read_text(encoding="utf-8"))
        source_identity = json.loads((bootstrap / "compile_source_identity.json").read_text(encoding="utf-8"))
        core = json.loads((bootstrap / "COMPILE_CORE.json").read_text(encoding="utf-8"))
        sim_exit = json.loads((bootstrap / "SIM_EXIT_RECEIPT.json").read_text(encoding="utf-8"))
        log_receipt = json.loads((bootstrap / "compile_log_receipt.json").read_text(encoding="utf-8"))
        differential = json.loads((bootstrap / "NATIVE_FLOW_FAILURE_DIFFERENTIAL.json").read_text(encoding="utf-8"))
        checks = {
            "dump_zero_actual_compile": all(token in argv["compile_argv"] for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")) and "DUMP_FSDB=1" not in argv["compile_argv"],
            "actual_cwd_sca_repeat": argv["actual_cwd"] == str(server) and argv["sca_cfg"] == str(sca) and argv["sca_cfg_d"] == str(sca_d) and argv["repeat_num"] == 1,
            "no_server_makefile_probe": source_identity["makefile"]["prelaunch_identity_probe"] is False and "sha256" not in source_identity["makefile"],
            "package_sources_exact": len(source_identity["package_sources"]) == 2 and all(row["authority"] == "PACKAGE_OWNED_SOURCE" for row in source_identity["package_sources"]),
            "complete_log": log_receipt["complete_log_returned"] is True and log_receipt["bytes"] == len(payload) and log_receipt["sha256"] == digest(payload),
            "bounded_head_tail": (bootstrap / "compile_log_head.txt").stat().st_size <= 65536 and (bootstrap / "compile_log_tail.txt").stat().st_size <= 65536,
            "first_true_error": (bootstrap / "compile_first_error.txt").read_text(encoding="utf-8").startswith("Error-[SE]"),
            "compile_core_complete": core["compile_exit"] == 2 and core["simulation_started"] is False and core["complete_log_receipt"]["complete_log_returned"] is True,
            "sim_exit_on_compile_fail": sim_exit["simulation_started"] is False and sim_exit["compile_exit"] == 2,
            "unknown_preserved": differential["classification"] == "SERVER_RUNTIME_UNKNOWN" and differential["provider_preflight_performed"] is False,
            "runner_prepare_before_compile": runner.find('compile_core_evidence.py" prepare') < runner.find("timeout --foreground --signal=TERM"),
            "runner_core_members": all(token in runner for token in ("ACTUAL_COMPILE_SIM_ARGV.json", "SIM_EXIT_RECEIPT.json", "COMPILE_CORE.json", "compile_driver.log")),
        }
        errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-p46-native-flow-compile-core-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "claim_boundary": "Synthetic local compile-failure evidence only; no server compile or DUT result.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
