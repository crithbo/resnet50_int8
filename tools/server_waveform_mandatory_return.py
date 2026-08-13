#!/usr/bin/env python3
"""Validate and collect mandatory, unbounded waveform evidence.

This helper is deliberately independent from formal result adjudication.  It
binds the exact final package to an explicitly selected VCS-native dump format,
discovers every waveform shard in a fresh attempt, emits streaming byte/SHA receipts, and
verifies/extracts the same members from a formal return ZIP without imposing a
file, archive, or extracted-size ceiling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable


PLAN_SCHEMA = "server-waveform-mandatory-plan-v2"
RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v2"
FSDB_PLAN_SCHEMA = "server-waveform-mandatory-plan-v3"
FSDB_RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v3"
VALIDATION_SCHEMA = "server-waveform-mandatory-validation-v2"
PLAN_MEMBER = "contracts/server_waveform_mandatory_plan.json"
WAVE_NAMES = ["wave.vpd", "wave.vpd.*"]
FSDB_WAVE_NAMES = ["wave.fsdb", "wave.fsdb.*"]
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HIERARCHY = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*(?:[./][A-Za-z_$][A-Za-z0-9_$]*(?:\[[0-9]+\])?)*$"
)
EXIT_KINDS = {
    "COMPILE_FAILURE",
    "SIMULATION_NOT_STARTED",
    "NATURAL",
    "TIMEOUT",
    "HUP",
    "INT",
    "TERM",
    "SIMULATION_NONZERO",
}
PARTIAL_EXIT_KINDS = {"TIMEOUT", "HUP", "INT", "TERM", "SIMULATION_NONZERO"}


class WaveformGateError(ValueError):
    """A plan, package, runtime tree, or return violates the waveform gate."""


def waveform_profile(plan: dict[str, Any]) -> dict[str, Any]:
    schema = plan.get("schema")
    if schema == PLAN_SCHEMA:
        return {
            "format": "VPD",
            "receipt_schema": RECEIPT_SCHEMA,
            "make_arguments": {"DUMP_VCD": "1", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "patterns": WAVE_NAMES,
            "primary": "wave.vpd",
        }
    if schema == FSDB_PLAN_SCHEMA:
        return {
            "format": "FSDB",
            "receipt_schema": FSDB_RECEIPT_SCHEMA,
            "make_arguments": {"DUMP_VCD": "0", "DUMP_FSDB": "1", "TB_DUMP_FSDB": "0"},
            "patterns": FSDB_WAVE_NAMES,
            "primary": "wave.fsdb",
        }
    raise WaveformGateError(f"unsupported waveform plan schema: {schema!r}")


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_relative(label: str, value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WaveformGateError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise WaveformGateError(f"{label} is unsafe: {value}")
    return path


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


def _exact_fields(label: str, value: Any, expected: set[str], errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    if set(value) != expected:
        errors.append(
            f"{label} fields mismatch: expected={sorted(expected)} actual={sorted(value)}"
        )
    return value


def validate_plan(plan: Any) -> list[str]:
    errors: list[str] = []
    plan = _exact_fields(
        "plan",
        plan,
        {
            "schema",
            "package_id",
            "family",
            "dump",
            "return_policy",
            "integration",
            "claim_boundary",
        },
        errors,
    )
    try:
        profile = waveform_profile(plan)
    except WaveformGateError as error:
        errors.append(str(error))
        profile = {
            "format": None,
            "receipt_schema": None,
            "make_arguments": {},
            "patterns": [],
            "primary": "waveform",
        }
    for field in ("package_id", "family"):
        value = plan.get(field)
        if not isinstance(value, str) or SAFE_NAME.fullmatch(value) is None:
            errors.append(f"{field} is not a safe name")

    dump = _exact_fields(
        "dump",
        plan.get("dump"),
        {
            "format",
            "make_arguments",
            "tb_top",
            "hierarchy_depth",
            "scope_mode",
            "included_scopes",
            "excluded_scopes",
            "runtime_search_roots",
            "waveform_name_patterns",
        },
        errors,
    )
    if dump.get("format") != profile["format"]:
        errors.append(f"dump.format must be {profile['format']}")
    if dump.get("make_arguments") != profile["make_arguments"]:
        expected = ",".join(f"{key}={value}" for key, value in profile["make_arguments"].items())
        errors.append(f"make arguments must be {expected}")
    if dump.get("tb_top") != "tb_NDP_Top_new_phy" or dump.get("hierarchy_depth") != 0:
        errors.append("default dump must bind tb_NDP_Top_new_phy at hierarchy depth 0")
    if dump.get("waveform_name_patterns") != profile["patterns"]:
        errors.append(
            f"waveform_name_patterns must collect {profile['primary']} and every shard"
        )

    mode = dump.get("scope_mode")
    scopes = dump.get("included_scopes")
    exclusions = dump.get("excluded_scopes")
    if mode not in {"FULL_HIERARCHY", "PROVEN_IRRELEVANT_PRUNED"}:
        errors.append("dump.scope_mode is invalid")
    if not isinstance(scopes, list) or not scopes or len(scopes) != len(set(scopes)):
        errors.append("included_scopes must be a non-empty unique array")
        scopes = []
    for index, scope in enumerate(scopes):
        if not isinstance(scope, str) or HIERARCHY.fullmatch(scope) is None:
            errors.append(f"included_scopes[{index}] is invalid")
    if not isinstance(exclusions, list) or len(exclusions) != len(
        {json.dumps(item, sort_keys=True) for item in exclusions if isinstance(item, dict)}
    ):
        errors.append("excluded_scopes must be a unique array")
        exclusions = []
    for index, exclusion in enumerate(exclusions):
        exclusion = _exact_fields(
            f"excluded_scopes[{index}]",
            exclusion,
            {"hierarchical_path", "evidence", "reason"},
            errors,
        )
        hierarchy = exclusion.get("hierarchical_path")
        if not isinstance(hierarchy, str) or HIERARCHY.fullmatch(hierarchy) is None:
            errors.append(f"excluded_scopes[{index}].hierarchical_path is invalid")
        evidence = _exact_fields(
            f"excluded_scopes[{index}].evidence",
            exclusion.get("evidence"),
            {"path", "sha256"},
            errors,
        )
        try:
            safe_relative(f"excluded_scopes[{index}].evidence.path", evidence.get("path"))
        except WaveformGateError as error:
            errors.append(str(error))
        evidence_sha = evidence.get("sha256")
        if not isinstance(evidence_sha, str) or SHA256.fullmatch(evidence_sha) is None:
            errors.append(f"excluded_scopes[{index}].evidence.sha256 is invalid")
        if not isinstance(exclusion.get("reason"), str) or not exclusion.get("reason"):
            errors.append(f"excluded_scopes[{index}].reason must be non-empty")
    if mode == "FULL_HIERARCHY":
        if scopes != ["tb_NDP_Top_new_phy"]:
            errors.append("FULL_HIERARCHY must include exactly tb_NDP_Top_new_phy")
        if exclusions:
            errors.append("FULL_HIERARCHY cannot exclude any scope")
    if mode == "PROVEN_IRRELEVANT_PRUNED" and not exclusions:
        errors.append("pruned waveform mode requires at least one evidence-bound exclusion")

    roots = dump.get("runtime_search_roots")
    if not isinstance(roots, list) or not roots or len(roots) != len(set(roots)):
        errors.append("runtime_search_roots must be a non-empty unique array")
    else:
        for index, root in enumerate(roots):
            try:
                safe_relative(f"runtime_search_roots[{index}]", root)
            except WaveformGateError as error:
                errors.append(str(error))

    policy = _exact_fields(
        "return_policy",
        plan.get("return_policy"),
        {
            "required_when_simulation_started",
            "compile_not_started_omission_allowed",
            "collect_all_matching",
            "archive_prefix",
            "manifest_archive_path",
            "hard_limit_bytes",
            "truncation_allowed",
            "sampling_allowed",
            "size_based_deletion_allowed",
        },
        errors,
    )
    constants = {
        "required_when_simulation_started": True,
        "compile_not_started_omission_allowed": True,
        "collect_all_matching": True,
        "hard_limit_bytes": None,
        "truncation_allowed": False,
        "sampling_allowed": False,
        "size_based_deletion_allowed": False,
    }
    for field, expected in constants.items():
        if policy.get(field) != expected:
            errors.append(f"return_policy.{field} must be {expected!r}")
    for field in ("archive_prefix", "manifest_archive_path"):
        try:
            path = safe_relative(f"return_policy.{field}", policy.get(field))
            if path.suffix.lower() == ".zip":
                errors.append(f"return_policy.{field} cannot name a ZIP")
        except WaveformGateError as error:
            errors.append(str(error))

    integration = _exact_fields(
        "integration",
        plan.get("integration"),
        {
            "plan_member",
            "runner_member",
            "return_request_member",
            "dump_control_member",
            "tool_member",
        },
        errors,
    )
    if integration.get("plan_member") != PLAN_MEMBER:
        errors.append(f"integration.plan_member must be {PLAN_MEMBER}")
    for field in (
        "plan_member",
        "runner_member",
        "return_request_member",
        "dump_control_member",
        "tool_member",
    ):
        try:
            safe_relative(f"integration.{field}", integration.get(field))
        except WaveformGateError as error:
            errors.append(str(error))
    if not isinstance(plan.get("claim_boundary"), str) or not plan.get("claim_boundary"):
        errors.append("claim_boundary must be non-empty")
    return errors


def render_dump_control(plan: dict[str, Any]) -> str:
    errors = validate_plan(plan)
    if errors:
        raise WaveformGateError("; ".join(errors))
    dump = plan["dump"]
    profile = waveform_profile(plan)
    if profile["format"] == "VPD":
        lines = ["dump -file $CODEX_WAVE_PATH -type VPD"]
        for scope in dump["included_scopes"]:
            depth = " -depth 0 -aggregates" if scope == dump["tb_top"] else " -aggregates"
            lines.append(f"dump -add {scope}{depth}")
    else:
        # VCS/Verdi FSDB PLI commands are used directly.  TB_DUMP_FSDB stays 0
        # so the package owns exactly one writer and one attempt-local path.
        lines = ["fsdbDumpfile $CODEX_WAVE_PATH"]
        for scope in dump["included_scopes"]:
            lines.append(f"fsdbDumpvars 0 {scope}")
            lines.append(f"fsdbDumpMDA 0 {scope}")
        lines.append("fsdbDumpflush")
    lines.extend(["run", "quit", ""])
    return "\n".join(lines)


def _safe_zip(archive: zipfile.ZipFile) -> tuple[str, list[str]]:
    names = archive.namelist()
    if not names:
        raise WaveformGateError("ZIP is empty")
    roots: set[str] = set()
    for name in names:
        if "\\" in name:
            raise WaveformGateError(f"ZIP member contains backslash: {name}")
        path = PurePosixPath(name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise WaveformGateError(f"unsafe ZIP member: {name}")
        roots.add(path.parts[0])
    if len(roots) != 1:
        raise WaveformGateError(f"ZIP must have one top-level root: {sorted(roots)}")
    return next(iter(roots)), names


def _member(root: str, relative: str) -> str:
    return f"{root}/{safe_relative('member', relative).as_posix()}"


def _noncomment_shell(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _has_shell_token(text: str, token: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text
    ) is not None


def validate_final_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            root, names = _safe_zip(archive)
            plan_name = _member(root, PLAN_MEMBER)
            if plan_name not in names:
                raise WaveformGateError(f"mandatory waveform plan is absent: {plan_name}")
            plan_data = archive.read(plan_name)
            plan = json.loads(plan_data)
            errors.extend(validate_plan(plan))
            details["plan_sha256"] = hashlib.sha256(plan_data).hexdigest()
            if plan.get("package_id") != root:
                errors.append("plan package_id does not match exact ZIP root")
            integration = plan.get("integration", {})
            required: dict[str, str] = {}
            for field in (
                "runner_member",
                "return_request_member",
                "dump_control_member",
                "tool_member",
            ):
                value = integration.get(field)
                if isinstance(value, str):
                    required[field] = _member(root, value)
            for field, name in required.items():
                if name not in names:
                    errors.append(f"required {field} is absent: {name}")
            if errors:
                raise WaveformGateError("required exact package members are incomplete")

            runner = _noncomment_shell(
                archive.read(required["runner_member"]).decode("utf-8", errors="replace")
            )
            profile = waveform_profile(plan)
            required_tokens = tuple(
                f"{key}={value}" for key, value in profile["make_arguments"].items()
            )
            for token in required_tokens:
                if not _has_shell_token(runner, token):
                    errors.append(f"actual runner misses mandatory token {token}")
            contradictory = (
                ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=1")
                if profile["format"] == "VPD"
                else ("DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=1")
            )
            for token in contradictory:
                if _has_shell_token(runner, token):
                    errors.append(f"actual runner contains contradictory waveform token {token}")
            if "server_waveform_mandatory_return.py" not in runner:
                errors.append("actual runner does not invoke the mandatory waveform collector")

            control = archive.read(required["dump_control_member"]).decode(
                "utf-8", errors="replace"
            )
            expected_control = render_dump_control(plan)
            if control != expected_control:
                errors.append(
                    f"dump control is not the exact plan-derived full/pruned {profile['format']} control"
                )
            request = json.loads(archive.read(required["return_request_member"]))
            discovery = request.get("waveform_discovery") if isinstance(request, dict) else None
            expected_discovery = {
                "plan_member": PLAN_MEMBER,
                "collector_member": integration["tool_member"],
                "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
                "collect_all_matching": True,
                "required_when_simulation_started": True,
                "no_size_limit": True,
                "manifest_archive_path": plan["return_policy"]["manifest_archive_path"],
            }
            if discovery != expected_discovery:
                errors.append("return request misses the exact unbounded waveform discovery contract")

            packaged_tool = archive.read(required["tool_member"])
            current_tool = Path(__file__).read_bytes()
            if packaged_tool != current_tool:
                errors.append("package waveform collector is not byte-equal to the shared tool")
            for exclusion in plan["dump"]["excluded_scopes"]:
                evidence = exclusion["evidence"]
                evidence_member = _member(root, evidence["path"])
                if evidence_member not in names:
                    errors.append(f"excluded-scope evidence is absent: {evidence_member}")
                    continue
                actual = hashlib.sha256(archive.read(evidence_member)).hexdigest()
                if actual != evidence["sha256"]:
                    errors.append(f"excluded-scope evidence SHA mismatch: {evidence_member}")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, WaveformGateError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "final_zip",
        "path": str(zip_path),
        "pass": not errors,
        "errors": errors,
        "details": details,
        "claim_boundary": "Package waveform plumbing only; no DUT or formal-result claim.",
    }


def _matches_waveform_name(name: str, profile: dict[str, Any] | None = None) -> bool:
    primary = (profile or {"primary": "wave.vpd"})["primary"]
    return name == primary or name.startswith(f"{primary}.")


def collect_runtime(
    plan_path: Path,
    attempt_root: Path,
    execution_id: str,
    simulation_started: bool,
    exit_kind: str,
) -> dict[str, Any]:
    plan_data = plan_path.read_bytes()
    plan = json.loads(plan_data)
    errors = validate_plan(plan)
    try:
        profile = waveform_profile(plan)
    except WaveformGateError as error:
        errors.append(str(error))
        profile = {"format": "UNKNOWN", "receipt_schema": "invalid", "primary": "waveform"}
    if not SAFE_NAME.fullmatch(execution_id):
        errors.append("execution_id is not a safe name")
    if exit_kind not in EXIT_KINDS:
        errors.append("exit_kind is invalid")
    if simulation_started and exit_kind in {"COMPILE_FAILURE", "SIMULATION_NOT_STARTED"}:
        errors.append("simulation_started conflicts with pre-simulation exit_kind")
    if not simulation_started and exit_kind not in {"COMPILE_FAILURE", "SIMULATION_NOT_STARTED"}:
        errors.append("simulation_not_started conflicts with dynamic exit_kind")

    root = attempt_root.resolve()
    matches: list[Path] = []
    for relative_root in plan.get("dump", {}).get("runtime_search_roots", []):
        try:
            search = (root / Path(*safe_relative("runtime_search_root", relative_root).parts)).resolve()
        except (OSError, WaveformGateError) as error:
            errors.append(str(error))
            continue
        if root != search and root not in search.parents:
            errors.append(f"runtime search root escapes attempt root: {relative_root}")
            continue
        if not search.exists():
            continue
        if search.is_symlink() or not search.is_dir():
            errors.append(f"runtime search root is not a real directory: {relative_root}")
            continue
        for path in search.rglob("*"):
            if not path.is_file() or not _matches_waveform_name(path.name, profile):
                continue
            if path.is_symlink():
                errors.append(f"waveform cannot be a symlink: {path}")
                continue
            resolved = path.resolve()
            if root not in resolved.parents:
                errors.append(f"waveform escapes attempt root: {path}")
                continue
            matches.append(resolved)
    matches = sorted(set(matches), key=lambda item: item.relative_to(root).as_posix())
    if simulation_started and not matches:
        errors.append(
            f"simulation_started=true but no {profile['primary']} or shard was found"
        )
    if not simulation_started and matches:
        errors.append("pre-simulation exit contains waveform files; possible stale attempt evidence")

    completeness = "COMPLETE" if exit_kind == "NATURAL" else "PARTIAL"
    waveforms: list[dict[str, Any]] = []
    archive_prefix = plan.get("return_policy", {}).get("archive_prefix", "waveforms")
    for path in matches:
        size, digest = hash_file(path)
        if size < 1:
            errors.append(f"waveform is empty: {path.relative_to(root).as_posix()}")
            continue
        source = path.relative_to(root).as_posix()
        archive_path = f"{archive_prefix}/{source}"
        safe_relative("waveform archive path", archive_path)
        waveforms.append(
            {
                "source_path": source,
                "archive_path": archive_path,
                "bytes": size,
                "sha256": digest,
                "format": profile["format"],
                "completeness": completeness,
            }
        )
    return {
        "schema": profile["receipt_schema"],
        "package_id": plan.get("package_id"),
        "execution_id": execution_id,
        "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
        "simulation_started": simulation_started,
        "exit_kind": exit_kind,
        "waveforms": waveforms,
        "no_size_limit": True,
        "all_matching_collected": True,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Waveform discovery and identity only; no DUT result claim.",
    }


def _find_receipt(archive: zipfile.ZipFile, root: str, manifest_path: str) -> tuple[str, Any]:
    member = _member(root, manifest_path)
    if member not in archive.namelist():
        raise WaveformGateError(f"waveform runtime receipt is absent: {member}")
    return member, json.loads(archive.read(member))


def inspect_return_zip(zip_path: Path, plan_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {}
    try:
        plan_data = plan_path.read_bytes()
        plan = json.loads(plan_data)
        errors.extend(validate_plan(plan))
        profile = waveform_profile(plan)
        with zipfile.ZipFile(zip_path) as archive:
            root, names = _safe_zip(archive)
            _, receipt = _find_receipt(
                archive, root, plan["return_policy"]["manifest_archive_path"]
            )
            if receipt.get("schema") != profile["receipt_schema"]:
                errors.append("waveform runtime receipt schema mismatch")
            if receipt.get("package_id") != plan.get("package_id"):
                errors.append("waveform receipt package identity mismatch")
            if receipt.get("plan_sha256") != hashlib.sha256(plan_data).hexdigest():
                errors.append("waveform receipt plan SHA mismatch")
            if receipt.get("no_size_limit") is not True:
                errors.append("waveform receipt introduced a size limit")
            if receipt.get("all_matching_collected") is not True:
                errors.append("waveform receipt did not collect every matching shard")
            waveforms = receipt.get("waveforms")
            if not isinstance(waveforms, list):
                errors.append("waveform receipt waveforms must be an array")
                waveforms = []
            if receipt.get("simulation_started") is True and not waveforms:
                errors.append("simulation_started=true formal return has no waveform")
            if receipt.get("simulation_started") is False and waveforms:
                errors.append("simulation_not_started formal return carries stale waveform")
            declared: set[str] = set()
            total = 0
            for index, waveform in enumerate(waveforms):
                if not isinstance(waveform, dict):
                    errors.append(f"waveforms[{index}] must be an object")
                    continue
                archive_path = waveform.get("archive_path")
                try:
                    safe_relative(f"waveforms[{index}].archive_path", archive_path)
                except WaveformGateError as error:
                    errors.append(str(error))
                    continue
                if not isinstance(archive_path, str) or ".zip" in archive_path.lower():
                    errors.append(f"waveforms[{index}] is not a waveform member")
                    continue
                name = _member(root, archive_path)
                declared.add(name)
                if name not in names:
                    errors.append(f"declared waveform is absent: {name}")
                    continue
                with archive.open(name) as stream:
                    size, digest = hash_stream(stream)
                total += size
                if size != waveform.get("bytes"):
                    errors.append(f"waveform byte count mismatch: {name}")
                if digest != waveform.get("sha256"):
                    errors.append(f"waveform SHA mismatch: {name}")
                if waveform.get("format") != profile["format"]:
                    errors.append(f"waveform format mismatch: {name}")
                expected_complete = (
                    "COMPLETE" if receipt.get("exit_kind") == "NATURAL" else "PARTIAL"
                )
                if waveform.get("completeness") != expected_complete:
                    errors.append(f"waveform completeness mismatch: {name}")
            prefix = f"{root}/{plan['return_policy']['archive_prefix']}/"
            actual = {
                name
                for name in names
                if name.startswith(prefix)
                and _matches_waveform_name(PurePosixPath(name).name, profile)
            }
            if actual != declared:
                errors.append(
                    f"formal return waveform exact-set mismatch: declared={sorted(declared)} actual={sorted(actual)}"
                )
            if receipt.get("pass") is not True or receipt.get("errors") != []:
                errors.append("runtime waveform collector did not pass")
            details.update(
                {
                    "waveform_count": len(waveforms),
                    "waveform_total_bytes": total,
                    "simulation_started": receipt.get("simulation_started"),
                    "exit_kind": receipt.get("exit_kind"),
                }
            )
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, WaveformGateError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "return_zip",
        "path": str(zip_path),
        "pass": not errors,
        "errors": errors,
        "details": details,
        "claim_boundary": "Waveform return integrity only; no DUT or formal-result claim.",
    }


def inspect_vpd(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not path.is_file() or path.is_symlink():
        errors.append("VPD path must be a real file")
        size, digest = 0, None
    elif not _matches_waveform_name(path.name) and path.suffix.lower() != ".vpd":
        errors.append("waveform file name is not VPD-compatible")
        size, digest = hash_file(path)
    else:
        size, digest = hash_file(path)
        if size < 1:
            errors.append("VPD file is empty")
    viewers = {name: shutil.which(name) for name in ("verdi", "dve", "vpd2vcd")}
    quoted = f'"{path.resolve()}"'
    commands = {
        "verdi": f"verdi -vpd {quoted}",
        "dve": f"dve -vpd {quoted}",
        "vpd2vcd": f"vpd2vcd {quoted} \"{path.resolve()}.vcd\"",
    }
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "vpd_identity",
        "path": str(path),
        "pass": not errors,
        "errors": errors,
        "identity": {"bytes": size, "sha256": digest, "format": "VPD"},
        "discovered_tools": viewers,
        "open_commands": commands,
        "claim_boundary": "File identity and viewer discovery only; waveform semantics are not decoded.",
    }


def inspect_fsdb(path: Path) -> dict[str, Any]:
    """Bind an FSDB file and discover only registered, read-only consumers.

    Binary FSDB semantics are deliberately not inferred by this helper.  A
    family may consume the file through Verdi/WaveUtils or an identity-bound
    query receipt, while the raw file remains the authoritative return asset.
    """
    errors: list[str] = []
    if not path.is_file() or path.is_symlink():
        errors.append("FSDB path must be a real file")
        size, digest = 0, None
    elif not _matches_waveform_name(path.name, {"primary": "wave.fsdb"}) and path.suffix.lower() != ".fsdb":
        errors.append("waveform file name is not FSDB-compatible")
        size, digest = hash_file(path)
    else:
        size, digest = hash_file(path)
        if size < 1:
            errors.append("FSDB file is empty")
    tools = {
        name: shutil.which(name)
        for name in ("verdi", "nWave", "fsdbreport", "fsdb2vcd", "wv")
    }
    quoted = f'"{path.resolve()}"'
    commands = {
        "verdi": f"verdi -ssf {quoted}",
        "nWave": f"nWave -ssf {quoted}",
        "fsdb2vcd": f"fsdb2vcd {quoted} -o \"{path.resolve()}.vcd\"",
    }
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "fsdb_identity",
        "path": str(path),
        "pass": not errors,
        "errors": errors,
        "identity": {"bytes": size, "sha256": digest, "format": "FSDB"},
        "discovered_tools": tools,
        "open_commands": commands,
        "semantic_status": "TOOL_REQUIRED" if not any(tools.values()) else "TOOL_DISCOVERED",
        "claim_boundary": "File identity and registered tool discovery only; waveform semantics are not inferred.",
    }


def extract_return(zip_path: Path, output_dir: Path, plan_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    extracted: list[dict[str, Any]] = []
    try:
        plan = load_json(plan_path)
        with zipfile.ZipFile(zip_path) as archive:
            root, _ = _safe_zip(archive)
            _, receipt = _find_receipt(
                archive, root, plan["return_policy"]["manifest_archive_path"]
            )
            destination_root = output_dir.resolve()
            destination_root.mkdir(parents=True, exist_ok=True)
            for waveform in receipt.get("waveforms", []):
                relative = safe_relative("archive_path", waveform.get("archive_path"))
                member = _member(root, relative.as_posix())
                target = (destination_root / Path(*relative.parts)).resolve()
                if destination_root not in target.parents:
                    raise WaveformGateError(f"extraction target escapes output root: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink, length=1024 * 1024)
                size, digest = hash_file(target)
                if size != waveform.get("bytes") or digest != waveform.get("sha256"):
                    errors.append(f"extracted waveform identity mismatch: {relative}")
                extracted.append(
                    {
                        "archive_path": relative.as_posix(),
                        "output_path": str(target),
                        "bytes": size,
                        "sha256": digest,
                    }
                )
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, WaveformGateError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "extract_return",
        "path": str(zip_path),
        "pass": not errors,
        "errors": errors,
        "extracted": extracted,
        "claim_boundary": "Safe waveform extraction and identity only.",
    }


def _bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-plan")
    validate.add_argument("--plan", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    render = commands.add_parser("render-dump-control")
    render.add_argument("--plan", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    final_zip = commands.add_parser("validate-final-zip")
    final_zip.add_argument("--zip", dest="zip_path", type=Path, required=True)
    final_zip.add_argument("--output", type=Path, required=True)
    collect = commands.add_parser("collect-runtime")
    collect.add_argument("--plan", type=Path, required=True)
    collect.add_argument("--attempt-root", type=Path, required=True)
    collect.add_argument("--execution-id", required=True)
    collect.add_argument("--simulation-started", type=_bool, required=True)
    collect.add_argument("--exit-kind", choices=sorted(EXIT_KINDS), required=True)
    collect.add_argument("--output", type=Path, required=True)
    returned = commands.add_parser("inspect-return")
    returned.add_argument("--zip", dest="zip_path", type=Path, required=True)
    returned.add_argument("--plan", type=Path, required=True)
    returned.add_argument("--output", type=Path, required=True)
    vpd = commands.add_parser("inspect-vpd")
    vpd.add_argument("--wave", type=Path, required=True)
    vpd.add_argument("--output", type=Path, required=True)
    fsdb = commands.add_parser("inspect-fsdb")
    fsdb.add_argument("--wave", type=Path, required=True)
    fsdb.add_argument("--output", type=Path, required=True)
    extract = commands.add_parser("extract-return")
    extract.add_argument("--zip", dest="zip_path", type=Path, required=True)
    extract.add_argument("--plan", type=Path, required=True)
    extract.add_argument("--output-dir", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate-plan":
            errors = validate_plan(load_json(args.plan))
            report = {
                "schema": VALIDATION_SCHEMA,
                "kind": "plan",
                "path": str(args.plan),
                "pass": not errors,
                "errors": errors,
            }
        elif args.command == "render-dump-control":
            rendered = render_dump_control(load_json(args.plan))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
            return 0
        elif args.command == "validate-final-zip":
            report = validate_final_zip(args.zip_path)
        elif args.command == "collect-runtime":
            report = collect_runtime(
                args.plan,
                args.attempt_root,
                args.execution_id,
                args.simulation_started,
                args.exit_kind,
            )
        elif args.command == "inspect-return":
            report = inspect_return_zip(args.zip_path, args.plan)
        elif args.command == "inspect-vpd":
            report = inspect_vpd(args.wave)
        elif args.command == "inspect-fsdb":
            report = inspect_fsdb(args.wave)
        else:
            report = extract_return(args.zip_path, args.output_dir, args.plan)
        write_json(args.output, report)
        return 0 if report.get("pass") else 1
    except (OSError, json.JSONDecodeError, WaveformGateError) as error:
        report = {
            "schema": VALIDATION_SCHEMA,
            "kind": args.command,
            "pass": False,
            "errors": [f"{type(error).__name__}: {error}"],
        }
        write_json(args.output, report)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
