#!/usr/bin/env python3
"""Prepare independent family/shared receipts before v52 storage rotation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_queueflow_v52"
OLD = "r5_qadd_n7_tailround_split_clean_v51"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package"
ZIP = OUT / f"{NAME}.zip"
AUDIT = OUT / "first_fresh_extra_audit"
SOURCE_HARNESS = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-package/runtime_layout_harness.json"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    extra = json.loads((AUDIT / "validation.json").read_text(encoding="utf-8"))
    if extra.get("pass") is not True or extra.get("errors") != [] or extra.get("upload_authorized") is not True:
        raise SystemExit("first-fresh extra audit is not a release prerequisite PASS")
    source = SOURCE_HARNESS.read_text(encoding="utf-8").replace(OLD, NAME)
    harness = json.loads(source)
    harness["derived_from_zip_sha256"] = sha(ZIP)
    import zipfile
    with zipfile.ZipFile(ZIP) as archive:
        root = archive.namelist()[0].split("/", 1)[0]
        runner = archive.read(f"{root}/PREPARE_AND_RUN.sh")
    harness["runner_member_sha256"] = hashlib.sha256(runner).hexdigest()
    harness["claim_boundary"] = "Install-only V2 scenarios reused only for byte-unchanged layout/finalizer path; exact v52 runner inputs, feature, parser and observer are independently clean-extract audited; no DUT/server action."
    harness_path = OUT / "runtime_layout_harness.json"
    write_json(harness_path, harness)
    shared_path = OUT / "shared_runtime_layout_validation.json"
    command = [
        str(PYTHON), str(ROOT / "tools/validate_server_package_runtime_layout.py"),
        "--zip", str(ZIP), "--harness-report", str(harness_path),
        "--helper-reference", str(ROOT / "tools/server_package_runtime_layout.py"),
        "--require-runner-error-visibility", "--output", str(shared_path),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"shared runtime validation failed: {result.stdout}\n{result.stderr}")
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    reports = [
        AUDIT / "exact_final_zip_clean_extract.json",
        AUDIT / "actual_runner_entry_and_input_open.json",
        AUDIT / "source_bound_logger_collector_parser_roundtrip.json",
        AUDIT / "post_sim_return_core_scenarios.json",
        AUDIT / "candidate_discrimination_matrix.json",
    ]
    checks = {
        "first_fresh_extra_audit": extra.get("pass") is True and extra.get("errors") == [],
        "shared_runtime_layout": shared.get("pass") is True and shared.get("errors") == [],
        "all_independent_reports_pass": all(json.loads(path.read_text(encoding="utf-8")).get("pass") is True for path in reports),
        "zip_identity": extra.get("package_id") == NAME and extra.get("candidate_coverage", {}).get("covered") == 4,
    }
    errors = [key for key, value in checks.items() if value is not True]
    family = {
        "schema": "qlinearadd-node0007-tailround-queueflow-v52-family-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "first_fresh_extra_audit": {"contract_sha256": sha(AUDIT / "contract.json"), "validation_sha256": sha(AUDIT / "validation.json"), "upload_authorized": extra.get("upload_authorized")},
        "shared_runtime_layout": {"harness_sha256": sha(harness_path), "validation_sha256": sha(shared_path)},
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_changed": False,
        "server_action": False,
        "claim_boundary": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / isolated op_tail_round queue-flow; host-precomputed FP32 stimulus is not producer evidence; no full-chain/E3/E4/E5 claim.",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(OUT / "family_validation.json", family)
    print(json.dumps({"valid": not errors, "errors": errors, "shared_exit": result.returncode, "family": str(OUT / 'family_validation.json')}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
