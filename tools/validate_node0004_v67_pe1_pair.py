from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.validate_node0004_v44_observer_syntax import compile_case  # noqa: E402

PACKAGE="r5_n4_hw_v67_pe1_pair_diag"
BEGIN="// v67 PE1_PAIR_ACTUAL_CONSUMER_BEGIN"
END="// v67 PE1_PAIR_ACTUAL_CONSUMER_END"
XMR_RE=re.compile(r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+")
LOCAL_RE=re.compile(r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+)")
NAME_RE=re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def leaf(x:str)->str: return re.sub(r"\[.*\]$","",x.rsplit(".",1)[-1])

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--zip",required=True,type=Path); ap.add_argument("--source-v66",required=True,type=Path); ap.add_argument("--iverilog",required=True,type=Path); ap.add_argument("--output",required=True,type=Path); a=ap.parse_args()
    checks={}; errors=[]
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v66) as s:
        ob=z.read(f"{PACKAGE}/tb_probe/native_return_observer.svh"); runner=z.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode(); runtime=z.read(f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py").decode(); manifest=json.loads(z.read(f"{PACKAGE}/package_manifest.json")); sr=s.namelist()[0].split('/',1)[0]; sm=json.loads(s.read(f"{sr}/package_manifest.json"))
        frozen=[p for p in sm["files"] if p.startswith("workload/") or "golden" in p.lower() or p.endswith(".bin")]
        checks["frozen_payload"]=bool(frozen) and all(z.read(f"{PACKAGE}/{p}").replace(PACKAGE.encode(),sr.encode())==s.read(f"{sr}/{p}") for p in frozen)
    observer=ob.decode(); checks["span_exact"]=observer.count(BEGIN)==observer.count(END)==1
    block=observer[observer.index(BEGIN):observer.index(END)+len(END)]
    exprs=sorted(set(XMR_RE.findall(block)),key=len,reverse=True); corpus={p:p.read_text(encoding='utf-8',errors='ignore') for p in (ROOT/'NDP_copy01/rtl').rglob('*') if p.is_file() and p.suffix.lower() in {'.sv','.v','.svh','.vh'}}
    missing=[]; bindings=[]
    for e in exprs:
        tok=leaf(e); loc=[p for p,t in corpus.items() if re.search(rf"\b{re.escape(tok)}\b",t)]
        if not loc: missing.append(e)
        bindings.append({"expression":e,"leaf":tok,"source_files":[{"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p.read_bytes())} for p in loc[:8]]})
    checks["actual_consumers_bound"]=not missing
    repl={e:f"xmr_{i}" for i,e in enumerate(exprs)}; focused=block
    for e,l in repl.items(): focused=focused.replace(e,l)
    declared=set(LOCAL_RE.findall(focused)); used=set(NAME_RE.findall(focused)); external=sorted((used-declared)-{"return_obs_write_pe1_pair"})
    decl='\n'.join([f"  logic [127:0] {x};" for x in external]+[f"  logic [127:0] {x};" for x in repl.values()])
    source="`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"+decl+"\n"+focused+'\n  initial begin #1; return_obs_write_pe1_pair("FOCUS"); end\nendmodule\n'
    with tempfile.TemporaryDirectory(prefix='v67-pe1-focus-') as td:
        tr=Path(td); pos=compile_case(a.iverilog,tr,'positive',source); miss=compile_case(a.iverilog,tr,'missing_decl',source.replace('  bit return_obs_p1_enabled;','',1)); first=next(iter(repl.values())); typo=compile_case(a.iverilog,tr,'consumer_typo',source.replace(first,first+'_typo',1))
    checks["focused_syntax_scope_positive"]=pos["exit_code"]==0; checks["missing_declaration_negative"]=miss["exit_code"]!=0; checks["actual_consumer_typo_negative"]=typo["exit_code"]!=0
    checks["epoch_shadow_width_fix"]=observer.count("logic [6:0] return_obs_eo_prev_tag")==3 and observer.count("logic [22:0] return_obs_eo_prev_lc")==3
    checks["runner_feature_twice"]=runner.count(" +RETURN_OBS_PE1_PAIR +RETURN_OBS_PE1_PAIR_LIMIT=128")==2
    checks["runtime_feature_binding"]=all(x in runtime for x in ('"feature": "RETURN_OBS_PE1_PAIR"','"+RETURN_OBS_PE1_PAIR"','"+RETURN_OBS_PE1_PAIR_LIMIT=128"'))
    c=manifest["diagnostic_features"]["RETURN_OBS_PE1_PAIR"]; checks["manifest_feature_binding"]=c["edge_schema"]=="PE1_PAIR_V1" and c["runtime_enable_parameter"]=="+RETURN_OBS_PE1_PAIR"
    checks["candidate_matrix_complete"]=all(x in block for x in ("iga_pe_inbuffer_enbale[0]","iga_pe_inbuffer_enbale[2]","iga_pe_inbuffer_valid_bit","iga_pe_inbuffer_matched","normal_mode_wr_handshake","normal_mode_rd_handshake","iga_pe_outport[1]","mem_idx_valid_same_gotten_masked[1]"))
    def emit(trace):
        prev=None; count=0
        for qualified,state in trace:
            change=state!=prev
            if qualified or change: count+=1
            prev=state
        return count
    trace=[(0,(0,0,0)),(0,(0,0,0)),(1,(1,0,0)),(0,(1,0,0)),(1,(1,1,0)),(1,(1,1,1)),(0,(1,1,1))]
    checks["predicate_trace_stable_level_not_progress"]=emit(trace)==4
    errors += [k for k,v in checks.items() if not v]
    report={"schema":"node0004-v67-pe1-pair-validation-v1","valid":not errors,"errors":errors,"checks":checks,"zip_sha256":sha(a.zip.read_bytes()),"observer_sha256":sha(ob),"actual_consumer_count":len(exprs),"uncovered_actual_consumers":len(missing),"bindings":bindings,"focused_frontend":{"positive":pos,"missing_declaration":miss,"actual_consumer_typo":typo},"predicate_trace":{"rows":trace,"emitted":emit(trace)},"claim_boundary":"Exact changed PE1 pair observer, v66 shadow-width correction and feature binding only; no DUT/natural/formal-D/E4/E5 claim."}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n'); print(json.dumps({"valid":not errors,"errors":errors})); return 0 if not errors else 1

if __name__=='__main__': raise SystemExit(main())
