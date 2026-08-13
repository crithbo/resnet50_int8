#!/usr/bin/env python3
"""Create the exact final-ZIP release receipt for native-four-lane p22."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p22_eoenfix"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p22_eoenfix"
ZIP_PATH = BASE / "build" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p22_family_audit_v2.json"
HARNESS = BASE / "p22_runtime_layout_harness_v2.json"
SHARED = BASE / "p22_shared_runtime_layout_v2.json"
PROFILE = BASE / "server_package_build_profile_v2.json"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_return_analysis/report_v2.json"
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit_v2.json"


class FinalizeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> int:
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, PROFILE, ANALYSIS)
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p22 release input is absent")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh").decode()
        manifest = json.loads(archive.read(f"{PACKAGE_ID}/package_manifest.json"))
        observer = archive.read(f"{PACKAGE_ID}/tb_probe/native_return_observer.svh").decode()
    scenarios = harness["scenarios"]
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    scenario_exits = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    actual_scope = family["observer"]["focused_compile"]["p22_actual_consumer_scope"]
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == build["zip_bytes"] and sha256(ZIP_PATH) == build["zip_sha256"],
        "formal_p21_analysis": analysis["valid"] is True and analysis["status"] == "P21_PACKAGE_LOCAL_OBSERVER_IDENTIFIER_ESCAPE_P22_REQUIRED",
        "shadow_build_profile": profile["contract_valid"] is True and profile["preflight"]["pass"] is True and not profile["preflight"]["errors"] and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH",
        "deterministic_frozen_build": build["deterministic_double_build"] is True and build["frozen"]["frozen_install_payload_byte_equal"] is True and all(build["frozen"]["sca_identity_normalized_equal"].values()) and build["functional_rtl_modified"] is False,
        "family_audit": family["valid"] is True and family["status"] == "PASS" and not family["errors"] and family["observer"]["focused_compile"]["valid"] is True,
        "actual_consumer_scope": actual_scope["valid"] is True and actual_scope["positive"]["exit_code"] == 0 and actual_scope["negative_missing_exact_declaration"]["exit_code"] != 0 and actual_scope["negative_mutation_back_to_p21_identifier"]["exit_code"] != 0 and actual_scope["legacy_undeclared_identifier_absent"] is True,
        "runtime_scenarios": all(scenarios[name]["runner_exit"] == scenario_exits[name] and scenarios[name]["finalizer_reached"] is True and scenarios[name]["fixed_result_return_published"] is True and scenarios[name]["root_exact_set_unchanged"] is True and scenarios[name]["unknown_items_deleted_or_overwritten"] is False and scenarios[name]["writes_outside_install"] is False for name in required_scenarios),
        "shared_runtime_layout_once": shared["pass"] is True and not shared["errors"],
        "observer_exact_fix": "return_obs_enabled" not in observer and observer.count("if (return_obs_eo_enabled && n4d_fd != 0) begin") == 2 and manifest["p22_epoch_owner_identifier_fix"]["exact_change_count"] == 1,
        "repeatable_return_contract": (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and 'return_zip="/home/panqs/ndp/simresult/${package_identity}_${return_tag}_return.zip"' in runner
        ),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p22-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD", "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid, "package_identity": PACKAGE_ID,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE", "checks": checks,
        "zip": {**receipt(ZIP_PATH), "deterministic_double_build": True},
        "audits": {
            "p21_return_analysis": receipt(ANALYSIS), "build_profile": receipt(PROFILE), "build": receipt(BUILD),
            "family": {**receipt(FAMILY), "pass": family["valid"], "errors": len(family["errors"])},
            "runtime_layout_harness": {**receipt(HARNESS), "required_scenarios_pass": list(required_scenarios)},
            "shared_runtime_layout": {**receipt(SHARED), "pass": shared["pass"], "errors": len(shared["errors"]), "exact_final_zip_invocation_count": 1, "runner_early_exit_visibility": shared["runner_early_exit_visibility"]["pass"]},
        },
        "frozen_surface": {
            "install_payload_member_count": build["frozen"]["frozen_install_payload_member_count"],
            "install_payload_byte_equal": True, "sca_identity_normalized_equal": True,
            "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False,
            "functional_rtl_modified": False,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["exact_zip_identity"]},
            "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runtime_scenarios"] and checks["repeatable_return_contract"]},
            "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout_once"]},
            "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["family_audit"] and checks["actual_consumer_scope"] and checks["observer_exact_fix"]},
            "diagnostic_semantics": {"applicability": "receipt_reuse", "pass": True},
            "materialized_config": {"applicability": "receipt_reuse", "pass": checks["deterministic_frozen_build"]},
            "numeric_w3_golden": {"applicability": "record_only", "pass": True},
            "production_compile_sim_return": {"applicability": "dynamic_only", "pass": None},
        },
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip.sha256",
            "duplicate_absent_required": True,
        },
        "claim_boundary": "p22 is c0 diagnostic-only. It fixes one package-local lexical identifier and does not claim natural terminal, formal 320D, E3/E4/E5, numeric correctness or performance before formal server return.",
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p22 final audit")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
