#!/usr/bin/env python3
"""Enforce observer whole-attempt operational growth and durable cleanup.

This helper never truncates, samples, rolls over, or deletes observer evidence
to stay within a byte budget.  It may terminate the *entire* owned attempt once
at a package-declared disk/growth boundary, preserve and flush all completed
rows, publish a diagnostic partial return, and clean exact owned leaves only
after the return ZIP and sidecar are durably verified.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


CONTRACT_SCHEMA = "server-observer-operational-attempt-boundary-v1"
RECEIPT_SCHEMA = "server-observer-operational-attempt-receipt-v1"
ACTIVATION_EPOCH = "observer-operational-attempt-boundary-v1"
PHASES = ("compile", "simulation", "finalization")
COMPONENTS = (
    "compile_outputs", "observer_chunks", "simulator_log_duplication",
    "parser_rewrite_scratch", "return_zip_staging", "publication_sidecar",
)
FORBIDDEN_CLAIMS = ["NATURAL_TERMINAL", "FORMAL_D", "E4", "E5"]
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PR_SET_CHILD_SUBREAPER = 36

GUARD_V2_PATH = Path(__file__).resolve().with_name("server_observer_operational_guard_v2.py")
GUARD_V2_SPEC = importlib.util.spec_from_file_location("server_observer_operational_guard_v2", GUARD_V2_PATH)
if GUARD_V2_SPEC is None or GUARD_V2_SPEC.loader is None:
    raise RuntimeError("cannot load observer operational guard v2")
GUARD_V2 = importlib.util.module_from_spec(GUARD_V2_SPEC)
GUARD_V2_SPEC.loader.exec_module(GUARD_V2)


class BoundaryError(ValueError):
    pass


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def safe_relative(value: str, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BoundaryError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise BoundaryError(f"{label} escapes its exact root")
    return path


def validate_contract(contract: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return {"schema": CONTRACT_SCHEMA, "errors": ["contract must be an object"], "pass": False}
    if contract.get("schema") != CONTRACT_SCHEMA:
        errors.append(f"schema must be {CONTRACT_SCHEMA}")
    if contract.get("activation_epoch") != ACTIVATION_EPOCH:
        errors.append(f"activation_epoch must be {ACTIVATION_EPOCH}")
    for key in ("package_id", "family", "claim_boundary"):
        if not isinstance(contract.get(key), str) or not contract.get(key):
            errors.append(f"{key} is required")

    source = contract.get("threshold_source")
    if not isinstance(source, dict):
        errors.append("threshold_source must be an identity object")
    else:
        try:
            safe_relative(source.get("path", ""), "threshold_source.path")
        except BoundaryError as exc:
            errors.append(str(exc))
        if not SHA_RE.fullmatch(str(source.get("sha256", ""))):
            errors.append("threshold_source.sha256 is invalid")
        if source.get("units") != "bytes":
            errors.append("threshold_source.units must be bytes")
        if not isinstance(source.get("method"), str) or not source.get("method"):
            errors.append("threshold_source.method is required")

    projection = contract.get("pre_run_peak_projection")
    if not isinstance(projection, dict):
        projection = {}
        errors.append("pre_run_peak_projection must be an object")
    components = projection.get("components")
    component_ids: list[str] = []
    component_sum = 0
    if not isinstance(components, list):
        errors.append("pre-run projection components must be an array")
        components = []
    for index, item in enumerate(components):
        if not isinstance(item, dict):
            errors.append(f"projection component {index} must be an object")
            continue
        component_id = item.get("component_id")
        if component_id not in COMPONENTS or component_id in component_ids:
            errors.append(f"invalid or duplicate projection component: {component_id}")
        else:
            component_ids.append(component_id)
        value = item.get("max_bytes")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"{component_id}: max_bytes must be a positive package-specific integer")
        else:
            component_sum += value
        if not isinstance(item.get("basis"), str) or not item.get("basis"):
            errors.append(f"{component_id}: projection basis is required")
    if set(component_ids) != set(COMPONENTS):
        errors.append(f"projection must cover exact components: {list(COMPONENTS)}")
    if projection.get("unknown_or_unbounded_amplification") is not False:
        errors.append("unknown or unbounded amplification must fail closed")
    if projection.get("peak_transient_bytes") != component_sum:
        errors.append("peak_transient_bytes must equal the exact component sum")
    reserve = projection.get("minimum_free_reserve_bytes")
    if not isinstance(reserve, int) or isinstance(reserve, bool) or reserve <= 0:
        errors.append("minimum_free_reserve_bytes must be a positive package-specific integer")
        reserve = 0
    if projection.get("start_required_free_bytes") != component_sum + reserve:
        errors.append("start_required_free_bytes must equal peak_transient_bytes plus reserve")

    watches = contract.get("phase_watches")
    seen_phases: set[str] = set()
    if not isinstance(watches, list):
        errors.append("phase_watches must be an array")
        watches = []
    for index, watch in enumerate(watches):
        if not isinstance(watch, dict):
            errors.append(f"phase watch {index} must be an object")
            continue
        phase = watch.get("phase")
        if phase not in PHASES or phase in seen_phases:
            errors.append(f"invalid or duplicate phase watch: {phase}")
        else:
            seen_phases.add(phase)
        paths = watch.get("watched_paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{phase}: watched_paths must be non-empty")
        else:
            for path in paths:
                try:
                    safe_relative(path, f"{phase}.watched_paths")
                except BoundaryError as exc:
                    errors.append(str(exc))
        for key in ("growth_limit_bytes", "remaining_projection_bytes"):
            value = watch.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"{phase}.{key} must be a positive package-specific integer")
        interval = watch.get("monitor_interval_seconds")
        if not isinstance(interval, (int, float)) or isinstance(interval, bool) or interval <= 0:
            errors.append(f"{phase}.monitor_interval_seconds must be positive")
    if seen_phases != set(PHASES):
        errors.append("phase_watches must cover compile, simulation and finalization exactly once")

    stop = contract.get("operational_stop")
    required_true = (
        "one_shot", "attempt_wide", "preserve_completed_rows", "flush_all_flushable_rows",
        "partial_exit_marker", "term_wait_kill_reap",
    )
    if not isinstance(stop, dict):
        stop = {}
        errors.append("operational_stop must be an object")
    for key in required_true:
        if stop.get(key) is not True:
            errors.append(f"operational_stop.{key} must be true")
    for key in ("event_cap", "byte_cap"):
        if stop.get(key) is not None:
            errors.append(f"operational_stop.{key} must remain null")
    for key in ("sampling", "truncation", "rolling_overwrite", "size_based_evidence_deletion"):
        if stop.get(key) is not False:
            errors.append(f"operational_stop.{key} must be false")
    if stop.get("diagnostic_status") != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
        errors.append("operational stop may only claim DIAGNOSTIC_EVIDENCE_INCOMPLETE")
    if stop.get("forbidden_claims") != FORBIDDEN_CLAIMS:
        errors.append("operational stop forbidden claims must be exact natural/formal-D/E4/E5 set")

    policy = contract.get("live_tree_policy")
    if not isinstance(policy, dict):
        errors.append("live_tree_policy must be a content-bound identity object")
    else:
        try:
            safe_relative(policy.get("path", ""), "live_tree_policy.path")
        except BoundaryError as exc:
            errors.append(str(exc))
        if policy.get("schema") != "server-observer-operational-live-tree-policy-v2":
            errors.append("live_tree_policy.schema must select v2")
        if not SHA_RE.fullmatch(str(policy.get("sha256", ""))):
            errors.append("live_tree_policy.sha256 is invalid")

    for section, keys in (
        ("durable_partial_return", ("atomic_unique_publication", "zip_crc_verified", "exact_member_set_verified", "sidecar_bytes_sha256_verified", "streaming_or_bounded_staging", "recursive_self_staging_forbidden")),
        ("post_durable_cleanup", (
            "after_durable_return_only", "exact_owned_attempt_and_bootstrap_leaves_only",
            "root_and_ancestor_symlinks_forbidden", "internal_owned_symlink_entries_no_follow",
            "internal_symlink_target_traversal_forbidden", "lexical_target_escape_forbidden",
            "special_entries_forbidden", "bounded_live_tree_resampling",
            "post_durable_unlink_internal_links_no_follow", "preserve_foreign_siblings",
            "failed_publication_uncleaned",
        )),
    ):
        value = contract.get(section)
        if not isinstance(value, dict):
            errors.append(f"{section} must be an object")
            continue
        for key in keys:
            if value.get(key) is not True:
                errors.append(f"{section}.{key} must be true")

    return {
        "schema": CONTRACT_SCHEMA,
        "package_id": contract.get("package_id"),
        "component_sum_bytes": component_sum,
        "minimum_free_reserve_bytes": reserve,
        "errors": sorted(set(errors)),
        "pass": not errors,
    }


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    report = validate_contract(contract)
    if not report["pass"]:
        raise BoundaryError("invalid operational contract: " + "; ".join(report["errors"]))
    return contract


def exact_watch(phase: str, contract: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in contract["phase_watches"] if item["phase"] == phase)


def require_inside(root: Path, relative: str) -> Path:
    rel = safe_relative(relative, "watched path")
    resolved_root = root.resolve(strict=True)
    path = (resolved_root / Path(*rel.parts)).resolve(strict=False)
    try:
        path.relative_to(resolved_root)
    except ValueError as exc:
        raise BoundaryError("watched path escapes attempt root") from exc
    return path


def measure_path(path: Path) -> tuple[int, list[dict[str, Any]]]:
    if not path.exists():
        return 0, []
    if path.is_symlink():
        raise BoundaryError(f"watched path is a symlink: {path}")
    mode = path.stat(follow_symlinks=False).st_mode
    if stat.S_ISREG(mode):
        return path.stat().st_size, [{"path": str(path), "bytes": path.stat().st_size}]
    if not stat.S_ISDIR(mode):
        raise BoundaryError(f"watched path is special: {path}")
    total = 0
    entries: list[dict[str, Any]] = []
    for child in sorted(path.rglob("*")):
        if child.is_symlink():
            raise BoundaryError(f"watched tree contains symlink: {child}")
        child_mode = child.stat(follow_symlinks=False).st_mode
        if stat.S_ISDIR(child_mode):
            continue
        if not stat.S_ISREG(child_mode):
            raise BoundaryError(f"watched tree contains special file: {child}")
        size = child.stat().st_size
        total += size
        entries.append({"path": str(child), "bytes": size})
    return total, entries


def measure_phase(contract: dict[str, Any], phase: str, attempt_root: Path) -> dict[str, Any]:
    watch = exact_watch(phase, contract)
    total = 0
    exact_set: list[dict[str, Any]] = []
    for relative in watch["watched_paths"]:
        size, entries = measure_path(require_inside(attempt_root, relative))
        total += size
        exact_set.extend(entries)
    return {"watched_bytes": total, "exact_set": exact_set}


def evaluate_sample(
    contract: dict[str, Any], phase: str, baseline_bytes: int,
    watched_bytes: int, filesystem_free_bytes: int, stop_count: int,
) -> dict[str, Any]:
    watch = exact_watch(phase, contract)
    reserve = contract["pre_run_peak_projection"]["minimum_free_reserve_bytes"]
    growth = max(0, watched_bytes - baseline_bytes)
    reasons: list[str] = []
    if growth > watch["growth_limit_bytes"]:
        reasons.append("PHASE_GROWTH_LIMIT")
    if filesystem_free_bytes < reserve:
        reasons.append("FILESYSTEM_RESERVE_FLOOR")
    if filesystem_free_bytes - reserve < watch["remaining_projection_bytes"]:
        reasons.append("REMAINING_PROJECTION_EXCEEDS_SAFE_FREE")
    if reasons and stop_count != 0:
        reasons.append("REPEATED_OPERATIONAL_STOP")
    return {
        "phase": phase,
        "baseline_bytes": baseline_bytes,
        "watched_bytes": watched_bytes,
        "growth_bytes": growth,
        "growth_limit_bytes": watch["growth_limit_bytes"],
        "remaining_projection_bytes": watch["remaining_projection_bytes"],
        "filesystem_free_bytes": filesystem_free_bytes,
        "minimum_free_reserve_bytes": reserve,
        "trigger_reasons": reasons,
        "should_stop": bool(reasons),
        "valid_one_shot": not reasons or stop_count == 0,
    }


def preflight(contract: dict[str, Any], attempt_root: Path) -> dict[str, Any]:
    projection = contract["pre_run_peak_projection"]
    free = shutil.disk_usage(attempt_root).free
    required = projection["start_required_free_bytes"]
    errors = [] if free >= required else ["pre-run free space is below projected peak plus reserve"]
    return {
        "schema": "server-observer-operational-preflight-receipt-v1",
        "package_id": contract["package_id"],
        "attempt_root": str(attempt_root.resolve()),
        "projection_components": projection["components"],
        "peak_transient_bytes": projection["peak_transient_bytes"],
        "minimum_free_reserve_bytes": projection["minimum_free_reserve_bytes"],
        "start_required_free_bytes": required,
        "filesystem_free_bytes": free,
        "errors": errors,
        "pass": not errors,
    }


def enable_subreaper() -> None:
    if sys.platform != "linux":
        raise BoundaryError("production operational supervision requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise BoundaryError(f"PR_SET_CHILD_SUBREAPER failed: errno={ctypes.get_errno()}")


def group_pids(pgid: int) -> list[int]:
    completed = subprocess.run(["ps", "-eo", "pid=,pgid="], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise BoundaryError("ps failed while checking owned process group")
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit() and int(fields[1]) == pgid:
            pid = int(fields[0])
            if pid != os.getpid():
                pids.append(pid)
    return sorted(set(pids))


def terminate_group(process: subprocess.Popen[Any], grace: float) -> dict[str, Any]:
    pgid = os.getpgid(process.pid)
    actions: list[dict[str, Any]] = []
    try:
        os.killpg(pgid, signal.SIGTERM)
        actions.append({"signal": "TERM", "pgid": pgid})
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and group_pids(pgid):
        time.sleep(0.05)
    remaining = group_pids(pgid)
    if remaining:
        try:
            os.killpg(pgid, signal.SIGKILL)
            actions.append({"signal": "KILL", "pgid": pgid, "pids": remaining})
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=max(grace, 0.1))
    except subprocess.TimeoutExpired:
        pass
    final = group_pids(pgid)
    return {"actions": actions, "owned_pids_remaining": final, "process_tree_reaped": not final}


def read_flush_receipt(path: Path | None, stopped: bool) -> tuple[bool, bool, list[str]]:
    if not stopped:
        return True, True, []
    if path is None or not path.exists() or not path.is_file() or path.is_symlink():
        return False, False, ["operational stop lacks safe flush/partial-exit receipt"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, False, [f"invalid flush receipt: {exc}"]
    completed = receipt.get("completed_rows_preserved") is True
    flushed = receipt.get("flushable_rows_flushed") is True and receipt.get("partial_exit_marker_written") is True
    errors = [] if completed and flushed else ["operational stop did not preserve/flush completed rows and partial marker"]
    return completed, flushed, errors


def supervise_phase(args: argparse.Namespace, contract: dict[str, Any]) -> tuple[dict[str, Any], int]:
    attempt_root = GUARD_V2.require_real_directory(args.attempt_root, "attempt root")
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise BoundaryError("phase command is required")
    watch = exact_watch(args.phase, contract)
    guard_args = argparse.Namespace(
        package_id=contract["package_id"], execution_id=args.execution_id,
        attempt_id=args.attempt_id, mode=args.phase, attempt_root=attempt_root,
        owned_root=[], cwd=args.cwd, disk_path=attempt_root,
        min_free_bytes=contract["pre_run_peak_projection"]["minimum_free_reserve_bytes"],
        growth_limit_bytes=watch["growth_limit_bytes"], watch=[], timeout=args.timeout,
        interval=watch["monitor_interval_seconds"], grace=args.grace,
        max_resamples=3, resample_delay=0.01, receipt=args.receipt,
        log=args.guard_log, command=command,
    )
    receipt, code = GUARD_V2.supervise(guard_args)
    args.samples.parent.mkdir(parents=True, exist_ok=True)
    with args.samples.open("a", encoding="utf-8", newline="\n") as stream:
        for sample in receipt.get("samples", []):
            stream.write(json.dumps(sample, sort_keys=True) + "\n")
    stopped = receipt.get("stop_count") == 1
    if args.phase == "compile" and receipt.get("command_started") is True:
        completed, flushed, flush_errors = True, True, []
    else:
        completed, flushed, flush_errors = read_flush_receipt(args.flush_receipt, stopped)
    receipt.update({
        "completed_rows_preserved": completed,
        "flushable_rows_flushed": flushed,
        "process_tree_reaped": receipt.get("process_fully_reaped") is True,
        "forbidden_claims_asserted": False,
        "errors": sorted(set([*receipt.get("errors", []), *flush_errors])),
    })
    receipt["pass"] = bool(receipt.get("pass") is True and not receipt["errors"])
    atomic_write(args.receipt, receipt)
    return receipt, int(code)


def validate_receipt(receipt: Any) -> dict[str, Any]:
    if isinstance(receipt, dict) and receipt.get("schema") == GUARD_V2.SCHEMA:
        report = GUARD_V2.validate_receipt(receipt)
        errors = list(report["errors"])
        if receipt.get("stop_count") == 1:
            if receipt.get("completed_rows_preserved") is not True or receipt.get("flushable_rows_flushed") is not True:
                errors.append("completed/flushable rows were not preserved")
        if receipt.get("forbidden_claims_asserted") is not False:
            errors.append("operational stop asserted forbidden natural/formal/E4/E5 claim")
        return {"schema": GUARD_V2.SCHEMA, "errors": sorted(set(errors)), "pass": not errors}
    errors: list[str] = []
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA:
        return {"schema": RECEIPT_SCHEMA, "errors": ["invalid operational receipt schema"], "pass": False}
    stop_count = receipt.get("stop_count")
    if stop_count not in (0, 1):
        errors.append("stop_count must be zero or one")
    if stop_count == 1:
        if not isinstance(receipt.get("trigger"), dict):
            errors.append("operational stop lacks exact trigger")
        if receipt.get("diagnostic_status") != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
            errors.append("operational stop cannot claim COMPLETE")
    if receipt.get("completed_rows_preserved") is not True or receipt.get("flushable_rows_flushed") is not True:
        errors.append("completed/flushable rows were not preserved")
    if receipt.get("process_tree_reaped") is not True:
        errors.append("process tree was not reaped")
    if receipt.get("forbidden_claims_asserted") is not False:
        errors.append("operational stop asserted forbidden natural/formal/E4/E5 claim")
    if receipt.get("errors"):
        errors.extend(f"receipt: {item}" for item in receipt["errors"])
    return {"schema": RECEIPT_SCHEMA, "errors": sorted(set(errors)), "pass": not errors}


def safe_zip_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        if name.startswith("/") or "\\" in name or ".." in pure.parts or name in seen:
            raise BoundaryError(f"unsafe or duplicate ZIP member: {name}")
        seen.add(name)
        names.append(name)
    return names


def tree_digest(root: Path, excluded: set[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        resolved = path.resolve(strict=False)
        if any(resolved == item or item in resolved.parents for item in excluded):
            continue
        if path.is_symlink():
            raise BoundaryError(f"foreign tree contains symlink: {path}")
        mode = path.stat(follow_symlinks=False).st_mode
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8") + b"\0")
        if stat.S_ISREG(mode):
            size, sha = sha256_file(path)
            digest.update(str(size).encode() + b":" + sha.encode())
        elif not stat.S_ISDIR(mode):
            raise BoundaryError(f"foreign tree contains special file: {path}")
    return digest.hexdigest()


def remove_owned_tree_nofollow(path: Path, owned_root: Path) -> list[str]:
    """Remove one already-validated owned tree without following link targets."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return []
    deleted: list[str] = []
    if stat.S_ISLNK(info.st_mode):
        GUARD_V2.unlink_exact_owned_link_entry(path, [owned_root])
        return [str(path)]
    if stat.S_ISREG(info.st_mode):
        os.unlink(path)
        return [str(path)]
    if not stat.S_ISDIR(info.st_mode):
        raise BoundaryError(f"owned cleanup tree contains special entry: {path}")
    with os.scandir(path) as iterator:
        children = sorted((Path(item.path) for item in iterator), key=str, reverse=True)
    for child in children:
        deleted.extend(remove_owned_tree_nofollow(child, owned_root))
    os.rmdir(path)
    deleted.append(str(path))
    return deleted


