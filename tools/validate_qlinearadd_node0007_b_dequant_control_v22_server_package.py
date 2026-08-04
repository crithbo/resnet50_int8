from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as base
from tools.validate_qlinearadd_node0007_b_dequant_isolated_v21_server_package import (
    INDEX_SHA,
    QADD_SHA,
    SERVER_SHA,
    TAIL_SHA,
    payload_sha,
)

BASE_WRITE_SIM_STUBS = base._write_sim_stubs


INSTALL_NAME = "r5_qadd_n7_b_dequant_control_v22"
SOURCE_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-b-dequant-control-v22"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"


def payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = base.relative(source_members, SOURCE_NAME)
    successor = base.relative(successor_members, INSTALL_NAME)
    removed = {
        "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
        "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
    }
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "diagnostics/progress_contract.json",
        "package_tools/qlinearadd_node0007_server_runtime.py",
        "package_tools/qlinearadd_progress_canonical_decision.py",
        "tb_probe/native_return_observer.svh",
        "workload/runtime/sca_cfg.json",
    }
    errors: list[str] = []
    if set(source) - set(successor) != removed:
        errors.append("removed observer-regression payload exact-set differs")
    if set(successor) - set(source):
        errors.append("unexpected payload added")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")
    native = successor["tb_probe/native_return_observer.svh"].decode()
    if "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh" in native:
        errors.append("v20 FP32 observer include remains")
    source_sca = json.loads(source["workload/runtime/sca_cfg.json"])
    successor_sca = json.loads(successor["workload/runtime/sca_cfg.json"])
    normalized_sca = json.loads(json.dumps(successor_sca).replace(INSTALL_NAME, SOURCE_NAME))
    source_sca["Repeat_Num"] = 1
    source_sca["Exec_Length"] = 29
    source_sca["ExecutionPlan"]["path"] = (
        f"install/cfg_pkg/{SOURCE_NAME}/install/execplan_op_b_dequant.txt"
    )
    if normalized_sca != source_sca:
        errors.append("SCA differs beyond B-only execution selection")
    return {
        "valid": not errors,
        "errors": errors,
        "removed_paths": sorted(removed),
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "config_bitstream_golden_byte_frozen": all(
            successor[name] == source[name]
            for name in successor
            if name.endswith((".bin", ".txt"))
        ),
    }


