#!/usr/bin/env python3
"""Persist v83 stable-phase evidence before the frozen bounded collector mutates sim.log."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys

def sha256(path: pathlib.Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--package-root",type=pathlib.Path,required=True)
    ap.add_argument("--attempt-root",type=pathlib.Path,required=True); ap.add_argument("--phase-live-log",type=pathlib.Path,required=True)
    ap.add_argument("--phase-output",type=pathlib.Path,required=True); a=ap.parse_args()
    if not a.phase_live_log.is_file(): raise RuntimeError("immutable raw stable-phase input is missing")
    before_bytes=a.phase_live_log.stat().st_size; before_sha=sha256(a.phase_live_log)
    phase=subprocess.run([sys.executable,str(a.package_root/"package_tools/buffer_ack_phase_parser.py"),"--log",str(a.phase_live_log),"--output",str(a.phase_output)],text=True,capture_output=True,check=False)
    phase_error=None; receipt=None
    if phase.returncode or not a.phase_output.is_file(): phase_error="exact stable-phase parser failed: "+phase.stderr
    else:
        value=json.loads(a.phase_output.read_text(encoding="utf-8")); receipt={
          "schema":"node0004-buffer-ack-stable-phase-parser-receipt-v1","parser_exit_status":phase.returncode,
          "decision":value["decision"],"decision_sha256":sha256(a.phase_output),"target_instance":value["target_instance"],
          "live_event_count":value["live_event_count"],"sequence_count":value["sequence_count"],
          "complete_sequence_count":value["complete_sequence_count"],"raw_phase_input_bytes_before_bounded_projection":before_bytes,
          "raw_phase_input_sha256_before_bounded_projection":before_sha,"parsed_before_frozen_bounded_collector":True,
          "sample_schedule":"PRE@negedge+250ps; EDGE; +1ps; +250ps; +750ps"}
        evidence=a.attempt_root/"evidence"; evidence.mkdir(parents=True,exist_ok=True)
        (evidence/"buffer_ack_phase_parser_receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    frozen=None; frozen_error=None
    if (a.attempt_root/"evidence/compile_exit_status.txt").is_file():
        frozen=subprocess.run([sys.executable,str(a.package_root/"package_tools/node0004_v79_post_sim_plugin.py"),"--package-root",str(a.package_root),"--attempt-root",str(a.attempt_root)],text=True,capture_output=True,check=False)
        if frozen.returncode: frozen_error="v79 frozen collector failed: "+frozen.stderr
    failures=[x for x in (phase_error,frozen_error) if x]
    if failures: raise RuntimeError("; ".join(failures))
    print(json.dumps({"buffer_ack_stable_phase":receipt,"frozen_v79_collector":None if frozen is None else frozen.stdout.strip(),"ordering":"STABLE_PHASE_PARSE_PERSIST_BEFORE_BOUNDED_SIM_LOG_PROJECTION"},sort_keys=True))
    return 0
if __name__ == "__main__": raise SystemExit(main())
