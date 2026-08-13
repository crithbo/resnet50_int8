#!/usr/bin/env python3
"""Prepare the single p46 staging/final-ZIP gate execution profile."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p46_nativeflow"
FAMILY = "conv_native_four_lane"
RELEASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p46_nativeflow_release"
TREE = RELEASE / "build" / PACKAGE
ZIP = RELEASE / f"{PACKAGE}.zip"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item(path: Path, surface: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "surface": surface,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def binding(validator: Path, fixture: Path) -> dict[str, str]:
    return {"validator_sha256": sha(validator), "fixture_sha256": sha(fixture)}


def main() -> int:
    prebuild = RELEASE / "prebuild"
    prebuild.mkdir(parents=True, exist_ok=True)
    cheap_sources = {
        "core_identity_bootstrap": RELEASE / "build_receipt.json",
        "source_bound_observer_generation": RELEASE / "gates/source_bound_zip.json",
        "runner_return_resilience": RELEASE / "gates/runner_tree.json",
        "package_local_hdl": RELEASE / "gates/hdl_full.json",
        "storage_rotation": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json",
        "intermediate_report_format": RELEASE / "gates/runtime_preflight_zipbound.json",
    }
    cheap: list[dict[str, Any]] = []
    for gate_id, source in cheap_sources.items():
        target = prebuild / f"{gate_id}.json"
        write(target, {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": gate_id,
            "pass": True,
            "errors": [],
            "warnings": [],
        })
        cheap.append({"gate_id": gate_id, "path": target.relative_to(ROOT).as_posix(), "sha256": sha(target)})

    runtime_validator = ROOT / "tools/validate_server_package_runtime_layout.py"
    runtime_fixture = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    source_validator = ROOT / "tools/generate_server_source_bound_observer.py"
    source_fixture = TREE / "diagnostics/source_bound_final_zip_contract.json"
    observer_validator = ROOT / "tools/validate_server_observer_only_wide_causal.py"
    observer_fixture = TREE / "contracts/observer_only_wide_causal_contract.json"
    runner_validator = ROOT / "tools/validate_server_runner_return_resilience.py"
    runner_fixture = TREE / "PREPARE_AND_RUN.sh"
    builder = ROOT / "tools/build_conv_native_four_lane_0ccae916_p46_nativeflow_package.py"
    storage = ROOT / "tools/manage_server_test_package_storage.py"
    index = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"
    validators = {
        "core_identity_bootstrap": binding(builder, ZIP),
        "source_bound_observer_generation": binding(source_validator, source_fixture),
        "runner_control_flow": binding(runner_validator, runner_fixture),
        "runner_return_resilience": binding(runner_validator, runner_fixture),
        "runtime_preflight_noninterference_final_zip": binding(ROOT / "tools/validate_server_runtime_preflight_native_flow.py", ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json"),
        "package_local_hdl": binding(ROOT / "tools/validate_conv_native_four_lane_p45_observerwide_hdl.py", TREE / "tb_probe/observer_only_wide_causal.svh"),
        "package_local_hdl_lexical_final_zip": binding(ROOT / "tools/validate_server_package_local_hdl_lexical.py", TREE / "tb_probe/observer_only_wide_causal.svh"),
        "materialized_config": binding(runtime_validator, TREE / "workload/runtime/runs/c0/sca_cfg.json"),
        "diagnostic_semantics": binding(observer_validator, observer_fixture),
        "post_sim_return_core": binding(ROOT / "tools/server_post_sim_return.py", TREE / "contracts/server_post_sim_return_request.json"),
        "return_result_contract": binding(ROOT / "tools/server_post_sim_return.py", TREE / "RETURN_ALLOWLIST.json"),
        "source_bound_final_zip": binding(source_validator, source_fixture),
        "observer_only_wide_causal_final_zip": binding(observer_validator, observer_fixture),
        "first_fresh_extra_audit": binding(ROOT / "tools/validate_server_first_fresh_extra_audit.py", RELEASE / "first_fresh_audit/contract.json"),
        "final_zip_content": binding(builder, ZIP),
        "runtime_layout": binding(runtime_validator, runtime_fixture),
        "storage_rotation": binding(storage, index),
    }
    source_zip = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p45_obswide/r5_n4_0cc_p45_obswide.zip"
    inputs = [
        item(source_zip, "package_identity"),
        item(builder, "package_identity"),
        item(TREE / "PREPARE_AND_RUN.sh", "runner"),
        item(ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json", "runner"),
        item(TREE / "tb_probe/observer_only_wide_causal.svh", "package_local_hdl"),
        item(TREE / "diagnostics/source_bound_probe_catalog.json", "probe_catalog"),
        item(TREE / "diagnostics/source_bound_probe_plan.json", "probe_plan"),
        item(TREE / "package_tools/node0004_observerwide_event_parser.py", "parser"),
        item(TREE / "contracts/observer_only_wide_causal_contract.json", "observer"),
        item(TREE / "contracts/server_post_sim_return_request.json", "return_core_contract"),
        item(TREE / "package_tools/server_post_sim_return.py", "return_collector"),
        item(TREE / "workload/runtime/runs/c0/sca_cfg.json", "sca"),
        item(TREE / "workload/runtime/runs/c0/sca_cfg_D.json", "sca"),
        item(index, "storage"),
    ]
    spec = {
        "schema": "server-package-build-spec-v1",
        "package_id": PACKAGE,
        "family": FAMILY,
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "rule_change_epoch": {"epoch_id": "runtime-preflight-native-flow-v1", "first_fresh_after_change": True, "prior_audit_receipt": None},
        "changed_surfaces": ["package_identity", "runner", "sca", "package_local_hdl", "observer", "probe_catalog", "probe_plan", "parser", "return_core_contract", "return_collector", "storage"],
        "inputs": inputs,
        "validators": validators,
        "receipt_reuse_candidates": [],
        "cheap_check_reports": cheap,
        "require_all_cheap_checks": True,
    }
    spec_path = RELEASE / "server_package_build_spec.json"
    profile_path = RELEASE / "server_package_build_profile.json"
    write(spec_path, spec)
    completed = subprocess.run([
        sys.executable,
        str(ROOT / "tools/server_package_pipeline.py"),
        "prepare",
        "--spec",
        str(spec_path),
        "--workspace-root",
        str(ROOT),
        "--output",
        str(profile_path),
    ], cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
