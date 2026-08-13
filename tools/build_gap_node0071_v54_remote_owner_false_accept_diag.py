#!/usr/bin/env python3
"""Build GAP node0071 v54 simultaneous remote-owner false-accept diagnostic."""
from __future__ import annotations
import argparse,json,shutil,tempfile
from pathlib import Path
import build_gap_node0071_v53_mse4_route_factor_diag as base

ROOT=Path(__file__).resolve().parents[1]
SOURCE="r5_n71_gap_v53_mse4_route_factor_diag"
INSTALL="r5_n71_gap_v54_remote_owner_false_accept_diag"
SOURCE_SHA="5a50594bae06c56040d48637f46709a32dea292d6af925c36b4a235d7a887d8a"
RETURN_SHA="36c04e4e93fd2f608239c634186c895d71a0edbbd697a8294a9678650d712ff4"
SERVER_RULE_SHA="1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c"
INDEX_SHA="b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378"
util=base.base.base
util.SOURCE=SOURCE;util.INSTALL=INSTALL;util.SOURCE_ZIP=ROOT/"artifacts/operator_config_validation/r5-server-test-packages/pending"/f"{SOURCE}.zip";util.SOURCE_SHA=SOURCE_SHA;util.RETURN_SHA=RETURN_SHA;util.SERVER_RULE_SHA=SERVER_RULE_SHA;util.INDEX_SHA=INDEX_SHA

PROGRESS=("m4_req_hs0","m4_req_hs1","m4_w_hs0","m4_w_hs1","g_req_wr0","g_req_wr1","g_w_wr0","g_w_wr1","finish")
VIOLATION=("remote_collision","req_owner_mismatch0","req_owner_mismatch1","w_owner_mismatch0","w_owner_mismatch1","req_no_fifo_write0","req_no_fifo_write1","w_no_fifo_write0","w_no_fifo_write1")
FACTOR=tuple(f"remote{i}" for i in range(5))+tuple(f"owner{i}" for i in range(5))+tuple(f"mse{i}_{kind}{ch}" for i in range(5) for kind in ("req_v","req_r","w_v","w_r") for ch in range(2))+tuple(f"g_{kind}{ch}" for kind in ("req_v","req_r","w_v","w_r") for ch in range(2))
FIELDS=PROGRESS+VIOLATION+FACTOR

def xmr(g:str,s:str,leaf:str)->str:return f"u_NDP_Top_new.slice_with_datahub_mc_group_gen[{g}].u_slice_with_datahub_mc_group.slice_group_gen[{s}].u_slice_wrapper.u_slice2hub_crossbar.{leaf}"

