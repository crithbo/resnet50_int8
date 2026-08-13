#!/usr/bin/env python3
"""Build and validate portable waveform evidence for a single simulation attempt.

This helper does not run a simulator.  It binds the existing mandatory raw VPD
receipt to either a directly dumped VCD or a registered, source-bound signal
event receipt.  The raw VPD remains authoritative and every failure mode keeps
``return_must_publish`` true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from tools.server_waveform_local_analysis import validate_vcd
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.server_waveform_local_analysis import validate_vcd


RULE_ID = "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001"
PROFILE_SCHEMA = "server-waveform-portable-query-profile-v1"
QUERY_SCHEMA = "server-waveform-signal-query-receipt-v1"
RUNTIME_SCHEMA = "server-waveform-portable-runtime-receipt-v1"
VALIDATION_SCHEMA = "server-waveform-portable-validation-v1"
RAW_RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v2"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
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
DYNAMIC_EXITS = EXIT_KINDS - {"COMPILE_FAILURE", "SIMULATION_NOT_STARTED"}


class PortableWaveformError(ValueError):
    """A portable waveform profile, request, receipt or path is invalid."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def pretty_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(pretty_json(value))
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hash_file(path: Path) -> tuple[int, str]:
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


def catalog_sha(catalog: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json(catalog)).hexdigest()


