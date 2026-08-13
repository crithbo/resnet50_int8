#!/usr/bin/env python3
"""Finalize the immutable p38 MSE4 join diagnostic after exact-ZIP gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p38_mse4join"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
PRIOR_PASS_SHA = "7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c"
FILES = {
    "build": BUILD / f"{PACKAGE}.build.json",
    "family": BASE / "p38_family_audit.json",
    "runner": BUILD / f"{PACKAGE}.runner_harness.json",
    "shared": BUILD / f"{PACKAGE}.shared_layout.json",
    "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
    "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    "profile": BASE / "server_package_build_profile_v2.json",
    "build_spec": BASE / "server_package_build_spec_v2.json",
    "p37b_return_analysis": ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_return_analysis/report.json",
    "prior_first_fresh": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json",
}
RULE_PATHS = (
    ".agents/agent.md", ".agents/plan.md", ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md", ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md", ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md", ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md", "tools/server_post_sim_return.py",
    "tools/generate_server_source_bound_observer.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p38 final audit")
    if not ZIP.is_file() or not all(path.is_file() for path in FILES.values()):
        raise RuntimeError("p38 final evidence is incomplete")
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}
    scenarios = reports["runner"].get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    live = reports["post_sim"].get("details", {}).get("partial_exit_live_causal_record", {})
    semantics = reports["source_bound"].get("semantic_controls", {})
    fingerprint = reports["source_bound"].get("diagnostic_semantics_sha256")
    plugin_results = live.get("plugin_results", {})
    checks = {
        "one_exact_final_zip": reports["build"].get("final_zip_count") == 1 and reports["build"].get("zip_sha256") == sha(ZIP),
        "deterministic_frozen_build": reports["build"].get("deterministic_double_build_tree_equal") is True and reports["build"]["frozen"]["frozen_install_payload_member_count"] == 87 and reports["build"]["frozen"]["frozen_install_payload_byte_equal"] is True and all(reports["build"]["frozen"]["sca_identity_normalized_equal"].values()) and reports["build"]["functional_rtl_modified"] is False,
        "one_prebuild_aggregate": reports["profile"].get("contract_valid") is True and reports["profile"].get("preflight", {}).get("errors") == [] and reports["profile"].get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") == 1,
        "same_epoch_prior_pass": reports["build"].get("first_fresh_after_change") is False and sha(FILES["prior_first_fresh"]) == PRIOR_PASS_SHA,
        "family_audit": reports["family"].get("valid") is True and reports["family"].get("errors") == [],
        "source_bound_v2": reports["source_bound"].get("pass") is True and reports["source_bound"].get("errors") == [] and reports["source_bound"].get("schema") == "server-source-bound-final-zip-validation-v2",
        "semantic_controls": semantics.get("pass") is True and semantics.get("negative_count", 0) >= 8 and {"serialized Conv v80 wrong-instance cross-aggregation", "native Conv p34b unknown X/Z payload parsed as numeric sentinel"} <= set(semantics.get("historical_regressions", [])) and isinstance(fingerprint, str),
        "post_sim_core": reports["post_sim"].get("pass") is True and reports["post_sim"].get("errors") == [],
        "live_causal_required_plugins": live.get("contract_errors") == [] and set(plugin_results) == {"arm_known_parser", "sa_epoch_parser", "mse4_join_parser"} and all(row.get("executed") is True and row.get("pass") is True for row in plugin_results.values()),
        "runner_six_state": all(scenarios.get(name, {}).get("runner_exit") == code and scenarios.get(name, {}).get("finalizer_reached") is True and scenarios.get(name, {}).get("fixed_result_return_published") is True and scenarios.get(name, {}).get("root_exact_set_unchanged") is True for name, code in expected.items()),
        "shared_runtime_layout": reports["shared"].get("pass") is True and reports["shared"].get("errors") == [],
        "p37b_formal_analysis": reports["p37b_return_analysis"].get("valid") is True and reports["p37b_return_analysis"].get("status") == "P37B_PARTIAL_RETURN_VALID_DISTINCT_SA_BEATS_PROVEN_WRITE_DESCRIPTOR_BOUNDARY_SUCCESSOR_REQUIRED",
    }
    valid = all(checks.values())
    matrix = {
        "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["one_exact_final_zip"]},
        "source_bound_observer_generation": {"applicability": "blocking_applicable", "pass": checks["source_bound_v2"]},
        "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["semantic_controls"], "fingerprint_sha256": fingerprint, "disposition": "SAME_EPOCH_TYPED_V2_AUDITED"},
        "diagnostic_partial_exit_live_causal": {"applicability": "blocking_applicable", "pass": checks["live_causal_required_plugins"]},
        "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runner_six_state"]},
        "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["source_bound_v2"]},
        "post_sim_return_core": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "return_result_contract": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout"]},
        "first_fresh_extra_audit": {"applicability": "receipt_reuse", "pass": checks["same_epoch_prior_pass"], "epoch_id": EPOCH, "prior_pass_sha256": PRIOR_PASS_SHA},
        "materialized_config": {"applicability": "receipt_reuse", "pass": checks["deterministic_frozen_build"], "scope": "87 payload bytes frozen; SCA identity-only rewrite"},
        "numeric_w3_golden": {"applicability": "record_only", "pass": True, "scope": "frozen; not rerun"},
        "production_compile_sim_return": {"applicability": "dynamic_only", "pass": None},
    }
    result = {
        "schema": "conv-native-four-lane-p38-mse4join-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "package_identity": PACKAGE,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False,
        "checks": checks,
        "release_gate_matrix": matrix,
        "zip": receipt(ZIP),
        "audits": {name: receipt(path) for name, path in FILES.items()},
        "rule_receipts": {path: receipt(ROOT / path) for path in RULE_PATHS},
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256",
            "duplicate_absent_required": True,
        },
        "claim_boundary": "One c0 diagnostic joining exact MSE4 memory-address/descriptor/Buffer5-data/wdata-output/slice-finish accepted events after p37b proved distinct SA beats. No natural terminal, formal 320D, E3/E4/E5 or measured performance claim.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": result["status"], "output": str(OUTPUT), "zip_sha256": sha(ZIP)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
