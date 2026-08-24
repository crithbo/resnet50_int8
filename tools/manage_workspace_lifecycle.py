#!/usr/bin/env python3
"""Inventory a ResNet50 workspace and prepare a non-destructive cleanup plan.

Version 1 deliberately has no apply/delete/move subcommand.  It discovers the
current protected set from the control plane, inventories generated roots with
no symlink traversal, and emits exact dry-run candidates.  Legacy and
identity-ambiguous content remains protected pending classification.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "workspace-lifecycle-v1"
PATH_REFERENCE = re.compile(
    r"(?P<path>(?:outputs|artifacts|server_returns)[/\\][A-Za-z0-9_.() /\\-]+)"
)


class LifecycleError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"cannot read JSON {path}: {type(error).__name__}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.resolve(strict=False).relative_to(root.resolve(strict=True)).as_posix()


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def add_protection(
    protected: dict[Path, set[str]], root: Path, raw_path: str | Path, reason: str
) -> None:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if not inside(candidate, root):
        return
    protected[candidate.resolve(strict=False)].add(reason)


def iter_path_values(value: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            location = f"{prefix}.{key}" if prefix else key
            if key == "path" and isinstance(child, str):
                yield location, child
            yield from iter_path_values(child, location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_path_values(child, f"{prefix}[{index}]")


def text_references(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except OSError:
        return []
    values: list[str] = []
    for match in PATH_REFERENCE.finditer(text):
        value = match.group("path").rstrip("`'\".,;:)]}> \r\n")
        if value:
            values.append(value)
    return values


def git_tracked(root: Path, warnings: list[str]) -> list[str]:
    command = [
        "git",
        "-c",
        f"safe.directory={root}",
        "-C",
        str(root),
        "ls-files",
        "-z",
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True)
    except OSError as error:
        warnings.append(f"git tracked-set unavailable: {type(error).__name__}: {error}")
        return []
    if result.returncode != 0:
        warnings.append(
            "git tracked-set unavailable: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
        return []
    return [item.decode("utf-8", errors="strict") for item in result.stdout.split(b"\0") if item]


@dataclass
class DirStat:
    files: int = 0
    directories: int = 0
    bytes: int = 0
    symlinks: int = 0
    access_error_count: int = 0

    def add(self, other: "DirStat") -> None:
        self.files += other.files
        self.directories += other.directories
        self.bytes += other.bytes
        self.symlinks += other.symlinks
        self.access_error_count += other.access_error_count

    def record(self) -> dict[str, int]:
        return {
            "files": self.files,
            "directories": self.directories,
            "bytes": self.bytes,
            "symlinks": self.symlinks,
            "access_error_count": self.access_error_count,
        }


def scan_tree(
    scan_root: Path,
    access_errors: list[dict[str, str]],
) -> tuple[dict[Path, DirStat], list[Path], DirStat]:
    if not scan_root.exists() and not scan_root.is_symlink():
        return {}, [], DirStat()
    if scan_root.is_symlink():
        return {scan_root: DirStat(symlinks=1)}, [], DirStat(symlinks=1)
    if scan_root.is_file():
        try:
            size = scan_root.stat(follow_symlinks=False).st_size
        except OSError as error:
            access_errors.append({"path": str(scan_root), "error": f"{type(error).__name__}: {error}"})
            return {}, [], DirStat(access_error_count=1)
        return {}, [scan_root], DirStat(files=1, bytes=size)

    direct: dict[Path, DirStat] = {}
    children: dict[Path, list[Path]] = defaultdict(list)
    repeat_files: list[Path] = []
    order: list[Path] = []
    stack = [scan_root]
    seen: set[Path] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        order.append(current)
        stat = direct.setdefault(current, DirStat())
        try:
            entries = list(os.scandir(current))
        except OSError as error:
            stat.access_error_count += 1
            access_errors.append({"path": str(current), "error": f"{type(error).__name__}: {error}"})
            continue
        for entry in entries:
            child = Path(entry.path)
            try:
                if entry.is_symlink():
                    stat.symlinks += 1
                elif entry.is_dir(follow_symlinks=False):
                    stat.directories += 1
                    children[current].append(child)
                    stack.append(child)
                elif entry.is_file(follow_symlinks=False):
                    item_stat = entry.stat(follow_symlinks=False)
                    stat.files += 1
                    stat.bytes += item_stat.st_size
                    if child.name.endswith(".repeat.zip"):
                        repeat_files.append(child)
            except OSError as error:
                stat.access_error_count += 1
                access_errors.append({"path": str(child), "error": f"{type(error).__name__}: {error}"})

    aggregate = {path: DirStat(**direct[path].record()) for path in direct}
    for current in reversed(order):
        for child in children.get(current, []):
            aggregate[current].add(aggregate.get(child, DirStat()))
    return aggregate, repeat_files, aggregate.get(scan_root, DirStat())


def path_is_reparse(path: Path) -> bool:
    try:
        stat = path.stat(follow_symlinks=False)
    except OSError:
        return True
    attributes = getattr(stat, "st_file_attributes", 0)
    reparse_flag = getattr(__import__("stat"), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def exact_tree_stat(path: Path) -> DirStat:
    errors: list[dict[str, str]] = []
    stats, _, total = scan_tree(path, errors)
    if errors or total.access_error_count:
        raise LifecycleError(f"tree is not fully readable: {path}: {errors[:3]}")
    if total.symlinks or path_is_reparse(path):
        raise LifecycleError(f"tree contains or is a symlink/reparse point: {path}")
    if path not in stats:
        raise LifecycleError(f"approved source is not a directory: {path}")
    return total


def ensure_real_ancestors(path: Path, stop: Path | None = None) -> None:
    current = path
    chain: list[Path] = []
    while True:
        chain.append(current)
        if stop is not None and current == stop:
            break
        if current.parent == current:
            break
        current = current.parent
    for item in reversed(chain):
        if item.exists() and path_is_reparse(item):
            raise LifecycleError(f"path ancestor is a symlink/reparse point: {item}")


def quarantine_exact(
    *,
    state_root: Path,
    plan_path: Path,
    approval_path: Path,
    quarantine_root: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    state_root = state_root.resolve(strict=True)
    plan = load_json(plan_path)
    approval = load_json(approval_path)
    if plan.get("schema") != SCHEMA or plan.get("kind") != "deletion_plan" or plan.get("mode") != "DRY_RUN_ONLY":
        raise LifecycleError("quarantine requires an exact workspace-lifecycle dry-run plan")
    if approval.get("schema") != "workspace-quarantine-approval-v1":
        raise LifecycleError("approval schema mismatch")
    if approval.get("dry_run_plan_sha256") != sha256(plan_path):
        raise LifecycleError("approval does not bind the exact dry-run plan")
    registry_path = state_root / "contracts/current_session_owner_registry_v1.json"
    registry = load_json(registry_path)
    epoch = registry.get("registry_epoch")
    if epoch != plan.get("registry_epoch") or epoch != approval.get("registry_epoch"):
        raise LifecycleError(
            f"registry epoch drift: current={epoch} plan={plan.get('registry_epoch')} approval={approval.get('registry_epoch')}"
        )
    approved_paths = approval.get("approved_paths")
    if not isinstance(approved_paths, list) or not approved_paths or len(approved_paths) != len(set(approved_paths)):
        raise LifecycleError("approval requires a non-empty unique approved_paths list")
    candidate_map = {item["path"]: item for item in plan.get("candidates", [])}
    quarantine_root = quarantine_root.resolve(strict=False)
    if inside(quarantine_root, state_root):
        raise LifecycleError("quarantine root must be outside the canonical state root")
    ensure_real_ancestors(quarantine_root)

    prepared: list[tuple[Path, Path, str, DirStat]] = []
    for relative_path in approved_paths:
        candidate = candidate_map.get(relative_path)
        if not candidate or candidate.get("safety_state") != "SAFE_TO_QUARANTINE_AFTER_REVIEW":
            raise LifecycleError(f"path is not exact approved-safe candidate: {relative_path}")
        source = (state_root / relative_path).resolve(strict=True)
        if not inside(source, state_root):
            raise LifecycleError(f"approved source escapes canonical root: {relative_path}")
        if relative(source, state_root) != Path(relative_path).as_posix():
            raise LifecycleError(f"approved source canonical path drift: {relative_path}")
        tree = exact_tree_stat(source)
        destination = quarantine_root / Path(relative_path)
        ensure_real_ancestors(destination.parent, quarantine_root)
        if destination.exists() or destination.is_symlink():
            raise LifecycleError(f"quarantine destination already exists: {destination}")
        prepared.append((source, destination, relative_path, tree))

    moved: list[tuple[Path, Path, str, DirStat]] = []
    try:
        for source, destination, relative_path, tree in prepared:
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved.append((source, destination, relative_path, tree))
        records: list[dict[str, Any]] = []
        for source, destination, relative_path, before in moved:
            if source.exists() or source.is_symlink():
                raise LifecycleError(f"source remains after quarantine move: {source}")
            after = exact_tree_stat(destination)
            if before.record() != after.record():
                raise LifecycleError(f"quarantine tree stats drifted: {relative_path}")
            records.append(
                {
                    "path": relative_path,
                    "source": str(source),
                    "destination": str(destination),
                    **before.record(),
                }
            )
        receipt = {
            "schema": "workspace-quarantine-receipt-v1",
            "pass": True,
            "state_root": str(state_root),
            "registry_epoch": epoch,
            "dry_run_plan": str(plan_path.resolve()),
            "dry_run_plan_sha256": sha256(plan_path),
            "approval": str(approval_path.resolve()),
            "approval_sha256": sha256(approval_path),
            "quarantine_root": str(quarantine_root),
            "moved": records,
            "generated_at_utc": utc_now(),
            "claim_boundary": "Exact reversible local quarantine only; no permanent delete, package, storage, control-plane or server action."
        }
        write_json(receipt_path, receipt)
        return receipt
    except Exception:
        for source, destination, _, _ in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)
        raise


def verify_quarantine(
    *, state_root: Path, receipt_path: Path, output_path: Path
) -> dict[str, Any]:
    state_root = state_root.resolve(strict=True)
    receipt = load_json(receipt_path)
    if receipt.get("schema") != "workspace-quarantine-receipt-v1" or receipt.get("pass") is not True:
        raise LifecycleError("invalid quarantine receipt")
    registry = load_json(state_root / "contracts/current_session_owner_registry_v1.json")
    errors: list[str] = []
    if registry.get("registry_epoch") != receipt.get("registry_epoch"):
        errors.append("registry epoch changed after quarantine")
    for item in receipt.get("moved", []):
        source = Path(item["source"])
        destination = Path(item["destination"])
        if source.exists() or source.is_symlink():
            errors.append(f"source reappeared: {source}")
            continue
        try:
            actual = exact_tree_stat(destination).record()
        except LifecycleError as error:
            errors.append(str(error))
            continue
        expected = {key: item[key] for key in ("files", "directories", "bytes", "symlinks", "access_error_count")}
        if actual != expected:
            errors.append(f"quarantine stats drifted: {destination}")
    verification = {
        "schema": "workspace-quarantine-verification-v1",
        "pass": not errors,
        "state_root": str(state_root),
        "registry_epoch": registry.get("registry_epoch"),
        "quarantine_receipt": str(receipt_path.resolve()),
        "quarantine_receipt_sha256": sha256(receipt_path),
        "errors": errors,
        "generated_at_utc": utc_now(),
        "claim_boundary": "Quarantine presence/absence and control-plane epoch only; external canonical audits are recorded separately."
    }
    write_json(output_path, verification)
    return verification


def purge_quarantine(
    *,
    receipt_path: Path,
    verification_path: Path,
    output_path: Path,
    confirm: str,
) -> dict[str, Any]:
    if confirm != "PERMANENT_DELETE_APPROVED_QUARANTINE":
        raise LifecycleError("permanent purge confirmation token mismatch")
    receipt = load_json(receipt_path)
    verification = load_json(verification_path)
    if verification.get("schema") != "workspace-quarantine-verification-v1" or verification.get("pass") is not True:
        raise LifecycleError("quarantine has not passed verification")
    if verification.get("quarantine_receipt_sha256") != sha256(receipt_path):
        raise LifecycleError("verification does not bind the exact quarantine receipt")
    quarantine_root = Path(receipt["quarantine_root"]).resolve(strict=True)
    deleted: list[dict[str, Any]] = []
    for item in receipt.get("moved", []):
        destination = Path(item["destination"]).resolve(strict=True)
        if not inside(destination, quarantine_root) or destination == quarantine_root:
            raise LifecycleError(f"purge destination escapes quarantine root: {destination}")
        if path_is_reparse(destination):
            raise LifecycleError(f"purge destination is a reparse point: {destination}")
        actual = exact_tree_stat(destination).record()
        expected = {key: item[key] for key in ("files", "directories", "bytes", "symlinks", "access_error_count")}
        if actual != expected:
            raise LifecycleError(f"purge destination stats drifted: {destination}")
        shutil.rmtree(destination)
        if destination.exists() or destination.is_symlink():
            raise LifecycleError(f"purge destination still exists: {destination}")
        deleted.append({"path": item["path"], "destination": str(destination), **expected})
    purge = {
        "schema": "workspace-quarantine-purge-receipt-v1",
        "pass": True,
        "quarantine_receipt": str(receipt_path.resolve()),
        "quarantine_receipt_sha256": sha256(receipt_path),
        "verification": str(verification_path.resolve()),
        "verification_sha256": sha256(verification_path),
        "deleted": deleted,
        "deleted_bytes": sum(item["bytes"] for item in deleted),
        "generated_at_utc": utc_now(),
        "claim_boundary": "Permanent deletion of the exact previously quarantined and verified directories only."
    }
    write_json(output_path, purge)
    return purge


def protection_intersections(
    path: Path,
    protected: dict[Path, set[str]],
    protected_keys: list[str],
    state_root: Path,
) -> list[str]:
    matches: list[str] = []
    resolved = path.resolve(strict=False)
    current: Path | None = resolved
    while current is not None:
        reasons = protected.get(current)
        if reasons:
            matches.extend(f"{current}: {reason}" for reason in sorted(reasons))
        if current == state_root:
            break
        parent = current.parent
        current = None if parent == current else parent

    rel = relative(resolved, state_root)
    prefix = rel.rstrip("/") + "/"
    start = bisect.bisect_left(protected_keys, prefix)
    for key in protected_keys[start:]:
        if not key.startswith(prefix):
            break
        item = state_root / Path(key)
        matches.extend(f"{item}: {reason}" for reason in sorted(protected[item.resolve(strict=False)]))
    return sorted(set(matches))


def candidate_kind(path: Path, policy: dict[str, Any], state_root: Path) -> tuple[str, str] | None:
    name = path.name
    exact_ephemeral = set(policy["ephemeral_exact_names"])
    ephemeral_prefixes = tuple(policy["ephemeral_prefixes"])
    exact_derived = set(policy["derived_exact_names"])
    derived_prefixes = tuple(policy["derived_prefixes"])
    if relative(path, state_root) == ".venv":
        return "REGENERABLE_ENVIRONMENT", "Local Python environment is reproducible from project lock files."
    if name in exact_ephemeral or name.startswith(ephemeral_prefixes):
        kind = "CACHE" if "cache" in name or name == "coverage" else "EPHEMERAL"
        return kind, "Exact policy-owned cache or ephemeral directory name."
    if name in exact_derived or name.startswith(derived_prefixes):
        return "REBUILDABLE_DERIVED", "Known build/extraction/failed-attempt surface; canonical anchor must be proven before deletion."
    return None


def parent_candidate(path: Path, candidate_paths: set[Path]) -> str | None:
    parents = [item for item in candidate_paths if item != path and item in path.parents]
    if not parents:
        return None
    return str(max(parents, key=lambda item: len(item.parts)))


def summarize_counts(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = Counter(item["candidate_kind"] for item in candidates)
    states = Counter(item["safety_state"] for item in candidates)
    return {
        "candidate_count": len(candidates),
        "by_kind": dict(sorted(kinds.items())),
        "by_safety_state": dict(sorted(states.items())),
        "candidate_bytes_including_overlaps": sum(item["bytes"] for item in candidates),
    }


def build_reports(state_root: Path, policy_path: Path) -> tuple[dict[str, Any], ...]:
    state_root = state_root.resolve(strict=True)
    policy = load_json(policy_path)
    if policy.get("schema") != "workspace-lifecycle-policy-v1" or policy.get("mode") != "DRY_RUN_ONLY":
        raise LifecycleError("policy is not workspace-lifecycle-policy-v1 DRY_RUN_ONLY")
    generated = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    access_errors: list[dict[str, str]] = []

    inputs = policy["control_plane_inputs"]
    registry_path = state_root / inputs["owner_registry"]
    registry = load_json(registry_path)
    registry_epoch = registry.get("registry_epoch")
    protected: dict[Path, set[str]] = defaultdict(set)
    source_counts: Counter[str] = Counter()

    for location, value in iter_path_values(registry):
        add_protection(protected, state_root, value, f"current owner registry {location}")
        source_counts["owner_registry"] += 1
        target = state_root / value if not Path(value).is_absolute() else Path(value)
        if inside(target, state_root):
            try:
                relative_parts = target.resolve(strict=False).relative_to(state_root).parts
            except ValueError:
                relative_parts = ()
            if relative_parts and relative_parts[0] == "outputs" and len(relative_parts) >= 2:
                add_protection(
                    protected,
                    state_root,
                    Path("outputs") / relative_parts[1],
                    f"current output root for registry pointer {location}",
                )

    plan_path = state_root / inputs["plan"]
    for value in text_references(plan_path):
        add_protection(protected, state_root, value, "current plan reference")
        source_counts["plan"] += 1

    records_root = state_root / inputs["task_records"]
    if records_root.is_dir():
        for record in records_root.glob("*.md"):
            for value in text_references(record):
                add_protection(protected, state_root, value, f"task record reference {record.name}")
                source_counts["task_records"] += 1

    storage_path = state_root / inputs["package_storage_index"]
    if storage_path.is_file():
        storage = load_json(storage_path)
        for package in storage.get("packages", []):
            if not isinstance(package, dict):
                continue
            disposition = package.get("disposition")
            for file_record in package.get("files", []):
                if not isinstance(file_record, dict) or not file_record.get("relative_path"):
                    continue
                add_protection(
                    protected,
                    state_root,
                    storage_path.parent.relative_to(state_root) / file_record["relative_path"],
                    f"managed storage {disposition} package {package.get('package_base')}",
                )
                source_counts[f"managed_storage_{disposition}"] += 1

    for value in git_tracked(state_root, warnings):
        add_protection(protected, state_root, value, "git tracked source/evidence")
        source_counts["git_tracked"] += 1

    roots: list[dict[str, Any]] = []
    all_stats: dict[Path, DirStat] = {}
    repeat_files: list[Path] = []
    totals = DirStat()
    scan_root_paths: list[Path] = []
    for entry in policy["scan_roots"]:
        scan_root = (state_root / entry["path"]).resolve(strict=False)
        if not inside(scan_root, state_root):
            errors.append(f"scan root escapes state root: {entry['path']}")
            continue
        scan_root_paths.append(scan_root)
        stats, repeats, root_stat = scan_tree(scan_root, access_errors)
        all_stats.update(stats)
        repeat_files.extend(repeats)
        totals.add(root_stat)
        roots.append(
            {
                "path": entry["path"],
                "kind": entry["kind"],
                "exists": scan_root.exists() or scan_root.is_symlink(),
                **root_stat.record(),
            }
        )

    protected_keys = sorted(relative(path, state_root) for path in protected)
    candidate_records: list[dict[str, Any]] = []
    candidate_paths: set[Path] = set()
    for path, stat in all_stats.items():
        classified = candidate_kind(path, policy, state_root)
        if classified is None:
            continue
        kind, reason = classified
        intersections = protection_intersections(path, protected, protected_keys, state_root)
        if stat.access_error_count or stat.symlinks:
            safety = "BLOCKED_ACCESS_OR_SYMLINK"
            requirements = ["resolve access errors and re-scan", "prove no symlink/reparse traversal"]
        elif intersections:
            safety = "PROTECTED"
            requirements = ["remove every current protection only through its owning lifecycle transition"]
        elif kind in {"EPHEMERAL", "CACHE"}:
            safety = "SAFE_TO_QUARANTINE_AFTER_REVIEW"
            requirements = ["confirm no active local process owns the path", "quarantine before first permanent delete"]
        else:
            safety = "REVIEW_REQUIRED"
            requirements = ["bind a canonical package/return or reproducible generator", "preserve final report and receipts"]
        candidate_paths.add(path)
        candidate_records.append(
            {
                "path": relative(path, state_root),
                "candidate_kind": kind,
                "safety_state": safety,
                **{key: value for key, value in stat.record().items() if key in {"files", "directories", "bytes"}},
                "reason": reason,
                "requirements": requirements,
                "protected_intersections": intersections,
                "overlap_parent": None,
                "duplicate_peer": None,
                "same_size": None,
            }
        )

    repeat_suffix = policy["repeat_zip_suffix"]
    for path in repeat_files:
        peer = path.with_name(path.name[: -len(repeat_suffix)] + ".zip")
        intersections = protection_intersections(path, protected, protected_keys, state_root)
        try:
            size = path.stat(follow_symlinks=False).st_size
        except OSError:
            size = 0
        same_size = peer.is_file() and not peer.is_symlink() and peer.stat().st_size == size
        if intersections:
            safety = "PROTECTED"
        elif same_size:
            safety = "DUPLICATE_CONFIRMATION_REQUIRED"
        else:
            safety = "REVIEW_REQUIRED"
        candidate_paths.add(path)
        candidate_records.append(
            {
                "path": relative(path, state_root),
                "candidate_kind": "DUPLICATE_REPEAT_ZIP",
                "safety_state": safety,
                "files": 1,
                "directories": 0,
                "bytes": size,
                "reason": "Repeat archive has a same-directory primary ZIP candidate; byte identity is deferred until destructive apply.",
                "requirements": ["hash this pair only at apply time", "keep the canonical primary or managed ZIP"],
                "protected_intersections": intersections,
                "overlap_parent": None,
                "duplicate_peer": relative(peer, state_root) if inside(peer, state_root) else str(peer),
                "same_size": same_size,
            }
        )

    normalized_paths = {Path(item["path"]): item for item in candidate_records}
    for item in candidate_records:
        path = Path(item["path"])
        for parent in path.parents:
            if parent in normalized_paths:
                item["overlap_parent"] = parent.as_posix()
                break

    candidate_records.sort(key=lambda item: (-item["bytes"], item["path"]))
    nonoverlap = sum(
        item["bytes"]
        for item in candidate_records
        if item["overlap_parent"] is None
        and item["safety_state"] in {"SAFE_TO_QUARANTINE_AFTER_REVIEW", "DUPLICATE_CONFIRMATION_REQUIRED", "REVIEW_REQUIRED"}
    )

    output_root = state_root / "outputs"
    unknown_entries: list[dict[str, Any]] = []
    if output_root in all_stats:
        for child in sorted(
            (path for path in all_stats if path.parent == output_root), key=lambda item: item.name
        ):
            intersections = protection_intersections(child, protected, protected_keys, state_root)
            stat = all_stats[child]
            top_candidate = any(Path(item["path"]) == Path("outputs") / child.name for item in candidate_records)
            if intersections or top_candidate:
                continue
            unknown_entries.append(
                {
                    "path": relative(child, state_root),
                    "files": stat.files,
                    "directories": stat.directories,
                    "bytes": stat.bytes,
                    "reason": "Legacy output root lacks a lifecycle manifest and is neither current-protected nor safely classified.",
                }
            )
    unknown_entries.sort(key=lambda item: (-item["bytes"], item["path"]))

    common = {
        "schema": SCHEMA,
        "state_root": str(state_root),
        "generated_at_utc": generated,
        "registry_epoch": registry_epoch,
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    inventory = {
        **common,
        "kind": "inventory",
        "policy": relative(policy_path, state_root) if inside(policy_path, state_root) else str(policy_path),
        "totals": totals.record(),
        "roots": roots,
        "access_errors": access_errors,
        "claim_boundary": "Read-only inventory of declared local roots; inaccessible contents are counted as errors, not assumed empty.",
    }
    protected_report = {
        **common,
        "kind": "protected_set",
        "entries": [
            {"path": relative(path, state_root), "reasons": sorted(reasons)}
            for path, reasons in sorted(protected.items(), key=lambda item: str(item[0]))
        ],
        "source_counts": dict(sorted(source_counts.items())),
        "claim_boundary": "Machine-derived protection inputs only; protection removal requires the owning control-plane transition.",
    }
    deletion_plan = {
        **common,
        "kind": "deletion_plan",
        "mode": "DRY_RUN_ONLY",
        "apply_authorized": False,
        "candidates": candidate_records,
        "candidate_summary": summarize_counts(candidate_records),
        "estimated_nonoverlap_bytes": nonoverlap,
        "next_checkpoint": "User reviews the exact quarantine set; no candidate is moved or deleted by this version.",
        "claim_boundary": "Candidate planning only. No path has been moved, deleted, overwritten or modified.",
    }
    unknown = {
        **common,
        "kind": "unknown_legacy",
        "entries": unknown_entries,
        "claim_boundary": "Unknown legacy roots remain protected pending owner/mainline classification.",
    }
    return inventory, protected_report, deletion_plan, unknown


def write_summary(output_dir: Path, reports: tuple[dict[str, Any], ...]) -> None:
    inventory, protected, plan, unknown = reports
    safe = [item for item in plan["candidates"] if item["safety_state"] == "SAFE_TO_QUARANTINE_AFTER_REVIEW"]
    duplicate = [item for item in plan["candidates"] if item["safety_state"] == "DUPLICATE_CONFIRMATION_REQUIRED"]
    review = [item for item in plan["candidates"] if item["safety_state"] == "REVIEW_REQUIRED"]
    blocked = [item for item in plan["candidates"] if item["safety_state"] in {"PROTECTED", "BLOCKED_ACCESS_OR_SYMLINK"}]
    lines = [
        "# Workspace lifecycle dry-run summary",
        "",
        f"- registry epoch: `{inventory['registry_epoch']}`",
        f"- scanned files: `{inventory['totals']['files']}`",
        f"- scanned bytes: `{inventory['totals']['bytes']}`",
        f"- access errors: `{inventory['totals']['access_error_count']}`",
        f"- protected entries: `{len(protected['entries'])}`",
        f"- safe quarantine candidates: `{len(safe)}`",
        f"- duplicate-confirmation candidates: `{len(duplicate)}`",
        f"- derived/rebuildable review candidates: `{len(review)}`",
        f"- protected/blocked candidates: `{len(blocked)}`",
        f"- unknown legacy output roots: `{len(unknown['entries'])}`",
        "",
        "No file was moved, deleted or overwritten. Version 1 has no destructive subcommand.",
        "",
    ]
    (output_dir / "reclaim_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        nargs="?",
        default="scan-plan",
        choices=["scan-plan", "quarantine", "verify-quarantine", "purge-quarantine"],
    )
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--quarantine-root", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--confirm")
    args = parser.parse_args()
    if args.action == "scan-plan":
        if not args.state_root or not args.policy or not args.output_dir:
            parser.error("scan-plan requires --state-root --policy --output-dir")
        reports = build_reports(args.state_root, args.policy)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        names = ("inventory.json", "protected_set.json", "deletion_plan.json", "unknown_legacy.json")
        for name, report in zip(names, reports):
            write_json(args.output_dir / name, report)
        write_summary(args.output_dir, reports)
        print(json.dumps({"pass": reports[0]["pass"], "output_dir": str(args.output_dir.resolve()), "mode": "DRY_RUN_ONLY"}, indent=2))
        return 0 if reports[0]["pass"] else 1
    if args.action == "quarantine":
        if not all((args.state_root, args.plan, args.approval, args.quarantine_root, args.receipt)):
            parser.error("quarantine requires --state-root --plan --approval --quarantine-root --receipt")
        result = quarantine_exact(
            state_root=args.state_root,
            plan_path=args.plan,
            approval_path=args.approval,
            quarantine_root=args.quarantine_root,
            receipt_path=args.receipt,
        )
    elif args.action == "verify-quarantine":
        if not all((args.state_root, args.receipt, args.output)):
            parser.error("verify-quarantine requires --state-root --receipt --output")
        result = verify_quarantine(
            state_root=args.state_root, receipt_path=args.receipt, output_path=args.output
        )
    else:
        if not all((args.receipt, args.verification, args.output, args.confirm)):
            parser.error("purge-quarantine requires --receipt --verification --output --confirm")
        result = purge_quarantine(
            receipt_path=args.receipt,
            verification_path=args.verification,
            output_path=args.output,
            confirm=args.confirm,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
