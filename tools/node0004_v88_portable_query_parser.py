#!/usr/bin/env python3
"""Create the registered node0004 ACK event receipt from one simulation log."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EVENT = re.compile(
    r"^CODEX_PORTABLE_QUERY_V1 kind=EVENT sequence=(?P<sequence>\d+) "
    r"time_tick=(?P<time>\d+) candidate=(?P<candidate>[A-Za-z0-9_.-]+) "
    r"width=(?P<width>\d+) value=(?P<value>[01xXzZ]+)$"
)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--exit-kind", required=True)
    parser.add_argument("--source-generation-report", type=Path, required=True)
    parser.add_argument("--source-generation-report-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    catalog = profile["probe_catalog"]
    by_id = {item["candidate_id"]: item for item in catalog}
    expected = [item["candidate_id"] for item in catalog]
    events: list[dict[str, Any]] = []
    end_values: dict[str, str] = {}
    errors: list[str] = []
    raw_sequence = 0
    if not args.log.is_file():
        errors.append("simulation log is absent")
        lines: list[str] = []
    else:
        lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        match = EVENT.fullmatch(line.strip())
        if match is None:
            continue
        found_sequence = int(match.group("sequence"))
        if found_sequence != raw_sequence:
            errors.append(
                f"observer sequence discontinuity: expected {raw_sequence} got {found_sequence}"
            )
            raw_sequence = found_sequence
        raw_sequence += 1
        candidate_id = match.group("candidate")
        candidate = by_id.get(candidate_id)
        width = int(match.group("width"))
        value = match.group("value").lower()
        if candidate is None:
            errors.append(f"unexpected candidate: {candidate_id}")
            continue
        if width != candidate["width"] or len(value) != width:
            errors.append(f"width mismatch for {candidate_id}")
            continue
        normalized = value if width == 1 else f"b{value}"
        events.append(
            {
                "sequence": len(events),
                "time_tick": int(match.group("time")),
                "candidate_id": candidate_id,
                "hierarchical_path": candidate["hierarchical_path"],
                "width": width,
                "value": normalized,
            }
        )
        end_values[candidate_id] = normalized

    missing = [candidate_id for candidate_id in expected if candidate_id not in end_values]
    if missing:
        errors.append(f"missing candidate event coverage: {missing}")
    if not args.source_generation_report.is_file():
        errors.append("source generation report is absent")
        source_sha = "0" * 64
    else:
        source_sha = digest(args.source_generation_report)
    expected_source_sha = profile["portable_vcd"]["source_bound_scope"][
        "source_receipt_sha256"
    ]
    if source_sha != expected_source_sha:
        errors.append("source generation report/profile SHA mismatch")

    receipt = {
        "schema": "server-waveform-signal-query-receipt-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "profile_sha256": hashlib.sha256(pretty(profile)).hexdigest(),
        "probe_catalog_sha256": profile["probe_catalog_sha256"],
        "timescale": "1ps",
        "completeness": "COMPLETE" if args.exit_kind == "NATURAL" else "PARTIAL",
        "catalog": catalog,
        "capture": {
            "format": "REGISTERED_EVENT_ROWS",
            "ordered": True,
            "every_transition": True,
            "no_byte_limit": True,
            "no_event_limit": True,
            "sampling": False,
            "truncation": False,
            "flush_complete": not errors,
            "source_generation_report": {
                "path": args.source_generation_report_path,
                "sha256": source_sha,
            },
        },
        "candidate_coverage": {
            "expected": expected,
            "covered": expected if not missing else [item for item in expected if item not in missing],
            "missing": missing,
            "unexpected": [],
        },
        "events": events,
        "candidate_end_states": [
            {
                "candidate_id": item["candidate_id"],
                "hierarchical_path": item["hierarchical_path"],
                "width": item["width"],
                "value": end_values.get(
                    item["candidate_id"], "x" if item["width"] == 1 else "b" + "x" * item["width"]
                ),
            }
            for item in catalog
        ],
        "claim_boundary": (
            "Exact registered event transport from the package-local input-only ACK monitor; "
            "family functional classification remains separate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pretty(receipt))
    if errors:
        (args.output.with_suffix(args.output.suffix + ".errors.json")).write_bytes(
            pretty({"pass": False, "errors": errors})
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
