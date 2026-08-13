#!/usr/bin/env python3
"""Create the final release receipt for frozen p32b diagnostic ZIP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p32b_validowner"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p32b_validowner"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
FILES = {
    "build": BUILD / f"{PACKAGE}.build.json",
    "family": BASE / "p32b_family_audit.json",
    "runner": BUILD / f"{PACKAGE}.runner_harness.json",
    "shared": BUILD / f"{PACKAGE}.shared_layout.json",
    "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
    "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    "profile": BASE / "server_package_build_profile_v2.json",
    "build_spec": BASE / "server_package_build_spec_v2.json",
    "p31_return_analysis": ROOT / "outputs/conv_native_four_lane_0ccae916_p31_return_analysis/report.json",
    "prior_first_fresh": ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json",
}
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p32b final release receipt")
    if not ZIP.is_file() or not all(path.is_file() for path in FILES.values()):
        raise RuntimeError("p32b final evidence is incomplete")
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}
    scenarios = reports["runner"].get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    checks = {
        "one_exact_final_zip": reports["build"].get("final_zip_count") == 1 and reports["build"].get("zip_sha256") == sha(ZIP),
        "deterministic_frozen_build": reports["build"].get("deterministic_double_build") is True and reports["build"]["frozen"]["frozen_install_payload_member_count"] == 87 and reports["build"]["frozen"]["frozen_install_payload_byte_equal"] is True and all(reports["build"]["frozen"]["sca_identity_normalized_equal"].values()) and reports["build"]["functional_rtl_modified"] is False,
        "family_audit": reports["family"].get("valid") is True and reports["family"].get("errors") == [],
        "source_bound_generation_and_final_zip": reports["source_bound"].get("pass") is True and reports["source_bound"].get("errors") == [],
        "post_sim_core": reports["post_sim"].get("pass") is True and reports["post_sim"].get("errors") == [],
        "runner_six_state": all(scenarios.get(name, {}).get("runner_exit") == code and scenarios.get(name, {}).get("finalizer_reached") is True and scenarios.get(name, {}).get("fixed_result_return_published") is True and scenarios.get(name, {}).get("root_exact_set_unchanged") is True for name, code in expected.items()),
        "shared_runtime_layout": reports["shared"].get("pass") is True and reports["shared"].get("errors") == [],
        "build_profile_contract": reports["profile"].get("contract_valid") is True and reports["profile"].get("preflight", {}).get("errors") == [],
        "same_epoch_prior_first_fresh": reports["prior_first_fresh"].get("pass") is True and reports["prior_first_fresh"].get("upload_authorized") is True and reports["prior_first_fresh"].get("package_id") == "r5_n4_0cc_p31_postclear" and reports["profile"].get("rule_change_epoch", {}).get("first_fresh_after_change") is False,
        "p31_formal_analysis": reports["p31_return_analysis"].get("valid") is True,
    }
    valid = all(checks.values())
    matrix = {
        "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["one_exact_final_zip"]},
        "source_bound_observer_generation": {"applicability": "blocking_applicable", "pass": checks["source_bound_generation_and_final_zip"]},
        "target_epoch_correlator": {"applicability": "blocking_applicable", "pass": checks["family_audit"]},
        "diagnostic_predicate_trace": {"applicability": "blocking_applicable", "pass": checks["family_audit"]},
        "diagnostic_multiclass_edge_no_loss": {"applicability": "blocking_applicable", "pass": checks["family_audit"]},
        "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runner_six_state"]},
        "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["source_bound_generation_and_final_zip"]},
        "post_sim_return_core": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "return_result_contract": {"applicability": "blocking_applicable", "pass": checks["post_sim_core"]},
        "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout"]},
        "first_fresh_extra_audit": {"applicability": "receipt_reuse", "pass": checks["same_epoch_prior_first_fresh"], "epoch_id": "20260810-first-fresh-extra-audit-v1", "prior_package_id": "r5_n4_0cc_p31_postclear"},
        "materialized_config": {"applicability": "receipt_reuse", "pass": checks["deterministic_frozen_build"], "scope": "87 payload bytes frozen; SCA identity-only rewrite"},
        "numeric_w3_golden": {"applicability": "record_only", "pass": True, "scope": "frozen; not rerun"},
        "production_compile_sim_return": {"applicability": "dynamic_only", "pass": None},
        "intermediate_profile_v1_escape": {"applicability": "record_only", "pass": True, "scope": "three receipt_reuse_candidates were strings rather than objects; exact ZIP and all runner/layout/final-ZIP receipts were unchanged"},
    }
    result = {
        "schema": "conv-native-four-lane-p32b-validowner-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD", "valid": valid,
        "package_identity": PACKAGE, "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "candidate_release": False, "checks": checks, "release_gate_matrix": matrix,
        "zip": receipt(ZIP), "audits": {name: receipt(path) for name, path in FILES.items()},
        "failed_intermediate_disposition": {
            "p32_zip": "UNRELEASED_SUPERSEDED_PREAUDIT_IDENTITY_RETAINED_NOT_REBUILT",
            "p32b_profile_v1": "RECORD_ONLY_BUILD_SPEC_SHAPE_ERROR_CONTENT_NEUTRAL_V2_REVALIDATION",
            "exact_p32b_zip_rebuilt": False, "p32b_identity_changed_after_zip": False,
        },
        "expected_server": {"command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02", "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip", "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256", "duplicate_absent_required": True},
        "claim_boundary": "One c0 diagnostic correlating exact target Buffer5 f0-clear to its immediate post-state and final row2 block. No natural terminal, formal 320D, E3/E4/E5 or performance claim.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": result["status"], "output": str(OUTPUT)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
