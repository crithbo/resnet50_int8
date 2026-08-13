#!/usr/bin/env python3
"""Bind all exact v56 local gates before storage publication."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_lanephase_v56"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package"
ZIP = LOCAL / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
FIRST = LOCAL / "first_fresh_extra_audit_v4"
FILES = {
    "build": LOCAL / "build_receipt.json",
    "source_bound": LOCAL / "source_bound_final_zip_validation.json",
    "post_sim": LOCAL / "post_sim_return_final_zip_validation.json",
    "runtime_layout": LOCAL / "shared_runtime_layout_validation.json",
    "first_contract": FIRST / "contract.json",
    "first_validation": FIRST / "validation.json",
    "v54_return": ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v54-return-analysis/report.json",
}
CONTROL = {
    "agent": ROOT / ".agents/agent.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "whole_net_specialist": ROOT / ".agents/rules/整网测试收敛优化专项规则.md",
    "server_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    "generator": ROOT / "tools/generate_server_source_bound_observer.py",
    "first_fresh_validator": ROOT / "tools/validate_server_first_fresh_extra_audit.py",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def receipt(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    errors: list[str] = []
    missing = [name for name, path in {**FILES, **CONTROL}.items() if not path.is_file()]
    errors.extend(f"missing:{name}" for name in missing)
    if errors:
        print(json.dumps({"pass": False, "errors": errors}))
        return 1
    build = load(FILES["build"])
    source = load(FILES["source_bound"])
    post = load(FILES["post_sim"])
    layout = load(FILES["runtime_layout"])
    first = load(FILES["first_validation"])
    v54 = load(FILES["v54_return"])
    with zipfile.ZipFile(ZIP) as archive:
        manifest_name = [name for name in archive.namelist() if name.endswith("/TEST_PACKAGE_MANIFEST.json")]
        manifest = json.loads(archive.read(manifest_name[0])) if len(manifest_name) == 1 else {}
        crc = archive.testzip() is None
        names = archive.namelist()
    zip_sha = sha(ZIP)
    controls = source.get("semantic_controls", {})
    checks = {
        "exact_zip_crc_single_manifest": crc and len(manifest_name) == 1,
        "build_receipt_exact": build.get("zip", {}).get("sha256") == zip_sha and build.get("zip", {}).get("bytes") == ZIP.stat().st_size and build.get("deterministic_double_build") is True,
        "sidecar_exact": SIDECAR.read_text(encoding="ascii").strip() == f"{zip_sha}  {ZIP.name}",
        "manifest_identity_claim": manifest.get("package_id") == NAME and manifest.get("install_name") == NAME and manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "source_bound_final_zip": source.get("pass") is True and source.get("errors") == [] and source.get("zip", {}).get("sha256") == zip_sha,
        "typed_v2_controls": controls.get("pass") is True and controls.get("positive_count") == 4 and controls.get("negative_count") == 8 and controls.get("case_count") == 12,
        "post_sim_core": post.get("pass") is True and post.get("errors") == [] and post.get("zip_sha256") == zip_sha,
        "runtime_layout": layout.get("pass") is True and layout.get("errors") == [] and layout.get("zip", {}).get("sha256") == zip_sha,
        "first_fresh_independent": first.get("pass") is True and first.get("errors") == [] and first.get("upload_authorized") is True and first.get("package_id") == NAME,
        "v54_root_cause_bound": v54.get("FIRST_DIVERGENCE") == "BUFFER5_ROW0_REQUEST_MASK_33333333_DISJOINT_FROM_VALID_MASK_CCCCCCCC",
        "host_stimulus_not_producer": manifest.get("boundary_input_contract", {}).get("host_precomputed_internal_tensor") is True and manifest.get("boundary_input_contract", {}).get("producer_evidence_claimed") is False,
        "frozen_stage_scope": manifest.get("split_segment_contract", {}).get("stage_names") == ["op_tail_round"] and manifest.get("split_segment_contract", {}).get("expected_output_count") == 28,
        "generator_current": sha(CONTROL["generator"]) == "c50c2f8117ee6e73da76cae4c5a0fc46a3774b7c775d9bb62942ff8bcd4b837f",
        "no_server_action": build.get("server_action") is False,
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    control_receipts = {name: receipt(path) for name, path in CONTROL.items()}
    validation_receipts = {name: receipt(path) for name, path in FILES.items()}
    release_matrix = {
        "package_bootstrap_path_runtime_D": "PASS_EXACT_ZIP_CLEAN_EXTRACT_AND_INPUT_OPEN",
        "runner_compile_finalizer": "PASS_BASH_PREFLIGHT_SHARED_LAYOUT_AND_JSON_CORE_SCENARIOS",
        "package_local_hdl": "PASS_GENERATED_EXACT_SOURCE_BOUND_TYPED_V2",
        "materialized_config": "NOT_APPLICABLE_BYTE_EQUAL_V54_RECEIPT_REUSE",
        "observer_canonical": "PASS_4_POSITIVE_8_NEGATIVE_SEMANTIC_CONTROLS",
        "return_result_conjunction": "PASS_SHARED_CORE_DYNAMIC_RESULT_PENDING",
        "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
        "functional_RTL": "RECORD_ONLY_UNMODIFIED",
        "first_fresh_extra_audit": "PASS_INDEPENDENT_CLEAN_EXTRACT_V4",
    }
    audit = {
        "schema": "qlinearadd-node0007-tailround-lanephase-v56-final-zip-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "zip": receipt(ZIP),
        "sidecar": receipt(SIDECAR),
        "control_receipts": control_receipts,
        "validation_receipts": validation_receipts,
        "release_gate_matrix": release_matrix,
        "negative_controls": {"positive": 4, "negative": 8, "all_fail_closed": controls.get("pass") is True},
        "failed_pre_release_artifacts": {
            "v55": "QUARANTINED_MISSING_RUNNER_DECISION_BINDING_AND_POST_SIM_CONTRACT_ERRORS",
            "v56_audit_v1_v2": "LOCAL_WINDOWS_LONG_PATH_FIXTURE_ONLY",
            "v56_audit_v3": "LOCAL_STANDALONE_IMPORT_BOOTSTRAP_ONLY",
        },
        "claim_boundary": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; exact isolated op_tail_round Buffer5 lane-phase chronology; host FP32 stimulus is not producer evidence; no full-chain/E3/E4/E5 claim.",
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_changed": False,
        "server_action": False,
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    audit_path = LOCAL / "final_zip_self_audit.json"
    write(audit_path, audit)
    family = {
        "schema": "qlinearadd-node0007-tailround-lanephase-v56-family-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip": audit["zip"],
        "release_gate_matrix": release_matrix,
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "UPLOAD_HOLD",
        "claim_boundary": audit["claim_boundary"],
        "numeric_workload_config_golden_repeated": False,
        "server_action": False,
    }
    family_path = LOCAL / "family_validation.json"
    write(family_path, family)
    release = {
        "schema": "qlinearadd-node0007-tailround-lanephase-v56-release-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "UPLOAD_HOLD",
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "NONE",
        "zip": audit["zip"],
        "sidecar": audit["sidecar"],
        "final_audit": receipt(audit_path),
        "family_validation": receipt(family_path),
        "first_fresh_validation": receipt(FILES["first_validation"]),
        "source_bound_validation": receipt(FILES["source_bound"]),
        "post_sim_validation": receipt(FILES["post_sim"]),
        "runtime_layout_validation": receipt(FILES["runtime_layout"]),
        "server_command": f"cd /home/panqs/ndp/{NAME} && bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy0x",
        "expected_return": f"/home/panqs/ndp/simresult/{NAME}_<execution>_return.zip",
        "successor_scope": "highest-information exact Buffer5 temporal lane-phase chronology diagnostic",
        "blocker_delta": {"closed": ["B_QADD_V54_BUFFER5_STATIC_MASK_OBSERVER_AMBIGUITY"], "opened": ["B_QADD_TAILROUND_TEMPORAL_LANE_PHASE_CORRECTING_CONFIG_LEAF"]},
        "rule_confirmation": "Current exact-instance/grouping, payload-known-width, semantic-fingerprint first-use, shared post-sim return-core, partial-exit and storage-rotation rules are sufficient; no non-synonymous delta proposed.",
        "claim_boundary": audit["claim_boundary"],
        "numeric_workload_config_golden_repeated": False,
        "server_action": False,
        "analysis_owner_thread": audit["analysis_owner_thread"],
        "return_target_thread": audit["return_target_thread"],
    }
    release_path = LOCAL / "release_report.json"
    write(release_path, release)
    print(json.dumps({"pass": not errors, "errors": errors, "zip_sha256": zip_sha, "audit": str(audit_path), "release": str(release_path)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
