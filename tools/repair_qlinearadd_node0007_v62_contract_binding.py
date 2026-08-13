#!/usr/bin/env python3
"""Refresh the identity-affine v62 observer-contract manifest receipt."""

from __future__ import annotations

import json

import build_qlinearadd_node0007_v62_nativeflow as build


def main() -> int:
    manifest_path = build.TREE / "TEST_PACKAGE_MANIFEST.json"
    contract_path = build.TREE / "contracts/server_observer_only_wide_causal_contract.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = build.digest(contract_path)
    if manifest.get("observer_only_contract_sha256") == expected:
        raise RuntimeError("observer contract receipt is already current")
    manifest["observer_only_contract_sha256"] = expected
    manifest["files"] = build.file_map(build.TREE)
    build.write_json(manifest_path, manifest)
    build.deterministic_zip(build.TREE, build.ZIP)
    recheck = build.exact_zip_recheck(build.TREE, build.ZIP)
    build.ZIP.with_name(build.ZIP.name + ".sha256").write_text(
        f"{build.digest(build.ZIP)}  {build.ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    receipt_path = build.BUILD / "build_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["zip"] = build.identity(build.ZIP)
    receipt["exact_final_zip_recheck"] = recheck
    receipt["observer_contract_manifest_binding_repaired"] = True
    build.write_json(receipt_path, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
