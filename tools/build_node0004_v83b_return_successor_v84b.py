from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.build_node0004_v83b_return_successor_v84 as base
base.INSTALL="r5_n4_hw_v84b_ack_inline_realtime_diag"
base.OUT=ROOT/"outputs/conv_node0004_v83b_return_v84b_successor"
if __name__=="__main__":raise SystemExit(base.main())
