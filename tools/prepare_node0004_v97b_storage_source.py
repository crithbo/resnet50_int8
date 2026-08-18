#!/usr/bin/env python3
"""Prepare the exact v97b flat source set for the package storage manager."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1"
ANALYSIS = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_return_r1786770065727401255_2781777"
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
        f"{PACKAGE}.release_receipt.json": OUT / "release_receipt.json",
        f"{PACKAGE}.task_record.md": OUT / "formal_task_record.md",
        f"{PACKAGE}.final_zip_release_audit.json": OUT / "gates/final_zip_release_audit.json",
        f"{PACKAGE}.first_fresh_validation.json": OUT / "first_fresh_extra_audit/validation.json",
        f"{PACKAGE}.active_rule_registry.json": OUT / "gates/active_rule_registry.json",
        f"{PACKAGE}.active_rule_registry_recheck.json": OUT / "gates/active_rule_registry_recheck.json",
        f"{PACKAGE}.hdl_lexical.json": OUT / "gates/hdl_lexical.json",
        f"{PACKAGE}.mode_selector.json": OUT / "gates/mode_selector.json",
        f"{PACKAGE}.normalizer_arity.json": OUT / "gates/normalizer_arity.json",
        f"{PACKAGE}.package_release_admission.json": OUT / "gates/package_release_admission.json",
        f"{PACKAGE}.post_sim_return.json": OUT / "gates/post_sim_return.json",
        f"{PACKAGE}.runner_resilience.json": OUT / "gates/runner_resilience.json",
        f"{PACKAGE}.runtime_preflight.json": OUT / "gates/runtime_preflight.json",
        f"{PACKAGE}.tb_vcd_contract.json": OUT / "gates/tb_vcd_contract.json",
        f"{PACKAGE}.v96_predecessor_contract_validation.json": OUT / "gates/v96_predecessor_contract_validation.json",
        f"{PACKAGE}.release_admission_contract.json": OUT / "release_admission/contract.json",
        f"{PACKAGE}.precompile_failure_core.json": OUT / "release_admission/precompile_failure_core.json",
        f"{PACKAGE}.release_admission_receipt.json": OUT / "release_admission/release_receipt.json",
        f"{PACKAGE}.v96_return_analysis.json": ANALYSIS / "return_analysis.json",
        f"{PACKAGE}.v96_rule_disposition.json": ANALYSIS / "rule_disposition.json",
        f"{PACKAGE}.v96_build_failure_audit.json": ANALYSIS / "package_build_failure_rule_audit_applicability.json",
        f"{PACKAGE}.v96_streaming_summary.json": ANALYSIS / "streaming_summary.json",
        f"{PACKAGE}.v96_analysis_state.json": ANALYSIS / "streaming/analysis_state.json",
        f"{PACKAGE}.v96_analysis_checkpoints.jsonl": ANALYSIS / "streaming/checkpoints.jsonl",
        f"{PACKAGE}.v96_incremental_report.md": ANALYSIS / "streaming/report.md",
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"v97 storage source inputs absent: {missing}")

    records = []
    for name, source in sorted(sources.items()):
        target = SOURCE / name
        shutil.copyfile(source, target)
        source_sha = sha256(source)
        if sha256(target) != source_sha:
            raise RuntimeError(f"storage source byte mismatch: {name}")
        records.append(
            {
                "bytes": target.stat().st_size,
                "name": name,
                "sha256": source_sha,
                "source": source.relative_to(ROOT).as_posix(),
            }
        )

    release_evidence = {
        "claim_boundary": "Authorized local storage publication only. v97 has not been uploaded or run; production compile, simulation, tuple-leaf dynamics, natural terminal, formal-D and E3-E5 remain unproven.",
        "conflicts": [],
        "family": FAMILY,
        "formal_previous_analysis": {
            "path": ANALYSIS.joinpath("return_analysis.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(ANALYSIS / "return_analysis.json"),
        },
        "gate_conjunction": {
            "current_first_fresh": True,
            "deterministic_final_zip": True,
            "lexical_and_full_hdl": True,
            "package_release_admission": True,
            "pass": True,
            "post_sim_and_six_exit": True,
            "runtime_semantic_v5": True,
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
        "previous_version_progress": "v96 formal return reached package pre-simulation compile and failed on 53 duplicated package-local Memory_AG XMR hierarchy identities; simulation did not start.",
        "current_version_purpose": "Correct the 53 duplicated Memory_AG probe identities one-for-one while preserving the v95 metadata/data tuple diagnostic and semantic-v5 runtime contract.",
        "registry_epoch": 6,
        "role_id": "family.conv.serialized",
        "schema": "serialized-conv-v97b-storage-release-evidence-v1",
        "server_actions": [],
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_authority": "MAINLINE SOLE STORAGE-WRITER RELEASE / family.conv.serialized",
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
        "schema": "serialized-conv-v97b-storage-source-v1",
        "server_actions": [],
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"members": len(records), "package_id": PACKAGE, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
