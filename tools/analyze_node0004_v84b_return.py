#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, stat, zipfile
from pathlib import Path, PurePosixPath

PACKAGE="r5_n4_hw_v84b_ack_inline_realtime_diag";EXECUTION="r1786436071113419680_1052700"
RETURN_BYTES=41307;RETURN_SHA="43f1a99877de60e40b273aa05f8d5a57e8159dd4a5229809e0f09a620b544a8d"
SOURCE_BYTES=5264811;SOURCE_SHA="0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4"
EXPECTED={"RETURN_CORE_MANIFEST.json","evidence/compile_exit_status.txt","evidence/returned_package_manifest.json","evidence/run_exit_status.txt","evidence/signal_status.txt","return_core/RETURN_CORE_STATUS.json","return_core/RETURN_PLUGIN_STATUS.json","return_core/SIM_EXIT_RECEIPT.json","return_core/plugins/node0004_source_bound_collect.status.json","return_core/plugins/node0004_source_bound_collect.stderr.log","return_core/plugins/node0004_source_bound_collect.stdout.log"}
def sha_bytes(value:bytes)->str:return hashlib.sha256(value).hexdigest()
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--return-zip",type=Path,required=True);ap.add_argument("--source-zip",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();errors=[]
    return_bytes=a.return_zip.read_bytes();source_bytes=a.source_zip.read_bytes()
    if len(return_bytes)!=RETURN_BYTES or sha_bytes(return_bytes)!=RETURN_SHA:errors.append("external_return_identity_mismatch")
    if len(source_bytes)!=SOURCE_BYTES or sha_bytes(source_bytes)!=SOURCE_SHA:errors.append("source_zip_identity_mismatch")
    with zipfile.ZipFile(a.source_zip) as source:
        source_manifest=source.read(PACKAGE+"/package_manifest.json");request=json.loads(source.read(PACKAGE+"/contracts/server_post_sim_return_request.json"));runner=source.read(PACKAGE+"/PREPARE_AND_RUN.sh").decode(errors="replace")
    root=PACKAGE+"_return";prefix=root+"/"
    with zipfile.ZipFile(a.return_zip) as archive:
        infos=archive.infolist();names=[item.filename for item in infos];rels={name[len(prefix):] for name in names if name.startswith(prefix)}
        if archive.testzip() is not None:errors.append("crc_failure")
        if len(names)!=len(set(names)):errors.append("duplicate_member")
        if any(not name.startswith(prefix) or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name for name in names):errors.append("root_or_path_failure")
        if any(stat.S_ISLNK(item.external_attr>>16) for item in infos):errors.append("symlink_member")
        if rels!=EXPECTED:errors.append("exact_set_mismatch")
        def load(name:str):return json.loads(archive.read(prefix+name))
        manifest=load("RETURN_CORE_MANIFEST.json");core=load("return_core/RETURN_CORE_STATUS.json");plugins=load("return_core/RETURN_PLUGIN_STATUS.json");sim=load("return_core/SIM_EXIT_RECEIPT.json");plugin=load("return_core/plugins/node0004_source_bound_collect.status.json");plugin_stderr=archive.read(prefix+"return_core/plugins/node0004_source_bound_collect.stderr.log").decode(errors="replace")
        for row in manifest.get("core_entry_receipts",[]):
            name=row["path"]
            if name not in rels or len(archive.read(prefix+name))!=row["bytes"] or sha_bytes(archive.read(prefix+name))!=row["sha256"]:errors.append("core_receipt_mismatch:"+name)
        returned_manifest=archive.read(prefix+"evidence/returned_package_manifest.json")
        if returned_manifest!=source_manifest:errors.append("source_manifest_byte_binding_mismatch")
        expected_return=a.return_zip.name
        identity=[manifest.get("package_id")==PACKAGE,manifest.get("execution_id")==EXECUTION,manifest.get("return_basename")==expected_return,core.get("package_id")==PACKAGE,core.get("execution_id")==EXECUTION,sim.get("package_id")==PACKAGE,sim.get("execution_id")==EXECUTION]
        if not all(identity):errors.append("internal_identity_mismatch")
        compile_exit=int(archive.read(prefix+"evidence/compile_exit_status.txt").strip());run_exit=int(archive.read(prefix+"evidence/run_exit_status.txt").strip());signal=archive.read(prefix+"evidence/signal_status.txt").decode().strip()
    allowed_archives={row["archive"] for row in request.get("core_entries",[])};generated={"RETURN_CORE_MANIFEST.json","return_core/RETURN_CORE_STATUS.json","return_core/RETURN_PLUGIN_STATUS.json","return_core/SIM_EXIT_RECEIPT.json","return_core/plugins/node0004_source_bound_collect.status.json","return_core/plugins/node0004_source_bound_collect.stderr.log","return_core/plugins/node0004_source_bound_collect.stdout.log"};allowlist_ok=rels<=(allowed_archives|generated)
    if not allowlist_ok:errors.append("allowlist_violation")
    report={"schema":"conv-node0004-v84b-formal-return-analysis-v1","analysis_valid":not errors,"structural_errors":errors,
      "RETURN_ANALYSIS":{"return":{"path":str(a.return_zip),"bytes":len(return_bytes),"sha256":RETURN_SHA},"source":{"path":str(a.source_zip),"bytes":len(source_bytes),"sha256":SOURCE_SHA},"execution_id":EXECUTION,"crc_root_path_duplicate_symlink_exact_set":not any(x in errors for x in ("crc_failure","duplicate_member","root_or_path_failure","symlink_member","exact_set_mismatch")),"allowlist":allowlist_ok,"per_file_receipts":not any(x.startswith("core_receipt_mismatch") for x in errors),"source_manifest_byte_binding":returned_manifest==source_manifest,"install_identity":"PACKAGE_MANIFEST_BYTE_EQUAL; runtime install preflight receipts are not present in this core-only compile-fail return","publication":{"fixed_return_basename_match":manifest.get("return_basename")==a.return_zip.name,"core_return_survived_plugin_failure":core.get("return_publication_independent_of_plugin_success") is True},"compile_exit":compile_exit,"run_exit":run_exit,"signal":signal,"sim_started":sim.get("sim_started"),"sim_exit_code":sim.get("sim_exit_code"),"core_disposition":core.get("disposition"),"required_plugin_failures":core.get("required_plugin_failures"),"missing_required_entries":core.get("missing_required_entries"),"plugin":{"exit_code":plugin.get("exit_code"),"error":"IMMUTABLE_RAW_INLINE_REALTIME_INPUT_MISSING","is_consequence_of_sim_not_started":True},"actual_compile_identity":"UNAVAILABLE_IN_RETURN","compile_driver_log":"NOT_RETURNED","natural_terminal":False,"formal_d":{"present":0,"missing":320,"mismatch":None,"adjudication":"NOT_EVALUATED_ALL_MISSING"},"E3":False,"E4":False,"E5":False},
      "LAST_PROVEN_GOOD":"SOURCE_PACKAGE_AND_EXECUTION_IDENTITY_BOUND_CORE_RETURN_PUBLISHED_AFTER_COMPILE_FAILURE",
      "FIRST_DIVERGENCE":"PRODUCTION_COMPILE_EXIT_2_BEFORE_SIMULATION_START",
      "HANG_ROOT_CAUSE":{"classification":"NOT_A_HANG_SIM_NOT_STARTED","compile_failure_root":"UNRESOLVED_COMPILE_FAILURE_CAUSE_BECAUSE_COMPILE_DRIVER_LOG_NOT_RETURNED","package_local_evidence_defect":"COMPILEFAIL_CORE_RETURN_OMITS_BOUNDED_COMPILE_DRIVER_LOG","consequential_plugin_failure":"sim.log absent because simulation never started","frozen_fix_surface":["server_post_sim_return_request core_entries","bounded compile_driver.log or first-error excerpt","compile-fail parser that preserves actual compile argv/identity"]},
      "PROGRESS_THIS_ROUND":{"relative_to":"v83b","classification":"PACKAGE_RUNNER_CAUSAL_PROGRESS_ONLY_WITH_DYNAMIC_REACHABILITY_REGRESSION","functional_progress":False,"target_causal_progress":False,"package_causal_progress":True,"closed":["v84b core return proves exact compile exit=2 and sim_started=false"],"regressed":["v83b reached compile=0/run=0 and emitted 65 target phase events; v84b did not start simulation"],"reason":"The return localizes failure to production compile, but lacks the compile log required to identify observer vs RTL vs environment cause."},
      "BLOCKER_DELTA":{"opened":["B_CONV_NODE0004_V84B_PRODUCTION_COMPILE_EXIT_2","B_CONV_NODE0004_COMPILEFAIL_RETURN_OMITS_DRIVER_LOG"],"retained":["B_CONV_NODE0004_ACK_OUTPUT_VS_INLINE_RHS_STABLE_MISMATCH_UNRESOLVED","B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL","B_CONV_NODE0004_FORMAL_D_320"],"closed":[],"invalidated_not_revived":["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"]},
      "RULE_DELTA_PROPOSAL":{"id":"CDA-SERVER-COMPILEFAIL-CORE-RETURN-FIRST-ERROR-001","proposal":"When production compile is nonzero, the independent core return must include a bounded compile driver log or deterministic first-error excerpt, actual compile argv, and compiled source identity. Missing diagnostics must fail closed as COMPILE_FAILURE_ROOT_UNOBSERVED; the plugin's missing sim.log must remain consequential, not root cause.","negative_controls":["compile exit nonzero with log omitted","log path exists but is absent from exact return","truncated excerpt lacks first compiler error","sim.log-missing plugin error promoted above compile failure"]},
      "PACKAGE_ACTION":{"successor_built":False,"storage_rotated":False,"status":"ANALYSIS_ONLY_FROZEN_BY_USER","frozen_repair_surface_only":True},"claims":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_modified":False,"functional_rtl_modified":False,"plan_or_rules_modified":False,"server_action":False,"successor_built":False,"storage_rotated":False},"evidence_notes":{"runner_compile_log_redirect":"PREPARE_AND_RUN.sh redirects production compile to compile/sim_results/compile_driver.log","core_request_omission":"contracts/server_post_sim_return_request.json does not archive compile_driver.log","plugin_stderr":plugin_stderr.strip(),"plugin_status_count":len(plugins)}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(json.dumps({"analysis_valid":not errors,"errors":errors,"first_divergence":report["FIRST_DIVERGENCE"]}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
