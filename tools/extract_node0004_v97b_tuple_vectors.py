#!/usr/bin/env python3
"""Stream the v97 VCD packed tuple vectors and derive the three input leaves.

Production VCS normalizes ``$dumpvars(...packed[i])`` requests into one VCD
variable for the complete packed vector.  The package catalog intentionally
named the selected leaves, so this pass binds those leaf identities to the
same-attempt packed variables without loading the VCD into memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
RETURN_ROOT = f"{PACKAGE}_return/"
VCD_MEMBER = RETURN_ROOT + "waveforms/causal_cone.vcd"
ANALYSIS = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853"
STREAM = ANALYSIS / "streaming"
QUEUE_SUFFIX = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Memory_AG_Idx_Queue."
)

# base RTL name, leaf catalog stem, complete packed width, bits per input
SPECS = (
    ("mem_idx_valid_bit_unmasked", "raw_valid", 3, 1),
    ("mem_idx_last_bit_unmasked", "raw_last", 3, 1),
    ("mem_idx_same_bit_unmasked", "raw_same", 3, 1),
    ("mem_idx_last_index", "raw_last_index", 12, 4),
    ("mem_idx_gotten_bit", "gotten", 3, 1),
    ("mem_idx_same_gotten_mask", "same_gotten_mask", 3, 1),
    ("mem_idx_valid_bit_masked", "valid_masked", 3, 1),
    ("mem_idx_split_fifo_wr_en", "split_wr", 3, 1),
    ("idx_split_fifo_empty", "split_empty", 3, 1),
    ("idx_split_fifo_full", "split_full", 3, 1),
    ("mem_idx_fifo_valid_bit_masked", "fifo_valid_masked", 3, 1),
    ("mem_idx_fifo_last_bit_masked", "fifo_last_masked", 3, 1),
    ("mem_idx_fifo_last_index_masked", "fifo_last_index", 12, 4),
    ("mse_mem_queue_bp_pre", "source_bp", 3, 1),
    ("mem_idx_queue_bp_pre", "queue_bp", 3, 1),
    ("mem_idx_bp_pre_keep_mask", "keep_mask", 3, 1),
    ("mem_idx_bp_pre_mask", "bp_mask", 3, 1),
)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def normalize(value: str, width: int) -> str:
    value = value.lower()
    if len(value) < width:
        fill = value[0] if value and value[0] in "xz" else "0"
        value = fill * (width - len(value)) + value
    return value[-width:]


def input_slice(value: str, input_index: int, bits: int) -> str:
    # Packed declarations are [2:0] or [2:0][3:0].  Input zero occupies the
    # least-significant/right-most bit or four-bit group in VCD text.
    right = input_index * bits
    left = right + bits
    reversed_bits = value[::-1]
    return reversed_bits[right:left][::-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    args = parser.parse_args()
    source = args.return_zip.resolve(strict=True)
    summary_path = ANALYSIS / "streaming_summary.json"
    existing = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_member = existing["vcd"]

    vector_path = STREAM / "tuple_vector_transitions.jsonl"
    leaf_path = STREAM / "tuple_leaf_transitions.jsonl"
    vector_tmp = vector_path.with_name(f".{vector_path.name}.tmp.{os.getpid()}")
    leaf_tmp = leaf_path.with_name(f".{leaf_path.name}.tmp.{os.getpid()}")
    target_by_hierarchy = {QUEUE_SUFFIX + base: (base, stem, width, bits) for base, stem, width, bits in SPECS}

    code_to_spec: dict[str, tuple[str, str, int, int]] = {}
    scopes: list[str] = []
    vector_values: dict[str, str] = {}
    leaf_values: dict[str, str] = {}
    vector_counts = {base: 0 for base, _, _, _ in SPECS}
    leaf_counts = {f"sig_mem_i{i}_{stem}_xmrfix": 0 for _, stem, _, _ in SPECS for i in range(3)}
    current_time = 0
    last_time = 0
    line_count = 0
    vector_sequence = 0
    leaf_sequence = 0
    digest = hashlib.sha256()
    member_bytes = 0

    with zipfile.ZipFile(source) as archive:
        info = archive.getinfo(VCD_MEMBER)
        with archive.open(info) as raw, vector_tmp.open("w", encoding="utf-8", newline="\n") as vector_out, leaf_tmp.open("w", encoding="utf-8", newline="\n") as leaf_out:
            for payload in raw:
                digest.update(payload)
                member_bytes += len(payload)
                line_count += 1
                line = payload.decode("utf-8", errors="strict").strip()
                if not line:
                    continue
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 4:
                        scopes.append(parts[2])
                    continue
                if line.startswith("$upscope"):
                    if scopes:
                        scopes.pop()
                    continue
                if line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 6:
                        hierarchy = ".".join([*scopes, parts[4]])
                        spec = target_by_hierarchy.get(hierarchy)
                        if spec is not None:
                            code_to_spec[parts[3]] = spec
                    continue
                if line.startswith("#") and line[1:].isdigit():
                    current_time = int(line[1:])
                    last_time = current_time
                    continue
                if line[0] in "01xXzZ":
                    value, code = line[0].lower(), line[1:]
                elif line[0] in "bB":
                    parts = line.split()
                    if len(parts) != 2:
                        continue
                    value, code = parts[0][1:].lower(), parts[1]
                else:
                    continue
                spec = code_to_spec.get(code)
                if spec is None:
                    continue
                base, stem, width, bits = spec
                value = normalize(value, width)
                if vector_values.get(base) == value:
                    continue
                vector_values[base] = value
                vector_sequence += 1
                vector_counts[base] += 1
                vector_out.write(json.dumps({
                    "sequence": vector_sequence,
                    "time": current_time,
                    "rtl_vector": base,
                    "value_4state": value,
                    "width_bits": width,
                }, sort_keys=True) + "\n")
                for input_index in range(3):
                    signal_id = f"sig_mem_i{input_index}_{stem}_xmrfix"
                    leaf_value = input_slice(value, input_index, bits)
                    if leaf_values.get(signal_id) == leaf_value:
                        continue
                    leaf_values[signal_id] = leaf_value
                    leaf_sequence += 1
                    leaf_counts[signal_id] += 1
                    leaf_out.write(json.dumps({
                        "sequence": leaf_sequence,
                        "signal_id": signal_id,
                        "source_packed_vector": base,
                        "source_select": f"[{input_index}]",
                        "time": current_time,
                        "value_4state": leaf_value,
                    }, sort_keys=True) + "\n")

    os.replace(vector_tmp, vector_path)
    os.replace(leaf_tmp, leaf_path)
    actual_sha = digest.hexdigest()
    errors: list[str] = []
    if member_bytes != expected_member["bytes"]:
        errors.append("VCD byte identity mismatch")
    if actual_sha != expected_member["sha256"]:
        errors.append("VCD SHA-256 identity mismatch")
    if len(code_to_spec) != len(SPECS):
        errors.append(f"packed vector catalog multiplicity:{len(code_to_spec)}/{len(SPECS)}")
    if set(vector_values) != {row[0] for row in SPECS}:
        errors.append("one or more packed vectors have no VCD value")

    result = {
        "claim_boundary": "Exact same-attempt packed-vector transitions and deterministic SystemVerilog packed-select leaf derivation; functional classification remains family-owned.",
        "errors": errors,
        "last_timestamp": last_time,
        "leaf_final_values": leaf_values,
        "leaf_transition_counts": leaf_counts,
        "leaf_transition_path": str(leaf_path),
        "member": VCD_MEMBER,
        "member_bytes": member_bytes,
        "member_sha256": actual_sha,
        "package_id": PACKAGE,
        "pass": not errors,
        "schema": "node0004-v97b-packed-tuple-vector-derivation-v1",
        "source_return": existing["source"],
        "vcd_line_count": line_count,
        "vector_codes": {code: spec[0] for code, spec in sorted(code_to_spec.items())},
        "vector_final_values": vector_values,
        "vector_transition_counts": vector_counts,
        "vector_transition_path": str(vector_path),
    }
    atomic_json(ANALYSIS / "tuple_vector_derivation.json", result)

    checkpoint_path = STREAM / "checkpoints.jsonl"
    checkpoint_kind = "family_v97b_packed_tuple_leaf_derivation"
    prior = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    state_path = STREAM / "analysis_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if f'"kind": "{checkpoint_kind}"' not in prior:
        sequence = int(state.get("checkpoint_count", 0)) + 1
        row = {
            "kind": checkpoint_kind,
            "leaf_events": leaf_sequence,
            "member_sha256": actual_sha,
            "pass": not errors,
            "schema": "server-tb-vcd-retention-analysis-v1",
            "sequence": sequence,
            "status": "PACKED_VECTOR_LEAVES_DERIVED",
            "vector_events": vector_sequence,
        }
        with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        state["checkpoint_count"] = sequence
    state["packed_tuple_derivation"] = {
        "leaf_events": leaf_sequence,
        "pass": not errors,
        "receipt": "../tuple_vector_derivation.json",
        "vector_events": vector_sequence,
    }
    atomic_json(state_path, state)
    with (STREAM / "report.md").open("a", encoding="utf-8", newline="\n") as report:
        report.write(
            "\n## Packed tuple vector derivation\n\n"
            f"- production VCS packed vectors bound: `{len(code_to_spec)}/{len(SPECS)}`\n"
            f"- vector transitions: `{vector_sequence}`\n"
            f"- derived leaf transitions: `{leaf_sequence}`\n"
            f"- same VCD identity: `{'PASS' if not errors else 'FAIL'}`\n"
        )
    print(json.dumps({"leaf_events": leaf_sequence, "pass": not errors, "receipt": str(ANALYSIS / "tuple_vector_derivation.json"), "vector_events": vector_sequence}, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
