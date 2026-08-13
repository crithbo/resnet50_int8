#!/usr/bin/env python3
"""Incrementally review large waveform returns and safely retain three raw versions.

The tool never interprets family semantics.  It binds immutable review chunks
to an exact return/waveform identity, atomically advances a small current index,
and stops accepting chunks after a unique-root or explicit inconclusive final.

Post-adjudication retention is separate from collection: the full raw waveform
must first arrive intact.  Retirement is allowed only for an exact regular ZIP
under a declared storage root, after family and mainline consumption, and only
when it is neither CURRENT, BASELINE nor CAUSAL.  Before unlinking the exact
heavy ZIP the tool builds a deterministic core-only ZIP containing every
non-waveform member plus a retirement manifest.  It never deletes directories,
reports, task records, packages, or an identity-mismatched file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


REVIEW_SCHEMA = "server-waveform-incremental-review-v1"
CHUNK_SCHEMA = "server-waveform-review-chunk-v1"
RETENTION_SCHEMA = "server-waveform-return-retention-v1"
RULE_ID = "CDA-SERVER-RETURN-WAVEFORM-INCREMENTAL-REVIEW-RETENTION-001"
PROTECTED_ROLES = {"CURRENT", "BASELINE", "CAUSAL"}
RAW_SUFFIXES = (".fsdb", ".vpd", ".vcd", ".fst")
TERMINAL_REVIEW_STATES = {"ROOT_CAUSE_UNIQUE_STOP", "INCONCLUSIVE_STOP"}


class ReviewError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def exclusive_write(path: Path, value: Any) -> None:
    """Create immutable evidence exactly once; never replace a racing writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(json_bytes(value))
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewError(f"cannot read JSON {path}: {type(error).__name__}: {error}") from error


