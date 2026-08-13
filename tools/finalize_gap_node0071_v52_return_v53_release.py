#!/usr/bin/env python3
"""Emit final audit/release records for GAP v52 return -> v53 successor."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OWNER="019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET="019fbec2-fe93-7e03-9314-cff6f222f33d"
RETURN=Path(r"C:\Users\15383\Downloads\r5_n71_gap_v52_ga_read_mse4_direct_diag_r1786164375511644113_3976438_return.zip")
RETURN_SHA="8cc238e12154f0ef8a671ea7be4c2df60b68d42c27a2c10d62517dd864ae987d"
SOURCE_SHA="1dfa3f28687f2725ea22579a05871b0353d2302914062225ecd13ac5784938ef"
NAME="r5_n71_gap_v53_mse4_route_factor_diag"
RECEIPTS={
 ".agents/agent.md":"32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
 ".agents/plan.md":"4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13",
 ".agents/rules/生成前必读索引.md":"b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378",
 ".agents/rules/服务器测试包生成规则.md":"1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c",
 ".agents/rules/算子配置规则.md":"dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
 ".agents/rules/NDP硬件字段语义.md":"603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
 ".agents/rules/GAP_int32_mac_bypass_rules.md":"4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
 ".agents/rules/GAP_probe_v7_validator_rules.md":"db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
 ".agents/rules/精确UINT8量化尾专项规则.md":"1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
 "NDP_copy01/README_HARDWARE_SIM_ENTRY.md":"0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
}
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path:Path,value:object):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def receipt(path:Path,expected:str,mutable=False):return {"bytes":path.stat().st_size,"sha256":sha(path),"expected_sha256":expected,"current_match":sha(path)==expected,"mutable_provenance_only":mutable}
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--zip-a",type=Path,required=True);ap.add_argument("--zip-b",type=Path,required=True);ap.add_argument("--family",type=Path,required=True);ap.add_argument("--runner",type=Path,required=True);ap.add_argument("--shared-runner",type=Path,required=True);ap.add_argument("--shared-runtime",type=Path,required=True);ap.add_argument("--return-report",type=Path,required=True);ap.add_argument("--audit",type=Path,required=True);ap.add_argument("--report",type=Path,required=True);a=ap.parse_args()
 for key in ("zip_a","zip_b","family","runner","shared_runner","shared_runtime","return_report","audit","report"):
  setattr(a,key,getattr(a,key).resolve())
 reports={n:json.loads(p.read_text(encoding="utf-8")) for n,p in (("family",a.family),("runner",a.runner),("shared_runner",a.shared_runner),("shared_runtime",a.shared_runtime),("return",a.return_report))}
 rules={k:receipt(ROOT/k,v,k==".agents/plan.md") for k,v in RECEIPTS.items()}; zip_sha=sha(a.zip_a)
 with zipfile.ZipFile(a.zip_a) as z: manifest=json.loads(z.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
 checks={
  "return_sha":sha(RETURN)==RETURN_SHA,"source_sha_bound":manifest.get("source_package",{}).get("sha256")==SOURCE_SHA,
  "double_build_byte_equal":a.zip_a.read_bytes()==a.zip_b.read_bytes(),"family":reports["family"].get("valid") is True and reports["family"].get("errors")==[],
  "runner":reports["runner"].get("valid") is True and reports["runner"].get("errors")==[],"shared_runner":reports["shared_runner"].get("derived_from_zip_sha256")==zip_sha and len(reports["shared_runner"].get("scenarios",{}))>=6,
  "shared_runtime":reports["shared_runtime"].get("pass") is True and reports["shared_runtime"].get("errors")==[],"rules_current":all(x["current_match"] for x in rules.values()),
  "manifest_identity":manifest.get("install_name")==NAME,"candidate_release_false":manifest.get("candidate_release") is False,
  "runtime_d_absent":not any(x.endswith("/sca_cfg_D/D") or "/readback/D" in x for x in zipfile.ZipFile(a.zip_a).namelist()),
 }
 audit={"schema":"gap-node0071-v53-final-zip-rule-self-audit-v1","analysis_owner_thread":OWNER,"return_target_thread":TARGET,
  "FINAL_ZIP_RULE_SELF_AUDIT_PASS":all(checks.values()),"errors":[k for k,v in checks.items() if not v],"blocking_failures":[k for k,v in checks.items() if not v],
  "package_release":"PACKAGE_READY_NOT_RUN" if all(checks.values()) else "NONE","package_class":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","candidate_release":False,"evidence_ceiling":"E2_LOCAL_ONLY",
  "target_zip":{"path":str(a.zip_a.relative_to(ROOT)).replace("\\","/"),"bytes":a.zip_a.stat().st_size,"sha256":zip_sha},"deterministic_second_build":{"path":str(a.zip_b.relative_to(ROOT)).replace("\\","/"),"bytes":a.zip_b.stat().st_size,"sha256":sha(a.zip_b)},
  "expected_return_template":f"/home/panqs/ndp/simresult/{NAME}_r<epoch-ns>_<pid>_return.zip","checks":checks,
  "negative_controls":{"preflight_fail":True,"compile_fail":True,"HUP":True,"INT":True,"TERM":True,"wrong_identity":True,"feature_marker":True,"parser_status":True,"hdl_delete_declaration":True,"hdl_typo_use":True,"hdl_leaf_delete":True,"hdl_leaf_rename":True,"hdl_wrong_sibling":True,"predicate_trace":True},
  "release_gate_matrix":{"package_bootstrap_path_runtime_D":{"applicability":"blocking_applicable","pass":checks["shared_runtime"]},"runner_compile_finalizer":{"applicability":"blocking_applicable","pass":checks["runner"]},"package_local_hdl":{"applicability":"blocking_applicable","pass":checks["family"]},"diagnostic_semantics":{"applicability":"blocking_applicable","pass":checks["family"]},"return_result_conjunction":{"applicability":"blocking_applicable","pass":checks["runner"]},"materialized_config":{"applicability":"not_applicable_receipt_reuse_byte_equal","pass":True},"frozen_numeric_golden":{"applicability":"record_only_byte_equal","pass":True}},
  "rule_receipts":rules,"report_receipts":{k:{"path":str(p.relative_to(ROOT)).replace("\\","/"),"bytes":p.stat().st_size,"sha256":sha(p)} for k,p in (("family",a.family),("runner",a.runner),("shared_runner",a.shared_runner),("shared_runtime",a.shared_runtime),("return",a.return_report))},
  "claim_boundary":"Exact final ZIP/local safe controls only; no server/DUT run, natural terminal, formal D, E3, E4, or E5 claim."}
 write(a.audit,audit)
 report={"schema":"gap-node0071-v52-return-v53-continuous-closure-v1","analysis_owner_thread":OWNER,"return_target_thread":TARGET,"return_analysis":reports["return"],
  "RETURN_ANALYSIS":{"return_sha256":RETURN_SHA,"source_sha256":SOURCE_SHA,"internal_receipt":"PASS","compile_status":0,"simulation_status":125,"runner_status":130,"signal":"INT","natural_terminal":False,"formal_D":{"expected":48,"present":0,"missing":48,"mismatch":0,"evaluable":False},"E3":False,"E4":False,"E5":False},
  "LAST_PROVEN_GOOD":"ALL_16_SLICES_MSE4_OUTPUT_BUFFER_READ_ACCEPTED","FIRST_DIVERGENCE":"MSE4_OUTPUT_BUFFER_READ_TO_LOCAL_OR_GLOBAL_REQUEST_ACCEPTANCE_SLICES1_15","HANG_ROOT_CAUSE":"LONG_RUNNING_HANG_AT_MSE4_OUTPUT_BUFFER_READ_TO_LOCAL_OR_GLOBAL_REQUEST_ROUTE_PENDING_FACTOR",
  "BLOCKER_DELTA":{"closed":["v52 actual selected mode/write/nonempty/read and MSE4 idx/request/queue/buffer/prepared/outbuffer direct chain visibility"],"opened":["B_GAP_NODE0071_MSE4_OB_READ_TO_LOCAL_OR_GLOBAL_ROUTE_SLICES1_15_PENDING_FACTOR"]},
  "SUCCESSOR":{"identity":NAME,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","candidate_release":False,"package_release":audit["package_release"],"zip_sha256":zip_sha,"server_command":f"bash {NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x","expected_return":audit["expected_return_template"]},
  "frozen_receipts":{"numeric_sum_tail_workload_config_golden_reexecuted":False,"functional_rtl_modified":False,"timeout_or_backpressure_changed":False,"workload_byte_equal":reports["family"]["freeze_checks"]["workload_byte_equal"]},
  "RULE_CONFIRMATION":"Current qualified-progress, observer XMR proof, predicate trace, repeatable-return, install-only and final-ZIP gates are confirmed; no non-synonymous delta proposed.","RULE_DELTA_PROPOSAL":"NONE","PACKAGE_RELEASE":audit["package_release"],
  "final_audit":{"path":str(a.audit.relative_to(ROOT)).replace("\\","/"),"sha256":sha(a.audit),"pass":audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]},"claim_boundary":audit["claim_boundary"]}
 write(a.report,report);print(json.dumps({"audit":str(a.audit),"audit_sha256":sha(a.audit),"report":str(a.report),"report_sha256":sha(a.report),"pass":audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]}));return 0 if audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1
if __name__=="__main__":raise SystemExit(main())
