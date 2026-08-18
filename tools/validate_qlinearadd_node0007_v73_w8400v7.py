#!/usr/bin/env python3
"""Adapt the complete v72 exact validator to fresh v73 identity."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source_path = ROOT / "tools/validate_qlinearadd_node0007_v72_wall8400_v7.py"
    source = source_path.read_text(encoding="utf-8")
    source = source.replace("r5_qadd_n7_tailround_lanephase_v72_wall8400_v7", "r5_qadd_n7_tailround_lanephase_v73_w8400v7")
    source = source.replace("qlinearadd_node0007_tb_vcd_live_supervision_v72.py", "qlinearadd_node0007_tb_vcd_live_supervision_v73.py")
    source = source.replace("qlinearadd_node0007_tb_vcd_finalize_v72.py", "qlinearadd_node0007_tb_vcd_finalize_v73.py")
    source = source.replace("qadd-v72", "qadd-v73").replace("qadd_v72", "qadd_v73")
    namespace: dict[str, Any] = {"__name__": "qadd_v73_exact", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
