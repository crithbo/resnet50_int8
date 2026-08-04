from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base


INSTALL_NAME = "r5_qadd_n7_minpre_v11"
SOURCE_NAME = "r5_qadd_n7_first_request_chain_v10"
ZIP_SHA256 = "d8a20d54ca83d0607a79740be79f632fce6115f9d1b6e58fb1e9f40d60c828d1"
SOURCE_ZIP_SHA256 = "573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf"
SERVER_RULE_SHA256 = "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-minpre-v11"
    / "report.json"
)
COMPILE_STUB_EXIT = 86


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_base() -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_NAME = SOURCE_NAME
    base.ZIP_PATH = ZIP_PATH
    base.ZIP_SHA256 = ZIP_SHA256
    base.SIDECAR_PATH = SIDECAR_PATH
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.REPORT_PATH = REPORT_PATH
    base.BUILD_RECEIPT = BUILD_RECEIPT


def _load_final() -> tuple[dict[str, bytes], dict[str, Any], str, str]:
    members, manifest, _ = base._load_zip(ZIP_PATH, INSTALL_NAME)
    root = f"{INSTALL_NAME}/"
    runner = members[root + "PREPARE_AND_RUN.sh"].decode("utf-8")
    runtime = members[
        root + "package_tools/qlinearadd_node0007_server_runtime.py"
    ].decode("utf-8")
    return members, manifest, runner, runtime


def _single_source_identity(manifest: dict[str, Any], runner: str) -> dict[str, Any]:
    literal_absent = INSTALL_NAME not in runner
    binding = (
        'install_name="$(python3 "$runtime" manifest-value '
        '--package-root "$package_root" --key install_name)"'
    )
    profile = manifest.get("runtime_preflight_profile", {})
    passed = (
        literal_absent
        and runner.count(binding) == 1
        and profile.get("identity_single_source")
        == "TEST_PACKAGE_MANIFEST.json:install_name"
        and profile.get("runner_hardcoded_expected_sha_count") == 0
        and re.search(r"(?i)(expected_)?sha(256)?=[\"'][0-9a-f]{64}", runner)
        is None
    )
    return {
        "passed": passed,
        "runner_install_name_literal_absent": literal_absent,
        "manifest_value_binding_count": runner.count(binding),
        "hardcoded_expected_sha_match": bool(
            re.search(r"(?i)(expected_)?sha(256)?=[\"'][0-9a-f]{64}", runner)
        ),
    }


def _minimal_runtime_preflight(
    manifest: dict[str, Any], runner: str, runtime: str
) -> dict[str, Any]:
    precompile = runner.split('cd "$server_root"', 1)[0]
    forbidden_source_gate_patterns = {
        "server_rtl": r"(?is)(test|find|grep|sha256sum|cmp).{0,120}\$server_root.{0,120}/rtl",
        "server_makefile": r"(?is)(test|find|grep|sha256sum|cmp).{0,120}\$server_root.{0,120}Makefile",
        "server_filelist": r"(?is)(test|find|grep|sha256sum|cmp).{0,120}\$server_root.{0,120}filelist",
        "server_tb": r"(?is)(test|find|grep|sha256sum|cmp).{0,120}\$server_root.{0,120}\bTB\b",
        "server_git": r"(?is)\bgit\b.{0,120}\$server_root",
        "server_readme": r"(?is)(test|find|grep|sha256sum|cmp).{0,120}\$server_root.{0,120}README",
    }
    hits = {
        name: bool(re.search(pattern, precompile))
        for name, pattern in forbidden_source_gate_patterns.items()
    }
    profile = manifest.get("runtime_preflight_profile", {})
    allowed_commands = {"python3", "timeout", "make", "date", "tail", "grep"}
    match = re.search(
        r"for tool in ([^;]+); do command -v", precompile, re.MULTILINE
    )
    observed_commands = set(match.group(1).split()) if match else set()
    passed = (
        not any(hits.values())
        and observed_commands == allowed_commands
        and profile.get("server_source_preflight_performed") is False
        and profile.get("server_source_identity_bound") is False
        and "server_source_files_inspected\": False" in runtime
        and "file_records(cfg_root" in runtime
        and "file_records(server_root" not in runtime
    )
    return {
        "passed": passed,
        "forbidden_server_source_gate_hits": hits,
        "generic_command_check_exact": sorted(observed_commands),
        "package_and_installed_payload_only": (
            "file_records(cfg_root" in runtime
            and "file_records(server_root" not in runtime
        ),
    }


