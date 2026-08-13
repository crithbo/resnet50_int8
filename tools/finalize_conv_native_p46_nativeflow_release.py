#!/usr/bin/env python3
"""Finalize the exact p46 native-flow ZIP and its publication receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p46_nativeflow"
SOURCE = "r5_n4_0cc_p45_obswide"
FAMILY = "conv_native_four_lane"
SOURCE_BYTES = 5_974_378
SOURCE_SHA = "fda80c374db7f906abc9e0dcbed768d64e58ab1e8351e90867abdb79e8d99e5c"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    release = args.release_dir.resolve()
    zip_path = release / f"{PACKAGE}.zip"
    repeat_zip = release / f"{PACKAGE}.repeat.zip"
    repeat_saved = release / "repeat_evidence/repeat.zip"
    if not zip_path.is_file():
        raise RuntimeError("exact final ZIP absent")
    if repeat_zip.is_file():
        if repeat_saved.exists():
            raise RuntimeError("both live and saved repeat ZIP exist")
        repeat_saved.parent.mkdir()
        shutil.move(str(repeat_zip), str(repeat_saved))
    if not repeat_saved.is_file():
        raise RuntimeError("deterministic repeat ZIP absent")
    if zip_path.stat().st_size != repeat_saved.stat().st_size or sha256(zip_path) != sha256(repeat_saved):
        raise RuntimeError("deterministic double build differs")

    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        safe = (
            archive.testzip() is None
            and roots == {PACKAGE}
            and len(names) == len(set(names))
            and all(
                not PurePosixPath(row.filename).is_absolute()
                and ".." not in PurePosixPath(row.filename).parts
                and "\\" not in row.filename
                and not stat.S_ISLNK(row.external_attr >> 16)
                for row in infos
            )
        )
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
        pointer = json.loads(archive.read(f"{PACKAGE}/TEST_PACKAGE_MANIFEST.json"))
        internal_receipt = f"{PACKAGE}/build_receipt.json" in names
    if not safe or internal_receipt:
        raise RuntimeError("exact ZIP integrity/root/safety or stale-receipt check failed")
    for value in (manifest, pointer):
        if value.get("status") != "PACKAGE_READY_NOT_RUN":
            raise RuntimeError("package release status differs")
        if value.get("server_actions_performed") != []:
            raise RuntimeError("package server-action receipt differs")
    if manifest.get("activation_epoch") != "runtime-preflight-native-flow-v1":
        raise RuntimeError("activation epoch differs")
    if manifest.get("dump_values") != {"DUMP_FSDB": 0, "DUMP_VCD": 0, "TB_DUMP_FSDB": 0}:
        raise RuntimeError("observer-only dump values differ")

    source_zip = STORAGE / "tested" / FAMILY / SOURCE / f"{SOURCE}.zip"
    if (
        not source_zip.is_file()
        or source_zip.stat().st_size != SOURCE_BYTES
        or sha256(source_zip) != SOURCE_SHA
    ):
        raise RuntimeError("tested p45 source identity differs")

    gate_names = (
        "compile_core_nativeflow",
        "first_fresh_validation",
        "hdl_full",
        "lexical_tree",
        "lexical_zip",
        "observer_zip",
        "post_sim_zip",
        "runner_tree",
        "runner_zip",
        "runtime_layout_zip",
        "runtime_preflight_zipbound",
        "source_bound_zip",
    )
    gate_rows: list[dict[str, Any]] = []
    for name in gate_names:
        path = release / "gates" / f"{name}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            raise RuntimeError(f"gate did not pass: {name}")
        gate_rows.append({"gate": name, **identity(path)})

    build_receipt = json.loads((release / "build_receipt.json").read_text(encoding="utf-8"))
    if build_receipt.get("pass") is not True or build_receipt.get("zip", {}).get("sha256") != sha256(zip_path):
        raise RuntimeError("build receipt does not bind exact ZIP")
    first_fresh_contract = release / "first_fresh_audit/contract.json"
    first_fresh = json.loads(first_fresh_contract.read_text(encoding="utf-8"))
    if first_fresh.get("package", {}).get("final_zip", {}).get("sha256") != sha256(zip_path):
        raise RuntimeError("first-fresh contract does not bind exact ZIP")
    profile_path = release / "server_package_build_profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("aggregate_prebuild", {}).get("coverage_complete") is not True:
        raise RuntimeError("shared build profile did not close")

    audit_cmd = [
        str(args.python),
        str(ROOT / "tools/manage_server_test_package_storage.py"),
        "audit",
        "--root",
        str(STORAGE),
    ]
    audit = subprocess.run(audit_cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if audit.returncode != 0:
        raise RuntimeError(f"pre-publication storage audit failed: {audit.stderr[-4096:]}")
    audit_value = json.loads(audit.stdout)
    if FAMILY in audit_value.get("pending_by_family", {}):
        raise RuntimeError("unexpected native pending package before publication")

    sidecar = release / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="ascii", newline="\n")
    copies = {
        release / "build_receipt.json": release / f"{PACKAGE}.build.json",
        release / "server_package_build_profile.json": release / f"{PACKAGE}.server_package_build_profile.json",
        release / "gates/compile_core_nativeflow.json": release / f"{PACKAGE}.compile_core_nativeflow.json",
        release / "gates/first_fresh_validation.json": release / f"{PACKAGE}.first_fresh_validation.json",
        release / "gates/lexical_zip.json": release / f"{PACKAGE}.package_local_hdl_lexical_final_zip.json",
        release / "gates/hdl_full.json": release / f"{PACKAGE}.package_local_hdl_full.json",
        release / "gates/runner_zip.json": release / f"{PACKAGE}.runner_return_resilience.json",
        release / "gates/runtime_preflight_zipbound.json": release / f"{PACKAGE}.runtime_preflight_noninterference.json",
        release / "gates/runtime_layout_zip.json": release / f"{PACKAGE}.runtime_layout.json",
        release / "gates/source_bound_zip.json": release / f"{PACKAGE}.source_bound_final_zip.json",
        release / "gates/post_sim_zip.json": release / f"{PACKAGE}.post_sim_return.json",
        release / "gates/observer_zip.json": release / f"{PACKAGE}.observer_only_final_zip.json",
        first_fresh_contract: release / f"{PACKAGE}.first_fresh_contract.json",
    }
    for source, target in copies.items():
        shutil.copyfile(source, target)

    receipt = {
        "schema": "conv-native-p46-native-flow-final-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": PACKAGE,
        "family": FAMILY,
        "activation_epoch": "runtime-preflight-native-flow-v1",
        "owner": {"role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6},
        "exact_zip": identity(zip_path),
        "deterministic_repeat": {**identity(repeat_saved), "byte_equal": True},
        "source_p45": {**identity(source_zip), "disposition": "tested", "unchanged": True},
        "previous_version_progress": "p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector valid/ready scalar false-negative; p45 broad observer-only localization failed production compile at unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf before simulation.",
        "current_version_purpose": "Run the corrected p42-equivalent MSE4 diagnostic through the native production path without provider preflight and capture exact native-flow evidence, including complete compile-core and observer simulation-exit return.",
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "gate_reports": gate_rows,
        "build_profile": identity(profile_path),
        "first_fresh_contract": identity(first_fresh_contract),
        "pre_storage_audit": {
            "pass": True,
            "counts": audit_value.get("counts"),
            "pending_by_family": audit_value.get("pending_by_family"),
        },
        "only_future_server_command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_formal_return": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
        "claim_boundary": "Local construction, exact-byte validation, synthetic runtime plumbing and storage publication only; no upload, lease, connection, production compile, DUT simulation, natural terminal, formal D, E3, E4 or E5 claim.",
        "server_actions_performed": [],
        "pass": True,
    }
    write_json(release / f"{PACKAGE}.final_zip_audit.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
