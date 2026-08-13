#!/usr/bin/env python3
"""Persist every exact v87b ACK phase EVENT row before bounded collectors run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PREFIX = "CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_inline_realtime_target "
TARGET = (
    "instance=tb_NDP_Top_new_phy.u_NDP_Top_new."
    "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group."
    "slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue "
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--expected-events", type=int, default=65)
    args = parser.parse_args()
    raw = args.log.read_text(encoding="utf-8", errors="replace") if args.log.is_file() else ""
    rows = [line for line in raw.splitlines() if line.startswith(PREFIX) and TARGET in line]
    args.events.parent.mkdir(parents=True, exist_ok=True)
    args.events.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8", newline="\n")
    sequences: dict[int, list[int]] = {}
    for line in rows:
        fields = dict(
            token.split("=", 1) for token in line.split() if "=" in token
        )
        try:
            sequences.setdefault(int(fields["seq"]), []).append(int(fields["ord"]))
        except (KeyError, ValueError):
            pass
    complete = all(ordinals == [0, 1, 2, 3, 4] for ordinals in sequences.values())
    passed = len(rows) == args.expected_events and complete
    receipt = {
        "schema": "node0004-buffer-ack-phase-raw-preservation-v1",
        "pass": passed,
        "expected_event_count": args.expected_events,
        "event_count": len(rows),
        "sequence_count": len(sequences),
        "complete_five_phase_sequences": sum(
            ordinals == [0, 1, 2, 3, 4] for ordinals in sequences.values()
        ),
        "all_rows_unbounded": True,
        "sampling": False,
        "truncation": False,
        "source_log": {
            "bytes": args.log.stat().st_size if args.log.is_file() else 0,
            "sha256": sha(args.log) if args.log.is_file() else None,
        },
        "events": {
            "bytes": args.events.stat().st_size,
            "sha256": sha(args.events),
        },
        "target_instance": TARGET[len("instance=") :].strip(),
        "claim_boundary": "Raw execution-bound phase row preservation only; no VPD decoding or RTL classification.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
