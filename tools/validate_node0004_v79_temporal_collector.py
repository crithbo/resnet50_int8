from __future__ import annotations
import argparse, sys, tempfile, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.validate_node0004_v77_temporal_collector as base

PACKAGE="r5_n4_hw_v79_buffer_ack_equation_diag"
TARGET=("tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
        "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
        "u_Buffer_AG_Idx_Queue.codex_probe_buf_ack_equation_witness_inst")

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--zip',required=True,type=Path); ap.add_argument('--v76-return',required=True,type=Path); ap.add_argument('--output',required=True,type=Path); a=ap.parse_args()
    extra=[
        f"CODEX_PROBE_V1 kind=ENABLED boundary=buf_ack_equation_witness instance={TARGET} role=internal_match_compute profile=HIGH_INFORMATION_CAUSAL_V1",
        f"CODEX_PROBE_V1 kind=SUMMARY boundary=buf_ack_equation_witness instance={TARGET} count=1 state=0 first=2446468 last=2446468 maxgap=0 sticky=1ff xor=1ff",
    ]
    names=['queue_write_accept','all_idx_matched','valid_masked_eq_3','same_masked_eq_3','gotten_eq_0','bp_keep_mask_eq_3','bp_mask_eq_3','output_bp_eq_3','mode_eq_2']
    extra += [f"CODEX_PROBE_V1 kind=CLASS boundary=buf_ack_equation_witness instance={TARGET} class={name} count=1 seen=1 progress={1 if i==0 else 0}" for i,name in enumerate(names)]
    extra += [f"CODEX_PROBE_V1 kind=RING_PROGRESS boundary=buf_ack_equation_witness instance={TARGET} time=2446468 mask=1ff payload=f seq=0"]
    with tempfile.TemporaryDirectory(prefix='n4v79_temporal_input_') as raw:
        temp=Path(raw)/'augmented.zip'
        with zipfile.ZipFile(a.v76_return) as src, zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data=src.read(info.filename)
                if info.filename.endswith('/runs/c0/sim.log'):
                    data += ('\n'.join(extra)+'\n').encode()
                dst.writestr(info,data)
        old=sys.argv; base.PACKAGE=PACKAGE
        try:
            sys.argv=['v79-temporal','--zip',str(a.zip),'--v76-return',str(temp),'--output',str(a.output)]
            return base.main()
        finally: sys.argv=old

if __name__=='__main__': raise SystemExit(main())
