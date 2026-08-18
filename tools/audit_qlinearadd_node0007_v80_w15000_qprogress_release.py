#!/usr/bin/env python3
"""Run the independent-ready local release audit for QAdd v80."""

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


audit = load_module(ROOT / "tools/audit_qlinearadd_node0007_v78_w15000_procfs_release.py", "qadd_v80_release_audit")
audit.PACKAGE = "r5_qadd_n7_tr_v80_w15kqf"
audit.OUT = ROOT / "outputs/qadd_v80_w15kqf"
audit.TREE = audit.OUT / "b" / audit.PACKAGE
audit.ZIP = audit.OUT / f"{audit.PACKAGE}.zip"
audit.REPEAT = audit.OUT / f"{audit.PACKAGE}.repeat.zip"
audit.GATES = audit.OUT / "gates"
audit.REPORTS = audit.OUT / "first_fresh_audit/reports"
audit.EPOCH = "qadd-source-bound-wall-15000-v1+family-dispatch-mode-binding-v1+qadd-tbvcd-semantic8-validator-coherence+selected-absolute-coherence+qualified-progress-final-conjunction"


if __name__ == "__main__":
    raise SystemExit(audit.main())
