#!/usr/bin/env python3
"""Prepare the exact v66 source set consumed by the storage manager rotate."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
OUT = ROOT / "outputs/qlinearadd_node0007_v66_cfg42_release"
SOURCE = OUT / "storage_source"
TREE = OUT / "build" / PACKAGE


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"storage source already exists: {SOURCE}")
    release = OUT / f"{PACKAGE}.release_receipt.json"
    required_pass = [
        release,
        OUT / "build_receipt.json",
        OUT / "gates/final_zip_release_audit.json",
        OUT / "gates/config_lineage_exact.json",
        OUT / "gates/first_fresh_validation.json",
        OUT / "gates/package_release_admission.json",
        OUT / "gates/runtime_layout.json",
        OUT / "gates/storage_prepublication_wait.json",
    ]
    failed = [str(path) for path in required_pass if not path.is_file() or load(path).get("pass") is not True]
    if failed:
        raise RuntimeError(f"required release evidence absent or failed: {failed}")
    package_zip = OUT / f"{PACKAGE}.zip"
    repeat_zip = OUT / f"{PACKAGE}.repeat.zip"
    if not package_zip.is_file() or package_zip.read_bytes() != repeat_zip.read_bytes():
        raise RuntimeError("deterministic exact ZIP source differs")
    copies = {
        package_zip: f"{PACKAGE}.zip",
        repeat_zip: f"{PACKAGE}.repeat.zip",
        release: f"{PACKAGE}.release_receipt.json",
        OUT / "build_receipt.json": f"{PACKAGE}.build_receipt.json",
        OUT / "frozen_surface_receipt.json": f"{PACKAGE}.frozen_surface_receipt.json",
        OUT / "gates/final_zip_release_audit.json": f"{PACKAGE}.final_zip_release_audit.json",
        OUT / "gates/config_lineage_exact.json": f"{PACKAGE}.config_lineage_exact.json",
        OUT / "gates/first_fresh_validation.json": f"{PACKAGE}.first_fresh_validation.json",
        OUT / "gates/hdl_lexical_tree.json": f"{PACKAGE}.hdl_lexical_tree.json",
        OUT / "gates/hdl_lexical_zip.json": f"{PACKAGE}.hdl_lexical_zip.json",
        OUT / "gates/mode_selector_tree.json": f"{PACKAGE}.mode_selector_tree.json",
        OUT / "gates/mode_selector_zip.json": f"{PACKAGE}.mode_selector_zip.json",
        OUT / "gates/tb_vcd_tree.json": f"{PACKAGE}.tb_vcd_tree.json",
        OUT / "gates/tb_vcd_zip.json": f"{PACKAGE}.tb_vcd_zip.json",
        OUT / "gates/runner_tree.json": f"{PACKAGE}.runner_tree.json",
        OUT / "gates/runner_zip.json": f"{PACKAGE}.runner_zip.json",
        OUT / "gates/runtime_preflight.json": f"{PACKAGE}.runtime_preflight.json",
        OUT / "gates/runtime_layout.json": f"{PACKAGE}.runtime_layout.json",
        OUT / "gates/runtime_layout_harness.json": f"{PACKAGE}.runtime_layout_harness.json",
        OUT / "gates/post_sim.json": f"{PACKAGE}.post_sim.json",
        OUT / "gates/package_release_admission.json": f"{PACKAGE}.package_release_admission.json",
        OUT / "gates/package_release_admission_contract.json": f"{PACKAGE}.package_release_admission_contract.json",
        OUT / "gates/precompile_failure_core.json": f"{PACKAGE}.precompile_failure_core.json",
        OUT / "gates/storage_prepublication_wait.json": f"{PACKAGE}.storage_prepublication_wait.json",
        OUT / "first_fresh_audit/reports/full_hdl_source_bound.json": f"{PACKAGE}.full_hdl_source_bound.json",
        OUT / "first_fresh_audit/reports/source_bound_logger_collector_parser_roundtrip.json": f"{PACKAGE}.source_bound_roundtrip.json",
        TREE / "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json": f"{PACKAGE}.config_lineage_contract.json",
        TREE / "provenance/config_lineage/op_tail_round_4_2.json": f"{PACKAGE}.op_tail_round_4_2.json",
        ROOT / "outputs/qlinearadd_node0007_v65_early_config_rtl_readonly_review/early_config_rtl_readonly_review.json": f"{PACKAGE}.validated_stale_v65_lineage_review.json",
    }
    absent = [str(path) for path in copies if not path.is_file()]
    if absent:
        raise RuntimeError(f"storage source member absent: {absent}")
    SOURCE.mkdir(parents=True)
    rows = []
    for source, name in sorted(copies.items(), key=lambda item: item[1]):
        target = SOURCE / name
        shutil.copy2(source, target)
        if target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"storage source byte mismatch: {name}")
        rows.append({"name": name, "source": source.relative_to(ROOT).as_posix(), "bytes": target.stat().st_size, "sha256": sha(target)})
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(SOURCE / f'{PACKAGE}.zip')}  {PACKAGE}.zip\n", encoding="utf-8", newline="\n")
    rows.append({"name": sidecar.name, "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP", "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)})
    manifest = {
        "schema": "qadd-v66-config42-storage-source-v1",
        "package_id": PACKAGE,
        "family": "qlinearadd_node0007",
        "members": sorted(rows, key=lambda row: row["name"]),
        "deterministic_exact_zip": True,
        "validated_stale_v65_lineage_review_bound": True,
        "managed_storage_touched": False,
        "server_actions_performed": [],
        "pass": True,
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"package_id": PACKAGE, "member_count": len(rows), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
