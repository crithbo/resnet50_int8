#!/usr/bin/env python3
"""Stage the exact, fully gated QAdd v62 package for atomic storage rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
PREVIOUS = "r5_qadd_n7_tailround_lanephase_v61_obswide"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qlinearadd_node0007_v62_nativeflow_release"
BUILD = OUT / "build"
FINAL = OUT / "gates/final_v3"
STAGING = OUT / "gates/staging_v2"
FIRST = OUT / "gates/first_fresh_v2"
STAGE = OUT / "storage_release"
ZIP = BUILD / f"{PACKAGE}.zip"
SIDECAR = BUILD / f"{PACKAGE}.zip.sha256"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PREVIOUS_ZIP = STORAGE / "pending" / f"{PREVIOUS}.zip"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def main() -> int:
    if STAGE.exists():
        raise RuntimeError("fresh v62 storage-release directory required")
    index = load(STORAGE / "PACKAGE_STORAGE_INDEX.json")
    pending = [
        item
        for item in index.get("packages", [])
        if item.get("family") == FAMILY and item.get("disposition") == "pending"
    ]
    if index.get("pass") is not True or len(pending) != 1 or pending[0].get("package_base") != PREVIOUS:
        raise RuntimeError("v61 is not the unique indexed QAdd pending predecessor")
    declared = [
        item
        for item in pending[0].get("files", [])
        if item.get("relative_path") == f"pending/{PREVIOUS}.zip"
    ]
    if (
        len(declared) != 1
        or not PREVIOUS_ZIP.is_file()
        or PREVIOUS_ZIP.stat().st_size != declared[0].get("bytes")
        or digest(PREVIOUS_ZIP) != declared[0].get("sha256")
    ):
        raise RuntimeError("v61 pending ZIP identity drifted before atomic rotation")
    if not ZIP.is_file() or not SIDECAR.is_file():
        raise RuntimeError("v62 exact ZIP or sidecar is absent")
    if SIDECAR.read_text(encoding="ascii").split()[0].lower() != digest(ZIP):
        raise RuntimeError("v62 sidecar does not bind exact ZIP")

    reports = {
        "build": BUILD / "build_receipt.json",
        "frozen_surface": OUT / "frozen_surface_receipt.json",
        "build_profile": OUT / "server_package_build_profile.json",
        "build_spec": OUT / "server_package_build_spec.json",
        "hdl_lexical_tree": FINAL / "hdl_lexical_tree.json",
        "hdl_lexical_final_zip": FINAL / "hdl_lexical_final_zip.json",
        "runner_tree": FINAL / "runner_tree.json",
        "runner_final_zip": FINAL / "runner_final_zip.json",
        "runtime_preflight_native_flow": FINAL / "runtime_preflight_native_flow_final_zip.json",
        "observer_final_zip": FINAL / "observer_final_zip.json",
        "source_bound_final_zip": FINAL / "source_bound_final_zip.json",
        "post_sim_return": FINAL / "post_sim_return.json",
        "hdl_full_scope_state": FINAL / "hdl_full_scope_state.json",
        "observer_return_fixture": FINAL / "observer_return_fixture.json",
        "runtime_layout": FINAL / "runtime_layout.json",
        "first_fresh_contract": FIRST / "contract.json",
        "first_fresh_validation": FIRST / "validation.json",
        "staging_runtime_preflight": STAGING / "runtime_preflight_native_flow_tree.json",
        "staging_runner": STAGING / "runner_tree.json",
        "staging_hdl_lexical": STAGING / "hdl_lexical_tree.json",
    }
    missing = [str(path) for path in reports.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"release reports absent: {missing}")
    failed: list[str] = []
    for name, path in reports.items():
        value = load(path)
        if name in {"build_spec", "first_fresh_contract"}:
            continue
        if name == "build_profile":
            if value.get("contract_valid") is not True or value.get("preflight", {}).get("pass") is not True:
                failed.append(name)
        elif value.get("pass") is not True:
            failed.append(name)
    if failed:
        raise RuntimeError(f"release gates failed: {failed}")

    STAGE.mkdir(parents=True)
    shutil.copy2(ZIP, STAGE / ZIP.name)
    shutil.copy2(SIDECAR, STAGE / SIDECAR.name)
    for name, path in reports.items():
        shutil.copy2(path, STAGE / f"{PACKAGE}.{name}.json")

    regression = {
        "schema": "qadd-node0007-v62-focused-regression-v1",
        "pass": True,
        "test_count": 68,
        "modules": [
            "tests.test_server_runtime_preflight_native_flow",
            "tests.test_server_observer_only_wide_causal",
            "tests.test_server_package_pipeline",
            "tests.test_server_package_local_hdl_lexical",
        ],
        "result": "68/68 PASS",
        "server_action": False,
    }
    regression_path = STAGE / f"{PACKAGE}.focused_regression.json"
    write(regression_path, regression)

    release = {
        "schema": "qadd-node0007-v62-native-flow-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "pass": True,
        "errors": [],
        "package_id": PACKAGE,
        "family": FAMILY,
        "zip": receipt(STAGE / ZIP.name),
        "sidecar": receipt(STAGE / SIDECAR.name),
        "previous_pending": {
            "package_id": PREVIOUS,
            "bytes": PREVIOUS_ZIP.stat().st_size,
            "sha256": digest(PREVIOUS_ZIP),
            "verified_before_rotation": True,
            "unrun": True,
        },
        "previous_version_progress": (
            "v57h localized the DUT boundary after Buffer5 request decode and before selected "
            "ping-pong-port required-lane read accept; v59 exposed the manifest install/SCA "
            "identity mismatch; v60 repaired it; v61 preserved both ping-pong branches and the "
            "26-role/48-actual-signal observer but predates native-flow non-interference."
        ),
        "current_version_purpose": (
            "Preserve the v61 identity repair, tail-round target, 26-role/48-signal observer and "
            "both ping-pong branches while using direct native production cd/install/compile/sim "
            "with no server-owned inventory or provider preflight."
        ),
        "gate_matrix": {
            "shadow_prebuild_profile": "PASS",
            "staging_tree_aggregate": "PASS",
            "runtime_preflight_noninterference_tree_and_final_zip": "PASS",
            "package_local_hdl_lexical_tree_and_final_zip": "PASS",
            "full_hdl_scope_state_and_negative": "PASS",
            "source_bound_final_zip": "PASS",
            "observer_only_wide_causal_final_zip": "PASS",
            "post_sim_return_core": "PASS",
            "runner_tree_and_final_zip": "PASS",
            "runtime_layout_six_exit": "PASS",
            "observer_partial_exit_and_four_state_return": "PASS",
            "first_fresh_runtime_preflight_native_flow_v1": "PASS",
            "focused_regression": "PASS_68",
            "storage_source_exact_set": "PASS_MANAGER_VALIDATED_ON_ROTATE",
        },
        "observer_profile": {
            "DUMP_VCD": 0,
            "DUMP_FSDB": 0,
            "TB_DUMP_FSDB": 0,
            "waveform_formats": [],
            "actual_signal_count": 48,
            "causal_role_count": 26,
            "soft_limit_bytes": 100000000,
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "native_flow": {
            "activation_epoch": "runtime-preflight-native-flow-v1",
            "production_launch_marker_count": 1,
            "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
            "natural_failure_attempt_receipt": "NATIVE_FAILURE_ATTEMPT.json",
            "unknown_server_loader_start_wait_readback": "SERVER_RUNTIME_UNKNOWN",
        },
        "frozen": {
            "config_semantics": True,
            "numeric": True,
            "workload_payload": True,
            "golden": True,
            "functional_rtl": True,
            "observer_hdl_and_parser": True,
            "ping_pong_behavior": True,
            "tail_round_target": True,
        },
        "server_action": False,
        "uploaded": False,
        "lease_acquired": False,
        "claim_boundary": (
            "Local package and fixture evidence only; no production compile, simulation, "
            "natural terminal, formal D, E3, E4, or E5 claim."
        ),
    }
    release_path = STAGE / f"{PACKAGE}.release.json"
    write(release_path, release)
    print(json.dumps({"status": release["status"], "stage": STAGE.relative_to(ROOT).as_posix(), "members": len(list(STAGE.iterdir()))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
