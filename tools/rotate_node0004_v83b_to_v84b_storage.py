#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools import manage_server_test_package_storage as storage
STORE=ROOT/"artifacts/operator_config_validation/r5-server-test-packages";OUT=ROOT/"outputs/conv_node0004_v83b_return_v84b_successor";SOURCE=OUT/"final_build"
FAMILY="conv_serialized_node0004";PREVIOUS="r5_n4_hw_v83b_phase_stable_diag";CURRENT="r5_n4_hw_v84b_ack_inline_realtime_diag"
PREVIOUS_ZIP_SHA="ddfb1ce5d120799d0b8d56b3b55c3a9f242ff6df3d3b975c66f7dea7bad1c319";CURRENT_ZIP_SHA="0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4"
PREVIOUS_EVIDENCE=ROOT/"outputs/conv_node0004_v83b_return_analysis/report.json";TASK=ROOT/".agents/task_records/20260811_conv_node0004_v83b_return_v84b_inline_realtime_successor.md"
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def rec(path:Path)->dict:return {"path":path.relative_to(ROOT).as_posix(),"bytes":path.stat().st_size,"sha256":sha(path)}
def identity_map(index:dict,exclude:set[str])->dict:
    return {row["package_base"]:(row.get("family"),row.get("disposition"),tuple(sorted((item.get("relative_path"),item.get("sha256"),item.get("bytes")) for item in row.get("files",[])))) for row in index.get("packages",[]) if row.get("package_base") and row["package_base"] not in exclude}
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--expected-index-sha",required=True);a=ap.parse_args();index=STORE/storage.INDEX_NAME;actual=sha(index)
    if actual!=a.expected_index_sha:raise SystemExit(f"storage index preimage drift expected={a.expected_index_sha} actual={actual}")
    before=storage.audit(STORE)
    if before.get("pending_by_family",{}).get(FAMILY)!=[PREVIOUS]:raise SystemExit("serialized pending preimage mismatch")
    others={key:value for key,value in before.get("pending_by_family",{}).items() if key!=FAMILY};unrelated=identity_map(before,{PREVIOUS,CURRENT})
    reports={"return_analysis":ROOT/"outputs/conv_node0004_v83b_return_analysis/report.json","phase":OUT/"validation_v84b_phase.json","source_bound":OUT/"validation_v84b_source_bound.json","post_sim":OUT/"validation_v84b_post_sim.json","runner":OUT/"validation_v84b_runner.json","shared_harness":OUT/"validation_v84b_shared_harness.json","runtime_layout":OUT/"validation_v84b_runtime_layout.json","return_contract":OUT/"validation_v84b_return_contract.json","final_zip_audit":OUT/"final_zip_audit_v84b.json","release_report":OUT/"release_report.json","task_record":TASK,"failed_exact_v84_post_sim":ROOT/"outputs/conv_node0004_v83b_return_v84_successor/validation_v84_post_sim.json"}
    for name,path in reports.items():
        if not path.is_file():raise SystemExit(f"missing release report {name}: {path}")
    audit=json.loads(reports["final_zip_audit"].read_text(encoding="utf-8"))
    if audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is not True or audit.get("errors")!=[]:raise SystemExit("final audit not pass")
    for name,path in reports.items():
        suffix="v84fail" if name=="failed_exact_v84_post_sim" else name
        shutil.copy2(path,SOURCE/f"{CURRENT}.{suffix}.json" if path.suffix==".json" else SOURCE/f"{CURRENT}.{suffix}.md")
    evidence=SOURCE/f"{CURRENT}.release_evidence.json";value={"schema":"conv-node0004-v84b-release-evidence-v1","status":"PACKAGE_READY_NOT_RUN","package_id":CURRENT,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","zip":{"bytes":SOURCE.joinpath(CURRENT+".zip").stat().st_size,"sha256":sha(SOURCE/f"{CURRENT}.zip")},"return_analysis":rec(reports["return_analysis"]),"last_proven_good":"COMPLETE_SOURCE_BOUND_TRUTH_TABLE_UNIQUE_MATCH_AND_13_EXACT_KNOWN_PHASE_GROUPS_PERSISTED","first_divergence":"V83B_STABLE_PHASE_PARSER_REJECTS_SUB_NS_SCHEDULE_DUE_TO_INTEGER_TIME_QUANTIZATION","functional_completion_advanced":False,"first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":"0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a","final_zip_audit":rec(reports["final_zip_audit"]),"rule_feedback":"RULE_CONFIRMATION","failed_exact_v84":{"bytes":5264421,"sha256":"7e7ba538ffd66f3dfbd5d36d78868d3550708eaecd3025707a4ac3f3797424f1","disposition":"NOT_RELEASED_ONE_FINAL_ZIP_FAILURE_RETAINED"},"claims":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False},"report_receipts":{name:rec(path) for name,path in reports.items()}};evidence.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    result=storage.rotate(root=STORE,source_dir=SOURCE,family=FAMILY,new_base=CURRENT,previous_disposition="tested",previous_reason="formal v83b return consumed; exact source-bound table closed but integer $time could not certify sub-ns phase order",previous_evidence=PREVIOUS_EVIDENCE,new_reason="v84b exact-instance inline expected/xor plus $realtime diagnostic; all current exact local gates PASS; PACKAGE_READY_NOT_RUN",new_evidence=evidence)
    after=storage.audit(STORE);errors=[]
    if after.get("pending_by_family",{}).get(FAMILY)!=[CURRENT]:errors.append("serialized pending mismatch")
    if {key:value for key,value in after.get("pending_by_family",{}).items() if key!=FAMILY}!=others:errors.append("other pending families changed")
    if identity_map(after,{PREVIOUS,CURRENT})!=unrelated:errors.append("unrelated package records changed")
    pending=STORE/"pending"/f"{CURRENT}.zip";tested=STORE/"tested"/FAMILY/PREVIOUS/f"{PREVIOUS}.zip"
    if not pending.is_file() or sha(pending)!=CURRENT_ZIP_SHA:errors.append("v84b pending identity mismatch")
    if not tested.is_file() or sha(tested)!=PREVIOUS_ZIP_SHA:errors.append("v83b tested identity mismatch")
    report={"schema":"conv-node0004-v83b-v84b-storage-rotation-v1","pass":not errors,"errors":errors,"storage_index_preimage_sha256":actual,"previous":{"package_id":PREVIOUS,"disposition":"tested","zip":tested.relative_to(ROOT).as_posix(),"sha256":sha(tested) if tested.is_file() else None},"current":{"package_id":CURRENT,"disposition":"pending","zip":pending.relative_to(ROOT).as_posix(),"bytes":pending.stat().st_size if pending.is_file() else None,"sha256":sha(pending) if pending.is_file() else None},"other_pending_preserved":others,"unrelated_records_preserved":identity_map(after,{PREVIOUS,CURRENT})==unrelated,"storage_index":{"path":index.relative_to(ROOT).as_posix(),"bytes":index.stat().st_size,"sha256":sha(index)},"rotation_result_semantic_sha256":hashlib.sha256((json.dumps(result,sort_keys=True)+"\n").encode()).hexdigest()};target=OUT/"storage_rotation_v84b.json";target.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(json.dumps({"pass":not errors,"errors":errors,"index_sha256":sha(index),"pending":str(pending)}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
