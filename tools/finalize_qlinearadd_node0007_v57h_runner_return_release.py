#!/usr/bin/env python3
"""Finalize local release receipts for exact QAdd v57h without server action."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v57h"
SOURCE_PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v57f"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57h-package"
ZIP = LOCAL / f"{PACKAGE}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{SOURCE_PACKAGE}.zip"
SOURCE_SHA = "eeb922f3828b0e1dd6532bf0903e516351f0a4a0a9a0439b917e8e1b2532415e"
V57G_FAILURE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57g-package/r5_qadd_n7_tailround_lanephase_qual_v57g.failed_exact_zip_audit.json"
AUDIT = LOCAL / "first_fresh_extra_audit_v2"
COPIES = {
    AUDIT / "contract.json": LOCAL / f"{PACKAGE}.first_fresh_contract.json",
    AUDIT / "preparation_report.json": LOCAL / f"{PACKAGE}.first_fresh_preparation.json",
    AUDIT / "exact_final_zip_clean_extract.json": LOCAL / f"{PACKAGE}.clean_extract.json",
    AUDIT / "actual_runner_entry_and_input_open.json": LOCAL / f"{PACKAGE}.runner_input.json",
    AUDIT / "source_bound_logger_collector_parser_roundtrip.json": LOCAL / f"{PACKAGE}.source_bound_roundtrip.json",
    AUDIT / "post_sim_return_core_scenarios.json": LOCAL / f"{PACKAGE}.post_sim_scenarios.json",
    AUDIT / "candidate_discrimination_matrix.json": LOCAL / f"{PACKAGE}.candidate_discrimination.json",
}
REPORTS = {
    "build": LOCAL / f"{PACKAGE}.build.json",
    "frozen_surface": LOCAL / f"{PACKAGE}.frozen_surface.json",
    "runner_resilience": LOCAL / f"{PACKAGE}.runner_resilience.json",
    "source_bound_final_zip": LOCAL / f"{PACKAGE}.source_bound_final_zip.json",
    "post_sim": LOCAL / f"{PACKAGE}.post_sim.json",
    "first_fresh": LOCAL / f"{PACKAGE}.first_fresh_validation.json",
    "local_tests": LOCAL / f"{PACKAGE}.local_tests.json",
}
RELEASE = LOCAL / f"{PACKAGE}.release.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    required = [ZIP, SIDECAR, SOURCE_ZIP, V57G_FAILURE, *REPORTS.values(), *COPIES.keys()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing release inputs: {missing}")
    if RELEASE.exists() or any(target.exists() for target in COPIES.values()):
        raise RuntimeError("fresh release receipt targets required")
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("immutable v57f source ZIP changed")
    sidecar_tokens = SIDECAR.read_text(encoding="ascii").strip().split()
    if not sidecar_tokens or sidecar_tokens[0] != sha(ZIP):
        raise RuntimeError("v57h sidecar differs")
    loaded = {name: load(path) for name, path in REPORTS.items()}
    failures = [name for name, value in loaded.items() if value.get("pass") is False]
    failures += [
        name
        for name, value in loaded.items()
        if name != "build" and not isinstance(value.get("pass"), bool)
    ]
    if loaded["first_fresh"].get("upload_authorized") is not True:
        failures.append("first_fresh.upload_authorized")
    if loaded["build"].get("status") != "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AND_FIRST_FRESH_AUDIT":
        failures.append("build.status")
    if loaded["build"].get("zip", {}).get("sha256") != sha(ZIP):
        failures.append("build.zip")
    if failures:
        raise RuntimeError(f"release gates failed: {sorted(set(failures))}")
    for source, target in COPIES.items():
        shutil.copy2(source, target)
    reports = {name: receipt(path) for name, path in REPORTS.items()}
    reports.update(
        {
            "first_fresh_contract": receipt(COPIES[AUDIT / "contract.json"]),
            "clean_extract": receipt(COPIES[AUDIT / "exact_final_zip_clean_extract.json"]),
            "runner_input": receipt(COPIES[AUDIT / "actual_runner_entry_and_input_open.json"]),
            "source_bound_roundtrip": receipt(COPIES[AUDIT / "source_bound_logger_collector_parser_roundtrip.json"]),
            "post_sim_scenarios": receipt(COPIES[AUDIT / "post_sim_return_core_scenarios.json"]),
            "candidate_discrimination": receipt(COPIES[AUDIT / "candidate_discrimination_matrix.json"]),
        }
    )
    value = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57h-release-v1",
        "pass": True,
        "errors": [],
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": PACKAGE,
        "family": "qlinearadd_node0007",
        "zip": receipt(ZIP),
        "sidecar": receipt(SIDECAR),
        "planned_pending_path": f"artifacts/operator_config_validation/r5-server-test-packages/pending/{PACKAGE}.zip",
        "source_v57f": {
            **receipt(SOURCE_ZIP),
            "immutable": True,
            "new_gate_pass": False,
        },
        "failed_unpublished_v57g": {
            **receipt(V57G_FAILURE),
            "disposition": "SUPERSEDED_UNPUBLISHED_HELD_EXACT_SOURCE_BOUND_FREEZE_FAILED",
        },
        "rule_change_epoch_id": "20260811-exact-instance-payload-semantic-fingerprint-v2",
        "first_fresh_for_family": True,
        "first_fresh_upload_authorized": True,
        "runner_return_only_successor": True,
        "frozen_surface": {
            "config_numeric_workload_rtl_changed": False,
            "diagnostic_observer_parser_plan_binding_exact_byte_equal": True,
            "numeric_or_golden_recomputed": False,
        },
        "release_gate_matrix": {
            "exact_clean_extract": "PASS",
            "runner_set_u_definition_before_use": "PASS",
            "compilefail_core_return_root_cause": "PASS",
            "source_bound_exact_generation_and_semantic_controls": "PASS",
            "post_sim_return_four_scenarios": "PASS",
            "candidate_discrimination": "PASS_4_POSITIVE_8_NEGATIVE",
            "first_fresh_independent_reaudit": "PASS_UPLOAD_AUTHORIZED",
            "local_regression_tests": "PASS_43",
            "server_execution": "NOT_RUN",
        },
        "validation_receipts": reports,
        "server_command": f"bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<execution>_return.zip",
        "claim_boundary": "RUNNER_RETURN_ONLY / E2_LOCAL_ONLY; no compile, simulation, natural terminal, formal D, E3, E4 or E5 server claim.",
        "server_action": False,
        "lease_acquired": False,
        "analysis_owner_thread": "019ff02d-9e93-7d61-8c98-c928fdea157c",
        "return_target_thread": "019ff027-e7db-72a3-b282-cfad8708da05",
    }
    write(RELEASE, value)
    print(json.dumps({"pass": True, "release": receipt(RELEASE), "zip": receipt(ZIP)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