def durable_cleanup(args: argparse.Namespace, contract: dict[str, Any]) -> dict[str, Any]:
    attempt_root = GUARD_V2.require_real_directory(args.attempt_root, "attempt root")
    return_zip = args.return_zip.resolve(strict=True)
    sidecar_path = args.sidecar.resolve(strict=True)
    receipt_path = args.receipt.resolve(strict=False)
    try:
        receipt_path.relative_to(attempt_root)
    except ValueError:
        pass
    else:
        raise BoundaryError("durability/cleanup receipt must be outside the attempt root")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    size, sha = sha256_file(return_zip)
    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        names = safe_zip_names(archive)
    errors: list[str] = []
    if bad is not None:
        errors.append(f"return ZIP CRC failure: {bad}")
    if sidecar.get("bytes") != size or sidecar.get("sha256") != sha:
        errors.append("sidecar bytes/SHA do not bind exact return ZIP")
    if sidecar.get("members") != names:
        errors.append("sidecar exact member set does not bind return ZIP order")

    owned: list[Path] = []
    for relative in args.owned_leaf:
        rel = safe_relative(relative, "owned cleanup leaf")
        path = Path(os.path.abspath(os.path.normpath(os.fspath(attempt_root / Path(*rel.parts)))))
        try:
            path.relative_to(attempt_root)
        except ValueError:
            errors.append(f"owned cleanup target escapes attempt root: {relative}")
            continue
        if path == attempt_root:
            errors.append("attempt root itself cannot be an owned cleanup leaf")
            continue
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            info = None
        if info is not None and stat.S_ISLNK(info.st_mode):
            errors.append(f"owned cleanup root is a symlink: {relative}")
        elif info is not None and stat.S_ISDIR(info.st_mode):
            try:
                GUARD_V2.snapshot_owned_roots([path], max_resamples=3, resample_delay_seconds=0.01)
            except (GUARD_V2.GuardError, OSError) as exc:
                errors.append(f"owned cleanup live-tree policy failed for {relative}: {exc}")
        elif info is not None and not stat.S_ISREG(info.st_mode):
            errors.append(f"owned cleanup target is special: {relative}")
        owned.append(path)
    if len(set(owned)) != len(owned):
        errors.append("owned cleanup leaf list contains duplicates")
    for left in owned:
        for right in owned:
            if left != right and (left in right.parents or right in left.parents):
                errors.append("owned cleanup leaves overlap")
    foreign_before = tree_digest(attempt_root, set(owned)) if not errors else None
    durable = not errors
    deleted: list[str] = []
    if args.execute and durable:
        for path in owned:
            deleted.extend(remove_owned_tree_nofollow(path, path if path.is_dir() else attempt_root))
    foreign_after = tree_digest(attempt_root, set(owned)) if not errors else None
    if foreign_before != foreign_after:
        errors.append("foreign sibling tree changed during exact cleanup")
    receipt = {
        "schema": "server-observer-post-durable-cleanup-receipt-v1",
        "package_id": contract["package_id"],
        "return_zip": {"path": str(return_zip), "bytes": size, "sha256": sha, "crc_pass": bad is None, "members": names},
        "sidecar": {"path": str(sidecar_path), "bytes": sidecar_path.stat().st_size, "sha256": sha256_file(sidecar_path)[1]},
        "durable_return_verified_before_cleanup": durable,
        "cleanup_executed": bool(args.execute and durable),
        "owned_leaves": [str(path) for path in owned],
        "deleted": deleted,
        "foreign_tree_sha256_before": foreign_before,
        "foreign_tree_sha256_after": foreign_after,
        "foreign_siblings_preserved": foreign_before == foreign_after,
        "failed_publication_uncleaned": not durable and not deleted,
        "errors": errors,
        "pass": not errors,
        "claim_boundary": "Durable return identity and exact-owned cleanup only.",
    }
    atomic_write(args.receipt, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)
    validate = sub.add_parser("validate-contract")
    validate.add_argument("--contract", type=Path, required=True)
    validate.add_argument("--output", type=Path)
    pre = sub.add_parser("preflight")
    pre.add_argument("--contract", type=Path, required=True)
    pre.add_argument("--attempt-root", type=Path, required=True)
    pre.add_argument("--receipt", type=Path, required=True)
    run = sub.add_parser("supervise-phase")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--phase", choices=PHASES, required=True)
    run.add_argument("--execution-id", required=True)
    run.add_argument("--attempt-id", required=True)
    run.add_argument("--attempt-root", type=Path, required=True)
    run.add_argument("--cwd", type=Path, required=True)
    run.add_argument("--samples", type=Path, required=True)
    run.add_argument("--flush-receipt", type=Path)
    run.add_argument("--receipt", type=Path, required=True)
    run.add_argument("--guard-log", type=Path, required=True)
    run.add_argument("--timeout", type=float, required=True)
    run.add_argument("--grace", type=float, default=10.0)
    run.add_argument("command", nargs=argparse.REMAINDER)
    check = sub.add_parser("validate-receipt")
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--output", type=Path)
    clean = sub.add_parser("cleanup-after-durable-return")
    clean.add_argument("--contract", type=Path, required=True)
    clean.add_argument("--attempt-root", type=Path, required=True)
    clean.add_argument("--return-zip", type=Path, required=True)
    clean.add_argument("--sidecar", type=Path, required=True)
    clean.add_argument("--owned-leaf", action="append", default=[], required=True)
    clean.add_argument("--receipt", type=Path, required=True)
    clean.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.command_name == "validate-contract":
        report = validate_contract(json.loads(args.contract.read_text(encoding="utf-8")))
        code = 0 if report["pass"] else 1
    elif args.command_name == "validate-receipt":
        report = validate_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
        code = 0 if report["pass"] else 1
    else:
        contract = load_contract(args.contract)
        if args.command_name == "preflight":
            report = preflight(contract, args.attempt_root)
            atomic_write(args.receipt, report)
            code = 0 if report["pass"] else 1
        elif args.command_name == "supervise-phase":
            report, code = supervise_phase(args, contract)
        else:
            report = durable_cleanup(args, contract)
            code = 0 if report["pass"] else 1
    payload = json_bytes(report)
    output = getattr(args, "output", None)
    if output:
        atomic_write(output, report)
    elif args.command_name not in ("preflight", "supervise-phase", "cleanup-after-durable-return"):
        sys.stdout.buffer.write(payload)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
