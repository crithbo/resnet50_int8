#!/usr/bin/env python3
"""Recompute v64 identity-dependent path budgets and rebuild exact ZIP."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOL = ROOT / "tools/build_qlinearadd_node0007_v64_tbvcd_failure_fix.py"
BASE_TOOL = ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py"
OUT = ROOT / "outputs/qlinearadd_node0007_v64_tb_vcd_fix_release"
PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / "build" / f"{PACKAGE}.zip"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    current = load(BUILD_TOOL, "qadd_v64_build_repair")
    base = load(BASE_TOOL, "qadd_v63_build_helpers")
    current.repair_path_budget(base, TREE)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.files_map(TREE)
    base.write_json(manifest_path, manifest)
    base.deterministic_zip(TREE, ZIP)
    recheck = base.zip_recheck(TREE, ZIP)
    ZIP.with_name(ZIP.name + ".sha256").write_text(
        f"{base.digest(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n"
    )
    receipt_path = OUT / "build/build_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["zip"] = base.identity(ZIP)
    receipt["exact_final_zip_recheck"] = recheck
    receipt["identity_path_budget_recomputed"] = True
    base.write_json(receipt_path, receipt)
    print(json.dumps({"pass": True, "package_id": PACKAGE}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
