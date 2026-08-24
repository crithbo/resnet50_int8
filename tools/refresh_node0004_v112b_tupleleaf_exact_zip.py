#!/usr/bin/env python3
"""Refresh the v112 manifest ordering and deterministic exact ZIP after gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.build_node0004_v112b_tupleleaf_tbvcd_successor as builder


def main() -> int:
    receipt = builder.load_json(builder.OUT / "build_receipt.json")
    predecessor_contract, published_receipt = builder.add_v111_provenance()
    current_contract_path = builder.TREE / builder.CONTRACT_REL
    current_contract = builder.load_json(current_contract_path)
    predecessor = current_contract["diagnostic_round"]["evolution"]["predecessor"]
    predecessor.update(
        {
            "contract_path": predecessor_contract["path"],
            "contract_sha256": predecessor_contract["sha256"],
            "published_pass_receipt_path": published_receipt["path"],
            "published_pass_receipt_sha256": published_receipt["sha256"],
        }
    )
    builder.write_json(current_contract_path, current_contract)
    receipt["patch_summary"]["actual_source_rebind"] = (
        builder.bind_catalog_to_v111_actual_compiled_sources()
    )
    builder.patch_return_contracts()
    builder.refresh_selector_and_manifest(receipt["patch_summary"])
    builder.deterministic_zip(builder.TREE, builder.ZIP_PATH)
    repeat = builder.OUT / f".{builder.NEW_ID}.refresh-repeat.zip"
    builder.deterministic_zip(builder.TREE, repeat)
    deterministic = builder.sha_file(builder.ZIP_PATH) == builder.sha_file(repeat)
    repeat.unlink()
    if not deterministic:
        raise RuntimeError("refreshed ZIP is not deterministic")
    receipt.update(
        {
            "zip_bytes": builder.ZIP_PATH.stat().st_size,
            "zip_sha256": builder.sha_file(builder.ZIP_PATH),
            "deterministic_rebuild": True,
            "manifest_order_refreshed": True,
        }
    )
    builder.write_json(builder.OUT / "build_receipt.json", receipt)
    print(json.dumps({"pass": True, "zip": receipt["zip"], "sha256": receipt["zip_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
