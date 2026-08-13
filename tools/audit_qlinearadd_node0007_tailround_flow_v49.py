"""Post-generation current-rule audit of the exact QAdd v49 ZIP."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_flow_v49"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-package"
ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SIDECAR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007" / NAME / f"{NAME}.zip.sha256"
FAMILY = OUT / "family_validation.json"
SHARED = OUT / "shared_runtime_layout_validation.json"
BUILD = OUT / "build_receipt.json"
REPORT = OUT / "final_zip_self_audit.json"
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
    family = json.loads(FAMILY.read_text(encoding="utf-8")); shared = json.loads(SHARED.read_text(encoding="utf-8")); build = json.loads(BUILD.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP) as archive:
        crc = archive.testzip() is None
        root = {name.split("/", 1)[0] for name in archive.namelist()} == {NAME}
        manifest = json.loads(archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
    zip_sha = sha(ZIP)
    sidecar_line = SIDECAR.read_text(encoding="ascii").strip()
    current = {key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)} for key, path in RULES.items()}
    package_rule_receipts = {key: {"path": current[key]["path"], "sha256": current[key]["sha256"]} for key in ("generation_index", "server", "common_config", "ndp_fields", "qlinearadd", "exact_uint8_tail")}
    checks = {
        "zip_exists_crc_root": ZIP.is_file() and crc and root,
        "sidecar_exact": sidecar_line == f"{zip_sha}  {ZIP.name}",
        "build_receipt_exact": build["zip"]["sha256"] == zip_sha and build["zip"]["bytes"] == ZIP.stat().st_size and build["deterministic_double_build"] is True,
        "family_validation": family.get("valid") is True and family.get("errors") == [] and family["zip"]["sha256"] == zip_sha,
        "shared_runtime_layout": shared.get("pass") is True and shared.get("errors") == [] and shared["zip"]["sha256"] == zip_sha,
        "manifest_rule_current_match": manifest.get("rule_receipts") == package_rule_receipts,
        "manifest_identity": manifest.get("install_name") == NAME,
        "negative_controls": family["hdl_scope_revalidation"]["negative_controls"]["all_fail_closed"] is True,
        "runner_fail_unit": family["runner_visibility_unit"]["pass"] is True and family["runner_visibility_unit"]["exit_code"] == 37,
        "runtime_D_absent": family["checks"]["runtime_D_absent"] is True,
        "predicate_and_qualified_progress": family["checks"]["canonical_qualified_only"] is True and family["checks"]["hdl_closure"] is True,
        "no_server_action": family.get("server_action") is False and build.get("server_action") is False,
        "frozen_semantics": build.get("runtime_diagnostic_functional_timeout_frozen") is True and build.get("numeric_workload_config_golden_repeated") is False,
    }
    errors = [key for key, value in checks.items() if value is not True]
    negative_exit_codes = family["hdl_scope_revalidation"]["negative_controls"]["exit_codes"]
    release_gate_matrix = {
        "package_bootstrap_path_runtime_D": "PASS",
        "runner_compile_finalizer": "PASS",
        "package_local_hdl": "PASS",
        "materialized_config": "NOT_APPLICABLE_FROZEN_BYTE_EQUIVALENT",
        "observer_canonical": "PASS",
        "return_result_conjunction": "PASS_LOCAL_CONTRACT_ONLY_DYNAMIC_PENDING",
        "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
        "functional_RTL": "RECORD_ONLY_UNMODIFIED",
    }
    report = {
        "schema": "qadd-tailround-flow-v49-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "sidecar": {"path": SIDECAR.relative_to(ROOT).as_posix(), "bytes": SIDECAR.stat().st_size, "sha256": sha(SIDECAR)},
        "current_rule_receipts_after_generation": current,
        "applicable_rule_ids": [
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001", "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001", "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001", "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001", "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001", "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001", "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001", "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001", "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001", "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001", "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001", "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001", "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001", "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001", "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001", "CDA-SERVER-RESULT-GATE-CONJUNCTION-001", "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001", "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001", "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001", "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001", "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001", "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001", "CDA-QADD-FIRST-REQUEST-HANG-INTERNAL-READY-OBSERVABILITY-001", "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"
        ],
        "negative_controls": {"exit_codes": negative_exit_codes, "all_fail_closed": all(value != 0 for value in negative_exit_codes.values())},
        "release_gate_matrix": release_gate_matrix,
        "claim_boundary": "PACKAGE_READY_NOT_RUN / E2 local exact-ZIP diagnostics only; no DUT rerun, natural terminal, formal 28D, E3, E4 or E5",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(REPORT, report)
    print(json.dumps({"pass": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
