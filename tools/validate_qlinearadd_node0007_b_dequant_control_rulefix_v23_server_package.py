from __future__ import annotations

import hashlib
import json
import shlex
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as base
from tools import validate_qlinearadd_node0007_b_dequant_control_v22_server_package as v22
from tools.qlinearadd_node0007_base_observer_hdl_gate_v23 import (
    package_local_hdl_gate,
)


INSTALL_NAME = "r5_qadd_n7_bctrl_v23"
SOURCE_NAME = "r5_qadd_n7_b_dequant_control_v22"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "4a51be0ab59b0ff8c0754de68f11d7f3d1328b6fe012b3945468b787d2b11fd5"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-b-dequant-control-rulefix-v23"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
INDEX_SHA = "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"
SERVER_SHA = "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
QADD_SHA = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_SHA = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
runner_validator = base.runner_validator


def payload_sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = base.relative(source_members, SOURCE_NAME)
    successor = base.relative(successor_members, INSTALL_NAME)
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/qlinearadd_progress_canonical_decision.py",
    }
    errors: list[str] = []
    if set(source) != set(successor):
        errors.append("source/successor file exact-set differs")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")
    if not all(
        successor[name] == source[name]
        for name in source
        if name.endswith((".sv", ".svh", ".v", ".vh", ".bin", ".txt"))
    ):
        errors.append("HDL/bitstream/config/golden payload differs")

    source_runner = source["PREPARE_AND_RUN.sh"]
    successor_runner = successor["PREPARE_AND_RUN.sh"].replace(
        INSTALL_NAME.encode(), SOURCE_NAME.encode()
    )
    expected_runner = source_runner
    for old, new in (
        (
            b"  grep -q '+RETURN_OBS_DEEP' \"$evidence_root/actual_simulator_argv.txt\" && feature_argv=true",
            b"  if [ -s \"$evidence_root/actual_simulator_argv.txt\" ] && grep -q '+RETURN_OBS_DEEP' \"$evidence_root/actual_simulator_argv.txt\"; then feature_argv=true; fi",
        ),
        (
            b"  grep -q '\\[RETURN_OBSERVER\\] enabled for slice' \"$run_root/sim_results/sim.log\" && feature_time0=true",
            b"  if [ -s \"$run_root/sim_results/sim.log\" ] && grep -q '\\[RETURN_OBSERVER\\] enabled for slice' \"$run_root/sim_results/sim.log\"; then feature_time0=true; fi",
        ),
        (
            b"  grep -q '# Native NDP return observer v4' \"$observer_log\" && feature_snapshot=true",
            b"  if [ -s \"$observer_log\" ] && grep -q '# Native NDP return observer v4' \"$observer_log\"; then feature_snapshot=true; fi",
        ),
    ):
        expected_runner = expected_runner.replace(old, new)
    if successor_runner != expected_runner:
        errors.append("runner differs beyond three finalizer guards")

    source_parser = source["package_tools/qlinearadd_progress_canonical_decision.py"]
    expected_parser = source_parser.replace(
        b'    text = observer.read_text(encoding="utf-8", errors="replace")',
        b'    text = (observer.read_text(encoding="utf-8", errors="replace") if observer.is_file() else "")',
    )
    if successor["package_tools/qlinearadd_progress_canonical_decision.py"] != expected_parser:
        errors.append("parser differs beyond missing-observer fail-closed handling")
    return {
        "valid": not errors,
        "errors": errors,
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "exact_hdl_members_byte_frozen": True,
        "numeric_w3_qparams_tail_workload_config_golden_frozen": True,
    }


