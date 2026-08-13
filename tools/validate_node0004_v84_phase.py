#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
PACKAGE="r5_n4_hw_v84_ack_inline_realtime_diag"
TARGET_INSTANCE=("tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue")
PHASES=("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS");RT=("1000.250","1001.000","1001.001","1001.250","1001.750")
WIDTHS={"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7,"expected":2,"xor":2}
TARGET=Path("NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv");FIFO=Path("NDP_copy01/rtl/utils/FIFO/FIFO.sv");INCLUDES=Path("NDP_copy01/rtl/includes")
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def line(seq:int,phase:str,*,instance:str=TARGET_INSTANCE,full="0",bpmask="3",bp="3",expected=None,xor=None,rt=None,ord_value=None,known="1")->str:
    expected=expected if expected is not None else ("0" if full=="1" else bpmask);xor=xor if xor is not None else f"{int(bp,16)^int(expected,16):x}"
    fields={"wr":"1","full":full,"all":"1","valid":"3","same":"3","gotten":"0" if phase=="PRE" else "3","keep":"3","bpmask":bpmask,"bp":bp,"mode":"2","row":"1","col":"1f","rowtag":"7f","coltag":"7f","expected":expected,"xor":xor};payload=0
    for name,width in WIDTHS.items():payload=(payload<<width)|int(fields[name],16)
    idx=PHASES.index(phase);return f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_inline_realtime_target instance={instance} time={RT[idx].split('.')[0]} rt={RT[idx] if rt is None else rt} mask=1 payload={payload:x} payload_known={known} payload_width=42 seq={seq} phase={phase} ord={idx if ord_value is None else ord_value} "+" ".join(f"{name}={fields[name]}" for name in WIDTHS)
def trace(**changes):return [line(0,p,**changes.get(p,{})) for p in PHASES]
def parse(parser:Path,root:Path,name:str,rows:list[str]):
    log=root/f"{name}.log";out=root/f"{name}.json";log.write_text("\n".join(rows)+"\n",encoding="utf-8");result=subprocess.run([sys.executable,str(parser),"--log",str(log),"--output",str(out)],capture_output=True,text=True);return result.returncode,json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
def declared(source:str,name:str)->bool:return re.search(rf"\b(?:input|output|inout|wire|reg|logic)\b[^;\n]*\b{re.escape(name)}\b",source) is not None
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--zip",type=Path,required=True);ap.add_argument("--iverilog",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args();checks={};details={}
    with tempfile.TemporaryDirectory(prefix="n4v84-phase-") as raw:
      root=Path(raw)
      with zipfile.ZipFile(a.zip) as archive:
        prefix=PACKAGE+"/";parser=root/"parser.py";parser.write_bytes(archive.read(prefix+"package_tools/buffer_ack_phase_parser.py"));observer=archive.read(prefix+"tb_probe/buffer_ack_phase_observer.svh").decode();runner=archive.read(prefix+"PREPARE_AND_RUN.sh").decode()
      checks["exact_instance_bind"]=f"bind {TARGET_INSTANCE} codex_probe_buf_ack_inline_realtime" in observer
      checks["inline_rhs_xor"]=all(token in observer for token in ("codex_expected_bp = {2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask","codex_bp_xor = mse_buf_queue_bp_pre ^ codex_expected_bp","$realtime","ord=%0d"))
      checks["runner_handoff"]="buffer_ack_phase_observer.svh" in runner and "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128" in runner
      cases={"stable":(trace(),"TOKEN_TRANSITION_WITH_STABLE_INLINE_RHS",0),"persistent":(trace(**{p:{"bp":"0"} for p in PHASES}),"PERSISTENT_INLINE_RHS_MISMATCH_AT_STABLE_LATE_SAMPLE",0),"settle":(trace(PRE={"bp":"0"}),"PRE_EDGE_MISMATCH_SETTLES_TO_INLINE_RHS",0)}
      for name,(rows,want,wrc) in cases.items():rc,value=parse(parser,root,name,rows);checks[name]=rc==wrc and value.get("decision")==want
      bad_cases={"wrong_instance":[row.replace("[13]","[12]",1) for row in trace()],"unknown":trace(EDGE={"known":"0"}),"wrong_ordinal":trace(EDGE={"ord_value":4}),"wrong_inline_expected":trace(EDGE={"expected":"2","xor":"1"}),"realtime_collision":trace(DELTA_1PS={"rt":"1001.000"}),"missing_phase":trace()[:-1]}
      for name,rows in bad_cases.items():rc,value=parse(parser,root,name,rows);checks[name+"_negative"]=rc!=0
      target=TARGET.read_text(encoding="utf-8");match=re.search(r"bind\s+([^\s]+)\s+codex_probe_buf_ack_inline_realtime\s+codex_probe_buf_ack_inline_realtime_inst\s*\((.*?)\)\s*;",observer,re.S);bind_map=dict(re.findall(r"\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\)",match.group(2))) if match else {}
      checks["actual_consumer_scope"]=bool(bind_map) and all(declared(target,value) for value in bind_map.values());actual=next(iter(bind_map.values()),"");checks["delete_actual_negative"]=bool(actual) and not declared(target.replace(actual,"",1),actual);checks["typo_actual_negative"]=not declared(target,actual+"_TYPO")
      obs=root/"obs.svh";obs.write_text(observer,encoding="utf-8");target_run=subprocess.run([str(a.iverilog),"-g2012","-Wall","-I",str(INCLUDES),"-s","Buffer_AG_Idx_Queue","-o",str(root/"target.vvp"),str(FIFO),str(TARGET)],capture_output=True,text=True);observer_run=subprocess.run([str(a.iverilog),"-g2012","-Wall","-I",str(INCLUDES),"-D","CODEX_SOURCE_BOUND_FOCUS","-s","codex_probe_buf_ack_inline_realtime","-o",str(root/"observer.vvp"),str(obs)],capture_output=True,text=True);checks["target_compile"]=target_run.returncode==0;checks["observer_compile"]=observer_run.returncode==0;details={"target_stderr":target_run.stderr,"observer_stderr":observer_run.stderr,"bind_map":bind_map}
    errors=[name for name,value in checks.items() if not value];report={"schema":"node0004-v84-inline-realtime-validation-v1","pass":not errors,"errors":errors,"checks":checks,"details":details,"zip":{"path":str(a.zip),"bytes":a.zip.stat().st_size,"sha256":sha(a.zip)},"claim_boundary":"Exact package-local inline expected/xor and $realtime HDL/parser gates only; no DUT/numeric/config/natural-terminal/formal-D claim."};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps({"pass":not errors,"errors":errors}));return 0 if not errors else 1
if __name__=="__main__":raise SystemExit(main())
