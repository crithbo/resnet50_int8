#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import manage_server_test_package_storage as storage
STORE=ROOT/"artifacts/operator_config_validation/r5-server-test-packages"; OUT=ROOT/"outputs/conv_node0004_v82b_return_v83b_successor"; SOURCE=OUT/"build"
FAMILY="conv_serialized_node0004"; PREVIOUS="r5_n4_hw_v82b_phase_collectfix"; CURRENT="r5_n4_hw_v83b_phase_stable_diag"; PREIMAGE="9cc063181c6dfbdd0dd5b25bfb686e516538a170973ecaa68730ab47d1f183c2"
PREVIOUS_EVIDENCE=ROOT/"outputs/conv_node0004_v82b_return_analysis/report.json"; TASK=ROOT/".agents/task_records/20260811_conv_node0004_v82b_return_v83b_phase_stable_successor.md"
ZIP_SHA="ddfb1ce5d120799d0b8d56b3b55c3a9f242ff6df3d3b975c66f7dea7bad1c319"
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def rec(p:Path)->dict:return {"path":p.relative_to(ROOT).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)}
def identity_map(index:dict,exclude:set[str]):
 return {r["package_base"]:(r.get("family"),r.get("disposition"),tuple(sorted((x.get("relative_path"),x.get("sha256"),x.get("bytes")) for x in r.get("files",[])))) for r in index.get("packages",[]) if r.get("package_base") and r["package_base"] not in exclude}
def main()->int:
 index=STORE/storage.INDEX_NAME; actual=sha(index)
 if actual!=PREIMAGE:raise SystemExit(f"storage index preimage drift expected={PREIMAGE} actual={actual}")
 before=storage.audit(STORE)
 if before.get("pending_by_family",{}).get(FAMILY)!=[PREVIOUS]:raise SystemExit("serialized pending preimage mismatch")
 others={k:v for k,v in before.get("pending_by_family",{}).items() if k!=FAMILY}; unrelated=identity_map(before,{PREVIOUS,CURRENT})
 reports={"return_analysis":ROOT/"outputs/conv_node0004_v82b_return_analysis/report.json","phase":OUT/"validation_v83b_phase.json","source_bound":OUT/"validation_v83b_source_bound.json","post_sim":OUT/"validation_v83b_post_sim.json","runner":OUT/"validation_v83b_runner.json","shared_harness":OUT/"validation_v83b_shared_harness.json","runtime_layout":OUT/"validation_v83b_runtime_layout.json","return_contract":OUT/"validation_v83b_return_contract.json","final_zip_audit":OUT/"final_zip_audit_v83b.json","task_record":TASK,"failed_v83_post_sim":ROOT/"outputs/conv_node0004_v82b_return_v83_successor/validation_v83_failed_post_sim.json"}
 for name,path in reports.items():
  if not path.is_file():raise SystemExit(f"missing release report {name}: {path}")
 final=json.loads(reports["final_zip_audit"].read_text(encoding="utf-8"))
 if final.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is not True or final.get("errors")!=[]:raise SystemExit("final audit not pass")
 for name,path in reports.items():shutil.copy2(path,SOURCE/f"{CURRENT}.{name}.json" if path.suffix==".json" else SOURCE/f"{CURRENT}.{name}.md")
 evidence=SOURCE/f"{CURRENT}.release_evidence.json"; value={"schema":"conv-node0004-v83b-release-evidence-v1","status":"PACKAGE_READY_NOT_RUN","package_id":CURRENT,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","zip":{"bytes":SOURCE.joinpath(CURRENT+".zip").stat().st_size,"sha256":sha(SOURCE/f"{CURRENT}.zip")},"return_analysis":rec(reports["return_analysis"]),"last_proven_good":"EXACT_TARGET_PARSE_BEFORE_PROJECTION_WITH_13_COMPLETE_BINARY_KNOWN_PHASE_GROUPS","first_divergence":"V82B_POSTNBA_SAMPLE_COLLIDES_WITH_NEGEDGE_AND_MIXES_SUCCESSIVE_TOKEN_EPOCHS","functional_completion_advanced":False,"first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":"0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a","final_zip_audit":rec(reports["final_zip_audit"]),"rule_feedback":"RULE_CONFIRMATION","claims":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False},"report_receipts":{k:rec(v) for k,v in reports.items()}}
 evidence.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
 result=storage.rotate(root=STORE,source_dir=SOURCE,family=FAMILY,new_base=CURRENT,previous_disposition="tested",previous_reason="formal v82b return consumed; exact phase evidence survived but old #1 sampler collided with half-cycle and source-bound candidate table missed mem_source_match=false",previous_evidence=PREVIOUS_EVIDENCE,new_reason="v83b edge-free stable-phase and complete source-bound truth-table diagnostic; all current exact local gates PASS; PACKAGE_READY_NOT_RUN",new_evidence=evidence)
 after=storage.audit(STORE); errors=[]
 if after.get("pending_by_family",{}).get(FAMILY)!=[CURRENT]:errors.append("serialized pending mismatch")
 if {k:v for k,v in after.get("pending_by_family",{}).items() if k!=FAMILY}!=others:errors.append("other pending families changed")
 if identity_map(after,{PREVIOUS,CURRENT})!=unrelated:errors.append("unrelated package records changed")
 pending=STORE/"pending"/f"{CURRENT}.zip";tested=STORE/"tested"/FAMILY/PREVIOUS/f"{PREVIOUS}.zip"
 if not pending.is_file() or sha(pending)!=ZIP_SHA:errors.append("v83b pending identity mismatch")
 if not tested.is_file() or sha(tested)!="cdd4dc08b616d29e891973267fff0dd00c380bada05c12e50e2a6d119bd7ee07":errors.append("v82b tested identity mismatch")
 report={"schema":"conv-node0004-v82b-v83b-storage-rotation-v1","pass":not errors,"errors":errors,"storage_index_preimage_sha256":actual,"previous":{"package_id":PREVIOUS,"disposition":"tested","zip":tested.relative_to(ROOT).as_posix(),"sha256":sha(tested) if tested.is_file() else None},"current":{"package_id":CURRENT,"disposition":"pending","zip":pending.relative_to(ROOT).as_posix(),"bytes":pending.stat().st_size if pending.is_file() else None,"sha256":sha(pending) if pending.is_file() else None},"other_pending_preserved":others,"unrelated_records_preserved":identity_map(after,{PREVIOUS,CURRENT})==unrelated,"storage_index":{"path":index.relative_to(ROOT).as_posix(),"bytes":index.stat().st_size,"sha256":sha(index)},"rotation_result_semantic_sha256":hashlib.sha256((json.dumps(result,sort_keys=True)+"\n").encode()).hexdigest()}
 target=OUT/"storage_rotation_v83b.json";target.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(json.dumps({"pass":not errors,"errors":errors,"index_sha256":sha(index),"pending":str(pending)}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