def observer_extension()->str:
 o=["","    // v54: simultaneous shared-remote owner and false-accept proof.","    // Only actual accepts/FIFO writes/finish are progress; violation, factor and heartbeat records are not."]
 for n in PROGRESS+VIOLATION+FACTOR:o.append(f"    logic [`GLB_SLICE_NUM-1:0] return_obs_v54_{n}_seen;")
 o += [f"    logic [{len(PROGRESS)}*`GLB_SLICE_NUM-1:0] return_obs_v54_prev_progress;",f"    logic [{len(VIOLATION)}*`GLB_SLICE_NUM-1:0] return_obs_v54_prev_violation;",f"    logic [{len(FACTOR)}*`GLB_SLICE_NUM-1:0] return_obs_v54_prev_factor;","    bit return_obs_v54_enabled; longint unsigned return_obs_v54_db_cycles, return_obs_v54_qcount, return_obs_v54_vcount, return_obs_v54_fcount;"]
 o += ["    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0] return_obs_v54_remote_mon;","    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][4:0][1:0] return_obs_v54_req_v_mon, return_obs_v54_req_r_mon, return_obs_v54_w_v_mon, return_obs_v54_w_r_mon;","    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] return_obs_v54_g_req_v_mon, return_obs_v54_g_req_r_mon, return_obs_v54_g_req_wr_mon, return_obs_v54_g_w_v_mon, return_obs_v54_g_w_r_mon, return_obs_v54_g_w_wr_mon;","    generate","      for(genvar v54_g=0;v54_g<`SLICE_GROUP_SIZE;v54_g++) begin: RETURN_OBS_V54_G","       for(genvar v54_s=0;v54_s<`SLICE_GROUP_NUM;v54_s++) begin: RETURN_OBS_V54_S"]
 o.append(f"        assign return_obs_v54_remote_mon[v54_g][v54_s]={xmr('v54_g','v54_s','slice_remote_req_flag')};")
 o += ["        for(genvar v54_m=0;v54_m<5;v54_m++) begin: RETURN_OBS_V54_M","         for(genvar v54_ch=0;v54_ch<2;v54_ch++) begin: RETURN_OBS_V54_MC"]
 for dst,leaf in (("req_v","mse2hub_req_valid[v54_m][v54_ch]"),("req_r","hub2mse_req_ready[v54_m][v54_ch]"),("w_v","mse2hub_wdata_valid[v54_m][v54_ch]"),("w_r","hub2mse_wdata_ready[v54_m][v54_ch]")):
  o.append(f"          assign return_obs_v54_{dst}_mon[v54_g][v54_s][v54_m][v54_ch]={xmr('v54_g','v54_s',leaf)};")
 o += ["         end","        end","        for(genvar v54_c=0;v54_c<2;v54_c++) begin: RETURN_OBS_V54_C"]
 for dst,leaf in (("g_req_v","slice_global_req_fifo_in_valid[v54_c]"),("g_req_r","slice_global_req_fifo_in_ready[v54_c]"),("g_req_wr","slice_global_req_fifo_wr_en[v54_c]"),("g_w_v","slice_global_wdata_fifo_in_valid[v54_c]"),("g_w_r","slice_global_wdata_fifo_in_ready[v54_c]"),("g_w_wr","slice_global_wdata_fifo_wr_en[v54_c]")):
  o.append(f"         assign return_obs_v54_{dst}_mon[v54_g][v54_s][v54_c]={xmr('v54_g','v54_s',leaf)};")
 o += ["        end","       end","      end","    endgenerate","","    initial begin","      return_obs_v54_enabled=$test$plusargs(\"RETURN_OBS_REMOTE_OWNER_FALSE_ACCEPT\"); return_obs_v54_db_cycles=0;return_obs_v54_qcount=0;return_obs_v54_vcount=0;return_obs_v54_fcount=0;return_obs_v54_prev_progress='0;return_obs_v54_prev_violation='0;return_obs_v54_prev_factor='0; #0;","      if(return_obs_enabled&&return_obs_v54_enabled&&return_obs_fd!=0) begin $fdisplay(return_obs_fd,\"# remote_owner_false_accept=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=384 violation_limit=64 factor_limit=128 heartbeat_cycles=1048576 nonprogress_events=VIOLATION_EDGE,FACTOR_EDGE,HEARTBEAT\");$fflush(return_obs_fd);end","    end","","    always @(posedge u_NDP_Top_new.clk_sg or negedge u_NDP_Top_new.rst_n_sg) begin","      if(!u_NDP_Top_new.rst_n_sg) begin"]
 for n in PROGRESS+VIOLATION+FACTOR:o.append(f"        return_obs_v54_{n}_seen<='0;")
 o += ["      end else if(return_obs_enabled&&return_obs_v54_enabled) begin","       for(int g=0;g<`SLICE_GROUP_SIZE;g++) for(int s=0;s<`SLICE_GROUP_NUM;s++) begin","        int id,owner; logic [4:0] remote; id=g*`SLICE_GROUP_NUM+s;remote=return_obs_v54_remote_mon[g][s];owner=remote[0]?0:remote[1]?1:remote[2]?2:remote[3]?3:remote[4]?4:-1;","        if(return_obs_pair_m4_finish_mon[g][s]) return_obs_v54_finish_seen[id]<=1'b1;","        if(remote[4]&&|remote[3:0]) return_obs_v54_remote_collision_seen[id]<=1'b1;"]
 for i in range(5):o += [f"        if(remote[{i}]) return_obs_v54_remote{i}_seen[id]<=1'b1;",f"        if(owner=={i}) return_obs_v54_owner{i}_seen[id]<=1'b1;"]
 o += ["        for(int ch=0;ch<2;ch++) begin"]
 for i in range(5):
  for kind in ("req_v","req_r","w_v","w_r"):o.append(f"         if(return_obs_v54_{kind}_mon[g][s][{i}][ch]) return_obs_v54_mse{i}_{kind}{0 if False else ''}_seen[id]<=1'b1;" if False else "")
 # Array channel-specific updates are emitted explicitly because field names carry channel.
 o=o[:-0] if False else o
 for i in range(5):
  for kind in ("req_v","req_r","w_v","w_r"):
   o.append(f"         if(ch==0&&return_obs_v54_{kind}_mon[g][s][{i}][ch]) return_obs_v54_mse{i}_{kind}0_seen[id]<=1'b1;")
   o.append(f"         if(ch==1&&return_obs_v54_{kind}_mon[g][s][{i}][ch]) return_obs_v54_mse{i}_{kind}1_seen[id]<=1'b1;")
 for kind in ("req_v","req_r","w_v","w_r"):
  o.append(f"         if(ch==0&&return_obs_v54_g_{kind}_mon[g][s][ch]) return_obs_v54_g_{kind}0_seen[id]<=1'b1;")
  o.append(f"         if(ch==1&&return_obs_v54_g_{kind}_mon[g][s][ch]) return_obs_v54_g_{kind}1_seen[id]<=1'b1;")
 for ch in range(2):
  o += [f"         if(ch=={ch}&&return_obs_v54_req_v_mon[g][s][4][ch]&&return_obs_v54_req_r_mon[g][s][4][ch]) return_obs_v54_m4_req_hs{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&return_obs_v54_w_v_mon[g][s][4][ch]&&return_obs_v54_w_r_mon[g][s][4][ch]) return_obs_v54_m4_w_hs{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&return_obs_v54_g_req_wr_mon[g][s][ch]) return_obs_v54_g_req_wr{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&return_obs_v54_g_w_wr_mon[g][s][ch]) return_obs_v54_g_w_wr{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&remote[4]&&owner!=4&&return_obs_v54_req_v_mon[g][s][4][ch]&&return_obs_v54_req_r_mon[g][s][4][ch]) return_obs_v54_req_owner_mismatch{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&remote[4]&&owner!=4&&return_obs_v54_w_v_mon[g][s][4][ch]&&return_obs_v54_w_r_mon[g][s][4][ch]) return_obs_v54_w_owner_mismatch{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&remote[4]&&return_obs_v54_req_v_mon[g][s][4][ch]&&return_obs_v54_req_r_mon[g][s][4][ch]&&!return_obs_v54_g_req_wr_mon[g][s][ch]) return_obs_v54_req_no_fifo_write{ch}_seen[id]<=1'b1;",f"         if(ch=={ch}&&remote[4]&&return_obs_v54_w_v_mon[g][s][4][ch]&&return_obs_v54_w_r_mon[g][s][4][ch]&&!return_obs_v54_g_w_wr_mon[g][s][ch]) return_obs_v54_w_no_fifo_write{ch}_seen[id]<=1'b1;"]
 o += ["        end","       end","      end","    end","","    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin",f"      logic [{len(PROGRESS)}*`GLB_SLICE_NUM-1:0] ps;logic [{len(VIOLATION)}*`GLB_SLICE_NUM-1:0] vs;logic [{len(FACTOR)}*`GLB_SLICE_NUM-1:0] fs;bit pc,vc,fc,hb;","      if(!u_NDP_Top_new.rst_n_db) begin return_obs_v54_db_cycles=0;return_obs_v54_qcount=0;return_obs_v54_vcount=0;return_obs_v54_fcount=0;return_obs_v54_prev_progress='0;return_obs_v54_prev_violation='0;return_obs_v54_prev_factor='0;end","      else if(return_obs_enabled&&return_obs_v54_enabled&&return_obs_fd!=0) begin return_obs_v54_db_cycles++;",f"       ps={{{','.join('return_obs_v54_'+n+'_seen' for n in PROGRESS)}}};",f"       vs={{{','.join('return_obs_v54_'+n+'_seen' for n in VIOLATION)}}};",f"       fs={{{','.join('return_obs_v54_'+n+'_seen' for n in FACTOR)}}};","       pc=ps!=return_obs_v54_prev_progress;vc=vs!=return_obs_v54_prev_violation;fc=fs!=return_obs_v54_prev_factor;hb=(return_obs_v54_db_cycles%1048576)==0;","       if((pc&&return_obs_v54_qcount<384)||(!pc&&vc&&return_obs_v54_vcount<64)||(!pc&&!vc&&fc&&return_obs_v54_fcount<128)||hb) begin","        if(pc)return_obs_v54_qcount++;else if(vc)return_obs_v54_vcount++;else if(fc)return_obs_v54_fcount++;"]
 fmt="%0t | REMOTE_OWNER_FALSE_ACCEPT_V1 | event=%0s qn=%0d vn=%0d fn=%0d db_cycle=%0d "+" ".join(f"{n}=0x%0h" for n in FIELDS)
 args=["$time","pc?\"QUALIFIED_EDGE\":vc?\"VIOLATION_EDGE\":fc?\"FACTOR_EDGE\":\"HEARTBEAT\"","return_obs_v54_qcount","return_obs_v54_vcount","return_obs_v54_fcount","return_obs_v54_db_cycles"]+[f"return_obs_v54_{n}_seen" for n in FIELDS]
 o += [f"        $fdisplay(return_obs_fd,\"{fmt}\",", "         "+",\n         ".join(args)+");","        $fflush(return_obs_fd);end","       return_obs_v54_prev_progress=ps;return_obs_v54_prev_violation=vs;return_obs_v54_prev_factor=fs;end","    end"]
 return "\n".join(x for x in o if x!="")+"\n"

