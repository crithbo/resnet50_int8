#!/usr/bin/env python3
"""Fail closed on v104 frozen surfaces and two-phase return ordering."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v103b_lcdup_obsfix"
NEW = "r5_n4_hw_v104b_lcdup_return2p"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def members(archive: zipfile.ZipFile, root: str) -> dict[str, bytes]:
    return {
        PurePosixPath(name).relative_to(root).as_posix(): archive.read(name)
        for name in archive.namelist()
        if name.startswith(root + "/") and not name.endswith("/")
    }


def normalized(value: bytes) -> bytes:
    try:
        text = value.decode("utf-8").replace(NEW, OLD)
        text = re.sub(r"(?m)^// plan_semantic_sha256=[0-9a-f]{64}\r?$", "// plan_semantic_sha256=<IDENTITY_BOUND>", text)
        return text.encode("utf-8")
    except UnicodeDecodeError:
        return value


def temporal_errors(runner: str, request: dict[str, Any], allowlist: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prepare = runner.find("node0004_two_phase_return.py\" prepare")
    validate = runner.find("node0004_two_phase_return.py\" validate")
    publish = runner.find("server_post_sim_return.py\" finalize")
    if min(prepare, validate, publish) < 0 or not (prepare < validate < publish):
        errors.append("two-phase prepare/validate/publish ordering differs")
    finalization_lines = [line for line in runner.splitlines() if "supervise-phase --phase finalization" in line]
    if len(finalization_lines) != 1 or "node0004_two_phase_return.py\" prepare" not in finalization_lines[0] or "server_post_sim_return.py" in finalization_lines[0]:
        errors.append("finalization guard does not exclusively wrap no-publication prepare")
    for token in (
        "PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        "PREPUBLICATION_RETURN_CONJUNCTION.json",
        "FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
        "prepublication_guard_rc",
        "prepublication_validate_rc",
        "cleanup-after-durable-return",
        "--finalization-guard-receipt",
    ):
        if token not in runner:
            errors.append(f"runner token absent: {token}")
    by_archive = {item.get("archive"): item for item in request.get("core_entries", [])}
    for archive in (
        "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
        "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
    ):
        if by_archive.get(archive, {}).get("required") is not True:
            errors.append(f"mandatory prepublication entry absent: {archive}")
    if "evidence/OPERATIONAL_GUARD_RECEIPT.json" in by_archive:
        errors.append("stale OPERATIONAL_GUARD_RECEIPT entry remains")
    prefix = f"{NEW}_return/"
    required = {item for item in allowlist.get("required", []) if isinstance(item, str)}
    for item in (
        prefix + "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
        prefix + "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
        prefix + "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
        prefix + "evidence/OPERATIONAL_STOP_RECEIPT.json",
    ):
        if item not in required:
            errors.append(f"return allowlist prepublication member absent: {item}")
    for item in (
        prefix + "evidence/OPERATIONAL_GUARD_RECEIPT.json",
        prefix + "evidence/DURABLE_RETURN_RECEIPT.json",
        prefix + "evidence/POST_DURABLE_CLEANUP_RECEIPT.json",
    ):
        if item in required:
            errors.append(f"post-publication/stale member falsely mandatory inside ZIP: {item}")
    external = set(allowlist.get("external_receipts", []))
    if "{package_id}_{execution_id}_DURABLE_RETURN_RECEIPT.json" not in external or "{return_zip}.cleanup.json" not in external:
        errors.append("durable/cleanup external sidecars are not declared")
    return errors


def synthetic_helper(helper: Path) -> tuple[list[dict[str, Any]], list[str]]:
    controls: list[dict[str, Any]] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v104-prepublication-") as raw:
        root = Path(raw)
        package = root / "package"; attempt = root / "attempt"
        package.mkdir(); (attempt / "evidence").mkdir(parents=True)
        (package / "package_manifest.json").write_text("{}\n", encoding="utf-8")
        (attempt / "evidence/input.json").write_text("{}\n", encoding="utf-8")
        request = {
            "schema": "server-post-sim-return-request-v1", "package_id": NEW,
            "core_entries": [
                {"archive": "evidence/input.json", "source": "evidence/input.json", "source_root": "attempt", "required": True},
                {"archive": "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json", "source": "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json", "source_root": "attempt", "required": True},
                {"archive": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json", "source": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json", "source_root": "attempt", "required": True},
                {"archive": "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json", "source": "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json", "source_root": "attempt", "required": True},
            ],
        }
        request_path = package / "request.json"; request_path.write_text(json.dumps(request), encoding="utf-8")
        admission = attempt / "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json"
        guard_path = attempt / "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json"
        conjunction = attempt / "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json"
        environment = os.environ.copy()
        environment.update({"CODEX_PACKAGE_ROOT": str(package), "CODEX_ATTEMPT_ROOT": str(attempt), "CODEX_PACKAGE_ID": NEW, "CODEX_EXECUTION_ID": "rsynthetic", "CODEX_ATTEMPT_ID": "asynthetic"})
        prepare = subprocess.run([sys.executable, str(helper), "prepare", "--request", str(request_path), "--admission", str(admission)], env=environment, capture_output=True, text=True, check=False)
        guard = {
            "schema": "server-observer-operational-guard-receipt-v2", "package_id": NEW,
            "execution_id": "rsynthetic", "attempt_id": "asynthetic", "phase": "finalization",
            "pass": True, "child_exit": 0, "process_fully_reaped": True,
            "termination": {"process_tree_reaped": True, "owned_pids_remaining": [], "owned_process_identities_remaining": []},
        }
        guard_path.write_text(json.dumps(guard), encoding="utf-8")
        positive = subprocess.run([sys.executable, str(helper), "validate", "--request", str(request_path), "--admission", str(admission), "--finalization-guard", str(guard_path), "--output", str(conjunction)], env=environment, capture_output=True, text=True, check=False)
        controls.append({"control": "two_phase_positive", "pass": prepare.returncode == 0 and positive.returncode == 0 and json.loads(conjunction.read_text()).get("publication_authorized") is True})
        (attempt / "evidence/input.json").write_text('{"drift":true}\n', encoding="utf-8")
        drift = subprocess.run([sys.executable, str(helper), "validate", "--request", str(request_path), "--admission", str(admission), "--finalization-guard", str(guard_path), "--output", str(conjunction)], env=environment, capture_output=True, text=True, check=False)
        controls.append({"control": "snapshot_drift_negative", "pass": drift.returncode != 0})
        (attempt / "evidence/input.json").write_text("{}\n", encoding="utf-8")
        guard["termination"]["owned_process_identities_remaining"] = [{"pid": 9, "start_time_ticks": 1}]
        guard_path.write_text(json.dumps(guard), encoding="utf-8")
        reap = subprocess.run([sys.executable, str(helper), "validate", "--request", str(request_path), "--admission", str(admission), "--finalization-guard", str(guard_path), "--output", str(conjunction)], env=environment, capture_output=True, text=True, check=False)
        controls.append({"control": "remaining_identity_negative", "pass": reap.returncode != 0})
    if not all(item["pass"] for item in controls):
        errors.append("two-phase helper controls did not all pass")
    return controls, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--fresh-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    frozen: list[dict[str, Any]] = []
    with zipfile.ZipFile(args.source_zip) as old_zip, zipfile.ZipFile(args.fresh_zip) as new_zip:
        old = members(old_zip, OLD); new = members(new_zip, NEW)
        required = sorted([path for path in old if path.startswith("workload/")] + [
            "provenance/lc_branch_duplication_mapper_ab_report.json",
            "provenance/B_duplicate_lc_branch_config.json",
            "diagnostics/source_bound_probe_catalog.json",
            "diagnostics/source_bound_probe_plan.json",
            "diagnostics/source_bound_exact_instance_identity.json",
            "tb_probe/observer_only_wide_causal.svh",
            "package_tools/node0004_observer_counter_guard_bridge.py",
            "package_tools/node0004_observerwide_event_parser.py",
        ])
        for path in required:
            equal = path in new and normalized(old[path]) == normalized(new[path])
            frozen.append({"path": path, "normalized_equal": equal, "old_sha256": sha(old.get(path, b"")), "new_sha256": sha(new.get(path, b""))})
            if not equal:
                errors.append(f"frozen member differs: {path}")
        old_contract = json.loads(old["contracts/observer_only_wide_causal_contract.json"])
        new_contract = json.loads(new["contracts/observer_only_wide_causal_contract.json"])
        axes = lambda value: [(row["signal_id"], row["width_bits"], row.get("hierarchy")) for row in value["signals"]]
        if axes(old_contract) != axes(new_contract) or len(new_contract.get("signals", [])) != 52:
            errors.append("52-signal cone differs")
        if old_contract.get("candidates") != new_contract.get("candidates") or old_contract.get("boundary_observations") != new_contract.get("boundary_observations"):
            errors.append("candidate/boundary matrix differs")
        runner = new["PREPARE_AND_RUN.sh"].decode("utf-8")
        request = json.loads(new["contracts/server_post_sim_return_request.json"])
        allowlist = json.loads(new["RETURN_ALLOWLIST.json"])
        errors.extend(temporal_errors(runner, request, allowlist))

        old_runner = old["PREPARE_AND_RUN.sh"].decode("utf-8")
        old_request = json.loads(old["contracts/server_post_sim_return_request.json"])
        old_allow = json.loads(old["RETURN_ALLOWLIST.json"])
        controls: list[dict[str, Any]] = []
        controls.append({"control": "exact_v103_negative", "pass": bool(temporal_errors(old_runner, old_request, old_allow))})
        controls.append({"control": "wrap_publisher_negative", "pass": bool(temporal_errors(runner.replace('node0004_two_phase_return.py\" prepare', 'server_post_sim_return.py\" finalize', 1), request, allowlist))})
        bad_allow = json.loads(json.dumps(allowlist)); bad_allow["required"].append(f"{NEW}_return/evidence/DURABLE_RETURN_RECEIPT.json")
        controls.append({"control": "post_durable_inside_zip_negative", "pass": bool(temporal_errors(runner, request, bad_allow))})
        bad_request = json.loads(json.dumps(request)); bad_request["core_entries"].append({"archive": "evidence/OPERATIONAL_GUARD_RECEIPT.json", "source": "evidence/OPERATIONAL_GUARD_RECEIPT.json", "source_root": "attempt", "required": True})
        controls.append({"control": "receipt_name_mismatch_negative", "pass": bool(temporal_errors(runner, bad_request, allowlist))})
        no_conjunction = json.loads(json.dumps(request)); no_conjunction["core_entries"] = [item for item in no_conjunction["core_entries"] if item.get("archive") != "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json"]
        controls.append({"control": "missing_conjunction_negative", "pass": bool(temporal_errors(runner, no_conjunction, allowlist))})
        if not all(item["pass"] for item in controls):
            errors.append("one or more exact v103 temporal negatives escaped")
    helper_controls, helper_errors = synthetic_helper(ROOT / "tools/node0004_two_phase_return.py")
    errors.extend(helper_errors)
    report = {
        "schema": "node0004-v104b-lcdup-return2p-validation-v1",
        "package_id": NEW,
        "pass": not errors,
        "errors": errors,
        "frozen_rows": frozen,
        "exact_v103_negative_controls": controls,
        "two_phase_helper_controls": helper_controls,
        "changed_surface": ["fresh identity", "mode binding", "two-phase return/finalization ordering"],
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3", "52-signal cone", "observer counters/plateau"],
        "claim_boundary": "Exact local package and two-phase return controls only; no production compile, simulation, tuple10, natural terminal or Formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
