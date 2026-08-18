#!/usr/bin/env python3
"""Run the current-epoch first-fresh audit with the v64 failure-delta gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/audit_qlinearadd_node0007_v63_tb_vcd_first_fresh.py"
PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"


def main() -> int:
    spec = importlib.util.spec_from_file_location("qadd_v63_first_fresh_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import v63 first-fresh audit")
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE = PACKAGE
    module.EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437+qadd-failure-delta-v1"
    original_run = module.run

    def run(argv: list[str]) -> tuple[int, str, str]:
        translated = list(argv)
        for index, value in enumerate(translated):
            if value.endswith("prepare_qlinearadd_node0007_v63_runtime_layout_harness.py"):
                translated[index] = str(ROOT / "tools/prepare_qlinearadd_node0007_v64_runtime_layout_harness.py")
            elif value.endswith("validate_qlinearadd_node0007_v63_tb_vcd_hdl.py"):
                translated[index] = str(ROOT / "tools/validate_qlinearadd_node0007_v64_tbvcd_failure_delta.py")
            elif value.endswith("validate_qlinearadd_node0007_v63_tb_vcd_source_bound.py"):
                translated[index] = str(ROOT / "tools/validate_qlinearadd_node0007_v64_tbvcd_failure_delta.py")
                if "--source-root" in translated:
                    position = translated.index("--source-root")
                    del translated[position:position + 2]
        return original_run(translated)

    module.run = run
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
