#!/usr/bin/env python3
"""Finalize and stage the local-only v87b mandatory-VPD release receipts."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v87b_mandatory_vpd_release6"
INSTALL = "r5_n4_hw_v87b_mandatory_vpd"
PACKAGE = OUT / "build" / f"{INSTALL}.zip"
SIDECAR = PACKAGE.with_name(PACKAGE.name + ".sha256")
STAGING = OUT / "storage_staging"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    reports = {
        "final_zip_audit": OUT / f"{INSTALL}.final_zip_audit.json",
        "first_fresh": OUT / "exact_zip_audit/first_fresh_extra_audit_validation.json",
        "waveform": OUT / "exact_zip_audit/waveform_mandatory_validation.json",
        "post_sim": OUT / "exact_zip_audit/post_sim_return_validation.json",
        "frozen": OUT / "exact_zip_audit/frozen_surface_validation.json",
        "runner": OUT / "exact_zip_audit/runner_return_resilience_validation.json",
        "source_bound": OUT / "exact_zip_audit/source_bound_final_zip_validation.json",
        "runtime_harness": OUT / "runtime_layout_harness_family.json",
        "runtime_layout": OUT / "runtime_layout_shared_validation.json",
        "build": OUT / "build" / f"{INSTALL}.build.json",
        "build_profile": OUT / "server_package_build_profile.json",
    }
    errors: list[str] = []
    for name, path in reports.items():
        if not path.is_file():
            errors.append(f"missing report: {name}")
            continue
        value = load(path)
        passed = value.get("pass", value.get("valid"))
        if name == "build":
            passed = value.get("status") == "PACKAGE_READY_NOT_RUN"
        if name == "build_profile":
            passed = (
                value.get("contract_valid") is True
                and isinstance(value.get("preflight"), dict)
                and value["preflight"].get("pass") is True
            )
        if passed is not True:
            errors.append(f"report did not pass: {name}")
    if not PACKAGE.is_file() or not SIDECAR.is_file():
        errors.append("exact ZIP or sidecar is absent")
    else:
        expected = f"{sha256(PACKAGE)}  {PACKAGE.name}\n"
        if SIDECAR.read_text(encoding="ascii") != expected:
            errors.append("exact ZIP sidecar differs")

    package_root = OUT / "build" / INSTALL
    manifest = load(package_root / "package_manifest.json")
    observer = package_root / "tb_probe/native_return_observer.svh"
    bound = manifest.get("observer_binding_four_way", {})
    source = bound.get("source", {}) if isinstance(bound, dict) else {}
    if not isinstance(source, dict) or source.get("sha256") != sha256(observer):
        errors.append("observer precompile identity binding differs")

    sys.path.insert(0, str(ROOT))
    import tools.build_node0004_v86b_waveform_successor_v87b as builder

    if manifest.get("active_receipts") != builder.current_receipts():
        errors.append("current-disk rule/registry receipts drifted")

    test_command = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_server_waveform_mandatory_return",
        "tests.test_server_post_sim_return",
    ]
    tested = subprocess.run(
        test_command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    test_report = OUT / "waveform_post_sim_unit_tests.json"
    write(
        test_report,
        {
            "schema": "conv-node0004-v87b-waveform-post-sim-tests-v1",
            "pass": tested.returncode == 0,
            "command": test_command,
            "test_count": 31,
            "returncode": tested.returncode,
            "stdout": tested.stdout,
            "stderr": tested.stderr,
            "server_action": False,
        },
    )
    reports["unit_tests"] = test_report
    if tested.returncode != 0:
        errors.append("waveform/post-sim unit tests failed")

    old = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
        / "conv_serialized_node0004/r5_n4_hw_v86b_observer_xmre_fix"
        / "r5_n4_hw_v86b_observer_xmre_fix.zip"
    )
    if not old.is_file():
        errors.append("held v86b superseded ZIP is absent")
    if (ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v86b_observer_xmre_fix.zip").exists():
        errors.append("held v86b unexpectedly reappeared in pending")

    release_path = OUT / f"{INSTALL}.release_receipt.json"
    release = {
        "schema": "conv-node0004-v87b-mandatory-vpd-release-receipt-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_BLOCKED",
        "pass": not errors,
        "errors": errors,
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "shared_gate_epoch": "waveform-mandatory-v2-01ca6d7cd4a4a270",
        "rule_id": "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
        "package_id": INSTALL,
        "package": receipt(PACKAGE) if PACKAGE.is_file() else None,
        "previous_progress": (
            "v85b closed production compile exit=2 to the two package-local observer "
            "arb_req_ready XMRE sites and recovered the seven compile-core files; "
            "held v86b preserved the observer and structured-first-error repair."
        ),
        "current_purpose": (
            "Preserve the v86b-equivalent diagnostic, prove production compile beyond "
            "the XMR repair, and return mandatory full-hierarchy VPD so ACK output "
            "versus inline RHS, natural terminal, and formal-D blockers can be localized."
        ),
        "frozen": {
            "config": True,
            "numeric": True,
            "workload_semantics": True,
            "functional_rtl": True,
            "target_diagnostic": True,
        },
        "waveform": {
            "DUMP_VCD": 1,
            "DUMP_FSDB": 0,
            "TB_DUMP_FSDB": 0,
            "format": "VPD",
            "scope": "tb_NDP_Top_new_phy",
            "hierarchy_depth": 0,
            "excluded_scopes": [],
            "unbounded_streaming_return": True,
            "simulation_started_missing_waveform": "FAIL_CLOSED",
            "compile_not_started_compile_core_preserved": True,
        },
        "reports": {name: receipt(path) for name, path in reports.items()},
        "held_v86b": receipt(old) if old.is_file() else None,
        "server_action": False,
    }
    write(release_path, release)
    if errors:
        print(json.dumps({"pass": False, "errors": errors}, ensure_ascii=False))
        return 1

    if STAGING.exists():
        raise FileExistsError(f"refusing to overwrite staging directory: {STAGING}")
    STAGING.mkdir()
    copies = {
        PACKAGE: f"{INSTALL}.zip",
        SIDECAR: f"{INSTALL}.zip.sha256",
        release_path: f"{INSTALL}.release_receipt.json",
    }
    copies.update({path: f"{INSTALL}.{name}.json" for name, path in reports.items()})
    for source_path, name in copies.items():
        shutil.copy2(source_path, STAGING / name)
    print(
        json.dumps(
            {
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN",
                "release_receipt": receipt(release_path),
                "storage_staging": STAGING.relative_to(ROOT).as_posix(),
                "server_action": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
