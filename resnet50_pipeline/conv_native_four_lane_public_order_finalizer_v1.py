#!/usr/bin/env python3
"""Parse the bounded p11 public-order witness into one canonical receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


FEATURE_PREFIX = "N4P_FEATURE_ENABLE_V1 "
SNAPSHOT_PREFIX = "N4P_SNAPSHOT_V1 "
EVENT_PREFIX = "N4P_EVENT_V1 "


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def fields(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line
        )
    }


def _status(path: Path, default: int = 125) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return default


def _signal(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip() or "MISSING"
    except OSError:
        return "MISSING"


def _parse(path: Path) -> dict[str, Any]:
    features: list[dict[str, str]] = []
    snapshots: list[dict[str, str]] = []
    events: list[dict[str, str]] = []
    unknown: list[str] = []
    if path.is_file():
        for line in path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith(FEATURE_PREFIX):
                features.append(fields(line))
            elif line.startswith(SNAPSHOT_PREFIX):
                snapshots.append(fields(line))
            elif line.startswith(EVENT_PREFIX):
                events.append(fields(line))
            elif line:
                unknown.append(line[:512])
    last = snapshots[-1] if snapshots else {}
    event_counts = {
        kind: sum(row.get("kind") == kind for row in events)
        for kind in (
            "SA_IN_ACCEPT",
            "SA_OUT_ACCEPT",
            "MSE4_INDEX_ACCEPT",
        )
    }
    raw_valid = int(last.get("saout_raw_valid_now", "0"), 0)
    ready = int(last.get("saout_ready_now", "0"), 0)
    input_count = int(last.get("sain_saved", "0"), 0)
    output_count = int(last.get("saout_saved", "0"), 0)
    mse4_count = int(last.get("mse4_saved", "0"), 0)
    blocked_cycles = int(last.get("saout_blocked", "0"), 0)
    if len(features) != 1:
        decision = "SIM_NOT_STARTED_OR_FEATURE_BINDING_MISSING"
    elif len(snapshots) != 1:
        decision = "PUBLIC_ORDER_SNAPSHOT_MISSING_OR_AMBIGUOUS"
    elif raw_valid and not ready and blocked_cycles:
        decision = "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
    elif not raw_valid and input_count > output_count:
        decision = "SA_OUTPUT_GENERATION_STOPPED_AFTER_ACCEPTED_INPUTS"
    elif raw_valid and ready and output_count <= 3:
        decision = "SA_OUTPUT_ACCEPT_PREDICATE_INCONSISTENT"
    elif output_count > mse4_count:
        decision = "SA_OUTPUT_REACHED_BUFFER_BUT_MSE4_DID_NOT_CONSUME"
    else:
        decision = "PUBLIC_ORDER_EVIDENCE_INCOMPLETE"
    return {
        "feature_count": len(features),
        "snapshot_count": len(snapshots),
        "event_count": len(events),
        "event_counts": event_counts,
        "features": features,
        "snapshots": snapshots,
        "events": events,
        "unknown_lines": unknown,
        "decision": decision,
    }


def finalize(
    *,
    observer_log: Path,
    compile_status: Path,
    run_status: Path,
    signal_status: Path,
) -> dict[str, Any]:
    parsed = _parse(observer_log)
    valid = (
        not parsed["unknown_lines"]
        and parsed["feature_count"] == 1
        and parsed["snapshot_count"] == 1
        and parsed["event_counts"]["SA_IN_ACCEPT"]
        == int(parsed["snapshots"][0].get("sain_saved", "-1"), 0)
        and parsed["event_counts"]["SA_OUT_ACCEPT"]
        == int(parsed["snapshots"][0].get("saout_saved", "-1"), 0)
        and parsed["event_counts"]["MSE4_INDEX_ACCEPT"]
        == int(parsed["snapshots"][0].get("mse4_saved", "-1"), 0)
    )
    return {
        "schema": "conv-native-four-lane-public-order-summary-v1",
        "valid": valid,
        "status": parsed["decision"] if valid else "EVIDENCE_INCOMPLETE",
        "execution": {
            "compile_exit_status": _status(compile_status),
            "run_exit_status": _status(run_status),
            "signal_status": _signal(signal_status),
        },
        "observer": {
            "path": str(observer_log),
            "present": observer_log.is_file(),
            "size_bytes": (
                observer_log.stat().st_size
                if observer_log.is_file()
                else 0
            ),
            "sha256": sha256(observer_log) if observer_log.is_file() else None,
            **parsed,
        },
        "claim_boundary": (
            "c0 public-order/backpressure diagnostic only; no formal 320D, "
            "E3, E4, E5, numeric correctness, or performance claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--compile-status", type=Path, required=True)
    parser.add_argument("--run-status", type=Path, required=True)
    parser.add_argument("--signal-status", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(
        observer_log=args.observer_log,
        compile_status=args.compile_status,
        run_status=args.run_status,
        signal_status=args.signal_status,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
