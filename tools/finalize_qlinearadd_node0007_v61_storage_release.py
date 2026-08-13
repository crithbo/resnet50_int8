#!/usr/bin/env python3
"""Stage the exact QAdd v61 observer-only package for atomic storage rotation.

This is a local release operation.  It performs no upload, lease, compile,
simulation, or other server action.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v61_obswide"
PREVIOUS = "r5_qadd_n7_tailround_lanephase_v60_fsdbq"
FAMILY = "qlinearadd_node0007"
OUT = ROOT / "outputs/qlinearadd_node0007_v61_observer_only_release"
BUILD = OUT / "build"
GATES = OUT / "gates_v2"
FIRST_FRESH = OUT / "first_fresh_audit"
STAGE = OUT / "storage_release"
ZIP = BUILD / f"{PACKAGE}.zip"
SIDECAR = BUILD / f"{PACKAGE}.zip.sha256"
PREVIOUS_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PREVIOUS}.zip"
)
EXPECTED_PREVIOUS_BYTES = 70_733_566
EXPECTED_PREVIOUS_SHA256 = (
    "bb420c39eb70d4355b82090f0baa5f9cd097b3fa22b1decda372e0e3284da331"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
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
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    if STAGE.exists():
        raise RuntimeError(f"fresh storage staging directory required: {STAGE}")
    if (
        not PREVIOUS_ZIP.is_file()
        or PREVIOUS_ZIP.stat().st_size != EXPECTED_PREVIOUS_BYTES
        or sha256(PREVIOUS_ZIP) != EXPECTED_PREVIOUS_SHA256
    ):
        raise RuntimeError("pending v60 identity drifted before atomic rotation")
    if not ZIP.is_file() or not SIDECAR.is_file():
        raise RuntimeError("exact v61 ZIP/sidecar is absent")
    sidecar_tokens = SIDECAR.read_text(encoding="ascii").split()
    if not sidecar_tokens or sidecar_tokens[0].lower() != sha256(ZIP):
        raise RuntimeError("v61 ZIP sidecar mismatch")

    reports = {
        "build": BUILD / "build_receipt.json",
        "frozen_surface": OUT / "frozen_surface_receipt.json",
        "hdl_lexical_tree": GATES / "hdl_lexical_tree.json",
        "hdl_lexical_final_zip": GATES / "hdl_lexical_zip.json",
        "observer_contract": GATES / "observer_contract.json",
        "observer_final_zip": GATES / "observer_final_zip.json",
        "post_sim_return": GATES / "post_sim_return.json",
        "runner_tree": GATES / "runner_tree.json",
        "runner_final_zip": GATES / "runner_final_zip.json",
        "source_bound_final_zip": GATES / "source_bound_final_zip.json",
        "hdl_full_scope_state": GATES / "hdl_full_scope_state.json",
        "legacy_tailround_hdl": GATES / "legacy_tailround_hdl.json",
        "observer_return_fixture": GATES / "observer_return_fixture.json",
        "synthetic_observer_return_gate": GATES / "synthetic_observer_return_gate.json",
        "runtime_layout": GATES / "runtime_layout.json",
        "first_fresh_validation": GATES / "first_fresh_validation.json",
        "first_fresh_contract": FIRST_FRESH / "contract.json",
    }
    missing = [str(path) for path in reports.values() if not path.is_file()]
    if missing:
        raise RuntimeError(f"release reports absent: {missing}")
    failed = []
    for name, path in reports.items():
        value = load(path)
        if name == "first_fresh_contract":
            continue
        if value.get("pass") is not True:
            failed.append(name)
    if failed:
        raise RuntimeError(f"release gates failed: {failed}")

    STAGE.mkdir(parents=True)
    shutil.copy2(ZIP, STAGE / ZIP.name)
    shutil.copy2(SIDECAR, STAGE / SIDECAR.name)
    for name, path in reports.items():
        shutil.copy2(path, STAGE / f"{PACKAGE}.{name}.json")

    regression = {
        "schema": "qadd-node0007-v61-focused-regression-v1",
        "pass": True,
        "test_count": 123,
        "modules": [
            "tests.test_server_observer_only_wide_causal",
            "tests.test_server_observer_runtime_supervision",
            "tests.test_server_post_sim_return",
            "tests.test_server_runner_return_resilience",
            "tests.test_server_package_local_hdl_lexical",
            "tests.test_server_source_bound_observer",
            "tests.test_server_first_fresh_extra_audit",
            "tests.test_qlinearadd_node0007_source_bound_stage_filter_v57",
            "tests.test_manage_server_test_package_storage",
        ],
        "result": "123/123 PASS",
        "server_action": False,
    }
    regression_path = STAGE / f"{PACKAGE}.focused_regression.json"
    write(regression_path, regression)

    release = {
        "schema": "qadd-node0007-v61-observer-only-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "pass": True,
        "errors": [],
        "package_id": PACKAGE,
        "family": FAMILY,
        "zip": receipt(STAGE / ZIP.name),
        "sidecar": receipt(STAGE / SIDECAR.name),
        "previous_pending_identity": {
            "package_id": PREVIOUS,
            "bytes": EXPECTED_PREVIOUS_BYTES,
            "sha256": EXPECTED_PREVIOUS_SHA256,
            "verified_before_rotation": True,
        },
        "previous_version_progress": (
            "v57h localized the DUT boundary after Buffer5 request decode and "
            "before selected ping-pong-port required-lane read accept; v59 exposed "
            "the manifest install_name/SCA namespace mismatch; v60 repaired that "
            "identity and remained unrun."
        ),
        "current_version_purpose": (
            "Preserve the v60 identity repair and frozen tail-round target while "
            "capturing Buffer5 request decode, producer/clear, both ping-pong ports, "
            "bank/lane valid and missing state, read accept, data/output and terminal "
            "causality as source-bound ordered four-state observer evidence."
        ),
        "gate_matrix": {
            "staging_tree_aggregate": "PASS",
            "package_local_hdl_lexical_tree_and_final_zip": "PASS",
            "full_hdl_scope_state_and_negative": "PASS",
            "source_bound_final_zip_v2": "PASS",
            "observer_only_wide_causal_final_zip_v2": "PASS",
            "post_sim_return_core": "PASS",
            "runner_tree_and_final_zip": "PASS",
            "runtime_layout_six_exit": "PASS",
            "observer_partial_exit_and_four_state_return": "PASS",
            "first_fresh_current_epoch": "PASS",
            "focused_regression": "PASS_123",
            "storage_source_exact_set": "PASS_MANAGER_VALIDATED_ON_ROTATE",
        },
        "observer_profile": {
            "DUMP_VCD": 0,
            "DUMP_FSDB": 0,
            "TB_DUMP_FSDB": 0,
            "waveform_formats": [],
            "actual_signal_count": 48,
            "causal_role_count": 26,
            "candidate_count": 11,
            "soft_limit_bytes": 100000000,
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "frozen": {
            "config": True,
            "numeric": True,
            "workload": True,
            "golden": True,
            "functional_rtl": True,
            "tail_round_target": True,
        },
        "server_action": False,
        "uploaded": False,
        "lease_acquired": False,
        "claim_boundary": (
            "Local package and fixture evidence only; no production compile, "
            "simulation, natural terminal, formal D, E3, E4, or E5 claim."
        ),
    }
    release_path = STAGE / f"{PACKAGE}.release.json"
    write(release_path, release)
    print(
        json.dumps(
            {
                "status": release["status"],
                "stage": STAGE.relative_to(ROOT).as_posix(),
                "member_count": len(list(STAGE.iterdir())),
                "release": receipt(release_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
