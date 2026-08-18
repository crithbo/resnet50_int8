#!/usr/bin/env python3
"""Prepare the exact v96b flat source set for the package storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1"
ANALYSIS = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866"
TASK = ROOT / ".agents/task_records/20260815_conv_node0004_v95b_return_v96b_tbvcd_memtuple_local_gates_complete.md"
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

    sources = {
        f"{PACKAGE}.zip": OUT / f"{PACKAGE}.zip",
        f"{PACKAGE}.zip.sha256": OUT / f"{PACKAGE}.zip.sha256",
        f"{PACKAGE}.build_receipt.json": OUT / "build_receipt.json",
        f"{PACKAGE}.final_zip_audit.json": OUT / f"{PACKAGE}.final_zip_audit.json",
        f"{PACKAGE}.release_receipt.json": OUT / f"{PACKAGE}.release_receipt.json",
        f"{PACKAGE}.first_fresh_validation.json": OUT / "first_fresh_extra_audit/validation.json",
        f"{PACKAGE}.active_rule_registry.json": OUT / "gates/active_rule_registry.json",
        f"{PACKAGE}.focused_regression.json": OUT / "gates/focused_regression.json",
        f"{PACKAGE}.hdl_lexical.json": OUT / "gates/hdl_lexical.json",
        f"{PACKAGE}.mode_selector.json": OUT / "gates/mode_selector.json",
        f"{PACKAGE}.normalizer_arity.json": OUT / "gates/normalizer_arity.json",
        f"{PACKAGE}.package_release_admission.json": OUT / "gates/package_release_admission.json",
        f"{PACKAGE}.post_sim_return.json": OUT / "gates/post_sim_return.json",
        f"{PACKAGE}.python_source_compile.json": OUT / "gates/python_source_compile.json",
        f"{PACKAGE}.runner_resilience.json": OUT / "gates/runner_resilience.json",
        f"{PACKAGE}.runtime_preflight.json": OUT / "gates/runtime_preflight.json",
        f"{PACKAGE}.tb_vcd_contract.json": OUT / "gates/tb_vcd_contract.json",
        f"{PACKAGE}.release_admission_contract.json": OUT / "release_admission/contract.json",
        f"{PACKAGE}.precompile_failure_core.json": OUT / "release_admission/precompile_failure_core.json",
        f"{PACKAGE}.release_admission_receipt.json": OUT / "release_admission/release_receipt.json",
        f"{PACKAGE}.v95_return_analysis.json": ANALYSIS / "return_analysis.json",
        f"{PACKAGE}.v95_rule_gap_audit.json": ANALYSIS / "rule_gap_audit.json",
        f"{PACKAGE}.v95_dynamic_adjudication.json": ANALYSIS / "dynamic_adjudication.json",
        f"{PACKAGE}.v95_streaming_summary.json": ANALYSIS / "streaming_summary.json",
        f"{PACKAGE}.v95_analysis_state.json": ANALYSIS / "streaming/analysis_state.json",
        f"{PACKAGE}.v95_analysis_checkpoints.jsonl": ANALYSIS / "streaming/checkpoints.jsonl",
        f"{PACKAGE}.v95_incremental_report.md": ANALYSIS / "streaming/report.md",
        f"{PACKAGE}.task_record.md": TASK,
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v96 storage source inputs absent: {missing}")

    records = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        if sha256(target) != sha256(source):
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append(
            {
                "bytes": target.stat().st_size,
                "name": name,
                "sha256": sha256(target),
                "source": source.relative_to(ROOT).as_posix(),
            }
        )

    release_evidence = {
        "claim_boundary": "Authorized local storage publication only. v96 has not been uploaded or run; production compile, simulation, the exact leaf root, natural terminal, formal-D and E3-E5 remain unproven.",
        "conflicts": [],
        "family": FAMILY,
        "formal_previous_analysis": {
            "path": ANALYSIS.joinpath("return_analysis.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(ANALYSIS / "return_analysis.json"),
        },
        "gate_conjunction": {
            "current_first_fresh": True,
            "deterministic_final_zip": True,
            "focused_regression": "113/113 PASS",
            "lexical_and_full_hdl": True,
            "package_release_admission": True,
            "pass": True,
            "post_sim_and_six_exit": True,
            "runtime_v3": True,
            "source_bound_actual_rtl_and_config": True,
            "tb_vcd_bounded_causal_cone": True,
        },
        "intended_disposition": "pending",
        "owner_epoch": 2,
        "package_id": PACKAGE,
        "package_zip": {
            "bytes": (SOURCE / f"{PACKAGE}.zip").stat().st_size,
            "sha256": sha256(SOURCE / f"{PACKAGE}.zip"),
        },
        "previous_version_progress": "v95 production compile passed and target execution validated a one-transaction/32-unit Memory_AG metadata supply deficit while rebutting prepared-data over-generation.",
        "current_version_purpose": "Identify which of Memory_AG input0 KEEP, input1 BUFFER, input2 KEEP, same/gotten masking or split-FIFO/keep-release suppresses tuple ten.",
        "registry_epoch": 6,
        "role_id": "family.conv.serialized",
        "schema": "serialized-conv-v96b-storage-release-evidence-v1",
        "server_actions": [],
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_authority": "MAINLINE_STORAGE_SERIAL_RELEASE / family.conv.serialized only",
    }
    release_name = f"{PACKAGE}.storage_release.json"
    release_path = SOURCE / release_name
    release_path.write_bytes(canonical(release_evidence))
    records.append(
        {
            "bytes": release_path.stat().st_size,
            "name": release_name,
            "sha256": sha256(release_path),
            "source": "GENERATED_STORAGE_RELEASE_EVIDENCE",
        }
    )

    manifest = {
        "family": FAMILY,
        "managed_storage_touched": False,
        "members": sorted(records, key=lambda row: row["name"]),
        "package_id": PACKAGE,
        "pass": True,
        "schema": "serialized-conv-v96b-storage-source-v1",
        "server_actions": [],
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"members": len(records), "package_id": PACKAGE, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
