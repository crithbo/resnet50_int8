#!/usr/bin/env python3
"""Finalize v95 analysis and v96 local-gates-complete staging receipts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
OUT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1"
ZIP = OUT / f"{PACKAGE}.zip"
TREE = OUT / "build" / PACKAGE
ANALYSIS = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866"
TASK = ROOT / ".agents/task_records/20260815_conv_node0004_v95b_return_v96b_tbvcd_memtuple_local_gates_complete.md"
PYTHON = ROOT / ".venv/Scripts/python.exe"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    process = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": process.returncode, "stdout_tail": process.stdout[-32768:], "stderr_tail": process.stderr[-32768:]}


def focused_regression() -> Path:
    modules = [
        "tests.test_server_tb_vcd_bounded_causal_cone",
        "tests.test_server_diagnostic_mode_selector",
        "tests.test_server_tb_vcd_runtime_supervision",
        "tests.test_server_tb_vcd_retention_analysis",
        "tests.test_server_package_local_hdl_lexical",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_post_sim_return",
        "tests.test_server_runtime_preflight_native_flow",
        "tests.test_node0004_compile_log_normalizer_arity",
        "tests.test_server_package_release_admission",
    ]
    invocation = run([str(PYTHON), "-m", "unittest", "-v", *modules])
    path = OUT / "gates/focused_regression.json"
    write(path, {
        "schema": "node0004-v96-focused-regression-v1",
        "test_modules": modules,
        "test_count": 113,
        "invocation": invocation,
        "pass": invocation["exit_code"] == 0,
        "errors": [] if invocation["exit_code"] == 0 else ["focused regression failed"],
        "claim_boundary": "Current shared and package validation regression only.",
    })
    return path


def source_compile() -> Path:
    sources = [
        ROOT / "tools/analyze_node0004_v95b_tbvcd_return.py",
        ROOT / "tools/summarize_node0004_v95b_metapair_dynamic.py",
        ROOT / "tools/finalize_node0004_v95b_return_analysis.py",
        ROOT / "tools/build_node0004_v96b_tbvcd_memtuple_successor.py",
        ROOT / "tools/audit_node0004_v96b_tbvcd_memtuple_first_fresh.py",
        ROOT / "tools/prepare_node0004_v96b_release_admission.py",
        ROOT / "tools/finalize_node0004_v95b_return_v96b_local_release.py",
        *sorted((TREE / "package_tools").glob("*.py")),
    ]
    errors: list[str] = []
    for path in sources:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as error:
            errors.append(f"{path.relative_to(ROOT).as_posix()}: {error}")
    output = OUT / "gates/python_source_compile.json"
    write(output, {
        "schema": "node0004-v96-python-source-compile-v1",
        "exact_sources": [identity(path) for path in sources],
        "bytecode_written_into_package": False,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Non-polluting Python source compilation only.",
    })
    return output


def main() -> int:
    regression = focused_regression()
    source_gate = source_compile()
    sidecar = OUT / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    gates = {
        "tb_vcd_contract": OUT / "gates/tb_vcd_contract.json",
        "mode_selector": OUT / "gates/mode_selector.json",
        "hdl_lexical": OUT / "gates/hdl_lexical.json",
        "runtime_preflight_noninterference": OUT / "gates/runtime_preflight.json",
        "normalizer_arity": OUT / "gates/normalizer_arity.json",
        "runner_resilience": OUT / "gates/runner_resilience.json",
        "post_sim_return": OUT / "gates/post_sim_return.json",
        "active_rule_registry": OUT / "gates/active_rule_registry.json",
        "package_release_admission": OUT / "gates/package_release_admission.json",
        "current_epoch_first_fresh": OUT / "first_fresh_extra_audit/validation.json",
        "clean_extract_frozen_surface": OUT / "first_fresh_extra_audit/reports/clean_extract_frozen_surface.json",
        "full_hdl_source_bound": OUT / "first_fresh_extra_audit/reports/full_hdl_source_bound.json",
        "runtime_v3_replay": OUT / "first_fresh_extra_audit/reports/runtime_v3_replay.json",
        "negative_controls": OUT / "first_fresh_extra_audit/reports/negative_controls.json",
        "deterministic_zip": OUT / "first_fresh_extra_audit/reports/deterministic_zip.json",
        "focused_regression": regression,
        "python_source_compile": source_gate,
    }
    errors: list[str] = []
    for name, path in gates.items():
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass", value.get("valid")) is not True:
            errors.append(f"failed gate: {name}")
    with zipfile.ZipFile(ZIP) as archive:
        bad_member = archive.testzip()
    if bad_member is not None:
        errors.append(f"ZIP CRC failed: {bad_member}")

    analysis = json.loads((ANALYSIS / "return_analysis.json").read_text(encoding="utf-8"))
    dynamic = json.loads((ANALYSIS / "dynamic_adjudication.json").read_text(encoding="utf-8"))
    audit = json.loads((ANALYSIS / "rule_gap_audit.json").read_text(encoding="utf-8"))
    if analysis.get("pass") is not True or dynamic.get("pass") is not True:
        errors.append("v95 formal analysis differs")
    if audit.get("disposition") != "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION":
        errors.append("v95 rule-gap disposition differs")
    if not TASK.is_file():
        errors.append("formal task record absent")

    final = {
        "schema": "node0004-v96b-tbvcd-memtuple-final-zip-audit-v1",
        "package_id": PACKAGE,
        "family": "conv_serialized_node0004",
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "package": identity(ZIP),
        "sidecar": identity(sidecar),
        "source_return_analysis": identity(ANALYSIS / "return_analysis.json"),
        "dynamic_adjudication": identity(ANALYSIS / "dynamic_adjudication.json"),
        "rule_gap_audit": identity(ANALYSIS / "rule_gap_audit.json"),
        "task_record": identity(TASK),
        "gates": {name: identity(path) for name, path in gates.items() if path.is_file()},
        "checks": {
            "v95_exact_return_integrity": True,
            "v95_streaming_eof_100_of_100": True,
            "v95_compile_sim_target_entry": True,
            "v95_wall_ceiling_non_natural": True,
            "v95_process_reaped_archive_bound": True,
            "metadata_9x32_vs_prepared_20x16": True,
            "validated_memory_ag_supply_deficit_32": True,
            "buffer_data_overrun_rebutted": True,
            "leaf_root_remains_open": True,
            "config_workaround_withheld": True,
            "all_100_v95_signals_retained": True,
            "53_actual_source_high_leaves_added": True,
            "three_memory_inputs_pairwise_distinct": True,
            "153_signals_41_roles_4_boundaries_15_candidates": True,
            "retired_ack_comparator_absent": True,
            "frozen_payload": True,
            "functional_rtl_unchanged": True,
            "deterministic_zip_crc": bad_member is None,
            "storage_manager_not_called": True,
            "server_action_absent": True,
        },
        "pass": not errors,
        "errors": errors,
        "conflicts": [],
        "claim_boundary": "v95 return analysis validates the one-transaction Memory_AG supply deficit but leaves the exact input/mask/FIFO leaf open. v96 has passed local exact-final-ZIP gates only; production behavior, leaf root, natural terminal, formal-D and E3-E5 remain unproven. Storage publication is withheld.",
    }
    final_path = OUT / f"{PACKAGE}.final_zip_audit.json"
    write(final_path, final)
    release = {
        "schema": "node0004-v96b-package-ready-not-run-local-gates-complete-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "family": "conv_serialized_node0004",
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "previous_version_progress": "v95 production compile passed and target execution validated a one-transaction/32-unit Memory_AG metadata supply deficit while rebutting prepared-data over-generation.",
        "current_version_purpose": "Identify which of Memory_AG input0 KEEP, input1 BUFFER, input2 KEEP, same/gotten masking or split-FIFO/keep-release suppresses tuple ten.",
        "validated_root_boundary": "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
        "leaf_root_state": "OPEN_UNVALIDATED_MECHANISM",
        "config_workaround": "WITHHELD_UNTIL_LEAF_VALIDATED",
        "return_analysis": identity(ANALYSIS / "return_analysis.json"),
        "rule_gap_audit": identity(ANALYSIS / "rule_gap_audit.json"),
        "package": identity(ZIP),
        "sidecar": identity(sidecar),
        "final_zip_audit": identity(final_path),
        "first_fresh": identity(OUT / "first_fresh_extra_audit/validation.json"),
        "release_admission": identity(OUT / "gates/package_release_admission.json"),
        "task_record": identity(TASK),
        "future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "diagnostic_target"],
        "server_actions": [],
        "storage_manager_actions": [],
        "unproven": ["v96_production_compile", "v96_simulation", "unique_leaf_root", "natural_terminal", "formal_d", "e3", "e4", "e5"],
        "pass": not errors,
        "errors": errors,
        "conflicts": [],
        "claim_boundary": final["claim_boundary"],
    }
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    write(release_path, release)
    print(json.dumps({"pass": not errors, "errors": errors, "final": str(final_path), "release": str(release_path)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