def observer_contract(manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    sca = json.loads(files["workload/runtime/sca_cfg.json"])
    contract = json.loads(files["diagnostics/progress_contract.json"])
    allow_targets = {item["target_path"] for item in manifest["return_allowlist"]}
    parser_payload = files["package_tools/qlinearadd_progress_canonical_decision.py"]
    checks = {
        "package_local_incdir": "+incdir+$package_root/tb_probe" in runner,
        "enable_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner,
        "base_observer_present": "# Native NDP return observer v4" in native,
        "v20_fp32_tail_absent": (
            "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh" not in native
            and "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"
            not in files
            and "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
            not in files
        ),
        "base_feature_actual_argv": (
            "+RETURN_OBSERVER" in runner
            and "+RETURN_OBS_DEEP" in runner
            and "+QADD_FP32_INGRESS_OBSERVER" not in runner
        ),
        "time0_marker_source": "[%0t] [RETURN_OBSERVER] enabled for slice %0d" in native,
        "feature_receipt_finalizer": (
            "feature=B_DEQUANT_BASE_OBSERVER_CONTROL" in runner
        ),
        "feature_receipt_allowlisted": (
            "evidence/fp32_ingress_feature_receipt.txt" in allow_targets
        ),
        "observer_log_allowlisted": "runs/return_observer.log" in allow_targets,
        "heartbeat_16384": (
            "+RETURN_OBS_HEARTBEAT_CYCLES=16384" in runner
            and contract["heartbeat_cycles"] == 16384
        ),
        "single_b_stage_sca": (
            sca["Repeat_Num"] == 1
            and sca["Exec_Length"] == 29
            and sca["ExecutionPlan"]["path"].endswith(
                "/install/execplan_op_b_dequant.txt"
            )
        ),
        "parser_hash_bound": (
            manifest["canonical_decision_contract"]["parser_sha256"]
            == payload_sha(parser_payload)
        ),
        "ordered_one_stage_scope": (
            manifest["canonical_decision_contract"]["ordered_final_stage_scope"]
            is True
            and manifest["canonical_decision_contract"]["expected_stage_count"] == 1
        ),
        "trap_safe_finalizer": all(
            token in runner
            for token in (
                "trap 'finalize $?' EXIT",
                "trap 'signal_name=INT;",
                "trap 'signal_name=TERM;",
                'exit "$final"',
            )
        ),
        "runtime_feature_four_way": all(
            token in runner
            for token in (
                "feature_argv=true",
                "feature_time0=true",
                "feature_snapshot=true",
                "fp32_ingress_feature_receipt.txt",
            )
        ),
    }
    return {"valid": all(checks.values()), "checks": checks}


def negative_controls(
    manifest: dict[str, Any], files: dict[str, bytes]
) -> dict[str, dict[str, Any]]:
    cases = {
        "delete_incdir": ("PREPARE_AND_RUN.sh", b"+incdir+$package_root/tb_probe"),
        "delete_macro": ("PREPARE_AND_RUN.sh", b"+define+NATIVE_RETURN_OBSERVER_ENABLE"),
        "delete_feature_plusarg": ("PREPARE_AND_RUN.sh", b"+RETURN_OBS_DEEP"),
        "delete_time0_marker": (
            "tb_probe/native_return_observer.svh",
            b"[%0t] [RETURN_OBSERVER] enabled for slice %0d",
        ),
        "delete_return_receipt": (
            "PREPARE_AND_RUN.sh",
            b"fp32_ingress_feature_receipt.txt",
        ),
        "delete_b_execplan_selection": (
            "workload/runtime/sca_cfg.json",
            b"execplan_op_b_dequant.txt",
        ),
    }
    result = {}
    for name, (path, needle) in cases.items():
        mutated = dict(files)
        mutated[path] = mutated[path].replace(needle, b"")
        failed = not observer_contract(manifest, mutated)["valid"]
        result[name] = {"failed_closed": failed, "exit_code": 1 if failed else 0}
    return result


def parser_controls() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "qadd_b_control_v22",
        ROOT / "tools/qlinearadd_node0007_b_dequant_control_canonical_v22.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = "# Native NDP return observer v4\n"

    def heartbeat(cycles: int, value: int) -> str:
        return (
            f"{cycles} | HEARTBEAT | slice=0 active_cycles={cycles} "
            f"gexec=1 gconfig=1 req={value} rdata={value} wdata=0 "
            "buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0\n"
        )

    with tempfile.TemporaryDirectory(prefix="qadd-b-control-v22-") as raw:
        root = Path(raw)
        cfg = root / "cfg.json"
        cfg.write_text(
            json.dumps({"stall_window_cycles": 1_048_576}),
            encoding="utf-8",
        )

        def run(text: str) -> dict[str, Any]:
            log = root / "observer.log"
            log.write_text(text, encoding="utf-8")
            return module.decide(log, cfg)

        completed = run(
            marker
            + "1 | EXEC_START | slice=0 active_cycles=0\n"
            + heartbeat(16384, 1)
            + "32768 | COMP_FINISH | slice=0 active_cycles=32768\n"
        )
        progress = run(
            marker
            + "1 | EXEC_START | slice=0 active_cycles=0\n"
            + heartbeat(16384, 1)
            + heartbeat(32768, 2)
        )
        missing_marker = run(
            "1 | EXEC_START | slice=0 active_cycles=0\n" + heartbeat(16384, 1)
        )
        two_stage = run(
            marker
            + "1 | EXEC_START | slice=0 active_cycles=0\n"
            + "2 | EXEC_START | slice=0 active_cycles=0\n"
        )
    checks = {
        "completion_requires_comp_finish": (
            completed["decision"] == "B_DEQUANT_CONTROL_COMPLETED"
        ),
        "progress_is_not_terminal": (
            progress["decision"] == "B_DEQUANT_CONTROL_PROGRESS_NOT_TERMINAL"
        ),
        "missing_marker_fails_closed": (
            missing_marker["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
        "multiple_stage_fails_closed": (
            two_stage["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "negative_controls": {
            key: {"failed_closed": value, "exit_code": 1 if value else 0}
            for key, value in checks.items()
            if "fails_closed" in key
        },
    }


def write_sim_stubs(
    tools: Path, marker: Path, *, wait_for_signal: bool
) -> None:
    BASE_WRITE_SIM_STUBS(tools, marker, wait_for_signal=wait_for_signal)
    template = tools / "simv_template"
    text = template.read_text(encoding="utf-8")
    text = text.replace(
        "# QADD_FP32_INGRESS_OBSERVER_V19_TIME0 enabled=1 "
        "source_clock=clk_sg snapshot_clock=clk_db",
        "[0] [RETURN_OBSERVER] enabled for slice 0",
    )
    template.write_text(text, encoding="utf-8", newline="\n")


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
    base.observer_contract = observer_contract
    base.source_negative_controls = negative_controls
    base.parser_controls = parser_controls
    base._write_sim_stubs = write_sim_stubs
    report = base.validate_final_zip(write_report=False)
    report["schema"] = "qlinearadd-node0007-b-dequant-control-v22-final-audit-v1"
    report["source_package_status"] = "QUARANTINED_DYNAMIC_ZERO_DELAY_LOOP"
    report["observer_regression_control"] = {
        "v20_fp32_tail_removed": True,
        "v20_ga_capture_shim_removed": True,
        "v18_base_observer_retained": True,
        "functional_fix": False,
        "full_chain_required": True,
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
