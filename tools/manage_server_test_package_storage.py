#!/usr/bin/env python3
"""Manage pending/tested/superseded server-package storage.

The operator-facing pickup directory is intentionally flat and ZIP-only:
``pending/<package-base>.zip``.  The checksum sidecar and auxiliary release
receipts live outside that pickup directory under
``pending_receipts/<family>/<package-base>/``.  Tested and superseded artifact
sets remain in their full archival trees.  The tool never deletes or
overwrites package files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISPOSITIONS = ("pending", "tested", "superseded")
INDEX_NAME = "PACKAGE_STORAGE_INDEX.json"


class StorageError(RuntimeError):
    pass


def io_path(path: Path) -> Path:
    """Return a Windows extended-length path for filesystem operations."""

    if sys.platform != "win32":
        return path
    value = str(path.resolve(strict=False))
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def path_exists(path: Path) -> bool:
    return io_path(path).exists()


def path_is_file(path: Path) -> bool:
    return io_path(path).is_file()


def path_is_dir(path: Path) -> bool:
    return io_path(path).is_dir()


def path_is_symlink(path: Path) -> bool:
    return io_path(path).is_symlink()


def iter_directory(path: Path):
    """Yield logical children while using an extended path for enumeration."""

    for child in io_path(path).iterdir():
        yield path / child.name


def walk_files(path: Path):
    for child in iter_directory(path):
        if path_is_dir(child):
            yield from walk_files(child)
        elif path_is_file(child):
            yield child


def ensure_directory(path: Path) -> None:
    io_path(path).mkdir(parents=True, exist_ok=True)


def move_file(source: Path, target: Path) -> None:
    ensure_directory(target.parent)
    shutil.move(str(io_path(source)), str(io_path(target)))


def remove_directory(path: Path) -> None:
    io_path(path).rmdir()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with io_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolved_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise StorageError(f"path escapes package root: {resolved}") from exc
    return resolved


def load_json(path: Path) -> dict[str, Any]:
    with io_path(path).open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise StorageError(f"JSON root must be an object: {path}")
    return value


def package_members(source_dir: Path, package_base: str) -> list[Path]:
    if not package_base or Path(package_base).name != package_base:
        raise StorageError(f"invalid package_base: {package_base!r}")
    prefix_dot = package_base + "."
    prefix_underscore = package_base + "_"
    members = [
        path
        for path in iter_directory(source_dir)
        if path_is_file(path)
        and (
            path.name == package_base + ".zip"
            or path.name == package_base + ".zip.sha256"
            or path.name.startswith(prefix_dot)
            or path.name.startswith(prefix_underscore)
        )
    ]
    return sorted(set(members), key=lambda item: item.name)


def validate_sidecar(zip_path: Path, sidecar_path: Path) -> None:
    tokens = io_path(sidecar_path).read_text(encoding="utf-8").strip().split()
    if not tokens:
        raise StorageError(f"empty ZIP sidecar: {sidecar_path}")
    actual = sha256(zip_path)
    if tokens[0].lower() != actual:
        raise StorageError(
            f"ZIP sidecar mismatch: {zip_path.name}: "
            f"sidecar={tokens[0].lower()} actual={actual}"
        )


def validate_source_set(source_dir: Path, package_base: str) -> list[Path]:
    members = package_members(source_dir, package_base)
    zip_path = source_dir / f"{package_base}.zip"
    sidecar_path = source_dir / f"{package_base}.zip.sha256"
    if zip_path not in members:
        raise StorageError(f"missing ZIP for {package_base}")
    if sidecar_path not in members:
        raise StorageError(f"missing ZIP sidecar for {package_base}")
    for member in members:
        if path_is_symlink(member):
            raise StorageError(f"package artifact must not be a symlink: {member}")
    validate_sidecar(zip_path, sidecar_path)
    return members


def validate_entry(entry: dict[str, Any]) -> None:
    required = ("family", "package_base", "disposition", "reason")
    missing = [key for key in required if not entry.get(key)]
    if missing:
        raise StorageError(f"manifest entry missing {missing}: {entry}")
    if entry["disposition"] not in DISPOSITIONS:
        raise StorageError(f"invalid disposition: {entry['disposition']}")
    for key in ("family", "package_base"):
        if Path(entry[key]).name != entry[key]:
            raise StorageError(f"invalid {key}: {entry[key]!r}")


def file_record(member: Path, root: Path) -> dict[str, Any]:
    return {
        "name": member.name,
        "relative_path": member.relative_to(root).as_posix(),
        "bytes": io_path(member).stat().st_size,
        "sha256": sha256(member),
    }


def pending_receipt_dir(root: Path, family: str, package_base: str) -> Path:
    return resolved_under(root / "pending_receipts" / family / package_base, root)


def pending_members(root: Path, family: str, package_base: str) -> list[Path]:
    zip_path = root / "pending" / f"{package_base}.zip"
    receipt_dir = pending_receipt_dir(root, family, package_base)
    sidecar_path = receipt_dir / f"{package_base}.zip.sha256"
    if not path_is_file(zip_path) or not path_is_file(sidecar_path):
        raise StorageError(f"incomplete ZIP-only pending package set: {package_base}")
    validate_sidecar(zip_path, sidecar_path)
    members = [zip_path, sidecar_path]
    if path_exists(receipt_dir):
        if not path_is_dir(receipt_dir) or path_is_symlink(receipt_dir):
            raise StorageError(f"invalid pending receipt directory: {receipt_dir}")
        nested = [path for path in iter_directory(receipt_dir) if path_is_dir(path)]
        if nested:
            raise StorageError(f"nested pending receipt directories are forbidden: {nested}")
        receipt_files = sorted(
            path
            for path in iter_directory(receipt_dir)
            if path_is_file(path) and path != sidecar_path
        )
        if any(path_is_symlink(path) for path in receipt_files):
            raise StorageError(f"pending receipts must not be symlinks: {receipt_dir}")
        members.extend(receipt_files)
    return members


def collect_tree_index(root: Path, annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flat_packages = sorted(path.name for path in root.glob("*.zip"))
    flat_sidecars = sorted(path.name for path in root.glob("*.zip.sha256"))
    if flat_packages or flat_sidecars:
        raise StorageError(
            "flat package artifacts are forbidden after migration: "
            f"zips={flat_packages} sidecars={flat_sidecars}"
        )
    records: list[dict[str, Any]] = []
    pending_by_family: dict[str, list[str]] = {}
    seen_bases: dict[str, str] = {}
    pending_root = root / "pending"
    referenced_receipts: set[Path] = set()
    if path_exists(pending_root):
        pending_dirs = sorted(
            path for path in iter_directory(pending_root) if path_is_dir(path)
        )
        if pending_dirs:
            raise StorageError(
                "pending pickup directory must be flat; run flatten-pending: "
                f"{pending_dirs}"
            )
        pending_zips = sorted(pending_root.glob("*.zip"))
        expected_pending_files: set[Path] = set()
        for zip_path in pending_zips:
            package_base = zip_path.name[: -len(".zip")]
            annotation = annotations.get(package_base, {})
            family = annotation.get("family")
            if not family or Path(family).name != family:
                raise StorageError(
                    f"pending package lacks indexed family identity: {package_base}"
                )
            if package_base in seen_bases:
                raise StorageError(f"duplicate pending package base: {package_base}")
            seen_bases[package_base] = str(zip_path)
            members = pending_members(root, family, package_base)
            expected_pending_files.add(members[0])
            referenced_receipts.update(path.resolve() for path in members[1:])
            pending_by_family.setdefault(family, []).append(package_base)
            records.append(
                {
                    "family": family,
                    "package_base": package_base,
                    "disposition": "pending",
                    "reason": annotation.get(
                        "reason", "preserved_existing_index_reason"
                    ),
                    "evidence": annotation.get("evidence"),
                    "pickup_zip": f"pending/{package_base}.zip",
                    "pickup_sidecar": None,
                    "receipt_sidecar": (
                        f"pending_receipts/{family}/{package_base}/"
                        f"{package_base}.zip.sha256"
                    ),
                    "receipt_dir": f"pending_receipts/{family}/{package_base}",
                    "files": [file_record(member, root) for member in members],
                }
            )
        actual_pending_files = {
            path for path in iter_directory(pending_root) if path_is_file(path)
        }
        unexpected_pending = sorted(actual_pending_files - expected_pending_files)
        if unexpected_pending:
            raise StorageError(
                f"pending pickup directory contains non-pickup artifacts: "
                f"{unexpected_pending}"
            )
    receipts_root = root / "pending_receipts"
    if path_exists(receipts_root):
        actual_receipts = {
            path.resolve() for path in walk_files(receipts_root)
        }
        unexpected_receipts = sorted(actual_receipts - referenced_receipts)
        if unexpected_receipts:
            raise StorageError(
                f"orphan pending receipt artifacts: {unexpected_receipts}"
            )
    for disposition in ("tested", "superseded"):
        disposition_root = root / disposition
        if not path_exists(disposition_root):
            continue
        for family_dir in sorted(
            path
            for path in iter_directory(disposition_root)
            if path_is_dir(path)
        ):
            for package_dir in sorted(
                path for path in iter_directory(family_dir) if path_is_dir(path)
            ):
                package_base = package_dir.name
                if package_base in seen_bases:
                    raise StorageError(
                        f"package exists in multiple locations: {package_base}: "
                        f"{seen_bases[package_base]} and {package_dir}"
                    )
                seen_bases[package_base] = str(package_dir)
                zip_path = package_dir / f"{package_base}.zip"
                sidecar_path = package_dir / f"{package_base}.zip.sha256"
                if not path_is_file(zip_path) or not path_is_file(sidecar_path):
                    raise StorageError(f"incomplete package pair: {package_dir}")
                validate_sidecar(zip_path, sidecar_path)
                files = [
                    file_record(member, root)
                    for member in sorted(
                        path
                        for path in iter_directory(package_dir)
                        if path_is_file(path)
                    )
                ]
                annotation = annotations.get(package_base, {})
                records.append(
                    {
                        "family": family_dir.name,
                        "package_base": package_base,
                        "disposition": disposition,
                        "reason": annotation.get("reason", "preserved_existing_index_reason"),
                        "evidence": annotation.get("evidence"),
                        "files": files,
                    }
                )
    violations = {
        family: packages
        for family, packages in pending_by_family.items()
        if len(packages) != 1
    }
    if violations:
        raise StorageError(f"pending one-per-family violation: {violations}")
    return {
        "schema": "server_test_package_storage_index_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "policy": {
            "pending_max_per_family": 1,
            "pending_pickup_layout": "pending/<package-base>.zip",
            "pending_pickup_zip_only": True,
            "dispositions": list(DISPOSITIONS),
            "overwrite_allowed": False,
        },
        "counts": {
            disposition: sum(
                1 for record in records if record["disposition"] == disposition
            )
            for disposition in DISPOSITIONS
        },
        "pending_by_family": pending_by_family,
        "packages": records,
        "pass": True,
    }


def write_index(root: Path, annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    index = collect_tree_index(root, annotations)
    target = root / INDEX_NAME
    io_path(target).write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def existing_annotations(root: Path) -> dict[str, dict[str, Any]]:
    path = root / INDEX_NAME
    if not path_is_file(path):
        return {}
    index = load_json(path)
    return {
        entry["package_base"]: {
            "family": entry.get("family"),
            "reason": entry.get("reason"),
            "evidence": entry.get("evidence"),
        }
        for entry in index.get("packages", [])
        if isinstance(entry, dict) and entry.get("package_base")
    }


def apply_manifest(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    if manifest.get("schema") != "server_test_package_storage_migration_v1":
        raise StorageError("unsupported migration manifest schema")
    entries = manifest.get("packages")
    if not isinstance(entries, list) or not entries:
        raise StorageError("migration manifest packages must be a non-empty array")
    seen: set[str] = set()
    pending_families: set[str] = set()
    annotations: dict[str, dict[str, Any]] = {}
    prepared: list[tuple[dict[str, Any], list[tuple[Path, Path]]]] = []
    all_targets: set[Path] = set()
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise StorageError("migration entry must be an object")
        validate_entry(raw_entry)
        package_base = raw_entry["package_base"]
        if package_base in seen:
            raise StorageError(f"duplicate migration package: {package_base}")
        seen.add(package_base)
        if raw_entry["disposition"] == "pending":
            if raw_entry["family"] in pending_families:
                raise StorageError(
                    f"multiple pending packages for family: {raw_entry['family']}"
                )
            pending_families.add(raw_entry["family"])
        members = validate_source_set(root, package_base)
        moves: list[tuple[Path, Path]] = []
        if raw_entry["disposition"] == "pending":
            receipt_dir = pending_receipt_dir(
                root, raw_entry["family"], package_base
            )
            if path_exists(receipt_dir):
                raise StorageError(f"pending receipt destination exists: {receipt_dir}")
            for source in members:
                if source.name == f"{package_base}.zip":
                    target = resolved_under(root / "pending" / source.name, root)
                else:
                    target = resolved_under(receipt_dir / source.name, root)
                moves.append((source, target))
        else:
            destination = resolved_under(
                root
                / raw_entry["disposition"]
                / raw_entry["family"]
                / package_base,
                root,
            )
            if path_exists(destination):
                raise StorageError(f"destination already exists: {destination}")
            moves = [
                (source, resolved_under(destination / source.name, root))
                for source in members
            ]
        for _, target in moves:
            if target in all_targets or path_exists(target):
                raise StorageError(f"refusing duplicate or overwrite target: {target}")
            all_targets.add(target)
        prepared.append((raw_entry, moves))
        annotations[package_base] = {
            "family": raw_entry["family"],
            "reason": raw_entry["reason"],
            "evidence": raw_entry.get("evidence"),
        }
    root_zips = {path.stem for path in root.glob("*.zip")}
    if root_zips != seen:
        raise StorageError(
            "migration manifest/root ZIP set mismatch: "
            f"missing={sorted(root_zips - seen)} extra={sorted(seen - root_zips)}"
        )
    for _, moves in prepared:
        for source, target in moves:
            move_file(source, target)
    return write_index(root, annotations)


def rotate(
    root: Path,
    source_dir: Path,
    family: str,
    new_base: str,
    previous_disposition: str | None,
    previous_reason: str | None,
    previous_evidence: Path | None,
    new_reason: str,
    new_evidence: Path,
) -> dict[str, Any]:
    if Path(family).name != family:
        raise StorageError(f"invalid family: {family!r}")
    if previous_disposition is not None and previous_disposition not in (
        "tested",
        "superseded",
    ):
        raise StorageError("previous disposition must be tested or superseded")
    if not path_is_file(new_evidence):
        raise StorageError(f"missing new release evidence: {new_evidence}")
    annotations = existing_annotations(root)
    current_index = collect_tree_index(root, annotations)
    current_bases = current_index["pending_by_family"].get(family, [])
    if len(current_bases) > 1:
        raise StorageError(f"existing pending multiplicity for {family}: {current_bases}")
    if current_bases and previous_disposition is None:
        raise StorageError("existing pending package requires previous disposition")
    if current_bases and not previous_reason:
        raise StorageError("existing pending package requires previous reason")
    if current_bases and (
        previous_evidence is None or not path_is_file(previous_evidence)
    ):
        raise StorageError("existing pending package requires readable evidence")
    new_evidence_sha256 = sha256(new_evidence)
    previous_evidence_sha256 = (
        sha256(previous_evidence) if previous_evidence is not None else None
    )
    members = validate_source_set(source_dir, new_base)
    previous_base = current_bases[0] if current_bases else None
    if previous_base == new_base:
        raise StorageError("fresh pending package must use a new package identity")
    new_receipt_dir = pending_receipt_dir(root, family, new_base)
    new_moves: list[tuple[Path, Path]] = []
    for source in members:
        if source.name == f"{new_base}.zip":
            target = resolved_under(root / "pending" / source.name, root)
        else:
            target = resolved_under(new_receipt_dir / source.name, root)
        if path_exists(target):
            raise StorageError(f"new pending target exists: {target}")
        new_moves.append((source, target))
    previous_moves: list[tuple[Path, Path]] = []
    if previous_base is not None:
        previous_sources = pending_members(root, family, previous_base)
        previous_destination = resolved_under(
            root / previous_disposition / family / previous_base,
            root,
        )
        if path_exists(previous_destination):
            raise StorageError(f"previous destination exists: {previous_destination}")
        previous_moves = [
            (
                source,
                resolved_under(previous_destination / source.name, root),
            )
            for source in previous_sources
        ]

    def evidence_path_after_moves(
        evidence_path: Path,
        moves: list[tuple[Path, Path]],
    ) -> Path:
        resolved_evidence = evidence_path.resolve()
        for source, target in moves:
            if source.resolve() == resolved_evidence:
                return target
        return evidence_path

    archived_previous_evidence = (
        evidence_path_after_moves(previous_evidence, previous_moves)
        if previous_evidence is not None
        else None
    )
    published_new_evidence = evidence_path_after_moves(new_evidence, new_moves)
    for source, target in previous_moves:
        move_file(source, target)
    if previous_base is not None:
        old_receipt_dir = pending_receipt_dir(root, family, previous_base)
        if path_exists(old_receipt_dir):
            remove_directory(old_receipt_dir)
            family_receipt_dir = old_receipt_dir.parent
            if path_exists(family_receipt_dir) and not any(
                iter_directory(family_receipt_dir)
            ):
                remove_directory(family_receipt_dir)
        annotations[previous_base] = {
            "family": family,
            "reason": previous_reason,
            "evidence": {
                "path": str(archived_previous_evidence),
                "sha256": previous_evidence_sha256,
            },
        }
    for source, target in new_moves:
        move_file(source, target)
    annotations[new_base] = {
        "family": family,
        "reason": new_reason,
        "evidence": {
            "path": str(published_new_evidence),
            "sha256": new_evidence_sha256,
        },
    }
    return write_index(root, annotations)


def retire_pending(
    root: Path,
    family: str,
    package_base: str,
    disposition: str,
    reason: str,
    evidence: Path,
) -> dict[str, Any]:
    """Archive one exact pending package without publishing a replacement."""

    if Path(family).name != family:
        raise StorageError(f"invalid family: {family!r}")
    if Path(package_base).name != package_base:
        raise StorageError(f"invalid package_base: {package_base!r}")
    if disposition not in ("tested", "superseded"):
        raise StorageError("retired disposition must be tested or superseded")
    if not reason:
        raise StorageError("retired pending package requires a reason")
    if not path_is_file(evidence):
        raise StorageError(f"missing retirement evidence: {evidence}")

    annotations = existing_annotations(root)
    current_index = collect_tree_index(root, annotations)
    current_bases = current_index["pending_by_family"].get(family, [])
    if current_bases != [package_base]:
        raise StorageError(
            "exact pending package/family mismatch: "
            f"expected={[package_base]} actual={current_bases}"
        )

    sources = pending_members(root, family, package_base)
    destination = resolved_under(
        root / disposition / family / package_base,
        root,
    )
    if path_exists(destination):
        raise StorageError(f"retirement destination exists: {destination}")
    moves = [
        (source, resolved_under(destination / source.name, root))
        for source in sources
    ]

    evidence_sha256 = sha256(evidence)
    resolved_evidence = evidence.resolve()
    archived_evidence = evidence
    for source, target in moves:
        if source.resolve() == resolved_evidence:
            archived_evidence = target
            break

    for source, target in moves:
        move_file(source, target)

    old_receipt_dir = pending_receipt_dir(root, family, package_base)
    if path_exists(old_receipt_dir):
        remove_directory(old_receipt_dir)
        family_receipt_dir = old_receipt_dir.parent
        if path_exists(family_receipt_dir) and not any(
            iter_directory(family_receipt_dir)
        ):
            remove_directory(family_receipt_dir)

    annotations[package_base] = {
        "family": family,
        "reason": reason,
        "evidence": {
            "path": str(archived_evidence),
            "sha256": evidence_sha256,
        },
    }
    return write_index(root, annotations)


def flatten_pending(root: Path) -> dict[str, Any]:
    """Migrate legacy pending/<family>/<package>/ sets to flat pickup paths."""

    annotations = existing_annotations(root)
    index_path = root / INDEX_NAME
    if not path_is_file(index_path):
        raise StorageError("flatten-pending requires an existing storage index")
    index = load_json(index_path)
    pending_records = [
        record
        for record in index.get("packages", [])
        if isinstance(record, dict) and record.get("disposition") == "pending"
    ]
    moves: list[tuple[Path, Path]] = []
    legacy_dirs: list[Path] = []
    all_targets: set[Path] = set()
    for record in pending_records:
        family = record.get("family")
        package_base = record.get("package_base")
        if not family or not package_base:
            raise StorageError(f"invalid indexed pending record: {record}")
        legacy_dir = resolved_under(
            root / "pending" / family / package_base,
            root,
        )
        if not path_is_dir(legacy_dir):
            raise StorageError(f"legacy pending directory missing: {legacy_dir}")
        members = validate_source_set(legacy_dir, package_base)
        all_legacy_files = sorted(
            path for path in iter_directory(legacy_dir) if path_is_file(path)
        )
        if members != all_legacy_files:
            raise StorageError(
                f"legacy pending directory contains unrelated files: {legacy_dir}"
            )
        if any(path_is_dir(path) for path in iter_directory(legacy_dir)):
            raise StorageError(f"legacy pending directory contains nested dirs: {legacy_dir}")
        receipt_dir = pending_receipt_dir(root, family, package_base)
        if path_exists(receipt_dir):
            raise StorageError(f"pending receipt destination exists: {receipt_dir}")
        for source in members:
            if source.name == f"{package_base}.zip":
                target = resolved_under(root / "pending" / source.name, root)
            else:
                target = resolved_under(receipt_dir / source.name, root)
            if path_exists(target) or target in all_targets:
                raise StorageError(f"refusing duplicate or overwrite target: {target}")
            all_targets.add(target)
            moves.append((source, target))
        legacy_dirs.append(legacy_dir)
        annotations[package_base] = {
            **annotations.get(package_base, {}),
            "family": family,
        }
    for source, target in moves:
        move_file(source, target)
    for legacy_dir in legacy_dirs:
        remove_directory(legacy_dir)
    for family_dir in sorted(
        iter_directory(root / "pending"), key=lambda path: path.name
    ):
        if path_is_dir(family_dir) and not any(iter_directory(family_dir)):
            remove_directory(family_dir)
    return write_index(root, annotations)


def compact_pending(root: Path) -> dict[str, Any]:
    """Move pickup sidecars out of an already-flat pending directory."""

    annotations = existing_annotations(root)
    index_path = root / INDEX_NAME
    if not path_is_file(index_path):
        raise StorageError("compact-pending requires an existing storage index")
    index = load_json(index_path)
    moves: list[tuple[Path, Path]] = []
    for record in index.get("packages", []):
        if not isinstance(record, dict) or record.get("disposition") != "pending":
            continue
        family = record.get("family")
        package_base = record.get("package_base")
        if not family or not package_base:
            raise StorageError(f"invalid indexed pending record: {record}")
        zip_path = root / "pending" / f"{package_base}.zip"
        sidecar_path = root / "pending" / f"{package_base}.zip.sha256"
        if not path_is_file(zip_path) or not path_is_file(sidecar_path):
            raise StorageError(f"flat pending pair missing: {package_base}")
        validate_sidecar(zip_path, sidecar_path)
        target = pending_receipt_dir(root, family, package_base) / sidecar_path.name
        if path_exists(target):
            raise StorageError(f"pending receipt sidecar already exists: {target}")
        moves.append((sidecar_path, target))
        annotations[package_base] = {
            **annotations.get(package_base, {}),
            "family": family,
        }
    for source, target in moves:
        move_file(source, target)
    return write_index(root, annotations)


def audit(root: Path) -> dict[str, Any]:
    return collect_tree_index(root, existing_annotations(root))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subparsers = result.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply-manifest")
    apply_parser.add_argument("--root", required=True, type=Path)
    apply_parser.add_argument("--manifest", required=True, type=Path)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--root", required=True, type=Path)

    flatten_parser = subparsers.add_parser("flatten-pending")
    flatten_parser.add_argument("--root", required=True, type=Path)

    compact_parser = subparsers.add_parser("compact-pending")
    compact_parser.add_argument("--root", required=True, type=Path)

    rotate_parser = subparsers.add_parser("rotate")
    rotate_parser.add_argument("--root", required=True, type=Path)
    rotate_parser.add_argument("--source-dir", required=True, type=Path)
    rotate_parser.add_argument("--family", required=True)
    rotate_parser.add_argument("--new-base", required=True)
    rotate_parser.add_argument(
        "--previous-disposition", choices=("tested", "superseded")
    )
    rotate_parser.add_argument("--previous-reason")
    rotate_parser.add_argument("--previous-evidence", type=Path)
    rotate_parser.add_argument("--new-reason", required=True)
    rotate_parser.add_argument("--new-evidence", required=True, type=Path)

    retire_parser = subparsers.add_parser("retire-pending")
    retire_parser.add_argument("--root", required=True, type=Path)
    retire_parser.add_argument("--family", required=True)
    retire_parser.add_argument("--package-base", required=True)
    retire_parser.add_argument(
        "--disposition", required=True, choices=("tested", "superseded")
    )
    retire_parser.add_argument("--reason", required=True)
    retire_parser.add_argument("--evidence", required=True, type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        root = args.root.resolve()
        if not path_is_dir(root):
            raise StorageError(f"package root is not a directory: {root}")
        if args.command == "apply-manifest":
            result = apply_manifest(root, args.manifest.resolve())
        elif args.command == "flatten-pending":
            result = flatten_pending(root)
        elif args.command == "compact-pending":
            result = compact_pending(root)
        elif args.command == "rotate":
            result = rotate(
                root=root,
                source_dir=args.source_dir.resolve(),
                family=args.family,
                new_base=args.new_base,
                previous_disposition=args.previous_disposition,
                previous_reason=args.previous_reason,
                previous_evidence=(
                    args.previous_evidence.resolve()
                    if args.previous_evidence is not None
                    else None
                ),
                new_reason=args.new_reason,
                new_evidence=args.new_evidence.resolve(),
            )
        elif args.command == "retire-pending":
            result = retire_pending(
                root=root,
                family=args.family,
                package_base=args.package_base,
                disposition=args.disposition,
                reason=args.reason,
                evidence=args.evidence.resolve(),
            )
        else:
            result = audit(root)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError, StorageError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
