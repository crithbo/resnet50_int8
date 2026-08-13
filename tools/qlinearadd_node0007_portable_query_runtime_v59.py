#!/usr/bin/env python3
"""Create QAdd v59 same-attempt portable VCD/query evidence.

The helper never runs a simulator.  ``prepare`` writes the exact dual-format
UCLI control for the already selected attempt.  ``finalize`` consumes that
attempt's direct VCD, emits a registered complete/partial event receipt for
the source-bound candidate catalog, and builds the shared portable runtime
receipt.  Portable failures remain diagnostic-only and do not suppress the
authoritative raw-VPD or compile/sim/core return.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from tools.server_waveform_local_analysis import validate_vcd  # noqa: E402
from tools.server_waveform_portable_query import (  # noqa: E402
    QUERY_SCHEMA,
    make_runtime_receipt,
    pretty_json,
    validate_query_receipt,
    validate_runtime_receipt,
)


STATUS_SCHEMA = "qlinearadd-node0007-portable-waveform-status-v1"
FAILURE_SCHEMA = "qlinearadd-node0007-signal-query-failure-v1"
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


class PortableQueryError(ValueError):
    """The exact attempt cannot produce a registered query receipt."""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(pretty_json(value))
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_vector(raw: str, width: int) -> str:
    value = raw.lower()
    if not value or any(char not in "01xz" for char in value):
        raise PortableQueryError(f"invalid VCD vector value: {raw!r}")
    if len(value) > width:
        raise PortableQueryError(
            f"VCD vector width overflow: declared={width} observed={len(value)}"
        )
    extension = value[0] if value[0] in "xz" else "0"
    return "b" + extension * (width - len(value)) + value


def _value_change(line: str, width: int) -> tuple[str, str] | None:
    if not line:
        return None
    if line[0] in "01xXzZ" and len(line) > 1:
        if width != 1:
            raise PortableQueryError("scalar VCD change used for a vector candidate")
        return line[1:], line[0].lower()
    if line[0] in "bB" and " " in line:
        value, identifier = line.split(None, 1)
        if width == 1:
            payload = value[1:].lower()
            if len(payload) != 1 or payload not in "01xz":
                raise PortableQueryError("vector VCD change is invalid for scalar candidate")
            return identifier, payload
        return identifier, _normalize_vector(value[1:], width)
    return None


def build_query_receipt(
    *,
    profile: dict[str, Any],
    vcd: Path,
    package_id: str,
    execution_id: str,
    attempt_id: str,
    source_report_relative: str,
    source_report: Path,
    completeness: str,
) -> dict[str, Any]:
    catalog = validate_vcd(vcd)
    if catalog.get("pass") is not True:
        raise PortableQueryError(f"direct VCD catalog failed: {catalog.get('errors')}")
    expected = profile["probe_catalog"]
    catalog_by_path = {
        item["path"]: item for item in catalog.get("signals", []) if isinstance(item, dict)
    }
    selected: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for candidate in expected:
        signal = catalog_by_path.get(candidate["hierarchical_path"])
        if signal is None or signal.get("width") != candidate["width"]:
            missing.append(candidate["candidate_id"])
            continue
        if signal["id"] in selected:
            raise PortableQueryError(
                f"VCD identifier aliases two registered candidates: {signal['id']}"
            )
        selected[signal["id"]] = candidate
    if missing:
        raise PortableQueryError(f"registered candidate catalog is incomplete: {missing}")

    events: list[dict[str, Any]] = []
    end_values: dict[str, tuple[int, str]] = {}
    current_time = 0
    header_done = False
    with vcd.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        for raw in stream:
            line = raw.strip()
            if not header_done:
                if line.startswith("$enddefinitions"):
                    header_done = True
                continue
            if not line or line.startswith("$"):
                continue
            if line.startswith("#"):
                try:
                    current_time = int(line[1:], 10)
                except ValueError as error:
                    raise PortableQueryError(f"invalid VCD time row: {line[:80]}") from error
                continue
            widths = {identifier: candidate["width"] for identifier, candidate in selected.items()}
            identifier_guess = line[1:] if line[0] in "01xXzZ" else (
                line.split(None, 1)[1] if line[0] in "bB" and " " in line else None
            )
            if identifier_guess not in widths:
                continue
            parsed = _value_change(line, widths[identifier_guess])
            if parsed is None:
                continue
            identifier, value = parsed
            candidate = selected[identifier]
            event = {
                "sequence": len(events),
                "time_tick": current_time,
                "candidate_id": candidate["candidate_id"],
                "hierarchical_path": candidate["hierarchical_path"],
                "width": candidate["width"],
                "value": value,
            }
            events.append(event)
            end_values[candidate["candidate_id"]] = (current_time, value)

    candidate_ids = [item["candidate_id"] for item in expected]
    missing_end = [candidate_id for candidate_id in candidate_ids if candidate_id not in end_values]
    if missing_end:
        raise PortableQueryError(f"registered candidates lack end state: {missing_end}")
    end_states = []
    for candidate in expected:
        time_tick, value = end_values[candidate["candidate_id"]]
        end_states.append(
            {
                "candidate_id": candidate["candidate_id"],
                "hierarchical_path": candidate["hierarchical_path"],
                "width": candidate["width"],
                "time_tick": time_tick,
                "value": value,
            }
        )
    profile_sha = hashlib.sha256(pretty_json(profile)).hexdigest()
    receipt = {
        "schema": QUERY_SCHEMA,
        "package_id": package_id,
        "execution_id": execution_id,
        "attempt_id": attempt_id,
        "profile_sha256": profile_sha,
        "probe_catalog_sha256": profile["probe_catalog_sha256"],
        "timescale": catalog["timescale"],
        "completeness": completeness,
        "catalog": expected,
        "capture": {
            "format": "REGISTERED_EVENT_ROWS",
            "ordered": True,
            "every_transition": True,
            "no_byte_limit": True,
            "no_event_limit": True,
            "sampling": False,
            "truncation": False,
            "flush_complete": True,
            "source_generation_report": {
                "path": source_report_relative,
                "sha256": sha256_file(source_report),
            },
        },
        "candidate_coverage": {
            "expected": candidate_ids,
            "covered": candidate_ids,
            "missing": [],
            "unexpected": [],
        },
        "events": events,
        "candidate_end_states": end_states,
        "claim_boundary": (
            "Every direct-VCD value change for the exact registered QAdd Buffer5 "
            "producer/clear/bank-ready/read-result candidates; family diagnosis remains separate."
        ),
    }
    errors = validate_query_receipt(
        receipt,
        profile,
        {
            "package_id": package_id,
            "execution_id": execution_id,
            "attempt_id": attempt_id,
            "profile_sha256": profile_sha,
        },
    )
    if errors:
        raise PortableQueryError(f"registered query receipt validation failed: {errors}")
    return receipt


def prepare(args: argparse.Namespace) -> int:
    profile = load_json(args.profile)
    attempt_relative = args.attempt_relative.rstrip("/")
    args.attempt_root.mkdir(parents=True, exist_ok=True)
    (args.attempt_root / "run/sim_results").mkdir(parents=True, exist_ok=True)
    (args.attempt_root / "evidence/portable").mkdir(parents=True, exist_ok=True)
    scope = profile["portable_vcd"]["source_bound_scope"]
    lines = [
        f"dump -file {attempt_relative}/run/sim_results/wave.vpd -type VPD",
        f"dump -add {scope['top']} -depth {scope['depth']} -aggregates",
        f"dump -file {attempt_relative}/run/sim_results/wave.vcd -type VCD",
        f"dump -add {scope['top']} -depth {scope['depth']} -aggregates",
        "run",
        "quit",
    ]
    args.output_tcl.parent.mkdir(parents=True, exist_ok=True)
    args.output_tcl.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


def finalize(args: argparse.Namespace) -> int:
    profile = load_json(args.profile)
    attempt_relative = args.attempt_relative.rstrip("/")
    portable_dir = args.attempt_root / "evidence/portable"
    portable_dir.mkdir(parents=True, exist_ok=True)
    source_copy = portable_dir / "source_generation_report.json"
    shutil.copyfile(args.source_generation_report, source_copy)
    source_relative = f"{attempt_relative}/evidence/portable/{source_copy.name}"
    vcd = args.attempt_root / "run/sim_results/wave.vcd"
    query_path = portable_dir / "SIGNAL_QUERY_RECEIPT.json"
    query_failure_path = portable_dir / "SIGNAL_QUERY_FAILURE.json"
    query_available = False
    query_errors: list[str] = []
    completeness = "COMPLETE" if args.exit_kind == "NATURAL" else "PARTIAL"
    if args.simulation_started:
        try:
            query = build_query_receipt(
                profile=profile,
                vcd=vcd,
                package_id=args.package_id,
                execution_id=args.execution_id,
                attempt_id=args.attempt_id,
                source_report_relative=source_relative,
                source_report=source_copy,
                completeness=completeness,
            )
            write_json(query_path, query)
            query_available = True
        except (OSError, KeyError, json.JSONDecodeError, PortableQueryError) as error:
            query_errors.append(f"{type(error).__name__}: {error}")
            write_json(
                query_failure_path,
                {
                    "schema": FAILURE_SCHEMA,
                    "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
                    "errors": query_errors,
                    "raw_core_return_preserved": True,
                    "no_byte_limit": True,
                    "no_event_limit": True,
                    "sampling": False,
                    "truncation": False,
                },
            )

    raw_receipt = args.attempt_root / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
    raw_data = load_json(raw_receipt)
    allowlist: list[str] = []
    for wave in raw_data.get("waveforms", []):
        source = wave.get("source_path") if isinstance(wave, dict) else None
        if isinstance(source, str):
            allowlist.append(f"{attempt_relative}/{source}")
    fixed = [
        f"{attempt_relative}/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        f"{attempt_relative}/codex_wave_dump.tcl",
        f"{attempt_relative}/evidence/actual_simulator_argv.json",
        source_relative,
    ]
    if vcd.is_file():
        fixed.append(f"{attempt_relative}/run/sim_results/wave.vcd")
    if query_available:
        fixed.append(f"{attempt_relative}/evidence/portable/{query_path.name}")
    else:
        fixed.append(f"{attempt_relative}/evidence/portable/{query_failure_path.name}")
    allowlist = list(dict.fromkeys([*allowlist, *fixed]))
    allowlist_path = portable_dir / "PORTABLE_RETURN_ALLOWLIST.json"
    write_json(allowlist_path, allowlist)
    request = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "attempt_root": attempt_relative,
        "first_fresh_for_profile": True,
        "capture_mode": "DIRECT_VCD_AND_QUERY",
        "simulation_started": args.simulation_started,
        "exit_kind": args.exit_kind,
        "actual_sim_argv_path": f"{attempt_relative}/evidence/actual_simulator_argv.json",
        "dump_tcl_path": f"{attempt_relative}/codex_wave_dump.tcl",
        "raw_vpd_runtime_receipt_path": (
            f"{attempt_relative}/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
        ),
        "portable_vcd_path": (
            f"{attempt_relative}/run/sim_results/wave.vcd" if vcd.is_file() else None
        ),
        "signal_query_receipt_path": (
            f"{attempt_relative}/evidence/portable/{query_path.name}"
            if query_available
            else None
        ),
        "return_allowlist_path": (
            f"{attempt_relative}/evidence/portable/{allowlist_path.name}"
        ),
    }
    request_path = portable_dir / "PORTABLE_RUNTIME_REQUEST.json"
    write_json(request_path, request)
    runtime_receipt_path = portable_dir / "PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json"
    validation_path = portable_dir / "PORTABLE_WAVEFORM_VALIDATION.json"
    runtime_receipt = make_runtime_receipt(profile, request, args.asset_root)
    write_json(runtime_receipt_path, runtime_receipt)
    validation = validate_runtime_receipt(runtime_receipt, profile, args.asset_root)
    write_json(validation_path, validation)
    status = {
        "schema": STATUS_SCHEMA,
        "diagnostic_status": runtime_receipt["diagnostic_status"],
        "contract_valid": validation["contract_valid"],
        "diagnostic_complete": validation["diagnostic_complete"],
        "query_available": query_available,
        "query_errors": query_errors,
        "return_must_publish": True,
        "raw_core_return_preserved": True,
        "no_byte_limit": True,
        "no_event_limit": True,
        "sampling": False,
        "truncation": False,
        "claim_boundary": "Portable evidence status only; no family root-cause claim.",
    }
    status_path = portable_dir / "PORTABLE_WAVEFORM_STATUS.json"
    write_json(status_path, status)
    extended = list(
        dict.fromkeys(
            [
                *allowlist,
                f"{attempt_relative}/evidence/portable/{request_path.name}",
                f"{attempt_relative}/evidence/portable/{runtime_receipt_path.name}",
                f"{attempt_relative}/evidence/portable/{validation_path.name}",
                f"{attempt_relative}/evidence/portable/{status_path.name}",
                f"{attempt_relative}/evidence/portable/{allowlist_path.name}",
            ]
        )
    )
    write_json(allowlist_path, extended)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    prepare_cmd = commands.add_parser("prepare")
    prepare_cmd.add_argument("--profile", type=Path, required=True)
    prepare_cmd.add_argument("--attempt-root", type=Path, required=True)
    prepare_cmd.add_argument("--attempt-relative", required=True)
    prepare_cmd.add_argument("--output-tcl", type=Path, required=True)
    finalize_cmd = commands.add_parser("finalize")
    finalize_cmd.add_argument("--profile", type=Path, required=True)
    finalize_cmd.add_argument("--asset-root", type=Path, required=True)
    finalize_cmd.add_argument("--attempt-root", type=Path, required=True)
    finalize_cmd.add_argument("--attempt-relative", required=True)
    finalize_cmd.add_argument("--package-id", required=True)
    finalize_cmd.add_argument("--execution-id", required=True)
    finalize_cmd.add_argument("--attempt-id", required=True)
    finalize_cmd.add_argument("--exit-kind", choices=sorted(EXIT_KINDS), required=True)
    finalize_cmd.add_argument("--simulation-started", action="store_true")
    finalize_cmd.add_argument("--source-generation-report", type=Path, required=True)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        return prepare(args) if args.command == "prepare" else finalize(args)
    except (OSError, KeyError, json.JSONDecodeError, PortableQueryError) as error:
        if args.command == "finalize":
            failure = args.attempt_root / "evidence/portable/PORTABLE_WAVEFORM_STATUS.json"
            write_json(
                failure,
                {
                    "schema": STATUS_SCHEMA,
                    "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
                    "contract_valid": False,
                    "diagnostic_complete": False,
                    "errors": [f"{type(error).__name__}: {error}"],
                    "return_must_publish": True,
                    "raw_core_return_preserved": True,
                },
            )
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
