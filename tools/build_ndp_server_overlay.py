from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_execplan_hardware import (  # noqa: E402
    validate_conv_hardware_execplan_package,
)


OBSERVATION_FULL_FSDB = "full_fsdb"
OBSERVATION_TARGETED_VPD = "targeted_vpd"
OBSERVATION_COMPLETION_NO_WAVE = "completion_no_wave"
_TCL_TIME_RE = re.compile(r"^[1-9][0-9]*(?:ps|ns|us|ms|s)$")
_GIT_REVISION_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SERVER_TEXT_SUFFIXES = {".json", ".mk", ".sh", ".tcl", ".tsv", ".txt"}
_REQUIRED_SERVER_COMMANDS = (
    "awk",
    "basename",
    "cp",
    "date",
    "dirname",
    "find",
    "grep",
    "head",
    "ln",
    "make",
    "mkdir",
    "mkfifo",
    "mv",
    "od",
    "readlink",
    "rm",
    "sed",
    "sha256sum",
    "sleep",
    "sort",
    "stat",
    "tail",
    "tee",
    "timeout",
    "tr",
    "vcs",
    "wc",
    "zip",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rewrite_paths(value: Any, prefix: str) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_paths(item, prefix) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_paths(item, prefix) for item in value]
    if isinstance(value, str) and value.startswith("install/"):
        return f"{prefix}/{value}"
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_text_lf(path: Path, value: str) -> None:
    """Write server-facing text with deterministic UTF-8/LF line endings."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    path.write_bytes(normalized.encode("utf-8"))


def _looks_like_bit_text(payload: bytes) -> bool:
    if not payload:
        return False
    compact = payload.translate(None, b" \t\r\n")
    return bool(compact) and not (set(compact) - {ord("0"), ord("1")})


def _is_server_text_file(path: Path) -> bool:
    if path.suffix.lower() in _SERVER_TEXT_SUFFIXES:
        return True
    return path.suffix.lower() == ".bin" and _looks_like_bit_text(path.read_bytes())


def _server_text_paths(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and _is_server_text_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _normalize_server_text_tree(root: Path) -> list[str]:
    records: list[str] = []
    for path in _server_text_paths(root):
        payload = path.read_bytes()
        if b"\x00" in payload:
            raise ValueError(f"server text contains NUL bytes: {path}")
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"server text is not UTF-8/ASCII: {path}") from error
        normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if normalized != payload:
            path.write_bytes(normalized)
        records.append(path.relative_to(root).as_posix())
    return records


def _assert_server_text_lf(root: Path) -> list[str]:
    records: list[str] = []
    for path in _server_text_paths(root):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        cr_count = payload.count(b"\r")
        if cr_count:
            raise ValueError(
                f"server text is not LF-only: {relative}, cr_byte_count={cr_count}"
            )
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"server text is not UTF-8/ASCII: {relative}"
            ) from error
        records.append(relative)
    return records


def _copy_text_lf(source: Path, destination: Path) -> None:
    try:
        value = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"server contract is not UTF-8 text: {source}") from error
    _write_text_lf(destination, value)


def _audit_overlay_zip(
    zip_path: Path,
    *,
    expected_paths: set[str],
    text_paths: set[str],
) -> int:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected_paths:
            raise ValueError(
                "overlay ZIP exact set differs: "
                f"missing={sorted(expected_paths - set(names))[:5]}, "
                f"extra={sorted(set(names) - expected_paths)[:5]}"
            )
        for relative in sorted(text_paths):
            payload = archive.read(relative)
            cr_count = payload.count(b"\r")
            if cr_count:
                raise ValueError(
                    "overlay ZIP text is not LF-only: "
                    f"{relative}, cr_byte_count={cr_count}"
                )
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(
                    f"overlay ZIP text is not UTF-8/ASCII: {relative}"
                ) from error
    return len(text_paths)


def _find_bash() -> str:
    discovered = shutil.which("bash")
    if discovered:
        return discovered
    for candidate in (
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path(r"C:\Program Files\Git\bin\bash.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise ValueError("round1 selfcheck requires Bash with GNU awk")


def _shell_function_block(source: str, start: str, end: str) -> str:
    try:
        start_index = source.index(start)
        end_index = source.index(end, start_index)
    except ValueError as error:
        raise ValueError(
            f"runner selfcheck function boundary is missing: {start!r} -> {end!r}"
        ) from error
    return source[start_index:end_index]


def run_overlay_round1_selfcheck(
    package: Path,
    output: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Execute the formal generation-chain and real-install behavior check."""

    package = package.resolve()
    output = output.resolve()
    report_path = report_path.resolve()
    if report_path.exists():
        raise FileExistsError(f"refusing to replace a round1 report: {report_path}")
    try:
        report_path.relative_to(output)
    except ValueError:
        pass
    else:
        raise ValueError("round1 report must not be written inside the zipped overlay")

    zip_path = output.with_suffix(".zip")
    if not zip_path.is_file():
        raise ValueError("round1 selfcheck requires the final on-disk overlay ZIP")
    overlay_manifest_path = output / "OVERLAY_MANIFEST.json"
    overlay_manifest = _json(overlay_manifest_path)
    package_preflight = overlay_manifest.get("package_preflight")
    if (
        not isinstance(package_preflight, dict)
        or package_preflight.get("status")
        != "hardware_execplan_package_validated"
        or overlay_manifest.get("package_manifest_sha256")
        != _sha256(package / "manifest.json")
    ):
        raise ValueError("round1 package-validation binding differs")

    ndp_root = output / "NDP_copy01"
    runtime_roots = sorted(
        path
        for path in (ndp_root / "install" / "cfg_pkg").iterdir()
        if path.is_dir() and not path.is_symlink()
    )
    runners = sorted(ndp_root.glob("RUN_SERVER_*.sh"))
    if len(runtime_roots) != 1 or len(runners) != 1:
        raise ValueError("round1 overlay must contain one runtime root and one runner")
    runtime_root = runtime_roots[0]
    runner_path = runners[0]
    runner = runner_path.read_text(encoding="utf-8")
    run_id_index = runner.index('requested_server_run_id="${SERVER_RUN_ID:-run1}"')
    identity_index = runner.index("actual_runner_hash_line=$(sha256sum")
    cleanup_index = runner.index(
        "# A run ID owns exactly one canonical return directory/archive"
    )
    trap_index = runner.index("trap unexpected_runner_error ERR")
    command_gate_index = runner.index(
        f'for required_command in {" ".join(_REQUIRED_SERVER_COMMANDS)}; do'
    )
    if not run_id_index < identity_index < trap_index < command_gate_index < cleanup_index:
        raise ValueError(
            "runner identity, failure trap, command gate, and cleanup order differs"
        )
    if "mkdir " in runner[:identity_index] or "rm " in runner[:identity_index]:
        raise ValueError("runner mutates filesystem before authenticating itself")
    make_environment_index = runner.index(
        "unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL"
    )
    make_launch_index = runner.index('  "${run_argv[@]}"')
    if not cleanup_index < make_environment_index < make_launch_index:
        raise ValueError("runner make-environment sanitization order differs")
    preinstalled_file_count = sum(
        1 for path in (runtime_root / "install").rglob("*") if path.is_file()
    )
    if preinstalled_file_count != 272:
        raise ValueError(
            "round1 full install preloaded file count differs: "
            f"{preinstalled_file_count} != 272"
        )

    forbidden_awk_loop = "for (index ="
    if forbidden_awk_loop in runner:
        raise ValueError("runner uses GNU awk builtin function name as a loop variable")
    sink_program = (
        "BEGIN { for (slice_index = 0; slice_index < 28; slice_index++) "
        "print slice_index }"
    )
    if f"awk '{sink_program}'" not in runner:
        raise ValueError("runner diagnostic sink GNU awk program differs")

    bash_path = _find_bash()
    bash_syntax = subprocess.run(
        [bash_path, "-lc", 'bash -n "$1"', "round1-bash-n", runner_path.as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if bash_syntax.returncode != 0:
        raise ValueError(f"round1 runner Bash syntax failed: {bash_syntax.stderr}")
    awk_version = subprocess.run(
        [bash_path, "-lc", "awk --version | head -n 1"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if awk_version.returncode != 0 or "GNU Awk" not in awk_version.stdout:
        raise ValueError("round1 behavior tests require GNU awk")
    sink_enumeration = subprocess.run(
        [bash_path, "-lc", f"awk '{sink_program}'"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    sink_values = sink_enumeration.stdout.splitlines()
    if sink_enumeration.returncode != 0 or sink_values != [str(i) for i in range(28)]:
        raise ValueError(
            "round1 GNU awk diagnostic sink enumeration failed: "
            f"status={sink_enumeration.returncode}, stderr={sink_enumeration.stderr}"
        )

    sink_functions = _shell_function_block(
        runner,
        "install_runtime_log_sinks() {",
        "\ninstall_runtime_log_sinks\n",
    )
    sink_creation_start = sink_functions.index(
        '    mkdir -p "$(dirname "${sink_path}")"'
    )
    sink_creation_end = sink_functions.index(
        "    diagnostic_sink_count=$((diagnostic_sink_count + 1))",
        sink_creation_start,
    )
    sink_audit_functions = (
        sink_functions[:sink_creation_start]
        + "    printf '%s\\n' \"${sink_path}\" >> \"${sink_audit_log}\"\n"
        + sink_functions[sink_creation_end:]
    )
    sink_identity_start = sink_audit_functions.index(
        "  actual_sink_count=$(find sim_results -type l -print"
    )
    sink_identity_end = sink_audit_functions.index(
        "\n  fi", sink_identity_start
    ) + len("\n  fi")
    sink_audit_functions = (
        sink_audit_functions[:sink_identity_start]
        + "  actual_sink_count=$(wc -l < \"${sink_audit_log}\" | tr -d '[:space:]')\n"
        + "  unique_sink_count=$(LC_ALL=C sort -u \"${sink_audit_log}\" | wc -l | tr -d '[:space:]')\n"
        + "  if [ \"${actual_sink_count}\" -ne \"${expected_diagnostic_sink_count}\" ] || "
        + "[ \"${unique_sink_count}\" -ne \"${expected_diagnostic_sink_count}\" ]; then\n"
        + "    emit_preflight_failure \"runtime_log_sink_identity_mismatch\" "
        + "\"runtime sink paths must be an exact unique set\"\n"
        + "  fi"
        + sink_audit_functions[sink_identity_end:]
    )
    preflight_failure_function = _shell_function_block(
        runner,
        "emit_preflight_failure() {",
        "emit_runtime_failure() {",
    )
    runtime_failure_function = _shell_function_block(
        runner,
        "emit_runtime_failure() {",
        "unexpected_runner_error() {",
    )
    entrypoint_provenance_block = _shell_function_block(
        runner,
        "record_server_entrypoint_provenance() {",
        "# Package-owned runtime contracts are checked below.",
    )
    static_install_block = _shell_function_block(
        runner,
        "static_install_path_is_expected() {",
        "archive_epoch=$(date +%s)",
    )
    for forbidden_exit in ("exit 11", "exit 14", "exit 15"):
        if forbidden_exit in runner:
            raise ValueError(
                f"runner bypasses unified failure archival with {forbidden_exit}"
            )

    console_functions = _shell_function_block(
        runner,
        "capture_complete_console_snapshot() {",
        "readback_path_is_expected() {",
    )
    readback_functions = _shell_function_block(
        runner,
        "readback_path_is_expected() {",
        "phase_watchdog() {",
    )
    runtime_log_guard_function = _shell_function_block(
        runner,
        "inspect_runtime_log_budget() {",
        'console_log="run/sim_results/',
    )
    wait_index = runner.index('wait "${phase_watchdog_pid}"')
    final_revalidation_index = runner.index(
        'final_protocol_reason=$(validate_ordered_progress "${console_log}")'
    )
    postrun_index = runner.index('runner_phase="postrun"')
    if not wait_index < final_revalidation_index < postrun_index:
        raise ValueError("runner final console revalidation is not after process exit")

    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ndp-overlay-round1-") as temporary:
        temporary_root = Path(temporary)
        copied_ndp = temporary_root / "NDP_copy01"
        shutil.copytree(ndp_root, copied_ndp)
        copied_runtime = (
            copied_ndp / "install" / "cfg_pkg" / runtime_root.name
        )
        copied_install_count = sum(
            1 for path in (copied_runtime / "install").rglob("*") if path.is_file()
        )
        if copied_install_count != preinstalled_file_count:
            raise ValueError("round1 copied full install file count differs")

        identity_ndp = temporary_root / "identity-failure" / "NDP_copy01"
        shutil.copytree(ndp_root, identity_ndp)
        revision_match = re.search(r'^revision="([A-Za-z0-9._-]+)"$', runner, re.MULTILINE)
        if revision_match is None:
            raise ValueError("round1 cannot determine runner revision")
        runner_revision = revision_match.group(1)
        identity_run_root = identity_ndp / "run"
        old_return = identity_run_root / f"{runner_revision}_run1_return"
        old_return.mkdir(parents=True)
        (old_return / "sentinel.txt").write_bytes(b"old-return-evidence\n")
        (identity_run_root / f"sim_results_{runner_revision}_run1.zip").write_bytes(
            b"old-archive-evidence\n"
        )
        (
            identity_run_root
            / f"{runner_revision}_run1_server_source_inventory.tsv"
        ).write_bytes(b"old-inventory-evidence\n")
        evidence_before = {
            path.relative_to(identity_run_root).as_posix(): path.read_bytes()
            for path in sorted(identity_run_root.rglob("*"))
            if path.is_file()
        }
        tampered_runner = identity_ndp / runner_path.name
        tampered_runner.write_text(
            tampered_runner.read_text(encoding="utf-8") + "# round1 tamper\n",
            encoding="utf-8",
            newline="\n",
        )
        identity_failure = subprocess.run(
            [
                bash_path,
                "-lc",
                'cd "$1"; SERVER_RUN_ID=run1 bash "$2"',
                "round1-runner-identity",
                identity_ndp.as_posix(),
                tampered_runner.name,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        evidence_after = {
            path.relative_to(identity_run_root).as_posix(): path.read_bytes()
            for path in sorted(identity_run_root.rglob("*"))
            if path.is_file()
        }
        if (
            identity_failure.returncode != 20
            or "runner self identity mismatch" not in identity_failure.stderr
            or evidence_after != evidence_before
        ):
            raise ValueError(
                "round1 tampered runner did not fail before preserving old evidence: "
                f"status={identity_failure.returncode}, stderr={identity_failure.stderr}"
            )
        cases.append(
            {
                "case": "runner_identity_before_cleanup",
                "status": "passed",
                "observed_exit_status": identity_failure.returncode,
                "verified_outcome": "tampered_runner_rejected_with_old_evidence_byte_unchanged",
            }
        )

        zip_shim_dir = temporary_root / "zip-shim-bin"
        zip_shim_dir.mkdir()
        zip_shim_python = zip_shim_dir / "zip_shim.py"
        zip_shim_python.write_text(
            "from __future__ import annotations\n"
            "import sys\n"
            "import zipfile\n"
            "from pathlib import Path\n"
            "arguments = [item for item in sys.argv[1:] if item not in {'-q', '-r'}]\n"
            "if len(arguments) != 2:\n"
            "    raise SystemExit(64)\n"
            "archive_path = Path(arguments[0])\n"
            "source_root = Path(arguments[1])\n"
            "mode = 'a' if archive_path.exists() else 'w'\n"
            "with zipfile.ZipFile(archive_path, mode, zipfile.ZIP_DEFLATED) as archive:\n"
            "    for path in sorted(source_root.rglob('*')):\n"
            "        if path.is_file() and not path.is_symlink():\n"
            "            archive.write(path, (Path(source_root.name) / path.relative_to(source_root)).as_posix())\n",
            encoding="utf-8",
            newline="\n",
        )
        zip_shim = zip_shim_dir / "zip"
        zip_shim.write_text(
            "#!/usr/bin/env bash\n"
            f'"{Path(sys.executable).as_posix()}" "{zip_shim_python.as_posix()}" "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        zip_shim.chmod(0o755)
        vcs_shim = zip_shim_dir / "vcs"
        vcs_shim.write_text(
            "#!/usr/bin/env bash\nprintf '%s\\n' 'round1-vcs-shim'\n",
            encoding="utf-8",
            newline="\n",
        )
        vcs_shim.chmod(0o755)
        make_shim = zip_shim_dir / "make"
        make_shim.write_text(
            "#!/usr/bin/env bash\nexit 99\n",
            encoding="utf-8",
            newline="\n",
        )
        make_shim.chmod(0o755)
        zip_shim_bash_dir = zip_shim_dir.resolve().as_posix()
        if re.fullmatch(r"[A-Za-z]:/.*", zip_shim_bash_dir):
            zip_shim_bash_dir = (
                f"/{zip_shim_bash_dir[0].lower()}{zip_shim_bash_dir[2:]}"
            )
        zip_smoke_root = temporary_root / "zip-smoke"
        zip_smoke_source = zip_smoke_root / "payload"
        zip_smoke_source.mkdir(parents=True)
        (zip_smoke_source / "evidence.txt").write_text(
            "evidence\n", encoding="utf-8", newline="\n"
        )
        zip_smoke = subprocess.run(
            [
                bash_path,
                "-lc",
                'export PATH="$1:$PATH"; cd "$2"; zip -q -r smoke.zip payload',
                "round1-zip-shim",
                zip_shim_bash_dir,
                zip_smoke_root.as_posix(),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        if zip_smoke.returncode != 0 or not (zip_smoke_root / "smoke.zip").is_file():
            raise ValueError(
                "round1 failure-archive ZIP shim is not executable: "
                f"status={zip_smoke.returncode}, stdout={zip_smoke.stdout}, "
                f"stderr={zip_smoke.stderr}"
            )

        cleanup_fault_ndp = temporary_root / "cleanup-fault" / "NDP_copy01"
        shutil.copytree(ndp_root, cleanup_fault_ndp)
        cleanup_fault_run = cleanup_fault_ndp / "run"
        old_cleanup_return = cleanup_fault_run / f"{runner_revision}_run1_return"
        old_cleanup_return.mkdir(parents=True)
        (old_cleanup_return / "sentinel.txt").write_text(
            "old\n", encoding="utf-8", newline="\n"
        )
        cleanup_fault = subprocess.run(
            [
                bash_path,
                "-lc",
                (
                    'export PATH="$2:$PATH"; '
                    'rm() { command rm "$@"; return 42; }; export -f rm; '
                    'cd "$1"; SERVER_RUN_ID=run1 bash "$3"'
                ),
                "round1-cleanup-fault",
                cleanup_fault_ndp.as_posix(),
                zip_shim_bash_dir,
                runner_path.name,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        cleanup_fault_archives = sorted(
            cleanup_fault_run.glob(
                f"sim_results_{runner_revision}_run1_bootstrap_failure_*.zip"
            )
        )
        if cleanup_fault.returncode != 20 or len(cleanup_fault_archives) != 1:
            raise ValueError(
                "round1 cleanup fault did not converge to a bootstrap failure archive: "
                f"status={cleanup_fault.returncode}, stderr={cleanup_fault.stderr}, "
                f"archives={cleanup_fault_archives}"
            )
        with zipfile.ZipFile(cleanup_fault_archives[0]) as archive:
            report_names = [
                name for name in archive.namelist() if name.endswith("preflight_report.json")
            ]
            if len(report_names) != 1:
                raise ValueError("round1 cleanup fault archive lacks one preflight report")
            cleanup_fault_report = json.loads(archive.read(report_names[0]))
        if cleanup_fault_report.get("reason") != "unexpected_runner_error":
            raise ValueError(
                "round1 cleanup fault reason differs: "
                f"{cleanup_fault_report.get('reason')!r}"
            )
        cases.append(
            {
                "case": "cleanup_fault_evidence_convergence",
                "status": "passed",
                "observed_exit_status": cleanup_fault.returncode,
                "verified_outcome": "cleanup_error_archived_in_unique_bootstrap_failure_bundle",
            }
        )

        entrypoint_probe = temporary_root / "round1_entrypoint_behavior.sh"
        entrypoint_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "cd \"$1\"\n"
            "revision=vnext\nserver_run_id=run1\n"
            "server_source_inventory=\"$2\"\n"
            "emit_preflight_failure() { printf '%s: %s\\n' \"$1\" \"${2:-}\" >&2; exit 20; }\n"
            + entrypoint_provenance_block
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        def run_entrypoint_probe(
            entrypoint_root: Path,
            source_inventory: Path,
            path_prefix: Path,
            dir_home: Path,
            *,
            timeout_seconds: int = 180,
        ) -> subprocess.CompletedProcess[str]:
            path_prefix_bash = path_prefix.resolve().as_posix()
            if re.fullmatch(r"[A-Za-z]:/.*", path_prefix_bash):
                path_prefix_bash = (
                    f"/{path_prefix_bash[0].lower()}{path_prefix_bash[2:]}"
                )
            return subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'export PATH="$4:$PATH"; export DIR_HOME="$5"; bash "$1" "$2" "$3"',
                    "round1-entrypoint",
                    entrypoint_probe.as_posix(),
                    entrypoint_root.as_posix(),
                    source_inventory.as_posix(),
                    path_prefix_bash,
                    dir_home.as_posix(),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout_seconds,
            )

        entrypoint_root = temporary_root / "entrypoint-fixture"
        external_root = temporary_root / "external-entrypoints"
        (entrypoint_root / "rtl/filelists").mkdir(parents=True)
        external_root.mkdir()
        entrypoint_payloads = {
            "Makefile.tb_NDP_Top_new_phy": "all:\n\t@true\n",
            "tb_NDP_Top_new_phy.sv": "module tb_NDP_Top_new_phy; endmodule\n",
            "NDP_Top_phy_filelist.f": "external.sv\n",
        }
        for name, payload in entrypoint_payloads.items():
            (external_root / name).write_text(
                payload, encoding="utf-8", newline="\n"
            )
        link_targets = {
            entrypoint_root / "Makefile.tb_NDP_Top_new_phy": (
                external_root / "Makefile.tb_NDP_Top_new_phy"
            ),
            entrypoint_root / "tb_NDP_Top_new_phy.sv": (
                external_root / "tb_NDP_Top_new_phy.sv"
            ),
            entrypoint_root / "rtl/filelists/NDP_Top_phy_filelist.f": (
                external_root / "NDP_Top_phy_filelist.f"
            ),
        }
        entrypoint_path_prefix = temporary_root / "entrypoint-native-path"
        entrypoint_path_prefix.mkdir()
        entrypoint_fixture_mode = "native_symlink"
        try:
            for link, target in link_targets.items():
                link.symlink_to(target)
        except OSError:
            for link in link_targets:
                if link.is_symlink():
                    link.unlink()
            for link, target in link_targets.items():
                shutil.copyfile(target, link)
            entrypoint_fixture_mode = "readlink_shim_no_symlink_privilege"
            readlink_shim = entrypoint_path_prefix / "readlink"
            readlink_shim.write_text(
                "#!/usr/bin/env bash\n"
                "logical_path=\"${@: -1}\"\n"
                "case \"${logical_path}\" in\n"
                "  Makefile.tb_NDP_Top_new_phy) physical_name=Makefile.tb_NDP_Top_new_phy ;;\n"
                "  tb_NDP_Top_new_phy.sv) physical_name=tb_NDP_Top_new_phy.sv ;;\n"
                "  rtl/filelists/NDP_Top_phy_filelist.f) physical_name=NDP_Top_phy_filelist.f ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n"
                f"printf '%s\\n' '{external_root.as_posix()}/'\"${{physical_name}}\"\n",
                encoding="utf-8",
                newline="\n",
            )
            readlink_shim.chmod(0o755)
        entrypoint_inventory = temporary_root / "entrypoint-inventory.tsv"
        entrypoint_result = run_entrypoint_probe(
            entrypoint_root,
            entrypoint_inventory,
            entrypoint_path_prefix,
            external_root,
        )
        if entrypoint_result.returncode != 0:
            raise ValueError(
                "round1 readable external entrypoint provenance failed: "
                f"status={entrypoint_result.returncode}, "
                f"stderr={entrypoint_result.stderr}"
            )
        entrypoint_inventory_lines = entrypoint_inventory.read_text(
            encoding="utf-8"
        ).splitlines()
        if (
            len(entrypoint_inventory_lines) != 4
            or sum(line.startswith("entrypoint\t") for line in entrypoint_inventory_lines)
            != 3
            or sum(
                line.startswith("environment\tDIR_HOME\tset\t")
                for line in entrypoint_inventory_lines
            )
            != 1
            or not all(
                "\tphysical:" in line
                for line in entrypoint_inventory_lines
                if line.startswith("entrypoint\t")
            )
        ):
            raise ValueError("round1 entrypoint provenance inventory differs")
        cases.append(
            {
                "case": "external_physical_entrypoints",
                "status": "passed",
                "observed_exit_status": entrypoint_result.returncode,
                "fixture_mode": entrypoint_fixture_mode,
                "verified_outcome": (
                    "three_readable_external_entrypoints_and_DIR_HOME_provenance_recorded"
                ),
            }
        )

        static_probe = temporary_root / "round1_static_install_exact_set.sh"
        static_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "cd \"$1\"\n"
            "install_root=\"$2\"\n"
            "launch_files_contract=\"$3\"\n"
            "launch_identity=\"$4\"\n"
            "runner_identity=\"$5\"\n"
            "expected_static_install_file_count=\"$6\"\n"
            "emit_preflight_failure() { printf '%s: %s\\n' \"$1\" \"${2:-}\" >&2; exit 20; }\n"
            + static_install_block
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        launch_contract_path = next(copied_runtime.glob("metadata/launch_manifest.*.tsv"))
        launch_identity_path = next(copied_runtime.glob("metadata/launch_identity.*.json"))
        runner_identity_path = (
            copied_runtime / "metadata" / f"{runner_revision}_runner.sha256"
        )
        static_expected = sum(
            1
            for path in copied_runtime.rglob("*")
            if path.is_file()
            and not path.relative_to(copied_runtime)
            .as_posix()
            .startswith("install/hwop-")
        )

        def run_static_probe() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2" "$3" "$4" "$5" "$6" "$7"',
                    "round1-static-install",
                    static_probe.as_posix(),
                    copied_ndp.as_posix(),
                    copied_runtime.relative_to(copied_ndp).as_posix(),
                    launch_contract_path.relative_to(copied_ndp).as_posix(),
                    launch_identity_path.relative_to(copied_ndp).as_posix(),
                    runner_identity_path.relative_to(copied_ndp).as_posix(),
                    str(static_expected),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=180,
            )

        static_valid = run_static_probe()
        if static_valid.returncode != 0:
            raise ValueError(
                "round1 static install exact-set rejected the pristine install: "
                f"status={static_valid.returncode}, stderr={static_valid.stderr}"
            )
        unexpected_static = copied_runtime / "metadata" / "unexpected-extra.txt"
        unexpected_static.write_text("unexpected\n", encoding="utf-8", newline="\n")
        static_extra = run_static_probe()
        unexpected_static.unlink()
        if (
            static_extra.returncode != 20
            or "static_install_unexpected_file" not in static_extra.stderr
        ):
            raise ValueError(
                "round1 static install exact-set accepted an extra file: "
                f"status={static_extra.returncode}, stderr={static_extra.stderr}"
            )
        cases.append(
            {
                "case": "static_install_exact_set",
                "status": "passed",
                "observed_exit_status": static_extra.returncode,
                "verified_outcome": (
                    "pristine_static_install_accepted_and_extra_file_rejected"
                ),
            }
        )

        make_environment_probe = temporary_root / "round1_make_environment.sh"
        make_environment_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "export MAKEFLAGS=--dry-run\n"
            "export MAKEFILES=unexpected.mk\n"
            "export GNUMAKEFLAGS=-j8\n"
            "export MFLAGS=-s\n"
            "export MAKELEVEL=7\n"
            "unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL\n"
            "for variable_name in MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL; do\n"
            "  if [[ -v ${variable_name} ]]; then exit 31; fi\n"
            "done\n",
            encoding="utf-8",
            newline="\n",
        )
        make_environment_result = subprocess.run(
            [bash_path, make_environment_probe.as_posix()],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        if make_environment_result.returncode != 0:
            raise ValueError(
                "round1 make-environment sanitization behavior failed: "
                f"status={make_environment_result.returncode}, "
                f"stderr={make_environment_result.stderr}"
            )
        cases.append(
            {
                "case": "make_environment_sanitization",
                "status": "passed",
                "observed_exit_status": make_environment_result.returncode,
                "verified_outcome": "all_five_inherited_make_control_variables_unset",
            }
        )

        sink_probe = temporary_root / "round1_sink_behavior.sh"
        sink_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "cd \"$1\"\n"
            "expected_diagnostic_sink_count=1037\n"
            "runtime_log_sink_contract=\"$PWD/runtime_log_sinks.tsv\"\n"
            ": > \"${runtime_log_sink_contract}\"\n"
            "declare -A runtime_log_sink_expected=()\n"
            "sink_audit_log=\"$PWD/sink_audit.tsv\"\n: > \"${sink_audit_log}\"\n"
            "emit_preflight_failure() { printf '%s\\n' \"$1\" >&2; exit 20; }\n"
            + sink_audit_functions
            + "\ninstall_runtime_log_sinks\n"
            + "[ \"${diagnostic_sink_count}\" -eq 1037 ]\n"
            + "[ \"$(wc -l < \"${sink_audit_log}\" | tr -d '[:space:]')\" -eq 1037 ]\n",
            encoding="utf-8",
            newline="\n",
        )
        sink_root = temporary_root / "sink-valid"
        sink_root.mkdir()
        sink_result = subprocess.run(
            [
                bash_path,
                "-lc",
                'bash "$1" "$2"',
                "round1-sink",
                sink_probe.as_posix(),
                sink_root.as_posix(),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=900,
        )
        if sink_result.returncode != 0:
            raise ValueError(
                "round1 full runtime sink installation failed: "
                f"status={sink_result.returncode}, stderr={sink_result.stderr}"
            )
        cases.append(
            {
                "case": "full_runtime_sink_install",
                "status": "passed",
                "observed_exit_status": 0,
                "verified_outcome": (
                    "all_1037_unique_runtime_sink_paths_enumerated_for_dev_null"
                ),
            }
        )

        collision_root = temporary_root / "sink-collision"
        collision = collision_root / "sim_results/gconfig2slice/slice0/gconfig2slice.log"
        collision.parent.mkdir(parents=True)
        collision.write_text("collision\n", encoding="utf-8", newline="\n")
        collision_result = subprocess.run(
            [
                bash_path,
                "-lc",
                'bash "$1" "$2"',
                "round1-sink-collision",
                sink_probe.as_posix(),
                collision_root.as_posix(),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        if collision_result.returncode != 20 or "runtime_log_sink_collision" not in collision_result.stderr:
            raise ValueError("round1 runtime sink collision did not fail closed")
        cases.append(
            {
                "case": "runtime_sink_collision",
                "status": "passed",
                "observed_exit_status": collision_result.returncode,
                "verified_outcome": "preexisting_sink_path_rejected_before_launch",
            }
        )

        runtime_log_guard_probe = temporary_root / "round1_runtime_log_guard.sh"
        runtime_log_guard_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "cd \"$1\"\n"
            "declare -A runtime_log_sink_expected=()\n"
            "runtime_log_total_size_limit_bytes=1073741824\n"
            "mkdir -p sim_results\n"
            + runtime_log_guard_function
            + "\ncase \"$2\" in\n"
            "  unknown) printf 'unexpected\\n' > sim_results/unknown.log; if inspect_runtime_log_budget > guard.out 2>&1; then exit 31; fi; grep -q unknown_runtime_log_file guard.out ;;\n"
            "  total) mkdir -p sim_results/gexec2slice/slice_all; printf '12' > sim_results/gexec2slice/slice_all/gexec2slice.log; runtime_log_total_size_limit_bytes=1; if inspect_runtime_log_budget > guard.out 2>&1; then exit 32; fi; grep -q runtime_log_total_size_exceeded guard.out ;;\n"
            "  *) exit 33 ;;\n"
            "esac\n",
            encoding="utf-8",
            newline="\n",
        )
        for guard_case in ("unknown", "total"):
            guard_root = temporary_root / f"runtime-log-{guard_case}"
            guard_root.mkdir()
            guard_result = subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2" "$3"',
                    "round1-runtime-log-guard",
                    runtime_log_guard_probe.as_posix(),
                    guard_root.as_posix(),
                    guard_case,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=60,
            )
            if guard_result.returncode != 0:
                raise ValueError(
                    f"round1 runtime log guard failed: {guard_case}, "
                    f"status={guard_result.returncode}, stderr={guard_result.stderr}"
                )
            cases.append(
                {
                    "case": f"runtime_log_guard_{guard_case}",
                    "status": "passed",
                    "observed_exit_status": 0,
                    "verified_outcome": (
                        "unknown_runtime_log_rejected"
                        if guard_case == "unknown"
                        else "runtime_log_total_limit_enforced"
                    ),
                }
            )

        failure_probe = temporary_root / "round1_failure_archive.sh"
        failure_probe.write_text(
            "#!/usr/bin/env bash\n"
            "set -Eeuo pipefail\n"
            "cd \"$1\"\n"
            "export PATH=\"$4:$PATH\"\n"
            "revision=vnext\nserver_run_id=\"$2\"\nrunner_phase=preflight\n"
            "return_root=\"run/${revision}_${server_run_id}_return\"\n"
            "return_archive=\"run/sim_results_${revision}_${server_run_id}.zip\"\n"
            "archive_timeout=1m\n"
            "sca_cfg=symlink-evidence\nsca_cfg_d=missing\nlaunch_identity=missing\n"
            "launch_files_contract=missing\nstage_contract=missing\nreadback_contract=missing\n"
            "runtime_make_override=missing\nrun_command_contract=missing\nrunner_identity=missing\n"
            "server_source_inventory=missing\n"
            "rm -f \"${sca_cfg}\"\nln -s /dev/null \"${sca_cfg}\"\n"
            + preflight_failure_function
            + runtime_failure_function
            + "\ncase \"$3\" in\n"
            + "  preflight) emit_preflight_failure injected_preflight_failure detail ;;\n"
            + "  runtime) runner_phase=postrun; emit_runtime_failure 15 injected_runtime_failure detail ;;\n"
            + "  runtime_rm_fault) runner_phase=postrun; rm() { command rm \"$@\"; return 42; }; emit_runtime_failure 15 injected_runtime_cleanup_failure detail ;;\n"
            + "  *) exit 99 ;;\n"
            + "esac\n",
            encoding="utf-8",
            newline="\n",
        )
        failure_root = temporary_root / "failure-archives"
        (failure_root / "run/vnext_run1_return").mkdir(parents=True)
        (failure_root / "run/vnext_run1_return/stale-success.txt").write_text(
            "stale\n", encoding="utf-8", newline="\n"
        )
        with zipfile.ZipFile(
            failure_root / "run/sim_results_vnext_run1.zip", "w"
        ) as stale_archive:
            stale_archive.writestr("stale-success.txt", "stale\n")

        def run_failure_probe(run_id: str, mode: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2" "$3" "$4" "$5"',
                    "round1-failure",
                    failure_probe.as_posix(),
                    failure_root.as_posix(),
                    run_id,
                    mode,
                    zip_shim_bash_dir,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=60,
            )

        for run_id in ("run1", "run2"):
            result = run_failure_probe(run_id, "preflight")
            if result.returncode != 20:
                raise ValueError(f"round1 preflight archive failed for {run_id}")
            archive_path = failure_root / f"run/sim_results_vnext_{run_id}.zip"
            with zipfile.ZipFile(archive_path) as archive:
                archive_names = archive.namelist()
                if any("stale-success" in name for name in archive_names):
                    raise ValueError("round1 preflight archive retained stale evidence")
                if any(name.endswith("symlink-evidence") for name in archive_names):
                    raise ValueError("round1 preflight archive copied symlink evidence")
        if not all(
            (failure_root / f"run/sim_results_vnext_{run_id}.zip").is_file()
            for run_id in ("run1", "run2")
        ):
            raise ValueError("round1 distinct run archives were not preserved")
        runtime_failure = run_failure_probe("run1", "runtime")
        if runtime_failure.returncode != 15:
            raise ValueError("round1 unified runtime failure archive was not emitted")
        runtime_cleanup_failure = run_failure_probe("run2", "runtime_rm_fault")
        runtime_cleanup_archives = sorted(
            failure_root.glob("run/sim_results_vnext_run2_runtime_failure_*.zip")
        )
        if runtime_cleanup_failure.returncode != 15 or len(runtime_cleanup_archives) != 1:
            raise ValueError(
                "round1 runtime cleanup fault did not converge to a unique archive: "
                f"status={runtime_cleanup_failure.returncode}, "
                f"stderr={runtime_cleanup_failure.stderr}"
            )
        with zipfile.ZipFile(runtime_cleanup_archives[0]) as archive:
            if not any(name.endswith("failure_report.json") for name in archive.namelist()):
                raise ValueError("round1 runtime cleanup fault archive lacks failure report")
        invalid_run_root = copied_ndp / "run"
        if invalid_run_root.exists():
            shutil.rmtree(invalid_run_root)
        invalid_run_id = subprocess.run(
            [
                bash_path,
                "-lc",
                'export PATH="$1:$PATH"; cd "$2"; SERVER_RUN_ID=run3 bash "$3"',
                "round1-invalid-run-id",
                zip_shim_bash_dir,
                copied_ndp.as_posix(),
                runner_path.relative_to(ndp_root).as_posix(),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        if invalid_run_id.returncode != 20:
            raise ValueError(
                "round1 invalid SERVER_RUN_ID did not fail before launch: "
                f"status={invalid_run_id.returncode}, stderr={invalid_run_id.stderr}"
            )
        if invalid_run_root.exists():
            raise ValueError("round1 invalid SERVER_RUN_ID mutated the result directory")
        cases.extend(
            [
                {
                    "case": "preflight_stale_archive_replacement",
                    "status": "passed",
                    "observed_exit_status": 20,
                    "verified_outcome": "stale_and_symlink_evidence_excluded_from_fresh_failure_zip",
                },
                {
                    "case": "distinct_run_id_archives",
                    "status": "passed",
                    "observed_exit_status": 0,
                    "verified_outcome": "run1_and_run2_failure_archives_coexist",
                },
                {
                    "case": "unified_runtime_failure_archive",
                    "status": "passed",
                    "observed_exit_status": runtime_failure.returncode,
                    "verified_outcome": "postrun_anomaly_uses_minimal_failure_archive",
                },
                {
                    "case": "runtime_cleanup_fault_evidence_convergence",
                    "status": "passed",
                    "observed_exit_status": runtime_cleanup_failure.returncode,
                    "verified_outcome": "runtime_cleanup_error_archived_in_unique_failure_bundle",
                },
                {
                    "case": "invalid_formal_run_id",
                    "status": "passed",
                    "observed_exit_status": invalid_run_id.returncode,
                    "verified_outcome": "SERVER_RUN_ID_run3_fails_without_result_directory_mutation",
                },
            ]
        )

        source_contract = runtime_root / "metadata" / "readback_regions.tsv"
        contract_lines = source_contract.read_text(encoding="utf-8").splitlines()
        if not contract_lines or "\t" not in contract_lines[0]:
            raise ValueError("round1 readback contract is empty or malformed")
        expected_relative, line_count_text = contract_lines[0].split("\t", 1)
        expected_line_count = int(line_count_text)
        probe_contract = copied_runtime / "metadata" / "round1_readback.tsv"
        probe_contract.write_text(
            f"{expected_relative}\t{expected_line_count}\n",
            encoding="utf-8",
            newline="\n",
        )
        install_relative = copied_runtime.relative_to(copied_ndp).as_posix()
        contract_relative = probe_contract.relative_to(copied_ndp).as_posix()
        expected_path = copied_ndp / Path(expected_relative)
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        probe_script = temporary_root / "round1_behavior.sh"
        probe_script.write_text(
            "#!/usr/bin/env bash\n"
            "set -uo pipefail\n"
            "cd \"$1\"\n"
            "install_root=\"$2\"\n"
            "readback_contract=\"$3\"\n"
            "expected_preload_count=1\n"
            "expected_repeat_num=1\n"
            "expected_stage_count=1\n"
            "expected_region_count=1\n"
            "testbench_observer_mode=fixed_slice0_start_slice1_finish\n"
            "readback_live_validation_state=round1-readback-live.tsv\n"
            ": > \"${readback_live_validation_state}\"\n"
            + console_functions
            + readback_functions
            + "\ncase \"$4\" in\n"
            "  zero) result=$(inspect_readback_progress live) || exit 20; [ \"${result}\" = 0 ] ;;\n"
            "  valid) result=$(inspect_readback_progress live) || exit 21; [ \"${result}\" = 1 ] ;;\n"
            "  extra) if inspect_readback_progress live > round1-case.out 2>&1; then exit 22; fi; grep -q unexpected_readback_file round1-case.out ;;\n"
            "  missing_final_lf) if inspect_readback_progress final > round1-case.out 2>&1; then exit 23; fi; grep -q readback_file_incomplete_at_final round1-case.out ;;\n"
            "  live_cache_final_revalidation) result=$(inspect_readback_progress live) || exit 25; [ \"${result}\" = 1 ] || exit 26; IFS=$'\\t' read -r observed_path _ < \"${readback_contract}\"; printf 'x' > round1-readback.tmp; tail -c +2 \"${observed_path}\" >> round1-readback.tmp; mv -- round1-readback.tmp \"${observed_path}\"; result=$(inspect_readback_progress live) || exit 27; [ \"${result}\" = 1 ] || exit 28; if inspect_readback_progress final > round1-case.out 2>&1; then exit 29; fi; grep -q readback_file_invalid_byte round1-case.out ;;\n"
            "  final_console) process_exit_status=0; printf '%s\\n' 'Simulation completed successfully!' > round1-final-console.log; final_protocol_reason=valid; if ! final_protocol_reason=$(validate_ordered_progress round1-final-console.log); then :; fi; [ \"${process_exit_status}\" = 0 ] && [ \"${final_protocol_reason}\" != valid ] ;;\n"
            "  *) exit 24 ;;\n"
            "esac\n",
            encoding="utf-8",
            newline="\n",
        )

        def run_case(case_id: str, expected_success: bool = True) -> None:
            completed = subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2" "$3" "$4" "$5"',
                    "round1-behavior",
                    probe_script.as_posix(),
                    copied_ndp.as_posix(),
                    install_relative,
                    contract_relative,
                    case_id,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=60,
            )
            if (completed.returncode == 0) is not expected_success:
                raise ValueError(
                    f"round1 behavior case failed: {case_id}, "
                    f"status={completed.returncode}, stdout={completed.stdout}, "
                    f"stderr={completed.stderr}"
                )
            cases.append(
                {
                    "case": case_id,
                    "status": "passed",
                    "observed_exit_status": completed.returncode,
                    "verified_outcome": {
                        "zero": "full_install_with_272_preloads_and_zero_readback_accepted_count_0",
                        "valid": "one_complete_128bit_lf_readback_accepted_count_1",
                        "extra": "unexpected_output_namespace_file_rejected",
                        "missing_final_lf": "live_count_0_and_final_expected_count_1_rejected",
                        "live_cache_final_revalidation": "complete_file_validated_once_live_then_all_bytes_revalidated_final",
                        "final_console": "zero_process_exit_still_rejected_by_final_console_validation",
                    }[case_id],
                }
            )

        run_case("zero")
        expected_path.write_bytes((b"0" * 128 + b"\n") * expected_line_count)
        run_case("valid")
        run_case("live_cache_final_revalidation")
        expected_path.write_bytes((b"0" * 128 + b"\n") * expected_line_count)
        extra_path = expected_path.parent / "round1-extra.txt"
        extra_path.write_bytes(b"")
        run_case("extra")
        extra_path.unlink()
        complete_payload = (b"0" * 128 + b"\n") * expected_line_count
        expected_path.write_bytes(complete_payload[:-1])
        run_case("missing_final_lf")
        run_case("final_console")

    report: dict[str, Any] = {
        "schema_version": "resnet50-ndp-server-overlay-selfcheck-round1-0.4",
        "status": "passed",
        "entrypoint": "tools/build_ndp_server_overlay.py",
        "package_authoritative_check": {
            "status": package_preflight["status"],
            "checked_file_count": package_preflight.get("checked_file_count"),
            "manifest_sha256": _sha256(package / "manifest.json"),
        },
        "overlay_manifest_sha256": _sha256(overlay_manifest_path),
        "zip_path": zip_path.name,
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": _sha256(zip_path),
        "runner_path": runner_path.relative_to(output).as_posix(),
        "runner_sha256": _sha256(runner_path),
        "runner_identity_before_cleanup": True,
        "tampered_runner_old_evidence_preserved": True,
        "cleanup_fault_evidence_convergence_checked": True,
        "bash_syntax": "passed",
        "awk_version": awk_version.stdout.strip(),
        "diagnostic_sink_slice_enumeration": sink_values,
        "diagnostic_sink_full_install_count": 1037,
        "runtime_unknown_log_guard_checked": True,
        "runtime_log_total_limit_checked": True,
        "readback_live_once_final_full_revalidation_checked": True,
        "entrypoint_provenance_behavior_checked": True,
        "entrypoint_provenance_record_count": 3,
        "environment_provenance_record_count": 1,
        "static_install_exact_set_checked": True,
        "make_environment_sanitization_checked": True,
        "stale_failure_archive_behavior_checked": True,
        "distinct_run_id_archives_checked": True,
        "explicit_runtime_failure_archival_checked": True,
        "runtime_cleanup_fault_evidence_convergence_checked": True,
        "failure_archive_zip_behavior": (
            "deterministic_test_shim_with_info_zip_stale_entry_retention_semantics"
        ),
        "preinstalled_file_count": preinstalled_file_count,
        "copied_full_install_file_count": preinstalled_file_count,
        "behavior_cases": cases,
        "final_revalidation_order": "process_exit_then_console_validation_then_postrun",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_lf(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return report


def _write_content_addressed_text(
    directory: Path,
    stem: str,
    suffix: str,
    value: str,
) -> tuple[Path, str]:
    """Write deterministic text under a filename containing its SHA-256."""

    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    payload = normalized.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    path = directory / f"{stem}.{digest}{suffix}"
    path.write_bytes(payload)
    return path, digest


def _completion_stage_records(
    package_manifest: dict[str, Any], runner_contract: dict[str, Any]
) -> list[tuple[int, str, str]]:
    """Return the exact ordered stage/mask contract used by the runner."""

    try:
        completion_gate = runner_contract["execution"]["completion_gate"]
        raw_expected_count = completion_gate["expected_runtime_stage_count"]
        if isinstance(raw_expected_count, bool):
            raise ValueError
        expected_count = int(raw_expected_count)
        expected_sequence = completion_gate["expected_runtime_sequence"]
        runtime_operators = package_manifest["runtime_operators"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("completion stage contract is incomplete") from error
    if (
        expected_count <= 0
        or not isinstance(expected_sequence, list)
        or not isinstance(runtime_operators, list)
        or len(expected_sequence) != expected_count
        or len(runtime_operators) != expected_count
    ):
        raise ValueError("completion stage contract count differs")

    records: list[tuple[int, str, str]] = []
    seen_operator_ids: set[str] = set()
    for stage_index, (expected_operator_id, operator) in enumerate(
        zip(expected_sequence, runtime_operators, strict=True)
    ):
        if (
            not isinstance(expected_operator_id, str)
            or not expected_operator_id
            or any(token in expected_operator_id for token in ("\t", "\r", "\n"))
            or not isinstance(operator, dict)
            or operator.get("operator_id") != expected_operator_id
            or expected_operator_id in seen_operator_ids
        ):
            raise ValueError("completion runtime operator order differs")
        raw_mask = operator.get("slice_mask")
        if not isinstance(raw_mask, str) or not re.fullmatch(
            r"0x[0-9a-fA-F]{1,7}", raw_mask
        ):
            raise ValueError(
                f"completion runtime operator mask is invalid: {expected_operator_id}"
            )
        mask = int(raw_mask, 16)
        if mask <= 0 or mask > 0x0FFFFFFF:
            raise ValueError(
                f"completion runtime operator mask is invalid: {expected_operator_id}"
            )
        seen_operator_ids.add(expected_operator_id)
        records.append((stage_index, expected_operator_id, f"0x{mask:07X}"))
    return records


def _sca_runtime_transfers(sca: dict[str, Any]) -> list[tuple[str, str]]:
    """Mirror the immutable line parser's actual top-level transfer sequence."""

    transfers: list[tuple[str, str]] = []
    for key, value in sca.items():
        if not isinstance(value, dict):
            continue
        nested = value.get("chunked_transport")
        if key == "ExecutionPlan" and isinstance(nested, dict):
            path = nested.get("path")
        elif isinstance(value.get("base_addr"), str):
            path = value.get("path")
        else:
            continue
        if not isinstance(path, str) or not path:
            raise ValueError(f"runtime SCA transfer path is invalid: {key}")
        transfers.append((key, path))
    return transfers


def _sca_payload_references(sca: dict[str, Any]) -> list[tuple[str, str]]:
    """Collect every payload path asserted anywhere in the relocated SCA."""

    references: list[tuple[str, str]] = []

    def visit(value: Any, locator: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                child_locator = f"{locator}.{key}" if locator else str(key)
                if key in {"path", "semantic_path"}:
                    if not isinstance(item, str) or not item:
                        raise ValueError(
                            f"runtime SCA payload reference is invalid: {child_locator}"
                        )
                    references.append((child_locator, item))
                else:
                    visit(item, child_locator)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{locator}[{index}]")

    visit(sca, "")
    return references


def build_overlay(
    package: Path,
    output: Path,
    install_name: str,
    *,
    observation: str = OBSERVATION_FULL_FSDB,
    diagnostic_run_time: str = "12ms",
    testbench: Path | None = None,
    expected_rtl_revision: str | None = None,
    expected_server_testbench_sha256: str | None = None,
) -> dict[str, Any]:
    package = package.resolve()
    output = output.resolve()
    revision_label = install_name.rsplit("-", 1)[-1].upper()
    revision_slug = revision_label.lower()
    if observation not in {
        OBSERVATION_FULL_FSDB,
        OBSERVATION_TARGETED_VPD,
        OBSERVATION_COMPLETION_NO_WAVE,
    }:
        raise ValueError(f"unsupported observation mode: {observation}")
    if observation == OBSERVATION_TARGETED_VPD and not _TCL_TIME_RE.fullmatch(
        diagnostic_run_time
    ):
        raise ValueError(
            "diagnostic run time must be a positive VCS time literal such as 12ms"
        )
    normalized_rtl_revision: str | None = None
    if expected_rtl_revision is not None:
        if not _GIT_REVISION_RE.fullmatch(expected_rtl_revision):
            raise ValueError("expected RTL revision must be exactly 40 hexadecimal digits")
        normalized_rtl_revision = expected_rtl_revision.lower()
    if testbench is not None:
        raise ValueError(
            "server overlays must not include or replace any .v/.sv file, including "
            "tb_NDP_Top_new_phy.sv"
        )
    normalized_testbench_sha256: str | None = None
    immutable_testbench_capability_attestation: dict[str, Any] | None = None
    if expected_server_testbench_sha256 is not None:
        if not _SHA256_RE.fullmatch(expected_server_testbench_sha256):
            raise ValueError(
                "expected server testbench SHA-256 must be exactly 64 hexadecimal digits"
            )
        normalized_testbench_sha256 = expected_server_testbench_sha256.lower()
    if output.exists():
        raise FileExistsError(f"refusing to replace an existing overlay: {output}")
    zip_path = output.with_suffix(".zip")
    zip_sha256_path = Path(f"{zip_path}.sha256")
    for companion in (zip_path, zip_sha256_path):
        if companion.exists():
            raise FileExistsError(
                f"refusing to replace an existing overlay companion: {companion}"
            )

    # This is the single authoritative package preflight.  The validator checks
    # the exact manifest file set, 4-KiB-safe SCA/SCA_D transport, Repeat_Num,
    # semantic-region reconstruction, and the frozen runner/dump contracts.
    package_preflight = validate_conv_hardware_execplan_package(package)
    if package_preflight.get("status") != "hardware_execplan_package_validated":
        raise ValueError("authoritative hardware execplan package preflight failed")
    package_manifest = _json(package / "manifest.json")
    prohibited_runtime_sources = sorted(
        path.relative_to(package).as_posix()
        for path in (package / "install").rglob("*")
        if path.is_file() and path.suffix.lower() in {".v", ".sv"}
    )
    if prohibited_runtime_sources:
        raise ValueError(
            "server overlay runtime payload must not contain .v/.sv files: "
            f"{prohibited_runtime_sources[:5]}"
        )

    ndp_root = output / "NDP_copy01"
    runtime_root = ndp_root / "install" / "cfg_pkg" / install_name
    runtime_root.mkdir(parents=True)
    shutil.copytree(package / "install", runtime_root / "install")
    _normalize_server_text_tree(runtime_root / "install")
    installed_prefix = f"install/cfg_pkg/{install_name}"
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        value = _rewrite_paths(_json(package / name), installed_prefix)
        _write_text_lf(
            runtime_root / name,
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        )

    sca = _json(runtime_root / "sca_cfg.json")
    sca_d = _json(runtime_root / "sca_cfg_D.json")
    runner_contract = _json(package / "runner_contract.json")
    package_manifest_sha256 = _sha256(package / "manifest.json")
    freeze_id = package_manifest.get("freeze_id")
    freeze_manifest_sha256 = package_manifest.get("freeze_manifest_sha256")
    if not isinstance(freeze_id, str) or not freeze_id:
        raise ValueError("package manifest lacks freeze_id")
    if not isinstance(freeze_manifest_sha256, str) or not freeze_manifest_sha256:
        raise ValueError("package manifest lacks freeze_manifest_sha256")
    try:
        completion_gate = runner_contract["execution"]["completion_gate"]
        expected_runtime_stage_count = int(
            completion_gate["expected_runtime_stage_count"]
        )
        expected_testbench_repeat_num = int(
            completion_gate.get(
                "expected_testbench_repeat_num", expected_runtime_stage_count
            )
        )
        testbench_observer_mode = str(
            completion_gate.get(
                "testbench_observer_mode", "mask_aware_runtime_stage_markers"
            )
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("runner contract lacks a valid runtime stage count") from error
    legacy_fixed_pair_observer = (
        testbench_observer_mode == "fixed_slice0_start_slice1_finish"
    )
    bank_frame_logging_policy = (
        "slice_start_only_plus_runtime_devnull_sinks"
        if legacy_fixed_pair_observer
        else "testbench_native"
    )
    reserved_clock_validation_policy = (
        "force_and_low_high_toggle_proof"
        if legacy_fixed_pair_observer
        else "testbench_native"
    )
    if testbench_observer_mode not in {
        "mask_aware_runtime_stage_markers",
        "fixed_slice0_start_slice1_finish",
    }:
        raise ValueError(
            f"unsupported testbench observer mode: {testbench_observer_mode}"
        )
    repeat_num = sca.get("Repeat_Num")
    if (
        isinstance(repeat_num, bool)
        or not isinstance(repeat_num, int)
        or repeat_num <= 0
        or repeat_num != expected_testbench_repeat_num
    ):
        raise ValueError(
            "SCA Repeat_Num must equal the runner testbench-observer count: "
            f"repeat_num={repeat_num!r}, expected={expected_testbench_repeat_num}"
        )
    if observation == OBSERVATION_COMPLETION_NO_WAVE:
        immutable_testbench_capability_attestation = {
            "schema_version": "resnet50-server-entrypoint-capability-policy-0.8",
            "identity_policy": "logical_entrypoints_unpinned_source_provenance",
            "required_entrypoints": [
                "Makefile.tb_NDP_Top_new_phy",
                "tb_NDP_Top_new_phy.sv",
                "rtl/filelists/NDP_Top_phy_filelist.f",
            ],
            "prestart_source_hash_required": False,
            "recursive_filelist_validation_required": False,
            "logical_filelist_readability_required": True,
            "include_directory_validation_required": False,
            "external_vendor_include_tree_equivalence_required": False,
            "physical_source_path_inside_server_root_required": False,
            "server_source_content_scan_required": False,
            "transport_contract_source": "package_axi4_4kb_report",
            "observer_mode": testbench_observer_mode,
            "reserved_axi_clock_policy": (
                "ucli_force_and_low_high_toggle_proof_400mhz"
                if legacy_fixed_pair_observer
                else "testbench_native"
            ),
            "bank_frame_logging_policy": (
                "compile_define_plus_runtime_devnull_sinks"
                if legacy_fixed_pair_observer
                else "testbench_native"
            ),
            "phase_stall_watchdog_required": True,
            "phase_progress_policy": "complete_line_snapshot_final_revalidation_v2",
            "watchdog_exit_status_required": True,
            "readback_progress_policy": "exact_regular_file_exact_size_v1",
            "make_archive_policy": "runner_no_archive_target_v1",
            "make_effective_command_check_required": False,
            "make_environment_policy": (
                "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
            ),
            "static_install_exact_set_policy": (
                "launch_manifest_plus_four_content_addressed_identity_files"
            ),
            "run_command_identity_required": True,
            "runner_self_identity_required": True,
            "static_install_exact_set_required": True,
            "waveform_disable_args_required": True,
            "return_archive_policy": "bounded_exact_set_allowlist_v2",
            "server_run_id_policy": {
                "environment_variable": "SERVER_RUN_ID",
                "default": "run1",
                "syntax": "run1|run2",
                "required_formal_run_ids": ["run1", "run2"],
                "preserve_distinct_archives": True,
            },
            "return_config_exact_set_required": True,
            "post_run_evidence_required": (
                [
                    "exact preload PASS count",
                    "exact fixed slice0-start/slice1-finish pair count",
                    "finish-slice-only final stage after all other final-shard slices barrier",
                    "unique Simulation completed successfully marker",
                    "exact readback region set",
                ]
                if legacy_fixed_pair_observer
                else [
                    "exact preload PASS count",
                    "ordered RUNTIME_STAGE_COMPLETE markers",
                    "unique RUNTIME_ALL_STAGES_COMPLETE marker",
                    "exact readback region set",
                ]
            ),
        }
    runtime_transfers = _sca_runtime_transfers(sca)
    if observation == OBSERVATION_COMPLETION_NO_WAVE:
        try:
            parser_transfer_count = int(
                runner_contract["preload"]["sca_cfg"]["immutable_tb_parser_abi"][
                    "validated_transfer_count"
                ]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "runner contract lacks the immutable SCA transfer count"
            ) from error
        if parser_transfer_count != len(runtime_transfers):
            raise ValueError(
                "runtime SCA transfer count differs from the immutable parser contract: "
                f"runtime={len(runtime_transfers)}, expected={parser_transfer_count}"
            )

    payload_references = _sca_payload_references(sca)
    installed_runtime_prefix = f"{installed_prefix}/"
    payload_reference_records: list[tuple[str, str, Path]] = []
    for locator, path_text in payload_references:
        if any(token in locator for token in ("\t", "\r", "\n")) or any(
            token in path_text for token in ("\t", "\r", "\n")
        ):
            raise ValueError(f"runtime SCA payload reference is unsafe: {locator}")
        if not path_text.startswith(installed_runtime_prefix):
            raise ValueError(
                f"relocated SCA payload is outside the runtime root: {path_text}"
            )
        relative_text = path_text[len(installed_runtime_prefix) :]
        relative_path = Path(relative_text)
        candidate = (runtime_root / relative_path).resolve()
        try:
            resolved_relative = candidate.relative_to(runtime_root)
        except ValueError as error:
            raise ValueError(
                f"relocated SCA payload escapes the runtime root: {path_text}"
            ) from error
        if relative_path.as_posix() != resolved_relative.as_posix():
            raise ValueError(
                f"relocated SCA payload path is not canonical: {path_text}"
            )
        if not candidate.is_file() or candidate.is_symlink():
            raise FileNotFoundError(f"relocated SCA payload is missing: {path_text}")
        payload_reference_records.append((locator, relative_path.as_posix(), candidate))

    completion_stage_records: list[tuple[int, str, str]] = []
    if observation == OBSERVATION_COMPLETION_NO_WAVE:
        completion_stage_records = _completion_stage_records(
            package_manifest, runner_contract
        )
        if len(completion_stage_records) != expected_runtime_stage_count:
            raise ValueError("completion stage count differs from the runner contract")

    readback_region_records: list[tuple[str, int]] = []
    if observation == OBSERVATION_COMPLETION_NO_WAVE:
        seen_readback_paths: set[str] = set()
        expected_readback_root = (ndp_root / installed_prefix / "install").resolve()
        for region_name, region in sca_d.items():
            if not isinstance(region, dict):
                raise ValueError(f"SCA_D region is not an object: {region_name}")
            region_path = region.get("path")
            region_length = region.get("length")
            if (
                not isinstance(region_path, str)
                or not region_path
                or "\t" in region_path
                or "\r" in region_path
                or "\n" in region_path
                or isinstance(region_length, bool)
                or not isinstance(region_length, int)
                or region_length <= 0
            ):
                raise ValueError(f"SCA_D region contract is invalid: {region_name}")
            relative_region_path = Path(region_path)
            canonical_region_path = relative_region_path.as_posix()
            resolved_region_path = (ndp_root / relative_region_path).resolve()
            try:
                resolved_relative_region_path = resolved_region_path.relative_to(
                    ndp_root
                )
            except ValueError as error:
                raise ValueError(
                    f"SCA_D region path escapes the overlay root: {region_path}"
                ) from error
            if canonical_region_path != resolved_relative_region_path.as_posix():
                raise ValueError(
                    f"SCA_D region path is not canonical: {region_path}"
                )
            try:
                readback_relative = resolved_region_path.relative_to(
                    expected_readback_root
                )
            except ValueError as error:
                raise ValueError(
                    f"SCA_D region path is outside the runtime output roots: {region_path}"
                ) from error
            if (
                len(readback_relative.parts) < 2
                or not readback_relative.parts[0].startswith("hwop-")
            ):
                raise ValueError(
                    f"SCA_D region path is outside a hwop output root: {region_path}"
                )
            if canonical_region_path in seen_readback_paths:
                raise ValueError(
                    f"SCA_D region path is duplicated: {canonical_region_path}"
                )
            seen_readback_paths.add(canonical_region_path)
            readback_region_records.append(
                (canonical_region_path, region_length)
            )
        readback_region_records.sort()

    signal_scope = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new."
        "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
        "slice_group_gen[0].u_slice_wrapper.u_Slice"
    )
    signal_suffixes = [
        "slice_start_run",
        "slice_cmpt_finish",
        "u_LSU.u_Buffer_Manager_Cluster.buf_src_id[5]",
        "sa_inport_group_in_tag",
        "sa_inport_group_in_data",
        "sa_inport_group_bp_pre",
        "sa_outport_group_out_tag",
        "sa_outport_group_out_data",
        "sa_outport_buf_bp_post",
        "spec_array2buf_wtag[0][0]",
        "u_LSU.u_Buffer_Manager_Cluster.array2arm_wtag[5]",
        "u_LSU.u_Buffer_Manager_Cluster.arm2array_bp_pre[5]",
        "u_LSU.u_Stream_Engine.buf2mse_rvalid[0]",
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_vld",
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_prepared_data_bp_pre",
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_data_vld",
        "u_LSU.u_Stream_Engine.mse2mem_request_valid[4]",
        "u_LSU.u_Stream_Engine.mse2mem_wdata_valid[4]",
        "u_LSU.u_Stream_Engine.mem2mse_wdata_ready[4]",
    ]
    signal_list = "\n".join(f"{signal_scope}.{suffix}" for suffix in signal_suffixes)
    signal_path_name: str | None = None
    if observation in {OBSERVATION_FULL_FSDB, OBSERVATION_TARGETED_VPD}:
        signal_path_name = (
            f"{revision_label}_FSDB_SIGNAL_PATHS.txt"
            if observation == OBSERVATION_FULL_FSDB
            else f"{revision_label}_TARGETED_SIGNAL_PATHS.txt"
        )
        _write_text_lf(
            output / signal_path_name,
            (
                "# Slice0 signals to inspect in run/sim_results/wave.fsdb\n"
                if observation == OBSERVATION_FULL_FSDB
                else f"# Slice0 signals captured in run/sim_results/{revision_slug}_diag.vpd\n"
            )
            + "# No RTL source modification is required.\n"
            + signal_list
            + "\n",
        )

    diagnostic_files: list[str] = []
    runner_name: str | None = None
    if observation == OBSERVATION_TARGETED_VPD:
        metadata_root = runtime_root / "metadata"
        metadata_root.mkdir()
        for name in ("manifest.json", "runner_contract.json", "dump_contract.json"):
            _copy_text_lf(package / name, metadata_root / name)

        diagnostic_tcl_name = f"{revision_slug}_diag.tcl"
        diagnostic_tcl = runtime_root / diagnostic_tcl_name
        _write_text_lf(
            diagnostic_tcl,
            "\n".join(
                [
                    f'dump -file run/sim_results/{revision_slug}_diag.vpd -type VPD',
                    *(
                        f"dump -add {{{signal_scope}.{suffix}}} -depth 0 -fid VPD0"
                        for suffix in signal_suffixes
                    ),
                    f"run {diagnostic_run_time}",
                    "quit",
                    "",
                ]
            ),
        )

        runner_name = f"RUN_SERVER_{revision_label}.sh"
        runner = ndp_root / runner_name
        _write_text_lf(
            runner,
            f"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${{BASH_SOURCE[0]}}")"

revision="{revision_slug}"
install_root="install/cfg_pkg/{install_name}"
diagnostic_tcl="${{install_root}}/{diagnostic_tcl_name}"
expected_dump_count={len(signal_suffixes)}

if [ ! -f "${{diagnostic_tcl}}" ]; then
  echo "ERROR: missing diagnostic Tcl: ${{diagnostic_tcl}}" >&2
  exit 2
fi
dump_count=$(grep -c '^dump -add .* -fid VPD0$' "${{diagnostic_tcl}}" || true)
if [ "${{dump_count}}" -ne "${{expected_dump_count}}" ]; then
  echo "ERROR: diagnostic Tcl has ${{dump_count}} validated dump commands; expected ${{expected_dump_count}}" >&2
  exit 2
fi
if grep -q $'\\r' "${{diagnostic_tcl}}"; then
  echo "ERROR: diagnostic Tcl contains CRLF line endings" >&2
  exit 2
fi

archive_epoch=$(date +%s)
archive_root="run/archive/preexisting-${{revision}}-${{archive_epoch}}"
if [ -e sim_results ] || [ -e run/sim_results ]; then
  mkdir -p "${{archive_root}}"
  if [ -e sim_results ]; then mv -- sim_results "${{archive_root}}/sim_results"; fi
  if [ -e run/sim_results ]; then mv -- run/sim_results "${{archive_root}}/run_sim_results"; fi
fi
rm -rf run/csrc run/${{revision}}_return run/${{revision}}_failure \
  run/sim_results_${{revision}}.zip
for stale_output in "${{install_root}}/install"/hwop-*; do
  if [ -e "${{stale_output}}" ]; then
    rm -rf -- "${{stale_output}}"
  fi
done
mkdir -p sim_results run/sim_results

set +e
make -f Makefile.tb_NDP_Top_new_phy compile sim \\
  DUMP_FSDB=0 TB_DUMP_FSDB=0 SIM_TIME={diagnostic_run_time} \\
  VCS_EXTRA_OPTS='-debug_access+all -kdb' \\
  SIM_EXTRA_OPTS="-ucli -i ${{diagnostic_tcl}}" \\
  PLUSARGS="+SCA_CFG=${{install_root}}/sca_cfg.json" \\
  </dev/null 2>&1 | tee run/sim_results/${{revision}}_console.log
sim_status=${{PIPESTATUS[0]}}
set -e
printf '%s\\n' "${{sim_status}}" > run/sim_results/${{revision}}_exit_status.txt

if command -v vpd2vcd >/dev/null 2>&1 && [ -s "run/sim_results/${{revision}}_diag.vpd" ]; then
  vpd2vcd "run/sim_results/${{revision}}_diag.vpd" \\
    "run/sim_results/${{revision}}_diag.vcd" \\
    > "run/sim_results/${{revision}}_vpd2vcd.log" 2>&1 || true
fi

return_root="run/${{revision}}_return"
mkdir -p "${{return_root}}/run_sim_results" "${{return_root}}/config"
for name in compile.log sim.log "${{revision}}_console.log" "${{revision}}_exit_status.txt" \\
  "${{revision}}_diag.vpd" "${{revision}}_diag.vcd" "${{revision}}_vpd2vcd.log"; do
  if [ -f "run/sim_results/${{name}}" ]; then
    cp -a "run/sim_results/${{name}}" "${{return_root}}/run_sim_results/"
  fi
done
if [ -f sim_results/gexec2slice/slice_all/gexec2slice.log ]; then
  mkdir -p "${{return_root}}/sim_results/gexec2slice/slice_all"
  cp -a sim_results/gexec2slice/slice_all/gexec2slice.log \
    "${{return_root}}/sim_results/gexec2slice/slice_all/"
fi
if compgen -G "${{install_root}}/install/hwop-*" >/dev/null; then
  mkdir -p "${{return_root}}/readback_regions"
  cp -a "${{install_root}}/install"/hwop-* "${{return_root}}/readback_regions/"
fi
cp -a "${{install_root}}/sca_cfg.json" "${{return_root}}/config/"
cp -a "${{install_root}}/sca_cfg_D.json" "${{return_root}}/config/"
cp -a "${{install_root}}/metadata" "${{return_root}}/config/"

if command -v zip >/dev/null 2>&1; then
  (cd run && zip -q -r "sim_results_${{revision}}.zip" "${{revision}}_return")
  echo "Return archive: run/sim_results_${{revision}}.zip"
else
  echo "zip is unavailable; return directory: ${{return_root}}"
fi
exit "${{sim_status}}"
""",
        )
        runner.chmod(0o755)
        diagnostic_files = [
            diagnostic_tcl.relative_to(output).as_posix(),
            runner.relative_to(output).as_posix(),
            metadata_root.relative_to(output).as_posix() + "/",
        ]

    if observation == OBSERVATION_COMPLETION_NO_WAVE:
        if immutable_testbench_capability_attestation is None:
            raise AssertionError("completion entrypoint policy was not initialized")
        metadata_root = runtime_root / "metadata"
        metadata_root.mkdir()
        for name in ("manifest.json", "runner_contract.json", "dump_contract.json"):
            _copy_text_lf(package / name, metadata_root / name)
        readback_contract = metadata_root / "readback_regions.tsv"
        _write_text_lf(
            readback_contract,
            "".join(
                f"{region_path}\t{region_length}\n"
                for region_path, region_length in readback_region_records
            ),
        )

        stage_contract = metadata_root / "expected_runtime_stages.tsv"
        _write_text_lf(
            stage_contract,
            "".join(
                f"{stage_index}\t{operator_id}\t{slice_mask}\n"
                for stage_index, operator_id, slice_mask in completion_stage_records
            ),
        )

        stage_contract_sha256 = _sha256(stage_contract)
        readback_contract_sha256 = _sha256(readback_contract)

        reserved_clock_tcl: Path | None = None
        reserved_clock_tcl_name = ""
        if legacy_fixed_pair_observer:
            reserved_clock_tcl_name = f"{revision_slug}_reserved_axi_clock.tcl"
            reserved_clock_tcl = runtime_root / reserved_clock_tcl_name
            _write_text_lf(
                reserved_clock_tcl,
                "\n".join(
                    [
                        'set reserved_clock_path "tb_NDP_Top_new_phy.u_NDP_Top_new.m_axi_reserved_clk"',
                        'echo "RESERVED_AXI_CLOCK_FORCE_BEGIN"',
                        "if {[catch {force $reserved_clock_path 0 0ns, 1 1.25ns -repeat 2.5ns} reserved_clock_force_error]} {",
                        '  echo "RESERVED_AXI_CLOCK_FORCE_FAILED force"',
                        "  echo $reserved_clock_force_error",
                        "  quit",
                        "} else {",
                        "  run 0.25ns",
                        "  if {[catch {set reserved_clock_low [get $reserved_clock_path]} reserved_clock_low_error]} {",
                        '    echo "RESERVED_AXI_CLOCK_FORCE_FAILED low_sample"',
                        "    echo $reserved_clock_low_error",
                        "    quit",
                        "  } else {",
                        "    run 1.25ns",
                        "    if {[catch {set reserved_clock_high [get $reserved_clock_path]} reserved_clock_high_error]} {",
                        '      echo "RESERVED_AXI_CLOCK_FORCE_FAILED high_sample"',
                        "      echo $reserved_clock_high_error",
                        "      quit",
                        "    } elseif {$reserved_clock_low eq $reserved_clock_high} {",
                        '      echo "RESERVED_AXI_CLOCK_FORCE_FAILED no_toggle"',
                        "      quit",
                        "    } else {",
                        '      echo "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING"',
                        "      run",
                        "    }",
                        "  }",
                        "}",
                        "",
                    ]
                ),
            )

        no_archive_target = f"{revision_slug}_sim_no_archive"
        runtime_make_override_name = f"{revision_slug}_runtime_no_archive.mk"
        runtime_make_override = metadata_root / runtime_make_override_name
        _write_text_lf(
            runtime_make_override,
            "\n".join(
                [
                    f".PHONY: {no_archive_target}",
                    f"{no_archive_target}: $(SIMV)",
                    '\t@if [ "$(DUMP_VCD)" -eq 1 ] || [ "$(DUMP_FSDB)" -eq 1 ]; then $(MAKE) -f $(THIS_MAKEFILE) $(SIM_DIR)/dump.tcl; fi',
                    '\t@echo "=========================================="',
                    '\t@echo "Running simulation without full-result archive..."',
                    '\t@echo "=========================================="',
                    '\t@echo "Command: $(SIMV) $(SIM_OPTS) $(SIM_EXTRA_OPTS)"',
                    "\t@sim_status=0; \\",
                    "\t$(SIMV) $(SIM_OPTS) $(SIM_EXTRA_OPTS) || sim_status=$$?; \\",
                    '\techo "Simulation exit status: $$sim_status"; \\',
                    '\texit $$sim_status',
                    "",
                ]
            ),
        )
        run_command_contract_name = f"{revision_slug}_run_argv.tsv"
        run_command_contract = metadata_root / run_command_contract_name
        runner_identity_name = f"{revision_slug}_runner.sha256"
        run_argv = [
            "make",
            "-f",
            "Makefile.tb_NDP_Top_new_phy",
            "-f",
            f"install/cfg_pkg/{install_name}/metadata/{runtime_make_override_name}",
            "compile",
            no_archive_target,
            "DUMP_VCD=0",
            "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0",
        ]
        if legacy_fixed_pair_observer:
            run_argv.extend(
                [
                    "VCS_EXTRA_OPTS=-debug_access+all +define+BANK_FRAME_LOG_SLICE_START_ONLY",
                    f"SIM_EXTRA_OPTS=-ucli -i install/cfg_pkg/{install_name}/{reserved_clock_tcl_name}",
                ]
            )
        run_argv.append(f"PLUSARGS=+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json")
        if any("\n" in argument or "\r" in argument or "\t" in argument for argument in run_argv):
            raise ValueError("run argv contract contains a control character")
        _write_text_lf(run_command_contract, "".join(f"{argument}\n" for argument in run_argv))
        run_command_contract_sha256 = _sha256(run_command_contract)
        runtime_make_override_sha256 = _sha256(runtime_make_override)

        launch_file_records_by_path: dict[
            str, tuple[str, str, str, int, str]
        ] = {}

        def add_launch_file_record(
            category: str,
            label: str,
            relative_path: str,
        ) -> None:
            if any(
                token in value
                for value in (category, label, relative_path)
                for token in ("\t", "\r", "\n")
            ):
                raise ValueError("launch-file contract contains unsafe text")
            relative = Path(relative_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(
                    f"launch-file path is not a contained relative path: {relative_path}"
                )
            candidate = (runtime_root / relative).resolve()
            try:
                resolved_relative = candidate.relative_to(runtime_root)
            except ValueError as error:
                raise ValueError(
                    f"runtime launch-file path escapes its root: {relative_path}"
                ) from error
            if resolved_relative.as_posix() != relative_path:
                raise ValueError(
                    f"runtime launch-file path is not canonical: {relative_path}"
                )
            if not candidate.is_file() or candidate.is_symlink():
                raise FileNotFoundError(
                    f"launch-file source is missing: {relative_path}"
                )
            record = (
                category,
                label,
                _sha256(candidate),
                candidate.stat().st_size,
                relative_path,
            )
            previous = launch_file_records_by_path.setdefault(relative_path, record)
            if previous[2:] != record[2:]:
                raise ValueError(
                    f"conflicting launch-file identity: {relative_path}"
                )

        for relative_path in (
            "sca_cfg.json",
            "sca_cfg_D.json",
            "metadata/manifest.json",
            "metadata/runner_contract.json",
            "metadata/dump_contract.json",
            "metadata/readback_regions.tsv",
            "metadata/expected_runtime_stages.tsv",
            f"metadata/{runtime_make_override_name}",
            f"metadata/{run_command_contract_name}",
        ):
            add_launch_file_record("runtime_contract", relative_path, relative_path)
        if reserved_clock_tcl is not None:
            add_launch_file_record(
                "runtime_contract",
                "reserved_axi_clock_ucli",
                reserved_clock_tcl.relative_to(runtime_root).as_posix(),
            )
        for locator, relative_path, _ in payload_reference_records:
            add_launch_file_record(
                "sca_payload_reference",
                locator,
                relative_path,
            )
        launch_file_records = sorted(launch_file_records_by_path.values())
        (
            launch_files_contract,
            launch_files_contract_sha256,
        ) = _write_content_addressed_text(
            metadata_root,
            "launch_manifest",
            ".tsv",
            "".join(
                f"{category}\t{label}\t{sha256}\t{size_bytes}\t{relative_path}\n"
                for category, label, sha256, size_bytes, relative_path
                in launch_file_records
            ),
        )

        launch_identity = {
            "schema_version": "resnet50-ndp-server-launch-identity-0.1",
            "freeze_id": freeze_id,
            "freeze_manifest_sha256": freeze_manifest_sha256,
            "package_manifest_sha256": package_manifest_sha256,
            "rtl_source_provenance": normalized_rtl_revision,
            "server_source_policy": {
                "mode": "readable_logical_entrypoints_with_nonblocking_provenance",
                "content_hash_required": False,
                "actual_hash_inventory_required": "entrypoints_and_DIR_HOME",
                "include_directory_validation_required": False,
                "external_vendor_include_tree_equivalence_required": False,
                "physical_source_path_inside_server_root_required": False,
                "required_entrypoints": immutable_testbench_capability_attestation[
                    "required_entrypoints"
                ],
            },
            "testbench_source_provenance_sha256": normalized_testbench_sha256,
            "expected_runtime_stage_count": expected_runtime_stage_count,
            "expected_testbench_repeat_num": expected_testbench_repeat_num,
            "testbench_observer_mode": testbench_observer_mode,
            "bank_frame_logging_policy": bank_frame_logging_policy,
            "reserved_clock_validation": reserved_clock_validation_policy,
            "phase_stall_watchdog": {
                "preload_seconds": 10800,
                "first_start_seconds": 1800,
                "compute_progress_seconds": 7200,
                "readback_progress_seconds": 3600,
                "completion_exit_seconds": 900,
                "poll_seconds": 30,
                "progress_policy": "complete_line_snapshot_final_revalidation_v2",
                "watchdog_exit_status_required": True,
                "readback_progress_policy": "exact_regular_file_exact_size_v1",
            },
            "runtime_log_sink_policy": {
                "policy": "audited_sinks_unknown_log_guard_v2",
                "expected_sink_count": 1037,
                "allowed_regular_files": [
                    "gexec2slice/slice_all/gexec2slice.log"
                ],
                "runtime_total_size_limit_bytes": 1073741824,
                "overlay_symlinks_allowed": False,
                "return_symlinks_allowed": False,
            },
            "make_archive_policy": "runner_no_archive_target_v1",
            "make_environment_policy": (
                "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
            ),
            "static_install_exact_set_policy": (
                "launch_manifest_plus_four_content_addressed_identity_files"
            ),
            "runtime_make_override": {
                "path": runtime_make_override.relative_to(output).as_posix(),
                "sha256": runtime_make_override_sha256,
                "target": no_archive_target,
            },
            "run_command_contract": {
                "path": run_command_contract.relative_to(output).as_posix(),
                "sha256": run_command_contract_sha256,
                "argument_count": len(run_argv),
            },
            "return_archive_policy": "bounded_exact_set_allowlist_v2",
            "server_run_id_policy": immutable_testbench_capability_attestation[
                "server_run_id_policy"
            ],
            "diagnostic_limits": {
                "file_size_limit_bytes": 1048576,
                "total_size_limit_bytes": 1048576,
                "truncation_policy": "head_bytes_v1",
            },
            "expected_runtime_transfer_count": len(runtime_transfers),
            "expected_region_count": len(sca_d),
            "relocated_sca_cfg_sha256": _sha256(runtime_root / "sca_cfg.json"),
            "relocated_sca_cfg_D_sha256": _sha256(runtime_root / "sca_cfg_D.json"),
            "readback_region_contract": {
                "sha256": readback_contract_sha256,
                "region_count": len(readback_region_records),
            },
            "runtime_stage_contract": {
                "sha256": stage_contract_sha256,
                "stage_count": len(completion_stage_records),
            },
            "launch_manifest": {
                "path": launch_files_contract.relative_to(output).as_posix(),
                "sha256": launch_files_contract_sha256,
                "record_count": len(launch_file_records),
                "sca_payload_reference_count": len(payload_reference_records),
            },
            "package_preflight": {
                "status": package_preflight["status"],
                "checked_file_count": package_preflight.get("checked_file_count"),
            },
            "immutable_testbench_capability_attestation": (
                immutable_testbench_capability_attestation
            ),
            "formal_acceptance_ready": True,
        }
        launch_identity_path, launch_identity_sha256 = _write_content_addressed_text(
            metadata_root,
            "launch_identity",
            ".json",
            json.dumps(launch_identity, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )

        runner_name = f"RUN_SERVER_{revision_label}.sh"
        runner = ndp_root / runner_name
        _write_text_lf(
            runner,
            f"""#!/usr/bin/env bash
set -Eeuo pipefail

# Resolve the runner location with Bash builtins.  The runner must authenticate
# itself before it creates, removes, archives, or otherwise mutates evidence.
runner_source="${{BASH_SOURCE[0]}}"
runner_name="${{runner_source##*/}}"
if [ "${{runner_source}}" = "${{runner_name}}" ]; then
  runner_dir="."
else
  runner_dir="${{runner_source%/*}}"
fi
if ! cd -- "${{runner_dir}}"; then
  echo "ERROR: cannot enter runner directory: ${{runner_dir}}" >&2
  exit 20
fi
runner_source="./${{runner_name}}"

revision="{revision_slug}"
install_root="install/cfg_pkg/{install_name}"
sca_cfg="${{install_root}}/sca_cfg.json"
sca_cfg_d="${{install_root}}/sca_cfg_D.json"
readback_contract="${{install_root}}/metadata/readback_regions.tsv"
stage_contract="${{install_root}}/metadata/expected_runtime_stages.tsv"
launch_files_contract="${{install_root}}/{launch_files_contract.relative_to(runtime_root).as_posix()}"
launch_identity="${{install_root}}/{launch_identity_path.relative_to(runtime_root).as_posix()}"
reserved_clock_tcl="${{install_root}}/{reserved_clock_tcl_name}"
runtime_make_override="${{install_root}}/metadata/{runtime_make_override_name}"
run_command_contract="${{install_root}}/metadata/{run_command_contract_name}"
runner_identity="${{install_root}}/metadata/{runner_identity_name}"
no_archive_target="{no_archive_target}"
testbench_observer_mode="{testbench_observer_mode}"
# A completion run always has the same non-zero wall guard.  Do not accept an
# environment override: GNU timeout treats 0 as "disabled", which would turn a
# simulator zero-time loop into an unbounded server job.
wall_timeout="24h"
preload_stall_timeout_seconds=10800
first_start_stall_timeout_seconds=1800
compute_stall_timeout_seconds=7200
readback_stall_timeout_seconds=3600
completion_exit_stall_timeout_seconds=900
phase_poll_seconds=30
archive_timeout="1h"
diagnostic_file_size_limit_bytes=1048576
diagnostic_total_size_limit_bytes=1048576
runtime_log_total_size_limit_bytes=1073741824
expected_diagnostic_sink_count=1037
expected_preload_count={len(runtime_transfers)}
expected_stage_count={expected_runtime_stage_count}
expected_repeat_num={expected_testbench_repeat_num}
expected_region_count={len(sca_d)}
expected_launch_file_record_count={len(launch_file_records)}
expected_static_install_file_count={len(launch_file_records) + 4}
expected_launch_files_contract_sha256="{launch_files_contract_sha256}"
expected_launch_identity_sha256="{launch_identity_sha256}"
expected_runtime_make_override_sha256="{runtime_make_override_sha256}"
expected_run_command_contract_sha256="{run_command_contract_sha256}"
expected_run_command_argument_count={len(run_argv)}
run_command="not_loaded"

requested_server_run_id="${{SERVER_RUN_ID:-run1}}"
if [ "${{requested_server_run_id}}" = run1 ] || \
   [ "${{requested_server_run_id}}" = run2 ]; then
  server_run_id="${{requested_server_run_id}}"
else
  echo "ERROR: SERVER_RUN_ID must be exactly run1 or run2" >&2
  exit 20
fi
return_root="run/${{revision}}_${{server_run_id}}_return"
return_archive="run/sim_results_${{revision}}_${{server_run_id}}.zip"
server_source_inventory="run/${{revision}}_${{server_run_id}}_server_source_inventory.tsv"
runner_phase="preflight"

if ! command -v sha256sum >/dev/null 2>&1; then
  echo "ERROR: sha256sum is required to verify runner identity" >&2
  exit 20
fi
if [ ! -f "${{runner_source}}" ] || [ -L "${{runner_source}}" ]; then
  echo "ERROR: runner must be a regular non-symlink file: ${{runner_source}}" >&2
  exit 20
fi
if [ ! -f "${{runner_identity}}" ] || [ -L "${{runner_identity}}" ]; then
  echo "ERROR: missing runner identity: ${{runner_identity}}" >&2
  exit 20
fi
identity_line=""
if ! IFS= read -r identity_line < "${{runner_identity}}"; then
  echo "ERROR: runner identity must be LF-terminated" >&2
  exit 20
fi
mapfile -t runner_identity_lines < "${{runner_identity}}"
if [ "${{#runner_identity_lines[@]}}" -ne 1 ] || \
   [[ ! "${{identity_line}}" =~ ^([0-9a-f]{{64}})[[:space:]][[:space:]]([^[:space:]]+)$ ]]; then
  echo "ERROR: malformed runner identity" >&2
  exit 20
fi
expected_runner_hash="${{BASH_REMATCH[1]}}"
expected_runner_name="${{BASH_REMATCH[2]}}"
if ! actual_runner_hash_line=$(sha256sum -- "${{runner_source}}"); then
  echo "ERROR: cannot hash runner: ${{runner_source}}" >&2
  exit 20
fi
actual_runner_hash="${{actual_runner_hash_line%% *}}"
if [ "${{expected_runner_name}}" != "${{runner_name}}" ] || \
   [ "${{actual_runner_hash}}" != "${{expected_runner_hash}}" ]; then
  echo "ERROR: runner self identity mismatch: expected_hash=${{expected_runner_hash}} actual_hash=${{actual_runner_hash}} expected_name=${{expected_runner_name}} actual_name=${{runner_name}}" >&2
  exit 20
fi

emit_preflight_failure() {{
  trap - ERR
  set +e
  local failure_reason="$1"
  local failure_detail="${{2:-no additional detail}}"
  local failure_status=20
  local evidence_dir="${{revision}}_${{server_run_id}}_return"
  local evidence_root="${{return_root}}"
  local evidence_archive="${{return_archive}}"
  local cleanup_status archive_status
  rm -rf -- "${{return_root}}" "${{return_archive}}"
  cleanup_status=$?
  if [ "${{cleanup_status}}" -ne 0 ]; then
    evidence_dir="${{revision}}_${{server_run_id}}_bootstrap_failure_${{BASHPID}}"
    evidence_root="run/${{evidence_dir}}"
    evidence_archive="run/sim_results_${{revision}}_${{server_run_id}}_bootstrap_failure_${{BASHPID}}.zip"
  fi
  if ! mkdir -p "${{evidence_root}}/run_sim_results" "${{evidence_root}}/config"; then
    echo "ERROR: cannot create preflight failure evidence: reason=${{failure_reason}} cleanup_status=${{cleanup_status}}" >&2
    exit "${{failure_status}}"
  fi
  printf '%s\n' "${{failure_status}}" > "${{evidence_root}}/run_sim_results/${{revision}}_exit_status.txt"
  printf '%s\n' "${{failure_detail}}" > "${{evidence_root}}/preflight_error.txt"
  printf '{{\n  "schema_version": "resnet50-ndp-server-preflight-report-0.1",\n  "status": "failed",\n  "reason": "%s",\n  "detail_file": "preflight_error.txt"\n}}\n' \
    "${{failure_reason}}" > "${{evidence_root}}/preflight_report.json"
  printf '{{\n  "schema_version": "resnet50-ndp-server-failed-run-metadata-0.2",\n  "server_run_id": "%s",\n  "exit_status": %s,\n  "make_exit_status": -1,\n  "simulator_exit_status": -1,\n  "simulator_exit_status_observed": false,\n  "termination_kind": "preflight_failure",\n  "preflight_status": "failed",\n  "preflight_reason": "%s"\n}}\n' \
    "${{server_run_id}}" "${{failure_status}}" "${{failure_reason}}" > "${{evidence_root}}/run_metadata.json"
  if command -v cp >/dev/null 2>&1; then
    for evidence_path in "${{sca_cfg}}" "${{sca_cfg_d}}" "${{launch_identity}}" \
      "${{launch_files_contract}}" "${{stage_contract}}" "${{readback_contract}}" \
      "${{runtime_make_override}}" "${{run_command_contract}}" "${{runner_identity}}" \
      "${{server_source_inventory}}"; do
      if [ -f "${{evidence_path}}" ] && [ ! -L "${{evidence_path}}" ]; then
        cp -- "${{evidence_path}}" "${{evidence_root}}/config/"
      fi
    done
  fi
  if command -v zip >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    (cd run && timeout --signal=TERM --kill-after=5m "${{archive_timeout}}" \
      zip -q -r "${{evidence_archive##*/}}" "${{evidence_dir}}")
    archive_status=$?
    if [ "${{archive_status}}" -eq 0 ]; then
      echo "Preflight failure archive: ${{evidence_archive}}" >&2
    else
      echo "Preflight failure directory: ${{evidence_root}} (archive_status=${{archive_status}})" >&2
    fi
  else
    echo "Preflight failure directory: ${{evidence_root}}" >&2
  fi
  exit "${{failure_status}}"
}}

emit_runtime_failure() {{
  local failure_status="$1"
  local failure_reason="$2"
  local failure_detail="${{3:-no additional detail}}"
  local failure_phase="${{runner_phase}}"
  local failure_dir="${{revision}}_${{server_run_id}}_failure"
  local failure_root="run/${{failure_dir}}"
  local failure_archive="${{return_archive}}"
  local cleanup_status archive_cleanup_status archive_status=0
  trap - ERR
  set +e
  rm -rf -- "${{failure_root}}"
  cleanup_status=$?
  if [ "${{cleanup_status}}" -ne 0 ]; then
    failure_dir="${{revision}}_${{server_run_id}}_runtime_failure_${{BASHPID}}"
    failure_root="run/${{failure_dir}}"
    failure_archive="run/sim_results_${{revision}}_${{server_run_id}}_runtime_failure_${{BASHPID}}.zip"
  fi
  if ! mkdir -p "${{failure_root}}/config" "${{failure_root}}/run_sim_results"; then
    echo "ERROR: cannot create runtime failure evidence: reason=${{failure_reason}} cleanup_status=${{cleanup_status}}" >&2
    exit "${{failure_status}}"
  fi
  printf '%s\n' "${{failure_status}}" > "${{failure_root}}/${{revision}}_exit_status.txt"
  printf '%s\n' "${{failure_detail}}" > "${{failure_root}}/failure_detail.txt"
  printf '{{\n  "schema_version": "resnet50-ndp-server-minimal-failure-0.2",\n  "status": "failed",\n  "server_run_id": "%s",\n  "exit_status": %s,\n  "phase": "%s",\n  "reason": "%s",\n  "detail_file": "failure_detail.txt"\n}}\n' \
    "${{server_run_id}}" "${{failure_status}}" "${{failure_phase}}" "${{failure_reason}}" \
    > "${{failure_root}}/failure_report.json"
  for evidence_path in "${{sca_cfg}}" "${{sca_cfg_d}}" "${{launch_identity}}" \
    "${{launch_files_contract}}" "${{stage_contract}}" "${{readback_contract}}" \
    "${{runtime_make_override}}" "${{run_command_contract}}" "${{runner_identity}}" \
    "${{server_source_inventory}}"; do
    if [ -f "${{evidence_path}}" ] && [ ! -L "${{evidence_path}}" ]; then
      cp -- "${{evidence_path}}" "${{failure_root}}/config/" || true
    fi
  done
  for failure_log in \
    "run/sim_results/${{revision}}_console.log" \
    "run/sim_results/${{revision}}_exit_status.txt" \
    "run/sim_results/${{revision}}_phase_progress.tsv" \
    "run/sim_results/${{revision}}_phase_timeout.tsv" \
    "run/sim_results/${{revision}}_phase_watchdog_done.tsv"; do
    if [ -f "${{failure_log}}" ] && [ ! -L "${{failure_log}}" ]; then
      failure_log_size=$(stat -c %s "${{failure_log}}" 2>/dev/null || printf '0')
      if [ "${{failure_log_size}}" -gt "${{diagnostic_file_size_limit_bytes}}" ]; then
        tail -c "${{diagnostic_file_size_limit_bytes}}" "${{failure_log}}" \
          > "${{failure_root}}/run_sim_results/$(basename "${{failure_log}}")" || true
      else
        cp -- "${{failure_log}}" "${{failure_root}}/run_sim_results/" || true
      fi
    fi
  done
  rm -f -- "${{return_archive}}"
  archive_cleanup_status=$?
  if [ "${{archive_cleanup_status}}" -ne 0 ] && [ "${{failure_archive}}" = "${{return_archive}}" ]; then
    failure_archive="run/sim_results_${{revision}}_${{server_run_id}}_runtime_archive_failure_${{BASHPID}}.zip"
  fi
  if command -v zip >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    (cd run && timeout --signal=TERM --kill-after=5m "${{archive_timeout}}" \
      zip -q -r "${{failure_archive##*/}}" "${{failure_dir}}")
    archive_status=$?
  else
    archive_status=127
  fi
  if [ "${{archive_status}}" -eq 0 ]; then
    echo "Failure archive: ${{failure_archive}}" >&2
  else
    echo "Failure directory: ${{failure_root}} (archive_status=${{archive_status}})" >&2
  fi
  exit "${{failure_status}}"
}}

unexpected_runner_error() {{
  local unexpected_status=$?
  trap - ERR
  if [ "${{runner_phase}}" = preflight ]; then
    emit_preflight_failure \
      "unexpected_runner_error" \
      "status=${{unexpected_status}} line=${{BASH_LINENO[0]:-unknown}} command=${{BASH_COMMAND:-unknown}}"
  else
    emit_runtime_failure "${{unexpected_status}}" \
      "unexpected_runner_error" \
      "status=${{unexpected_status}} line=${{BASH_LINENO[0]:-unknown}} command=${{BASH_COMMAND:-unknown}}"
  fi
}}
trap unexpected_runner_error ERR

missing_server_commands=()
for required_command in {" ".join(_REQUIRED_SERVER_COMMANDS)}; do
  if ! command -v "${{required_command}}" >/dev/null 2>&1; then
    missing_server_commands+=("${{required_command}}")
  fi
done
if [ "${{#missing_server_commands[@]}}" -ne 0 ]; then
  missing_server_command_list="${{missing_server_commands[*]}}"
  echo "ERROR: required server commands are unavailable: ${{missing_server_command_list}}" >&2
  # The capability gate has not passed, so no evidence path may be replaced.
  # stderr is the only dependable failure channel when an arbitrary required
  # command is absent; preserve every existing run artifact byte-for-byte.
  exit 20
fi

# A run ID owns exactly one canonical return directory/archive.  This cleanup
# runs only after runner identity, failure handlers, ERR trap, and the complete
# command capability gate are ready.  A cleanup error is converged by the trap
# into a unique bootstrap-failure evidence directory/archive.
mkdir -p run
rm -rf -- "${{return_root}}" "run/${{revision}}_${{server_run_id}}_failure" \
  "${{return_archive}}" "${{server_source_inventory}}"

if [ ! -f "${{sca_cfg}}" ] || [ -L "${{sca_cfg}}" ]; then
  echo "ERROR: missing runtime config: ${{sca_cfg}}" >&2
  emit_preflight_failure "missing_sca_cfg" "${{sca_cfg}} must be a regular non-symlink file"
fi
if [ ! -f "${{sca_cfg_d}}" ] || [ -L "${{sca_cfg_d}}" ]; then
  echo "ERROR: missing runtime readback config: ${{sca_cfg_d}}" >&2
  emit_preflight_failure "missing_sca_cfg_d" "${{sca_cfg_d}} must be a regular non-symlink file"
fi
if [ ! -f "${{readback_contract}}" ] || [ -L "${{readback_contract}}" ]; then
  echo "ERROR: missing exact readback-region contract: ${{readback_contract}}" >&2
  emit_preflight_failure "missing_readback_contract" "${{readback_contract}} must be a regular non-symlink file"
fi
for contract_path in "${{stage_contract}}" "${{launch_files_contract}}" "${{launch_identity}}" \
  "${{runtime_make_override}}" "${{run_command_contract}}"; do
  if [ ! -f "${{contract_path}}" ] || [ -L "${{contract_path}}" ]; then
    echo "ERROR: runtime launch contract is missing or is a symlink: ${{contract_path}}" >&2
    emit_preflight_failure "missing_runtime_launch_contract" "${{contract_path}}"
  fi
done
if [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ]; then
  if [ ! -f "${{reserved_clock_tcl}}" ] || [ -L "${{reserved_clock_tcl}}" ]; then
    emit_preflight_failure "missing_reserved_clock_ucli" "${{reserved_clock_tcl}}"
  fi
fi
check_lf_text_file() {{
  local candidate="$1"
  local cr_byte_count
  cr_byte_count=$(LC_ALL=C od -An -v -t x1 "${{candidate}}" | awk '{{ for (field_idx = 1; field_idx <= NF; field_idx++) if ($field_idx == "0d") count++ }} END {{ print count + 0 }}')
  if [ "${{cr_byte_count}}" -ne 0 ]; then
    echo "ERROR: runtime text is not LF-only: ${{candidate}}" >&2
    emit_preflight_failure \
      "invalid_launch_text_line_endings" \
      "path=${{candidate}} cr_byte_count=${{cr_byte_count}} expected_line_ending=lf"
  fi
}}
path_control_byte_count() {{
  printf '%s' "$1" | LC_ALL=C od -An -v -t x1 | awk '
    {{ for (field_idx = 1; field_idx <= NF; field_idx++)
         if ($field_idx == "09" || $field_idx == "0a" || $field_idx == "0d") count++ }}
    END {{ print count + 0 }}
  '
}}
for required_lf_text in \
  "${{sca_cfg}}" \
  "${{sca_cfg_d}}" \
  "${{readback_contract}}" \
  "${{stage_contract}}" \
  "${{launch_files_contract}}" \
  "${{launch_identity}}" \
  "${{runtime_make_override}}" \
  "${{run_command_contract}}" \
  "${{runner_identity}}"; do
  check_lf_text_file "${{required_lf_text}}"
done
if [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ]; then
  check_lf_text_file "${{reserved_clock_tcl}}"
fi

check_fixed_hash() {{
  local candidate="$1"
  local expected_hash="$2"
  local failure_reason="$3"
  local observed_hash
  observed_hash=$(sha256sum "${{candidate}}" | awk '{{print $1}}')
  if [ "${{observed_hash}}" != "${{expected_hash}}" ]; then
    echo "ERROR: fixed runtime hash differs: ${{candidate}}" >&2
    emit_preflight_failure "${{failure_reason}}" "${{candidate}} expected=${{expected_hash}} observed=${{observed_hash}}"
  fi
}}
check_fixed_hash "${{launch_files_contract}}" "${{expected_launch_files_contract_sha256}}" "launch_files_contract_hash_mismatch"
check_fixed_hash "${{launch_identity}}" "${{expected_launch_identity_sha256}}" "launch_identity_hash_mismatch"
check_fixed_hash "${{runtime_make_override}}" "${{expected_runtime_make_override_sha256}}" "runtime_make_override_hash_mismatch"
check_fixed_hash "${{run_command_contract}}" "${{expected_run_command_contract_sha256}}" "run_command_contract_hash_mismatch"

run_argv=()
while IFS= read -r run_argument || [ -n "${{run_argument}}" ]; do
  if [ -z "${{run_argument}}" ] || [[ "${{run_argument}}" == *$'\t'* ]]; then
    emit_preflight_failure "malformed_run_command_contract" "empty or tab-containing argv element"
  fi
  run_argv+=("${{run_argument}}")
done < "${{run_command_contract}}"
if [ "${{#run_argv[@]}}" -ne "${{expected_run_command_argument_count}}" ]; then
  emit_preflight_failure "run_command_argument_count_mismatch" "observed=${{#run_argv[@]}} expected=${{expected_run_command_argument_count}}"
fi
run_command=""
for run_argument in "${{run_argv[@]}}"; do
  if [ -n "${{run_command}}" ]; then run_command="${{run_command}} | "; fi
  run_command="${{run_command}}${{run_argument}}"
done

for server_entrypoint in \
  Makefile.tb_NDP_Top_new_phy \
  tb_NDP_Top_new_phy.sv \
  rtl/filelists/NDP_Top_phy_filelist.f; do
  if [ ! -r "${{server_entrypoint}}" ]; then
    echo "ERROR: required server simulation entrypoint is not readable: ${{server_entrypoint}}" >&2
    emit_preflight_failure "server_entrypoint_missing" "${{server_entrypoint}}"
  fi
done

: > "${{server_source_inventory}}"

record_server_entrypoint_provenance() {{
  local logical_path="$1"
  local physical_path source_size source_hash
  physical_path=$(readlink -f -- "${{logical_path}}")
  source_size=$(stat -c %s "${{logical_path}}")
  source_hash=$(sha256sum "${{logical_path}}" | awk '{{print $1}}')
  printf 'entrypoint\t%s\tphysical:%s\t%s\t%s\n' \
    "${{logical_path}}" "${{physical_path}}" "${{source_size}}" "${{source_hash}}" \
    >> "${{server_source_inventory}}"
}}

for server_entrypoint in \
  Makefile.tb_NDP_Top_new_phy \
  tb_NDP_Top_new_phy.sv \
  rtl/filelists/NDP_Top_phy_filelist.f; do
  record_server_entrypoint_provenance "${{server_entrypoint}}"
done

dir_home_state=unset
dir_home_value="${{DIR_HOME-}}"
if [[ -v DIR_HOME ]]; then dir_home_state=set; fi
case "${{dir_home_value}}" in
  *$'\t'*|*$'\n'*|*$'\r'*)
    emit_preflight_failure \
      "unsafe_dir_home_value" \
      "DIR_HOME contains a tab, LF, or CR byte"
    ;;
esac
dir_home_value_sha256=$(printf '%s' "${{dir_home_value}}" | sha256sum | awk '{{print $1}}')
vendor_source_physical_path=unresolved
if [ "${{dir_home_state}}" = set ] && [ -n "${{dir_home_value}}" ]; then
  vendor_source_logical_path="${{dir_home_value}}/Hardware/IP/bus/nic_cgra_0310"
  vendor_source_physical_path=$(readlink -f -- "${{vendor_source_logical_path}}" 2>/dev/null || printf 'unresolved')
fi
case "${{vendor_source_physical_path}}" in
  *$'\t'*|*$'\n'*|*$'\r'*)
    emit_preflight_failure \
      "unsafe_dir_home_physical_path" \
      "resolved DIR_HOME vendor path contains a tab, LF, or CR byte"
    ;;
esac
printf 'environment\tDIR_HOME\t%s\tvalue:%s\tvendor_physical:%s\t%s\n' \
  "${{dir_home_state}}" "${{dir_home_value}}" "${{vendor_source_physical_path}}" \
  "${{dir_home_value_sha256}}" >> "${{server_source_inventory}}"
LC_ALL=C sort -o "${{server_source_inventory}}" "${{server_source_inventory}}"

# Package-owned runtime contracts are checked below.  Server HDL/filelist
# semantics are owned by VCS/Make and failures are archived as compile output.

if ! awk -v expected="${{expected_repeat_num}}" '
  /^[[:space:]]*"Repeat_Num"[[:space:]]*:/ {{
    matches++
    value = $0
    sub(/^[^:]*:[[:space:]]*/, "", value)
    sub(/,[[:space:]]*$/, "", value)
    gsub(/[[:space:]]/, "", value)
    if (value !~ /^[1-9][0-9]*$/ || value + 0 != expected) invalid = 1
  }}
  END {{ exit (matches == 1 && !invalid) ? 0 : 1 }}
' "${{sca_cfg}}"; then
  echo "ERROR: SCA Repeat_Num is missing or differs from the testbench observer contract" >&2
  emit_preflight_failure "repeat_num_mismatch" "Repeat_Num must equal ${{expected_repeat_num}}"
fi

if ! contract_region_count=$(awk -F '\t' -v root="${{install_root}}/install/hwop-" '
  NF != 2 || $1 == "" || index($1, root) != 1 ||
    $1 ~ /(^|[/])[.][.]($|[/])/ || $2 !~ /^[1-9][0-9]*$/ || seen[$1]++ {{ invalid = 1 }}
  END {{ if (invalid) exit 1; print NR }}
' "${{readback_contract}}"); then
  echo "ERROR: malformed exact readback-region contract" >&2
  emit_preflight_failure "malformed_readback_contract" "${{readback_contract}}"
fi
if [ "${{contract_region_count}}" -ne "${{expected_region_count}}" ]; then
  echo "ERROR: readback contract has ${{contract_region_count}} regions; expected ${{expected_region_count}}" >&2
  emit_preflight_failure "readback_region_count_mismatch" "observed=${{contract_region_count}} expected=${{expected_region_count}}"
fi
if ! awk -F '\t' -v expected="${{expected_stage_count}}" '
  NF != 3 || $1 !~ /^[0-9]+$/ || $1 + 0 != NR - 1 ||
    $2 == "" || $2 ~ /[[:space:]]/ || $3 !~ /^0x[0-9A-F]{{7}}$/ {{ invalid = 1 }}
  END {{ exit (NR == expected && !invalid) ? 0 : 1 }}
' "${{stage_contract}}"; then
  echo "ERROR: ordered runtime stage/mask contract is malformed" >&2
  emit_preflight_failure "malformed_stage_contract" "${{stage_contract}}"
fi
if ! launch_file_record_count=$(awk -F '\t' '
  NF != 5 || ($1 != "runtime_contract" && $1 != "sca_payload_reference") ||
    $2 == "" || $3 !~ /^[0-9a-f]{{64}}$/ || $4 !~ /^(0|[1-9][0-9]*)$/ ||
    $5 == "" || $5 ~ /(^\\/|(^|\\/)\\.\\.($|\\/))/ {{ invalid = 1 }}
  END {{ if (invalid) exit 1; print NR }}
' "${{launch_files_contract}}"); then
  echo "ERROR: runtime launch-file contract is malformed" >&2
  emit_preflight_failure "malformed_launch_files_contract" "${{launch_files_contract}}"
fi
if [ "${{launch_file_record_count}}" -ne "${{expected_launch_file_record_count}}" ]; then
  emit_preflight_failure "launch_file_record_count_mismatch" "observed=${{launch_file_record_count}} expected=${{expected_launch_file_record_count}}"
fi
while IFS=$'\t' read -r file_category file_label expected_file_hash expected_file_size relative_file_path; do
  if [ "$(path_control_byte_count "${{relative_file_path}}")" -ne 0 ]; then
    emit_preflight_failure \
      "unsafe_launch_file_path" \
      "launch-file contract path contains a tab, LF, or CR byte"
  fi
  launch_file="${{install_root}}/${{relative_file_path}}"
  if [ ! -f "${{launch_file}}" ] || [ -L "${{launch_file}}" ]; then
    echo "ERROR: launch file is missing or is a symlink: ${{launch_file}}" >&2
    emit_preflight_failure "launch_file_missing" "${{file_category}}:${{file_label}}:${{launch_file}}"
  fi
  check_lf_text_file "${{launch_file}}"
  observed_file_hash=$(sha256sum "${{launch_file}}" | awk '{{print $1}}')
  observed_file_size=$(wc -c < "${{launch_file}}" | tr -d '[:space:]')
  if [ "${{observed_file_hash}}" != "${{expected_file_hash}}" ] || \
     [ "${{observed_file_size}}" != "${{expected_file_size}}" ]; then
    echo "ERROR: launch file differs from its frozen identity: ${{launch_file}}" >&2
    emit_preflight_failure "launch_file_identity_mismatch" "${{file_category}}:${{file_label}}:${{launch_file}}"
  fi
done < "${{launch_files_contract}}"

static_install_path_is_expected() {{
  local candidate="$1"
  case "${{candidate}}" in
    "${{launch_files_contract#${{install_root}}/}}"|\
    "${{launch_identity#${{install_root}}/}}"|\
    "${{runner_identity#${{install_root}}/}}"|\
    "metadata/runtime_identity.json") return 0 ;;
  esac
  awk -F '\t' -v target="${{candidate}}" '
    $5 == target {{ matches++ }}
    END {{ exit matches == 1 ? 0 : 1 }}
  ' "${{launch_files_contract}}"
}}

static_install_file_count=0
while IFS= read -r -d '' static_install_object; do
  relative_static_path="${{static_install_object#${{install_root}}/}}"
  case "${{relative_static_path}}" in
    install/hwop-*|install/hwop-*/*) continue ;;
  esac
  if [ -L "${{static_install_object}}" ] || [ ! -f "${{static_install_object}}" ]; then
    emit_preflight_failure \
      "static_install_nonregular_object" \
      "${{relative_static_path}}"
  fi
  if ! static_install_path_is_expected "${{relative_static_path}}"; then
    emit_preflight_failure \
      "static_install_unexpected_file" \
      "${{relative_static_path}}"
  fi
  static_install_file_count=$((static_install_file_count + 1))
done < <(find "${{install_root}}" -mindepth 1 ! -type d -print0)
if [ "${{static_install_file_count}}" -ne "${{expected_static_install_file_count}}" ]; then
  emit_preflight_failure \
    "static_install_file_count_mismatch" \
    "observed=${{static_install_file_count}} expected=${{expected_static_install_file_count}}"
fi

archive_epoch=$(date +%s)
archive_root="run/archive/preexisting-${{revision}}-${{server_run_id}}-${{archive_epoch}}"
if [ -e sim_results ] || [ -e run/sim_results ]; then
  mkdir -p "${{archive_root}}"
  if [ -e sim_results ]; then mv -- sim_results "${{archive_root}}/sim_results"; fi
  if [ -e run/sim_results ]; then mv -- run/sim_results "${{archive_root}}/run_sim_results"; fi
fi
rm -rf run/csrc "${{return_root}}" "run/${{revision}}_${{server_run_id}}_failure" \
  "${{return_archive}}"
for stale_output in "${{install_root}}/install"/hwop-*; do
  if [ -e "${{stale_output}}" ]; then
    rm -rf -- "${{stale_output}}"
  fi
done
if compgen -G "${{install_root}}/install/hwop-*" >/dev/null; then
  echo "ERROR: stale readback output remains after cleanup" >&2
  emit_preflight_failure "stale_readback_cleanup_failed" "${{install_root}}/install/hwop-*"
fi
mkdir -p sim_results run/sim_results

runtime_log_sink_contract="run/sim_results/.${{revision}}_runtime_log_sinks.tsv"
: > "${{runtime_log_sink_contract}}"
declare -A runtime_log_sink_expected=()
install_runtime_log_sinks() {{
  diagnostic_sink_count=0
  sink_runtime_log() {{
    local relative_path="$1"
    local sink_path="sim_results/${{relative_path}}"
    if [ -e "${{sink_path}}" ] || [ -L "${{sink_path}}" ]; then
      emit_preflight_failure "runtime_log_sink_collision" "${{sink_path}}"
    fi
    mkdir -p "$(dirname "${{sink_path}}")"
    ln -s /dev/null "${{sink_path}}"
    if [ ! -L "${{sink_path}}" ] || [ "$(readlink "${{sink_path}}")" != /dev/null ]; then
      emit_preflight_failure "runtime_log_sink_creation_failed" "${{sink_path}}"
    fi
    diagnostic_sink_count=$((diagnostic_sink_count + 1))
    runtime_log_sink_expected["${{relative_path}}"]=1
    printf '%s\n' "${{relative_path}}" >> "${{runtime_log_sink_contract}}"
  }}
  for diagnostic_slice in $(awk 'BEGIN {{ for (slice_index = 0; slice_index < 28; slice_index++) print slice_index }}'); do
    sink_runtime_log "gconfig2slice/slice${{diagnostic_slice}}/gconfig2slice.log"
    sink_runtime_log "nrm_buf_write/slice${{diagnostic_slice}}/nrm2buf_write.log"
    sink_runtime_log "nrm_buf_read/slice${{diagnostic_slice}}/nrm2buf_read.log"
    for diagnostic_mse in 0 1 2 3 4; do
      for diagnostic_channel in req wdata rdata; do
        sink_runtime_log "local/slice${{diagnostic_slice}}/local_mse${{diagnostic_mse}}_${{diagnostic_channel}}.log"
      done
    done
    for diagnostic_bank in 0 1 2 3; do
      sink_runtime_log "local/slice${{diagnostic_slice}}/hub/local_hub_req_bank${{diagnostic_bank}}.log"
      sink_runtime_log "bank_frame/slice${{diagnostic_slice}}/bank${{diagnostic_bank}}_frame.log"
      sink_runtime_log "bank_frame/slice${{diagnostic_slice}}/bank${{diagnostic_bank}}_mc_rdata.log"
      sink_runtime_log "bank_frame/slice${{diagnostic_slice}}/bank${{diagnostic_bank}}_full.log"
    done
    for diagnostic_channel in req wdata rdata; do
      sink_runtime_log "global/slice${{diagnostic_slice}}/global_req_${{diagnostic_channel}}.log"
    done
  done
  sink_runtime_log "local_summary/slice_all/local_summary.log"
  if [ "${{diagnostic_sink_count}}" -ne "${{expected_diagnostic_sink_count}}" ]; then
    emit_preflight_failure "runtime_log_sink_count_mismatch" "observed=${{diagnostic_sink_count}} expected=${{expected_diagnostic_sink_count}}"
  fi
  actual_sink_count=$(find sim_results -type l -print | wc -l | tr -d '[:space:]')
  if [ "${{actual_sink_count}}" -ne "${{expected_diagnostic_sink_count}}" ] || \
     find sim_results -type l ! -lname /dev/null -print | grep -q .; then
    emit_preflight_failure "runtime_log_sink_identity_mismatch" "all runtime sinks must point exactly to /dev/null"
  fi
}}
install_runtime_log_sinks

inspect_runtime_log_budget() {{
  local runtime_log_object relative_log_path runtime_log_size
  local runtime_regular_total=0
  while IFS= read -r -d '' runtime_log_object; do
    relative_log_path="${{runtime_log_object#sim_results/}}"
    if [ -L "${{runtime_log_object}}" ]; then
      if [ "$(readlink "${{runtime_log_object}}")" != /dev/null ] || \
         [[ ! -v runtime_log_sink_expected["${{relative_log_path}}"] ]]; then
        printf 'unknown_runtime_log_symlink:%s\n' "${{relative_log_path}}"
        return 1
      fi
    elif [ -d "${{runtime_log_object}}" ]; then
      continue
    elif [ -f "${{runtime_log_object}}" ]; then
      if [ "${{relative_log_path}}" != "gexec2slice/slice_all/gexec2slice.log" ]; then
        printf 'unknown_runtime_log_file:%s\n' "${{relative_log_path}}"
        return 1
      fi
      runtime_log_size=$(stat -c %s "${{runtime_log_object}}")
      runtime_regular_total=$((runtime_regular_total + runtime_log_size))
      if [ "${{runtime_regular_total}}" -gt "${{runtime_log_total_size_limit_bytes}}" ]; then
        printf 'runtime_log_total_size_exceeded:%s:%s\n' \
          "${{runtime_regular_total}}" "${{runtime_log_total_size_limit_bytes}}"
        return 1
      fi
    else
      printf 'runtime_log_non_regular_object:%s\n' "${{relative_log_path}}"
      return 1
    fi
  done < <(find sim_results -mindepth 1 -print0 2>/dev/null)
  printf '%s\n' "${{runtime_regular_total}}"
}}

console_log="run/sim_results/${{revision}}_console.log"
phase_progress_log="run/sim_results/${{revision}}_phase_progress.tsv"
phase_timeout_record="run/sim_results/${{revision}}_phase_timeout.tsv"
phase_watchdog_done_record="run/sim_results/${{revision}}_phase_watchdog_done.tsv"
console_fifo="run/sim_results/.${{revision}}_console.fifo"
complete_console_snapshot="run/sim_results/.${{revision}}_console_complete.log"
readback_live_validation_state="run/sim_results/.${{revision}}_readback_live_validated.tsv"
: > "${{console_log}}"
: > "${{phase_progress_log}}"
rm -f -- "${{phase_timeout_record}}" "${{phase_watchdog_done_record}}" \
  "${{console_fifo}}" "${{complete_console_snapshot}}" "${{complete_console_snapshot}}.tmp" \
  "${{readback_live_validation_state}}"
: > "${{readback_live_validation_state}}"
mkfifo "${{console_fifo}}"

capture_complete_console_snapshot() {{
  local final_byte
  cp -- "${{console_log}}" "${{complete_console_snapshot}}.tmp"
  if [ ! -s "${{complete_console_snapshot}}.tmp" ]; then
    : > "${{complete_console_snapshot}}"
    rm -f -- "${{complete_console_snapshot}}.tmp"
    return 0
  fi
  final_byte=$(tail -c 1 "${{complete_console_snapshot}}.tmp" | od -An -t x1 | tr -d '[:space:]')
  if [ "${{final_byte}}" = "0a" ]; then
    mv -- "${{complete_console_snapshot}}.tmp" "${{complete_console_snapshot}}"
  else
    sed '$d' "${{complete_console_snapshot}}.tmp" > "${{complete_console_snapshot}}"
    rm -f -- "${{complete_console_snapshot}}.tmp"
  fi
}}

validate_ordered_progress() {{
  local progress_input="${{1:-${{console_log}}}}"
  awk -v expected_preload="${{expected_preload_count}}" \
      -v expected_repeat="${{expected_repeat_num}}" \
      -v expected_stages="${{expected_stage_count}}" \
      -v observer_mode="${{testbench_observer_mode}}" '
    function reject(message) {{ if (!invalid) {{ invalid = 1; reason = message }} }}
    index($0, "JSON: Loading matrix[") > 0 {{
      load_index = $0
      sub(/^.*JSON: Loading matrix\\[/, "", load_index)
      sub(/\\].*$/, "", load_index)
      if (runtime_started || pending_load || load_index !~ /^[0-9]+$/ ||
          load_index + 0 != load_count || load_count >= expected_preload) {{
        reject("preload_index_or_order_violation")
      }} else {{ pending_load = 1; load_count++ }}
    }}
    index($0, "PASS: Continuous transfer completed successfully") > 0 {{
      if (!pending_load || pass_count >= expected_preload || runtime_started) {{
        reject("preload_pass_pair_violation")
      }} else {{ pending_load = 0; pass_count++ }}
    }}
    index($0, "INFO: slice start") > 0 {{
      if (pass_count != expected_preload || pending_load) {{
        reject("runtime_start_before_preload_complete")
      }}
      runtime_started = 1
      if (observer_mode == "fixed_slice0_start_slice1_finish") {{
        if (start_count >= expected_repeat || start_count != finish_count) {{
          reject("observer_start_order_or_limit_violation")
        }} else {{ start_count++ }}
      }}
    }}
    index($0, "INFO: slice completed after") > 0 {{
      if (observer_mode != "fixed_slice0_start_slice1_finish" ||
          pass_count != expected_preload || finish_count >= expected_repeat ||
          start_count != finish_count + 1) {{
        reject("observer_finish_order_or_limit_violation")
      }} else {{ finish_count++ }}
    }}
    index($0, "RUNTIME_STAGE_COMPLETE") > 0 &&
      index($0, "RUNTIME_ALL_STAGES_COMPLETE") == 0 {{
      stage_index = $0
      sub(/^.*RUNTIME_STAGE_COMPLETE[[:space:]]+stage=/, "", stage_index)
      sub(/[[:space:]].*$/, "", stage_index)
      if (observer_mode != "mask_aware_runtime_stage_markers" ||
          pass_count != expected_preload || stage_index !~ /^[0-9]+$/ ||
          stage_index + 0 != stage_count || stage_count >= expected_stages) {{
        reject("runtime_stage_order_or_limit_violation")
      }} else {{ runtime_started = 1; stage_count++ }}
    }}
    $0 == "Simulation completed successfully!" {{
      complete_count++
      if (complete_count != 1 ||
          (observer_mode == "fixed_slice0_start_slice1_finish" &&
           (start_count != expected_repeat || finish_count != expected_repeat)) ||
          (observer_mode == "mask_aware_runtime_stage_markers" &&
           stage_count != expected_stages)) {{
        reject("natural_completion_before_runtime_contract")
      }}
    }}
    END {{
      if (invalid) {{ print reason; exit 1 }}
      print "valid"
    }}
  ' "${{progress_input}}"
}}

readback_path_is_expected() {{
  local candidate="$1"
  awk -F '\t' -v target="${{candidate}}" '
    $1 == target {{ matches++ }}
    END {{ exit matches == 1 ? 0 : 1 }}
  ' "${{readback_contract}}"
}}

readback_directory_is_expected() {{
  local candidate="${{1%/}}/"
  awk -F '\t' -v prefix="${{candidate}}" '
    index($1, prefix) == 1 {{ matches++ }}
    END {{ exit matches > 0 ? 0 : 1 }}
  ' "${{readback_contract}}"
}}

validate_readback_file_record() {{
  local observed_path="$1"
  local expected_line_count="$2"
  local expected_size observed_size final_byte
  expected_size=$((expected_line_count * 129))
  observed_size=$(stat -c %s "${{observed_path}}")
  if [ "${{observed_size}}" -gt "${{expected_size}}" ]; then
    printf 'readback_file_oversize:%s:%s:%s\n' \
      "${{observed_path}}" "${{observed_size}}" "${{expected_size}}"
    return 1
  fi
  if ! od -An -v -t x1 "${{observed_path}}" | awk '
    {{ for (byte_field_index = 1; byte_field_index <= NF; byte_field_index++)
         if ($byte_field_index != "30" && $byte_field_index != "31" && $byte_field_index != "0a") invalid = 1 }}
    END {{ exit invalid ? 1 : 0 }}
  '; then
    printf 'readback_file_invalid_byte:%s\n' "${{observed_path}}"
    return 1
  fi
  final_byte=""
  if [ "${{observed_size}}" -gt 0 ]; then
    final_byte=$(tail -c 1 "${{observed_path}}" | od -An -t x1 | tr -d '[:space:]')
  fi
  if ! awk -v final_byte="${{final_byte}}" '
    {{
      widths[NR] = length($0)
      if ($0 ~ /[^01]/ || length($0) > 128) invalid = 1
    }}
    END {{
      complete_records = NR
      if (final_byte != "0a" && NR > 0) complete_records = NR - 1
      for (record_index = 1; record_index <= complete_records; record_index++)
        if (widths[record_index] != 128) invalid = 1
      exit invalid ? 1 : 0
    }}
  ' "${{observed_path}}"; then
    printf 'readback_file_invalid_record:%s\n' "${{observed_path}}"
    return 1
  fi
  if [ "${{observed_size}}" -eq "${{expected_size}}" ]; then
    if [ "${{final_byte}}" != "0a" ]; then
      printf 'readback_file_missing_final_lf:%s\n' "${{observed_path}}"
      return 1
    fi
    if ! awk -v expected="${{expected_line_count}}" '
      length($0) != 128 || $0 ~ /[^01]/ {{ invalid = 1 }}
      END {{ exit (NR == expected && !invalid) ? 0 : 1 }}
    ' "${{observed_path}}"; then
      printf 'readback_file_exact_record_contract_failed:%s\n' "${{observed_path}}"
      return 1
    fi
    printf 'complete\n'
  else
    printf 'incomplete\n'
  fi
}}

inspect_readback_progress() {{
  local validation_mode="${{1:-live}}"
  local output_root observed_path expected_line_count expected_size observed_size
  local record_status live_validation_record
  local complete_count=0
  while IFS= read -r -d '' output_root; do
    if [ -L "${{output_root}}" ] || [ ! -d "${{output_root}}" ]; then
      printf 'readback_output_root_not_directory:%s\n' "${{output_root}}"
      return 1
    fi
    if ! readback_directory_is_expected "${{output_root}}"; then
      printf 'unexpected_readback_directory:%s\n' "${{output_root}}"
      return 1
    fi
    while IFS= read -r -d '' observed_path; do
      if [ -L "${{observed_path}}" ]; then
        printf 'readback_symlink_forbidden:%s\n' "${{observed_path}}"
        return 1
      elif [ -d "${{observed_path}}" ]; then
        if ! readback_directory_is_expected "${{observed_path}}"; then
          printf 'unexpected_readback_directory:%s\n' "${{observed_path}}"
          return 1
        fi
      elif [ -f "${{observed_path}}" ]; then
        if ! readback_path_is_expected "${{observed_path}}"; then
          printf 'unexpected_readback_file:%s\n' "${{observed_path}}"
          return 1
        fi
      else
        printf 'readback_non_regular_object:%s\n' "${{observed_path}}"
        return 1
      fi
    done < <(find "${{output_root}}" -mindepth 1 -print0 2>/dev/null)
  done < <(
    find "${{install_root}}/install" -mindepth 1 -maxdepth 1 \
      -name 'hwop-*' -print0 2>/dev/null
  )
  while IFS=$'\t' read -r observed_path expected_line_count; do
    if [ -L "${{observed_path}}" ] || {{ [ -e "${{observed_path}}" ] && [ ! -f "${{observed_path}}" ]; }}; then
      printf 'readback_contract_path_not_regular:%s\n' "${{observed_path}}"
      return 1
    fi
    if [ -f "${{observed_path}}" ]; then
      expected_size=$((expected_line_count * 129))
      observed_size=$(stat -c %s "${{observed_path}}")
      if [ "${{observed_size}}" -gt "${{expected_size}}" ]; then
        printf 'readback_file_oversize:%s:%s:%s\n' \
          "${{observed_path}}" "${{observed_size}}" "${{expected_size}}"
        return 1
      fi
      if [ "${{validation_mode}}" = final ] || \
         [ "${{observed_size}}" -eq "${{expected_size}}" ]; then
        live_validation_record="${{observed_path}}"$'\t'"${{observed_size}}"
        if [ "${{validation_mode}}" = live ] && \
           grep -Fqx -- "${{live_validation_record}}" "${{readback_live_validation_state}}"; then
          record_status=complete
        else
          if ! record_status=$(validate_readback_file_record \
            "${{observed_path}}" "${{expected_line_count}}"); then
            printf '%s\n' "${{record_status}}"
            return 1
          fi
          if [ "${{validation_mode}}" = live ] && [ "${{record_status}}" = complete ]; then
            printf '%s\n' "${{live_validation_record}}" >> "${{readback_live_validation_state}}"
          fi
        fi
        if [ "${{validation_mode}}" = final ] && [ "${{record_status}}" != complete ]; then
          printf 'readback_file_incomplete_at_final:%s:%s:%s\n' \
            "${{observed_path}}" "${{observed_size}}" "${{expected_size}}"
          return 1
        fi
      else
        record_status=incomplete
      fi
      if [ "${{record_status}}" = complete ]; then
        complete_count=$((complete_count + 1))
      fi
    fi
  done < "${{readback_contract}}"
  printf '%s\n' "${{complete_count}}"
}}

phase_watchdog() {{
  local monitored_pid="$1"
  local last_signature=""
  local last_progress_epoch
  last_progress_epoch=$(date +%s)
  while kill -0 "${{monitored_pid}}" 2>/dev/null; do
    local now_epoch preload_count start_count finish_count stage_count load_count
    local region_count simulation_complete_count compute_progress
    local phase metric phase_limit signature stalled_seconds protocol_reason
    local runtime_log_guard_output
    now_epoch=$(date +%s)
    capture_complete_console_snapshot
    load_count=$(grep -c 'JSON: Loading matrix\\[' "${{complete_console_snapshot}}" 2>/dev/null || true)
    preload_count=$(grep -c 'PASS: Continuous transfer completed successfully' "${{complete_console_snapshot}}" 2>/dev/null || true)
    start_count=$(grep -c 'INFO: slice start' "${{complete_console_snapshot}}" 2>/dev/null || true)
    finish_count=$(grep -c 'INFO: slice completed after' "${{complete_console_snapshot}}" 2>/dev/null || true)
    stage_count=$(grep -c 'RUNTIME_STAGE_COMPLETE' "${{complete_console_snapshot}}" 2>/dev/null || true)
    simulation_complete_count=$(grep -c '^Simulation completed successfully!$' "${{complete_console_snapshot}}" 2>/dev/null || true)
    if ! runtime_log_guard_output=$(inspect_runtime_log_budget); then
      metric="runtime_log_contract_violation=${{runtime_log_guard_output}}"
      printf '%s\t%s\t0\t0\t%s\n' "protocol_error" "${{metric}}" "runtime_log_unknown_or_total_limit" > "${{phase_timeout_record}}"
      echo "ERROR: runtime log protocol failed: ${{metric}}" >&2
      kill -TERM "${{monitored_pid}}" 2>/dev/null || true
      return 70
    fi
    if ! region_count=$(inspect_readback_progress live); then
      metric="readback_contract_violation=${{region_count}}"
      printf '%s\t%s\t0\t0\t%s\n' "protocol_error" "${{metric}}" "readback_exact_set_or_size_violation" > "${{phase_timeout_record}}"
      echo "ERROR: ordered readback protocol failed: ${{metric}}" >&2
      kill -TERM "${{monitored_pid}}" 2>/dev/null || true
      return 70
    fi
    if ! protocol_reason=$(validate_ordered_progress "${{complete_console_snapshot}}"); then
      metric="loads=${{load_count}} passes=${{preload_count}} starts=${{start_count}} finishes=${{finish_count}} stages=${{stage_count}} regions=${{region_count}} complete=${{simulation_complete_count}}"
      printf '%s\t%s\t0\t0\t%s\n' "protocol_error" "${{metric}}" "${{protocol_reason}}" > "${{phase_timeout_record}}"
      echo "ERROR: ordered phase protocol failed: reason=${{protocol_reason}} ${{metric}}" >&2
      kill -TERM "${{monitored_pid}}" 2>/dev/null || true
      return 70
    fi
    if [ "${{region_count}}" -gt "${{expected_region_count}}" ] || \
       {{ [ "${{simulation_complete_count}}" -gt 0 ] && [ "${{region_count}}" -ne "${{expected_region_count}}" ]; }}; then
      metric="regions=${{region_count}} expected=${{expected_region_count}} complete=${{simulation_complete_count}}"
      printf '%s\t%s\t0\t0\t%s\n' "protocol_error" "${{metric}}" "readback_count_or_completion_order_violation" > "${{phase_timeout_record}}"
      echo "ERROR: ordered readback protocol failed: ${{metric}}" >&2
      kill -TERM "${{monitored_pid}}" 2>/dev/null || true
      return 70
    fi
    if [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ]; then
      compute_progress="${{finish_count}}/${{expected_repeat_num}} pending=$((start_count - finish_count))"
    else
      compute_progress="${{stage_count}}"
    fi

    if [ "${{preload_count}}" -lt "${{expected_preload_count}}" ]; then
      phase="preload"
      metric="passes=${{preload_count}} loads=${{load_count}}"
      phase_limit="${{preload_stall_timeout_seconds}}"
    elif {{ [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ] && [ "${{start_count}}" -eq 0 ]; }} || \
         {{ [ "${{testbench_observer_mode}}" = "mask_aware_runtime_stage_markers" ] && [ "${{stage_count}}" -eq 0 ]; }}; then
      phase="first_start"
      metric="0"
      phase_limit="${{first_start_stall_timeout_seconds}}"
    elif [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ] && \
         {{ [ "${{start_count}}" -lt "${{expected_repeat_num}}" ] || [ "${{finish_count}}" -lt "${{expected_repeat_num}}" ]; }}; then
      phase="compute_observer"
      metric="${{compute_progress}}"
      phase_limit="${{compute_stall_timeout_seconds}}"
    elif [ "${{testbench_observer_mode}}" = "mask_aware_runtime_stage_markers" ] && \
         [ "${{stage_count}}" -lt "${{expected_stage_count}}" ]; then
      phase="compute_observer"
      metric="${{compute_progress}}"
      phase_limit="${{compute_stall_timeout_seconds}}"
    elif [ "${{region_count}}" -lt "${{expected_region_count}}" ]; then
      phase="readback"
      metric="${{region_count}}/${{expected_region_count}}"
      phase_limit="${{readback_stall_timeout_seconds}}"
    elif [ "${{region_count}}" -eq "${{expected_region_count}}" ]; then
      phase="completion_exit"
      metric="regions=${{region_count}} simulation_complete=${{simulation_complete_count}}"
      phase_limit="${{completion_exit_stall_timeout_seconds}}"
    fi

    signature="${{phase}}:${{metric}}"
    if [ "${{signature}}" != "${{last_signature}}" ]; then
      last_signature="${{signature}}"
      last_progress_epoch="${{now_epoch}}"
      printf '%s\t%s\t%s\n' "${{now_epoch}}" "${{phase}}" "${{metric}}" >> "${{phase_progress_log}}"
    fi
    stalled_seconds=$((now_epoch - last_progress_epoch))
    if [ "${{stalled_seconds}}" -ge "${{phase_limit}}" ]; then
      printf '%s\t%s\t%s\t%s\t%s\n' \
        "${{phase}}" "${{metric}}" "${{stalled_seconds}}" "${{phase_limit}}" "stall_timeout" \
        > "${{phase_timeout_record}}"
      echo "ERROR: phase stalled: phase=${{phase}} progress=${{metric}} stalled_seconds=${{stalled_seconds}} limit_seconds=${{phase_limit}}" >&2
      kill -TERM "${{monitored_pid}}" 2>/dev/null || true
      return 70
    fi
    sleep "${{phase_poll_seconds}}"
  done
  printf 'normal_process_exit\t0\n' > "${{phase_watchdog_done_record}}"
  return 0
}}

# The run argv is content-addressed.  GNU make control variables inherited from
# an interactive shell could otherwise add makefiles, force dry-run/parallel
# behavior, or alter recursive-make semantics without changing that argv.
unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL

runner_phase="runtime"
run_start_epoch=$(date +%s)
trap - ERR
set +e
tee "${{console_log}}" < "${{console_fifo}}" &
tee_pid=$!
timeout --signal=TERM --kill-after=5m "${{wall_timeout}}" \
  "${{run_argv[@]}}" \
  </dev/null > "${{console_fifo}}" 2>&1 &
run_pid=$!
phase_watchdog "${{run_pid}}" &
phase_watchdog_pid=$!
wait "${{run_pid}}"
process_exit_status=$?
wait "${{tee_pid}}"
tee_exit_status=$?
wait "${{phase_watchdog_pid}}" 2>/dev/null
raw_phase_watchdog_exit_status=$?
rm -f -- "${{console_fifo}}" "${{complete_console_snapshot}}" "${{complete_console_snapshot}}.tmp"
phase_watchdog_exit_status="${{raw_phase_watchdog_exit_status}}"
final_protocol_reason="valid"
final_console_byte=""
if [ -s "${{console_log}}" ]; then
  final_console_byte=$(tail -c 1 "${{console_log}}" | od -An -t x1 | tr -d '[:space:]')
fi
if [ -n "${{final_console_byte}}" ] && [ "${{final_console_byte}}" != "0a" ]; then
  final_protocol_reason="unterminated_final_console_record"
elif ! final_protocol_reason=$(validate_ordered_progress "${{console_log}}"); then
  :
fi
if [ "${{final_protocol_reason}}" != "valid" ] && [ ! -f "${{phase_timeout_record}}" ]; then
  printf '%s\t%s\t0\t0\t%s\n' \
    "protocol_error" "final_console_revalidation" "${{final_protocol_reason}}" \
    > "${{phase_timeout_record}}"
  phase_watchdog_exit_status=70
fi
run_end_epoch=$(date +%s)
wall_time_seconds=$((run_end_epoch - run_start_epoch))
set -e
trap unexpected_runner_error ERR
runner_phase="postrun"

mkdir -p "${{return_root}}/run_sim_results" "${{return_root}}/config"
timeout_status="not_timed_out"
phase_timeout_status="not_timed_out"
phase_timeout_phase="none"
phase_last_progress="complete"
phase_stall_seconds=0
phase_failure_reason="none"
make_exit_status=${{process_exit_status}}
termination_kind="natural_process_exit"
if [ -f "${{phase_timeout_record}}" ]; then
  IFS=$'\t' read -r phase_timeout_phase phase_last_progress phase_stall_seconds phase_limit_seconds phase_failure_reason < "${{phase_timeout_record}}"
  if [ "${{phase_timeout_phase}}" = protocol_error ]; then
    phase_timeout_status="protocol_error"
    termination_kind="phase_protocol_failure"
  else
    phase_timeout_status="stalled"
    termination_kind="phase_stall_timeout"
  fi
  make_exit_status=-1
elif [ "${{phase_watchdog_exit_status}}" -ne 0 ] || \
     [ ! -s "${{phase_watchdog_done_record}}" ]; then
  phase_timeout_status="watchdog_failure"
  phase_timeout_phase="watchdog"
  phase_failure_reason="watchdog_abnormal_exit_or_missing_done_sentinel"
  termination_kind="phase_watchdog_failure"
  make_exit_status=-1
fi
if [ "${{process_exit_status}}" -eq 124 ] || [ "${{process_exit_status}}" -eq 137 ]; then
  timeout_status="wall_timeout"
  make_exit_status=-1
  if [ "${{phase_timeout_status}}" = "not_timed_out" ]; then
    termination_kind="wall_timeout"
  fi
fi
simulator_exit_status=-1
simulator_exit_status_observed=false
simulator_status_marker_count=$(grep -Ec '^Simulation exit status: [0-9]+$' "${{console_log}}" 2>/dev/null || true)
if [ "${{simulator_status_marker_count}}" -eq 1 ]; then
  simulator_exit_status=$(awk '/^Simulation exit status: [0-9]+$/ {{ print $4 }}' "${{console_log}}")
  simulator_exit_status_observed=true
fi
if [ "${{timeout_status}}" = "not_timed_out" ] && \
   [ "${{phase_timeout_status}}" = "not_timed_out" ]; then
  if [ "${{tee_exit_status}}" -ne 0 ]; then
    termination_kind="console_capture_failure"
  elif [ "${{simulator_exit_status_observed}}" != true ]; then
    termination_kind="simulator_exit_status_unavailable"
  elif [ "${{simulator_exit_status}}" -ne "${{make_exit_status}}" ]; then
    termination_kind="make_simulator_status_mismatch"
  elif [ "${{simulator_exit_status}}" -ne 0 ]; then
    termination_kind="simulator_failure"
  elif [ "${{make_exit_status}}" -ne 0 ]; then
    termination_kind="make_failure"
  fi
fi
preload_pass_count=$(grep -c 'PASS: Continuous transfer completed successfully' "${{console_log}}" 2>/dev/null || true)
completed_stage_count=$(grep -c 'RUNTIME_STAGE_COMPLETE' "${{console_log}}" 2>/dev/null || true)
all_stages_complete_count=$(grep -c 'RUNTIME_ALL_STAGES_COMPLETE' "${{console_log}}" 2>/dev/null || true)
stage_marker_status="failed"
if awk -v expected="${{expected_stage_count}}" -v stage_contract="${{stage_contract}}" '
  BEGIN {{
    while ((getline contract_line < stage_contract) > 0) {{
      split(contract_line, contract_fields, "\t")
      expected_mask[contract_fields[1] + 0] = tolower(contract_fields[3])
    }}
    close(stage_contract)
  }}
  /RUNTIME_STAGE_COMPLETE/ {{
    marker_count++
    if (NF != 5 || $1 !~ /^\\[[0-9]+\\]$/ ||
        $2 != "RUNTIME_STAGE_COMPLETE" ||
        $3 !~ /^stage=[0-9]+$/ ||
        $4 !~ /^mask=0x[0-9a-fA-F]+$/ ||
        $5 !~ /^cycles=[0-9]+$/) {{
      invalid = 1
      next
    }}
    field_matches = 0
    mask_matches = 0
    stage_index = -1
    observed_mask = ""
    for (field_index = 1; field_index <= NF; field_index++) {{
      if ($field_index ~ /^stage=[0-9]+$/) {{
        split($field_index, pair, "=")
        stage_index = pair[2] + 0
        field_matches++
      }}
      if ($field_index ~ /^mask=0x[0-9a-fA-F]+$/) {{
        split($field_index, mask_pair, "=")
        observed_mask = tolower(mask_pair[2])
        mask_matches++
      }}
    }}
    if (field_matches != 1 || mask_matches != 1 ||
        stage_index < 0 || stage_index >= expected ||
        stage_index != marker_count - 1 || seen[stage_index]++ ||
        observed_mask != expected_mask[stage_index]) {{
      invalid = 1
    }}
  }}
  END {{
    if (marker_count != expected) invalid = 1
    for (stage_index = 0; stage_index < expected; stage_index++) {{
      if (!(stage_index in seen)) invalid = 1
    }}
    exit invalid ? 1 : 0
  }}
' "${{console_log}}"; then
  stage_marker_status="passed"
fi
all_stages_marker_status="failed"
if awk -v expected="${{expected_stage_count}}" '
  /RUNTIME_STAGE_COMPLETE/ {{
    if (all_seen) invalid = 1
    stage_count++
  }}
  /RUNTIME_ALL_STAGES_COMPLETE/ {{
    marker_count++
    if (NF != 3 || $1 !~ /^\\[[0-9]+\\]$/ ||
        $2 != "RUNTIME_ALL_STAGES_COMPLETE" ||
        $3 !~ /^count=[0-9]+$/) {{
      invalid = 1
      next
    }}
    field_matches = 0
    completed_count = -1
    for (field_index = 1; field_index <= NF; field_index++) {{
      if ($field_index ~ /^count=[0-9]+$/) {{
        split($field_index, pair, "=")
        completed_count = pair[2] + 0
        field_matches++
      }}
    }}
    if (field_matches != 1 || completed_count != expected ||
        stage_count != expected || all_seen) invalid = 1
    all_seen = 1
  }}
  END {{ exit (marker_count == 1 && stage_count == expected && !invalid) ? 0 : 1 }}
' "${{console_log}}"; then
  all_stages_marker_status="passed"
fi
observer_start_count=$(grep -c 'INFO: slice start' "${{console_log}}" 2>/dev/null || true)
observer_finish_count=$(grep -c 'INFO: slice completed after' "${{console_log}}" 2>/dev/null || true)
simulation_complete_count=$(grep -c '^Simulation completed successfully!$' "${{console_log}}" 2>/dev/null || true)
reserved_clock_force_count=$(grep -Ec '^(ucli%[[:space:]]*)?RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING$' "${{console_log}}" 2>/dev/null || true)
reserved_clock_failure_count=$(grep -c 'RESERVED_AXI_CLOCK_FORCE_FAILED' "${{console_log}}" 2>/dev/null || true)
if [ "${{testbench_observer_mode}}" = "fixed_slice0_start_slice1_finish" ]; then
  stage_marker_status="failed"
  all_stages_marker_status="failed"
  if [ "${{observer_start_count}}" -eq "${{expected_repeat_num}}" ] && \
     [ "${{observer_finish_count}}" -eq "${{expected_repeat_num}}" ] && \
     [ "${{reserved_clock_force_count}}" -eq 1 ] && \
     [ "${{reserved_clock_failure_count}}" -eq 0 ]; then
    # The frozen observer contract binds the final pair to the final
    # barrier-ordered runtime stage.  This is schedule-derived stage evidence,
    # not a claim that the legacy TB emitted mask-aware stage markers.
    completed_stage_count="${{expected_stage_count}}"
    stage_marker_status="passed"
  fi
  if [ "${{stage_marker_status}}" = passed ] && \
     [ "${{simulation_complete_count}}" -eq 1 ]; then
    all_stages_marker_status="passed"
  fi
fi
region_contract_status="passed"
readback_validation_output=""
runtime_log_guard_status="passed"
runtime_log_guard_output=""
if ! runtime_log_guard_output=$(inspect_runtime_log_budget); then
  echo "ERROR: final runtime log validation failed: ${{runtime_log_guard_output}}" >&2
  runtime_log_guard_status="failed"
fi
if ! readback_validation_output=$(inspect_readback_progress final); then
  echo "ERROR: final readback validation failed: ${{readback_validation_output}}" >&2
  region_contract_status="failed"
  returned_region_count=0
else
  returned_region_count="${{readback_validation_output}}"
fi
if [ "${{returned_region_count}}" -ne "${{expected_region_count}}" ]; then
  echo "ERROR: returned ${{returned_region_count}} readback-region files; expected ${{expected_region_count}}" >&2
  region_contract_status="failed"
fi
preload_status="failed"
if [ "${{preload_pass_count}}" -eq "${{expected_preload_count}}" ]; then
  preload_status="passed"
fi
effective_status=0
if [ "${{tee_exit_status}}" -ne 0 ]; then
  effective_status=9
elif [ "${{phase_timeout_status}}" = "stalled" ]; then
  effective_status=10
elif [ "${{phase_timeout_status}}" = "protocol_error" ]; then
  effective_status=12
elif [ "${{phase_timeout_status}}" = "watchdog_failure" ]; then
  effective_status=13
elif [ "${{timeout_status}}" = "wall_timeout" ]; then
  effective_status=6
elif [ "${{simulator_exit_status_observed}}" != true ]; then
  effective_status=7
elif [ "${{simulator_exit_status}}" -ne "${{make_exit_status}}" ] || \
     [ "${{simulator_exit_status}}" -ne 0 ] || [ "${{make_exit_status}}" -ne 0 ]; then
  effective_status=8
fi
if [ "${{effective_status}}" -eq 0 ] && [ "${{preload_pass_count}}" -ne "${{expected_preload_count}}" ]; then
  effective_status=3
fi
if [ "${{effective_status}}" -eq 0 ] && {{ [ "${{stage_marker_status}}" != passed ] || [ "${{all_stages_marker_status}}" != passed ]; }}; then
  effective_status=4
fi
if [ "${{effective_status}}" -eq 0 ] && [ "${{region_contract_status}}" != passed ]; then
  effective_status=5
fi
if [ "${{effective_status}}" -eq 0 ] && [ "${{runtime_log_guard_status}}" != passed ]; then
  effective_status=14
fi
printf '%s\n' "${{effective_status}}" > run/sim_results/${{revision}}_exit_status.txt
if [ "${{effective_status}}" -ne 0 ]; then
  case "${{effective_status}}" in
    3) effective_failure_reason="preload_contract_failed" ;;
    4) effective_failure_reason="completion_evidence_failed" ;;
    5) effective_failure_reason="readback_contract_failed" ;;
    6) effective_failure_reason="wall_timeout" ;;
    7) effective_failure_reason="simulator_exit_status_unobserved" ;;
    8) effective_failure_reason="simulation_process_failed" ;;
    9) effective_failure_reason="console_tee_failed" ;;
    10) effective_failure_reason="phase_watchdog_stalled" ;;
    12) effective_failure_reason="phase_protocol_error" ;;
    13) effective_failure_reason="phase_watchdog_failed" ;;
    14) effective_failure_reason="runtime_log_contract_failed" ;;
    *) effective_failure_reason="unclassified_effective_status" ;;
  esac
  emit_runtime_failure "${{effective_status}}" "${{effective_failure_reason}}" \
    "make=${{make_exit_status}} simulator=${{simulator_exit_status}} observed=${{simulator_exit_status_observed}} tee=${{tee_exit_status}} timeout=${{timeout_status}} phase=${{phase_timeout_status}} preload=${{preload_pass_count}}/${{expected_preload_count}} stages=${{stage_marker_status}}/${{all_stages_marker_status}} readback=${{region_contract_status}}"
fi
printf '{{\n  "status": "%s",\n  "expected_transfer_count": %s,\n  "passed_transfer_count": %s\n}}\n' \
  "${{preload_status}}" "${{expected_preload_count}}" "${{preload_pass_count}}" \
  > "${{return_root}}/preload_readback_report.json"

simulator_version=$(vcs -ID 2>&1 | head -n 1 | tr -cd '[:alnum:] ._:/+-' || true)
if [ -z "${{simulator_version}}" ]; then simulator_version="unknown"; fi
rtl_version="server_entrypoint_unpinned"
sca_cfg_sha256=$(sha256sum "${{sca_cfg}}" | awk '{{print $1}}')
runner_sha256=$(sha256sum "${{runner_source}}" | awk '{{print $1}}')
runner_identity_sha256=$(sha256sum "${{runner_identity}}" | awk '{{print $1}}')
testbench_sha256=$(sha256sum tb_NDP_Top_new_phy.sv | awk '{{print $1}}')
server_makefile_sha256=$(sha256sum Makefile.tb_NDP_Top_new_phy | awk '{{print $1}}')
server_top_filelist_sha256=$(sha256sum rtl/filelists/NDP_Top_phy_filelist.f | awk '{{print $1}}')
server_source_inventory_sha256=$(sha256sum "${{server_source_inventory}}" | awk '{{print $1}}')
readback_contract_sha256=$(sha256sum "${{readback_contract}}" | awk '{{print $1}}')
runtime_identity_sha256=$(sha256sum "${{install_root}}/metadata/runtime_identity.json" | awk '{{print $1}}')
sca_cfg_d_sha256=$(sha256sum "${{sca_cfg_d}}" | awk '{{print $1}}')
diagnostic_allowlist_file="${{return_root}}/diagnostic_allowlist.tsv"
: > "${{diagnostic_allowlist_file}}"
diagnostic_return_file_count=0
diagnostic_return_total_bytes=0
copy_runtime_diagnostic_bounded() {{
  local relative_path="$1"
  local source_path="sim_results/${{relative_path}}"
  local destination_path="${{return_root}}/sim_results/${{relative_path}}"
  local source_size returned_size truncated file_sha256
  if [ ! -f "${{source_path}}" ] || [ -L "${{source_path}}" ]; then
    return 0
  fi
  source_size=$(wc -c < "${{source_path}}" | tr -d '[:space:]')
  mkdir -p "$(dirname "${{destination_path}}")"
  if [ "${{source_size}}" -gt "${{diagnostic_file_size_limit_bytes}}" ]; then
    head -c "${{diagnostic_file_size_limit_bytes}}" "${{source_path}}" > "${{destination_path}}"
    truncated=true
  else
    cp -a -- "${{source_path}}" "${{destination_path}}"
    truncated=false
  fi
  returned_size=$(wc -c < "${{destination_path}}" | tr -d '[:space:]')
  diagnostic_return_total_bytes=$((diagnostic_return_total_bytes + returned_size))
  if [ "${{returned_size}}" -gt "${{diagnostic_file_size_limit_bytes}}" ] || \
     [ "${{diagnostic_return_total_bytes}}" -gt "${{diagnostic_total_size_limit_bytes}}" ]; then
    echo "ERROR: bounded diagnostic policy exceeded" >&2
    emit_runtime_failure 14 \
      "bounded_diagnostic_policy_exceeded" \
      "relative_path=${{relative_path}} returned_size=${{returned_size}} total=${{diagnostic_return_total_bytes}}"
  fi
  file_sha256=$(sha256sum "${{destination_path}}" | awk '{{print $1}}')
  printf '%s\t%s\t%s\t%s\t%s\n' "${{relative_path}}" "${{source_size}}" \
    "${{returned_size}}" "${{truncated}}" "${{file_sha256}}" >> "${{diagnostic_allowlist_file}}"
  diagnostic_return_file_count=$((diagnostic_return_file_count + 1))
}}
copy_runtime_diagnostic_bounded "gexec2slice/slice_all/gexec2slice.log"
phase_watchdog_done=false
if [ "${{phase_watchdog_exit_status}}" -eq 0 ] && [ -s "${{phase_watchdog_done_record}}" ]; then
  phase_watchdog_done=true
fi
printf '{{\n  "schema_version": "resnet50-server-source-provenance-0.4",\n  "server_run_id": "%s",\n  "identity_policy": "logical_entrypoints_and_dir_home_recorded_nonblocking",\n  "preflight_source_policy": "readable_logical_entrypoints_only",\n  "makefile_sha256": "%s",\n  "testbench_sha256": "%s",\n  "top_filelist_sha256": "%s",\n  "source_inventory_sha256": "%s",\n  "entrypoint_record_count": 3,\n  "environment_record_count": 1,\n  "dir_home_value_sha256": "%s"\n}}\n' \
  "${{server_run_id}}" "${{server_makefile_sha256}}" "${{testbench_sha256}}" \
  "${{server_top_filelist_sha256}}" "${{server_source_inventory_sha256}}" \
  "${{dir_home_value_sha256}}" \
  > "${{return_root}}/server_source_provenance.json"
printf '{{\n  "server_run_id": "%s",\n  "execution_environment": "rtl_simulation",\n  "board_version": "not_applicable_rtl_simulation",\n  "simulator_version": "%s",\n  "rtl_version": "%s",\n  "firmware_version": "not_applicable_rtl_simulation",\n  "isa_contract": "model_execplan_package_manifest_and_execplan_128bit_v1",\n  "run_command": "%s",\n  "run_command_contract_sha256": "{run_command_contract_sha256}",\n  "runtime_make_override_sha256": "{runtime_make_override_sha256}",\n  "make_archive_policy": "runner_no_archive_target_v1",\n  "exit_status": %s,\n  "process_exit_status": %s,\n  "make_exit_status": %s,\n  "tee_exit_status": %s,\n  "phase_watchdog_exit_status": %s,\n  "raw_phase_watchdog_exit_status": %s,\n  "phase_watchdog_done": %s,\n  "simulator_exit_status": %s,\n  "simulator_exit_status_observed": %s,\n  "timeout_status": "%s",\n  "phase_timeout_status": "%s",\n  "phase_timeout_phase": "%s",\n  "phase_last_progress": "%s",\n  "phase_stall_seconds": %s,\n  "phase_failure_reason": "%s",\n  "termination_kind": "%s",\n  "preflight_status": "passed",\n  "wall_time_seconds": %s,\n  "freeze_id": "{freeze_id}",\n  "freeze_manifest_sha256": "{freeze_manifest_sha256}",\n  "package_manifest_sha256": "{package_manifest_sha256}",\n  "server_source_provenance": "server_source_provenance.json",\n  "preload_readback_report": "preload_readback_report.json",\n  "completed_runtime_stage_count": %s,\n  "expected_runtime_stage_count": %s,\n  "testbench_observer_mode": "%s",\n  "expected_testbench_repeat_num": %s,\n  "observed_slice0_start_count": %s,\n  "observed_slice1_finish_count": %s,\n  "reserved_clock_force_marker_count": %s,\n  "reserved_clock_failure_marker_count": %s,\n  "stage_marker_status": "%s",\n  "all_stages_marker_status": "%s",\n  "returned_region_count": %s,\n  "expected_region_count": %s,\n  "readback_region_contract_status": "%s",\n  "sca_cfg_sha256": "%s",\n  "sca_cfg_D_sha256": "%s",\n  "runner_sha256": "%s",\n  "runner_identity_sha256": "%s",\n  "testbench_sha256": "%s",\n  "readback_contract_sha256": "%s",\n  "stage_contract_sha256": "{stage_contract_sha256}",\n  "launch_files_contract_sha256": "{launch_files_contract_sha256}",\n  "launch_identity_sha256": "{launch_identity_sha256}",\n  "runtime_identity_sha256": "%s",\n  "wall_timeout": "%s",\n  "bank_frame_logging_policy": "{bank_frame_logging_policy}",\n  "reserved_clock_validation": "{reserved_clock_validation_policy}",\n  "runtime_log_sink_policy": "audited_sinks_unknown_log_guard_v2",\n  "runtime_log_total_size_limit_bytes": %s,\n  "diagnostic_sink_count": %s,\n  "diagnostic_return_file_count": %s,\n  "diagnostic_return_total_bytes": %s,\n  "diagnostic_file_size_limit_bytes": %s,\n  "diagnostic_total_size_limit_bytes": %s,\n  "return_file_contract": "return_file_contract.tsv",\n  "return_archive_policy": "bounded_exact_set_allowlist_v2"\n}}\n' \
  "${{server_run_id}}" "${{simulator_version}}" "${{rtl_version}}" "${{run_command}}" \
  "${{effective_status}}" "${{process_exit_status}}" "${{make_exit_status}}" "${{tee_exit_status}}" "${{phase_watchdog_exit_status}}" \
  "${{raw_phase_watchdog_exit_status}}" "${{phase_watchdog_done}}" \
  "${{simulator_exit_status}}" "${{simulator_exit_status_observed}}" \
  "${{timeout_status}}" "${{phase_timeout_status}}" "${{phase_timeout_phase}}" \
  "${{phase_last_progress}}" "${{phase_stall_seconds}}" "${{phase_failure_reason}}" "${{termination_kind}}" "${{wall_time_seconds}}" \
  "${{completed_stage_count}}" "${{expected_stage_count}}" \
  "${{testbench_observer_mode}}" "${{expected_repeat_num}}" \
  "${{observer_start_count}}" "${{observer_finish_count}}" "${{reserved_clock_force_count}}" "${{reserved_clock_failure_count}}" \
  "${{stage_marker_status}}" "${{all_stages_marker_status}}" \
  "${{returned_region_count}}" "${{expected_region_count}}" \
  "${{region_contract_status}}" \
  "${{sca_cfg_sha256}}" "${{sca_cfg_d_sha256}}" "${{runner_sha256}}" "${{runner_identity_sha256}}" \
  "${{testbench_sha256}}" "${{readback_contract_sha256}}" \
  "${{runtime_identity_sha256}}" "${{wall_timeout}}" \
  "${{runtime_log_total_size_limit_bytes}}" \
  "${{diagnostic_sink_count}}" "${{diagnostic_return_file_count}}" "${{diagnostic_return_total_bytes}}" \
  "${{diagnostic_file_size_limit_bytes}}" "${{diagnostic_total_size_limit_bytes}}" \
  > "${{return_root}}/run_metadata.json"

for name in "${{revision}}_console.log" "${{revision}}_exit_status.txt" \
  "${{revision}}_phase_progress.tsv" "${{revision}}_phase_timeout.tsv" \
  "${{revision}}_phase_watchdog_done.tsv"; do
  if [ -f "run/sim_results/${{name}}" ]; then
    cp -a "run/sim_results/${{name}}" "${{return_root}}/run_sim_results/"
  fi
done
mkdir -p "${{return_root}}/readback_regions" "${{return_root}}/config/metadata"
while IFS=$'\t' read -r region_path expected_line_count; do
  if [ -f "${{region_path}}" ] && [ ! -L "${{region_path}}" ]; then
    relative_region_path="${{region_path#${{install_root}}/install/}}"
    returned_region_path="${{return_root}}/readback_regions/${{relative_region_path}}"
    mkdir -p "$(dirname "${{returned_region_path}}")"
    cp -- "${{region_path}}" "${{returned_region_path}}"
  fi
done < "${{readback_contract}}"
cp -- "${{install_root}}/sca_cfg.json" "${{return_root}}/config/sca_cfg.json"
cp -- "${{install_root}}/sca_cfg_D.json" "${{return_root}}/config/sca_cfg_D.json"
cp -- "${{server_source_inventory}}" "${{return_root}}/config/server_source_inventory.tsv"
for approved_metadata_file in \
  "${{install_root}}/metadata/manifest.json" \
  "${{install_root}}/metadata/runner_contract.json" \
  "${{install_root}}/metadata/dump_contract.json" \
  "${{readback_contract}}" \
  "${{stage_contract}}" \
  "${{launch_files_contract}}" \
  "${{launch_identity}}" \
  "${{runtime_make_override}}" \
  "${{run_command_contract}}" \
  "${{runner_identity}}" \
  "${{install_root}}/metadata/runtime_identity.json"; do
  cp -- "${{approved_metadata_file}}" "${{return_root}}/config/metadata/"
done
printf '{{\n  "schema_version": "resnet50-server-return-archive-policy-0.4",\n  "server_run_id": "%s",\n  "policy": "bounded_exact_set_allowlist_v2",\n  "diagnostic_allowlist": "diagnostic_allowlist.tsv",\n  "diagnostic_file_size_limit_bytes": %s,\n  "diagnostic_total_size_limit_bytes": %s,\n  "diagnostic_truncation_policy": "head_bytes_v1",\n  "diagnostic_return_file_count": %s,\n  "diagnostic_return_total_bytes": %s,\n  "runtime_log_sink_policy": "audited_sinks_unknown_log_guard_v2",\n  "runtime_log_total_size_limit_bytes": %s,\n  "runtime_log_sink_count": %s,\n  "make_archive_policy": "runner_no_archive_target_v1",\n  "run_command_contract_sha256": "{run_command_contract_sha256}",\n  "return_file_contract": "return_file_contract.tsv",\n  "full_sim_results_copied": false,\n  "waveform_included": false,\n  "archive_timeout": "%s"\n}}\n' \
  "${{server_run_id}}" "${{diagnostic_file_size_limit_bytes}}" "${{diagnostic_total_size_limit_bytes}}" \
  "${{diagnostic_return_file_count}}" "${{diagnostic_return_total_bytes}}" \
  "${{runtime_log_total_size_limit_bytes}}" "${{diagnostic_sink_count}}" "${{archive_timeout}}" \
  > "${{return_root}}/return_archive_policy.json"

if find "${{return_root}}" -type l -print | grep -q .; then
  echo "ERROR: return root contains a symlink" >&2
  emit_runtime_failure 15 \
    "return_root_contains_symlink" \
    "${{return_root}} must contain only directories and regular files"
fi
if find "${{return_root}}" ! -type d ! -type f -print | grep -q .; then
  echo "ERROR: return root contains a non-regular object" >&2
  emit_runtime_failure 15 \
    "return_root_contains_nonregular_object" \
    "${{return_root}} must contain only directories and regular files"
fi
return_file_contract="${{return_root}}/return_file_contract.tsv"
: > "${{return_file_contract}}"
while IFS= read -r -d '' return_file; do
  relative_return_path="${{return_file#${{return_root}}/}}"
  if [[ "${{relative_return_path}}" == /* ]] || [[ "${{relative_return_path}}" == *$'\t'* ]] || \
     [[ "${{relative_return_path}}" == *$'\n'* ]] || [[ "${{relative_return_path}}" == *"/../"* ]]; then
    echo "ERROR: unsafe return path: ${{relative_return_path}}" >&2
    emit_runtime_failure 15 \
      "unsafe_return_path" \
      "${{relative_return_path}}"
  fi
  return_size=$(stat -c %s "${{return_file}}")
  return_sha256=$(sha256sum "${{return_file}}" | awk '{{print $1}}')
  printf '%s\t%s\t%s\n' "${{relative_return_path}}" "${{return_size}}" "${{return_sha256}}" \
    >> "${{return_file_contract}}"
done < <(find "${{return_root}}" -type f ! -path "${{return_file_contract}}" -print0)
LC_ALL=C sort -o "${{return_file_contract}}" "${{return_file_contract}}"

trap - ERR
set +e
(cd run && timeout --signal=TERM --kill-after=5m "${{archive_timeout}}" \
  zip -q -r "sim_results_${{revision}}_${{server_run_id}}.zip" \
    "${{revision}}_${{server_run_id}}_return")
archive_exit_status=$?
set -e
trap unexpected_runner_error ERR
if [ "${{archive_exit_status}}" -ne 0 ]; then
  echo "ERROR: return archive failed or timed out: status=${{archive_exit_status}} timeout=${{archive_timeout}}" >&2
  emit_runtime_failure 11 \
    "return_archive_failed" \
    "archive_status=${{archive_exit_status}} timeout=${{archive_timeout}}"
fi
echo "Return archive: ${{return_archive}}"
exit "${{effective_status}}"
""",
        )
        runner.chmod(0o755)
        runner_identity = metadata_root / runner_identity_name
        _write_text_lf(
            runner_identity,
            f"{_sha256(runner)}  {runner.name}\n",
        )
        runner_identity_sha256 = _sha256(runner_identity)
        runtime_identity = {
            "schema_version": "resnet50-ndp-server-runtime-identity-0.1",
            "freeze_id": freeze_id,
            "freeze_manifest_sha256": freeze_manifest_sha256,
            "package_manifest_sha256": package_manifest_sha256,
            "rtl_source_provenance": normalized_rtl_revision,
            "server_source_policy": launch_identity["server_source_policy"],
            "expected_runtime_stage_count": expected_runtime_stage_count,
            "expected_testbench_repeat_num": expected_testbench_repeat_num,
            "testbench_observer_mode": testbench_observer_mode,
            "bank_frame_logging_policy": bank_frame_logging_policy,
            "reserved_clock_validation": reserved_clock_validation_policy,
            "phase_stall_watchdog": launch_identity["phase_stall_watchdog"],
            "runtime_log_sink_policy": launch_identity["runtime_log_sink_policy"],
            "make_archive_policy": launch_identity["make_archive_policy"],
            "make_environment_policy": (
                "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
            ),
            "static_install_exact_set_policy": launch_identity[
                "static_install_exact_set_policy"
            ],
            "diagnostic_limits": launch_identity["diagnostic_limits"],
            "return_archive_policy": launch_identity["return_archive_policy"],
            "server_run_id_policy": launch_identity["server_run_id_policy"],
            "expected_runtime_transfer_count": len(runtime_transfers),
            "expected_region_count": len(sca_d),
            "immutable_testbench_sca_parser_abi": (
                "line_oriented_json_executionplan_nested_head_then_page_aligned_tail"
            ),
            "required_immutable_testbench_markers": (
                [
                    "INFO: slice start",
                    "INFO: slice completed after",
                    "Simulation completed successfully!",
                    "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
                ]
                if legacy_fixed_pair_observer
                else [
                    "RUNTIME_STAGE_COMPLETE stage=<ordered-index> mask=<expected-mask>",
                    "RUNTIME_ALL_STAGES_COMPLETE count=<expected-stage-count>",
                ]
            ),
            "immutable_testbench_capability_required": True,
            "immutable_testbench_prestart_probe": (
                "entrypoint_existence_only_content_unpinned"
            ),
            "immutable_testbench_capability_attestation": (
                immutable_testbench_capability_attestation
            ),
            "formal_acceptance_ready": True,
            "relocated_sca_cfg": {
                "path": (runtime_root / "sca_cfg.json").relative_to(output).as_posix(),
                "sha256": _sha256(runtime_root / "sca_cfg.json"),
            },
            "relocated_sca_cfg_D": {
                "path": (runtime_root / "sca_cfg_D.json").relative_to(output).as_posix(),
                "sha256": _sha256(runtime_root / "sca_cfg_D.json"),
            },
            "runner": {
                "path": runner.relative_to(output).as_posix(),
                "sha256": _sha256(runner),
            },
            "runner_identity": {
                "path": runner_identity.relative_to(output).as_posix(),
                "sha256": runner_identity_sha256,
            },
            "readback_region_contract": {
                "path": readback_contract.relative_to(output).as_posix(),
                "sha256": _sha256(readback_contract),
                "region_count": len(readback_region_records),
            },
            "runtime_stage_contract": {
                "path": stage_contract.relative_to(output).as_posix(),
                "sha256": stage_contract_sha256,
                "stage_count": len(completion_stage_records),
            },
            "launch_file_contract": {
                "path": launch_files_contract.relative_to(output).as_posix(),
                "sha256": launch_files_contract_sha256,
                "record_count": len(launch_file_records),
                "sca_payload_reference_count": len(payload_reference_records),
            },
            "launch_manifest": {
                "path": launch_files_contract.relative_to(output).as_posix(),
                "sha256": launch_files_contract_sha256,
                "record_count": len(launch_file_records),
            },
            "launch_identity": {
                "path": launch_identity_path.relative_to(output).as_posix(),
                "sha256": launch_identity_sha256,
            },
            "runtime_make_override": {
                "path": runtime_make_override.relative_to(output).as_posix(),
                "sha256": runtime_make_override_sha256,
                "target": no_archive_target,
            },
            "run_command_contract": {
                "path": run_command_contract.relative_to(output).as_posix(),
                "sha256": run_command_contract_sha256,
                "argument_count": len(run_argv),
            },
            "testbench": {
                "path": "tb_NDP_Top_new_phy.sv",
                "source": "existing_server_file_not_in_overlay",
                "identity_policy": "record_actual_hash_without_prestart_comparison",
            },
            "package_preflight": launch_identity["package_preflight"],
        }
        _write_text_lf(
            metadata_root / "runtime_identity.json",
            json.dumps(runtime_identity, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
        diagnostic_files = [
            runner.relative_to(output).as_posix(),
            metadata_root.relative_to(output).as_posix() + "/",
        ]
        if reserved_clock_tcl is not None:
            diagnostic_files.append(reserved_clock_tcl.relative_to(output).as_posix())

    if observation == OBSERVATION_FULL_FSDB:
        run_instructions = f"""make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_FSDB=1 \\
  PLUSARGS='+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json'

The existing Makefile adds -debug_access+all -kdb and writes the complete
hierarchy to run/sim_results/wave.fsdb when DUMP_FSDB=1. Inspect the paths in
{signal_path_name}. Return wave.fsdb, sim.log, dump.tcl and post-run data."""
        observation_description = "existing_makefile_full_hierarchy_fsdb"
        waveform = "run/sim_results/wave.fsdb"
    elif observation == OBSERVATION_TARGETED_VPD:
        run_instructions = f"""bash {runner_name}

This keeps DUMP_FSDB=0, compiles with debug visibility, records only the
signals in {signal_path_name}, and stops deterministically at
{diagnostic_run_time}. Return run/sim_results_{revision_slug}.zip; if zip is
unavailable, return run/{revision_slug}_return/."""
        observation_description = "ucli_slice0_targeted_vpd_no_rtl_changes"
        waveform = f"run/sim_results/{revision_slug}_diag.vpd"
    else:
        if legacy_fixed_pair_observer:
            run_instructions = f"""SERVER_RUN_ID=run1 bash {runner_name}

This keeps DUMP_FSDB=0, deletes run/csrc before compilation, and uses the
packaged UCLI script only to generate the missing 400 MHz reserved AXI input
clock. The UCLI proves a low/high toggle before emitting its success marker;
the compile command enables the immutable TB's existing
`BANK_FRAME_LOG_SLICE_START_ONLY` guard. Before compilation, the runner requires the
three active server entrypoints to be readable and records only their logical
path, resolved physical path, size and SHA-256. It does not recursively parse
server HDL/filelists or pin physical paths to the server root. If the
active filelist uses `${{DIR_HOME}}/Hardware/IP/bus/nic_cgra_0310`, `DIR_HOME`
must identify the server vendor-source root; do not invent a replacement path or
edit the filelist. The runner creates the approved fixed set of exactly 1037 temporary
/dev/null sinks inside the fresh sim_results tree; the one approved gexec log is
the only regular runtime log allowed, unknown log files fail closed, and live
regular-log storage is capped at 1 GiB. It is returned only through a 1 MiB
bounded diagnostic policy. The content-addressed
additional Makefile defines a separate no-archive simulation target that reuses
the server Makefile's SIMV/SIM_OPTS and therefore never invokes its full-result
archive target. Neither action modifies RTL/testbench or the server Makefile. The
{expected_runtime_stage_count} real runtime stages are barrier ordered for the immutable fixed slice0-start/
slice1-finish observer, whose Repeat_Num is {expected_testbench_repeat_num}.
The final shard's non-slice1 members complete behind their own barrier before
the finish-slice-only final stage, so the final observed slice1 event fences
the complete output mask. The fail-closed
runner also requires the exact preload PASS count, one natural simulation
completion marker, and the exact readback region set. Phase-specific progress
watchdogs stop stalled preload/first-start/observer/readback work. Readback polling
checks paths, types and sizes, performs a full content check only when each file
first reaches its exact frozen size, and then fully revalidates all files after
process exit. The return ZIP
contains the bounded diagnostic allowlist and complete readback set, and an
exact-set/size/SHA contract covers every returned file. It returns
run/sim_results_{revision_slug}_run1.zip.

After run1 completes, return `run/sim_results_{revision_slug}_run1.zip` and wait
for local return validation. Only after that validation passes, preserve the
run1 archive and execute the same immutable package again:

SERVER_RUN_ID=run2 bash {runner_name}

Return both run/sim_results_{revision_slug}_run1.zip and
run/sim_results_{revision_slug}_run2.zip. The two run IDs use distinct return
directories and archives."""
            observation_description = (
                "legacy_fixed_pair_completion_ucli_reserved_clock_no_waveform"
            )
        else:
            run_instructions = f"""SERVER_RUN_ID=run1 bash {runner_name}

This keeps DUMP_FSDB=0, adds no UCLI/Tcl stop and waits for the natural end of
all {expected_runtime_stage_count} runtime stages. The fail-closed runner requires
the existing server testbench to emit the complete unique stage-marker set and the
exact per-payload PASS count; missing evidence is a nonzero result. It requires zip
and returns run/sim_results_{revision_slug}_run1.zip. Repeat with
SERVER_RUN_ID=run2 and return both archives. Before launch, the runner checks the
three active server entrypoints and records source provenance without pinning
server source contents or physical source path prefixes. The actual source
inventory and testbench SHA-256 are recorded in the returned metadata."""
            observation_description = "natural_completion_no_waveform"
        waveform = None

    harness_description = (
        "No .v or .sv file is included or changed. The server Makefile, testbench, "
        "and active RTL top filelist only need to be readable logical entrypoints; "
        "symlinked or root-external physical targets are allowed. Their resolved "
        "paths, sizes and SHA-256 values are returned as nonblocking provenance; "
        "DIR_HOME state/value identity and the resolved vendor path are recorded "
        "with them. "
        "Server HDL/filelist semantics are left to the existing Make/VCS flow, whose "
        "real compile errors are preserved in the failure archive. "
        f"The {revision_slug} runtime is added only under "
        f"install/cfg_pkg/{install_name}/."
    )

    readme = f"""NDP node-0004 {revision_slug} runtime-only server overlay

This directory is NOT a complete NDP_copy01 replacement.
Before extraction, verify the delivered archive from its containing directory:

sha256sum -c {output.with_suffix('.zip').name}.sha256

Git is neither required nor used on the server. Do not run git commands or
require a .git directory for integrity checks; the runner uses packaged
SHA-256 contracts and records the three active entrypoint hashes plus DIR_HOME
and vendor-path resolution as nonblocking provenance.
After the minimal run-ID check, the runner authenticates its own packaged SHA-256
before it creates, removes or overwrites any result evidence. It then installs
its failure handlers, validates the complete required-command set, and only then
cleans this run ID's stale result paths. The merged static install must be the
packaged exact set; inherited MAKEFLAGS, MAKEFILES, GNUMAKEFLAGS, MFLAGS and
MAKELEVEL are cleared immediately before the content-addressed Make launch.

Merge the contained NDP_copy01/ into the existing server NDP_copy01/.
{harness_description}

From the existing server NDP_copy01 directory, run:

{run_instructions}

Do not delete or replace the complete server NDP_copy01 directory.
"""
    readme_name = f"README_SERVER_{revision_label}.txt"
    _write_text_lf(output / readme_name, readme)

    overlay_text_paths = sorted(
        [*_assert_server_text_lf(output), "OVERLAY_MANIFEST.json"]
    )
    payload_files = sorted(path for path in output.rglob("*") if path.is_file())
    prohibited_overlay_sources = [
        path.relative_to(output).as_posix()
        for path in payload_files
        if path.suffix.lower() in {".v", ".sv"}
    ]
    if prohibited_overlay_sources:
        raise AssertionError(
            "generated server overlay contains prohibited .v/.sv files: "
            f"{prohibited_overlay_sources[:5]}"
        )
    try:
        source_package_path = package.relative_to(ROOT).as_posix()
    except ValueError:
        source_package_path = str(package)
    manifest = {
        "schema_version": "0.1",
        "status": (
            "runtime_only_ndp_server_overlay_ready_formal_acceptance_ready"
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else "runtime_only_ndp_server_overlay_ready"
        ),
        "overlay_semantics": "merge_only_do_not_replace_server_ndp_root",
        "server_merge_root": "NDP_copy01/",
        "runtime_sca_cfg": (
            f"install/cfg_pkg/{install_name}/sca_cfg.json"
        ),
        "rtl_files_included": 0,
        "design_rtl_files_included": 0,
        "versioned_testbench_included": False,
        "versioned_testbench": None,
        "observation_mode": observation_description,
        "diagnostic_run_time": (
            diagnostic_run_time
            if observation == OBSERVATION_TARGETED_VPD
            else None
        ),
        "waveform": waveform,
        "signal_path_list": signal_path_name,
        "targeted_signal_count": (
            len(signal_suffixes)
            if observation == OBSERVATION_TARGETED_VPD
            else None
        ),
        "targeted_signal_evidence": (
            "all_paths_accepted_by_server_v7_ucli_before_removed_raw_data_bus"
            if observation == OBSERVATION_TARGETED_VPD
            else None
        ),
        "server_text_encoding": "utf-8_lf",
        "text_file_contract": {
            "schema_version": "resnet50-overlay-text-abi-0.1",
            "encoding": "utf-8_or_ascii",
            "line_ending": "lf",
            "carriage_return_byte_allowed": False,
            "paths": overlay_text_paths,
        },
        "ucli_stdin_mode": (
            "noninteractive_dev_null"
            if observation == OBSERVATION_TARGETED_VPD
            or (
                observation == OBSERVATION_COMPLETION_NO_WAVE
                and legacy_fixed_pair_observer
            )
            else None
        ),
        "natural_completion_required": observation == OBSERVATION_COMPLETION_NO_WAVE,
        "immutable_testbench_capability_required": (
            observation == OBSERVATION_COMPLETION_NO_WAVE
        ),
        "immutable_testbench_capability_attestation": (
            immutable_testbench_capability_attestation
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "formal_acceptance_ready": (
            True if observation == OBSERVATION_COMPLETION_NO_WAVE else None
        ),
        "required_immutable_testbench_markers": (
            (
                [
                    "INFO: slice start",
                    "INFO: slice completed after",
                    "Simulation completed successfully!",
                    "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
                ]
                if legacy_fixed_pair_observer
                else [
                    "RUNTIME_STAGE_COMPLETE stage=<ordered-index> mask=<expected-mask>",
                    "RUNTIME_ALL_STAGES_COMPLETE count=<expected-stage-count>",
                ]
            )
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "expected_runtime_stage_count": (
            expected_runtime_stage_count
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "expected_testbench_repeat_num": (
            expected_testbench_repeat_num
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "testbench_observer_mode": (
            testbench_observer_mode
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "bank_frame_logging_policy": (
            bank_frame_logging_policy
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "reserved_clock_validation": (
            reserved_clock_validation_policy
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "phase_stall_watchdog": (
            launch_identity["phase_stall_watchdog"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "runtime_log_sink_policy": (
            launch_identity["runtime_log_sink_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "make_archive_policy": (
            launch_identity["make_archive_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "make_environment_policy": (
            runtime_identity["make_environment_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "static_install_exact_set_policy": (
            runtime_identity["static_install_exact_set_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "run_command_contract": (
            runtime_identity["run_command_contract"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "return_archive_policy": (
            launch_identity["return_archive_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "server_run_id_policy": (
            launch_identity["server_run_id_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "rtl_source_provenance": (
            normalized_rtl_revision
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "server_source_policy": (
            launch_identity["server_source_policy"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "testbench_source_provenance_sha256": (
            normalized_testbench_sha256
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "readme": readme_name,
        "diagnostic_files": diagnostic_files,
        "source_package": {
            "path": source_package_path,
            "manifest_sha256": _sha256(package / "manifest.json"),
        },
        "freeze_id": freeze_id,
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "package_manifest_sha256": package_manifest_sha256,
        "package_preflight": launch_identity["package_preflight"],
        "runner": (
            {
                "path": runner.relative_to(output).as_posix(),
                "sha256": _sha256(runner),
            }
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "runner_self_identity": (
            runtime_identity["runner_identity"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "expected_return_archive": (
            f"run/sim_results_{revision_slug}_<SERVER_RUN_ID>.zip"
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "required_formal_return_archives": (
            [
                f"run/sim_results_{revision_slug}_run1.zip",
                f"run/sim_results_{revision_slug}_run2.zip",
            ]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "runtime_stage_contract": (
            runtime_identity["runtime_stage_contract"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "readback_region_contract": (
            runtime_identity["readback_region_contract"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "launch_file_contract": (
            runtime_identity["launch_file_contract"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "launch_identity": (
            runtime_identity["launch_identity"]
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "runtime_identity": (
            {
                "path": (
                    metadata_root / "runtime_identity.json"
                ).relative_to(output).as_posix(),
                "sha256": _sha256(metadata_root / "runtime_identity.json"),
            }
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "testbench_observer": (
            completion_gate.get("testbench_observer")
            if observation == OBSERVATION_COMPLETION_NO_WAVE
            else None
        ),
        "excluded_as_not_required_on_server": [
            "Bank_data/",
            "source/",
            "golden and local comparison reports",
            "local generators and tests",
            "all .v and .sv files, including the testbench",
        ],
        "sca_reference_count": len(runtime_transfers),
        "sca_payload_reference_count": len(payload_reference_records),
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in payload_files
        ],
    }
    manifest_path = output / "OVERLAY_MANIFEST.json"
    _write_text_lf(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    audited_directory_text_paths = _assert_server_text_lf(output)
    if audited_directory_text_paths != overlay_text_paths:
        raise ValueError(
            "overlay LF text contract differs after manifest creation: "
            f"missing={sorted(set(audited_directory_text_paths) - set(overlay_text_paths))[:5]}, "
            f"extra={sorted(set(overlay_text_paths) - set(audited_directory_text_paths))[:5]}"
        )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            relative = path.relative_to(output).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    zip_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    zip_lf_text_file_count = _audit_overlay_zip(
        zip_path,
        expected_paths=zip_paths,
        text_paths=set(overlay_text_paths),
    )
    manifest["overlay_manifest_sha256"] = _sha256(manifest_path)
    try:
        manifest["zip_path"] = zip_path.relative_to(ROOT).as_posix()
    except ValueError:
        manifest["zip_path"] = str(zip_path)
    manifest["zip_size_bytes"] = zip_path.stat().st_size
    manifest["zip_sha256"] = _sha256(zip_path)
    manifest["directory_lf_text_file_count"] = len(overlay_text_paths)
    manifest["zip_lf_text_file_count"] = zip_lf_text_file_count
    _write_text_lf(
        zip_sha256_path,
        f"{manifest['zip_sha256']}  {zip_path.name}\n",
    )
    manifest["zip_sha256_path"] = (
        zip_sha256_path.relative_to(ROOT).as_posix()
        if ROOT in zip_sha256_path.parents
        else str(zip_sha256_path)
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a minimal merge-only NDP server overlay."
    )
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install-name", required=True)
    parser.add_argument(
        "--observation",
        choices=(
            OBSERVATION_FULL_FSDB,
            OBSERVATION_TARGETED_VPD,
            OBSERVATION_COMPLETION_NO_WAVE,
        ),
        required=True,
    )
    parser.add_argument("--diagnostic-run-time", default="12ms")
    parser.add_argument(
        "--testbench",
        type=Path,
        help=(
            "Prohibited compatibility option: server overlays must not include or "
            "replace tb_NDP_Top_new_phy.sv."
        ),
    )
    parser.add_argument(
        "--expected-rtl-revision",
        help=(
            "Optional 40-hex RTL source provenance label for records only; server "
            "sources are not compared to it."
        ),
    )
    parser.add_argument(
        "--expected-server-testbench-sha256",
        help=(
            "Optional testbench SHA-256 provenance label for records only; the "
            "server testbench is not compared to it before launch."
        ),
    )
    parser.add_argument(
        "--selfcheck-round1-report",
        type=Path,
        required=True,
        help=(
            "New output path for the formal package/runner/full-install behavior "
            "selfcheck report. The report is written after the final ZIP exists."
        ),
    )
    args = parser.parse_args()
    if args.selfcheck_round1_report.exists():
        parser.error(
            "refusing to replace an existing round1 report: "
            f"{args.selfcheck_round1_report}"
        )
    report = build_overlay(
        args.package,
        args.output,
        args.install_name,
        observation=args.observation,
        diagnostic_run_time=args.diagnostic_run_time,
        testbench=args.testbench,
        expected_rtl_revision=args.expected_rtl_revision,
        expected_server_testbench_sha256=args.expected_server_testbench_sha256,
    )
    round1 = run_overlay_round1_selfcheck(
        args.package,
        args.output,
        args.selfcheck_round1_report,
    )
    report["selfcheck_round1"] = {
        "path": str(args.selfcheck_round1_report.resolve()),
        "status": round1["status"],
        "zip_sha256": round1["zip_sha256"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
