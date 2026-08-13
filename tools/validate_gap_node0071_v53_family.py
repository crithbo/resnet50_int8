#!/usr/bin/env python3
"""Changed-surface validation for the exact GAP node0071 v53 ZIP."""
from __future__ import annotations
import argparse,hashlib,json,re,stat,subprocess,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
NAME="r5_n71_gap_v53_mse4_route_factor_diag"
SOURCE_NAME="r5_n71_gap_v52_ga_read_mse4_direct_diag"
SOURCE=ROOT/"artifacts/operator_config_validation/r5-server-test-packages/pending"/f"{SOURCE_NAME}.zip"
SOURCE_SHA="1dfa3f28687f2725ea22579a05871b0353d2302914062225ecd13ac5784938ef"
INDEX_SHA="b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378"
SERVER_SHA="1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c"
MARKER="    // v53: owner-clock qualified MSE4 local/global route factors."
IVERILOG=Path(r"C:\iverilog\bin\iverilog.exe")
CROSSBAR=ROOT/"NDP_copy01/rtl/Slice/slice2hub_crossbar.sv"
FIFO=ROOT/"NDP_copy01/rtl/utils/FIFO/FIFO.sv"
INCLUDES=ROOT/"NDP_copy01/rtl/includes"

def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha(path:Path)->str:return sha_bytes(path.read_bytes())
def write_json(path:Path,value:object)->None:
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
def zmap(path:Path,root:str):
 with zipfile.ZipFile(path) as z:
  infos=z.infolist();names=[x.filename for x in infos];roots={PurePosixPath(n).parts[0] for n in names if n}
  checks={"crc":z.testzip() is None,"single_root":roots=={root},"path_safe":all(not PurePosixPath(n).is_absolute() and ".." not in PurePosixPath(n).parts and "\\" not in n for n in names),"duplicate_free":len(names)==len(set(names)),"symlink_free":all(not stat.S_ISLNK((x.external_attr>>16)&0xffff) for x in infos)}
  members={PurePosixPath(*PurePosixPath(x.filename).parts[1:]).as_posix():z.read(x) for x in infos if not x.is_dir()}
 return members,checks
def run(argv:list[str],cwd:Path,timeout:int=40):
 p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout,check=False)
 return {"argv":argv,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr}

def observer_focused(extension:str)->str:
 body=extension.replace("u_NDP_Top_new.clk_sg","clk_sg").replace("u_NDP_Top_new.rst_n_sg","rst_n_sg").replace("u_NDP_Top_new.clk_db","clk_db").replace("u_NDP_Top_new.rst_n_db","rst_n_db")
 start=body.index("    generate\n"); end=body.index("    endgenerate\n",start)+len("    endgenerate\n")
 body=body[:start]+body[end:]
 # Icarus cannot dynamically index the production packed multidimensional
 # monitor declaration.  Preserve every use/update while projecting only
 # those package-local monitor declarations to equivalent unpacked arrays.
 body=re.sub(r"logic \[`SLICE_GROUP_SIZE-1:0\]\[`SLICE_GROUP_NUM-1:0\]\[1:0\] (return_obs_v53_[a-z0-9_]+);",r"logic \1 [4][4][2];",body)
 body=re.sub(r"logic \[`SLICE_GROUP_SIZE-1:0\]\[`SLICE_GROUP_NUM-1:0\] (return_obs_v53_remote_mon);",r"logic \1 [4][4];",body)
 decl='''`define GLB_SLICE_NUM 16
`define SLICE_GROUP_SIZE 4
`define SLICE_GROUP_NUM 4
module gap_v53_changed_surface;
 logic clk_sg,clk_db,rst_n_sg,rst_n_db; bit return_obs_enabled; integer return_obs_fd;
 logic [1:0] return_obs_pair_m4_ob_rd_mon [4][4]; logic return_obs_pair_m4_finish_mon [4][4];
'''
 return decl+body+"\nendmodule\n"
def compile_sv(text:str,d:Path,label:str,extra:list[str]|None=None,top:str="gap_v53_changed_surface"):
 p=d/f"{label}.sv";p.write_text(text,encoding="utf-8",newline="\n")
 argv=[str(IVERILOG),"-g2012","-tnull","-s",top]
 if extra:argv+=extra
 argv.append(str(p));r=run(argv,d);r["source_sha256"]=sha_bytes(text.encode());return r

