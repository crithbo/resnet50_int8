#!/usr/bin/env python3
"""Validate the observer-only wide-causal next-fresh package and return gate.

This is a shared infrastructure validator.  It validates package/return evidence
and never interprets family-specific signal values as a DUT verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA = "server-observer-only-wide-causal-contract-v1"
REPORT_SCHEMA = "server-observer-only-wide-causal-validation-v1"
PROFILE = "OBSERVER_ONLY_WIDE_CAUSAL_V1"
ACTIVATION_EPOCH = "observer-only-wide-causal-v1"
SOFT_LIMIT_BYTES = 100_000_000
RULE_IDS = {
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
}
REQUIRED_DUMP_ENV = {
    "DUMP_VCD": "0",
    "DUMP_FSDB": "0",
    "TB_DUMP_FSDB": "0",
}
WAVE_SUFFIXES = (".vpd", ".fsdb", ".vcd", ".fst")
CAUSAL_ROLES = (
    "clock", "reset", "stage", "source", "producer",
    "queue_enqueue", "queue_dequeue", "queue_count", "queue_full", "queue_empty",
    "request", "valid", "ready", "accept", "backpressure",
    "selected_port", "selected_bank", "selected_lane",
    "internal_match", "internal_state", "internal_clear",
    "output", "wdata", "terminal", "finish", "formal_d",
)
BOUNDARY_LAYERS = (
    "FIRST_DIVERGENCE_UPSTREAM_ONE",
    "FIRST_DIVERGENCE_CURRENT",
    "FIRST_DIVERGENCE_DOWNSTREAM_ONE",
    "STATE_HOLD_CLEAR",
)
REQUIRED_EVENT_FIELDS = (
    "record_type", "package_id", "execution_id", "attempt_id", "seq",
    "sim_time", "timescale", "signal_id", "width_bits", "value_4state",
)
TEXT_SUFFIXES = (".sh", ".bash", ".py", ".tcl", ".mk", ".sv", ".svh", ".v", ".vh")
FORBIDDEN_WRITER_PATTERNS = (
    re.compile(r"\$fsdb(?:Dump|AutoSwitchDump)", re.IGNORECASE),
    re.compile(r"\$vcdplus", re.IGNORECASE),
    re.compile(r"\$dump(?:file|vars|all|on|off)\b", re.IGNORECASE),
    re.compile(r"\bdump\s+-file\b", re.IGNORECASE),
    re.compile(r"\b-type\s+(?:VCD|VPD|FSDB)\b", re.IGNORECASE),
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SYMBOL_RE = re.compile(r"^sym_[0-9a-f]{24}$")
POST_SIM_EXEMPTION_SCHEMA = "observer-only-post-sim-helper-exemption-v1"
POST_SIM_CANONICAL_SOURCE = "tools/server_post_sim_return.py"
POST_SIM_HELPER_SUFFIX = "package_tools/server_post_sim_return.py"
POST_SIM_REQUEST_SUFFIX = "contracts/server_post_sim_return_request.json"


class GateError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_post_sim_helper_identity() -> dict[str, Any]:
    path = Path(__file__).resolve().with_name("server_post_sim_return.py")
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise GateError(f"canonical post-sim helper is absent or unsafe: {path}")
    data = path.read_bytes()
    text = data.decode("utf-8", errors="strict").lower()
    return {
        "path": POST_SIM_CANONICAL_SOURCE,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "inert_literal_tokens": sorted(suffix for suffix in WAVE_SUFFIXES if suffix in text),
        "data": data,
    }


def _relative_package_path(member: str) -> str:
    parts = PurePosixPath(member).parts
    return "/".join(parts[1:]) if len(parts) > 1 else member


def validate_post_sim_exemption(
    contract: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    exemption = as_object(
        contract.get("post_sim_historical_compatibility_exemption"),
        "post_sim_historical_compatibility_exemption",
        errors,
    )
    package_members = contract.get("package_members", {})
    helper_member = package_members.get("post_sim_helper")
    request_member = package_members.get("post_sim_request")
    try:
        canonical = canonical_post_sim_helper_identity()
    except (GateError, UnicodeDecodeError) as exc:
        errors.append(str(exc))
        canonical = {"path": POST_SIM_CANONICAL_SOURCE, "bytes": None, "sha256": None, "inert_literal_tokens": [], "data": b""}
    expected = {
        "schema": POST_SIM_EXEMPTION_SCHEMA,
        "canonical_source_path": canonical["path"],
        "canonical_helper_bytes": canonical["bytes"],
        "canonical_helper_sha256": canonical["sha256"],
        "member_path": helper_member,
        "request_member": request_member,
        "inert_literal_tokens": canonical["inert_literal_tokens"],
        "waveform_discovery_disposition": "OMITTED_OR_NULL_ONLY",
    }
    for key, value in expected.items():
        if exemption.get(key) != value:
            errors.append(f"post-sim exemption {key} must be exact canonical value {value!r}")
    if not isinstance(helper_member, str) or _relative_package_path(helper_member) != POST_SIM_HELPER_SUFFIX:
        errors.append(f"post-sim helper must have exact package-relative path {POST_SIM_HELPER_SUFFIX}")
    if not isinstance(request_member, str) or _relative_package_path(request_member) != POST_SIM_REQUEST_SUFFIX:
        errors.append(f"post-sim request must have exact package-relative path {POST_SIM_REQUEST_SUFFIX}")
    return {**exemption, "canonical_data": canonical["data"]}


def _active_request_wave_errors(request: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(request, dict):
        return ["post-sim request must be a JSON object"]
    if request.get("waveform_discovery") is not None:
        errors.append("post-sim request activates waveform_discovery")
    active_values: list[str] = []
    for entry in request.get("core_entries", []) if isinstance(request.get("core_entries"), list) else []:
        if isinstance(entry, dict):
            active_values.extend(str(entry.get(key, "")) for key in ("source", "archive"))
    for plugin in request.get("plugins", []) if isinstance(request.get("plugins"), list) else []:
        if isinstance(plugin, dict) and isinstance(plugin.get("argv"), list):
            active_values.extend(str(value) for value in plugin["argv"])
    for value in active_values:
        lower = value.lower()
        if (
            any(suffix in lower for suffix in WAVE_SUFFIXES)
            or any(token in lower for token in ("waveform", "vpd", "fsdb", "novas", "verdi"))
            or re.search(r"(?:^|[/\\])(?:wave|dump)[^/\\]*\.tcl$", lower)
        ):
            errors.append(f"post-sim request contains active waveform path/control: {value}")
    return errors


def safe_member_names(zf: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in zf.infolist():
        raw = info.filename
        pure = PurePosixPath(raw)
        if raw.startswith("/") or ".." in pure.parts or "\\" in raw:
            raise GateError(f"unsafe ZIP member: {raw}")
        if raw in seen:
            raise GateError(f"duplicate ZIP member: {raw}")
        seen.add(raw)
        names.append(raw)
    return names


def zip_member_bytes(zf: zipfile.ZipFile, name: str) -> bytes:
    try:
        return zf.read(name)
    except KeyError as exc:
        raise GateError(f"required ZIP member is absent: {name}") from exc


def as_object(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def exact_dump_tokens(argv: Any, label: str, errors: list[str]) -> None:
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        errors.append(f"{label} must be an argv string array")
        return
    for key, expected in REQUIRED_DUMP_ENV.items():
        exact = f"{key}={expected}"
        hits = [item for item in argv if item == exact]
        conflicting = [item for item in argv if item.startswith(f"{key}=") and item != exact]
        if len(hits) != 1:
            errors.append(f"{label} must contain {exact} exactly once")
        if conflicting:
            errors.append(f"{label} contains conflicting {key}: {conflicting}")
    approved_dump_tokens = {f"{key}={value}" for key, value in REQUIRED_DUMP_ENV.items()}
    for token in argv:
        if token in approved_dump_tokens:
            continue
        lower = token.lower()
        if (
            any(suffix in lower for suffix in WAVE_SUFFIXES)
            or "dump_portable_vcd=" in lower
            or "novas" in lower
            or re.search(r"(?:^|[/\\])(?:wave|dump)[^/\\]*\.tcl$", lower)
        ):
            errors.append(f"{label} contains waveform writer/control token: {token}")


def validate_budget(budget: Any, errors: list[str]) -> dict[str, Any]:
    budget = as_object(budget, "budget", errors)
    if budget.get("observer_evidence_soft_limit_bytes") != SOFT_LIMIT_BYTES:
        errors.append("observer evidence soft limit must be decimal 100000000")
    for key in (
        "observer_evidence_hard_limit_bytes", "formal_return_hard_limit_bytes",
        "event_count_cap", "byte_cap",
    ):
        if key in budget and budget.get(key) is not None:
            errors.append(f"{key} must be null or absent")
    for key in ("sampling", "truncation", "size_based_deletion"):
        if budget.get(key) is not False:
            errors.append(f"{key} must be false")
    return budget


def evaluate_soft_budget(observer_bytes: int, formal_return_bytes: int) -> dict[str, Any]:
    warning = observer_bytes > SOFT_LIMIT_BYTES
    return {
        "observer_evidence_aggregate_bytes": observer_bytes,
        "formal_return_total_bytes": formal_return_bytes,
        "soft_limit_bytes": SOFT_LIMIT_BYTES,
        "soft_limit_exceeded": warning,
        "warning": (
            "OBSERVER_EVIDENCE_SOFT_LIMIT_EXCEEDED_COMPLETE_RETURN_RETAINED" if warning else None
        ),
        "hard_limit_bytes": None,
        "coverage_reduced": False,
    }


def validate_contract(contract: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    contract = as_object(contract, "contract", errors)
    if contract.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if contract.get("profile") != PROFILE:
        errors.append(f"profile must be {PROFILE}")
    if contract.get("activation_epoch") != ACTIVATION_EPOCH:
        errors.append(f"activation_epoch must be {ACTIVATION_EPOCH}")
    rule_ids = contract.get("rule_ids")
    if not isinstance(rule_ids, list) or not RULE_IDS.issubset(set(rule_ids)):
        errors.append("contract must reuse both source-bound and always-on rule IDs")

    package_id = contract.get("package_id")
    family = contract.get("family")
    if not isinstance(package_id, str) or not package_id:
        errors.append("package_id is required")
    if not isinstance(family, str) or not family:
        errors.append("family is required")

    execution = as_object(contract.get("execution"), "execution", errors)
    exact_dump_tokens(execution.get("compile_argv"), "execution.compile_argv", errors)
    exact_dump_tokens(execution.get("sim_argv"), "execution.sim_argv", errors)
    if execution.get("runtime_supervision") != "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT":
        errors.append("runtime supervision must preserve process-tree reap and sim-time heartbeat")
    if execution.get("repeat_safe_exact_owned_reset") is not True:
        errors.append("repeat-safe exact-owned reset is required")
    if execution.get("atomic_unique_return") is not True:
        errors.append("atomic unique return publication is required")
    if execution.get("waveform_writer") is not None:
        errors.append("waveform_writer must be null")

    validate_budget(contract.get("budget"), errors)

    signals = contract.get("signals")
    signal_by_id: dict[str, dict[str, Any]] = {}
    if not isinstance(signals, list) or not signals:
        errors.append("signals must be a non-empty array")
        signals = []
    for number, item in enumerate(signals):
        if not isinstance(item, dict):
            errors.append(f"signals[{number}] must be an object")
            continue
        sid = item.get("signal_id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"signals[{number}].signal_id is required")
            continue
        if sid in signal_by_id:
            errors.append(f"duplicate signal_id: {sid}")
        signal_by_id[sid] = item
        if not SYMBOL_RE.fullmatch(str(item.get("symbol_id", ""))):
            errors.append(f"{sid}: invalid source-bound symbol_id")
        for field in ("exact_hierarchy", "target_module", "source_path"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"{sid}: {field} is required")
        for field in ("source_sha256", "declaration_span_sha256"):
            if not SHA_RE.fullmatch(str(item.get(field, ""))):
                errors.append(f"{sid}: invalid {field}")
        if not isinstance(item.get("width_bits"), int) or item.get("width_bits", 0) < 1:
            errors.append(f"{sid}: width_bits must be positive")
        if item.get("source_binding") != "ACTUAL_SOURCE_NET":
            errors.append(f"{sid}: source_binding must be ACTUAL_SOURCE_NET")
        if item.get("derived_expected_equation") is not False:
            errors.append(f"{sid}: derived expected equation cannot replace an actual net")
        if item.get("observer_drives_dut") is not False:
            errors.append(f"{sid}: observer must not drive DUT")
        roles = item.get("roles")
        if not isinstance(roles, list) or not roles or any(role not in CAUSAL_ROLES for role in roles):
            errors.append(f"{sid}: roles must be non-empty known causal roles")
    for sid, item in signal_by_id.items():
        owner_clock = item.get("owner_clock_signal_id")
        owner_reset = item.get("owner_reset_signal_id")
        if owner_clock not in signal_by_id or "clock" not in signal_by_id[owner_clock].get("roles", []):
            errors.append(f"{sid}: owner clock does not resolve to an actual clock signal")
        if owner_reset not in signal_by_id or "reset" not in signal_by_id[owner_reset].get("roles", []):
            errors.append(f"{sid}: owner reset does not resolve to an actual reset signal")

    role_coverage = contract.get("role_coverage")
    seen_roles: set[str] = set()
    if not isinstance(role_coverage, list):
        errors.append("role_coverage must be an array")
        role_coverage = []
    for item in role_coverage:
        if not isinstance(item, dict):
            errors.append("role_coverage entry must be an object")
            continue
        role = item.get("role")
        if role not in CAUSAL_ROLES:
            errors.append(f"unknown role coverage: {role}")
            continue
        if role in seen_roles:
            errors.append(f"duplicate role coverage: {role}")
        seen_roles.add(role)
        disposition = item.get("disposition")
        ids = item.get("signal_ids")
        if disposition == "covered":
            if not isinstance(ids, list) or not ids:
                errors.append(f"{role}: covered role needs signal_ids")
            else:
                for sid in ids:
                    if sid not in signal_by_id or role not in signal_by_id[sid].get("roles", []):
                        errors.append(f"{role}: signal {sid} does not bind this role")
        elif disposition == "not_applicable":
            proof = item.get("proof")
            if not isinstance(proof, dict):
                errors.append(f"{role}: not_applicable needs exact machine proof")
            else:
                if proof.get("machine_check_exit") != 0:
                    errors.append(f"{role}: N/A machine proof did not pass")
                if not SHA_RE.fullmatch(str(proof.get("sha256", ""))):
                    errors.append(f"{role}: N/A proof SHA is invalid")
                if not proof.get("path") or not proof.get("reason"):
                    errors.append(f"{role}: N/A proof path/reason is required")
        else:
            errors.append(f"{role}: disposition must be covered or not_applicable")
    missing_roles = sorted(set(CAUSAL_ROLES) - seen_roles)
    if missing_roles:
        errors.append(f"missing causal role coverage: {missing_roles}")

    observations = contract.get("boundary_observations")
    observation_by_id: dict[str, dict[str, Any]] = {}
    layers: set[str] = set()
    if not isinstance(observations, list) or not observations:
        errors.append("boundary_observations must be non-empty")
        observations = []
    for item in observations:
        if not isinstance(item, dict):
            errors.append("boundary observation must be an object")
            continue
        oid = item.get("observation_id")
        if not isinstance(oid, str) or not oid or oid in observation_by_id:
            errors.append(f"invalid or duplicate observation_id: {oid}")
            continue
        observation_by_id[oid] = item
        layer = item.get("layer")
        if layer not in BOUNDARY_LAYERS:
            errors.append(f"{oid}: invalid boundary layer")
        else:
            layers.add(layer)
        ids = item.get("signal_ids")
        if not isinstance(ids, list) or not ids or any(sid not in signal_by_id for sid in ids):
            errors.append(f"{oid}: signal_ids must resolve to actual catalog signals")
    if layers != set(BOUNDARY_LAYERS):
        errors.append(f"boundary layers must cover all required layers: {sorted(set(BOUNDARY_LAYERS)-layers)}")

    candidates = contract.get("candidates")
    candidate_ids: list[str] = []
    signatures: dict[str, tuple[Any, ...]] = {}
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must contain every open candidate")
        candidates = []
    ordered_observations = sorted(observation_by_id)
    for item in candidates:
        if not isinstance(item, dict):
            errors.append("candidate must be an object")
            continue
        cid = item.get("candidate_id")
        if not isinstance(cid, str) or not cid or cid in candidate_ids:
            errors.append(f"invalid or duplicate candidate_id: {cid}")
            continue
        candidate_ids.append(cid)
        signature = item.get("signature")
        if not isinstance(signature, dict) or set(signature) != set(ordered_observations):
            errors.append(f"{cid}: signature must cover every boundary observation")
            continue
        signatures[cid] = tuple(signature[oid] for oid in ordered_observations)
    for left_index, left in enumerate(candidate_ids):
        for right in candidate_ids[left_index + 1:]:
            if left in signatures and right in signatures and signatures[left] == signatures[right]:
                errors.append(f"candidate pair is not distinguishable: {left}, {right}")
    if contract.get("all_coobservable_candidates_aggregated") is not True:
        errors.append("all co-observable candidates must be aggregated in one round")

    events = as_object(contract.get("event_recording"), "event_recording", errors)
    if events.get("format") not in ("JSONL", "TSV"):
        errors.append("event format must be JSONL or TSV")
    if events.get("fields") != list(REQUIRED_EVENT_FIELDS):
        errors.append("event fields must preserve exact identity/time/seq/width/4-state value")
    for key in ("ordered_transitions", "end_state_required", "periodic_sim_time_heartbeat", "partial_exit_live_records"):
        if events.get(key) is not True:
            errors.append(f"event_recording.{key} must be true")
    for key in ("sampling", "truncation"):
        if events.get(key) is not False:
            errors.append(f"event_recording.{key} must be false")
    for key in ("event_cap", "byte_cap"):
        if events.get(key) is not None:
            errors.append(f"event_recording.{key} must be null")

    members = as_object(contract.get("return_members"), "return_members", errors)
    required_member_keys = (
        "actual_argv", "sim_exit", "process_tree", "sim_time_heartbeat",
        "signal_catalog", "chunk_index", "decision", "return_manifest",
    )
    for key in required_member_keys:
        if not isinstance(members.get(key), str) or not members.get(key):
            errors.append(f"return_members.{key} is required")
    if not isinstance(members.get("chunk_prefix"), str) or not members.get("chunk_prefix"):
        errors.append("return_members.chunk_prefix is required")
    core = members.get("compile_core_when_not_started")
    if not isinstance(core, list) or not core:
        errors.append("compile-not-started core member list is required")

    validate_post_sim_exemption(contract, errors)

    return {
        "schema": REPORT_SCHEMA,
        "phase": "contract",
        "package_id": package_id,
        "family": family,
        "causal_role_count": len(seen_roles),
        "signal_count": len(signal_by_id),
        "candidate_count": len(candidate_ids),
        "pairwise_candidate_count": len(candidate_ids) * (len(candidate_ids) - 1) // 2,
        "errors": errors,
        "warnings": warnings,
        "pass": not errors,
        "claim_boundary": "Local observer-only package/return evidence integrity; no family signal interpretation, production execution, natural terminal, formal D, E3, E4 or E5 claim.",
    }


def _scan_text_member(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(TEXT_SUFFIXES) or PurePosixPath(lower).name in {
        "makefile", "test_package_manifest.json", "return_allowlist.json",
    }


def validate_final_zip(zip_path: Path, contract: Any) -> dict[str, Any]:
    base = validate_contract(contract)
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    contract_sha = sha256_bytes(canonical_bytes(contract))
    exemption = validate_post_sim_exemption(contract, errors)
    with zipfile.ZipFile(zip_path) as zf:
        names = safe_member_names(zf)
        bad_wave = [name for name in names if name.lower().endswith(WAVE_SUFFIXES)]
        if bad_wave:
            errors.append(f"waveform members are forbidden: {bad_wave}")
        bad_pli = [name for name in names if "novas" in name.lower() or PurePosixPath(name).name.lower() in {"pli.a", "novas.tab"}]
        if bad_pli:
            errors.append(f"waveform PLI members are forbidden: {bad_pli}")
        package_members = contract.get("package_members", {})
        for key in (
            "runner", "manifest", "return_allowlist", "contract", "observer", "parser",
            "runtime_supervisor", "post_sim_helper", "post_sim_request",
        ):
            member = package_members.get(key)
            if not isinstance(member, str) or member not in names:
                errors.append(f"package member missing for {key}: {member}")
        contract_name = package_members.get("contract")
        if isinstance(contract_name, str) and contract_name in names:
            if zip_member_bytes(zf, contract_name) != canonical_bytes(contract):
                errors.append("embedded observer-only contract is not byte-exact canonical input")
        manifest_name = package_members.get("manifest")
        if isinstance(manifest_name, str) and manifest_name in names:
            try:
                manifest = json.loads(zip_member_bytes(zf, manifest_name).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid package manifest: {exc}")
            else:
                if manifest.get("observer_only_profile") != PROFILE:
                    errors.append("package manifest does not bind observer-only profile")
                if manifest.get("observer_only_contract_sha256") != contract_sha:
                    errors.append("package manifest does not bind exact observer-only contract SHA")
        runner_name = package_members.get("runner")
        runner_text = ""
        if isinstance(runner_name, str) and runner_name in names:
            runner_text = zip_member_bytes(zf, runner_name).decode("utf-8", errors="replace")
            for key, value in REQUIRED_DUMP_ENV.items():
                if f"{key}={value}" not in runner_text:
                    errors.append(f"exact runner does not bind {key}={value}")
                if re.search(rf"\b{re.escape(key)}=(?!{value}\b)\S+", runner_text):
                    errors.append(f"exact runner contains conflicting {key}")
            if "server_observer_runtime_supervision.py" not in runner_text:
                errors.append("exact runner does not invoke observer runtime supervision")
            helper_relative = _relative_package_path(str(package_members.get("post_sim_helper", "")))
            request_relative = _relative_package_path(str(package_members.get("post_sim_request", "")))
            if helper_relative not in runner_text or request_relative not in runner_text:
                errors.append("exact runner does not invoke the exact post-sim helper/request pair")
            if "finalize" not in runner_text or "--request" not in runner_text:
                errors.append("exact runner lacks post-sim finalize --request handoff")

        helper_name = package_members.get("post_sim_helper")
        helper_exempt = False
        if isinstance(helper_name, str) and helper_name in names:
            helper_data = zip_member_bytes(zf, helper_name)
            if helper_data != exemption.get("canonical_data"):
                errors.append("packaged post-sim helper is not byte-exact canonical helper")
            else:
                helper_exempt = True
        request_name = package_members.get("post_sim_request")
        if isinstance(request_name, str) and request_name in names:
            try:
                post_sim_request = json.loads(zip_member_bytes(zf, request_name).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid post-sim request JSON: {exc}")
            else:
                errors.extend(_active_request_wave_errors(post_sim_request))
                if post_sim_request.get("package_id") != contract.get("package_id"):
                    errors.append("post-sim request package_id does not match observer contract")
        for name in names:
            if not _scan_text_member(name):
                continue
            data = zip_member_bytes(zf, name)
            if len(data) > 8_000_000:
                warnings.append(f"text member scan skipped beyond 8MB record-only: {name}")
                continue
            text = data.decode("utf-8", errors="replace")
            if any(suffix in text.lower() for suffix in WAVE_SUFFIXES) and not (helper_exempt and name == helper_name):
                errors.append(f"waveform suffix appears in executable/manifest surface: {name}")
            for pattern in FORBIDDEN_WRITER_PATTERNS:
                if pattern.search(text):
                    errors.append(f"wave dump writer/control appears in {name}: {pattern.pattern}")
        allow_name = package_members.get("return_allowlist")
        if isinstance(allow_name, str) and allow_name in names:
            allow = json.loads(zip_member_bytes(zf, allow_name).decode("utf-8"))
            allow_blob = json.dumps(allow, sort_keys=True).lower()
            if any(suffix in allow_blob for suffix in WAVE_SUFFIXES):
                errors.append("return allowlist contains a waveform member")
            for key, member in contract.get("return_members", {}).items():
                if key in ("chunk_prefix", "compile_core_when_not_started"):
                    continue
                if isinstance(member, str) and member.lower() not in allow_blob:
                    errors.append(f"return allowlist does not include required observer member: {member}")
            prefix = contract.get("return_members", {}).get("chunk_prefix")
            if isinstance(prefix, str) and prefix.lower() not in allow_blob:
                errors.append("return allowlist does not include observer chunk prefix")
            for member in contract.get("return_members", {}).get("compile_core_when_not_started", []):
                if isinstance(member, str) and member.lower() not in allow_blob:
                    errors.append(f"return allowlist does not include compile-core member: {member}")

    return {
        **base,
        "phase": "final_zip",
        "zip": {"path": str(zip_path), "bytes": zip_path.stat().st_size, "sha256": sha256_bytes(zip_path.read_bytes())},
        "contract_sha256": contract_sha,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "pass": not errors,
    }


def _read_return_json(zf: zipfile.ZipFile, name: str, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(zip_member_bytes(zf, name).decode("utf-8"))
    except (GateError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid required return JSON {name}: {exc}")
        return {}


def _validate_event_rows(
    zf: zipfile.ZipFile,
    chunk_entries: list[dict[str, Any]],
    signal_widths: dict[str, int],
    identity: tuple[str, str, str],
    errors: list[str],
) -> dict[str, Any]:
    expected_seq = 0
    last_time = -1
    timescale: str | None = None
    last_values: dict[str, str] = {}
    event_count = heartbeat_count = partial_exit_count = 0
    observer_bytes = 0
    for entry in chunk_entries:
        path = entry.get("path")
        if not isinstance(path, str):
            errors.append("chunk index path is invalid")
            continue
        try:
            raw = zip_member_bytes(zf, path)
        except GateError as exc:
            errors.append(str(exc))
            continue
        observer_bytes += len(raw)
        if entry.get("bytes") != len(raw) or entry.get("sha256") != sha256_bytes(raw):
            errors.append(f"chunk identity mismatch: {path}")
        if entry.get("sampling") is not False or entry.get("truncated") is not False:
            errors.append(f"chunk sampling/truncation is forbidden: {path}")
        try:
            decoded = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            errors.append(f"{path}: observer chunk is not strict UTF-8: {exc}")
            continue
        for line_number, line in enumerate(decoded.splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSONL: {exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"{path}:{line_number}: event row must be an object")
                continue
            for field in REQUIRED_EVENT_FIELDS:
                if field not in row:
                    errors.append(f"{path}:{line_number}: missing field {field}")
            if (row.get("package_id"), row.get("execution_id"), row.get("attempt_id")) != identity:
                errors.append(f"{path}:{line_number}: execution identity drift")
            seq = row.get("seq")
            if seq != expected_seq:
                errors.append(f"{path}:{line_number}: seq {seq} expected {expected_seq}")
            if isinstance(seq, int):
                expected_seq = seq + 1
            sim_time = row.get("sim_time")
            if not isinstance(sim_time, int) or sim_time < 0 or sim_time < last_time:
                errors.append(f"{path}:{line_number}: invalid/nonordered sim_time")
            elif isinstance(sim_time, int):
                last_time = sim_time
            if not isinstance(row.get("timescale"), str) or not row.get("timescale"):
                errors.append(f"{path}:{line_number}: timescale is required")
            elif timescale is None:
                timescale = row["timescale"]
            elif timescale != row["timescale"]:
                errors.append(f"{path}:{line_number}: timescale changed")
            record_type = row.get("record_type")
            if record_type == "EVENT":
                event_count += 1
                sid = row.get("signal_id")
                width = row.get("width_bits")
                value = row.get("value_4state")
                if sid not in signal_widths:
                    errors.append(f"{path}:{line_number}: unknown signal_id {sid}")
                elif width != signal_widths[sid]:
                    errors.append(f"{path}:{line_number}: width mismatch for {sid}")
                if not isinstance(value, str) or len(value) != width or not re.fullmatch(r"[01XxZz]+", value or ""):
                    errors.append(f"{path}:{line_number}: invalid 4-state value")
                elif isinstance(sid, str):
                    last_values[sid] = value.upper()
            elif record_type == "HEARTBEAT":
                heartbeat_count += 1
            elif record_type == "PARTIAL_EXIT":
                partial_exit_count += 1
            else:
                errors.append(f"{path}:{line_number}: unknown record_type {record_type}")
    return {
        "event_count": event_count,
        "heartbeat_count": heartbeat_count,
        "partial_exit_count": partial_exit_count,
        "last_values": last_values,
        "last_seq": expected_seq - 1,
        "observer_chunk_bytes": observer_bytes,
        "timescale": timescale,
    }


def validate_return(zip_path: Path, contract: Any) -> dict[str, Any]:
    base = validate_contract(contract)
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    members = contract.get("return_members", {})
    with zipfile.ZipFile(zip_path) as zf:
        names = safe_member_names(zf)
        bad_wave = [name for name in names if name.lower().endswith(WAVE_SUFFIXES)]
        if bad_wave:
            errors.append(f"formal return contains forbidden waveform members: {bad_wave}")
        bad_pli = [name for name in names if "novas" in name.lower() or PurePosixPath(name).name.lower() in {"pli.a", "novas.tab"}]
        if bad_pli:
            errors.append(f"formal return contains forbidden waveform PLI members: {bad_pli}")
        sim_exit = _read_return_json(zf, members.get("sim_exit", ""), errors)
        actual_argv = _read_return_json(zf, members.get("actual_argv", ""), errors)
        exact_dump_tokens(actual_argv.get("compile_argv"), "actual compile argv", errors)
        exact_dump_tokens(actual_argv.get("sim_argv"), "actual sim argv", errors)
        simulation_started = sim_exit.get("simulation_started") is True
        return_manifest = _read_return_json(zf, members.get("return_manifest", ""), errors)
        package_id = str(contract.get("package_id"))
        execution_id = actual_argv.get("execution_id")
        attempt_id = actual_argv.get("attempt_id")
        identity = (package_id, execution_id, attempt_id)
        if not all(isinstance(item, str) and item for item in identity):
            errors.append("actual argv receipt lacks exact package/execution/attempt identity")
        for label, receipt in (
            ("actual argv", actual_argv), ("sim exit", sim_exit), ("return manifest", return_manifest),
        ):
            observed = (receipt.get("package_id"), receipt.get("execution_id"), receipt.get("attempt_id"))
            if observed != identity:
                errors.append(f"{label} identity does not match actual attempt")
        observer_bytes = 0
        event_summary: dict[str, Any] = {}
        if simulation_started:
            process_tree = _read_return_json(zf, members.get("process_tree", ""), errors)
            heartbeat_receipt = _read_return_json(zf, members.get("sim_time_heartbeat", ""), errors)
            for label, receipt in (("process tree", process_tree), ("simulation-time heartbeat", heartbeat_receipt)):
                observed = (receipt.get("package_id"), receipt.get("execution_id"), receipt.get("attempt_id"))
                if observed != identity:
                    errors.append(f"{label} identity does not match actual attempt")
            if process_tree.get("process_tree_reaped") is not True:
                errors.append("complete simulator process tree was not reaped")
            if process_tree.get("owned_pids_remaining") not in ([], None):
                errors.append("owned simulator descendants remain")
            if heartbeat_receipt.get("simulation_time_progress_observed") is not True:
                errors.append("simulation_started return lacks same-attempt simulation-time progress")
            catalog_name = members.get("signal_catalog", "")
            index_name = members.get("chunk_index", "")
            decision_name = members.get("decision", "")
            catalog = _read_return_json(zf, catalog_name, errors)
            index = _read_return_json(zf, index_name, errors)
            decision = _read_return_json(zf, decision_name, errors)
            for name in (catalog_name, index_name, decision_name):
                if isinstance(name, str) and name in names:
                    observer_bytes += zf.getinfo(name).file_size
            expected_catalog = contract.get("signals", [])
            expected_signals = {item["signal_id"]: item["width_bits"] for item in expected_catalog if isinstance(item, dict) and "signal_id" in item and "width_bits" in item}
            returned_signals = {
                item.get("signal_id"): item.get("width_bits")
                for item in catalog.get("signals", []) if isinstance(item, dict)
            }
            if returned_signals != expected_signals:
                errors.append("returned signal catalog identity/width coverage is incomplete")
            if catalog.get("signals") != expected_catalog:
                errors.append("returned signal catalog is not the exact source-bound contract catalog")
            if catalog.get("source_bound") is not True or catalog.get("derived_expected_equation") is not False:
                errors.append("returned catalog is not source-bound actual-signal evidence")
            chunks = index.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                errors.append("simulation-started return lacks observer chunks")
                chunks = []
            prefix = members.get("chunk_prefix", "")
            if any(not str(entry.get("path", "")).startswith(prefix) for entry in chunks if isinstance(entry, dict)):
                errors.append("chunk path is outside declared observer prefix")
            indexed_paths = {entry.get("path") for entry in chunks if isinstance(entry, dict)}
            actual_chunk_paths = {name for name in names if isinstance(prefix, str) and name.startswith(prefix)}
            if indexed_paths != actual_chunk_paths:
                errors.append("observer chunk index is not the exact returned chunk set")
            candidate_ids = sorted(item.get("candidate_id") for item in contract.get("candidates", []) if isinstance(item, dict))
            matrix_sha256 = sha256_bytes(canonical_bytes({
                "boundary_observations": contract.get("boundary_observations", []),
                "candidates": contract.get("candidates", []),
            }))
            if sorted(index.get("candidate_ids", [])) != candidate_ids:
                errors.append("observer index does not cover every open candidate")
            if index.get("candidate_boundary_matrix_sha256") != matrix_sha256:
                errors.append("observer index does not bind the exact candidate-by-boundary matrix")
            if index.get("event_count_cap") is not None or index.get("byte_cap") is not None:
                errors.append("observer index contains a hard event/byte cap")
            if index.get("sampling") is not False or index.get("truncated") is not False:
                errors.append("observer index sampled or truncated evidence")
            if (index.get("package_id"), index.get("execution_id"), index.get("attempt_id")) != identity:
                errors.append("observer index identity does not match actual attempt")
            event_summary = _validate_event_rows(zf, chunks, expected_signals, identity, errors)
            observer_bytes += event_summary.get("observer_chunk_bytes", 0)
            if event_summary.get("heartbeat_count", 0) < 1:
                errors.append("observer event stream lacks periodic simulation-time heartbeat")
            if set(event_summary.get("last_values", {})) != set(expected_signals):
                errors.append("observer event stream lacks exact end-state for required signals")
            if index.get("end_state") != event_summary.get("last_values"):
                errors.append("observer index end-state does not match ordered transitions")
            partial_exit_required = (
                sim_exit.get("signal") in ("HUP", "INT", "TERM")
                or sim_exit.get("timed_out") is True
                or (isinstance(sim_exit.get("exit_code"), int) and sim_exit.get("exit_code") != 0)
            )
            if partial_exit_required and event_summary.get("partial_exit_count", 0) < 1:
                errors.append("timeout/signal/nonzero return lacks a live partial-exit observer record")
            if decision.get("candidate_ids_covered") != candidate_ids:
                errors.append("decision receipt does not explicitly cover every candidate")
            if decision.get("candidate_boundary_matrix_sha256") != matrix_sha256:
                errors.append("decision receipt does not bind the exact candidate-by-boundary matrix")
            if (decision.get("package_id"), decision.get("execution_id"), decision.get("attempt_id")) != identity:
                errors.append("decision receipt identity does not match actual attempt")
            if decision.get("diagnostic_evidence_complete") is not True:
                errors.append("simulation-started observer decision is incomplete")
        else:
            for name in members.get("compile_core_when_not_started", []):
                if name not in names:
                    errors.append(f"compile-not-started core member missing: {name}")

        manifest_members = return_manifest.get("members")
        if not isinstance(manifest_members, list) or not all(isinstance(item, str) for item in manifest_members):
            errors.append("return manifest must enumerate exact returned members")
            manifest_members = []
        manifest_set = set(manifest_members)
        if manifest_set != set(names) - {members.get("return_manifest", "")}:
            errors.append("return manifest exact member set does not match ZIP payload")
        if any(str(name).lower().endswith(WAVE_SUFFIXES) for name in manifest_members):
            errors.append("return manifest lists a forbidden waveform member")
        if simulation_started:
            required_observer_members = {
                members.get("actual_argv"), members.get("sim_exit"), members.get("process_tree"),
                members.get("sim_time_heartbeat"), members.get("signal_catalog"),
                members.get("chunk_index"), members.get("decision"),
            }
            if not required_observer_members.issubset(manifest_set):
                errors.append("return manifest omits required observer/core evidence")
            prefix = members.get("chunk_prefix", "")
            if not any(isinstance(name, str) and name.startswith(prefix) for name in manifest_members):
                errors.append("return manifest omits observer chunks")

        total_uncompressed = sum(info.file_size for info in zf.infolist())
        budget = evaluate_soft_budget(observer_bytes, total_uncompressed)
        if budget["warning"]:
            warnings.append(budget["warning"])
        return {
            **base,
            "phase": "formal_return",
            "zip": {"path": str(zip_path), "bytes": zip_path.stat().st_size, "sha256": sha256_bytes(zip_path.read_bytes())},
            "simulation_started": simulation_started,
            "event_summary": event_summary,
            "budget": budget,
            "errors": sorted(set(errors)),
            "warnings": sorted(set(warnings)),
            "diagnostic_status": "COMPLETE" if not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "pass": not errors,
        }


def write_report(report: dict[str, Any], output: Path | None) -> None:
    payload = canonical_bytes(report)
    if output is None:
        sys.stdout.buffer.write(payload)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    contract_cmd = sub.add_parser("validate-contract")
    contract_cmd.add_argument("--contract", type=Path, required=True)
    contract_cmd.add_argument("--output", type=Path)
    zip_cmd = sub.add_parser("validate-final-zip")
    zip_cmd.add_argument("--zip", type=Path, required=True)
    zip_cmd.add_argument("--contract", type=Path, required=True)
    zip_cmd.add_argument("--output", type=Path)
    return_cmd = sub.add_parser("validate-return")
    return_cmd.add_argument("--zip", type=Path, required=True)
    return_cmd.add_argument("--contract", type=Path, required=True)
    return_cmd.add_argument("--output", type=Path)
    args = parser.parse_args()
    contract = load_json(args.contract)
    if args.command == "validate-contract":
        report = validate_contract(contract)
    elif args.command == "validate-final-zip":
        report = validate_final_zip(args.zip, contract)
    else:
        report = validate_return(args.zip, contract)
    write_report(report, args.output)
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
