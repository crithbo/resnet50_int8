#!/usr/bin/env python3
"""Adapt every current v72 release gate to fresh short-identity v73."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source_path = ROOT / "tools/audit_qlinearadd_node0007_v72_wall8400_v7_release.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = (
        ("r5_qadd_n7_tailround_lanephase_v72_wall8400_v7", "r5_qadd_n7_tailround_lanephase_v73_w8400v7"),
        ("outputs/qlinearadd_node0007_v72_release", "outputs/qlinearadd_node0007_v73_release"),
        ("validate_qlinearadd_node0007_v72_wall8400_v7.py", "validate_qlinearadd_node0007_v73_w8400v7.py"),
        ("qlinearadd_node0007_tb_vcd_causal_cone_v72.svh", "qlinearadd_node0007_tb_vcd_causal_cone_v73.svh"),
        ("qlinearadd_node0007_tb_vcd_live_supervision_v72.py", "qlinearadd_node0007_tb_vcd_live_supervision_v73.py"),
        ("qlinearadd_node0007_tb_vcd_finalize_v72.py", "qlinearadd_node0007_tb_vcd_finalize_v73.py"),
        ("codex_qadd_tb_vcd_causal_cone_v72", "codex_qadd_tb_vcd_causal_cone_v73"),
        ("qadd-v72", "qadd-v73"),
        ("qadd_v72", "qadd_v73"),
        ("QAdd v72", "QAdd v73"),
        ("final_release_conjunction_v72.json", "final_release_conjunction_v73.json"),
    )
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v72 release adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v73_release_audit", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
