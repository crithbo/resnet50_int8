from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as base


INSTALL_NAME = "r5_qadd_n7_b_dequant_isolated_v21"
SOURCE_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-b-dequant-isolated-v21"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
INDEX_SHA = "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"
SERVER_SHA = "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
QADD_SHA = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_SHA = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"


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
        "diagnostics/progress_contract.json",
        "package_tools/qlinearadd_node0007_server_runtime.py",
        "package_tools/qlinearadd_progress_canonical_decision.py",
        "workload/runtime/sca_cfg.json",
    }
    errors: list[str] = []
    if set(source) != set(successor):
        errors.append("successor/source payload exact-set differs")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")

    source_sca = json.loads(source["workload/runtime/sca_cfg.json"])
    successor_sca = json.loads(successor["workload/runtime/sca_cfg.json"])
    normalized_sca = json.loads(json.dumps(successor_sca).replace(INSTALL_NAME, SOURCE_NAME))
    expected_sca = json.loads(json.dumps(source_sca))
    expected_sca["Repeat_Num"] = 1
    expected_sca["Exec_Length"] = 29
    expected_sca["ExecutionPlan"]["path"] = (
        f"install/cfg_pkg/{SOURCE_NAME}/install/execplan_op_b_dequant.txt"
    )
    if normalized_sca != expected_sca:
        errors.append("SCA differs beyond isolated B exec selection")

    source_runtime = source["package_tools/qlinearadd_node0007_server_runtime.py"]
    successor_runtime = successor[
        "package_tools/qlinearadd_node0007_server_runtime.py"
    ].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
    expected_runtime = source_runtime.replace(
        b'if sca.get("Repeat_Num") != 6 or len(sca_d) != 28:',
        b'if sca.get("Repeat_Num") != 1 or len(sca_d) != 28:',
    ).replace(
        b'raise RuntimeGateError("six-stage or 28-readback contract differs")',
        b'raise RuntimeGateError("isolated-one-stage or 28-readback contract differs")',
    )
    if successor_runtime != expected_runtime:
        errors.append("package runtime differs beyond one-stage preflight")

    source_runner = source["PREPARE_AND_RUN.sh"]
    successor_runner = successor["PREPARE_AND_RUN.sh"].replace(
        INSTALL_NAME.encode(), SOURCE_NAME.encode()
    )
    expected_runner = source_runner.replace(
        b"+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        b"+RETURN_OBS_HEARTBEAT_CYCLES=16384",
    ).replace(b"30s 12h", b"30s 2h")
    if successor_runner != expected_runner:
        errors.append("runner differs beyond cadence/timeout/namespace")

    return {
        "valid": not errors,
        "errors": errors,
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "all_hdl_members_byte_frozen": all(
            successor[name] == source[name]
            for name in source
            if name.endswith((".sv", ".svh", ".v"))
        ),
        "all_bitstreams_configs_golden_byte_frozen": all(
            successor[name] == source[name]
            for name in source
            if name.endswith((".bin", ".txt"))
            and name != "workload/runtime/install/execplan.txt"
        ),
    }


