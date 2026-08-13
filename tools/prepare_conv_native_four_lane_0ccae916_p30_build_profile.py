#!/usr/bin/env python3
"""Materialize the p30 shadow-only server-package build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
BASE = "outputs/conv_native_four_lane_0ccae916_p30_bankvalid"
BUILD = f"{BASE}/build"
BOUND = "outputs/conv_native_four_lane_0ccae916_p30_bankvalid_source_bound_v2"
OUTPUT = ROOT / BASE / "server_package_build_spec.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha256(path)}


def validator(path: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha256(ROOT / path), "fixture_sha256": sha256(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p30 build specification")
    source_bound_report = f"{BUILD}/{PACKAGE_ID}.source_bound_final_zip.json"
    post_report = f"{BUILD}/{PACKAGE_ID}.post_sim.json"
    shared_report = f"{BUILD}/{PACKAGE_ID}.shared_layout.json"
    harness_report = f"{BUILD}/{PACKAGE_ID}.runner_harness.json"
    zip_path = f"{BUILD}/{PACKAGE_ID}.zip"
    generation = f"{BOUND}/source_bound_observer_generation.json"
    builder = "tools/build_conv_native_four_lane_0ccae916_p30_bankvalid_package.py"
    generator = "tools/generate_server_source_bound_observer.py"
    post_helper = "tools/server_post_sim_return.py"
    runtime_validator = "tools/validate_server_package_runtime_layout.py"
    storage = "tools/manage_server_test_package_storage.py"
    inputs = [
        record("artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p29_row2own.zip", "package_identity"),
        record(builder, "runner"),
        record("outputs/conv_native_four_lane_0ccae916_p29_return_analysis/report_v2.json", "return_collector"),
        record(f"{BOUND}/source_bound_probe_catalog.json", "probe_catalog"),
        record(f"{BOUND}/source_bound_probe_plan.json", "probe_plan"),
        record(f"{BOUND}/generated/source_bound_causal_observer.svh", "package_local_hdl"),
        record(f"{BOUND}/generated/source_bound_causal_parser.py", "parser"),
        record(post_helper, "return_core_contract"),
    ]
    validators = {
        "core_identity_bootstrap": validator(builder, "outputs/conv_native_four_lane_0ccae916_p29_return_analysis/report_v2.json"),
        "source_bound_observer_generation": validator(generator, generation),
        "runner_control_flow": validator("tools/validate_conv_native_four_lane_0ccae916_p30_runner_harness.py", harness_report),
        "package_local_hdl": validator(generator, f"{BOUND}/generated/source_bound_causal_observer.svh"),
        "materialized_config": validator(builder, "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p29_row2own.zip"),
        "diagnostic_semantics": validator(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "post_sim_return_core": validator(post_helper, post_report),
        "return_result_contract": validator(post_helper, post_report),
        "source_bound_final_zip": validator(generator, source_bound_report),
        "final_zip_content": validator(builder, zip_path),
        "storage_rotation": validator(storage, "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"),
        "runtime_layout": validator(runtime_validator, shared_report),
    }
    value = {
        "schema": "server-package-build-spec-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "changed_surfaces": [
            "package_identity", "runner", "package_local_hdl", "observer", "probe_catalog", "probe_plan",
            "parser", "progress", "canonical_predicate", "return_core_contract", "return_collector", "storage",
        ],
        "inputs": inputs,
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": "core_identity_bootstrap", "path": "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json", "sha256": sha256(ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json")},
            {"gate_id": "source_bound_observer_generation", "path": generation, "sha256": sha256(ROOT / generation)},
            {"gate_id": "storage_rotation", "path": "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json", "sha256": sha256(ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json")},
            {"gate_id": "intermediate_report_format", "path": "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json", "sha256": sha256(ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json")},
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha256(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
