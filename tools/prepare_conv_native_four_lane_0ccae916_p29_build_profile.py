#!/usr/bin/env python3
"""Materialize the p29 shadow-only server-package build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own/server_package_build_spec.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha256(path)}


def validator(path: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha256(ROOT / path), "fixture_sha256": sha256(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p29 build specification")
    inputs = [
        record("artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p28_b5release.zip", "package_identity"),
        record("tools/build_conv_native_four_lane_0ccae916_p29_row2own_package.py", "runner"),
        record("outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json", "return_collector"),
        record("outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/source_bound_probe_catalog.json", "probe_catalog"),
        record("outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/source_bound_probe_plan.json", "probe_plan"),
        record("outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/generated/source_bound_causal_observer.svh", "package_local_hdl"),
        record("outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/generated/source_bound_causal_parser.py", "parser"),
        record("tools/server_post_sim_return.py", "return_core_contract"),
    ]
    builder = "tools/build_conv_native_four_lane_0ccae916_p29_row2own_package.py"
    generator = "tools/generate_server_source_bound_observer.py"
    post_helper = "tools/server_post_sim_return.py"
    runtime_validator = "tools/validate_server_package_runtime_layout.py"
    storage = "tools/manage_server_test_package_storage.py"
    generation = "outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/source_bound_observer_generation.json"
    post_report = "outputs/conv_native_four_lane_0ccae916_p29_row2own/build_v6/r5_n4_0cc_p29_row2own.post_sim.json"
    source_report = "outputs/conv_native_four_lane_0ccae916_p29_row2own/build_v6/r5_n4_0cc_p29_row2own.source_bound_final_zip.json"
    shared_report = "outputs/conv_native_four_lane_0ccae916_p29_row2own/build_v6/r5_n4_0cc_p29_row2own.shared_layout.json"
    zip_path = "outputs/conv_native_four_lane_0ccae916_p29_row2own/build_v6/r5_n4_0cc_p29_row2own.zip"
    validators = {
        "core_identity_bootstrap": validator(builder, "outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json"),
        "source_bound_observer_generation": validator(generator, generation),
        "runner_control_flow": validator(builder, "outputs/conv_native_four_lane_0ccae916_p29_row2own/build_v6/r5_n4_0cc_p29_row2own.runner_harness.json"),
        "package_local_hdl": validator(generator, "outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/generated/source_bound_causal_observer.svh"),
        "materialized_config": validator(builder, "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p28_b5release.zip"),
        "diagnostic_semantics": validator(generator, "outputs/conv_native_four_lane_0ccae916_p29_row2own_source_bound/source_bound_probe_plan.json"),
        "post_sim_return_core": validator(post_helper, post_report),
        "return_result_contract": validator(post_helper, post_report),
        "source_bound_final_zip": validator(generator, source_report),
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
