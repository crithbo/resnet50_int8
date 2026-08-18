#!/usr/bin/env python3
"""Prepare the exact flat GAP v73 source set for the package storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n71_gap_v73_sum_s2_tbvcd_cpath"
FAMILY = "gap_node0071"
OUT = ROOT / "outputs/gap_node0071_v73_sum_s2_cpath_cone"
DECISION = ROOT / "outputs/gap_node0071_config_bypass_continuation_decision"
SOURCE = OUT / "storage_source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"fresh storage source required: {SOURCE}")
    SOURCE.mkdir(parents=True)

    sources: dict[str, Path] = {
        f"{PACKAGE}.zip": OUT / "server_package_build" / f"{PACKAGE}.zip",
        f"{PACKAGE}.package_ready_not_run.json": OUT / "PACKAGE_READY_NOT_RUN_LOCAL_STAGING.json",
        f"{PACKAGE}.mainline_notification.json": OUT / "mainline_notification.json",
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.local_semantic_gate.json": OUT / "local_semantic_gate.json",
        f"{PACKAGE}.focused_regression_receipt.json": OUT / "focused_regression_receipt.json",
        f"{PACKAGE}.package_build_failure_rule_audit.json": OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        f"{PACKAGE}.python_compile_receipt.json": OUT / "python_compile_receipt.json",
        f"{PACKAGE}.release_admission_candidate_receipt.json": OUT / "release_admission_candidate_receipt.json",
        f"{PACKAGE}.config_bypass_continuation_decision.json": DECISION / "CONFIG_BYPASS_CONTINUATION_DECISION.json",
        f"{PACKAGE}.first_fresh_summary.json": OUT / "first_fresh_audit" / "summary.json",
    }
    for gate_name in (
        "active_rule_registry.json",
        "adaptive_v4_negative_controls.json",
        "deterministic_zip_recheck.json",
        "first_fresh_validation_after_v4_negatives.json",
        "frozen_surface.json",
        "hdl_lexical_zip.json",
        "local_gate_conjunction.json",
        "materialized_config.json",
        "mode_zip.json",
        "post_sim_zip.json",
        "release_admission.json",
        "runner_zip.json",
        "runtime_layout.json",
        "runtime_preflight.json",
        "tb_vcd_zip.json",
    ):
        sources[f"{PACKAGE}.{gate_name}"] = OUT / "gates" / gate_name

    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"GAP v73 storage source inputs absent: {missing}")

    records: list[dict[str, Any]] = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        source_sha = sha256(source)
        if sha256(target) != source_sha:
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append({
            "bytes": target.stat().st_size,
            "name": name,
            "sha256": source_sha,
            "source": source.relative_to(ROOT).as_posix(),
        })

    zip_path = SOURCE / f"{PACKAGE}.zip"
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    records.append({
        "bytes": sidecar.stat().st_size,
        "name": sidecar.name,
        "sha256": sha256(sidecar),
        "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP",
    })

    manifest = {
        "family": FAMILY,
        "managed_storage_touched": False,
        "members": sorted(records, key=lambda row: row["name"]),
        "package_id": PACKAGE,
        "pass": True,
        "schema": "gap-node0071-v73-storage-source-v1",
        "server_actions": [],
    }
    manifest_path = OUT / "storage_source_manifest.json"
    manifest_path.write_bytes(canonical(manifest))
    print(json.dumps({"members": len(records), "package_id": PACKAGE, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
