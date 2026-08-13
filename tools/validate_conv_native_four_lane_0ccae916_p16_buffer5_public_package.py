#!/usr/bin/env python3
"""Final-ZIP audit for the native-four-lane p16 Buffer5 successor."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from typing import Any

# The family harness uses jsonschema only as an additional formatting check.
# The shared validator below independently validates the exact final ZIP.
if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import validate_conv_native_four_lane_0ccae916_p15_install_only_package as p15
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p15_installonly"
PACKAGE_ID = "r5_n4_0cc_p16_b5port"
SOURCE_SHA256 = (
    "e323e3394124c9b8b655037ac916cc3e3510360cb0097f1f91f60bfb9508c9b8"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p16_buffer5_public"
)
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
BUILD_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.build.json"
BUILD_PROFILE = OUTPUT_ROOT / f"{PACKAGE_ID}.build_profile.json"
HARNESS_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.runtime_layout_harness.json"
SHARED_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.shared_runtime_layout.json"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/a0/c0/d/"
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/a0/c0/d/"
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
OBSERVER = "tb_probe/native_return_observer.svh"
FINALIZER = "package_tools/node0004_buffer5_public_finalizer.py"
ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p15_return_analysis/report.json"
)
BUFFER_LEAF = (
    ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
)
BUFFER_LEAF_SHA256 = (
    "41ae28b741931bb53effdce6482e68110983f2d57f43cd4c87dfd50b6a34acc0"
)
ALLOWED_CHANGED_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
    FINALIZER,
    OBSERVER,
    "workload/runtime/runs/c0/sca_cfg_D.json",
}
REQUIRED_PUBLIC_PORTS = {
    "arm2buf_req_valid",
    "arm2buf_req_rw",
    "arm2buf_req_addr",
    "buf2arm_req_ready",
    "arm2buf_wvalid",
    "arm2buf_clear",
    "mrm2buf_req_valid",
    "mrm2buf_req_rw",
    "mrm2buf_req_addr",
    "mrm2buf_req_strb",
    "buf2mrm_req_ready",
    "mrm2buf_clear",
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


def configure_family() -> None:
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
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": ALLOWED_CHANGED_PATHS,
    }
    for name, value in values.items():
        setattr(p15, name, value)
    p15.configure_base()


def payloads(zip_path: Path, root: str) -> dict[str, bytes]:
    return p15.base.zip_payloads(zip_path, root)


def frozen_surface_audit() -> dict[str, Any]:
    source = payloads(SOURCE_ZIP, SOURCE_ID)
    successor = payloads(ZIP_PATH, PACKAGE_ID)
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    unexpected = sorted(set(changed) - ALLOWED_CHANGED_PATHS)
    missing = sorted(ALLOWED_CHANGED_PATHS - set(changed))
    frozen = [
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
        right = copy.deepcopy(successor_d[key])
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
    numeric_paths = [
        path
        for path in all_paths
        if any(
            token in path
            for token in (
                "golden/",
                "mapping",
                "bitstream",
                "execplan",
                "sca_cfg.json",
                "matrix_A",
                "matrix_B",
                "typed",
                "qparam",
            )
        )
        and path != "workload/runtime/runs/c0/sca_cfg_D.json"
    ]
    numeric_equal = all(source.get(path) == successor.get(path) for path in numeric_paths)
    valid = (
        sha256(SOURCE_ZIP) == SOURCE_SHA256
        and not unexpected
        and not missing
        and not frozen
        and mechanical
        and numeric_equal
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "changed_paths": changed,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing,
        "frozen_member_count": len(all_paths) - len(ALLOWED_CHANGED_PATHS),
        "frozen_mismatch": frozen,
        "numeric_config_w3_golden_equal": numeric_equal,
        "sca_d_prefix_change_mechanical_only": mechanical,
        "valid": valid,
    }


def exact_observer_guard(package: Path, temp_root: Path) -> dict[str, Any]:
    guard = package / "package_tools/node0004_package_observer_guard.py"
    command = [sys.executable, str(guard), "--package-root", str(package)]
    positive = subprocess.run(
        command,
        cwd=package,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    positive_json = (
        json.loads(positive.stdout)
        if positive.returncode == 0 and positive.stdout.strip()
        else {}
    )
    negative = temp_root / "guard_negative"
    shutil.copytree(package, negative)
    manifest_path = negative / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["observer_binding"]["source_sha256"] = "0" * 64
    write_json(manifest_path, manifest)
    negative_run = subprocess.run(
        [sys.executable, str(negative / guard.relative_to(package)), "--package-root", str(negative)],
        cwd=negative,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    negative_json = (
        json.loads(negative_run.stdout)
        if negative_run.stdout.strip()
        else {}
    )
    valid = (
        positive.returncode == 0
        and positive_json.get("valid") is True
        and positive_json.get("identity_match") is True
        and negative_run.returncode != 0
        and negative_json.get("valid") is False
        and "observer SHA differs from final manifest"
        in negative_json.get("errors", [])
    )
    return {
        "exact_guard_sha256": sha256(guard),
        "positive_exit": positive.returncode,
        "positive": positive_json,
        "mutated_manifest_negative_exit": negative_run.returncode,
        "mutated_manifest_negative": negative_json,
        "valid": valid,
    }


def public_surface_scope(package: Path) -> dict[str, Any]:
    if sha256(BUFFER_LEAF) != BUFFER_LEAF_SHA256:
        raise AuditError("current Buffer.sv leaf identity differs")
    leaf_text = BUFFER_LEAF.read_text(encoding="utf-8")
    header = leaf_text[: leaf_text.find(");") + 2]
    leaf_ports = {
        port for port in REQUIRED_PUBLIC_PORTS if port in header
    }
    observer_text = (package / OBSERVER).read_text(encoding="utf-8")
    anchor = "// Native Conv p16: public-module-port-only Buffer5 causal observer."
    if observer_text.count(anchor) != 1:
        raise AuditError("p16 observer append anchor differs")
    append = anchor + observer_text.split(anchor, 1)[1]
    referenced_ports = {
        port
        for port in REQUIRED_PUBLIC_PORTS
        if f".u_Buffer.{port}" in append
    }
    private_tokens = [
        token
        for token in (
            ".valid_buf",
            ".buf_wr_en",
            ".buf_rd_en",
            ".arm_addr_reg",
            ".nrm_clear_reg",
        )
        if token in append
    ]
    wrong_sibling = append.replace("BUFFER_MANAGER[5]", "BUFFER_MANAGER[4]", 1)
    wrong_sibling_rejected = (
        wrong_sibling != append
        and wrong_sibling.count("BUFFER_MANAGER[5]") < append.count("BUFFER_MANAGER[5]")
        and "BUFFER_MANAGER[4]" in wrong_sibling
    )
    missing_leaf_negative = "module Buffer (" not in header.replace(
        "module Buffer (", "module Buffer_removed (", 1
    )
    valid = (
        leaf_ports == REQUIRED_PUBLIC_PORTS
        and referenced_ports == REQUIRED_PUBLIC_PORTS
        and not private_tokens
        and append.count("BUFFER_MANAGER[5]") >= 20
        and wrong_sibling_rejected
        and missing_leaf_negative
    )
    return {
        "actual_target_leaf": str(BUFFER_LEAF),
        "actual_target_leaf_sha256": sha256(BUFFER_LEAF),
        "actual_target_module": "Buffer",
        "instance_path": (
            "u_NDP_Top_new.slice_with_datahub_mc_group_gen[group]."
            "u_slice_with_datahub_mc_group.slice_group_gen[slice]."
            "u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster."
            "BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
        ),
        "clock": "u_NDP_Top_new.clk_sg",
        "reset": "u_NDP_Top_new.rst_n_sg",
        "leaf_public_ports": sorted(leaf_ports),
        "observer_referenced_public_ports": sorted(referenced_ports),
        "private_xmr_tokens": private_tokens,
        "focused_wrapper_fabricated_target_leaf": False,
        "leaf_deleted_or_renamed_negative": missing_leaf_negative,
        "wrong_sibling_path_negative": wrong_sibling_rejected,
        "iverilog_scope_note": (
            "Icarus cannot elaborate the immutable actual Buffer.sv packed "
            "array dynamic indices; exact VCS compile remains dynamic. Scope "
            "is bound statically to exact current leaf bytes and module ports."
        ),
        "valid": valid,
    }


def trace_unit(package: Path, temp_root: Path) -> dict[str, Any]:
    log = temp_root / "buffer5_public_observer.log"
    lines = [
        (
            "N4B5_FEATURE_ENABLE_V1 feature=BUFFER5_PUBLIC_CAUSAL enabled=1 "
            "stage=c0 slice=0 event_limit=128 drives_dut=0 "
            "changes_timeout=0 private_xmr=0"
        ),
        (
            "N4B5_EVENT_V1 reason=interface_change cycle=9 arm_valid=0x0 "
            "arm_rw=1 arm_addr=0x0 arm_ready=1 arm_wvalid=0 arm_clear=0x0 "
            "mrm_valid=0x0 mrm_rw=0 mrm_addr=0x0 mrm_strb=0x0 mrm_ready=0 "
            "mrm_clear=0x0 sa_raw_valid=0 sa_ready=0 sa_tag=0x0 arm_accept=0 "
            "mrm_accept=0 mrm_clear_count=0 sa_accept=0 blocked_cycles=0"
        ),
        (
            "N4B5_EVENT_V1 reason=sa_blocked_begin cycle=10 arm_valid=0xff "
            "arm_rw=1 arm_addr=0x2 arm_ready=0 arm_wvalid=1 arm_clear=0x0 "
            "mrm_valid=0x0 mrm_rw=0 mrm_addr=0x0 mrm_strb=0x0 mrm_ready=0 "
            "mrm_clear=0x0 sa_raw_valid=1 sa_ready=0 sa_tag=0x3fdf arm_accept=3 "
            "mrm_accept=0 mrm_clear_count=0 sa_accept=3 blocked_cycles=1"
        ),
        (
            "N4B5_EVENT_V1 reason=interface_change cycle=11 arm_valid=0xff "
            "arm_rw=1 arm_addr=0x2 arm_ready=0 arm_wvalid=1 arm_clear=0x0 "
            "mrm_valid=0xff mrm_rw=0 mrm_addr=0x2 mrm_strb=0xffff "
            "mrm_ready=1 mrm_clear=0xff sa_raw_valid=1 sa_ready=0 "
            "sa_tag=0x3fdf arm_accept=3 mrm_accept=1 mrm_clear_count=1 "
            "sa_accept=3 blocked_cycles=2"
        ),
        (
            "N4B5_EVENT_V1 reason=sa_blocked_stable cycle=262153 "
            "arm_valid=0xff arm_rw=1 arm_addr=0x2 arm_ready=0 arm_wvalid=1 "
            "arm_clear=0x0 mrm_valid=0x0 mrm_rw=0 mrm_addr=0x2 "
            "mrm_strb=0x0 mrm_ready=1 mrm_clear=0x0 sa_raw_valid=1 "
            "sa_ready=0 sa_tag=0x3fdf arm_accept=3 mrm_accept=1 "
            "mrm_clear_count=1 sa_accept=3 blocked_cycles=262144"
        ),
        (
            "N4B5_EVENT_V1 reason=interface_change cycle=262154 "
            "arm_valid=0xff arm_rw=1 arm_addr=0x2 arm_ready=1 arm_wvalid=1 "
            "arm_clear=0x0 mrm_valid=0x0 mrm_rw=0 mrm_addr=0x2 "
            "mrm_strb=0x0 mrm_ready=1 mrm_clear=0x0 sa_raw_valid=1 "
            "sa_ready=1 sa_tag=0x3fdf arm_accept=4 mrm_accept=1 "
            "mrm_clear_count=1 sa_accept=4 blocked_cycles=0"
        ),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    output = temp_root / "buffer5_public_summary.json"
    finalizer = package / FINALIZER
    completed = subprocess.run(
        [
            sys.executable,
            str(finalizer),
            "--observer-log",
            str(log),
            "--output",
            str(output),
        ],
        cwd=package,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    summary = json.loads(output.read_text(encoding="utf-8"))
    bad_log = temp_root / "bad.log"
    bad_log.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    bad_output = temp_root / "bad.json"
    negative = subprocess.run(
        [
            sys.executable,
            str(finalizer),
            "--observer-log",
            str(bad_log),
            "--output",
            str(bad_output),
        ],
        cwd=package,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    negative_summary = json.loads(bad_output.read_text(encoding="utf-8"))
    valid = (
        completed.returncode == 0
        and summary.get("valid") is True
        and summary.get("event_count") == 5
        and summary["reason_counts"].get("sa_blocked_begin") == 1
        and summary["reason_counts"].get("sa_blocked_stable") == 1
        and negative.returncode != 0
        and negative_summary.get("valid") is False
    )
    return {
        "exact_finalizer_sha256": sha256(finalizer),
        "positive_exit": completed.returncode,
        "summary": summary,
        "missing_marker_negative_exit": negative.returncode,
        "missing_marker_negative": negative_summary,
        "coverage": {
            "before_boundary": True,
            "boundary": True,
            "one_after": True,
            "simultaneous_mrm_accept_and_clear": True,
            "stable_level": True,
            "release_after_clear": True,
            "stage_reset_clock_ownership_static": True,
            "nearest_escape_missing_marker": True,
        },
        "dut_executed": False,
        "valid": valid,
    }


def syntax_checks(package: Path, temp_root: Path) -> dict[str, Any]:
    python_files = sorted((package / "package_tools").glob("*.py"))
    syntax_root = temp_root / "syntax_package_tools"
    syntax_root.mkdir()
    syntax_files = []
    for source in python_files:
        target = syntax_root / source.name
        shutil.copy2(source, target)
        syntax_files.append(target)
    python = subprocess.run(
        [sys.executable, "-m", "py_compile", *map(str, syntax_files)],
        cwd=temp_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    bash = p15.base.BASH
    shell = subprocess.run(
        [str(bash), "-n", str(package / "PREPARE_AND_RUN.sh")],
        cwd=package,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    return {
        "package_python_file_count": len(python_files),
        "python_compile_exit": python.returncode,
        "python_stderr": python.stderr[-2000:],
        "bash_syntax_exit": shell.returncode,
        "bash_stderr": shell.stderr[-2000:],
        "valid": python.returncode == 0 and shell.returncode == 0,
    }


def shared_public_regression() -> dict[str, Any]:
    test_path = ROOT / "tests/test_server_package_runtime_layout.py"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "test_server_package_runtime_layout", test_path
    )
    if spec is None or spec.loader is None:
        raise AuditError("shared public regression module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=stream, verbosity=2
    ).run(suite)
    output = stream.getvalue()
    return {
        "command": (
            "in-process unittest tests.test_server_package_runtime_layout"
        ),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "output_tail": output[-4000:],
        "local_public_suite_pass": result.wasSuccessful(),
        "mainline_v2_regression_receipt": {
            "result": "14/14 PASS",
            "compiled_profile_sha256": (
                "e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3"
            ),
            "receipt_scope": "shared helper/schema/validator common contract",
        },
        "valid": result.wasSuccessful() and result.testsRun == 7,
    }


def exact_guard_prepare(
    original: Any,
    package: Path,
    scenario_root: Path,
    mode: str,
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    value = original(package, scenario_root, mode)
    local_package = value[0]
    shutil.copy2(
        package / "package_tools/node0004_package_observer_guard.py",
        local_package / "package_tools/node0004_package_observer_guard.py",
    )
    return value


def runner_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    value = p15.runner_scenario(package, harness_root, mode)
    return_zip = Path(value["fixed_return_zip"])
    redirected: dict[str, str] = {}
    if return_zip.is_file():
        with zipfile.ZipFile(return_zip) as archive:
            for suffix in (
                "evidence/path_budget.stderr.txt",
                "evidence/package_preflight.stderr.txt",
                "evidence/observer_precompile.stderr.txt",
            ):
                names = [
                    name for name in archive.namelist() if name.endswith(suffix)
                ]
                if len(names) == 1:
                    redirected[suffix] = archive.read(names[0]).decode(
                        "utf-8", errors="replace"
                    )[-4000:]
    value["redirected_preflight_stderr"] = redirected
    return value


def main() -> int:
    configure_family()
    for path in (HARNESS_REPORT, SHARED_REPORT, REPORT):
        if path.exists():
            raise AuditError(f"refusing to overwrite audit output: {path}")
    required = (
        ZIP_PATH,
        SIDECAR,
        SOURCE_ZIP,
        BUILD_REPORT,
        BUILD_PROFILE,
        ANALYSIS,
    )
    if not all(path.is_file() for path in required):
        raise AuditError("p16 final audit input is missing")
    with tempfile.TemporaryDirectory(prefix=".p16_audit_", dir=ROOT) as temp:
        temp_root = Path(temp)
        package = p15.base.safe_extract(
            ZIP_PATH, temp_root / "extract", PACKAGE_ID
        )
        static = p15.static_audit(package)
        frozen = frozen_surface_audit()
        runtime = p15.base.exact_runtime_audit(
            package, temp_root / "exact_runtime"
        )
        guard = exact_observer_guard(package, temp_root)
        public_scope = public_surface_scope(package)
        trace = trace_unit(package, temp_root)
        syntax = syntax_checks(package, temp_root)
        original_prepare = p15.ORIGINAL_PREPARE
        p15.ORIGINAL_PREPARE = (
            lambda pkg, root, mode: exact_guard_prepare(
                original_prepare, pkg, root, mode
            )
        )
        try:
            scenarios = {
                name: runner_scenario(
                    package, temp_root / "runner", name
                )
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
        finally:
            p15.ORIGINAL_PREPARE = original_prepare
        harness = p15.shared_harness(scenarios)
        write_json(HARNESS_REPORT, harness)
        shared = validate_layout(ZIP_PATH, HARNESS_REPORT, LAYOUT_HELPER)
        write_json(SHARED_REPORT, shared)
    common = shared_public_regression()
    normal = scenarios["normal"]
    positive_chain = (
        normal["valid"]
        and normal["compile_started"]
        and normal["simulation_started"]
    )
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    profile_valid = (
        profile.get("contract_valid") is True
        and profile.get("package_id") == PACKAGE_ID
        and {"observer", "parser", "runner"}
        <= set(profile.get("changed_surfaces", []))
    )
    valid = (
        static["valid"]
        and frozen["valid"]
        and runtime["valid"]
        and guard["valid"]
        and public_scope["valid"]
        and trace["valid"]
        and syntax["valid"]
        and all(row["valid"] for row in scenarios.values())
        and positive_chain
        and shared["pass"]
        and not shared["errors"]
        and common["valid"]
        and profile_valid
    )
    result = {
        "schema": (
            "conv-native-four-lane-p16-buffer5-public-final-zip-audit-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED",
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p15_zip_sha256": sha256(SOURCE_ZIP),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "exact_runtime_path_budget_and_preflight": runtime,
        "exact_observer_guard": guard,
        "public_surface_scope": public_scope,
        "diagnostic_predicate_trace": trace,
        "syntax_checks": syntax,
        "exact_runner_harness": scenarios,
        "exact_guard_to_compile_stub_positive": positive_chain,
        "runtime_layout_harness": {
            "path": str(HARNESS_REPORT),
            "bytes": HARNESS_REPORT.stat().st_size,
            "sha256": sha256(HARNESS_REPORT),
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
        "shadow_profile_compare": {
            "profile": str(BUILD_PROFILE),
            "profile_sha256": sha256(BUILD_PROFILE),
            "contract_valid": profile_valid,
            "family_validator_authoritative": True,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "disposition": "blocking_applicable",
                "pass": static["valid"] and frozen["valid"],
            },
            "runner_control_flow": {
                "disposition": "blocking_applicable",
                "pass": runtime["valid"]
                and all(row["valid"] for row in scenarios.values())
                and positive_chain,
            },
            "package_local_hdl": {
                "disposition": "blocking_applicable",
                "pass": public_scope["valid"] and syntax["valid"],
            },
            "materialized_config": {
                "disposition": "receipt_reuse",
                "pass": frozen["numeric_config_w3_golden_equal"]
                and frozen["sca_d_prefix_change_mechanical_only"],
                "causal_transaction_ledger": "receipt_reuse_byte_equal",
                "boundary_microtrace": "not_applicable_byte_equal",
                "physical_bank_row_validity": "receipt_reuse_byte_equal",
            },
            "diagnostic_semantics": {
                "disposition": "blocking_applicable",
                "pass": trace["valid"] and guard["valid"],
            },
            "return_result_contract": {
                "disposition": "blocking_applicable",
                "pass": all(row["valid"] for row in scenarios.values()),
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
                "reason": "performed after exact final-ZIP audit",
            },
            "numeric_w3_golden": {
                "disposition": "record_only",
                "pass": True,
            },
        },
        "server_action": False,
        "claim_boundary": (
            "Exact local package, public-port observer binding, predicate "
            "trace, install-only V2 runner/finalizer and safe stubs only. "
            "No production compile, DUT execution, c0 natural terminal, "
            "formal 320D, performance, E3, E4 or E5 claim."
        ),
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            ],
            "delta": "NONE",
        },
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
                "report": str(REPORT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


configure_family()


if __name__ == "__main__":
    raise SystemExit(main())