def xmr_probe(leaf_override:str|None=None)->str:
 leaves=["slice_remote_req_flag[4]","mse2hub_req_valid[4][0]","hub2mse_req_ready[4][0]","mse2hub_wdata_valid[4][0]","hub2mse_wdata_ready[4][0]","slice_local_req_valid[4][0]","slice_local_req_ready[4][0]","slice_local_wdata_valid[4][0]","slice_local_wdata_ready[4][0]","slice_global_req_fifo_in_valid[0]","slice_global_req_fifo_in_ready[0]","slice_global_wdata_fifo_in_valid[0]","slice_global_wdata_fifo_in_ready[0]","slice_global_req_valid[0]","slice_global_req_ready[0]","slice_global_wdata_valid[0]","slice_global_wdata_ready[0]"]
 if leaf_override:leaves[9]=leaf_override
 assigns="\n".join(f" wire p{i}=dut.{leaf};" for i,leaf in enumerate(leaves))
 return "module gap_v53_xmr_probe; slice2hub_crossbar dut();\n"+assigns+"\nendmodule\n"

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--target-zip",type=Path,required=True);ap.add_argument("--runner-report",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();target=a.target_zip.resolve();errors=[]
 members,archive=zmap(target,NAME);source,source_archive=zmap(SOURCE,SOURCE_NAME)
 if sha(SOURCE)!=SOURCE_SHA:errors.append("source_sha")
 errors += [f"archive:{k}" for k,v in archive.items() if not v]
 manifest=json.loads(members["TEST_PACKAGE_MANIFEST.json"]);payload={k:v for k,v in members.items() if k!="TEST_PACKAGE_MANIFEST.json"};decl=manifest.get("files",{})
 mchecks={"exact_set":set(payload)==set(decl),"per_file_receipts":all(decl[k]["size_bytes"]==len(v) and decl[k]["sha256"]==sha_bytes(v) for k,v in payload.items()),"identity":manifest.get("install_name")==NAME and manifest.get("package_name")==NAME+".zip","source_binding":manifest.get("source_package",{}).get("sha256")==SOURCE_SHA,"allowlist_87":len(manifest.get("return_allowlist",[]))==87,"formal_d_48":len(manifest.get("readback_checks",[]))==48,"current_receipts":manifest.get("rule_receipts",{}).get("server_package_rule_sha256")==SERVER_SHA and manifest.get("rule_receipts",{}).get("generation_index_sha256")==INDEX_SHA}
 errors += [f"manifest:{k}" for k,v in mchecks.items() if not v]
 normalized={k:v.replace(NAME.encode(),SOURCE_NAME.encode()) for k,v in members.items()};changed=sorted(k for k in set(source)|set(normalized) if source.get(k)!=normalized.get(k))
 expected=sorted(["PREPARE_AND_RUN.sh","README.md","SERVER_RUNTIME_LAYOUT_CONTRACT.json","TEST_PACKAGE_MANIFEST.json","package_tools/gap_node0071_complete_server_runtime.py","package_tools/gap_node0071_mse4_route_factor_decision.py","provenance/v52_to_v53_mse4_route_factor.json","tb_probe/native_return_observer.svh"])
 freeze={"normalized_changed_exact_set":changed==expected,"source_archive_safe":all(source_archive.values()),"workload_byte_equal":all(source.get(k)==normalized.get(k) for k in source if k.startswith("workload/")),"timeout_unchanged":[x for x in normalized["PREPARE_AND_RUN.sh"].splitlines() if b"timeout " in x]==[x for x in source["PREPARE_AND_RUN.sh"].splitlines() if b"timeout " in x],"functional_rtl_absent":not any(k.startswith("rtl/") for k in members)}
 errors += [f"freeze:{k}" for k,v in freeze.items() if not v]
 observer=members["tb_probe/native_return_observer.svh"].decode();ext=observer[observer.index(MARKER):]
 semantics={"owner_clk_sg":"always @(posedge u_NDP_Top_new.clk_sg" in ext,"reporter_clk_db":"always @(posedge u_NDP_Top_new.clk_db" in ext,"qualified_limit_384":"progress_changed && return_obs_v53_qualified_emit_count < 384" in ext,"factor_separate_budget":"factor_changed && return_obs_v53_factor_emit_count < 128" in ext,"stable_not_progress":'progress_changed ? "QUALIFIED_EDGE" : (factor_changed ? "FACTOR_EDGE" : "HEARTBEAT")' in ext,"two_channels":"for (genvar v53_ch=0; v53_ch<2; v53_ch++)" in ext,"private_xmr_exact":"u_slice2hub_crossbar.slice_global_req_fifo_in_valid[v53_ch]" in ext,"finish_direct":"return_obs_pair_m4_finish_mon" in ext}
 errors += [f"semantics:{k}" for k,v in semantics.items() if not v]
 with tempfile.TemporaryDirectory(prefix="gap-v53-hdl-") as td:
  d=Path(td);focused=observer_focused(ext);positive=compile_sv(focused,d,"observer_positive")
  delete_decl=compile_sv(focused.replace(" logic [1:0] return_obs_pair_m4_ob_rd_mon [4][4];","",1),d,"observer_delete_decl")
  typo_use=compile_sv(focused.replace("return_obs_pair_m4_finish_mon[g][s]","return_obs_pair_m4_finish_mom[g][s]",1),d,"observer_typo")
  probe=d/"probe.sv";probe.write_text(xmr_probe(),encoding="utf-8")
  actual=[str(IVERILOG),"-g2012","-tnull","-s","gap_v53_xmr_probe","-I",str(INCLUDES),str(FIFO),str(CROSSBAR),str(probe)]
  actual_positive=run(actual,d)
  bad=d/"bad_probe.sv";bad.write_text(xmr_probe("slice_global_req_fifo_in_vlaid[0]"),encoding="utf-8")
  bad_leaf=run(actual[:-1]+[str(bad)],d)
  sibling=d/"sibling_probe.sv";sibling.write_text(xmr_probe("wr_fifo_gen[0].slice_global_req_fifo_in_valid[0]"),encoding="utf-8")
  wrong_sibling=run(actual[:-1]+[str(sibling)],d)
  crossbar_text=CROSSBAR.read_text(encoding="utf-8");deleted=crossbar_text.replace("    wire [`MSE_REQ_CHL_NUM-1:0]                            slice_global_req_fifo_in_valid;\n","",1);deleted_path=d/"slice2hub_crossbar_deleted.sv";deleted_path.write_text(deleted,encoding="utf-8")
  leaf_deleted=run([str(IVERILOG),"-g2012","-tnull","-s","gap_v53_xmr_probe","-I",str(INCLUDES),str(FIFO),str(deleted_path),str(probe)],d)
 hchecks={"observer_positive":positive["exit_code"]==0,"delete_decl_fails":delete_decl["exit_code"]!=0,"typo_use_fails":typo_use["exit_code"]!=0,"actual_crossbar_xmr_positive":actual_positive["exit_code"]==0,"leaf_rename_fails":bad_leaf["exit_code"]!=0,"wrong_sibling_fails":wrong_sibling["exit_code"]!=0,"leaf_delete_fails":leaf_deleted["exit_code"]!=0,"delete_key_update_fail_closed":"return_obs_v53_global_req_in_hs_seen[ch][id] <= 1'b1;" in ext}
 errors += [f"hdl:{k}" for k,v in hchecks.items() if not v]
 hdl={"tool":str(IVERILOG),"tool_version":run([str(IVERILOG),"-V"],ROOT),"observer_positive":positive,"delete_declaration":delete_decl,"typo_use":typo_use,"actual_crossbar_xmr_positive":actual_positive,"leaf_rename":bad_leaf,"wrong_sibling":wrong_sibling,"leaf_delete":leaf_deleted,"checks":hchecks,"actual_target":{"crossbar_path":str(CROSSBAR.relative_to(ROOT)).replace("\\","/"),"crossbar_sha256":sha(CROSSBAR),"fifo_path":str(FIFO.relative_to(ROOT)).replace("\\","/"),"fifo_sha256":sha(FIFO),"instance_path_suffix":"u_slice_wrapper.u_slice2hub_crossbar","owner_clock":"clk_sg"},"claim_boundary":"Exact changed observer syntax plus actual current crossbar private-leaf name resolution; no full-design elaboration or DUT simulation."}
 with tempfile.TemporaryDirectory(prefix="gap-v53-pred-") as td:
  d=Path(td);script=d/"parser.py";out=d/"trace.json";script.write_bytes(members["package_tools/gap_node0071_mse4_route_factor_decision.py"]);pred=run([sys.executable,str(script),"self-test","--output",str(out)],d);pp=json.loads(out.read_text()) if out.is_file() else {}
 pred["payload"]=pp;pred["all_checks_true"]=pred["exit_code"]==0 and pp.get("pass") is True and all(pp.get("checks",{}).values())
 if not pred["all_checks_true"]:errors.append("predicate_trace")
 runner=json.loads(a.runner_report.read_text());rtxt=members["PREPARE_AND_RUN.sh"].decode();rchecks={"feature_plusarg":"+RETURN_OBS_MSE4_ROUTE_FACTOR" in rtxt,"parser_bound":"gap_node0071_mse4_route_factor_decision.py" in rtxt,"unique_return":'return_tag="r$(date -u +%s%N)_$$"' in rtxt,"harness_valid":runner.get("valid") is True and runner.get("errors")==[],"parser_exit_zero":runner.get("checks",{}).get("normal_all_decision_parsers_exit_zero") is True,"parser_stderr_empty":runner.get("checks",{}).get("normal_decision_parser_stderr_empty") is True}
 errors += [f"runner:{k}" for k,v in rchecks.items() if not v]
 result={"schema":"gap-node0071-v53-family-validation-v1","analysis_owner_thread":"019fa366-cb1f-7ae2-880c-f527be0680cd","return_target_thread":"019fbec2-fe93-7e03-9314-cff6f222f33d","target_zip":str(target.relative_to(ROOT)).replace("\\","/"),"target_zip_bytes":target.stat().st_size,"target_zip_sha256":sha(target),"archive_checks":archive,"manifest_checks":mchecks,"freeze_checks":freeze,"normalized_changed_members":changed,"observer_semantics":semantics,"hdl_scope":hdl,"predicate_trace":pred,"runner_checks":rchecks,"errors":errors,"valid":not errors,"claim_boundary":"Exact final package-local changed surfaces and frozen-byte receipts only; no server/DUT run, natural terminal, formal D, E3, E4, or E5 claim."}
 write_json(a.output,result);print(json.dumps({"output":str(a.output),"sha256":sha(a.output),"valid":not errors,"errors":errors}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
