#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
PACKAGE="r5_n4_hw_v83b_phase_stable_diag"
TARGET_INSTANCE=("tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue")
PHASES=("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS")
WIDTHS={"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7}
TARGET=Path("NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"); FIFO=Path("NDP_copy01/rtl/utils/FIFO/FIFO.sv"); INCLUDES=Path("NDP_copy01/rtl/includes")
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def line(seq:int,phase:str,*,instance:str=TARGET_INSTANCE,full="0",gotten="0",bpmask="3",bp="3",row="1",time=None)->str:
 f={"wr":"1","full":full,"all":"1","valid":"3","same":"3","gotten":gotten,"keep":"3","bpmask":bpmask,"bp":bp,"mode":"2","row":row,"col":"1f","rowtag":"7f","coltag":"7f"}; payload=0
 for n,w in WIDTHS.items():payload=(payload<<w)|int(f[n],16)
 t=(1000,2000,2001,2250,2750)[PHASES.index(phase)] if time is None else time
 return f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={instance} time={t} mask=1 payload={payload:x} payload_known=1 payload_width=38 seq={seq} phase={phase} "+" ".join(f"{n}={f[n]}" for n in WIDTHS)
def trace(**changes):return [line(0,p,**changes.get(p,{})) for p in PHASES]
def parse(parser:Path,root:Path,name:str,rows:list[str]):
 log=root/f"{name}.log";out=root/f"{name}.json";log.write_text("\n".join(rows)+"\n",encoding="utf-8");r=subprocess.run([sys.executable,str(parser),"--log",str(log),"--output",str(out)],capture_output=True,text=True);return r.returncode,json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
def declared(source:str,name:str)->bool:return re.search(rf"\b(?:input|output|inout|wire|reg|logic)\b[^;\n]*\b{re.escape(name)}\b",source) is not None
def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--zip",type=Path,required=True);ap.add_argument("--iverilog",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();checks={};details={}
 with tempfile.TemporaryDirectory(prefix="n4v83-phase-") as raw:
  root=Path(raw)
  with zipfile.ZipFile(a.zip) as z:
   p=PACKAGE+"/"; parser=root/"parser.py";parser.write_bytes(z.read(p+"package_tools/buffer_ack_phase_parser.py"));observer=z.read(p+"tb_probe/buffer_ack_phase_observer.svh").decode();runner=z.read(p+"PREPARE_AND_RUN.sh").decode()
  checks["exact_instance_bind"]=f"bind {TARGET_INSTANCE} codex_probe_buf_ack_phase_target" in observer
  checks["strictly_edge_free_delays"]=all(x in observer for x in ("#0.001","#0.249","#0.500","#0.250")) and "#1 codex_emit" not in observer
  checks["five_stable_phases"]=all(p in observer for p in PHASES)
  checks["runner_compile_runtime_handoff"]="buffer_ack_phase_observer.svh" in runner and "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128" in runner
  cases={"stable":(trace(),"STABLE_EQUATION_NO_TOKEN_TRANSITION",0),"transition":(trace(LATE_750PS={"row":"2"}),"EDGE_LOCAL_TOKEN_TRANSITION_WITH_STABLE_EQUATION",0),"settle":(trace(PRE={"bp":"0"}),"PRE_EDGE_ACK_MISMATCH_SETTLES_AFTER_EDGE",0),"persistent":(trace(PRE={"bp":"0"},EDGE={"bp":"0"},DELTA_1PS={"bp":"0"},QUARTER_250PS={"bp":"0"},LATE_750PS={"bp":"0"}),"PERSISTENT_STABLE_WINDOW_EQUATION_MISMATCH",0)}
  for n,(rows,want,wrc) in cases.items():rc,v=parse(parser,root,n,rows);checks[n]=rc==wrc and v.get("decision")==want
  rc,v=parse(parser,root,"collision",[line(0,p,time=2000 if p in {"EDGE","DELTA_1PS"} else None) for p in PHASES]);checks["phase_collision_negative"]=rc!=0 and v.get("decision")=="PHASE_TIME_COLLISION_FAIL_CLOSED"
  wrong=[x.replace("[13]","[12]",1) for x in trace()];rc,v=parse(parser,root,"wrong",wrong);checks["wrong_instance_negative"]=rc!=0 and v.get("decision")=="NO_EXACT_TARGET_LIVE_EVENT"
  rc,v=parse(parser,root,"missing",trace()[:-1]);checks["missing_phase_negative"]=rc!=0 and v.get("decision")=="INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE"
  bad=trace();bad[0]=bad[0].replace("payload_known=1","payload_known=0");rc,v=parse(parser,root,"unknown",bad);checks["unknown_payload_negative"]=rc!=0 and v.get("decision")=="UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
  target=TARGET.read_text(encoding="utf-8");m=re.search(r"bind\s+([^\s]+)\s+codex_probe_buf_ack_phase_target\s+codex_probe_buf_ack_phase_target_inst\s*\((.*?)\)\s*;",observer,re.S);bind_map=dict(re.findall(r"\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\)",m.group(2))) if m else {}
  checks["actual_consumer_scope"]=bool(bind_map) and all(declared(target,x) for x in bind_map.values());actual=next(iter(bind_map.values()),"");checks["delete_actual_negative"]=bool(actual) and not declared(target.replace(actual,"",1),actual);checks["typo_actual_negative"]=not declared(target,actual+"_TYPO")
  obs=root/"obs.svh";obs.write_text(observer,encoding="utf-8");tc=[str(a.iverilog),"-g2012","-Wall","-I",str(INCLUDES),"-s","Buffer_AG_Idx_Queue","-o",str(root/"t.vvp"),str(FIFO),str(TARGET)];oc=[str(a.iverilog),"-g2012","-Wall","-I",str(INCLUDES),"-D","CODEX_SOURCE_BOUND_FOCUS","-s","codex_probe_buf_ack_phase_target","-o",str(root/"o.vvp"),str(obs)];tr=subprocess.run(tc,capture_output=True,text=True);orr=subprocess.run(oc,capture_output=True,text=True);checks["target_compile"]=tr.returncode==0;checks["observer_compile"]=orr.returncode==0;details={"target_stderr":tr.stderr,"observer_stderr":orr.stderr,"bind_map":bind_map}
 errors=[k for k,v in checks.items() if not v];report={"schema":"node0004-v83-stable-phase-validation-v1","pass":not errors,"errors":errors,"checks":checks,"details":details,"zip":{"path":str(a.zip),"bytes":a.zip.stat().st_size,"sha256":sha(a.zip)},"claim_boundary":"Exact package-local stable-phase HDL/parser gates only; no DUT/numeric/config/natural-terminal/formal-D claim."};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps({"pass":not errors,"errors":errors}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
