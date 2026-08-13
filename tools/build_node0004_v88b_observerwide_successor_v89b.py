#!/usr/bin/env python3
"""Build the first formal serialized-Conv observer-only wide-causal successor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v89b_obswide"
SOURCE_ID = "r5_n4_hw_v88b_portvcd"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v89b_observerwide_release1"
BUILD_ROOT = OUT / "build" / PACKAGE_ID
FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/r5_n4_hw_v88b_portvcd/r5_n4_hw_v88b_portvcd.zip"
ACTUAL_BUFFER = ROOT / "outputs/conv_node0004_v88b_formal_return_analysis2/evidence/actual_target_source.sv"
HIER = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
BUFFER_REL = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
WR_REL = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
FIFO_REL = "rtl/utils/FIFO/FIFO.sv"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write(relative: str, data: bytes, executable: bool = False) -> Path:
    path = BUILD_ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_json(relative: str, value: object) -> Path:
    return write(relative, canonical(value))


def source_bytes(relative: str) -> bytes:
    if relative == BUFFER_REL:
        return ACTUAL_BUFFER.read_bytes()
    return (ROOT / "NDP_copy01" / relative).read_bytes()


def declaration_hash(relative: str, name: str) -> str:
    lines = source_bytes(relative).decode("utf-8", errors="replace").splitlines()
    matches = [line.strip() for line in lines if name in line and not line.strip().startswith("//")]
    return sha((matches[0] if matches else name).encode("utf-8"))


RAW_SIGNALS = [
    # id, width, hierarchy relative to the exact MSE4 WR engine, source, module, causal roles
    ("sig_clk", 1, "clk", WR_REL, "Memory_WR_Stream_Engine", ["clock"]),
    ("sig_rst_n", 1, "rst_n", WR_REL, "Memory_WR_Stream_Engine", ["reset"]),
    ("sig_slice_rst", 1, "slice_rst", WR_REL, "Memory_WR_Stream_Engine", ["reset", "internal_clear"]),
    ("sig_mse_enable", 1, "mse_enable", WR_REL, "Memory_WR_Stream_Engine", ["stage"]),
    ("sig_row_tag", 7, "mse_buf_queue_row_tag", WR_REL, "Memory_WR_Stream_Engine", ["source", "producer"]),
    ("sig_col_tag", 7, "mse_buf_queue_col_tag", WR_REL, "Memory_WR_Stream_Engine", ["source", "producer"]),
    ("sig_row_idx", 2, "mse_buf_queue_row_idx", WR_REL, "Memory_WR_Stream_Engine", ["selected_port"]),
    ("sig_col_idx", 5, "mse_buf_queue_col_idx", WR_REL, "Memory_WR_Stream_Engine", ["selected_bank"]),
    ("sig_idx_mode", 2, "mse_buf_idx_mode", WR_REL, "Memory_WR_Stream_Engine", ["selected_lane"]),
    ("sig_public_ack", 2, "mse_buf_queue_bp_pre", WR_REL, "Memory_WR_Stream_Engine", ["ready", "output"]),
    ("sig_valid_mask", 2, "u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_masked", BUFFER_REL, "Buffer_AG_Idx_Queue", ["valid", "producer"]),
    ("sig_row_wr", 1, "u_Buffer_AG_Idx_Queue.u_row_fifo.fifo_wr_en", FIFO_REL, "FIFO", ["queue_enqueue"]),
    ("sig_row_rd", 1, "u_Buffer_AG_Idx_Queue.u_row_fifo.fifo_rd_en", FIFO_REL, "FIFO", ["queue_dequeue"]),
    ("sig_row_count", 3, "u_Buffer_AG_Idx_Queue.u_row_fifo.fifo_counter", FIFO_REL, "FIFO", ["queue_count", "internal_state"]),
    ("sig_row_full", 1, "u_Buffer_AG_Idx_Queue.row_fifo_full", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_full", "backpressure"]),
    ("sig_row_empty", 1, "u_Buffer_AG_Idx_Queue.row_fifo_empty", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_empty"]),
    ("sig_col_wr", 1, "u_Buffer_AG_Idx_Queue.u_col_fifo.fifo_wr_en", FIFO_REL, "FIFO", ["queue_enqueue"]),
    ("sig_col_rd", 1, "u_Buffer_AG_Idx_Queue.u_col_fifo.fifo_rd_en", FIFO_REL, "FIFO", ["queue_dequeue"]),
    ("sig_col_count", 3, "u_Buffer_AG_Idx_Queue.u_col_fifo.fifo_counter", FIFO_REL, "FIFO", ["queue_count", "internal_state"]),
    ("sig_col_full", 1, "u_Buffer_AG_Idx_Queue.col_fifo_full", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_full", "backpressure"]),
    ("sig_col_empty", 1, "u_Buffer_AG_Idx_Queue.col_fifo_empty", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_empty"]),
    ("sig_all_match", 1, "u_Buffer_AG_Idx_Queue.buf_all_idx_matched", BUFFER_REL, "Buffer_AG_Idx_Queue", ["internal_match"]),
    ("sig_gotten", 2, "u_Buffer_AG_Idx_Queue.buf_idx_gotten_bit", BUFFER_REL, "Buffer_AG_Idx_Queue", ["internal_state"]),
    ("sig_queue_wr", 1, "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_enqueue"]),
    ("sig_queue_rd", 1, "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_dequeue"]),
    ("sig_queue_count", 3, "u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter", FIFO_REL, "FIFO", ["queue_count", "internal_state"]),
    ("sig_queue_full", 1, "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_full", "backpressure"]),
    ("sig_queue_empty", 1, "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty", BUFFER_REL, "Buffer_AG_Idx_Queue", ["queue_empty"]),
    ("sig_bp_post", 1, "mse_buf_ag_bp_post", WR_REL, "Memory_WR_Stream_Engine", ["backpressure"]),
    ("sig_tag_valid", 1, "mse_buf_ag_tag_valid", WR_REL, "Memory_WR_Stream_Engine", ["accept", "output"]),
    ("sig_tag", 6, "mse_buf_ag_tag", WR_REL, "Memory_WR_Stream_Engine", ["output"]),
    ("sig_out_idx", 7, "mse_buf_ag_idx", WR_REL, "Memory_WR_Stream_Engine", ["output"]),
    ("sig_mem_req_valid", 2, "mse2mem_request_valid", WR_REL, "Memory_WR_Stream_Engine", ["request", "valid"]),
    ("sig_mem_req_ready", 2, "mem2mse_request_ready", WR_REL, "Memory_WR_Stream_Engine", ["ready", "accept"]),
    ("sig_wdata_valid", 2, "mse2mem_wdata_valid", WR_REL, "Memory_WR_Stream_Engine", ["valid", "wdata"]),
    ("sig_wdata_ready", 2, "mem2mse_wdata_ready", WR_REL, "Memory_WR_Stream_Engine", ["ready", "accept"]),
    ("sig_wdata", 256, "mse2mem_wdata", WR_REL, "Memory_WR_Stream_Engine", ["wdata", "formal_d"]),
    ("sig_slice_finish", 1, "slice_cmpt_finish", WR_REL, "Memory_WR_Stream_Engine", ["terminal", "finish"]),
]


def signal_catalog() -> list[dict[str, object]]:
    signals = []
    for signal_id, width, relative_hierarchy, source_path, module, roles in RAW_SIGNALS:
        name = relative_hierarchy.rsplit(".", 1)[-1]
        signals.append({
            "signal_id": signal_id,
            "symbol_id": "sym_" + sha(f"{source_path}:{name}".encode())[:24],
            "exact_hierarchy": f"{HIER}.{relative_hierarchy}",
            "target_module": module, "source_path": source_path,
            "source_sha256": sha(source_bytes(source_path)),
            "declaration_span_sha256": declaration_hash(source_path, name),
            "width_bits": width, "owner_clock_signal_id": "sig_clk",
            "owner_reset_signal_id": "sig_rst_n", "roles": roles,
            "source_binding": "ACTUAL_SOURCE_NET", "derived_expected_equation": False,
            "observer_drives_dut": False,
        })
    return signals


def contract() -> dict[str, object]:
    canonical_post_sim = (ROOT / "tools/server_post_sim_return.py").read_bytes()
    signals = signal_catalog()
    roles = [
        "clock", "reset", "stage", "source", "producer", "queue_enqueue", "queue_dequeue",
        "queue_count", "queue_full", "queue_empty", "request", "valid", "ready", "accept",
        "backpressure", "selected_port", "selected_bank", "selected_lane", "internal_match",
        "internal_state", "internal_clear", "output", "wdata", "terminal", "finish", "formal_d",
    ]
    coverage = [{"role": role, "disposition": "covered", "signal_ids": [item["signal_id"] for item in signals if role in item["roles"]]} for role in roles]
    observations = [
        {"observation_id": "obs_source", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_row_tag", "sig_col_tag", "sig_valid_mask", "sig_mse_enable"], "predicate": "actual MSE4 row/column producers and stage state"},
        {"observation_id": "obs_fifo", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_row_count", "sig_col_count", "sig_row_full", "sig_col_full", "sig_public_ack"], "predicate": "actual row/column FIFO state and public ACK"},
        {"observation_id": "obs_queue", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_queue_count", "sig_queue_full", "sig_tag_valid", "sig_bp_post", "sig_mem_req_valid", "sig_mem_req_ready"], "predicate": "actual aggregate queue, accept and request state"},
        {"observation_id": "obs_terminal", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_slice_rst", "sig_gotten", "sig_wdata_valid", "sig_wdata_ready", "sig_wdata", "sig_slice_finish"], "predicate": "actual hold/clear, write-data, terminal and formal-D precursor state"},
    ]
    candidates = [
        ("candidate_source_starvation", [True, False, False, False]),
        ("candidate_row_fifo_backpressure", [True, True, False, False]),
        ("candidate_col_fifo_backpressure", [False, True, False, False]),
        ("candidate_aggregate_queue_hold", [True, True, True, False]),
        ("candidate_downstream_accept_hold", [False, True, True, False]),
        ("candidate_terminal_formal_d_hold", [True, True, True, True]),
    ]
    observation_ids = [item["observation_id"] for item in observations]
    root = f"{PACKAGE_ID}_return/"
    return {
        "schema": "server-observer-only-wide-causal-contract-v1", "profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "activation_epoch": "observer-only-wide-causal-v1",
        "rule_ids": ["CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001", "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001"],
        "package_id": PACKAGE_ID, "family": FAMILY,
        "execution": {
            "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "runtime_supervision": "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT",
            "repeat_safe_exact_owned_reset": True, "atomic_unique_return": True, "waveform_writer": None,
        },
        "budget": {"observer_evidence_soft_limit_bytes": 100000000, "observer_evidence_hard_limit_bytes": None, "formal_return_hard_limit_bytes": None, "event_count_cap": None, "byte_cap": None, "sampling": False, "truncation": False, "size_based_deletion": False},
        "signals": signals, "role_coverage": coverage, "boundary_observations": observations,
        "candidates": [{"candidate_id": cid, "signature": dict(zip(observation_ids, signature))} for cid, signature in candidates],
        "all_coobservable_candidates_aggregated": True,
        "event_recording": {"format": "JSONL", "fields": ["record_type", "package_id", "execution_id", "attempt_id", "seq", "sim_time", "timescale", "signal_id", "width_bits", "value_4state"], "ordered_transitions": True, "end_state_required": True, "periodic_sim_time_heartbeat": True, "partial_exit_live_records": True, "event_cap": None, "byte_cap": None, "sampling": False, "truncation": False},
        "package_members": {"runner": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh", "manifest": f"{PACKAGE_ID}/package_manifest.json", "return_allowlist": f"{PACKAGE_ID}/RETURN_ALLOWLIST.json", "contract": f"{PACKAGE_ID}/contracts/observer_only_wide_causal_contract.json", "observer": f"{PACKAGE_ID}/tb_probe/observer_only_wide_causal.svh", "parser": f"{PACKAGE_ID}/package_tools/node0004_observerwide_event_parser.py", "runtime_supervisor": f"{PACKAGE_ID}/package_tools/server_observer_runtime_supervision.py", "post_sim_helper": f"{PACKAGE_ID}/package_tools/server_post_sim_return.py", "post_sim_request": f"{PACKAGE_ID}/contracts/server_post_sim_return_request.json"},
        "post_sim_historical_compatibility_exemption": {
            "schema": "observer-only-post-sim-helper-exemption-v1",
            "canonical_source_path": "tools/server_post_sim_return.py",
            "canonical_helper_bytes": len(canonical_post_sim),
            "canonical_helper_sha256": sha(canonical_post_sim),
            "member_path": f"{PACKAGE_ID}/package_tools/server_post_sim_return.py",
            "request_member": f"{PACKAGE_ID}/contracts/server_post_sim_return_request.json",
            "inert_literal_tokens": sorted(suffix for suffix in (".fsdb", ".fst", ".vcd", ".vpd") if suffix in canonical_post_sim.decode("utf-8").lower()),
            "waveform_discovery_disposition": "OMITTED_OR_NULL_ONLY",
        },
        "return_members": {"actual_argv": root + "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "sim_exit": root + "evidence/SIM_EXIT_RECEIPT.json", "process_tree": root + "evidence/PROCESS_TREE_RECEIPT.json", "sim_time_heartbeat": root + "evidence/SIM_TIME_HEARTBEAT.json", "signal_catalog": root + "evidence/OBSERVER_SIGNAL_CATALOG.json", "chunk_index": root + "evidence/OBSERVER_EVENT_INDEX.json", "chunk_prefix": root + "observer/chunks/", "decision": root + "evidence/OBSERVER_DECISION.json", "return_manifest": root + "RETURN_CORE_MANIFEST.json", "compile_core_when_not_started": [root + "evidence/compile_rootcause/COMPILE_CORE.json", root + "evidence/compile_rootcause/compile_first_error.txt"]},
        "claim_boundary": "Actual-net observer transport and causal coverage only; family owner retains signal interpretation and DUT verdict authority.",
    }


def observer_source(signals: list[dict[str, object]]) -> str:
    ports = []
    regs = []
    capture = []
    updates = []
    sensitivity = []
    connections = []
    for item, raw in zip(signals, RAW_SIGNALS):
        sid = str(item["signal_id"])
        width = int(item["width_bits"])
        connection = raw[2]
        decl = "input wire" if width == 1 else f"input wire [{width-1}:0]"
        ports.append(f"    {decl} {sid}")
        reg = "reg" if width == 1 else f"reg [{width-1}:0]"
        regs.append(f"  {reg} prev_{sid};")
        capture.append(f'''      if (force_all || {sid} !== prev_{sid}) begin
        $fdisplay(codex_fd, "{{\\\"record_type\\\":\\\"EVENT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\"{sid}\\\",\\\"width_bits\\\":{width},\\\"value_4state\\\":\\\"%b\\\"}}", codex_package_id, codex_execution_id, codex_attempt_id, codex_seq, codex_time_ps, {sid});
        codex_seq = codex_seq + 1;
      end''')
        updates.append(f"      prev_{sid} = {sid};")
        sensitivity.append(sid)
        connections.append(f"  .{sid}({connection})")
    return f'''`timescale 1ns/1ps
// Generated from contracts/observer_only_wide_causal_contract.json.
// Actual nets only: no expected-equation or retired buf-index comparator.
module codex_node0004_observerwide(
{',\n'.join(ports)}
);
  integer codex_fd;
  integer codex_enabled;
  integer codex_have_previous;
  longint unsigned codex_seq;
  longint unsigned codex_time_ps;
  longint unsigned codex_clock_count;
  string codex_path;
  string codex_package_id;
  string codex_execution_id;
  string codex_attempt_id;
{os.linesep.join(regs)}

  task automatic codex_capture(input integer force_all);
    begin
      codex_time_ps = $rtoi($realtime * 1000.0);
{os.linesep.join(capture)}
{os.linesep.join(updates)}
      codex_have_previous = 1;
      if ((codex_seq & 4095) == 0) $fflush(codex_fd);
    end
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_OBSERVER_ONLY_WIDE_CAUSAL");
    codex_seq = 0; codex_clock_count = 0; codex_have_previous = 0;
    if (codex_enabled) begin
      if (!$value$plusargs("CODEX_OBSERVER_CHUNK=%s", codex_path)) $fatal(1, "missing CODEX_OBSERVER_CHUNK");
      if (!$value$plusargs("CODEX_PACKAGE_ID=%s", codex_package_id)) $fatal(1, "missing CODEX_PACKAGE_ID");
      if (!$value$plusargs("CODEX_EXECUTION_ID=%s", codex_execution_id)) $fatal(1, "missing CODEX_EXECUTION_ID");
      if (!$value$plusargs("CODEX_ATTEMPT_ID=%s", codex_attempt_id)) $fatal(1, "missing CODEX_ATTEMPT_ID");
      codex_fd = $fopen(codex_path, "w");
      if (!codex_fd) $fatal(1, "cannot open observer chunk");
      #0; codex_capture(1); $fflush(codex_fd);
    end
  end

  always @({ ' or '.join(sensitivity) }) if (codex_enabled && codex_have_previous) codex_capture(0);
  always @(posedge sig_clk) if (codex_enabled) begin
    codex_clock_count = codex_clock_count + 1;
    if ((codex_clock_count & 262143) == 0) begin
      codex_time_ps = $rtoi($realtime * 1000.0);
      $fdisplay(codex_fd, "{{\\\"record_type\\\":\\\"HEARTBEAT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\"__heartbeat__\\\",\\\"width_bits\\\":1,\\\"value_4state\\\":\\\"0\\\"}}", codex_package_id, codex_execution_id, codex_attempt_id, codex_seq, codex_time_ps);
      codex_seq = codex_seq + 1; $fflush(codex_fd);
      $display("CODEX_OBSERVER_SIM_TIME_V1 sim_time=%0d", codex_time_ps);
    end
  end
  final if (codex_enabled && codex_fd) begin $fflush(codex_fd); $fclose(codex_fd); end
endmodule

bind {HIER} codex_node0004_observerwide codex_node0004_observerwide_inst (
{',\n'.join(connections)}
);
'''.replace("\r\n", "\n")


def post_request() -> dict[str, object]:
    def entry(source: str, archive: str | None = None, required: bool = False, root: str = "attempt") -> dict[str, object]:
        return {"source_root": root, "source": source, "archive": archive or source, "required": required}
    entries = [
        entry("evidence/ACTUAL_COMPILE_SIM_ARGV.json", required=True),
        entry("evidence/SIM_EXIT_RECEIPT.json", required=True),
        entry("evidence/PROCESS_TREE_RECEIPT.json"), entry("evidence/SIM_TIME_HEARTBEAT.json"),
        entry("evidence/OBSERVER_SIGNAL_CATALOG.json"), entry("evidence/OBSERVER_EVENT_INDEX.json"),
        entry("evidence/OBSERVER_DECISION.json"),
        entry("evidence/observer/chunks/events-000000.jsonl", "observer/chunks/events-000000.jsonl"),
        entry("evidence/compile_rootcause/COMPILE_CORE.json", required=True),
        entry("evidence/compile_rootcause/compile_first_error.txt", required=True),
        entry("evidence/compile_rootcause/compile_argv.json"), entry("evidence/compile_rootcause/compile_source_identity.json"),
        entry("evidence/compile_rootcause/compile_driver.log"), entry("evidence/compile_rootcause/compile_log_head.txt"), entry("evidence/compile_rootcause/compile_log_tail.txt"),
        entry("evidence/compiled_source/source_identity.json"), entry("evidence/compiled_source/actual_vcs_argv.json"),
        entry("evidence/compiled_source/preprocessed_target.sv"), entry("evidence/compiled_source/preprocessed_target_receipt.json"), entry("evidence/compiled_source/elaborated_ack_driver_set.json"),
        entry("c0/sim.log", "runs/c0/sim.log"), entry("c0/simulator_argv.txt", "runs/c0/simulator_argv.txt"),
        entry("package_manifest.json", "evidence/returned_package_manifest.json", True, "package"),
        entry("contracts/observer_only_wide_causal_contract.json", "evidence/observer_only_wide_causal_contract.json", True, "package"),
    ]
    return {"schema": "server-post-sim-return-request-v1", "package_id": PACKAGE_ID, "result_root": "/home/panqs/ndp/simresult", "return_basename_template": "{package_id}_{execution_id}_return.zip", "core_entries": entries, "waveform_discovery": None, "plugins": [], "max_plugin_output_bytes": 1048576, "claim_boundary": "Observer/core/source evidence only; no waveform transport and no family DUT verdict."}


RUNNER = r'''#!/usr/bin/env bash
# Parser/finalizer-published exact return members: SIM_TIME_HEARTBEAT.json OBSERVER_SIGNAL_CATALOG.json OBSERVER_EVENT_INDEX.json OBSERVER_DECISION.json RETURN_FINALIZER_STATE.json
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
package_id="r5_n4_hw_v89b_obswide"
install_name="$package_id"
package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
result_root="/home/panqs/ndp/simresult"
return_tag="r$(date -u +%s%N)_$$"
attempt="a$$"
return_zip="$result_root/${package_id}_${return_tag}_return.zip"
return_sha="${return_zip}.sha256"
server_root="${1:-}"
bootstrap_root="${server_root:-/invalid}/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_full_log="$bootstrap_root/compile_driver.full.log"
compile_status=125
run_status=125
signal_status=NONE
sim_started=false
timed_out=false
finalized=0
run_root=
evidence_root=
compile_root=
cfg_root=

runner_fail() { rc="$1"; shift; printf 'RUNNER_ERROR code=%s package=%s message=%s\n' "$rc" "$package_id" "$*" >&2; exit "$rc"; }

publish_minimal_return() {
  mkdir -p "$result_root" || return 98
  stage="$result_root/.${package_id}.${return_tag}.partial.$$"; [ ! -e "$stage" ] || return 98
  mkdir -p "$stage/evidence/compile_rootcause" || return 98
  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do [ -f "$source" ] && cp -f "$source" "$stage/evidence/compile_rootcause/$(basename "$source")"; done
  python3 - "$stage" "$return_zip" "$return_sha" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage,target,side,pkg,exe,att,code=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]),*sys.argv[4:]
cc=stage/"evidence/compile_rootcause"; cc.mkdir(parents=True,exist_ok=True)
(cc/"COMPILE_CORE.json").write_text(json.dumps({"schema":"server-compile-core-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":int(code)},indent=2,sort_keys=True)+"\n")
if not (cc/"compile_first_error.txt").is_file(): (cc/"compile_first_error.txt").write_text("runner failed before compile start\n")
argv={"schema":"server-observer-actual-argv-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"source_identity_status":"DIAGNOSTIC_EVIDENCE_INCOMPLETE","compile_argv":["make","compile","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"],"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"]}
(stage/"evidence/ACTUAL_COMPILE_SIM_ARGV.json").write_text(json.dumps(argv,indent=2,sort_keys=True)+"\n")
sim={"schema":"server-observer-sim-exit-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"simulation_started":False,"exit_code":125,"signal":"NONE","timed_out":False,"compile_exit":int(code)}
(stage/"evidence/SIM_EXIT_RECEIPT.json").write_text(json.dumps(sim,indent=2,sort_keys=True)+"\n")
members=sorted(f"{pkg}_return/{p.relative_to(stage).as_posix()}" for p in stage.rglob("*") if p.is_file())
manifest={"schema":"server-post-sim-return-core-manifest-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"members":members,"observer_only_profile":"OBSERVER_ONLY_WIDE_CAUSAL_V1"}
(stage/"RETURN_CORE_MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
tmp=target.with_name("."+target.name+".tmp."+str(os.getpid()))
with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED,allowZip64=True) as z:
  for p in sorted(x for x in stage.rglob("*") if x.is_file()): z.write(p,f"{pkg}_return/{p.relative_to(stage).as_posix()}")
os.replace(tmp,target); d=hashlib.sha256(target.read_bytes()).hexdigest(); st=side.with_name("."+side.name+".tmp."+str(os.getpid())); st.write_text(f"{d}  {target.name}\n"); os.replace(st,side)
PY
  rc=$?; rm -rf "$stage"; return "$rc"
}

write_actual_argv() {
  python3 - "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" "$package_id" "$return_tag" "$attempt" "$compile_status" "$1" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,ce,source=sys.argv[1:]
d={"schema":"server-observer-actual-argv-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":int(ce),"source_identity_status":source,
"compile_argv":["make","-f","Makefile.tb_NDP_Top_new_phy","compile","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0","RUN_DIR=<attempt-compile>","VCS_EXTRA_OPTS=<package-observer>"],
"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0","-l","<attempt-sim-log>","+SCA_CFG=<attempt-sca>","+SCA_CFG_D=<attempt-sca-d>","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL"]}
pathlib.Path(p).write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
PY
}

finalize() {
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1; trap - EXIT HUP INT TERM; set +e
  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then publish_minimal_return; exit "$original"; fi
  mkdir -p "$evidence_root/compile_rootcause"
  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do [ -f "$source" ] && cp -f "$source" "$evidence_root/compile_rootcause/$(basename "$source")"; done
  python3 - "$evidence_root/compile_rootcause/COMPILE_CORE.json" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,code=sys.argv[1:]
pathlib.Path(p).write_text(json.dumps({"schema":"server-compile-core-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":int(code)},indent=2,sort_keys=True)+"\n")
PY
  [ -f "$evidence_root/compile_rootcause/compile_first_error.txt" ] || printf '%s\n' 'compile did not start' > "$evidence_root/compile_rootcause/compile_first_error.txt"
  if [ ! -f "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" ]; then write_actual_argv DIAGNOSTIC_EVIDENCE_INCOMPLETE; fi
  if [ "$sim_started" = true ]; then
    python3 "$package_root/package_tools/node0004_observerwide_event_parser.py" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --chunk "$evidence_root/observer/chunks/events-000000.jsonl" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$run_status" --signal "$signal_status" --timed-out "$timed_out" --simulation-started true --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --heartbeat-log "$evidence_root/supervisor_heartbeat.jsonl" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --output-dir "$evidence_root"
    observer_rc=$?
  else
    python3 - "$evidence_root/SIM_EXIT_RECEIPT.json" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,code=sys.argv[1:]
pathlib.Path(p).write_text(json.dumps({"schema":"server-observer-sim-exit-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"simulation_started":False,"exit_code":125,"signal":"NONE","timed_out":False,"compile_exit":int(code)},indent=2,sort_keys=True)+"\n")
PY
    observer_rc=0
  fi
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" CODEX_PACKAGE_ID="$package_id" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL=false
  [ "$run_status" -eq 0 ] && export CODEX_NATURAL_TERMINAL=true
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core_rc=$?
  if [ -f "$return_zip" ]; then python3 "$package_root/package_tools/node0004_observerwide_return_manifest.py" --zip "$return_zip" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --sidecar "$return_sha"; manifest_rc=$?; else manifest_rc=98; fi
  final="$original"; [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"; [ "$observer_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}

on_signal() { signal_status="$1"; finalize "$2"; }
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

[ "$#" -eq 1 ] || runner_fail 2 "usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy01"
case "$1" in /*) ;; *) runner_fail 2 "server_root must be absolute";; esac
for tool in python3 make; do command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "missing tool: $tool"; done
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server root absent"
[ -f "$server_root/Makefile.tb_NDP_Top_new_phy" ] || runner_fail 4 "wrong server root"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"; compile_source_identity_json="$bootstrap_root/compile_source_identity.json"; compile_exit_txt="$bootstrap_root/compile_exit.txt"; compile_driver_log="$bootstrap_root/compile_driver.log"; compile_first_error_txt="$bootstrap_root/compile_first_error.txt"; compile_log_head_txt="$bootstrap_root/compile_log_head.txt"; compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"; compile_full_log="$bootstrap_root/compile_driver.full.log"
mkdir -p "$bootstrap_root" || runner_fail 14 "cannot create bootstrap evidence root"
printf '%s\n' '{"schema":"server-compile-argv-v1","status":"NOT_YET_RECORDED"}' > "$compile_argv_json"; printf '%s\n' '{"schema":"server-compile-source-identity-v1","status":"NOT_YET_RECORDED"}' > "$compile_source_identity_json"; printf '%s\n' 125 > "$compile_exit_txt"; printf '%s\n' 'compile driver has not started' > "$compile_driver_log"; cp "$compile_driver_log" "$compile_first_error_txt"; cp "$compile_driver_log" "$compile_log_head_txt"; cp "$compile_driver_log" "$compile_log_tail_txt"
mkdir -p "$result_root" || runner_fail 9 "cannot create result root"
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "return identity collision"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
layout_values="$(python3 "$layout_helper" prepare --server-root "$server_root" --package-id "$package_id" --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 13 "runtime layout prepare failed"
eval "$layout_values"
cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"
mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/observer/chunks" "$compile_root/sim_results" || runner_fail 14 "attempt layout create failed"
compile_log="$compile_full_log"
printf '%s\n' '{"schema":"server-compile-argv-v1","status":"STARTING","argv":["make","compile","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"]}' > "$compile_argv_json"
write_actual_argv NOT_YET_BOUND
cd "$server_root" || runner_fail 4 "cannot enter server root"
compile_argv=(make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 "RUN_DIR=$compile_root" "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe $package_root/tb_probe/observer_only_wide_causal.svh")
python3 - "$compile_argv_json" "$server_root" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-compile-argv-v1","cwd":sys.argv[2],"argv":sys.argv[3:]},indent=2,sort_keys=True)+"\n")
PY
set +e; timeout --foreground --signal=TERM --kill-after=30s 2h "${compile_argv[@]}" > "$compile_log" 2>&1; compile_status=$?; set -e
python3 - "$compile_log" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt" <<'PY'
import pathlib,re,sys
s,d,f,h,t=map(pathlib.Path,sys.argv[1:]); raw=s.read_bytes() if s.is_file() else b""; head=raw[:65536]; tail=raw[-65536:] if len(raw)>65536 else raw; h.write_bytes(head); t.write_bytes(tail); d.write_bytes(head+(b"\n--- BOUNDED HEAD/TAIL ---\n"+tail if len(raw)>65536 else b"")); lines=raw.decode(errors="replace").splitlines(); pats=[re.compile(x,re.I) for x in (r"^\s*(Error|Fatal)-\[",r"^\s*(error|fatal)\s*[:[]",r"^make: \*\*\*")]; hit=next((line for pat in pats for line in lines if pat.search(line)),next((line for line in lines if line.strip()),"compile log is empty")); f.write_text(hit[:4096]+"\n")
PY
printf '%s\n' "$compile_status" > "$compile_exit_txt"
set +e
python3 "$package_root/package_tools/node0004_actual_compile_source_identity.py" --server-root "$server_root" --package-root "$package_root" --compile-log "$compile_log" --compile-exit "$compile_exit_txt" --target-instance "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue" --output-dir "$evidence_root/compiled_source" --output "$compile_source_identity_json"
python3 "$package_root/package_tools/node0004_observerwide_source_identity.py" --server-root "$server_root" --compile-log "$compile_log" --compile-exit "$compile_exit_txt" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --output-dir "$evidence_root/compiled_source" --output "$evidence_root/compiled_source/source_identity.json"
source_rc=$?; set -e; source_status=DIAGNOSTIC_EVIDENCE_INCOMPLETE; [ "$source_rc" -eq 0 ] && source_status=COMPLETE; write_actual_argv "$source_status"
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed"
simv="$compile_root/sim_results/simv"; [ -x "$simv" ] || runner_fail 15 "simv missing"
sim_started=true
observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"
printf '%s\n' "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv -l $run_root/c0/sim.log +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_OBSERVER_ONLY_WIDE_CAUSAL +CODEX_OBSERVER_CHUNK=$observer_chunk" > "$run_root/c0/simulator_argv.txt"
set +e
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$evidence_root/supervisor_heartbeat.jsonl" --heartbeat-regex 'CODEX_OBSERVER_SIM_TIME_V1 sim_time=([0-9]+)' --timescale 1ps --timeout 21600 --interval 30 --grace 30 --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
run_status=$?
set -e
[ "$run_status" -eq 124 ] && timed_out=true
[ "$run_status" -eq 129 ] && signal_status=HUP
[ "$run_status" -eq 130 ] && signal_status=INT
[ "$run_status" -eq 143 ] && signal_status=TERM
exit "$run_status"
'''


def deterministic_zip() -> None:
    temp = FINAL_ZIP.with_name(f".{FINAL_ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
            relative = path.relative_to(BUILD_ROOT.parent).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 13, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temp) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("generated ZIP fails CRC")
    os.replace(temp, FINAL_ZIP)


def import_workload() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("smoke_base", ROOT / "tools/build_node0004_fsdb_smoke_s1.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE_ID
    module.OLD_ID = SOURCE_ID
    module.SOURCE_ZIP = SOURCE_ZIP
    module.OUT = OUT
    module.BUILD_ROOT = BUILD_ROOT
    return module.import_frozen_workload()


def file_map() -> list[dict[str, object]]:
    rows = []
    for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
        data = path.read_bytes()
        rows.append({"path": path.relative_to(BUILD_ROOT).as_posix(), "bytes": len(data), "sha256": sha(data)})
    return rows


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    BUILD_ROOT.mkdir(parents=True)
    frozen = import_workload()
    write_json("provenance/frozen_v88b_workload_import.json", frozen)
    write("provenance/v88_actual_target_source.sv", ACTUAL_BUFFER.read_bytes())
    selected = {
        "package_tools/server_post_sim_return.py": ROOT / "tools/server_post_sim_return.py",
        "package_tools/server_package_runtime_layout.py": ROOT / "tools/server_package_runtime_layout.py",
        "package_tools/server_observer_runtime_supervision.py": ROOT / "tools/server_observer_runtime_supervision.py",
        "package_tools/node0004_actual_compile_source_identity.py": ROOT / "tools/node0004_actual_compile_source_identity.py",
        "package_tools/node0004_observerwide_source_identity.py": ROOT / "tools/node0004_observerwide_source_identity.py",
        "package_tools/node0004_observerwide_event_parser.py": ROOT / "tools/node0004_observerwide_event_parser.py",
        "package_tools/node0004_observerwide_return_manifest.py": ROOT / "tools/node0004_observerwide_return_manifest.py",
    }
    for relative, source in selected.items():
        write(relative, source.read_bytes(), executable=True)
    contract_value = contract()
    contract_path = write_json("contracts/observer_only_wide_causal_contract.json", contract_value)
    write("tb_probe/observer_only_wide_causal.svh", observer_source(contract_value["signals"]).encode("utf-8"))
    write_json("contracts/server_post_sim_return_request.json", post_request())
    post_request_sha = sha((BUILD_ROOT / "contracts/server_post_sim_return_request.json").read_bytes())
    write_json("contracts/server_post_sim_return_contract.json", {
        "schema": "server-post-sim-return-contract-v1", "package_id": PACKAGE_ID,
        "helper_member": "package_tools/server_post_sim_return.py",
        "helper_sha256": sha((BUILD_ROOT / "package_tools/server_post_sim_return.py").read_bytes()),
        "request_member": "contracts/server_post_sim_return_request.json", "request_sha256": post_request_sha,
        "runner_member": "PREPARE_AND_RUN.sh", "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "sim_exit_persisted_before_plugins": True, "plugin_failure_blocks_core_return": False,
        "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"],
        "partial_exit_live_causal_record": {"rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "enforcement": "required_next_fresh", "required_signals": ["INT", "TERM"], "final_block_ring_sole_input_forbidden": True, "plugin_dispositions": []},
        "claim_boundary": "Observer/core publication with no waveform discovery; family signal interpretation remains separate.",
    })
    write_json("RETURN_ALLOWLIST.json", {"schema": "server-observer-return-allowlist-v1", "required": list(contract_value["return_members"].values()), "prefixes": [contract_value["return_members"]["chunk_prefix"]], "no_size_limit": True})
    write("PREPARE_AND_RUN.sh", RUNNER.encode("utf-8"), executable=True)
    runner_data = (BUILD_ROOT / "PREPARE_AND_RUN.sh").read_bytes()
    write_json("contracts/server_runner_return_resilience.json", {
        "schema": "server-runner-return-resilience-contract-v1", "package_id": PACKAGE_ID,
        "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh", "runner_sha256": sha(runner_data),
        "nounset_required": True, "bootstrap_root_variable": "bootstrap_root",
        "package_owned_variables": ["package_id", "install_name", "package_root", "result_root", "return_tag", "attempt", "return_zip", "return_sha", "server_root", "bootstrap_root", "compile_argv_json", "compile_source_identity_json", "compile_exit_txt", "compile_driver_log", "compile_first_error_txt", "compile_log_head_txt", "compile_log_tail_txt", "compile_full_log", "compile_status", "run_status", "signal_status", "sim_started", "timed_out", "finalized", "run_root", "evidence_root", "compile_root", "cfg_root"],
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"], "first_fallible_tokens": ["command -v", "make -f"],
        "compile_evidence_tokens": {"argv": "compile_argv.json", "source_identity": "compile_source_identity.json", "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log", "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt", "bounded_tail": "compile_log_tail.txt"},
        "return_allowlist_tokens": ["ACTUAL_COMPILE_SIM_ARGV.json", "SIM_EXIT_RECEIPT.json", "PROCESS_TREE_RECEIPT.json", "SIM_TIME_HEARTBEAT.json", "OBSERVER_SIGNAL_CATALOG.json", "OBSERVER_EVENT_INDEX.json", "OBSERVER_DECISION.json", "events-000000.jsonl", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    })
    write("README.md", f"""# {PACKAGE_ID}\n\nFormal serialized Conv observer-only wide-causal successor.\n\nPrevious progress: v88b compiled/elaborated and proved the retired ACK comparator was an observer/source-identity semantic false positive; the portable path stopped at time zero. The later FSDB smoke advanced but plateaued and did not adjudicate the DUT.\n\nCurrent purpose: preserve the exact v88 workload/config/numeric/golden/functional RTL while collecting the complete actual ACK, row/column FIFO, aggregate queue, accept/backpressure, MSE4 write-data, terminal and formal-D causal cone. No waveform format or vendor query is used.\n\nRun only when authorized:\n\n    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\nThe observer evidence soft threshold is decimal 100000000 bytes and warning-only. There is no hard byte/event/time cap, sampling, truncation, head-tail reduction or size deletion.\n""".encode("utf-8"))
    write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", {"schema": "server-package-runtime-layout-contract-v1", "package_id": PACKAGE_ID, "install_name": PACKAGE_ID, "attempt_identity": "fresh_per_invocation", "repeat_safe_exact_owned_reset": True, "foreign_siblings_preserved": True, "return_unique_atomic_no_overwrite": True, "compile_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile", "run_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}", "cfg_root": f"install/cfg_pkg/{PACKAGE_ID}"})
    manifest = {
        "schema": "node0004-observer-only-wide-causal-package-v1", "package_id": PACKAGE_ID,
        "install_name": PACKAGE_ID, "family": FAMILY, "status": "PACKAGE_BUILT_AWAITING_GATES",
        "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "observer_only_contract_sha256": sha(canonical(contract_value)),
        "activation_epoch": "observer-only-wide-causal-v1", "first_fresh_after_change": True,
        "post_sim_conjunction_activation_epoch": "observer-only-post-sim-conjunction-fix-v1",
        "first_fresh_extra_audit": {
            "epoch_id": "observer-only-post-sim-conjunction-fix-v1",
            "base_epoch": "observer-only-wide-causal-v1",
            "bound_package_id": PACKAGE_ID,
            "notification_acknowledged": True,
            "first_fresh_after_change": True,
            "receipt_reuse_allowed": False,
        },
        "dump": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "retired_buf_idx_queue_bp_pre_comparator_present": False,
        "previous_version_progress": "v88b production compile/elaboration passed and actual compiled source proved the old ACK comparator was a semantic false positive; portable control stopped before time advance. FSDB smoke s2 later advanced to 2.446091 ms then plateaued; s4 was only a quiescence smoke.",
        "current_purpose": "One formal observer-only run covering actual ACK, row/column FIFO, aggregate queue, accept/backpressure, MSE4 write-data, terminal and formal-D causal state without waveform transport.",
        "server_actions_performed": [], "source_package": SOURCE_ID, "files": [],
    }
    write_json("package_manifest.json", manifest)
    manifest["files"] = [row for row in file_map() if row["path"] != "package_manifest.json"]
    write_json("package_manifest.json", manifest)
    deterministic_zip()
    write_json("build_receipt.json", {"schema": "node0004-observerwide-build-v1", "package_id": PACKAGE_ID, "zip": {"path": FINAL_ZIP.relative_to(ROOT).as_posix(), "bytes": FINAL_ZIP.stat().st_size, "sha256": sha(FINAL_ZIP.read_bytes())}, "contract": {"path": contract_path.relative_to(ROOT).as_posix(), "bytes": contract_path.stat().st_size, "sha256": sha(contract_path.read_bytes())}, "member_count": len(file_map()), "pass": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
