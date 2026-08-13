#!/usr/bin/env python3
"""Final-ZIP audit for native Conv p13 path-budget/early-finalizer fix."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from validate_conv_native_four_lane_0ccae916_p12_rootgate_package import (
    STUB_FINALIZER,
    STUB_GUARD,
    STUB_MAKE,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p12_rootgate"
PACKAGE_ID = "r5_n4_0cc_p13_pathfix"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
SOURCE_SHA256 = (
    "ab8f13aaa2e66f01bd9c5461f8131b9cf0f89fb1706feb5fcd6aac0f15957646"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "pending"
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p12_preflight_failure_p13_pathfix"
)
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
PYTHON = Path(sys.executable).resolve()
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PRODUCTION_RESULT_ROOT = "/home/panqs/ndp/simresult"
ACTUAL_SERVER_ROOT_TEXT = "/home/panqs/ndp/NDP_copy02"


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
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def posix_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    if len(value) >= 3 and value[1] == ":" and value[2] == "/":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def safe_extract(zip_path: Path, target: Path, expected: str) -> Path:
    package = target / expected
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise AuditError(f"ZIP CRC differs: {zip_path}")
        names = [info.filename for info in archive.infolist()]
        if len(names) != len(set(names)):
            raise AuditError("ZIP contains duplicate members")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != expected
            ):
                raise AuditError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = package.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return package


def zip_payloads(zip_path: Path, expected: str) -> dict[str, bytes]:
    values: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            if not pure.parts or pure.parts[0] != expected:
                raise AuditError(f"unexpected ZIP root: {info.filename}")
            values[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    return values


def package_records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def run_python(
    script: Path, *args: str, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), str(script), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def frozen_surface_audit() -> dict[str, Any]:
    source = zip_payloads(SOURCE_ZIP, SOURCE_ID)
    successor = zip_payloads(ZIP_PATH, PACKAGE_ID)
    allowed_changes = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_manifest.json",
        "package_tools/fixed_simresult_publisher.py",
    }
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    frozen_prefixes = (
        "workload/runtime/",
        "diagnostics/",
        "tb_probe/",
    )
    frozen_explicit = {
        "package_tools/node0004_assumed_hardware_server_runtime.py",
        "package_tools/node0004_assumed_hardware_server_runtime_v2_base.py",
        "package_tools/node0004_package_observer_guard.py",
        "package_tools/node0004_public_order_finalizer.py",
        "package_tools/node0004_triggered_causal_finalizer.py",
        "package_tools/ndp_root_toplevel_exact_set_gate.py",
    }
    frozen = [
        path
        for path in all_paths
        if path.startswith(frozen_prefixes) or path in frozen_explicit
    ]
    frozen_mismatch = [
        path for path in frozen if source.get(path) != successor.get(path)
    ]
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "changed_paths": changed,
        "allowed_changed_paths": sorted(allowed_changes),
        "frozen_path_count": len(frozen),
        "frozen_mismatch": frozen_mismatch,
        "valid": (
            sha256(SOURCE_ZIP) == SOURCE_SHA256
            and set(changed) == allowed_changes
            and not frozen_mismatch
        ),
    }


def static_audit(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    observed = package_records(package)
    budget = manifest.get("path_length_budget", {})
    longest = budget.get("longest_projected_relative_path")
    relative_chars = budget.get("max_projected_relative_path_chars")
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    fixed_publication = manifest.get("fixed_server_result_publication", {})
    root_contract = manifest.get("ndp_root_toplevel_contract", {})
    expected_return_zip = (
        f"{PRODUCTION_RESULT_ROOT}/{PACKAGE_ID}_return.zip"
    )
    expected_return_sidecar = f"{expected_return_zip}.sha256"
    expected_work_root = (
        f"{PRODUCTION_RESULT_ROOT}/.{PACKAGE_ID}.run.<pid>"
    )
    exact_runner_order = {
        "root_snapshot_before_result_root": runner.index(
            'pre_snapshot_json="$(python3 "$root_gate"'
        )
        < runner.index('mkdir -p -- "$result_root"'),
        "evidence_before_path_budget": runner.index(
            'mkdir -p "$cfg_root"'
        )
        < runner.index('python3 "$runtime" path-budget'),
        "exit_trap_before_path_budget": runner.index(
            "trap 'finalize $?' EXIT"
        )
        < runner.index('python3 "$runtime" path-budget'),
        "signal_traps_before_path_budget": runner.index(
            "trap 'on_signal TERM 143' TERM"
        )
        < runner.index('python3 "$runtime" path-budget'),
        "path_budget_before_package_preflight": runner.index(
            'python3 "$runtime" path-budget'
        )
        < runner.index('python3 "$runtime" preflight'),
        "preflight_before_compile": runner.index(
            'python3 "$runtime" preflight'
        )
        < runner.index('cd "$server_root"'),
    }
    sidecar_tokens = SIDECAR.read_text(encoding="ascii").split()
    actual_projected = len(ACTUAL_SERVER_ROOT_TEXT) + 1 + int(relative_chars)
    valid = (
        sidecar_tokens == [sha256(ZIP_PATH), ZIP_PATH.name]
        and manifest.get("files") == observed
        and manifest.get("package_identity") == PACKAGE_ID
        and manifest.get("install_name") == WORKLOAD_INSTALL_NAME
        and isinstance(longest, str)
        and len(longest) == relative_chars == 115
        and budget.get("max_projected_absolute_path_chars") == 212
        and actual_projected == 142
        and actual_projected
        <= budget.get("max_projected_absolute_path_limit_chars", -1)
        and all(exact_runner_order.values())
        and runner.count(PRODUCTION_RESULT_ROOT) > 0
        and fixed_publication.get("return_zip") == expected_return_zip
        and fixed_publication.get("return_sidecar")
        == expected_return_sidecar
        and root_contract.get("root_external_write_roots")
        == [PRODUCTION_RESULT_ROOT, expected_work_root]
    )
    return {
        "zip_sha256": sha256(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "sidecar_valid": sidecar_tokens == [sha256(ZIP_PATH), ZIP_PATH.name],
        "manifest_exact_set_valid": manifest.get("files") == observed,
        "package_identity_valid": (
            manifest.get("package_identity") == PACKAGE_ID
        ),
        "longest_projected_relative_path": longest,
        "declared_relative_chars": relative_chars,
        "observed_relative_chars": len(longest) if isinstance(longest, str) else None,
        "declared_target_projection_chars": budget.get(
            "max_projected_absolute_path_chars"
        ),
        "actual_server_root_chars": len(ACTUAL_SERVER_ROOT_TEXT),
        "actual_server_projection_chars": actual_projected,
        "exact_runner_order": exact_runner_order,
        "production_result_root_literal": PRODUCTION_RESULT_ROOT,
        "fixed_publication_return_zip": fixed_publication.get("return_zip"),
        "fixed_publication_return_sidecar": fixed_publication.get(
            "return_sidecar"
        ),
        "root_external_write_roots": root_contract.get(
            "root_external_write_roots"
        ),
        "valid": valid,
    }


def mutate_manifest(package: Path, mutation: str) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    if mutation == "stale_count":
        budget["max_projected_relative_path_chars"] -= 1
    elif mutation == "longest_changed":
        budget["longest_projected_relative_path"] += "x"
    elif mutation == "over_limit":
        budget["max_projected_absolute_path_limit_chars"] = 1
    else:
        raise AuditError(f"unknown mutation: {mutation}")
    write_json(path, manifest)


def exact_runtime_audit(package: Path, target: Path) -> dict[str, Any]:
    runtime = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    server_root = target / "NDP_copy_exact"
    server_root.mkdir(parents=True)
    positive_budget = run_python(
        runtime,
        "path-budget",
        "--package-root",
        str(package),
        "--server-root",
        str(server_root),
    )
    positive_preflight = run_python(
        runtime, "preflight", "--package-root", str(package)
    )
    negatives: dict[str, Any] = {}
    for mutation in ("stale_count", "longest_changed", "over_limit"):
        mutated = target / mutation / PACKAGE_ID
        shutil.copytree(package, mutated)
        mutate_manifest(mutated, mutation)
        completed = run_python(
            mutated
            / "package_tools/node0004_assumed_hardware_server_runtime.py",
            "path-budget",
            "--package-root",
            str(mutated),
            "--server-root",
            str(server_root),
        )
        expected = (
            "server root exceeds path budget"
            if mutation == "over_limit"
            else "path budget is malformed"
        )
        negatives[mutation] = {
            "exit_code": completed.returncode,
            "stderr_tail": completed.stderr[-1000:],
            "expected_error": expected,
            "valid": completed.returncode != 0
            and expected in completed.stderr,
        }
    preflight_mutated = target / "preflight_file_mutation" / PACKAGE_ID
    shutil.copytree(package, preflight_mutated)
    with (preflight_mutated / "README.md").open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("mutation\n")
    preflight_negative = run_python(
        preflight_mutated
        / "package_tools/node0004_assumed_hardware_server_runtime.py",
        "preflight",
        "--package-root",
        str(preflight_mutated),
    )
    positive_budget_value = (
        json.loads(positive_budget.stdout)
        if positive_budget.returncode == 0
        else {}
    )
    positive_preflight_value = (
        json.loads(positive_preflight.stdout)
        if positive_preflight.returncode == 0
        else {}
    )
    preflight_negative_value = {
        "exit_code": preflight_negative.returncode,
        "stderr_tail": preflight_negative.stderr[-1000:],
        "valid": preflight_negative.returncode != 0
        and "package exact-set differs" in preflight_negative.stderr,
    }
    valid = (
        positive_budget.returncode == 0
        and positive_budget_value.get("valid") is True
        and positive_budget_value.get(
            "max_projected_relative_path_chars"
        )
        == 115
        and positive_preflight.returncode == 0
        and positive_preflight_value.get("valid") is True
        and all(item["valid"] for item in negatives.values())
        and preflight_negative_value["valid"]
    )
    return {
        "positive_path_budget": {
            "exit_code": positive_budget.returncode,
            "receipt": positive_budget_value,
            "stderr": positive_budget.stderr,
        },
        "positive_preflight": {
            "exit_code": positive_preflight.returncode,
            "receipt": positive_preflight_value,
            "stderr": positive_preflight.stderr,
        },
        "path_budget_negatives": negatives,
        "preflight_file_mutation_negative": preflight_negative_value,
        "valid": valid,
    }


def runtime_wrapper_text(
    exact_runtime: Path, exact_package: Path, marker: Path
) -> str:
    return f'''#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

EXACT_RUNTIME = Path({str(exact_runtime)!r})
EXACT_PACKAGE = Path({str(exact_package)!r})
MARKER = Path({str(marker)!r})

def option(name):
    index = sys.argv.index(name)
    return Path(sys.argv[index + 1])

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\\n", encoding="utf-8")

command = sys.argv[1]
if command in {{"path-budget", "preflight"}}:
    args = sys.argv[1:]
    index = args.index("--package-root")
    args[index + 1] = str(EXACT_PACKAGE)
    completed = subprocess.run([sys.executable, str(EXACT_RUNTIME), *args])
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    with MARKER.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({{
            "command": command,
            "exit_code": completed.returncode,
            "exact_runtime": str(EXACT_RUNTIME),
            "exact_package": str(EXACT_PACKAGE),
        }}) + "\\n")
    raise SystemExit(completed.returncode)
if command == "verify-install":
    print(json.dumps({{"valid": True, "command": command, "receipt_reuse": True}}))
    raise SystemExit(0)
if command == "compile-identity":
    write(option("--output"), {{"valid": True, "collection_valid": True, "stub": True}})
elif command in {{"feature-binding", "qualify-run"}}:
    write(option("--output"), {{"valid": True, "command": command}})
elif command == "analyze":
    evidence = option("--evidence-root")
    write(evidence / "SERVER_RESULT_GATE.json", {{
        "schema": "local-runner-control-flow-result-v1",
        "status": "LOCAL_RUNNER_HARNESS_ONLY",
        "valid": False,
        "claim_boundary": "no DUT",
    }})
else:
    raise SystemExit("unexpected runtime command: " + command)
print(json.dumps({{"valid": True, "command": command}}))
'''


def direct_set(root: Path) -> list[dict[str, str]]:
    result = []
    for child in root.iterdir():
        mode = child.lstat().st_mode
        kind = (
            "directory"
            if stat.S_ISDIR(mode)
            else "file"
            if stat.S_ISREG(mode)
            else "other"
        )
        result.append({"name": child.name, "type": kind})
    return sorted(result, key=lambda item: os.fsencode(item["name"]))


def prepare_runner_harness(
    package: Path, scenario_root: Path, mode: str
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    exact_package = scenario_root / "exact" / PACKAGE_ID
    local_package = scenario_root / PACKAGE_ID
    shutil.copytree(package, exact_package)
    shutil.copytree(package, local_package)
    if mode == "path_budget_fail":
        mutate_manifest(exact_package, "stale_count")
    elif mode == "preflight_fail":
        with (exact_package / "README.md").open(
            "a", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write("exact-preflight-negative\n")
    marker = scenario_root / "exact_runtime_calls.jsonl"
    wrapper = scenario_root / "runtime_wrapper.py"
    wrapper.write_text(
        runtime_wrapper_text(
            exact_package
            / "package_tools/node0004_assumed_hardware_server_runtime.py",
            exact_package,
            marker,
        ),
        encoding="utf-8",
        newline="\n",
    )
    result_root = scenario_root / "simresult"
    runner_result_root = "../simresult"
    runner = local_package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    runner_text = runner_text.replace(
        'runtime="$package_root/package_tools/'
        'node0004_assumed_hardware_server_runtime.py"',
        f'runtime="{posix_path(wrapper)}"',
    )
    runner_text = runner_text.replace(
        PRODUCTION_RESULT_ROOT, runner_result_root
    )
    runner_text = runner_text.replace(
        '[ "$resolved_result_root" = "../simresult" ] || exit 9',
        '[ -n "$resolved_result_root" ] || exit 9',
    )
    runner.write_text(runner_text, encoding="utf-8", newline="\n")
    publisher = (
        local_package / "package_tools/fixed_simresult_publisher.py"
    )
    publisher_text = publisher.read_text(encoding="utf-8").replace(
        PRODUCTION_RESULT_ROOT, "../simresult"
    )
    publisher_text = publisher_text.replace(
        "    if result_root.resolve() != result_root or not os.access(\n",
        "    if not os.access(\n",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("result_root") != str(result_root)',
        "False",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("return_zip") != str(final_zip)',
        "False",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("return_sidecar")\n'
        "        != str(final_sidecar)",
        "False",
    )
    publisher.write_text(
        publisher_text, encoding="utf-8", newline="\n"
    )
    (local_package / "package_tools/node0004_package_observer_guard.py").write_text(
        STUB_GUARD, encoding="utf-8", newline="\n"
    )
    for name in (
        "node0004_public_order_finalizer.py",
        "node0004_triggered_causal_finalizer.py",
    ):
        (local_package / "package_tools" / name).write_text(
            STUB_FINALIZER, encoding="utf-8", newline="\n"
        )
    stub_bin = scenario_root / "bin"
    stub_bin.mkdir()
    fake_make = stub_bin / "make"
    fake_make.write_text(STUB_MAKE, encoding="utf-8", newline="\n")
    fake_make.chmod(fake_make.stat().st_mode | stat.S_IXUSR)
    python3 = stub_bin / "python3"
    python3.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(posix_path(PYTHON))} \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    python3.chmod(python3.stat().st_mode | stat.S_IXUSR)
    server_root = scenario_root / "NDP_copy_stub"
    server_root.mkdir()
    (server_root / "existing_dir").mkdir()
    (server_root / "existing_file.txt").write_text(
        "stable\n", encoding="utf-8"
    )
    (server_root / "Makefile.tb_NDP_Top_new_phy").write_text(
        "stub\n", encoding="utf-8"
    )
    sim_marker = scenario_root / "sim_started.marker"
    env = dict(os.environ)
    env["PATH"] = f"{posix_path(stub_bin)}:/usr/bin:/bin"
    env["STUB_MARKER"] = posix_path(sim_marker)
    env["STUB_MODE"] = mode
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return local_package, server_root, result_root, marker, env


def return_json(return_zip: Path, suffix: str) -> dict[str, Any]:
    with zipfile.ZipFile(return_zip) as archive:
        names = [name for name in archive.namelist() if name.endswith(suffix)]
        if len(names) != 1:
            raise AuditError(f"return member differs for {suffix}: {names}")
        return json.loads(archive.read(names[0]).decode("utf-8"))


def run_runner_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    scenario_root = harness_root / mode
    scenario_root.mkdir(parents=True)
    local_package, server_root, result_root, marker, env = (
        prepare_runner_harness(package, scenario_root, mode)
    )
    runner = local_package / "PREPARE_AND_RUN.sh"
    if mode in {"hup", "int", "term"}:
        signal_name = {"hup": "HUP", "int": "INT", "term": "TERM"}[mode]
        anchor = "sim_pid=$!\n(\n  while kill -0"
        injection = (
            "sim_pid=$!\n"
            f"( sleep 0.2; kill -{signal_name} \"$$\" ) &\n"
            "(\n  while kill -0"
        )
        text = runner.read_text(encoding="utf-8")
        if text.count(anchor) != 1:
            raise AuditError("signal injection anchor differs")
        runner.write_text(
            text.replace(anchor, injection),
            encoding="utf-8",
            newline="\n",
        )
    before = direct_set(server_root)
    completed = subprocess.run(
        [str(BASH), posix_path(runner), posix_path(server_root)],
        cwd=local_package,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    after = direct_set(server_root)
    return_zip = result_root / f"{PACKAGE_ID}_return.zip"
    sidecar = Path(f"{return_zip}.sha256")
    if not return_zip.is_file() or not sidecar.is_file():
        raise AuditError(
            f"{mode} did not publish return: exit={completed.returncode} "
            f"stdout={completed.stdout[-1000:]} stderr={completed.stderr[-1000:]}"
        )
    calls = [
        json.loads(line)
        for line in marker.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    preflight = return_json(
        return_zip, "/evidence/package_local_preflight_status.json"
    )
    root_gate = return_json(
        return_zip, "/evidence/ndp_root_toplevel_gate.json"
    )
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    call_map = {item["command"]: item["exit_code"] for item in calls}
    compile_started = (
        preflight.get("production_compile_started") is True
    )
    expected_compile = mode not in {"path_budget_fail", "preflight_fail"}
    expected_path = 1 if mode == "path_budget_fail" else 0
    expected_preflight = (
        None
        if mode == "path_budget_fail"
        else 1
        if mode == "preflight_fail"
        else 0
    )
    expected_exit_zero = mode == "normal"
    valid = (
        before == after
        and root_gate.get("valid") is True
        and root_gate.get("ndp_root_toplevel_unchanged") is True
        and sidecar_tokens == [sha256(return_zip), return_zip.name]
        and call_map.get("path-budget") == expected_path
        and (
            "preflight" not in call_map
            if expected_preflight is None
            else call_map.get("preflight") == expected_preflight
        )
        and compile_started is expected_compile
        and (
            completed.returncode == 0
            if expected_exit_zero
            else completed.returncode != 0
        )
        and not (server_root / f"{PACKAGE_ID}_return.zip").exists()
        and not (local_package / f"{PACKAGE_ID}_return.zip").exists()
    )
    return {
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "exact_runtime_calls": calls,
        "package_local_preflight_status": preflight,
        "root_gate": root_gate,
        "root_before": before,
        "root_after": after,
        "root_direct_child_exact_set_unchanged": before == after,
        "compile_started": compile_started,
        "fixed_return_zip": str(return_zip),
        "fixed_return_sha256": sha256(return_zip),
        "sidecar_valid": sidecar_tokens
        == [sha256(return_zip), return_zip.name],
        "duplicates_absent": (
            not (server_root / f"{PACKAGE_ID}_return.zip").exists()
            and not (local_package / f"{PACKAGE_ID}_return.zip").exists()
        ),
        "valid": valid,
    }


def main() -> int:
    if REPORT.exists():
        raise AuditError("refusing to overwrite p13 final ZIP audit")
    if (
        not ZIP_PATH.is_file()
        or not SIDECAR.is_file()
        or not SOURCE_ZIP.is_file()
        or not BASH.is_file()
    ):
        raise AuditError("p13 audit inputs are missing")
    with tempfile.TemporaryDirectory(prefix=".p13_", dir=ROOT) as temp:
        temp_root = Path(temp)
        package = safe_extract(ZIP_PATH, temp_root / "extract", PACKAGE_ID)
        static = static_audit(package)
        frozen = frozen_surface_audit()
        exact = exact_runtime_audit(package, temp_root / "exact_runtime")
        scenarios = [
            run_runner_scenario(package, temp_root / "runner", mode)
            for mode in (
                "normal",
                "compile_fail",
                "hup",
                "int",
                "term",
                "path_budget_fail",
                "preflight_fail",
            )
        ]
    valid = (
        static["valid"]
        and frozen["valid"]
        and exact["valid"]
        and all(item["valid"] for item in scenarios)
    )
    result = {
        "schema": "conv-native-four-lane-p13-pathfix-final-zip-audit-v1",
        "status": (
            "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED"
        ),
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p12_zip_sha256": sha256(SOURCE_ZIP),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "exact_runtime_path_budget_and_preflight": exact,
        "exact_runner_harness": scenarios,
        "release_gate_matrix": {
            "core_always": (
                "PASS" if static["valid"] and frozen["valid"] else "FAIL"
            ),
            "runner": (
                "PASS"
                if exact["valid"] and all(item["valid"] for item in scenarios)
                else "FAIL"
            ),
            "package_local_hdl": "RECEIPT_REUSE",
            "materialized_config": "RECEIPT_REUSE",
            "diagnostic_semantics": "RECEIPT_REUSE",
            "return_result": (
                "PASS" if all(item["valid"] for item in scenarios) else "FAIL"
            ),
        },
        "server_action": False,
        "claim_boundary": (
            "exact package-local path-budget/preflight and isolated runner "
            "control-flow only; no DUT execution, natural terminal, formal "
            "320D, E3/E4/E5, numeric correctness, or performance claim"
        ),
    }
    write_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
