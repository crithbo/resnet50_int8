from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PACKAGE = "r5_n4_hw_v81_ack_phase_targetfix"
TARGET_INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)
TARGET = Path("NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv")
FIFO = Path("NDP_copy01/rtl/utils/FIFO/FIFO.sv")
INCLUDES = Path("NDP_copy01/rtl/includes")
TARGET_SHA = "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca"
PHASES = ("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line(seq: int, phase: str, *, instance: str = TARGET_INSTANCE, full: str = "0", gotten: str = "0", bpmask: str = "3", bp: str = "0", row: str = "1") -> str:
    return (
        f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={instance} time={100+seq} mask=1 payload=1 seq={seq} phase={phase} "
        f"wr=1 full={full} all=1 valid=3 same=3 gotten={gotten} keep=3 bpmask={bpmask} bp={bp} mode=2 row={row} col=75 rowtag=73 coltag=73"
    )


def trace(**changes: dict[str, dict[str, str]]) -> list[str]:
    return [line(0, phase, **changes.get(phase, {})) for phase in PHASES]


def run_parser(parser: Path, root: Path, name: str, lines: list[str]) -> tuple[int, dict]:
    log=root/f"{name}.log"; out=root/f"{name}.json"; log.write_text("\n".join(lines)+"\n",encoding="utf-8")
    done=subprocess.run([sys.executable,str(parser),'--log',str(log),'--output',str(out)],text=True,capture_output=True,check=False)
    return done.returncode, json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}


