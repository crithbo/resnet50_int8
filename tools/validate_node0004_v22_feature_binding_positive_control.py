from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_SIM_STUB_EXIT = 74
RULE_ID = "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
FEATURES = {
    "RETURN_OBS_DEEP": (
        "+RETURN_OBS_DEEP",
        "+RETURN_OBS_DEEP_LIMIT=256",
        "limit=256",
    ),
    "RETURN_OBS_ABPE": (
        "+RETURN_OBS_ABPE",
        "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        "budget=8388608",
    ),
    "RETURN_HANG_DIAG": (
        "+RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
        "sample_cycles=262144",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_records(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def msys_path(path: Path) -> str:
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


def make_stubs(stub_bin: Path, python: Path) -> None:
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
        ': "${SIM_STUB_LOG:?}"\n'
        '{ printf "cwd=%s\\n" "$PWD"; printf "argv="; '
        'printf "%q " "$@"; printf "\\n"; } >> "$SIM_STUB_LOG"\n'
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
        '# Native NDP return observer feature-binding stub\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DEEP enabled=1 limit_name=RETURN_OBS_DEEP_LIMIT limit=256\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_ABPE enabled=1 budget_name=RETURN_HANG_DIAG_MAX_CYCLES budget=8388608\n'
        '0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_HANG_DIAG enabled=1 sample_cycles=262144 stall_windows=4 max_cycles=8388608\n'
        '1 | PROGRESS_WINDOW | stage=c0 start_comp=1 completed_stages=0 sample=1 qualified_progress=1 delta=1 no_progress_windows=0 consecutive_progress_windows=1 req0=1 req1=0 req3=0 rdata0=0 rdata1=0 rdata3=0 d_req=0 d_wdata=0\n'
        'OBSLOG\n'
        'printf "[0] safe simulator feature-binding stub\\n" > "$sim_log"\n'
        f"exit {EXPECTED_SIM_STUB_EXIT}\n"
        "SIMSTUB\n"
        'chmod +x "$run_dir/sim_results/simv"\n'
        'printf "safe compile stub\\n" > "$run_dir/sim_results/compile.log"\n'
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    for path in (python_stub, make_stub):
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_runner(
    package: Path,
    server_root: Path,
    stub_bin: Path,
    bash: Path,
    compile_log: Path,
    sim_log: Path,
) -> subprocess.CompletedProcess[str]:
    server_root.mkdir()
    environment = dict(os.environ)
    return subprocess.run(
        [
            str(bash),
            "-c",
            (
                'export PATH="$1:/usr/bin:/mingw64/bin"; '
                'export COMPILE_STUB_LOG="$2"; '
                'export SIM_STUB_LOG="$3"; '
                'exec /usr/bin/bash -x "$4" "$5"'
            ),
            "feature-binding-positive-control",
            msys_path(stub_bin),
            msys_path(compile_log),
            msys_path(sim_log),
            msys_path(package / "PREPARE_AND_RUN.sh"),
            msys_path(server_root),
        ],
        cwd=package,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def validate(
    zip_path: Path,
    sidecar_path: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    digest = sha256_file(zip_path)
    sidecar_tokens = sidecar_path.read_text(encoding="ascii").split()
    sidecar_valid = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == digest
        and sidecar_tokens[1] == zip_path.name
    )
    with tempfile.TemporaryDirectory(
        prefix="r22feature-",
        dir=zip_path.parents[3],
    ) as temp:
        root = Path(temp)
        package = extract(zip_path, root / "extract")
        before = tree_records(package)
        stub_bin = root / "stubs"
        make_stubs(stub_bin, python)
        compile_stub_log = root / "compile_stub.log"
        sim_stub_log = root / "sim_stub.log"
        server_root = root / "server"
        process = run_runner(
            package,
            server_root,
            stub_bin,
            bash,
            compile_stub_log,
            sim_stub_log,
        )
        after = tree_records(package)
        install_name = package.name
        evidence = server_root / f"evidence_{install_name}"
        run_root = server_root / f"run_{install_name}"
        receipt = load_json(evidence / "diagnostic_feature_binding.json")
        gate = load_json(evidence / "SERVER_RESULT_GATE.json")
        actual_argv_path = run_root / "c0/simulator_argv.txt"
        actual_argv = (
            actual_argv_path.read_text(encoding="utf-8")
            if actual_argv_path.is_file()
            else ""
        )
        observer_path = run_root / "c0/return_observer.log"
        observer = (
            observer_path.read_text(encoding="utf-8")
            if observer_path.is_file()
            else ""
        )
        return_zip = server_root / f"{install_name}_return.zip"
        return_sidecar = Path(str(return_zip) + ".sha256")
        returned: set[str] = set()
        if return_zip.is_file():
            with zipfile.ZipFile(return_zip) as archive:
                returned = {
                    PurePosixPath(*PurePosixPath(info.filename).parts[1:])
                    .as_posix()
                    for info in archive.infolist()
                    if not info.is_dir()
                }
        feature_checks: dict[str, bool] = {}
        for feature, (enable, limit, marker) in FEATURES.items():
            feature_checks[f"{feature}_argv"] = (
                enable in actual_argv.split()
                and limit in actual_argv.split()
            )
            feature_checks[f"{feature}_time0_marker"] = (
                f"feature={feature}" in observer
                and "enabled=1" in observer
                and marker in observer
            )
        checks = {
            "runner_reached_safe_simulator_stub": (
                process.returncode == EXPECTED_SIM_STUB_EXIT
            ),
            "package_tree_unchanged": before == after,
            "actual_simulator_argv_returned": (
                "runs/c0/simulator_argv.txt" in returned
            ),
            "feature_record_returned": (
                "runs/c0/return_observer.log" in returned
            ),
            "feature_binding_receipt_returned": (
                "evidence/diagnostic_feature_binding.json" in returned
            ),
            "feature_binding_receipt_valid": (
                receipt is not None
                and receipt.get("valid") is True
                and len(receipt.get("features", [])) == 3
                and all(
                    item.get("valid") is True
                    for item in receipt.get("features", [])
                )
            ),
            "result_gate_embeds_binding_receipt": (
                gate is not None
                and gate.get("diagnostic_feature_binding", {}).get("valid")
                is True
            ),
            "return_sidecar_generated_and_matches": (
                return_sidecar.is_file()
                and return_sidecar.read_text(encoding="ascii").split()[0]
                == sha256_file(return_zip)
            ),
            **feature_checks,
        }
        report = {
            "schema": "node0004-v22-feature-runtime-positive-control-v1",
            "rule_id": RULE_ID,
            "valid": sidecar_valid and all(checks.values()),
            "zip": {
                "path": str(zip_path),
                "bytes": zip_path.stat().st_size,
                "sha256": digest,
            },
            "sidecar": {
                "path": str(sidecar_path),
                "sha256": sha256_file(sidecar_path),
                "valid": sidecar_valid,
            },
            "checks": checks,
            "runner_exit_code": process.returncode,
            "expected_safe_simulator_stub_exit": EXPECTED_SIM_STUB_EXIT,
            "actual_simulator_argv": actual_argv.strip(),
            "feature_binding_receipt": receipt,
            "result_gate": gate,
            "returned_exact_members": sorted(returned),
            "runner_stdout": process.stdout,
            "runner_stderr": process.stderr,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
            "claim_boundary": (
                "safe local simulator-stub control flow only; no VCS, DUT "
                "simulation, formal D, E3, E4, or E5"
            ),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--bash", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.bash.resolve(),
        args.python.resolve(),
    )
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
