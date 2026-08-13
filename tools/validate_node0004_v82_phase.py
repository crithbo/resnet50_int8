from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.validate_node0004_v81_phase as base

base.PACKAGE = "r5_n4_hw_v82b_phase_collectfix"
WIDTHS = {"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7}

def exact_line(seq: int, phase: str, *, instance: str = base.TARGET_INSTANCE, full: str = "0", gotten: str = "0", bpmask: str = "3", bp: str = "0", row: str = "1") -> str:
    fields = {"wr":"1","full":full,"all":"1","valid":"3","same":"3","gotten":gotten,"keep":"3","bpmask":bpmask,"bp":bp,"mode":"2","row":row,"col":"1f","rowtag":"7f","coltag":"7f"}
    payload = 0
    for name, width in WIDTHS.items():
        payload = (payload << width) | int(fields[name], 16)
    return (
        f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={instance} time={100+seq} mask=1 "
        f"payload={payload:x} payload_known=1 payload_width=38 seq={seq} phase={phase} "
        + " ".join(f"{name}={fields[name]}" for name in WIDTHS)
    )

base.line = exact_line
if __name__ == "__main__":
    raise SystemExit(base.main())
