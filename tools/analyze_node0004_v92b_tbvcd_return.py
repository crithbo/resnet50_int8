#!/usr/bin/env python3
"""Stream the node0004 bounded-cone VCD and persist family causal summaries.

The raw VCD is never loaded into memory.  All non-clock transitions are copied
to an append-only-style JSONL derivative without an event cap, while compact
per-signal and owner-clock summaries are accumulated in memory.  The tool is
resume-safe at the completed-pass boundary: an identity-equal completed result
is reused and does not append a duplicate checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO


def hash_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
        total += len(block)
    return total, digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(data)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def known_bits(value: str | None, width: int) -> int | None:
    if value is None or len(value) != width or any(bit not in "01" for bit in value):
        return None
    return int(value, 2)


def transition_summary() -> dict[str, Any]:
    return {
        "transitions": 0,
        "xz_transitions": 0,
        "first_time": None,
        "first_value": None,
        "last_time": None,
        "last_value": None,
        "first_known_time": None,
        "last_change_time": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--vcd-member", required=True)
    parser.add_argument("--catalog-member", required=True)
    parser.add_argument("--state-dir", required=True, type=Path)
    args = parser.parse_args()

    output = args.state_dir
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "family_causal_summary.json"
    transition_path = output / "causal_transitions.jsonl"
    state_path = output / "analysis_state.json"
    checkpoint_path = output / "checkpoints.jsonl"
    report_path = output / "report.md"

    archive_digest = hashlib.sha256()
    archive_bytes = 0
    with args.return_zip.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            archive_digest.update(block)
            archive_bytes += len(block)
    archive_sha = archive_digest.hexdigest()

    if summary_path.exists():
        old = json.loads(summary_path.read_text(encoding="utf-8"))
        source = old.get("source", {})
        if source.get("container_sha256") == archive_sha and old.get("status") == "EOF_REACHED":
            print(json.dumps({"status": "IDENTITY_EQUAL_COMPLETED_REUSE", "summary": str(summary_path)}))
            return 0

    with zipfile.ZipFile(args.return_zip) as archive:
        info = archive.getinfo(args.vcd_member)
        catalog = json.load(archive.open(args.catalog_member))
        catalog_rows = catalog["signals"]
        by_name = {row["signal_id"]: row for row in catalog_rows}

        temporary = transition_path.with_name(f".{transition_path.name}.tmp.{os.getpid()}")
        summaries = {name: transition_summary() for name in by_name}
        code_to_name: dict[str, str] = {}
        values: dict[str, str] = {}
        widths = {name: int(row["width_bits"]) for name, row in by_name.items()}
        current_time = 0
        line_number = 0
        event_count = 0
        non_clock_events = 0
        clock_posedges = 0
        last_clock = None
        current_changed: set[str] = set()
        current_clock_posedge = False
        timescale = None
        directive: str | None = None
        directive_body: list[str] = []
        ack_mismatches = 0
        ack_checks = 0
        first_ack_mismatch = None
        last_ack_mismatch = None
        mem_request_accept_cycles = 0
        wdata_accept_cycles = 0
        global_accept_cycles = 0
        fifo_activity_cycles = 0
        first_owner_posedge = None
        last_owner_posedge = None
        first_state_progress = None
        last_state_progress = None
        first_fully_known_state = None
        last_fully_known_state = None
        natural_terminal_times: list[int] = []
        counter_ranges = {
            name: {"min": None, "max": None, "first_nonzero_time": None, "last_nonzero_time": None}
            for name in ("sig_row_count", "sig_col_count", "sig_queue_count")
        }

        def flush_time() -> None:
            nonlocal clock_posedges, last_clock, current_clock_posedge
            nonlocal ack_mismatches, ack_checks, first_ack_mismatch, last_ack_mismatch
            nonlocal mem_request_accept_cycles, wdata_accept_cycles, global_accept_cycles
            nonlocal fifo_activity_cycles, first_owner_posedge, last_owner_posedge
            nonlocal first_state_progress, last_state_progress
            nonlocal first_fully_known_state, last_fully_known_state
            if not current_changed:
                return
            if any(name != "sig_clk" for name in current_changed):
                if first_state_progress is None:
                    first_state_progress = current_time
                last_state_progress = current_time
            if current_clock_posedge:
                clock_posedges += 1
                if first_owner_posedge is None:
                    first_owner_posedge = current_time
                last_owner_posedge = current_time
                ack = known_bits(values.get("sig_public_ack"), 2)
                row_full = known_bits(values.get("sig_row_full"), 1)
                col_full = known_bits(values.get("sig_col_full"), 1)
                if ack is not None and row_full is not None and col_full is not None:
                    expected = ((1 - row_full) << 1) | (1 - col_full)
                    ack_checks += 1
                    if ack != expected:
                        ack_mismatches += 1
                        row = {"time": current_time, "observed": ack, "expected": expected, "row_full": row_full, "col_full": col_full}
                        if first_ack_mismatch is None:
                            first_ack_mismatch = row
                        last_ack_mismatch = row
                mem_valid = known_bits(values.get("sig_mem_req_valid"), 2)
                mem_ready = known_bits(values.get("sig_mem_req_ready"), 2)
                if mem_valid is not None and mem_ready is not None and mem_valid & mem_ready:
                    mem_request_accept_cycles += 1
                data_valid = known_bits(values.get("sig_wdata_valid"), 2)
                data_ready = known_bits(values.get("sig_wdata_ready"), 2)
                if data_valid is not None and data_ready is not None and data_valid & data_ready:
                    wdata_accept_cycles += 1
                global_valid = known_bits(values.get("sig_global_valid"), 28)
                global_ready = known_bits(values.get("sig_global_ready"), 28)
                if global_valid is not None and global_ready is not None and global_valid & global_ready:
                    global_accept_cycles += 1
                fifo_bits = [known_bits(values.get(name), 1) for name in ("sig_row_wr", "sig_row_rd", "sig_col_wr", "sig_col_rd", "sig_queue_wr", "sig_queue_rd")]
                if any(value == 1 for value in fifo_bits):
                    fifo_activity_cycles += 1
                relevant = [name for name in by_name if name != "sig_clk"]
                fully_known = all(known_bits(values.get(name), widths[name]) is not None for name in relevant)
                if fully_known:
                    if first_fully_known_state is None:
                        first_fully_known_state = current_time
                    last_fully_known_state = current_time
                fetch = known_bits(values.get("sig_global_fetch_finish"), 1)
                slices = known_bits(values.get("sig_global_slice_finish"), 28)
                if fetch == 1 and slices == (1 << 28) - 1:
                    natural_terminal_times.append(current_time)
                for name, ranges in counter_ranges.items():
                    number = known_bits(values.get(name), widths[name])
                    if number is None:
                        continue
                    ranges["min"] = number if ranges["min"] is None else min(ranges["min"], number)
                    ranges["max"] = number if ranges["max"] is None else max(ranges["max"], number)
                    if number:
                        if ranges["first_nonzero_time"] is None:
                            ranges["first_nonzero_time"] = current_time
                        ranges["last_nonzero_time"] = current_time
            current_changed.clear()
            current_clock_posedge = False

        with archive.open(info) as raw, temporary.open("w", encoding="utf-8", newline="\n") as transitions:
            for raw_line in raw:
                line_number += 1
                line = raw_line.decode("utf-8", errors="strict").strip()
                if not line:
                    continue
                if directive is not None:
                    if line == "$end":
                        if directive == "$timescale":
                            timescale = " ".join(directive_body).strip()
                        directive = None
                        directive_body = []
                    else:
                        directive_body.append(line)
                    continue
                if line in {"$timescale", "$date", "$version"}:
                    directive = line
                    directive_body = []
                    continue
                if line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 6:
                        code_to_name[parts[3]] = parts[4]
                    continue
                if line.startswith("#") and line[1:].isdigit():
                    flush_time()
                    current_time = int(line[1:])
                    continue
                if line[0] in "01xXzZ":
                    value, code = line[0].lower(), line[1:]
                elif line[0] in "bBrR":
                    parts = line.split()
                    if len(parts) != 2:
                        continue
                    value, code = parts[0][1:].lower(), parts[1]
                else:
                    continue
                name = code_to_name.get(code)
                if name not in by_name:
                    continue
                old = values.get(name)
                values[name] = value
                if old == value:
                    continue
                event_count += 1
                current_changed.add(name)
                if name == "sig_clk":
                    if old == "0" and value == "1":
                        current_clock_posedge = True
                    last_clock = value
                else:
                    non_clock_events += 1
                    transitions.write(json.dumps({"sequence": non_clock_events, "time": current_time, "signal_id": name, "value_4state": value}, sort_keys=True) + "\n")
                summary = summaries[name]
                summary["transitions"] += 1
                if any(bit in "xz" for bit in value):
                    summary["xz_transitions"] += 1
                if summary["first_time"] is None:
                    summary["first_time"] = current_time
                    summary["first_value"] = value
                if summary["first_known_time"] is None and known_bits(value, widths[name]) is not None:
                    summary["first_known_time"] = current_time
                summary["last_time"] = current_time
                summary["last_change_time"] = current_time
                summary["last_value"] = value
            flush_time()
        os.replace(temporary, transition_path)

        with archive.open(info) as raw:
            vcd_bytes, vcd_sha = hash_stream(raw)

    summary = {
        "schema": "node0004-v92b-family-causal-analysis-v1",
        "status": "EOF_REACHED",
        "source": {
            "container_path": args.return_zip.as_posix(),
            "container_bytes": archive_bytes,
            "container_sha256": archive_sha,
            "member": args.vcd_member,
            "member_bytes": vcd_bytes,
            "member_sha256": vcd_sha,
            "member_crc32": f"{info.CRC:08x}",
        },
        "timescale": timescale,
        "line_count": line_number,
        "event_count": event_count,
        "non_clock_event_count": non_clock_events,
        "last_sim_time": current_time,
        "catalog_count": len(by_name),
        "catalog_signal_ids": sorted(by_name),
        "signal_summaries": summaries,
        "owner_clock": {
            "posedge_count": clock_posedges,
            "first_posedge_time": first_owner_posedge,
            "last_posedge_time": last_owner_posedge,
        },
        "causal": {
            "first_state_progress_time": first_state_progress,
            "last_state_progress_time": last_state_progress,
            "first_fully_known_state_time": first_fully_known_state,
            "last_fully_known_state_time": last_fully_known_state,
            "ack_equation": "sig_public_ack == {!sig_row_full,!sig_col_full}",
            "ack_checks": ack_checks,
            "ack_mismatches": ack_mismatches,
            "first_ack_mismatch": first_ack_mismatch,
            "last_ack_mismatch": last_ack_mismatch,
            "fifo_activity_cycles": fifo_activity_cycles,
            "mem_request_accept_cycles": mem_request_accept_cycles,
            "wdata_accept_cycles": wdata_accept_cycles,
            "global_accept_cycles": global_accept_cycles,
            "counter_ranges": counter_ranges,
            "natural_terminal_witness_count": len(natural_terminal_times),
            "first_natural_terminal_time": natural_terminal_times[0] if natural_terminal_times else None,
            "last_natural_terminal_time": natural_terminal_times[-1] if natural_terminal_times else None,
            "final_values": values,
        },
        "claim_boundary": "Complete streaming summary of the declared 42-signal VCD cone; source-identity and expected-behavior adjudication remain separate.",
    }
    atomic_json(summary_path, summary)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise ValueError("base streaming analysis has not reached EOF")
    sequence = int(state.get("checkpoint_count", 0)) + 1
    checkpoint = {
        "schema": "server-tb-vcd-retention-analysis-v1",
        "kind": "family_causal_analysis_checkpoint",
        "sequence": sequence,
        "source_sha256": archive_sha,
        "member_sha256": vcd_sha,
        "lines_read": line_number,
        "events_read": event_count,
        "non_clock_events": non_clock_events,
        "last_sim_time": current_time,
        "status": "EOF_REACHED",
    }
    with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, sort_keys=True) + "\n")
    state["checkpoint_count"] = sequence
    state["family_causal_pass"] = {
        "status": "EOF_REACHED",
        "summary": summary_path.name,
        "transitions": transition_path.name,
        "member_sha256": vcd_sha,
        "non_clock_events": non_clock_events,
    }
    atomic_json(state_path, state)

    existing = report_path.read_text(encoding="utf-8") if report_path.exists() else "# Incremental diagnostic review\n"
    family = [
        "",
        "## Family causal streaming pass",
        "",
        f"- status: `EOF_REACHED`",
        f"- VCD timescale: `{timescale}`",
        f"- last simulation time: `{current_time}`",
        f"- owner-clock positive edges: `{clock_posedges}`",
        f"- non-clock transitions retained: `{non_clock_events}`",
        f"- ACK actual-driver equation mismatches: `{ack_mismatches}/{ack_checks}`",
        f"- FIFO activity cycles: `{fifo_activity_cycles}`",
        f"- memory-request accepts: `{mem_request_accept_cycles}`",
        f"- write-data accepts: `{wdata_accept_cycles}`",
        f"- natural-terminal witness cycles: `{len(natural_terminal_times)}`",
        "",
        "All declared non-clock transitions were retained without an event cap in `causal_transitions.jsonl`.",
        "",
    ]
    report_path.write_text(existing.rstrip() + "\n" + "\n".join(family), encoding="utf-8")
    print(json.dumps({"status": "EOF_REACHED", "summary": str(summary_path), "non_clock_events": non_clock_events, "last_sim_time": current_time}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
