from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools.validate_node0004_v63_runner_visibility as base


PACKAGE = "r5_n4_hw_v65_branchcatch_diag"


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
    if collision:
        text = text.replace(
            'return_tag="r$(date -u +%s%N)_$$"',
            'return_tag="r_collision"',
            1,
        )
    runner.write_text(text, encoding="utf-8", newline="\n")
    result_root.mkdir(parents=True, exist_ok=True)
    collision_path = (
        result_root / f"{PACKAGE}_r_collision_return.zip"
        if collision
        else None
    )
    if collision_path is not None:
        collision_path.write_bytes(b"preserved")
    completed = subprocess.run(
        [str(bash), str(runner), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env={
            **os.environ,
            "MSYS2_ARG_CONV_EXCL": "*",
            "PATH": f"{base.bash_path(tool_stubs)}:/usr/bin:/bin",
        },
        timeout=30,
    )
    return {
        "exit": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "collision_path": str(collision_path) if collision_path else None,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="v65-runner-visible-") as temp:
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
        collision_path = Path(str(collision["collision_path"]))
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
            "unique_tag_collision_exit10_visible": (
                collision["exit"] == 10
                and "RUNNER_ERROR code=10" in str(collision["stderr"])
                and "return target collision" in str(collision["stderr"])
            ),
            "unique_tag_collision_preserved": (
                collision_path.read_bytes() == b"preserved"
            ),
            "final_status_marker_present": (
                "RUNNER_FINAL_STATUS package=%s"
                in (package / "PREPARE_AND_RUN.sh").read_text(
                    encoding="utf-8"
                )
            ),
        }
    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v65-repeatable-runner-visibility-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "cases": {
            "no_args": no_args,
            "bad_server": bad_server,
            "collision": collision,
        },
        "claim_boundary": (
            "Exact v65 final runner early-error visibility and unique-tag "
            "collision preservation only; no DUT, numeric, compile, "
            "simulation, terminal, formal-D, E4, or E5 claim."
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
