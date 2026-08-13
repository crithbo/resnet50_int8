from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v63_runnerdiag"


def bash_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1:3] == ":/":
        return "/" + value[0].lower() + value[2:]
    return value


def run_case(
    bash: Path,
    package: Path,
    result_root: Path,
    args: list[str],
    tool_stubs: Path,
    bash_result_root: str,
    *,
    collision: bool = False,
) -> dict[str, object]:
    runner = package / "PREPARE_AND_RUN.sh"
    text = re.sub(
        r'^result_root="[^"]+"$',
        f'result_root="{bash_result_root}"',
        runner.read_text(encoding="utf-8"),
        count=1,
        flags=re.MULTILINE,
    )
    runner.write_text(text, encoding="utf-8", newline="\n")
    result_root.mkdir(parents=True, exist_ok=True)
    if collision:
        (result_root / f"{PACKAGE}_return.zip").write_bytes(b"preserved")
    completed = subprocess.run(
        [str(bash), str(runner), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env={
            **os.environ,
            "MSYS2_ARG_CONV_EXCL": "*",
            "PATH": f"{bash_path(tool_stubs)}:/usr/bin:/bin",
        },
        timeout=30,
    )
    return {
        "exit": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v63-runner-visible-") as temp:
        root = Path(temp)
        bash_temp = f"/tmp/{root.name}"
        with zipfile.ZipFile(args.zip) as archive:
            archive.extractall(root / "extract")
        package = root / "extract" / PACKAGE
        server = root / "server"
        server.mkdir()
        tool_stubs = root / "tool-stubs"
        tool_stubs.mkdir()
        for name in ("python3", "timeout", "make"):
            stub = tool_stubs / name
            stub.write_text(
                "#!/usr/bin/env bash\nexit 99\n",
                encoding="utf-8",
                newline="\n",
            )
            stub.chmod(0o755)
        no_args = run_case(
            args.bash,
            package,
            root / "result-no-args",
            [],
            tool_stubs,
            f"{bash_temp}/result-no-args",
        )
        bad_server = run_case(
            args.bash,
            package,
            root / "result-bad-server",
            [f"{bash_temp}/absent-server"],
            tool_stubs,
            f"{bash_temp}/result-bad-server",
        )
        collision = run_case(
            args.bash,
            package,
            root / "result-collision",
            [f"{bash_temp}/server"],
            tool_stubs,
            f"{bash_temp}/result-collision",
            collision=True,
        )
        checks = {
            "no_args_exit2_visible": (
                no_args["exit"] == 2
                and "RUNNER_ERROR code=2" in str(no_args["stderr"])
                and "expected exactly one server_root argument"
                in str(no_args["stderr"])
            ),
            "bad_server_exit2_visible": (
                bad_server["exit"] == 2
                and "RUNNER_ERROR code=2" in str(bad_server["stderr"])
                and "server_root missing or unreadable"
                in str(bad_server["stderr"])
            ),
            "collision_exit10_visible": (
                collision["exit"] == 10
                and "RUNNER_ERROR code=10" in str(collision["stderr"])
                and "return target collision" in str(collision["stderr"])
            ),
            "collision_preserved": (
                (
                    root
                    / "result-collision"
                    / f"{PACKAGE}_return.zip"
                ).read_bytes()
                == b"preserved"
            ),
            "final_status_marker_present": (
                "RUNNER_FINAL_STATUS package=%s" in
                (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
            ),
        }
        negative_runner = (
            package / "PREPARE_AND_RUN.sh"
        ).read_text(encoding="utf-8").replace(
            'runner_fail 10 "return target collision;',
            'exit 10 # return target collision;',
        )
        checks["bare_collision_negative_fail_closed"] = (
            'runner_fail 10 "return target collision;' not in negative_runner
        )
    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v63-runner-visibility-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "cases": {
            "no_args": no_args,
            "bad_server": bad_server,
            "collision": collision,
        },
        "claim_boundary": (
            "Exact final runner early-error visibility only; no DUT, numeric, "
            "compile, simulation, terminal, formal-D, E4, or E5 claim."
        ),
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
