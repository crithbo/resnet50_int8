#!/usr/bin/env python3
"""Write the one-shot p37 same-epoch shadow build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p37_saepoch"
BASE = "outputs/conv_native_four_lane_0ccae916_p37_saepoch"
BOUND = "outputs/conv_native_four_lane_0ccae916_p37_saepoch_source_bound_v4"
OUTPUT = ROOT / BASE / "server_package_build_spec_v2.json"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
PRIOR = "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha(path)}


def identity(validator: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha(ROOT / validator), "fixture_sha256": sha(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p37 build specification")
    builder = "tools/build_conv_native_four_lane_0ccae916_p37_saepoch_package.py"
    family = "tools/validate_conv_native_four_lane_0ccae916_p37_saepoch_package.py"
    runner = "tools/validate_conv_native_four_lane_0ccae916_p37_runner_harness.py"
    generator = "tools/generate_server_source_bound_observer.py"
    source = "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p36b_semfp.zip"
    analysis = "outputs/conv_native_four_lane_0ccae916_p36b_return_analysis/report.json"
    parser = "tools/conv_native_four_lane_p37_sa_epoch_parser.py"
    helper = "tools/server_post_sim_return.py"
    fixture = "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    generation = f"{BOUND}/source_bound_observer_generation.json"
    validators = {
        "core_identity_bootstrap": identity(builder, analysis),
        "source_bound_observer_generation": identity(generator, generation),
        "runner_control_flow": identity(runner, fixture),
        "package_local_hdl": identity(generator, f"{BOUND}/generated/source_bound_causal_observer.svh"),
        "materialized_config": identity(builder, source),
        "diagnostic_semantics": identity(family, f"{BOUND}/source_bound_probe_plan.json"),
        "post_sim_return_core": identity(helper, fixture),
        "return_result_contract": identity(helper, fixture),
        "source_bound_final_zip": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "final_zip_content": identity(family, source),
        "storage_rotation": identity("tools/manage_server_test_package_storage.py", "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"),
        "runtime_layout": identity("tools/validate_server_package_runtime_layout.py", fixture),
        "first_fresh_extra_audit": identity("tools/validate_server_first_fresh_extra_audit.py", PRIOR),
    }
    value = {
        "schema": "server-package-build-spec-v1", "package_id": PACKAGE,
        "family": "conv_native_four_lane", "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True, "current_package_impact": False,
        "rule_change_epoch": {
            "epoch_id": EPOCH, "first_fresh_after_change": False,
            "prior_audit_receipt": {"path": PRIOR, "sha256": sha(ROOT / PRIOR)},
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
            record(parser, "canonical_predicate"), record(f"{BOUND}/sa_epoch_contract.json", "canonical_predicate"),
            record(f"{BOUND}/exact_instance_identity.json", "canonical_predicate"),
            record(helper, "return_core_contract"), record(PRIOR, "storage"),
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
