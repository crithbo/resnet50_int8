#!/usr/bin/env python3
"""Build the single serialized-Conv v84 inline-RHS/realtime diagnostic successor."""
from __future__ import annotations
import argparse, hashlib, json, shutil, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.build_node0004_v82b_return_successor_v83 as prior
SOURCE="r5_n4_hw_v83b_phase_stable_diag";INSTALL="r5_n4_hw_v84_ack_inline_realtime_diag"
SOURCE_SHA="ddfb1ce5d120799d0b8d56b3b55c3a9f242ff6df3d3b975c66f7dea7bad1c319"
RETURN_SHA="f9caa057a0f9000fcfc4e78a5a8b96741ff601f861a2be1df94c313d3f2823b9";EXECUTION="r1786424711791299061_943615"
SOURCE_ZIP=ROOT/"artifacts/operator_config_validation/r5-server-test-packages/pending"/f"{SOURCE}.zip"
ANALYSIS=ROOT/"outputs/conv_node0004_v83b_return_analysis/report.json";OUT=ROOT/"outputs/conv_node0004_v83b_return_v84_successor"
PRIOR_PASS=prior.PRIOR_PASS

class BuildError(RuntimeError):pass
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path:Path,value:object)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")

def configure()->None:
    prior.SOURCE=SOURCE;prior.INSTALL=INSTALL;prior.SOURCE_SHA=SOURCE_SHA;prior.RETURN_SHA=RETURN_SHA;prior.EXECUTION=EXECUTION
    prior.SOURCE_ZIP=SOURCE_ZIP;prior.ANALYSIS=ANALYSIS;prior.OUT=OUT;prior.configure()

