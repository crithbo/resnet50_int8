#!/usr/bin/env python3
"""Prepare p48's current aggregate build profile using the canonical p47 implementation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p48_xmrscopefix"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"


def main() -> int:
    source = ROOT / "tools/prepare_conv_native_p47_tbvcdcone_build_profile.py"
    spec = importlib.util.spec_from_file_location("conv_native_p47_profile_base", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical build-profile implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE_ID
    module.OUT = OUT
    module.TREE = OUT / "build" / PACKAGE_ID
    module.ZIP = OUT / f"{PACKAGE_ID}.zip"
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
