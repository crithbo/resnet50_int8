#!/usr/bin/env python3
"""Publish a minimal, recoverable return after a simulator has exited.

The package runner supplies one JSON request and a fixed set of environment
variables.  This helper persists the simulator exit receipt before executing
any package-specific analysis plugin.  Plugin failures and missing evidence
degrade the returned adjudication status but cannot suppress publication of
the core return.  No family-specific positional ``collect()`` wrapper is used.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA = "server-post-sim-return-request-v1"
CONTRACT_SCHEMA = "server-post-sim-return-contract-v1"
VALIDATION_SCHEMA = "server-post-sim-return-validation-v1"
PARTIAL_EXIT_RULE_ID = "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"
WAVE_PLAN_SCHEMA = "server-waveform-mandatory-plan-v2"
WAVE_RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v2"
FSDB_WAVE_PLAN_SCHEMA = "server-waveform-mandatory-plan-v3"
FSDB_WAVE_RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v3"
FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ENV_KEYS = {
    "package_root": "CODEX_PACKAGE_ROOT",
    "attempt_root": "CODEX_ATTEMPT_ROOT",
    "execution_id": "CODEX_EXECUTION_ID",
    "sim_exit_code": "CODEX_SIM_EXIT_CODE",
    "sim_signal": "CODEX_SIM_SIGNAL",
    "sim_started": "CODEX_SIM_STARTED",
    "natural_terminal": "CODEX_NATURAL_TERMINAL",
}
REQUIRED_RUNNER_TOKENS = (
    "CODEX_PACKAGE_ROOT",
    "CODEX_ATTEMPT_ROOT",
    "CODEX_EXECUTION_ID",
    "CODEX_SIM_EXIT_CODE",
    "CODEX_SIM_SIGNAL",
    "CODEX_SIM_STARTED",
    "CODEX_NATURAL_TERMINAL",
    "server_post_sim_return.py",
    "finalize --request",
    "RETURN_FINALIZER_STATE.json",
)
FORBIDDEN_WRAPPER_TOKENS = (
    "base.collect",
    "_base_collect",
    ".collect(",
    "def collect(",
)


class ReturnCoreError(ValueError):
    """The shared return-core request or publication is unsafe."""


def _waveform_profile(plan: Mapping[str, Any]) -> dict[str, str]:
    if plan.get("schema") == WAVE_PLAN_SCHEMA:
        return {
            "format": "VPD",
            "receipt_schema": WAVE_RECEIPT_SCHEMA,
            "primary": "wave.vpd",
            "kind": "waveform_vpd",
        }
    if plan.get("schema") == FSDB_WAVE_PLAN_SCHEMA:
        return {
            "format": "FSDB",
            "receipt_schema": FSDB_WAVE_RECEIPT_SCHEMA,
            "primary": "wave.fsdb",
            "kind": "waveform_fsdb",
        }
    raise ReturnCoreError("mandatory waveform plan schema mismatch")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            digest.update(block)
    return total, digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(_json_bytes(value))
    os.replace(temporary, path)


def _safe_name(label: str, value: Any) -> str:
    if not isinstance(value, str) or SAFE_NAME.fullmatch(value) is None:
        raise ReturnCoreError(f"{label} is not a safe name")
    return value


def _safe_relative(label: str, value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ReturnCoreError(f"{label} must be a non-empty relative path")
    if "\\" in value:
        raise ReturnCoreError(f"{label} uses a backslash")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReturnCoreError(f"{label} is unsafe: {value}")
    return path


def _real_directory(label: str, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ReturnCoreError(f"{label} must be absolute")
    if path.is_symlink() or not path.is_dir():
        raise ReturnCoreError(f"{label} must be a real directory")
    return path.resolve()


def _inside(root: Path, relative: PurePosixPath) -> Path:
    path = root.joinpath(*relative.parts)
    resolved_parent = path.parent.resolve()
    try:
        resolved_parent.relative_to(root)
    except ValueError as error:
        raise ReturnCoreError(f"path escapes root: {relative}") from error
    if path.is_symlink():
        raise ReturnCoreError(f"source is a symlink: {relative}")
    return path


def _bool_env(label: str, value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    raise ReturnCoreError(f"{label} must be a boolean environment value")


def _runtime_from_env(environment: Mapping[str, str]) -> dict[str, Any]:
    missing = [name for name in ENV_KEYS.values() if name not in environment]
    if missing:
        raise ReturnCoreError(f"runtime environment is incomplete: {sorted(missing)}")
    execution_id = _safe_name("execution_id", environment[ENV_KEYS["execution_id"]])
    signal = environment[ENV_KEYS["sim_signal"]].strip()
    if signal not in {"NONE", "HUP", "INT", "TERM", "EXIT"}:
        raise ReturnCoreError("CODEX_SIM_SIGNAL is invalid")
    try:
        exit_code = int(environment[ENV_KEYS["sim_exit_code"]], 10)
    except ValueError as error:
        raise ReturnCoreError("CODEX_SIM_EXIT_CODE is not decimal") from error
    if exit_code < 0 or exit_code > 255:
        raise ReturnCoreError("CODEX_SIM_EXIT_CODE is outside [0,255]")
    return {
        "package_root": _real_directory(
            "package_root", environment[ENV_KEYS["package_root"]]
        ),
        "attempt_root": _real_directory(
            "attempt_root", environment[ENV_KEYS["attempt_root"]]
        ),
        "execution_id": execution_id,
        "sim_exit_code": exit_code,
        "sim_signal": signal,
        "sim_started": _bool_env(
            "CODEX_SIM_STARTED", environment[ENV_KEYS["sim_started"]]
        ),
        "natural_terminal": _bool_env(
            "CODEX_NATURAL_TERMINAL",
            environment[ENV_KEYS["natural_terminal"]],
        ),
    }


def validate_request(request: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(request, dict):
        return ["request must be an object"]
    allowed = {
        "schema",
        "package_id",
        "result_root",
        "return_basename_template",
        "core_entries",
        "waveform_discovery",
        "plugins",
        "max_plugin_output_bytes",
        "claim_boundary",
    }
    extras = sorted(set(request) - allowed)
    if extras:
        errors.append(f"unknown request fields: {extras}")
    if request.get("schema") != SCHEMA:
        errors.append("request schema mismatch")
    try:
        _safe_name("package_id", request.get("package_id"))
    except ReturnCoreError as error:
        errors.append(str(error))
    if request.get("result_root") != FIXED_RESULT_ROOT:
        errors.append("result_root must be the fixed simresult path")
    if request.get("return_basename_template") != (
        "{package_id}_{execution_id}_return.zip"
    ):
        errors.append("return basename template mismatch")
    maximum = request.get("max_plugin_output_bytes")
    if not isinstance(maximum, int) or maximum < 1024 or maximum > 1_048_576:
        errors.append("max_plugin_output_bytes must be in [1024,1048576]")
    entries = request.get("core_entries")
    if not isinstance(entries, list) or not entries:
        errors.append("core_entries must be a non-empty array")
        entries = []
    archives: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"core_entries[{index}] must be an object")
            continue
        if set(entry) != {"source_root", "source", "archive", "required"}:
            errors.append(f"core_entries[{index}] fields mismatch")
            continue
        if entry.get("source_root") not in {"attempt", "package"}:
            errors.append(f"core_entries[{index}].source_root invalid")
        for key in ("source", "archive"):
            try:
                _safe_relative(f"core_entries[{index}].{key}", entry.get(key))
            except ReturnCoreError as error:
                errors.append(str(error))
        archive = entry.get("archive")
        if isinstance(archive, str):
            if archive in archives:
                errors.append(f"duplicate archive path: {archive}")
            archives.add(archive)
        if not isinstance(entry.get("required"), bool):
            errors.append(f"core_entries[{index}].required must be boolean")
    discovery = request.get("waveform_discovery")
    if discovery is not None:
        expected = {
            "plan_member",
            "collector_member",
            "runtime_receipt_source",
            "collect_all_matching",
            "required_when_simulation_started",
            "no_size_limit",
            "manifest_archive_path",
        }
        if not isinstance(discovery, dict):
            errors.append("waveform_discovery must be an object")
        elif set(discovery) != expected:
            errors.append("waveform_discovery fields mismatch")
        else:
            constants = {
                "plan_member": "contracts/server_waveform_mandatory_plan.json",
                "collector_member": "package_tools/server_waveform_mandatory_return.py",
                "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
                "collect_all_matching": True,
                "required_when_simulation_started": True,
                "no_size_limit": True,
            }
            for field, expected_value in constants.items():
                if discovery.get(field) != expected_value:
                    errors.append(
                        f"waveform_discovery.{field} must be {expected_value!r}"
                    )
            for field in (
                "plan_member",
                "collector_member",
                "runtime_receipt_source",
                "manifest_archive_path",
            ):
                try:
                    _safe_relative(
                        f"waveform_discovery.{field}", discovery.get(field)
                    )
                except ReturnCoreError as error:
                    errors.append(str(error))
            manifest = discovery.get("manifest_archive_path")
            if isinstance(manifest, str) and manifest in archives:
                errors.append(f"duplicate archive path: {manifest}")
    plugins = request.get("plugins")
    if not isinstance(plugins, list):
        errors.append("plugins must be an array")
        plugins = []
    plugin_ids: set[str] = set()
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            errors.append(f"plugins[{index}] must be an object")
            continue
        required = {
            "plugin_id",
            "argv",
            "cwd_root",
            "timeout_seconds",
            "required_for_adjudication",
        }
        if set(plugin) != required:
            errors.append(f"plugins[{index}] fields mismatch")
            continue
        try:
            plugin_id = _safe_name("plugin_id", plugin.get("plugin_id"))
            if plugin_id in plugin_ids:
                errors.append(f"duplicate plugin_id: {plugin_id}")
            plugin_ids.add(plugin_id)
        except ReturnCoreError as error:
            errors.append(str(error))
        argv = plugin.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
        ):
            errors.append(f"plugins[{index}].argv invalid")
        if plugin.get("cwd_root") not in {"attempt", "package"}:
            errors.append(f"plugins[{index}].cwd_root invalid")
        timeout = plugin.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout < 1 or timeout > 600:
            errors.append(f"plugins[{index}].timeout_seconds invalid")
        if not isinstance(plugin.get("required_for_adjudication"), bool):
            errors.append(
                f"plugins[{index}].required_for_adjudication must be boolean"
            )
    if not isinstance(request.get("claim_boundary"), str) or not request.get(
        "claim_boundary"
    ):
        errors.append("claim_boundary must be a non-empty string")
    return errors


def _expand_argv(argv: list[str], runtime: dict[str, Any]) -> list[str]:
    replacements = {
        "{package_root}": str(runtime["package_root"]),
        "{attempt_root}": str(runtime["attempt_root"]),
        "{execution_id}": runtime["execution_id"],
    }
    expanded: list[str] = []
    for argument in argv:
        value = argument
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
        if "{" in value or "}" in value:
            raise ReturnCoreError(f"unknown plugin argv placeholder: {argument}")
        expanded.append(value)
    return expanded


def _bounded(data: bytes, maximum: int) -> tuple[bytes, bool]:
    if len(data) <= maximum:
        return data, False
    half = maximum // 2
    marker = b"\n...CODEX_RETURN_CORE_TRUNCATED...\n"
    retained = data[:half] + marker + data[-half:]
    return retained[:maximum], True


def _run_plugins(
    request: dict[str, Any], runtime: dict[str, Any], evidence: Path
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    maximum = request["max_plugin_output_bytes"]
    plugin_root = evidence / "plugins"
    plugin_root.mkdir(parents=True, exist_ok=True)
    for plugin in request["plugins"]:
        plugin_id = plugin["plugin_id"]
        argv = _expand_argv(plugin["argv"], runtime)
        cwd = runtime[f"{plugin['cwd_root']}_root"]
        started = time.monotonic()
        timed_out = False
        launch_error: str | None = None
        exit_code: int | None = None
        stdout = b""
        stderr = b""
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                check=False,
                timeout=plugin["timeout_seconds"],
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout or b""
            stderr = error.stderr or b""
        except OSError as error:
            launch_error = f"{type(error).__name__}: {error}"
        stdout, stdout_truncated = _bounded(stdout, maximum)
        stderr, stderr_truncated = _bounded(stderr, maximum)
        (plugin_root / f"{plugin_id}.stdout.log").write_bytes(stdout)
        (plugin_root / f"{plugin_id}.stderr.log").write_bytes(stderr)
        passed = exit_code == 0 and not timed_out and launch_error is None
        result = {
            "plugin_id": plugin_id,
            "argv": argv,
            "cwd": str(cwd),
            "duration_seconds": round(time.monotonic() - started, 6),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "launch_error": launch_error,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "required_for_adjudication": plugin["required_for_adjudication"],
            "pass": passed,
        }
        _write_json(plugin_root / f"{plugin_id}.status.json", result)
        results.append(result)
    return results


def _copy_entry(source: Path, destination: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise ReturnCoreError(f"entry source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_stream, destination.open("wb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
    size, digest = _hash_file(destination)
    return {"path": destination.as_posix(), "bytes": size, "sha256": digest}


def _matches_waveform_name(name: str, profile: Mapping[str, str]) -> bool:
    primary = profile["primary"]
    return name == primary or name.startswith(f"{primary}.")


def _discover_waveforms(plan: dict[str, Any], attempt_root: Path) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    found: list[Path] = []
    roots = plan.get("dump", {}).get("runtime_search_roots")
    try:
        profile = _waveform_profile(plan)
    except ReturnCoreError as error:
        return [], [str(error)]
    if not isinstance(roots, list) or not roots:
        return [], ["waveform plan has no runtime_search_roots"]
    for index, value in enumerate(roots):
        try:
            relative = _safe_relative(f"runtime_search_roots[{index}]", value)
            search = _inside(attempt_root, relative)
        except (OSError, ReturnCoreError) as error:
            errors.append(str(error))
            continue
        if not search.exists():
            continue
        if search.is_symlink() or not search.is_dir():
            errors.append(f"waveform search root is not a real directory: {value}")
            continue
        for path in search.rglob("*"):
            if not path.is_file() or not _matches_waveform_name(path.name, profile):
                continue
            if path.is_symlink():
                errors.append(f"waveform source is a symlink: {path}")
                continue
            resolved = path.resolve()
            try:
                resolved.relative_to(attempt_root)
            except ValueError:
                errors.append(f"waveform source escapes attempt root: {path}")
                continue
            found.append(resolved)
    unique = sorted(set(found), key=lambda path: path.relative_to(attempt_root).as_posix())
    return unique, errors


def _stage_waveforms(
    request: dict[str, Any],
    runtime: dict[str, Any],
    staging: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    discovery = request.get("waveform_discovery")
    if discovery is None:
        return [], []
    errors: list[str] = []
    receipts: list[dict[str, Any]] = []
    package_root = runtime["package_root"]
    attempt_root = runtime["attempt_root"]
    try:
        plan_relative = _safe_relative("waveform plan member", discovery["plan_member"])
        plan_path = _inside(package_root, plan_relative)
        if not plan_path.is_file() or plan_path.is_symlink():
            raise ReturnCoreError("mandatory waveform plan is absent or not a real file")
        plan_data = plan_path.read_bytes()
        plan = json.loads(plan_data)
        profile = _waveform_profile(plan)
        if plan.get("package_id") != request["package_id"]:
            errors.append("mandatory waveform plan package identity mismatch")
        if plan.get("return_policy", {}).get("manifest_archive_path") != discovery.get(
            "manifest_archive_path"
        ):
            errors.append("waveform plan and return request manifest path differ")
        if plan.get("integration", {}).get("collector_member") is not None:
            errors.append("waveform plan uses an unknown collector_member field")
        if plan.get("integration", {}).get("tool_member") != discovery.get(
            "collector_member"
        ):
            errors.append("waveform plan and return request collector member differ")
        policy = plan.get("return_policy", {})
        if policy.get("hard_limit_bytes") is not None or any(
            policy.get(field) is not False
            for field in (
                "truncation_allowed",
                "sampling_allowed",
                "size_based_deletion_allowed",
            )
        ):
            errors.append("waveform plan introduces a forbidden size or deletion policy")

        receipt_relative = _safe_relative(
            "waveform runtime receipt source", discovery["runtime_receipt_source"]
        )
        receipt_path = _inside(attempt_root, receipt_relative)
        if not receipt_path.exists():
            if runtime["sim_started"]:
                errors.append("simulation started but waveform runtime receipt is absent")
            return receipts, errors
        if receipt_path.is_symlink() or not receipt_path.is_file():
            errors.append("waveform runtime receipt is not a real file")
            return receipts, errors
        receipt_data = receipt_path.read_bytes()
        receipt = json.loads(receipt_data)
        manifest_relative = _safe_relative(
            "waveform manifest archive", discovery["manifest_archive_path"]
        )
        manifest_destination = staging.joinpath(*manifest_relative.parts)
        if manifest_destination.exists():
            errors.append("waveform runtime receipt collides with an existing return member")
        else:
            manifest_copy = _copy_entry(receipt_path, manifest_destination)
            manifest_copy.update(
                {
                    "path": manifest_relative.as_posix(),
                    "required": runtime["sim_started"],
                    "kind": "waveform_runtime_receipt",
                }
            )
            receipts.append(manifest_copy)

        if receipt.get("schema") != profile["receipt_schema"]:
            errors.append("waveform runtime receipt schema mismatch")
        if receipt.get("package_id") != request["package_id"]:
            errors.append("waveform runtime receipt package identity mismatch")
        if receipt.get("execution_id") != runtime["execution_id"]:
            errors.append("waveform runtime receipt execution identity mismatch")
        if receipt.get("plan_sha256") != _sha256(plan_data):
            errors.append("waveform runtime receipt plan SHA mismatch")
        if receipt.get("simulation_started") is not runtime["sim_started"]:
            errors.append("waveform runtime receipt simulation-started mismatch")
        if receipt.get("no_size_limit") is not True:
            errors.append("waveform runtime receipt introduced a size limit")
        if receipt.get("all_matching_collected") is not True:
            errors.append("waveform runtime receipt did not claim exact discovery")
        if receipt.get("pass") is not True or receipt.get("errors") != []:
            errors.append("waveform runtime collector did not pass")
        waveforms = receipt.get("waveforms")
        if not isinstance(waveforms, list):
            errors.append("waveform runtime receipt waveforms must be an array")
            waveforms = []
        actual_paths, discovery_errors = _discover_waveforms(plan, attempt_root)
        errors.extend(discovery_errors)
        actual_sources = {
            path.relative_to(attempt_root).as_posix() for path in actual_paths
        }
        declared_sources: set[str] = set()
        declared_archives: set[str] = set()
        for index, item in enumerate(waveforms):
            if not isinstance(item, dict):
                errors.append(f"waveforms[{index}] must be an object")
                continue
            try:
                source_relative = _safe_relative(
                    f"waveforms[{index}].source_path", item.get("source_path")
                )
                archive_relative = _safe_relative(
                    f"waveforms[{index}].archive_path", item.get("archive_path")
                )
            except ReturnCoreError as error:
                errors.append(str(error))
                continue
            source_key = source_relative.as_posix()
            archive_key = archive_relative.as_posix()
            if source_key in declared_sources:
                errors.append(f"duplicate waveform source: {source_key}")
                continue
            if archive_key in declared_archives:
                errors.append(f"duplicate waveform archive path: {archive_key}")
                continue
            declared_sources.add(source_key)
            declared_archives.add(archive_key)
            if not _matches_waveform_name(source_relative.name, profile):
                errors.append(
                    f"waveforms[{index}] source is not {profile['primary']} or a shard"
                )
                continue
            source = _inside(attempt_root, source_relative)
            destination = staging.joinpath(*archive_relative.parts)
            if destination.exists():
                errors.append(f"waveform archive collides with existing member: {archive_key}")
                continue
            try:
                copied = _copy_entry(source, destination)
            except ReturnCoreError as error:
                errors.append(str(error))
                continue
            copied.update({"path": archive_key, "required": True, "kind": profile["kind"]})
            receipts.append(copied)
            if copied["bytes"] != item.get("bytes"):
                errors.append(f"waveform byte count mismatch: {source_key}")
            if copied["sha256"] != item.get("sha256"):
                errors.append(f"waveform SHA mismatch: {source_key}")
            if item.get("format") != profile["format"]:
                errors.append(f"waveform format mismatch: {source_key}")
            expected_completeness = (
                "COMPLETE" if receipt.get("exit_kind") == "NATURAL" else "PARTIAL"
            )
            if item.get("completeness") != expected_completeness:
                errors.append(f"waveform completeness mismatch: {source_key}")
        if actual_sources != declared_sources:
            errors.append(
                "waveform source exact-set mismatch: "
                f"declared={sorted(declared_sources)} actual={sorted(actual_sources)}"
            )
        if runtime["sim_started"] and not declared_sources:
            errors.append("simulation started but no waveform was declared")
        if not runtime["sim_started"] and declared_sources:
            errors.append("simulation did not start but stale waveform was declared")
    except (OSError, json.JSONDecodeError, ReturnCoreError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return receipts, errors


def _zip_tree(root: Path, target: Path) -> list[str]:
    members: list[str] = []
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ReturnCoreError(f"staging tree contains symlink: {path}")
            if path.is_file():
                member = path.relative_to(root.parent).as_posix()
                compression = (
                    zipfile.ZIP_STORED
                    if "/waveforms/" in f"/{member}/"
                    or path.name == "wave.vpd"
                    or path.name.startswith("wave.vpd.")
                    or path.name == "wave.fsdb"
                    or path.name.startswith("wave.fsdb.")
                    else zipfile.ZIP_DEFLATED
                )
                archive.write(path, member, compress_type=compression)
                members.append(member)
    with zipfile.ZipFile(target, "r") as archive:
        if archive.testzip() is not None:
            raise ReturnCoreError("return ZIP CRC failed")
        if sorted(archive.namelist()) != sorted(members):
            raise ReturnCoreError("return ZIP exact-set mismatch")
    return members


def _publish_no_overwrite(temporary: Path, target: Path) -> None:
    try:
        os.link(temporary, target)
    except FileExistsError as error:
        raise ReturnCoreError(f"return target already exists: {target}") from error
    except OSError as error:
        raise ReturnCoreError(f"atomic no-overwrite publish failed: {error}") from error
    temporary.unlink()


def _read_existing_identity(target: Path) -> tuple[str, str] | None:
    try:
        with zipfile.ZipFile(target, "r") as archive:
            names = [name for name in archive.namelist() if name.endswith("/RETURN_CORE_MANIFEST.json")]
            if len(names) != 1 or archive.testzip() is not None:
                return None
            manifest = json.loads(archive.read(names[0]))
            return manifest.get("package_id"), manifest.get("execution_id")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError):
        return None


def finalize(
    request: dict[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    result_root_override: Path | None = None,
) -> dict[str, Any]:
    errors = validate_request(request)
    if errors:
        raise ReturnCoreError("; ".join(errors))
    runtime = _runtime_from_env(environment or os.environ)
    package_id = request["package_id"]
    execution_id = runtime["execution_id"]
    attempt_root = runtime["attempt_root"]
    evidence = attempt_root / "evidence" / "return_core"
    if evidence.is_symlink():
        raise ReturnCoreError("return-core evidence root is a symlink")
    evidence.mkdir(parents=True, exist_ok=True)
    if evidence.is_symlink() or not evidence.is_dir():
        raise ReturnCoreError("return-core evidence root is not a real directory")
    state_path = evidence / "RETURN_FINALIZER_STATE.json"
    state: dict[str, Any] = {
        "schema": "server-post-sim-finalizer-state-v1",
        "package_id": package_id,
        "execution_id": execution_id,
        "phase": "SIM_EXIT_PERSISTED",
        "published": False,
        "error": None,
    }
    sim_receipt = {
        "schema": "server-sim-exit-receipt-v1",
        "package_id": package_id,
        "execution_id": execution_id,
        "sim_started": runtime["sim_started"],
        "sim_exit_code": runtime["sim_exit_code"],
        "signal": runtime["sim_signal"],
        "natural_terminal_observed": runtime["natural_terminal"],
    }
    _write_json(evidence / "SIM_EXIT_RECEIPT.json", sim_receipt)
    _write_json(state_path, state)
    try:
        state["phase"] = "PLUGINS_RUNNING"
        _write_json(state_path, state)
        plugin_results = _run_plugins(request, runtime, evidence)
        _write_json(evidence / "RETURN_PLUGIN_STATUS.json", plugin_results)
        state["phase"] = "CORE_STAGING"
        _write_json(state_path, state)
        missing_required: list[str] = []
        entry_errors: list[str] = []
        required_plugin_failures = [
            item["plugin_id"]
            for item in plugin_results
            if item["required_for_adjudication"] and not item["pass"]
        ]
        result_root = (
            result_root_override.resolve()
            if result_root_override is not None
            else Path(request["result_root"])
        )
        if result_root.is_symlink() or not result_root.is_dir():
            raise ReturnCoreError("result_root must be a real pre-existing directory")
        basename = request["return_basename_template"].format(
            package_id=package_id, execution_id=execution_id
        )
        _safe_name("return basename stem", basename.removesuffix(".zip"))
        target = result_root / basename
        sidecar = target.with_name(target.name + ".sha256")
        if target.exists():
            identity = _read_existing_identity(target)
            if identity == (package_id, execution_id):
                _, existing_sha = _hash_file(target)
                expected_sidecar = f"{existing_sha}  {basename}\n"
                if sidecar.exists():
                    if not sidecar.is_file() or sidecar.read_text(
                        encoding="utf-8"
                    ) != expected_sidecar:
                        raise ReturnCoreError(
                            f"existing return sidecar differs: {sidecar}"
                        )
                else:
                    sidecar_temporary = result_root / (
                        f".{sidecar.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
                    )
                    sidecar_temporary.write_text(
                        expected_sidecar, encoding="utf-8", newline="\n"
                    )
                    _publish_no_overwrite(sidecar_temporary, sidecar)
                state.update(
                    {
                        "phase": "PUBLISHED_IDEMPOTENT",
                        "published": True,
                        "return_zip": str(target),
                        "return_sha256": existing_sha,
                    }
                )
                _write_json(state_path, state)
                return state
            raise ReturnCoreError(f"conflicting return target exists: {target}")
        top_name = f"{package_id}_return"
        with tempfile.TemporaryDirectory(prefix=".return_core_", dir=attempt_root) as temporary_dir:
            staging_base = Path(temporary_dir)
            staging = staging_base / top_name
            staging.mkdir()
            copied: list[dict[str, Any]] = []
            for entry in request["core_entries"]:
                source_root = runtime[f"{entry['source_root']}_root"]
                source_relative = _safe_relative("entry source", entry["source"])
                archive_relative = _safe_relative("entry archive", entry["archive"])
                source = _inside(source_root, source_relative)
                destination = staging.joinpath(*archive_relative.parts)
                if not source.exists():
                    message = f"missing entry: {entry['source_root']}:{entry['source']}"
                    if entry["required"]:
                        missing_required.append(message)
                    else:
                        entry_errors.append(message)
                    continue
                try:
                    receipt = _copy_entry(source, destination)
                    receipt["path"] = archive_relative.as_posix()
                    receipt["required"] = entry["required"]
                    copied.append(receipt)
                except ReturnCoreError as error:
                    if entry["required"]:
                        missing_required.append(str(error))
                    else:
                        entry_errors.append(str(error))
            waveform_receipts, waveform_errors = _stage_waveforms(
                request, runtime, staging
            )
            copied.extend(waveform_receipts)
            missing_required.extend(
                f"waveform: {message}" for message in waveform_errors
            )
            generated = staging / "return_core"
            generated.mkdir()
            shutil.copyfile(evidence / "SIM_EXIT_RECEIPT.json", generated / "SIM_EXIT_RECEIPT.json")
            shutil.copyfile(evidence / "RETURN_PLUGIN_STATUS.json", generated / "RETURN_PLUGIN_STATUS.json")
            plugin_logs = evidence / "plugins"
            if plugin_logs.exists():
                shutil.copytree(plugin_logs, generated / "plugins")
            if not runtime["sim_started"]:
                disposition = "SIM_NOT_STARTED_RETURN"
            elif runtime["sim_exit_code"] != 0 or runtime["sim_signal"] != "NONE":
                disposition = "PARTIAL_EXECUTION_RETURN"
            elif missing_required or required_plugin_failures:
                disposition = "EVIDENCE_INCOMPLETE"
            elif not runtime["natural_terminal"]:
                disposition = "NON_NATURAL_RETURN"
            else:
                disposition = "COMPLETE_RETURN"
            core_status = {
                "schema": "server-post-sim-return-core-status-v1",
                "package_id": package_id,
                "execution_id": execution_id,
                "disposition": disposition,
                "sim_exit": sim_receipt,
                "missing_required_entries": missing_required,
                "optional_entry_errors": entry_errors,
                "required_plugin_failures": required_plugin_failures,
                "waveform_errors": waveform_errors,
                "waveform_receipts": waveform_receipts,
                "return_publication_independent_of_plugin_success": True,
                "claim_boundary": request["claim_boundary"],
            }
            _write_json(generated / "RETURN_CORE_STATUS.json", core_status)
            manifest = {
                "schema": "server-post-sim-return-core-manifest-v1",
                "package_id": package_id,
                "execution_id": execution_id,
                "disposition": disposition,
                "core_entry_receipts": copied,
                "missing_required_entries": missing_required,
                "required_plugin_failures": required_plugin_failures,
                "waveform_entry_receipts": waveform_receipts,
                "waveform_errors": waveform_errors,
                "waveform_no_size_limit": request.get("waveform_discovery") is not None,
                "return_basename": basename,
                "claim_boundary": request["claim_boundary"],
            }
            _write_json(staging / "RETURN_CORE_MANIFEST.json", manifest)
            temporary_zip = result_root / f".{basename}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
            try:
                members = _zip_tree(staging, temporary_zip)
                zip_size, zip_sha = _hash_file(temporary_zip)
                _publish_no_overwrite(temporary_zip, target)
                sidecar_temporary = result_root / f".{sidecar.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
                sidecar_temporary.write_text(f"{zip_sha}  {basename}\n", encoding="utf-8", newline="\n")
                _publish_no_overwrite(sidecar_temporary, sidecar)
            finally:
                if temporary_zip.exists():
                    temporary_zip.unlink()
        state.update(
            {
                "phase": "PUBLISHED",
                "published": True,
                "disposition": disposition,
                "return_zip": str(target),
                "return_bytes": zip_size,
                "return_sha256": zip_sha,
                "sidecar": str(sidecar),
                "member_count": len(members),
            }
        )
        _write_json(state_path, state)
        return state
    except Exception as error:
        state.update(
            {
                "phase": "FAILED_RECOVERABLE_FROM_ATTEMPT_ROOT",
                "published": False,
                "error": f"{type(error).__name__}: {error}",
                "recovery": "rerun the same JSON-only finalizer request; do not rerun simulation",
            }
        )
        _write_json(state_path, state)
        raise


def _safe_zip_members(archive: zipfile.ZipFile) -> tuple[str, list[str]]:
    names = archive.namelist()
    if not names or archive.testzip() is not None:
        raise ReturnCoreError("ZIP is empty or fails CRC")
    roots: set[str] = set()
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ReturnCoreError(f"unsafe ZIP member: {name}")
        if path.parts:
            roots.add(path.parts[0])
    if len(roots) != 1:
        raise ReturnCoreError("ZIP must have one top-level root")
    return next(iter(roots)), names


def _validate_partial_exit_profile(
    profile: Any,
    request: dict[str, Any],
    root: str,
    names: list[str],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    required_fields = {
        "rule_id",
        "enforcement",
        "required_signals",
        "final_block_ring_sole_input_forbidden",
        "plugin_dispositions",
    }
    if not isinstance(profile, dict):
        return ["partial-exit live-causal-record contract is absent"], by_id
    if set(profile) != required_fields:
        errors.append("partial-exit live-causal-record contract fields mismatch")
    if profile.get("rule_id") != PARTIAL_EXIT_RULE_ID:
        errors.append("partial-exit live-causal-record rule identity mismatch")
    if profile.get("enforcement") != "required_next_fresh":
        errors.append("partial-exit live-causal-record enforcement mismatch")
    if profile.get("required_signals") != ["INT", "TERM"]:
        errors.append("partial-exit live-causal-record signals must be exact INT/TERM")
    if profile.get("final_block_ring_sole_input_forbidden") is not True:
        errors.append("final-block ring must be forbidden as the sole causal input")

    rows = profile.get("plugin_dispositions")
    if not isinstance(rows, list):
        errors.append("partial-exit plugin_dispositions must be an array")
        rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"partial-exit plugin_dispositions[{index}] must be an object")
            continue
        plugin_id = row.get("plugin_id")
        try:
            plugin_id = _safe_name(f"partial-exit plugin_dispositions[{index}].plugin_id", plugin_id)
        except ReturnCoreError as error:
            errors.append(str(error))
            continue
        if plugin_id in by_id:
            errors.append(f"duplicate partial-exit plugin disposition: {plugin_id}")
            continue
        by_id[plugin_id] = row
        disposition = row.get("disposition")
        if disposition == "NOT_APPLICABLE_NON_CAUSAL_PLUGIN":
            if set(row) != {"plugin_id", "disposition", "reason"}:
                errors.append(f"partial-exit not-applicable fields mismatch: {plugin_id}")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                errors.append(f"partial-exit not-applicable reason is absent: {plugin_id}")
            continue
        expected = {
            "plugin_id",
            "disposition",
            "input_root",
            "input_path",
            "fixture_member",
            "input_kind",
            "output_root",
            "output_path",
            "expected_exit_code",
            "timeout_seconds",
        }
        if disposition != "LIVE_CAUSAL_FIXTURE":
            errors.append(f"partial-exit disposition is invalid: {plugin_id}")
            continue
        if set(row) != expected:
            errors.append(f"partial-exit live fixture fields mismatch: {plugin_id}")
        if row.get("input_root") != "attempt" or row.get("output_root") != "attempt":
            errors.append(f"partial-exit fixture input/output roots must be attempt: {plugin_id}")
        for key in ("input_path", "output_path", "fixture_member"):
            try:
                _safe_relative(f"partial-exit {plugin_id}.{key}", row.get(key))
            except ReturnCoreError as error:
                errors.append(str(error))
        fixture_member = row.get("fixture_member")
        if isinstance(fixture_member, str) and f"{root}/{fixture_member}" not in names:
            errors.append(f"partial-exit fixture member is absent: {plugin_id}")
        if row.get("input_kind") not in {
            "QUALIFIED_LIVE_RECORD",
            "SIGNAL_SAFE_PERSISTED_EQUIVALENT",
        }:
            errors.append(f"partial-exit input kind is invalid: {plugin_id}")
        if row.get("expected_exit_code") != 0:
            errors.append(f"partial-exit expected exit must be zero: {plugin_id}")
        timeout = row.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout < 1 or timeout > 30:
            errors.append(f"partial-exit fixture timeout must be in [1,30]: {plugin_id}")

    required_plugins = {
        item.get("plugin_id"): item
        for item in request.get("plugins", [])
        if isinstance(item, dict) and item.get("required_for_adjudication") is True
    }
    if set(by_id) != set(required_plugins):
        errors.append(
            "partial-exit dispositions must exactly cover required plugins: "
            f"expected={sorted(required_plugins)} actual={sorted(by_id)}"
        )
    for plugin_id, row in by_id.items():
        if row.get("disposition") != "LIVE_CAUSAL_FIXTURE":
            continue
        plugin = required_plugins.get(plugin_id)
        if not isinstance(plugin, dict):
            continue
        argv = plugin.get("argv", [])
        input_token = f"{{attempt_root}}/{row.get('input_path')}"
        output_token = f"{{attempt_root}}/{row.get('output_path')}"
        if input_token not in argv:
            errors.append(f"partial-exit exact plugin argv lacks live input: {plugin_id}")
        if output_token not in argv:
            errors.append(f"partial-exit exact plugin argv lacks decision output: {plugin_id}")
    return errors, by_id


def _exercise_partial_exit_plugins(
    archive: zipfile.ZipFile,
    root: str,
    request: dict[str, Any],
    rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    plugins = {
        item["plugin_id"]: item
        for item in request["plugins"]
        if item.get("required_for_adjudication") is True
    }
    with tempfile.TemporaryDirectory(prefix="partial_exit_live_causal_") as directory:
        harness_root = Path(directory)
        package_root = harness_root / root
        attempt_root = harness_root / "attempt"
        package_root.mkdir()
        attempt_root.mkdir()
        for info in archive.infolist():
            if info.is_dir():
                continue
            relative = PurePosixPath(info.filename).relative_to(root)
            target = package_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info.filename))
        for plugin_id, row in rows.items():
            if row.get("disposition") != "LIVE_CAUSAL_FIXTURE":
                results[plugin_id] = {
                    "disposition": row.get("disposition"),
                    "executed": False,
                    "pass": True,
                }
                continue
            fixture_path = package_root.joinpath(
                *_safe_relative("partial-exit fixture_member", row["fixture_member"]).parts
            )
            fixture = fixture_path.read_bytes()
            text = fixture.decode("utf-8", errors="replace")
            fixture_errors: list[str] = []
            if "kind=RING_POST" in text:
                fixture_errors.append("fixture contains final-only RING_POST")
            if row["input_kind"] == "QUALIFIED_LIVE_RECORD":
                if re.search(r"CODEX_PROBE_V1\s+kind=EVENT\b", text) is None:
                    fixture_errors.append("fixture lacks qualified live EVENT")
            elif "CODEX_PARTIAL_EXIT_PERSISTED_V1 qualified=true signal_safe=true" not in text:
                fixture_errors.append("fixture lacks signal-safe persisted marker")
            input_path = _inside(
                attempt_root,
                _safe_relative("partial-exit input_path", row["input_path"]),
            )
            output_path = _inside(
                attempt_root,
                _safe_relative("partial-exit output_path", row["output_path"]),
            )
            input_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            input_path.write_bytes(fixture)
            runtime = {
                "package_root": package_root,
                "attempt_root": attempt_root,
                "execution_id": "partial_exit_fixture",
            }
            argv = _expand_argv(plugins[plugin_id]["argv"], runtime)
            if argv and Path(argv[0]).name.lower() in {"python", "python3", "python.exe", "python3.exe"}:
                argv[0] = sys.executable
            completed: subprocess.CompletedProcess[str] | None = None
            if not fixture_errors:
                try:
                    completed = subprocess.run(
                        argv,
                        cwd=attempt_root if plugins[plugin_id]["cwd_root"] == "attempt" else package_root,
                        capture_output=True,
                        text=True,
                        timeout=row["timeout_seconds"],
                        check=False,
                    )
                except (OSError, subprocess.SubprocessError) as error:
                    fixture_errors.append(f"fixture execution failed: {type(error).__name__}: {error}")
            if completed is not None and completed.returncode != row["expected_exit_code"]:
                fixture_errors.append(
                    f"fixture exit {completed.returncode} != {row['expected_exit_code']}"
                )
            output_json_valid = False
            if not fixture_errors and output_path.is_file():
                try:
                    json.loads(output_path.read_text(encoding="utf-8"))
                    output_json_valid = True
                except (UnicodeDecodeError, json.JSONDecodeError):
                    fixture_errors.append("fixture decision output is not JSON")
            elif not fixture_errors:
                fixture_errors.append("fixture decision output is absent")
            results[plugin_id] = {
                "disposition": row["disposition"],
                "executed": completed is not None,
                "exit_code": completed.returncode if completed is not None else None,
                "output_json_valid": output_json_valid,
                "pass": not fixture_errors,
                "errors": fixture_errors,
                "stdout": completed.stdout[-2048:] if completed is not None else "",
                "stderr": completed.stderr[-2048:] if completed is not None else "",
            }
    return results


def _exercise_scenarios(
    request: dict[str, Any], waveform_plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="post_sim_return_exact_") as directory:
        root = Path(directory)
        package_root = root / "package"
        attempt_root = root / "attempt"
        result_root = root / "simresult"
        for path in (package_root, attempt_root, result_root):
            path.mkdir()
        for entry in request["core_entries"]:
            source_root = (
                attempt_root if entry["source_root"] == "attempt" else package_root
            )
            relative = _safe_relative("scenario entry", entry["source"])
            target = source_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("synthetic exact-final-ZIP evidence\n", encoding="utf-8")

        def prepare_waveform(execution_id: str, exit_kind: str) -> None:
            discovery = request.get("waveform_discovery")
            if discovery is None:
                return
            if waveform_plan is None:
                raise ReturnCoreError("waveform scenario is missing the exact package plan")
            plan_relative = _safe_relative("scenario waveform plan", discovery["plan_member"])
            plan_path = package_root.joinpath(*plan_relative.parts)
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_data = _json_bytes(waveform_plan)
            plan_path.write_bytes(plan_data)
            profile = _waveform_profile(waveform_plan)
            roots = waveform_plan["dump"]["runtime_search_roots"]
            wave_root = attempt_root.joinpath(*_safe_relative("scenario wave root", roots[0]).parts)
            wave_root.mkdir(parents=True, exist_ok=True)
            for stale in attempt_root.rglob(f"{profile['primary']}*"):
                if stale.is_file() and not stale.is_symlink():
                    stale.unlink()
            wave = wave_root / profile["primary"]
            wave.write_bytes(
                (f"synthetic-{execution_id}-{profile['format'].lower()}\n" * 16).encode("utf-8")
            )
            wave_size, wave_sha = _hash_file(wave)
            source = wave.relative_to(attempt_root).as_posix()
            receipt = {
                "schema": profile["receipt_schema"],
                "package_id": request["package_id"],
                "execution_id": execution_id,
                "plan_sha256": _sha256(plan_data),
                "simulation_started": True,
                "exit_kind": exit_kind,
                "waveforms": [
                    {
                        "source_path": source,
                        "archive_path": (
                            f"{waveform_plan['return_policy']['archive_prefix']}/{source}"
                        ),
                        "bytes": wave_size,
                        "sha256": wave_sha,
                        "format": profile["format"],
                        "completeness": (
                            "COMPLETE" if exit_kind == "NATURAL" else "PARTIAL"
                        ),
                    }
                ],
                "no_size_limit": True,
                "all_matching_collected": True,
                "pass": True,
                "errors": [],
                "claim_boundary": "synthetic exact-final-ZIP scenario only",
            }
            receipt_relative = _safe_relative(
                "scenario waveform receipt", discovery["runtime_receipt_source"]
            )
            receipt_path = attempt_root.joinpath(*receipt_relative.parts)
            _write_json(receipt_path, receipt)


        def scenario_request(exit_code: int) -> dict[str, Any]:
            value = copy.deepcopy(request)
            plugins = value["plugins"]
            if not plugins:
                plugins.append(
                    {
                        "plugin_id": "synthetic_decision",
                        "argv": [sys.executable, "-c", f"raise SystemExit({exit_code})"],
                        "cwd_root": "attempt",
                        "timeout_seconds": 5,
                        "required_for_adjudication": True,
                    }
                )
            for index, plugin in enumerate(plugins):
                plugin["argv"] = [
                    sys.executable,
                    "-c",
                    f"raise SystemExit({exit_code if index == 0 else 0})",
                ]
                plugin["required_for_adjudication"] = index == 0
                plugin["timeout_seconds"] = min(plugin["timeout_seconds"], 5)
            return value

        def environment(execution_id: str, sim_exit: int, natural: bool) -> dict[str, str]:
            return {
                "CODEX_PACKAGE_ROOT": str(package_root),
                "CODEX_ATTEMPT_ROOT": str(attempt_root),
                "CODEX_EXECUTION_ID": execution_id,
                "CODEX_SIM_EXIT_CODE": str(sim_exit),
                "CODEX_SIM_SIGNAL": "NONE",
                "CODEX_SIM_STARTED": "true",
                "CODEX_NATURAL_TERMINAL": "true" if natural else "false",
            }

        prepare_waveform("natural", "NATURAL")
        natural = finalize(
            scenario_request(0),
            environment=environment("natural", 0, True),
            result_root_override=result_root,
        )
        results["natural_success"] = {
            "published": natural["published"],
            "disposition": natural["disposition"],
        }
        prepare_waveform("plugin_fail", "NATURAL")
        plugin_failure = finalize(
            scenario_request(9),
            environment=environment("plugin_fail", 0, True),
            result_root_override=result_root,
        )
        results["natural_success_plugin_failure"] = {
            "published": plugin_failure["published"],
            "disposition": plugin_failure["disposition"],
        }
        prepare_waveform("sim_nonzero", "SIMULATION_NONZERO")
        simulation_failure = finalize(
            scenario_request(0),
            environment=environment("sim_nonzero", 124, False),
            result_root_override=result_root,
        )
        results["simulation_nonzero"] = {
            "published": simulation_failure["published"],
            "disposition": simulation_failure["disposition"],
        }
        prepare_waveform("idempotent", "NATURAL")
        idempotent_first = finalize(
            scenario_request(0),
            environment=environment("idempotent", 0, True),
            result_root_override=result_root,
        )
        idempotent_second = finalize(
            scenario_request(0),
            environment=environment("idempotent", 0, True),
            result_root_override=result_root,
        )
        results["idempotent_reentry"] = {
            "first_sha256": idempotent_first["return_sha256"],
            "second_sha256": idempotent_second["return_sha256"],
            "second_phase": idempotent_second["phase"],
        }
    return results


def validate_final_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            root, names = _safe_zip_members(archive)
            contract_names = [name for name in names if name == f"{root}/contracts/server_post_sim_return_contract.json"]
            if len(contract_names) != 1:
                raise ReturnCoreError("exact post-sim return contract is absent")
            contract = json.loads(archive.read(contract_names[0]))
            if contract.get("schema") != CONTRACT_SCHEMA:
                errors.append("contract schema mismatch")
            package_id = contract.get("package_id")
            try:
                _safe_name("contract package_id", package_id)
            except ReturnCoreError as error:
                errors.append(str(error))
            helper_member = contract.get("helper_member")
            request_member = contract.get("request_member")
            runner_member = contract.get("runner_member")
            for label, member in (
                ("helper", helper_member),
                ("request", request_member),
                ("runner", runner_member),
            ):
                if not isinstance(member, str) or f"{root}/{member}" not in names:
                    errors.append(f"{label} member is absent")
            helper_data = archive.read(f"{root}/{helper_member}") if isinstance(helper_member, str) and f"{root}/{helper_member}" in names else b""
            request_data = archive.read(f"{root}/{request_member}") if isinstance(request_member, str) and f"{root}/{request_member}" in names else b""
            runner_data = archive.read(f"{root}/{runner_member}") if isinstance(runner_member, str) and f"{root}/{runner_member}" in names else b""
            if _sha256(helper_data) != contract.get("helper_sha256"):
                errors.append("helper SHA mismatch")
            if helper_data != Path(__file__).read_bytes():
                errors.append("helper bytes differ from the shared validator runtime")
            if _sha256(request_data) != contract.get("request_sha256"):
                errors.append("request SHA mismatch")
            request: dict[str, Any] = {}
            waveform_plan: dict[str, Any] | None = None
            try:
                request = json.loads(request_data)
                errors.extend(f"request: {item}" for item in validate_request(request))
                if request.get("package_id") != package_id:
                    errors.append("request package_id differs")
                discovery = request.get("waveform_discovery")
                if isinstance(discovery, dict):
                    plan_name = f"{root}/{discovery.get('plan_member')}"
                    collector_name = f"{root}/{discovery.get('collector_member')}"
                    if plan_name not in names:
                        errors.append("mandatory waveform plan member is absent")
                    else:
                        waveform_plan = json.loads(archive.read(plan_name))
                        try:
                            _waveform_profile(waveform_plan)
                        except ReturnCoreError as error:
                            errors.append(str(error))
                    if collector_name not in names:
                        errors.append("mandatory waveform collector member is absent")
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append("request JSON is invalid")
            partial_exit_rows: dict[str, dict[str, Any]] = {}
            partial_exit_errors: list[str] = []
            if request:
                partial_exit_errors, partial_exit_rows = _validate_partial_exit_profile(
                    contract.get("partial_exit_live_causal_record"),
                    request,
                    root,
                    names,
                )
                errors.extend(partial_exit_errors)
            runner_text = runner_data.decode("utf-8", errors="replace")
            missing_tokens = [token for token in REQUIRED_RUNNER_TOKENS if token not in runner_text]
            if missing_tokens:
                errors.append(f"runner tokens missing: {missing_tokens}")
            forbidden = [token for token in FORBIDDEN_WRAPPER_TOKENS if token in runner_text]
            python_members = [name for name in names if name.endswith(".py")]
            for name in python_members:
                if name == f"{root}/{helper_member}":
                    continue
                text = archive.read(name).decode("utf-8", errors="replace")
                forbidden.extend(token for token in FORBIDDEN_WRAPPER_TOKENS if token in text)
            if forbidden:
                errors.append(f"family positional collector wrapper is forbidden: {sorted(set(forbidden))}")
            if contract.get("invocation_mode") != "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR":
                errors.append("invocation_mode mismatch")
            required_scenarios = contract.get("required_scenarios")
            expected = [
                "natural_success",
                "natural_success_plugin_failure",
                "simulation_nonzero",
                "idempotent_reentry",
            ]
            if required_scenarios != expected:
                errors.append("required scenario list mismatch")
            if contract.get("plugin_failure_blocks_core_return") is not False:
                errors.append("plugin failure must not block core return")
            if contract.get("sim_exit_persisted_before_plugins") is not True:
                errors.append("sim exit must be persisted before plugins")
            partial_exit_results: dict[str, Any] = {}
            if request and not partial_exit_errors:
                try:
                    partial_exit_results = _exercise_partial_exit_plugins(
                        archive,
                        root,
                        request,
                        partial_exit_rows,
                    )
                    for plugin_id, result in partial_exit_results.items():
                        if result.get("pass") is not True:
                            errors.append(
                                f"partial-exit live fixture failed: {plugin_id}: "
                                f"{result.get('errors', [])}"
                            )
                except Exception as error:
                    errors.append(
                        "partial-exit live fixture harness failed: "
                        f"{type(error).__name__}: {error}"
                    )
            scenarios: dict[str, Any] = {}
            if not errors:
                try:
                    scenarios = _exercise_scenarios(request, waveform_plan)
                    if scenarios["natural_success"] != {
                        "published": True,
                        "disposition": "COMPLETE_RETURN",
                    }:
                        errors.append("natural-success return-core scenario failed")
                    if scenarios["natural_success_plugin_failure"] != {
                        "published": True,
                        "disposition": "EVIDENCE_INCOMPLETE",
                    }:
                        errors.append("plugin-failure core publication scenario failed")
                    if scenarios["simulation_nonzero"] != {
                        "published": True,
                        "disposition": "PARTIAL_EXECUTION_RETURN",
                    }:
                        errors.append("simulation-nonzero core publication scenario failed")
                    idempotent = scenarios["idempotent_reentry"]
                    if (
                        idempotent["first_sha256"] != idempotent["second_sha256"]
                        or idempotent["second_phase"] != "PUBLISHED_IDEMPOTENT"
                    ):
                        errors.append("idempotent re-entry scenario failed")
                except Exception as error:
                    errors.append(
                        "exact request scenario harness failed: "
                        f"{type(error).__name__}: {error}"
                    )
            details = {
                "root": root,
                "member_count": len(names),
                "package_id": package_id,
                "missing_runner_tokens": missing_tokens,
                "partial_exit_live_causal_record": {
                    "rule_id": PARTIAL_EXIT_RULE_ID,
                    "contract_errors": partial_exit_errors,
                    "plugin_results": partial_exit_results,
                    "final_block_ring_sole_input_forbidden": True,
                },
                "scenario_results": scenarios,
            }
    except (OSError, zipfile.BadZipFile, ReturnCoreError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VALIDATION_SCHEMA,
        "zip_path": str(zip_path),
        "zip_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        "zip_sha256": _hash_file(zip_path)[1] if zip_path.exists() else None,
        "pass": not errors,
        "errors": errors,
        "details": details,
        "claim_boundary": "Exact post-simulation return-core and partial-exit parser-fixture integration only; no DUT, natural-terminal, formal-D, E4 or E5 claim.",
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--request", type=Path, required=True)
    validate_parser = subparsers.add_parser("validate-final-zip")
    validate_parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    validate_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "finalize":
        try:
            result = finalize(_load_json(args.request))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        except (OSError, json.JSONDecodeError, ReturnCoreError, subprocess.SubprocessError) as error:
            print(f"RETURN_CORE_ERROR {type(error).__name__}: {error}", file=sys.stderr)
            return 1
    report = validate_final_zip(args.zip_path)
    _write_json(args.output, report)
    print(json.dumps({"pass": report["pass"], "errors": len(report["errors"]), "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
