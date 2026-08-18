#!/usr/bin/env python3
"""Validate cross-member and temporal release consistency for a final ZIP.

The gate is deliberately family-agnostic.  It does not build a package or run
the simulator.  It closes invariants that cannot be proven by validating each
JSON member in isolation: terminal manifest state, selected/absolute budget
identity, producer-before-publication closure, and qualified progress events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "server-release-consistency-v1"
READY = "PACKAGE_READY_NOT_RUN"
ABSOLUTE_MAXIMUM_WALL_SECONDS = 86400
ALLOWED_EVENT_KINDS = {
    "QUALIFIED_HANDSHAKE",
    "RISING_EDGE_TRANSITION",
    "MONOTONIC_VALUE_DELTA",
    "TERMINAL_TRANSITION",
}
PHASES = [
    "FINALIZATION_GUARD_COMPLETE",
    "RETURN_PUBLISH",
    "DURABLE_RETURN_RECEIPT",
    "POST_DURABLE_CLEANUP_RECEIPT",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return value


def _json_pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise KeyError(pointer)
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[token]
        elif isinstance(current, list):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current


def _safe_member(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("member path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"unsafe member path: {value}")
    return path.as_posix()


def _resolve_workspace(workspace: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("workspace path must be a non-empty string")
    candidate = (workspace / value).resolve()
    candidate.relative_to(workspace.resolve())
    return candidate


def _safe_zip_members(archive: zipfile.ZipFile, expected_root: str) -> dict[str, bytes]:
    if archive.testzip() is not None:
        raise ValueError("final ZIP CRC check failed")
    result: dict[str, bytes] = {}
    prefix = expected_root.rstrip("/") + "/"
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"unsafe final ZIP member: {name}")
        if info.is_dir():
            continue
        if not name.startswith(prefix):
            raise ValueError(f"final ZIP member escapes exact root {expected_root}: {name}")
        relative = name[len(prefix):]
        if not relative or relative in result:
            raise ValueError(f"duplicate or empty final ZIP member: {relative}")
        result[relative] = archive.read(info)
    if not result:
        raise ValueError("final ZIP contains no payload members")
    return result


def _member_json(members: dict[str, bytes], member: Any) -> dict[str, Any]:
    name = _safe_member(member)
    if name not in members:
        raise ValueError(f"required JSON member is absent: {name}")
    return _load_json_bytes(members[name], name)


def _identity_checks(
    contract: dict[str, Any], members: dict[str, bytes], errors: list[str]
) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    rows = contract.get("cross_member_identities")
    if not isinstance(rows, list):
        errors.append("cross_member_identities must be an array")
        return controls
    by_id = {
        row.get("identity_id"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("identity_id"), str)
    }
    required = {"selected_wall_seconds", "absolute_maximum_wall_seconds"}
    if set(by_id) != required:
        errors.append(
            "cross-member identities must contain exactly selected_wall_seconds "
            "and absolute_maximum_wall_seconds"
        )
    cache: dict[str, dict[str, Any]] = {}
    for identity_id in sorted(required):
        row = by_id.get(identity_id, {})
        endpoints = row.get("endpoints") if isinstance(row, dict) else None
        values: list[Any] = []
        endpoint_receipts: list[dict[str, Any]] = []
        if not isinstance(endpoints, list) or len(endpoints) < 2:
            errors.append(f"{identity_id}: at least two endpoints are required")
            continue
        for endpoint in endpoints:
            try:
                member = _safe_member(endpoint.get("member"))
                pointer = endpoint.get("pointer")
                document = cache.setdefault(member, _member_json(members, member))
                value = _json_pointer(document, pointer)
                values.append(value)
                endpoint_receipts.append({"member": member, "pointer": pointer, "value": value})
            except (AttributeError, KeyError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{identity_id}: endpoint resolution failed: {exc}")
        if values and any(value != values[0] for value in values[1:]):
            errors.append(f"{identity_id}: cross-member values differ: {values}")
        expected = row.get("expected_value") if isinstance(row, dict) else None
        if identity_id == "absolute_maximum_wall_seconds":
            if expected != ABSOLUTE_MAXIMUM_WALL_SECONDS:
                errors.append("absolute maximum expected value must remain 86400")
            if values and values[0] != ABSOLUTE_MAXIMUM_WALL_SECONDS:
                errors.append("absolute maximum cross-member value is not 86400")
        elif expected is not None and values and values[0] != expected:
            errors.append(f"{identity_id}: value differs from declared expected value")
        controls[identity_id] = endpoint_receipts
    return controls


def _manifest_checks(
    contract: dict[str, Any], members: dict[str, bytes], errors: list[str]
) -> dict[str, Any]:
    spec = contract.get("manifest") if isinstance(contract.get("manifest"), dict) else {}
    try:
        manifest = _member_json(members, spec.get("member"))
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return {}
    receipts: dict[str, Any] = {}
    try:
        top = _json_pointer(manifest, spec.get("top_status_pointer"))
    except (KeyError, TypeError) as exc:
        errors.append(f"manifest top status pointer failed: {exc}")
        top = None
    if top != READY or spec.get("top_ready_status") != READY:
        errors.append("manifest top-level status is not PACKAGE_READY_NOT_RUN")
    receipts["top_status"] = top
    statuses = spec.get("release_critical_statuses")
    if not isinstance(statuses, list) or not statuses:
        errors.append("release-critical nested status list is absent")
        return receipts
    pointers = [item.get("pointer") for item in statuses if isinstance(item, dict)]
    required_pointer = "/final_zip_rule_self_audit/status"
    if required_pointer not in pointers:
        errors.append(f"release-critical status list omits {required_pointer}")
    for item in statuses:
        try:
            pointer = item.get("pointer")
            expected = item.get("expected_terminal_status")
            actual = _json_pointer(manifest, pointer)
            receipts[str(pointer)] = actual
            if not isinstance(expected, str) or not expected or actual != expected:
                errors.append(
                    f"release-critical manifest status is not terminal: {pointer}={actual!r}"
                )
            if isinstance(actual, str) and (
                "PENDING" in actual.upper() or "LOCAL_BUILD" in actual.upper()
            ):
                errors.append(f"release-critical manifest status remains pending: {pointer}")
        except (AttributeError, KeyError, TypeError) as exc:
            errors.append(f"release-critical status pointer failed: {exc}")
    return receipts


def _return_phase_checks(
    contract: dict[str, Any], members: dict[str, bytes], errors: list[str]
) -> dict[str, Any]:
    spec = contract.get("return_phase") if isinstance(contract.get("return_phase"), dict) else {}
    controls: dict[str, Any] = {}
    try:
        request = _member_json(members, spec.get("request_member"))
        allowlist = _member_json(members, spec.get("allowlist_member"))
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        return controls
    core_entries = request.get("core_entries")
    if not isinstance(core_entries, list):
        errors.append("post-sim request core_entries is absent")
        return controls
    required_entries = [
        item for item in core_entries
        if isinstance(item, dict) and item.get("required") is True
    ]
    required_archives = {item.get("archive") for item in required_entries}
    try:
        allowlist_required = _json_pointer(allowlist, spec.get("allowlist_required_pointer"))
    except (KeyError, TypeError) as exc:
        errors.append(f"return allowlist pointer failed: {exc}")
        allowlist_required = []
    if not isinstance(allowlist_required, list) or not all(
        isinstance(item, str) for item in allowlist_required
    ):
        errors.append("return allowlist required set is not an array of paths")
        allowlist_required = []
    allowlist_set = set(allowlist_required)
    if not required_archives.issubset(allowlist_set):
        errors.append("required post-sim core archives are absent from return allowlist")

    producers = spec.get("prepublication_producers")
    if not isinstance(producers, list):
        errors.append("prepublication producer closure is absent")
        producers = []
    producer_keys: list[tuple[Any, Any, Any]] = []
    for row in producers:
        if not isinstance(row, dict):
            errors.append("prepublication producer row must be an object")
            continue
        key = (row.get("source_root"), row.get("source"), row.get("archive"))
        producer_keys.append(key)
        try:
            producer_member = _safe_member(row.get("producer_member"))
            producer_bytes = members[producer_member]
        except (KeyError, ValueError) as exc:
            errors.append(f"producer member is absent or unsafe: {exc}")
            continue
        if _sha256(producer_bytes) != row.get("producer_sha256"):
            errors.append(f"producer member SHA differs: {producer_member}")
        literal = row.get("producer_output_literal")
        if not isinstance(literal, str) or not literal or literal.encode("utf-8") not in producer_bytes:
            errors.append(
                f"producer output literal is absent from exact producer: {producer_member}"
            )
    for entry in required_entries:
        key = (entry.get("source_root"), entry.get("source"), entry.get("archive"))
        if producer_keys.count(key) != 1:
            errors.append(f"required return entry lacks exactly one producer closure: {key}")
    if len(set(producer_keys)) != len(producer_keys):
        errors.append("prepublication producer closure contains duplicate entries")

    guard_archive = spec.get("finalization_guard_archive")
    if guard_archive not in required_archives:
        errors.append("finalization guard receipt is not a required prepublication core entry")

    post = spec.get("postpublication_receipts")
    if not isinstance(post, list) or not post:
        errors.append("postpublication external receipt set is absent")
        post = []
    for row in post:
        if not isinstance(row, dict):
            errors.append("postpublication receipt row must be an object")
            continue
        path = row.get("path")
        if row.get("location") != "EXTERNAL_IMMUTABLE_SIDECAR":
            errors.append(f"postpublication receipt is not external immutable sidecar: {path}")
        if path in required_archives or path in allowlist_set:
            errors.append(f"postpublication receipt is impossible inside first return ZIP: {path}")

    try:
        runner_member = _safe_member(spec.get("runner_member"))
        runner = members[runner_member]
    except (KeyError, ValueError) as exc:
        errors.append(f"runner member is absent or unsafe: {exc}")
        return controls
    if _sha256(runner) != spec.get("runner_sha256"):
        errors.append("runner SHA differs in return-phase contract")
    marker_rows = spec.get("ordered_runner_markers")
    positions: list[int] = []
    phases: list[Any] = []
    if not isinstance(marker_rows, list):
        errors.append("ordered runner markers are absent")
        marker_rows = []
    for row in marker_rows:
        phase = row.get("phase") if isinstance(row, dict) else None
        literal = row.get("literal") if isinstance(row, dict) else None
        phases.append(phase)
        if not isinstance(literal, str) or not literal:
            errors.append(f"runner marker literal is absent for phase {phase}")
            positions.append(-1)
            continue
        count = runner.count(literal.encode("utf-8"))
        if count != 1:
            errors.append(f"runner marker must occur exactly once: {phase} count={count}")
        positions.append(runner.find(literal.encode("utf-8")))
    if phases != PHASES:
        errors.append(f"runner phase order declaration differs: {phases}")
    if len(positions) != len(PHASES) or any(item < 0 for item in positions) or positions != sorted(positions):
        errors.append("runner does not prove guard->publish->durable->cleanup temporal order")
    controls.update({
        "required_core_archives": sorted(str(item) for item in required_archives),
        "allowlist_required": sorted(allowlist_set),
        "producer_key_count": len(producer_keys),
        "runner_marker_phases": phases,
        "runner_marker_positions": positions,
    })
    return controls


def _replay_deltas(kind: str, sources: list[Any], qualifiers: list[Any]) -> list[int]:
    result: list[int] = []
    previous: Any = 0
    for index, current in enumerate(sources):
        qualifier = qualifiers[index] if index < len(qualifiers) else 0
        if kind == "QUALIFIED_HANDSHAKE":
            delta = int(current == 1 and qualifier == 1)
        elif kind in {"RISING_EDGE_TRANSITION", "TERMINAL_TRANSITION"}:
            delta = int(current == 1 and previous != 1)
        elif kind == "MONOTONIC_VALUE_DELTA":
            delta = int(index > 0 and current != previous)
        else:
            delta = 0
        result.append(delta)
        previous = current
    return result


def _progress_checks(
    contract: dict[str, Any], members: dict[str, bytes], errors: list[str]
) -> dict[str, Any]:
    spec = contract.get("progress_qualification") if isinstance(contract.get("progress_qualification"), dict) else {}
    try:
        source_member = _safe_member(spec.get("source_member"))
        source = members[source_member]
    except (KeyError, ValueError) as exc:
        errors.append(f"progress source member is absent or unsafe: {exc}")
        return {}
    if _sha256(source) != spec.get("source_sha256"):
        errors.append("progress source SHA differs")
    events = spec.get("events") if isinstance(spec.get("events"), list) else []
    replays = spec.get("held_level_replays") if isinstance(spec.get("held_level_replays"), list) else []
    if spec.get("held_level_replay_required") is not True:
        errors.append("held-level replay is not required")
    event_ids: set[str] = set()
    replay_by_id = {
        row.get("event_id"): row
        for row in replays
        if isinstance(row, dict) and isinstance(row.get("event_id"), str)
    }
    receipts: dict[str, Any] = {}
    for row in events:
        if not isinstance(row, dict):
            errors.append("progress event row must be an object")
            continue
        event_id = row.get("event_id")
        kind = row.get("event_kind")
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            errors.append(f"progress event ID is absent or duplicate: {event_id}")
            continue
        event_ids.add(event_id)
        if kind not in ALLOWED_EVENT_KINDS:
            errors.append(f"{event_id}: raw/unknown level event cannot count as progress")
        start = row.get("source_span_start_byte")
        end = row.get("source_span_end_byte")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 0 <= start < end <= len(source):
            errors.append(f"{event_id}: source span is invalid")
            continue
        span = source[start:end]
        if _sha256(span) != row.get("source_span_sha256"):
            errors.append(f"{event_id}: source span SHA differs")
        required_tokens = [row.get("counter_symbol")]
        for field in ("source_signal_tokens", "qualifier_signal_tokens", "state_memory_tokens"):
            values = row.get(field)
            if isinstance(values, list):
                required_tokens.extend(values)
        for token in required_tokens:
            if not isinstance(token, str) or not token or token.encode("utf-8") not in span:
                errors.append(f"{event_id}: bound source span omits token {token!r}")
        qualifiers = row.get("qualifier_signal_tokens") if isinstance(row.get("qualifier_signal_tokens"), list) else []
        state = row.get("state_memory_tokens") if isinstance(row.get("state_memory_tokens"), list) else []
        if kind == "QUALIFIED_HANDSHAKE" and not qualifiers:
            errors.append(f"{event_id}: handshake progress lacks ready/accept qualifier")
        if kind in {"RISING_EDGE_TRANSITION", "MONOTONIC_VALUE_DELTA", "TERMINAL_TRANSITION"} and not state:
            errors.append(f"{event_id}: transition progress lacks previous-state memory")
        replay = replay_by_id.get(event_id)
        if not isinstance(replay, dict):
            errors.append(f"{event_id}: held-level replay is absent")
            continue
        sources = replay.get("source_samples")
        qualifiers_samples = replay.get("qualifier_samples")
        expected = replay.get("expected_counter_deltas")
        if not isinstance(sources, list) or len(sources) < 5 or not isinstance(qualifiers_samples, list) or len(qualifiers_samples) != len(sources) or not isinstance(expected, list) or len(expected) != len(sources):
            errors.append(f"{event_id}: held-level replay vectors are invalid")
            continue
        actual = _replay_deltas(str(kind), sources, qualifiers_samples)
        if actual != expected:
            errors.append(f"{event_id}: held-level replay counter deltas differ")
        held_without_qualifier = any(
            sources[index] == 1 and sources[index - 1] == 1
            and qualifiers_samples[index] == 0 and expected[index] == 0
            for index in range(1, len(sources))
        )
        if not held_without_qualifier:
            errors.append(f"{event_id}: replay does not prove held level is non-progress")
        receipts[event_id] = {"event_kind": kind, "actual_counter_deltas": actual}
    if set(replay_by_id) != event_ids:
        errors.append("held-level replay exact set differs from progress event set")
    return receipts


def validate_contract(contract: dict[str, Any], workspace: Path) -> dict[str, Any]:
    errors: list[str] = []
    controls: dict[str, Any] = {}
    if contract.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    package = contract.get("package") if isinstance(contract.get("package"), dict) else {}
    try:
        zip_path = _resolve_workspace(workspace, (package.get("final_zip") or {}).get("path"))
    except (AttributeError, ValueError) as exc:
        errors.append(str(exc))
        zip_path = workspace / "__absent__.zip"
    identity = package.get("final_zip") if isinstance(package.get("final_zip"), dict) else {}
    if not zip_path.is_file():
        errors.append("exact final ZIP is absent")
    elif identity.get("bytes") != zip_path.stat().st_size or identity.get("sha256") != _sha256_file(zip_path):
        errors.append("exact final ZIP bytes/SHA differ")
    members: dict[str, bytes] = {}
    if zip_path.is_file():
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                members = _safe_zip_members(archive, str(package.get("zip_root_member")))
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(f"final ZIP extraction failed: {exc}")
    if members:
        controls["manifest"] = _manifest_checks(contract, members, errors)
        controls["cross_member_identities"] = _identity_checks(contract, members, errors)
        controls["return_phase"] = _return_phase_checks(contract, members, errors)
        controls["progress_qualification"] = _progress_checks(contract, members, errors)
    checks = {
        "final_zip_identity": bool(
            zip_path.is_file()
            and identity.get("bytes") == zip_path.stat().st_size
            and identity.get("sha256") == _sha256_file(zip_path)
        ),
        "manifest_terminal": not any("manifest" in item for item in errors),
        "budget_identity": not any("wall" in item or "cross-member" in item or "maximum" in item for item in errors),
        "return_phase_closed": not any("return" in item or "producer" in item or "runner" in item or "postpublication" in item or "finalization guard" in item for item in errors),
        "progress_events_qualified": not any("progress" in item or "replay" in item or "handshake" in item or "transition" in item for item in errors),
    }
    return {
        "schema": SCHEMA,
        "package_id": package.get("package_id"),
        "pass": not errors,
        "checks": checks,
        "errors": sorted(set(errors)),
        "controls": controls,
        "claim_boundary": "Local final-ZIP cross-member and temporal consistency only; no server, DUT, natural-terminal, formal-D or E3-E5 claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    report = validate_contract(contract, args.workspace.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
