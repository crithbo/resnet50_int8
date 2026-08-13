#!/usr/bin/env python3
"""Create the final immutable release receipt for p35c."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p35c_armknown"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_armknown"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
FILES = {
    "build": BUILD / f"{PACKAGE}.build.json",
    "family": BASE / "p35c_family_audit.json",
    "runner": BUILD / f"{PACKAGE}.runner_harness.json",
    "shared": BUILD / f"{PACKAGE}.shared_layout.json",
    "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
    "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    "profile": BASE / "server_package_build_profile_v2.json",
    "build_spec": BASE / "server_package_build_spec_v2.json",
    "p34b_return_analysis": ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_return_analysis/report.json",
    "first_fresh_contract": ROOT / "outputs/p35c_first_fresh_audit_v2/contract.json",
    "first_fresh_validation": ROOT / "outputs/p35c_first_fresh_audit_v2/validation.json",
}
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
RULE_PATHS = (
    ".agents/agent.md", ".agents/plan.md", ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md", ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md", ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md", ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md", "tools/server_post_sim_return.py",
    "tools/validate_server_first_fresh_extra_audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p35c final release receipt")
    if not ZIP.is_file() or not all(path.is_file() for path in FILES.values()):
        raise RuntimeError("p35c final evidence is incomplete")
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}
    scenarios = reports["runner"].get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    live = reports["post_sim"].get("details", {}).get("partial_exit_live_causal_record", {})
    checks = {
        "one_exact_final_zip": reports["build"].get("final_zip_count") == 1 and reports["build"].get("zip_sha256") == sha(ZIP),
        "deterministic_frozen_build": reports["build"].get("deterministic_double_build_tree_equal") is True and reports["build"]["frozen"]["frozen_install_payload_member_count"] == 87 and reports["build"]["frozen"]["frozen_install_payload_byte_equal"] is True and all(reports["build"]["frozen"]["sca_identity_normalized_equal"].values()) and reports["build"]["functional_rtl_modified"] is False,
        "one_prebuild_aggregate": reports["profile"].get("contract_valid") is True and reports["profile"].get("preflight", {}).get("errors") == [] and reports["profile"].get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") == 1,
        "family_audit": reports["family"].get("valid") is True and reports["family"].get("errors") == [],
        "source_bound_generation_and_final_zip": reports["source_bound"].get("pass") is True and reports["source_bound"].get("errors") == [],
        "post_sim_core": reports["post_sim"].get("pass") is True and reports["post_sim"].get("errors") == [],
        "live_causal_required_plugin": live.get("contract_errors") == [] and set(live.get("plugin_results", {})) == {"arm_known_parser"} and live["plugin_results"]["arm_known_parser"].get("executed") is True and live["plugin_results"]["arm_known_parser"].get("pass") is True,
        "runner_six_state": all(scenarios.get(name, {}).get("runner_exit") == code and scenarios.get(name, {}).get("finalizer_reached") is True and scenarios.get(name, {}).get("fixed_result_return_published") is True and scenarios.get(name, {}).get("root_exact_set_unchanged") is True for name, code in expected.items()),
        "shared_runtime_layout": reports["shared"].get("pass") is True and reports["shared"].get("errors") == [],
        "first_fresh_extra_audit": reports["first_fresh_validation"].get("pass") is True and reports["first_fresh_validation"].get("upload_authorized") is True and reports["first_fresh_validation"].get("package_id") == PACKAGE and reports["first_fresh_validation"].get("rule_change_epoch_id") == "20260811-native-live-causal-partial-exit-v1",
        "p34b_formal_analysis": reports["p34b_return_analysis"].get("valid") is True and reports["p34b_return_analysis"].get("status") == "P34B_PARTIAL_RETURN_VALID_PACKAGE_PARSER_FAIL_OPEN_SUCCESSOR_REQUIRED",
    }
    valid = all(checks.values())
    matrix = {
        "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["one_exact_final_zip"]},
        "source_bound_observer_generation": {"applicability": "blocking_applicable", "pass": checks["source_bound_generation_and_final_zip"]},
        "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["family_audit"]},
        "diagnostic_partial_exit_live_causal": {"applicability": "blocking_applicable", "pass": checks["live_causal_required_plugin"]},
        "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runner_six_state"]},
        "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["source_bound_generation_and_final_zip"]},
        "post_sim_return_core": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "return_result_contract": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout"]},
        "first_fresh_extra_audit": {"applicability": "blocking_applicable", "pass": checks["first_fresh_extra_audit"], "epoch_id": "20260811-native-live-causal-partial-exit-v1"},
        "materialized_config": {"applicability": "receipt_reuse", "pass": checks["deterministic_frozen_build"], "scope": "87 payload bytes frozen; SCA identity-only rewrite"},
        "numeric_w3_golden": {"applicability": "record_only", "pass": True, "scope": "frozen; not rerun"},
        "production_compile_sim_return": {"applicability": "dynamic_only", "pass": None},
    }
    result = {
        "schema": "conv-native-four-lane-p35c-armknown-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid, "package_identity": PACKAGE,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False, "checks": checks, "release_gate_matrix": matrix,
        "zip": receipt(ZIP), "audits": {name: receipt(path) for name, path in FILES.items()},
        "rule_receipts": {path: receipt(ROOT / path) for path in RULE_PATHS},
        "failed_intermediate_disposition": {
            "p35": "PREBUILD_ONLY_FAILED_NO_ZIP_PRESERVED",
            "p35b": "PREFINAL_STAGING_FAILED_NO_ZIP_PRESERVED",
            "p35c_final_zip_rebuilt": False,
            "p35c_final_zip_count": 1,
        },
        "expected_server": {"command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02", "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip", "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256", "duplicate_absent_required": True},
        "claim_boundary": "One c0 diagnostic re-running the p34b ARM token split with binary-known live EVENT payloads. No natural terminal, formal 320D, E3/E4/E5 or performance claim.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": result["status"], "output": str(OUTPUT)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
