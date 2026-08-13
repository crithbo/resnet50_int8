#!/usr/bin/env python3
"""Post-rotation current-rule audit for the exact QAdd v52 pending ZIP."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_queueflow_v52"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package"
ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
RECEIPT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007" / NAME
SIDECAR = RECEIPT / f"{NAME}.zip.sha256"
REPORT = LOCAL / "final_zip_self_audit.json"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "server_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    build = json.loads((LOCAL / "build_receipt.json").read_text(encoding="utf-8"))
    family = json.loads((LOCAL / "family_validation.json").read_text(encoding="utf-8"))
    shared = json.loads((LOCAL / "shared_runtime_layout_validation.json").read_text(encoding="utf-8"))
    extra = json.loads((LOCAL / "first_fresh_extra_audit/validation.json").read_text(encoding="utf-8"))
    zip_sha = sha(ZIP)
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos if not row.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        manifest = json.loads(archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
        records = manifest.get("files", {})
        rels = {name.split("/", 1)[1] for name in names} - {"TEST_PACKAGE_MANIFEST.json"}
        inventory = set(records) == rels and all(records[rel] == {"size_bytes": len(archive.read(f"{NAME}/{rel}")), "sha256": sha_bytes(archive.read(f"{NAME}/{rel}"))} for rel in rels)
        safe = archive.testzip() is None and roots == {NAME} and len(names) == len(set(names)) and all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names) and all(((row.external_attr >> 16) & 0o170000) != 0o120000 for row in infos)
    current = {key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)} for key, path in RULES.items()}
    expected_rules = {key: {"path": current[key]["path"], "sha256": current[key]["sha256"], "current_match": True} for key in ("generation_index", "server", "common_config", "ndp_fields", "qlinearadd", "exact_uint8_tail")}
    sidecar_line = SIDECAR.read_text(encoding="ascii").strip()
    roundtrip = json.loads((LOCAL / "first_fresh_extra_audit/source_bound_logger_collector_parser_roundtrip.json").read_text(encoding="utf-8"))
    candidate = json.loads((LOCAL / "first_fresh_extra_audit/candidate_discrimination_matrix.json").read_text(encoding="utf-8"))
    checks = {
        "pending_zip_safe_exact": safe and inventory,
        "pending_zip_same_as_built": zip_sha == build["zip"]["sha256"] and ZIP.stat().st_size == build["zip"]["bytes"],
        "sidecar_exact": sidecar_line == f"{zip_sha}  {ZIP.name}",
        "manifest_identity_and_current_rules": manifest.get("package_id") == NAME and manifest.get("install_name") == NAME and manifest.get("rule_receipts") == expected_rules,
        "honest_diagnostic_boundary": manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX" and manifest.get("boundary_input_contract", {}).get("host_precomputed_internal_tensor") is True and manifest.get("boundary_input_contract", {}).get("producer_evidence_claimed") is False,
        "isolated_one_stage_28D": manifest.get("split_segment_contract", {}).get("stage_names") == ["op_tail_round"] and manifest.get("split_segment_contract", {}).get("expected_output_count") == 28,
        "family_validation": family.get("valid") is True and family.get("errors") == [] and family["zip"]["sha256"] == zip_sha,
        "shared_runtime_layout": shared.get("pass") is True and shared.get("errors") == [] and shared["zip"]["sha256"] == zip_sha,
        "first_fresh_extra_audit": extra.get("pass") is True and extra.get("errors") == [] and extra.get("upload_authorized") is True and extra.get("package_id") == NAME,
        "candidate_4_of_4": candidate.get("pass") is True and all(candidate.get("checks", {}).get(value) is True for value in ("C_BAG_PAIR_DEQUEUE", "C_RDAG_ELIGIBILITY_READ_REQUEST", "C_WR_PREPARED_SECOND_BEAT", "C_CHANNEL1_OUTPUT_DELIVERY")),
        "hdl_parser_negatives": roundtrip.get("pass") is True and roundtrip.get("negative_controls", {}).get("all_fail_closed") is True,
        "frozen_functional_surface": family.get("numeric_workload_config_golden_repeated") is False and family.get("functional_rtl_changed") is False,
        "no_server_action": family.get("server_action") is False and build.get("server_action") is False,
        "epoch_ack": build.get("rule_change_epoch_id") == "20260810-first-fresh-extra-audit-v1" and build.get("first_fresh_after_change") is True and build.get("cheap_prebuild_aggregate_invocations") == 1 and build.get("final_zip_count") == 1,
    }
    errors = [key for key, value in checks.items() if value is not True]
    report = {
        "schema": "qlinearadd-node0007-tailround-queueflow-v52-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "sidecar": {"path": SIDECAR.relative_to(ROOT).as_posix(), "bytes": SIDECAR.stat().st_size, "sha256": sha(SIDECAR)},
        "current_rule_receipts_after_generation": current,
        "first_fresh_extra_audit": {"epoch_id": "20260810-first-fresh-extra-audit-v1", "contract_sha256": sha(LOCAL / "first_fresh_extra_audit/contract.json"), "validation_sha256": sha(LOCAL / "first_fresh_extra_audit/validation.json"), "candidate_coverage": "4/4", "upload_authorized": extra.get("upload_authorized")},
        "negative_controls": roundtrip.get("negative_controls"),
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "PASS",
            "runner_compile_finalizer": "PASS_EXACT_RUNNER_INPUT_OPEN_PLUS_SHARED_V2_RECEIPT_REUSE",
            "package_local_hdl": "PASS_EXACT_PREPROCESS_XMR_CLOSURE_THREE_NEGATIVES",
            "materialized_config": "RECORD_ONLY_BYTE_FROZEN_FROM_V51",
            "observer_canonical": "PASS_CHANGED_SURFACE_MULTI_INSTANCE_AND_BUDGET_FAIL_CLOSED",
            "return_result_conjunction": "PASS_LOCAL_CONTRACT_ONLY_DYNAMIC_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
        },
        "package_release": "PACKAGE_READY_NOT_RUN",
        "claim_boundary": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; isolated tail_round queue-flow only; host FP32 boundary stimulus is not producer evidence; no full-chain/E3/E4/E5 claim.",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(REPORT, report)
    print(json.dumps({"pass": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
