#!/usr/bin/env python3
"""Formal GAP node0071 v53 route-factor return analysis."""
from __future__ import annotations
import argparse,hashlib,json,re,sys,tempfile,zipfile
from pathlib import Path
import analyze_gap_node0071_v51_return as base

ROOT=Path(__file__).resolve().parents[1]
INSTALL="r5_n71_gap_v53_mse4_route_factor_diag"
RETURN_PATH=Path(r"C:\Users\15383\Downloads\r5_n71_gap_v53_mse4_route_factor_diag_r1786179791001243962_4049814_return.zip")
RETURN_SHA="36c04e4e93fd2f608239c634186c895d71a0edbbd697a8294a9678650d712ff4"
SOURCE_PATH=ROOT/"artifacts/operator_config_validation/r5-server-test-packages/pending"/f"{INSTALL}.zip"
SOURCE_SHA="5a50594bae06c56040d48637f46709a32dea292d6af925c36b4a235d7a887d8a"
EXECUTION="r1786179791001243962_4049814"
ATTEMPT="a4049814"

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path:Path,v:object):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")

def analyze(output:Path)->dict:
 base.INSTALL=INSTALL;base.RETURN_ROOT=f"{INSTALL}_return";base.RETURN_PATH=RETURN_PATH;base.RETURN_SHA=RETURN_SHA;base.RETURN_BYTES=182212;base.SOURCE_PATH=SOURCE_PATH;base.SOURCE_SHA=SOURCE_SHA;base.EXECUTION=EXECUTION;base.ATTEMPT=ATTEMPT
 report=base.analyze(output)
 with tempfile.TemporaryDirectory(prefix="gap-v53-return-") as td:
  d=Path(td)
  with zipfile.ZipFile(RETURN_PATH) as z:z.extractall(d/"ret")
  with zipfile.ZipFile(SOURCE_PATH) as z:z.extractall(d/"src")
  returned=d/"ret"/f"{INSTALL}_return";source=d/"src"/INSTALL;observer=returned/"runs/return_observer.log";parser=source/"package_tools/gap_node0071_mse4_route_factor_decision.py"
  replay_path=output/"formal_replay/mse4_route_factor.json";replay=base.run_parser([sys.executable,str(parser),"analyze","--observer-log",str(observer),"--output",str(replay_path)],replay_path)
  decision=json.loads((returned/"evidence/mse4_route_factor_decision.json").read_text(encoding="utf-8"));equal=replay.get("output")==decision;text=observer.read_text(encoding="utf-8",errors="replace")
  raw_records=[x for x in text.splitlines() if "MSE4_ROUTE_FACTOR_V1" in x];raw_counts={k:sum(f"event={k}" in x.replace(" ","") for x in raw_records) for k in ("QUALIFIED_EDGE","FACTOR_EDGE","HEARTBEAT")}
  # Exact parser requires no spaces after event=, while $fdisplay right-justifies
  # shorter event strings.  Reparse the same immutable log with whitespace tolerance.
  fixed_text=re.sub(r"event=\s+(FACTOR_EDGE|HEARTBEAT)",r"event=\1",text)
  fixed_log=output/"formal_replay/observer_event_spacing_normalized.log";fixed_log.write_text(fixed_text,encoding="utf-8",newline="\n")
  fixed_path=output/"formal_replay/mse4_route_factor_whitespace_tolerant.json";fixed=base.run_parser([sys.executable,str(parser),"analyze","--observer-log",str(fixed_log),"--output",str(fixed_path)],fixed_path)
  fixed_decision=fixed.get("output",{});masks=decision["progress_masks"];factors=decision["factor_seen_high_masks"]
  expected={"ob_rd":"0xffff","pre_req_hs0":"0xffff","pre_req_hs1":"0xffff","pre_wdata_hs0":"0xffff","pre_wdata_hs1":"0xffff","local_req_hs0":"0x0001","local_req_hs1":"0x0001","local_wdata_hs0":"0x0001","local_wdata_hs1":"0x0001","global_req_in_hs0":"0xfffe","global_req_in_hs1":"0xfffe","global_req_out_hs0":"0xfffe","global_req_out_hs1":"0xfffe","global_wdata_in_hs0":"0x0000","global_wdata_in_hs1":"0x0000","global_wdata_out_hs0":"0x0000","global_wdata_out_hs1":"0x0000","finish":"0x0001"}
  masks_expected=all(masks.get(k)==v for k,v in expected.items());remote=factors.get("remote")=="0xfffe";marker="# mse4_route_factor=1" in text
  parser_spacing_bug=(raw_counts["FACTOR_EDGE"]>0 or raw_counts["HEARTBEAT"]>0) and decision["record_counts"]["FACTOR_EDGE"]==0 and decision["record_counts"]["HEARTBEAT"]==0 and fixed_decision.get("record_counts")==raw_counts
  evidence_valid=all((replay["exit_code"]==0,equal,marker,masks_expected,remote,decision["stable_level_or_heartbeat_is_progress"] is False,len(raw_records)==sum(raw_counts.values()),len([x for x in raw_records if "event=QUALIFIED_EDGE" in x])<384))
  if not evidence_valid:report["return_analysis"]["errors"].append("v53 route-factor evidence invalid")
 report.update({
  "schema":"gap-node0071-v53-repeatable-return-analysis-v1","status":"PARTIAL_INTERRUPTED_REMOTE_REQUEST_PATH_PROVEN_WDATA_MUX_INPUT_ABSENT",
  "runtime_binding":{**report["runtime_binding"],"actual_compiled_production_identity":"NOT_DYN_RECOVERED_BY_V53_RETURN"},
  "formal_decision_collection":{**report["formal_decision_collection"],"route_factor_replay_exit":replay["exit_code"],"route_factor_returned_equals_replay":equal,"parser_event_spacing_bug":parser_spacing_bug},
  "local_exact_parser_replay":{**report["local_exact_parser_replay"],"route_factor":replay,"whitespace_tolerant_route_factor":fixed},
  "qualified_progress":{**report["qualified_progress"],"progress_masks":masks,"factor_seen_high_masks":factors,"returned_record_counts":decision["record_counts"],"raw_record_counts":raw_counts,"qualified_limit":384,"factor_limit":128,"state_factor_or_heartbeat_counts_as_progress":False,"coverage_unexhausted":raw_counts["QUALIFIED_EDGE"]<384,"all_slices_mse4_pre_request_and_wdata_accepted":all(masks[x]=="0xffff" for x in ("pre_req_hs0","pre_req_hs1","pre_wdata_hs0","pre_wdata_hs1")),"remote_request_fifo_input_and_output_accepted_slices1_15":all(masks[x]=="0xfffe" for x in ("global_req_in_hs0","global_req_in_hs1","global_req_out_hs0","global_req_out_hs1")),"remote_wdata_fifo_input_and_output_accept_absent":all(masks[x]=="0x0000" for x in ("global_wdata_in_hs0","global_wdata_in_hs1","global_wdata_out_hs0","global_wdata_out_hs1"))},
  "last_proven_good":{"boundary":"SLICES1_15_REMOTE_REQUEST_FIFO_INPUT_AND_OUTPUT_ACCEPTED","qualified_masks":{k:masks[k] for k in ("ob_rd","pre_req_hs0","pre_req_hs1","pre_wdata_hs0","pre_wdata_hs1","global_req_in_hs0","global_req_in_hs1","global_req_out_hs0","global_req_out_hs1")}},
  "first_divergence":{"boundary":"MSE4_PRE_WDATA_ACCEPTED_BUT_SELECTED_GLOBAL_WDATA_FIFO_INPUT_VALID_AND_ACCEPT_ABSENT_SLICES1_15","pre_wdata_accept_masks":[masks["pre_wdata_hs0"],masks["pre_wdata_hs1"]],"global_wdata_fifo_accept_masks":[masks["global_wdata_in_hs0"],masks["global_wdata_in_hs1"]],"global_wdata_output_accept_masks":[masks["global_wdata_out_hs0"],masks["global_wdata_out_hs1"]],"remote_mask":factors["remote"],"qualified_coverage_evaluable":True},
  "hang_root_cause":{"classification":"LONG_RUNNING_HANG_AT_SLICE2HUB_REMOTE_WDATA_OWNER_SELECTION_PENDING_SIMULTANEOUS_FACTOR","unique_functional_leaf_closed":False,"crossbar_equation":"global_wdata_fifo_in_valid[ch] selects the first asserted remote_flag MSE; hub2mse_wdata_ready[4][ch] uses remote_flag[4] independently","remaining_candidates":["simultaneous higher-priority remote_flag[0:3] steals the global wdata mux while MSE4 receives ready","MSE4 pre-wdata sticky accept and global FIFO sticky evidence occurred in disjoint epochs","observer factor event-spacing parser bug hides a required simultaneous witness"],"package_local_parser_defect":"event=FACTOR_EDGE/HEARTBEAT right-justification is not accepted by the exact parser regex"},
  "blocker_delta":{"closed":["local-vs-remote route selection: slice0 local, slices1-15 remote","slices1-15 global request FIFO input and output acceptance","local request readiness as the slice1-15 blocker"],"remaining":"B_GAP_NODE0071_REMOTE_WDATA_SHARED_PRIORITY_OWNER_CONJUNCTION_PENDING"},
  "formal_d":report["formal_d"],"e3_e4_e5":{"E3":False,"E4":False,"E5":False,"reason":"INT, no natural terminal, actual compiled identity unavailable, and 0/48 formal D"},
  "rule_confirmation":["CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001","CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001","CDA-SERVER-RESULT-GATE-CONJUNCTION-001"],
  "rule_delta_proposal":"Changed parser regex must be tested against the exact formatted logger output, including right-justified enum strings; synthetic unpadded unit records are insufficient.",
  "successor_required":True,"successor_class":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","successor_scope":"simultaneous all-MSE remote flags/source-valid/mux-owner/ready-delivery/global FIFO writes plus false-accept predicate on both channels; fix event whitespace parser"})
 write(output/"report.json",report);return report

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();r=analyze(a.output.resolve());print(json.dumps({"output":str((a.output/"report.json").resolve()),"sha256":sha(a.output/"report.json"),"errors":r["return_analysis"]["errors"],"last_proven_good":r["last_proven_good"]["boundary"],"first_divergence":r["first_divergence"]["boundary"]}));return 0 if not r["return_analysis"]["errors"] else 1
if __name__=="__main__":raise SystemExit(main())
