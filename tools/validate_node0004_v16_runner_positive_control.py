from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_STUB_EXIT = 73
RULE_ID = "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001"


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
        ': "${COMPILE_STUB_LOG:?COMPILE_STUB_LOG is required}"\n'
        '{ printf "cwd=%s\\n" "$PWD"; printf "argv="; '
        'printf "%q " "$@"; printf "\\n"; } >> "$COMPILE_STUB_LOG"\n'
        f"exit {EXPECTED_STUB_EXIT}\n",
        encoding="utf-8",
        newline="\n",
    )
    for path in (python_stub, make_stub):
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_case(
    package_root: Path,
    server_root: Path,
    stub_bin: Path,
    bash: Path,
    compile_log: Path,
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
                'exec /usr/bin/bash -x "$3" "$4"'
            ),
            "runner-positive-control",
            msys_path(stub_bin),
            msys_path(compile_log),
            msys_path(package_root / "PREPARE_AND_RUN.sh"),
            msys_path(server_root),
        ],
        cwd=package_root,
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


def positive_case(
    zip_path: Path,
    root: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    extract_root = root / "positive_extract"
    package = extract(zip_path, extract_root)
    before = tree_records(package)
    stub_bin = root / "positive_stubs"
    write_stubs(stub_bin, python)
    compile_stub_log = root / "positive_compile_stub.log"
    server_root = root / "positive_server"
    process = run_case(
        package, server_root, stub_bin, bash, compile_stub_log
    )
    after = tree_records(package)
    install_name = package.name
    evidence = server_root / f"evidence_{install_name}"
    package_preflight = load_json(evidence / "package_preflight.json")
    install_preflight = load_json(evidence / "install_preflight.json")
    observer_precompile = load_json(evidence / "observer_precompile.json")
    compile_status_path = evidence / "compile_exit_status.txt"
    compile_status = (
        int(compile_status_path.read_text(encoding="ascii").strip())
        if compile_status_path.is_file()
        else None
    )
    stub_lines = (
        compile_stub_log.read_text(encoding="utf-8").splitlines()
        if compile_stub_log.is_file()
        else []
    )
    argv_lines = [line for line in stub_lines if line.startswith("argv=")]
    actual_argv = argv_lines[0][len("argv="):] if len(argv_lines) == 1 else None
    ordered = (
        package_preflight is not None
        and package_preflight.get("valid") is True
        and install_preflight is not None
        and install_preflight.get("valid") is True
        and observer_precompile is not None
        and observer_precompile.get("valid") is True
        and len(argv_lines) == 1
    )
    checks = {
        "runner_exit_is_unique_stub_exit": (
            process.returncode == EXPECTED_STUB_EXIT
        ),
        "package_preflight_valid": (
            package_preflight is not None
            and package_preflight.get("valid") is True
        ),
        "installed_preflight_valid": (
            install_preflight is not None
            and install_preflight.get("valid") is True
        ),
        "observer_guard_valid_and_identity_match": (
            observer_precompile is not None
            and observer_precompile.get("valid") is True
            and observer_precompile.get("identity_match") is True
        ),
        "compile_stub_invoked_exactly_once": len(argv_lines) == 1,
        "compile_status_is_stub_exit": compile_status == EXPECTED_STUB_EXIT,
        "actual_compile_argv_is_compile_target": (
            actual_argv is not None
            and "Makefile.tb_NDP_Top_new_phy" in actual_argv
            and "compile" in actual_argv
            and "RUN_DIR=" in actual_argv
            and "VCS_EXTRA_OPTS=" in actual_argv
        ),
        "ordered_chain_reached_compile": ordered,
        "package_tree_unchanged": before == after,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "runner_exit_code": process.returncode,
        "expected_stub_exit_code": EXPECTED_STUB_EXIT,
        "actual_compile_argv": actual_argv,
        "compile_stub_invocation_count": len(argv_lines),
        "package_preflight": package_preflight,
        "installed_preflight": install_preflight,
        "observer_precompile": observer_precompile,
        "compile_exit_status": compile_status,
        "runner_stdout": process.stdout,
        "runner_stderr": process.stderr,
        "package_tree_before": before,
        "package_tree_after": after,
    }


def negative_case(
    zip_path: Path,
    root: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    extract_root = root / "negative_extract"
    package = extract(zip_path, extract_root)
    observer = package / "tb_probe/native_return_observer.svh"
    observer.write_text(
        observer.read_text(encoding="utf-8") + "\n// wrong identity\n",
        encoding="utf-8",
        newline="\n",
    )
    stub_bin = root / "negative_stubs"
    write_stubs(stub_bin, python)
    compile_stub_log = root / "negative_compile_stub.log"
    server_root = root / "negative_server"
    process = run_case(
        package, server_root, stub_bin, bash, compile_stub_log
    )
    stub_invocations = (
        len(
            [
                line
                for line in compile_stub_log.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.startswith("argv=")
            ]
        )
        if compile_stub_log.is_file()
        else 0
    )
    install_name = package.name
    evidence = server_root / f"evidence_{install_name}"
    checks = {
        "runner_failed": process.returncode != 0,
        "failed_before_compile": stub_invocations == 0,
        "package_preflight_did_not_validate": not (
            (load_json(evidence / "package_preflight.json") or {}).get("valid")
            is True
        ),
        "installed_preflight_not_reached": not (
            evidence / "install_preflight.json"
        ).exists(),
        "observer_precompile_not_reached": not (
            evidence / "observer_precompile.json"
        ).exists(),
    }
    return {
        "valid": all(checks.values()),
        "failed_closed": all(checks.values()),
        "mutation": "append one line to package-local observer after extraction",
        "checks": checks,
        "runner_exit_code": process.returncode,
        "compile_stub_invocation_count": stub_invocations,
        "runner_stdout": process.stdout,
        "runner_stderr": process.stderr,
    }


def validate(
    zip_path: Path,
    sidecar: Path,
    bash: Path,
    python: Path,
) -> dict[str, Any]:
    digest = sha256_file(zip_path)
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    sidecar_valid = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == digest
        and sidecar_tokens[1] == zip_path.name
    )
    with tempfile.TemporaryDirectory(
        prefix="r16pc-",
        dir=zip_path.parents[3],
    ) as temp:
        temporary = Path(temp)
        positive = positive_case(zip_path, temporary, bash, python)
        negative = negative_case(zip_path, temporary, bash, python)
    valid = sidecar_valid and positive["valid"] and negative["valid"]
    return {
        "schema": "node0004-v16-runner-positive-control-v1",
        "rule_id": RULE_ID,
        "valid": valid,
        "status": (
            "RUNNER_PREFLIGHT_TO_COMPILE_POSITIVE_CONTROL_PASS"
            if valid
            else "PACKAGE_RUNNER_PREFLIGHT_TO_COMPILE_CHAIN_UNPROVEN"
        ),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": str(sidecar),
            "sha256": sha256_file(sidecar),
            "valid": sidecar_valid,
        },
        "bash": {
            "path": str(bash),
            "sha256": sha256_file(bash),
        },
        "python": {
            "path": str(python),
            "sha256": sha256_file(python),
        },
        "positive_control": positive,
        "negative_controls": {
            "wrong_observer_identity_sha": negative,
            "all_failed_closed": negative["failed_closed"],
        },
        "claim_boundary": (
            "safe local runner control flow only; no real VCS, elaboration, "
            "simulation, E3, E4, or E5"
        ),
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


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
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
