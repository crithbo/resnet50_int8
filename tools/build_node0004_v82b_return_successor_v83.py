#!/usr/bin/env python3
"""Build the single serialized-Conv v83 stable-phase diagnostic successor."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import tools.build_node0004_v81_return_successor_v82 as prior

SOURCE="r5_n4_hw_v82b_phase_collectfix"; INSTALL="r5_n4_hw_v83b_phase_stable_diag"
SOURCE_SHA="cdd4dc08b616d29e891973267fff0dd00c380bada05c12e50e2a6d119bd7ee07"
RETURN_SHA="f328f1cc6f634310466aca206148297825db3231beaf7102ff5b92516eff3638"
EXECUTION="r1786417609012229751_870730"
SOURCE_ZIP=ROOT/"artifacts/operator_config_validation/r5-server-test-packages/pending"/f"{SOURCE}.zip"
ANALYSIS=ROOT/"outputs/conv_node0004_v82b_return_analysis/report.json"
OUT=ROOT/"outputs/conv_node0004_v82b_return_v83b_successor"
GENERATOR=ROOT/"tools/generate_server_source_bound_observer.py"
PRIOR_PASS="0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a"

class BuildError(RuntimeError): pass
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p:Path,v:object)->None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def run(argv:list[str])->None:
    r=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,check=False)
    if r.returncode: raise BuildError(f"command failed {r.returncode}: {' '.join(argv)}\n{r.stdout}\n{r.stderr}")

def configure()->None:
    prior.SOURCE=SOURCE; prior.INSTALL=INSTALL; prior.SOURCE_SHA=SOURCE_SHA; prior.RETURN_SHA=RETURN_SHA
    prior.SOURCE_ZIP=SOURCE_ZIP; prior.ANALYSIS=ANALYSIS; prior.OUT=OUT; prior.configure_old()

def patch_phase(package:Path)->None:
    shutil.copy2(ROOT/"tools/node0004_v83_buffer_ack_phase_observer.svh",package/"tb_probe/buffer_ack_phase_observer.svh")
    shutil.copy2(ROOT/"tools/node0004_v83_buffer_ack_phase_parser.py",package/"package_tools/buffer_ack_phase_parser.py")
    shutil.copy2(ROOT/"tools/node0004_v83_post_sim_plugin.py",package/"package_tools/node0004_v83_post_sim_plugin.py")
    widths={"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7}
    fixture=[]
    for index,phase in enumerate(("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS")):
      fields={"wr":"1","full":"0","all":"1","valid":"3","same":"3","gotten":"0" if phase=="PRE" else "3","keep":"3","bpmask":"3","bp":"3","mode":"2","row":"1","col":"1f","rowtag":"7f","coltag":"7f"}; payload=0
      for name,width in widths.items(): payload=(payload<<width)|int(fields[name],16)
      fixture.append(f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={prior.TARGET} time={(1000,2000,2001,2250,2750)[index]} mask=1 payload={payload:x} payload_known=1 payload_width=38 seq=0 phase={phase} "+" ".join(f"{name}={fields[name]}" for name in widths))
    fixture_path=package/"diagnostics/partial_exit_live/buffer_ack_phase_live.log"; fixture_path.parent.mkdir(parents=True,exist_ok=True); fixture_path.write_text("\n".join(fixture)+"\n",encoding="utf-8",newline="\n")
    request_path=package/"contracts/server_post_sim_return_request.json"; request=json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"]=INSTALL; request["plugins"][0]["argv"]=["python3","{package_root}/package_tools/node0004_v83_post_sim_plugin.py","--package-root","{package_root}","--attempt-root","{attempt_root}","--phase-live-log","{attempt_root}/c0/sim.log","--phase-output","{attempt_root}/c0/buffer_ack_phase_decision.json"]
    write(request_path,request)
    contract_path=package/"contracts/server_post_sim_return_contract.json"; contract=json.loads(contract_path.read_text(encoding="utf-8"))
    contract["package_id"]=INSTALL; contract["request_sha256"]=sha(request_path); contract["claim_boundary"]="Stable phase evidence is parsed and persisted before bounded source-bound projection; core return remains independently publishable."
    write(contract_path,contract)
    semantics={"schema":"conv-node0004-v83-buffer-ack-stable-phase-semantics-v1","package_id":INSTALL,
      "boundary_id":"buf_ack_phase_target","expected_instance":prior.TARGET,"near_miss_instance":prior.NEAR_TARGET,
      "record_grouping_key":["boundary_id","instance","seq"],"payload":{"width_bits":38,"required_binary_known":True,"unknown_disposition":"EVIDENCE_INCOMPLETE"},
      "phases":["PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS"],
      "sample_schedule":{"pre":"negedge+250ps","edge":"posedge","delta":"posedge+1ps","quarter":"posedge+250ps","late":"posedge+750ps"},
      "observer_sha256":sha(package/"tb_probe/buffer_ack_phase_observer.svh"),"parser_sha256":sha(package/"package_tools/buffer_ack_phase_parser.py"),
      "post_sim_plugin_sha256":sha(package/"package_tools/node0004_v83_post_sim_plugin.py"),"collector_order":"STABLE_PHASE_PARSE_AND_PERSIST_BEFORE_BOUNDED_SOURCE_BOUND_PROJECTION"}
    canonical=json.dumps(semantics,sort_keys=True,separators=(",",":")).encode(); semantics["diagnostic_semantics_sha256"]=hashlib.sha256(canonical).hexdigest()
    write(package/"diagnostics/buffer_ack_phase_semantics_contract.json",semantics)

def complete_source_bound_truth_table(package:Path)->None:
    plan_path=package/"diagnostics/source_bound_probe_plan.json"; catalog_path=package/"diagnostics/source_bound_probe_catalog.json"
    plan=json.loads(plan_path.read_text(encoding="utf-8")); existing={c["candidate_id"] for c in plan["candidates"]}
    for mem_terminal in (False,True):
      for buf_terminal in (False,True):
        cid=f"mem_match_absent_memterm_{int(mem_terminal)}_bufterm_{int(buf_terminal)}"
        if cid not in existing: plan["candidates"].append({"candidate_id":cid,"root_cause_class":"MEMORY_SOURCE_MATCH_ABSENT_REQUIRES_STABLE_PHASE_LEDGER","signature":{"buf_ack_witness_count_nonzero":True,"buf_terminal_seen":buf_terminal,"mem_source_match_count_nonzero":False,"mem_terminal_seen":mem_terminal}})
    plan["package_id"]=INSTALL
    plan["claim_boundary"]="Complete eight-row terminal/source-match truth table; exact generated probe identity and payload contracts unchanged. Stable-phase diagnostic adjudicates the remaining memory-source-match-absent class."
    write(plan_path,plan)
    with tempfile.TemporaryDirectory(prefix="n4v83-sourcebound-") as raw:
      gen=Path(raw)/"generated"; report=Path(raw)/"report.json"; cheap=Path(raw)/"cheap.json"
      run([sys.executable,str(GENERATOR),"materialize","--catalog",str(catalog_path),"--plan",str(plan_path),"--output-dir",str(gen),"--report",str(report),"--cheap-check-output",str(cheap)])
      shutil.copy2(gen/"source_bound_causal_observer.svh",package/"tb_probe/source_bound_causal_observer.svh")
      shutil.copy2(gen/"source_bound_causal_parser.py",package/"package_tools/source_bound_causal_parser.py")
      shutil.copy2(gen/"source_bound_probe_binding.json",package/"diagnostics/source_bound_probe_binding.json")
      rr=json.loads(report.read_text(encoding="utf-8")); rr["catalog"]["path"]="diagnostics/source_bound_probe_catalog.json"; rr["plan"]["path"]="diagnostics/source_bound_probe_plan.json"
      write(package/"diagnostics/source_bound_observer_generation_report.json",rr); write(package/"diagnostics/source_bound_observer_generation.json",json.loads(cheap.read_text(encoding="utf-8")))

def build_directory(out:Path)->Path:
    configure(); out.mkdir(parents=True,exist_ok=True); package=prior.old.extract_source(out); prior.old.rebase_identity(package)
    patch_phase(package); complete_source_bound_truth_table(package); prior.old.base.update_path_budget(package)
    manifest_path=package/"package_manifest.json"; manifest=json.loads(manifest_path.read_text(encoding="utf-8")); manifest["install_name"]=INSTALL; manifest["status"]="PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"]={"epoch_id":"20260811-exact-instance-payload-semantic-fingerprint-v2","notification_acknowledged":True,"first_fresh_after_change":False,"bound_package_id":INSTALL,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"upload_hold_until_final_audit_pass":True}
    manifest["v82b_return_adjudication"]={"formal_return_sha256":RETURN_SHA,"execution_id":EXECUTION,"return_analysis_sha256":sha(ANALYSIS),"last_proven_good":"EXACT_TARGET_PARSE_BEFORE_PROJECTION_WITH_13_COMPLETE_BINARY_KNOWN_PHASE_GROUPS","first_divergence":"V82B_POSTNBA_SAMPLE_COLLIDES_WITH_NEGEDGE_AND_MIXES_SUCCESSIVE_TOKEN_EPOCHS","root_leaf_status":"PACKAGE_LOCAL_PHASE_SAMPLER_EDGE_COLLISION_AND_INCOMPLETE_SOURCE_BOUND_TRUTH_TABLE"}
    manifest["buffer_ack_phase_diagnostic"]={"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","target_instance":prior.TARGET,"payload_width_bits":38,"required_binary_known":True,"sample_phases":["PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS"],"edge_free_post_samples":True,"natural_terminal_or_formal_d_claim":False}
    manifest["rule_change_ack"]={"epoch_id":"20260811-exact-instance-payload-semantic-fingerprint-v2","first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"rule_ids":["CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001","CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001","CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001"],"upload_hold_until":"FINAL_ZIP_RULE_SELF_AUDIT_PASS"}
    write(package/"diagnostics/rule_change_ack.json",{"schema":"conv-node0004-v83-rule-change-ack-v1","package_id":INSTALL,**manifest["rule_change_ack"]})
    write(package/"provenance/v82b_return_to_v83_phase_stable_diag.json",{"schema":"conv-node0004-v82b-return-to-v83-v1","source_package_zip_sha256":SOURCE_SHA,"formal_return_sha256":RETURN_SHA,"return_analysis_sha256":sha(ANALYSIS),"changed_surface":["fresh identity","strictly edge-free stable phase sampler","complete source-bound candidate truth table"],"frozen":["numeric/W3/qparams/tail/workload/config/golden","timeout/backpressure","functional RTL/ISA/hardware/active ndp-sim"],"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False})
    prior.old.base.refresh_receipts(manifest); manifest.setdefault("active_receipts",{})["source_bound_generator_sha256"]=sha(GENERATOR)
    rules=manifest["active_receipts"].setdefault("rules",[])
    for rid in manifest["rule_change_ack"]["rule_ids"]:
      if rid not in rules: rules.append(rid)
    write(manifest_path,manifest); manifest["files"]=prior.old.base.package_records(package); write(manifest_path,manifest); manifest["files"]=prior.old.base.package_records(package); write(manifest_path,manifest)
    return package

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--output-root",type=Path,default=OUT/"build"); a=ap.parse_args(); out=a.output_root.resolve()
    package=build_directory(out)
    with tempfile.TemporaryDirectory(prefix="n4v83-repeat-") as raw:
      repeat=build_directory(Path(raw));
      if prior.old.base.package_records(package)!=prior.old.base.package_records(repeat): raise BuildError("deterministic directory rebuild differs")
    archive=out/f"{INSTALL}.zip"; prior.old.base.deterministic_zip(package,archive); digest=sha(archive); sidecar=out/f"{INSTALL}.zip.sha256"; sidecar.write_text(f"{digest}  {archive.name}\n",encoding="ascii",newline="\n")
    report={"schema":"conv-node0004-v83-build-v1","status":"PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT","package_id":INSTALL,"zip":str(archive),"zip_bytes":archive.stat().st_size,"zip_sha256":digest,"sidecar":str(sidecar),"deterministic_directory_rebuild_equal":True,"first_fresh_after_change":False,"prior_first_fresh_pass_receipt_sha256":PRIOR_PASS,"cheap_aggregate_invocations":1,"final_zip_count":1,"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False}
    write(out/f"{INSTALL}.build.json",report); print(json.dumps(report,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
