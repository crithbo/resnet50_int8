#!/usr/bin/env python3
"""Finalize bounded native-Conv triggered-causal observer evidence.

This package-local helper never touches DUT inputs or timing.  It parses the
small triggered log at runner finalization time and emits one deterministic
receipt that remains useful when the simulator exits by signal or timeout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


FEATURE_PREFIX = "N4T_FEATURE_ENABLE_V1 "
TRIGGER_PREFIX = "N4T_TRIGGER_V1 "
TRIGGER_RE = re.compile(
    r"^N4T_TRIGGER_V1 trigger=(?P<trigger>\S+) "
    r"classification=(?P<classification>\S+) "
    r"reason=(?P<reason>\S+) "
)
CANONICAL = {
    "TEST_INFRASTRUCTURE_FAILURE",
    "SIM_NOT_STARTED",
    "TARGET_STAGE_NOT_REACHED",
    "DYNAMIC_FLOW_CONTROL_STALL",
    "TERMINAL_PROPAGATION_FAILURE",
    "RESULT_COLLECTION_FAILURE",
    "NUMERIC_MISMATCH",
    "NATURAL_SUCCESS",
    "EVIDENCE_INCOMPLETE",
}
TRIGGERS = {
    "FIRST_QUEUE_FULL",
    "FIRST_BRANCH_DIVERGENCE",
    "NO_PROGRESS_WINDOW",
    "TERMINAL_GAP",
    "STAGE_TRANSITION",
    "EXIT_OR_SIGNAL",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _status(path: Path) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 125


def _signal(path: Path) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
    except OSError:
        return "MISSING"
    return value or "MISSING"


def _parse_log(path: Path) -> dict[str, Any]:
    features: list[str] = []
    records: list[dict[str, str]] = []
    malformed: list[str] = []
    if path.is_file():
        for line in path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith(FEATURE_PREFIX):
                features.append(line)
            elif line.startswith(TRIGGER_PREFIX):
                match = TRIGGER_RE.match(line)
                if match is None:
                    malformed.append(line[:512])
                else:
                    records.append(match.groupdict())
    trigger_counts = {
        trigger: sum(record["trigger"] == trigger for record in records)
        for trigger in sorted(TRIGGERS)
    }
    classification_counts = {
        classification: sum(
            record["classification"] == classification
            for record in records
        )
        for classification in sorted(CANONICAL)
    }
    unknown_triggers = sorted(
        {record["trigger"] for record in records} - TRIGGERS
    )
    unknown_classifications = sorted(
        {record["classification"] for record in records} - CANONICAL
    )
    natural = any(
        record["trigger"] == "STAGE_TRANSITION"
        and record["classification"] == "NATURAL_SUCCESS"
        for record in records
    )
    if not features:
        classification = "SIM_NOT_STARTED"
    elif natural:
        classification = "NATURAL_SUCCESS"
    elif trigger_counts["TERMINAL_GAP"]:
        classification = "TERMINAL_PROPAGATION_FAILURE"
    elif (
        trigger_counts["FIRST_QUEUE_FULL"]
        or trigger_counts["FIRST_BRANCH_DIVERGENCE"]
        or trigger_counts["NO_PROGRESS_WINDOW"]
    ):
        classification = "DYNAMIC_FLOW_CONTROL_STALL"
    else:
        classification = "EVIDENCE_INCOMPLETE"
    return {
        "feature_marker_count": len(features),
        "trigger_record_count": len(records),
        "trigger_counts": trigger_counts,
        "classification_counts": classification_counts,
        "unknown_triggers": unknown_triggers,
        "unknown_classifications": unknown_classifications,
        "malformed_records": malformed,
        "natural_slice_finish_observed": natural,
        "canonical_classification": classification,
        "last_record": records[-1] if records else None,
    }


def finalize(
    *,
    observer_log: Path,
    sim_log: Path,
    compile_status: Path,
    run_status: Path,
    signal_status: Path,
) -> dict[str, Any]:
    parsed = _parse_log(observer_log)
    compile_value = _status(compile_status)
    run_value = _status(run_status)
    signal_value = _signal(signal_status)
    parser_valid = (
        not parsed["malformed_records"]
        and not parsed["unknown_triggers"]
        and not parsed["unknown_classifications"]
    )
    return {
        "schema": "conv-native-four-lane-triggered-causal-summary-v1",
        "valid": parser_valid,
        "status": parsed["canonical_classification"],
        "execution": {
            "compile_exit_status": compile_value,
            "run_exit_status": run_value,
            "signal_status": signal_value,
            "compile_succeeded": compile_value == 0,
            "simulator_natural_exit": (
                run_value == 0 and signal_value == "NONE"
            ),
        },
        "observer": {
            "path": str(observer_log),
            "present": observer_log.is_file(),
            "bytes": (
                observer_log.stat().st_size
                if observer_log.is_file()
                else 0
            ),
            "sha256": sha256(observer_log) if observer_log.is_file() else None,
            **parsed,
        },
        "sim_log": {
            "path": str(sim_log),
            "present": sim_log.is_file(),
            "bytes": sim_log.stat().st_size if sim_log.is_file() else 0,
            "sha256": sha256(sim_log) if sim_log.is_file() else None,
        },
        "claim_boundary": (
            "c0 triggered-causal diagnostic only; no formal 320D, E3, "
            "E4, E5, numeric correctness, or performance claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--compile-status", type=Path, required=True)
    parser.add_argument("--run-status", type=Path, required=True)
    parser.add_argument("--signal-status", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(
        observer_log=args.observer_log,
        sim_log=args.sim_log,
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
