#!/usr/bin/env python3
"""Refresh the v98 embedded identities and deterministic exact ZIP before gates."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
OUT = ROOT / "outputs/conv_node0004_v98b_lcdup_tuple10_release1"
TREE = OUT / "build" / PACKAGE


def load_builder():
    source = ROOT / "tools/build_node0004_v98b_lcdup_tuple10_successor.py"
    spec = importlib.util.spec_from_file_location("node0004_v98_builder", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    builder = load_builder()
    contract = TREE / "contracts/observer_only_wide_causal_contract.json"
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["observer_only_contract_sha256"] = builder.sha_file(contract)
    manifest["files"] = builder.file_rows()
    builder.write_json(manifest_path, manifest)
    builder.deterministic_zip()
    receipt = json.loads((OUT / "build_receipt.json").read_text(encoding="utf-8"))
    receipt["zip"] = {
        "path": builder.ZIP.relative_to(ROOT).as_posix(),
        "bytes": builder.ZIP.stat().st_size,
        "sha256": builder.sha_file(builder.ZIP),
    }
    receipt["observer_only_contract_sha256"] = builder.sha_file(contract)
    builder.write_json(OUT / "build_receipt.json", receipt)
    print(builder.ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
