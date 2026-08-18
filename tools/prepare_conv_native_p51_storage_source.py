#!/usr/bin/env python3
"""Prepare the exact flat p51 source set for the storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p51_metaidxcone"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release"
SOURCE = OUT / "storage_source"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_r1786734260114876474_2596301"
TASK = ROOT / ".agents/task_records/20260815_conv_native_four_lane_p50_return_p51_metaidxcone_storage_wait.md"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"storage source already exists: {SOURCE}")
    SOURCE.mkdir(parents=True)
    sources = {
        f"{PACKAGE}.zip": OUT / f"{PACKAGE}.zip",
        f"{PACKAGE}.repeat.zip": OUT / f"{PACKAGE}.repeat.zip",
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.release_evidence.json": OUT / f"{PACKAGE}.release_evidence.json",
        f"{PACKAGE}.storage_wait_receipt.json": OUT / "storage_wait_receipt.json",
        f"{PACKAGE}.final_zip_release_audit.json": OUT / "gates/final_zip_release_audit.json",
        f"{PACKAGE}.first_fresh_validation.json": OUT / "gates/first_fresh_validation.json",
        f"{PACKAGE}.tb_vcd_tree_v4.json": OUT / "gates/tb_vcd_tree_v4.json",
        f"{PACKAGE}.mode_selector_tree_v4.json": OUT / "gates/mode_selector_tree_v4.json",
        f"{PACKAGE}.mode_selector_zip_v4.json": OUT / "gates/mode_selector_zip_v4.json",
        f"{PACKAGE}.hdl_lexical_tree_v4.json": OUT / "gates/hdl_lexical_tree_v4.json",
        f"{PACKAGE}.hdl_lexical_zip_v4.json": OUT / "gates/hdl_lexical_zip_v4.json",
        f"{PACKAGE}.runtime_preflight_v4.json": OUT / "gates/runtime_preflight_v4.json",
        f"{PACKAGE}.runner_tree_v4.json": OUT / "gates/runner_tree_v4.json",
        f"{PACKAGE}.runner_zip_v4.json": OUT / "gates/runner_zip_v4.json",
        f"{PACKAGE}.post_sim_final_zip_v4.json": OUT / "gates/post_sim_final_zip_v4.json",
        f"{PACKAGE}.package_release_admission.json": OUT / "gates/package_release_admission.json",
        f"{PACKAGE}.package_release_receipt.json": OUT / "gates/package_release_receipt.json",
        f"{PACKAGE}.current_shared_regression.json": OUT / "gates/current_shared_regression.json",
        f"{PACKAGE}.p50_formal_return_analysis.json": ANALYSIS / "formal_return_analysis.json",
        f"{PACKAGE}.p50_rule_gap_audit.json": ANALYSIS / "RULE_GAP_AUDIT.json",
        f"{PACKAGE}.p50_config_rtl_direct_evidence_review.json": ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json",
        f"{PACKAGE}.p50_analysis_state.json": ANALYSIS / "analysis_state.json",
        f"{PACKAGE}.p50_analysis_checkpoints.jsonl": ANALYSIS / "checkpoints.jsonl",
        f"{PACKAGE}.p50_incremental_report.md": ANALYSIS / "report.md",
        f"{PACKAGE}.p50_causal_window_evidence.json": ANALYSIS / "causal_window_evidence.json",
        f"{PACKAGE}.task_record.md": TASK,
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"p51 storage source inputs absent: {missing}")
    records = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        if target.read_bytes() != source.read_bytes():
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append({"name": name, "source": source.relative_to(ROOT).as_posix(), "bytes": target.stat().st_size, "sha256": sha(target)})
    zip_path = SOURCE / f"{PACKAGE}.zip"
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({"name": sidecar.name, "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP", "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)})
    manifest = {
        "schema": "conv-native-p51-storage-source-v1", "package_id": PACKAGE,
        "family": "conv_native_four_lane", "members": sorted(records, key=lambda row: row["name"]),
        "managed_storage_touched": False, "server_actions_performed": [], "pass": True,
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"package_id": PACKAGE, "members": len(records), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
