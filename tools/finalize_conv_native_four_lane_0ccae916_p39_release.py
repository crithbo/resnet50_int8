#!/usr/bin/env python3
"""Finalize the local exact-ZIP evidence for p39 without server action."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p39_compilecore"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p39_compilecore"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
FILES = {
    "build": BUILD / f"{PACKAGE}.build.json",
    "profile": BASE / "server_package_build_profile_v2.json",
    "runner_resilience": BUILD / f"{PACKAGE}.runner_return_resilience.json",
    "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
    "compile_core_waveform": BUILD / f"{PACKAGE}.compile_core_harness.json",
    "six_state_runner": BUILD / f"{PACKAGE}.runner_harness.json",
    "runtime_layout": BUILD / f"{PACKAGE}.shared_layout.json",
    "first_fresh": BASE / "first_fresh_audit/first_fresh_validation.json",
    "first_fresh_contract": BASE / "first_fresh_audit/contract.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p39 final audit")
    reports = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}
    build = reports["build"]
    profile = reports["profile"]
    runner = reports["runner_resilience"]
    source = reports["source_bound"]
    post = reports["post_sim"]
    core = reports["compile_core_waveform"]
    six = reports["six_state_runner"]
    runtime = reports["runtime_layout"]
    first = reports["first_fresh"]
    scenarios = six.get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    checks = {
        "one_exact_final_zip": build.get("final_zip_count") == 1 and build.get("zip_sha256") == sha(ZIP),
        "deterministic_frozen_build": build.get("deterministic_double_build_tree_equal") is True and build.get("config_numeric_workload_rtl_frozen") is True and build["frozen"].get("frozen_install_payload_member_count") == 87 and build["frozen"].get("frozen_install_payload_byte_equal") is True and all(build["frozen"].get("sca_identity_normalized_equal", {}).values()) and build["frozen"].get("functional_rtl_modified") is False,
        "one_shared_prebuild_aggregate": profile.get("contract_valid") is True and profile.get("preflight", {}).get("errors") == [] and profile.get("execution_contract", {}).get("prebuild_aggregate_top_level_invocations") == 1,
        "runner_definition_before_use": runner.get("pass") is True and runner.get("errors") == [] and runner.get("definition_before_use", {}).get("unsafe_uses") == [],
        "compile_core_return": core.get("pass") is True and core.get("errors") == [] and core.get("details", {}).get("checks", {}).get("compile_core_complete") is True and core.get("details", {}).get("checks", {}).get("first_error_actual") is True,
        "waveform_gate": core.get("details", {}).get("checks", {}).get("explicit_waveform_disable") is True and core.get("details", {}).get("checks", {}).get("waveform_absent") is True,
        "source_bound_typed_v2": source.get("pass") is True and source.get("errors") == [] and source.get("semantic_controls", {}).get("pass") is True,
        "post_sim_core": post.get("pass") is True and post.get("errors") == [],
        "six_state_runner": all(scenarios.get(name, {}).get("runner_exit") == code and scenarios.get(name, {}).get("finalizer_reached") is True and scenarios.get(name, {}).get("fixed_result_return_published") is True for name, code in expected.items()),
        "runtime_layout": runtime.get("pass") is True and runtime.get("errors") == [],
        "first_fresh_exact_zip": first.get("pass") is True and first.get("errors") == [] and first.get("upload_authorized") is True,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-p39-compilecore-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "valid": valid, "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "package_identity": PACKAGE, "candidate_release": False,
        "checks": checks, "errors": [name for name, passed in checks.items() if not passed],
        "zip": receipt(ZIP), "audits": {name: receipt(path) for name, path in FILES.items()},
        "expected_server": {"command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02", "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip", "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256"},
        "claim_boundary": "Runner/compile-rootcause return successor only. No production compile, DUT simulation, numeric/config/RTL change, natural terminal, formal D, E4 or E5 claim.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": result["status"], "output": str(OUTPUT), "zip_sha256": sha(ZIP)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
