#!/usr/bin/env python3
"""Close the exact-final-ZIP gates for native Conv mandatory-VPD p41."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p41_vpdfull"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p41_vpdfull"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite final audit: {OUTPUT}")
    paths = {
        "build": BUILD / f"{PACKAGE}.build.json",
        "profile": BASE / "server_package_build_profile_v2.json",
        "runner_resilience": BUILD / f"{PACKAGE}.runner_return_resilience.json",
        "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
        "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
        "waveform": BUILD / f"{PACKAGE}.waveform.json",
        "compile_core_waveform": BUILD / f"{PACKAGE}.compile_core_harness.json",
        "six_state_runner": BUILD / f"{PACKAGE}.runner_harness.json",
        "runtime_layout": BUILD / f"{PACKAGE}.shared_layout.json",
        "observer_public_surface": BUILD / f"{PACKAGE}.observer_public_surface.json",
        "first_fresh_contract": BASE / "first_fresh_audit/contract.json",
        "first_fresh": BASE / "first_fresh_audit/first_fresh_validation.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing audit receipts: {missing}")
    values = {name: load(path) for name, path in paths.items()}
    build = values["build"]
    profile = values["profile"]
    runner = values["runner_resilience"]
    core = values["compile_core_waveform"]
    runtime = values["runtime_layout"]
    first = values["first_fresh"]
    with zipfile.ZipFile(ZIP) as archive:
        names = archive.namelist()
        crc_error = archive.testzip()
        plan = json.loads(archive.read(f"{PACKAGE}/contracts/server_waveform_mandatory_plan.json"))
        runner_text = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
    dump = plan.get("dump", {})
    policy = plan.get("return_policy", {})
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    harness_scenarios = values["six_state_runner"].get("scenarios", {})
    checks = {
        "one_exact_final_zip": len(list(BUILD.glob(f"{PACKAGE}.zip"))) == 1 and crc_error is None,
        "single_safe_root": bool(names) and {name.split("/", 1)[0] for name in names} == {PACKAGE},
        "deterministic_frozen_build": build.get("deterministic_double_build_tree_equal") is True
        and build.get("config_numeric_workload_rtl_frozen") is True
        and build.get("target_diagnostic_frozen") is True,
        "one_shared_prebuild_aggregate": build.get("prebuild_aggregate_top_level_invocations") == 1
        and profile.get("preflight", {}).get("pass") is True
        and profile.get("preflight", {}).get("errors") == [],
        "runner_definition_before_use": runner.get("pass") is True
        and runner.get("definition_before_use", {}).get("unsafe_uses") == [],
        "compile_core_return": core.get("pass") is True
        and core.get("details", {}).get("checks", {}).get("actual_compile_argv") is True
        and core.get("details", {}).get("checks", {}).get("actual_source_identity") is True
        and core.get("details", {}).get("checks", {}).get("compile_not_started_waveform_absent") is True,
        "structured_first_error": core.get("details", {}).get("checks", {}).get("first_error_actual") is True
        and core.get("details", {}).get("checks", {}).get("first_error_bounded") is True,
        "source_bound_typed_v2": values["source_bound"].get("pass") is True,
        "post_sim_core": values["post_sim"].get("pass") is True,
        "mandatory_waveform_final_zip": values["waveform"].get("pass") is True,
        "mandatory_waveform_actual_controls": dump.get("make_arguments")
        == {"DUMP_FSDB": "0", "DUMP_VCD": "1", "TB_DUMP_FSDB": "0"}
        and "DUMP_VCD=0" not in runner_text,
        "full_hierarchy_depth0_no_exclusions": dump.get("tb_top") == "tb_NDP_Top_new_phy"
        and dump.get("scope_mode") == "FULL_HIERARCHY"
        and dump.get("hierarchy_depth") == 0
        and dump.get("included_scopes") == ["tb_NDP_Top_new_phy"]
        and dump.get("excluded_scopes") == [],
        "unbounded_all_vpd_shards": dump.get("waveform_name_patterns") == ["wave.vpd", "wave.vpd.*"]
        and policy.get("collect_all_matching") is True
        and policy.get("hard_limit_bytes") is None
        and policy.get("sampling_allowed") is False
        and policy.get("truncation_allowed") is False
        and policy.get("size_based_deletion_allowed") is False,
        "simulation_started_without_wave_fail_closed": policy.get("required_when_simulation_started") is True,
        "compile_not_started_compile_core_exemption": policy.get("compile_not_started_omission_allowed") is True,
        "six_state_runner": all(harness_scenarios.get(name, {}).get("finalizer_reached") is True for name in required_scenarios),
        "runtime_layout": runtime.get("pass") is True and runtime.get("errors") == [],
        "observer_public_surface": values["observer_public_surface"].get("pass") is True,
        "first_fresh_exact_zip": first.get("pass") is True
        and first.get("upload_authorized") is True
        and first.get("errors") == [],
        "old_p40_not_pending": not (ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p40_dhpubfix.zip").exists(),
        "old_p40_preserved_superseded": (ROOT / "artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.zip").is_file(),
        "server_action_absent": build.get("server_action") is False and core.get("server_action") is False,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p41-vpdfull-final-zip-audit-v1",
        "package_identity": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "candidate_release": False,
        "previous_version_progress": "p39 closed production compile exit=2 to two package-local observer arb_req_ready XMR sites; old p40 preserved the Datahub public-surface and structured-first-error repair but was withdrawn for dump=0 semantics.",
        "current_version_purpose": "Preserve the p40-equivalent diagnostic, prove production compile beyond that repair, and return mandatory full-hierarchy unbounded VPD to localize the retained MSE4 causal blocker in one run.",
        "checks": checks,
        "errors": errors,
        "zip": receipt(ZIP),
        "audits": {name: receipt(path) for name, path in paths.items()},
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256",
        },
        "claim_boundary": "Local package construction and exact-ZIP gates only. No upload, lease, server execution, production compile, DUT result, natural terminal, formal D, E4 or E5 claim.",
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(OUTPUT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
