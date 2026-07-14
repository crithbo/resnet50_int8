from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import ContractError


LEGACY16_METADATA = {
    "target_family": "legacy16",
    "slice_count": 16,
    "status": "superseded_by_adr_007",
    "superseded_by": "ADR-007",
    "current_gate_eligible": False,
}
CURRENT_TARGET_FAMILY = "rtl28"
CURRENT_SLICE_COUNT = 28


def add_legacy16_cli_guard(parser: Any) -> None:
    parser.add_argument(
        "--legacy16",
        action="store_true",
        required=True,
        help=(
            "Required acknowledgement that this command regenerates superseded "
            "16-slice diagnostic evidence, never current RTL28 evidence"
        ),
    )


def annotate_legacy16_report(report: dict[str, Any]) -> dict[str, Any]:
    for field, expected in LEGACY16_METADATA.items():
        actual = report.get(field, expected)
        if field == "status" and actual in {
            "candidate",
            "candidate_software_evidence",
        }:
            report.setdefault("legacy_generation_status", actual)
            actual = expected
        if actual != expected:
            raise ContractError(
                f"legacy16 report metadata {field} must be {expected!r}, got {actual!r}"
            )
        report[field] = expected
    return report


def resolve_legacy16_output(
    project_root: Path, output: Path | None
) -> Path | None:
    if output is None:
        return None
    root = project_root.resolve()
    path = output if output.is_absolute() else root / output
    path = path.resolve()
    namespace = (root / "artifacts/w4/legacy16").resolve()
    try:
        path.relative_to(namespace)
    except ValueError as error:
        raise ContractError(
            "legacy16 tools may only write below artifacts/w4/legacy16; "
            "registered historical snapshots are immutable"
        ) from error
    return path


def canonical_json_bytes(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def architecture_evidence_basis_sha256(architecture: dict[str, Any]) -> str:
    """Hash architecture semantics without self-referential current evidence.

    Current, gate-eligible software evidence records contain their own content
    hashes and paths.  Excluding only those records gives them a stable basis
    digest while keeping target geometry, profiles, layouts, legacy locks, and
    gate-ineligible RTL evidence inside the hash boundary.
    """

    if not isinstance(architecture, dict):
        raise ContractError("architecture evidence basis must be an object")
    basis = json.loads(json.dumps(architecture))
    candidate_evidence = basis.get("candidate_evidence")
    if not isinstance(candidate_evidence, dict):
        raise ContractError("architecture candidate_evidence must be an object")
    basis["candidate_evidence"] = {
        evidence_id: record
        for evidence_id, record in candidate_evidence.items()
        if not isinstance(record, dict)
        or record.get("current_gate_eligible") is not True
    }
    return hashlib.sha256(canonical_json_bytes(basis)).hexdigest()


def current_evidence_path(
    project_root: Path,
    architecture_sha256: str,
    evidence_kind: str,
    payload: bytes,
) -> Path:
    if len(architecture_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in architecture_sha256
    ):
        raise ContractError("architecture_sha256 must be lowercase SHA-256")
    if not evidence_kind or any(
        not (character.islower() or character.isdigit() or character in "_-")
        for character in evidence_kind
    ):
        raise ContractError(
            "evidence_kind must contain only lowercase letters, digits, '_' or '-'"
        )
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    return (
        project_root.resolve()
        / "artifacts/w4/rtl28"
        / architecture_sha256
        / f"{evidence_kind}-{payload_sha256}.json"
    )


def resolve_current_output(
    project_root: Path,
    requested: Path | None,
    expected: Path,
    write_current_evidence: bool,
) -> Path | None:
    if requested is not None and write_current_evidence:
        raise ContractError("choose either --output or --write-current-evidence")
    if write_current_evidence:
        return expected
    if requested is None:
        return None
    root = project_root.resolve()
    path = requested if requested.is_absolute() else root / requested
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return path
    if path != expected.resolve():
        raise ContractError(
            "current in-repository W4 evidence must use the content-addressed RTL28 "
            f"path {expected.relative_to(root).as_posix()}"
        )
    return path