def _to_bash(path: Path) -> str:
    value = path.resolve().as_posix()
    match = re.match(r"^([A-Za-z]):/(.*)$", value)
    if match:
        return f"/{match.group(1).lower()}/{match.group(2)}"
    return value


def _git_bash() -> Path:
    candidates = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Git Bash is unavailable for runner positive control")


def _extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        archive.extractall(destination)
    package = destination / INSTALL_NAME
    if not package.is_dir():
        raise RuntimeError("fresh extract root differs")
    return package


def _directory_records(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _write_stubs(tools: Path, marker: Path) -> None:
    tools.mkdir(parents=True)
    python = tools / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(_to_bash(Path(sys.executable)))} \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    make = tools / "make"
    make.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(_to_bash(marker))}\n"
        f"exit {COMPILE_STUB_EXIT}\n",
        encoding="utf-8",
        newline="\n",
    )
    mkdir = tools / "mkdir"
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


def _run_runner(
    package: Path, server: Path, tools: Path, timeout_seconds: int = 120
) -> subprocess.CompletedProcess[str]:
    command = (
        f"cd {shlex.quote(_to_bash(package))} && "
        f"PATH={shlex.quote(_to_bash(tools))}:/usr/bin:/bin "
        f"bash PREPARE_AND_RUN.sh {shlex.quote(_to_bash(server))}"
    )
    return subprocess.run(
        [str(_git_bash()), "--noprofile", "--norc", "-c", command],
        cwd=package,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _runner_controls() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".q11-pc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = _extract(ZIP_PATH, temp / "extract")
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub_argv.txt"
        _write_stubs(tools, marker)
        before = _directory_records(package)
        result = _run_runner(package, server, tools)
        after = _directory_records(package)
        evidence = server / f"evidence_{INSTALL_NAME}/actual_compile_argv.txt"
        positive = {
            "passed": (
                result.returncode == COMPILE_STUB_EXIT
                and marker.is_file()
                and evidence.is_file()
                and before == after
            ),
            "runner_exit_code": result.returncode,
            "expected_compile_stub_exit_code": COMPILE_STUB_EXIT,
            "compile_stub_reached": marker.is_file(),
            "actual_compile_argv_saved": evidence.is_file(),
            "package_tree_unchanged": before == after,
            "stderr_tail": result.stderr[-1000:],
        }

    with tempfile.TemporaryDirectory(prefix=".q11-nc-", dir=ROOT) as raw:
        temp = Path(raw)
        package = _extract(ZIP_PATH, temp / "extract")
        manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["README.md"]["sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        server = temp / "server"
        server.mkdir()
        tools = temp / "tools"
        marker = temp / "compile_stub_argv.txt"
        _write_stubs(tools, marker)
        result = _run_runner(package, server, tools)
        negative = {
            "passed": result.returncode == 5 and not marker.exists(),
            "runner_exit_code": result.returncode,
            "expected_precompile_exit_code": 5,
            "compile_stub_reached": marker.exists(),
            "stderr_tail": result.stderr[-1000:],
        }
    return {
        "safe_compile_stub_positive_control": positive,
        "wrong_payload_identity_negative_control": negative,
        "all_passed": positive["passed"] and negative["passed"],
    }


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_base()
    report = base.validate_final_zip(write_report=False)
    _, manifest, runner, runtime = _load_final()
    identity = _single_source_identity(manifest, runner)
    minimal = _minimal_runtime_preflight(manifest, runner, runtime)
    controls = _runner_controls()
    new_checks = {
        "manifest_single_source_identity": identity["passed"],
        "minimal_runtime_preflight": minimal["passed"],
        "runner_preflight_to_compile_positive_control": controls[
            "safe_compile_stub_positive_control"
        ]["passed"],
        "wrong_identity_precompile_negative_control": controls[
            "wrong_payload_identity_negative_control"
        ]["passed"],
    }
    report["checks"].update(new_checks)
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"observer: {error}" for error in report["binding_errors"])
    report.update(
        {
            "schema": "qlinearadd-node0007-minimal-runtime-final-zip-self-audit-v1",
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "manifest_single_source_identity": identity,
            "minimal_runtime_preflight": minimal,
            "runner_control_flow": controls,
            "v10_status": "QUARANTINED_RUNTIME_PREFLIGHT_IDENTITY_DUPLICATION",
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
        }
    )
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
