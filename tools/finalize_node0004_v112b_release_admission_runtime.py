#!/usr/bin/env python3
"""Close the v112 release-admission runtime receipt without server actions."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
GATES = OUT / "gates"
PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    target = GATES / "package_release_admission_runtime_preflight.json"
    incident = (
        GATES
        / "package_release_admission_runtime_preflight_attempt1_schema_interface_mismatch.json"
    )
    if target.is_file() and load(target).get("pass") is not True and not incident.exists():
        target.rename(incident)

    admission_path = OUT / "server_package_admission.json"
    admission = load(admission_path)
    schema_path = ROOT / "schemas/server_package_release_admission_v1.schema.json"
    schema = load(schema_path)
    schema_errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(admission),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    runner = load(
        OUT
        / "first_fresh_extra_audit/reports/actual_runner_entry_and_input_open.json"
    )
    exact = load(
        OUT / "first_fresh_extra_audit/reports/exact_final_zip_clean_extract.json"
    )
    checks = {
        "pipeline_release_admission_pass": admission.get("pass") is True
        and admission.get("status") == "PACKAGE_READY_NOT_RUN"
        and admission.get("package_id") == PACKAGE,
        "release_admission_output_schema_valid": not schema_errors,
        "jsonschema_runtime_available": True,
        "clean_exact_zip_preflight_pass": runner.get("checks", {}).get(
            "exact_zip_package_preflight"
        )
        is True,
        "pending_status_negative_pass": runner.get("checks", {}).get(
            "pending_status_negative"
        )
        is True,
        "package_python_exact_set_compile_pass": runner.get("checks", {}).get(
            "python_exact_set_compile"
        )
        is True,
        "bytecode_outside_package": runner.get("checks", {}).get(
            "bytecode_outside_package"
        )
        is True,
        "staging_clean_extract_exact_set": exact.get("checks", {}).get(
            "exact_tree_zip_equal"
        )
        is True,
        "deterministic_exact_zip": exact.get("checks", {}).get(
            "deterministic_rebuild"
        )
        is True,
    }
    report = {
        "schema": "node0004-v112-package-release-admission-runtime-preflight-v1",
        "package_id": PACKAGE,
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed]
        + [error.message for error in schema_errors],
        "warnings": [],
        "checks": checks,
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "schema_path": schema_path.relative_to(ROOT).as_posix(),
        "pipeline_admission_path": admission_path.relative_to(ROOT).as_posix(),
        "preserved_standalone_interface_mismatch_attempt": (
            incident.relative_to(ROOT).as_posix() if incident.is_file() else None
        ),
        "claim_boundary": (
            "Local clean-extract preflight, pending-status negative, Python exact-set "
            "compile and typed pipeline admission only; no server or storage claim."
        ),
    }
    write(target, report)

    gate_results_path = OUT / "server_package_gate_results.json"
    gate_results = load(gate_results_path)
    gate_results["results"] = [
        row
        for row in gate_results["results"]
        if row.get("gate_id") != "package_release_admission_runtime_preflight"
    ]
    gate_results["results"].append(
        {
            "gate_id": "package_release_admission_runtime_preflight",
            "pass": report["pass"],
            "errors": report["errors"],
            "warnings": report["warnings"],
            "detail_path": target.relative_to(ROOT).as_posix(),
        }
    )
    write(gate_results_path, gate_results)
    print(json.dumps({"pass": report["pass"], "schema_errors": len(schema_errors)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