def event(seq:int,phase:str,ord_value:int,rt:str)->str:
    fields={"wr":"1","full":"0","all":"1","valid":"3","same":"3","gotten":"0" if phase=="PRE" else "3","keep":"3","bpmask":"3","bp":"3","mode":"2","row":"1","col":"1f","rowtag":"7f","coltag":"7f","expected":"3","xor":"0"};widths={"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7,"expected":2,"xor":2};payload=0
    for name,width in widths.items():payload=(payload<<width)|int(fields[name],16)
    return f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_inline_realtime_target instance={prior.prior.TARGET} time={rt.split('.')[0]} rt={rt} mask=1 payload={payload:x} payload_known=1 payload_width=42 seq={seq} phase={phase} ord={ord_value} "+" ".join(f"{name}={fields[name]}" for name in widths)

def patch_phase(package:Path)->None:
    shutil.copy2(ROOT/"tools/node0004_v84_buffer_ack_inline_realtime_observer.svh",package/"tb_probe/buffer_ack_phase_observer.svh")
    shutil.copy2(ROOT/"tools/node0004_v84_buffer_ack_inline_realtime_parser.py",package/"package_tools/buffer_ack_phase_parser.py")
    shutil.copy2(ROOT/"tools/node0004_v84_post_sim_plugin.py",package/"package_tools/node0004_v84_post_sim_plugin.py")
    phases=(("PRE",0,"1000.250"),("EDGE",1,"1001.000"),("DELTA_1PS",2,"1001.001"),("QUARTER_250PS",3,"1001.250"),("LATE_750PS",4,"1001.750"))
    fixture=package/"diagnostics/partial_exit_live/buffer_ack_phase_live.log";fixture.write_text("\n".join(event(0,*row) for row in phases)+"\n",encoding="utf-8",newline="\n")
    request_path=package/"contracts/server_post_sim_return_request.json";request=json.loads(request_path.read_text(encoding="utf-8"));request["package_id"]=INSTALL
    request["plugins"][0]["argv"]=["python3","{package_root}/package_tools/node0004_v84_post_sim_plugin.py","--package-root","{package_root}","--attempt-root","{attempt_root}","--phase-live-log","{attempt_root}/c0/sim.log","--phase-output","{attempt_root}/c0/buffer_ack_phase_decision.json"]
    write(request_path,request)
    contract_path=package/"contracts/server_post_sim_return_contract.json";contract=json.loads(contract_path.read_text(encoding="utf-8"));contract["package_id"]=INSTALL;contract["request_sha256"]=sha(request_path);contract["claim_boundary"]="Inline expected/xor plus strict $realtime evidence is persisted before bounded source-bound projection; core return remains independently publishable.";write(contract_path,contract)
    semantics={"schema":"conv-node0004-v84-buffer-ack-inline-realtime-semantics-v1","package_id":INSTALL,"boundary_id":"buf_ack_inline_realtime_target","expected_instance":prior.prior.TARGET,"near_miss_instance":prior.prior.NEAR_TARGET,"record_grouping_key":["boundary_id","instance","seq"],"payload":{"width_bits":42,"required_binary_known":True,"unknown_disposition":"EVIDENCE_INCOMPLETE","inline_fields":["expected","xor"]},"phases":[x[0] for x in phases],"phase_ordinals":{x[0]:x[1] for x in phases},"sample_schedule":{"pre":"negedge+250ps","edge":"posedge","delta":"posedge+1ps","quarter":"posedge+250ps","late":"posedge+750ps","ordering_basis":"$realtime"},"observer_sha256":sha(package/"tb_probe/buffer_ack_phase_observer.svh"),"parser_sha256":sha(package/"package_tools/buffer_ack_phase_parser.py"),"post_sim_plugin_sha256":sha(package/"package_tools/node0004_v84_post_sim_plugin.py"),"collector_order":"INLINE_REALTIME_PARSE_AND_PERSIST_BEFORE_BOUNDED_SOURCE_BOUND_PROJECTION"}
    semantics["diagnostic_semantics_sha256"]=hashlib.sha256(json.dumps(semantics,sort_keys=True,separators=(",",":")).encode()).hexdigest();write(package/"diagnostics/buffer_ack_phase_semantics_contract.json",semantics)

def build_directory(out:Path)->Path:
    configure();out.mkdir(parents=True,exist_ok=True);package=prior.prior.old.extract_source(out);prior.prior.old.rebase_identity(package)
    patch_phase(package);prior.complete_source_bound_truth_table(package);prior.prior.old.base.update_path_budget(package)
    manifest_path=package/"package_manifest.json";manifest=json.loads(manifest_path.read_text(encoding="utf-8"));manifest["install_name"]=INSTALL;manifest["status"]="PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"]={"epoch_id":"20260811-exact-instance-payload-semantic-fingerprint-v2","notification_acknowledged":True,"first_fresh_after_change":False,"bound_package_id":INSTALL,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"upload_hold_until_final_audit_pass":True}
    manifest["v83b_return_adjudication"]={"formal_return_sha256":RETURN_SHA,"execution_id":EXECUTION,"return_analysis_sha256":sha(ANALYSIS),"last_proven_good":"COMPLETE_SOURCE_BOUND_TRUTH_TABLE_UNIQUE_MATCH_AND_13_EXACT_KNOWN_PHASE_GROUPS_PERSISTED","first_divergence":"V83B_STABLE_PHASE_PARSER_REJECTS_SUB_NS_SCHEDULE_DUE_TO_INTEGER_TIME_QUANTIZATION","root_leaf_status":"PACKAGE_LOCAL_INTEGER_TIMEBASE_ESCAPE_WITH_FUNCTIONAL_ACK_MISMATCH_UNRESOLVED"}
    manifest["buffer_ack_phase_diagnostic"]={"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","target_instance":prior.prior.TARGET,"payload_width_bits":42,"required_binary_known":True,"sample_phases":[x for x in ("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS")],"strict_realtime_order":True,"inline_expected_xor":True,"natural_terminal_or_formal_d_claim":False}
    manifest["rule_change_ack"]={"epoch_id":"20260811-exact-instance-payload-semantic-fingerprint-v2","first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"upload_hold_until":"FINAL_ZIP_RULE_SELF_AUDIT_PASS"}
    write(package/"diagnostics/rule_change_ack.json",{"schema":"conv-node0004-v84-rule-change-ack-v1","package_id":INSTALL,**manifest["rule_change_ack"]})
    write(package/"provenance/v83b_return_to_v84_ack_inline_realtime.json",{"schema":"conv-node0004-v83b-return-to-v84-v1","source_package_zip_sha256":SOURCE_SHA,"formal_return_sha256":RETURN_SHA,"return_analysis_sha256":sha(ANALYSIS),"changed_surface":["fresh identity","$realtime and explicit phase ordinal","inline expected_bp/xor payload","post-sim phase plugin"],"frozen":["numeric/W3/qparams/tail/workload/config/golden","timeout/backpressure","functional RTL/ISA/hardware/active ndp-sim"],"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False})
    prior.prior.old.base.refresh_receipts(manifest);manifest.setdefault("active_receipts",{})["source_bound_generator_sha256"]=sha(ROOT/"tools/generate_server_source_bound_observer.py")
    write(manifest_path,manifest);manifest["files"]=prior.prior.old.base.package_records(package);write(manifest_path,manifest);manifest["files"]=prior.prior.old.base.package_records(package);write(manifest_path,manifest);return package

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--output-root",type=Path,default=OUT/"build");a=ap.parse_args();out=a.output_root.resolve();package=build_directory(out)
    with tempfile.TemporaryDirectory(prefix="n4v84-repeat-") as raw:
        repeat=build_directory(Path(raw))
        if prior.prior.old.base.package_records(package)!=prior.prior.old.base.package_records(repeat):raise BuildError("deterministic directory rebuild differs")
    archive=out/f"{INSTALL}.zip";prior.prior.old.base.deterministic_zip(package,archive);digest=sha(archive);sidecar=out/f"{INSTALL}.zip.sha256";sidecar.write_text(f"{digest}  {archive.name}\n",encoding="ascii",newline="\n")
    report={"schema":"conv-node0004-v84-build-v1","status":"PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT","package_id":INSTALL,"zip":str(archive),"zip_bytes":archive.stat().st_size,"zip_sha256":digest,"sidecar":str(sidecar),"deterministic_directory_rebuild_equal":True,"first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"cheap_aggregate_invocations":1,"final_zip_count":1,"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False};write(out/f"{INSTALL}.build.json",report);print(json.dumps(report,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
