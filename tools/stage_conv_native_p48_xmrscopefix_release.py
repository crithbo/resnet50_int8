#!/usr/bin/env python3
"""Stage exact p48 ZIP and gate receipts for atomic family storage rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p48_xmrscopefix"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"
SOURCE = OUT / "publish"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824/formal_return_analysis.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    if SOURCE.exists():
        raise RuntimeError(f"refusing to overwrite staged publication: {SOURCE}")
    final = json.loads((OUT / "gates/final_zip_release_audit.json").read_text(encoding="utf-8"))
    if final.get("pass") is not True:
        raise RuntimeError("final release audit did not pass")
    SOURCE.mkdir(parents=True)
    mapping = {
        f"{PACKAGE}.zip": OUT / f"{PACKAGE}.zip",
        f"{PACKAGE}.build.json": OUT / "build_receipt.json",
        f"{PACKAGE}.final_zip_audit.json": OUT / "gates/final_zip_release_audit.json",
        f"{PACKAGE}.first_fresh_contract.json": OUT / "first_fresh_audit/contract.json",
        f"{PACKAGE}.first_fresh_validation.json": OUT / "gates/first_fresh_validation.json",
        f"{PACKAGE}.full_hdl_source_bound.json": OUT / "gates/full_hdl_source_bound.json",
        f"{PACKAGE}.hdl_lexical_final_zip.json": OUT / "gates/hdl_lexical_zip.json",
        f"{PACKAGE}.mode_selector_final_zip.json": OUT / "gates/mode_selector_zip.json",
        f"{PACKAGE}.p47_xmr_scope_repair.json": OUT / "gates/p47_xmr_scope_repair.json",
        f"{PACKAGE}.post_sim_return.json": OUT / "gates/post_sim_final_zip.json",
        f"{PACKAGE}.runner_final_zip.json": OUT / "gates/runner_zip.json",
        f"{PACKAGE}.runtime_layout.json": OUT / "gates/runtime_layout.json",
        f"{PACKAGE}.runtime_preflight.json": OUT / "gates/native_preflight.json",
        f"{PACKAGE}.runtime_six_exit.json": OUT / "gates/runtime_six_exit.json",
        f"{PACKAGE}.server_package_build_profile.json": OUT / "server_package_build_profile.json",
        f"{PACKAGE}.streaming_retention.json": OUT / "gates/streaming_retention.json",
        f"{PACKAGE}.tb_vcd_final_zip.json": OUT / "gates/tb_vcd_final_zip.json",
    }
    for name, source in mapping.items():
        if not source.is_file():
            raise RuntimeError(f"missing publication receipt: {source}")
        shutil.copy2(source, SOURCE / name)
    zip_path = SOURCE / f"{PACKAGE}.zip"
    (SOURCE / f"{PACKAGE}.zip.sha256").write_text(f"{sha(zip_path)}  {PACKAGE}.zip\n", encoding="utf-8", newline="\n")
    release = {
        "schema": "conv-native-p48-xmrscopefix-release-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN",
        "source_formal_package": "r5_n4_0cc_p47_tbvcdcone",
        "source_formal_analysis": {"path": ANALYSIS.relative_to(ROOT).as_posix(), "bytes": ANALYSIS.stat().st_size, "sha256": sha(ANALYSIS)},
        "zip": {"bytes": zip_path.stat().st_size, "sha256": sha(zip_path)},
        "repair": "delete only three package-local dump-only MSE_INST[5..7] references rejected by production VCS",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "target_diagnostic"],
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "server_actions_performed": [],
        "claim_boundary": "Local package construction/gates only; no production compile, simulation, root cause beyond the consumed p47 compile stop, natural terminal, formal D, E3, E4 or E5 claim.",
        "pass": True,
    }
    write_json(SOURCE / f"{PACKAGE}.release.json", release)
    print(json.dumps({"pass": True, "source_dir": SOURCE.as_posix(), "members": len(list(SOURCE.iterdir())), "zip_sha256": sha(zip_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
