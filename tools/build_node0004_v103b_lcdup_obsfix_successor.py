#!/usr/bin/env python3
"""Build serialized Conv v103 from exact v102 with counter/plateau/runtime fixes only."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v102b_lcdup_guardprocfs"
NEW = "r5_n4_hw_v103b_lcdup_obsfix"
SOURCE_ZIP = ROOT / "outputs/conv_node0004_v102b_lcdup_guardprocfs_release1" / f"{OLD}.zip"
OUT = ROOT / "outputs/conv_node0004_v103b_lcdup_obsfix_release1"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v102b_lcdup_guardprocfs_return_r1786958038398677116_3776638"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_base():
    path = ROOT / "tools/build_node0004_v102b_lcdup_guardprocfs_successor.py"
    spec = importlib.util.spec_from_file_location("node0004_v102_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v102 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OLD = OLD
    module.NEW = NEW
    module.SOURCE_ZIP = SOURCE_ZIP
    module.OUT = OUT
    module.TREE = TREE
    module.ZIP = ZIP
    return module


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor count differs: {count}")
    return text.replace(old, new)


def install_counter_observer() -> None:
    path = TREE / "tb_probe/observer_only_wide_causal.svh"
    text = path.read_text(encoding="utf-8")
    text = text.replace("`timescale 1ns/1ps", "`timescale 1ps/1ps", 1)
    text = text.replace("codex_time_ps = $rtoi($realtime * 1000.0);", "codex_time_ps = $time;")
    if "$rtoi" in text or "$realtime" in text:
        raise RuntimeError("32-bit-prone observer time conversion remains")

    contract = json.loads((TREE / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
    state_signals = [item["signal_id"] for item in contract["signals"] if item["signal_id"] != "sig_clk"]
    if sum(int(item["width_bits"]) for item in contract["signals"] if item["signal_id"] != "sig_clk") != 256:
        raise RuntimeError("v102 non-clock causal state is not exactly 256 bits")
    state_concat = ", ".join(state_signals)

    declarations = r'''
  // Package-local v103 qualified counter/plateau state.  These registers are
  // observer-only and never drive a DUT net.
  integer codex_counter_fd;
  integer codex_counter_enabled;
  string codex_counter_path;
  longint unsigned codex_counter_seq;
  longint unsigned codex_counter_time_ps;
  longint unsigned codex_owner_cycle;
  longint unsigned codex_plateau_cycles;
  longint unsigned cnt_lc3_accept;
  longint unsigned cnt_pe_tuple_wr;
  longint unsigned cnt_pe_tuple_rd;
  longint unsigned cnt_input1_accept;
  longint unsigned cnt_mem_tuple_wr;
  longint unsigned cnt_mem_tuple_rd;
  longint unsigned cnt_metadata_emit;
  longint unsigned cnt_prepared_wr;
  longint unsigned cnt_prepared_rd;
  longint unsigned cnt_wdata0_accept;
  longint unsigned cnt_wdata1_accept;
  longint unsigned cnt_terminal_witness;
  reg [255:0] codex_causal_state;
  reg [255:0] codex_previous_causal_state;
  reg [770:0] codex_global_witness;
  reg [770:0] codex_previous_global_witness;
  reg codex_counter_previous_valid;
  reg codex_target_active;
  reg codex_planned_stop_latched;
  reg codex_terminal_latched;
  reg codex_accept_qualified_progress;
  reg codex_state_has_xz;

  task automatic codex_emit_counter(input string record_kind);
    begin
      codex_counter_time_ps = $time;
      $fdisplay(codex_counter_fd, "{\"record_type\":\"%0s\",\"package_id\":\"%0s\",\"execution_id\":\"%0s\",\"attempt_id\":\"%0s\",\"seq\":%0d,\"sim_time\":%0d,\"timescale\":\"1ps\",\"owner_cycle\":%0d,\"target_active\":%0d,\"plateau_cycles\":%0d,\"lc3_accept\":%0d,\"pe_tuple_wr\":%0d,\"pe_tuple_rd\":%0d,\"input1_accept\":%0d,\"memory_tuple_wr\":%0d,\"memory_tuple_rd\":%0d,\"metadata_emit\":%0d,\"prepared_wr\":%0d,\"prepared_rd\":%0d,\"wdata0_accept\":%0d,\"wdata1_accept\":%0d,\"terminal_witness\":%0d,\"state_width\":256,\"state_4state\":\"%b\",\"global_witness_4state\":\"%b\",\"state_has_xz\":%0d}", record_kind, codex_package_id, codex_execution_id, codex_attempt_id, codex_counter_seq, codex_counter_time_ps, codex_owner_cycle, codex_target_active, codex_plateau_cycles, cnt_lc3_accept, cnt_pe_tuple_wr, cnt_pe_tuple_rd, cnt_input1_accept, cnt_mem_tuple_wr, cnt_mem_tuple_rd, cnt_metadata_emit, cnt_prepared_wr, cnt_prepared_rd, cnt_wdata0_accept, cnt_wdata1_accept, cnt_terminal_witness, codex_causal_state, codex_global_witness, codex_state_has_xz);
      codex_counter_seq = codex_counter_seq + 1;
    end
  endtask
'''
    text = replace_once(
        text,
        "  reg prev_sig_exec_slice13_finish;\n\n  task automatic codex_capture",
        "  reg prev_sig_exec_slice13_finish;\n" + declarations + "\n  task automatic codex_capture",
        "counter declarations",
    )

    old_initial = """    codex_seq = 0; codex_clock_count = 0; codex_have_previous = 0;
    if (codex_enabled) begin
      if (!$value$plusargs(\"CODEX_OBSERVER_CHUNK=%s\", codex_path)) $fatal(1, \"missing CODEX_OBSERVER_CHUNK\");
      if (!$value$plusargs(\"CODEX_PACKAGE_ID=%s\", codex_package_id)) $fatal(1, \"missing CODEX_PACKAGE_ID\");
      if (!$value$plusargs(\"CODEX_EXECUTION_ID=%s\", codex_execution_id)) $fatal(1, \"missing CODEX_EXECUTION_ID\");
      if (!$value$plusargs(\"CODEX_ATTEMPT_ID=%s\", codex_attempt_id)) $fatal(1, \"missing CODEX_ATTEMPT_ID\");
      codex_fd = $fopen(codex_path, \"w\");
      if (!codex_fd) $fatal(1, \"cannot open observer chunk\");
      #0; codex_capture(1); $fflush(codex_fd);
    end"""
    new_initial = """    codex_seq = 0; codex_clock_count = 0; codex_have_previous = 0;
    codex_counter_seq = 0; codex_owner_cycle = 0; codex_plateau_cycles = 0;
    cnt_lc3_accept = 0; cnt_pe_tuple_wr = 0; cnt_pe_tuple_rd = 0;
    cnt_input1_accept = 0; cnt_mem_tuple_wr = 0; cnt_mem_tuple_rd = 0;
    cnt_metadata_emit = 0; cnt_prepared_wr = 0; cnt_prepared_rd = 0;
    cnt_wdata0_accept = 0; cnt_wdata1_accept = 0; cnt_terminal_witness = 0;
    codex_counter_previous_valid = 0; codex_target_active = 0;
    codex_planned_stop_latched = 0; codex_terminal_latched = 0;
    codex_counter_enabled = 0;
    if (codex_enabled) begin
      if (!$value$plusargs(\"CODEX_OBSERVER_CHUNK=%s\", codex_path)) $fatal(1, \"missing CODEX_OBSERVER_CHUNK\");
      if (!$value$plusargs(\"CODEX_COUNTER_CHUNK=%s\", codex_counter_path)) $fatal(1, \"missing CODEX_COUNTER_CHUNK\");
      if (!$value$plusargs(\"CODEX_PACKAGE_ID=%s\", codex_package_id)) $fatal(1, \"missing CODEX_PACKAGE_ID\");
      if (!$value$plusargs(\"CODEX_EXECUTION_ID=%s\", codex_execution_id)) $fatal(1, \"missing CODEX_EXECUTION_ID\");
      if (!$value$plusargs(\"CODEX_ATTEMPT_ID=%s\", codex_attempt_id)) $fatal(1, \"missing CODEX_ATTEMPT_ID\");
      codex_fd = $fopen(codex_path, \"w\");
      if (!codex_fd) $fatal(1, \"cannot open observer chunk\");
      codex_counter_fd = $fopen(codex_counter_path, \"w\");
      if (!codex_counter_fd) $fatal(1, \"cannot open counter chunk\");
      codex_counter_enabled = 1;
      #0; codex_capture(1); $fflush(codex_fd);
    end"""
    text = replace_once(text, old_initial, new_initial, "observer initial")

    old_clock = r'''  always @(posedge sig_clk) if (codex_enabled) begin
    codex_clock_count = codex_clock_count + 1;
    if ((codex_clock_count & 262143) == 0) begin
      codex_time_ps = $time;
      $fdisplay(codex_fd, "{\"record_type\":\"HEARTBEAT\",\"package_id\":\"%0s\",\"execution_id\":\"%0s\",\"attempt_id\":\"%0s\",\"seq\":%0d,\"sim_time\":%0d,\"timescale\":\"1ps\",\"signal_id\":\"__heartbeat__\",\"width_bits\":1,\"value_4state\":\"0\"}", codex_package_id, codex_execution_id, codex_attempt_id, codex_seq, codex_time_ps);
      codex_seq = codex_seq + 1; $fflush(codex_fd);
      $display("CODEX_OBSERVER_SIM_TIME_V1 sim_time=%0d", codex_time_ps);
    end
  end
  final if (codex_enabled && codex_fd) begin $fflush(codex_fd); $fclose(codex_fd); end'''
    new_clock = rf'''  always @(posedge sig_clk) if (codex_enabled && codex_counter_enabled) begin
    codex_clock_count = codex_clock_count + 1;
    codex_owner_cycle = codex_owner_cycle + 1;
    codex_causal_state = {{{state_concat}}};
    codex_state_has_xz = $isunknown(codex_causal_state);
    codex_accept_qualified_progress = 0;
    if (sig_rst_n && !sig_slice_rst) begin
      if (sig_lc3_valid && !sig_lc3_bp) begin cnt_lc3_accept = cnt_lc3_accept + 1; codex_accept_qualified_progress = 1; end
      if (sig_pe8_wr) begin cnt_pe_tuple_wr = cnt_pe_tuple_wr + 1; codex_accept_qualified_progress = 1; end
      if (sig_pe8_rd) begin cnt_pe_tuple_rd = cnt_pe_tuple_rd + 1; codex_accept_qualified_progress = 1; end
      if (sig_mem_i1_split_wr) begin cnt_input1_accept = cnt_input1_accept + 1; codex_accept_qualified_progress = 1; end
      if (sig_mem_ag_wr) begin cnt_mem_tuple_wr = cnt_mem_tuple_wr + 1; codex_accept_qualified_progress = 1; end
      // One accepted Memory_AG tuple produces two 16-unit metadata
      // descriptors.  Counting the accepted tuple avoids treating a held
      // tag-valid level as repeated progress and still gives the exact
      // descriptor supply needed to adjudicate tuple10.
      if (sig_mem_ag_rd && !sig_mem_ag_empty) begin
        cnt_mem_tuple_rd = cnt_mem_tuple_rd + 1;
        cnt_metadata_emit = cnt_metadata_emit + 2;
        codex_accept_qualified_progress = 1;
      end
      if (sig_prepared_wr) begin cnt_prepared_wr = cnt_prepared_wr + 1; codex_accept_qualified_progress = 1; end
      if (sig_prepared_rd) begin cnt_prepared_rd = cnt_prepared_rd + 1; codex_accept_qualified_progress = 1; end
      if (sig_wdata_valid[0] && sig_wdata_ready[0]) begin cnt_wdata0_accept = cnt_wdata0_accept + 1; codex_accept_qualified_progress = 1; end
      if (sig_wdata_valid[1] && sig_wdata_ready[1]) begin cnt_wdata1_accept = cnt_wdata1_accept + 1; codex_accept_qualified_progress = 1; end
      if (sig_slice_finish && sig_exec_fetch_finish && sig_exec_slice13_finish && !codex_terminal_latched) begin
        cnt_terminal_witness = cnt_terminal_witness + 1; codex_terminal_latched = 1; codex_accept_qualified_progress = 1;
      end
    end
    codex_global_witness = {{cnt_lc3_accept, cnt_pe_tuple_wr, cnt_pe_tuple_rd, cnt_input1_accept, cnt_mem_tuple_wr, cnt_mem_tuple_rd, cnt_metadata_emit, cnt_prepared_wr, cnt_prepared_rd, cnt_wdata0_accept, cnt_wdata1_accept, cnt_terminal_witness, sig_slice_finish, sig_exec_fetch_finish, sig_exec_slice13_finish}};
    if (!sig_rst_n) begin
      codex_target_active = 0; codex_plateau_cycles = 0; codex_counter_previous_valid = 0; codex_terminal_latched = 0;
    end else begin
      if (!codex_target_active && !sig_slice_rst && (sig_prepared_valid || sig_lc3_valid || sig_mem_i1_split_wr)) begin
        codex_target_active = 1; codex_plateau_cycles = 0;
        codex_emit_counter("TARGET_ENTRY"); $fflush(codex_counter_fd);
      end
      if (codex_target_active && codex_counter_previous_valid) begin
        if (codex_state_has_xz || codex_accept_qualified_progress || codex_causal_state !== codex_previous_causal_state || codex_global_witness !== codex_previous_global_witness)
          codex_plateau_cycles = 0;
        else
          codex_plateau_cycles = codex_plateau_cycles + 1;
      end
      codex_previous_causal_state = codex_causal_state;
      codex_previous_global_witness = codex_global_witness;
      codex_counter_previous_valid = 1;
    end
    if ((codex_owner_cycle & 16383) == 0) begin
      codex_emit_counter("COUNTER_HEARTBEAT");
      codex_time_ps = $time;
      $fdisplay(codex_fd, "{{\"record_type\":\"HEARTBEAT\",\"package_id\":\"%0s\",\"execution_id\":\"%0s\",\"attempt_id\":\"%0s\",\"seq\":%0d,\"sim_time\":%0d,\"timescale\":\"1ps\",\"signal_id\":\"__heartbeat__\",\"width_bits\":1,\"value_4state\":\"0\"}}", codex_package_id, codex_execution_id, codex_attempt_id, codex_seq, codex_time_ps);
      codex_seq = codex_seq + 1; $fflush(codex_fd); $fflush(codex_counter_fd);
      $display("CODEX_OBSERVER_SIM_TIME_V2 sim_time=%0d owner_cycle=%0d", codex_time_ps, codex_owner_cycle);
    end
    if (codex_target_active && !codex_planned_stop_latched && !codex_state_has_xz && codex_plateau_cycles >= 1048576) begin
      codex_planned_stop_latched = 1; codex_emit_counter("PLANNED_PLATEAU_STOP");
      $fflush(codex_fd); $fflush(codex_counter_fd);
      $display("CODEX_OBSERVER_PLANNED_STOP_V1 sim_time=%0d owner_cycle=%0d plateau_cycles=%0d", $time, codex_owner_cycle, codex_plateau_cycles);
      $finish;
    end
  end
  final if (codex_enabled) begin
    codex_causal_state = {{{state_concat}}};
    codex_global_witness = {{cnt_lc3_accept, cnt_pe_tuple_wr, cnt_pe_tuple_rd, cnt_input1_accept, cnt_mem_tuple_wr, cnt_mem_tuple_rd, cnt_metadata_emit, cnt_prepared_wr, cnt_prepared_rd, cnt_wdata0_accept, cnt_wdata1_accept, cnt_terminal_witness, sig_slice_finish, sig_exec_fetch_finish, sig_exec_slice13_finish}};
    codex_state_has_xz = $isunknown(codex_causal_state);
    if (codex_counter_fd) begin
      codex_counter_time_ps = $time;
      $fdisplay(codex_counter_fd, "{{\"record_type\":\"FINAL\",\"package_id\":\"%0s\",\"execution_id\":\"%0s\",\"attempt_id\":\"%0s\",\"seq\":%0d,\"sim_time\":%0d,\"timescale\":\"1ps\",\"owner_cycle\":%0d,\"target_active\":%0d,\"plateau_cycles\":%0d,\"lc3_accept\":%0d,\"pe_tuple_wr\":%0d,\"pe_tuple_rd\":%0d,\"input1_accept\":%0d,\"memory_tuple_wr\":%0d,\"memory_tuple_rd\":%0d,\"metadata_emit\":%0d,\"prepared_wr\":%0d,\"prepared_rd\":%0d,\"wdata0_accept\":%0d,\"wdata1_accept\":%0d,\"terminal_witness\":%0d,\"state_width\":256,\"state_4state\":\"%b\",\"global_witness_4state\":\"%b\",\"state_has_xz\":%0d}}", codex_package_id, codex_execution_id, codex_attempt_id, codex_counter_seq, codex_counter_time_ps, codex_owner_cycle, codex_target_active, codex_plateau_cycles, cnt_lc3_accept, cnt_pe_tuple_wr, cnt_pe_tuple_rd, cnt_input1_accept, cnt_mem_tuple_wr, cnt_mem_tuple_rd, cnt_metadata_emit, cnt_prepared_wr, cnt_prepared_rd, cnt_wdata0_accept, cnt_wdata1_accept, cnt_terminal_witness, codex_causal_state, codex_global_witness, codex_state_has_xz);
      codex_counter_seq = codex_counter_seq + 1; $fflush(codex_counter_fd); $fclose(codex_counter_fd);
    end
    if (codex_fd) begin $fflush(codex_fd); $fclose(codex_fd); end
  end'''
    text = replace_once(text, old_clock, new_clock, "qualified counter clock block")
    path.write_text(text, encoding="utf-8", newline="\n")


BRIDGE = r'''#!/usr/bin/env python3
"""Bind the sole simulation guard to counter heartbeat/process/plateau receipts."""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path

def canonical(v): return (json.dumps(v,indent=2,sort_keys=True)+"\n").encode()
def atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_name(f".{p.name}.tmp.{os.getpid()}"); t.write_bytes(data); os.replace(t,p)
def load(p): return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
def main():
    a=argparse.ArgumentParser(); a.add_argument("--guard",type=Path,required=True); a.add_argument("--counter",type=Path,required=True); a.add_argument("--package-id",required=True); a.add_argument("--execution-id",required=True); a.add_argument("--attempt-id",required=True); a.add_argument("--output-dir",type=Path,required=True); ns=a.parse_args()
    errors=[]; rows=[]; last_time=-1; last_cycle=-1; expected_seq=0; h=hashlib.sha256(); size=0; ended=False
    if ns.counter.is_file():
      with ns.counter.open("rb") as f:
        for number,raw in enumerate(f,1):
          size+=len(raw); h.update(raw); ended=raw.endswith(b"\n")
          try: row=json.loads(raw)
          except Exception as e: errors.append(f"counter line {number}: {e}"); continue
          if tuple(row.get(k) for k in ("package_id","execution_id","attempt_id")) != (ns.package_id,ns.execution_id,ns.attempt_id): errors.append(f"counter line {number}: identity drift")
          if row.get("seq") != expected_seq: errors.append(f"counter line {number}: sequence gap")
          expected_seq += 1
          t=row.get("sim_time"); c=row.get("owner_cycle")
          if not isinstance(t,int) or t < last_time: errors.append(f"counter line {number}: sim time nonmonotonic")
          else: last_time=t
          if not isinstance(c,int) or c < last_cycle: errors.append(f"counter line {number}: owner cycle nonmonotonic")
          else: last_cycle=c
          state=row.get("state_4state","")
          if len(state)!=256: errors.append(f"counter line {number}: complete state width differs")
          rows.append(row)
    else: errors.append("counter chunk absent")
    if rows and not ended: errors.append("counter chunk lacks complete newline")
    guard=load(ns.guard); term=guard.get("termination",{})
    reaped=guard.get("pass") is True and guard.get("process_fully_reaped") is True and term.get("process_tree_reaped") is True and not term.get("owned_pids_remaining") and not term.get("owned_process_identities_remaining")
    if not reaped: errors.append("sole simulation guard did not prove full PID+start-time reap")
    heart=[r for r in rows if r.get("record_type") in {"TARGET_ENTRY","COUNTER_HEARTBEAT","PLANNED_PLATEAU_STOP","FINAL"}]
    planned=[r for r in rows if r.get("record_type")=="PLANNED_PLATEAU_STOP"]
    if len(planned)>1: errors.append("planned stop is not one-shot")
    if len(rows)>1 and not (last_time>rows[0].get("sim_time",-1) and last_cycle>rows[0].get("owner_cycle",-1)): errors.append("counter time/cycle did not advance")
    atomic(ns.output_dir/"supervisor_heartbeat.jsonl",b"".join((json.dumps({"simulation_time":r["sim_time"],"owner_cycle":r["owner_cycle"],"record_type":r["record_type"]},sort_keys=True,separators=(",",":"))+"\n").encode() for r in heart))
    process={"schema":"server-observer-runtime-supervision-v1","package_id":ns.package_id,"execution_id":ns.execution_id,"attempt_id":ns.attempt_id,"pass":reaped and not errors,"process_tree_reaped":reaped,"owned_pids_remaining":term.get("owned_pids_remaining",[]),"owned_process_identities_remaining":term.get("owned_process_identities_remaining",[]),"root_exit":term.get("root_exit",guard.get("child_exit")),"received_signal":None,"simulation_time_progress_observed":len(rows)>1 and last_time>rows[0].get("sim_time",-1),"last_simulation_time":last_time if rows else None,"counter_chunk":{"path":ns.counter.name,"bytes":size,"sha256":h.hexdigest(),"rows":len(rows),"complete_final_newline":ended},"sole_exit_authority":"server_observer_operational_attempt_boundary.py","guard_receipt":guard,"errors":errors,"claim_boundary":"Sole guard process-tree and counter transport binding only; no DUT verdict."}
    atomic(ns.output_dir/"PROCESS_TREE_RECEIPT.json",canonical(process))
    plateau={"schema":"node0004-observer-planned-plateau-stop-v1","package_id":ns.package_id,"execution_id":ns.execution_id,"attempt_id":ns.attempt_id,"planned_stop":len(planned)==1,"one_shot":len(planned)<=1,"row":planned[0] if planned else None,"diagnostic_status":"DIAGNOSTIC_EVIDENCE_INCOMPLETE" if planned else "NOT_APPLICABLE","natural_terminal":False,"errors":errors,"claim_boundary":"Planned diagnostic plateau only; never natural terminal or Formal-D."}
    atomic(ns.output_dir/"PLANNED_STOP_RECEIPT.json",canonical(plateau))
    ledger={"schema":"node0004-observer-qualified-counter-ledger-v1","package_id":ns.package_id,"execution_id":ns.execution_id,"attempt_id":ns.attempt_id,"pass":not errors,"rows":len(rows),"first":rows[0] if rows else None,"final":rows[-1] if rows else None,"planned_stop_rows":len(planned),"heartbeat_cadence_owner_cycles":16384,"plateau_required_cycles":1048576,"complete_state_width":256,"accept_qualified":True,"errors":errors,"claim_boundary":"Clock-qualified observer counters and full-state plateau evidence only; no DUT verdict."}
    atomic(ns.output_dir/"OBSERVER_COUNTER_LEDGER.json",canonical(ledger))
    return 0 if process["pass"] and ledger["pass"] else 1
if __name__=="__main__": raise SystemExit(main())
'''


def install_bridge_and_patch_parser() -> None:
    bridge = TREE / "package_tools/node0004_observer_counter_guard_bridge.py"
    bridge.write_text(BRIDGE, encoding="utf-8", newline="\n")
    parser_path = TREE / "package_tools/node0004_observerwide_event_parser.py"
    text = parser_path.read_text(encoding="utf-8")
    text = replace_once(text, '    parser.add_argument("--guard-receipt", type=Path)\n', '    parser.add_argument("--guard-receipt", type=Path)\n    parser.add_argument("--planned-stop-receipt", type=Path, required=True)\n', "planned stop parser argument")
    text = replace_once(text, "    guard = load_json(args.guard_receipt) if args.guard_receipt else {}\n", "    guard = load_json(args.guard_receipt) if args.guard_receipt else {}\n    planned = load_json(args.planned_stop_receipt)\n    planned_stop = planned.get(\"planned_stop\") is True\n", "planned stop load")
    text = replace_once(text, '            "natural_terminal": args.exit_code == 0 and args.signal == "NONE" and guard.get("guard_triggered") is not True,\n', '            "natural_terminal": args.exit_code == 0 and args.signal == "NONE" and guard.get("guard_triggered") is not True and not planned_stop and last_values.get("sig_slice_finish") == "1" and last_values.get("sig_exec_slice13_finish") == "1",\n            "planned_diagnostic_stop": planned_stop,\n', "natural terminal qualification")
    text = replace_once(text, '            "classification": "RETURN_REQUIRES_FAMILY_SIGNAL_INTERPRETATION" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",\n', '            "classification": ("DIAGNOSTIC_EVIDENCE_COMPLETE_PLANNED_PLATEAU" if complete and planned_stop else "RETURN_REQUIRES_FAMILY_SIGNAL_INTERPRETATION" if complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"),\n            "planned_stop_receipt": planned,\n', "planned stop classification")
    parser_path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "observer_chunk=\n", "observer_chunk=\ncounter_chunk=\n", "counter variable")
    text = replace_once(text, 'observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"\n', 'observer_chunk="$evidence_root/observer/chunks/events-000000.jsonl"\ncounter_chunk="$evidence_root/observer/chunks/counters-000000.jsonl"\n', "counter path")
    text = text.replace("+CODEX_OBSERVER_CHUNK=$observer_chunk", "+CODEX_OBSERVER_CHUNK=$observer_chunk +CODEX_COUNTER_CHUNK=$counter_chunk")
    text = text.replace('"+CODEX_OBSERVER_CHUNK=$observer_chunk"', '"+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_COUNTER_CHUNK=$counter_chunk"')
    text = replace_once(
        text,
        '"+CODEX_CAUSAL_OBSERVER","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL"]}',
        '"+CODEX_CAUSAL_OBSERVER","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL","+CODEX_COUNTER_CHUNK=<attempt-counter>"]}',
        "actual argv counter binding",
    )
    text = replace_once(
        text,
        '"$simv" "$observer_chunk" <<\'PY\'',
        '"$simv" "$observer_chunk" "$counter_chunk" <<\'PY\'',
        "native flow counter argument",
    )
    text = replace_once(
        text,
        ' source_identity,sca_cfg,sca_cfg_d,simv,observer_chunk)=sys.argv[1:]',
        ' source_identity,sca_cfg,sca_cfg_d,simv,observer_chunk,counter_chunk)=sys.argv[1:]',
        "native flow counter unpack",
    )
    text = replace_once(
        text,
        'f"+CODEX_OBSERVER_CHUNK={observer_chunk}",f"+CODEX_PACKAGE_ID={pkg}"',
        'f"+CODEX_OBSERVER_CHUNK={observer_chunk}",f"+CODEX_COUNTER_CHUNK={counter_chunk}",f"+CODEX_PACKAGE_ID={pkg}"',
        "native flow planned counter",
    )
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if "supervise-phase --phase simulation" in line]
    if len(matches) != 1 or "server_observer_runtime_supervision.py" not in lines[matches[0]]:
        raise RuntimeError(f"sole simulation authority anchor differs: {matches}")
    lines[matches[0]] = 'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase simulation --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$operational_stop_receipt" --guard-log "$operational_guard_log" --timeout 3660 --grace 45 -- "$simv" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk" "+CODEX_COUNTER_CHUNK=$counter_chunk" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt"'
    lines.insert(matches[0], "# server_observer_runtime_supervision.py is intentionally retired here: the operational guard above is the sole simulation process/wall authority; the bridge below preserves process-tree and sim-time receipts.")
    text = "\n".join(lines) + "\n"
    bridge_call = 'python3 "$package_root/package_tools/node0004_observer_counter_guard_bridge.py" --guard "$operational_stop_receipt" --counter "$counter_chunk" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --output-dir "$evidence_root"\nbridge_status=$?\n'
    text = replace_once(text, "run_status=$?\nset -e\n", "run_status=$?\n" + bridge_call + "set -e\n", "guard counter bridge")
    old_parser = '--guard-receipt "$guard_receipt" --output-dir "$evidence_root"'
    new_parser = '--guard-receipt "$guard_receipt" --planned-stop-receipt "$evidence_root/PLANNED_STOP_RECEIPT.json" --output-dir "$evidence_root"'
    text = replace_once(text, old_parser, new_parser, "parser planned stop")
    old_natural = '  [ "$run_status" -eq 0 ] && export CODEX_NATURAL_TERMINAL=true\n'
    new_natural = '''  natural_terminal="$(python3 - "$evidence_root/SIM_EXIT_RECEIPT.json" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); print(str(p.is_file() and json.loads(p.read_text()).get("natural_terminal") is True).lower())
PY
)"
  export CODEX_NATURAL_TERMINAL="$natural_terminal"
'''
    text = replace_once(text, old_natural, new_natural, "qualified natural terminal")
    text = replace_once(
        text,
        'and not d.get("termination",{}).get("owned_pids_remaining")).lower())',
        'and not d.get("termination",{}).get("owned_pids_remaining") and not d.get("termination",{}).get("owned_process_identities_remaining")).lower())',
        "finalization PID plus start-time reap admission",
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    unused = TREE / "package_tools/server_observer_runtime_supervision.py"
    if unused.exists():
        unused.unlink()


def update_contracts() -> None:
    observer_path = TREE / "contracts/observer_only_wide_causal_contract.json"
    observer = json.loads(observer_path.read_text(encoding="utf-8"))
    if len(observer.get("signals", [])) != 52:
        raise RuntimeError("52-signal causal cone changed")
    observer["package_id"] = NEW
    observer["package_local_counter_plateau"] = {
        "schema": "node0004-observer-qualified-counter-plateau-v1",
        "sim_time_source": "$time under module timescale 1ps/1ps",
        "owner_clock_heartbeat_cycles": 16384,
        "required_plateau_cycles": 1048576,
        "complete_causal_state_bits": 256,
        "accept_qualified_counters": ["lc3_accept", "pe_tuple_wr", "pe_tuple_rd", "input1_accept", "memory_tuple_wr", "memory_tuple_rd", "metadata_emit", "prepared_wr", "prepared_rd", "wdata0_accept", "wdata1_accept", "terminal_witness"],
        "global_witness": "all qualified counters plus slice/fetch/slice13 terminal bits",
        "xz_resets_plateau": True,
        "planned_stop_is_natural_terminal": False,
    }
    observer["execution"]["runtime_supervision"] = "PROCESS_TREE_REAP_AND_SIM_TIME_HEARTBEAT"
    observer["package_members"]["runtime_supervisor"] = f"{NEW}/package_tools/node0004_observer_counter_guard_bridge.py"
    observer["package_members"]["counter_guard_bridge"] = f"{NEW}/package_tools/node0004_observer_counter_guard_bridge.py"
    observer["return_members"]["counter_chunk"] = f"{NEW}_return/observer/chunks/counters-000000.jsonl"
    observer["return_members"]["counter_ledger"] = f"{NEW}_return/evidence/OBSERVER_COUNTER_LEDGER.json"
    observer["return_members"]["planned_stop"] = f"{NEW}_return/evidence/PLANNED_STOP_RECEIPT.json"
    observer["claim_boundary"] = "Exact 52-signal transitions plus 64-bit-safe accept-qualified counter ledger and complete-state/global-witness plateau; a planned plateau is diagnostic, never natural terminal."
    observer_path.write_bytes(canonical(observer))

    guard_contract_path = TREE / "contracts/observer_operational_guard_contract.json"
    guard_contract = json.loads(guard_contract_path.read_text(encoding="utf-8"))
    guard_contract["package_id"] = NEW
    guard_contract["thresholds"]["simulation_wall_seconds"] = 3660
    guard_contract["single_simulation_exit_authority"] = True
    guard_contract["inner_wall_timeout"] = None
    guard_contract_path.write_bytes(canonical(guard_contract))

    # The package admission preflight must validate the same sole simulation
    # wall authority that the runner and operational contract use.  v102 had
    # an outer 3600-second guard and an inner 3660-second supervisor; v103
    # removes the inner supervisor and deliberately uses one 3660-second
    # operational guard, so retaining the inherited 3600 constant here would
    # reject the corrected package for an identity mismatch of our own making.
    preflight_path = TREE / "package_tools/package_release_preflight.py"
    preflight = preflight_path.read_text(encoding="utf-8")
    preflight = replace_once(
        preflight,
        '"simulation_wall_seconds": 3600,',
        '"simulation_wall_seconds": 3660,',
        "release preflight sole simulation wall",
    )
    preflight_path.write_text(preflight, encoding="utf-8", newline="\n")

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    present = {item["archive"] for item in request["core_entries"]}
    for archive, source in (
        ("observer/chunks/counters-000000.jsonl", "evidence/observer/chunks/counters-000000.jsonl"),
        ("evidence/OBSERVER_COUNTER_LEDGER.json", "evidence/OBSERVER_COUNTER_LEDGER.json"),
        ("evidence/PLANNED_STOP_RECEIPT.json", "evidence/PLANNED_STOP_RECEIPT.json"),
    ):
        if archive not in present:
            request["core_entries"].append({"archive": archive, "required": False, "source": source, "source_root": "attempt"})
    request_path.write_bytes(canonical(request))
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    post["request_sha256"] = sha_file(request_path)
    post_path.write_bytes(canonical(post))

    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    prefix = f"{NEW}_return/"
    for item in (
        prefix + "observer/chunks/counters-000000.jsonl",
        prefix + "evidence/OBSERVER_COUNTER_LEDGER.json",
        prefix + "evidence/PLANNED_STOP_RECEIPT.json",
    ):
        if item not in allow["required"]:
            allow["required"].append(item)
    allow_path.write_bytes(canonical(allow))


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": p.relative_to(TREE).as_posix(), "bytes": p.stat().st_size, "sha256": sha_file(p)}
        for p in sorted(x for x in TREE.rglob("*") if x.is_file())
        if p.name != "package_manifest.json"
    ]


def finalize_metadata(base) -> None:
    base.update_contracts()
    # base update_contracts recalculates the runner hash after our runtime edits.
    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    for name in ("formal_return_analysis.json", "RULE_GAP_AUDIT.json", "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"):
        shutil.copy2(ANALYSIS / name, provenance / f"v102b_{name}")
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v103b-lcdup-obsfix-package-manifest-v1",
        "package_id": NEW,
        "source_package": OLD,
        "activation_epoch": "node0004-v102-runtime-observer-counter-plateau-fix-v1",
        "build_gate_registry_sha256": sha_file(ROOT / "contracts/server_package_build_gate_registry_v1.json"),
        "observer_only_semantic_version": 5,
        "first_fresh_semantic_version": 6,
        "first_fresh_after_change": True,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "previous_version_progress": "v102 compiled and entered the frozen LC3/PE8/Memory_AG target, but duplicated 3600/3660 wall authorities, signed-32 observer time and transition-only progress prevented tuple10 adjudication and left one PID unreaped.",
        "current_purpose": "Keep the exact LC9-to-LC3 configuration, functional RTL, workload and 52-signal cone while adding 64-bit time, qualified counters, complete-state plateau, one simulation exit authority and guard-before-return binding.",
        "observer_time_model": {"source": "$time", "module_timescale": "1ps/1ps", "width_bits": 64, "signed_32_conversion_forbidden": True},
        "plateau_model": {"target_only": True, "qualified_counter_stability": True, "complete_state_bits": 256, "global_witness_stability": True, "xz_forbidden": True, "required_owner_cycles": 1048576},
        "simulation_exit_authority": {"count": 1, "authority": "server_observer_operational_attempt_boundary.py", "wall_seconds": 3660, "inner_timeout": None},
        "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3 mapper semantics", "52-signal causal cone"],
        "changed_surface": ["fresh identity", "observer 64-bit time", "accept-qualified counters", "complete-state/global-witness plateau", "single simulation exit authority", "guard/counter/process return bridge"],
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_FIX_REQUIRED",
        "server_actions_performed": [],
    })
    readme = TREE / "README.md"
    readme.write_text(
        "# Serialized Conv node0004 v103 observer/runtime correction\n\n"
        "v102 proved production compile and target entry. This fresh package keeps the exact LC9→LC3 mapper/config, workload, functional RTL and 52-signal tuple10 cone. It changes only observer time/counters/plateau and simulation exit/return handling.\n\n"
        f"Future command after managed-storage publication and separate server authorization:\n\n`bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "This package has not been uploaded or run.\n",
        encoding="utf-8", newline="\n",
    )
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(x for x in TREE.rglob("*") if x.is_file()):
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2026, 8, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    OUT.mkdir(parents=True)
    base = load_base()
    base.safe_extract()
    base.replace_identity()
    base.regenerate_source_bound_observer()
    install_counter_observer()
    install_bridge_and_patch_parser()
    patch_runner()
    update_contracts()
    finalize_metadata(base)
    deterministic_zip()
    receipt = {
        "schema": "node0004-v103b-lcdup-obsfix-build-v1",
        "package_id": NEW,
        "source_zip": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha_file(SOURCE_ZIP)},
        "package_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3 mapper semantics", "52-signal causal cone"],
        "changed_surface": ["fresh identity", "observer", "qualified counters", "plateau", "simulation exit and return bridge"],
        "status": "LOCAL_BUILD_PENDING_GATES",
        "storage_manager_called": False,
        "server_actions_performed": [],
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
