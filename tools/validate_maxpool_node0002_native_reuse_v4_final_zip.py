#!/usr/bin/env python3
"""Independent final-ZIP audit for the exact-native MaxPool node0002 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n2_maxpool_native_reuse_v4"
ZIP_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{INSTALL_NAME}.zip"
)
SIDECAR = Path(str(ZIP_PATH) + ".sha256")
REPORT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{INSTALL_NAME}.final_zip_rule_self_audit.json"
)
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
EXPECTED_STUB_EXIT = 86


class FinalZipAuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def records(root: Path, *, exclude_manifest: bool = False) -> dict[str, Any]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if not (
            exclude_manifest
            and path.relative_to(root).as_posix() == "TEST_PACKAGE_MANIFEST.json"
        )
    }


def _to_bash(path: Path) -> str:
    value = path.resolve().as_posix()
    match = re.match(r"^([A-Za-z]):/(.*)$", value)
    return f"/{match.group(1).lower()}/{match.group(2)}" if match else value


def _git_bash() -> Path:
    for path in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ):
        if path.is_file():
            return path
    raise FinalZipAuditError("Git Bash unavailable")


def _extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise FinalZipAuditError("ZIP CRC failure")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise FinalZipAuditError("ZIP duplicate member")
        for name in names:
            pure = PurePosixPath(name)
            if (
                pure.is_absolute()
                or not pure.parts
                or pure.parts[0] != INSTALL_NAME
                or any(part in {"", ".", ".."} for part in pure.parts)
            ):
                raise FinalZipAuditError(f"unsafe ZIP path: {name}")
        archive.extractall(destination)
    package = destination / INSTALL_NAME
    if not package.is_dir():
        raise FinalZipAuditError("ZIP root differs")
    return package


def _rule_current_match(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    errors = []
    for receipt in manifest.get("rule_receipts", []):
        path = ROOT / str(receipt.get("path", ""))
        if (
            not path.is_file()
            or path.stat().st_size != receipt.get("size_bytes")
            or sha256(path) != receipt.get("sha256")
        ):
            errors.append(str(receipt.get("path")))
    return not errors, errors


def audit_tree(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid": False, "errors": [f"manifest parse: {exc}"]}
    actual = records(package, exclude_manifest=True)
    if manifest.get("files") != actual:
        errors.append("manifest exact-set differs")
    source = (
        package
        / "workload/runtime/source_config/"
        "maxpool_config_16_112_112_stride2_padding1.json.original"
    )
    if not source.is_file() or sha256(source) != SOURCE_JSON_SHA256:
        errors.append("source JSON byte identity differs")
    materialized = package / "validation/materialized_diff.json"
    if not materialized.is_file():
        errors.append("materialized diff receipt missing")
    else:
        diff = json.loads(materialized.read_text(encoding="utf-8"))
        if (
            diff.get("operator_json_diff_count") != 0
            or diff.get("semantic_non_base_diff_count") != 0
            or diff.get("planner_owned_base_diff_count") != 0
        ):
            errors.append("operator semantic diff differs")
    if (
        manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or manifest.get("reuse_class") != "EXACT_FULL_OPERATOR"
        or manifest.get("numeric_analysis_repeated") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("server_rtl_entries") != 0
    ):
        errors.append("claim boundary differs")
    rule_ok, drift = _rule_current_match(manifest)
    if not rule_ok:
        errors.append(f"post-generation rule drift: {drift}")
    required_ids = {
        "CDA-REUSE-FIRST-DEFERRED-RETEST-001",
        "CDA-GA-INT8-MAX-PIPE-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
    }
    if not required_ids.issubset(set(manifest.get("rule_ids", []))):
        errors.append("required rule ID missing")
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    runtime = (
        package
        / "package_tools/maxpool_node0002_native_reuse_server_runtime_v4.py"
    ).read_text(encoding="utf-8")
    observer = (package / "tb_probe/native_return_observer.svh")
    observer_text = observer.read_text(encoding="utf-8") if observer.is_file() else ""
    observer_contract = manifest.get("observer_binding_four_way", {})
    if (
        not observer.is_file()
        or sha256(observer) != observer_contract.get("source_sha256")
        or observer.stat().st_size != observer_contract.get("source_size_bytes")
        or "+define+NATIVE_RETURN_OBSERVER_ENABLE" not in runner
        or "+incdir+${package_root}/tb_probe" not in runner
        or re.search(
            r"(?<![A-Za-z0-9_])\+RETURN_OBSERVER(?:\s|$)", runner
        )
        is None
        or "[MAXPOOL_RETURN_OBSERVER] enabled" not in observer_text
        or "return_observer.log" not in runtime
    ):
        errors.append("observer four-way binding differs")
    if (
        observer_text.count("| CANONICAL_MAXPOOL_DIAG_DECISION_V1 |") != 1
        or "return_mp_p0_capture" not in observer_text
        or "return_mp_ga_output" not in observer_text
        or "return_mp_active_cycles % return_mp_sample_cycles" not in observer_text
        or "always @(negedge u_NDP_Top_new.clk_db)" not in observer_text
        or "always @(posedge u_NDP_Top_new.clk_sg)" not in observer_text
    ):
        errors.append("qualified/canonical diagnostic contract differs")
    progress_assignment = re.search(
        r"return_mp_progress\s*=\s*(.*?)\s*;",
        observer_text,
        flags=re.DOTALL,
    )
    if (
        progress_assignment is None
        or "raw_p0_valid" in progress_assignment.group(1)
        or "raw_p0_ready" in progress_assignment.group(1)
    ):
        errors.append("raw level incorrectly contributes to progress")
    forbidden_server_checks = (
        "git -C",
        "rg ",
        "find ",
        "NDP_Top_phy_filelist",
        "README_HARDWARE_SIM_ENTRY",
        "server_root.rglob",
        "file_records(server_root",
    )
    if any(token in runner or token in runtime for token in forbidden_server_checks):
        errors.append("runtime preflight inspects server source")
    if "manifest-value" not in runner or INSTALL_NAME in runner:
        errors.append("manifest is not sole runtime identity source")
    if (
        "actual_compile_argv.txt" not in runner
        or "simulator_argv.txt" not in runner
        or "host_progress.log" not in runner
        or "trap 'termination_signal=INT" not in runner
    ):
        errors.append("runner progress/signal return contract differs")
    return {"valid": not errors, "errors": errors}


def _write_stubs(tool_root: Path, marker: Path) -> None:
    tool_root.mkdir(parents=True)
    python = tool_root / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(_to_bash(Path(sys.executable)))} \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    make = tool_root / "make"
    make.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(_to_bash(marker))}\n"
        f"exit {EXPECTED_STUB_EXIT}\n",
        encoding="utf-8",
        newline="\n",
    )
    mkdir = tool_root / "mkdir"
    mkdir.write_text(
        "#!/usr/bin/env bash\n"
        "args=()\n"
        "for arg in \"$@\"; do [ \"$arg\" = \"-p\" ] || args+=(\"$arg\"); done\n"
        "exec python3 -c 'import os,sys; "
        "[os.makedirs(p, exist_ok=True) for p in sys.argv[1:]]' \"${args[@]}\"\n",
        encoding="utf-8",
        newline="\n",
    )
    python.chmod(0o755)
    make.chmod(0o755)
    mkdir.chmod(0o755)


def _run_runner(package: Path, server: Path, tools: Path) -> subprocess.CompletedProcess[str]:
    command = (
        f"cd {shlex.quote(_to_bash(package))} && "
        f"PATH={shlex.quote(_to_bash(tools))}:/usr/bin:/bin "
        f"bash PREPARE_AND_RUN.sh {shlex.quote(_to_bash(server))}"
    )
    return subprocess.run(
        [str(_git_bash()), "--noprofile", "--norc", "-c", command],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def runner_controls() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".mp-v4-pc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = _extract(ZIP_PATH, temp / "extract")
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub.txt"
        _write_stubs(tools, marker)
        before = records(package)
        result = _run_runner(package, server, tools)
        after = records(package)
        compile_argv = (
            server
            / f"evidence_{INSTALL_NAME}/actual_compile_argv.txt"
        )
        positive = {
            "passed": (
                result.returncode == EXPECTED_STUB_EXIT
                and marker.is_file()
                and compile_argv.is_file()
                and before == after
            ),
            "runner_exit": result.returncode,
            "expected_exit": EXPECTED_STUB_EXIT,
            "make_reached": marker.is_file(),
            "actual_compile_argv_saved": compile_argv.is_file(),
            "package_tree_unchanged": before == after,
            "stderr_tail": result.stderr[-1000:],
        }
    with tempfile.TemporaryDirectory(prefix=".mp-v4-nc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = _extract(ZIP_PATH, temp / "extract")
        manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["README.md"]["sha256"] = "0" * 64
        write_json(manifest_path, manifest)
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub.txt"
        _write_stubs(tools, marker)
        result = _run_runner(package, server, tools)
        negative = {
            "passed": result.returncode == 5 and not marker.exists(),
            "runner_exit": result.returncode,
            "expected_exit": 5,
            "make_reached": marker.exists(),
            "stderr_tail": result.stderr[-1000:],
        }
    return {
        "positive": positive,
        "wrong_identity_negative": negative,
        "all_passed": positive["passed"] and negative["passed"],
    }


def negative_controls(package: Path) -> dict[str, Any]:
    mutations: dict[str, Any] = {
        "source_json_changed": lambda root: (
            root
            / "workload/runtime/source_config/"
            "maxpool_config_16_112_112_stride2_padding1.json.original"
        ).write_bytes(b"{}\n"),
        "observer_source_removed": lambda root: (
            root / "tb_probe/native_return_observer.svh"
        ).unlink(),
        "compile_enable_removed": lambda root: (
            root / "PREPARE_AND_RUN.sh"
        ).write_text(
            (root / "PREPARE_AND_RUN.sh")
            .read_text(encoding="utf-8")
            .replace("+define+NATIVE_RETURN_OBSERVER_ENABLE", ""),
            encoding="utf-8",
            newline="\n",
        ),
        "runtime_enable_removed": lambda root: (
            root / "PREPARE_AND_RUN.sh"
        ).write_text(
            (root / "PREPARE_AND_RUN.sh")
            .read_text(encoding="utf-8")
            .replace("+RETURN_OBSERVER", "+RETURN_OBSERVER_REMOVED"),
            encoding="utf-8",
            newline="\n",
        ),
        "canonical_prefix_removed": lambda root: (
            root / "tb_probe/native_return_observer.svh"
        ).write_text(
            (root / "tb_probe/native_return_observer.svh")
            .read_text(encoding="utf-8")
            .replace("| CANONICAL_MAXPOOL_DIAG_DECISION_V1 |", "| DIAG_SUMMARY |"),
            encoding="utf-8",
            newline="\n",
        ),
        "raw_level_added_to_progress": lambda root: (
            root / "tb_probe/native_return_observer.svh"
        ).write_text(
            (root / "tb_probe/native_return_observer.svh")
            .read_text(encoding="utf-8")
            .replace(
                "return_mp_capture + return_mp_ga_output +",
                "return_mp_capture + return_mp_ga_output + return_mp_raw_p0_valid +",
                1,
            ),
            encoding="utf-8",
            newline="\n",
        ),
        "required_rule_id_removed": lambda root: _remove_rule(root),
    }
    results = {}
    for name, mutate in mutations.items():
        with tempfile.TemporaryDirectory(prefix=".mp-v4-neg-", dir=ROOT) as raw:
            root = Path(raw) / INSTALL_NAME
            shutil.copytree(package, root)
            mutate(root)
            _rebind_manifest_files(root)
            outcome = audit_tree(root)
            results[name] = {
                "failed_closed": not outcome["valid"],
                "errors": outcome["errors"],
            }
    return {
        "controls": results,
        "all_failed_closed": all(item["failed_closed"] for item in results.values()),
    }


def _remove_rule(root: Path) -> None:
    path = root / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["rule_ids"] = [
        value
        for value in manifest["rule_ids"]
        if value != "CDA-REUSE-FIRST-DEFERRED-RETEST-001"
    ]
    write_json(path, manifest)


def _rebind_manifest_files(root: Path) -> None:
    path = root / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = records(root, exclude_manifest=True)
    write_json(path, manifest)


def validate() -> dict[str, Any]:
    if not ZIP_PATH.is_file() or not SIDECAR.is_file():
        raise FinalZipAuditError("ZIP or sidecar missing")
    sidecar = SIDECAR.read_text(encoding="ascii").split()
    if len(sidecar) != 2 or sidecar[0] != sha256(ZIP_PATH) or sidecar[1] != ZIP_PATH.name:
        raise FinalZipAuditError("sidecar differs")
    with tempfile.TemporaryDirectory(prefix=".mp-v4-audit-", dir=ROOT) as raw:
        package = _extract(ZIP_PATH, Path(raw))
        tree = audit_tree(package)
        before = records(package)
        runtime = (
            package
            / "package_tools/maxpool_node0002_native_reuse_server_runtime_v4.py"
        )
        preflight_output = Path(raw) / "preflight.json"
        preflight_result = subprocess.run(
            [
                sys.executable,
                str(runtime),
                "preflight-package",
                "--package-root",
                str(package),
                "--install-name",
                INSTALL_NAME,
                "--output",
                str(preflight_output),
            ],
            cwd=package,
            capture_output=True,
            text=True,
            check=False,
        )
        after = records(package)
        syntax_result = subprocess.run(
            [str(_git_bash()), "-n", str(package / "PREPARE_AND_RUN.sh")],
            cwd=package,
            capture_output=True,
            text=True,
            check=False,
        )
        negatives = negative_controls(package)
    controls = runner_controls()
    errors = list(tree["errors"])
    if preflight_result.returncode != 0:
        errors.append(f"fresh preflight failed: {preflight_result.stderr[-500:]}")
    if before != after:
        errors.append("fresh preflight mutated package")
    if syntax_result.returncode != 0:
        errors.append(f"runner bash syntax failed: {syntax_result.stderr[-500:]}")
    if not negatives["all_failed_closed"]:
        errors.append("one or more negative controls did not fail closed")
    if not controls["all_passed"]:
        errors.append("runner positive/negative control differs")
    report = {
        "schema": "maxpool-node0002-native-reuse-final-zip-audit-v4",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_size_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "sidecar_sha256": sha256(SIDECAR),
        "tree_audit": tree,
        "fresh_extract_preflight_exit": preflight_result.returncode,
        "fresh_extract_tree_immutable": before == after,
        "runner_bash_syntax_exit": syntax_result.returncode,
        "runner_controls": controls,
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": negatives["all_failed_closed"],
        "numeric_analysis_repeated": False,
        "source_json_sha256": SOURCE_JSON_SHA256,
        "package_status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
    }
    write_json(REPORT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        report = validate()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1
    except Exception as exc:
        print(f"MaxPool final-ZIP audit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
