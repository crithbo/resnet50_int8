from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True


EXPECTED_ZIP_SHA256 = (
    "9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27"
)
EXPECTED_EXIT_STUB = 74
FEATURES = {
    "RETURN_OBS_DEEP": ("+RETURN_OBS_DEEP", "+RETURN_OBS_DEEP_LIMIT=256"),
    "RETURN_OBS_ABPE": (
        "+RETURN_OBS_ABPE",
        "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
    ),
    "RETURN_HANG_DIAG": (
        "+RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
    ),
    "RETURN_OBS_FINAL_RELEASE": (
        "+RETURN_OBS_FINAL_RELEASE",
        "+RETURN_OBS_FINAL_RELEASE_LIMIT=256",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def msys(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/{value[0].lower()}/{value[3:]}"
    return value


def extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
            ):
                raise ValueError(f"unsafe ZIP member: {info.filename}")
            roots.add(pure.parts[0])
        if len(roots) != 1:
            raise ValueError(f"ZIP root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / next(iter(roots))


def records(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def write_stubs(stub_root: Path, python: Path) -> None:
    stub_root.mkdir()
    python_stub = stub_root / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{msys(python)}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    make_stub = stub_root / "make"
    make_stub.write_text(
        "#!/usr/bin/env bash\n"
        ': "${COMPILE_STUB_LOG:?}"\n'
        '{ printf "cwd=%s\\n" "$PWD"; printf "argv="; '
        'printf "%q " "$@"; printf "\\n"; } >> "$COMPILE_STUB_LOG"\n'
        'run_dir=""\n'
        'for arg in "$@"; do case "$arg" in RUN_DIR=*) '
        'run_dir="${arg#RUN_DIR=}";; esac; done\n'
        '[ -n "$run_dir" ] || exit 91\n'
        'mkdir -p "$run_dir/sim_results"\n'
        'cat > "$run_dir/sim_results/simv" <<\'SIMSTUB\'\n'
        '#!/usr/bin/env bash\n'
        'set -u\n'
        ': "${SIM_STUB_MODE:?}"\n'
        ': "${SIM_STUB_STARTED:?}"\n'
        'observer=""\n'
        'sim_log=""\n'
        'previous=""\n'
        'for arg in "$@"; do '
        'if [ "$previous" = "-l" ]; then sim_log="$arg"; fi; '
        'case "$arg" in +RETURN_OBS_FILE=*) '
        'observer="${arg#+RETURN_OBS_FILE=}";; esac; previous="$arg"; done\n'
        '[ -n "$observer" ] || exit 92\n'
        '[ -n "$sim_log" ] || exit 93\n'
        'mkdir -p "$(dirname "$observer")"\n'
        'cat > "$observer" <<\'OBSLOG\'\n'
        '# safe node0004 final-release diagnostic stub\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DEEP enabled=1 limit_name=RETURN_OBS_DEEP_LIMIT limit=256\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_ABPE enabled=1 budget_name=RETURN_HANG_DIAG_MAX_CYCLES budget=8388608\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_HANG_DIAG enabled=1 sample_cycles=262144 stall_windows=4 max_cycles=8388608\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_FINAL_RELEASE enabled=1 limit_name=RETURN_OBS_FINAL_RELEASE_LIMIT limit=256\n'
        '1 | FINAL_RELEASE_EDGE_V1 | n=1 input_matched=0x1 alu_last_matched=0x1 ready=0x1 pe_valid=0x1\n'
        '2 | PROGRESS_WINDOW | stage=c0 start_comp=1 completed_stages=0 sample=1 qualified_progress=1 delta=1 no_progress_windows=0 consecutive_progress_windows=1 req0=1 req1=0 req3=0 rdata0=0 rdata1=0 rdata3=0 d_req=0 d_wdata=0\n'
        '3 | FINAL_RELEASE_BOUNDARY_V1 | event=SAFE_STUB input_matched_edges=1 alu_terminal_writes=1 ready_set_edges=1 pe_valid_edges=1\n'
        'OBSLOG\n'
        'printf "[0] safe simulator stub\\n" > "$sim_log"\n'
        'printf "STARTED\\n" > "$SIM_STUB_STARTED"\n'
        'if [ "$SIM_STUB_MODE" = "exit" ]; then exit 74; fi\n'
        "trap 'exit 143' TERM INT HUP\n"
        'while :; do sleep 1; done\n'
        'SIMSTUB\n'
        'chmod +x "$run_dir/sim_results/simv"\n'
        'printf "safe compile stub\\n" > "$run_dir/sim_results/compile.log"\n'
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    for path in (python_stub, make_stub):
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def env_for(
    stub: Path,
    compile_log: Path,
    mode: str,
    started: Path,
) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": (
            f"{msys(stub)}:/usr/bin:/mingw64/bin:"
            "/c/Windows/System32"
        ),
        "COMPILE_STUB_LOG": msys(compile_log),
        "SIM_STUB_MODE": mode,
        "SIM_STUB_STARTED": msys(started),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def run_exit(
    package: Path,
    server: Path,
    stub: Path,
    compile_log: Path,
    started: Path,
    bash: Path,
) -> subprocess.CompletedProcess[str]:
    server.mkdir()
    return subprocess.run(
        [
            str(bash),
            "-c",
            'exec /usr/bin/bash -x "$1" "$2"',
            "v23-exit-control",
            msys(package / "PREPARE_AND_RUN.sh"),
            msys(server),
        ],
        cwd=package,
        env=env_for(stub, compile_log, "exit", started),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )


def run_term(
    package: Path,
    server: Path,
    stub: Path,
    compile_log: Path,
    started: Path,
    bash: Path,
    status: Path,
) -> subprocess.CompletedProcess[str]:
    server.mkdir()
    harness = (
        'bash "$1" "$2" >"$3" 2>"$4" &\n'
        "pid=$!\n"
        "n=0\n"
        'while [ ! -f "$5" ] && [ "$n" -lt 400 ]; do '
        "sleep 0.05; n=$((n+1)); done\n"
        'if [ ! -f "$5" ]; then kill -TERM "$pid" 2>/dev/null; '
        'wait "$pid" 2>/dev/null; printf "124\\n" >"$6"; exit 0; fi\n'
        'kill -TERM "$pid"\n'
        'wait "$pid"\n'
        'printf "%s\\n" "$?" >"$6"\n'
    )
    stdout = status.with_suffix(".stdout")
    stderr = status.with_suffix(".stderr")
    return subprocess.run(
        [
            str(bash),
            "-c",
            harness,
            "v23-term-control",
            msys(package / "PREPARE_AND_RUN.sh"),
            msys(server),
            msys(stdout),
            msys(stderr),
            msys(started),
            msys(status),
        ],
        cwd=package,
        env=env_for(stub, compile_log, "loop", started),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def returned_members(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    with zipfile.ZipFile(path) as archive:
        return {
            PurePosixPath(*PurePosixPath(info.filename).parts[1:]).as_posix()
            for info in archive.infolist()
            if not info.is_dir()
        }


def canonical_negatives(package: Path) -> dict[str, bool]:
    runtime_path = (
        package / "package_tools/node0004_hang_localization_runtime.py"
    )
    spec = importlib.util.spec_from_file_location("v23_runtime_check", runtime_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import package runtime")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(runtime_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    valid = (
        "1 | CANONICAL_DIAG_DECISION_V1 | schema=node0004_hang_diag "
        "version=1 decision=LONG_RUNNING_HANG_AT_X reason=STALL_WINDOW_EXCEEDED "
        "boundary=X window_first=1 window_last=5 window_cycles=262144 "
        "qualified_progress=1 qualified_delta=0 req0=1 req1=0 req3=0 "
        "rdata0=0 rdata1=0 rdata3=0 d_req=0 d_wdata=0 "
        "content_digest=QIOV1_1_0_5"
    )
    cases = {
        "summary_only_append": [
            "1 | DIAG_SUMMARY | stage=c0 qualified_progress=1"
        ],
        "conflicting_double_decision": [valid, valid],
        "missing_reason": [valid.replace(" reason=STALL_WINDOW_EXCEEDED", "")],
        "missing_boundary": [valid.replace(" boundary=X", "")],
        "level_only_pseudo_progress": [
            "1 | STATE | valid=1 ready=1 count=16"
        ],
    }
    return {
        name: module.parse_canonical_records(lines)["valid"] is False
        for name, lines in cases.items()
    }


def validate(
    zip_path: Path,
    sidecar: Path,
    bash: Path,
    python: Path,
    expected_zip_sha256: str = EXPECTED_ZIP_SHA256,
    report_schema: str = "node0004-v23-runner-feature-controls-v1",
    require_return_manifest: bool = False,
) -> dict[str, Any]:
    digest = sha256(zip_path)
    sidecar_ok = sidecar.read_text(encoding="ascii") == (
        f"{digest}  {zip_path.name}\n"
    )
    with tempfile.TemporaryDirectory(
        prefix=".n4-v23-controls-", dir=zip_path.parents[3]
    ) as temporary:
        root = Path(temporary)
        package = extract(zip_path, root / "extract")
        before = records(package)

        exit_stub = root / "exit_stub"
        write_stubs(exit_stub, python)
        exit_server = root / "exit_server"
        exit_compile = root / "exit_compile.log"
        exit_started = root / "exit_started"
        exit_process = run_exit(
            package,
            exit_server,
            exit_stub,
            exit_compile,
            exit_started,
            bash,
        )
        name = package.name
        exit_evidence = exit_server / f"evidence_{name}"
        exit_run = exit_server / f"run_{name}/c0"
        if not (exit_evidence / "diagnostic_feature_binding.json").is_file():
            raise ValueError(
                "exit control failed before feature receipt: "
                f"rc={exit_process.returncode}\nstdout={exit_process.stdout}\n"
                f"stderr={exit_process.stderr}"
            )
        exit_receipt = load(exit_evidence / "diagnostic_feature_binding.json")
        exit_gate = load(exit_evidence / "SERVER_RESULT_GATE.json")
        exit_argv = (exit_run / "simulator_argv.txt").read_text(
            encoding="utf-8"
        )
        exit_return = exit_server / f"{name}_return.zip"
        exit_members = returned_members(exit_return)
        exit_checks = {
            "runner_exit_74": exit_process.returncode == EXPECTED_EXIT_STUB,
            "compile_called_once": (
                exit_compile.read_text(encoding="utf-8").count("argv=") == 1
            ),
            "package_preflight_valid": load(
                exit_evidence / "package_preflight.json"
            ).get("valid")
            is True,
            "install_preflight_valid": load(
                exit_evidence / "install_preflight.json"
            ).get("valid")
            is True,
            "observer_precompile_identity_valid": load(
                exit_evidence / "observer_precompile.json"
            ).get("valid")
            is True,
            "four_feature_receipt_valid": (
                exit_receipt.get("valid") is True
                and len(exit_receipt.get("features", [])) == len(FEATURES)
                and all(
                    item.get("valid") is True
                    for item in exit_receipt.get("features", [])
                )
            ),
            "actual_argv_has_all_features": all(
                enable in exit_argv.split() and limit in exit_argv.split()
                for enable, limit in FEATURES.values()
            ),
            "feature_receipt_returned": (
                "evidence/diagnostic_feature_binding.json" in exit_members
            ),
            "observer_returned": (
                "runs/c0/return_observer.log" in exit_members
            ),
            "result_gate_not_pass": (
                exit_gate.get("formal_readback_claimed") is False
                and exit_gate.get("e4_claimed") is False
                and exit_gate.get("e5_claimed") is False
            ),
            "return_manifest_contract": (
                not require_return_manifest
                or {
                    "RETURN_MANIFEST.json",
                    "evidence/returned_package_manifest.json",
                }
                <= exit_members
            ),
        }

        term_stub = root / "term_stub"
        write_stubs(term_stub, python)
        term_server = root / "term_server"
        term_compile = root / "term_compile.log"
        term_started = root / "term_started"
        term_status = root / "term_status.txt"
        term_process = run_term(
            package,
            term_server,
            term_stub,
            term_compile,
            term_started,
            bash,
            term_status,
        )
        term_runner_status = (
            int(term_status.read_text(encoding="ascii").strip())
            if term_status.is_file()
            else None
        )
        term_evidence = term_server / f"evidence_{name}"
        term_return = term_server / f"{name}_return.zip"
        term_members = returned_members(term_return)
        term_checks = {
            "harness_exit_zero": term_process.returncode == 0,
            "runner_term_exit_143": term_runner_status == 143,
            "safe_sim_started": term_started.is_file(),
            "signal_status_term": (
                (term_evidence / "signal_status.txt")
                .read_text(encoding="ascii")
                .strip()
                == "TERM"
            ),
            "partial_return_exists": term_return.is_file(),
            "critical_partial_evidence_returned": {
                "evidence/compile_exit_status.txt",
                "evidence/run_exit_status.txt",
                "evidence/signal_status.txt",
                "evidence/SERVER_RESULT_GATE.json",
                "evidence/diagnostic_feature_binding.json",
                "runs/c0/simulator_argv.txt",
                "runs/c0/return_observer.log",
            }
            <= term_members,
            "return_manifest_contract": (
                not require_return_manifest
                or {
                    "RETURN_MANIFEST.json",
                    "evidence/returned_package_manifest.json",
                }
                <= term_members
            ),
        }
        canonical = canonical_negatives(package)
        after = records(package)
        checks = {
            "zip_identity": digest == expected_zip_sha256,
            "sidecar": sidecar_ok,
            "package_immutable": before == after,
            "exit_finalizer": all(exit_checks.values()),
            "term_finalizer": all(term_checks.values()),
            "canonical_negatives": all(canonical.values()),
        }
        return {
            "schema": report_schema,
            "valid": all(checks.values()),
            "checks": checks,
            "exit_control": {
                "runner_exit_code": exit_process.returncode,
                "checks": exit_checks,
                "actual_simulator_argv": exit_argv.strip(),
                "feature_receipt": exit_receipt,
                "return_members": sorted(exit_members),
            },
            "term_control": {
                "harness_exit_code": term_process.returncode,
                "runner_exit_code": term_runner_status,
                "checks": term_checks,
                "return_members": sorted(term_members),
            },
            "canonical_negative_controls": canonical,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_action": False,
            "claim_boundary": (
                "safe local compile/simulator stubs and runtime contract only; "
                "no VCS, DUT simulation, formal D, E3, E4, or E5"
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--bash", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument(
        "--expected-zip-sha256", default=EXPECTED_ZIP_SHA256
    )
    parser.add_argument(
        "--report-schema",
        default="node0004-v23-runner-feature-controls-v1",
    )
    parser.add_argument(
        "--require-return-manifest", action="store_true"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.bash.resolve(),
        args.python.resolve(),
        args.expected_zip_sha256,
        args.report_schema,
        args.require_return_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