def observer_contract(manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    tail = files[
        "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    ].decode()
    sca = json.loads(files["workload/runtime/sca_cfg.json"])
    contract = json.loads(files["diagnostics/progress_contract.json"])
    parser_payload = files["package_tools/qlinearadd_progress_canonical_decision.py"]
    allow_targets = {item["target_path"] for item in manifest["return_allowlist"]}
    checks = {
        "package_local_incdir": "+incdir+$package_root/tb_probe" in runner,
        "enable_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner,
        "native_includes_compilefix_and_tail": (
            native.count(
                '`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"'
            )
            == 1
            and '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'
            in files["tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"].decode()
        ),
        "feature_plusarg_actual_argv": runner.count(
            "+QADD_FP32_INGRESS_OBSERVER"
        )
        >= 2,
        "time0_marker_source": "QADD_FP32_INGRESS_OBSERVER_V19_TIME0" in tail,
        "feature_receipt_finalizer": "fp32_ingress_feature_receipt.txt" in runner,
        "feature_receipt_allowlisted": (
            "evidence/fp32_ingress_feature_receipt.txt" in allow_targets
        ),
        "observer_log_allowlisted": "runs/return_observer.log" in allow_targets,
        "qualified_source_clock": "always @(posedge u_NDP_Top_new.clk_sg)" in tail,
        "surviving_snapshot_clock": "always @(posedge u_NDP_Top_new.clk_db)" in tail,
        "heartbeat_16384_actual_argv": (
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
        "original_b_input_and_hardware_scratch": (
            contract["split_execution"]["host_precomputed_internal_tensor"] is False
            and contract["split_execution"]["input"]
            == "original B edge payload already present in frozen workload"
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
        "two_hour_isolated_timeout": runner.count("30s 2h") == 2,
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
        "delete_feature_plusarg": (
            "PREPARE_AND_RUN.sh",
            b"+QADD_FP32_INGRESS_OBSERVER",
        ),
        "delete_time0_marker": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
            b"QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
        ),
        "delete_return_receipt": (
            "PREPARE_AND_RUN.sh",
            b"fp32_ingress_feature_receipt.txt",
        ),
        "delete_qualified_update": (
            "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
            b"qadd_ingress_mse_req[qadd_ingress_mse]++;",
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
        "qadd_b_v21",
        ROOT / "tools/qlinearadd_node0007_b_dequant_canonical_v21.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = (
        "# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1 "
        "source_clock=clk_sg snapshot_clock=clk_db level_is_progress=0\n"
    )

    def line(cycles: int, value: int, stage: int = 1) -> str:
        fields = {
            "slice": 0,
            "stage_seq": stage,
            "snapshot_cycles": cycles,
            "mse0_req": value,
            "mse1_req": 0,
            "mse0_rdata": value,
            "mse1_rdata": 0,
            "mse0_buf": value,
            "mse1_buf": 0,
            "buf0_wr": value,
            "buf2_wr": 0,
            "buf0_arm_req": value,
            "buf2_arm_req": 0,
            "buf0_array": value,
            "buf2_array": 0,
            "ga0_capture": value,
            "ga1_capture": 0,
            "ga_pair": 0,
            "ga_accept": value,
            "ga_output": value,
            "buf_valid": 1,
            "buf_arm_ready": 1,
        }
        return (
            f"{cycles} | QADD_FP32_INGRESS | "
            + " ".join(f"{key}={value}" for key, value in fields.items())
            + "\n"
        )

    with tempfile.TemporaryDirectory(prefix="qadd-b-v21-parser-") as raw:
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

        completed = run(marker + "1 | EXEC_START | x\n" + line(0, 1) + "3 | COMP_FINISH | x\n")
        progress = run(marker + "1 | EXEC_START | x\n" + line(0, 1) + line(16384, 2))
        missing_marker = run("1 | EXEC_START | x\n" + line(0, 1))
        wrong_stage = run(marker + "1 | EXEC_START | x\n" + line(0, 1, stage=2))
        no_event = run(marker + "1 | EXEC_START | x\n")
    checks = {
        "completion_requires_same_stage_comp_finish": (
            completed["decision"] == "B_DEQUANT_SEGMENT_COMPLETED"
        ),
        "qualified_progress_not_terminal": (
            progress["decision"] == "B_DEQUANT_QUALIFIED_PROGRESS_NOT_TERMINAL"
        ),
        "missing_marker_fails_closed": (
            missing_marker["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
        "wrong_stage_fails_closed": (
            wrong_stage["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
        "no_qualified_event_fails_closed": (
            no_event["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
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
    report = base.validate_final_zip(write_report=False)
    report["schema"] = "qlinearadd-node0007-b-dequant-isolated-v21-final-audit-v1"
    report["source_package_status"] = "QUARANTINED_DYNAMIC_ZERO_DELAY_LOOP"
    report["split_execution_scope"] = {
        "stage": "op_b_dequant",
        "diagnostic_only": True,
        "functional_fix": False,
        "host_precomputed_internal_tensor": False,
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
