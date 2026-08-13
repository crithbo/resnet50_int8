#!/usr/bin/env python3
"""Audit candidate-to-observation coverage of current pending ZIPs read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(source_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    storage_path = (
        source_root
        / "artifacts/operator_config_validation/r5-server-test-packages"
        / "PACKAGE_STORAGE_INDEX.json"
    )
    storage = json.loads(storage_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if sha256_file(storage_path) != contract["source_state"][
        "storage_index_sha256"
    ]:
        errors.append("storage index drifted from contract")
    pending = {
        item.get("family"): item
        for item in storage.get("packages", [])
        if isinstance(item, dict) and item.get("disposition") == "pending"
    }
    family_reports: list[dict[str, Any]] = []
    for package in contract.get("packages", []):
        family = package["family"]
        package_base = package["package_base"]
        family_errors: list[str] = []
        current = pending.get(family)
        if not current or current.get("package_base") != package_base:
            family_errors.append("not the unique current pending package")
        zip_path = (
            storage_path.parent / "pending" / f"{package_base}.zip"
        )
        if not zip_path.is_file():
            family_errors.append("exact ZIP is absent")
            zip_sha = ""
        else:
            zip_sha = sha256_file(zip_path)
            if zip_sha != package["zip_sha256"]:
                family_errors.append("exact ZIP SHA mismatch")
        record_path = source_root / package["task_record"]
        if not record_path.is_file():
            family_errors.append("task record is absent")
            record_text = ""
            record_sha = ""
        else:
            record_text = record_path.read_text(
                encoding="utf-8", errors="replace"
            )
            record_sha = sha256_file(record_path)
            if record_sha != package["task_record_sha256"]:
                family_errors.append("task record SHA mismatch")
            if package_base not in record_text:
                family_errors.append("task record does not bind package base")
        evidence_text = record_text
        member_receipts = []
        if zip_path.is_file():
            with zipfile.ZipFile(zip_path, "r") as archive:
                names = set(archive.namelist())
                for member in package.get("evidence_members", []):
                    if member not in names:
                        family_errors.append(f"evidence member missing: {member}")
                        continue
                    data = archive.read(member)
                    evidence_text += "\n" + data.decode("utf-8", errors="replace")
                    member_receipts.append(
                        {
                            "path": member,
                            "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    )
        candidate_reports = []
        signatures: set[tuple[tuple[str, ...], str]] = set()
        for candidate in package.get("candidates", []):
            missing_tokens = [
                token
                for token in candidate.get("evidence_tokens", [])
                if token not in evidence_text
            ]
            boundaries = candidate.get("distinguished_by", [])
            decision = candidate.get("decision", "")
            if not boundaries:
                family_errors.append(
                    f"{candidate.get('candidate_id')}: no observation boundary"
                )
            if not decision:
                family_errors.append(
                    f"{candidate.get('candidate_id')}: no decision"
                )
            signature = (tuple(sorted(boundaries)), decision)
            if signature in signatures:
                family_errors.append(
                    f"{candidate.get('candidate_id')}: duplicate decision signature"
                )
            signatures.add(signature)
            if missing_tokens:
                family_errors.append(
                    f"{candidate.get('candidate_id')}: evidence tokens missing "
                    f"{missing_tokens}"
                )
            candidate_reports.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "distinguished_by": boundaries,
                    "decision": decision,
                    "evidence_tokens": candidate.get("evidence_tokens", []),
                    "missing_evidence_tokens": missing_tokens,
                    "covered": bool(boundaries and decision and not missing_tokens),
                }
            )
        family_reports.append(
            {
                "family": family,
                "package_base": package_base,
                "scope": package.get("scope"),
                "zip_sha256": zip_sha,
                "task_record_sha256": record_sha,
                "evidence_member_receipts": member_receipts,
                "candidate_count": len(candidate_reports),
                "covered_candidate_count": sum(
                    item["covered"] for item in candidate_reports
                ),
                "candidates": candidate_reports,
                "deferred_after_this_return": package.get(
                    "deferred_after_this_return", []
                ),
                "one_return_complete_for_declared_scope": not family_errors,
                "errors": family_errors,
            }
        )
        errors.extend(f"{family}: {value}" for value in family_errors)
    return {
        "schema": "current-pending-one-return-matrix-audit-v1",
        "pass": not errors,
        "storage_index": {
            "path": storage_path.resolve().as_posix(),
            "bytes": storage_path.stat().st_size,
            "sha256": sha256_file(storage_path),
        },
        "serialized_conv_v60_disposition": contract["source_state"][
            "serialized_conv_v60_disposition"
        ],
        "families": family_reports,
        "errors": errors,
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    report = audit(args.source_root.resolve(), contract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "families": len(report["families"]),
                "errors": len(report["errors"]),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
