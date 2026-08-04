#!/usr/bin/env python3
"""Independent final-ZIP and real-runner checks for native MaxPool v5."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOT_NAME = "r5_n2_maxpool_ndpsim_native_v5"
SOURCE_SHA = "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
SIM_STUB_EXIT = 74


class ValidationError(RuntimeError):
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


def file_records(root: Path, *, exclude_manifest: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def msys_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/{value[0].lower()}/{value[3:]}"
    return value


def extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or ((info.external_attr >> 16) & 0o170000) == 0o120000
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {ROOT_NAME}:
            raise ValidationError(f"ZIP root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / ROOT_NAME


def validate_static(package: Path, zip_path: Path, sidecar: Path) -> dict[str, Any]:
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = file_records(package, exclude_manifest=True)
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    source = (
        package
        / "workload/native/source_config/"
        "maxpool_config_16_112_112_stride2_padding1.json"
    )
    materialized = (
        package
        / "workload/native/jsons/"
        "op0_maxpool_config_16_112_112_stride2_padding1.json"
    )
    forbidden_members = [
        relative
        for relative in actual
        if any(
            token in relative.lower()
            for token in ("observer", "canonical_diag", "tb_probe")
        )
    ]
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    forbidden_runner = [
        token
        for token in (
            "+RETURN_OBSERVER",
            "NATIVE_RETURN_OBSERVER_ENABLE",
            "CANONICAL_DIAG_DECISION",
            "r5_n2_maxpool_native_reuse_v4",
        )
        if token in runner
    ]
    source_json = json.loads(source.read_text(encoding="utf-8"))
    materialized_json = json.loads(materialized.read_text(encoding="utf-8"))
    stream0_before = source_json["stream_engine"]["stream0"]["base_addr"]
    stream1_before = source_json["stream_engine"]["stream1"]["base_addr"]
    source_json["stream_engine"]["stream0"]["base_addr"] = materialized_json[
        "stream_engine"
    ]["stream0"]["base_addr"]
    source_json["stream_engine"]["stream1"]["base_addr"] = materialized_json[
        "stream_engine"
    ]["stream1"]["base_addr"]
    checks = {
        "sidecar_exact": sidecar_tokens
        == [sha256(zip_path), zip_path.name],
        "identity_exact": manifest.get("install_name") == ROOT_NAME,
        "manifest_exact_set": actual == manifest.get("files"),
        "source_json_byte_identity": sha256(source) == SOURCE_SHA,
        "materialized_only_two_base_leaves": source_json == materialized_json
        and stream0_before == 1024
        and stream1_before == 201728,
        "native_root_files_present": all(
            (package / f"workload/native/{relative}").is_file()
            for relative in (
                "instructions_explained.txt",
                "node0002_maxpool_wave0_graph_withbaseaddr.json",
                "sca_cfg.json",
                "sca_cfg_D.json",
                "install/execplan.txt",
                "jsons/op0_maxpool_config_16_112_112_stride2_padding1.json",
            )
        ),
        "native_directory_style": all(
            (package / f"workload/native/{name}").is_dir()
            for name in ("jsons", "config", "install")
        ),
        "runtime_D_absent": not any(
            (package / "workload/native").glob(
                "install/op0/slice*/matrix_D_linearized_128bit*"
            )
        ),
        "golden_D_separated": len(
            list(
                (package / "validation/golden/op0").glob(
                    "slice*/matrix_D_linearized_128bit.txt"
                )
            )
        )
        == 28,
        "no_generic_observer_members": not forbidden_members,
        "no_generic_observer_runner": not forbidden_runner,
        "native_single_stage_contract": manifest.get("native_structure", {}).get(
            "execplan_128bit_lines"
        )
        == 29
        and manifest.get("native_structure", {}).get("formal_D_count") == 28,
    }
    if not all(checks.values()):
        raise ValidationError(
            "static final-ZIP checks failed: "
            + ", ".join(name for name, passed in checks.items() if not passed)
        )
    return {
        "valid": True,
        "checks": checks,
        "forbidden_members": forbidden_members,
        "forbidden_runner_tokens": forbidden_runner,
    }


def write_stubs(stub_bin: Path, python: Path) -> None:
    stub_bin.mkdir(parents=True)
    python_stub = stub_bin / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{msys_path(python)}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    make_stub = stub_bin / "make"
    make_stub.write_text(
        "#!/usr/bin/env bash\n"
        ': "${STUB_TRACE:?STUB_TRACE is required}"\n'
        'printf "make:%s\\n" "$*" >> "$STUB_TRACE"\n'
        'run_dir=""\n'
        'for arg in "$@"; do case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac; done\n'
        '[ -n "$run_dir" ] || exit 88\n'
        'mkdir -p "$run_dir/sim_results"\n'
        'cat > "$run_dir/sim_results/simv" <<\'SIMV\'\n'
        "#!/usr/bin/env bash\n"
        ': "${STUB_TRACE:?STUB_TRACE is required}"\n'
        'printf "simv:%s\\n" "$*" >> "$STUB_TRACE"\n'
        'log=""\n'
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-l" ]; then log="$2"; shift 2; else shift; fi\n'
        "done\n"
        'if [ -n "$log" ]; then\n'
        '  printf "Using SCA cfg\\nUsing SCA cfg D\\nSIM_STUB_EXECUTED\\n" > "$log"\n'
        "fi\n"
        f"exit {SIM_STUB_EXIT}\n"
        "SIMV\n"
        'chmod +x "$run_dir/sim_results/simv"\n'
        'printf "compile stub\\n" > "$run_dir/sim_results/compile.log"\n'
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    timeout_stub = stub_bin / "timeout"
    timeout_stub.write_text(
        "#!/usr/bin/env bash\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        '    --foreground) shift;;\n'
        '    --signal=*|--kill-after=*) shift;;\n'
        '    [0-9]*[smhd]) shift; break;;\n'
        '    *) break;;\n'
        "  esac\n"
        "done\n"
        'if [ "${STUB_MODE:-exit}" = "term" ] && [[ "$1" == */simv ]]; then\n'
        '  kill -TERM "$PPID"\n'
        "  exit 143\n"
        "fi\n"
        'exec "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    for path in (python_stub, make_stub, timeout_stub):
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_runner(
    package: Path,
    server_root: Path,
    stub_bin: Path,
    bash: Path,
    trace: Path,
    *,
    mode: str,
) -> subprocess.CompletedProcess[str]:
    server_root.mkdir()
    environment = dict(os.environ)
    environment["STUB_TRACE"] = msys_path(trace)
    environment["STUB_MODE"] = mode
    return subprocess.run(
        [
            str(bash),
            "-c",
            (
                'export PATH="$1:/usr/bin:/mingw64/bin"; '
                'exec /usr/bin/bash -x "$2" "$3"'
            ),
            "maxpool-native-runner-control",
            msys_path(stub_bin),
            msys_path(package / "PREPARE_AND_RUN.sh"),
            msys_path(server_root),
        ],
        cwd=package,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def runner_case(
    source_package: Path,
    root: Path,
    bash: Path,
    python: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    package = root / "package"
    shutil.copytree(source_package, package)
    before = file_records(package)
    stub_bin = root / "stubs"
    write_stubs(stub_bin, python)
    trace = root / "stub_trace.log"
    server = root / "server"
    process = run_runner(
        package, server, stub_bin, bash, trace, mode=mode
    )
    after = file_records(package)
    evidence = server / f"evidence_{ROOT_NAME}"
    return_zip = server / f"{ROOT_NAME}_return.zip"
    return_sidecar = server / f"{ROOT_NAME}_return.zip.sha256"
    trace_text = trace.read_text(encoding="utf-8") if trace.is_file() else ""
    signal = (
        (evidence / "termination_signal.txt").read_text(
            encoding="ascii"
        ).strip()
        if (evidence / "termination_signal.txt").is_file()
        else ""
    )
    result_gate = load_json(evidence / "SERVER_RESULT_GATE.json")
    finalizer = load_json(evidence / "finalizer_status.json")
    checks = {
        "compile_stub_once": trace_text.count("make:") == 1,
        "sim_stub_once": trace_text.count("simv:") == 1
        if mode == "exit"
        else trace_text.count("simv:") == 0,
        "package_tree_immutable": before == after,
        "actual_compile_argv": (
            evidence / "actual_compile_argv.txt"
        ).is_file(),
        "actual_simulator_argv": (
            evidence / "actual_simulator_argv.txt"
        ).is_file(),
        "finalizer_entered": bool(
            finalizer and finalizer.get("finalizer_entered") is True
        ),
        "result_gate_fail_closed": bool(
            result_gate and result_gate.get("result_gate") is False
        ),
        "return_zip_and_sidecar": return_zip.is_file()
        and return_sidecar.is_file(),
        "return_zip_crc": return_zip.is_file()
        and zipfile.ZipFile(return_zip).testzip() is None,
        "expected_exit": process.returncode
        == (SIM_STUB_EXIT if mode == "exit" else 143),
        "signal_receipt": signal == ("" if mode == "exit" else "TERM"),
    }
    if not all(checks.values()):
        raise ValidationError(
            f"{mode} runner case failed: "
            + ", ".join(name for name, passed in checks.items() if not passed)
            + f"; exit={process.returncode}; stderr={process.stderr[-8000:]}"
        )
    return {
        "valid": True,
        "mode": mode,
        "checks": checks,
        "runner_exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(process.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr.encode()).hexdigest(),
        "return_zip_sha256": sha256(return_zip),
        "termination_signal": signal or None,
    }


def identity_negative(
    source_package: Path,
    root: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    package = root / "package"
    shutil.copytree(source_package, package)
    source = (
        package
        / "workload/native/source_config/"
        "maxpool_config_16_112_112_stride2_padding1.json"
    )
    source.write_bytes(source.read_bytes() + b"\n")
    stub_bin = root / "stubs"
    write_stubs(stub_bin, python)
    trace = root / "stub_trace.log"
    process = run_runner(
        package, root / "server", stub_bin, bash, trace, mode="exit"
    )
    trace_text = trace.read_text(encoding="utf-8") if trace.is_file() else ""
    checks = {
        "failed_before_compile": "make:" not in trace_text,
        "failed_before_sim": "simv:" not in trace_text,
        "runner_nonzero": process.returncode != 0,
    }
    if not all(checks.values()):
        raise ValidationError("wrong source identity did not fail closed")
    return {
        "valid": True,
        "failed_closed": True,
        "mutation": "append LF to authoritative source JSON copy",
        "runner_exit_code": process.returncode,
        "checks": checks,
    }


def native_structure_negative(source_package: Path, root: Path) -> dict[str, Any]:
    package = root / "package"
    shutil.copytree(source_package, package)
    target = (
        package
        / "workload/native/jsons/"
        "op0_maxpool_config_16_112_112_stride2_padding1.json"
    )
    target.unlink()
    runtime = (
        package
        / "package_tools/maxpool_node0002_ndpsim_native_runtime_v5.py"
    )
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            str(runtime),
            "preflight-package",
            "--package-root",
            str(package),
            "--output",
            str(root / "preflight.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode == 0:
        raise ValidationError("missing native materialized JSON did not fail")
    return {
        "valid": True,
        "failed_closed": True,
        "mutation": "delete native materialized operator JSON",
        "exit_code": process.returncode,
    }


def validate(
    zip_path: Path,
    sidecar: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".maxpool-native-v5-",
        dir=ROOT,
        ignore_cleanup_errors=True,
    ) as temporary:
        root = Path(temporary)
        package = extract(zip_path, root / "extract")
        static = validate_static(package, zip_path, sidecar)
        exit_control = runner_case(
            package, root / "exit_control", bash, python, mode="exit"
        )
        signal_control = runner_case(
            package, root / "signal_control", bash, python, mode="term"
        )
        identity = identity_negative(
            package, root / "identity_negative", bash, python
        )
        native = native_structure_negative(
            package, root / "native_negative"
        )
    return {
        "schema": "maxpool-node0002-ndpsim-native-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": True,
        "errors": [],
        "zip": {
            "path": zip_path.relative_to(ROOT).as_posix(),
            "bytes": zip_path.stat().st_size,
            "sha256": sha256(zip_path),
        },
        "sidecar": {
            "path": sidecar.relative_to(ROOT).as_posix(),
            "sha256": sha256(sidecar),
        },
        "static": static,
        "runner_exit_finalizer_positive": exit_control,
        "runner_signal_finalizer_positive": signal_control,
        "negative_controls": {
            "wrong_source_identity": identity,
            "missing_native_structure": native,
        },
        "all_negative_controls_fail_closed": True,
        "server_source_files_inspected": False,
        "functional_rtl_modified": False,
        "generic_observer_schema_present": False,
        "canonical_diagnostic_present": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument(
        "--python", type=Path, default=Path(sys.executable)
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(
            args.zip.resolve(),
            args.sidecar.resolve(),
            args.bash.resolve(),
            args.python.resolve(),
        )
        write_json(args.output.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MaxPool native v5 validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
