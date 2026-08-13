#!/usr/bin/env python3
"""Validate the Requant 54-stage exact-scope family-set-only migration."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_complete_operator_json_family_set import audit_family_set

ARTIFACT_ROOT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "requantize_uint8"
)
FAMILY_SET = ARTIFACT_ROOT / "family_set.json"
LOWERING = ROOT / "contracts" / "resnet50_r5_lowering_bundle.json"
AUTHORITY = (
    ROOT
    / "contracts"
    / "operator_config"
    / "operator_config_authority_v1.json"
)
POLICY = (
    ROOT
    / "contracts"
    / "operator_config"
    / "complete_json_generation_contract_v1.json"
)
SCHEMA = (
    ROOT / "schemas" / "operator_config_complete_json_family_set_v1.schema.json"
)
AUDITOR = ROOT / "tools" / "audit_complete_operator_json_family_set.py"
OUTPUT_ROOT = ARTIFACT_ROOT / "validation" / "exact_stage_scope"
AUDIT_REPORT = OUTPUT_ROOT / "family_set_audit.json"
MIGRATION_REPORT = OUTPUT_ROOT / "report.json"

EXPECTED_SCHEMA_SHA256 = (
    "bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18"
)
EXPECTED_AUDITOR_SHA256 = (
    "3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1"
)
EXPECTED_LOWERING_SHA256 = (
    "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
)
EXPECTED_FROZEN_TREE_SHA256 = (
    "12d225cd9df45bc489b923b91c2b38ab55de4a644f6860751f5c6e32a841ed48"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _frozen_files() -> list[Path]:
    paths = sorted(
        path for path in (ARTIFACT_ROOT / "candidates").rglob("*") if path.is_file()
    )
    paths.extend(
        ARTIFACT_ROOT / relative
        for relative in (
            "field_provenance_ledger.json",
            "reference_applicability.json",
            "handler_capability.json",
            "current_test_diff.json",
            "stage_inventory.json",
            "complete_json/index.json",
        )
    )
    paths.extend(
        sorted(
            (ARTIFACT_ROOT / "validation" / "public_gate").glob(
                "*.candidate_validation.json"
            )
        )
    )
    return sorted(paths)


def _frozen_tree_receipt() -> dict[str, Any]:
    rows = []
    for path in _frozen_files():
        rows.append(
            {
                "path": path.relative_to(ARTIFACT_ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    canonical = "".join(
        f"{row['path']}\0{row['size']}\0{row['sha256']}\n" for row in rows
    ).encode()
    return {
        "file_count": len(rows),
        "byte_count": sum(row["size"] for row in rows),
        "tree_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "pass": passed, "detail": detail})

    schema_sha = _sha256(SCHEMA)
    auditor_sha = _sha256(AUDITOR)
    lowering_sha = _sha256(LOWERING)
    manifest_sha = _sha256(FAMILY_SET)
    check("current_schema_identity", schema_sha == EXPECTED_SCHEMA_SHA256, schema_sha)
    check("current_auditor_identity", auditor_sha == EXPECTED_AUDITOR_SHA256, auditor_sha)
    check("lowering_identity", lowering_sha == EXPECTED_LOWERING_SHA256, lowering_sha)

    lowering = _load(LOWERING)
    expected_ids = [
        request["identity"]["hw_op_id"]
        for request in lowering["requests"]
        if request["identity"]["hw_op_type"] == "RequantizeUint8"
    ]
    manifest = _load(FAMILY_SET)
    scope = manifest.get("family_scope", {})
    check(
        "scope_mode",
        scope.get("mode") == "PINNED_EXACT_STAGE_IDS",
        scope.get("mode"),
    )
    check(
        "scope_lowering_sha",
        scope.get("lowering_sha256") == lowering_sha,
        scope.get("lowering_sha256"),
    )
    check(
        "ordered_exact_stage_ids",
        scope.get("expected_stage_ids") == expected_ids,
        {
            "expected_count": len(expected_ids),
            "declared_count": len(scope.get("expected_stage_ids", [])),
        },
    )
    check(
        "target_hw_op_types",
        manifest.get("target_hw_op_types") == ["RequantizeUint8"],
        manifest.get("target_hw_op_types"),
    )

    frozen = _frozen_tree_receipt()
    check(
        "frozen_candidate_and_evidence_tree",
        frozen["tree_sha256"] == EXPECTED_FROZEN_TREE_SHA256,
        frozen,
    )

    audit = audit_family_set(
        workspace_root=ROOT,
        manifest_path=FAMILY_SET,
        authority_path=AUTHORITY,
        policy_path=POLICY,
        lowering_path=LOWERING,
    )
    _write(AUDIT_REPORT, audit)

    exact_receipts = audit.get("exact_scope_receipts", [])
    exact_receipts_valid = (
        len(exact_receipts) == 54
        and [item["stage_id"] for item in exact_receipts] == expected_ids
        and all(item.get("present") is True for item in exact_receipts)
        and all(item.get("hw_op_type") == "RequantizeUint8" for item in exact_receipts)
    )
    check("audit_exact_scope_receipts", exact_receipts_valid, len(exact_receipts))
    check(
        "audit_coverage",
        audit.get("scope_mode") == "PINNED_EXACT_STAGE_IDS"
        and audit.get("expected_stage_count") == 54
        and audit.get("covered_stage_count") == 54
        and audit.get("missing_stage_ids") == []
        and audit.get("unexpected_stage_ids") == [],
        {
            "scope_mode": audit.get("scope_mode"),
            "expected": audit.get("expected_stage_count"),
            "covered": audit.get("covered_stage_count"),
            "missing": audit.get("missing_stage_ids"),
            "unexpected": audit.get("unexpected_stage_ids"),
        },
    )

    candidate_reports = audit.get("candidate_reports", [])
    candidate_blocked_valid = (
        len(candidate_reports) == 54
        and all(report.get("pass") is False for report in candidate_reports)
        and all(report.get("contract_valid") is True for report in candidate_reports)
        and all(report.get("blocked_valid") is True for report in candidate_reports)
        and all(report.get("errors") == [] for report in candidate_reports)
        and all(bool(report.get("completion_blockers")) for report in candidate_reports)
    )
    check("frozen_candidate_blocked_status", candidate_blocked_valid, len(candidate_reports))

    expected_failure_prefix = (
        "candidate contract did not pass complete-JSON validation: "
    )
    audit_errors = audit.get("errors", [])
    nonblocked_errors = [
        error for error in audit_errors if not error.startswith(expected_failure_prefix)
    ]
    check(
        "only_54_legal_blocked_failures",
        len(audit_errors) == 54 and not nonblocked_errors,
        {
            "audit_error_count": len(audit_errors),
            "nonblocked_error_count": len(nonblocked_errors),
            "nonblocked_errors": nonblocked_errors,
        },
    )

    frozen_after = _frozen_tree_receipt()
    check("frozen_tree_stable_during_audit", frozen_after == frozen, frozen_after)
    passed = all(item["pass"] for item in checks)
    report = {
        "schema": "requant-exact-stage-scope-migration-report-v1",
        "status": "BLOCKED_FAIL_CLOSED" if passed else "MIGRATION_VALIDATION_FAILED",
        "family": "requantize_uint8",
        "receipts": {
            "family_set": {
                "path": FAMILY_SET.relative_to(ROOT).as_posix(),
                "sha256": manifest_sha,
            },
            "lowering": {
                "path": LOWERING.relative_to(ROOT).as_posix(),
                "sha256": lowering_sha,
            },
            "schema": {
                "path": SCHEMA.relative_to(ROOT).as_posix(),
                "sha256": schema_sha,
            },
            "auditor": {
                "path": AUDITOR.relative_to(ROOT).as_posix(),
                "sha256": auditor_sha,
            },
            "family_audit": {
                "path": AUDIT_REPORT.relative_to(ROOT).as_posix(),
                "sha256": _sha256(AUDIT_REPORT),
            },
        },
        "scope": {
            "mode": audit.get("scope_mode"),
            "expected_stage_ids": expected_ids,
            "expected_stage_count": audit.get("expected_stage_count"),
            "covered_stage_count": audit.get("covered_stage_count"),
            "missing_stage_ids": audit.get("missing_stage_ids"),
            "unexpected_stage_ids": audit.get("unexpected_stage_ids"),
            "expected_hw_op_type_counts": audit.get("expected_hw_op_type_counts"),
        },
        "candidate_status": {
            "count": len(candidate_reports),
            "contract_valid_count": sum(
                report.get("contract_valid") is True for report in candidate_reports
            ),
            "blocked_valid_count": sum(
                report.get("blocked_valid") is True for report in candidate_reports
            ),
            "complete_pass_count": sum(
                report.get("pass") is True for report in candidate_reports
            ),
            "candidate_error_count": sum(
                len(report.get("errors", [])) for report in candidate_reports
            ),
            "family_audit_error_count": len(audit_errors),
            "nonblocked_family_audit_error_count": len(nonblocked_errors),
            "overall_family_audit_pass": audit.get("pass"),
            "overall_failure_semantics": (
                "Exactly one legal non-COMPLETE fail-closed finding for each of "
                "54 frozen BLOCKED candidate contracts."
            ),
        },
        "frozen_assertion": {
            "before": frozen,
            "after": frozen_after,
            "byte_identical": frozen_after == frozen,
            "candidate_contracts_ledgers_blocked_status_current_diff_unchanged": passed,
        },
        "checks": checks,
        "errors": [item for item in checks if not item["pass"]],
        "claim_boundary": {
            "family_set_scope_only": True,
            "candidate_assets_modified": False,
            "mapping_bitstream_execplan_sca": False,
            "server_package_or_action": False,
            "functional_rtl": False,
            "e4": False,
            "e5": False,
        },
        "package_release": "NONE",
    }
    _write(MIGRATION_REPORT, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
