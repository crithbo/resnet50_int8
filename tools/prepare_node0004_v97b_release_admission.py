#!/usr/bin/env python3
"""Prepare exact-final-ZIP release admission inputs for v97b."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
OUT = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
ADMISSION = OUT / "release_admission"
CLAIM = "Local staged v97 package-only XMR repair release; no production execution, tuple-leaf root, configuration workaround, natural-terminal, formal-D, E3, E4 or E5 claim."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    zip_sha = sha256(ZIP)
    release_path = ADMISSION / "release_receipt.json"
    failure_path = ADMISSION / "precompile_failure_core.json"
    contract_path = ADMISSION / "contract.json"
    write(release_path, {
        "claim_boundary": CLAIM, "package": {"bytes": ZIP.stat().st_size, "path": relative(ZIP), "sha256": zip_sha},
        "package_id": PACKAGE, "pass": True, "schema": "node0004-v97b-release-admission-receipt-v1",
        "status": "PACKAGE_READY_NOT_RUN", "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
    })
    write(failure_path, {
        "claim_boundary": "Precompile package-claim failure visibility only.", "compile_started": False,
        "core_return": {"classification": "COMPILE_NOT_STARTED", "published": True, "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "final_zip_sha256": zip_sha, "package_id": PACKAGE,
        "preflight": {"exit_code": 19, "stderr": "", "stdout": "package claim boundary differs\n"},
        "runner_member_sha256": sha256(TREE / "PREPARE_AND_RUN.sh"), "schema": "server-precompile-preflight-failure-core-v1", "simulation_started": False,
    })
    write(contract_path, {
        "build_receipt_semantics": {
            "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
            "informational_facts": [
                {"fact_id": "activation_epoch", "value": "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3"},
                {"fact_id": "rule_audit_disposition", "value": "RULE_CONFIRMATION_NO_CHANGE"},
                {"fact_id": "storage_status", "value": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE"},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "config_numeric_workload_modified", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
                {"fact_id": "duplicated_memory_ag_anchor_present", "observed": False, "required": False},
                {"fact_id": "retired_ack_comparator_reintroduced", "observed": False, "required": False},
            ],
            "positive_assertions": [
                {"fact_id": "current_epoch_first_fresh_pass", "observed": True, "required": True},
                {"fact_id": "runtime_v3_replay_pass", "observed": True, "required": True},
                {"fact_id": "deterministic_final_zip", "observed": True, "required": True},
                {"fact_id": "frozen_operator_payload", "observed": True, "required": True},
                {"fact_id": "all_v96_evidence_retained", "observed": True, "required": True},
                {"fact_id": "all_53_memory_ag_paths_corrected", "observed": True, "required": True},
            ],
        },
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
        "manifest": {"member": "package_manifest.json", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES", "package_id_pointer": "/package_id", "ready_status": "PACKAGE_READY_NOT_RUN", "status_pointer": "/status"},
        "package": {"family": "conv_serialized_node0004", "final_zip": {"bytes": ZIP.stat().st_size, "path": relative(ZIP), "sha256": zip_sha}, "package_id": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh", "staging_root": relative(TREE), "zip_root_member": PACKAGE},
        "precompile_failure_core": {"path": relative(failure_path), "sha256": sha256(failure_path)},
        "python_schema_runtime": {"bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY", "compile_staging_and_clean_exact_zip": True, "exact_set_compile": True, "missing_dependency_disposition": "FAIL_CLOSED", "package_python_source_suffixes": [".py"], "schema_dependency": "jsonschema", "schema_validation_enabled": True, "skip_allowed": False},
        "release_receipt": {"claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": CLAIM, "final_zip_sha256_pointer": "/package/sha256", "package_id_pointer": "/package_id", "pass_pointer": "/pass", "path": relative(release_path), "sha256": sha256(release_path), "status_pointer": "/status"},
        "runtime_preflight": {"command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "expected_exit": 0, "non_mutating": True, "nonfinal_rejection_marker": "package claim boundary differs", "runtime_member": "package_tools/package_release_preflight.py", "timeout_seconds": 30},
        "schema": "server-package-release-admission-v1",
    })
    print(contract_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
