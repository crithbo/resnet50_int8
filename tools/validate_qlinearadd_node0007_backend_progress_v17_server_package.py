from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_d_buffer_rule_v16_server_package as v16
from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as runner_validator


INSTALL_NAME = "r5_qadd_n7_backend_progress_v17"
SOURCE_NAME = "r5_qadd_n7_dbuf_rule_v16"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = (
    ROOT / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-backend-progress-v17"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
SOURCE_ZIP_SHA256 = "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
INDEX_SHA256 = "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964"
OLD_HEARTBEAT_CYCLES = 262_144
HEARTBEAT_CYCLES = 32_768


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }
    manifest = json.loads(members[f"{root}/TEST_PACKAGE_MANIFEST.json"])
    return members, manifest


def _relative(members: dict[str, bytes], root: str) -> dict[str, bytes]:
    prefix = f"{root}/"
    return {name[len(prefix):]: payload for name, payload in members.items()}


def _payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = _relative(source_members, SOURCE_NAME)
    successor = _relative(successor_members, INSTALL_NAME)
    allowed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "workload/runtime/sca_cfg.json",
        "workload/runtime/sca_cfg_D.json",
    }
    errors: list[str] = []
    if set(source) != set(successor):
        errors.append("package exact-set differs")
    for name in sorted(set(source) & set(successor) - allowed):
        if successor[name] != source[name]:
            errors.append(f"frozen payload differs: {name}")
    for name in (
        "workload/runtime/sca_cfg.json",
        "workload/runtime/sca_cfg_D.json",
    ):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"namespace-only JSON differs semantically: {name}")
    old_runner = source["PREPARE_AND_RUN.sh"]
    new_runner = successor["PREPARE_AND_RUN.sh"].replace(
        INSTALL_NAME.encode(), SOURCE_NAME.encode()
    )
    new_runner = new_runner.replace(
        f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}".encode(),
        f"+RETURN_OBS_HEARTBEAT_CYCLES={OLD_HEARTBEAT_CYCLES}".encode(),
    )
    if new_runner != old_runner:
        errors.append("runner differs outside identity and heartbeat cadence")
    return {
        "valid": not errors,
        "allowed_changed_paths": sorted(allowed),
        "frozen_payload_count": len(set(source) & set(successor) - allowed),
        "errors": errors,
    }


def _heartbeat_contract(manifest: dict[str, Any], runner: str) -> dict[str, Any]:
    contract = manifest.get("backend_progress_logging_contract", {})
    expected_arg = f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}"
    old_arg = f"+RETURN_OBS_HEARTBEAT_CYCLES={OLD_HEARTBEAT_CYCLES}"
    records = set(contract.get("records_per_heartbeat", []))
    required_records = {
        "HEARTBEAT",
        "SG_COUNTS",
        "INTERNAL_STATE",
        "FIRST_REQUEST_CHAIN",
        "FIRST_REQUEST_CLOCK",
    }
    checks = {
        "runner_exact_new_heartbeat": runner.count(expected_arg) == 1,
        "runner_old_heartbeat_absent": old_arg not in runner,
        "manifest_heartbeat_matches": contract.get("heartbeat_cycles")
        == HEARTBEAT_CYCLES,
        "manifest_old_heartbeat_bound": contract.get("old_heartbeat_cycles")
        == OLD_HEARTBEAT_CYCLES,
        "frontend_transaction_logging_not_added": contract.get(
            "frontend_transaction_logging_added"
        )
        is False,
        "required_backend_records_declared": required_records <= records,
        "no_dut_or_timeout_change": all(
            contract.get(name) is False
            for name in (
                "changes_dut_input",
                "changes_ready_or_backpressure",
                "changes_timeout",
                "changes_configuration",
                "changes_workload",
                "changes_golden",
                "changes_functional_rtl",
            )
        ),
    }
    return {"valid": all(checks.values()), "checks": checks}


def _rate_gate_source_checks(successor: dict[str, bytes]) -> dict[str, Any]:
    base_source = successor["tb_probe/native_return_observer.svh"].decode()
    tail_source = successor[
        "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
    ].decode()
    base_gate = (
        "return_obs_active_cycles %" in base_source
        and "return_obs_heartbeat_period) == 0" in base_source
        and 'return_obs_write_summary("HEARTBEAT")' in base_source
        and 'return_obs_write_internal_state("HEARTBEAT")' in base_source
    )
    tail_gate = (
        "return_obs_active_cycles %" in tail_source
        and "return_obs_heartbeat_period) == 0" in tail_source
        and "| FIRST_REQUEST_CHAIN |" in tail_source
        and "| FIRST_REQUEST_CLOCK |" in tail_source
    )
    summary = (
        "| SG_COUNTS |" in base_source
        and "mse4_req0=%0d" in base_source
        and "mse4_wdata0=%0d" in base_source
        and "mse4_outstanding0=%0d" in base_source
        and '"COMP_FINISH"' in base_source
    )
    return {
        "valid": base_gate and tail_gate and summary,
        "base_summary_shared_gate": base_gate,
        "first_request_records_shared_gate": tail_gate,
        "qualified_output_and_completion_summary_present": summary,
    }


