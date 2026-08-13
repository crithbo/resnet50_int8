#!/usr/bin/env python3
"""Finalize exact p45 ZIP receipts without modifying package bytes."""

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
PACKAGE = "r5_n4_0cc_p45_obswide"
OLD = "r5_n4_0cc_p44_fsdbvq"
FAMILY = "conv_native_four_lane"
P44_BYTES = 5_997_161
P44_SHA = "97e3339800f463ebd4f3552996bc00cf5c7eb862b4affac5ec77a0ce2b22b621"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    release = args.release_dir.resolve()
    zip_path = release / f"{PACKAGE}.zip"
    repeat_zip = release / f"{PACKAGE}.repeat.zip"
    if not zip_path.is_file() or not repeat_zip.is_file():
        raise RuntimeError("exact ZIP or repeat ZIP absent")
    if identity(zip_path)["bytes"] != identity(repeat_zip)["bytes"] or sha(zip_path) != sha(repeat_zip):
        raise RuntimeError("deterministic double build differs")
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        safe = (
            archive.testzip() is None
            and roots == {PACKAGE}
            and len(names) == len(set(names))
            and all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
        )
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
        pointer = json.loads(archive.read(f"{PACKAGE}/TEST_PACKAGE_MANIFEST.json"))
    if not safe:
        raise RuntimeError("exact ZIP integrity/root/safety failed")
    if manifest.get("status") != "PACKAGE_READY_NOT_RUN" or pointer.get("status") != "PACKAGE_READY_NOT_RUN":
        raise RuntimeError("exact ZIP release status differs")
    if manifest.get("server_actions_performed") != [] or pointer.get("server_actions_performed") != []:
        raise RuntimeError("server action receipt differs")
    p44 = STORAGE / "pending" / f"{OLD}.zip"
    if not p44.is_file() or p44.stat().st_size != P44_BYTES or sha(p44) != P44_SHA:
        raise RuntimeError("p44 pending identity changed before publication")
    gate_names = (
        "lexical_tree", "runner_tree", "lexical_zip", "runner_zip", "source_bound_zip",
        "post_sim_zip", "observer_zip", "hdl_full", "first_fresh_validation",
    )
    gate_rows: list[dict[str, Any]] = []
    for name in gate_names:
        path = release / "gates" / f"{name}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            raise RuntimeError(f"gate did not pass: {name}")
        gate_rows.append({"gate": name, **identity(path)})
    first_fresh_contract = release / "first_fresh_audit/contract.json"
    first_fresh = json.loads(first_fresh_contract.read_text(encoding="utf-8"))
    if first_fresh.get("package", {}).get("final_zip", {}).get("sha256") != sha(zip_path):
        raise RuntimeError("first-fresh does not bind exact ZIP")
    audit_cmd = [str(args.python), str(ROOT / "tools/manage_server_test_package_storage.py"), "audit", "--root", str(STORAGE)]
    audit = subprocess.run(audit_cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    if audit.returncode != 0:
        raise RuntimeError(f"pre-publication storage audit failed: {audit.stderr[-4096:]}")
    audit_value = json.loads(audit.stdout)
    if audit_value.get("pending_by_family", {}).get(FAMILY) != [OLD]:
        raise RuntimeError("pre-publication native pending identity differs")
    sidecar = release / f"{PACKAGE}.zip.sha256"
    sidecar.write_text(f"{sha(zip_path)}  {zip_path.name}\n", encoding="ascii", newline="\n")
    copies = {
        release / "build" / PACKAGE / "build_receipt.json": release / f"{PACKAGE}.build.json",
        release / "gates" / "lexical_zip.json": release / f"{PACKAGE}.package_local_hdl_lexical_final_zip.json",
        release / "gates" / "runner_zip.json": release / f"{PACKAGE}.runner_return_resilience.json",
        release / "gates" / "source_bound_zip.json": release / f"{PACKAGE}.source_bound_final_zip.json",
        release / "gates" / "post_sim_zip.json": release / f"{PACKAGE}.post_sim_return.json",
        release / "gates" / "observer_zip.json": release / f"{PACKAGE}.observer_only_final_zip.json",
        release / "gates" / "hdl_full.json": release / f"{PACKAGE}.package_local_hdl_full.json",
        first_fresh_contract: release / f"{PACKAGE}.first_fresh_contract.json",
        release / "gates" / "first_fresh_validation.json": release / f"{PACKAGE}.first_fresh_validation.json",
    }
    for source, target in copies.items():
        shutil.copyfile(source, target)
    repeat_dir = release / "repeat_evidence"
    repeat_dir.mkdir()
    shutil.move(str(repeat_zip), str(repeat_dir / "repeat.zip"))
    receipt = {
        "schema": "conv-native-p45-observerwide-final-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": PACKAGE,
        "family": FAMILY,
        "activation_epoch": "observer-only-post-sim-conjunction-fix-v1",
        "base_epoch": "observer-only-wide-causal-v1",
        "owner": {"role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6},
        "exact_zip": identity(zip_path),
        "deterministic_repeat": {**identity(repeat_dir / "repeat.zip"), "byte_equal": True},
        "source_p44": {"path": p44.relative_to(ROOT).as_posix(), "bytes": P44_BYTES, "sha256": P44_SHA, "pending_unchanged_before_rotation": True},
        "previous_version_progress": "p41 passed production compile beyond the Datahub repair; p42 fixed the two-bit vector predicate; p43 stopped at time zero; p44 FSDB-v3 was built but never run.",
        "current_version_purpose": "Preserve the p42 vector predicate and MSE4 wdata/slice-finish target while returning broad unbounded source-bound actual-signal observer evidence in one run.",
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "dump_values": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "gate_reports": gate_rows,
        "first_fresh_contract": identity(first_fresh_contract),
        "pre_storage_audit": {"pass": True, "counts": audit_value.get("counts"), "pending_by_family": audit_value.get("pending_by_family")},
        "claim_boundary": "Local package construction and exact-byte validation only; no upload, lease, connection, compile, simulation, dynamic DUT, natural terminal, formal D, E3, E4 or E5 claim.",
        "server_actions_performed": [],
        "pass": True,
    }
    final_receipt = release / f"{PACKAGE}.final_zip_audit.json"
    write_json(final_receipt, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
