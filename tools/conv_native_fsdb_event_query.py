#!/usr/bin/env python3
"""Build an identity-bound registered event receipt for native-Conv FSDB runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


EVENT = re.compile(
    r"^CODEX_NATIVE_FSDB_EVENT_V1 instance=(\S+) sequence=(\d+) time_tick=(\d+) "
    r"candidate=([A-Za-z0-9_.-]+) width=(\d+) value=([bB]?[01xXzZ]+)$"
)
SUMMARY = re.compile(
    r"^CODEX_NATIVE_FSDB_SUMMARY_V1 instance=(\S+) sequence_count=(\d+) "
    r"time_tick=(\d+) end_vector=([bB]?[01xXzZ]+)$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def argv_json(text_path: Path, output: Path) -> int:
    text = text_path.read_text(encoding="utf-8", errors="replace").strip()
    write_json(
        output,
        {
            "schema": "server-production-simulation-argv-v1",
            "cwd": os.getcwd(),
            "argv_text": text,
            "shell_pipeline": False,
        },
    )
    return 0


def collect_query(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    source = json.loads(args.source_report.read_text(encoding="utf-8"))
    raw = json.loads(args.waveform_receipt.read_text(encoding="utf-8"))
    catalog = profile["candidates"]
    candidates = {row["candidate_id"]: row for row in catalog}
    expected_instance = profile["exact_probe_instance"]
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    summary: tuple[str, str, str, str] | None = None

    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = EVENT.match(line.strip())
        if match:
            instance, sequence, tick, candidate_id, width, value = match.groups()
            if instance != expected_instance:
                continue
            candidate = candidates.get(candidate_id)
            if candidate is None:
                errors.append(f"unexpected_candidate:{candidate_id}")
                continue
            row = {
                "sequence": int(sequence),
                "time_tick": int(tick),
                "candidate_id": candidate_id,
                "hierarchical_path": candidate["hierarchical_path"],
                "width": int(width),
                "value": value.lower(),
            }
            if row["width"] != candidate["width"]:
                errors.append(f"width_mismatch:{candidate_id}")
            events.append(row)
            continue
        match = SUMMARY.match(line.strip())
        if match and match.group(1) == expected_instance:
            summary = match.groups()

    sequences = [row["sequence"] for row in events]
    if sequences != list(range(len(events))):
        errors.append("noncontiguous_sequence")
    if summary is None:
        errors.append("summary_missing")
    elif int(summary[1]) != len(events):
        errors.append("summary_sequence_count_mismatch")
    expected = sorted(candidates)
    covered = sorted({row["candidate_id"] for row in events})
    missing = sorted(set(expected) - set(covered))
    if missing:
        errors.append("missing_candidates:" + ",".join(missing))

    raw_complete = (
        raw.get("schema") == "server-waveform-runtime-receipt-v3"
        and raw.get("pass") is True
        and raw.get("package_id") == args.package_id
        and raw.get("execution_id") == args.execution_id
        and bool(raw.get("waveforms"))
        and all(row.get("completeness") == "COMPLETE" for row in raw.get("waveforms", []))
    )
    if not raw_complete:
        errors.append("raw_fsdb_incomplete_or_identity_drift")
    compile_argv = json.loads(args.actual_compile_argv.read_text(encoding="utf-8"))
    sim_argv = json.loads(args.actual_sim_argv.read_text(encoding="utf-8"))
    compile_text = " ".join(str(item) for item in compile_argv.get("argv", []))
    sim_text = sim_argv.get("argv_text", "")
    dump_text = args.dump_control.read_text(encoding="utf-8", errors="replace")
    for token, haystack, label in (
        ("DUMP_VCD=0", compile_text + " " + sim_text, "dump_vcd"),
        ("DUMP_FSDB=1", compile_text + " " + sim_text, "dump_fsdb"),
        ("TB_DUMP_FSDB=0", compile_text + " " + sim_text, "tb_dump_fsdb"),
        ("+CODEX_NATIVE_FSDB_QUERY", sim_text, "query_plusarg"),
        ("fsdbDumpfile", dump_text, "fsdb_file"),
        ("fsdbDumpvars 0 tb_NDP_Top_new_phy", dump_text, "fsdb_scope"),
    ):
        if token not in haystack:
            errors.append(f"identity_binding_missing:{label}")

    end_states: list[dict[str, Any]] = []
    for candidate in catalog:
        rows = [row for row in events if row["candidate_id"] == candidate["candidate_id"]]
        if rows:
            end_states.append(
                {
                    key: rows[-1][key]
                    for key in ("candidate_id", "hierarchical_path", "width", "time_tick", "value")
                }
            )
    complete = not errors
    receipt = {
        "schema": "server-waveform-signal-query-receipt-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "profile_sha256": sha256(args.profile),
        "probe_catalog_sha256": profile["probe_catalog_sha256"],
        "timescale": profile["timescale"],
        "completeness": "COMPLETE" if complete else "PARTIAL",
        "catalog": catalog,
        "capture": {
            "format": "REGISTERED_EVENT_ROWS",
            "ordered": True,
            "every_transition": True,
            "no_byte_limit": True,
            "no_event_limit": True,
            "sampling": False,
            "truncation": False,
            "flush_complete": summary is not None,
            "source_generation_report": {
                "path": str(args.source_report.resolve()),
                "sha256": sha256(args.source_report),
            },
        },
        "candidate_coverage": {
            "expected": expected,
            "covered": covered,
            "missing": missing,
            "unexpected": sorted(
                {item.split(":", 1)[1] for item in errors if item.startswith("unexpected_candidate:")}
            ),
        },
        "events": events,
        "candidate_end_states": end_states
        or [
            {
                "candidate_id": catalog[0]["candidate_id"],
                "hierarchical_path": catalog[0]["hierarchical_path"],
                "width": catalog[0]["width"],
                "time_tick": 0,
                "value": "x" if catalog[0]["width"] == 1 else "bxx",
            }
        ],
        "claim_boundary": (
            "Complete source-bound MSE4 registered event rows for this exact attempt only; "
            "no DUT success, natural-terminal, formal-D, E3, E4 or E5 claim."
        ),
    }
    binding = {
        "schema": "conv-native-fsdb-query-binding-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "exact_probe_instance": expected_instance,
        "profile": identity(args.profile),
        "source_report": identity(args.source_report),
        "actual_compile_argv": identity(args.actual_compile_argv),
        "actual_sim_argv": identity(args.actual_sim_argv),
        "dump_control": identity(args.dump_control),
        "raw_waveform_receipt": identity(args.waveform_receipt),
        "sim_log": identity(args.log),
        "exit_kind": args.exit_kind,
        "errors": errors,
    }
    status = {
        "schema": "conv-native-fsdb-diagnostic-status-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "status": "DIAGNOSTIC_EVIDENCE_COMPLETE" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "raw_fsdb_preserved": bool(raw.get("waveforms")),
        "core_return_must_publish": True,
        "errors": errors,
    }
    write_json(args.output_dir / "SIGNAL_QUERY_RECEIPT.json", receipt)
    write_json(args.output_dir / "FSDB_QUERY_BINDING.json", binding)
    write_json(args.output_dir / "DIAGNOSTIC_STATUS.json", status)
    return 0 if complete else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    argv = sub.add_parser("argv-json")
    argv.add_argument("--text", type=Path, required=True)
    argv.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("collect")
    for name in (
        "log",
        "profile",
        "source-report",
        "waveform-receipt",
        "actual-compile-argv",
        "actual-sim-argv",
        "dump-control",
        "output-dir",
    ):
        run.add_argument("--" + name, type=Path, required=True)
    run.add_argument("--package-id", required=True)
    run.add_argument("--execution-id", required=True)
    run.add_argument("--attempt-id", required=True)
    run.add_argument("--exit-kind", required=True)
    args = parser.parse_args()
    if args.command == "argv-json":
        return argv_json(args.text, args.output)
    return collect_query(args)


if __name__ == "__main__":
    raise SystemExit(main())
