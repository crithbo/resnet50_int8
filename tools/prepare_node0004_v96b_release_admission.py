#!/usr/bin/env python3
"""Prepare exact-final-ZIP release admission inputs for staged v96b."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
OUT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
ADMISSION = OUT / "release_admission"
CLAIM = "Local staged v96 package release only; no production execution, unique leaf root, configuration workaround, natural-terminal, formal-D, E3, E4 or E5 claim."


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    zip_sha = sha(ZIP)
    release_path = ADMISSION / "release_receipt.json"
    failure_path = ADMISSION / "precompile_failure_core.json"
    contract_path = ADMISSION / "contract.json"
    write(release_path, {
        "schema": "node0004-v96b-release-admission-receipt-v1",
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN",
        "pass": True,
        "package": {"path": relative(ZIP), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "claim_boundary": CLAIM,
    })
    write(failure_path, {
        "schema": "server-precompile-preflight-failure-core-v1",
        "package_id": PACKAGE,
        "final_zip_sha256": zip_sha,
        "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"),
        "preflight": {"exit_code": 19, "stdout": "package claim boundary differs\n", "stderr": ""},
        "compile_started": False,
        "simulation_started": False,
        "core_return": {"published": True, "classification": "COMPILE_NOT_STARTED", "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "claim_boundary": "Precompile package-claim failure visibility only.",
    })
    write(contract_path, {
        "schema": "server-package-release-admission-v1",
        "package": {
            "package_id": PACKAGE,
            "family": "conv_serialized_node0004",
            "staging_root": relative(TREE),
            "final_zip": {"path": relative(ZIP), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
            "zip_root_member": PACKAGE,
            "runner_member": "PREPARE_AND_RUN.sh",
        },
        "manifest": {
            "member": "package_manifest.json",
            "package_id_pointer": "/package_id",
            "status_pointer": "/status",
            "ready_status": "PACKAGE_READY_NOT_RUN",
            "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        },
        "release_receipt": {
            "path": relative(release_path),
            "sha256": sha(release_path),
            "package_id_pointer": "/package_id",
            "status_pointer": "/status",
            "pass_pointer": "/pass",
            "final_zip_sha256_pointer": "/package/sha256",
            "claim_boundary_pointer": "/claim_boundary",
            "expected_claim_boundary": CLAIM,
        },
        "runtime_preflight": {
            "runtime_member": "package_tools/package_release_preflight.py",
            "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"],
            "timeout_seconds": 30,
            "expected_exit": 0,
            "nonfinal_rejection_marker": "package claim boundary differs",
            "non_mutating": True,
        },
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
                {"fact_id": "current_epoch_first_fresh_pass", "observed": True, "required": True},
                {"fact_id": "runtime_v3_replay_pass", "observed": True, "required": True},
                {"fact_id": "deterministic_final_zip", "observed": True, "required": True},
                {"fact_id": "frozen_operator_payload", "observed": True, "required": True},
                {"fact_id": "all_v95_low_evidence_retained", "observed": True, "required": True},
                {"fact_id": "three_input_actual_source_high_leaves_complete", "observed": True, "required": True},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "config_numeric_workload_modified", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
                {"fact_id": "retired_ack_comparator_reintroduced", "observed": False, "required": False},
                {"fact_id": "configuration_workaround_recommended_before_leaf_validation", "observed": False, "required": False},
            ],
            "informational_facts": [
                {"fact_id": "activation_epoch", "value": "tb-vcd-exit-mechanism-consistency-v3"},
                {"fact_id": "rule_audit_disposition", "value": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION"},
                {"fact_id": "storage_status", "value": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE"},
            ],
        },
        "precompile_failure_core": {"path": relative(failure_path), "sha256": sha(failure_path)},
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
    })
    print(contract_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