def declared(source: str, name: str) -> bool:
    return re.search(rf"\b(?:input|output|inout|wire|reg|logic)\b[^;\n]*\b{re.escape(name)}\b", source) is not None


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--zip',type=Path,required=True); ap.add_argument('--iverilog',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    checks: dict[str,bool]={}; details={}
    with tempfile.TemporaryDirectory(prefix='n4v81_phase_') as raw:
        root=Path(raw)
        with zipfile.ZipFile(a.zip) as z:
            prefix=PACKAGE+'/'
            parser=root/'buffer_ack_phase_parser.py'; parser.write_bytes(z.read(prefix+'package_tools/buffer_ack_phase_parser.py'))
            observer=z.read(prefix+'tb_probe/buffer_ack_phase_observer.svh').decode()
            runner=z.read(prefix+'PREPARE_AND_RUN.sh').decode()
            fixture=z.read(prefix+'diagnostics/partial_exit_live/buffer_ack_phase_live.log').decode()
            manifest=json.loads(z.read(prefix+'package_manifest.json'))
        checks['exact_instance_bind']=f"bind {TARGET_INSTANCE} codex_probe_buf_ack_phase_target" in observer
        checks['five_live_phases']=all(f'codex_emit("{p}"' in observer for p in PHASES)
        checks['event_not_final_ring_input']='kind=EVENT boundary=buf_ack_phase_target' in observer and 'kind=RING_POST boundary=buf_ack_phase_target' not in observer
        checks['runner_compile_handoff']=runner.count('$package_root/tb_probe/buffer_ack_phase_observer.svh')==1
        checks['runner_runtime_gate']=runner.count('+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128')==2
        checks['target_sha']=sha(TARGET)==TARGET_SHA

        cases={
          'postnba_accept':(trace(POSTNBA={'bp':'3','gotten':'3'},HALF={'bp':'3','gotten':'3'},NEXT={'bp':'3','gotten':'3'}),'POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT',0),
          'half_next_accept':(trace(HALF={'bp':'3'},NEXT={'bp':'3','gotten':'3'}),'HALF_SETTLE_THEN_NEXT_EDGE_CONSUMER_ACCEPT',0),
          'consumer_stale':(trace(HALF={'bp':'3'},NEXT={'bp':'3'}),'SETTLED_PUBLIC_ACK_BUT_CONSUMER_STALE',0),
          'inactive_settle':(trace(INACTIVE={'bp':'3'},POSTNBA={'bp':'3','gotten':'3'},HALF={'bp':'3','gotten':'3'},NEXT={'bp':'3','gotten':'3'}),'POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT',0),
          'persistent':(trace(),'PERSISTENT_EQUATION_OR_COMPILED_SOURCE_MISMATCH',0),
          'operand_transition':(trace(HALF={'row':'2'},NEXT={'row':'2'}),'OPERAND_OR_EPOCH_TRANSITION',0),
        }
        for name,(rows,want,want_rc) in cases.items():
            rc,val=run_parser(parser,root,name,rows); checks[name]=rc==want_rc and val.get('decision')==want
        wrong=trace(); wrong=[x.replace(TARGET_INSTANCE,TARGET_INSTANCE.replace('[13]','[12]')) for x in wrong]
        rc,val=run_parser(parser,root,'wrong_instance',wrong); checks['wrong_instance_fails_closed']=rc!=0 and val.get('decision')=='NO_EXACT_TARGET_LIVE_EVENT'
        rc,val=run_parser(parser,root,'missing_phase',trace()[:-1]); checks['missing_phase_fails_closed']=rc!=0 and val.get('decision')=='INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE'
        rc,val=run_parser(parser,root,'duplicate_phase',trace()+[line(0,'ACTIVE')]); checks['duplicate_phase_fails_closed']=rc!=0 and val.get('decision')=='DUPLICATE_PHASE_FAIL_CLOSED'
        ring=[x.replace('kind=EVENT','kind=RING_POST') for x in trace()]
        rc,val=run_parser(parser,root,'final_ring_only',ring); checks['final_ring_only_fails_closed']=rc!=0 and val.get('decision')=='NO_EXACT_TARGET_LIVE_EVENT'
        rc,val=run_parser(parser,root,'exact_fixture',fixture.splitlines()); checks['tiny_live_fixture_passes']=rc==0 and val.get('complete_sequence_count')==1

        target_text=TARGET.read_text(encoding='utf-8')
        match=re.search(r"bind\s+([^\s]+)\s+codex_probe_buf_ack_phase_target\s+codex_probe_buf_ack_phase_target_inst\s*\((.*?)\)\s*;",observer,re.S)
        bind_map=dict(re.findall(r"\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\)",match.group(2))) if match else {}
        checks['actual_consumer_map_complete']=bool(bind_map) and all(declared(target_text,x) for x in bind_map.values())
        actual=next(iter(bind_map.values()),'')
        checks['deleted_actual_negative']=bool(actual) and not declared(target_text.replace(actual,'',1),actual)
        checks['typo_actual_negative']=bool(actual) and not declared(target_text,actual+'_TYPO')
        checks['wrong_sibling_negative']=not declared(target_text,'mse_buf_queue_bp_pre_sibling')
        obs=root/'obs.svh'; obs.write_text(observer,encoding='utf-8')
        target_cmd=[str(a.iverilog),'-g2012','-Wall','-I',str(INCLUDES),'-s','Buffer_AG_Idx_Queue','-o',str(root/'target.vvp'),str(FIFO),str(TARGET)]
        obs_cmd=[str(a.iverilog),'-g2012','-Wall','-I',str(INCLUDES),'-D','CODEX_SOURCE_BOUND_FOCUS','-s','codex_probe_buf_ack_phase_target','-o',str(root/'obs.vvp'),str(obs)]
        tr=subprocess.run(target_cmd,text=True,capture_output=True); orr=subprocess.run(obs_cmd,text=True,capture_output=True)
        checks['target_focused_compile']=tr.returncode==0; checks['observer_focused_compile']=orr.returncode==0
        details={'bind_actuals':bind_map,'target_compile':{'command':target_cmd,'exit':tr.returncode,'stderr':tr.stderr},'observer_compile':{'command':obs_cmd,'exit':orr.returncode,'stderr':orr.stderr},'manifest_proof':manifest.get('observer_public_surface_or_xmr_proof',{}).get('buffer_ack_phase_observer',{})}
    errors=[k for k,v in checks.items() if not v]
    report={'schema':'node0004-v81-exact-target-phase-validation-v1','pass':not errors,'errors':errors,'checks':checks,'details':details,'zip':{'path':str(a.zip),'bytes':a.zip.stat().st_size,'sha256':sha(a.zip)},'claim_boundary':'Exact target package-local HDL scope and live phase predicate traces only; no DUT, config, numeric, natural-terminal or formal-D claim.'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'pass':not errors,'errors':errors})); return 0 if not errors else 1

if __name__=='__main__': raise SystemExit(main())
