#!/usr/bin/env python3
"""Prepare the exact v68 cfg42 tick-safe source set for managed storage.

This script writes release-side receipts only.  It verifies but never mutates the
managed package-storage tree; the storage manager remains the sole storage writer.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
PREDECESSOR = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
OUT = ROOT / "outputs/qlinearadd_node0007_v68_cfg42_tick_release"
SOURCE = OUT / "storage_source"
TREE = OUT / "build" / PACKAGE
ANALYSIS_DIR = ROOT / "outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_qadd_n7_tailround_lanephase_v67_cfg42_tg_"
    r"r1786793338560402996_2911236_return.zip"
)
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORAGE / "PACKAGE_STORAGE_INDEX.json"
OTHER_PENDING = {
    "conv_native_four_lane": "r5_n4_0cc_p52_memtupleleaf",
    "conv_serialized_node0004": "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def io_path(path: Path) -> Path:
    """Return a Windows extended-length spelling for long storage members."""
    absolute = path.resolve()
    if len(str(absolute)) >= 248 and not str(absolute).startswith("\\\\?\\"):
        return Path("\\\\?\\" + str(absolute))
    return absolute


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def pending_snapshot(index: dict[str, Any]) -> dict[str, Any]:
    packages = [row for row in index.get("packages", []) if row.get("disposition") == "pending"]
    selected = []
    for row in packages:
        if row.get("family") not in (*OTHER_PENDING.keys(), "qlinearadd_node0007"):
            continue
        files = sorted(
            (
                {
                    "relative_path": item["relative_path"],
                    "bytes": item["bytes"],
                    "sha256": item["sha256"],
                }
                for item in row.get("files", [])
            ),
            key=lambda item: item["relative_path"],
        )
        for item in files:
            physical = STORAGE / item["relative_path"]
            physical_io = io_path(physical)
            if not physical_io.is_file():
                raise RuntimeError(f"indexed pending member absent: {physical}")
            if physical_io.stat().st_size != item["bytes"] or sha(physical_io) != item["sha256"]:
                raise RuntimeError(f"indexed pending member differs: {physical}")
        selected.append(
            {
                "family": row["family"],
                "package_base": row["package_base"],
                "file_count": len(files),
                "files": files,
                "exact_set_digest": hashlib.sha256(canonical(files)).hexdigest(),
            }
        )
    selected.sort(key=lambda row: row["family"])
    expected = {
        "conv_native_four_lane": OTHER_PENDING["conv_native_four_lane"],
        "conv_serialized_node0004": OTHER_PENDING["conv_serialized_node0004"],
        "qlinearadd_node0007": PREDECESSOR,
    }
    actual = {row["family"]: row["package_base"] for row in selected}
    if actual != expected:
        raise RuntimeError(f"pending exact set changed: expected={expected!r} actual={actual!r}")
    return {"pending_exact_set": selected, "pending_by_family": actual}


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"storage source already exists: {SOURCE}")

    index = load(INDEX)
    if index.get("pass") is not True or index.get("counts") != {
        "pending": 3,
        "superseded": 24,
        "tested": 49,
    }:
        raise RuntimeError(f"unexpected pre-transaction storage index: {index.get('counts')!r}")
    snapshot = {
        "schema": "qadd-v68-managed-storage-pretransaction-snapshot-v1",
        "index": identity(INDEX),
        "counts": index["counts"],
        **pending_snapshot(index),
        "pass": True,
    }
    (OUT / "storage_pretransaction_snapshot.json").write_bytes(canonical(snapshot))

    if not RETURN_ZIP.is_file():
        raise RuntimeError(f"exact formal return absent: {RETURN_ZIP}")
    return_id = identity(RETURN_ZIP)
    if return_id["bytes"] != 131087 or return_id["sha256"] != (
        "484fe4cad1e4b18db1c541eafe497720720465d38ac54e2f2c35d771902897b8"
    ):
        raise RuntimeError(f"exact formal return differs: {return_id!r}")

    analysis = ANALYSIS_DIR / "formal_return_analysis.json"
    audit = ANALYSIS_DIR / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    disposition = ANALYSIS_DIR / "RULE_AUDIT_DISPOSITION.json"
    analysis_value = load(analysis)
    if analysis_value.get("pass") is not True or analysis_value.get("package_id") != PREDECESSOR:
        raise RuntimeError("v67 formal analysis is not the completed exact predecessor analysis")
    consumption = {
        "schema": "qadd-v67-exact-formal-return-consumption-receipt-v1",
        "family": "qlinearadd_node0007",
        "package_id": PREDECESSOR,
        "return": return_id,
        "formal_analysis": identity(analysis),
        "package_build_failure_rule_audit": identity(audit),
        "rule_audit_disposition": identity(disposition),
        "execution_id": analysis_value.get("execution_id"),
        "attempt_id": analysis_value.get("attempt_id"),
        "return_disposition": analysis_value["integrity"]["return_disposition"],
        "compile_exit": analysis_value["production"]["compile_exit"],
        "simulation_started": analysis_value["production"]["simulation_started"],
        "simulation_exit": analysis_value["production"]["simulation_exit"],
        "target_entry_observed": analysis_value["production"]["target_entry_observed"],
        "first_divergence": analysis_value["first_divergence"],
        "claim_boundary": analysis_value["claim_boundary"],
        "storage_disposition": "tested",
        "server_actions_performed": [],
        "pass": True,
    }
    consumption_path = ANALYSIS_DIR / "formal_return_consumption_receipt.json"
    consumption_path.write_bytes(canonical(consumption))

    package_zip = OUT / f"{PACKAGE}.zip"
    repeat_zip = OUT / f"{PACKAGE}.repeat.zip"
    release = OUT / f"{PACKAGE}.release_receipt.json"
    required_pass = [
        release,
        OUT / "build_receipt.json",
        OUT / "gates/final_zip_release_audit.json",
        OUT / "gates/first_fresh_validation.json",
        OUT / "gates/package_release_admission.json",
        OUT / "gates/runtime_layout.json",
        OUT / "gates/storage_prepublication_wait.json",
        OUT / "gates/target_capture_exact.json",
        OUT / "gates/v68_exact.json",
    ]
    failed = [str(path) for path in required_pass if not path.is_file() or load(path).get("pass") is not True]
    if failed:
        raise RuntimeError(f"required release evidence absent or failed: {failed}")
    if not package_zip.is_file() or package_zip.read_bytes() != repeat_zip.read_bytes():
        raise RuntimeError("deterministic exact ZIP source differs")

    copies = {
        package_zip: f"{PACKAGE}.zip",
        repeat_zip: f"{PACKAGE}.repeat.zip",
        release: f"{PACKAGE}.release_receipt.json",
        OUT / "build_receipt.json": f"{PACKAGE}.build_receipt.json",
        OUT / "frozen_surface_receipt.json": f"{PACKAGE}.frozen_surface_receipt.json",
        OUT / "gates/final_zip_release_audit.json": f"{PACKAGE}.final_zip_release_audit.json",
        OUT / "gates/first_fresh_validation.json": f"{PACKAGE}.first_fresh_validation.json",
        OUT / "gates/hdl_lexical_tree.json": f"{PACKAGE}.hdl_lexical_tree.json",
        OUT / "gates/hdl_lexical_zip.json": f"{PACKAGE}.hdl_lexical_zip.json",
        OUT / "gates/mode_selector_tree.json": f"{PACKAGE}.mode_selector_tree.json",
        OUT / "gates/mode_selector_zip.json": f"{PACKAGE}.mode_selector_zip.json",
        OUT / "gates/tb_vcd_tree.json": f"{PACKAGE}.tb_vcd_tree.json",
        OUT / "gates/tb_vcd_zip.json": f"{PACKAGE}.tb_vcd_zip.json",
        OUT / "gates/target_capture_exact.json": f"{PACKAGE}.target_capture_exact.json",
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
        OUT / "gates/v68_exact.json": f"{PACKAGE}.v68_exact.json",
        OUT / "first_fresh_audit/reports/full_hdl_source_bound.json": f"{PACKAGE}.full_hdl_source_bound.json",
        OUT / "first_fresh_audit/reports/source_bound_logger_collector_parser_roundtrip.json": f"{PACKAGE}.source_bound_roundtrip.json",
        OUT / "first_fresh_audit/reports/candidate_discrimination_matrix.json": f"{PACKAGE}.candidate_matrix.json",
        TREE / "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json": f"{PACKAGE}.config_lineage_contract.json",
        TREE / "provenance/config_lineage/op_tail_round_4_2.json": f"{PACKAGE}.op_tail_round_4_2.json",
        analysis: f"{PACKAGE}.predecessor_v67_formal_analysis.json",
        audit: f"{PACKAGE}.predecessor_v67_package_build_failure_rule_audit.json",
        disposition: f"{PACKAGE}.predecessor_v67_rule_audit_disposition.json",
        consumption_path: f"{PACKAGE}.predecessor_v67_formal_return_consumption_receipt.json",
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
        rows.append({"name": name, "source": identity(source)["path"], **identity(target)})
    sidecar = SOURCE / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(SOURCE / f'{PACKAGE}.zip')}  {PACKAGE}.zip\n", encoding="utf-8", newline="\n")
    rows.append({"name": sidecar.name, "source": "GENERATED_FROM_EXACT_STORAGE_SOURCE_ZIP", **identity(sidecar)})
    manifest = {
        "schema": "qadd-v68-cfg42-tick-safe-storage-source-v1",
        "package_id": PACKAGE,
        "family": "qlinearadd_node0007",
        "members": sorted(rows, key=lambda row: row["name"]),
        "semantic_epoch": "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3",
        "deterministic_exact_zip": True,
        "formal_return_consumption_receipt": identity(consumption_path),
        "managed_storage_touched": False,
        "server_actions_performed": [],
        "pass": True,
    }
    (OUT / "storage_source_manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({"package_id": PACKAGE, "member_count": len(rows), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
