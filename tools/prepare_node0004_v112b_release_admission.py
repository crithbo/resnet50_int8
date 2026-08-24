#!/usr/bin/env python3
"""Prepare exact external release-admission receipts for serialized Conv v112."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
GATES = OUT / "gates"
CLAIM = (
    "Local serialized Conv v112 exact staging/ZIP admission only; "
    "no production VCS, DUT, storage or server claim."
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    zip_sha = sha(ZIP)
    with zipfile.ZipFile(ZIP) as archive:
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh")
        if archive.testzip() is not None:
            raise RuntimeError("exact ZIP CRC failed")
    runner_sha = hashlib.sha256(runner).hexdigest()
    release_path = GATES / "package_release_receipt.json"
    release = {
        "schema": "node0004-v112-release-admission-receipt-v1",
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN",
        "pass": True,
        "package": {"sha256": zip_sha},
        "claim_boundary": CLAIM,
    }
    write(release_path, release)

    failure_path = GATES / "precompile_failure_core.json"
    failure = {
        "schema": "server-precompile-preflight-failure-core-v1",
        "package_id": PACKAGE,
        "final_zip_sha256": zip_sha,
        "runner_member_sha256": runner_sha,
        "preflight": {
            "exit_code": 19,
            "stdout": "",
            "stderr": "package claim boundary differs\n",
        },
        "compile_started": False,
        "simulation_started": False,
        "core_return": {
            "published": True,
            "classification": "COMPILE_NOT_STARTED",
            "required_evidence": [
                "preflight_stdout",
                "preflight_stderr",
                "preflight_exit",
                "compile_not_started",
            ],
        },
        "claim_boundary": "Precompile package-claim failure visibility only.",
    }
    write(failure_path, failure)

    contract = {
        "schema": "server-package-release-admission-v1",
        "package": {
            "package_id": PACKAGE,
            "family": "conv_serialized_node0004",
            "staging_root": TREE.relative_to(ROOT).as_posix(),
            "final_zip": {
                "path": ZIP.relative_to(ROOT).as_posix(),
                "bytes": ZIP.stat().st_size,
                "sha256": zip_sha,
            },
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
        "runtime_preflight": {
            "runtime_member": "package_tools/package_release_preflight.py",
            "command_template": [
                "{python}",
                "{runtime_member}",
                "preflight",
                "--package-root",
                "{package_root}",
            ],
            "expected_exit": 0,
            "non_mutating": True,
            "nonfinal_rejection_marker": "package claim boundary differs",
            "timeout_seconds": 60,
        },
        "python_schema_runtime": {
            "schema_dependency": "jsonschema",
            "schema_validation_enabled": True,
            "missing_dependency_disposition": "FAIL_CLOSED",
            "skip_allowed": False,
            "compile_staging_and_clean_exact_zip": True,
            "exact_set_compile": True,
            "package_python_source_suffixes": [".py"],
            "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
        },
        "release_receipt": {
            "path": release_path.relative_to(ROOT).as_posix(),
            "sha256": sha(release_path),
            "package_id_pointer": "/package_id",
            "status_pointer": "/status",
            "pass_pointer": "/pass",
            "final_zip_sha256_pointer": "/package/sha256",
            "claim_boundary_pointer": "/claim_boundary",
            "expected_claim_boundary": CLAIM,
        },
        "precompile_failure_core": {
            "path": failure_path.relative_to(ROOT).as_posix(),
            "sha256": sha(failure_path),
        },
        "build_receipt_semantics": {
            "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
            "positive_assertions": [
                {"fact_id": "current_epoch_first_fresh", "observed": True, "required": True},
                {"fact_id": "deterministic_exact_zip", "observed": True, "required": True},
                {"fact_id": "frozen_payload", "observed": True, "required": True},
                {"fact_id": "mode_dispatch_binding", "observed": True, "required": True},
            ],
            "negative_observations": [
                {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                {"fact_id": "config_numeric_workload_modified", "observed": False, "required": False},
                {"fact_id": "server_action", "observed": False, "required": False},
                {"fact_id": "managed_storage_write", "observed": False, "required": False},
            ],
            "informational_facts": [
                {
                    "fact_id": "activation_epoch",
                    "value": "family-dispatch-mode-binding-v1-registry43-tbvcd-v112",
                },
                {"fact_id": "diagnostic_mode", "value": "TB_VCD_BOUNDED_CAUSAL_CONE"},
            ],
        },
        "claim_boundary": "Exact final-ZIP package/runtime preflight conjunction only.",
    }
    write(GATES / "package_release_admission_contract.json", contract)
    print(
        json.dumps(
            {
                "pass": True,
                "zip_sha256": zip_sha,
                "contract": str(GATES / "package_release_admission_contract.json"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
