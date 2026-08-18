#!/usr/bin/env python3
"""Build fresh QAdd v80 after the v79 pre-ZIP admission request failure."""

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


v79 = load_module(ROOT / "tools/build_qlinearadd_node0007_v79_w15000_qprogress.py", "qadd_v80_build_v79")
build = v79.build
build.NEW = "r5_qadd_n7_tr_v80_w15kqf"
build.VERSION = "v80"
build.OUT = ROOT / "outputs/qadd_v80_w15kqf"
build.TREE = build.OUT / "b" / build.NEW
build.ZIP = build.OUT / f"{build.NEW}.zip"
build.REPEAT = build.OUT / f"{build.NEW}.repeat.zip"
build.NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v80.svh"
build.NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v80.py"
build.NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v80.py"
build.DISPATCH_DIR = ROOT / "outputs/mainline_qadd_v80_mode_authority"
build.DISPATCH_BINDING = build.DISPATCH_DIR / "server_family_dispatch_mode_binding.json"
build.MODE_AUTHORITY = build.DISPATCH_DIR / "server_family_diagnostic_mode_authority.json"
build.BUILD_FAILURE_AUDIT_SHA = "461e58e971496ba872681242443947901dbd4858e972c0f82d54db3e6cdbce31"


if __name__ == "__main__":
    raise SystemExit(build.main())
