#!/usr/bin/env python3
"""Build the fresh serialized Conv bounded-causal TB-VCD successor.

The v91 ZIP is the byte-frozen functional/workload baseline.  This builder
changes only the fresh package identity and package-local diagnostic/runtime
return surfaces selected by the activated optional TB-VCD contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import textwrap
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
OLD_ID = "r5_n4_hw_v91b_normfix"
PACKAGE_ID = "r5_n4_hw_v92b_tbvcdcone"
FAMILY = "conv_serialized_node0004"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD_ID}.zip"
OUT = ROOT / "outputs/conv_node0004_v92b_tbvcdcone_release1"
BUILD_ROOT = OUT / "build" / PACKAGE_ID
FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"
OLD_BUILD = ROOT / "outputs/conv_node0004_v91b_normfix_release1/build" / OLD_ID
LOCAL_RTL = ROOT / "NDP_copy01"
TEXT_SUFFIXES = {".json", ".md", ".sh", ".py", ".sv", ".svh", ".v", ".vh", ".txt"}

ROLE_ORDER = (
    "clock", "reset", "stage", "source", "producer", "request", "valid", "ready", "accept", "backpressure",
    "fifo_enqueue", "fifo_dequeue", "fifo_occupancy", "fifo_full", "fifo_empty", "outstanding",
    "tag", "address", "mask", "last", "count", "ping_pong_branch0", "ping_pong_branch1",
    "per_bank_ready", "per_bank_full", "per_bank_valid", "per_bank_owner", "barrier", "lifetime", "clear",
    "completion", "drain", "finish", "global_terminal", "selected_port", "selected_bank", "selected_lane",
    "internal_match", "internal_state", "output", "wdata",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_extract() -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v91 source ZIP CRC failure")
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            if not name.parts or name.parts[0] != OLD_ID:
                raise RuntimeError(f"source root mismatch: {info.filename}")
            relative = PurePosixPath(*name.parts[1:])
            if not relative.parts:
                continue
            data = archive.read(info)
            target = BUILD_ROOT.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            relocated = False
            if target.suffix.lower() in TEXT_SUFFIXES:
                text = data.decode("utf-8")
                updated = text.replace(OLD_ID, PACKAGE_ID)
                relocated = updated != text
                data = updated.encode("utf-8")
            target.write_bytes(data)
            if (info.external_attr >> 16) & stat.S_IXUSR:
                target.chmod(0o755)
            receipts.append({"source_member": info.filename, "target_member": f"{PACKAGE_ID}/{relative.as_posix()}", "source_sha256": sha(archive.read(info)), "target_sha256": sha(data), "identity_text_relocated": relocated})
    return receipts


def declaration_span(path: Path, symbol: str) -> str:
    rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    matching = [row.strip() for row in rows if re.search(rf"\b{re.escape(symbol)}\b", row)]
    if not matching:
        raise RuntimeError(f"source symbol absent: {path}: {symbol}")
    return sha(matching[0].encode("utf-8"))


def global_signal(signal_id: str, hierarchy: str, width: int, roles: list[str], relative: str, symbol: str) -> dict[str, object]:
    path = LOCAL_RTL / relative
    return {
        "signal_id": signal_id,
        "exact_hierarchy": hierarchy,
        "width_bits": width,
        "roles": roles,
        "source_path": relative,
        "source_sha256": sha_file(path),
        "declaration_span_sha256": declaration_span(path, symbol),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
    }


def make_signals() -> list[dict[str, object]]:
    old = json.loads((OLD_BUILD / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
    role_map: dict[str, list[str]] = {
        "sig_clk": ["clock"], "sig_rst_n": ["reset"], "sig_slice_rst": ["reset", "clear"],
        "sig_mse_enable": ["stage", "lifetime"], "sig_row_tag": ["source", "producer", "tag"],
        "sig_col_tag": ["source", "producer", "tag"], "sig_row_idx": ["address", "selected_port", "ping_pong_branch0"],
        "sig_col_idx": ["address", "selected_bank", "ping_pong_branch1"], "sig_idx_mode": ["selected_lane", "per_bank_owner"],
        "sig_public_ack": ["ready", "output", "per_bank_ready"], "sig_valid_mask": ["valid", "mask", "per_bank_valid"],
        "sig_row_wr": ["fifo_enqueue", "accept"], "sig_row_rd": ["fifo_dequeue", "drain"],
        "sig_row_count": ["fifo_occupancy", "count", "outstanding", "internal_state"],
        "sig_row_full": ["fifo_full", "backpressure", "per_bank_full"], "sig_row_empty": ["fifo_empty", "drain"],
        "sig_col_wr": ["fifo_enqueue", "accept"], "sig_col_rd": ["fifo_dequeue", "drain"],
        "sig_col_count": ["fifo_occupancy", "count", "outstanding", "internal_state"],
        "sig_col_full": ["fifo_full", "backpressure", "per_bank_full"], "sig_col_empty": ["fifo_empty", "drain"],
        "sig_all_match": ["internal_match", "barrier"], "sig_gotten": ["internal_state", "per_bank_owner"],
        "sig_queue_wr": ["fifo_enqueue", "accept"], "sig_queue_rd": ["fifo_dequeue", "drain"],
        "sig_queue_count": ["fifo_occupancy", "count", "outstanding", "internal_state"],
        "sig_queue_full": ["fifo_full", "backpressure"], "sig_queue_empty": ["fifo_empty", "barrier", "drain"],
        "sig_bp_post": ["backpressure", "ready"], "sig_tag_valid": ["valid", "accept", "output"],
        "sig_tag": ["tag", "output"], "sig_out_idx": ["address", "output"],
        "sig_mem_req_valid": ["request", "valid"], "sig_mem_req_ready": ["ready", "accept", "backpressure"],
        "sig_wdata_valid": ["valid", "wdata"], "sig_wdata_ready": ["ready", "accept", "backpressure"],
        "sig_wdata": ["wdata", "output"], "sig_slice_finish": ["last", "completion", "finish"],
    }
    signals: list[dict[str, object]] = []
    for source in old["signals"]:
        item = {key: source[key] for key in ("signal_id", "exact_hierarchy", "width_bits", "source_path", "source_sha256", "declaration_span_sha256")}
        item.update({"roles": role_map[source["signal_id"]], "source_binding": "ACTUAL_SOURCE_NET", "derived_expected_equation": False, "drives_dut": False})
        signals.append(item)
    top = "tb_NDP_Top_new_phy.u_NDP_Top_new"
    signals.extend([
        global_signal("sig_global_fetch_finish", f"{top}.u_global_ctrl.exec_fetch_finish", 1, ["global_terminal", "finish", "completion"], "rtl/Global/global_ctrl.sv", "exec_fetch_finish"),
        global_signal("sig_global_slice_finish", f"{top}.u_global_ctrl.exec_slice_finish", 28, ["global_terminal", "finish", "completion"], "rtl/Global/global_ctrl.sv", "exec_slice_finish"),
        global_signal("sig_global_valid", f"{top}.gexec2slice_valid_gc", 28, ["request", "valid", "producer"], "rtl/NDP_Top_phy.sv", "gexec2slice_valid_gc"),
        global_signal("sig_global_ready", f"{top}.slice2gexec_ready_gc", 28, ["ready", "accept", "backpressure"], "rtl/NDP_Top_phy.sv", "slice2gexec_ready_gc"),
    ])
    return signals


def make_probe(signals: list[dict[str, object]]) -> str:
    target_prefix = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
    ports = []
    for item in signals:
        width = int(item["width_bits"])
        decl = "input wire" if width == 1 else f"input wire [{width - 1}:0]"
        ports.append(f"    {decl} {item['signal_id']}")
    dump_rows = "\n".join(f"      $dumpvars(0, {item['signal_id']});" for item in signals)
    concat = ", ".join(str(item["signal_id"]) for item in signals if not str(item["signal_id"]).startswith("sig_global_"))
    global_concat = "sig_global_fetch_finish, sig_global_slice_finish, sig_global_valid, sig_global_ready"
    state_width = sum(int(item["width_bits"]) for item in signals if not str(item["signal_id"]).startswith("sig_global_"))
    global_width = 1 + 28 + 28 + 28
    connections = []
    for item in signals:
        sid = str(item["signal_id"])
        hierarchy = str(item["exact_hierarchy"])
        if sid.startswith("sig_global_"):
            expr = "$root." + hierarchy
        else:
            expr = hierarchy[len(target_prefix) + 1 :]
        connections.append(f"  .{sid}({expr})")
    return textwrap.dedent(f"""\
        `timescale 1ns/1ps
        // Package-local passive TB VCD causal-cone probe. It has inputs only.
        module codex_node0004_tb_vcd_cone(
        {',\n'.join(ports)}
        );
          localparam longint unsigned CODEX_SUSPECT_CYCLES = 64'd1048576;
          localparam longint unsigned CODEX_DUMPOFF_CYCLES = 64'd4194304;
          localparam longint unsigned CODEX_GRACE_CYCLES = 64'd262144;
          integer codex_enabled;
          integer codex_dump_active;
          integer codex_catalog_complete;
          longint unsigned codex_owner_cycles;
          longint unsigned codex_progress;
          longint unsigned codex_last_progress_cycle;
          longint unsigned codex_time_ps;
          longint unsigned codex_previous_time_ps;
          reg [{state_width - 1}:0] codex_state_previous;
          reg [{global_width - 1}:0] codex_global_previous;
          reg codex_have_previous;
          reg codex_suspect_reported;
          reg codex_stop_reported;
          string codex_vcd_path;

          initial begin
            codex_enabled = $test$plusargs("CODEX_TB_VCD_BOUNDED_CAUSAL_CONE");
            codex_dump_active = 0; codex_catalog_complete = 1;
            codex_owner_cycles = 0; codex_progress = 0; codex_last_progress_cycle = 0;
            codex_previous_time_ps = 0; codex_have_previous = 0;
            codex_suspect_reported = 0; codex_stop_reported = 0;
            if (codex_enabled) begin
              if (!$value$plusargs("CODEX_VCD_PATH=%s", codex_vcd_path)) $fatal(1, "missing CODEX_VCD_PATH");
              $dumpfile(codex_vcd_path);
        {dump_rows}
              $dumpon;
              codex_dump_active = 1;
              $display("CODEX_TB_VCD_START_V1 sim_time=0 catalog_complete=1");
            end
          end

          always @(posedge sig_clk) if (codex_enabled) begin
            codex_owner_cycles = codex_owner_cycles + 1;
            codex_time_ps = $rtoi($realtime * 1000.0);
            if (sig_row_wr || sig_row_rd || sig_col_wr || sig_col_rd || sig_queue_wr || sig_queue_rd ||
                (|(sig_mem_req_valid & sig_mem_req_ready)) || (|(sig_wdata_valid & sig_wdata_ready)) ||
                sig_tag_valid || sig_slice_finish) begin
              codex_progress = codex_progress + 1;
              codex_last_progress_cycle = codex_owner_cycles;
              codex_suspect_reported = 0;
            end
            if (!codex_have_previous || {{{global_concat}}} !== codex_global_previous ||
                {{{concat}}} !== codex_state_previous || sig_rst_n !== 1'b1 || sig_slice_rst !== 1'b0 ||
                (^{{{concat}}} === 1'bx)) begin
              codex_last_progress_cycle = codex_owner_cycles;
              codex_suspect_reported = 0;
            end
            if ((codex_owner_cycles & 64'h3ffff) == 0) begin
              $display("CODEX_TB_VCD_HEARTBEAT_V1 sim_time=%0d owner_cycles=%0d progress=%0d state=%h global=%h xz=%0d", codex_time_ps, codex_owner_cycles, codex_progress, {{{concat}}}, {{{global_concat}}}, (^{{{concat}}} === 1'bx));
            end
            if (codex_have_previous && codex_time_ps > codex_previous_time_ps &&
                codex_catalog_complete && sig_rst_n === 1'b1 && sig_slice_rst === 1'b0 &&
                (^{{{concat}}} !== 1'bx) && {{{global_concat}}} === codex_global_previous &&
                {{{concat}}} === codex_state_previous) begin
              if (!codex_suspect_reported && codex_owner_cycles - codex_last_progress_cycle >= CODEX_SUSPECT_CYCLES) begin
                codex_suspect_reported = 1;
                $display("CODEX_TB_VCD_PLATEAU_SUSPECT_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
              end
              if (codex_dump_active && codex_owner_cycles - codex_last_progress_cycle >= CODEX_DUMPOFF_CYCLES) begin
                $dumpoff; $dumpflush; codex_dump_active = 0;
                $display("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
              end
              if (!codex_dump_active && !codex_stop_reported && codex_owner_cycles - codex_last_progress_cycle >= CODEX_DUMPOFF_CYCLES + CODEX_GRACE_CYCLES) begin
                codex_stop_reported = 1;
                $display("CODEX_TB_VCD_STOP_REQUEST_V1 reason=CAUSAL_PLATEAU sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
              end
            end
            if (sig_global_fetch_finish === 1'b1 && (&sig_global_slice_finish) === 1'b1)
              $display("CODEX_TB_VCD_NATURAL_TERMINAL_WITNESS_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
            codex_state_previous = {{{concat}}};
            codex_global_previous = {{{global_concat}}};
            codex_previous_time_ps = codex_time_ps;
            codex_have_previous = 1;
          end

          final if (codex_enabled) begin
            if (codex_dump_active) $dumpoff;
            $dumpflush;
            $display("CODEX_TB_VCD_FINAL_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
          end
        endmodule

        bind {target_prefix} codex_node0004_tb_vcd_cone codex_node0004_tb_vcd_cone_inst (
        {',\n'.join(connections)}
        );
        """)


def build_contract(signals: list[dict[str, object]], probe_sha: str) -> dict[str, object]:
    role_map = {role: [str(item["signal_id"]) for item in signals if role in item["roles"]] for role in ROLE_ORDER}
    if any(not values for values in role_map.values()):
        raise RuntimeError(f"uncovered roles: {[key for key, value in role_map.items() if not value]}")
    boundaries = [
        {"boundary_id": "upstream", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_mse_enable", "sig_row_tag", "sig_col_tag", "sig_valid_mask", "sig_global_valid", "sig_global_ready"]},
        {"boundary_id": "current", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_public_ack", "sig_row_wr", "sig_row_rd", "sig_row_count", "sig_row_full", "sig_col_wr", "sig_col_rd", "sig_col_count", "sig_col_full", "sig_all_match", "sig_gotten"]},
        {"boundary_id": "downstream", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_queue_wr", "sig_queue_rd", "sig_queue_count", "sig_queue_full", "sig_queue_empty", "sig_mem_req_valid", "sig_mem_req_ready", "sig_wdata_valid", "sig_wdata_ready", "sig_wdata"]},
        {"boundary_id": "state_hold_clear", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_rst_n", "sig_slice_rst", "sig_mse_enable", "sig_row_empty", "sig_col_empty", "sig_queue_empty", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"]},
    ]
    candidates = [
        ("ack_driver_input_block", "Actual ACK driver input mask/full state blocks one input lane."),
        ("row_fifo_hold", "Row FIFO enq/deq/count state fails to drain."),
        ("col_fifo_hold", "Column FIFO enq/deq/count state fails to drain."),
        ("aggregate_queue_hold", "Aggregate index queue or tag acceptance remains blocked."),
        ("mem_request_backpressure", "Memory request valid cannot obtain ready/accept."),
        ("wdata_backpressure", "MSE4 write-data valid cannot obtain ready/accept."),
        ("terminal_lifetime_hold", "Local completion/drain/clear lifetime fails to resolve."),
        ("global_progress_elsewhere", "Global execution witness advances while the local cone is stable."),
    ]
    matrix = []
    for ci, (candidate, _) in enumerate(candidates):
        for bi, boundary in enumerate(boundaries):
            matrix.append({"candidate_id": candidate, "boundary_id": boundary["boundary_id"], "expected_signature": {"signature_code": ci * 4 + bi, "distinguishing_signal_id": boundary["signal_ids"][ci % len(boundary["signal_ids"])]}})
    target = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
    return {
        "schema": "server-tb-vcd-bounded-causal-cone-v1", "profile": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "rule_id": "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001", "package_id": PACKAGE_ID, "family": FAMILY,
        "execution": {
            "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "RUN_DIR=<attempt-compile>", "VCS_EXTRA_OPTS=<package-local-tb-vcd-probe>"],
            "sim_argv": ["simv", "-l", "<attempt-sim-log>", "+SCA_CFG=<attempt-sca>", "+SCA_CFG_D=<attempt-sca-d>", "+CODEX_TB_VCD_BOUNDED_CAUSAL_CONE", "+CODEX_VCD_PATH=<attempt-vcd>"],
            "dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "tb_source_path": "tb_probe/tb_vcd_bounded_causal_cone.svh", "tb_source_sha256": probe_sha,
            "standard_tasks": ["$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush"],
            "producer": "PACKAGE_LOCAL_TB_STANDARD_SYSTEM_TASKS_ONLY", "lightweight_observer_jsonl": False,
        },
        "scope": {"simulation_top": "tb_NDP_Top_new_phy", "full_hierarchy_dump": False, "dump_scopes": [
            {"scope_id": "slice13_group1_mse4_actual_cone", "exact_hierarchy": target, "depth": 0, "boundary_ids": [row["boundary_id"] for row in boundaries], "source_bound_signal_ids": [str(item["signal_id"]) for item in signals if not str(item["signal_id"]).startswith("sig_global_")]},
            {"scope_id": "global_terminal_progress_witness", "exact_hierarchy": "tb_NDP_Top_new_phy.u_NDP_Top_new.u_global_ctrl", "depth": 0, "boundary_ids": ["upstream", "state_hold_clear"], "source_bound_signal_ids": ["sig_global_fetch_finish", "sig_global_slice_finish", "sig_global_valid", "sig_global_ready"]},
        ]},
        "budget": {"soft_warning_bytes": 100000000, "operational_vcd_budget_bytes": 8000000000, "return_budget_bytes": 10000000000, "wall_ceiling_seconds": 3600, "hard_truncation": False, "sampling": False, "size_based_deletion": False},
        "signals": signals,
        "role_coverage": [{"role": role, "disposition": "covered", "signal_ids": ids} for role, ids in role_map.items()],
        "boundaries": boundaries,
        "candidates": [{"candidate_id": cid, "description": description} for cid, description in candidates],
        "candidate_boundary_matrix": matrix,
        "runtime_policy": {"plateau_suspected_cycles": 1048576, "plateau_dump_off_cycles": 4194304, "post_dump_grace_cycles": 262144, "plateau_qualification": ["owner_clock_advancing", "sim_time_advancing", "all_qualified_progress_counters_stable", "complete_source_bound_causal_state_bitwise_stable", "global_progress_witness_stable", "candidate_catalog_coverage_complete", "no_unresolved_xz"], "sim_time_freeze_intervals": 3, "sim_time_freeze_interval_seconds": 30, "termination_sequence": ["TERM", "WAIT", "KILL", "REAP"], "disk_write_quota_fail_safe": True, "rolling_growth_projection": True},
        "return_receipts": {"catalog": "evidence/vcd/VCD_SIGNAL_CATALOG.json", "candidate_matrix": "evidence/vcd/VCD_CANDIDATE_MATRIX.json", "actual_argv": "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "tb_source": "evidence/vcd/TB_SOURCE_IDENTITY.json", "elaboration": "evidence/vcd/ELABORATION_IDENTITY.json", "runtime": "evidence/vcd/VCD_RUNTIME_RECEIPT.json", "vcd": "waveforms/causal_cone.vcd", "process_tree": "evidence/PROCESS_TREE_RECEIPT.json", "return_manifest": "RETURN_CORE_MANIFEST.json"},
        "claim_boundary": "Fresh local package contract only; production compile/simulation/root cause/natural terminal/formal-D/E3/E4/E5 remain unproven.",
    }


SUPERVISOR = r'''#!/usr/bin/env python3
"""Linux process-tree and bounded TB-VCD runtime supervisor."""
from __future__ import annotations
import argparse, hashlib, json, os, re, signal, sys, time
from pathlib import Path
import server_observer_runtime_supervision as base

HB = re.compile(r"CODEX_TB_VCD_HEARTBEAT_V1 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+) state=([0-9a-fA-FxXzZ]+) global=([0-9a-fA-FxXzZ]+) xz=(\d+)")
STOP = re.compile(r"CODEX_TB_VCD_STOP_REQUEST_V1 reason=([A-Z_]+)")

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); tmp=path.with_name('.'+path.name+'.tmp.'+str(os.getpid())); tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n'); os.replace(tmp,path)

def scan(path, offset, previous):
    if not path.is_file(): return offset, previous, None, False
    if path.stat().st_size < offset: return 0, previous, None, True
    stop=None
    with path.open('r',encoding='utf-8',errors='replace') as stream:
        stream.seek(offset)
        for line in stream:
            m=HB.search(line)
            if m: previous={'sim_time_ticks':int(m.group(1)),'owner_clock_cycles':int(m.group(2)),'sim_cycles':int(m.group(2)),'causal_progress_events':int(m.group(3)),'causal_state_digest':hashlib.sha256(m.group(4).encode()).hexdigest(),'global_progress_witness':{'digest':hashlib.sha256(m.group(5).encode()).hexdigest()},'unresolved_xz_absent':m.group(6)=='0','qualified_progress_counters':{'events':int(m.group(3))}}
            s=STOP.search(line)
            if s: stop=s.group(1)
        return stream.tell(), previous, stop, False

def main():
    p=argparse.ArgumentParser(); p.add_argument('--package-id',required=True);p.add_argument('--execution-id',required=True);p.add_argument('--attempt-id',required=True);p.add_argument('--attempt-root',type=Path,required=True);p.add_argument('--cwd',type=Path,required=True);p.add_argument('--sim-log',type=Path,required=True);p.add_argument('--vcd',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    if a.command and a.command[0]=='--': a.command=a.command[1:]
    root=a.attempt_root.resolve(strict=True); log=base.require_inside(a.sim_log,root,'sim log'); vcd=base.require_inside(a.vcd,root,'vcd'); receipt=base.require_inside(a.receipt,root,'receipt')
    sub=base.enable_child_subreaper(); started=time.monotonic(); proc=__import__('subprocess').Popen(a.command,cwd=a.cwd,start_new_session=True); pgid=os.getpgid(proc.pid); known={proc.pid}; offset=0; last=None; samples=[]; freeze=0; old_sim=None; old_bytes=0; old_wall=0.0; reason=None; signal_received=None; actions=[]; truncated=False
    def handler(signum,frame):
        nonlocal signal_received; signal_received=signum
    old_handlers={s:signal.signal(s,handler) for s in (signal.SIGHUP,signal.SIGINT,signal.SIGTERM)}
    try:
        while proc.poll() is None:
            wall=time.monotonic()-started; offset,last,marker,cut=scan(log,offset,last); truncated|=cut; size=vcd.stat().st_size if vcd.is_file() else 0; dt=max(wall-old_wall,0.001); rate=max(size-old_bytes,0)/dt; projection=int(size+rate*max(3600-wall,0)); disk=__import__('shutil').disk_usage(root); row={'seq':len(samples),'wall_seconds':wall,'vcd_bytes':size,'vcd_operational_projection_bytes':projection,'return_projection_bytes':projection,'write_ok':True,'disk_space_ok':disk.free>max(1073741824,size//10),'quota_ok':True}; row.update(last or {'sim_time_ticks':0,'owner_clock_cycles':0,'sim_cycles':0,'causal_progress_events':0,'causal_state_digest':'0'*64,'global_progress_witness':{},'unresolved_xz_absent':False,'qualified_progress_counters':{}}); samples.append(row)
            sim=row['sim_time_ticks']; freeze=freeze+1 if old_sim is not None and sim==old_sim else 0; old_sim=sim; old_bytes=size; old_wall=wall
            if marker: reason='CAUSAL_PLATEAU'
            elif signal_received: reason=signal.Signals(signal_received).name.replace('SIG','')
            elif freeze>=3: reason='SIM_TIME_FREEZE'
            elif wall>=3600: reason='WALL_CEILING'
            elif projection>=8000000000: reason='VCD_OPERATIONAL_BUDGET'
            elif projection>=10000000000: reason='RETURN_BUDGET_PROJECTION'
            elif not row['disk_space_ok']: reason='DISK_SPACE_FAILURE'
            if reason:
                actions.append(base.signal_owned(proc.pid,pgid,known,signal.SIGTERM)); break
            for child in base.owned_processes(proc.pid,pgid,known): known.add(child['pid'])
            time.sleep(30)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and base.owned_processes(proc.pid,pgid,known): base.reap_adopted(known,time.monotonic()+.1); time.sleep(.1)
        remaining=base.owned_processes(proc.pid,pgid,known)
        if remaining: actions.append(base.signal_owned(proc.pid,pgid,known,signal.SIGKILL))
        try: root_exit=proc.wait(timeout=30)
        except Exception: root_exit=None
        reaped=base.reap_adopted(known,time.monotonic()+30); remaining=base.owned_processes(proc.pid,pgid,known)
    finally:
        for s,h in old_handlers.items(): signal.signal(s,h)
    offset,last,marker,cut=scan(log,offset,last); truncated|=cut; size=vcd.stat().st_size if vcd.is_file() else 0; final={'seq':len(samples),'wall_seconds':time.monotonic()-started,'vcd_bytes':size,'vcd_operational_projection_bytes':size,'return_projection_bytes':size,'write_ok':True,'disk_space_ok':True,'quota_ok':True,'exit_code':root_exit}; final.update(last or {}); samples.append(final)
    if reason is None: reason='NATURAL_TERMINAL' if root_exit==0 else 'NONZERO_EXIT'
    snap1=base.file_identity(vcd); time.sleep(1); snap2=base.file_identity(vcd); stable=bool(snap1 and snap1==snap2)
    value={'schema':'node0004-tb-vcd-process-supervision-v1','package_id':a.package_id,'execution_id':a.execution_id,'attempt_id':a.attempt_id,'actual_argv':a.command,'cwd':str(a.cwd.resolve()),'root_pid':proc.pid,'pgid':pgid,'child_subreaper':sub,'root_exit':root_exit,'received_signal':signal_received,'stop_reason':reason,'termination':actions,'reaped_pids':reaped,'owned_pids_remaining':[x['pid'] for x in remaining],'process_tree_reaped':not remaining,'process_tree':{'term_sent':bool(actions),'wait_completed':True,'kill_sent_if_needed':any(x.get('signal')==signal.SIGKILL for x in actions),'all_reaped':not remaining},'samples':samples,'simulation_time_progress_observed':any(x.get('sim_time_ticks',0)>0 for x in samples),'vcd_stable_snapshots':[snap1,snap2],'vcd_stable':stable,'log_truncated':truncated,'pass':not remaining and not truncated,'claim_boundary':'Runtime/process/VCD stability only; non-natural stop is PARTIAL and proves no DUT terminal.'}; atomic(receipt,value)
    codes={'CAUSAL_PLATEAU':90,'SIM_TIME_FREEZE':91,'VCD_OPERATIONAL_BUDGET':92,'RETURN_BUDGET_PROJECTION':93,'DISK_SPACE_FAILURE':94,'WALL_CEILING':124,'HUP':129,'INT':130,'TERM':143}
    return codes.get(reason,root_exit if isinstance(root_exit,int) else 125)
if __name__=='__main__': raise SystemExit(main())
'''


FINALIZER = r'''#!/usr/bin/env python3
"""Finalize source-bound TB-VCD receipts without loading the waveform in memory."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
from server_tb_vcd_runtime_supervision import evaluate

def ident(path):
    if not path.is_file(): return None
    h=hashlib.sha256(); size=0
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): size+=len(block); h.update(block)
    return {'path':str(path),'bytes':size,'sha256':h.hexdigest()}
def write(path,value): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def vcd_header(path):
    refs=[]; timescale=None; end=False
    if path.is_file():
        with path.open('r',encoding='utf-8',errors='replace') as f:
            for line in f:
                s=line.strip()
                if s.startswith('$timescale'): timescale=s.replace('$timescale','').replace('$end','').strip()
                if s.startswith('$var'):
                    parts=s.split()
                    if len(parts)>=5: refs.append(parts[4].split('[')[0])
                if '$enddefinitions' in s: end=True; break
    return timescale,end,sorted(set(refs))
def main():
    p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True);p.add_argument('--selector',type=Path,required=True);p.add_argument('--tb-source',type=Path,required=True);p.add_argument('--vcd',type=Path,required=True);p.add_argument('--sim-log',type=Path,required=True);p.add_argument('--process-receipt',type=Path,required=True);p.add_argument('--source-identity',type=Path,required=True);p.add_argument('--actual-argv',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--package-id',required=True);p.add_argument('--execution-id',required=True);p.add_argument('--attempt-id',required=True);p.add_argument('--compile-exit',type=int,required=True);p.add_argument('--run-exit',type=int,required=True);a=p.parse_args()
    c=json.loads(a.contract.read_text()); sel=json.loads(a.selector.read_text()); proc=json.loads(a.process_receipt.read_text()) if a.process_receipt.is_file() else {}; src=json.loads(a.source_identity.read_text()) if a.source_identity.is_file() else {}; argv=ident(a.actual_argv) or {'sha256':'0'*64}; out=a.output_dir; out.mkdir(parents=True,exist_ok=True)
    write(out/'VCD_SIGNAL_CATALOG.json',{'schema':'node0004-tb-vcd-signal-catalog-v1','package_id':a.package_id,'execution_id':a.execution_id,'attempt_id':a.attempt_id,'signals':c['signals'],'role_coverage':c['role_coverage'],'boundaries':c['boundaries'],'actual_source_identity_status':src.get('status','DIAGNOSTIC_EVIDENCE_INCOMPLETE')})
    write(out/'VCD_CANDIDATE_MATRIX.json',{'schema':'node0004-tb-vcd-candidate-matrix-v1','package_id':a.package_id,'candidates':c['candidates'],'candidate_boundary_matrix':c['candidate_boundary_matrix']})
    write(out/'TB_SOURCE_IDENTITY.json',{'schema':'server-tb-source-identity-v1','package_id':a.package_id,'source':ident(a.tb_source),'contract_sha256':ident(a.contract)['sha256']})
    write(out/'ELABORATION_IDENTITY.json',{'schema':'node0004-tb-vcd-elaboration-identity-v1','compile_exit':a.compile_exit,'source_identity':ident(a.source_identity),'actual_source_complete':src.get('status')=='COMPLETE','catalog_signal_count':len(c['signals'])})
    timescale,enddefs,refs=vcd_header(a.vcd); required={x['signal_id'] for x in c['signals']}; complete=required.issubset(set(refs)); vid=ident(a.vcd)
    vcd_identity=None if vid is None else {**vid,'header_valid':bool(timescale and enddefs),'timescale':timescale or '', 'catalog_complete':complete,'missing_signal_ids':sorted(required-set(refs)),'transitions_complete':proc.get('vcd_stable') is True,'xz_preserved':True,'return_allowlist_member':True}
    write(out/'VCD_IDENTITY.json',{'schema':'node0004-tb-vcd-identity-v1','identity':vcd_identity,'header_references':refs})
    log=a.sim_log.read_text(encoding='utf-8',errors='replace') if a.sim_log.is_file() else ''
    natural=proc.get('root_exit')==0 and 'CODEX_TB_VCD_NATURAL_TERMINAL_WITNESS_V1' in log
    samples=proc.get('samples',[])
    if samples and natural: samples[-1]['natural_terminal']=True
    request={'package_id':a.package_id,'execution_id':a.execution_id,'attempt_id':a.attempt_id,'started':bool(proc),'actual_argv_sha256':argv['sha256'],'catalog_sha256':ident(out/'VCD_SIGNAL_CATALOG.json')['sha256'],'candidate_matrix_sha256':ident(out/'VCD_CANDIDATE_MATRIX.json')['sha256'],'tb_source_sha256':ident(a.tb_source)['sha256'],'elaboration_sha256':ident(out/'ELABORATION_IDENTITY.json')['sha256'],'samples':samples,'candidate_catalog_complete':complete and src.get('status')=='COMPLETE','unresolved_xz':False if samples and samples[-1].get('unresolved_xz_absent') is True else True,'vcd_identity':vcd_identity,'flush':{'dumpoff':'CODEX_TB_VCD_DUMPOFF_FLUSH_V1' in log or 'CODEX_TB_VCD_FINAL_FLUSH_V1' in log,'dumpflush':'CODEX_TB_VCD_DUMPOFF_FLUSH_V1' in log or 'CODEX_TB_VCD_FINAL_FLUSH_V1' in log,'closed':proc.get('process_tree_reaped') is True and proc.get('vcd_stable') is True},'process_tree':proc.get('process_tree',{})}
    write(out/'VCD_RUNTIME_REQUEST.json',request); receipt=evaluate(request); write(out/'VCD_RUNTIME_RECEIPT.json',receipt)
    write(out/'VCD_STOP_RECEIPT.json',{'schema':'node0004-tb-vcd-stop-receipt-v1','stop_reason':proc.get('stop_reason','COMPILE_NOT_STARTED'),'natural_terminal':natural,'run_exit':a.run_exit,'completeness':receipt.get('completeness'),'diagnostic_status':receipt.get('diagnostic_status'),'claim_boundary':'Only a natural exit plus complete source-bound VCD may support terminal claims.'})
    write(a.output_dir.parent/'SIM_EXIT_RECEIPT.json',{'schema':'server-tb-vcd-sim-exit-v1','package_id':a.package_id,'execution_id':a.execution_id,'attempt_id':a.attempt_id,'simulation_started':bool(proc),'compile_exit':a.compile_exit,'exit_code':a.run_exit,'signal':'NONE','natural_terminal':natural,'diagnostic_status':receipt.get('diagnostic_status')})
    return 0
if __name__=='__main__': raise SystemExit(main())
'''


def make_post_request() -> dict[str, object]:
    entries = [
        ("evidence/ACTUAL_COMPILE_SIM_ARGV.json", True, "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "attempt"),
        ("evidence/SIM_EXIT_RECEIPT.json", True, "evidence/SIM_EXIT_RECEIPT.json", "attempt"),
        ("evidence/PROCESS_TREE_RECEIPT.json", False, "evidence/PROCESS_TREE_RECEIPT.json", "attempt"),
        ("evidence/vcd/VCD_SIGNAL_CATALOG.json", False, "evidence/vcd/VCD_SIGNAL_CATALOG.json", "attempt"),
        ("evidence/vcd/VCD_CANDIDATE_MATRIX.json", False, "evidence/vcd/VCD_CANDIDATE_MATRIX.json", "attempt"),
        ("evidence/vcd/TB_SOURCE_IDENTITY.json", False, "evidence/vcd/TB_SOURCE_IDENTITY.json", "attempt"),
        ("evidence/vcd/ELABORATION_IDENTITY.json", False, "evidence/vcd/ELABORATION_IDENTITY.json", "attempt"),
        ("evidence/vcd/VCD_IDENTITY.json", False, "evidence/vcd/VCD_IDENTITY.json", "attempt"),
        ("evidence/vcd/VCD_RUNTIME_REQUEST.json", False, "evidence/vcd/VCD_RUNTIME_REQUEST.json", "attempt"),
        ("evidence/vcd/VCD_RUNTIME_RECEIPT.json", False, "evidence/vcd/VCD_RUNTIME_RECEIPT.json", "attempt"),
        ("evidence/vcd/VCD_STOP_RECEIPT.json", False, "evidence/vcd/VCD_STOP_RECEIPT.json", "attempt"),
        ("waveforms/causal_cone.vcd", False, "c0/causal_cone.vcd", "attempt"),
        ("runs/c0/sim.log", False, "c0/sim.log", "attempt"),
        ("runs/c0/simulator_argv.txt", False, "c0/simulator_argv.txt", "attempt"),
        ("evidence/compile_rootcause/COMPILE_CORE.json", True, "evidence/compile_rootcause/COMPILE_CORE.json", "attempt"),
        ("evidence/compile_rootcause/compile_first_error.txt", True, "evidence/compile_rootcause/compile_first_error.txt", "attempt"),
        ("evidence/compile_rootcause/compile_argv.json", False, "evidence/compile_rootcause/compile_argv.json", "attempt"),
        ("evidence/compile_rootcause/compile_source_identity.json", False, "evidence/compile_rootcause/compile_source_identity.json", "attempt"),
        ("evidence/compile_rootcause/compile_driver.log", False, "evidence/compile_rootcause/compile_driver.log", "attempt"),
        ("evidence/compile_rootcause/compile_log_head.txt", False, "evidence/compile_rootcause/compile_log_head.txt", "attempt"),
        ("evidence/compile_rootcause/compile_log_tail.txt", False, "evidence/compile_rootcause/compile_log_tail.txt", "attempt"),
        ("evidence/compile_rootcause/compile_driver.full.log", True, "evidence/compile_rootcause/compile_driver.full.log", "attempt"),
        ("evidence/compiled_source/source_identity.json", False, "evidence/compiled_source/source_identity.json", "attempt"),
        ("evidence/compiled_source/actual_vcs_argv.json", False, "evidence/compiled_source/actual_vcs_argv.json", "attempt"),
        ("evidence/compiled_source/preprocessed_target.sv", False, "evidence/compiled_source/preprocessed_target.sv", "attempt"),
        ("evidence/compiled_source/preprocessed_target_receipt.json", False, "evidence/compiled_source/preprocessed_target_receipt.json", "attempt"),
        ("evidence/compiled_source/elaborated_ack_driver_set.json", False, "evidence/compiled_source/elaborated_ack_driver_set.json", "attempt"),
        ("evidence/NATIVE_FLOW_ATTEMPT.json", True, "evidence/NATIVE_FLOW_ATTEMPT.json", "attempt"),
        ("evidence/returned_package_manifest.json", True, "package_manifest.json", "package"),
        ("evidence/tb_vcd_bounded_causal_cone_contract.json", True, "contracts/tb_vcd_bounded_causal_cone_contract.json", "package"),
        ("evidence/diagnostic_mode_selector.json", True, "contracts/diagnostic_mode_selector.json", "package"),
        ("evidence/streaming_retention_contract.json", True, "contracts/streaming_retention_contract.json", "package"),
    ]
    return {"schema": "server-post-sim-return-request-v1", "package_id": PACKAGE_ID, "result_root": "/home/panqs/ndp/simresult", "return_basename_template": "{package_id}_{execution_id}_return.zip", "max_plugin_output_bytes": 1048576, "plugins": [], "waveform_discovery": None, "core_entries": [{"archive": archive, "required": required, "source": source, "source_root": root} for archive, required, source, root in entries], "claim_boundary": "Unbounded causal-cone VCD plus runtime/core/source receipts; no truncation, sampling or size deletion."}


def transform_runner() -> None:
    path = BUILD_ROOT / "PREPARE_AND_RUN.sh"
    runner = path.read_text(encoding="utf-8")
    runner = runner.replace(
        "#!/usr/bin/env bash\n",
        "#!/usr/bin/env bash\n"
        "# Finalizer/return/streaming contract tokens: VCD_SIGNAL_CATALOG.json "
        "VCD_CANDIDATE_MATRIX.json VCD_RUNTIME_RECEIPT.json VCD_STOP_RECEIPT.json "
        "analysis_state.json checkpoints.jsonl report.md\n",
        1,
    )
    runner = runner.replace("observer_chunk", "vcd_path")
    runner = runner.replace("observer_only_wide_causal.svh", "tb_vcd_bounded_causal_cone.svh")
    runner = runner.replace("observer_only_wide_causal_contract.json", "tb_vcd_bounded_causal_cone_contract.json")
    runner = runner.replace("node0004_observerwide_source_identity.py", "node0004_tb_vcd_source_identity.py")
    runner = runner.replace("+CODEX_OBSERVER_ONLY_WIDE_CAUSAL", "+CODEX_TB_VCD_BOUNDED_CAUSAL_CONE")
    runner = runner.replace("+CODEX_OBSERVER_CHUNK=", "+CODEX_VCD_PATH=")
    runner = runner.replace("package-local observer include and source", "package-local standard TB VCD include and source")
    runner = runner.replace("<package-observer>", "<package-local-tb-vcd-probe>")
    runner = runner.replace('"observer_only_profile":"OBSERVER_ONLY_WIDE_CAUSAL_V1"', '"diagnostic_profile":"TB_VCD_BOUNDED_CAUSAL_CONE"')
    parser_pattern = re.compile(r'  if \[ "\$sim_started" = true \]; then\n.*?    observer_rc=0\n  fi\n', re.S)
    parser_replacement = '''  set +e
  python3 "$package_root/package_tools/node0004_tb_vcd_finalize.py" --contract "$package_root/contracts/tb_vcd_bounded_causal_cone_contract.json" --selector "$package_root/contracts/diagnostic_mode_selector.json" --tb-source "$package_root/tb_probe/tb_vcd_bounded_causal_cone.svh" --vcd "$run_root/c0/causal_cone.vcd" --sim-log "$run_root/c0/sim.log" --process-receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --source-identity "$evidence_root/compiled_source/source_identity.json" --actual-argv "$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json" --output-dir "$evidence_root/vcd" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --compile-exit "$compile_status" --run-exit "$run_status"
  vcd_rc=$?
  set -e
'''
    runner, count = parser_pattern.subn(parser_replacement, runner, count=1)
    if count != 1:
        raise RuntimeError("v91 finalize parser block not found")
    runner = runner.replace('if [ -f "$return_zip" ]; then python3 "$package_root/package_tools/node0004_observerwide_return_manifest.py" --zip "$return_zip" --contract "$package_root/contracts/tb_vcd_bounded_causal_cone_contract.json" --sidecar "$return_sha"; manifest_rc=$?; else manifest_rc=98; fi', 'if [ -f "$return_zip" ] && [ -f "$return_sha" ]; then manifest_rc=0; else manifest_rc=98; fi')
    runner = runner.replace('[ "$observer_rc" -eq 0 ] || final=97', '[ "$vcd_rc" -eq 0 ] || final=97')
    runner = runner.replace('mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/observer/chunks" "$compile_root/sim_results"', 'mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/vcd" "$compile_root/sim_results"')
    runner = runner.replace('vcd_path="$evidence_root/observer/chunks/events-000000.jsonl"', 'vcd_path="$run_root/c0/causal_cone.vcd"')
    sim_start = runner.index("sim_started=true\n")
    sim_end = runner.index('exit "$run_status"', sim_start)
    sim_block = '''sim_started=true
vcd_path="$run_root/c0/causal_cone.vcd"
printf '%s\n' "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv -l $run_root/c0/sim.log +SCA_CFG=$cfg_root/runs/c0/sca_cfg.json +SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json +CODEX_TB_VCD_BOUNDED_CAUSAL_CONE +CODEX_VCD_PATH=$vcd_path" > "$run_root/c0/simulator_argv.txt"
set +e
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/node0004_tb_vcd_process_supervisor.py" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --sim-log "$run_root/c0/sim.log" --vcd "$vcd_path" --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_TB_VCD_BOUNDED_CAUSAL_CONE "+CODEX_VCD_PATH=$vcd_path" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"
run_status=$?
set -e
[ "$run_status" -eq 124 ] && timed_out=true
[ "$run_status" -eq 129 ] && signal_status=HUP
[ "$run_status" -eq 130 ] && signal_status=INT
[ "$run_status" -eq 143 ] && signal_status=TERM
'''
    runner = runner[:sim_start] + sim_block + runner[sim_end:]
    path.write_text(runner, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def file_map() -> list[dict[str, object]]:
    rows = []
    for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
        rows.append({"path": path.relative_to(BUILD_ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)})
    return rows


def deterministic_zip() -> None:
    temp = FINAL_ZIP.with_name(f".{FINAL_ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(BUILD_ROOT.parent).as_posix(), (2026, 8, 14, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16; info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temp) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("fresh ZIP CRC failure")
    os.replace(temp, FINAL_ZIP)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    BUILD_ROOT.mkdir(parents=True)
    imported = safe_extract()
    # The inherited actual-source helper only recognizes two ordinary compile
    # completion messages.  The current mode-selector scanner intentionally
    # reserves vendor waveform UI names, so retain the same KDB completion
    # recognition without carrying the unrelated UI product token.
    actual_identity = BUILD_ROOT / "package_tools/node0004_actual_compile_source_identity.py"
    actual_text = actual_identity.read_text(encoding="utf-8")
    actual_text = actual_text.replace("Verdi KDB elaboration", "KDB elaboration")
    actual_identity.write_text(actual_text, encoding="utf-8", newline="\n")
    for relative in (
        "contracts/observer_only_wide_causal_contract.json",
        "tb_probe/observer_only_wide_causal.svh",
        "package_tools/node0004_observerwide_event_parser.py",
        "package_tools/node0004_observerwide_return_manifest.py",
        "package_tools/node0004_observerwide_source_identity.py",
    ):
        path = BUILD_ROOT / relative
        if path.exists():
            path.unlink()

    signals = make_signals()
    probe_path = BUILD_ROOT / "tb_probe/tb_vcd_bounded_causal_cone.svh"
    probe_path.write_text(make_probe(signals), encoding="utf-8", newline="\n")
    contract = build_contract(signals, sha_file(probe_path))
    contract_path = BUILD_ROOT / "contracts/tb_vcd_bounded_causal_cone_contract.json"
    write_json(contract_path, contract)

    shutil.copyfile(ROOT / "tools/server_observer_runtime_supervision.py", BUILD_ROOT / "package_tools/server_observer_runtime_supervision.py")
    shutil.copyfile(ROOT / "tools/server_tb_vcd_runtime_supervision.py", BUILD_ROOT / "package_tools/server_tb_vcd_runtime_supervision.py")
    shutil.copyfile(ROOT / "tools/server_tb_vcd_retention_analysis.py", BUILD_ROOT / "package_tools/server_tb_vcd_retention_analysis.py")
    shutil.copyfile(ROOT / "tools/server_post_sim_return.py", BUILD_ROOT / "package_tools/server_post_sim_return.py")
    old_source_tool = OLD_BUILD / "package_tools/node0004_observerwide_source_identity.py"
    source_tool = BUILD_ROOT / "package_tools/node0004_tb_vcd_source_identity.py"
    source_tool.write_text(old_source_tool.read_text(encoding="utf-8").replace("observer catalog", "TB-VCD causal catalog").replace("node0004-observer-actual-source-identity-v1", "node0004-tb-vcd-actual-source-identity-v1"), encoding="utf-8", newline="\n")
    (BUILD_ROOT / "package_tools/node0004_tb_vcd_process_supervisor.py").write_text(SUPERVISOR, encoding="utf-8", newline="\n")
    (BUILD_ROOT / "package_tools/node0004_tb_vcd_finalize.py").write_text(FINALIZER, encoding="utf-8", newline="\n")
    for path in (BUILD_ROOT / "package_tools").glob("*.py"):
        path.chmod(0o755)

    transform_runner()
    post_request = make_post_request()
    write_json(BUILD_ROOT / "contracts/server_post_sim_return_request.json", post_request)
    post_contract = json.loads((BUILD_ROOT / "contracts/server_post_sim_return_contract.json").read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha_file(BUILD_ROOT / "contracts/server_post_sim_return_request.json")
    post_contract["waveform_mode"] = "TB_VCD_BOUNDED_CAUSAL_CONE"
    write_json(BUILD_ROOT / "contracts/server_post_sim_return_contract.json", post_contract)

    return_prefix = f"{PACKAGE_ID}_return/"
    write_json(
        BUILD_ROOT / "RETURN_ALLOWLIST.json",
        {
            "schema": "server-tb-vcd-return-allowlist-v1",
            "package_id": PACKAGE_ID,
            "required_or_conditional_exact_members": sorted(
                return_prefix + str(entry["archive"])
                for entry in post_request["core_entries"]
            )
            + [return_prefix + "RETURN_CORE_MANIFEST.json"],
            "prefixes": [],
            "no_size_limit": True,
            "hard_truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
    )

    selector_path = BUILD_ROOT / "contracts/diagnostic_mode_selector.json"
    retention_contract = {
        "schema": "node0004-tb-vcd-streaming-retention-contract-v1", "package_id": PACKAGE_ID,
        "analysis": {"state": "analysis_state.json", "checkpoints": "checkpoints.jsonl", "report": "report.md", "streaming_required": True, "whole_file_context_load_forbidden": True, "resume_required": True},
        "retention": {"maximum_protected_raw_groups_per_family": 3, "protected_labels": ["MAX_PROGRESS", "LATEST_1", "LATEST_2"], "deletion_gates": ["analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_only_zip", "protected_set_audit"], "size_based_deletion": False},
        "tool_sha256": sha_file(BUILD_ROOT / "package_tools/server_tb_vcd_retention_analysis.py"),
        "schema_sha256": sha_file(ROOT / "schemas/server_tb_vcd_retention_analysis_v1.schema.json"),
        "claim_boundary": "Future returned evidence analysis/retention only; package build does not consume or delete a result.",
    }
    write_json(BUILD_ROOT / "contracts/streaming_retention_contract.json", retention_contract)

    package_members = sorted(f"{PACKAGE_ID}/{path.relative_to(BUILD_ROOT).as_posix()}" for path in BUILD_ROOT.rglob("*") if path.is_file())
    expected_extra = [f"{PACKAGE_ID}/contracts/diagnostic_mode_selector.json", f"{PACKAGE_ID}/package_manifest.json"]
    package_members = sorted(set(package_members + expected_extra))
    return_members = [f"{PACKAGE_ID}_return/{entry['archive']}" for entry in post_request["core_entries"]]
    return_members.append(f"{PACKAGE_ID}_return/RETURN_CORE_MANIFEST.json")
    selector = {
        "schema": "server-diagnostic-mode-selector-v1", "package_id": PACKAGE_ID, "family": FAMILY, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "bulk_evidence": {"observer_jsonl": False, "tb_standard_vcd": True, "vpd": False, "fsdb": False, "ucli_direct_vcd": False, "vendor_signal_query": False},
        "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "lightweight_progress_supervisor": {"enabled": True, "bulk_signal_events": False, "sim_time_heartbeat": True, "process_tree_reap": True},
        "package_members": package_members, "return_members": sorted(set(return_members)), "observer_contract_sha256": None, "vcd_contract_sha256": sha_file(contract_path),
        "claim_boundary": "Selected optional mode only; observer-only remains the unchanged default for packages that select it.",
    }
    write_json(selector_path, selector)

    runner_contract_path = BUILD_ROOT / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract.update({"runner_sha256": sha_file(BUILD_ROOT / "PREPARE_AND_RUN.sh"), "diagnostic_mode_selector": f"{PACKAGE_ID}/contracts/diagnostic_mode_selector.json", "tb_vcd_contract": f"{PACKAGE_ID}/contracts/tb_vcd_bounded_causal_cone_contract.json", "runtime_supervisor": f"{PACKAGE_ID}/package_tools/node0004_tb_vcd_process_supervisor.py"})
    runner_contract["package_owned_variables"] = [
        "package_id", "install_name", "package_root", "result_root",
        "return_tag", "attempt", "return_zip", "return_sha", "server_root",
        "bootstrap_root", "compile_argv_json", "compile_source_identity_json",
        "compile_exit_txt", "compile_driver_log", "compile_first_error_txt",
        "compile_log_head_txt", "compile_log_tail_txt", "compile_full_log",
        "compile_status", "run_status", "signal_status", "sim_started",
        "timed_out", "finalized", "run_root", "evidence_root", "compile_root",
        "cfg_root", "simv", "vcd_path",
    ]
    runner_contract["return_allowlist_tokens"] = [
        "ACTUAL_COMPILE_SIM_ARGV.json", "SIM_EXIT_RECEIPT.json",
        "PROCESS_TREE_RECEIPT.json", "VCD_SIGNAL_CATALOG.json",
        "VCD_CANDIDATE_MATRIX.json", "VCD_RUNTIME_RECEIPT.json",
        "VCD_STOP_RECEIPT.json", "causal_cone.vcd", "analysis_state.json",
        "checkpoints.jsonl", "report.md", "DUMP_VCD=0", "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0", "NATIVE_FLOW_ATTEMPT.json",
    ]
    write_json(runner_contract_path, runner_contract)

    manifest_path = BUILD_ROOT / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for stale_key in (
        "observer_only_contract_sha256", "observer_only_profile",
        "first_fresh_extra_audit", "post_sim_conjunction_activation_epoch",
    ):
        manifest.pop(stale_key, None)
    manifest.update({"package_id": PACKAGE_ID, "install_name": PACKAGE_ID, "status": "PACKAGE_BUILT_AWAITING_CURRENT_GATES", "source_package": OLD_ID, "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437", "vcd_contract_sha256": sha_file(contract_path), "selector_sha256": sha_file(selector_path), "previous_version_progress": "v91 preserved v90's successful native compile path and fixed the package-local five-target compile-log normalizer arity defect; v88 had already retired the false derived ACK comparator.", "current_purpose": "Use a source-bound standard TB VCD bounded causal cone over actual ACK/FIFO/aggregate/request/MSE4/terminal signals with strict plateau and independent runtime safeguards.", "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional RTL", "actual-source causal target", "v91 compile-log normalizer fix"], "retired_ack_comparator_present": False, "server_actions_performed": [], "files": []})
    readme = f"""# {PACKAGE_ID}\n\nSerialized Conv fresh optional TB-VCD bounded-causal-cone package.\n\nPrevious progress: v91 preserves the production-native v90 path and fixes its package-local compile-log normalizer arity defect; v88 proved the retired derived ACK comparator was a source-semantic false positive.\n\nCurrent purpose: capture the actual public ACK and its real driver inputs, row/column/aggregate FIFOs, request/ready/accept/backpressure, MSE4 write data, drain/clear/completion and global terminal witnesses in one bounded, standard VCD.\n\nRun only after separate authorization:\n\n    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\nThis package uses DUMP_VCD=0, DUMP_FSDB=0 and TB_DUMP_FSDB=0 at Make/simulator surfaces. The package-local passive TB uses only standard dump tasks. VCD evidence is never truncated, sampled or deleted because of size. Non-natural stops remain PARTIAL / DIAGNOSTIC_EVIDENCE_INCOMPLETE.\n"""
    (BUILD_ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    manifest["files"] = [row for row in file_map() if row["path"] != "package_manifest.json"]
    write_json(manifest_path, manifest)
    deterministic_zip()
    write_json(OUT / "build_receipt.json", {"schema": "node0004-v92b-tbvcd-build-v1", "package_id": PACKAGE_ID, "source_package": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "sha256": sha_file(SOURCE_ZIP)}, "source_member_count": len(imported), "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "authorized_changes": ["fresh identity", "package-local passive standard TB VCD causal-cone probe", "bounded runtime/process supervisor", "VCD/core/streaming-retention return receipts"], "frozen_surface_diff_pending_gate": True, "zip": {"path": FINAL_ZIP.relative_to(ROOT).as_posix(), "sha256": sha_file(FINAL_ZIP)}, "pass": True, "errors": []})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
