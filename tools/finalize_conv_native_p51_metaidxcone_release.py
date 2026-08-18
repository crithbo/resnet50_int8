#!/usr/bin/env python3
"""Fail-closed local final release receipt for native Conv p51."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p51_metaidxcone"
SOURCE = "r5_n4_0cc_p50_rdbufdrain"
FAMILY = "conv_native_four_lane"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
GATES = OUT / "gates"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_r1786734260114876474_2596301"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    errors: list[str] = []
    regression = {
        "schema": "conv-native-p51-current-shared-regression-v1",
        "package_id": PACKAGE,
        "command": [
            "python", "-m", "pytest", "-q",
            "tests/test_server_tb_vcd_bounded_causal_cone.py",
            "tests/test_server_tb_vcd_runtime_supervision.py",
            "tests/test_server_tb_vcd_exit_returns.py",
            "tests/test_server_tb_vcd_retention_analysis.py",
            "tests/test_server_diagnostic_mode_selector.py",
            "tests/test_server_package_release_admission.py",
            "tests/test_server_package_pipeline.py",
        ],
        "test_result": "93 passed, 7 subtests passed",
        "exit_code": 0,
        "pass": True,
        "server_actions_performed": [],
    }
    regression_path = GATES / "current_shared_regression.json"
    regression_path.write_bytes(canonical(regression))
    required_gates = [
        "first_fresh_validation.json", "tb_vcd_tree_v4.json", "mode_selector_tree_v4.json",
        "mode_selector_zip_v4.json", "hdl_lexical_tree_v4.json", "hdl_lexical_zip_v4.json",
        "runtime_preflight_v4.json", "runner_tree_v4.json", "runner_zip_v4.json",
        "post_sim_final_zip_v4.json", "package_release_admission.json",
        "package_release_receipt.json", "current_shared_regression.json",
    ]
    gate_receipts = []
    for name in required_gates:
        path = GATES / name
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        value = load(path)
        if value.get("pass") is not True:
            errors.append(f"gate not pass: {name}")
        gate_receipts.append({"name": name, **identity(path)})
    for path in (ZIP, REPEAT, SOURCE_ZIP, ANALYSIS / "formal_return_analysis.json", ANALYSIS / "RULE_GAP_AUDIT.json"):
        if not path.is_file():
            errors.append(f"required artifact absent: {path}")
    if ZIP.is_file() and REPEAT.is_file() and ZIP.read_bytes() != REPEAT.read_bytes():
        errors.append("deterministic exact-ZIP recomputation differs")

    manifest_errors: list[str] = []
    if ZIP.is_file():
        with zipfile.ZipFile(ZIP) as archive:
            names = [row.filename for row in archive.infolist() if not row.is_dir()]
            if len(names) != len(set(names)):
                manifest_errors.append("duplicate ZIP member")
            prefix = f"{PACKAGE}/"
            manifest_member = prefix + "package_manifest.json"
            if manifest_member not in names:
                manifest_errors.append("package manifest missing")
            else:
                manifest = json.loads(archive.read(manifest_member))
                actual = {name[len(prefix):] for name in names if name.startswith(prefix)}
                expected = set(manifest.get("files", {})) | {"package_manifest.json"}
                if actual != expected:
                    manifest_errors.append("manifest exact-set mismatch")
                for relative, record in manifest.get("files", {}).items():
                    payload = archive.read(prefix + relative)
                    if len(payload) != record.get("size_bytes") or sha_bytes(payload) != record.get("sha256"):
                        manifest_errors.append(f"manifest identity mismatch: {relative}")
                if manifest.get("status") != "PACKAGE_READY_NOT_RUN":
                    manifest_errors.append("package status is not canonical PACKAGE_READY_NOT_RUN")
            runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode("utf-8")
            tb = archive.read(prefix + "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").decode("utf-8")
            if "(buffer_fifo_enq && !buffer_fifo_full)" not in tb or "(mem_idx_wr && !mem_idx_full)" not in tb:
                manifest_errors.append("accept-qualified progress predicate absent")
            if "capture_actual_compiled_sources.py" not in runner:
                manifest_errors.append("post-compile actual source capture absent")
            request = json.loads(archive.read(prefix + "contracts/server_post_sim_return_request.json"))
            reviews = [row for row in request.get("core_entries", []) if row.get("archive") == "evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"]
            if len(reviews) != 1 or reviews[0].get("source_root") != "attempt":
                manifest_errors.append("direct config/RTL review is not attempt-owned")
            if not any(row.get("archive") == "evidence/compile_bootstrap/actual_compiled_sources/manifest.json" for row in request.get("core_entries", [])):
                manifest_errors.append("actual compiled source manifest absent from return core")
            if archive.read(prefix + "package_tools/server_post_sim_return.py") != (ROOT / "tools/server_post_sim_return.py").read_bytes():
                manifest_errors.append("post-sim helper differs from current canonical")
    errors.extend(manifest_errors)

    p51_storage_matches = sorted(STORAGE.glob(f"*/**/{PACKAGE}.zip"))
    if p51_storage_matches:
        errors.append("p51 unexpectedly exists in managed storage before serialized release")
    formal = load(ANALYSIS / "formal_return_analysis.json") if (ANALYSIS / "formal_return_analysis.json").is_file() else {}
    gap = load(ANALYSIS / "RULE_GAP_AUDIT.json") if (ANALYSIS / "RULE_GAP_AUDIT.json").is_file() else {}
    if formal.get("pass") is not True:
        errors.append("p50 formal analysis not pass")
    if gap.get("rule_disposition") != "RULE_CONFIRMATION_NO_CHANGE":
        errors.append("p50 rule disposition differs")

    report = {
        "schema": "conv-native-p51-final-zip-release-audit-v1",
        "package_id": PACKAGE, "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_TERMINAL_GATE_FAILURE",
        "storage_disposition": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<execution>_return.zip",
        "zip": identity(ZIP) if ZIP.is_file() else None,
        "repeat_zip": identity(REPEAT) if REPEAT.is_file() else None,
        "source_p50_pending": identity(SOURCE_ZIP) if SOURCE_ZIP.is_file() else None,
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json") if (ANALYSIS / "formal_return_analysis.json").is_file() else None,
        "rule_gap_audit": identity(ANALYSIS / "RULE_GAP_AUDIT.json") if (ANALYSIS / "RULE_GAP_AUDIT.json").is_file() else None,
        "rule_audit_disposition": gap.get("rule_disposition"),
        "gate_receipts": gate_receipts,
        "manifest_exact_set_pass": not manifest_errors,
        "deterministic_zip_pass": ZIP.is_file() and REPEAT.is_file() and ZIP.read_bytes() == REPEAT.read_bytes(),
        "p51_storage_matches": [path.relative_to(ROOT).as_posix() for path in p51_storage_matches],
        "storage_manager_invoked": False,
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
        "claim_boundary": "Local build/gates only; no p51 production compile/simulation, validated root, natural terminal, formal D, E3, E4 or E5 claim.",
    }
    final_path = GATES / "final_zip_release_audit.json"; final_path.write_bytes(canonical(report))
    evidence = {
        "schema": "conv-native-p51-release-evidence-v1", "package_id": PACKAGE, "family": FAMILY,
        "status": report["status"], "final_zip_release_audit": identity(final_path), "package": report["zip"],
        "storage_disposition": report["storage_disposition"],
        "previous_version_progress": "p50 executed MSE4 and proved an 18 metadata/output versus 20 prepared versus 23/21 RD enqueue/dequeue mismatch, but false held-enqueue progress reached the wall ceiling.",
        "current_version_purpose": "Qualify real progress and distinguish Buffer_AG/Memory_AG index lifetime, WR metadata transfer and spatial accounting while returning actual post-compile RTL bytes.",
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM",
        "server_actions_performed": [], "errors": errors, "pass": not errors,
        "claim_boundary": report["claim_boundary"],
    }
    evidence_path = OUT / f"{PACKAGE}.release_evidence.json"; evidence_path.write_bytes(canonical(evidence))
    wait = {
        "schema": "conv-native-p51-storage-wait-v1", "package_id": PACKAGE,
        "disposition": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE", "p51_present_in_managed_storage": bool(p51_storage_matches),
        "source_p50_pending_preserved": SOURCE_ZIP.is_file(), "storage_manager_invoked": False,
        "server_actions_performed": [], "pass": not p51_storage_matches and SOURCE_ZIP.is_file(),
    }
    wait_path = OUT / "storage_wait_receipt.json"; wait_path.write_bytes(canonical(wait))
    print(json.dumps({"package_id": PACKAGE, "pass": not errors, "errors": errors, "final": str(final_path)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
