#!/usr/bin/env python3
"""Write the one-shot p31 next-fresh build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p31_postclear"
BASE = "outputs/conv_native_four_lane_0ccae916_p31_postclear"
BOUND = "outputs/conv_native_four_lane_0ccae916_p31_postclear_source_bound_v2"
OUTPUT = ROOT / BASE / "server_package_build_spec.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha(path)}


def identity(validator: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha(ROOT / validator), "fixture_sha256": sha(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p31 build specification")
    builder = "tools/build_conv_native_four_lane_0ccae916_p31_postclear_package.py"
    generator = "tools/generate_server_source_bound_observer.py"
    generation = f"{BOUND}/source_bound_observer_generation.json"
    p30 = "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p30_bankvalid.zip"
    analysis = "outputs/conv_native_four_lane_0ccae916_p30_return_analysis/report.json"
    post_helper = "tools/server_post_sim_return.py"
    dispatch = "contracts/server_first_fresh_extra_audit_dispatch_v1.json"
    validators = {
        "core_identity_bootstrap": identity(builder, analysis),
        "source_bound_observer_generation": identity(generator, generation),
        "runner_control_flow": identity("tools/validate_conv_native_four_lane_0ccae916_p30_runner_harness.py", "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"),
        "package_local_hdl": identity(generator, f"{BOUND}/generated/source_bound_causal_observer.svh"),
        "materialized_config": identity(builder, p30),
        "diagnostic_semantics": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "post_sim_return_core": identity(post_helper, "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"),
        "return_result_contract": identity(post_helper, "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"),
        "source_bound_final_zip": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "final_zip_content": identity(builder, p30),
        "storage_rotation": identity("tools/manage_server_test_package_storage.py", "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"),
        "runtime_layout": identity("tools/validate_server_package_runtime_layout.py", "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"),
        "first_fresh_extra_audit": identity("tools/validate_server_first_fresh_extra_audit.py", dispatch),
    }
    value = {
        "schema": "server-package-build-spec-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "rule_change_epoch": {
            "epoch_id": "20260810-first-fresh-extra-audit-v1",
            "first_fresh_after_change": True,
            "prior_audit_receipt": None,
        },
        "changed_surfaces": [
            "package_identity", "runner", "package_local_hdl", "observer", "probe_catalog", "probe_plan",
            "parser", "progress", "canonical_predicate", "return_core_contract", "return_collector", "storage",
        ],
        "inputs": [
            record(p30, "package_identity"), record(builder, "runner"), record(analysis, "return_collector"),
            record(f"{BOUND}/source_bound_probe_catalog.json", "probe_catalog"),
            record(f"{BOUND}/source_bound_probe_plan.json", "probe_plan"),
            record(f"{BOUND}/generated/source_bound_causal_observer.svh", "package_local_hdl"),
            record(f"{BOUND}/generated/source_bound_causal_parser.py", "parser"),
            record(post_helper, "return_core_contract"),
            record(f"{BOUND}/first_fresh_epoch_ack.json", "storage"),
        ],
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": "core_identity_bootstrap", "path": "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json", "sha256": sha(ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json")},
            {"gate_id": "source_bound_observer_generation", "path": generation, "sha256": sha(ROOT / generation)},
            {"gate_id": "storage_rotation", "path": "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json", "sha256": sha(ROOT / "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json")},
            {"gate_id": "intermediate_report_format", "path": "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json", "sha256": sha(ROOT / "fixtures/server_package_pipeline_v1/cheap/intermediate_report_format.json")},
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(OUTPUT), "sha256": sha(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
