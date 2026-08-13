"""Filter generated CODEX_PROBE_V1 records to the ordered tail_round stage.

The generated observer remains the source of all signal predicates.  This
package-local adapter only removes pre-EXEC_START records and aggregate final
records whose counters include pre-stage activity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


START_RE = re.compile(r"^(\d+)\s*\|\s*EXEC_START\s*\|\s*stage=(\d+)\b")
TIME_RE = re.compile(r"\btime=(\d+)\b")
KIND_RE = re.compile(r"\bkind=([A-Z_]+)\b")
KEEP_TIMED = {"EVENT", "TRIGGER", "STALL"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-log", required=True, type=Path)
    parser.add_argument("--observer-log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    source_text = args.source_log.read_text(encoding="utf-8", errors="replace") if args.source_log.exists() else ""
    observer_path = args.observer_log
    observer = (
        observer_path.read_text(encoding="utf-8", errors="replace")
        if observer_path is not None and observer_path.exists()
        else source_text
    )
    starts = [(int(m.group(1)), int(m.group(2))) for line in observer.splitlines() if (m := START_RE.match(line))]
    ordered = [item for item in starts if item[1] == 1]
    start_ps = ordered[0][0] if ordered else None
    source_lines = source_text.splitlines()
    kept: list[str] = []
    pre_stage_dropped = 0
    aggregate_dropped = 0
    malformed_dropped = 0
    for line in source_lines:
        if not line.startswith("CODEX_PROBE_V1 "):
            continue
        kind_match = KIND_RE.search(line)
        kind = kind_match.group(1) if kind_match else ""
        if kind == "ENABLED":
            kept.append(line)
            continue
        if kind not in KEEP_TIMED:
            aggregate_dropped += 1
            continue
        time_match = TIME_RE.search(line)
        if time_match is None:
            malformed_dropped += 1
            continue
        if start_ps is None or int(time_match.group(1)) < start_ps:
            pre_stage_dropped += 1
            continue
        kept.append(line)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8", newline="\n")
    receipt = {
        "schema": "qlinearadd-node0007-source-bound-stage-filter-v57",
        "valid": True,
        "stage_start_found": start_ps is not None,
        "ordered_stage_start_count": len(ordered),
        "stage_id": 1,
        "stage_start_time_ps": start_ps,
        "input_records": len(source_lines),
        "kept_records": len(kept),
        "pre_stage_records_dropped": pre_stage_dropped,
        "aggregate_records_dropped": aggregate_dropped,
        "malformed_records_dropped": malformed_dropped,
        "source_log_sha256": digest(args.source_log) if args.source_log.exists() else None,
        "observer_log_sha256": digest(observer_path) if observer_path is not None and observer_path.exists() else None,
        "ordered_start_source": "observer_log" if observer_path is not None else "source_log",
        "filtered_log_sha256": digest(args.output),
        "claim_boundary": "Record qualification only; no DUT/config/numeric/golden/terminal/D claim.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
