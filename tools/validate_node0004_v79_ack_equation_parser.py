from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v79_buffer_ack_equation_diag"
INSTANCE = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.codex_probe_buf_ack_equation_witness_inst"


def run(parser: Path, root: Path, name: str, masks: list[int]) -> tuple[int, dict]:
    log = root / f"{name}.log"
    out = root / f"{name}.json"
    lines = [f"CODEX_PROBE_V1 kind=RING_PROGRESS boundary=buf_ack_equation_witness instance={INSTANCE} time={100+i} mask={mask:x} payload=0 seq={i}" for i, mask in enumerate(masks)]
    log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    done = subprocess.run([sys.executable, str(parser), "--log", str(log), "--output", str(out)], text=True, capture_output=True, check=False)
    return done.returncode, json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--zip',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    checks={}
    with tempfile.TemporaryDirectory(prefix='n4v79_eq_') as raw:
        root=Path(raw)
        with zipfile.ZipFile(a.zip) as z:
            parser=root/'buffer_input_ack_equation_parser.py'; parser.write_bytes(z.read(f'{PACKAGE}/package_tools/buffer_input_ack_equation_parser.py'))
        rc, value=run(parser,root,'full',[0x1ff]); checks['positive_full_equation']=rc==0 and value.get('decision')=='FULL_ACK_EQUATION_VISIBLE_AT_WRITE'
        rc, value=run(parser,root,'missing',[]); checks['negative_missing_write_fails_closed']=rc!=0 and value.get('decision')=='NO_TARGET_BUFFER_WRITE_WITNESS'
        _, value=run(parser,root,'bp_drop',[0x17f]); checks['bp_mask_without_output_distinguished']=value.get('decision')=='BP_MASK_PRESENT_BUT_OUTPUT_ACK_ZERO'
        _, value=run(parser,root,'keep',[0x11f]); checks['keep_suppression_distinguished']=value.get('decision')=='KEEP_MASK_SUPPRESSES_OUTPUT_ACK'
        _, value=run(parser,root,'upstream',[0x101]); checks['upstream_not_ready_distinguished']=value.get('decision')=='VALID_MATCH_GOTTEN_OR_MODE_NOT_READY_AT_WRITE'
        _, value=run(parser,root,'phase',[0x13f]); checks['phase_or_token_distinguished']=value.get('decision')=='WRITE_ACK_PHASE_OR_TOKEN_ALIGNMENT_UNRESOLVED'
        rc, value=run(parser,root,'held_level',[0x100]); checks['held_level_not_progress']=rc!=0 and value.get('decision')=='NO_TARGET_BUFFER_WRITE_WITNESS'
    errors=[k for k,v in checks.items() if not v]
    report={'schema':'node0004-v79-buffer-ack-equation-parser-validation-v1','pass':not errors,'errors':errors,'checks':checks,'candidate_count':6,'negative_count':6,'claim_boundary':'Synthetic exact parser/event-trace validation only; no DUT or numerical execution.'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(report,indent=2)); return 0 if not errors else 1


if __name__=='__main__': raise SystemExit(main())
