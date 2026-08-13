#!/usr/bin/env python3
"""Write the p36 one-shot prebuild aggregate specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p36_semfp"
BASE = "outputs/conv_native_four_lane_0ccae916_p36_semfp"
BOUND = "outputs/conv_native_four_lane_0ccae916_p36_semfp_source_bound"
OUTPUT = ROOT / BASE / "server_package_build_spec_v2.json"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(relative: str, surface: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "surface": surface, "bytes": path.stat().st_size, "sha256": sha(path)}


def identity(validator: str, fixture: str) -> dict[str, str]:
    return {"validator_sha256": sha(ROOT / validator), "fixture_sha256": sha(ROOT / fixture)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p36 build specification")
    builder = "tools/build_conv_native_four_lane_0ccae916_p36_semfp_package.py"
    generator = "tools/generate_server_source_bound_observer.py"
    source = "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p35c_armknown.zip"
    analysis = "outputs/conv_native_four_lane_0ccae916_p35c_return_analysis/report_v2.json"
    parser = "tools/conv_native_four_lane_p35_arm_known_parser.py"
    post_helper = "tools/server_post_sim_return.py"
    fixture = "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    validators = {
        "core_identity_bootstrap": identity(builder, analysis),
        "source_bound_observer_generation": identity(generator, f"{BOUND}/source_bound_generation_report.json"),
        "runner_control_flow": identity("tools/validate_conv_native_four_lane_0ccae916_p35c_runner_harness.py", fixture),
        "package_local_hdl": identity(generator, f"{BOUND}/generated/source_bound_causal_observer.svh"),
        "materialized_config": identity(builder, source),
        "diagnostic_semantics": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "post_sim_return_core": identity(post_helper, fixture),
        "return_result_contract": identity(post_helper, fixture),
        "source_bound_final_zip": identity(generator, f"{BOUND}/source_bound_probe_plan.json"),
        "final_zip_content": identity(builder, source),
        "storage_rotation": identity("tools/manage_server_test_package_storage.py", "fixtures/server_package_pipeline_v1/cheap/storage_rotation.json"),
        "runtime_layout": identity("tools/validate_server_package_runtime_layout.py", fixture),
        "first_fresh_extra_audit": identity("tools/validate_server_first_fresh_extra_audit.py", f"{BOUND}/rule_change_ack.json"),
    }
    value = {
        "schema": "server-package-build-spec-v1",
        "package_id": PACKAGE,
        "family": "conv_native_four_lane",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "rule_change_epoch": {"epoch_id": EPOCH, "first_fresh_after_change": True, "notification_acknowledged": True, "rule_ids": RULE_IDS},
        "changed_surfaces": ["package_identity", "package_local_hdl", "observer", "probe_catalog", "probe_plan", "parser", "canonical_predicate", "return_core_contract", "return_collector", "storage"],
        "inputs": [
            record(source, "package_identity"), record(builder, "package_identity"), record(analysis, "return_collector"),
            record(f"{BOUND}/source_bound_probe_catalog.json", "probe_catalog"),
            record(f"{BOUND}/source_bound_probe_plan.json", "probe_plan"),
            record(f"{BOUND}/generated/source_bound_causal_observer.svh", "package_local_hdl"),
            record(f"{BOUND}/generated/source_bound_causal_parser.py", "parser"),
            record(parser, "canonical_predicate"), record(f"{BOUND}/arm_known_contract.json", "canonical_predicate"),
            record(f"{BOUND}/exact_instance_identity.json", "canonical_predicate"),
            record(post_helper, "return_core_contract"), record(f"{BOUND}/rule_change_ack.json", "storage"),
        ],
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": "core_identity_bootstrap", "path": fixture, "sha256": sha(ROOT / fixture)},
            {"gate_id": "source_bound_observer_generation", "path": f"{BOUND}/source_bound_observer_generation.json", "sha256": sha(ROOT / BOUND / "source_bound_observer_generation.json")},
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