def runner_controls() -> dict[str, Any]:
    runner_validator.INSTALL_NAME = INSTALL_NAME
    runner_validator.ZIP_PATH = ZIP_PATH
    runner_validator.SIDECAR_PATH = SIDECAR_PATH
    runner_validator.BUILD_RECEIPT = BUILD_RECEIPT
    runner_validator.REPORT_PATH = REPORT_PATH
    required_evidence = {
        "actual_compile_argv.txt",
        "package_preflight.json",
        "installed_preflight.json",
        "host_timing.txt",
        "signal_status.txt",
        "observer_binding.txt",
        "fp32_ingress_feature_receipt.txt",
        "compile_exit_status.txt",
        "simulation_exit_status.txt",
        "canonical_decision_exit_status.txt",
        "CANONICAL_PROGRESS_DECISION.json",
        "SERVER_RESULT_GATE.json",
        "PACKAGE_MANIFEST.json",
        "progress_contract.json",
    }
    with tempfile.TemporaryDirectory(prefix=".q23-pc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = runner_validator._extract(ZIP_PATH, temp / "extract")
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub_argv.txt"
        runner_validator._write_stubs(tools, marker)
        before = runner_validator._directory_records(package)
        result = runner_validator._run_runner(package, server, tools)
        after = runner_validator._directory_records(package)
        evidence = server / f"evidence_{INSTALL_NAME}"
        return_zip = server / f"{INSTALL_NAME}_return.zip"
        return_sidecar = Path(str(return_zip) + ".sha256")
        present_evidence = {
            path.name for path in evidence.iterdir() if path.is_file()
        } if evidence.is_dir() else set()
        return_missing: list[str] = []
        return_manifest_valid = False
        if return_zip.is_file():
            with zipfile.ZipFile(return_zip) as archive:
                name = f"{INSTALL_NAME}_return/RETURN_MANIFEST.json"
                if name in archive.namelist():
                    returned = json.loads(archive.read(name))
                    return_missing = list(returned.get("required_missing", []))
                    return_manifest_valid = (
                        len(return_missing) == 28
                        and all(
                            "matrix_D_linearized_128bit.txt" in item
                            for item in return_missing
                        )
                    )
        positive = {
            "passed": (
                result.returncode == runner_validator.COMPILE_STUB_EXIT
                and marker.is_file()
                and required_evidence <= present_evidence
                and return_zip.is_file()
                and return_sidecar.is_file()
                and return_manifest_valid
                and result.stderr == ""
                and before == after
            ),
            "runner_exit_code": result.returncode,
            "expected_compile_stub_exit_code": runner_validator.COMPILE_STUB_EXIT,
            "compile_stub_reached": marker.is_file(),
            "actual_compile_argv_saved": (
                evidence / "actual_compile_argv.txt"
            ).is_file(),
            "required_finalizer_artifacts_complete": (
                required_evidence <= present_evidence
            ),
            "required_finalizer_artifacts_missing": sorted(
                required_evidence - present_evidence
            ),
            "return_zip_collected": return_zip.is_file(),
            "return_sidecar_collected": return_sidecar.is_file(),
            "return_manifest_missing_only_formal_d_28": return_manifest_valid,
            "return_manifest_required_missing": return_missing,
            "stderr_empty": result.stderr == "",
            "stderr": result.stderr,
            "package_tree_unchanged": before == after,
        }

    with tempfile.TemporaryDirectory(prefix=".q23-nc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = runner_validator._extract(ZIP_PATH, temp / "extract")
        manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["README.md"]["sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub_argv.txt"
        runner_validator._write_stubs(tools, marker)
        result = runner_validator._run_runner(package, server, tools)
        negative = {
            "passed": result.returncode == 5 and not marker.exists(),
            "runner_exit_code": result.returncode,
            "expected_precompile_exit_code": 5,
            "compile_stub_reached": marker.exists(),
            "stderr_tail": result.stderr[-1000:],
        }
    return {
        "safe_compile_stub_positive_control": positive,
        "wrong_payload_identity_negative_control": negative,
        "all_passed": positive["passed"] and negative["passed"],
    }


def validate() -> dict[str, Any]:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_NAME = SOURCE_NAME
    base.ZIP_PATH = ZIP_PATH
    base.SIDECAR_PATH = SIDECAR_PATH
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_ZIP_SHA256 = SOURCE_SHA
    base.BUILD_RECEIPT = BUILD_RECEIPT
    base.EVIDENCE_ROOT = EVIDENCE_ROOT
    base.REPORT_PATH = REPORT_PATH
    base.INDEX_SHA256 = INDEX_SHA
    base.SERVER_RULE_SHA256 = SERVER_SHA
    base.QADD_RULE_SHA256 = QADD_SHA
    base.TAIL_RULE_SHA256 = TAIL_SHA
    base.payload_equivalence = payload_equivalence
    base.observer_contract = v22.observer_contract
    base.source_negative_controls = v22.negative_controls
    base.parser_controls = v22.parser_controls
    base.runner_controls = runner_controls
    base._write_sim_stubs = v22.write_sim_stubs
    report = base.validate_final_zip(write_report=False)

    members, manifest, _ = base.load_zip(ZIP_PATH, INSTALL_NAME)
    files = base.relative(members, INSTALL_NAME)
    hdl_gate = package_local_hdl_gate(files, manifest)
    positive = report["runner_control_flow"]["safe_compile_stub_positive_control"]
    added_checks = {
        "package_local_hdl_gate": hdl_gate["valid"],
        "safe_compile_finalizer_stderr_empty": positive["stderr_empty"],
        "safe_compile_required_finalizer_artifacts_complete": positive[
            "required_finalizer_artifacts_complete"
        ],
        "safe_compile_return_manifest_missing_only_formal_d_28": positive[
            "return_manifest_missing_only_formal_d_28"
        ],
        "safe_exit_and_signal_stderr_empty": all(
            item["stderr_tail"] == ""
            for key, item in report["exit_and_signal_finalizer_controls"].items()
            if key != "all_passed"
        ),
    }
    report["checks"].update(added_checks)
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(report["zip_structure"]["errors"])
    errors.extend(report["manifest_file_errors"])
    errors.extend(report["payload_equivalence"]["errors"])
    if not report["all_required_negative_controls_fail_closed"]:
        errors.append("all_required_negative_controls_fail_closed")
    errors = list(dict.fromkeys(errors))
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-b-dequant-control-rulefix-v23-"
                "final-audit-v1"
            ),
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "package_local_hdl_gate": hdl_gate,
            "source_package_status": "QUARANTINED_FINAL_ZIP_AUDIT_OVERCLAIM",
            "rulefix_scope": {
                "runner_finalizer_only": True,
                "validator_only": True,
                "B_only_control_unchanged": True,
                "functional_rtl_modified": False,
                "numeric_workload_config_golden_unchanged": True,
            },
        }
    )
    return report


def main() -> int:
    try:
        report = validate()
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": base.sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "error_count": report["error_count"],
                "report": str(REPORT_PATH),
            },
            indent=2,
        )
    )
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
