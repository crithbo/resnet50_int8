from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_NAME = "r5_n71_gap_v9_ingress_rule"
TARGET_NAME = "r5_n71_gap_v10_runner_guard"
OBSERVER_RELATIVE = Path("tb_probe/native_return_observer.svh")
RUNNER_RELATIVE = Path("PREPARE_AND_RUN.sh")
OLD_EXPECTED = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
ACTUAL_EXPECTED = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)


class ValidationError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def to_git_bash(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":/", 1)[1]
    return f"/{drive}/{rest}"


def extract(path: Path, root_name: str, destination: Path) -> Path:
    package = destination / root_name
    package.mkdir(parents=True, exist_ok=False)
    prefix = f"{root_name}/"
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValidationError(f"ZIP CRC differs: {path}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not info.filename.startswith(prefix)
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = pure.relative_to(root_name)
            rel = relative.as_posix()
            if rel in seen:
                raise ValidationError(f"duplicate ZIP member: {rel}")
            seen.add(rel)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    return package


def run_guard(
    package: Path,
    expected: str,
    runner: Path | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(
            package
            / "package_tools/gap_node0071_package_observer_guard.py"
        ),
        "--package-root",
        str(package),
        "--expected-sha256",
        expected,
        "--runner",
        str(runner or package / RUNNER_RELATIVE),
    ]
    process = subprocess.run(
        command,
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    parsed = None
    if process.stdout.strip():
        try:
            parsed = json.loads(process.stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(
            process.stdout.encode("utf-8")
        ).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            process.stderr.encode("utf-8")
        ).hexdigest(),
        "parsed": parsed,
    }


def refresh_manifest_file_receipt(package: Path, relative: str) -> None:
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = package / relative
    manifest["files"][relative] = {
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
    }
    manifest_path.write_text(
        json.dumps(
            manifest, indent=2, ensure_ascii=False, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def mock_tools(root: Path) -> tuple[Path, Path]:
    bin_dir = root / "mock_bin"
    bin_dir.mkdir()
    marker = root / "make_reached.txt"
    python_wrapper = bin_dir / "python3"
    python_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{Path(sys.executable).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    make_wrapper = bin_dir / "make"
    make_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'printf "MOCK_MAKE_REACHED\\n" >"$MOCK_MAKE_MARKER"\n'
        "exit 86\n",
        encoding="utf-8",
        newline="\n",
    )
    mkdir_wrapper = bin_dir / "mkdir"
    mkdir_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "exec python3 -c 'import os,sys; "
        "[os.makedirs(p, exist_ok=(\"-p\" in sys.argv)) "
        "for p in sys.argv[1:] if not p.startswith(\"-\")]' \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    python_wrapper.chmod(0o755)
    make_wrapper.chmod(0o755)
    mkdir_wrapper.chmod(0o755)
    return bin_dir, marker


def run_runner_mock(
    package: Path,
    root: Path,
    bash: Path,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    runner_text = (package / RUNNER_RELATIVE).read_text(encoding="utf-8")
    install_match = re.search(
        r'^install_name="([^"]+)"', runner_text, re.MULTILINE
    )
    if install_match is None:
        raise ValidationError(f"runner install_name missing: {package}")
    install_name = install_match.group(1)
    mock_root = root / "mock_server_root"
    mock_root.mkdir()
    bin_dir, marker = mock_tools(root)
    env = {
        **os.environ,
        "MOCK_MAKE_MARKER": to_git_bash(marker),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = subprocess.run(
        [
            str(bash),
            "-c",
            (
                'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"; '
                'cd "$2"; exec bash PREPARE_AND_RUN.sh "$3"'
            ),
            "gap-runner-mock",
            to_git_bash(bin_dir),
            to_git_bash(package),
            to_git_bash(mock_root),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    evidence = mock_root / f"evidence_{install_name}"
    installed = evidence / "installed_preflight.json"
    observer = evidence / "observer_precompile.json"
    actual_compile = evidence / "actual_compile_argv.txt"
    def read_json_if_valid(path: Path) -> Any:
        if not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "_invalid_json": True,
                "_content": content,
            }
    return {
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": hashlib.sha256(
            process.stdout.encode("utf-8")
        ).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            process.stderr.encode("utf-8")
        ).hexdigest(),
        "make_reached": marker.is_file(),
        "installed_preflight": read_json_if_valid(installed),
        "observer_precompile": read_json_if_valid(observer),
        "actual_compile_argv_exists": actual_compile.is_file(),
        "return_zip_exists": (
            mock_root / f"{install_name}_return.zip"
        ).is_file(),
    }


def mutate_runner_term(package: Path, old: str, new: str) -> Path:
    runner = package / RUNNER_RELATIVE
    text = runner.read_text(encoding="utf-8")
    if old not in text:
        raise ValidationError(f"runner mutation term absent: {old}")
    runner.write_text(
        text.replace(old, new),
        encoding="utf-8",
        newline="\n",
    )
    return runner


def validate(
    source_zip: Path,
    target_zip: Path,
    bash: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".g71-",
        dir=Path.cwd(),
        ignore_cleanup_errors=True,
    ) as temporary:
        root = Path(temporary)
        source = extract(source_zip, SOURCE_NAME, root / "source")
        target = extract(target_zip, TARGET_NAME, root / "target")
        source_runner = source / RUNNER_RELATIVE
        target_runner = target / RUNNER_RELATIVE
        source_text = source_runner.read_text(encoding="utf-8")
        target_text = target_runner.read_text(encoding="utf-8")
        observer_sha = sha256(target / OBSERVER_RELATIVE)
        if (
            source_text.count(OLD_EXPECTED) != 1
            or target_text.count(ACTUAL_EXPECTED) != 1
            or OLD_EXPECTED in target_text
            or observer_sha != ACTUAL_EXPECTED
        ):
            raise ValidationError("runner/observer SHA static binding differs")

        source_guard = run_guard(source, OLD_EXPECTED)
        target_guard = run_guard(target, ACTUAL_EXPECTED)
        if source_guard["exit_code"] != 1:
            raise ValidationError("v9 mismatch did not fail observer guard")
        if (
            target_guard["exit_code"] != 0
            or target_guard["parsed"].get("valid") is not True
            or target_guard["parsed"].get("identity_match") is not True
        ):
            raise ValidationError("v10 observer guard positive control failed")

        controls: dict[str, Any] = {}
        control_specs = {
            "source_missing": None,
            "incdir_missing": (
                "+incdir+$package_root/tb_probe",
                "+incdir+$package_root/absent_probe",
            ),
            "macro_missing": (
                "+define+NATIVE_RETURN_OBSERVER_ENABLE",
                "+define+NATIVE_RETURN_OBSERVER_DISABLED",
            ),
            "runtime_missing": (
                "+RETURN_OBSERVER",
                "+NO_RETURN_OBSERVER",
            ),
        }
        for name, mutation in control_specs.items():
            control_root = root / f"control_{name}"
            shutil.copytree(target, control_root)
            if name == "source_missing":
                (control_root / OBSERVER_RELATIVE).unlink()
            else:
                assert mutation is not None
                mutate_runner_term(control_root, mutation[0], mutation[1])
            receipt = run_guard(control_root, ACTUAL_EXPECTED)
            controls[name] = receipt
            if receipt["exit_code"] != 1:
                raise ValidationError(f"negative control did not fail: {name}")

        wrong_expected = run_guard(target, OLD_EXPECTED)
        controls["wrong_expected_sha"] = wrong_expected
        if wrong_expected["exit_code"] != 1:
            raise ValidationError("wrong expected SHA did not fail")

        source_staged = source_zip.with_suffix("")
        target_staged = target_zip.with_suffix("")
        if not source_staged.is_dir() or not target_staged.is_dir():
            raise ValidationError("staged package directory missing for mock")
        source_mock = run_runner_mock(
            source_staged, root / "source_mock", bash
        )
        if (
            source_mock["exit_code"] != 7
            or source_mock["make_reached"]
            or source_mock["observer_precompile"] is None
            or source_mock["observer_precompile"].get("valid") is not False
        ):
            raise ValidationError(
                "v9 full-run mock did not stop at guard exit7: "
                + json.dumps(source_mock, ensure_ascii=False)
            )

        target_mock = run_runner_mock(
            target_staged, root / "target_mock", bash
        )
        if (
            target_mock["exit_code"] != 86
            or not target_mock["make_reached"]
            or target_mock["installed_preflight"].get("valid") is not True
            or target_mock["observer_precompile"].get("valid") is not True
            or not target_mock["actual_compile_argv_exists"]
        ):
            raise ValidationError(
                "v10 full-run mock did not pass guard and reach compile"
            )

        mismatch_mock = source_mock

        return {
            "schema": "gap-node0071-runner-guard-chain-validation-v1",
            "valid": True,
            "source_v9": {
                "zip": str(source_zip),
                "zip_sha256": sha256(source_zip),
                "runner_expected_sha256": OLD_EXPECTED,
                "observer_actual_sha256": sha256(
                    source / OBSERVER_RELATIVE
                ),
                "guard": source_guard,
                "full_runner_mock": source_mock,
            },
            "target_v10": {
                "zip": str(target_zip),
                "zip_sha256": sha256(target_zip),
                "runner_expected_sha256": ACTUAL_EXPECTED,
                "observer_actual_sha256": observer_sha,
                "guard": target_guard,
                "full_runner_mock": target_mock,
            },
            "negative_controls": controls,
            "full_runner_wrong_sha_control": mismatch_mock,
            "all_negative_controls_fail_closed": True,
            "first_divergence":
                "OBSERVER_GUARD_EXPECTED_SHA_MISMATCH_BEFORE_COMPILE",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(
            args.source_zip.resolve(),
            args.target_zip.resolve(),
            args.bash.resolve(),
        )
        if args.output:
            args.output.write_text(
                json.dumps(
                    result, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except Exception as error:
        print(f"runner-chain validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
