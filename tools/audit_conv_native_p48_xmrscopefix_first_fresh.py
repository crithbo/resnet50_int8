#!/usr/bin/env python3
"""Run the current p47 semantic first-fresh suite against exact p48 bytes."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p48_xmrscopefix"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"


def main() -> int:
    source = ROOT / "tools/audit_conv_native_p47_tbvcdcone_first_fresh.py"
    spec = importlib.util.spec_from_file_location("conv_native_p47_first_fresh_base", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical first-fresh implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE_ID
    module.OUT = OUT
    module.ZIP = OUT / f"{PACKAGE_ID}.zip"
    module.REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
    module.P46_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.zip"
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