def parser_text()->str:
 return f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
FIELDS={FIELDS!r};PROGRESS={PROGRESS!r};VIOLATION={VIOLATION!r};FACTOR={FACTOR!r}
PAT=re.compile(r"REMOTE_OWNER_FALSE_ACCEPT_V1\\s+\\|\\s+event=\\s*(QUALIFIED_EDGE|VIOLATION_EDGE|FACTOR_EDGE|HEARTBEAT).*?"+r"\\s+".join(fr"{{n}}=0x([0-9a-fA-F]+)" for n in FIELDS))
def decide(text):
 masks={{n:0 for n in FIELDS}};counts={{x:0 for x in ("QUALIFIED_EDGE","VIOLATION_EDGE","FACTOR_EDGE","HEARTBEAT")}}
 for m in PAT.finditer(text):
  e=m.group(1);counts[e]+=1;vals={{n:int(m.group(i+2),16) for i,n in enumerate(FIELDS)}}
  for n,v in vals.items():
   if (e=="QUALIFIED_EDGE" and n in PROGRESS) or (e=="VIOLATION_EDGE" and n in VIOLATION) or n in FACTOR:masks[n]|=v
 rows=[]
 for sid in range(16):
  b=1<<sid;seen={{n:bool(v&b) for n,v in masks.items()}}
  if seen["w_owner_mismatch0"] or seen["w_owner_mismatch1"]:boundary="MSE4_WDATA_ACCEPT_OWNER_MISMATCH_PROVEN"
  elif seen["w_no_fifo_write0"] or seen["w_no_fifo_write1"]:boundary="MSE4_WDATA_ACCEPT_WITHOUT_FIFO_WRITE_PROVEN"
  elif seen["remote_collision"]:boundary="REMOTE_OWNER_COLLISION_WITHOUT_FALSE_ACCEPT_WITNESS"
  elif seen["m4_w_hs0"] or seen["m4_w_hs1"]:boundary="MSE4_WDATA_ACCEPTED_OWNER_NOT_YET_DISTINGUISHED"
  else:boundary="MSE4_WDATA_ACCEPT_ABSENT"
  rows.append({{"slice":sid,"first_missing_or_violation":boundary,"seen":seen}})
 marker="# remote_owner_false_accept=1" in text
 return {{"schema":"gap-node0071-remote-owner-false-accept-decision-v1","feature_enabled_marker":marker,"record_counts":counts,"progress_masks":{{n:f"0x{{masks[n]:04x}}" for n in PROGRESS}},"violation_masks":{{n:f"0x{{masks[n]:04x}}" for n in VIOLATION}},"factor_masks":{{n:f"0x{{masks[n]:04x}}" for n in FACTOR}},"per_slice":rows,"state_factor_violation_or_heartbeat_is_progress":False,"status":"DIAGNOSTIC_EVIDENCE_AVAILABLE" if marker and counts["QUALIFIED_EDGE"] else "FAIL_CLOSED","natural_terminal":False}}
