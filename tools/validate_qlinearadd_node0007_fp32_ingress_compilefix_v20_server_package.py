from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as base


INSTALL_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
SOURCE_NAME = "r5_qadd_n7_fp32_ingress_diag_v19"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-ingress-compilefix-v20"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"


def payload_sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = base.relative(source_members, SOURCE_NAME)
    successor = base.relative(successor_members, INSTALL_NAME)
    added = {"tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"}
    allowed_changed = {
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "tb_probe/native_return_observer.svh",
    }
    errors: list[str] = []
    if set(successor) - set(source) != added:
        errors.append("added-file exact-set differs")
    if set(source) - set(successor):
        errors.append("source file removed")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")
    v19_tail = "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    return {
        "valid": not errors,
        "errors": errors,
        "added_paths": sorted(added),
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "v19_tail_byte_identical": successor[v19_tail] == source[v19_tail],
        "numeric_workload_config_golden_unchanged": not errors,
    }


def observer_contract(manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    shim = files["tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"].decode()
    tail = files["tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"].decode()
    parser_payload = files["package_tools/qlinearadd_progress_canonical_decision.py"]
    allow_targets = {item["target_path"] for item in manifest["return_allowlist"]}
    declaration = (
        "return_obs_ga_operand_capture_mon;" in shim
        and "[`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]" in shim
    )
    checks = {
        "package_local_incdir": "+incdir+$package_root/tb_probe" in runner,
        "enable_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner,
        "native_includes_shim_once": native.count(
            '`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"'
        ) == 1,
        "shim_declares_consumed_identifier": declaration,
        "shim_binds_physical_ga_col0": (
            ".GA_COL_PE[0].GA_PE" in shim and "[qadd_v20_row][0]" in shim
        ),
        "shim_binds_physical_ga_col2": (
            ".GA_COL_PE[2].GA_PE" in shim and "[qadd_v20_row][1]" in shim
        ),
        "qualified_leaf_is_inbuffer_enable": shim.count("ga_pe_inbuffer_enable") == 2,
        "shim_includes_unchanged_v19_tail": shim.count(
            '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'
        ) == 1,
        "v19_tail_consumes_declared_identifier": tail.count(
            "return_obs_ga_operand_capture_mon"
        ) >= 4,
        "feature_plusarg_actual_argv": runner.count("+QADD_FP32_INGRESS_OBSERVER") >= 2,
        "time0_marker_source": "QADD_FP32_INGRESS_OBSERVER_V19_TIME0" in tail,
        "feature_receipt_finalizer": "fp32_ingress_feature_receipt.txt" in runner,
        "feature_receipt_allowlisted": (
            "evidence/fp32_ingress_feature_receipt.txt" in allow_targets
        ),
        "observer_log_allowlisted": "runs/return_observer.log" in allow_targets,
        "qualified_source_clock": "always @(posedge u_NDP_Top_new.clk_sg)" in tail,
        "surviving_snapshot_clock": "always @(posedge u_NDP_Top_new.clk_db)" in tail,
        "mse0_mse1_buffer0_buffer2_ga_chain": all(
            token in tail
            for token in (
                "MSE_INST[0]",
                "MSE_INST[1]",
                "qadd_ingress_pair * 2",
                "qadd_ingress_ga_capture[0]",
                "qadd_ingress_ga_capture[1]",
                "qadd_ingress_ga_consumer_accept",
                "qadd_ingress_ga_first_output",
            )
        ),
        "parser_hash_bound": (
            manifest["canonical_decision_contract"]["parser_sha256"]
            == payload_sha(parser_payload)
        ),
        "ordered_stage_scope": (
            manifest["canonical_decision_contract"]["ordered_final_stage_scope"] is True
        ),
        "trap_safe_exit_and_signals": all(
            token in runner
            for token in (
                "trap 'finalize $?' EXIT",
                "trap 'signal_name=HUP;",
                "trap 'signal_name=INT;",
                "trap 'signal_name=TERM;",
                'final="$original"',
                'exit "$final"',
            )
        ),
        "no_timeout_extension": "12h" in runner,
    }
    return {"valid": all(checks.values()), "checks": checks}


def negative_controls(
    manifest: dict[str, Any], files: dict[str, bytes]
) -> dict[str, dict[str, Any]]:
    cases = {
        "delete_source_include": (
            "tb_probe/native_return_observer.svh",
            b'`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"',
        ),
        "delete_incdir": ("PREPARE_AND_RUN.sh", b"+incdir+$package_root/tb_probe"),
        "delete_macro": ("PREPARE_AND_RUN.sh", b"+define+NATIVE_RETURN_OBSERVER_ENABLE"),
        "delete_feature_plusarg": ("PREPARE_AND_RUN.sh", b"+QADD_FP32_INGRESS_OBSERVER"),
        "delete_time0_marker": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
            b"QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
        ),
        "delete_return_receipt": ("PREPARE_AND_RUN.sh", b"fp32_ingress_feature_receipt.txt"),
        "delete_stage_event": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
            b"qadd_ingress_ga_consumer_accept",
        ),
        "delete_monitor_declaration": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
            b"return_obs_ga_operand_capture_mon;",
        ),
        "delete_ga_col0_binding": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
            b".GA_COL_PE[0].GA_PE",
        ),
        "delete_ga_col2_binding": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
            b".GA_COL_PE[2].GA_PE",
        ),
    }
    result = {}
    for name, (path, needle) in cases.items():
        mutated = dict(files)
        mutated[path] = mutated[path].replace(needle, b"")
        failed = not observer_contract(manifest, mutated)["valid"]
        result[name] = {"failed_closed": failed, "exit_code": 1 if failed else 0}
    return result


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
    base.payload_equivalence = payload_equivalence
    base.observer_contract = observer_contract
    base.source_negative_controls = negative_controls
    report = base.validate_final_zip(write_report=False)
    report["schema"] = "qlinearadd-node0007-fp32-ingress-compilefix-v20-final-audit-v1"
    report["source_package_status"] = "QUARANTINED_OBSERVER_COMPILE_IDENTIFIER_UNDECLARED"
    report["compilefix_scope"] = {
        "package_local_observer_only": True,
        "functional_fix": False,
        "functional_rtl_modified": False,
        "configuration_changed": False,
        "old_compile_failure_closed_locally": report["observer_contract"]["valid"],
    }
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
    print(json.dumps({
        "status": report["status"],
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
        "error_count": report["error_count"],
        "report": str(REPORT_PATH),
    }, indent=2))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
