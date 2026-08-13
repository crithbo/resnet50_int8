#!/usr/bin/env python3
"""Run the v89 exact observer HDL gate against the fresh v90 identity."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v90b_nativeflow"


def main() -> int:
    source = ROOT / "tools/validate_node0004_v89b_observerwide_hdl.py"
    spec = importlib.util.spec_from_file_location("node0004_v89_hdl_gate", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE = PACKAGE_ID
    module.MEMBER = f"{PACKAGE_ID}/tb_probe/observer_only_wide_causal.svh"
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
