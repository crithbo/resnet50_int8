#!/usr/bin/env python3
"""Persist exact-target phase evidence before the frozen bounded collector mutates sim.log."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=pathlib.Path, required=True)
    parser.add_argument("--attempt-root", type=pathlib.Path, required=True)
    parser.add_argument("--phase-live-log", type=pathlib.Path, required=True)
    parser.add_argument("--phase-output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if not args.phase_live_log.is_file():
        raise RuntimeError("immutable raw phase input is missing")
    input_bytes = args.phase_live_log.stat().st_size
    input_sha256 = sha256(args.phase_live_log)

    phase = subprocess.run(
        [
            sys.executable,
            str(args.package_root / "package_tools/buffer_ack_phase_parser.py"),
            "--log",
            str(args.phase_live_log),
            "--output",
            str(args.phase_output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    phase_error = None
    phase_receipt = None
    if phase.returncode != 0 or not args.phase_output.is_file():
        phase_error = "exact target live phase parser failed: " + phase.stderr
    else:
        value = json.loads(args.phase_output.read_text(encoding="utf-8"))
        phase_receipt = {
            "schema": "node0004-buffer-ack-phase-parser-receipt-v3",
            "parser_exit_status": phase.returncode,
            "decision": value["decision"],
            "decision_sha256": sha256(args.phase_output),
            "target_instance": value["target_instance"],
            "live_event_count": value["live_event_count"],
            "sequence_count": value["sequence_count"],
            "complete_sequence_count": value["complete_sequence_count"],
            "raw_phase_input_bytes_before_bounded_projection": input_bytes,
            "raw_phase_input_sha256_before_bounded_projection": input_sha256,
            "parsed_before_frozen_bounded_collector": True,
        }
        evidence = args.attempt_root / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "buffer_ack_phase_parser_receipt.json").write_text(
            json.dumps(phase_receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    frozen = None
    frozen_error = None
    if (args.attempt_root / "evidence/compile_exit_status.txt").is_file():
        frozen = subprocess.run(
            [
                sys.executable,
                str(args.package_root / "package_tools/node0004_v79_post_sim_plugin.py"),
                "--package-root",
                str(args.package_root),
                "--attempt-root",
                str(args.attempt_root),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if frozen.returncode != 0:
            frozen_error = "v79 frozen collector failed: " + frozen.stderr

    failures = [item for item in (phase_error, frozen_error) if item]
    if failures:
        raise RuntimeError("; ".join(failures))
    print(
        json.dumps(
            {
                "buffer_ack_phase": phase_receipt,
                "frozen_v79_collector": None if frozen is None else frozen.stdout.strip(),
                "ordering": "PHASE_PARSE_PERSIST_BEFORE_BOUNDED_SIM_LOG_PROJECTION",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
