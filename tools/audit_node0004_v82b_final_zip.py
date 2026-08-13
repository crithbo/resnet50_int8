#!/usr/bin/env python3
"""Aggregate exact final-ZIP changed-surface gates for serialized Conv v82b."""
from __future__ import annotations
import argparse, hashlib, json, stat, zipfile
from pathlib import Path, PurePosixPath

PACKAGE="r5_n4_hw_v82b_phase_collectfix"
RULE_SHA="74ae37513d6bcb763543a7a4583ec1acea3d4b2919f07ab8fab266272bf3cc0b"
INDEX_SHA="991740fe543243c1697174fe9c9621af0201469c8bab37c95ea4db12d8276f2c"
GENERATOR_SHA="c50c2f8117ee6e73da76cae4c5a0fc46a3774b7c775d9bb62942ff8bcd4b837f"
EPOCH="20260811-exact-instance-payload-semantic-fingerprint-v2"

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8"))
def receipt(path:Path)->dict:return {"path":str(path),"bytes":path.stat().st_size,"sha256":sha(path)}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--zip",type=Path,required=True);ap.add_argument("--sidecar",type=Path,required=True);ap.add_argument("--build-report",type=Path,required=True);ap.add_argument("--validation-root",type=Path,required=True);ap.add_argument("--first-fresh-contract",type=Path,required=True);ap.add_argument("--first-fresh-validation",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    paths={name:a.validation_root/file for name,file in {"source_bound":"exact_source_bound.json","phase":"exact_phase.json","post_sim":"exact_post_sim.json","runner":"exact_runner.json","shared_harness":"exact_shared_harness.json"}.items()}
    paths["runtime_layout"]=a.validation_root.parent/"validation_v82b_runtime_layout.json"
    paths["return_contract"]=a.validation_root.parent/"validation_v82b_return_contract.json"
    values={name:load(path) for name,path in paths.items() if path.is_file()}; missing=sorted(set(paths)-set(values))
    build=load(a.build_report); first_contract=load(a.first_fresh_contract); first=load(a.first_fresh_validation)
    with zipfile.ZipFile(a.zip) as z:
        infos=z.infolist(); names=[row.filename for row in infos]; prefix=PACKAGE+"/"
        crc=z.testzip() is None; safe=all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr>>16) for row in infos)
        root={PurePosixPath(name).parts[0] for name in names if name}=={PACKAGE}; duplicates=len(names)==len(set(names))
        manifest=json.loads(z.read(prefix+"package_manifest.json")); actual={row.filename[len(prefix):]:hashlib.sha256(z.read(row)).hexdigest() for row in infos if row.filename.startswith(prefix) and row.filename!=prefix+"package_manifest.json" and not row.is_dir()}
        semantics=json.loads(z.read(prefix+"diagnostics/buffer_ack_phase_semantics_contract.json"))
        phase_hashes={"observer":hashlib.sha256(z.read(prefix+"tb_probe/buffer_ack_phase_observer.svh")).hexdigest(),"parser":hashlib.sha256(z.read(prefix+"package_tools/buffer_ack_phase_parser.py")).hexdigest(),"plugin":hashlib.sha256(z.read(prefix+"package_tools/node0004_v82_post_sim_plugin.py")).hexdigest()}
        runner=z.read(prefix+"PREPARE_AND_RUN.sh").decode("utf-8")
    side=a.sidecar.read_text(encoding="ascii").strip().split(); active=manifest.get("active_receipts",{})
    checks={
      "zip_crc":crc,"zip_safe":safe,"zip_single_root":root,"zip_duplicate_free":duplicates,"sidecar_exact":len(side)>=2 and side[0]==sha(a.zip) and side[-1].endswith(a.zip.name),"manifest_exact":manifest.get("files")==actual,
      "build_identity":build.get("zip_sha256")==sha(a.zip) and build.get("zip_bytes")==a.zip.stat().st_size and build.get("deterministic_directory_rebuild_equal") is True,
      "one_final_zip":build.get("final_zip_count")==1 and build.get("cheap_aggregate_invocations")==1,
      "current_rule":active.get("server_package_rule_sha256")==RULE_SHA,"current_index":active.get("generation_index_sha256")==INDEX_SHA,"current_generator":active.get("source_bound_generator_sha256")==GENERATOR_SHA,
      "epoch_ack":manifest.get("first_fresh_extra_audit",{}).get("epoch_id")==EPOCH and manifest.get("first_fresh_extra_audit",{}).get("bound_package_id")==PACKAGE and manifest.get("first_fresh_extra_audit",{}).get("first_fresh_after_change") is True,
      "source_bound_v2":values.get("source_bound",{}).get("pass") is True and values.get("source_bound",{}).get("schema")=="server-source-bound-final-zip-validation-v2" and values.get("source_bound",{}).get("semantic_controls",{}).get("pass") is True,
      "phase_exact":values.get("phase",{}).get("pass") is True and values.get("phase",{}).get("errors")==[],
      "phase_contract_hashes":semantics.get("observer_sha256")==phase_hashes["observer"] and semantics.get("parser_sha256")==phase_hashes["parser"] and semantics.get("post_sim_plugin_sha256")==phase_hashes["plugin"] and semantics.get("payload",{}).get("width_bits")==38,
      "parse_before_projection":"node0004_v82_post_sim_plugin.py" in json.dumps(json.loads(zipfile.ZipFile(a.zip).read(prefix+"contracts/server_post_sim_return_request.json"))) and semantics.get("collector_order")=="PHASE_PARSE_AND_PERSIST_BEFORE_BOUNDED_SOURCE_BOUND_PROJECTION",
      "post_sim":values.get("post_sim",{}).get("pass") is True and values.get("post_sim",{}).get("errors")==[],
      "runner":values.get("runner",{}).get("valid") is True and values.get("runner",{}).get("errors")==[],
      "runtime_layout":values.get("runtime_layout",{}).get("pass") is True and values.get("runtime_layout",{}).get("errors")==[],
      "return_contract":values.get("return_contract",{}).get("valid") is True and values.get("return_contract",{}).get("errors")==[],
      "runner_tokens":"source_bound_causal_observer.svh" in runner and "buffer_ack_phase_observer.svh" in runner and "+CODEX_CAUSAL_OBSERVER" in runner and "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128" in runner,
      "first_fresh_zip_identity":first_contract.get("package",{}).get("final_zip",{}).get("sha256")==sha(a.zip),
      "first_fresh_pass":first.get("pass") is True and first.get("upload_authorized") is True and first.get("errors")==[],
      "all_reports_present":not missing,
    }
    matrix={
      "package_bootstrap_path_runtime_D":{"applicability":"blocking_applicable","pass":all(checks[k] for k in ("zip_crc","zip_safe","zip_single_root","zip_duplicate_free","sidecar_exact","manifest_exact"))},
      "actual_runner_compile_finalizer_and_86_inputs":{"applicability":"blocking_applicable","pass":checks["runner"] and checks["runtime_layout"]},
      "actual_package_local_HDL":{"applicability":"blocking_applicable","pass":checks["source_bound_v2"] and checks["phase_exact"] and checks["phase_contract_hashes"]},
      "changed_observer_and_canonical_semantics":{"applicability":"blocking_applicable","pass":checks["source_bound_v2"] and checks["phase_exact"] and checks["parse_before_projection"] and checks["post_sim"]},
      "return_result_joint_gate":{"applicability":"blocking_applicable","pass":checks["return_contract"]},
      "first_fresh_independent_reaudit":{"applicability":"blocking_applicable","pass":checks["first_fresh_pass"]},
      "materialized_config":{"applicability":"receipt_reuse","pass":True,"reason":"byte-identical frozen v81 config/address/workload"},
      "numeric_W3_golden":{"applicability":"not_applicable","pass":True,"reason":"not changed or repeated"},
      "functional_RTL":{"applicability":"not_applicable","pass":True,"reason":"not modified"},
    }
    errors=[k for k,v in checks.items() if not v]+["release_gate:"+k for k,v in matrix.items() if v.get("pass") is not True]
    out={"schema":"conv-node0004-v82b-final-zip-audit-v1","FINAL_ZIP_RULE_SELF_AUDIT_PASS":not errors,"errors":errors,"checks":checks,"release_gate_matrix":matrix,"zip":receipt(a.zip),"active_receipts":{"server_rule_sha256":RULE_SHA,"generation_index_sha256":INDEX_SHA,"generator_sha256":GENERATOR_SHA,"epoch_id":EPOCH},"report_receipts":{k:receipt(v) for k,v in paths.items()},"first_fresh_receipts":{"contract":receipt(a.first_fresh_contract),"validation":receipt(a.first_fresh_validation)},"claims":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False},"claim_boundary":"Exact local package/diagnostic/runtime gates only; no DUT natural terminal, formal D, E3, E4 or E5 claim."}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n");print(json.dumps({"pass":not errors,"errors":errors,"zip_sha256":sha(a.zip)}));return 0 if not errors else 1

if __name__=="__main__":raise SystemExit(main())
