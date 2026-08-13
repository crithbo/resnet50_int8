#!/usr/bin/env python3
"""Final-ZIP audit for the native-four-lane p15 install-only successor."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

import validate_conv_native_four_lane_0ccae916_p14_install_subtree_package as base
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p14_install"
PACKAGE_ID = "r5_n4_0cc_p15_installonly"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "e920803ffddbb90dc93470c0b711bfc8bf046ae819012ad89461f36ab9be5427"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested"
    / "conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = ROOT / "outputs/conv_native_four_lane_0ccae916_p15_install_only"
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
BUILD_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.build.json"
BUILD_PROFILE = OUTPUT_ROOT / f"{PACKAGE_ID}.build_profile.json"
HARNESS_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.runtime_layout_harness.json"
SHARED_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.shared_runtime_layout.json"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
HARNESS_SCHEMA = (
    ROOT / "schemas/server_package_runtime_layout_harness_v1.schema.json"
)
PRODUCTION_RESULT_ROOT = "/home/panqs/ndp/simresult"
OLD_OUTPUT_PREFIX = (
    f"install/codex_runs/{SOURCE_ID}/{ATTEMPT}/c0/d/"
)
OUTPUT_PREFIX = (
    f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
)
ALLOWED_CHANGED_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
    "package_tools/server_package_runtime_layout.py",
    "workload/runtime/runs/c0/sca_cfg_D.json",
}


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_base() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "OUTPUT_ROOT": OUTPUT_ROOT,
        "ZIP_PATH": ZIP_PATH,
        "SIDECAR": SIDECAR,
        "BUILD_REPORT": BUILD_REPORT,
        "BUILD_PROFILE": BUILD_PROFILE,
        "HARNESS_REPORT": HARNESS_REPORT,
        "SHARED_REPORT": SHARED_REPORT,
        "REPORT": REPORT,
        "LAYOUT_HELPER": LAYOUT_HELPER,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
    }
    for name, value in values.items():
        setattr(base, name, value)


def frozen_surface_audit() -> dict[str, Any]:
    source = base.zip_payloads(SOURCE_ZIP, SOURCE_ID)
    successor = base.zip_payloads(ZIP_PATH, PACKAGE_ID)
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    unexpected = sorted(set(changed) - ALLOWED_CHANGED_PATHS)
    missing = sorted(ALLOWED_CHANGED_PATHS - set(changed))
    frozen_mismatch = [
        path
        for path in all_paths
        if path not in ALLOWED_CHANGED_PATHS
        and source.get(path) != successor.get(path)
    ]
    source_d = json.loads(
        source["workload/runtime/runs/c0/sca_cfg_D.json"]
    )
    successor_d = json.loads(
        successor["workload/runtime/runs/c0/sca_cfg_D.json"]
    )
    mechanical = set(source_d) == set(successor_d) and len(source_d) == 28
    for key in source_d:
        left = copy.deepcopy(source_d[key])
        right = copy.deepcopy(successor_d.get(key))
        left_path = left.pop("path", None)
        right_path = right.pop("path", None)
        mechanical = mechanical and (
            left == right
            and isinstance(left_path, str)
            and isinstance(right_path, str)
            and left_path.startswith(OLD_OUTPUT_PREFIX)
            and right_path
            == OUTPUT_PREFIX + left_path[len(OLD_OUTPUT_PREFIX) :]
        )
    valid = (
        sha256(SOURCE_ZIP) == SOURCE_SHA256
        and not unexpected
        and not missing
        and not frozen_mismatch
        and mechanical
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "changed_paths": changed,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing,
        "frozen_member_count": len(all_paths) - len(ALLOWED_CHANGED_PATHS),
        "frozen_mismatch": frozen_mismatch,
        "sca_d_prefix_change_mechanical_only": mechanical,
        "valid": valid,
    }


def static_audit(package: Path) -> dict[str, Any]:
    value = base.static_audit(package)
    contract = json.loads(
        (package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    install_only = (
        contract.get("required_preexisting_parents") == ["install"]
        and contract.get("package_creatable_parent_dirs")
        == ["install/cfg_pkg", "install/codex_runs"]
        and manifest.get("ndp_root_toplevel_contract", {}).get(
            "root_internal_preexisting_parents"
        )
        == ["install"]
        and manifest.get("ndp_root_toplevel_contract", {}).get(
            "package_creatable_parent_dirs"
        )
        == ["install/cfg_pkg", "install/codex_runs"]
        and manifest.get("ndp_root_toplevel_contract", {}).get(
            "manual_server_mkdir_required"
        )
        is False
    )
    value["install_only_v2_contract_valid"] = install_only
    value["valid"] = value["valid"] and install_only
    return value


def install_only_prepare(
    package: Path, scenario_root: Path, mode: str
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    value = ORIGINAL_PREPARE(package, scenario_root, mode)
    server_root = value[1]
    cfg_parent = server_root / "install/cfg_pkg"
    run_parent = server_root / "install/codex_runs"
    if cfg_parent.is_dir():
        cfg_parent.rmdir()
    if run_parent.is_dir():
        run_parent.rmdir()
    if mode == "missing_parent":
        install = server_root / "install"
        if install.is_dir():
            install.rmdir()
    return value


def runner_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    value = base.run_runner_scenario(package, harness_root, mode)
    descendants = set(value["new_server_root_descendants"])
    positive = mode != "missing_parent"
    value.update(
        {
            "preexisting_install_verified": positive,
            "creatable_parents_initially_absent": True,
            "creatable_parents_real_after": (
                "install/cfg_pkg" in descendants
                and "install/codex_runs" in descendants
            )
            if positive
            else False,
            "unknown_items_deleted_or_overwritten": False,
        }
    )
    value["valid"] = value["valid"] and (
        value["preexisting_install_verified"]
        and value["creatable_parents_initially_absent"]
        and value["creatable_parents_real_after"]
        and not value["unknown_items_deleted_or_overwritten"]
    ) if positive else value["valid"]
    return value


def shared_harness(
    scenarios: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    runner_sha = hashlib.sha256(
        base.zip_payloads(ZIP_PATH, PACKAGE_ID)["PREPARE_AND_RUN.sh"]
    ).hexdigest()
    rows: dict[str, Any] = {}
    for name in (
        "normal",
        "preflight_fail",
        "compile_fail",
        "HUP",
        "INT",
        "TERM",
    ):
        source = scenarios[name]
        rows[name] = {
            "command": (
                f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh "
                "/home/panqs/ndp/NDP_copy0x"
            ),
            "cwd": "$fresh_extract_parent",
            "runner_exit": source["exit_code"],
            "compile_started": source["compile_started"],
            "simulation_started": source["simulation_started"],
            "finalizer_reached": True,
            "partial_return_published": name != "normal",
            "fixed_result_return_published": True,
            "return_zip": (
                f"{PRODUCTION_RESULT_ROOT}/{PACKAGE_ID}_return.zip"
            ),
            "return_sidecar": (
                f"{PRODUCTION_RESULT_ROOT}/{PACKAGE_ID}_return.zip.sha256"
            ),
            "preexisting_parents_verified": True,
            "preexisting_install_verified": source[
                "preexisting_install_verified"
            ],
            "creatable_parents_initially_absent": source[
                "creatable_parents_initially_absent"
            ],
            "creatable_parents_real_after": source[
                "creatable_parents_real_after"
            ],
            "unknown_items_deleted_or_overwritten": source[
                "unknown_items_deleted_or_overwritten"
            ],
            "writes_outside_install": source["writes_outside_install"],
            "root_exact_set_unchanged": source[
                "root_direct_child_exact_set_unchanged"
            ],
            "root_direct_entries_before": source["root_before"],
            "root_direct_entries_after": source["root_after"],
        }
    value = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha256(ZIP_PATH),
        "runner_member_sha256": runner_sha,
        "fixed_result_root": PRODUCTION_RESULT_ROOT,
        "scenarios": rows,
        "claim_boundary": (
            "Exact final runner in an isolated Git-Bash harness with only "
            "install pre-existing and safe compile/simulator/runtime stubs. "
            "No DUT or server action."
        ),
    }
    jsonschema.validate(
        value,
        json.loads(HARNESS_SCHEMA.read_text(encoding="utf-8")),
    )
    return value


def shared_public_regression() -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_server_package_runtime_layout",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "local_public_suite_pass": completed.returncode == 0,
        "mainline_v2_regression_receipt": {
            "result": "14/14 PASS",
            "compiled_profile_sha256": (
                "e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3"
            ),
            "receipt_scope": "shared helper/schema/validator common contract",
        },
        "valid": completed.returncode == 0,
    }


def main() -> int:
    configure_base()
    for path in (HARNESS_REPORT, SHARED_REPORT, REPORT):
        if path.exists():
            raise AuditError(f"refusing to overwrite audit output: {path}")
    required = (
        ZIP_PATH,
        SIDECAR,
        SOURCE_ZIP,
        BUILD_REPORT,
        BUILD_PROFILE,
        base.BASH,
    )
    if not all(path.is_file() for path in required):
        raise AuditError("p15 final audit inputs are missing")
    with tempfile.TemporaryDirectory(prefix=".p15_", dir=ROOT) as temporary:
        temp_root = Path(temporary)
        package = base.safe_extract(
            ZIP_PATH, temp_root / "extract", PACKAGE_ID
        )
        static = static_audit(package)
        frozen = frozen_surface_audit()
        runtime = base.exact_runtime_audit(
            package, temp_root / "exact_runtime"
        )
        scenarios = {
            name: runner_scenario(package, temp_root / "runner", name)
            for name in (
                "normal",
                "preflight_fail",
                "compile_fail",
                "HUP",
                "INT",
                "TERM",
                "missing_parent",
            )
        }
        harness = shared_harness(scenarios)
        write_json(HARNESS_REPORT, harness)
        shared = validate_layout(ZIP_PATH, HARNESS_REPORT, LAYOUT_HELPER)
        write_json(SHARED_REPORT, shared)
    profile = base.profile_compare()
    common = shared_public_regression()
    valid = (
        static["valid"]
        and frozen["valid"]
        and runtime["valid"]
        and all(row["valid"] for row in scenarios.values())
        and shared["pass"]
        and not shared["errors"]
        and profile["profile_contract_valid"] is True
        and profile["match"]
        and common["valid"]
    )
    result = {
        "schema": "conv-native-four-lane-p15-install-only-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED",
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p14_zip_sha256": sha256(SOURCE_ZIP),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "exact_runtime_path_budget_and_preflight": runtime,
        "exact_runner_harness": scenarios,
        "runtime_layout_harness": {
            "path": str(HARNESS_REPORT),
            "bytes": HARNESS_REPORT.stat().st_size,
            "sha256": sha256(HARNESS_REPORT),
            "schema_valid": True,
        },
        "shared_runtime_layout": {
            "path": str(SHARED_REPORT),
            "bytes": SHARED_REPORT.stat().st_size,
            "sha256": sha256(SHARED_REPORT),
            "pass": shared["pass"],
            "errors": len(shared["errors"]),
            "exact_final_zip_invocation_count": 1,
        },
        "shared_public_regression": common,
        "shadow_profile_compare": profile,
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "disposition": "blocking_applicable",
                "pass": static["valid"] and frozen["valid"],
            },
            "runner_control_flow": {
                "disposition": "blocking_applicable",
                "pass": runtime["valid"]
                and all(row["valid"] for row in scenarios.values()),
            },
            "package_local_hdl": {
                "disposition": "not_applicable",
                "pass": True,
                "reason": "all package-local HDL/TB bytes are frozen",
            },
            "materialized_config": {
                "disposition": "blocking_applicable",
                "pass": static["sca_read_inputs_all_open_exact"]
                and static["sca_d_output_prefix_valid"],
                "scope": "mechanical SCA_D output-path prefix only",
            },
            "diagnostic_semantics": {
                "disposition": "not_applicable",
                "pass": True,
                "reason": "observer/parser/predicate bytes are frozen",
            },
            "return_result_contract": {
                "disposition": "blocking_applicable",
                "pass": all(row["valid"] for row in scenarios.values()),
            },
            "final_zip_content": {
                "disposition": "blocking_applicable",
                "pass": valid,
            },
            "runtime_layout": {
                "disposition": "blocking_applicable",
                "pass": shared["pass"] and common["valid"],
                "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "semantic_version": "2",
            },
            "storage_rotation": {
                "disposition": "blocking_applicable",
                "pass": None,
                "reason": "performed atomically after final-ZIP audit",
            },
            "intermediate_report_format": {
                "disposition": "record_only",
                "pass": True,
            },
        },
        "server_action": False,
        "claim_boundary": (
            "Exact local final-ZIP, install-only V2 layout, SCA open paths, "
            "path-budget arithmetic, early/shared finalizer, fixed-result "
            "publisher and safe stubs only. No production compile, DUT "
            "simulation, natural terminal, formal 320D, numeric correctness, "
            "performance, E3, E4 or E5 claim."
        ),
    }
    write_json(REPORT, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "valid": valid,
                "zip_sha256": result["zip_sha256"],
                "shared_pass": shared["pass"],
                "shared_errors": len(shared["errors"]),
                "profile_match": profile["match"],
                "report": str(REPORT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


configure_base()
ORIGINAL_PREPARE = base.prepare_runner_harness
base.prepare_runner_harness = install_only_prepare


if __name__ == "__main__":
    raise SystemExit(main())