def line(event,spaces=0,**kw):
 vals={{n:kw.get(n,0) for n in FIELDS}};return "0 | REMOTE_OWNER_FALSE_ACCEPT_V1 | event="+(" "*spaces)+event+" qn=1 vn=1 fn=1 db_cycle=1 "+" ".join(f"{{n}}=0x{{vals[n]:x}}" for n in FIELDS)
def self_test():
 marker="# remote_owner_false_accept=1\\n";q={{"m4_w_hs0":1,"g_w_wr0":1,"finish":1}};v={{"w_owner_mismatch0":2,"remote_collision":2}};stable={{n:4 for n in FACTOR}};sim={{n:0xffff for n in FIELDS}}
 a=decide(marker+line("QUALIFIED_EDGE",**q)+"\\n"+line("VIOLATION_EDGE",3,**v)+"\\n"+line("FACTOR_EDGE",3,**stable)+"\\n"+line("HEARTBEAT",5,**stable));s=decide(marker+line("FACTOR_EDGE",3,**stable));m=decide(marker+line("QUALIFIED_EDGE",**sim)+"\\n"+line("VIOLATION_EDGE",3,**sim))
 checks={{"padded_events_parsed":a["record_counts"]=={{"QUALIFIED_EDGE":1,"VIOLATION_EDGE":1,"FACTOR_EDGE":1,"HEARTBEAT":1}},"violation_not_progress":a["progress_masks"]["m4_w_hs0"]=="0x0001" and a["violation_masks"]["w_owner_mismatch0"]=="0x0002","stable_not_progress":s["status"]=="FAIL_CLOSED","owner_mismatch_boundary":a["per_slice"][1]["first_missing_or_violation"]=="MSE4_WDATA_ACCEPT_OWNER_MISMATCH_PROVEN","simultaneous_all_slices":all(x["first_missing_or_violation"]=="MSE4_WDATA_ACCEPT_OWNER_MISMATCH_PROVEN" for x in m["per_slice"])}}
 return {{"schema":"gap-node0071-remote-owner-false-accept-self-test-v1","checks":checks,"pass":all(checks.values())}}
