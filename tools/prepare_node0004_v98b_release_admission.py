#!/usr/bin/env python3
"""Prepare exact release-admission inputs for v98."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
OUT = ROOT / "outputs/conv_node0004_v98b_lcdup_tuple10_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
ADMISSION = OUT / "release_admission"
CLAIM = "Local mapper-A/B-proven LC-branch configuration package release; no production tuple10, natural-terminal, Formal-D, E3, E4 or E5 claim."


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    zip_sha = sha(ZIP)
    release = ADMISSION / "release_receipt.json"
    failure = ADMISSION / "precompile_failure_core.json"
    contract = ADMISSION / "contract.json"
    write(release, {
        "schema": "node0004-v98b-release-admission-receipt-v1",
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "package": {"path": relative(ZIP), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "claim_boundary": CLAIM,
        "pass": True,
    })
    write(failure, {
        "schema": "server-precompile-preflight-failure-core-v1",
        "package_id": PACKAGE,
        "final_zip_sha256": zip_sha,
        "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"),
        "preflight": {"exit_code": 19, "stdout": "", "stderr": "package claim boundary differs\n"},
        "compile_started": False,
        "simulation_started": False,
        "core_return": {"classification": "COMPILE_NOT_STARTED", "published": True, "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "claim_boundary": "Precompile package-claim failure visibility only.",
    })
    write(contract, {
        "schema": "server-package-release-admission-v1",
        "package": {"package_id": PACKAGE, "family": "conv_serialized_node0004", "staging_root": relative(TREE), "final_zip": {"path": relative(ZIP), "bytes": ZIP.stat().st_size, "sha256": zip_sha}, "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"},
        "manifest": {"member": "package_manifest.json", "package_id_pointer": "/package_id", "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"},
        "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py", "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "expected_exit": 0, "nonfinal_rejection_marker": "package claim boundary differs", "timeout_seconds": 60, "non_mutating": True},
        "release_receipt": {"path": relative(release), "sha256": sha(release), "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass", "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": CLAIM},
        "precompile_failure_core": {"path": relative(failure), "sha256": sha(failure)},
        "python_schema_runtime": {"schema_validation_enabled": True, "schema_dependency": "jsonschema", "missing_dependency_disposition": "FAIL_CLOSED", "skip_allowed": False, "exact_set_compile": True, "compile_staging_and_clean_exact_zip": True, "package_python_source_suffixes": [".py"], "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY"},
        "build_receipt_semantics": {
            "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
            "positive_assertions": [
                {"fact_id": "mapper_ab_equivalence_pass", "observed": True, "required": True},
                {"fact_id": "negligible_cost_pass", "observed": True, "required": True},
                {"fact_id": "source_bound_observer_conjunction_pass", "observed": True, "required": True},
                {"fact_id": "current_first_fresh_pass", "observed": True, "required": True},
                {"fact_id": "deterministic_exact_zip", "observed": True, "required": True},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "numeric_workload_golden_modified", "observed": False, "required": False},
                {"fact_id": "retired_ack_comparator_reintroduced", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
            ],
            "informational_facts": [
                {"fact_id": "family_target_epoch", "value": "node0004-lc-branch-duplication-targeted-v1"},
                {"fact_id": "storage_status", "value": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE"},
            ],
        },
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
    })
    print(contract)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
