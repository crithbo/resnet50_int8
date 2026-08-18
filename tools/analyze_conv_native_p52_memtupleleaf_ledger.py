#!/usr/bin/env python3
"""One-pass bounded event ledger for the exact native-Conv p52 VCD."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_conv_native_p49_tbvcdrt2_return import normalized_scope, vcd_header_map
from analyze_conv_native_p51_metaidxcone_return import parse_value


PACKAGE = "r5_n4_0cc_p52_memtupleleaf"
EXECUTION = "r1786793357121273848_2914398"
PREFIX = f"{PACKAGE}_return/"
RETURN = Path(r"C:\Users\15383\Downloads\r5_n4_0cc_p52_memtupleleaf_r1786793357121273848_2914398_return.zip")
OUT = ROOT / f"outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_return_analysis_{EXECUTION}"
VCD = PREFIX + "runs/c0/native_mse4_causal.vcd"
CONTRACT = PREFIX + "evidence/server_tb_vcd_bounded_causal_cone_contract.json"


LEAF_IDS = {
    "sig_mse_mem_queue_idx", "sig_mse_mem_queue_tag", "sig_mse_mem_queue_bp_pre",
    "sig_mse_mem_idx_mode", "sig_mse_mem_idx_keep_last_index", "sig_mse_mem_idx_enable",
    "sig_mse_mem_idx_buffer_mode", "sig_mse_mem_idx_keep_mode", "sig_mse_mem_idx_cons_mode",
    "sig_mem_idx_valid_bit_unmasked", "sig_mem_idx_last_bit_unmasked", "sig_mem_idx_same_bit_unmasked",
    "sig_mem_idx_last_index", "sig_mem_idx_gotten_bit", "sig_mem_idx_same_bit_keep_mask",
    "sig_mem_idx_same_bit_masked", "sig_mem_idx_same_gotten_mask", "sig_mem_idx_valid_bit_operands_mask",
    "sig_mem_idx_last_bit_operands_mask", "sig_mem_idx_valid_bit_masked", "sig_mem_idx_last_bit_masked",
    "sig_idx_split_fifo_empty", "sig_idx_split_fifo_full", "sig_mem_idx_fifo_last_bit",
    "sig_mem_idx_fifo_last_index", "sig_mse_mem_fifo_idx", "sig_mem_idx_fifo_valid_bit",
    "sig_mem_idx_fifo_valid_bit_masked", "sig_mem_idx_fifo_last_bit_masked",
    "sig_mem_idx_fifo_last_index_masked", "sig_mse_mem_fifo_idx_masked", "sig_mem_idx_queue_bp_pre",
    "sig_mem_idx_split_fifo_wr_en", "sig_mem_idx_bp_pre_keep_mask", "sig_mem_idx_bp_pre_mask",
    "sig_mem_buffer_idx_last_index", "sig_mem_buffer_idx_last_bit", "sig_mem_idx_split_fifo0_count",
    "sig_mem_idx_split_fifo1_count", "sig_mem_idx_split_fifo2_count",
}

EVENT_IDS = {
    "sig_clk", "sig_mse_enable", "sig_wr_data_chl_req_valid", "sig_wr_data_chl_req_ready",
    "sig_wr_data_chl_req_tsf_size", "sig_wr_chl_queue_wr_en", "sig_wr_chl_queue_rd_en",
    "sig_wr_chl_queue_empty", "sig_wr_chl_queue_full", "sig_wr_data_chl_prepared_data_wr_hs",
    "sig_wr_data_chl_prepared_data_rd_hs", "sig_mse_buf_spatial_size", "sig_mem_all_idx_matched",
    "sig_mem_ag_idx_queue_wr_en", "sig_mem_ag_idx_queue_rd_en", "sig_mem_ag_idx_queue_empty",
    "sig_mem_ag_idx_queue_full", "sig_mem_idx_queue_count", "sig_buf_ag_ob_wr_en",
    "sig_buf_ag_ob_rd_en", "sig_buf_ag_ob_empty", "sig_buf_ag_ob_full", "sig_slice_cmpt_finish_2",
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def known_int(value: str | None) -> int | None:
    if not isinstance(value, str) or any(char in value.lower() for char in "xz"):
        return None
    return int(value, 2)


def bit(value: str | None, index: int) -> int | None:
    number = known_int(value)
    return None if number is None else (number >> index) & 1


def scalar(value: str | None) -> bool:
    return value == "1"


def summarize(values: dict[str, str], ids: set[str]) -> dict[str, Any]:
    return {
        signal_id: {
            "bits": values.get(signal_id),
            "integer": known_int(values.get(signal_id)),
        }
        for signal_id in sorted(ids)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN)
    parser.add_argument("--analysis-dir", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.analysis_dir.resolve()
    state_path = out / "analysis_state.json"
    checkpoints_path = out / "checkpoints.jsonl"
    report_path = out / "report.md"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("bounded streaming scan has not reached EOF")

    with zipfile.ZipFile(args.return_zip.resolve()) as archive:
        contract = json.loads(archive.read(CONTRACT))
        header, timescale = vcd_header_map(archive, VCD)
        code_to_id: dict[str, str] = {}
        for signal in contract.get("signals", []):
            matches = header.get(normalized_scope(str(signal.get("exact_hierarchy", ""))), [])
            for match in matches:
                code_to_id[match["code"]] = str(signal.get("signal_id"))
        required = LEAF_IDS | EVENT_IDS
        missing = sorted(required - set(code_to_id.values()))
        if missing:
            raise RuntimeError(f"required p52 signals absent from VCD: {missing}")

        values: dict[str, str] = {}
        current_time = 0
        changed: set[str] = set()
        transitions: dict[str, int] = defaultdict(int)
        first_transition: dict[str, int] = {}
        last_transition: dict[str, int] = {}
        value_histograms: dict[str, Counter[str]] = defaultdict(Counter)
        events: dict[str, list[int]] = defaultdict(list)
        tuple_snapshots: list[dict[str, Any]] = []
        split_snapshots: list[dict[str, Any]] = []
        focus_rows: list[dict[str, Any]] = []
        last_effective_nonclock = 0
        last_effective_ids: set[str] = set()
        target_time = 2_445_780_625
        focus_start = 2_446_350_000
        focus_end = 2_446_700_000
        analysis_end = 2_450_000_000
        definitions = True

        def record_event(name: str) -> None:
            events[name].append(current_time)

        def flush() -> None:
            nonlocal changed, last_effective_nonclock, last_effective_ids
            if changed - {"sig_clk"}:
                last_effective_nonclock = current_time
                last_effective_ids = set(changed - {"sig_clk"})
            # The proven p51/p52 causal episode ends near 2.446 ms.  Continue
            # parsing every later transition through EOF for final-state and
            # last-change integrity, but do not execute the 40-signal
            # per-owner-edge accounting across tens of millions of idle clocks.
            if current_time > analysis_end:
                changed = set()
                return
            if current_time < target_time or current_time % 1250 != 625:
                changed = set()
                return
            for signal_id in LEAF_IDS:
                value_histograms[signal_id][values.get(signal_id, "ABSENT")] += 1

            tuple_write = scalar(values.get("sig_mem_ag_idx_queue_wr_en")) and not scalar(values.get("sig_mem_ag_idx_queue_full"))
            tuple_read = scalar(values.get("sig_mem_ag_idx_queue_rd_en")) and not scalar(values.get("sig_mem_ag_idx_queue_empty"))
            metadata = scalar(values.get("sig_wr_data_chl_req_valid")) and scalar(values.get("sig_wr_data_chl_req_ready"))
            prepared = scalar(values.get("sig_wr_data_chl_prepared_data_wr_hs"))
            if tuple_write:
                record_event("memory_tuple_write")
            if tuple_read:
                record_event("memory_tuple_read")
            if metadata:
                record_event("metadata_request_accept")
            if prepared:
                record_event("prepared_write_accept")
            if scalar(values.get("sig_wr_data_chl_prepared_data_rd_hs")):
                record_event("prepared_read_accept")

            split_activity = False
            split_row: dict[str, Any] = {"time_ps": current_time, "ports": {}}
            for port in range(3):
                split_write = bit(values.get("sig_mem_idx_split_fifo_wr_en"), port) == 1 and bit(values.get("sig_idx_split_fifo_full"), port) == 0
                split_read = bit(values.get("sig_mem_idx_queue_bp_pre"), port) == 1 and bit(values.get("sig_idx_split_fifo_empty"), port) == 0
                if split_write:
                    record_event(f"split{port}_write")
                if split_read:
                    record_event(f"split{port}_read")
                split_activity = split_activity or split_write or split_read
                split_row["ports"][str(port)] = {
                    "write": split_write,
                    "read": split_read,
                    "count": known_int(values.get(f"sig_mem_idx_split_fifo{port}_count")),
                    "raw_valid": bit(values.get("sig_mem_idx_valid_bit_unmasked"), port),
                    "raw_last": bit(values.get("sig_mem_idx_last_bit_unmasked"), port),
                    "raw_same": bit(values.get("sig_mem_idx_same_bit_unmasked"), port),
                    "gotten": bit(values.get("sig_mem_idx_gotten_bit"), port),
                    "same_gotten_mask": bit(values.get("sig_mem_idx_same_gotten_mask"), port),
                    "fifo_valid_masked": bit(values.get("sig_mem_idx_fifo_valid_bit_masked"), port),
                    "queue_ready": bit(values.get("sig_mem_idx_queue_bp_pre"), port),
                    "keep_release": bit(values.get("sig_mem_idx_bp_pre_keep_mask"), port),
                }
            if split_activity:
                split_snapshots.append(split_row)
            if tuple_write:
                tuple_snapshots.append({
                    "time_ps": current_time,
                    "split": split_row["ports"],
                    "memory_queue_count": known_int(values.get("sig_mem_idx_queue_count")),
                    "buffer_last_bit": bit(values.get("sig_mem_buffer_idx_last_bit"), 0),
                    "buffer_last_index": known_int(values.get("sig_mem_buffer_idx_last_index")),
                    "leaf_state": summarize(values, LEAF_IDS),
                })
            if focus_start <= current_time <= focus_end and (changed - {"sig_clk"} or tuple_write or tuple_read or split_activity or metadata or prepared):
                focus_rows.append({
                    "time_ps": current_time,
                    "events": {
                        "tuple_write": tuple_write,
                        "tuple_read": tuple_read,
                        "metadata": metadata,
                        "prepared": prepared,
                        "split": split_row["ports"],
                    },
                    "changed": sorted(changed - {"sig_clk"}),
                    "leaf_state": summarize(values, LEAF_IDS),
                })
            changed = set()

        with archive.open(VCD) as stream:
            for raw in stream:
                line = raw.decode("utf-8", "strict")
                text = line.strip()
                if definitions:
                    if text.startswith("$enddefinitions"):
                        definitions = False
                    continue
                if text.startswith("#") and text[1:].isdigit():
                    flush()
                    current_time = int(text[1:])
                    continue
                parsed = parse_value(line)
                if parsed is None:
                    continue
                code, value = parsed
                signal_id = code_to_id.get(code)
                if signal_id is None:
                    continue
                if values.get(signal_id) != value:
                    changed.add(signal_id)
                    if signal_id != "sig_clk":
                        transitions[signal_id] += 1
                        first_transition.setdefault(signal_id, current_time)
                        last_transition[signal_id] = current_time
                values[signal_id] = value
            flush()

    counts = {name: len(times) for name, times in events.items()}
    ledger = {
        "schema": "conv-native-p52-direct-memory-tuple-leaf-ledger-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "timescale": timescale,
        "catalog_mapped": len(code_to_id),
        "scan_status": "EOF_REACHED",
        "final_timestamp_ps": state.get("last_sim_time"),
        "last_effective_nonclock_change_ps": last_effective_nonclock,
        "last_effective_nonclock_signal_ids": sorted(last_effective_ids),
        "event_counts": counts,
        "event_times_ps": dict(events),
        "tuple_snapshots": tuple_snapshots,
        "split_snapshots": split_snapshots,
        "focus_window": {"start_ps": focus_start, "end_ps": focus_end, "rows": focus_rows},
        "leaf_transition_summary": {
            signal_id: {
                "transitions": transitions.get(signal_id, 0),
                "first_ps": first_transition.get(signal_id),
                "last_ps": last_transition.get(signal_id),
                "value_histogram_at_owner_edges_after_target": dict(value_histograms.get(signal_id, {})),
                "final": values.get(signal_id),
            }
            for signal_id in sorted(LEAF_IDS)
        },
        "final_leaf_state": summarize(values, LEAF_IDS),
        "claim_boundary": "Exact source-bound p52 VCD event ledger only; root adjudication requires actual RTL/config conjunction.",
        "pass": True,
        "errors": [],
    }
    ledger_path = out / "direct_leaf_ledger.json"
    ledger_path.write_text(canonical(ledger), encoding="utf-8", newline="\n")

    checkpoint_lines = checkpoints_path.read_text(encoding="utf-8").splitlines()
    if not any("P52_DIRECT_LEAF_LEDGER_EOF" in line for line in checkpoint_lines):
        checkpoint = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1",
            "seq": len(checkpoint_lines),
            "event": "P52_DIRECT_LEAF_LEDGER_EOF",
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "last_effective_nonclock": last_effective_nonclock,
            "event_counts": counts,
            "ledger_sha256": sha(ledger_path),
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(checkpoint_lines))) + 1
    state["direct_leaf_ledger"] = {"path": ledger_path.name, "sha256": sha(ledger_path), "status": "EOF_REACHED"}
    state_path.write_text(canonical(state), encoding="utf-8", newline="\n")
    with report_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "\n## p52 direct-leaf ledger\n\n"
            f"- mapped catalog / VCD status: `{len(code_to_id)} / EOF_REACHED`\n"
            f"- tuple writes/reads: `{counts.get('memory_tuple_write', 0)} / {counts.get('memory_tuple_read', 0)}`\n"
            f"- metadata/prepared accepts: `{counts.get('metadata_request_accept', 0)} / {counts.get('prepared_write_accept', 0)}`\n"
            f"- split writes: `{[counts.get(f'split{port}_write', 0) for port in range(3)]}`; reads: `{[counts.get(f'split{port}_read', 0) for port in range(3)]}`\n"
            f"- last effective non-clock change: `{last_effective_nonclock} ps`\n"
        )
    print(json.dumps({
        "pass": True,
        "ledger": str(ledger_path),
        "event_counts": counts,
        "tuple_snapshots": len(tuple_snapshots),
        "split_snapshots": len(split_snapshots),
        "focus_rows": len(focus_rows),
        "last_effective_nonclock": last_effective_nonclock,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
