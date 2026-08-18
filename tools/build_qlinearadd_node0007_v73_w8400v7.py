#!/usr/bin/env python3
"""Build the fresh short-identity v73 after v72 path-budget rejection."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_module(ROOT / "tools/build_qlinearadd_node0007_v72_wall8400_v7.py", "qadd_v72_build_base")
build.NEW = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
build.VERSION = "v73"
build.OUT = ROOT / "outputs/qlinearadd_node0007_v73_release"
build.TREE = build.OUT / "build" / build.NEW
build.ZIP = build.OUT / f"{build.NEW}.zip"
build.REPEAT = build.OUT / f"{build.NEW}.repeat.zip"
build.NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v73.svh"
build.NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v73.py"
build.NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v73.py"


if __name__ == "__main__":
    raise SystemExit(build.main())
