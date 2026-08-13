"""Post-generation current-rule audit for exact isolated tail_round v50 ZIP."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_split_v50"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-v50-package"
ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
RECEIPTS = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007" / NAME
SIDECAR = RECEIPTS / f"{NAME}.zip.sha256"
FAMILY = LOCAL / "family_validation.json"
SHARED = LOCAL / "shared_runtime_layout_validation.json"
BUILD = LOCAL / "build_receipt.json"
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


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    zip_sha = sha(ZIP)
    with zipfile.ZipFile(ZIP) as archive:
        crc = archive.testzip() is None
        roots = {name.split("/", 1)[0] for name in archive.namelist()}
        manifest = json.loads(archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
    current = {key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)} for key, path in RULES.items()}
    package_rules = {key: {"path": current[key]["path"], "sha256": current[key]["sha256"], "current_match": True} for key in ("generation_index", "server", "common_config", "ndp_fields", "qlinearadd", "exact_uint8_tail")}
    hdl_neg = family["hdl_scope_revalidation"]["negative_controls"]
    config_neg = family["config_negative_controls"]
    sidecar_line = SIDECAR.read_text(encoding="ascii").strip()
    checks = {
        "final_pending_zip_crc_root": ZIP.is_file() and crc and roots == {NAME},
        "sidecar_exact": sidecar_line == f"{zip_sha}  {ZIP.name}",
        "build_identity_unchanged_after_rotation": build["zip"]["sha256"] == zip_sha and build["zip"]["bytes"] == ZIP.stat().st_size and build["deterministic_double_build"] is True,
        "family_validation": family.get("valid") is True and family.get("errors") == [] and family["zip"]["sha256"] == zip_sha,
        "shared_runtime_layout": shared.get("pass") is True and shared.get("errors") == [] and shared["zip"]["sha256"] == zip_sha,
        "manifest_rule_current_match": manifest.get("rule_receipts") == package_rules,
        "honest_split_claim": manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX" and manifest.get("boundary_input_contract", {}).get("host_precomputed_internal_tensor") is True and manifest.get("boundary_input_contract", {}).get("producer_evidence_claimed") is False,
        "one_stage_28D_contract": manifest.get("split_segment_contract", {}).get("stage_names") == ["op_tail_round"] and manifest.get("split_segment_contract", {}).get("expected_output_count") == 28,
        "hdl_positive_and_negatives": all(family["checks"].get(key) is True for key in ("hdl_declaration_use_update_closure", "hdl_xmr_scope", "hdl_compatible_frontend", "hdl_three_negative_classes")) and hdl_neg.get("all_fail_closed") is True,
        "config_positive_and_negatives": family["checks"].get("config_colfix_and_negatives") is True and all(row.get("exit_code") != 0 and row.get("failed_closed") is True for row in config_neg.values()),
        "runner_canonical_runtime_preflight": all(family["checks"].get(key) is True for key in ("runner_bash_syntax", "package_python_syntax", "canonical_selftest_decimal_safe", "runtime_preflight_exact_package", "runner_error_visibility_unit")),
        "runtime_D_absent": family["checks"].get("runtime_D_initially_absent") is True,
        "no_server_action": family.get("server_action") is False and build.get("server_action") is False,
        "frozen_analysis": family.get("numeric_analysis_repeated") is False and family.get("workload_analysis_repeated") is False,
    }
    errors = [key for key, value in checks.items() if value is not True]
    negative_exit_codes = {f"hdl_{key}": value for key, value in hdl_neg.get("exit_codes", {}).items()}
    negative_exit_codes.update({f"config_{key}": value["exit_code"] for key, value in config_neg.items()})
    report = {
        "schema": "qlinearadd-node0007-tailround-split-v50-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "sidecar": {"path": SIDECAR.relative_to(ROOT).as_posix(), "bytes": SIDECAR.stat().st_size, "sha256": sha(SIDECAR)},
        "current_rule_receipts_after_generation": current,
        "applicable_rule_ids": [
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
            "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
        ],
        "negative_controls": {"exit_codes": negative_exit_codes, "all_fail_closed": all(value != 0 for value in negative_exit_codes.values())},
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "PASS",
            "runner_compile_finalizer": "PASS_CHANGED_SURFACE_PLUS_SHARED_V2_RECEIPT_REUSE",
            "package_local_hdl": "PASS",
            "materialized_config": "PASS_CHANGED_TAILROUND_COL_WINDOW",
            "observer_canonical": "PASS",
            "return_result_conjunction": "PASS_LOCAL_CONTRACT_ONLY_DYNAMIC_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
        },
        "claim_boundary": "PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; isolated tail_round natural terminal and stage-local 28D pending server return; no tail_mul producer, full-chain, E3, E4 or E5 claim",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(REPORT, report)
    print(json.dumps({"pass": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
