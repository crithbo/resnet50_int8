#!/usr/bin/env python3
"""Prepare and validate an exact prepublication snapshot for node0004 returns.

This helper never publishes a return ZIP and never performs cleanup.  It is
intended to run as the child of the finalization operational guard.  The
canonical server_post_sim_return.py publisher may run only after ``validate``
has bound the completed guard receipt to an unchanged source snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any


CONTROL_ARCHIVES = {
    "evidence/PREPUBLICATION_RETURN_ADMISSION_RECEIPT.json",
    "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
    "evidence/PREPUBLICATION_RETURN_CONJUNCTION.json",
}


class AdmissionError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(canonical(value))
    os.replace(temporary, path)


def digest_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AdmissionError(f"source is absent, non-file or symlink: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def safe_relative(label: str, raw: str) -> Path:
    pure = PurePosixPath(raw)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or "\\" in raw:
        raise AdmissionError(f"unsafe {label}: {raw}")
    return Path(*pure.parts)


def inside(root: Path, relative: Path) -> Path:
    raw_root = root
    if raw_root.is_symlink():
        raise AdmissionError(f"unsafe symlink source root: {raw_root}")
    root = raw_root.resolve(strict=True)
    if not root.is_dir():
        raise AdmissionError(f"unsafe source root: {root}")
    target = root.joinpath(relative)
    resolved = target.resolve(strict=True)
    if root != resolved and root not in resolved.parents:
        raise AdmissionError(f"source escapes root: {target}")
    return target


def runtime_roots() -> dict[str, Path]:
    required = {
        "attempt": "CODEX_ATTEMPT_ROOT",
        "package": "CODEX_PACKAGE_ROOT",
    }
    result: dict[str, Path] = {}
    for key, variable in required.items():
        raw = os.environ.get(variable)
        if not raw:
            raise AdmissionError(f"missing environment: {variable}")
        result[key] = Path(raw)
    return result


def load_request(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AdmissionError("request is absent or unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "server-post-sim-return-request-v1":
        raise AdmissionError("request schema differs")
    return value


def snapshot(request: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    roots = runtime_roots()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for entry in request.get("core_entries", []):
        archive = entry.get("archive")
        if archive in CONTROL_ARCHIVES:
            continue
        try:
            source_root = entry["source_root"]
            if source_root not in roots:
                raise AdmissionError(f"unsupported source_root: {source_root}")
            relative = safe_relative("entry source", entry["source"])
            source = inside(roots[source_root], relative)
            identity = digest_file(source)
            rows.append(
                {
                    "archive": archive,
                    "source_root": source_root,
                    "source": entry["source"],
                    "required": entry.get("required") is True,
                    **identity,
                }
            )
        except (OSError, KeyError, json.JSONDecodeError, AdmissionError) as error:
            if entry.get("required") is True:
                errors.append(f"{archive}: {type(error).__name__}: {error}")
    rows.sort(key=lambda item: (str(item["archive"]), str(item["source_root"]), str(item["source"])))
    return rows, errors


def identity(path: Path) -> dict[str, Any]:
    item = digest_file(path)
    return {"path": path.name, **item}


def prepare(args: argparse.Namespace) -> int:
    request = load_request(args.request)
    package_id = os.environ.get("CODEX_PACKAGE_ID", "")
    execution_id = os.environ.get("CODEX_EXECUTION_ID", "")
    attempt_id = os.environ.get("CODEX_ATTEMPT_ID", "")
    if not package_id or not execution_id or not attempt_id:
        raise AdmissionError("package/execution/attempt identity is incomplete")
    if request.get("package_id") != package_id:
        raise AdmissionError("request/package identity differs")
    sources, errors = snapshot(request)
    receipt = {
        "schema": "node0004-prepublication-return-admission-v1",
        "package_id": package_id,
        "execution_id": execution_id,
        "attempt_id": attempt_id,
        "pass": not errors,
        "publication_performed": False,
        "cleanup_performed": False,
        "request": identity(args.request),
        "source_snapshot": sources,
        "errors": errors,
        "claim_boundary": "Prepublication source identity only; no durable-return, cleanup or DUT-result claim.",
    }
    atomic(args.admission, receipt)
    return 0 if receipt["pass"] else 1


def guard_complete(guard: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    termination = guard.get("termination", {})
    if guard.get("pass") is not True:
        errors.append("guard is not a PASS receipt")
    if guard.get("phase") != "finalization":
        errors.append("guard phase is not finalization")
    if guard.get("process_fully_reaped") is not True:
        errors.append("guard process_fully_reaped is not true")
    if termination.get("process_tree_reaped") is not True:
        errors.append("guard termination did not reap the process tree")
    if termination.get("owned_pids_remaining"):
        errors.append("guard has owned PIDs remaining")
    if termination.get("owned_process_identities_remaining"):
        errors.append("guard has owned process identities remaining")
    if guard.get("child_exit") != 0:
        errors.append("prepublication child exit is nonzero")
    return not errors, errors


def validate(args: argparse.Namespace) -> int:
    request = load_request(args.request)
    admission = json.loads(args.admission.read_text(encoding="utf-8"))
    guard = json.loads(args.finalization_guard.read_text(encoding="utf-8"))
    package_id = os.environ.get("CODEX_PACKAGE_ID", "")
    execution_id = os.environ.get("CODEX_EXECUTION_ID", "")
    attempt_id = os.environ.get("CODEX_ATTEMPT_ID", "")
    errors: list[str] = []
    for document, label in ((admission, "admission"), (guard, "guard")):
        for key, expected in (("package_id", package_id), ("execution_id", execution_id), ("attempt_id", attempt_id)):
            if document.get(key) != expected:
                errors.append(f"{label} {key} differs")
    if admission.get("schema") != "node0004-prepublication-return-admission-v1" or admission.get("pass") is not True:
        errors.append("prepublication admission is not a PASS receipt")
    current, current_errors = snapshot(request)
    errors.extend(current_errors)
    if current != admission.get("source_snapshot"):
        errors.append("prepublication source snapshot drifted before publish")
    guard_ok, guard_errors = guard_complete(guard)
    errors.extend(guard_errors)
    result = {
        "schema": "node0004-prepublication-return-conjunction-v1",
        "package_id": package_id,
        "execution_id": execution_id,
        "attempt_id": attempt_id,
        "pass": not errors and guard_ok,
        "publication_authorized": not errors and guard_ok,
        "publication_performed": False,
        "admission": identity(args.admission),
        "finalization_guard": identity(args.finalization_guard),
        "source_snapshot": current,
        "all_mandatory_evidence_preexists_publish": not current_errors,
        "durable_or_cleanup_receipt_claimed": False,
        "errors": errors,
        "claim_boundary": "Completed finalization guard plus unchanged prepublication evidence only; no durable-return, cleanup or DUT-result claim.",
    }
    atomic(args.output, result)
    return 0 if result["pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--admission", type=Path, required=True)
    p.set_defaults(function=prepare)
    v = sub.add_parser("validate")
    v.add_argument("--request", type=Path, required=True)
    v.add_argument("--admission", type=Path, required=True)
    v.add_argument("--finalization-guard", type=Path, required=True)
    v.add_argument("--output", type=Path, required=True)
    v.set_defaults(function=validate)
    args = parser.parse_args()
    try:
        return int(args.function(args))
    except (OSError, json.JSONDecodeError, AdmissionError) as error:
        print(f"PREPUBLICATION_RETURN_ERROR {type(error).__name__}: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
