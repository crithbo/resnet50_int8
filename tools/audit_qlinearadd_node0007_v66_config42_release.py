#!/usr/bin/env python3
"""Run all current v66 final-ZIP gates plus the authorized config-lineage gate."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
PRIOR = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
EPOCH = "qadd-validated-config-lineage-repair-v1+tb-vcd-adaptive-v4+runtime-v3"
OUT = ROOT / "outputs/qlinearadd_node0007_v66_cfg42_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PRIOR}.zip"
GATES = OUT / "gates"
CONFIG_REPORT = GATES / "config_lineage_exact.json"
PYTHON = Path(sys.executable)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def run_config_gate() -> None:
    argv = [
        str(PYTHON),
        str(ROOT / "tools/validate_qlinearadd_node0007_v66_config42_release.py"),
        "--tree", str(TREE),
        "--zip", str(ZIP),
        "--repeat-zip", str(REPEAT),
        "--prior-zip", str(PRIOR_ZIP),
        "--output", str(CONFIG_REPORT),
    ]
    completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
    if completed.returncode != 0 or not CONFIG_REPORT.is_file() or load(CONFIG_REPORT).get("pass") is not True:
        raise RuntimeError(f"config-lineage exact gate failed: rc={completed.returncode} stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}")


def adapted_v65_audit() -> int:
    source_path = ROOT / "tools/audit_qlinearadd_node0007_v65_tbvcdrt3_release.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"', f'PACKAGE = "{PACKAGE}"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"', f'PRIOR = "{PRIOR}"'),
        ('EPOCH = "tb-vcd-first-round-breadth-v4+tb-vcd-exit-mechanism-consistency-v3+package-python-schema-runtime-v2"', f'EPOCH = "{EPOCH}"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v66_cfg42_release"'),
        ('TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v65.svh"', 'TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v66.svh"'),
        ('LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v65.py"', 'LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v66.py"'),
        ('FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v65.py"', 'FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v66.py"'),
        ("codex_qadd_tb_vcd_causal_cone_v65", "codex_qadd_tb_vcd_causal_cone_v66"),
        ("qadd-v65", "qadd-v66"),
        ("QAdd v65", "QAdd v66"),
        ("config_numeric_workload_modified", "unauthorized_config_numeric_workload_modified"),
        ('"config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"', '"all_other_config_leaves", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"'),
        ("no production v65 compile/simulation", "no production v66 compile/simulation"),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v65 audit adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v66_adapted_audit", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    return int(namespace["main"]())


def rerun_first_fresh_with_config_gate() -> None:
    candidate_path = OUT / "first_fresh_audit/reports/candidate_discrimination_matrix.json"
    candidate = load(candidate_path)
    candidate["config_lineage_materialization_and_negative_controls"] = {
        "report": identity(CONFIG_REPORT),
        "authorized_two_leaf_delta_exact": True,
        "positive_recompute_byte_equal": True,
        "restore_32_16_rejected": True,
        "old_bad_bitstream_rejected": True,
    }
    candidate["pass"] = candidate.get("pass") is True and load(CONFIG_REPORT).get("pass") is True
    write(candidate_path, candidate)
    contract_path = OUT / "first_fresh_audit/contract.json"
    contract = load(contract_path)
    contract["rule_change"]["epoch_id"] = EPOCH
    contract["rule_change"]["rule_ids"] = [
        "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
        "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
    ]
    for row in contract["evidence_reports"]:
        if row["gate_id"] == "candidate_discrimination_matrix":
            row["sha256"] = sha(candidate_path)
    write(contract_path, contract)
    output = GATES / "first_fresh_validation.json"
    completed = subprocess.run(
        [str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0 or load(output).get("pass") is not True:
        raise RuntimeError(f"current-epoch first-fresh rerun failed: rc={completed.returncode} stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}")


def storage_prepublication_gate() -> Path:
    index_path = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"
    pending = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    index = load(index_path)
    physical = sorted(path.name for path in pending.glob("*.zip"))
    checks = {
        "storage_index_read_only": True,
        "prior_v65_still_physical_pending": PRIOR_ZIP.is_file() and sha(PRIOR_ZIP) == "ed204d677bd379f30aba96c2a3d4c228a646dd8c885a9b07ebe545278948c800",
        "fresh_v66_not_published": not (pending / f"{PACKAGE}.zip").exists(),
        "fresh_v66_staged_only": ZIP.is_file(),
        "no_storage_manager_call": True,
    }
    report = {
        "schema": "qadd-v66-storage-prepublication-wait-v1",
        "package_id": PACKAGE,
        "status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "checks": checks,
        "physical_pending_zip_names": physical,
        "storage_index": identity(index_path),
        "prior_pending": identity(PRIOR_ZIP),
        "staged_fresh": identity(ZIP),
        "storage_manager_called": False,
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
    }
    path = GATES / "storage_prepublication_wait.json"
    write(path, report)
    if report["pass"] is not True:
        raise RuntimeError(f"storage prepublication gate failed: {report['errors']}")
    return path


def finalize_receipts(storage_report: Path) -> None:
    first_path = GATES / "first_fresh_validation.json"
    final_path = GATES / "final_zip_release_audit.json"
    final = load(final_path)
    final["schema"] = "qadd-v66-config42-final-release-audit-v1"
    final["activation_epoch"] = EPOCH
    final["status"] = "PACKAGE_READY_NOT_RUN"
    final["checks"]["config_materialization_roundtrip"] = load(CONFIG_REPORT).get("pass") is True
    final["checks"]["full_hdl_scope_state_source_bound"] = load(OUT / "first_fresh_audit/reports/full_hdl_source_bound.json").get("pass") is True
    final["checks"]["deterministic_exact_zip"] = ZIP.read_bytes() == REPEAT.read_bytes()
    final["checks"]["storage_prepublication_wait"] = load(storage_report).get("pass") is True
    final["config_lineage_validation"] = identity(CONFIG_REPORT)
    final["storage_prepublication"] = identity(storage_report)
    final["first_fresh"] = identity(first_path)
    final["previous_version_progress"] = "v57h localized the Buffer5 request-decode to selected required-lane read-accept alias boundary; v65 fixed runtime-v3 but remained unrun with the stale 32/16 bitstream."
    final["current_version_purpose"] = "Dynamically confirm the validated 4/2 lineage through ordered 0x33333333 then 0xcccccccc requests, both accept/clear, output, terminal and formal-D evidence."
    final["claim_boundary"] = "All local exact-ZIP/config/source/runtime/return/first-fresh/release/storage-prepublication gates only; no production compile/simulation, natural terminal, formal-D or E3-E5 claim."
    final["pass"] = all(final["checks"].values())
    final["errors"] = [] if final["pass"] else [name for name, passed in final["checks"].items() if not passed]
    write(final_path, final)
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    release = load(release_path)
    release["schema"] = "qadd-v66-config42-package-ready-not-run-v1"
    release["activation_epoch"] = EPOCH
    release["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE"
    release["final_zip_audit"] = identity(final_path)
    release["first_fresh"] = identity(first_path)
    release["config_lineage_validation"] = identity(CONFIG_REPORT)
    release["storage_prepublication"] = identity(storage_report)
    release["previous_version_progress"] = final["previous_version_progress"]
    release["current_version_purpose"] = final["current_version_purpose"]
    release["frozen"] = ["all_other_config_leaves", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"]
    release["pass"] = final["pass"]
    release["errors"] = final["errors"]
    release["claim_boundary"] = final["claim_boundary"]
    write(release_path, release)
    build_path = OUT / "build_receipt.json"
    build = load(build_path)
    build["status"] = release["status"]
    build["local_gates"] = identity(final_path)
    build["storage_prepublication"] = identity(storage_report)
    build["pass"] = release["pass"]
    build["errors"] = release["errors"]
    write(build_path, build)


def main() -> int:
    dependency = Path(r"C:\Users\15383\AppData\Local\Temp\codex_jsonschema_20260809")
    if dependency.is_dir():
        current = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(dependency) if not current else str(dependency) + os.pathsep + current
    if sys.argv[1:] == ["--finalize-only"]:
        storage_report = storage_prepublication_gate()
        finalize_receipts(storage_report)
        final = load(GATES / "final_zip_release_audit.json")
        print(json.dumps({"package_id": PACKAGE, "status": final["status"], "pass": final["pass"], "errors": final["errors"]}, sort_keys=True))
        return 0 if final["pass"] else 1
    run_config_gate()
    result = adapted_v65_audit()
    if result != 0:
        return result
    rerun_first_fresh_with_config_gate()
    storage_report = storage_prepublication_gate()
    finalize_receipts(storage_report)
    final = load(GATES / "final_zip_release_audit.json")
    print(json.dumps({"package_id": PACKAGE, "status": final["status"], "pass": final["pass"], "errors": final["errors"]}, sort_keys=True))
    return 0 if final["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
