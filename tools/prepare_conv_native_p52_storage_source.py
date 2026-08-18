#!/usr/bin/env python3
"""Prepare the exact flat p52 source set for the storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p52_memtupleleaf"
FAMILY = "conv_native_four_lane"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release"
SOURCE = OUT / "storage_source"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_return_analysis_r1786770085722684994_2783486"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"storage source already exists: {SOURCE}")
    SOURCE.mkdir(parents=True)
    gate_names = [
        "final_zip_release_audit.json",
        "first_fresh_validation_v5.json",
        "tb_vcd_tree_v5.json",
        "mode_selector_tree_v5.json",
        "mode_selector_zip_v5.json",
        "hdl_lexical_tree_v5.json",
        "hdl_lexical_zip_v5.json",
        "runtime_preflight_v5.json",
        "runner_tree_v5.json",
        "runner_zip_v5.json",
        "post_sim_final_zip_v5.json",
        "package_release_admission_contract.json",
        "package_release_admission.json",
        "package_release_receipt.json",
        "precompile_failure_core.json",
        "current_shared_regression_v5.json",
    ]
    sources: dict[str, Path] = {
        f"{PACKAGE}.zip": OUT / f"{PACKAGE}.zip",
        f"{PACKAGE}.repeat.zip": OUT / f"{PACKAGE}.repeat.zip",
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.release_evidence.json": OUT / f"{PACKAGE}.release_evidence.json",
        f"{PACKAGE}.mainline_package_ready_receipt.json": OUT / "mainline_package_ready_receipt.json",
        f"{PACKAGE}.p51_formal_return_analysis.json": ANALYSIS / "formal_return_analysis.json",
        f"{PACKAGE}.p51_rule_gap_audit.json": ANALYSIS / "RULE_GAP_AUDIT.json",
        f"{PACKAGE}.p51_direct_config_actual_rtl_evidence.json": ANALYSIS / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json",
        f"{PACKAGE}.p51_analysis_state.json": ANALYSIS / "analysis_state.json",
        f"{PACKAGE}.p51_analysis_checkpoints.jsonl": ANALYSIS / "checkpoints.jsonl",
        f"{PACKAGE}.p51_incremental_report.md": ANALYSIS / "report.md",
        f"{PACKAGE}.p51_dynamic_ledger.json": ANALYSIS / "dynamic_ledger.json",
        f"{PACKAGE}.p51_mainline_return_receipt.json": ANALYSIS / "mainline_return_receipt.json",
    }
    for gate_name in gate_names:
        sources[f"{PACKAGE}.{gate_name}"] = OUT / "gates" / gate_name
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"p52 storage source inputs absent: {missing}")

    records: list[dict[str, Any]] = []
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

    zip_path = SOURCE / f"{PACKAGE}.zip"
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({
        "name": sidecar.name,
        "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP",
        "bytes": sidecar.stat().st_size,
        "sha256": sha(sidecar),
    })
    manifest = {
        "schema": "conv-native-p52-storage-source-v1",
        "package_id": PACKAGE,
        "family": FAMILY,
        "members": sorted(records, key=lambda row: row["name"]),
        "managed_storage_touched": False,
        "server_actions_performed": [],
        "pass": True,
    }
    manifest_path = OUT / "storage_source_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    print(json.dumps({
        "package_id": PACKAGE,
        "members": len(records),
        "manifest": str(manifest_path),
        "pass": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
