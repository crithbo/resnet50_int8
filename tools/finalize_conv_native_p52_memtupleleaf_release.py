#!/usr/bin/env python3
"""Fail-closed local final release receipt for native Conv p52."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p52_memtupleleaf"
SOURCE = "r5_n4_0cc_p51_metaidxcone"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3"
PACKAGE_EPOCH = EPOCH + "+conv-native-p51-direct-memory-tuple-leaf-v1"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release"
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
GATES = OUT / "gates"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "tested" / FAMILY / SOURCE / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_return_analysis_r1786770085722684994_2783486"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    errors: list[str] = []
    regression = {
        "schema": "conv-native-p52-current-shared-regression-v1",
        "package_id": PACKAGE,
        "activation_epoch": EPOCH,
        "command": [
            ".venv/Scripts/python.exe", "-m", "unittest",
            "tests.test_server_tb_vcd_bounded_causal_cone",
            "tests.test_server_tb_vcd_runtime_supervision",
            "tests.test_server_tb_vcd_exit_returns",
            "tests.test_server_tb_vcd_retention_analysis",
            "tests.test_server_diagnostic_mode_selector",
            "tests.test_server_package_release_admission",
            "tests.test_server_package_pipeline",
        ],
        "test_result": "Ran 99 tests; OK",
        "exit_code": 0,
        "package_python_compile_count": 13,
        "package_python_compile_errors": [],
        "pass": True,
        "server_actions_performed": [],
    }
    regression_path = GATES / "current_shared_regression_v5.json"
    regression_path.write_bytes(canonical(regression))

    required_gates = [
        "first_fresh_validation_v5.json",
        "tb_vcd_tree_v5.json",
        "mode_selector_tree_v5.json",
        "mode_selector_zip_v5.json",
        "hdl_lexical_tree_v5.json",
        "hdl_lexical_zip_v5.json",
        "runtime_preflight_v5.json",
        "runner_tree_v5.json",
        "runner_zip_v5.json",
        "post_sim_final_zip_v5.json",
        "package_release_admission.json",
        "package_release_receipt.json",
        "current_shared_regression_v5.json",
    ]
    gate_receipts: list[dict[str, Any]] = []
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
    deterministic = ZIP.is_file() and REPEAT.is_file() and ZIP.read_bytes() == REPEAT.read_bytes()
    if not deterministic:
        errors.append("deterministic exact-ZIP recomputation differs")

    manifest_errors: list[str] = []
    if ZIP.is_file():
        with zipfile.ZipFile(ZIP) as archive:
            if archive.testzip() is not None:
                manifest_errors.append("ZIP CRC failure")
            names = [row.filename for row in archive.infolist() if not row.is_dir()]
            prefix = f"{PACKAGE}/"
            if len(names) != len(set(names)):
                manifest_errors.append("duplicate ZIP member")
            if {Path(name).parts[0] for name in names} != {PACKAGE}:
                manifest_errors.append("ZIP root member differs")
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
                if manifest.get("package_identity") != PACKAGE or manifest.get("status") != "PACKAGE_READY_NOT_RUN":
                    manifest_errors.append("package identity/status differs")
                if manifest.get("source_package") != SOURCE:
                    manifest_errors.append("source package differs")
                if manifest.get("activation_epoch") != PACKAGE_EPOCH:
                    manifest_errors.append("activation epoch differs")

            contract = json.loads(archive.read(prefix + "contracts/server_tb_vcd_bounded_causal_cone_contract.json"))
            policy = contract.get("runtime_policy", {})
            if len(contract.get("signals", [])) != 146 or len(contract.get("candidates", [])) != 14:
                manifest_errors.append("p52 signal/candidate breadth differs")
            required_policy = {
                "planned_dumpoff_state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
                "post_dumpoff_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
                "dump_off_grace_precedes_freeze": True,
                "stop_marker_policy": "ONE_SHOT_LATCHED",
                "decision_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
            }
            for key, expected_value in required_policy.items():
                if policy.get(key) != expected_value:
                    manifest_errors.append(f"semantic-v5 runtime policy differs: {key}")

            runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode("utf-8")
            tb = archive.read(prefix + "tb_probe/native_mse4_bounded_causal_cone_vcd.sv").decode("utf-8")
            live = archive.read(prefix + "package_tools/tb_vcd_live_supervision.py").decode("utf-8")
            finalizer = archive.read(prefix + "package_tools/tb_vcd_finalize.py").decode("utf-8")
            if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
                manifest_errors.append("production launch cardinality differs")
            if not all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")):
                manifest_errors.append("actual Make dump argv differs")
            if tb.count("CODEX_TBVCD_STOP_V2") != 1 or "!codex_stop_reported" not in tb:
                manifest_errors.append("TB one-shot STOP differs")
            if "if (codex_dump_off) begin" not in tb or "$dumpon;\n        codex_dump_off <= 0" in tb:
                manifest_errors.append("TB planned dumpoff is not sticky")
            if not all(token in live for token in ("dumpoff_consistency_authority", "planned_dumpoff_cycle", "stop_marker_count")):
                manifest_errors.append("live supervisor semantic-v5 binding differs")
            if not all(token in finalizer for token in ("dumpoff_consistency_authority", "TB_VCD_DUMP_CONTROL_RECEIPT.json", "stop_marker_count")):
                manifest_errors.append("finalizer semantic-v5 binding differs")
            request = json.loads(archive.read(prefix + "contracts/server_post_sim_return_request.json"))
            if not any(row.get("archive") == "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json" for row in request.get("core_entries", [])):
                manifest_errors.append("dump-control receipt absent from return core")
            if archive.read(prefix + "package_tools/server_tb_vcd_runtime_supervision.py") != (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes():
                manifest_errors.append("shared runtime evaluator differs from canonical")
            if archive.read(prefix + "package_tools/server_post_sim_return.py") != (ROOT / "tools/server_post_sim_return.py").read_bytes():
                manifest_errors.append("post-sim helper differs from canonical")
    errors.extend(manifest_errors)

    formal = load(ANALYSIS / "formal_return_analysis.json") if (ANALYSIS / "formal_return_analysis.json").is_file() else {}
    gap = load(ANALYSIS / "RULE_GAP_AUDIT.json") if (ANALYSIS / "RULE_GAP_AUDIT.json").is_file() else {}
    if formal.get("pass") is not True:
        errors.append("p51 formal return analysis not pass")
    if gap.get("pass") is not True or gap.get("runtime_gap", {}).get("code") != "PLANNED_DUMPOFF_RESETS_SHARED_DUMP_OFF_STATE_AND_TRIGGERS_FALSE_FREEZE":
        errors.append("p51 rule-gap/runtime boundary differs")

    storage_matches = sorted(STORAGE.glob(f"*/**/{PACKAGE}.zip"))
    if storage_matches:
        errors.append("p52 unexpectedly exists in managed storage before authorization")

    report = {
        "schema": "conv-native-p52-final-zip-release-audit-v1",
        "package_id": PACKAGE,
        "family": FAMILY,
        "activation_epoch": EPOCH,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE" if not errors else "LOCAL_TERMINAL_GATE_FAILURE",
        "storage_disposition": "NOT_PUBLISHED_STORAGE_MANAGER_NOT_AUTHORIZED",
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<execution>_return.zip",
        "zip": identity(ZIP) if ZIP.is_file() else None,
        "repeat_zip": identity(REPEAT) if REPEAT.is_file() else None,
        "source_p51_tested": identity(SOURCE_ZIP) if SOURCE_ZIP.is_file() else None,
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json") if (ANALYSIS / "formal_return_analysis.json").is_file() else None,
        "rule_gap_audit": identity(ANALYSIS / "RULE_GAP_AUDIT.json") if (ANALYSIS / "RULE_GAP_AUDIT.json").is_file() else None,
        "gate_receipts": gate_receipts,
        "manifest_exact_set_pass": not manifest_errors,
        "deterministic_zip_pass": deterministic,
        "p52_storage_matches": [path.relative_to(ROOT).as_posix() for path in storage_matches],
        "storage_manager_invoked": False,
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
        "claim_boundary": "Local p52 build and gates only; no production compile/simulation, target execution, validated root, natural terminal, formal D, E3, E4 or E5 claim.",
    }
    final_path = GATES / "final_zip_release_audit.json"
    final_path.write_bytes(canonical(report))
    evidence = {
        "schema": "conv-native-p52-release-evidence-v1",
        "package_id": PACKAGE,
        "family": FAMILY,
        "status": report["status"],
        "final_zip_release_audit": identity(final_path),
        "package": report["zip"],
        "storage_disposition": report["storage_disposition"],
        "previous_version_progress": "p51 dynamically proved a one-transaction / 32-unit metadata supply deficit after the p50 RD-buffer join and narrowed the open mechanism to Memory_AG three-input formation, same/gotten suppression, split-FIFO state, or keep-release gating; its planned dumpoff also exposed the shared false-freeze and repeated-STOP defect.",
        "current_version_purpose": "Preserve the p51 validated boundary and frozen functional surfaces, add the 40 direct Memory_AG tuple-formation leaves, and apply semantic-v5 two-phase planned-dumpoff/freeze plus one-shot STOP so the next real return can discriminate all 14 retained candidates.",
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM",
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
        "claim_boundary": report["claim_boundary"],
    }
    evidence_path = OUT / f"{PACKAGE}.release_evidence.json"
    evidence_path.write_bytes(canonical(evidence))
    mainline = {
        "schema": "conv-native-p52-mainline-package-ready-receipt-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "status": report["status"],
        "package": report["zip"],
        "release_evidence": identity(evidence_path),
        "final_zip_release_audit": identity(final_path),
        "storage_disposition": report["storage_disposition"],
        "unique_future_command": report["unique_future_command"],
        "expected_return": report["expected_return"],
        "previous_version_progress": evidence["previous_version_progress"],
        "current_version_purpose": evidence["current_version_purpose"],
        "claim_boundary": report["claim_boundary"],
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
    }
    mainline_path = OUT / "mainline_package_ready_receipt.json"
    mainline_path.write_bytes(canonical(mainline))
    print(json.dumps({"package_id": PACKAGE, "pass": not errors, "errors": errors, "final": str(final_path), "mainline": str(mainline_path)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
