#!/usr/bin/env python3
"""Aggregate all current exact-p48 release gates before storage publication."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p48_xmrscopefix"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"


def main() -> int:
    source = ROOT / "tools/audit_conv_native_p47_final_release.py"
    spec = importlib.util.spec_from_file_location("conv_native_p47_final_base", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load canonical final-release implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE_ID
    module.OLD_ID = "r5_n4_0cc_p47_tbvcdcone"
    module.OUT = OUT
    module.ZIP = OUT / f"{PACKAGE_ID}.zip"
    module.TREE = OUT / "build" / PACKAGE_ID
    base_status = module.main()
    report_path = OUT / "gates/final_zip_release_audit.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    repair_path = OUT / "gates/p47_xmr_scope_repair.json"
    repair = json.loads(repair_path.read_text(encoding="utf-8")) if repair_path.is_file() else {"pass": False}
    report["checks"]["p47_formal_xmr_scope_repair"] = repair.get("pass") is True
    if repair.get("pass") is not True:
        report["errors"].append("p47 formal-return XMRE scope repair gate failed or absent")
    report["pass"] = base_status == 0 and not report["errors"]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
