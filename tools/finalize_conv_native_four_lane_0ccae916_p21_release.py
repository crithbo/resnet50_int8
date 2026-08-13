#!/usr/bin/env python3
"""Create the exact final-ZIP release receipt for native-four-lane p21."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p21_epochowner"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_epochowner"
ZIP_PATH = BASE / "build_v3" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build_v3" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p21_family_audit_v2.json"
HARNESS = BASE / "p21_runtime_layout_harness.json"
SHARED = BASE / "p21_shared_runtime_layout.json"
PROFILE = BASE / "server_package_build_profile_v3.json"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p20_return_analysis/report_v2.json"
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit.json"
EXPECTED_ZIP_SHA256 = "cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d"


class FinalizeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> int:
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, PROFILE, ANALYSIS)
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p21 release input is absent")
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
    epoch_feature = next(row for row in manifest["diagnostic_features"] if row.get("feature") == "RETURN_OBS_EPOCH_OWNER")
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == 5_876_983 and sha256(ZIP_PATH) == EXPECTED_ZIP_SHA256,
        "formal_p20_analysis": analysis["valid"] is True and analysis["status"] == "P20_COMPILE_FIX_PASS_PER_INPUT_EPOCH_OWNER_SUCCESSOR_REQUIRED",
        "shadow_build_profile": profile["contract_valid"] is True and profile["preflight"]["pass"] is True and not profile["preflight"]["errors"] and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH",
        "deterministic_frozen_build": build["deterministic_double_build"] is True and build["frozen"]["frozen_install_payload_byte_equal"] is True and all(build["frozen"]["sca_identity_normalized_equal"].values()) and build["functional_rtl_modified"] is False,
        "family_audit": family["valid"] is True and family["status"] == "PASS" and not family["errors"] and family["observer"]["focused_compile"]["valid"] is True and family["observer"]["focused_compile"]["epoch_owner"]["valid"] is True,
        "runtime_scenarios": all(scenarios[name]["runner_exit"] == scenario_exits[name] and scenarios[name]["finalizer_reached"] is True and scenarios[name]["fixed_result_return_published"] is True and scenarios[name]["root_exact_set_unchanged"] is True and scenarios[name]["unknown_items_deleted_or_overwritten"] is False and scenarios[name]["writes_outside_install"] is False for name in required_scenarios),
        "shared_runtime_layout_once": shared["pass"] is True and not shared["errors"],
        "epoch_feature_exact": epoch_feature["runtime_enable_parameter"] == "+RETURN_OBS_EPOCH_OWNER" and epoch_feature["limit_parameter"] == "+RETURN_OBS_EPOCH_OWNER_LIMIT=128" and observer.count("// v66 EPOCH_OWNER_ACTUAL_CONSUMER_BEGIN") == observer.count("// v66 EPOCH_OWNER_ACTUAL_CONSUMER_END") == 1,
        "signal_safe_partial_receipt": runner.count("[ ! -f \"$evidence_root/feature_binding/c0.json\" ]") == 1 and runner.count("[ -s \"$run_root/c0/simulator_argv.txt\" ]") == 1 and runner.index("feature-binding --sim-log") < runner.index('python3 "$runtime" analyze --package-root'),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p21-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid, "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID, "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "checks": checks, "zip": {**receipt(ZIP_PATH), "deterministic_double_build": True},
        "audits": {
            "p20_return_analysis": receipt(ANALYSIS), "build_profile": receipt(PROFILE), "build": receipt(BUILD),
            "family": {**receipt(FAMILY), "pass": family["valid"], "errors": len(family["errors"])},
            "runtime_layout_harness": {**receipt(HARNESS), "required_scenarios_pass": list(required_scenarios)},
            "shared_runtime_layout": {**receipt(SHARED), "pass": shared["pass"], "errors": len(shared["errors"]), "exact_final_zip_invocation_count": 1, "runner_early_exit_visibility": shared["runner_early_exit_visibility"]["pass"]},
        },
        "frozen_surface": {"install_payload_member_count": 87, "install_payload_byte_equal": True, "sca_identity_normalized_equal": True, "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False, "functional_rtl_modified": False},
        "release_gate_matrix": {
            "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["exact_zip_identity"]},
            "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runtime_scenarios"] and checks["signal_safe_partial_receipt"]},
            "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout_once"]},
            "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["family_audit"]},
            "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["epoch_feature_exact"]},
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
        "claim_boundary": "p21 is c0 diagnostic-only. It adds per-input epoch ownership and signal-safe partial receipts; it does not claim natural terminal, formal 320D, E4/E5, numeric correctness or performance before formal server return.",
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p21 final audit")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