def _negative_controls(
    manifest: dict[str, Any], runner: str, successor: dict[str, bytes]
) -> dict[str, Any]:
    cases: dict[str, bool] = {}
    expected = f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}"
    restored = runner.replace(
        expected, f"+RETURN_OBS_HEARTBEAT_CYCLES={OLD_HEARTBEAT_CYCLES}"
    )
    cases["restore_old_heartbeat"] = not _heartbeat_contract(
        manifest, restored
    )["valid"]
    removed = runner.replace(expected, "")
    cases["remove_heartbeat_argument"] = not _heartbeat_contract(
        manifest, removed
    )["valid"]
    mismatched = json.loads(json.dumps(manifest))
    mismatched["backend_progress_logging_contract"]["heartbeat_cycles"] = 65_536
    cases["tamper_manifest_heartbeat"] = not _heartbeat_contract(
        mismatched, runner
    )["valid"]
    changed_members = dict(successor)
    tail_name = "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
    changed_members[tail_name] = changed_members[tail_name].replace(
        b"(return_obs_active_cycles %\n                    return_obs_heartbeat_period) == 0",
        b"1'b1",
    )
    cases["move_first_request_records_outside_rate_gate"] = not (
        _rate_gate_source_checks(changed_members)["valid"]
    )
    return {
        name: {"failed_closed": passed, "exit_code": 1 if passed else 0}
        for name, passed in cases.items()
    }


def _runner_controls() -> dict[str, Any]:
    runner_validator.INSTALL_NAME = INSTALL_NAME
    runner_validator.ZIP_PATH = ZIP_PATH
    runner_validator.SIDECAR_PATH = SIDECAR_PATH
    runner_validator.BUILD_RECEIPT = BUILD_RECEIPT
    runner_validator.EVIDENCE_ROOT = EVIDENCE_ROOT
    runner_validator.REPORT_PATH = REPORT_PATH
    return runner_validator._runner_controls()


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    baseline = v16.validate_final_zip(write_report=False)
    successor_members, manifest = _load(ZIP_PATH, INSTALL_NAME)
    source_members, _ = _load(SOURCE_ZIP, SOURCE_NAME)
    successor = _relative(successor_members, INSTALL_NAME)
    runner = successor["PREPARE_AND_RUN.sh"].decode()
    equivalence = _payload_equivalence(source_members, successor_members)
    heartbeat = _heartbeat_contract(manifest, runner)
    rate_gate = _rate_gate_source_checks(successor)
    negatives = _negative_controls(manifest, runner, successor)
    controls = _runner_controls()
    receipts = manifest["final_zip_rule_self_audit"]["rule_receipts"]
    sidecar_tokens = SIDECAR_PATH.read_text(encoding="ascii").split()
    checks = {
        "source_v16_baseline_self_audit_pass": baseline.get(
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
        )
        is True,
        "source_v16_bound": manifest["source_package"]["sha256"]
        == SOURCE_ZIP_SHA256
        == sha256(SOURCE_ZIP),
        "sidecar_exact": len(sidecar_tokens) == 2
        and sidecar_tokens[0] == sha256(ZIP_PATH)
        and sidecar_tokens[1] == ZIP_PATH.name,
        "current_index_bound": receipts["generation_index"]["sha256"]
        == INDEX_SHA256,
        "current_server_rule_bound": receipts["server_package_rule"]["sha256"]
        == SERVER_RULE_SHA256,
        "current_qadd_rule_bound": receipts["qlinearadd_rule"]["sha256"]
        == QADD_RULE_SHA256,
        "payload_equivalence": equivalence["valid"],
        "heartbeat_contract": heartbeat["valid"],
        "shared_rate_gate_source": rate_gate["valid"],
        "negative_controls_fail_closed": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "runner_positive_control": controls[
            "safe_compile_stub_positive_control"
        ]["passed"],
        "wrong_identity_negative_control": controls[
            "wrong_payload_identity_negative_control"
        ]["passed"],
    }
    errors = [name for name, passed in checks.items() if not passed]
    errors.extend(equivalence["errors"])
    report = {
        "schema": "qlinearadd-node0007-backend-progress-final-zip-self-audit-v1",
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if not errors
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": list(dict.fromkeys(errors)),
        "error_count": len(list(dict.fromkeys(errors))),
        "checks": checks,
        "source_v16_final_zip_audit_pass": baseline.get(
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
        ),
        "payload_equivalence": equivalence,
        "backend_heartbeat_contract": heartbeat,
        "rate_gate_source_checks": rate_gate,
        "negative_controls": negatives,
        "all_required_negative_controls_fail_closed": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "runner_control_flow": controls,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "expected_return": f"{INSTALL_NAME}_return.zip",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_changed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        receipt = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        receipt.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
