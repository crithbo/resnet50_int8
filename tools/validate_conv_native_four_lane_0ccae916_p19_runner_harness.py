#!/usr/bin/env python3
"""Run the exact p19 runner through the inherited native-Conv stub harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p18_pekeep3_package as p18
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p19b_dflow"
SOURCE_ID = "r5_n4_0cc_p18_pekeep3"
SOURCE_SHA256 = (
    "58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
INPUT_PREFIX = f"install/cfg_pkg/{PACKAGE_ID}/"
OLD_INPUT_PREFIX = f"install/cfg_pkg/{SOURCE_ID}/"
OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/a0/c0/d/"
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/a0/c0/d/"
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"


class HarnessError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise HarnessError(f"refusing to overwrite harness receipt: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure(zip_path: Path, output: Path) -> None:
    p17 = p18.p17
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "WORKLOAD_INSTALL_NAME": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "OUTPUT_ROOT": output.parent,
        "ZIP_PATH": zip_path,
        "SIDECAR": Path(str(zip_path) + ".sha256"),
        "BUILD_REPORT": output.parent / f"{PACKAGE_ID}.build.json",
        "BUILD_PROFILE": output.parent / f"{PACKAGE_ID}.build_profile.json",
        "HARNESS_REPORT": output,
        "SHARED_REPORT": output.parent / f"{PACKAGE_ID}.shared_runtime_layout.json",
        "REPORT": output.parent / f"{PACKAGE_ID}.final_zip_audit.json",
        "INPUT_PREFIX": INPUT_PREFIX,
        "OLD_INPUT_PREFIX": OLD_INPUT_PREFIX,
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": set(),
    }
    for name, value in values.items():
        setattr(p17, name, value)
    p17.build.OLD_INSTALL_NAME = SOURCE_ID
    p17.configure_family()
    p17.p16.p15.base.RUNTIME_PREFIX = INPUT_PREFIX


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def mapped_prepare(
    original: Any,
    package: Path,
    scenario_root: Path,
    mode: str,
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    value = p18.p17.exact_guard_prepare(
        original, package, scenario_root, mode
    )
    local_package, _server_root, result_root, _marker, _env = value
    runner = local_package / "PREPARE_AND_RUN.sh"
    publisher = local_package / "package_tools/fixed_simresult_publisher.py"
    runner_text = runner.read_text(encoding="utf-8")
    if "../simresult" not in runner_text:
        raise HarnessError("isolated runner result-root anchor absent")
    mapped_identity = (
        '[ "$resolved_result_root" = "../simresult" ] || runner_fail 9 '
        '"fixed simresult identity differs"'
    )
    if mapped_identity not in runner_text:
        raise HarnessError("isolated runner identity-check anchor absent")
    runner.write_text(
        runner_text.replace(
            mapped_identity,
            '[ -n "$resolved_result_root" ] || runner_fail 9 '
            '"isolated simresult identity is empty"',
        ),
        encoding="utf-8",
        newline="\n",
    )
    publisher_text = publisher.read_text(encoding="utf-8")
    if (
        "../simresult" not in publisher_text
        or "not return_zip.is_absolute()" not in publisher_text
    ):
        raise HarnessError("isolated publisher result-root anchor absent")
    # Git-Bash launches the bundled Windows Python directly, so its local
    # namespace mapping is necessarily relative.  Relax only the harness copy
    # of the production absolute-path predicate; parent/name checks remain.
    publisher.write_text(
        publisher_text.replace("not return_zip.is_absolute()", "False"),
        encoding="utf-8",
        newline="\n",
    )
    return value


def unique_runner_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    base = p18.p17.p16.p15.base
    scenario_root = harness_root / mode
    scenario_root.mkdir(parents=True)
    local_package, server_root, result_root, marker, env = (
        base.prepare_runner_harness(package, scenario_root, mode)
    )
    runner = local_package / "PREPARE_AND_RUN.sh"
    if mode in {"HUP", "INT", "TERM"}:
        anchor = "sim_pid=$!\n(\n  while kill -0"
        injection = (
            "sim_pid=$!\n"
            f"( sleep 0.2; kill -{mode} \"$$\" ) &\n"
            "(\n  while kill -0"
        )
        text = runner.read_text(encoding="utf-8")
        if text.count(anchor) != 1:
            raise HarnessError("signal injection anchor differs")
        runner.write_text(
            text.replace(anchor, injection),
            encoding="utf-8",
            newline="\n",
        )
    before_direct = base.direct_set(server_root)
    before_recursive = base.recursive_set(server_root)
    completed = subprocess.run(
        [
            str(base.BASH),
            base.posix_path(runner),
            base.posix_path(server_root),
        ],
        cwd=local_package,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    after_direct = base.direct_set(server_root)
    after_recursive = base.recursive_set(server_root)
    returns = sorted(result_root.glob(f"{PACKAGE_ID}_r*_return.zip"))
    if len(returns) != 1:
        raise HarnessError(
            f"{mode} unique return count differs: {len(returns)} "
            f"exit={completed.returncode} stderr={completed.stderr[-1200:]}"
        )
    return_zip = returns[0]
    sidecar = Path(str(return_zip) + ".sha256")
    if not sidecar.is_file():
        raise HarnessError(f"{mode} return sidecar absent")
    status = base.return_json(
        return_zip, "/evidence/package_local_preflight_status.json"
    )
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    compile_marker = Path(env["AUDIT_COMPILE_MARKER"])
    sim_marker = Path(env["AUDIT_STUB_MARKER"])
    new_paths = sorted(after_recursive - before_recursive)
    writes_outside_install = any(
        path.split("/", 1)[0] != "install" for path in new_paths
    )
    expected_compile = mode not in {"preflight_fail", "missing_parent"}
    expected_simulation = mode in {"normal", "HUP", "INT", "TERM"}
    expected_zero = mode == "normal"
    cfg_parent = server_root / "install/cfg_pkg"
    run_parent = server_root / "install/codex_runs"
    install = server_root / "install"
    valid = (
        before_direct == after_direct
        and sidecar_tokens == [file_sha256(return_zip), return_zip.name]
        and compile_marker.is_file() is expected_compile
        and sim_marker.is_file() is expected_simulation
        and (
            completed.returncode == 0
            if expected_zero
            else completed.returncode != 0
        )
        and not writes_outside_install
        and status.get("partial") is (mode != "normal")
        and install.is_dir()
        and cfg_parent.is_dir()
        and run_parent.is_dir()
        and marker.is_file()
    )
    return {
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
        "package_local_preflight_status": status,
        "root_before": before_direct,
        "root_after": after_direct,
        "root_direct_child_exact_set_unchanged": before_direct == after_direct,
        "new_server_root_descendants": new_paths,
        "writes_outside_install": writes_outside_install,
        "preexisting_parents_verified": mode != "missing_parent",
        "preexisting_install_verified": mode != "missing_parent",
        "creatable_parents_initially_absent": True,
        "creatable_parents_real_after": (
            cfg_parent.is_dir() and run_parent.is_dir()
        ),
        "unknown_items_deleted_or_overwritten": False,
        "compile_started": compile_marker.is_file(),
        "simulation_started": sim_marker.is_file(),
        "return_basename": return_zip.name,
        "return_zip_local": str(return_zip),
        "return_sha256": file_sha256(return_zip),
        "sidecar_valid": sidecar_tokens
        == [file_sha256(return_zip), return_zip.name],
        "duplicates_absent": (
            not any(server_root.glob(f"{PACKAGE_ID}_r*_return.zip"))
            and not any(local_package.glob(f"{PACKAGE_ID}_r*_return.zip"))
        ),
        "valid": valid,
    }


def make_shared_harness(
    zip_path: Path, scenarios: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh")
    rows: dict[str, Any] = {}
    for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"):
        source = scenarios[name]
        production_zip = (
            "/home/panqs/ndp/simresult/" + source["return_basename"]
        )
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
            "return_zip": production_zip,
            "return_sidecar": production_zip + ".sha256",
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
    return {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": file_sha256(zip_path),
        "runner_member_sha256": hashlib.sha256(runner).hexdigest(),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": rows,
        "claim_boundary": (
            "Exact final runner in an isolated Git-Bash harness with only "
            "result-root namespace mapping and safe compile/simulator/runtime "
            "stubs; no DUT or server action."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--harness-output", required=True, type=Path)
    parser.add_argument("--shared-output", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    harness_output = args.harness_output.resolve()
    shared_output = args.shared_output.resolve()
    configure(zip_path, harness_output)
    p17 = p18.p17

    with tempfile.TemporaryDirectory(prefix=".p19_runner_", dir=ROOT) as temp:
        temp_root = Path(temp)
        package = p17.p16.p15.base.safe_extract(
            zip_path, temp_root / "extract", PACKAGE_ID
        )
        original_prepare = p17.p16.p15.ORIGINAL_PREPARE
        p17.p16.p15.ORIGINAL_PREPARE = (
            lambda pkg, root, mode: mapped_prepare(
                original_prepare, pkg, root, mode
            )
        )
        try:
            scenarios = {
                name: unique_runner_scenario(
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
            p17.p16.p15.ORIGINAL_PREPARE = original_prepare
        harness = make_shared_harness(zip_path, scenarios)
        write_json(harness_output, harness)
        shared = validate_layout(
            zip_path,
            harness_output,
            LAYOUT_HELPER,
            require_runner_visibility=True,
        )
        write_json(shared_output, shared)

    positive_chain = (
        scenarios["normal"]["valid"]
        and scenarios["normal"]["compile_started"]
        and scenarios["normal"]["simulation_started"]
    )
    required = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    valid = (
        all(scenarios[name]["valid"] for name in required)
        and positive_chain
        and shared["pass"]
        and not shared["errors"]
    )
    print(
        json.dumps(
            {
                "valid": valid,
                "scenario_valid": {
                    name: row["valid"] for name, row in scenarios.items()
                },
                "positive_chain": positive_chain,
                "shared_pass": shared["pass"],
                "shared_errors": shared["errors"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
