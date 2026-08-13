#!/usr/bin/env python3
"""Write the p33b same-epoch next-fresh shadow build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p33b_wrowner"
BASE = "outputs/conv_native_four_lane_0ccae916_p33b_wrowner"
BOUND = "outputs/conv_native_four_lane_0ccae916_p33b_wrowner_source_bound"
OUTPUT = ROOT / BASE / "server_package_build_spec_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha(path)}


def identity(validator: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha(ROOT / validator), "fixture_sha256": sha(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p33b build specification")
    builder = "tools/build_conv_native_four_lane_0ccae916_p33b_wrowner_package.py"
    family_validator = "tools/validate_conv_native_four_lane_0ccae916_p33b_wrowner_package.py"
    target_parser = "tools/conv_native_four_lane_p33_target_epoch_write_owner_parser.py"
    runner_validator = "tools/validate_conv_native_four_lane_0ccae916_p33b_runner_harness.py"
    generator = "tools/generate_server_source_bound_observer.py"
    generation = f"{BOUND}/source_bound_observer_generation.json"
    source = "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p32b_validowner.zip"
    analysis = "outputs/conv_native_four_lane_0ccae916_p32b_return_analysis/report.json"
    post_helper = "tools/server_post_sim_return.py"
    prior = "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
    fixture = "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    validators = {
        "core_identity_bootstrap": identity(builder, analysis),
        "source_bound_observer_generation": identity(generator, generation),
        "runner_control_flow": identity(runner_validator, fixture),
        "package_local_hdl": identity(generator, f"{BOUND}/generated/source_bound_causal_observer.svh"),
        "materialized_config": identity(builder, source),
        "diagnostic_semantics": identity(family_validator, f"{BOUND}/source_bound_probe_plan.json"),
        "post_sim_return_core": identity(post_helper, fixture),
        "return_result_contract": identity(post_helper, fixture),
        "source_bound_final_zip": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "final_zip_content": identity(family_validator, source),
        "storage_rotation": identity("tools/manage_server_test_package_storage.py", "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"),
        "runtime_layout": identity("tools/validate_server_package_runtime_layout.py", fixture),
        "first_fresh_extra_audit": identity("tools/validate_server_first_fresh_extra_audit.py", prior),
    }
    value = {
        "schema": "server-package-build-spec-v1", "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane", "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True, "current_package_impact": False,
        "rule_change_epoch": {
            "epoch_id": "20260810-first-fresh-extra-audit-v1", "first_fresh_after_change": False,
            "prior_audit_receipt": {"path": prior, "sha256": sha(ROOT / prior)},
        },
        "changed_surfaces": [
            "package_identity", "package_local_hdl", "observer", "probe_catalog", "probe_plan",
            "parser", "canonical_predicate", "return_core_contract", "return_collector", "storage",
        ],
        "inputs": [
            record(source, "package_identity"), record(builder, "package_identity"), record(analysis, "return_collector"),
            record(f"{BOUND}/source_bound_probe_catalog.json", "probe_catalog"),
            record(f"{BOUND}/source_bound_probe_plan.json", "probe_plan"),
            record(f"{BOUND}/generated/source_bound_causal_observer.svh", "package_local_hdl"),
            record(f"{BOUND}/generated/source_bound_causal_parser.py", "parser"),
            record(target_parser, "canonical_predicate"),
            record(f"{BOUND}/target_epoch_write_owner_contract.json", "canonical_predicate"),
            record(post_helper, "return_core_contract"), record(prior, "storage"),
        ],
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": "core_identity_bootstrap", "path": fixture, "sha256": sha(ROOT / fixture)},
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
