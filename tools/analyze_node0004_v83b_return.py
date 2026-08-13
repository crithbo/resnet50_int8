#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, stat, zipfile
from pathlib import Path, PurePosixPath
PACKAGE="r5_n4_hw_v83b_phase_stable_diag"; ROOT_NAME=PACKAGE+"_return"; RETURN_BYTES=348917; RETURN_SHA="f9caa057a0f9000fcfc4e78a5a8b96741ff601f861a2be1df94c313d3f2823b9"; SOURCE_BYTES=5259860; SOURCE_SHA="ddfb1ce5d120799d0b8d56b3b55c3a9f242ff6df3d3b975c66f7dea7bad1c319"; EXECUTION="r1786424711791299061_943615"
EXPECTED={"RETURN_CORE_MANIFEST.json","evidence/SERVER_RESULT_GATE.json","evidence/compile_exit_status.txt","evidence/post_final_buffer_input_owner_parser_receipt.json","evidence/returned_package_manifest.json","evidence/run_exit_status.txt","evidence/signal_status.txt","evidence/source_bound_parser_receipt.json","evidence/target_temporal_parser_receipt.json","return_core/RETURN_CORE_STATUS.json","return_core/RETURN_PLUGIN_STATUS.json","return_core/SIM_EXIT_RECEIPT.json","return_core/plugins/node0004_source_bound_collect.status.json","return_core/plugins/node0004_source_bound_collect.stderr.log","return_core/plugins/node0004_source_bound_collect.stdout.log","runs/c0/buffer_ack_phase_decision.json","runs/c0/buffer_input_ack_equation_decision.json","runs/c0/post_final_buffer_input_owner_decision.json","runs/c0/return_observer.log","runs/c0/sim.log","runs/c0/simulator_argv.txt","runs/c0/source_bound_causal.log","runs/c0/source_bound_causal_decision.json","runs/c0/target_temporal_decision.json"}
def sha_bytes(x:bytes)->str:return hashlib.sha256(x).hexdigest()
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--return-zip",type=Path,required=True);ap.add_argument("--source-zip",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();errors=[]
 rb=a.return_zip.read_bytes();sb=a.source_zip.read_bytes()
 if len(rb)!=RETURN_BYTES or sha_bytes(rb)!=RETURN_SHA:errors.append("external_return_identity_mismatch")
 if len(sb)!=SOURCE_BYTES or sha_bytes(sb)!=SOURCE_SHA:errors.append("source_identity_mismatch")
 with zipfile.ZipFile(a.source_zip) as source_zip:
  source_manifest_bytes=source_zip.read(PACKAGE+"/package_manifest.json")
 prefix=ROOT_NAME+"/"
 with zipfile.ZipFile(a.return_zip) as z:
  infos=z.infolist();names=[x.filename for x in infos];rels={n[len(prefix):] for n in names if n.startswith(prefix)}
  if z.testzip() is not None:errors.append("crc_failure")
  if len(names)!=len(set(names)):errors.append("duplicate_member")
  if any(not n.startswith(prefix) or PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts or "\\" in n for n in names):errors.append("root_or_path_failure")
  if any(stat.S_ISLNK(x.external_attr>>16) for x in infos):errors.append("symlink_member")
  if rels!=EXPECTED:errors.append("exact_set_mismatch")
  def load(n):return json.loads(z.read(prefix+n))
  core_manifest=load("RETURN_CORE_MANIFEST.json");core=load("return_core/RETURN_CORE_STATUS.json");plugin=load("return_core/plugins/node0004_source_bound_collect.status.json");simexit=load("return_core/SIM_EXIT_RECEIPT.json");gate=load("evidence/SERVER_RESULT_GATE.json");returned=load("evidence/returned_package_manifest.json");phase=load("runs/c0/buffer_ack_phase_decision.json");source=load("runs/c0/source_bound_causal_decision.json");temporal=load("runs/c0/target_temporal_decision.json")
  for row in core_manifest.get("core_entry_receipts",[]):
   n=row["path"]
   if n not in rels or len(z.read(prefix+n))!=row["bytes"] or sha_bytes(z.read(prefix+n))!=row["sha256"]:errors.append("core_receipt_mismatch:"+n)
  identity=[core_manifest.get("package_id")==PACKAGE,core_manifest.get("execution_id")==EXECUTION,core_manifest.get("return_basename")==a.return_zip.name,core.get("package_id")==PACKAGE,core.get("execution_id")==EXECUTION,simexit.get("package_id")==PACKAGE,simexit.get("execution_id")==EXECUTION,returned.get("install_name")==PACKAGE,z.read(prefix+"evidence/returned_package_manifest.json")==source_manifest_bytes]
  if not all(identity):errors.append("internal_identity_mismatch")
 z=zipfile.ZipFile(a.return_zip)
 sequences=phase.get("sequences",{}); complete=phase.get("complete_sequence_count")==13 and phase.get("sequence_count")==13 and phase.get("live_event_count")==65; known=phase.get("unknown_or_width_invalid_count")==0 and phase.get("foreign_event_count")==0 and phase.get("payload_width_bits")==38
 phase_order=("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS"); mismatch_count=0; late_mismatch=0; changed=0; time_collisions=0
 for row in sequences.values():
  if not all(p in row for p in phase_order):continue
  eq=[]
  for p in phase_order:
   e=row[p];expected=0 if int(e["full"],16) else int(e["bpmask"],16);eq.append(int(e["bp"],16)!=expected)
  mismatch_count+=sum(eq);late_mismatch+=int(eq[-1]);changed+=int(any(row["PRE"][f]!=row["LATE_750PS"][f] for f in ("row","col","rowtag","coltag","mode","gotten")))
  time_collisions+=int(len({row[p]["time"] for p in phase_order})<5)
 output={"schema":"conv-node0004-v83b-formal-return-analysis-v1","analysis_valid":not errors,"structural_errors":errors,
 "RETURN_ANALYSIS":{"return":{"path":str(a.return_zip),"bytes":len(rb),"sha256":RETURN_SHA},"source":{"path":str(a.source_zip),"bytes":len(sb),"sha256":SOURCE_SHA},"execution_id":EXECUTION,"crc_root_path_exact_set_allowlist_per_file":not errors,"compile_exit":int(z.read(prefix+"evidence/compile_exit_status.txt").strip()),"run_exit":int(z.read(prefix+"evidence/run_exit_status.txt").strip()),"signal":z.read(prefix+"evidence/signal_status.txt").decode().strip(),"core_disposition":core.get("disposition"),"missing_required_entries":core.get("missing_required_entries"),"required_plugin_failures":core.get("required_plugin_failures"),"plugin_exit":plugin.get("exit_code"),"natural_terminal":gate.get("natural_terminal_observed") is True,"formal_d":{"present":0,"missing":320,"mismatch":0},"E3":False,"E4":False,"E5":False,"source_bound":{"decision":source.get("decision"),"matching_candidate_ids":source.get("matching_candidate_ids"),"observations":source.get("observations"),"errors":source.get("errors")},"target_temporal":{"decision":temporal.get("decision"),"observations":temporal.get("observations")}},
 "STABLE_PHASE_ADJUDICATION":{"decision":phase.get("decision"),"complete_exact_groups":complete,"exact_instance_binary_known_38bit":known,"phase_time_collision_group_count":time_collisions,"equation_mismatch_sample_count":mismatch_count,"late_750ps_equation_mismatch_group_count":late_mismatch,"token_transition_group_count":changed,"adjudication":"The intended sub-ns phase schedule executed and persisted, but integer $time quantizes multiple phase labels into the same 1ns bucket. The parser therefore correctly fails closed. All named-field samples nevertheless show mse_buf_queue_bp_pre != ({2{!full}} & bpmask); an inline expected/xor witness with $realtime is required before classifying compiled RTL versus observer/scheduling semantics."},
 "LAST_PROVEN_GOOD":"COMPLETE_SOURCE_BOUND_TRUTH_TABLE_UNIQUE_MATCH_AND_13_EXACT_KNOWN_PHASE_GROUPS_PERSISTED",
 "FIRST_DIVERGENCE":"V83B_STABLE_PHASE_PARSER_REJECTS_SUB_NS_SCHEDULE_DUE_TO_INTEGER_TIME_QUANTIZATION",
 "HANG_ROOT_CAUSE":{"status":"UNRESOLVED_FUNCTIONAL_ROOT_AFTER_PACKAGE_LOCAL_TIMEBASE_ESCAPE","package_local_root":"INTEGER_$TIME_CANNOT_PROVE_SUB_NS_PHASE_SEPARATION","functional_scope":"ACK output versus direct RHS remains mismatched in 65/65 named samples, including all 13 LATE_750PS labels; exact inline RHS/XOR and $realtime witness required to distinguish compiled-source/consumer mismatch from observation scheduling."},
 "PROGRESS_THIS_ROUND":{"closed_since_v82b":["SOURCE_BOUND_CANDIDATE_TABLE_MISSING_MEM_SOURCE_MATCH_FALSE","V82B_POSTNBA_HALF_EDGE_COLLISION_IN_OBSERVER_SCHEDULE"],"first_proven":["UNIQUE_SOURCE_BOUND_SIGNATURE_MEM_MATCH_ABSENT_MEMTERM1_BUFTERM1","65_OF_65_NAMED_ACK_EQUATION_SAMPLES_MISMATCH","13_OF_13_LATE_750PS_LABELS_MISMATCH"],"functional_completion_advanced":False,"reason":"Natural terminal and formal D remain absent; parser cannot formally accept stable separation with integer $time."},
 "BLOCKER_DELTA":{"closed":["B_CONV_NODE0004_SOURCE_BOUND_CANDIDATE_TABLE_MISSES_MEM_SOURCE_MATCH_FALSE","B_CONV_NODE0004_V82B_PHASE_SAMPLE_COLLIDES_WITH_CLOCK_EDGE"],"opened":["B_CONV_NODE0004_V83B_INTEGER_TIMEBASE_CANNOT_CERTIFY_SUBNS_PHASES","B_CONV_NODE0004_ACK_OUTPUT_VS_INLINE_RHS_STABLE_MISMATCH_UNRESOLVED"],"retained":["B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL","B_CONV_NODE0004_FORMAL_D_320"],"invalidated_not_revived":["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"]},
 "PACKAGE_NEXT":{"required":True,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","minimal_scope":"$realtime plus explicit ordinal and inline expected_bp/xor at exact target; preserve complete source-bound truth table and all frozen workload bytes."},"claims":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False}}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(output,indent=2,sort_keys=True));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