def hash_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def hash_file(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        return hash_stream(stream)


def safe_zip(archive: zipfile.ZipFile) -> tuple[str, list[zipfile.ZipInfo]]:
    infos = archive.infolist()
    if not infos or archive.testzip() is not None:
        raise ReviewError("return ZIP is empty or fails CRC")
    names = [item.filename for item in infos]
    if len(names) != len(set(names)):
        raise ReviewError("return ZIP has duplicate member names")
    roots: set[str] = set()
    for info in infos:
        name = info.filename
        if "\\" in name:
            raise ReviewError(f"ZIP member contains backslash: {name}")
        path = PurePosixPath(name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ReviewError(f"unsafe ZIP member: {name}")
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise ReviewError(f"ZIP member is a symlink: {name}")
        roots.add(path.parts[0])
    if len(roots) != 1:
        raise ReviewError(f"return ZIP must have one root: {sorted(roots)}")
    return next(iter(roots)), infos


def is_raw_waveform(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(RAW_SUFFIXES) or any(f"{suffix}." in lower for suffix in RAW_SUFFIXES)


def inspect_return_zip(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReviewError("return ZIP must be an existing regular non-symlink file")
    size, digest = hash_file(path)
    waveforms: list[dict[str, Any]] = []
    non_waveform_members = 0
    with zipfile.ZipFile(path) as archive:
        root, infos = safe_zip(archive)
        for info in infos:
            if info.is_dir():
                continue
            if not is_raw_waveform(info.filename):
                non_waveform_members += 1
                continue
            with archive.open(info) as stream:
                member_size, member_sha = hash_stream(stream)
            waveforms.append(
                {"path": info.filename, "bytes": member_size, "sha256": member_sha}
            )
    return {
        "path": str(path.resolve()),
        "bytes": size,
        "sha256": digest,
        "zip_root": root,
        "waveforms": waveforms,
        "non_waveform_member_count": non_waveform_members,
    }


def init_review(
    *,
    family: str,
    track: str,
    return_id: str,
    return_zip: Path,
    review_dir: Path,
    candidates: list[str],
) -> dict[str, Any]:
    identity = inspect_return_zip(return_zip)
    if not identity["waveforms"]:
        raise ReviewError("return ZIP contains no raw waveform member")
    normalized_candidates = sorted(set(candidates))
    if not normalized_candidates or any(not isinstance(item, str) or not item for item in normalized_candidates):
        raise ReviewError("review requires a non-empty candidate set")
    identity_path = review_dir / "return_identity.json"
    index_path = review_dir / "review_index.json"
    if identity_path.exists() or index_path.exists():
        if not identity_path.is_file() or not index_path.is_file():
            raise ReviewError("review directory contains an incomplete immutable identity")
        existing_identity = read_json(identity_path)
        existing_index = read_json(index_path)
        stable_match = (
            existing_identity.get("family") == family
            and existing_identity.get("track") == track
            and existing_identity.get("return_id") == return_id
            and existing_identity.get("return_zip") == identity
            and existing_index.get("return_zip_sha256") == identity["sha256"]
        )
        if stable_match:
            return existing_index
        raise ReviewError("review directory is not fresh; immutable identity cannot be overwritten")
    identity_report = {
        "schema": REVIEW_SCHEMA,
        "kind": "return_identity",
        "rule_id": RULE_ID,
        "family": family,
        "track": track,
        "return_id": return_id,
        "return_zip": identity,
        "created_at": utc_now(),
        "claim_boundary": "Return and raw-waveform identity only; no signal or family diagnosis.",
    }
    index = {
        "schema": REVIEW_SCHEMA,
        "kind": "review_index",
        "rule_id": RULE_ID,
        "family": family,
        "track": track,
        "return_id": return_id,
        "return_zip_sha256": identity["sha256"],
        "review_revision": 0,
        "next_chunk_sequence": 1,
        "status": "IN_PROGRESS",
        "open_candidates": normalized_candidates,
        "closed_candidates": [],
        "chunks": [],
        "root_cause_unique": False,
        "stop_reason": None,
        "final_adjudication": None,
        "updated_at": identity_report["created_at"],
        "claim_boundary": "Rolling pointer only; immutable chunks and final adjudication carry evidence.",
    }
    exclusive_write(identity_path, identity_report)
    exclusive_write(index_path, index)
    return index


def _validate_chunk(chunk: dict[str, Any], identity: dict[str, Any], index: dict[str, Any]) -> None:
    required = {
        "schema",
        "expected_review_revision",
        "return_zip_sha256",
        "waveform_sha256",
        "analysis_tool",
        "query",
        "candidate_updates",
        "status",
        "finding",
        "last_proven_good",
        "first_divergence",
        "root_cause",
        "next_query",
        "unreviewed_scope",
        "claim_boundary",
    }
    missing = sorted(required - set(chunk))
    if missing:
        raise ReviewError(f"chunk misses fields: {missing}")
    if chunk["schema"] != CHUNK_SCHEMA:
        raise ReviewError("chunk schema mismatch")
    if chunk["expected_review_revision"] != index["review_revision"]:
        raise ReviewError("review revision conflict")
    if chunk["return_zip_sha256"] != identity["return_zip"]["sha256"]:
        raise ReviewError("chunk return ZIP identity mismatch")
    waveform_shas = {item["sha256"] for item in identity["return_zip"]["waveforms"]}
    if chunk["waveform_sha256"] not in waveform_shas:
        raise ReviewError("chunk waveform identity mismatch")
    query = chunk["query"]
    if query.get("no_sampling") is not True or query.get("no_truncation") is not True:
        raise ReviewError("selected signal/time query must preserve every transition in its declared window")
    if not isinstance(query.get("signals"), list) or not query["signals"]:
        raise ReviewError("chunk query requires a non-empty exact signal list")
    window = query.get("time_window")
    if not isinstance(window, dict) or not {"start", "end", "timescale"} <= set(window):
        raise ReviewError("chunk query requires an exact time window and timescale")
    if window["end"] < window["start"]:
        raise ReviewError("chunk time window is reversed")
    status = chunk["status"]
    if status not in {"EVIDENCE_ADDED", "QUERY_FAILED", "ROOT_CAUSE_UNIQUE"}:
        raise ReviewError(f"unsupported chunk status: {status}")
    updates = chunk["candidate_updates"]
    open_updates = updates.get("open")
    closed_updates = updates.get("closed")
    if (
        not isinstance(open_updates, list)
        or not isinstance(closed_updates, list)
        or any(not isinstance(item, str) or not item for item in open_updates + closed_updates)
    ):
        raise ReviewError("candidate updates must be non-empty-string arrays")
    if set(open_updates) & set(closed_updates):
        raise ReviewError("candidate cannot be both open and closed")
    if status == "ROOT_CAUSE_UNIQUE" and not closed_updates:
        raise ReviewError("unique root requires explicit closed alternatives")
    if set(open_updates) | set(closed_updates) != set(index["open_candidates"]):
        raise ReviewError("candidate update must account for every previously open candidate exactly once")
    if status == "ROOT_CAUSE_UNIQUE":
        if not chunk["root_cause"] or not chunk["last_proven_good"] or not chunk["first_divergence"]:
            raise ReviewError("unique root requires root cause, last proven good and first divergence")
        if updates.get("open"):
            raise ReviewError("unique root cannot retain open candidates")


def add_review_chunk(review_dir: Path, chunk_path: Path) -> dict[str, Any]:
    identity = read_json(review_dir / "return_identity.json")
    index_path = review_dir / "review_index.json"
    index = read_json(index_path)
    if index["status"] in TERMINAL_REVIEW_STATES:
        raise ReviewError("review is terminal; no further waveform chunks are accepted")
    chunk = read_json(chunk_path)
    _validate_chunk(chunk, identity, index)
    sequence = index["next_chunk_sequence"]
    stored = dict(chunk)
    stored["sequence"] = sequence
    stored["family"] = identity["family"]
    stored["track"] = identity["track"]
    stored["return_id"] = identity["return_id"]
    stored["recorded_at"] = utc_now()
    destination = review_dir / "chunks" / f"{sequence:06d}.json"
    if destination.exists():
        raise ReviewError(f"immutable chunk already exists: {destination}")
    try:
        exclusive_write(destination, stored)
    except FileExistsError as error:
        raise ReviewError(f"immutable chunk already exists: {destination}") from error
    chunk_bytes, chunk_sha = hash_file(destination)
    updates = stored["candidate_updates"]
    index["review_revision"] += 1
    index["next_chunk_sequence"] += 1
    index["open_candidates"] = sorted(set(updates.get("open", [])))
    index["closed_candidates"] = sorted(
        set(index["closed_candidates"]) | set(updates.get("closed", []))
    )
    index["chunks"].append(
        {
            "sequence": sequence,
            "path": destination.relative_to(review_dir).as_posix(),
            "bytes": chunk_bytes,
            "sha256": chunk_sha,
            "status": stored["status"],
        }
    )
    index["updated_at"] = stored["recorded_at"]
    if stored["status"] == "ROOT_CAUSE_UNIQUE":
        final = {
            "schema": REVIEW_SCHEMA,
            "kind": "final_adjudication",
            "rule_id": RULE_ID,
            "family": identity["family"],
            "track": identity["track"],
            "return_id": identity["return_id"],
            "return_zip_sha256": identity["return_zip"]["sha256"],
            "status": "ROOT_CAUSE_UNIQUE_STOP",
            "decisive_chunk": index["chunks"][-1],
            "root_cause": stored["root_cause"],
            "last_proven_good": stored["last_proven_good"],
            "first_divergence": stored["first_divergence"],
            "closed_candidates": index["closed_candidates"],
            "unreviewed_scope": stored["unreviewed_scope"],
            "stop_reason": "A unique root was established; further waveform scanning would not increase the diagnosis claim.",
            "claim_boundary": stored["claim_boundary"],
        }
        final_path = review_dir / "final_adjudication.json"
        try:
            exclusive_write(final_path, final)
        except FileExistsError as error:
            raise ReviewError("immutable final adjudication already exists") from error
        final_bytes, final_sha = hash_file(final_path)
        index["status"] = "ROOT_CAUSE_UNIQUE_STOP"
        index["root_cause_unique"] = True
        index["stop_reason"] = final["stop_reason"]
        index["final_adjudication"] = {
            "path": final_path.relative_to(review_dir).as_posix(),
            "bytes": final_bytes,
            "sha256": final_sha,
        }
    atomic_write(index_path, index)
    return index


def finalize_inconclusive(review_dir: Path, reason: str, unreviewed_scope: list[str]) -> dict[str, Any]:
    identity = read_json(review_dir / "return_identity.json")
    index_path = review_dir / "review_index.json"
    index = read_json(index_path)
    if index["status"] in TERMINAL_REVIEW_STATES:
        raise ReviewError("review is already terminal")
    if not index["chunks"]:
        raise ReviewError("cannot finalize an inconclusive review without an evidence chunk")
    final = {
        "schema": REVIEW_SCHEMA,
        "kind": "final_adjudication",
        "rule_id": RULE_ID,
        "family": identity["family"],
        "track": identity["track"],
        "return_id": identity["return_id"],
        "return_zip_sha256": identity["return_zip"]["sha256"],
        "status": "INCONCLUSIVE_STOP",
        "decisive_chunk": None,
        "root_cause": None,
        "last_proven_good": None,
        "first_divergence": None,
        "closed_candidates": index["closed_candidates"],
        "open_candidates": index["open_candidates"],
        "unreviewed_scope": unreviewed_scope,
        "stop_reason": reason,
        "claim_boundary": "Incremental review stopped inconclusive; no unique root, RTL, config, natural-terminal, formal-D, E4 or E5 claim.",
    }
    final_path = review_dir / "final_adjudication.json"
    try:
        exclusive_write(final_path, final)
    except FileExistsError as error:
        raise ReviewError("immutable final adjudication already exists") from error
    final_bytes, final_sha = hash_file(final_path)
    index["review_revision"] += 1
    index["status"] = "INCONCLUSIVE_STOP"
    index["stop_reason"] = reason
    index["final_adjudication"] = {
        "path": final_path.relative_to(review_dir).as_posix(),
        "bytes": final_bytes,
        "sha256": final_sha,
    }
    index["updated_at"] = utc_now()
    atomic_write(index_path, index)
    return index


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def register_return(
    *,
    index_path: Path,
    storage_root: Path,
    family: str,
    track: str,
    return_id: str,
    return_zip: Path,
    review_dir: Path,
    role: str,
) -> dict[str, Any]:
    if role not in {"CURRENT", "BASELINE", "CAUSAL", "OTHER"}:
        raise ReviewError(f"unsupported retention role: {role}")
    root = storage_root.resolve(strict=True)
    if root.is_symlink() or not root.is_dir():
        raise ReviewError("storage root must be a real directory")
    if not _inside(return_zip, root):
        raise ReviewError("return ZIP escapes declared storage root")
    identity = inspect_return_zip(return_zip)
    review_index = read_json(review_dir / "review_index.json")
    if review_index["return_zip_sha256"] != identity["sha256"]:
        raise ReviewError("review/return identity mismatch")
    if index_path.exists():
        index = read_json(index_path)
        if index["family"] != family or index["track"] != track:
            raise ReviewError("retention index family/track mismatch")
    else:
        index = {
            "schema": RETENTION_SCHEMA,
            "kind": "retention_index",
            "rule_id": RULE_ID,
            "family": family,
            "track": track,
            "storage_root": str(root),
            "max_raw_returns": 3,
            "next_registration_order": 1,
            "entries": [],
            "retirement_receipts": [],
            "updated_at": utc_now(),
        }
    if any(item["return_id"] == return_id for item in index["entries"]):
        raise ReviewError("return_id is already registered")
    if role in PROTECTED_ROLES and any(
        item["raw_present"] and item["role"] == role for item in index["entries"]
    ):
        raise ReviewError(f"protected slot {role} is already occupied")
    index["entries"].append(
        {
            "return_id": return_id,
            "return_zip": {
                "path": identity["path"],
                "bytes": identity["bytes"],
                "sha256": identity["sha256"],
            },
            "waveforms": identity["waveforms"],
            "review_dir": str(review_dir.resolve()),
            "role": role,
            "protected_reasons": [],
            "family_consumed_receipt": None,
            "mainline_consumed_receipt": None,
            "final_adjudication": review_index["final_adjudication"],
            "raw_present": True,
            "registered_order": index["next_registration_order"],
            "registered_at": utc_now(),
            "status": "ACTIVE_RAW",
        }
    )
    index["next_registration_order"] += 1
    index["updated_at"] = utc_now()
    atomic_write(index_path, index)
    return index


def mark_consumed(
    index_path: Path,
    return_id: str,
    family_receipt: Path,
    mainline_receipt: Path,
    protected_reasons: list[str],
) -> dict[str, Any]:
    index = read_json(index_path)
    matches = [item for item in index["entries"] if item["return_id"] == return_id]
    if len(matches) != 1:
        raise ReviewError("return_id is absent or duplicated")
    entry = matches[0]
    review_dir = Path(entry["review_dir"])
    review_index = read_json(review_dir / "review_index.json")
    if review_index["status"] not in TERMINAL_REVIEW_STATES:
        raise ReviewError("return review is not terminal")
    for label, path in (("family", family_receipt), ("mainline", mainline_receipt)):
        if path.is_symlink() or not path.is_file():
            raise ReviewError(f"{label} consumption receipt is absent")
        size, digest = hash_file(path)
        entry[f"{label}_consumed_receipt"] = {
            "path": str(path.resolve()),
            "bytes": size,
            "sha256": digest,
        }
    entry["protected_reasons"] = sorted(set(protected_reasons))
    entry["final_adjudication"] = review_index["final_adjudication"]
    entry["status"] = "CONSUMED_PROTECTED" if entry["role"] in PROTECTED_ROLES or protected_reasons else "ELIGIBLE_RETIRE"
    index["updated_at"] = utc_now()
    atomic_write(index_path, index)
    return index


def retention_plan(index: dict[str, Any]) -> dict[str, Any]:
    raw = [item for item in index["entries"] if item["raw_present"]]
    excess = max(0, len(raw) - index["max_raw_returns"])
    eligible = sorted(
        (
            item
            for item in raw
            if item["status"] == "ELIGIBLE_RETIRE"
            and item["role"] not in PROTECTED_ROLES
            and not item["protected_reasons"]
            and item["family_consumed_receipt"]
            and item["mainline_consumed_receipt"]
            and item["final_adjudication"]
        ),
        key=lambda item: item["registered_order"],
    )
    selected = eligible[:excess]
    errors: list[str] = []
    if len(selected) != excess:
        errors.append(
            f"raw return count {len(raw)} exceeds {index['max_raw_returns']}, but only {len(eligible)} safely retireable entries exist"
        )
    return {
        "schema": RETENTION_SCHEMA,
        "kind": "retention_plan",
        "rule_id": RULE_ID,
        "family": index["family"],
        "track": index["track"],
        "raw_count": len(raw),
        "max_raw_returns": index["max_raw_returns"],
        "excess": excess,
        "selected_return_ids": [item["return_id"] for item in selected],
        "selection_policy": "oldest registered entry among fully consumed, terminal-reviewed, unprotected non-anchor returns",
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Retention planning only; no file is deleted.",
    }


def _copy_core_zip(source: Path, destination: Path, manifest: dict[str, Any]) -> list[str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(
            temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as derived:
            root, infos = safe_zip(original)
            for info in sorted(infos, key=lambda item: item.filename):
                if info.is_dir() or is_raw_waveform(info.filename):
                    continue
                payload = original.read(info)
                target_info = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
                target_info.compress_type = zipfile.ZIP_DEFLATED
                target_info.external_attr = info.external_attr
                derived.writestr(target_info, payload)
                kept.append(info.filename)
            manifest_path = f"{root}/retention/RAW_WAVEFORM_RETIREMENT_MANIFEST.json"
            manifest_info = zipfile.ZipInfo(manifest_path, date_time=(1980, 1, 1, 0, 0, 0))
            manifest_info.compress_type = zipfile.ZIP_DEFLATED
            derived.writestr(manifest_info, json_bytes(manifest))
            kept.append(manifest_path)
        # Hard-link publication is same-filesystem and fails if another writer
        # already created the immutable destination; it never overwrites.
        os.link(temporary_path, destination)
        temporary_path.unlink()
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return kept


def retire_return(index_path: Path, return_id: str, retired_dir: Path) -> dict[str, Any]:
    index = read_json(index_path)
    plan = retention_plan(index)
    if not plan["pass"] or return_id not in plan["selected_return_ids"]:
        raise ReviewError("return is not selected by the current safe retention plan")
    entry = next(item for item in index["entries"] if item["return_id"] == return_id)
    source = Path(entry["return_zip"]["path"])
    root = Path(index["storage_root"])
    if not _inside(source, root) or source.is_symlink() or not source.is_file():
        raise ReviewError("retirement target is not an exact regular file under storage root")
    current_bytes, current_sha = hash_file(source)
    if current_bytes != entry["return_zip"]["bytes"] or current_sha != entry["return_zip"]["sha256"]:
        raise ReviewError("retirement target identity drifted")
    source_stat = source.stat()
    manifest = {
        "schema": RETENTION_SCHEMA,
        "kind": "raw_waveform_retirement_manifest",
        "rule_id": RULE_ID,
        "family": index["family"],
        "track": index["track"],
        "return_id": return_id,
        "original_return_zip": entry["return_zip"],
        "retired_waveforms": entry["waveforms"],
        "family_consumed_receipt": entry["family_consumed_receipt"],
        "mainline_consumed_receipt": entry["mainline_consumed_receipt"],
        "final_adjudication": entry["final_adjudication"],
        "recoverability": "RAW_WAVEFORM_NOT_LOCALLY_RECOVERABLE_AFTER_RETIREMENT",
        "claim_boundary": "Core-only derivative; it cannot support a new full-waveform query.",
    }
    core_zip = retired_dir / f"{return_id}_core_return.zip"
    if core_zip.exists():
        raise ReviewError("core-only destination already exists")
    kept = _copy_core_zip(source, core_zip, manifest)
    core_bytes, core_sha = hash_file(core_zip)
    with zipfile.ZipFile(core_zip) as derived:
        _root, derived_infos = safe_zip(derived)
        derived_names = [item.filename for item in derived_infos if not item.is_dir()]
        if any(is_raw_waveform(name) for name in derived_names):
            raise ReviewError("core-only derivative still contains a raw waveform")
        if not any(name.endswith("/retention/RAW_WAVEFORM_RETIREMENT_MANIFEST.json") for name in derived_names):
            raise ReviewError("core-only derivative lacks retirement manifest")
    receipt = {
        "schema": RETENTION_SCHEMA,
        "kind": "retirement_receipt",
        "rule_id": RULE_ID,
        "family": index["family"],
        "track": index["track"],
        "return_id": return_id,
        "original_return_zip": entry["return_zip"],
        "retired_waveforms": entry["waveforms"],
        "core_return_zip": {
            "path": str(core_zip.resolve()),
            "bytes": core_bytes,
            "sha256": core_sha,
            "kept_member_count": len(kept),
        },
        "family_consumed_receipt": entry["family_consumed_receipt"],
        "mainline_consumed_receipt": entry["mainline_consumed_receipt"],
        "final_adjudication": entry["final_adjudication"],
        "deletion_target_identity_rechecked": True,
        "deleted": False,
        "recoverability": "RAW_WAVEFORM_NOT_LOCALLY_RECOVERABLE_AFTER_RETIREMENT",
        "created_at": utc_now(),
        "claim_boundary": "Post-adjudication local raw-waveform retirement only; packages, reports and server state are untouched.",
    }
    receipt_path = retired_dir / f"{return_id}_retirement_receipt.json"
    atomic_write(receipt_path, receipt)
    final_stat = source.stat()
    if (
        final_stat.st_dev != source_stat.st_dev
        or final_stat.st_ino != source_stat.st_ino
        or final_stat.st_size != source_stat.st_size
    ):
        raise ReviewError("retirement target filesystem identity changed before unlink")
    source.unlink()
    receipt["deleted"] = True
    receipt["deleted_at"] = utc_now()
    atomic_write(receipt_path, receipt)
    receipt_bytes, receipt_sha = hash_file(receipt_path)
    entry["raw_present"] = False
    entry["status"] = "RAW_EVIDENCE_RETIRED"
    entry["core_return_zip"] = receipt["core_return_zip"]
    entry["retirement_receipt"] = {
        "path": str(receipt_path.resolve()),
        "bytes": receipt_bytes,
        "sha256": receipt_sha,
    }
    index["retirement_receipts"].append(entry["retirement_receipt"])
    index["updated_at"] = receipt["deleted_at"]
    atomic_write(index_path, index)
    return receipt


def _read_string_list(path: Path | None) -> list[str]:
    if path is None:
        return []
    value = read_json(path)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ReviewError(f"expected JSON string list: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-review")
    init.add_argument("--family", required=True)
    init.add_argument("--track", required=True)
    init.add_argument("--return-id", required=True)
    init.add_argument("--return-zip", type=Path, required=True)
    init.add_argument("--review-dir", type=Path, required=True)
    init.add_argument("--candidates", type=Path)

    add = subparsers.add_parser("add-chunk")
    add.add_argument("--review-dir", type=Path, required=True)
    add.add_argument("--chunk", type=Path, required=True)

    inconclusive = subparsers.add_parser("finalize-inconclusive")
    inconclusive.add_argument("--review-dir", type=Path, required=True)
    inconclusive.add_argument("--reason", required=True)
    inconclusive.add_argument("--unreviewed-scope", type=Path)

    register = subparsers.add_parser("register-return")
    register.add_argument("--index", type=Path, required=True)
    register.add_argument("--storage-root", type=Path, required=True)
    register.add_argument("--family", required=True)
    register.add_argument("--track", required=True)
    register.add_argument("--return-id", required=True)
    register.add_argument("--return-zip", type=Path, required=True)
    register.add_argument("--review-dir", type=Path, required=True)
    register.add_argument("--role", choices=["CURRENT", "BASELINE", "CAUSAL", "OTHER"], required=True)

    consumed = subparsers.add_parser("mark-consumed")
    consumed.add_argument("--index", type=Path, required=True)
    consumed.add_argument("--return-id", required=True)
    consumed.add_argument("--family-receipt", type=Path, required=True)
    consumed.add_argument("--mainline-receipt", type=Path, required=True)
    consumed.add_argument("--protected-reasons", type=Path)

    plan = subparsers.add_parser("plan-retention")
    plan.add_argument("--index", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)

    retire = subparsers.add_parser("retire-return")
    retire.add_argument("--index", type=Path, required=True)
    retire.add_argument("--return-id", required=True)
    retire.add_argument("--retired-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "init-review":
            report = init_review(
                family=args.family,
                track=args.track,
                return_id=args.return_id,
                return_zip=args.return_zip,
                review_dir=args.review_dir,
                candidates=_read_string_list(args.candidates),
            )
        elif args.command == "add-chunk":
            report = add_review_chunk(args.review_dir, args.chunk)
        elif args.command == "finalize-inconclusive":
            report = finalize_inconclusive(
                args.review_dir, args.reason, _read_string_list(args.unreviewed_scope)
            )
        elif args.command == "register-return":
            report = register_return(
                index_path=args.index,
                storage_root=args.storage_root,
                family=args.family,
                track=args.track,
                return_id=args.return_id,
                return_zip=args.return_zip,
                review_dir=args.review_dir,
                role=args.role,
            )
        elif args.command == "mark-consumed":
            report = mark_consumed(
                args.index,
                args.return_id,
                args.family_receipt,
                args.mainline_receipt,
                _read_string_list(args.protected_reasons),
            )
        elif args.command == "plan-retention":
            report = retention_plan(read_json(args.index))
            atomic_write(args.output, report)
        else:
            report = retire_return(args.index, args.return_id, args.retired_dir)
    except (OSError, zipfile.BadZipFile, ReviewError) as error:
        print(f"{type(error).__name__}: {error}", file=os.sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("pass", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
