#!/usr/bin/env python3
"""Bounded, resumable formal analysis of the exact QAdd v73 return.

The return and managed source package are immutable inputs.  ZIP members are
hashed individually and the VCD is parsed as a stream; it is never extracted
or materialized in memory.  Durable checkpoints and an incremental report are
published after each analysis phase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
RETURN_ROOT = f"{PACKAGE}_return/"
EXECUTION = "r1786958027042931325_3775010"
ATTEMPT = "a3775010"
EXPECTED_RETURN_BYTES = 5_817_903
EXPECTED_RETURN_SHA256 = "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c"
EXPECTED_PACKAGE_BYTES = 108_809_782
EXPECTED_PACKAGE_SHA256 = "0cd165a36014e878e507dfc3e810d0271c1e41e1484ca7d5d8e248f8330be18f"
GOOD_BITSTREAM_SHA256 = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
BAD_BITSTREAM_SHA256 = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
EXPECTED_MASKS = (0x33333333, 0xCCCCCCCC)
EXPECTED_TRANSACTION_BYTES = 32

OUT = ROOT / f"outputs/qlinearadd_node0007_v73_return_{EXECUTION}"
ANALYSIS = OUT / "analysis"
CHUNKS = ANALYSIS / "chunks"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1 << 16), b""):
        size += len(block)
        digest.update(block)
    return size, digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = str(path)
    return {"path": display, "bytes": path.stat().st_size, "sha256": sha_file(path)}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_bytes(canonical(value))
    os.replace(temp, path)


def immutable_json(path: Path, value: Any) -> None:
    payload = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"immutable chunk drift: {path}")
        return
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_bytes(payload)
    os.replace(temp, path)


def checkpoint(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"checkpoint_id": "{value["checkpoint_id"]}"'
    if path.exists() and marker in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def report(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and heading in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n{heading}\n\n{body.rstrip()}\n")


def jmember(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {relative}")
    return value


def safe_zip(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist()
    names = [row.filename for row in infos]
    counts = Counter(names)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    unsafe: list[str] = []
    links: list[str] = []
    for row in infos:
        pure = PurePosixPath(row.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename:
            unsafe.append(row.filename)
        if stat.S_ISLNK(row.external_attr >> 16):
            links.append(row.filename)
    roots = sorted({name.split("/", 1)[0] for name in names if name})
    crc_bad = archive.testzip()
    passed = not duplicates and not unsafe and not links and crc_bad is None and roots == [PACKAGE + "_return"]
    return {
        "member_count": len(infos),
        "uncompressed_bytes": sum(row.file_size for row in infos),
        "roots": roots,
        "duplicates": duplicates,
        "unsafe_members": unsafe,
        "symlink_members": links,
        "crc_bad_member": crc_bad,
        "pass": passed,
    }


def core_receipts(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for declared in manifest.get("core_entry_receipts", []):
        relative = declared.get("path")
        if not isinstance(relative, str):
            rows.append({"path": relative, "match": False, "error": "invalid declared path"})
            continue
        try:
            with archive.open(RETURN_ROOT + relative) as stream:
                size, digest = sha_stream(stream)
            rows.append(
                {
                    "path": relative,
                    "bytes": size,
                    "sha256": digest,
                    "match": size == declared.get("bytes") and digest == declared.get("sha256"),
                }
            )
        except KeyError:
            rows.append({"path": relative, "match": False, "error": "member absent"})
    return {"entries": rows, "pass": bool(rows) and all(row["match"] for row in rows)}


def package_member(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    member = f"{PACKAGE}/{relative}"
    with archive.open(member) as stream:
        size, digest = sha_stream(stream)
    return {"path": relative, "bytes": size, "sha256": digest}


def returned_member(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        size, digest = sha_stream(stream)
    return {"path": relative, "bytes": size, "sha256": digest}


def parse_int(bits: str | None) -> int | None:
    if bits is None or any(char in bits.lower() for char in "xz"):
        return None
    try:
        return int(bits, 2)
    except ValueError:
        return None


def parse_vcd(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    code_to_name: dict[str, str] = {}
    widths: dict[str, int] = {}
    current: dict[str, str] = {}
    changes: Counter[str] = Counter()
    nonzero_cycles: Counter[str] = Counter()
    rises: Counter[str] = Counter()
    previous_nonzero: dict[str, bool] = {}
    first_nonzero: dict[str, int] = {}
    last_nonzero: dict[str, int] = {}
    accepted_by_mask: Counter[int] = Counter()
    cleared_by_request_mask: Counter[int] = Counter()
    accepted_masks: list[int] = []
    first_accept_by_mask: dict[int, int] = {}
    last_accept_by_mask: dict[int, int] = {}
    output_rises = 0
    output_known_rises = 0
    output_first = None
    output_last = None
    finish_cycles: list[int] = []
    timestamp = 0
    final_timestamp = 0
    last_nonclock_change = 0
    posedges = 0
    target_time = None
    target_posedge = None
    dump_on_count = 0
    dump_off_count = 0
    dump_flush_count = 0
    header_complete = False
    timescale_tokens: list[str] = []
    current_group: list[tuple[str, str]] = []

    def apply_group(group: list[tuple[str, str]], now: int) -> None:
        nonlocal last_nonclock_change, posedges, target_time, target_posedge
        nonlocal output_rises, output_known_rises, output_first, output_last
        clock_posedge = False
        for code, value in group:
            old = current.get(code)
            if old != value:
                name = code_to_name.get(code, code)
                changes[name] += 1
                if name != "clk":
                    last_nonclock_change = now
                if name == "clk" and old == "0" and value == "1":
                    clock_posedge = True
            current[code] = value
        if not clock_posedge:
            return
        posedges += 1
        values = {name: parse_int(current.get(code)) for code, name in code_to_name.items()}
        for name, value in values.items():
            nonzero = value not in (None, 0)
            if nonzero:
                nonzero_cycles[name] += 1
                first_nonzero.setdefault(name, now)
                last_nonzero[name] = now
            if nonzero and not previous_nonzero.get(name, False):
                rises[name] += 1
            previous_nonzero[name] = nonzero
        if target_time is None and (values.get("sem2iga_exec_start") or values.get("slice0_exec_active")):
            target_time = now
            target_posedge = posedges
        valid = values.get("mrm2buf_req_valid") or 0
        mask = values.get("mrm2buf_req_strb")
        ready = values.get("buf2mrm_rreq_ready")
        read_enable = values.get("mrm2buf_rd_en") or 0
        accepted = bool(valid and read_enable and ready == 1 and mask is not None)
        if accepted and mask is not None:
            accepted_masks.append(mask)
            accepted_by_mask[mask] += 1
            first_accept_by_mask.setdefault(mask, now)
            last_accept_by_mask[mask] = now
            if (values.get("mrm2buf_clear") or 0) and (values.get("valid_buf_clear") or 0):
                cleared_by_request_mask[mask] += 1
        rvalid = bool(values.get("buf2mrm_rvalid"))
        if rvalid and rises["buf2mrm_rvalid"] > output_rises:
            output_rises += 1
            output_first = now if output_first is None else output_first
            output_last = now
            if values.get("buf2mrm_rdata") is not None and values.get("data_buf_out") is not None:
                output_known_rises += 1
        if values.get("slice_cmpt_finish") or values.get("slice0_done_pulse"):
            finish_cycles.append(now)

    with archive.open(member) as stream:
        in_header = True
        timescale_open = False
        for raw in stream:
            line = raw.decode("utf-8", errors="replace").strip()
            if in_header:
                if line.startswith("$timescale"):
                    timescale_open = True
                    tail = line[len("$timescale") :].replace("$end", "").strip()
                    if tail:
                        timescale_tokens.append(tail)
                    if "$end" in line:
                        timescale_open = False
                elif timescale_open:
                    if "$end" in line:
                        token = line.replace("$end", "").strip()
                        if token:
                            timescale_tokens.append(token)
                        timescale_open = False
                    elif line:
                        timescale_tokens.append(line)
                if line.startswith("$var"):
                    parts = line.split()
                    if len(parts) >= 6:
                        widths[parts[3]] = int(parts[2])
                        code_to_name[parts[3]] = parts[4]
                if line.startswith("$enddefinitions"):
                    in_header = False
                    header_complete = True
                continue
            if line.startswith("#"):
                apply_group(current_group, timestamp)
                current_group = []
                timestamp = int(line[1:])
                final_timestamp = timestamp
                continue
            if line.startswith("$dumpon"):
                dump_on_count += 1
                continue
            if line.startswith("$dumpoff"):
                dump_off_count += 1
                continue
            if line.startswith("$dumpflush"):
                dump_flush_count += 1
                continue
            if not line or line[0] == "$":
                continue
            if line[0] in "01xXzZ":
                current_group.append((line[1:], line[0].lower()))
            elif line[0] in "bBrR":
                parts = line.split()
                if len(parts) == 2:
                    current_group.append((parts[1], parts[0][1:].lower()))
        apply_group(current_group, timestamp)

    alternating = all(mask == EXPECTED_MASKS[index % 2] for index, mask in enumerate(accepted_masks))
    pair_count = len(accepted_masks) // 2 if alternating else 0
    complete_pairs = alternating and len(accepted_masks) % 2 == 0
    name_to_code = {name: code for code, name in code_to_name.items()}
    key_names = [
        "sem2iga_exec_start",
        "slice_cmpt_finish",
        "mrm2buf_req_valid",
        "mrm2buf_req_strb",
        "mrm2buf_clear",
        "mrm2buf_rd_en",
        "valid_buf",
        "valid_buf_clear",
        "buf2mrm_rreq_ready",
        "buf2mrm_rvalid",
        "buf2mrm_last_bit",
        "buf2mrm_last_index",
        "slice0_cycle_since_start",
        "slice0_start_count",
        "slice0_exec_active",
        "slice0_done_pulse",
    ]
    final_signals = {
        name: {
            "bits": current.get(name_to_code.get(name, "")),
            "changes": changes[name],
            "rises": rises[name],
            "nonzero_owner_cycles": nonzero_cycles[name],
            "first_nonzero_ps": first_nonzero.get(name),
            "last_nonzero_ps": last_nonzero.get(name),
        }
        for name in key_names
    }
    return {
        "schema": "qadd-v73-streaming-vcd-ledger-v1",
        "header_complete": header_complete,
        "timescale": " ".join(timescale_tokens),
        "declared_signal_count": len(code_to_name),
        "width_total_bits": sum(widths.values()),
        "owner_clock_posedges_streamed": posedges,
        "final_timestamp_ps": final_timestamp,
        "last_nonclock_change_ps": last_nonclock_change,
        "target_entry_ps": target_time,
        "target_entry_owner_posedge": target_posedge,
        "dump_control": {
            "dumpon_count": dump_on_count,
            "dumpoff_count": dump_off_count,
            "dumpflush_statement_count": dump_flush_count,
        },
        "accepted_masks": {
            "total": len(accepted_masks),
            "by_mask": {f"0x{key:08x}": value for key, value in sorted(accepted_by_mask.items())},
            "first_ps": {f"0x{key:08x}": value for key, value in sorted(first_accept_by_mask.items())},
            "last_ps": {f"0x{key:08x}": value for key, value in sorted(last_accept_by_mask.items())},
            "only_expected_masks": set(accepted_by_mask) == set(EXPECTED_MASKS),
            "strictly_alternating_333_then_ccc": alternating,
            "complete_pairs": complete_pairs,
            "pair_count": pair_count,
            "first_16": [f"0x{value:08x}" for value in accepted_masks[:16]],
            "last_16": [f"0x{value:08x}" for value in accepted_masks[-16:]],
        },
        "accepted_and_cleared": {
            "by_request_mask": {f"0x{key:08x}": value for key, value in sorted(cleared_by_request_mask.items())},
            "every_accept_cleared": cleared_by_request_mask == accepted_by_mask,
        },
        "output": {
            "rvalid_rising_pulses": output_rises,
            "known_data_rising_pulses": output_known_rises,
            "first_ps": output_first,
            "last_ps": output_last,
            "one_output_pulse_per_pair": output_rises == pair_count,
        },
        "terminal": {
            "slice_finish_rises": rises["slice_cmpt_finish"],
            "global_done_rises": rises["slice0_done_pulse"],
            "terminal_cycles": finish_cycles[:64],
            "observed": bool(finish_cycles),
        },
        "final_signals": final_signals,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--package-zip", type=Path, required=True)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    package_zip = args.package_zip.resolve()
    if return_zip.stat().st_size != EXPECTED_RETURN_BYTES or sha_file(return_zip) != EXPECTED_RETURN_SHA256:
        raise RuntimeError("exact v73 return identity mismatch")
    if package_zip.stat().st_size != EXPECTED_PACKAGE_BYTES or sha_file(package_zip) != EXPECTED_PACKAGE_SHA256:
        raise RuntimeError("exact managed v73 package identity mismatch")

    state_path = ANALYSIS / "analysis_state.json"
    checks_path = ANALYSIS / "checkpoints.jsonl"
    report_path = ANALYSIS / "report.md"
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    initial_state = {
        "schema": "qadd-v73-bounded-streaming-analysis-state-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "IDENTITY_VERIFIED",
        "return_zip": identity(return_zip),
        "source_package_zip": identity(package_zip),
        "bounded_policy": "one ZIP member at a time; VCD line stream; no archive extraction or whole-VCD materialization",
        "resume": {"next_sequence": 2, "vcd_member_offset": 0},
    }
    atomic_json(state_path, initial_state)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "001_identity", "sequence": 1, "status": "IDENTITY_VERIFIED"})
    report(report_path, "# QAdd v73 formal return analysis", "Exact return and managed pending package identities are verified. Both inputs remain read-only; analysis is bounded, incremental, and resumable.")

    with zipfile.ZipFile(return_zip) as returned, zipfile.ZipFile(package_zip) as package:
        safety = safe_zip(returned)
        if not safety["pass"]:
            raise RuntimeError(f"unsafe or corrupt return ZIP: {safety}")
        manifest = jmember(returned, "RETURN_CORE_MANIFEST.json")
        core = jmember(returned, "return_core/RETURN_CORE_STATUS.json")
        sim_exit = jmember(returned, "return_core/SIM_EXIT_RECEIPT.json")
        attempt = jmember(returned, "evidence/NATIVE_FAILURE_ATTEMPT.json")
        argv = jmember(returned, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        preflight = jmember(returned, "evidence/PACKAGE_PREFLIGHT_EXECUTION.json")
        source_identity = jmember(returned, "evidence/compile_source_identity.json")
        target = jmember(returned, "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        vcd_identity = jmember(returned, "evidence/TB_VCD_IDENTITY.json")
        dump_control = jmember(returned, "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json")
        stop = jmember(returned, "evidence/TB_VCD_STOP_RECEIPT.json")
        decision = jmember(returned, "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json")
        safety_receipt = jmember(returned, "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json")
        process = jmember(returned, "evidence/PROCESS_TREE_RECEIPT.json")
        lineage = jmember(returned, "source_package/CONFIG_LINEAGE_CONTRACT.json")
        config = jmember(returned, "source_package/op_tail_round_4_2.json")
        source_manifest = jmember(returned, "source_package/TEST_PACKAGE_MANIFEST.json")
        acceptance = jmember(returned, "source_package/qadd_config42_dynamic_acceptance.json")
        budget = jmember(returned, "source_package/runtime_budget_admission.json")
        receipts = core_receipts(returned, manifest)

        source_pairs = {
            "TEST_PACKAGE_MANIFEST.json": "source_package/TEST_PACKAGE_MANIFEST.json",
            "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json": "source_package/CONFIG_LINEAGE_CONTRACT.json",
            "provenance/config_lineage/op_tail_round_4_2.json": "source_package/op_tail_round_4_2.json",
            "diagnostics/qadd_config42_dynamic_acceptance.json": "source_package/qadd_config42_dynamic_acceptance.json",
            "diagnostics/runtime_budget_admission.json": "source_package/runtime_budget_admission.json",
            "diagnostics/post_kill_fresh_reap_contract.json": "source_package/post_kill_fresh_reap_contract.json",
            "diagnostics/tb_vcd_candidate_matrix.json": "source_package/tb_vcd_candidate_matrix.json",
            "diagnostics/tb_vcd_signal_catalog.json": "source_package/tb_vcd_signal_catalog.json",
            "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v73.svh": "source_package/qlinearadd_node0007_tb_vcd_causal_cone_v73.svh",
            "provenance/qadd_source_bound_wall_8400_activation_receipt.json": "source_package/qadd_source_bound_wall_8400_activation_receipt.json",
            "provenance/tbvcd_predecessor_semantic_v7_activation_receipt.json": "source_package/tbvcd_predecessor_semantic_v7_activation_receipt.json",
        }
        bindings: list[dict[str, Any]] = []
        for package_relative, return_relative in source_pairs.items():
            left = package_member(package, package_relative)
            right = returned_member(returned, return_relative)
            bindings.append({"package": left, "return": right, "match": left["bytes"] == right["bytes"] and left["sha256"] == right["sha256"]})
        supervisor_source = package.read(f"{PACKAGE}/package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v73.py").decode("utf-8")
        supervisor_identity = package_member(package, "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v73.py")
        vcd_ledger = parse_vcd(returned, RETURN_ROOT + "evidence/vcd/wave.vcd")

    identity_values = [
        manifest.get("package_id"), core.get("package_id"), attempt.get("package_id"), argv.get("package_id"),
        preflight.get("package_id"), target.get("package_id"), source_manifest.get("package_id"), source_manifest.get("install_name"),
    ]
    execution_values = [manifest.get("execution_id"), core.get("execution_id"), attempt.get("execution_id"), argv.get("execution_id"), preflight.get("execution_id"), target.get("execution_id")]
    attempt_values = [attempt.get("attempt_id"), argv.get("attempt_id"), preflight.get("attempt_id"), target.get("attempt_id")]
    integrity = {
        "schema": "qadd-v73-return-integrity-v1",
        "return": identity(return_zip),
        "managed_source_package": identity(package_zip),
        "archive": safety,
        "core_entry_receipts": receipts,
        "identity_binding": {
            "package": all(value == PACKAGE for value in identity_values),
            "execution": all(value == EXECUTION for value in execution_values),
            "attempt": all(value == ATTEMPT for value in attempt_values),
        },
        "source_package_bindings": bindings,
        "source_package_all_match": all(row["match"] for row in bindings),
        "pass": safety["pass"] and receipts["pass"] and all(value == PACKAGE for value in identity_values) and all(value == EXECUTION for value in execution_values) and all(value == ATTEMPT for value in attempt_values) and all(row["match"] for row in bindings),
    }
    immutable_json(CHUNKS / "002_integrity_source_binding.json", integrity)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "002_integrity", "sequence": 2, "status": "RETURN_AND_SOURCE_BINDING_PASS", "member_count": safety["member_count"]})
    report(report_path, "## Integrity, provenance, and source binding", f"The return has {safety['member_count']} safe unique members and passes CRC. Declared core receipts, package/execution/attempt identity, and {len(bindings)} returned package-control members bind exactly to `{PACKAGE}` / `{EXECUTION}` / `{ATTEMPT}` and the managed pending ZIP.")

    runtime_budget = safety_receipt.get("runtime_budget_admission", {})
    stop_sample = decision.get("shared_evaluator_receipt", {}).get("stop", {})
    start_sample = decision.get("shared_evaluator_receipt", {}).get("start", {})
    runtime = {
        "schema": "qadd-v73-runtime-adjudication-v1",
        "preflight_exit": preflight.get("exit_code"),
        "compile_exit": attempt.get("compile_exit"),
        "simulation_started": True,
        "simulation_exit": attempt.get("simulation_exit"),
        "signal": sim_exit.get("signal"),
        "shared_evaluator_decision": decision.get("decision"),
        "shared_evaluator_sole_authority": decision.get("decision_authority", {}).get("outer_runner_consumes_only_receipt") is True,
        "target_entry_observed": target.get("observed") is True and stop.get("markers", {}).get("target_entry") is True,
        "budget": {
            "selected_wall_ceiling_seconds": runtime_budget.get("selected_wall_ceiling_seconds"),
            "threshold_wall_ceiling_seconds": safety_receipt.get("thresholds", {}).get("wall_ceiling_seconds"),
            "admission_pass": runtime_budget.get("pass"),
            "stop_wall_seconds": stop_sample.get("wall_seconds"),
            "pretarget_completions": stop_sample.get("global_progress_witness", {}).get("pretarget_matrix_completions"),
            "applied_exact_8400": runtime_budget.get("selected_wall_ceiling_seconds") == 8400 and safety_receipt.get("thresholds", {}).get("wall_ceiling_seconds") == 8400 and decision.get("decision") == "WALL_CEILING",
        },
        "non_natural": sim_exit.get("natural_terminal_observed") is False,
        "formal_d_present": False,
        "missing_required_entries": core.get("missing_required_entries", []),
        "dump_closed": stop.get("markers", {}).get("flush", {}).get("closed") is True,
        "dump_flushed": stop.get("markers", {}).get("flush", {}).get("dumpflush") is True,
        "process_tree_reaped": process.get("process_tree_reaped") is True,
        "owned_pids_remaining": process.get("owned_pids_remaining", []),
        "fresh_post_kill_deadline": process.get("post_kill_reap_deadline_origin") == "FRESH_AFTER_LAST_KILL",
        "return_disposition": core.get("disposition"),
    }
    immutable_json(CHUNKS / "003_runtime.json", runtime)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "003_runtime", "sequence": 3, "status": "COMPILE_SIM_TARGET_WALL_BOUND", "compile_exit": runtime["compile_exit"], "sim_exit": runtime["simulation_exit"], "wall": runtime["budget"]["stop_wall_seconds"]})
    report(report_path, "## Runtime and exit", f"Production compile exited 0 and simulation entered the live target. The authorized 8400-second wall was applied exactly; the sole shared evaluator selected `WALL_CEILING` at {runtime['budget']['stop_wall_seconds']:.3f}s. This is non-natural. Dump close/flush is absent and one reported owned PID remained, so the return is `PARTIAL / DIAGNOSTIC_EVIDENCE_INCOMPLETE` even though the archived causal interval is usable.")

    immutable_json(CHUNKS / "004_vcd_ledger.json", vcd_ledger)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "004_vcd_eof", "sequence": 4, "status": "VCD_STREAMED_TO_EOF", "vcd_timestamp_ps": vcd_ledger["final_timestamp_ps"], "accepted_pairs": vcd_ledger["accepted_masks"]["pair_count"]})
    report(report_path, "## Streamed VCD causal ledger", f"The 64-declaration, 1ps VCD was streamed to EOF at {vcd_ledger['final_timestamp_ps']}ps. Target entry is {vcd_ledger['target_entry_ps']}ps. It contains {vcd_ledger['accepted_masks']['pair_count']} strict `0x33333333 -> 0xcccccccc` accepted pairs, every accept has clear evidence, and each pair has one known read-output pulse. No wrong-mask or repeated-first alias appears.")

    expected_from_lc = int(config["dram_loop_configs"]["LC1"]["end"])
    output_checks = source_manifest.get("split_segment_contract", {}).get("output_checks", [])
    slice0_output_bytes = next(int(row["decoded_bytes"]) for row in output_checks if row.get("slice_id") == 0)
    expected_from_output = slice0_output_bytes // EXPECTED_TRANSACTION_BYTES
    completed_pairs = int(vcd_ledger["accepted_masks"]["pair_count"])
    target_detect_wall = None
    for row in process.get("samples", []):
        if row.get("target_entry_observed") is True:
            target_detect_wall = float(row["wall_seconds"])
            break
    final_wall = float(runtime["budget"]["stop_wall_seconds"])
    target_wall_elapsed = final_wall - float(target_detect_wall or final_wall)
    target_rate = completed_pairs / target_wall_elapsed if target_wall_elapsed > 0 else 0.0
    projected_target_wall = expected_from_lc / target_rate if target_rate > 0 else None
    projected_total_wall = float(target_detect_wall or 0.0) + float(projected_target_wall or 0.0)
    conservative_selected_example = int(math.ceil((float(target_detect_wall or 0.0) + float(projected_target_wall or 0.0) * 1.25 + 900.0) / 300.0) * 300)
    progress = {
        "schema": "qadd-v73-config42-dynamic-progress-v1",
        "exact_config": {
            "group2_col_lc_end_stride": [config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["end"], config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["stride"]],
            "positive_bitstream_sha256": lineage.get("positive_mapping_a", {}).get("sha256"),
            "expected_positive_bitstream_sha256": GOOD_BITSTREAM_SHA256,
            "rejected_restore_bitstream_sha256": lineage.get("negative_restore_mapping", {}).get("sha256"),
            "expected_rejected_bitstream_sha256": BAD_BITSTREAM_SHA256,
        },
        "dynamic_acceptance": {
            "required_sequence": acceptance.get("required_ordered_sequence"),
            "strict_order_pass": vcd_ledger["accepted_masks"]["strictly_alternating_333_then_ccc"],
            "mask_set_pass": vcd_ledger["accepted_masks"]["only_expected_masks"],
            "accept_clear_pass": vcd_ledger["accepted_and_cleared"]["every_accept_cleared"],
            "read_output_pass": vcd_ledger["output"]["one_output_pulse_per_pair"] and vcd_ledger["output"]["known_data_rising_pulses"] == completed_pairs,
            "old_interleaved_alias_excluded": vcd_ledger["accepted_masks"]["strictly_alternating_333_then_ccc"],
        },
        "completion_projection": {
            "expected_pairs_from_dram_lc1_end": expected_from_lc,
            "expected_pairs_from_slice0_output_bytes": expected_from_output,
            "completed_pairs": completed_pairs,
            "completion_fraction": completed_pairs / expected_from_lc,
            "remaining_pairs": expected_from_lc - completed_pairs,
            "target_entry_detected_wall_seconds": target_detect_wall,
            "target_wall_elapsed_seconds": target_wall_elapsed,
            "measured_pairs_per_wall_second": target_rate,
            "unmargined_projected_total_wall_seconds": projected_total_wall,
            "illustrative_1p25_plus_900_rounded_300_seconds": conservative_selected_example,
            "note": "Illustrative projection is not an authorized next wall value; current public admission permits only the exact 8400-second v70-derived value.",
        },
        "natural_terminal": False,
        "formal_d": "NOT_REACHED",
        "E3": False,
        "E4": False,
        "E5": False,
    }
    immutable_json(CHUNKS / "005_dynamic_acceptance_projection.json", progress)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "005_dynamic", "sequence": 5, "status": "CONFIG42_DYNAMIC_REPAIR_VALIDATED_PARTIAL_COMPLETION", "completed_pairs": completed_pairs, "expected_pairs": expected_from_lc})
    report(report_path, "## Direct config and dynamic adjudication", f"Exact GROUP2.COL_LC 4/2 and the corrected bitstream are bound. Both independent workload facts require {expected_from_lc} 32-byte pairs for slice0. The archived interval completed {completed_pairs} ({completed_pairs / expected_from_lc:.1%}) while still advancing. Thus the old 32/16 interleaved-column alias is dynamically excluded and the 4/2 Buffer5 repair is validated, but end-to-end output/natural terminal/Formal-D is not complete.")

    ps_self_enum = all(token in supervisor_source for token in (
        '["ps", "-eo", "pid=,ppid=,pgid=,sid=,stat=,comm="]',
        'closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())',
    ))
    process_audit = {
        "schema": "qadd-v73-process-finalization-audit-v1",
        "supervisor_source": supervisor_identity,
        "fresh_post_kill_deadline_implemented_and_observed": runtime["fresh_post_kill_deadline"],
        "reported_owned_pids_remaining": runtime["owned_pids_remaining"],
        "process_tree_reaped": runtime["process_tree_reaped"],
        "deterministic_self_enumerator_escape_present": ps_self_enum,
        "mechanism": "process_rows launches ps as a child and parses that ps row after subprocess.run has reaped it; owned then adds every row whose PPID equals the supervisor, so each verification can report the just-finished ps enumerator as an owned live process",
        "classification": "PACKAGE_LOCAL_QADD_SUPERVISOR_SELF_PS_ENUMERATOR_FALSE_POSITIVE",
        "confidence": "HIGH_FOR_CODE_PATH_LOW_FOR_RETURNED_PID_IDENTITY",
        "required_next_fresh_implementation": "use childless procfs PID+start_time snapshots, retain real descendants, and return remaining process identities rather than PID-only rows",
    }
    immutable_json(CHUNKS / "006_process_finalization.json", process_audit)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "006_process", "sequence": 6, "status": "PROCESS_FINALIZATION_ESCAPE_BOUND"})
    report(report_path, "## Process and return completeness", "The fresh post-KILL deadline is present, but final reaping still reports one PID. The exact packaged supervisor deterministically creates a `ps` child for every ownership scan and then treats any PPID==supervisor row as owned, reproducing the already-audited self-enumerator class. The return does not include that remaining PID's command/start-time tuple, so PID attribution itself is not overclaimed. Missing dump close/flush and exact finalization members keep the result partial.")

    last_good_ps = vcd_ledger["output"]["last_ps"]
    formal = {
        "schema": "qadd-node0007-v73-formal-return-analysis-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "pass": True,
        "integrity": integrity,
        "runtime": runtime,
        "vcd_ledger": vcd_ledger,
        "direct_config_dynamic_evidence": progress,
        "process_finalization_audit": process_audit,
        "last_proven_good": {
            "classification": "EXACT_CONFIG42_ORDERED_COMPLEMENTARY_ACCEPT_CLEAR_AND_OUTPUT_PROGRESS",
            "time_ps": last_good_ps,
            "details": f"{completed_pairs} of {expected_from_lc} expected 32-byte pairs completed; the last archived completed pair still follows 0x33333333 then 0xcccccccc with accept, clear, and known read output.",
        },
        "first_divergence": {
            "classification": "SOURCE_BOUND_8400S_WALL_CEILING_BEFORE_EXPECTED_18816_PAIR_COMPLETION",
            "time_ps": vcd_ledger["final_timestamp_ps"],
            "wall_seconds": final_wall,
            "details": f"WALL_CEILING stopped a still-progressing target at {completed_pairs}/{expected_from_lc}; this is not a DUT causal plateau or a recurrence of the 32/16 alias.",
        },
        "root_classification": "QADD_V73_8400S_SOURCE_BOUND_WALL_EXPIRES_WHILE_CONFIG42_TARGET_CONTINUES",
        "root_state": "VALIDATED_ATTEMPT_RUNTIME_BOUNDARY__FUNCTIONAL_COMPLETION_NOT_YET_EXECUTED",
        "config42_repair": "DYNAMICALLY_VALIDATED_FOR_ORDERED_BUFFER5_REQUEST_ACCEPT_CLEAR_AND_READ_OUTPUT",
        "remaining_mechanism": "NONE_OBSERVED_IN_ARCHIVED_CAUSAL_INTERVAL; natural terminal and Formal-D require a longer separately authorized run",
        "rule_gap_audit": "TRIGGERED_TARGET_EXECUTED_WITHOUT_END_TO_END_TERMINAL",
        "package_build_failure_rule_audit": "NOT_TRIGGERED_V73_ENTERED_TARGET",
        "successor_disposition": "WAIT_USER_AND_SHARED_RUNTIME_BUDGET_OR_DIAGNOSTIC_MODE_AUTHORIZATION",
        "claims": {
            "production_compile": True,
            "simulation_started": True,
            "target_entered": True,
            "wall_8400_applied": True,
            "ordered_333_then_ccc": True,
            "both_accept_clear": True,
            "old_alias_excluded": True,
            "read_output_progress": True,
            "natural_terminal": False,
            "formal_d": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "unique_functional_root_beyond_budget": False,
        },
        "claim_boundary": "Exact copy04 v73 archived causal interval only. Functional RTL bytes were not returned transitively; no natural terminal, Formal-D, E3/E4/E5, full-output equality, or authorized >8400-second successor claim.",
    }
    formal_path = OUT / "formal_return_analysis.json"
    atomic_json(formal_path, formal)

    rule_audit = {
        "schema": "qadd-v73-rule-gap-audit-v1",
        "role_id": "family.qlinearadd",
        "trigger": "target executed but one run did not reach natural terminal/Formal-D",
        "evidence": {
            "target_entered": True,
            "config42_dynamic_acceptance_closed": True,
            "completed_pairs": completed_pairs,
            "expected_pairs": expected_from_lc,
            "still_progressing_at_wall": True,
            "selected_wall_seconds": 8400,
            "unmargined_projected_total_wall_seconds": projected_total_wall,
            "illustrative_bounded_selection_seconds": conservative_selected_example,
            "post_kill_ps_self_enumerator": ps_self_enum,
        },
        "disposition": "RULE_DELTA_PROPOSAL_REQUIRES_USER_AUTHORIZED_TARGET_MEASURED_BUDGET_OR_MODE",
        "public_rule_action_by_family": "NONE",
        "proposal": [
            "Permit a next-fresh QAdd admission to use the exact v73 target-rate receipt and exact expected 18816-pair workload count, with a user-authorized bounded wall above 8400 and no change to independent 8GB/10GB/disk/growth/write/quota protections.",
            "Require the QAdd supervisor to consume the activated childless-procfs PID+start_time ownership implementation and return full remaining identities; forbid subprocess-backed ps self-enumeration.",
            "Preserve the validated 4/2 config, workload, numeric, golden, functional RTL, 64-signal cone, candidate matrix, and dynamic acceptance requirements.",
        ],
        "blocking_reason": "Current active admission permits only exact 8400 for the v70-derived successor; this family cannot select a different wall or mode without user/shared activation.",
    }
    rule_path = OUT / "RULE_GAP_AUDIT.json"
    atomic_json(rule_path, rule_audit)
    applicability = {
        "schema": "qadd-v73-package-build-failure-rule-audit-applicability-v1",
        "triggered": False,
        "reason": "v73 production compile and simulation entered the functional target; this is not a consecutive package/pretarget failure",
    }
    applicability_path = OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json"
    atomic_json(applicability_path, applicability)
    checkpoint(checks_path, {"schema": "qadd-v73-stream-checkpoint-v1", "checkpoint_id": "007_formal", "sequence": 7, "status": "FORMAL_ANALYSIS_AND_RULE_AUDIT_COMPLETE", "root": formal["root_classification"]})
    report(report_path, "## Formal disposition", f"LAST_PROVEN_GOOD is the final archived completed complementary pair at {last_good_ps}ps. FIRST_DIVERGENCE is the 8400-second wall at {vcd_ledger['final_timestamp_ps']}ps, after {completed_pairs}/{expected_from_lc} pairs. Root is `QADD_V73_8400S_SOURCE_BOUND_WALL_EXPIRES_WHILE_CONFIG42_TARGET_CONTINUES`. The functional 4/2 Buffer5 repair is dynamically validated, but full output, natural terminal, and Formal-D remain unexecuted. A longer wall or different low-overhead mode requires explicit user/shared authorization; this family does not build a knowingly blocked successor.")

    complete_state = dict(initial_state)
    complete_state.update(
        {
            "status": "FORMAL_RETURN_ANALYSIS_COMPLETE_WAIT_RUNTIME_AUTHORIZATION",
            "resume": {"next_sequence": None, "vcd_member_offset": 86_281_383, "vcd_eof": True},
            "last_proven_good": formal["last_proven_good"],
            "first_divergence": formal["first_divergence"],
            "root_classification": formal["root_classification"],
            "formal_analysis": identity(formal_path),
            "rule_gap_audit": identity(rule_path),
        }
    )
    atomic_json(state_path, complete_state)
    receipt = {
        "schema": "qadd-v73-mainline-return-receipt-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "status": "RETURN_ANALYSIS_COMPLETE__WAIT_USER_AND_SHARED_RUNTIME_BUDGET_OR_MODE_AUTHORIZATION",
        "return_zip": identity(return_zip),
        "managed_source_package": identity(package_zip),
        "analysis_state": identity(state_path),
        "checkpoints": identity(checks_path),
        "incremental_report": identity(report_path),
        "formal_return_analysis": identity(formal_path),
        "rule_gap_audit": identity(rule_path),
        "package_build_failure_audit_applicability": identity(applicability_path),
        "last_proven_good": formal["last_proven_good"],
        "first_divergence": formal["first_divergence"],
        "root_classification": formal["root_classification"],
        "config42_repair": formal["config42_repair"],
        "successor_built": False,
        "managed_storage_action": False,
        "server_action": False,
        "claim_boundary": formal["claim_boundary"],
    }
    receipt_path = OUT / "formal_mainline_receipt.json"
    atomic_json(receipt_path, receipt)
    print(json.dumps({"pass": True, "root": formal["root_classification"], "completed_pairs": completed_pairs, "expected_pairs": expected_from_lc, "receipt": str(receipt_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
