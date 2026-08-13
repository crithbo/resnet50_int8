#!/usr/bin/env python3
"""Close p42 exact-final-ZIP gates and bind the epoch's p41 first-fresh PASS."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p42_vecjoinfix"
SOURCE = "r5_n4_0cc_p41_vpdfull"
EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix"
BUILD = BASE / "build"
ZIP = BUILD / f"{PACKAGE}.zip"
AUDIT = BASE / "final_zip_audit"
OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
PRIOR_FIRST_FRESH = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p41_vpdfull/first_fresh_audit/first_fresh_validation.json"
)


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
        "runner_resilience": AUDIT / "runner_return_resilience.json",
        "source_bound": AUDIT / "source_bound_final_zip.json",
        "post_sim": AUDIT / "post_sim_return.json",
        "waveform": AUDIT / "waveform_return.json",
        "compile_core": AUDIT / "compile_core_harness.json",
        "compile_core_layout": AUDIT / "compile_core_shared_layout.json",
        "six_state_runner": AUDIT / "six_state_runner_harness.json",
        "six_state_layout": AUDIT / "six_state_shared_layout.json",
        "observer_public_surface": AUDIT / "observer_public_surface.json",
        "vector_join_predicate": AUDIT / "vector_join_predicate.json",
        "prior_first_fresh": PRIOR_FIRST_FRESH,
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing audit receipts: {missing}")
    values = {name: load(path) for name, path in paths.items()}
    build = values["build"]
    profile = values["profile"]
    runner = values["runner_resilience"]
    core = values["compile_core"]
    six = values["six_state_runner"]
    prior = values["prior_first_fresh"]
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        safe = all(
            not PurePosixPath(row.filename).is_absolute()
            and ".." not in PurePosixPath(row.filename).parts
            and "\\" not in row.filename
            and not stat.S_ISLNK(row.external_attr >> 16)
            for row in infos
        )
        crc_error = archive.testzip()
        plan = json.loads(archive.read(f"{PACKAGE}/contracts/server_waveform_mandatory_plan.json"))
        runner_text = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
    dump = plan.get("dump", {})
    policy = plan.get("return_policy", {})
    scenarios = six.get("scenarios", {})
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    epoch = profile.get("rule_change_epoch", {})
    first_disposition = [
        row for row in profile.get("gate_dispositions", []) if row.get("gate_id") == "first_fresh_extra_audit"
    ]
    prior_receipt = epoch.get("prior_audit_receipt", {})
    core_checks = core.get("details", {}).get("checks", {})
    checks = {
        "one_exact_final_zip": len(list(BUILD.glob(f"{PACKAGE}.zip"))) == 1,
        "safe_crc_single_root": crc_error is None
        and safe
        and len(names) == len(set(names))
        and bool(names)
        and {name.split("/", 1)[0] for name in names} == {PACKAGE},
        "exact_identity": manifest.get("package_identity") == PACKAGE
        and manifest.get("status") == "PACKAGE_READY_NOT_RUN",
        "deterministic_frozen_build": build.get("deterministic_double_build_tree_equal") is True
        and build.get("config_numeric_workload_golden_rtl_frozen") is True
        and build.get("target_diagnostic_frozen") is True,
        "one_shared_prebuild_aggregate": build.get("prebuild_aggregate_top_level_invocations") == 1
        and profile.get("contract_valid") is True
        and profile.get("preflight", {}).get("pass") is True
        and profile.get("preflight", {}).get("errors") == [],
        "runner_definition_before_use": runner.get("pass") is True
        and runner.get("definition_before_use", {}).get("unsafe_uses") == [],
        "bootstrap_safe_compile_core": core.get("pass") is True
        and all(
            core_checks.get(name) is True
            for name in (
                "actual_compile_argv",
                "actual_source_identity",
                "head_bounded",
                "tail_bounded",
                "first_error_bounded",
                "first_error_actual",
                "compile_fail_return_published",
                "compile_not_started_waveform_absent",
            )
        ),
        "source_bound_typed_v2": values["source_bound"].get("pass") is True,
        "vector_join_predicate": values["vector_join_predicate"].get("pass") is True,
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
        "six_state_runner": all(
            scenarios.get(name, {}).get("finalizer_reached") is True
            and scenarios.get(name, {}).get("fixed_result_return_published") is True
            for name in required_scenarios
        ),
        "runtime_layout": values["six_state_layout"].get("pass") is True
        and values["six_state_layout"].get("errors") == [],
        "observer_public_surface": values["observer_public_surface"].get("pass") is True,
        "first_fresh_reuse_bound": epoch.get("epoch_id") == EPOCH
        and epoch.get("first_fresh_after_change") is False
        and prior_receipt.get("package_id") == SOURCE
        and prior_receipt.get("path") == PRIOR_FIRST_FRESH.relative_to(ROOT).as_posix()
        and prior_receipt.get("sha256") == sha(PRIOR_FIRST_FRESH)
        and prior.get("package_id") == SOURCE
        and prior.get("rule_change_epoch_id") == EPOCH
        and prior.get("pass") is True
        and prior.get("upload_authorized") is True
        and prior.get("errors") == []
        and len(first_disposition) == 1
        and first_disposition[0].get("disposition") == "not_applicable",
        "server_action_absent": build.get("server_action") is False and core.get("server_action") is False,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p42-vecjoinfix-final-zip-audit-v1",
        "package_identity": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "first_fresh_after_change": False,
        "first_fresh_disposition": "REUSE_BOUND_P41_PASS" if checks["first_fresh_reuse_bound"] else "INVALID",
        "candidate_release": False,
        "previous_version_progress": (
            "p39 closed production compile exit=2 to two package-local observer arb_req_ready XMR sites; "
            "p40 repaired the Datahub public surface and structured first-error return but was withdrawn for dump=0; "
            "p41 proved production compile passed and returned mandatory full-hierarchy VPD."
        ),
        "current_version_purpose": (
            "Preserve the p40/p41 diagnostic and waveform semantics while correcting only the p41 package-local "
            "two-bit MSE4 valid/ready overlap observer so the retained causal blocker can be localized dynamically."
        ),
        "checks": checks,
        "errors": errors,
        "zip": receipt(ZIP),
        "audits": {name: receipt(path) for name, path in paths.items()},
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip.sha256",
        },
        "claim_boundary": (
            "Local package construction and exact-ZIP gates only. No upload, lease, server execution, p42 production "
            "compile, DUT result, natural terminal, formal D, E3, E4 or E5 claim."
        ),
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(OUTPUT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
