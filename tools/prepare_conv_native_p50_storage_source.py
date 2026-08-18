#!/usr/bin/env python3
"""Prepare the exact flat source set consumed by the storage manager.

This script writes only under the p50 release output directory.  It does not
touch managed package storage, the storage index, any other family, or a
server.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p50_rdbufdrain"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release"
SOURCE = OUT / "storage_source"
ANALYSIS = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_"
    "r1786716730326805125_2394257"
)
TASK_RECORD = ROOT / (
    ".agents/task_records/"
    "20260814_conv_native_four_lane_p49_return_p50_rdbufdrain_storage_wait.md"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"storage source already exists: {SOURCE}")
    SOURCE.mkdir(parents=True)
    sources = {
        f"{PACKAGE_ID}.zip": OUT / f"{PACKAGE_ID}.zip",
        f"{PACKAGE_ID}.repeat.zip": OUT / f"{PACKAGE_ID}.repeat.zip",
        f"{PACKAGE_ID}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE_ID}.release_evidence.json": OUT / f"{PACKAGE_ID}.release_evidence.json",
        f"{PACKAGE_ID}.storage_wait_receipt.json": OUT / "storage_wait_receipt.json",
        f"{PACKAGE_ID}.final_zip_release_audit.json": OUT / "gates/final_zip_release_audit.json",
        f"{PACKAGE_ID}.first_fresh_validation.json": OUT / "gates/first_fresh_validation.json",
        f"{PACKAGE_ID}.tb_vcd_tree_v4.json": OUT / "gates/tb_vcd_tree_v4.json",
        f"{PACKAGE_ID}.mode_selector_tree_v4.json": OUT / "gates/mode_selector_tree_v4.json",
        f"{PACKAGE_ID}.mode_selector_zip_v4.json": OUT / "gates/mode_selector_zip_v4.json",
        f"{PACKAGE_ID}.hdl_lexical_tree_v4.json": OUT / "gates/hdl_lexical_tree_v4.json",
        f"{PACKAGE_ID}.hdl_lexical_zip_v4.json": OUT / "gates/hdl_lexical_zip_v4.json",
        f"{PACKAGE_ID}.runtime_preflight_v4.json": OUT / "gates/runtime_preflight_v4.json",
        f"{PACKAGE_ID}.runner_tree_v4.json": OUT / "gates/runner_tree_v4.json",
        f"{PACKAGE_ID}.runner_zip_v4.json": OUT / "gates/runner_zip_v4.json",
        f"{PACKAGE_ID}.post_sim_final_zip_v4.json": OUT / "gates/post_sim_final_zip_v4.json",
        f"{PACKAGE_ID}.package_release_admission.json": OUT / "gates/package_release_admission.json",
        f"{PACKAGE_ID}.package_release_receipt.json": OUT / "gates/package_release_receipt.json",
        f"{PACKAGE_ID}.current_shared_regression.json": OUT / "gates/current_shared_regression.json",
        f"{PACKAGE_ID}.p49_formal_return_analysis.json": ANALYSIS / "formal_return_analysis.json",
        f"{PACKAGE_ID}.p49_rule_gap_audit.json": ANALYSIS / "RULE_GAP_AUDIT.json",
        f"{PACKAGE_ID}.p49_config_rtl_direct_evidence_review.json": ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        f"{PACKAGE_ID}.task_record.md": TASK_RECORD,
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"storage source inputs absent: {missing}")
    records = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        if target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append({
            "name": name,
            "source": source.relative_to(ROOT).as_posix(),
            "bytes": target.stat().st_size,
            "sha256": sha(target),
        })
    zip_path = SOURCE / f"{PACKAGE_ID}.zip"
    sidecar = SOURCE / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(f"{sha(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({
        "name": sidecar.name,
        "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP",
        "bytes": sidecar.stat().st_size,
        "sha256": sha(sidecar),
    })
    manifest = {
        "schema": "conv-native-p50-storage-source-v1",
        "package_id": PACKAGE_ID,
        "family": "conv_native_four_lane",
        "members": sorted(records, key=lambda item: item["name"]),
        "managed_storage_touched": False,
        "server_actions_performed": [],
        "pass": True,
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"package_id": PACKAGE_ID, "members": len(records), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
