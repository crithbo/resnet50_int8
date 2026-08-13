#!/usr/bin/env python3
"""Validate the one-time independent audit for a first fresh package.

The validator is intentionally package-family agnostic.  It consumes only
the exact final ZIP receipt plus independently generated report receipts.  It
never builds a package, changes storage state, or runs a server simulation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HEX64 = set("0123456789abcdef")
CAUSAL_CLASSES = {"server_start", "actual_input", "state_safety", "return"}
REQUIRED_REPORTS = {
    "exact_final_zip_clean_extract": "exact-final-zip-clean-extract",
    "actual_runner_entry_and_input_open": "exact-runner-safe-compile-and-open-paths",
    "source_bound_logger_collector_parser_roundtrip": (
        "exact-generated-over-budget-multi-instance"
    ),
    "post_sim_return_core_scenarios": "exact-final-request-four-scenario",
    "candidate_discrimination_matrix": "exact-candidate-positive-negative-matrix",
}
STRICT_DIAGNOSTIC_RULE_IDS = {
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in HEX64 for character in value)
    )


def check_exact_keys(
    value: dict[str, Any],
    allowed: set[str],
    required: set[str],
    label: str,
    errors: list[str],
) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        errors.append(f"{label}: unknown fields: {unknown}")
    if missing:
        errors.append(f"{label}: missing fields: {missing}")


def resolve_workspace_file(
    relative: Any, workspace: Path, errors: list[str], label: str
) -> Path | None:
    if not isinstance(relative, str) or not relative:
        errors.append(f"{label}: path must be a non-empty relative string")
        return None
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes workspace: {relative}")
        return None
    if not candidate.is_file():
        errors.append(f"{label}: file is missing: {relative}")
        return None
    return candidate


def validate_zip(path: Path, errors: list[str]) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if not names:
                errors.append("final_zip: ZIP is empty")
                return
            if len(names) != len(set(names)):
                errors.append("final_zip: duplicate ZIP members")
            roots: set[str] = set()
            for name in names:
                normalized = name.replace("\\", "/")
                member = PurePosixPath(normalized)
                if member.is_absolute() or ".." in member.parts:
                    errors.append(f"final_zip: unsafe member path: {name}")
                    continue
                if member.parts:
                    roots.add(member.parts[0])
            if len(roots) != 1:
                errors.append(f"final_zip: expected one root, found {sorted(roots)}")
            corrupt = archive.testzip()
            if corrupt is not None:
                errors.append(f"final_zip: CRC failure: {corrupt}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"final_zip: unreadable ZIP: {exc}")


def validate_contract(contract: dict[str, Any], workspace: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    report_receipts: list[dict[str, Any]] = []

    if contract.get("schema") != "server-first-fresh-extra-audit-v1":
        errors.append("schema mismatch")
    check_exact_keys(
        contract,
        {
            "schema",
            "package",
            "rule_change",
            "independent_reaudit",
            "diagnostic_semantics",
            "evidence_reports",
            "candidate_discrimination",
            "findings",
        },
        {
            "schema",
            "package",
            "rule_change",
            "independent_reaudit",
            "evidence_reports",
            "candidate_discrimination",
            "findings",
        },
        "contract",
        errors,
    )

    package = contract.get("package")
    if not isinstance(package, dict):
        errors.append("package must be an object")
        package = {}
    check_exact_keys(
        package,
        {"package_id", "family", "final_zip"},
        {"package_id", "family", "final_zip"},
        "package",
        errors,
    )
    package_id = package.get("package_id")
    family = package.get("family")
    if not isinstance(package_id, str) or not package_id:
        errors.append("package.package_id must be non-empty")
    if not isinstance(family, str) or not family:
        errors.append("package.family must be non-empty")
    final_zip = package.get("final_zip")
    if not isinstance(final_zip, dict):
        errors.append("package.final_zip must be an object")
        final_zip = {}
    check_exact_keys(
        final_zip,
        {"path", "bytes", "sha256"},
        {"path", "bytes", "sha256"},
        "package.final_zip",
        errors,
    )
    final_path = resolve_workspace_file(
        final_zip.get("path"), workspace, errors, "final_zip"
    )
    if final_path is not None:
        if final_zip.get("bytes") != final_path.stat().st_size:
            errors.append("final_zip: byte count mismatch")
        actual_zip_sha = sha256_file(final_path)
        if final_zip.get("sha256") != actual_zip_sha:
            errors.append("final_zip: sha256 mismatch")
        validate_zip(final_path, errors)
    if not is_sha256(final_zip.get("sha256")):
        errors.append("final_zip: declared sha256 is invalid")

    rule_change = contract.get("rule_change")
    if not isinstance(rule_change, dict):
        errors.append("rule_change must be an object")
        rule_change = {}
    check_exact_keys(
        rule_change,
        {
            "epoch_id",
            "rule_ids",
            "first_fresh_for_family",
            "notification_acknowledged",
        },
        {
            "epoch_id",
            "rule_ids",
            "first_fresh_for_family",
            "notification_acknowledged",
        },
        "rule_change",
        errors,
    )
    epoch_id = rule_change.get("epoch_id")
    if not isinstance(epoch_id, str) or not epoch_id:
        errors.append("rule_change.epoch_id must be non-empty")
    rule_ids = rule_change.get("rule_ids")
    if not isinstance(rule_ids, list) or not rule_ids:
        errors.append("rule_change.rule_ids must be non-empty")
    elif len(rule_ids) != len(set(rule_ids)):
        errors.append("rule_change.rule_ids contains duplicates")
    if rule_change.get("first_fresh_for_family") is not True:
        errors.append("first_fresh_for_family must be true")
    if rule_change.get("notification_acknowledged") is not True:
        errors.append("notification_acknowledged must be true")

    diagnostic_receipt: dict[str, Any] | None = None
    strict_diagnostic = isinstance(rule_ids, list) and bool(
        set(rule_ids) & STRICT_DIAGNOSTIC_RULE_IDS
    )
    diagnostic = contract.get("diagnostic_semantics")
    if strict_diagnostic and not isinstance(diagnostic, dict):
        errors.append(
            "diagnostic_semantics is required for exact-instance/payload rules"
        )
        diagnostic = {}
    if isinstance(diagnostic, dict):
        diagnostic_fields = {
            "fingerprint_sha256",
            "final_zip_report_path",
            "final_zip_report_sha256",
            "prior_fingerprint_sha256",
            "disposition",
            "prior_audit_receipt",
        }
        check_exact_keys(
            diagnostic,
            diagnostic_fields,
            diagnostic_fields,
            "diagnostic_semantics",
            errors,
        )
        fingerprint = diagnostic.get("fingerprint_sha256")
        prior_fingerprint = diagnostic.get("prior_fingerprint_sha256")
        disposition = diagnostic.get("disposition")
        if not is_sha256(fingerprint):
            errors.append("diagnostic_semantics fingerprint is invalid")
        if prior_fingerprint is not None and not is_sha256(prior_fingerprint):
            errors.append("diagnostic_semantics prior fingerprint is invalid")
        semantics_changed = prior_fingerprint != fingerprint
        if semantics_changed and disposition != "FIRST_USE_AUDITED":
            errors.append(
                "changed diagnostic semantics require FIRST_USE_AUDITED"
            )
        if not semantics_changed and disposition not in {
            "FIRST_USE_AUDITED",
            "BYTE_EQUAL_RECEIPT_REUSE",
        }:
            errors.append("unchanged diagnostic semantics disposition is invalid")

        report_path = resolve_workspace_file(
            diagnostic.get("final_zip_report_path"),
            workspace,
            errors,
            "diagnostic_semantics.final_zip_report",
        )
        if report_path is not None:
            report_sha = sha256_file(report_path)
            if diagnostic.get("final_zip_report_sha256") != report_sha:
                errors.append("diagnostic semantics final-ZIP report SHA mismatch")
            try:
                report = load_json(report_path)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"diagnostic semantics report is unreadable: {exc}")
                report = {}
            if report.get("schema") != "server-source-bound-final-zip-validation-v2":
                errors.append("diagnostic semantics report schema is not typed v2")
            if report.get("pass") is not True:
                errors.append("diagnostic semantics final-ZIP report did not pass")
            if report.get("diagnostic_semantics_sha256") != fingerprint:
                errors.append("diagnostic semantics fingerprint/report mismatch")
            if report.get("zip", {}).get("sha256") != final_zip.get("sha256"):
                errors.append("diagnostic semantics report is bound to another ZIP")
            controls = report.get("semantic_controls", {})
            if controls.get("pass") is not True:
                errors.append("diagnostic semantic controls did not pass")
            if controls.get("diagnostic_semantics_sha256") != fingerprint:
                errors.append("semantic controls fingerprint mismatch")
            diagnostic_receipt = {
                "fingerprint_sha256": fingerprint,
                "prior_fingerprint_sha256": prior_fingerprint,
                "semantics_changed": semantics_changed,
                "disposition": disposition,
                "final_zip_report_path": diagnostic.get("final_zip_report_path"),
                "final_zip_report_sha256": report_sha,
                "semantic_control_case_count": controls.get("case_count", 0),
            }

        prior_receipt = diagnostic.get("prior_audit_receipt")
        if disposition == "BYTE_EQUAL_RECEIPT_REUSE":
            if semantics_changed:
                errors.append("changed diagnostic semantics cannot reuse a receipt")
            if not isinstance(prior_receipt, dict):
                errors.append("byte-equal semantic reuse requires a prior audit receipt")
            else:
                prior_path = resolve_workspace_file(
                    prior_receipt.get("path"),
                    workspace,
                    errors,
                    "diagnostic_semantics.prior_audit_receipt",
                )
                if prior_path is not None:
                    prior_sha = sha256_file(prior_path)
                    if prior_receipt.get("sha256") != prior_sha:
                        errors.append("prior diagnostic audit receipt SHA mismatch")
                    try:
                        prior_report = load_json(prior_path)
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"prior diagnostic audit receipt unreadable: {exc}")
                        prior_report = {}
                    if prior_report.get("pass") is not True:
                        errors.append("prior diagnostic audit receipt did not pass")
                    if (
                        prior_report.get("diagnostic_semantics", {}).get(
                            "fingerprint_sha256"
                        )
                        != fingerprint
                    ):
                        errors.append("prior audit receipt fingerprint mismatch")
        elif prior_receipt is not None:
            errors.append("FIRST_USE_AUDITED must not provide a reused receipt")

    independent = contract.get("independent_reaudit")
    if not isinstance(independent, dict):
        errors.append("independent_reaudit must be an object")
        independent = {}
    required_independent = {
        "clean_extract_from_final_zip": True,
        "from_final_zip_only": True,
        "family_build_reports_reused": False,
        "top_level_invocations": 1,
        "all_errors_collected": True,
        "rebuild_per_single_error_forbidden": True,
    }
    check_exact_keys(
        independent,
        set(required_independent),
        set(required_independent),
        "independent_reaudit",
        errors,
    )
    for field, expected in required_independent.items():
        if independent.get(field) != expected:
            errors.append(
                f"independent_reaudit.{field} must equal {expected!r}"
            )

    evidence = contract.get("evidence_reports")
    if not isinstance(evidence, list):
        errors.append("evidence_reports must be an array")
        evidence = []
    gate_ids = [
        item.get("gate_id") for item in evidence if isinstance(item, dict)
    ]
    duplicates = sorted(
        gate_id
        for gate_id, count in Counter(gate_ids).items()
        if gate_id is not None and count > 1
    )
    if duplicates:
        errors.append(f"duplicate evidence report gates: {duplicates}")
    missing = sorted(set(REQUIRED_REPORTS) - set(gate_ids))
    unexpected = sorted(set(gate_ids) - set(REQUIRED_REPORTS))
    if missing:
        errors.append(f"missing evidence report gates: {missing}")
    if unexpected:
        errors.append(f"unexpected evidence report gates: {unexpected}")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"evidence_reports[{index}] must be an object")
            continue
        check_exact_keys(
            item,
            {"gate_id", "evidence_kind", "path", "sha256"},
            {"gate_id", "evidence_kind", "path", "sha256"},
            f"evidence_reports[{index}]",
            errors,
        )
        gate_id = item.get("gate_id")
        expected_kind = REQUIRED_REPORTS.get(gate_id)
        if expected_kind is not None and item.get("evidence_kind") != expected_kind:
            errors.append(
                f"{gate_id}: evidence_kind must be {expected_kind}"
            )
        report_path = resolve_workspace_file(
            item.get("path"), workspace, errors, f"{gate_id}.report"
        )
        if report_path is None:
            continue
        actual_sha = sha256_file(report_path)
        if item.get("sha256") != actual_sha:
            errors.append(f"{gate_id}: report sha256 mismatch")
            continue
        try:
            report = load_json(report_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{gate_id}: report JSON is unreadable: {exc}")
            continue
        report_errors = report.get("errors")
        if not isinstance(report.get("pass"), bool):
            errors.append(f"{gate_id}: report pass must be boolean")
        if not isinstance(report_errors, list) or not all(
            isinstance(value, str) for value in report_errors
        ):
            errors.append(f"{gate_id}: report errors must be string array")
            report_errors = []
        if report.get("pass") is not True:
            errors.append(f"{gate_id}: report did not pass")
            errors.extend(f"{gate_id}: {message}" for message in report_errors)
        report_receipts.append(
            {
                "gate_id": gate_id,
                "path": item.get("path"),
                "sha256": actual_sha,
                "pass": report.get("pass"),
                "error_count": len(report_errors),
            }
        )

    discrimination = contract.get("candidate_discrimination")
    if not isinstance(discrimination, dict):
        errors.append("candidate_discrimination must be an object")
        discrimination = {}
    discrimination_fields = {
        "candidate_ids",
        "covered_candidate_ids",
        "uncovered_candidate_ids",
        "positive_control_count",
        "negative_control_count",
        "pairwise_distinguishable",
    }
    check_exact_keys(
        discrimination,
        discrimination_fields,
        discrimination_fields,
        "candidate_discrimination",
        errors,
    )
    candidates = discrimination.get("candidate_ids")
    covered = discrimination.get("covered_candidate_ids")
    uncovered = discrimination.get("uncovered_candidate_ids")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidate_ids must be a non-empty array")
        candidates = []
    if not isinstance(covered, list):
        errors.append("covered_candidate_ids must be an array")
        covered = []
    if not isinstance(uncovered, list):
        errors.append("uncovered_candidate_ids must be an array")
        uncovered = []
    for label, values in (
        ("candidate_ids", candidates),
        ("covered_candidate_ids", covered),
        ("uncovered_candidate_ids", uncovered),
    ):
        if len(values) != len(set(values)):
            errors.append(f"{label} contains duplicates")
    if set(covered) | set(uncovered) != set(candidates):
        errors.append("covered plus uncovered candidates must equal candidate_ids")
    if set(covered) & set(uncovered):
        errors.append("covered and uncovered candidates overlap")
    if uncovered:
        errors.append(f"candidate coverage is incomplete: {sorted(uncovered)}")
    for field in ("positive_control_count", "negative_control_count"):
        value = discrimination.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{field} must be a positive integer")
    if discrimination.get("pairwise_distinguishable") is not True:
        errors.append("candidate matrix is not pairwise distinguishable")

    findings = contract.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    blocking_findings = 0
    record_only_findings = 0
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"findings[{index}] must be an object")
            continue
        check_exact_keys(
            finding,
            {"finding_id", "disposition", "causal_class", "message"},
            {"finding_id", "disposition", "causal_class", "message"},
            f"findings[{index}]",
            errors,
        )
        disposition = finding.get("disposition")
        causal_class = finding.get("causal_class")
        if disposition == "blocking_applicable":
            blocking_findings += 1
            if causal_class not in CAUSAL_CLASSES:
                errors.append(
                    f"findings[{index}]: blocking finding lacks valid causal class"
                )
            else:
                errors.append(
                    f"blocking finding {finding.get('finding_id')}: "
                    f"{finding.get('message')}"
                )
        elif disposition == "record_only":
            record_only_findings += 1
            if causal_class is not None:
                errors.append(
                    f"findings[{index}]: record-only causal_class must be null"
                )
            warnings.append(
                f"record-only {finding.get('finding_id')}: {finding.get('message')}"
            )
        else:
            errors.append(f"findings[{index}]: invalid disposition")

    return {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "pass": not errors,
        "family": family or "",
        "package_id": package_id or "",
        "rule_change_epoch_id": epoch_id or "",
        "errors": errors,
        "warnings": warnings,
        "all_errors_collected": True,
        "report_receipts": report_receipts,
        "candidate_coverage": {
            "expected": len(candidates),
            "covered": len(covered),
            "uncovered": sorted(uncovered),
            "pairwise_distinguishable": (
                discrimination.get("pairwise_distinguishable") is True
            ),
        },
        "finding_counts": {
            "blocking_applicable": blocking_findings,
            "record_only": record_only_findings,
        },
        "diagnostic_semantics": diagnostic_receipt,
        "upload_authorized": not errors,
        "claim_boundary": {
            "changes_current_package": False,
            "builds_package": False,
            "runs_server": False,
            "claims_natural_terminal_or_formal_d": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate one first-fresh final-ZIP independent audit."
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    workspace = args.workspace_root.resolve()
    contract = load_json(args.contract.resolve())
    if not isinstance(contract, dict):
        raise SystemExit("contract root must be an object")
    result = validate_contract(contract, workspace)
    write_json(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "pass": result["pass"],
                "error_count": len(result["errors"]),
                "warning_count": len(result["warnings"]),
                "upload_authorized": result["upload_authorized"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