def safe_relative(label: str, value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise PortableWaveformError(f"{label} must be a POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PortableWaveformError(f"{label} is unsafe: {value}")
    return path


def resolve_asset(root: Path, label: str, relative: Any) -> Path:
    parts = safe_relative(label, relative).parts
    resolved_root = root.resolve()
    target = (resolved_root / Path(*parts)).resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise PortableWaveformError(f"{label} escapes asset root: {relative}")
    return target


def is_under_attempt(relative: str, attempt_root: str) -> bool:
    path = safe_relative("artifact path", relative)
    attempt = safe_relative("attempt_root", attempt_root)
    return path == attempt or attempt in path.parents


def _profile_catalog(profile: dict[str, Any]) -> list[dict[str, Any]]:
    value = profile.get("probe_catalog")
    return value if isinstance(value, list) else []


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("schema") != PROFILE_SCHEMA:
        errors.append("profile schema mismatch")
    if profile.get("rule_id") != RULE_ID:
        errors.append("profile rule_id mismatch")
    if profile.get("activation") != "required_next_fresh":
        errors.append("profile activation must be required_next_fresh")
    raw = profile.get("raw_vpd")
    if not isinstance(raw, dict):
        errors.append("raw_vpd contract is absent")
        raw = {}
    if raw.get("authoritative") is not True:
        errors.append("raw VPD must remain authoritative")
    if raw.get("existing_dump_vcd_semantics") != "VPD":
        errors.append("DUMP_VCD=1 must remain explicitly bound to VPD")
    if raw.get("make_arguments") != {
        "DUMP_VCD": "1",
        "DUMP_FSDB": "0",
        "TB_DUMP_FSDB": "0",
    }:
        errors.append("raw VPD make arguments are not exact")
    if raw.get("hard_limit_bytes") is not None:
        errors.append("raw VPD hard_limit_bytes must be null")
    for field in ("truncation", "sampling", "size_based_deletion"):
        if raw.get(field) is not False:
            errors.append(f"raw VPD {field} must be false")

    direct = profile.get("portable_vcd")
    if not isinstance(direct, dict):
        errors.append("portable_vcd contract is absent")
        direct = {}
    if direct.get("make_argument") != {"DUMP_PORTABLE_VCD": "1"}:
        errors.append("portable VCD must use distinct DUMP_PORTABLE_VCD=1")
    if direct.get("format") != "VCD" or direct.get("ucli_type") != "VCD":
        errors.append("portable VCD format/UCLI type mismatch")
    if direct.get("first_fresh_required") is not True:
        errors.append("first fresh must require direct portable VCD")
    if direct.get("hard_limit_bytes") is not None:
        errors.append("portable VCD hard_limit_bytes must be null")
    for field in ("truncation", "sampling", "size_based_deletion"):
        if direct.get(field) is not False:
            errors.append(f"portable VCD {field} must be false")
    scope = direct.get("source_bound_scope")
    if not isinstance(scope, dict):
        errors.append("portable VCD source_bound_scope is absent")
        scope = {}
    if scope.get("top") != "tb_NDP_Top_new_phy":
        errors.append("portable VCD top must be tb_NDP_Top_new_phy")
    if not isinstance(scope.get("depth"), int) or scope.get("depth") < 0:
        errors.append("portable VCD depth must be a non-negative integer")
    if not SHA256.fullmatch(str(scope.get("source_receipt_sha256", ""))):
        errors.append("portable VCD source scope lacks exact receipt SHA")

    query = profile.get("signal_query")
    if not isinstance(query, dict):
        errors.append("signal_query contract is absent")
        query = {}
    expected_query = {
        "format": "REGISTERED_EVENT_ROWS",
        "custom_free_form_text": False,
        "hard_limit_bytes": None,
        "hard_limit_events": None,
        "sampling": False,
        "truncation": False,
        "ordered_every_transition": True,
    }
    for field, expected in expected_query.items():
        if query.get(field) != expected:
            errors.append(f"signal_query {field} must be {expected!r}")

    failure = profile.get("failure_semantics")
    if not isinstance(failure, dict):
        errors.append("failure_semantics is absent")
    else:
        if failure.get("return_must_publish") is not True:
            errors.append("portable/query failure must still publish the return")
        if failure.get("diagnostic_status") != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
            errors.append("failure diagnostic status mismatch")
        required = set(failure.get("preserve", []))
        if required != {"raw_vpd", "compile_core", "sim_core", "signal_core", "return_core"}:
            errors.append("failure preservation exact-set mismatch")

    catalog = _profile_catalog(profile)
    if not catalog:
        errors.append("probe_catalog must not be empty")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, candidate in enumerate(catalog):
        if not isinstance(candidate, dict):
            errors.append(f"probe_catalog[{index}] must be an object")
            continue
        candidate_id = candidate.get("candidate_id")
        path = candidate.get("hierarchical_path")
        width = candidate.get("width")
        if not isinstance(candidate_id, str) or not SAFE_NAME.fullmatch(candidate_id):
            errors.append(f"probe_catalog[{index}] candidate_id is invalid")
        elif candidate_id in seen_ids:
            errors.append(f"duplicate probe candidate_id: {candidate_id}")
        else:
            seen_ids.add(candidate_id)
        if not isinstance(path, str) or not path.startswith("tb_NDP_Top_new_phy."):
            errors.append(f"probe_catalog[{index}] hierarchical_path is invalid")
        elif path in seen_paths:
            errors.append(f"duplicate probe hierarchical_path: {path}")
        else:
            seen_paths.add(path)
        if not isinstance(width, int) or width < 1:
            errors.append(f"probe_catalog[{index}] width must be positive")
    if profile.get("probe_catalog_sha256") != catalog_sha(catalog):
        errors.append("probe_catalog_sha256 mismatch")
    return errors


def render_dump_tcl(
    profile: dict[str, Any],
    attempt_root: str,
    sim_time: str,
    capture_mode: str,
) -> str:
    errors = validate_profile(profile)
    if errors:
        raise PortableWaveformError("; ".join(errors))
    safe_relative("attempt_root", attempt_root)
    if not isinstance(sim_time, str) or not sim_time.strip() or "\n" in sim_time:
        raise PortableWaveformError("sim_time must be one non-empty Tcl token")
    if capture_mode not in {"DIRECT_VCD_AND_QUERY", "QUERY_ONLY"}:
        raise PortableWaveformError("capture_mode is invalid")
    scope = profile["portable_vcd"]["source_bound_scope"]
    lines = [
        f"dump -file {attempt_root}/run/sim_results/wave.vpd -type VPD",
        f"dump -add {scope['top']} -depth {scope['depth']} -aggregates",
    ]
    if capture_mode == "DIRECT_VCD_AND_QUERY":
        lines.extend(
            [
                f"dump -file {attempt_root}/run/sim_results/wave.vcd -type VCD",
                f"dump -add {scope['top']} -depth {scope['depth']} -aggregates",
            ]
        )
    lines.extend([f"run {sim_time}", "quit"])
    return "\n".join(lines) + "\n"


def _identity(path: Path) -> dict[str, Any]:
    size, digest = hash_file(path)
    return {"path": None, "bytes": size, "sha256": digest}


def _expected_value(width: int, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower()
    if width == 1:
        return bool(re.fullmatch(r"[01xz]", normalized))
    return bool(re.fullmatch(rf"b[01xz]{{{width}}}", normalized))


def validate_query_receipt(
    query: dict[str, Any], profile: dict[str, Any], identities: dict[str, str]
) -> list[str]:
    errors: list[str] = []
    allowed_top = {
        "schema",
        "package_id",
        "execution_id",
        "attempt_id",
        "profile_sha256",
        "probe_catalog_sha256",
        "timescale",
        "completeness",
        "catalog",
        "capture",
        "candidate_coverage",
        "events",
        "candidate_end_states",
        "claim_boundary",
    }
    unexpected_top = set(query) - allowed_top
    if unexpected_top:
        errors.append(f"query receipt contains unregistered fields: {sorted(unexpected_top)}")
    catalog = _profile_catalog(profile)
    expected_ids = [item["candidate_id"] for item in catalog if isinstance(item, dict)]
    by_id = {item["candidate_id"]: item for item in catalog if isinstance(item, dict)}
    if query.get("schema") != QUERY_SCHEMA:
        errors.append("query receipt schema mismatch")
    for field in ("package_id", "execution_id", "attempt_id"):
        if query.get(field) != identities[field]:
            errors.append(f"query {field} identity mismatch")
    if query.get("profile_sha256") != identities["profile_sha256"]:
        errors.append("query profile SHA mismatch")
    if query.get("probe_catalog_sha256") != profile.get("probe_catalog_sha256"):
        errors.append("query probe catalog SHA mismatch")
    if query.get("catalog") != catalog:
        errors.append("query catalog is not exact profile catalog")
    if not isinstance(query.get("timescale"), str) or not query.get("timescale"):
        errors.append("query timescale is absent")
    capture = query.get("capture")
    expected_capture = {
        "format": "REGISTERED_EVENT_ROWS",
        "ordered": True,
        "every_transition": True,
        "no_byte_limit": True,
        "no_event_limit": True,
        "sampling": False,
        "truncation": False,
        "flush_complete": True,
    }
    if not isinstance(capture, dict):
        errors.append("query capture contract is absent")
    else:
        for field, expected in expected_capture.items():
            if capture.get(field) != expected:
                errors.append(f"query capture {field} must be {expected!r}")
        allowed = set(expected_capture) | {"source_generation_report"}
        unexpected = set(capture) - allowed
        if unexpected:
            errors.append(f"query capture contains unregistered fields: {sorted(unexpected)}")
        source = capture.get("source_generation_report")
        if not isinstance(source, dict) or not SHA256.fullmatch(str(source.get("sha256", ""))):
            errors.append("query source generation report identity is absent")
    coverage = query.get("candidate_coverage")
    if not isinstance(coverage, dict):
        errors.append("query candidate_coverage is absent")
    else:
        if coverage.get("expected") != expected_ids or coverage.get("covered") != expected_ids:
            errors.append("query candidate coverage is not exact ordered complete set")
        if coverage.get("missing") != [] or coverage.get("unexpected") != []:
            errors.append("query candidate coverage has missing/unexpected candidates")
    end_states = query.get("candidate_end_states")
    if not isinstance(end_states, list):
        errors.append("query candidate_end_states is absent")
        end_states = []
    if [item.get("candidate_id") for item in end_states if isinstance(item, dict)] != expected_ids:
        errors.append("query candidate end-state coverage is incomplete or reordered")
    for item in end_states:
        if not isinstance(item, dict):
            continue
        candidate = by_id.get(item.get("candidate_id"))
        if candidate is None:
            continue
        if item.get("hierarchical_path") != candidate["hierarchical_path"]:
            errors.append(f"query end-state path mismatch: {item.get('candidate_id')}")
        if item.get("width") != candidate["width"]:
            errors.append(f"query end-state width mismatch: {item.get('candidate_id')}")
        if not _expected_value(candidate["width"], item.get("value")):
            errors.append(f"query end-state value mismatch: {item.get('candidate_id')}")
    events = query.get("events")
    if not isinstance(events, list):
        errors.append("query events must be an array")
        events = []
    for sequence, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"query events[{sequence}] must be an object")
            continue
        if event.get("sequence") != sequence:
            errors.append(f"query event sequence discontinuity at {sequence}")
        candidate = by_id.get(event.get("candidate_id"))
        if candidate is None:
            errors.append(f"query event candidate is unknown: {event.get('candidate_id')}")
            continue
        if event.get("hierarchical_path") != candidate["hierarchical_path"]:
            errors.append(f"query event path mismatch: {event.get('candidate_id')}")
        if event.get("width") != candidate["width"]:
            errors.append(f"query event width mismatch: {event.get('candidate_id')}")
        if not isinstance(event.get("time_tick"), int) or event["time_tick"] < 0:
            errors.append(f"query event time is invalid: {sequence}")
        if not _expected_value(candidate["width"], event.get("value")):
            errors.append(f"query event value is invalid: {sequence}")
    return errors


def _load_identity_bound_json(
    asset_root: Path,
    relative: str,
    identity: dict[str, Any],
    label: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        path = resolve_asset(asset_root, label, relative)
        if not path.is_file() or path.is_symlink():
            raise PortableWaveformError(f"{label} must be a real file")
        size, digest = hash_file(path)
        if identity != {"path": relative, "bytes": size, "sha256": digest}:
            errors.append(f"{label} identity mismatch")
        return load_json(path), errors
    except (OSError, json.JSONDecodeError, PortableWaveformError) as error:
        errors.append(f"{label}: {type(error).__name__}: {error}")
        return None, errors


def validate_runtime_receipt(
    receipt: dict[str, Any], profile: dict[str, Any], asset_root: Path
) -> dict[str, Any]:
    structural: list[str] = validate_profile(profile)
    diagnostic: list[str] = []
    profile_sha = hashlib.sha256(pretty_json(profile)).hexdigest()
    if receipt.get("schema") != RUNTIME_SCHEMA:
        structural.append("runtime receipt schema mismatch")
    if receipt.get("rule_id") != RULE_ID:
        structural.append("runtime receipt rule_id mismatch")
    if receipt.get("profile_sha256") != profile_sha:
        structural.append("runtime profile SHA mismatch")
    identities = {
        "package_id": receipt.get("package_id"),
        "execution_id": receipt.get("execution_id"),
        "attempt_id": receipt.get("attempt_id"),
        "profile_sha256": profile_sha,
    }
    for field in ("package_id", "execution_id", "attempt_id"):
        if not isinstance(identities[field], str) or not SAFE_NAME.fullmatch(identities[field]):
            structural.append(f"runtime {field} is invalid")
    attempt_root = receipt.get("attempt_root")
    try:
        safe_relative("attempt_root", attempt_root)
    except PortableWaveformError as error:
        structural.append(str(error))
        attempt_root = "invalid"
    if receipt.get("exit_kind") not in EXIT_KINDS:
        structural.append("runtime exit_kind is invalid")
    sim_started = receipt.get("simulation_started") is True
    if sim_started != (receipt.get("exit_kind") in DYNAMIC_EXITS):
        structural.append("simulation_started and exit_kind conflict")
    mode = receipt.get("capture_mode")
    if mode not in {"DIRECT_VCD_AND_QUERY", "QUERY_ONLY"}:
        structural.append("runtime capture_mode is invalid")
    if receipt.get("first_fresh_for_profile") is True and mode != "DIRECT_VCD_AND_QUERY":
        diagnostic.append("first fresh requires direct portable VCD")

    argv = receipt.get("actual_sim_argv")
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        structural.append("actual_sim_argv must be an argv array")
        argv = []
    required_tokens = ["DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"]
    if mode == "DIRECT_VCD_AND_QUERY":
        required_tokens.append("DUMP_PORTABLE_VCD=1")
    else:
        required_tokens.append("DUMP_PORTABLE_VCD=0")
    for token in required_tokens:
        if argv.count(token) != 1:
            structural.append(f"actual sim argv must contain exactly one {token}")
    if "DUMP_VCD=0" in argv:
        structural.append("actual sim argv disables authoritative VPD")

    allowlist = receipt.get("return_allowlist")
    if not isinstance(allowlist, list) or not all(isinstance(item, str) for item in allowlist):
        structural.append("return_allowlist must be an array of source paths")
        allowlist = []
    if len(allowlist) != len(set(allowlist)):
        structural.append("return_allowlist contains duplicates")

    dump = receipt.get("dump_tcl")
    dump_text = ""
    if not isinstance(dump, dict):
        structural.append("dump_tcl identity is absent")
    else:
        relative = dump.get("path")
        try:
            if not is_under_attempt(relative, attempt_root):
                structural.append("dump_tcl is outside exact attempt")
            path = resolve_asset(asset_root, "dump_tcl", relative)
            size, digest = hash_file(path)
            if dump != {"path": relative, "bytes": size, "sha256": digest}:
                structural.append("dump_tcl identity mismatch")
            dump_text = path.read_text(encoding="utf-8")
        except (OSError, PortableWaveformError) as error:
            structural.append(f"dump_tcl: {type(error).__name__}: {error}")
    scope = profile["portable_vcd"]["source_bound_scope"]
    vpd_line = f"dump -file {attempt_root}/run/sim_results/wave.vpd -type VPD"
    vcd_line = f"dump -file {attempt_root}/run/sim_results/wave.vcd -type VCD"
    scope_line = f"dump -add {scope['top']} -depth {scope['depth']} -aggregates"
    if dump_text.count(vpd_line) != 1 or dump_text.count(scope_line) < 1:
        structural.append("dump Tcl does not preserve exact authoritative VPD scope")
    if mode == "DIRECT_VCD_AND_QUERY":
        if dump_text.count(vcd_line) != 1 or dump_text.count(scope_line) != 2:
            structural.append("dump Tcl lacks exact distinct portable VCD scope")
    elif vcd_line in dump_text:
        structural.append("QUERY_ONLY dump Tcl unexpectedly enables portable VCD")

    raw = receipt.get("raw_vpd_runtime_receipt")
    raw_data = None
    if not isinstance(raw, dict):
        structural.append("raw VPD runtime receipt identity is absent")
    else:
        relative = raw.get("path")
        try:
            if not is_under_attempt(relative, attempt_root):
                structural.append("raw VPD runtime receipt is outside exact attempt")
            raw_data, raw_errors = _load_identity_bound_json(
                asset_root, relative, raw, "raw VPD runtime receipt"
            )
            structural.extend(raw_errors)
        except PortableWaveformError as error:
            structural.append(str(error))
    if raw_data is not None:
        if raw_data.get("schema") != RAW_RECEIPT_SCHEMA:
            structural.append("raw VPD runtime receipt schema mismatch")
        for field in ("package_id", "execution_id"):
            if raw_data.get(field) != identities[field]:
                structural.append(f"raw VPD runtime {field} mismatch")
        if raw_data.get("simulation_started") is not sim_started:
            structural.append("raw VPD simulation_started mismatch")
        waves = raw_data.get("waveforms") if isinstance(raw_data.get("waveforms"), list) else []
        if sim_started and not waves:
            structural.append("started simulation lacks authoritative raw VPD")
        if raw_data.get("no_size_limit") is not True or raw_data.get("all_matching_collected") is not True:
            structural.append("raw VPD receipt weakens unbounded exact-set collection")
        if raw_data.get("pass") is not True or raw_data.get("errors") != []:
            structural.append("raw VPD runtime receipt did not pass")
        for wave in waves:
            source = wave.get("source_path") if isinstance(wave, dict) else None
            if not isinstance(source, str):
                structural.append("raw VPD source path is absent")
                continue
            full_source = f"{attempt_root}/{source}"
            if full_source not in allowlist:
                structural.append(f"raw VPD absent from return allowlist: {full_source}")
                continue
            try:
                path = resolve_asset(asset_root, "raw VPD", full_source)
                size, digest = hash_file(path)
                if size != wave.get("bytes") or digest != wave.get("sha256"):
                    structural.append(f"raw VPD identity mismatch: {full_source}")
            except (OSError, PortableWaveformError) as error:
                structural.append(f"raw VPD: {type(error).__name__}: {error}")

    direct_valid = False
    direct = receipt.get("portable_vcd")
    if mode == "DIRECT_VCD_AND_QUERY" and sim_started:
        if not isinstance(direct, dict) or direct.get("status") != "AVAILABLE":
            diagnostic.append("direct portable VCD is unavailable")
        else:
            relative = direct.get("path")
            try:
                if not is_under_attempt(relative, attempt_root):
                    structural.append("portable VCD is outside exact attempt")
                path = resolve_asset(asset_root, "portable VCD", relative)
                size, digest = hash_file(path)
                if size != direct.get("bytes") or digest != direct.get("sha256"):
                    structural.append("portable VCD identity mismatch")
                if relative not in allowlist:
                    structural.append("portable VCD is absent from return allowlist")
                catalog = validate_vcd(path)
                if not catalog["pass"]:
                    structural.extend(f"portable VCD: {item}" for item in catalog["errors"])
                else:
                    if direct.get("header_valid") is not True:
                        structural.append("portable VCD header_valid is false")
                    if direct.get("timescale") != catalog.get("timescale"):
                        structural.append("portable VCD timescale receipt mismatch")
                    if direct.get("signal_count") != catalog.get("signal_count"):
                        structural.append("portable VCD signal_count receipt mismatch")
                    catalog_map = {item["path"]: item["width"] for item in catalog["signals"]}
                    missing = [
                        item["candidate_id"]
                        for item in _profile_catalog(profile)
                        if catalog_map.get(item["hierarchical_path"]) != item["width"]
                    ]
                    if missing:
                        diagnostic.append(f"portable VCD required candidate coverage missing: {missing}")
                    expected_complete = "COMPLETE" if receipt.get("exit_kind") == "NATURAL" else "PARTIAL"
                    if direct.get("completeness") != expected_complete:
                        structural.append("portable VCD completeness mismatch")
                    direct_valid = not missing and not any(
                        item.startswith("portable VCD") for item in structural
                    )
            except (OSError, PortableWaveformError) as error:
                structural.append(f"portable VCD: {type(error).__name__}: {error}")

    query_valid = False
    query_identity = receipt.get("signal_query_receipt")
    if sim_started and isinstance(query_identity, dict) and query_identity.get("status") == "AVAILABLE":
        relative = query_identity.get("path")
        try:
            if not is_under_attempt(relative, attempt_root):
                structural.append("signal query receipt is outside exact attempt")
            if relative not in allowlist:
                structural.append("signal query receipt is absent from return allowlist")
            query, query_load_errors = _load_identity_bound_json(
                asset_root, relative, {key: query_identity.get(key) for key in ("path", "bytes", "sha256")}, "signal query receipt"
            )
            structural.extend(query_load_errors)
            if query is not None:
                query_errors = validate_query_receipt(query, profile, identities)
                expected_query_complete = (
                    "COMPLETE" if receipt.get("exit_kind") == "NATURAL" else "PARTIAL"
                )
                if query.get("completeness") != expected_query_complete:
                    query_errors.append("query completeness mismatch")
                source = query.get("capture", {}).get("source_generation_report", {})
                source_relative = source.get("path") if isinstance(source, dict) else None
                try:
                    if not isinstance(source_relative, str) or not is_under_attempt(
                        source_relative, attempt_root
                    ):
                        query_errors.append("query source generation report is outside exact attempt")
                    else:
                        if source_relative not in allowlist:
                            query_errors.append(
                                "query source generation report is absent from return allowlist"
                            )
                        source_path = resolve_asset(
                            asset_root, "query source generation report", source_relative
                        )
                        _, source_sha = hash_file(source_path)
                        if source_sha != source.get("sha256"):
                            query_errors.append("query source generation report identity mismatch")
                        if source_sha != profile["portable_vcd"]["source_bound_scope"][
                            "source_receipt_sha256"
                        ]:
                            query_errors.append("query source generation report/profile scope mismatch")
                except (OSError, PortableWaveformError) as error:
                    query_errors.append(
                        f"query source generation report: {type(error).__name__}: {error}"
                    )
                diagnostic.extend(query_errors)
                query_valid = not query_errors and not any(
                    item.startswith("signal query") for item in structural
                )
        except PortableWaveformError as error:
            structural.append(str(error))
    elif sim_started and mode == "QUERY_ONLY":
        diagnostic.append("query-only mode lacks an available registered signal query receipt")

    if not sim_started:
        diagnostic_complete = True
        expected_status = "NOT_APPLICABLE_SIMULATION_NOT_STARTED"
    elif receipt.get("first_fresh_for_profile") is True:
        diagnostic_complete = direct_valid
        expected_status = "COMPLETE" if diagnostic_complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    else:
        diagnostic_complete = direct_valid or query_valid
        expected_status = "COMPLETE" if diagnostic_complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    if receipt.get("diagnostic_status") != expected_status:
        structural.append(
            f"diagnostic_status mismatch: expected {expected_status} got {receipt.get('diagnostic_status')}"
        )
    if receipt.get("return_must_publish") is not True:
        structural.append("return_must_publish must remain true")
    if receipt.get("no_byte_limit") is not True or receipt.get("no_event_limit") is not True:
        structural.append("runtime receipt introduces a hard byte/event limit")
    if receipt.get("sampling") is not False or receipt.get("truncation") is not False:
        structural.append("runtime receipt permits sampling/truncation")
    contract_valid = not structural
    return {
        "schema": VALIDATION_SCHEMA,
        "kind": "runtime_receipt",
        "contract_valid": contract_valid,
        "diagnostic_complete": diagnostic_complete,
        "pass": contract_valid and diagnostic_complete,
        "errors": structural,
        "diagnostic_findings": diagnostic,
        "return_must_publish": True,
        "claim_boundary": "Portable waveform/query plumbing only; family diagnosis is out of scope.",
    }


def make_runtime_receipt(
    profile: dict[str, Any], request: dict[str, Any], asset_root: Path
) -> dict[str, Any]:
    """Build an identity receipt from exact already-on-disk attempt artifacts."""
    attempt_root = request["attempt_root"]
    def identity(relative: str) -> dict[str, Any]:
        path = resolve_asset(asset_root, "request artifact", relative)
        size, digest = hash_file(path)
        return {"path": relative, "bytes": size, "sha256": digest}

    allowlist = load_json(resolve_asset(asset_root, "return allowlist", request["return_allowlist_path"]))
    argv = load_json(resolve_asset(asset_root, "actual sim argv", request["actual_sim_argv_path"]))
    mode = request["capture_mode"]
    direct: dict[str, Any] = {"status": "NOT_REQUESTED"}
    if mode == "DIRECT_VCD_AND_QUERY":
        vcd_relative = request.get("portable_vcd_path")
        if isinstance(vcd_relative, str):
            try:
                vcd_path = resolve_asset(asset_root, "portable VCD", vcd_relative)
                catalog = validate_vcd(vcd_path)
                size, digest = hash_file(vcd_path)
                direct = {
                    "status": "AVAILABLE" if catalog["pass"] else "FAILED",
                    "path": vcd_relative,
                    "bytes": size,
                    "sha256": digest,
                    "header_valid": catalog["pass"],
                    "timescale": catalog.get("timescale"),
                    "signal_count": catalog.get("signal_count"),
                    "completeness": "COMPLETE" if request["exit_kind"] == "NATURAL" else "PARTIAL",
                }
            except OSError:
                direct = {"status": "FAILED"}
        else:
            direct = {"status": "FAILED"}
    query: dict[str, Any] = {"status": "NOT_REQUESTED"}
    query_relative = request.get("signal_query_receipt_path")
    if isinstance(query_relative, str):
        try:
            query = {"status": "AVAILABLE", **identity(query_relative)}
        except OSError:
            query = {"status": "FAILED"}
    receipt = {
        "schema": RUNTIME_SCHEMA,
        "rule_id": RULE_ID,
        "profile_sha256": hashlib.sha256(pretty_json(profile)).hexdigest(),
        "package_id": request["package_id"],
        "execution_id": request["execution_id"],
        "attempt_id": request["attempt_id"],
        "attempt_root": attempt_root,
        "first_fresh_for_profile": request["first_fresh_for_profile"],
        "capture_mode": mode,
        "simulation_started": request["simulation_started"],
        "exit_kind": request["exit_kind"],
        "actual_sim_argv": argv,
        "dump_tcl": identity(request["dump_tcl_path"]),
        "raw_vpd_runtime_receipt": identity(request["raw_vpd_runtime_receipt_path"]),
        "portable_vcd": direct,
        "signal_query_receipt": query,
        "return_allowlist": allowlist,
        "no_byte_limit": True,
        "no_event_limit": True,
        "sampling": False,
        "truncation": False,
        "diagnostic_status": "NOT_APPLICABLE_SIMULATION_NOT_STARTED"
        if not request["simulation_started"]
        else "COMPLETE",
        "return_must_publish": True,
        "claim_boundary": "Portable waveform/query plumbing only; family diagnosis is out of scope.",
    }
    validation = validate_runtime_receipt(receipt, profile, asset_root)
    if not validation["diagnostic_complete"]:
        receipt["diagnostic_status"] = "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    return receipt


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-profile")
    validate.add_argument("--profile", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    render = commands.add_parser("render-dump-tcl")
    render.add_argument("--profile", type=Path, required=True)
    render.add_argument("--attempt-root", required=True)
    render.add_argument("--sim-time", required=True)
    render.add_argument("--capture-mode", choices=["DIRECT_VCD_AND_QUERY", "QUERY_ONLY"], required=True)
    render.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build-runtime-receipt")
    build.add_argument("--profile", type=Path, required=True)
    build.add_argument("--request", type=Path, required=True)
    build.add_argument("--asset-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    runtime = commands.add_parser("validate-runtime-receipt")
    runtime.add_argument("--profile", type=Path, required=True)
    runtime.add_argument("--receipt", type=Path, required=True)
    runtime.add_argument("--asset-root", type=Path, required=True)
    runtime.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        profile = load_json(args.profile)
        if args.command == "validate-profile":
            errors = validate_profile(profile)
            report = {
                "schema": VALIDATION_SCHEMA,
                "kind": "profile",
                "pass": not errors,
                "errors": errors,
                "claim_boundary": "Profile semantics only; no DUT claim.",
            }
        elif args.command == "render-dump-tcl":
            rendered = render_dump_tcl(profile, args.attempt_root, args.sim_time, args.capture_mode)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
            return 0
        elif args.command == "build-runtime-receipt":
            report = make_runtime_receipt(profile, load_json(args.request), args.asset_root)
        else:
            report = validate_runtime_receipt(load_json(args.receipt), profile, args.asset_root)
        write_json(args.output, report)
        return 0 if report.get("pass", report.get("diagnostic_status") == "COMPLETE") else 1
    except (OSError, KeyError, json.JSONDecodeError, PortableWaveformError) as error:
        report = {
            "schema": VALIDATION_SCHEMA,
            "kind": args.command,
            "pass": False,
            "errors": [f"{type(error).__name__}: {error}"],
            "return_must_publish": True,
        }
        write_json(args.output, report)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
