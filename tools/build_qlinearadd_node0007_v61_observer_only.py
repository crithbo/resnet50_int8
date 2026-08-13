#!/usr/bin/env python3
"""Build the QLinearAdd node0007 v61 observer-only wide-causal package.

The source of truth is the exact v60 pending ZIP.  This builder changes only
the package identity and observer/runtime-return surfaces; workload, numeric,
golden and functional-RTL payloads remain frozen.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD_ID = "r5_qadd_n7_tailround_lanephase_v60_fsdbq"
NEW_ID = "r5_qadd_n7_tailround_lanephase_v61_obswide"
FAMILY = "qlinearadd_node0007"
BASE_EPOCH = "observer-only-wide-causal-v1"
FIX_EPOCH = "observer-only-post-sim-conjunction-fix-v1"
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
OLD_ZIP = PENDING / f"{OLD_ID}.zip"
RELEASE = ROOT / "outputs/qlinearadd_node0007_v61_observer_only_release"
BUILD = RELEASE / "build"
TREE = BUILD / NEW_ID
ZIP = BUILD / f"{NEW_ID}.zip"
RTL = ROOT / "NDP_copy01/rtl"
REFERENCE = ROOT / "outputs/conv_node0004_v89b_observerwide_release1/build/r5_n4_hw_v89b_obswide"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def identity(path: Path, base: Path = ROOT) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def safe_extract(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    resolved = target.resolve()
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v60 source ZIP CRC failure")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"unsafe ZIP member: {info.filename}")
            destination = (target / Path(*member.parts)).resolve()
            if resolved not in destination.parents and destination != resolved:
                raise RuntimeError(f"ZIP member escapes extraction root: {info.filename}")
        archive.extractall(target)


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json":
            result[path.relative_to(root).as_posix()] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha(path),
            }
    return result


def strip_retired_dump_metadata(value: Any) -> Any:
    """Remove predecessor-only binary-dump metadata before adding current fields."""
    retired = ("waveform", "fsdb", "vpd", "vcd", "fst", "portable")
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if any(token in str(key).lower() for token in retired):
                continue
            blob = json.dumps(item, ensure_ascii=False, sort_keys=True).lower()
            if isinstance(item, str) and any(token in blob for token in retired):
                continue
            cleaned[key] = strip_retired_dump_metadata(item)
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            blob = json.dumps(item, ensure_ascii=False, sort_keys=True).lower()
            if any(token in blob for token in retired):
                continue
            cleaned_list.append(strip_retired_dump_metadata(item))
        return cleaned_list
    return value


def tree_identity(root: Path, excluded: set[str] | None = None) -> dict[str, tuple[int, str]]:
    excluded = excluded or set()
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, sha(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    }


def declaration(source_path: str, name: str) -> dict[str, Any]:
    relative = source_path.removeprefix("rtl/")
    path = RTL / relative
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [
        (number, line)
        for number, line in enumerate(lines, 1)
        if re.search(rf"\b{re.escape(name)}\b", line)
        and re.search(r"\b(input|output|wire|reg|logic)\b", line)
        and not line.lstrip().startswith("//")
    ]
    if not hits:
        raise RuntimeError(f"declaration not found: {source_path}:{name}")
    line_number, line = hits[0]
    span = line.strip()
    symbol = sha_bytes(f"{source_path}:{line_number}:{name}:{span}".encode("utf-8"))[:24]
    return {
        "source_path": source_path,
        "source_sha256": sha(path),
        "declaration_span_sha256": sha_bytes(span.encode("utf-8")),
        "symbol_id": f"sym_{symbol}",
    }


def signal_templates() -> list[dict[str, Any]]:
    buffer_path = "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
    buffer_prefix = (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0]."
        "u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster."
        "BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    )
    slice_prefix = (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice"
    )
    rows = [
        ("clk", "clk", buffer_path, f"{buffer_prefix}.clk", 1, ["clock"]),
        ("rst_n", "rst_n", buffer_path, f"{buffer_prefix}.rst_n", 1, ["reset"]),
        ("slice_rst", "slice_rst", buffer_path, f"{buffer_prefix}.slice_rst", 1, ["reset", "internal_clear"]),
        ("exec_start", "sem2iga_exec_start", "rtl/Slice/Slice_cdc.sv", f"{slice_prefix}.sem2iga_exec_start", 1, ["stage"]),
        ("slice_finish", "slice_cmpt_finish", "rtl/Slice/Slice_cdc.sv", f"{slice_prefix}.slice_cmpt_finish", 1, ["terminal", "finish"]),
        ("arm_req_valid", "arm2buf_req_valid", buffer_path, f"{buffer_prefix}.arm2buf_req_valid", 8, ["source", "producer", "request", "selected_bank"]),
        ("arm_req_rw", "arm2buf_req_rw", buffer_path, f"{buffer_prefix}.arm2buf_req_rw", 1, ["selected_port"]),
        ("arm_req_addr", "arm2buf_req_addr", buffer_path, f"{buffer_prefix}.arm2buf_req_addr", 2, ["selected_lane"]),
        ("arm_clear", "arm2buf_clear", buffer_path, f"{buffer_prefix}.arm2buf_clear", 8, ["internal_clear"]),
        ("arm_force_clear", "arm2buf_force_clear", buffer_path, f"{buffer_prefix}.arm2buf_force_clear", 8, ["internal_clear"]),
        ("arm_wvalid", "arm2buf_wvalid", buffer_path, f"{buffer_prefix}.arm2buf_wvalid", 1, ["producer", "valid"]),
        ("arm_wdata", "arm2buf_wdata", buffer_path, f"{buffer_prefix}.arm2buf_wdata", 256, ["wdata"]),
        ("mrm_req_valid", "mrm2buf_req_valid", buffer_path, f"{buffer_prefix}.mrm2buf_req_valid", 8, ["source", "request", "selected_bank"]),
        ("mrm_req_rw", "mrm2buf_req_rw", buffer_path, f"{buffer_prefix}.mrm2buf_req_rw", 1, ["selected_port"]),
        ("mrm_req_addr", "mrm2buf_req_addr", buffer_path, f"{buffer_prefix}.mrm2buf_req_addr", 2, ["selected_lane"]),
        ("mrm_req_strb", "mrm2buf_req_strb", buffer_path, f"{buffer_prefix}.mrm2buf_req_strb", 32, ["selected_lane"]),
        ("mrm_clear", "mrm2buf_clear", buffer_path, f"{buffer_prefix}.mrm2buf_clear", 8, ["internal_clear"]),
        ("mrm_wvalid", "mrm2buf_wvalid", buffer_path, f"{buffer_prefix}.mrm2buf_wvalid", 1, ["producer", "valid"]),
        ("mrm_wdata", "mrm2buf_wdata", buffer_path, f"{buffer_prefix}.mrm2buf_wdata", 256, ["wdata"]),
        ("arm_wr_en", "arm2buf_wr_en", buffer_path, f"{buffer_prefix}.arm2buf_wr_en", 8, ["queue_enqueue", "accept"]),
        ("arm_rd_en", "arm2buf_rd_en", buffer_path, f"{buffer_prefix}.arm2buf_rd_en", 8, ["queue_dequeue", "accept"]),
        ("mrm_wr_en", "mrm2buf_wr_en", buffer_path, f"{buffer_prefix}.mrm2buf_wr_en", 8, ["queue_enqueue", "accept"]),
        ("mrm_rd_en", "mrm2buf_rd_en", buffer_path, f"{buffer_prefix}.mrm2buf_rd_en", 8, ["queue_dequeue", "accept"]),
        ("buf_wr_en", "buf_wr_en", buffer_path, f"{buffer_prefix}.buf_wr_en", 8, ["queue_enqueue"]),
        ("buf_rd_en", "buf_rd_en", buffer_path, f"{buffer_prefix}.buf_rd_en", 8, ["queue_dequeue"]),
        ("buf_wr_addr", "buf_wr_addr", buffer_path, f"{buffer_prefix}.buf_wr_addr", 2, ["selected_port"]),
        ("buf_rd_addr", "buf_rd_addr", buffer_path, f"{buffer_prefix}.buf_rd_addr", 2, ["selected_port"]),
        ("valid_buf", "valid_buf", buffer_path, f"{buffer_prefix}.valid_buf", 128, ["queue_count", "queue_full", "queue_empty", "valid", "internal_state"]),
        ("valid_wr_en", "valid_buf_wr_en", buffer_path, f"{buffer_prefix}.valid_buf_wr_en", 8, ["queue_enqueue", "internal_state"]),
        ("valid_in", "valid_buf_in", buffer_path, f"{buffer_prefix}.valid_buf_in", 32, ["valid", "internal_state"]),
        ("valid_in_strb", "valid_buf_in_strb", buffer_path, f"{buffer_prefix}.valid_buf_in_strb", 32, ["selected_lane", "internal_state"]),
        ("valid_clear", "valid_buf_clear", buffer_path, f"{buffer_prefix}.valid_buf_clear", 8, ["internal_clear"]),
        ("valid_clr_mask", "valid_buf_clr_mask", buffer_path, f"{buffer_prefix}.valid_buf_clr_mask", 32, ["internal_clear", "selected_lane"]),
        ("valid_clr_addr", "valid_buf_clr_addr", buffer_path, f"{buffer_prefix}.valid_buf_clr_addr", 16, ["internal_clear", "selected_port"]),
        ("mrm_r_bank_ready", "buf2mrm_rreq_bank_ready", buffer_path, f"{buffer_prefix}.buf2mrm_rreq_bank_ready", 8, ["ready", "internal_match"]),
        ("arm_r_bank_ready", "buf2arm_rreq_bank_ready", buffer_path, f"{buffer_prefix}.buf2arm_rreq_bank_ready", 8, ["ready", "internal_match"]),
        ("mrm_w_bank_ready", "buf2mrm_wreq_bank_ready", buffer_path, f"{buffer_prefix}.buf2mrm_wreq_bank_ready", 8, ["ready", "internal_match"]),
        ("arm_w_bank_ready", "buf2arm_wreq_bank_ready", buffer_path, f"{buffer_prefix}.buf2arm_wreq_bank_ready", 8, ["ready", "internal_match"]),
        ("mrm_req_ready", "buf2mrm_req_ready", buffer_path, f"{buffer_prefix}.buf2mrm_req_ready", 1, ["ready", "backpressure"]),
        ("mrm_rreq_ready", "buf2mrm_rreq_ready", buffer_path, f"{buffer_prefix}.buf2mrm_rreq_ready", 1, ["ready", "accept", "backpressure"]),
        ("arm_req_ready", "buf2arm_req_ready", buffer_path, f"{buffer_prefix}.buf2arm_req_ready", 1, ["ready", "backpressure"]),
        ("arm_rreq_ready", "buf2arm_rreq_ready", buffer_path, f"{buffer_prefix}.buf2arm_rreq_ready", 1, ["ready", "accept", "backpressure"]),
        ("buf_wreq_ready", "buf_wreq_ready", buffer_path, f"{buffer_prefix}.buf_wreq_ready", 1, ["ready", "accept", "backpressure"]),
        ("buf_rreq_ready", "buf_rreq_ready", buffer_path, f"{buffer_prefix}.buf_rreq_ready", 1, ["ready", "accept", "backpressure"]),
        ("mrm_rvalid", "buf2mrm_rvalid", buffer_path, f"{buffer_prefix}.buf2mrm_rvalid", 1, ["valid", "output"]),
        ("arm_rvalid", "buf2arm_rvalid", buffer_path, f"{buffer_prefix}.buf2arm_rvalid", 1, ["valid", "output"]),
        ("mrm_rdata", "buf2mrm_rdata", buffer_path, f"{buffer_prefix}.buf2mrm_rdata", 256, ["output", "formal_d"]),
        ("data_out", "data_buf_out", buffer_path, f"{buffer_prefix}.data_buf_out", 256, ["output", "internal_state"]),
    ]
    result: list[dict[str, Any]] = []
    for short, name, source_path, expression, width, roles in rows:
        binding = declaration(source_path, name)
        result.append(
            {
                **binding,
                "signal_id": f"sig_{short}",
                "exact_hierarchy": f"tb_NDP_Top_new_phy.{expression}",
                "connection": expression,
                "target_module": Path(source_path).stem,
                "width_bits": width,
                "owner_clock_signal_id": "sig_clk",
                "owner_reset_signal_id": "sig_rst_n",
                "roles": roles,
                "source_binding": "ACTUAL_SOURCE_NET",
                "derived_expected_equation": False,
                "observer_drives_dut": False,
            }
        )
    return result


def observer_source(signals: list[dict[str, Any]]) -> str:
    ports = []
    declarations = []
    comparisons = []
    assignments = []
    sensitivity = []
    bindings = []
    for signal in signals:
        sid = signal["signal_id"]
        width = signal["width_bits"]
        vector = "" if width == 1 else f"[{width - 1}:0] "
        ports.append(f"    input wire {vector}{sid}")
        declarations.append(f"  reg {vector}prev_{sid};")
        comparisons.extend(
            [
                f"      if (force_all || {sid} !== prev_{sid}) begin",
                "        $fdisplay(qow_fd, \"{\\\"record_type\\\":\\\"EVENT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\""
                + sid
                + "\\\",\\\"width_bits\\\":"
                + str(width)
                + ",\\\"value_4state\\\":\\\"%b\\\"}\", qow_package, qow_execution, qow_attempt, qow_seq, qow_time_ps, "
                + sid
                + ");",
                "        qow_seq = qow_seq + 1;",
                "      end",
            ]
        )
        assignments.append(f"      prev_{sid} = {sid};")
        sensitivity.append(sid)
        bindings.append(f"    .{sid}({signal['connection']})")
    joined_ports = ",\n".join(ports)
    joined_bindings = ",\n".join(bindings)
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "// QAdd v61 read-only actual-net transition observer.",
            "module codex_qadd_observer_wide_v61(",
            joined_ports,
            ");",
            "  integer qow_fd; integer qow_enabled; integer qow_have_previous;",
            "  longint unsigned qow_seq; longint unsigned qow_time_ps; longint unsigned qow_clock_count;",
            "  string qow_path; string qow_package; string qow_execution; string qow_attempt;",
            *declarations,
            "  task automatic qow_capture(input integer force_all);",
            "    begin",
            "      qow_time_ps = $rtoi($realtime * 1000.0);",
            *comparisons,
            *assignments,
            "      qow_have_previous = 1;",
            "      if ((qow_seq & 4095) == 0) $fflush(qow_fd);",
            "    end",
            "  endtask",
            "  initial begin",
            "    qow_enabled = $test$plusargs(\"CODEX_QADD_OBSERVER_WIDE\");",
            "    qow_seq = 0; qow_clock_count = 0; qow_have_previous = 0;",
            "    if (qow_enabled) begin",
            "      if (!$value$plusargs(\"CODEX_OBSERVER_CHUNK=%s\", qow_path)) $fatal(1, \"missing observer chunk\");",
            "      if (!$value$plusargs(\"CODEX_PACKAGE_ID=%s\", qow_package)) $fatal(1, \"missing package identity\");",
            "      if (!$value$plusargs(\"CODEX_EXECUTION_ID=%s\", qow_execution)) $fatal(1, \"missing execution identity\");",
            "      if (!$value$plusargs(\"CODEX_ATTEMPT_ID=%s\", qow_attempt)) $fatal(1, \"missing attempt identity\");",
            "      qow_fd = $fopen(qow_path, \"w\");",
            "      if (!qow_fd) $fatal(1, \"cannot open observer chunk\");",
            "      #0; qow_capture(1); $fflush(qow_fd);",
            "    end",
            "  end",
            f"  always @({' or '.join(sensitivity)}) if (qow_enabled && qow_have_previous) qow_capture(0);",
            "  always @(posedge sig_clk) if (qow_enabled) begin",
            "    qow_clock_count = qow_clock_count + 1;",
            "    if ((qow_clock_count & 262143) == 0) begin",
            "      qow_time_ps = $rtoi($realtime * 1000.0);",
            "      $fdisplay(qow_fd, \"{\\\"record_type\\\":\\\"HEARTBEAT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\"__heartbeat__\\\",\\\"width_bits\\\":1,\\\"value_4state\\\":\\\"0\\\"}\", qow_package, qow_execution, qow_attempt, qow_seq, qow_time_ps);",
            "      qow_seq = qow_seq + 1; $fflush(qow_fd);",
            "      $display(\"CODEX_OBSERVER_SIM_TIME_V1 sim_time=%0d\", qow_time_ps);",
            "    end",
            "  end",
            "  final if (qow_enabled && qow_fd) begin $fflush(qow_fd); $fclose(qow_fd); end",
            "endmodule",
            "`ifndef CODEX_QADD_OBSERVER_FOCUS",
            "bind tb_NDP_Top_new_phy codex_qadd_observer_wide_v61 codex_qadd_observer_wide_v61_inst(",
            joined_bindings,
            ");",
            "`endif",
            "",
        ]
    )


def public_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in signal.items() if key != "connection"} for signal in signals]


def build_contract(signals: list[dict[str, Any]]) -> dict[str, Any]:
    public = public_signals(signals)
    by_role: dict[str, list[str]] = {}
    for signal in public:
        for role in signal["roles"]:
            by_role.setdefault(role, []).append(signal["signal_id"])
    roles = [
        "clock", "reset", "stage", "source", "producer", "queue_enqueue",
        "queue_dequeue", "queue_count", "queue_full", "queue_empty", "request",
        "valid", "ready", "accept", "backpressure", "selected_port",
        "selected_bank", "selected_lane", "internal_match", "internal_state",
        "internal_clear", "output", "wdata", "terminal", "finish", "formal_d",
    ]
    coverage = [
        {"role": role, "disposition": "covered", "signal_ids": by_role[role]}
        for role in roles
    ]
    ids = {signal["signal_id"] for signal in public}
    def select(*wanted: str) -> list[str]:
        result = [f"sig_{name}" for name in wanted if f"sig_{name}" in ids]
        if not result:
            raise RuntimeError(f"empty observation selection: {wanted}")
        return result
    observations = [
        {
            "observation_id": "obs_buffer5_request_decode",
            "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE",
            "predicate": "actual Buffer5 producer/request decode and ping-pong address selection",
            "signal_ids": select("exec_start", "arm_req_valid", "arm_req_rw", "arm_req_addr", "arm_wvalid", "mrm_req_valid", "mrm_req_rw", "mrm_req_addr", "mrm_req_strb"),
        },
        {
            "observation_id": "obs_selected_port_lane_ready",
            "layer": "FIRST_DIVERGENCE_CURRENT",
            "predicate": "actual selected-port bank/lane readiness and read acceptance",
            "signal_ids": select("mrm_r_bank_ready", "arm_r_bank_ready", "mrm_w_bank_ready", "arm_w_bank_ready", "mrm_rreq_ready", "arm_rreq_ready", "buf_rreq_ready", "mrm_rd_en", "arm_rd_en"),
        },
        {
            "observation_id": "obs_read_data_terminal",
            "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE",
            "predicate": "actual read-valid/data propagation and tail terminal precursor",
            "signal_ids": select("mrm_rvalid", "arm_rvalid", "mrm_rdata", "data_out", "slice_finish"),
        },
        {
            "observation_id": "obs_valid_hold_clear",
            "layer": "STATE_HOLD_CLEAR",
            "predicate": "actual bank/lane valid residency, producer writes and all clear causes",
            "signal_ids": select("valid_buf", "valid_wr_en", "valid_in", "valid_in_strb", "valid_clear", "valid_clr_mask", "valid_clr_addr", "arm_clear", "arm_force_clear", "mrm_clear", "buf_wr_en"),
        },
    ]
    candidate_names = [
        "residual_lane_blocks_next_arm_write",
        "producer_never_attempts_second_write",
        "selected_pingpong_port_decode_mismatch",
        "selected_bank_mask_mismatch",
        "required_lane_never_valid",
        "clear_releases_valid_before_read",
        "other_port_ready_only",
        "read_accept_never_asserts",
        "read_accept_occurs_without_result",
        "tail_terminal_not_propagated",
        "legacy_selected_ready_mismatch",
    ]
    ordered = sorted(item["observation_id"] for item in observations)
    candidates = [
        {
            "candidate_id": name,
            "signature": {
                observation: bool(index & (1 << bit))
                for bit, observation in enumerate(ordered)
            },
        }
        for index, name in enumerate(candidate_names)
    ]
    prefix = f"{NEW_ID}_return/"
    helper = ROOT / "tools/server_post_sim_return.py"
    helper_data = helper.read_bytes()
    return {
        "schema": "server-observer-only-wide-causal-contract-v1",
        "profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "activation_epoch": BASE_EPOCH,
        "rule_ids": [
            "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
            "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
        ],
        "package_id": NEW_ID,
        "family": FAMILY,
        "execution": {
            "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "runtime_supervision": "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT",
            "repeat_safe_exact_owned_reset": True,
            "atomic_unique_return": True,
            "waveform_writer": None,
        },
        "budget": {
            "observer_evidence_soft_limit_bytes": 100000000,
            "observer_evidence_hard_limit_bytes": None,
            "formal_return_hard_limit_bytes": None,
            "event_count_cap": None,
            "byte_cap": None,
            "sampling": False,
            "truncation": False,
            "size_based_deletion": False,
        },
        "signals": public,
        "role_coverage": coverage,
        "boundary_observations": observations,
        "candidates": candidates,
        "all_coobservable_candidates_aggregated": True,
        "event_recording": {
            "format": "JSONL",
            "fields": ["record_type", "package_id", "execution_id", "attempt_id", "seq", "sim_time", "timescale", "signal_id", "width_bits", "value_4state"],
            "ordered_transitions": True,
            "end_state_required": True,
            "periodic_sim_time_heartbeat": True,
            "partial_exit_live_records": True,
            "event_cap": None,
            "byte_cap": None,
            "sampling": False,
            "truncation": False,
        },
        "package_members": {
            "runner": f"{NEW_ID}/PREPARE_AND_RUN.sh",
            "manifest": f"{NEW_ID}/TEST_PACKAGE_MANIFEST.json",
            "return_allowlist": f"{NEW_ID}/RETURN_ALLOWLIST.json",
            "contract": f"{NEW_ID}/contracts/server_observer_only_wide_causal_contract.json",
            "observer": f"{NEW_ID}/tb_probe/qadd_observer_wide_impl.svh",
            "parser": f"{NEW_ID}/package_tools/qadd_observer_event_parser.py",
            "runtime_supervisor": f"{NEW_ID}/package_tools/server_observer_runtime_supervision.py",
            "post_sim_helper": f"{NEW_ID}/package_tools/server_post_sim_return.py",
            "post_sim_request": f"{NEW_ID}/contracts/server_post_sim_return_request.json",
        },
        "return_members": {
            "actual_argv": prefix + "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
            "sim_exit": prefix + "evidence/SIM_EXIT_RECEIPT.json",
            "process_tree": prefix + "evidence/PROCESS_TREE_RECEIPT.json",
            "sim_time_heartbeat": prefix + "evidence/SIM_TIME_HEARTBEAT.json",
            "signal_catalog": prefix + "evidence/OBSERVER_SIGNAL_CATALOG.json",
            "chunk_index": prefix + "evidence/OBSERVER_EVENT_INDEX.json",
            "chunk_prefix": prefix + "observer/chunks/",
            "decision": prefix + "evidence/OBSERVER_DECISION.json",
            "return_manifest": prefix + "RETURN_CORE_MANIFEST.json",
            "compile_core_when_not_started": [
                prefix + "evidence/compile_rootcause/COMPILE_CORE.json",
                prefix + "evidence/compile_rootcause/compile_first_error.txt",
            ],
        },
        "post_sim_historical_compatibility_exemption": {
            "schema": "observer-only-post-sim-helper-exemption-v1",
            "canonical_source_path": "tools/server_post_sim_return.py",
            "canonical_helper_bytes": len(helper_data),
            "canonical_helper_sha256": sha_bytes(helper_data),
            "member_path": f"{NEW_ID}/package_tools/server_post_sim_return.py",
            "request_member": f"{NEW_ID}/contracts/server_post_sim_return_request.json",
            "inert_literal_tokens": [".fsdb", ".vpd"],
            "waveform_discovery_disposition": "OMITTED_OR_NULL_ONLY",
        },
        "claim_boundary": "Wide source-bound actual-signal observer transport for the frozen Buffer5 tail-round selected-port/lane-readiness boundary; no production result claim.",
    }


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8").replace(OLD_ID, NEW_ID)
    text = re.sub(r'^query_(?:helper|profile|source_report)=.*\n', '', text, flags=re.M)
    declaration = (
        'observer_parser="$package_root/package_tools/qadd_observer_event_parser.py"\n'
        'observer_contract="$package_root/contracts/server_observer_only_wide_causal_contract.json"\n'
        'observer_supervisor="$package_root/package_tools/server_observer_runtime_supervision.py"\n'
        'observer_impl="$package_root/tb_probe/qadd_observer_wide_impl.svh"\n'
        'observer_return_manifest="$package_root/package_tools/qadd_observer_return_manifest.py"\n'
    )
    anchor = 'post_sim_request="$package_root/contracts/server_post_sim_return_request.json"\n'
    if text.count(anchor) != 2:
        raise RuntimeError(f"observer declaration anchor count={text.count(anchor)}")
    text = text.replace(anchor, anchor + declaration, 1)
    text = text.replace('waveform_exit_kind=SIMULATION_NOT_STARTED\nwaveform_receipt_rc=0\nruntime_dump_tcl=\nquery_receipt_rc=0\nquery_signal_receipt_name=SIGNAL_QUERY_RECEIPT.json\nquery_status_name=DIAGNOSTIC_STATUS.json\n', 'observer_rc=125\nmanifest_rc=125\nobserver_chunk=\nprocess_receipt=\nsupervisor_heartbeat=\nactual_argv_json=\n')
    minimal_pattern = re.compile(r'  python3 - "\$stage" "\$return_zip" "\$install_name" <<\'PY\'\n.*?\nPY\n', re.S)
    minimal = '''  python3 - "$stage" "$return_zip" "$return_sha" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage,target,side=map(pathlib.Path,sys.argv[1:4]);pkg,exe,att=sys.argv[4:7];code=int(sys.argv[7])
core=stage/"evidence/compile_rootcause";core.mkdir(parents=True,exist_ok=True)
(core/"COMPILE_CORE.json").write_text(json.dumps({"schema":"server-compile-core-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":code},sort_keys=True)+"\\n")
(core/"compile_first_error.txt").write_text("runner failed before complete attempt layout\\n")
(stage/"evidence/ACTUAL_COMPILE_SIM_ARGV.json").write_text(json.dumps({"schema":"server-observer-actual-argv-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"source_identity_status":"DIAGNOSTIC_EVIDENCE_INCOMPLETE","compile_argv":["make","compile","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"],"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"]},sort_keys=True)+"\\n")
(stage/"evidence/SIM_EXIT_RECEIPT.json").write_text(json.dumps({"schema":"server-observer-sim-exit-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"simulation_started":False,"exit_code":125,"signal":"NONE","timed_out":False},sort_keys=True)+"\\n")
members=sorted(f"{pkg}_return/{p.relative_to(stage).as_posix()}" for p in stage.rglob("*") if p.is_file())
(stage/"RETURN_CORE_MANIFEST.json").write_text(json.dumps({"schema":"server-post-sim-return-core-manifest-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"members":members,"observer_only_profile":"OBSERVER_ONLY_WIDE_CAUSAL_V1"},sort_keys=True)+"\\n")
tmp=target.with_name("."+target.name+".tmp."+str(os.getpid()))
with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
    for p in sorted(x for x in stage.rglob("*") if x.is_file()): archive.write(p,f"{pkg}_return/{p.relative_to(stage).as_posix()}")
os.replace(tmp,target);digest=hashlib.sha256(target.read_bytes()).hexdigest();st=side.with_name("."+side.name+".tmp."+str(os.getpid()));st.write_text(f"{digest}  {target.name}\\n");os.replace(st,side)
PY
'''
    # Use a callable replacement so re.sub does not reinterpret the literal
    # ``\\n`` sequences inside the generated Python heredoc.
    text, count = minimal_pattern.subn(lambda _match: minimal, text, count=1)
    if count != 1:
        raise RuntimeError(f"minimal return replacement count={count}")
    finalize_pattern = re.compile(r'    if \[ "\$simulation_started" != true \]; then\n.*?    query_receipt_rc=\$\?\n    fi\n', re.S)
    finalize_observer = '''    if [ "$simulation_started" = true ]; then
      python3 "$observer_parser" --contract "$observer_contract" --chunk "$observer_chunk" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$simulation_status" --signal "$signal_name" --timed-out "$([ "$simulation_status" -eq 124 ] && printf true || printf false)" --simulation-started true --process-receipt "$process_receipt" --heartbeat-log "$supervisor_heartbeat" --actual-argv "$actual_argv_json" --output-dir "$evidence_root"
      observer_rc=$?
    else
      mkdir -p "$evidence_root/compile_rootcause"
      python3 - "$evidence_root/SIM_EXIT_RECEIPT.json" "$evidence_root/compile_rootcause/COMPILE_CORE.json" "$evidence_root/compile_rootcause/compile_first_error.txt" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import json,pathlib,sys
sim,core,first=map(pathlib.Path,sys.argv[1:4]);pkg,exe,att=sys.argv[4:7];code=int(sys.argv[7])
sim.write_text(json.dumps({"schema":"server-observer-sim-exit-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"simulation_started":False,"exit_code":125,"signal":"NONE","timed_out":False,"compile_exit":code},sort_keys=True)+"\\n")
core.write_text(json.dumps({"schema":"server-compile-core-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":code},sort_keys=True)+"\\n")
if not first.is_file(): first.write_text("simulation did not start\\n")
PY
      observer_rc=0
    fi
'''
    text, count = finalize_pattern.subn(lambda _match: finalize_observer, text, count=1)
    if count != 1:
        raise RuntimeError(f"finalize observer replacement count={count}")
    text = replace_once(
        text,
        '    python3 "$post_sim_helper" finalize --request "$post_sim_request"\n    collect_status=$?\n',
        '    python3 "$post_sim_helper" finalize --request "$post_sim_request"\n    collect_status=$?\n    if [ -f "$return_zip" ]; then python3 "$observer_return_manifest" --zip "$return_zip" --contract "$observer_contract" --sidecar "$return_sha"; manifest_rc=$?; else manifest_rc=98; fi\n',
        "return manifest handoff",
    )
    text = text.replace('    [ "$waveform_receipt_rc" -eq 0 ] || final=97\n    [ "$query_receipt_rc" -eq 0 ] || [ "$final" -ne 0 ] || final=95\n', '    [ "$observer_rc" -eq 0 ] || [ "$final" -ne 0 ] || final=95\n    [ "$manifest_rc" -eq 0 ] || [ "$final" -ne 0 ] || final=98\n')
    text = text.replace('DUMP_VCD=0 DUMP_FSDB=1', 'DUMP_VCD=0 DUMP_FSDB=0')
    text = text.replace('$package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/qadd_fsdb_event_probe_v60.svh', '$package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/qadd_observer_wide_impl.svh')
    simulation_pattern = re.compile(r'runtime_dump_tcl="\$run_root/run/sim_results/dump_waveform\.tcl"\n.*?DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 2h "\$simv" "\$\{sim_args\[@\]\}" &\n', re.S)
    simulation = '''  simv="$compile_root/sim_results/simv"
  observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"
  process_receipt="$evidence_root/PROCESS_TREE_RECEIPT.json"
  supervisor_heartbeat="$evidence_root/supervisor_heartbeat.jsonl"
  actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
  mkdir -p "$evidence_root/observer/chunks"
  sim_args=(-l "$run_root/sim.log" +vcs+lic+wait
    "+SCA_CFG=$cfg_root/sca_cfg.json" "+SCA_CFG_D=$cfg_root/sca_cfg_D.json"
    +CODEX_CAUSAL_OBSERVER +RETURN_OBSERVER +QADD_TAILROUND_BUFREADY +RETURN_OBS_SLICE=0
    +RETURN_OBS_STALL_CYCLES=1048576 +RETURN_OBS_HEARTBEAT_CYCLES=1048576
    +QADD_FP32_INGRESS_OBSERVER +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=64
    +CODEX_QADD_OBSERVER_WIDE "+CODEX_OBSERVER_CHUNK=$observer_chunk"
    "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
    "+RETURN_OBS_FILE=$run_root/return_observer.log")
  printf 'RUNTIME_LAYOUT_SIMULATION_START\n' >"$evidence_root/simulation_started.marker"
  simulation_started=true
  python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "${compile_argv[@]}" --SIM-- "$simv" "${sim_args[@]}" <<'PY'
import json,pathlib,sys
cut=sys.argv.index("--SIM--")
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-observer-actual-argv-v1","package_id":sys.argv[2],"execution_id":sys.argv[3],"attempt_id":sys.argv[4],"cwd":sys.argv[5],"source_identity_status":"COMPLETE","compile_argv":sys.argv[6:cut],"sim_argv":["env","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0",*sys.argv[cut+1:]]},sort_keys=True)+"\\n")
PY
  printf 'python3 %q supervise' "$observer_supervisor" >"$evidence_root/actual_simulator_argv.txt"; printf ' %q' "$simv" "${sim_args[@]}" >>"$evidence_root/actual_simulator_argv.txt"; printf '\n' >>"$evidence_root/actual_simulator_argv.txt"
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$observer_supervisor" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$observer_chunk" --heartbeat-output "$supervisor_heartbeat" --heartbeat-regex '"sim_time":([0-9]+)' --timescale 1ps --timeout 7200 --interval 30 --grace 30 --receipt "$process_receipt" -- "$simv" "${sim_args[@]}" &
'''
    text, count = simulation_pattern.subn(lambda _match: simulation, text, count=1)
    if count != 1:
        raise RuntimeError(f"simulation block replacement count={count}")
    compile_receipt_anchor = 'printf \'%s\\n\' "${compile_argv[*]}" >"$evidence_root/actual_compile_argv.txt"\n'
    compile_receipt = compile_receipt_anchor + '''  actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
  python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-observer-actual-argv-v1","package_id":sys.argv[2],"execution_id":sys.argv[3],"attempt_id":sys.argv[4],"source_identity_status":"NOT_YET_BOUND","compile_argv":sys.argv[5:],"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"]},sort_keys=True)+"\\n")
PY
'''
    text = replace_once(text, compile_receipt_anchor, compile_receipt, "compile argv receipt")
    text = text.replace(
        "#!/usr/bin/env bash\n",
        "#!/usr/bin/env bash\n# Parser/finalizer-published exact return members: SIM_TIME_HEARTBEAT.json OBSERVER_SIGNAL_CATALOG.json OBSERVER_EVENT_INDEX.json OBSERVER_DECISION.json\n",
        1,
    )
    if re.search(r"\.(?:vpd|fsdb|vcd|fst)\b", text, re.I):
        raise RuntimeError("runner retains a forbidden binary-dump suffix")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_post_sim_request(path: Path) -> None:
    request = json.loads(path.read_text(encoding="utf-8"))
    request["package_id"] = NEW_ID
    request.pop("waveform_discovery", None)
    request["claim_boundary"] = "Frozen QAdd tail-round target with observer-only actual-signal return; no server-result claim."
    filtered = []
    for row in request["core_entries"]:
        blob = json.dumps(row, sort_keys=True).lower()
        if any(token in blob for token in ("waveform", "fsdb_query", "signal_query_receipt", ".fsdb", ".vpd", ".vcd", ".fst", "dump_waveform")):
            continue
        filtered.append(row)
    additions = [
        ("package", "contracts/server_observer_only_wide_causal_contract.json", "source_package/server_observer_only_wide_causal_contract.json", True),
        ("package", "diagnostics/observer_signal_catalog.json", "source_package/observer_signal_catalog.json", True),
        ("package", "diagnostics/observer_capture_plan.json", "source_package/observer_capture_plan.json", True),
        ("package", "diagnostics/observer_candidate_matrix.json", "source_package/observer_candidate_matrix.json", True),
        ("package", "package_tools/qadd_observer_event_parser.py", "source_package/qadd_observer_event_parser.py", True),
        ("package", "package_tools/server_observer_runtime_supervision.py", "source_package/server_observer_runtime_supervision.py", True),
        ("attempt", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", False),
        ("attempt", "evidence/PROCESS_TREE_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json", False),
        ("attempt", "evidence/SIM_TIME_HEARTBEAT.json", "evidence/SIM_TIME_HEARTBEAT.json", False),
        ("attempt", "evidence/SIM_EXIT_RECEIPT.json", "evidence/SIM_EXIT_RECEIPT.json", False),
        ("attempt", "evidence/OBSERVER_SIGNAL_CATALOG.json", "evidence/OBSERVER_SIGNAL_CATALOG.json", False),
        ("attempt", "evidence/OBSERVER_EVENT_INDEX.json", "evidence/OBSERVER_EVENT_INDEX.json", False),
        ("attempt", "evidence/observer/chunks/events-000000.jsonl", "observer/chunks/events-000000.jsonl", False),
        ("attempt", "evidence/OBSERVER_DECISION.json", "evidence/OBSERVER_DECISION.json", False),
        ("attempt", "evidence/compile_rootcause/COMPILE_CORE.json", "evidence/compile_rootcause/COMPILE_CORE.json", False),
        ("attempt", "evidence/compile_rootcause/compile_first_error.txt", "evidence/compile_rootcause/compile_first_error.txt", False),
    ]
    archives = {row["archive"] for row in filtered}
    for source_root, source, archive, required in additions:
        if archive not in archives:
            filtered.append({"source_root": source_root, "source": source, "archive": archive, "required": required})
    request["core_entries"] = filtered
    write_json(path, request)


def update_contracts(contract_path: Path) -> None:
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    post["package_id"] = NEW_ID
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    post["request_sha256"] = sha(TREE / "contracts/server_post_sim_return_request.json")
    post["claim_boundary"] = "Observer-only post-simulation return-core publication; no DUT result claim."
    write_json(post_path, post)

    runner_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    runner["package_id"] = NEW_ID
    runner["runner_path"] = f"{NEW_ID}/PREPARE_AND_RUN.sh"
    runner["runner_sha256"] = sha(TREE / "PREPARE_AND_RUN.sh")
    runner["package_owned_variables"] = [
        "install_name", "package_id", "return_tag", "result_root", "return_zip", "return_sha",
        "package_root", "runtime", "base_runtime", "root_guard", "layout_helper",
        "post_sim_helper", "post_sim_request", "observer_parser", "observer_contract",
        "observer_supervisor", "observer_impl", "observer_return_manifest",
        "source_bound_observer", "compile_status", "simulation_status", "simulation_started",
        "signal_name", "observer_rc", "manifest_rc", "finalized", "sim_pid", "sampler_pid",
        "server_root", "cfg_root", "run_root", "evidence_root", "compile_root", "attempt",
        "bootstrap_root", "source_bound_filtered_log", "observer_chunk", "process_receipt",
        "supervisor_heartbeat", "actual_argv_json",
    ]
    runner["return_allowlist_tokens"] = [
        "compile_argv.json", "compile_source_identity.json", "compile_exit.txt",
        "compile_driver.log", "compile_first_error.txt", "compile_log_head.txt",
        "compile_log_tail.txt", "compile_downstream_state.json", "ACTUAL_COMPILE_SIM_ARGV.json",
        "PROCESS_TREE_RECEIPT.json", "SIM_TIME_HEARTBEAT.json", "SIM_EXIT_RECEIPT.json",
        "OBSERVER_SIGNAL_CATALOG.json", "OBSERVER_EVENT_INDEX.json", "OBSERVER_DECISION.json",
        "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0",
    ]
    write_json(runner_path, runner)

    runtime_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["package_id"] = NEW_ID
    runtime["install_name"] = NEW_ID
    runtime["claim_boundary"] = "Frozen QAdd install/runtime paths with observer-only attempt evidence."
    runtime["path_budget"]["additional_projected_paths"] = [
        path.replace(OLD_ID, NEW_ID)
        for path in runtime["path_budget"]["additional_projected_paths"]
        if not re.search(r"\.(?:vpd|fsdb|vcd|fst)\b", path, re.I)
    ]
    for mount in runtime["payload_mounts"]:
        mount["runtime_prefix"] = mount["runtime_prefix"].replace(OLD_ID, NEW_ID)
    for value in runtime["runtime_roots"].values():
        if OLD_ID in value:
            raise RuntimeError("runtime root identity replacement did not occur")
    runtime["runtime_roots"] = {key: value.replace(OLD_ID, NEW_ID) for key, value in runtime["runtime_roots"].items()}
    write_json(runtime_path, runtime)


def refresh_path_budget(manifest: dict[str, Any]) -> None:
    runtime_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    budget = runtime["path_budget"]
    attempt = "a" * budget["attempt_max_chars"]
    candidates: set[str] = set()
    members = [path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file()]
    for mount in runtime["payload_mounts"]:
        source = mount["source_prefix"]
        target = mount["runtime_prefix"]
        candidates.update(target + member[len(source):] for member in members if member.startswith(source))
    candidates.update(value.replace("{attempt}", attempt) for value in runtime["runtime_roots"].values())
    candidates.update(value.replace("{attempt}", attempt) for value in budget["additional_projected_paths"])
    longest = max(candidates, key=lambda value: (len(value), value))
    projected_absolute = budget["declared_target_root_max_chars"] + 1 + len(longest)
    budget["max_projected_absolute_path_chars"] = projected_absolute
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": budget["declared_target_root_max_chars"],
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": projected_absolute,
        "absolute_path_limit_chars": budget["absolute_path_limit_chars"],
    }
    write_json(runtime_path, runtime)


def deterministic_zip(tree: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(tree.rglob("*")):
            if not path.is_file():
                continue
            name = f"{NEW_ID}/{path.relative_to(tree).as_posix()}"
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failure")


def exact_zip_tree_recheck(tree: Path, output: Path) -> dict[str, Any]:
    expected = {
        f"{NEW_ID}/{path.relative_to(tree).as_posix()}": (path.stat().st_size, sha(path))
        for path in sorted(tree.rglob("*")) if path.is_file()
    }
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise RuntimeError("exact final ZIP member set differs from staging tree")
        actual = {
            name: (len(data := archive.read(name)), sha_bytes(data))
            for name in names
        }
    if actual != expected:
        raise RuntimeError("exact final ZIP member identity differs from staging tree")
    return {"member_count": len(actual), "exact_set": True, "exact_bytes_sha": True}


def build() -> None:
    if not OLD_ZIP.is_file():
        raise RuntimeError(f"missing exact v60 pending ZIP: {OLD_ZIP}")
    if not REFERENCE.is_dir():
        raise RuntimeError("current-disk observer reference is missing")
    old_identity = identity(OLD_ZIP)
    RELEASE.mkdir(parents=True, exist_ok=True)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    short_extract = ROOT / "q61x"
    if short_extract.exists():
        shutil.rmtree(short_extract)
    short_extract.mkdir()
    try:
        extracted = short_extract
        safe_extract(OLD_ZIP, extracted)
        source_tree = extracted / OLD_ID
        if not source_tree.is_dir():
            raise RuntimeError("v60 ZIP root identity mismatch")
        source_workload = tree_identity(source_tree / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"})
        source_golden = tree_identity(source_tree / "validation")
        source_legacy = tree_identity(source_tree / "tb_probe", {"qadd_fsdb_event_probe_v60.svh"})
        shutil.copytree(source_tree, TREE)
    finally:
        if short_extract.exists():
            shutil.rmtree(short_extract)

    remove = [
        "contracts/qadd_fsdb_query_profile.json",
        "contracts/server_waveform_mandatory_plan.json",
        "contracts/waveform_policy.json",
        "diagnostics/qadd_fsdb_query_source_report.json",
        "package_tools/dump_waveform.tcl",
        "package_tools/qadd_fsdb_event_parser_v60.py",
        "package_tools/server_waveform_mandatory_return.py",
        "tb_probe/qadd_fsdb_event_probe_v60.svh",
        "provenance/v57h_to_v58_mandatory_vpd.json",
        "provenance/v58_to_v59_portable_waveform.json",
        "provenance/v59_to_v60_fsdb_identity_fix.json",
    ]
    for relative in remove:
        target = TREE / relative
        if target.exists():
            target.unlink()

    for path in TREE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".py", ".sh", ".md", ".txt"}:
            continue
        if path.is_relative_to(TREE / "workload") and path.name not in {"sca_cfg.json", "sca_cfg_D.json"}:
            continue
        text = path.read_text(encoding="utf-8")
        if OLD_ID in text:
            path.write_text(text.replace(OLD_ID, NEW_ID), encoding="utf-8", newline="\n")

    signals = signal_templates()
    observer = TREE / "tb_probe/qadd_observer_wide_impl.svh"
    observer.write_text(observer_source(signals), encoding="utf-8", newline="\n")
    parser_source = REFERENCE / "package_tools/node0004_observerwide_event_parser.py"
    parser_target = TREE / "package_tools/qadd_observer_event_parser.py"
    parser_text = parser_source.read_text(encoding="utf-8").replace(
        "serialized-Conv", "QLinearAdd node0007"
    )
    parser_target.write_text(parser_text, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "tools/server_observer_runtime_supervision.py", TREE / "package_tools/server_observer_runtime_supervision.py")
    shutil.copyfile(ROOT / "tools/server_post_sim_return.py", TREE / "package_tools/server_post_sim_return.py")
    manifest_source = REFERENCE / "package_tools/node0004_observerwide_return_manifest.py"
    shutil.copyfile(manifest_source, TREE / "package_tools/qadd_observer_return_manifest.py")

    contract = build_contract(signals)
    contract_path = TREE / "contracts/server_observer_only_wide_causal_contract.json"
    write_json(contract_path, contract)
    public = contract["signals"]
    write_json(TREE / "diagnostics/observer_signal_catalog.json", {
        "schema": "qadd-observer-signal-catalog-v1", "source_bound": True,
        "derived_expected_equation": False, "signals": public,
    })
    write_json(TREE / "diagnostics/observer_capture_plan.json", {
        "schema": "qadd-observer-capture-plan-v1", "package_id": NEW_ID,
        "event_recording": contract["event_recording"], "budget": contract["budget"],
        "signal_ids": [signal["signal_id"] for signal in public], "partial_exit": True,
        "immutable_chunk": "observer/chunks/events-000000.jsonl",
    })
    write_json(TREE / "diagnostics/observer_candidate_matrix.json", {
        "schema": "qadd-observer-candidate-matrix-v1",
        "boundary_observations": contract["boundary_observations"],
        "candidates": contract["candidates"],
    })
    write_json(TREE / "provenance/v60_to_v61_observer_only.json", {
        "schema": "qadd-v61-observer-only-provenance-v1", "package_id": NEW_ID,
        "previous_version_progress": "v57h localized the first divergence after Buffer5 request decode and before selected ping-pong-port required-lane read accept; v59 exposed the install/SCA identity defect; v60 repaired that identity and remains unrun.",
        "current_version_purpose": "Preserve the v60 identity repair and tail-round target while capturing producer, clear, selected-port, bank/lane readiness, read-accept, data/output and tail-terminal actual nets in one observer-only return.",
        "changed_surface": ["fresh identity", "package-local read-only observer", "runtime supervision", "formal return"],
        "frozen_surface": ["configuration", "numeric", "workload", "golden", "functional RTL", "tail-round diagnostic target"],
        "post_sim_conjunction_activation_epoch": FIX_EPOCH,
    })
    required = [
        value for key, value in contract["return_members"].items()
        if key not in {"chunk_prefix", "compile_core_when_not_started"}
    ] + contract["return_members"]["compile_core_when_not_started"]
    write_json(TREE / "RETURN_ALLOWLIST.json", {
        "schema": "server-observer-return-allowlist-v1", "required": required,
        "prefixes": [contract["return_members"]["chunk_prefix"]], "no_size_limit": True,
    })

    patch_runner(TREE / "PREPARE_AND_RUN.sh")
    update_post_sim_request(TREE / "contracts/server_post_sim_return_request.json")
    update_contracts(contract_path)

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = strip_retired_dump_metadata(json.loads(manifest_path.read_text(encoding="utf-8")))
    manifest.update({
        "schema": "qlinearadd-node0007-v61-observer-only-wide-causal",
        "test_id": "r5-qadd-node0007-v61-observer-wide",
        "package_name": NEW_ID, "install_name": NEW_ID, "run_name": NEW_ID,
        "return_name": f"{NEW_ID}_<execution>_return.zip",
        "claim": "Re-run the frozen Buffer5 selected-port required-lane readiness target with wide source-bound actual-signal observer evidence only.",
        "claim_boundary": "Local package gates only; production compile/simulation, natural terminal, formal D and E3-E5 remain unproven.",
        "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "observer_only_contract_sha256": sha(contract_path),
        "post_sim_conjunction_activation_epoch": FIX_EPOCH,
        "functional_rtl_modified": False, "server_run_performed": False, "uploaded": False,
        "generation_provenance": {
            "previous_progress": "v57h localized the first divergence after Buffer5 request decode and before selected ping-pong-port required-lane read accept; v59 found the manifest/install/SCA mismatch; v60 repaired it and was not run.",
            "current_purpose": "Keep the repaired identity and tail-round target, and capture Buffer5 producer/clear/selected-port/bank-lane/read/data/terminal causality in one observer-only return.",
            "changed_surface": ["fresh identity", "observer", "runtime supervision", "formal return"],
            "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "target diagnostic"],
        },
        "observer_only_wide_causal": {
            "activation_epoch": BASE_EPOCH, "post_sim_conjunction_epoch": FIX_EPOCH,
            "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
            "signal_count": len(public), "causal_roles": 26,
            "candidate_count": len(contract["candidates"]), "soft_limit_bytes": 100000000,
            "hard_limit_bytes": None, "sampling": False, "truncation": False,
            "size_based_deletion": False,
            "runtime_supervision": "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT",
        },
        "rule_change_epoch": {
            "epoch_id": FIX_EPOCH, "base_epoch": BASE_EPOCH, "family": FAMILY,
            "first_fresh_after_change": True, "notification_acknowledged": True,
            "package_id": NEW_ID, "upload_hold_until": "EXPLICIT_USER_SERVER_AUTHORIZATION",
        },
    })
    manifest.setdefault("post_sim_return_core", {})["members"] = {
        "helper": identity(TREE / "package_tools/server_post_sim_return.py", TREE),
        "request": identity(TREE / "contracts/server_post_sim_return_request.json", TREE),
        "contract": identity(TREE / "contracts/server_post_sim_return_contract.json", TREE),
    }
    manifest["runner_return_resilience"] = {
        "runner": identity(TREE / "PREPARE_AND_RUN.sh", TREE),
        "contract": identity(TREE / "contracts/server_runner_return_resilience_contract.json", TREE),
    }
    manifest["return_allowlist"] = "RETURN_ALLOWLIST.json"
    refresh_path_budget(manifest)
    manifest["files"] = file_map(TREE)
    write_json(manifest_path, manifest)
    manifest["files"] = file_map(TREE)
    write_json(manifest_path, manifest)
    (TREE / "README.md").write_text(
        f"# QLinearAdd node0007 v61 observer-only wide-causal successor\n\n"
        "This fresh package preserves v60's manifest/install/SCA identity repair, frozen tail-round payload and selected-port lane-readiness target. It returns source-bound four-state observer events spanning Buffer5 request decode, both port readiness paths, bank/lane valid and clear state, read acceptance, data and tail termination.\n\n"
        f"Run only after explicit server authorization: `bash {NEW_ID}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n",
        encoding="utf-8", newline="\n",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = file_map(TREE)
    write_json(manifest_path, manifest)

    frozen = {
        "schema": "qadd-v61-frozen-surface-receipt-v1",
        "workload_excluding_identity_files_equal": tree_identity(TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == source_workload,
        "golden_equal": tree_identity(TREE / "validation") == source_golden,
        "legacy_diagnostic_hdl_equal": tree_identity(TREE / "tb_probe", {"qadd_observer_wide_impl.svh"}) == source_legacy,
        "functional_rtl_modified": False,
    }
    frozen["pass"] = all(value is True for key, value in frozen.items() if key.endswith("_equal"))
    write_json(RELEASE / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen}")

    canonical_helper = ROOT / "tools/server_post_sim_return.py"
    packaged_helper = TREE / "package_tools/server_post_sim_return.py"
    if packaged_helper.read_bytes() != canonical_helper.read_bytes():
        raise RuntimeError("post-sim helper is not exact canonical bytes")
    forbidden_members = [
        path.relative_to(TREE).as_posix() for path in TREE.rglob("*")
        if path.is_file() and path.suffix.lower() in {".vpd", ".fsdb", ".vcd", ".fst", ".tcl"}
    ]
    if forbidden_members:
        raise RuntimeError(f"forbidden observer-only members: {forbidden_members}")
    text_errors = []
    for path in sorted(TREE.rglob("*")):
        if not path.is_file() or path in {packaged_helper, contract_path} or path.stat().st_size > 8_000_000:
            continue
        if path.suffix.lower() not in {".json", ".py", ".sh", ".md", ".txt", ".sv", ".svh"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if re.search(r"\.(?:vpd|fsdb|vcd|fst)\b", text):
            text_errors.append(path.relative_to(TREE).as_posix())
    if text_errors:
        raise RuntimeError(f"binary-dump suffix remains outside exact helper: {text_errors}")

    deterministic_zip(TREE, ZIP)
    zip_recheck = exact_zip_tree_recheck(TREE, ZIP)
    ZIP.with_name(ZIP.name + ".sha256").write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    if identity(OLD_ZIP) != old_identity:
        raise RuntimeError("v60 pending ZIP changed during build")
    write_json(BUILD / "build_receipt.json", {
        "schema": "qadd-node0007-v61-observer-wide-build-v1", "package_id": NEW_ID,
        "activation_epoch": FIX_EPOCH, "base_epoch": BASE_EPOCH,
        "source_v60_pending": old_identity, "zip": identity(ZIP),
        "signal_count": len(public), "candidate_count": len(contract["candidates"]),
        "frozen_surface": frozen, "exact_final_zip_recheck": zip_recheck,
        "server_action": False, "pass": True,
    })


if __name__ == "__main__":
    build()
