#!/usr/bin/env python3
"""Create the final release receipt for native-four-lane Conv p29."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own"
BUILD_ROOT = BASE / "build_v6"
ZIP_PATH = BUILD_ROOT / f"{PACKAGE_ID}.zip"
BUILD = BUILD_ROOT / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p29_family_audit.json"
HARNESS = BUILD_ROOT / f"{PACKAGE_ID}.runner_harness.json"
SHARED = BUILD_ROOT / f"{PACKAGE_ID}.shared_layout.json"
POST_SIM = BUILD_ROOT / f"{PACKAGE_ID}.post_sim.json"
SOURCE_BOUND = BUILD_ROOT / f"{PACKAGE_ID}.source_bound_final_zip.json"
PROFILE = BASE / "server_package_build_profile.json"
P28_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json"
GENERATOR_FIX = ROOT / "outputs/server_source_bound_generator_instance_token_fix/report.json"
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main() -> int:
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, POST_SIM, SOURCE_BOUND, PROFILE, P28_ANALYSIS, GENERATOR_FIX)
    if not all(path.is_file() for path in required):
        raise RuntimeError("required p29 release receipt is absent")
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p29 final audit")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    post_sim = json.loads(POST_SIM.read_text(encoding="utf-8"))
    source_bound = json.loads(SOURCE_BOUND.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(P28_ANALYSIS.read_text(encoding="utf-8"))
    generator_fix = json.loads(GENERATOR_FIX.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        prefix = PACKAGE_ID + "/"
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode("utf-8")
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))
        helper = archive.read(prefix + "package_tools/server_post_sim_return.py")
        contract = json.loads(archive.read(prefix + "contracts/server_post_sim_return_contract.json"))
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    scenarios = harness["scenarios"]
    six_state = all(
        scenarios[name]["runner_exit"] == code
        and scenarios[name]["finalizer_reached"] is True
        and scenarios[name]["fixed_result_return_published"] is True
        and scenarios[name]["root_exact_set_unchanged"] is True
        and scenarios[name]["unknown_items_deleted_or_overwritten"] is False
        and scenarios[name]["writes_outside_install"] is False
        for name, code in expected.items()
    )
    post_scenarios = post_sim["details"]["scenario_results"]
    post_ok = (
        post_scenarios["natural_success"] == {"published": True, "disposition": "COMPLETE_RETURN"}
        and post_scenarios["natural_success_plugin_failure"] == {"published": True, "disposition": "EVIDENCE_INCOMPLETE"}
        and post_scenarios["simulation_nonzero"] == {"published": True, "disposition": "PARTIAL_EXECUTION_RETURN"}
        and post_scenarios["idempotent_reentry"]["first_sha256"] == post_scenarios["idempotent_reentry"]["second_sha256"]
        and post_scenarios["idempotent_reentry"]["second_phase"] == "PUBLISHED_IDEMPOTENT"
    )
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == build["zip_bytes"] and sha256(ZIP_PATH) == build["zip_sha256"],
        "formal_p28_analysis": analysis["valid"] is True and analysis["status"] == "P28_ROW2_CLEAR_VISIBLE_READY_STILL_BLOCKED_SUCCESSOR_REQUIRED",
        "generator_narrow_fix": generator_fix["valid"] is True and generator_fix["verification"]["unittest"]["tests_run"] == 14,
        "deterministic_frozen_build": (
            build["deterministic_double_build"] is True
            and build["frozen"]["frozen_install_payload_member_count"] == 87
            and build["frozen"]["frozen_install_payload_byte_equal"] is True
            and all(build["frozen"]["sca_identity_normalized_equal"].values())
            and build["functional_rtl_modified"] is False
        ),
        "family_audit": family["valid"] is True and not family["errors"],
        "source_bound_final_zip": source_bound["pass"] is True and not source_bound["errors"],
        "post_sim_return_core": post_sim["pass"] is True and not post_sim["errors"] and post_ok,
        "post_sim_exact_helper": hashlib.sha256(helper).hexdigest() == "87c78dd8408d75430074f05e07e99ba3d1b7db3bc5907860b9d15969b172b0b8" and contract["helper_sha256"] == hashlib.sha256(helper).hexdigest(),
        "runner_six_state": six_state,
        "shared_runtime_layout": shared["pass"] is True and not shared["errors"],
        "shadow_profile": profile["contract_valid"] is True and profile["preflight"]["pass"] is True and not profile["preflight"]["errors"],
        "runner_json_only_core": runner.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') == 1 and all(token in runner for token in ("CODEX_PACKAGE_ROOT", "CODEX_ATTEMPT_ROOT", "CODEX_EXECUTION_ID", "CODEX_SIM_EXIT_CODE", "CODEX_SIM_SIGNAL", "CODEX_SIM_STARTED", "CODEX_NATURAL_TERMINAL")),
        "diagnostic_only_claim": manifest["candidate_release"] is False and manifest["formal_readback_claimed"] is False and manifest["formal_readback_count"] == 0,
    }
    valid = all(checks.values())
    release_gate_matrix = {
        "core_identity_bootstrap": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["exact_zip_identity"]},
        "source_bound_observer_generation": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["generator_narrow_fix"]},
        "runner_control_flow": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["runner_six_state"] and checks["runner_json_only_core"]},
        "package_local_hdl": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["source_bound_final_zip"]},
        "diagnostic_semantics": {"applicability": "blocking_applicable", "blocking": True, "pass": family["checks"]["p28_real_raw_parser_charset"]},
        "post_sim_return_core": {"applicability": "blocking_applicable", "blocking": True, "enforcement": "required_next_fresh", "pass": checks["post_sim_return_core"] and checks["post_sim_exact_helper"]},
        "return_result_contract": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["post_sim_return_core"]},
        "source_bound_final_zip": {"applicability": "blocking_applicable", "blocking": True, "enforcement": "required_next_fresh", "pass": checks["source_bound_final_zip"]},
        "final_zip_content": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["family_audit"]},
        "runtime_layout": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["shared_runtime_layout"]},
        "materialized_config": {"applicability": "receipt_reuse", "blocking": False, "pass": checks["deterministic_frozen_build"], "scope": "87 byte-equal installed payload members; SCA identity-only rewrite"},
        "numeric_w3_golden": {"applicability": "record_only", "blocking": False, "pass": True, "scope": "byte-equal/frozen; no redundant numeric rerun"},
        "production_compile_sim_return": {"applicability": "dynamic_only", "blocking": False, "pass": None},
    }
    result = {
        "schema": "conv-native-four-lane-0ccae916-p29-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE" if valid else "NONE",
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "zip": {**receipt(ZIP_PATH), "deterministic_double_build": True},
        "audits": {name: receipt(path) for name, path in {
            "p28_return_analysis": P28_ANALYSIS, "generator_fix": GENERATOR_FIX, "build": BUILD,
            "family": FAMILY, "runner_harness": HARNESS, "shared_runtime_layout": SHARED,
            "post_sim_return_core": POST_SIM, "source_bound_final_zip": SOURCE_BOUND, "shadow_profile": PROFILE,
        }.items()},
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip.sha256",
            "duplicate_absent_required": True,
        },
        "claim_boundary": "p29 is one c0 row2 post-clear ownership diagnostic. It does not claim c0/27 natural terminal, formal 320D, E3/E4/E5, numeric correctness or performance.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
