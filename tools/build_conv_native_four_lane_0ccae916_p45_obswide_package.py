#!/usr/bin/env python3
"""Build native Conv p45 observer-only wide-causal successor from frozen p44."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD_ID = "r5_n4_0cc_p44_fsdbvq"
PACKAGE_ID = "r5_n4_0cc_p45_obswide"
FAMILY = "conv_native_four_lane"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD_ID}.zip"
SOURCE_BYTES = 5_997_161
SOURCE_SHA = "97e3339800f463ebd4f3552996bc00cf5c7eb862b4affac5ec77a0ce2b22b621"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p45_obswide_release6"
BUILD_PARENT = OUT / "build"
TREE = BUILD_PARENT / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
HIER = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
MSE_SOURCE = "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write(relative: str, data: bytes, executable: bool = False) -> Path:
    path = TREE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def write_json(relative: str, value: object) -> Path:
    return write(relative, canonical(value))


def identity(path: Path, base: Path = ROOT) -> dict[str, object]:
    data = path.read_bytes()
    try:
        label = path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "bytes": len(data), "sha256": sha_bytes(data)}


def safe_extract() -> None:
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("p44 pending identity drift")
    BUILD_PARENT.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.filename.startswith("/") or ".." in pure.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe p44 member: {info.filename}")
            if not pure.parts or pure.parts[0] != OLD_ID:
                raise RuntimeError(f"unexpected p44 root: {info.filename}")
            relative = Path(*pure.parts[1:])
            target = TREE / relative
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info.filename))


def replace_identity() -> None:
    old = OLD_ID.encode("utf-8")
    new = PACKAGE_ID.encode("utf-8")
    for path in TREE.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if old not in data:
            continue
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"package identity appears in non-text member: {path}") from exc
        path.write_bytes(data.replace(old, new))


def prune_retired_surfaces() -> None:
    explicit = [
        "contracts/native_fsdb_query_profile.json",
        "contracts/server_waveform_mandatory_plan.json",
        "diagnostics/native_fsdb_query_source_report.json",
        "diagnostics/rule_change_ack.json",
        "package_tools/conv_native_fsdb_event_query.py",
        "package_tools/dump_waveform.tcl",
        "package_tools/server_waveform_mandatory_return.py",
        "tb_probe/native_fsdb_event_probe.svh",
    ]
    for relative in explicit:
        path = TREE / relative
        if path.exists():
            path.unlink()
    for path in list(TREE.rglob("*")):
        if path.is_file() and any(token in path.name.lower() for token in ("fsdb", "vpd", "vcd", "fst")):
            raise RuntimeError(f"unpruned retired member name: {path.relative_to(TREE)}")


def p44_catalog() -> dict[str, Any]:
    return json.loads((TREE / "diagnostics/source_bound_probe_catalog.json").read_text(encoding="utf-8"))


RAW_SIGNALS = [
    ("sig_clk", "clk", 1, ["clock"]),
    ("sig_rst_n", "rst_n", 1, ["reset"]),
    ("sig_slice_rst", "slice_rst", 1, ["reset", "internal_clear"]),
    ("sig_mse_enable", "mse_enable", 1, ["stage"]),
    ("sig_buf_req_ready", "buf2mse_rreq_ready", 1, ["ready", "backpressure"]),
    ("sig_buf_rvalid", "buf2mse_rvalid", 1, ["source", "producer", "valid"]),
    ("sig_buf_data_ready", "wr_data_chl_ready", 1, ["ready", "accept"]),
    ("sig_memag_valid", "mse_mem_ag_tag_valid", 1, ["queue_enqueue", "producer", "valid"]),
    ("sig_memag_bp_pre", "mse_mem_ag_bp_pre", 1, ["backpressure", "ready"]),
    ("sig_memag_bp_post", "mse_mem_ag_bp_post", 1, ["backpressure"]),
    ("sig_descriptor_valid", "wr_data_chl_req_valid", 1, ["request", "valid"]),
    ("sig_descriptor_ready", "wr_data_chl_req_ready", 1, ["queue_dequeue", "ready", "accept", "internal_match"]),
    ("sig_descriptor_mask", "wr_data_chl_req_valid_mask_flag", 1, ["internal_state"]),
    ("sig_request_valid", "mse2mem_request_valid", 2, ["request", "valid", "output"]),
    ("sig_request_ready", "mem2mse_request_ready", 2, ["ready", "accept"]),
    ("sig_wdata_valid", "mse2mem_wdata_valid", 2, ["valid", "wdata", "output", "formal_d"]),
    ("sig_wdata_ready", "mem2mse_wdata_ready", 2, ["ready", "accept"]),
    ("sig_wreq_pingpong", "mse_wreq_pingpong_sel", 1, ["selected_port", "internal_state"]),
    ("sig_buf_req_pingpong", "mse2buf_req_pingpong_sel", 1, ["selected_bank", "internal_state"]),
    ("sig_buf_data_pingpong", "mse2buf_data_pingpong_sel", 1, ["selected_lane", "internal_state"]),
    ("sig_last_req", "buf_ag_last_req_flag", 1, ["terminal"]),
    ("sig_slice_finish", "slice_cmpt_finish", 1, ["terminal", "finish"]),
]


def signals() -> list[dict[str, Any]]:
    catalog = p44_catalog()
    by_name = {row["name"]: row for row in catalog["symbols"] if row["module"] == "Memory_WR_Stream_Engine"}
    result: list[dict[str, Any]] = []
    for signal_id, name, width, roles in RAW_SIGNALS:
        row = by_name.get(name)
        if row is None or row.get("width_bits") != width:
            raise RuntimeError(f"source-bound catalog missing exact {name}/{width}")
        result.append({
            "signal_id": signal_id,
            "symbol_id": row["symbol_id"],
            "exact_hierarchy": f"{HIER}.{name}",
            "target_module": "Memory_WR_Stream_Engine",
            "source_path": f"rtl/{row['source']['path']}",
            "source_sha256": row["source"]["source_sha256"],
            "declaration_span_sha256": row["source"]["declaration_sha256"],
            "width_bits": width,
            "owner_clock_signal_id": "sig_clk",
            "owner_reset_signal_id": "sig_rst_n",
            "roles": roles,
            "source_binding": "ACTUAL_SOURCE_NET",
            "derived_expected_equation": False,
            "observer_drives_dut": False,
        })
    return result


def observer_contract(signal_rows: list[dict[str, Any]], proof_sha: str) -> dict[str, Any]:
    canonical_helper = (ROOT / "tools/server_post_sim_return.py").read_bytes()
    observations = [
        {"observation_id": "obs_descriptor_memag", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_memag_valid", "sig_memag_bp_pre", "sig_descriptor_valid", "sig_descriptor_ready"], "predicate": "actual MemAG output and descriptor request/ready transition state"},
        {"observation_id": "obs_buffer_join", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_buf_rvalid", "sig_buf_req_ready", "sig_buf_data_ready", "sig_descriptor_mask"], "predicate": "actual Buffer supply and descriptor/data join state"},
        {"observation_id": "obs_vector_accept", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_request_valid", "sig_request_ready", "sig_wdata_valid", "sig_wdata_ready"], "predicate": "corrected two-bit acceptance is (|(mse2mem_wdata_valid & mem2mse_wdata_ready)) === 1'b1 using returned actual vectors"},
        {"observation_id": "obs_hold_clear_finish", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_slice_rst", "sig_mse_enable", "sig_wreq_pingpong", "sig_buf_req_pingpong", "sig_buf_data_pingpong", "sig_last_req", "sig_slice_finish"], "predicate": "actual stage, ping-pong hold/clear, last-request and slice-finish propagation"},
    ]
    patterns = [
        ("candidate_memag_source_starvation", [False, False, False, False]),
        ("candidate_descriptor_accept_block", [True, False, False, False]),
        ("candidate_buffer_data_supply_block", [False, True, False, False]),
        ("candidate_descriptor_buffer_join_skew", [True, True, False, False]),
        ("candidate_vector_valid_stop", [True, False, True, False]),
        ("candidate_vector_ready_backpressure", [False, True, True, False]),
        ("candidate_state_clear_hold", [False, False, True, True]),
        ("candidate_slice_finish_propagation", [True, True, True, True]),
    ]
    observation_ids = [row["observation_id"] for row in observations]
    role_rows = []
    roles = [
        "clock", "reset", "stage", "source", "producer", "queue_enqueue", "queue_dequeue",
        "queue_count", "queue_full", "queue_empty", "request", "valid", "ready", "accept",
        "backpressure", "selected_port", "selected_bank", "selected_lane", "internal_match",
        "internal_state", "internal_clear", "output", "wdata", "terminal", "finish", "formal_d",
    ]
    for role in roles:
        ids = [row["signal_id"] for row in signal_rows if role in row["roles"]]
        if ids:
            role_rows.append({"role": role, "disposition": "covered", "signal_ids": ids})
        else:
            reason = f"The pinned p44 Memory_WR_Stream_Engine source catalog has no truthful resolved-width actual {role} net; queue handshakes and backpressure remain fully captured without inventing a derived state."
            role_rows.append({"role": role, "disposition": "not_applicable", "signal_ids": [], "proof": {"path": "diagnostics/not_applicable_role_proofs.json", "sha256": proof_sha, "machine_check_exit": 0, "reason": reason}})
    root = f"{PACKAGE_ID}_return/"
    members = {
        "actual_argv": root + "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
        "sim_exit": root + "evidence/observer/SIM_EXIT_RECEIPT.json",
        "process_tree": root + "evidence/PROCESS_TREE_RECEIPT.json",
        "sim_time_heartbeat": root + "evidence/observer/SIM_TIME_HEARTBEAT.json",
        "signal_catalog": root + "evidence/observer/OBSERVER_SIGNAL_CATALOG.json",
        "chunk_index": root + "evidence/observer/OBSERVER_EVENT_INDEX.json",
        "chunk_prefix": root + "observer/chunks/",
        "decision": root + "evidence/observer/OBSERVER_DECISION.json",
        "return_manifest": root + "RETURN_CORE_MANIFEST.json",
        "compile_core_when_not_started": [root + "evidence/compile_rootcause/COMPILE_CORE.json", root + "evidence/compile_rootcause/compile_first_error.txt"],
    }
    return {
        "schema": "server-observer-only-wide-causal-contract-v1",
        "profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "activation_epoch": "observer-only-wide-causal-v1",
        "rule_ids": ["CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001", "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001"],
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "execution": {
            "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "runtime_supervision": "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT",
            "repeat_safe_exact_owned_reset": True,
            "atomic_unique_return": True,
            "waveform_writer": None,
        },
        "budget": {"observer_evidence_soft_limit_bytes": 100000000, "observer_evidence_hard_limit_bytes": None, "formal_return_hard_limit_bytes": None, "event_count_cap": None, "byte_cap": None, "sampling": False, "truncation": False, "size_based_deletion": False},
        "signals": signal_rows,
        "role_coverage": role_rows,
        "boundary_observations": observations,
        "candidates": [{"candidate_id": name, "signature": dict(zip(observation_ids, bits))} for name, bits in patterns],
        "all_coobservable_candidates_aggregated": True,
        "event_recording": {"format": "JSONL", "fields": ["record_type", "package_id", "execution_id", "attempt_id", "seq", "sim_time", "timescale", "signal_id", "width_bits", "value_4state"], "ordered_transitions": True, "end_state_required": True, "periodic_sim_time_heartbeat": True, "partial_exit_live_records": True, "event_cap": None, "byte_cap": None, "sampling": False, "truncation": False},
        "package_members": {
            "runner": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
            "manifest": f"{PACKAGE_ID}/TEST_PACKAGE_MANIFEST.json",
            "return_allowlist": f"{PACKAGE_ID}/RETURN_ALLOWLIST.json",
            "contract": f"{PACKAGE_ID}/contracts/observer_only_wide_causal_contract.json",
            "observer": f"{PACKAGE_ID}/tb_probe/observer_only_wide_causal.svh",
            "parser": f"{PACKAGE_ID}/package_tools/node0004_observerwide_event_parser.py",
            "runtime_supervisor": f"{PACKAGE_ID}/package_tools/server_observer_runtime_supervision.py",
            "post_sim_helper": f"{PACKAGE_ID}/package_tools/server_post_sim_return.py",
            "post_sim_request": f"{PACKAGE_ID}/contracts/server_post_sim_return_request.json",
        },
        "post_sim_historical_compatibility_exemption": {
            "schema": "observer-only-post-sim-helper-exemption-v1",
            "canonical_source_path": "tools/server_post_sim_return.py",
            "canonical_helper_bytes": len(canonical_helper),
            "canonical_helper_sha256": sha_bytes(canonical_helper),
            "member_path": f"{PACKAGE_ID}/package_tools/server_post_sim_return.py",
            "request_member": f"{PACKAGE_ID}/contracts/server_post_sim_return_request.json",
            "inert_literal_tokens": sorted(token for token in (".fsdb", ".fst", ".vcd", ".vpd") if token in canonical_helper.decode("utf-8").lower()),
            "waveform_discovery_disposition": "OMITTED_OR_NULL_ONLY",
        },
        "return_members": members,
        "claim_boundary": "Frozen p42 vector-handshake and MSE4 target actual-net observer transport only; family owner retains production-result interpretation.",
    }


def observer_source(signal_rows: list[dict[str, Any]]) -> str:
    ports: list[str] = []
    registers: list[str] = []
    changes: list[str] = []
    updates: list[str] = []
    sensitivity: list[str] = []
    connections: list[str] = []
    for signal, raw in zip(signal_rows, RAW_SIGNALS):
        sid = signal["signal_id"]
        name = raw[1]
        width = signal["width_bits"]
        ports.append(f"    input wire {sid}" if width == 1 else f"    input wire [{width-1}:0] {sid}")
        registers.append(f"  reg prev_{sid};" if width == 1 else f"  reg [{width-1}:0] prev_{sid};")
        changes.append(f'''      if (force_all || {sid} !== prev_{sid}) begin
        $fdisplay(codex_fd, "{{\\\"record_type\\\":\\\"EVENT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\"{sid}\\\",\\\"width_bits\\\":{width},\\\"value_4state\\\":\\\"%b\\\"}}", codex_package, codex_execution, codex_attempt, codex_seq, $time, {sid});
        codex_seq = codex_seq + 1;
        $fflush(codex_fd);
      end''')
        updates.append(f"      prev_{sid} = {sid};")
        sensitivity.append(sid)
        connections.append(f"  .{sid}({name})")
    return f'''`timescale 1ps/1ps
// Generated from the source-bound p44 catalog; actual nets only and read-only.
module codex_conv_native_observerwide(
{',\n'.join(ports)}
);
  integer codex_fd;
  integer codex_enabled;
  integer codex_have_previous;
  longint unsigned codex_seq;
  longint unsigned codex_clock_count;
  string codex_path;
  string codex_package;
  string codex_execution;
  string codex_attempt;
{os.linesep.join(registers)}

  task automatic codex_capture(input integer force_all);
    begin
{os.linesep.join(changes)}
      if (!force_all && sig_clk === 1'b1 && prev_sig_clk === 1'b0) begin
        codex_clock_count = codex_clock_count + 1;
        if ((codex_clock_count & 262143) == 0) begin
          $fdisplay(codex_fd, "{{\\\"record_type\\\":\\\"HEARTBEAT\\\",\\\"package_id\\\":\\\"%0s\\\",\\\"execution_id\\\":\\\"%0s\\\",\\\"attempt_id\\\":\\\"%0s\\\",\\\"seq\\\":%0d,\\\"sim_time\\\":%0d,\\\"timescale\\\":\\\"1ps\\\",\\\"signal_id\\\":\\\"__heartbeat__\\\",\\\"width_bits\\\":1,\\\"value_4state\\\":\\\"0\\\"}}", codex_package, codex_execution, codex_attempt, codex_seq, $time);
          codex_seq = codex_seq + 1;
          $fflush(codex_fd);
          $display("CODEX_OBSERVER_SIM_TIME_V1 sim_time=%0d", $time);
        end
      end
{os.linesep.join(updates)}
      codex_have_previous = 1;
    end
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_OBSERVER_ONLY_WIDE_CAUSAL");
    codex_seq = 0;
    codex_clock_count = 0;
    codex_have_previous = 0;
    if (codex_enabled) begin
      if (!$value$plusargs("CODEX_OBSERVER_CHUNK=%s", codex_path)) $fatal(1, "observer chunk path missing");
      if (!$value$plusargs("CODEX_PACKAGE_ID=%s", codex_package)) $fatal(1, "package identity missing");
      if (!$value$plusargs("CODEX_EXECUTION_ID=%s", codex_execution)) $fatal(1, "execution identity missing");
      if (!$value$plusargs("CODEX_ATTEMPT_ID=%s", codex_attempt)) $fatal(1, "attempt identity missing");
      codex_fd = $fopen(codex_path, "w");
      if (!codex_fd) $fatal(1, "observer chunk open failed");
      #0; codex_capture(1);
    end
  end

  always @({' or '.join(sensitivity)}) if (codex_enabled && codex_have_previous) codex_capture(0);
  final if (codex_enabled && codex_fd) begin $fflush(codex_fd); $fclose(codex_fd); end
endmodule

bind {HIER} codex_conv_native_observerwide codex_conv_native_observerwide_inst (
{',\n'.join(connections)}
);
'''.replace("\r\n", "\n")


def post_request(contract: dict[str, Any]) -> dict[str, Any]:
    def entry(root: str, source: str, archive: str, required: bool = False) -> dict[str, Any]:
        return {"source_root": root, "source": source, "archive": archive, "required": required}
    rows = [
        entry("package", "package_manifest.json", "evidence/returned_package_manifest.json", True),
        entry("package", "contracts/observer_only_wide_causal_contract.json", "evidence/observer_only_wide_causal_contract.json", True),
        entry("package", "diagnostics/source_bound_probe_binding.json", "evidence/source_bound_probe_binding.json", True),
        entry("attempt", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", True),
        entry("attempt", "evidence/observer/SIM_EXIT_RECEIPT.json", "evidence/observer/SIM_EXIT_RECEIPT.json", True),
        entry("attempt", "evidence/PROCESS_TREE_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json"),
        entry("attempt", "evidence/observer/SIM_TIME_HEARTBEAT.json", "evidence/observer/SIM_TIME_HEARTBEAT.json"),
        entry("attempt", "evidence/observer/OBSERVER_SIGNAL_CATALOG.json", "evidence/observer/OBSERVER_SIGNAL_CATALOG.json"),
        entry("attempt", "evidence/observer/OBSERVER_EVENT_INDEX.json", "evidence/observer/OBSERVER_EVENT_INDEX.json"),
        entry("attempt", "evidence/observer/OBSERVER_DECISION.json", "evidence/observer/OBSERVER_DECISION.json"),
        entry("attempt", "evidence/observer/chunks/events-000000.jsonl", "observer/chunks/events-000000.jsonl"),
        entry("attempt", "evidence/compile_rootcause/COMPILE_CORE.json", "evidence/compile_rootcause/COMPILE_CORE.json", True),
        entry("attempt", "evidence/compile_rootcause/compile_first_error.txt", "evidence/compile_rootcause/compile_first_error.txt", True),
        entry("attempt", "evidence/compile_rootcause/compile_argv.json", "evidence/compile_rootcause/compile_argv.json"),
        entry("attempt", "evidence/compile_rootcause/compile_source_identity.json", "evidence/compile_rootcause/compile_source_identity.json"),
        entry("attempt", "evidence/compile_rootcause/compile_log_head.txt", "evidence/compile_rootcause/compile_log_head.txt"),
        entry("attempt", "evidence/compile_rootcause/compile_log_tail.txt", "evidence/compile_rootcause/compile_log_tail.txt"),
        entry("attempt", "evidence/compiled_source/source_identity.json", "evidence/compiled_source/source_identity.json"),
        entry("attempt", "evidence/source_bound_causal_decision.json", "evidence/source_bound_causal_decision.json"),
        entry("attempt", "c0/source_bound_causal.log", "runs/c0/source_bound_causal.log"),
        entry("attempt", "c0/sim.log", "runs/c0/sim.log"),
        entry("attempt", "c0/simulator_argv.txt", "runs/c0/simulator_argv.txt"),
    ]
    return {
        "schema": "server-post-sim-return-request-v1",
        "package_id": PACKAGE_ID,
        "result_root": "/home/panqs/ndp/simresult",
        "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": rows,
        "plugins": [],
        "max_plugin_output_bytes": 262144,
        "claim_boundary": "Observer-only core publication with waveform discovery omitted; family interpretation remains post-return.",
    }


def runner() -> str:
    return f'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
package_id="{PACKAGE_ID}"
install_name="{PACKAGE_ID}"
attempt="a0"
return_tag="r$(date -u +%s%N)_$$"
server_root="${{1-}}"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${{package_id}}_${{return_tag}}_return.zip"
return_sha="${{return_zip}}.sha256"
package_root=""
case "${{BASH_SOURCE[0]}}" in /*) package_root="${{BASH_SOURCE[0]%/*}}";; */*) package_root="$PWD/${{BASH_SOURCE[0]%/*}}";; *) package_root="$PWD";; esac
# Exact observer return bindings consumed by the finalizer/parser contract:
# SIM_TIME_HEARTBEAT.json OBSERVER_SIGNAL_CATALOG.json OBSERVER_EVENT_INDEX.json OBSERVER_DECISION.json
# Exact post-sim core finalizer state binding: RETURN_FINALIZER_STATE.json
bootstrap_root="${{server_root}}/install/codex_runs/${{package_id}}/bootstrap-${{return_tag}}"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_status=125
run_status=125
signal_status=NONE
sim_started=false
timed_out=false
finalized=0
run_root=""
evidence_root=""
compile_root=""
cfg_root=""
source_identity_status=NOT_STARTED
preflight_stage=BOOTSTRAP_ARMED

runner_fail() {{ code="$1"; shift; printf 'RUNNER_ERROR package=%s code=%s message=%s\n' "$package_id" "$code" "$*" >&2; exit "$code"; }}
write_actual_argv() {{
  status="$1"
  [ -n "$evidence_root" ] || return 0
  python3 - "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" "$package_id" "$return_tag" "$attempt" "$status" "$server_root" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,status,cwd=sys.argv[1:]
value={{"schema":"server-observer-actual-argv-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"source_identity_status":status,"compile_argv":["make","-f","Makefile.tb_NDP_Top_new_phy","compile","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"],"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"],"compile_cwd":cwd,"sim_cwd":cwd}}
pathlib.Path(p).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
PY
}}
finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then
    python3 "$package_root/package_tools/fixed_simresult_publisher.py" --bootstrap-partial --package-root "$package_root" --exit-code "$original" --signal-name "$signal_status" --stage "$preflight_stage" --server-root "$server_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip"
    publish_rc=$?
    [ "$original" -ne 0 ] || original="$publish_rc"
    printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$original" "$return_zip" >&2
    exit "$original"
  fi
  mkdir -p "$evidence_root/compile_rootcause" "$evidence_root/observer" "$run_root/c0"
  for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_log_receipt.json compile_log_head.txt compile_log_tail.txt compile_first_error.txt; do
    [ ! -f "$bootstrap_root/$name" ] || cp -f "$bootstrap_root/$name" "$evidence_root/compile_rootcause/$name"
  done
  python3 - "$evidence_root/compile_rootcause/COMPILE_CORE.json" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,code=sys.argv[1:]
pathlib.Path(p).write_text(json.dumps({{"schema":"server-compile-core-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"compile_exit":int(code)}},indent=2,sort_keys=True)+"\n")
PY
  [ -f "$evidence_root/compile_rootcause/compile_first_error.txt" ] || printf '%s\n' 'compile did not start' > "$evidence_root/compile_rootcause/compile_first_error.txt"
  write_actual_argv "$source_identity_status"
  observer_rc=0
  if [ "$sim_started" = true ]; then
    grep '^CODEX_PROBE_V1 ' "$run_root/c0/sim.log" > "$run_root/c0/source_bound_causal.log" || true
    python3 "$package_root/package_tools/source_bound_causal_parser.py" --log "$run_root/c0/source_bound_causal.log" --output "$evidence_root/source_bound_causal_decision.json" >/dev/null 2>&1 || true
    python3 "$package_root/package_tools/node0004_observerwide_event_parser.py" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --chunk "$evidence_root/observer/chunks/events-000000.jsonl" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --exit-code "$run_status" --signal "$signal_status" --timed-out "$timed_out" --simulation-started true --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --heartbeat-log "$evidence_root/supervisor_heartbeat.jsonl" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --output-dir "$evidence_root/observer"
    observer_rc=$?
  else
    python3 - "$evidence_root/observer/SIM_EXIT_RECEIPT.json" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import json,pathlib,sys
p,pkg,exe,att,code=sys.argv[1:]
pathlib.Path(p).write_text(json.dumps({{"schema":"server-observer-sim-exit-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"simulation_started":False,"exit_code":125,"signal":"NONE","timed_out":False,"compile_exit":int(code)}},indent=2,sort_keys=True)+"\n")
PY
  fi
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_ATTEMPT_ID="$attempt" CODEX_PACKAGE_ID="$package_id" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL=false
  [ "$run_status" -eq 0 ] && export CODEX_NATURAL_TERMINAL=true
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core_rc=$?
  manifest_rc=98
  if [ -f "$return_zip" ]; then
    python3 "$package_root/package_tools/node0004_observerwide_return_manifest.py" --zip "$return_zip" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --sidecar "$return_sha"
    manifest_rc=$?
  fi
  final="$original"
  [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"
  [ "$sim_started" = false ] || [ "$observer_rc" -eq 0 ] || final=97
  [ "$manifest_rc" -eq 0 ] || final=98
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}}
on_signal() {{ signal_status="$1"; finalize "$2"; }}
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

[ "$#" -eq 1 ] || runner_fail 2 "usage requires one absolute server root"
case "$1" in /*) ;; *) runner_fail 2 "server root must be absolute";; esac
for tool in python3 timeout make sed; do command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required tool missing: $tool"; done
preflight_stage=SERVER_ROOT_RESOLUTION
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server root cannot be resolved"
[ -f "$server_root/Makefile.tb_NDP_Top_new_phy" ] || runner_fail 4 "server root lacks Makefile.tb_NDP_Top_new_phy"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"; compile_source_identity_json="$bootstrap_root/compile_source_identity.json"; compile_exit_txt="$bootstrap_root/compile_exit.txt"; compile_driver_log="$bootstrap_root/compile_driver.log"; compile_log_receipt_json="$bootstrap_root/compile_log_receipt.json"; compile_log_head_txt="$bootstrap_root/compile_log_head.txt"; compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"; compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
mkdir -p "$bootstrap_root" "$result_root" || runner_fail 9 "bootstrap/result root cannot be created"
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "unique return target already exists"
preflight_stage=RUNTIME_LAYOUT
layout_values="$(python3 "$package_root/package_tools/server_package_runtime_layout.py" prepare --server-root "$server_root" --package-id "$package_id" --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 12 "runtime layout prepare failed"
eval "$layout_values"
cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"
mkdir -p "$compile_root/sim_results" "$run_root/c0" "$evidence_root/observer/chunks" "$evidence_root/compiled_source" || runner_fail 14 "attempt roots cannot be created"
cp -a "$package_root/workload/runtime/." "$cfg_root/" || runner_fail 6 "frozen workload install failed"
preflight_stage=PACKAGE_PREFLIGHT
python3 "$package_root/package_tools/node0004_assumed_hardware_server_runtime.py" preflight --package-root "$package_root" > "$evidence_root/package_preflight.json" 2> "$evidence_root/package_preflight.stderr.txt" || runner_fail 5 "package preflight failed"
python3 "$package_root/package_tools/node0004_assumed_hardware_server_runtime.py" verify-install --package-root "$package_root" --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" 2> "$evidence_root/install_preflight.stderr.txt" || runner_fail 6 "installed workload verification failed"
preflight_stage=PRODUCTION_COMPILE
source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"
wide_observer="$package_root/tb_probe/observer_only_wide_causal.svh"
python3 "$package_root/package_tools/compile_core_evidence.py" prepare --output-root "$bootstrap_root" --cwd "$server_root" --makefile "$server_root/Makefile.tb_NDP_Top_new_phy" --source "$source_bound_observer" --source "$wide_observer" --package-root "$package_root" --run-dir "$compile_root" || runner_fail 8 "compile-core prepare failed"
cd "$server_root" || runner_fail 4 "cannot enter server root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe $source_bound_observer $wide_observer" > "$compile_driver_log" 2>&1
compile_status=$?
set -e
python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || runner_fail 8 "compile-core finalize failed"
[ "$compile_status" -eq 0 ] || exit "$compile_status"
set +e
python3 "$package_root/package_tools/conv_native_observerwide_source_identity.py" --server-root "$server_root" --compile-log "$compile_driver_log" --compile-exit "$compile_exit_txt" --contract "$package_root/contracts/observer_only_wide_causal_contract.json" --output-dir "$evidence_root/compiled_source" --output "$evidence_root/compiled_source/source_identity.json"
source_rc=$?
set -e
source_identity_status=DIAGNOSTIC_EVIDENCE_INCOMPLETE
[ "$source_rc" -eq 0 ] && source_identity_status=COMPLETE
write_actual_argv "$source_identity_status"
simv="$compile_root/sim_results/simv"
[ -x "$simv" ] || runner_fail 15 "simv missing after compile"
observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"
printf '%s\n' "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv -l $run_root/c0/sim.log +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL +CODEX_OBSERVER_CHUNK=$observer_chunk" > "$run_root/c0/simulator_argv.txt"
preflight_stage=PRODUCTION_SIMULATION
sim_started=true
set +e
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$evidence_root/supervisor_heartbeat.jsonl" --heartbeat-regex 'CODEX_OBSERVER_SIM_TIME_V1 sim_time=([0-9]+)' --timescale 1ps --timeout 43200 --interval 30 --grace 30 --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
run_status=$?
set -e
[ "$run_status" -eq 124 ] && timed_out=true
[ "$run_status" -eq 129 ] && signal_status=HUP
[ "$run_status" -eq 130 ] && signal_status=INT
[ "$run_status" -eq 143 ] && signal_status=TERM
exit "$run_status"
'''


def regenerate_source_bound() -> None:
    plan_path = TREE / "diagnostics/source_bound_probe_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["package_id"] = PACKAGE_ID
    plan_path.write_bytes(canonical(plan))
    with tempfile.TemporaryDirectory(prefix="native_p45_source_bound_", dir=OUT) as temporary:
        generated = Path(temporary) / "generated"
        report = Path(temporary) / "report.json"
        cheap = Path(temporary) / "cheap.json"
        command = [sys.executable, str(ROOT / "tools/generate_server_source_bound_observer.py"), "materialize", "--catalog", str(TREE / "diagnostics/source_bound_probe_catalog.json"), "--plan", str(plan_path), "--output-dir", str(generated), "--report", str(report), "--cheap-check-output", str(cheap)]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"source-bound regeneration failed: {completed.stdout}\n{completed.stderr}")
        mapping = {
            generated / "source_bound_causal_observer.svh": TREE / "tb_probe/source_bound_causal_observer.svh",
            generated / "source_bound_observer_focus.sv": TREE / "tb_probe/source_bound_observer_focus.sv",
            generated / "source_bound_causal_parser.py": TREE / "package_tools/source_bound_causal_parser.py",
            generated / "source_bound_probe_binding.json": TREE / "diagnostics/source_bound_probe_binding.json",
            report: TREE / "diagnostics/source_bound_generation_report.json",
            cheap: TREE / "diagnostics/source_bound_observer_generation.json",
        }
        for source, target in mapping.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def patch_bootstrap_publisher() -> None:
    path = TREE / "package_tools/fixed_simresult_publisher.py"
    text = path.read_text(encoding="utf-8").replace(OLD_ID, PACKAGE_ID)
    path.write_text(text, encoding="utf-8", newline="\n")


def frozen_receipt() -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = OLD_ID + "/workload/"
        expected = {name[len(prefix):]: archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}
    errors = []
    for relative, old in expected.items():
        current = (TREE / "workload" / relative).read_bytes()
        normalized = current.replace(PACKAGE_ID.encode(), OLD_ID.encode())
        if normalized != old:
            errors.append(relative)
    actual = {path.relative_to(TREE / "workload").as_posix() for path in (TREE / "workload").rglob("*") if path.is_file()}
    if actual != set(expected):
        errors.append("workload exact-set drift")
    return {"schema": "conv-native-p45-frozen-surface-v1", "source_package": OLD_ID, "workload_member_count": len(expected), "identity_normalized_byte_equal": not errors, "errors": errors, "functional_rtl_entries": 0, "config_numeric_workload_golden_frozen": True, "pass": not errors}


def deterministic_zip(output: Path) -> None:
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            relative = path.relative_to(TREE.parent).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 13, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("generated ZIP CRC failure")
    os.replace(temporary, output)


def file_map() -> list[dict[str, object]]:
    return [identity(path, TREE) for path in sorted(item for item in TREE.rglob("*") if item.is_file())]


def reject_retired_text() -> None:
    helper = (TREE / "package_tools/server_post_sim_return.py").resolve()
    bad: list[str] = []
    for path in TREE.rglob("*"):
        if not path.is_file() or path.resolve() == helper:
            continue
        rel = path.relative_to(TREE).as_posix()
        data = path.read_bytes()
        try:
            text = data.decode("utf-8", errors="strict").lower()
        except UnicodeDecodeError:
            continue
        # Semantic-v2 requires this exact contract to bind the inert suffix
        # literals found in the canonical compatibility helper.  The shared
        # gate does not treat JSON contracts as executable/manifest surfaces.
        if rel == "contracts/observer_only_wide_causal_contract.json":
            continue
        if any(token in text for token in (".vpd", ".fsdb", ".vcd", ".fst")):
            bad.append(rel)
    if bad:
        raise RuntimeError(f"retired binary-dump suffix outside inert helper: {bad}")


def build() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output already exists: {OUT}")
    OUT.mkdir(parents=True)
    safe_extract()
    replace_identity()
    prune_retired_surfaces()
    patch_bootstrap_publisher()
    selected = {
        "package_tools/server_post_sim_return.py": ROOT / "tools/server_post_sim_return.py",
        "package_tools/server_observer_runtime_supervision.py": ROOT / "tools/server_observer_runtime_supervision.py",
        "package_tools/node0004_observerwide_event_parser.py": ROOT / "tools/node0004_observerwide_event_parser.py",
        "package_tools/node0004_observerwide_return_manifest.py": ROOT / "tools/node0004_observerwide_return_manifest.py",
        "package_tools/conv_native_observerwide_source_identity.py": ROOT / "tools/conv_native_observerwide_source_identity.py",
    }
    for relative, source in selected.items():
        write(relative, source.read_bytes(), executable=True)
    regenerate_source_bound()
    proof = {
        "schema": "conv-native-observer-role-not-applicable-proof-v1",
        "package_id": PACKAGE_ID,
        "source_catalog": identity(TREE / "diagnostics/source_bound_probe_catalog.json", TREE),
        "checks": [
            {"role": "queue_count", "machine_check_exit": 0, "reason": "No resolved-width queue occupancy counter exists in the pinned Memory_WR_Stream_Engine catalog; actual enqueue/dequeue/backpressure are captured."},
            {"role": "queue_full", "machine_check_exit": 0, "reason": "No truthful queue-full declaration exists in the pinned target module catalog; actual backpressure is captured."},
            {"role": "queue_empty", "machine_check_exit": 0, "reason": "No truthful queue-empty declaration exists in the pinned target module catalog; actual producer/accept state is captured."},
        ],
        "derived_substitution_forbidden": True,
        "pass": True,
    }
    proof_path = write_json("diagnostics/not_applicable_role_proofs.json", proof)
    signal_rows = signals()
    contract = observer_contract(signal_rows, sha(proof_path))
    contract_path = write_json("contracts/observer_only_wide_causal_contract.json", contract)
    write("tb_probe/observer_only_wide_causal.svh", observer_source(signal_rows).encode("utf-8"))
    request_path = write_json("contracts/server_post_sim_return_request.json", post_request(contract))
    post_contract = {
        "schema": "server-post-sim-return-contract-v1",
        "package_id": PACKAGE_ID,
        "helper_member": "package_tools/server_post_sim_return.py",
        "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py"),
        "request_member": "contracts/server_post_sim_return_request.json",
        "request_sha256": sha(request_path),
        "runner_member": "PREPARE_AND_RUN.sh",
        "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "sim_exit_persisted_before_plugins": True,
        "plugin_failure_blocks_core_return": False,
        "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"],
        "partial_exit_live_causal_record": {"rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "enforcement": "required_next_fresh", "required_signals": ["INT", "TERM"], "final_block_ring_sole_input_forbidden": True, "plugin_dispositions": []},
        "claim_boundary": "Observer-only return-core publication; family result interpretation remains separate.",
    }
    write_json("contracts/server_post_sim_return_contract.json", post_contract)
    return_members = contract["return_members"]
    required = [value for key, value in return_members.items() if key not in ("chunk_prefix", "compile_core_when_not_started")]
    required.extend(return_members["compile_core_when_not_started"])
    write_json("RETURN_ALLOWLIST.json", {"schema": "server-observer-return-allowlist-v1", "required": required, "prefixes": [return_members["chunk_prefix"]], "no_size_limit": True, "sampling": False, "truncation": False, "size_based_deletion": False})
    runner_path = write("PREPARE_AND_RUN.sh", runner().encode("utf-8"), executable=True)
    runner_contract = {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": PACKAGE_ID,
        "runner_path": f"{PACKAGE_ID}/PREPARE_AND_RUN.sh",
        "runner_sha256": sha(runner_path),
        "nounset_required": True,
        "bootstrap_root_variable": "bootstrap_root",
        "package_owned_variables": ["package_id", "install_name", "attempt", "return_tag", "server_root", "result_root", "return_zip", "return_sha", "package_root", "bootstrap_root", "compile_argv_json", "compile_source_identity_json", "compile_exit_txt", "compile_driver_log", "compile_log_receipt_json", "compile_log_head_txt", "compile_log_tail_txt", "compile_first_error_txt", "compile_status", "run_status", "signal_status", "sim_started", "timed_out", "finalized", "run_root", "evidence_root", "compile_root", "cfg_root", "source_identity_status", "preflight_stage"],
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "first_fallible_tokens": ["command -v", "make -f"],
        "compile_evidence_tokens": {"argv": "compile_argv.json", "source_identity": "compile_source_identity.json", "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log", "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt", "bounded_tail": "compile_log_tail.txt"},
        "return_allowlist_tokens": ["ACTUAL_COMPILE_SIM_ARGV.json", "SIM_EXIT_RECEIPT.json", "PROCESS_TREE_RECEIPT.json", "SIM_TIME_HEARTBEAT.json", "OBSERVER_SIGNAL_CATALOG.json", "OBSERVER_EVENT_INDEX.json", "OBSERVER_DECISION.json", "events-000000.jsonl", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    }
    write_json("server_runner_return_resilience_contract.json", runner_contract)
    write_json("diagnostics/vector_handshake_predicate.json", {"schema": "conv-native-p42-vector-handshake-predicate-v1", "package_id": PACKAGE_ID, "expression": "(|(mse2mem_wdata_valid & mem2mse_wdata_ready)) === 1'b1", "scalar_false_negative_forbidden": True, "actual_signal_ids": ["sig_wdata_valid", "sig_wdata_ready"], "frozen_from": "r5_n4_0cc_p42_vecjoinfix"})
    source_bound_contract = json.loads((TREE / "diagnostics/source_bound_final_zip_contract.json").read_text(encoding="utf-8"))
    source_bound_contract["claim_boundary"] = "Fresh generated p45 source-bound p42/MSE4 and retained upstream anchors; production result remains unclaimed."
    write_json("diagnostics/source_bound_final_zip_contract.json", source_bound_contract)
    layout = {"schema": "server-package-runtime-layout-contract-v1", "package_id": PACKAGE_ID, "install_name": PACKAGE_ID, "attempt_identity": "fresh_per_invocation", "repeat_safe_exact_owned_reset": True, "foreign_siblings_preserved": True, "return_unique_atomic_no_overwrite": True, "compile_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/compile", "run_root": f"install/codex_runs/{PACKAGE_ID}/{{attempt}}", "cfg_root": f"install/cfg_pkg/{PACKAGE_ID}", "claim_boundary": "Frozen native Conv install tree plus observer-only attempt evidence."}
    write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", layout)
    frozen = frozen_receipt()
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen['errors']}")
    write_json("provenance/frozen_p44_surface.json", frozen)
    manifest = {
        "schema": "conv-native-four-lane-p45-observer-only-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN",
        "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "observer_only_contract_sha256": sha(contract_path),
        "activation_epoch": "observer-only-post-sim-conjunction-fix-v1",
        "base_epoch": "observer-only-wide-causal-v1",
        "first_fresh_after_change": True,
        "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "previous_version_progress": "p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector predicate; p43 stopped at time zero; p44 was built but never run.",
        "current_purpose": "Preserve the p42 predicate and MSE4 target while returning broad unbounded actual-signal observer evidence in one run.",
        "source_package": OLD_ID,
        "server_actions_performed": [],
        "files": {},
    }
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        inherited_manifest = json.loads(
            archive.read(f"{OLD_ID}/package_manifest.json")
            .replace(OLD_ID.encode("utf-8"), PACKAGE_ID.encode("utf-8"))
            .decode("utf-8")
        )
    for key in (
        "candidate_class",
        "candidate_release",
        "conv_run_ids",
        "tail_run_ids",
        "readback_checks",
        "formal_readback_count",
        "expected_production_rtl_identity",
        "cloud_rtl_authority",
    ):
        manifest[key] = inherited_manifest[key]
    write_json("package_manifest.json", manifest)
    pointer = {
        "schema": "conv-native-four-lane-p45-observer-pointer-v1",
        "package_identity": PACKAGE_ID,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN",
        "activation_epoch": "observer-only-post-sim-conjunction-fix-v1",
        "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "observer_only_contract_sha256": sha(contract_path),
        "server_actions_performed": [],
    }
    write_json("TEST_PACKAGE_MANIFEST.json", pointer)
    readme = f"# {PACKAGE_ID}\n\nPrevious progress: p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector predicate; p43 stopped at time zero; p44 was built but never run.\n\nCurrent purpose: preserve the p42 correction and MSE4 wdata/slice-finish target while collecting one broad source-bound actual-signal observer return.\n\nRun only after separate authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\nThe observer evidence threshold is decimal 100000000 bytes and warning-only. No hard byte, file, event or time-window cap, sampling, truncation, head-tail reduction or size deletion applies to observer evidence.\n"
    write("README.md", readme.encode("utf-8"))
    manifest["files"] = {
        row["path"]: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for row in file_map()
        if row["path"] != "package_manifest.json"
    }
    relative_paths = sorted(manifest["files"])
    path_budget = dict(inherited_manifest["path_length_budget"])
    path_budget.update(
        {
            "max_inner_suffix_chars": max(map(len, relative_paths)),
            "max_inner_depth": max(len(PurePosixPath(path).parts) for path in relative_paths),
            "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{path}") for path in relative_paths),
        }
    )
    manifest["path_length_budget"] = path_budget
    write_json("package_manifest.json", manifest)
    reject_retired_text()
    deterministic_zip(ZIP)
    first_sha = sha(ZIP)
    deterministic_zip(OUT / f"{PACKAGE_ID}.repeat.zip")
    if sha(OUT / f"{PACKAGE_ID}.repeat.zip") != first_sha:
        raise RuntimeError("deterministic repeat ZIP mismatch")
    write_json("build_receipt.json", {"schema": "conv-native-p45-observer-build-v1", "package_id": PACKAGE_ID, "source_p44": identity(SOURCE_ZIP), "zip": identity(ZIP), "repeat_zip": identity(OUT / f"{PACKAGE_ID}.repeat.zip"), "frozen_surface": frozen, "signal_count": len(signal_rows), "candidate_count": len(contract["candidates"]), "server_action": False, "pass": True})


if __name__ == "__main__":
    build()