def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="cmd",required=True);a=sub.add_parser("analyze");a.add_argument("--observer-log",type=Path,required=True);a.add_argument("--output",type=Path,required=True);s=sub.add_parser("self-test");s.add_argument("--output",type=Path,required=True);n=ap.parse_args();v=self_test() if n.cmd=="self-test" else decide(n.observer_log.read_text(encoding="utf-8",errors="replace") if n.observer_log.is_file() else "");n.output.write_text(json.dumps(v,indent=2,sort_keys=True)+"\\n",encoding="utf-8");return 0 if (v.get("pass",True) and (n.cmd=="self-test" or v["status"]!="FAIL_CLOSED")) else 1
if __name__=="__main__":raise SystemExit(main())
'''

def patch_package(package:Path):
 obs=package/"tb_probe/native_return_observer.svh";obs.write_text(obs.read_text(encoding="utf-8")+observer_extension(),encoding="utf-8",newline="\n")
 (package/"package_tools/gap_node0071_remote_owner_false_accept_decision.py").write_text(parser_text(),encoding="utf-8",newline="\n")
 old=package/"package_tools/gap_node0071_mse4_route_factor_decision.py";t=old.read_text(encoding="utf-8");t=util.replace_once(t,'event=(QUALIFIED_EDGE|FACTOR_EDGE|HEARTBEAT)','event=\\s*(QUALIFIED_EDGE|FACTOR_EDGE|HEARTBEAT)',"v53 event whitespace parser fix");old.write_text(t,encoding="utf-8",newline="\n")
 runp=package/"PREPARE_AND_RUN.sh";t=runp.read_text(encoding="utf-8");tool='routefactor_tool="$package_root/package_tools/gap_node0071_mse4_route_factor_decision.py"';
 if t.count(tool)!=2:raise util.BuildError("v53 route tool declaration differs")
 t=t.replace(tool,tool+'\nownerfactor_tool="$package_root/package_tools/gap_node0071_remote_owner_false_accept_decision.py"')
 t=util.replace_once(t,"       grep -Fq 'MSE4_ROUTE_FACTOR_V1' \"$observer_log\"; then","       grep -Fq 'MSE4_ROUTE_FACTOR_V1' \"$observer_log\" &&\n       grep -Fq 'remote_owner_false_accept=1' \"$observer_log\" &&\n       grep -Fq 'REMOTE_OWNER_FALSE_ACCEPT_V1' \"$observer_log\"; then","v54 binding")
 t=util.replace_once(t,"mse4_route_factor_records_returned=true\\n'","mse4_route_factor_records_returned=true\\nremote_owner_false_accept_enabled=true\\nremote_owner_false_accept_records_returned=true\\n'","v54 binding true")
 t=util.replace_once(t,"mse4_route_factor_records_returned=false\\n'","mse4_route_factor_records_returned=false\\nremote_owner_false_accept_enabled=false\\nremote_owner_false_accept_records_returned=false\\n'","v54 binding false")
 status='      printf "mse4_route_factor=%s\\n" "$?" >>"$evidence_root/decision_parser_status.txt"';parse='      python3 "$ownerfactor_tool" analyze --observer-log "$observer_log" --output "$evidence_root/remote_owner_false_accept_decision.json" >/dev/null 2>>"$evidence_root/decision_parser_stderr.log"\n      printf "remote_owner_false_accept=%s\\n" "$?" >>"$evidence_root/decision_parser_status.txt"';t=util.replace_once(t,status,status+"\n"+parse,"v54 parser")
 oldargv='"$evidence_root/mse4_route_factor_decision.json"       "$evidence_root/canonical_decision.json"';t=util.replace_once(t,oldargv,'"$evidence_root/mse4_route_factor_decision.json"       "$evidence_root/remote_owner_false_accept_decision.json"       "$evidence_root/canonical_decision.json"',"v54 fallback argv")
 t=util.replace_once(t,'{"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",','{"schema":"gap-node0071-remote-owner-false-accept-decision-v1","status":"FAIL_CLOSED",\n     "reason":reason,"natural_terminal":False},\n    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',"v54 fallback payload")
 t=util.replace_once(t,'"signal":sys.argv[9],"simulation_status":int(sys.argv[10]),','"signal":sys.argv[10],"simulation_status":int(sys.argv[11]),',"v54 fallback indices");t=util.replace_once(t,"for name,payload in zip(sys.argv[1:9],payloads):","for name,payload in zip(sys.argv[1:10],payloads):","v54 fallback outputs")
 st='python3 "$routefactor_tool" self-test --output "$evidence_root/mse4_route_factor_predicate_self_test.json" >/dev/null || runner_fail 8 "MSE4 route-factor predicate self-test failed"';t=util.replace_once(t,st,st+'\npython3 "$ownerfactor_tool" self-test --output "$evidence_root/remote_owner_false_accept_predicate_self_test.json" >/dev/null || runner_fail 8 "remote-owner false-accept predicate self-test failed"',"v54 selftest");t=util.replace_once(t,"  +RETURN_OBS_MSE4_ROUTE_FACTOR","  +RETURN_OBS_MSE4_ROUTE_FACTOR\n  +RETURN_OBS_REMOTE_OWNER_FALSE_ACCEPT","v54 plusarg");runp.write_text(t,encoding="utf-8",newline="\n")
 runtime=package/"package_tools/gap_node0071_complete_server_runtime.py";t=runtime.read_text(encoding="utf-8");runtime.write_text(util.replace_once(t,"len(allowlist) != 87","len(allowlist) != 89","v54 allowlist"),encoding="utf-8",newline="\n")
 contract=package/"SERVER_RUNTIME_LAYOUT_CONTRACT.json";v=json.loads(contract.read_text(encoding="utf-8"));adds=v["path_budget"]["additional_projected_paths"]
 for rel in (f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/remote_owner_false_accept_decision.json",f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/remote_owner_false_accept_predicate_self_test.json"):
  if rel not in adds:adds.append(rel)
 adds.sort();attempt="a"*int(v["path_budget"]["attempt_max_chars"]);longest=max((x.replace("{attempt}",attempt).replace("{name}",INSTALL) for x in adds),key=lambda x:(len(x),x));v["path_budget"]["max_projected_absolute_path_chars"]=int(v["path_budget"]["declared_target_root_max_chars"])+1+len(longest);util.write_json(contract,v)

def manifest_patch(package:Path):
 p=package/"TEST_PACKAGE_MANIFEST.json";v=json.loads(p.read_text(encoding="utf-8"));v.update({"install_name":INSTALL,"package_name":INSTALL+".zip","return_name":INSTALL+"_return","test_id":"r5-gap-node0071-v54-remote-owner-false-accept-diagnostic"});v["source_package"]={"install_name":SOURCE,"sha256":SOURCE_SHA,"return_sha256":RETURN_SHA,"return_analysis":"artifacts/operator_config_validation/r5-gap-node0071-v53-return-analysis/report.json"};v["rule_receipts"]["server_package_rule_sha256"]=SERVER_RULE_SHA;v["rule_receipts"]["generation_index_sha256"]=INDEX_SHA
 v["remote_owner_false_accept_contract"]={"feature":"REMOTE_OWNER_FALSE_ACCEPT_V1","plusarg":"+RETURN_OBS_REMOTE_OWNER_FALSE_ACCEPT","owner_clock":"clk_sg","reporter_clock":"clk_db","qualified_limit":384,"violation_limit":64,"factor_limit":128,"heartbeat_cycles":1048576,"state_factor_violation_or_heartbeat_is_progress":False,"simultaneous_cone":["remote_flag[0:4]","priority owner[0:4]","all MSE req/wdata valid-ready both channels","global req/wdata FIFO input valid-ready-write","MSE4 owner-mismatch accept","MSE4 accept-without-FIFO-write","finish"],"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"}
 for row in ({"source_root":"evidence","source_path":"remote_owner_false_accept_decision.json","target_path":"evidence/remote_owner_false_accept_decision.json","required":True,"max_bytes":262144,"missing_meaning":"remote-owner false-accept decision absent"},{"source_root":"evidence","source_path":"remote_owner_false_accept_predicate_self_test.json","target_path":"evidence/remote_owner_false_accept_predicate_self_test.json","required":True,"max_bytes":32768,"missing_meaning":"remote-owner false-accept self-test absent"}):
  if row["target_path"] not in {x["target_path"] for x in v["return_allowlist"]}:v["return_allowlist"].append(row)
 v["budgets"]["return_extracted_max_bytes"]+=294912;v["budgets"]["return_zip_max_bytes"]+=163840;v["release_gate_matrix"]=[{"gate_id":"PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT","applicability":"blocking_applicable_identity_and_runner_changed","status":"PASS_PENDING_FINAL_ZIP_VALIDATION"},{"gate_id":"PACKAGE_LOCAL_HDL","applicability":"blocking_applicable_observer_changed_exact_private_xmr","status":"PASS_PENDING_CHANGED_SURFACE_SCOPE_VALIDATION"},{"gate_id":"DIAGNOSTIC_SEMANTICS","applicability":"blocking_applicable_predicate_and_parser_changed","status":"PASS_PENDING_EXACT_FORMATTED_TRACE"},{"gate_id":"MATERIALIZED_CONFIG","applicability":"receipt_reuse_byte_equal","status":"PASS"},{"gate_id":"RETURN_RESULT_CONTRACT","applicability":"blocking_applicable_parser_finalizer_changed","status":"PASS_PENDING_SIGNAL_FINALIZER_VALIDATION"},{"gate_id":"FROZEN_NUMERIC_GOLDEN","applicability":"record_only_byte_equal","status":"PASS"}]
 v.update({"candidate_release":False,"package_class":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","evidence_level":"E2_LOCAL_COMPLETE_NODE","numeric_analysis_repeated":False,"sum_or_tail_numeric_reexecuted":False,"functional_rtl_modified":False});runtime=json.loads((package/"SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"));attempt="a"*int(runtime["path_budget"]["attempt_max_chars"]);projected={f"install/cfg_pkg/{INSTALL}/"+x.relative_to(package/"workload").as_posix() for x in (package/"workload").rglob("*") if x.is_file()}|{x.replace("{attempt}",attempt).replace("{name}",INSTALL) for x in runtime["path_budget"]["additional_projected_paths"]};longest=max(projected,key=lambda x:(len(x),x));rootmax=int(runtime["path_budget"]["declared_target_root_max_chars"]);v["path_length_budget"].update({"longest_projected_relative_path":longest,"longest_projected_relative_path_chars":len(longest),"max_projected_absolute_path_chars":rootmax+1+len(longest),"pass":rootmax+1+len(longest)<=int(v["path_length_budget"]["absolute_path_limit_chars"])});v["files"]=util.files_map(package);util.write_json(p,v);v["files"]=util.files_map(package);util.write_json(p,v)

def build(out:Path)->Path:
 package=out/INSTALL
 if package.exists():raise util.BuildError(f"refusing overwrite {package}")
 out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix="gap-v54-source-") as td:shutil.copytree(util.extract_source(Path(td)),package)
 util.replace_identity(package);patch_package(package);util.write_json(package/"provenance/v53_to_v54_remote_owner_false_accept.json",{"schema":"gap-node0071-v53-to-v54-remote-owner-false-accept-v1","source_zip_sha256":SOURCE_SHA,"return_sha256":RETURN_SHA,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","last_proven_good":"SLICES1_15_REMOTE_REQUEST_FIFO_INPUT_AND_OUTPUT_ACCEPTED","first_divergence":"MSE4_PRE_WDATA_ACCEPTED_BUT_SELECTED_GLOBAL_WDATA_FIFO_INPUT_VALID_AND_ACCEPT_ABSENT_SLICES1_15","changed_surface":["fresh identity","simultaneous remote-owner/mux false-accept observer/parser","v53 event whitespace parser fix","manifest/allowlist/provenance"],"frozen":["73 numeric/workload/config/golden files","sum and exact uint8 tail","materialized JSON/mapping/bitstream/execplan/SCA except identity text","timeout/backpressure","functional RTL"],"server_action":False});(package/"README.md").write_text(f"# GAP node0071 v54 remote-owner false-accept diagnostic\n\nClassification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\nThis successor freezes v53 numeric/config/workload/golden, timeout, backpressure and functional RTL. It samples all five MSE remote owners, both request channels, priority-mux inputs, ready grants and FIFO writes in the same clk_sg cycle, and emits explicit MSE4 owner-mismatch/accept-without-write witnesses.\n\nRun: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\nEach execution publishes one unique return under `/home/panqs/ndp/simresult`.\n",encoding="utf-8",newline="\n");manifest_patch(package);return package
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();out=a.output.resolve();p=build(out);z=out/(INSTALL+".zip");util.deterministic_zip(p,z);s=Path(str(z)+".sha256");s.write_text(f"{util.digest(z)}  {z.name}\n",encoding="ascii",newline="\n");print(json.dumps({"zip":str(z),"bytes":z.stat().st_size,"sha256":util.digest(z),"sidecar":str(s),"sidecar_sha256":util.digest(s)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
