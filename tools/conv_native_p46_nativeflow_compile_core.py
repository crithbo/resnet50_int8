#!/usr/bin/env python3
"""Capture the exact native-flow compile core without server preflight.

The prepare phase records the command that will actually be launched and
identities only package-owned observer sources.  It deliberately does not
stat, hash, inventory, or attest the server Makefile, RTL, libraries, tools,
or module providers.  The finalize phase runs only after the real production
compile attempt and preserves the complete log plus bounded head/tail and the
first true compiler error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


HEAD_BYTES = 64 * 1024
TAIL_BYTES = 64 * 1024
FIRST_ERROR_BYTES = 4 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def package_file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "authority": "PACKAGE_OWNED_SOURCE",
    }


def compile_argv(args: argparse.Namespace) -> list[str]:
    sources = " ".join(str(path.resolve()) for path in args.source)
    return [
        "timeout",
        "--foreground",
        "--signal=TERM",
        "--kill-after=30s",
        "2h",
        "make",
        "-f",
        args.makefile_name,
        "compile",
        "DUMP_VCD=0",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        f"RUN_DIR={args.run_dir}",
        (
            "VCS_EXTRA_OPTS="
            f"+incdir+{args.package_root.resolve() / 'tb_probe'} {sources}"
        ),
    ]


def sim_argv(args: argparse.Namespace) -> list[str]:
    return [
        str(args.run_dir / "sim_results" / "simv"),
        "-l",
        str(args.attempt_root / "c0" / "sim.log"),
        "+vcs+lic+wait",
        f"+SCA_CFG={args.sca_cfg}",
        f"+SCA_CFG_D={args.sca_cfg_d}",
        "+CODEX_CAUSAL_OBSERVER",
        "+CODEX_OBSERVER_ONLY_WIDE_CAUSAL",
        f"+CODEX_OBSERVER_CHUNK={args.observer_chunk}",
        f"+CODEX_PACKAGE_ID={args.package_id}",
        f"+CODEX_EXECUTION_ID={args.execution_id}",
        f"+CODEX_ATTEMPT_ID={args.attempt_id}",
    ]


def prepare(args: argparse.Namespace) -> int:
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    actual_compile = compile_argv(args)
    actual_sim = sim_argv(args)
    write_json(
        output / "compile_argv.json",
        {
            "schema": "server-production-compile-argv-v2",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "actual_cwd": str(args.cwd),
            "argv": actual_compile,
            "shell_pipeline": False,
            "waveforms_explicitly_disabled": [
                "DUMP_VCD=0",
                "DUMP_FSDB=0",
                "TB_DUMP_FSDB=0",
            ],
            "server_preflight_performed": False,
        },
    )
    write_json(
        output / "compile_source_identity.json",
        {
            "schema": "server-production-compile-source-identity-v2",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "actual_cwd": str(args.cwd),
            "makefile": {
                "path": str(Path(args.cwd) / args.makefile_name),
                "prelaunch_identity_probe": False,
                "identity_disposition": "ADJUDICATED_ONLY_BY_ACTUAL_COMPILE_LOG_EXIT",
            },
            "package_sources": [package_file_identity(path) for path in args.source],
            "package_root": str(args.package_root.resolve()),
            "source_binding": "ACTUAL_PACKAGE_LOCAL_SOURCES_IN_PRODUCTION_COMPILE_ARGV",
        },
    )
    write_json(
        output / "ACTUAL_COMPILE_SIM_ARGV.json",
        {
            "schema": "server-observer-actual-argv-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "source_identity_status": "PACKAGE_SOURCES_BOUND_SERVER_ENVIRONMENT_UNCLAIMED",
            "actual_cwd": str(args.cwd),
            "compile_cwd": str(args.cwd),
            "sim_cwd": str(args.cwd),
            "compile_argv": actual_compile,
            "sim_argv": actual_sim,
            "relevant_env": {
                "DUMP_VCD": "0",
                "DUMP_FSDB": "0",
                "TB_DUMP_FSDB": "0",
                "SCA_CFG": str(args.sca_cfg),
                "SCA_CFG_D": str(args.sca_cfg_d),
                "Repeat_Num": args.repeat_num,
            },
            "sca_cfg": str(args.sca_cfg),
            "sca_cfg_d": str(args.sca_cfg_d),
            "repeat_num": args.repeat_num,
            "server_preflight_performed": False,
        },
    )
    (output / "compile_exit.txt").write_text("125\n", encoding="ascii", newline="\n")
    for name in (
        "compile_driver.log",
        "compile_log_head.txt",
        "compile_log_tail.txt",
        "compile_first_error.txt",
    ):
        (output / name).write_bytes(b"")
    return 0


def first_error(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()

    def excerpt(index: int) -> bytes:
        context = [
            lines[index],
            *lines[index + 1 : index + 8],
            *lines[max(0, index - 2) : index],
        ]
        return (("\n".join(context) + "\n").encode("utf-8"))[:FIRST_ERROR_BYTES]

    structured = re.compile(
        r"(?i)^\s*(?:Error-\[[^]]+\]|Error:|Fatal(?:-|:)|\*\*\s*(?:Error|Fatal)|"
        r"[^:\n]+:\d+(?::\d+)?:\s*(?:fatal\s+error|error):)"
    )
    for index, line in enumerate(lines):
        if structured.search(line):
            return excerpt(index)
    generic = re.compile(
        r"(?i)(^|\s)(fatal|failed|failure|undefined|unresolved|not found|"
        r"no rule to make target|syntax error|xmre|undeclared identifier|"
        r"cannot open|permission denied)(\s|:|$)"
    )
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "warning" in lowered or "error message report included" in lowered:
            continue
        if generic.search(line):
            return excerpt(index)
    fallback = "\n".join(lines[-8:]) + ("\n" if lines else "")
    return fallback.encode("utf-8")[:FIRST_ERROR_BYTES]


def finalize(args: argparse.Namespace) -> int:
    output = args.output_root.resolve()
    log = output / "compile_driver.log"
    data = log.read_bytes() if log.is_file() else b""
    first = first_error(data)
    (output / "compile_exit.txt").write_text(
        f"{args.exit_code}\n", encoding="ascii", newline="\n"
    )
    (output / "compile_log_head.txt").write_bytes(data[:HEAD_BYTES])
    (output / "compile_log_tail.txt").write_bytes(data[-TAIL_BYTES:] if data else b"")
    (output / "compile_first_error.txt").write_bytes(first)
    log_receipt = {
        "schema": "server-production-compile-driver-log-receipt-v2",
        "path": str(log),
        "exists": log.is_file(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "complete_log_returned": True,
        "head_limit_bytes": HEAD_BYTES,
        "tail_limit_bytes": TAIL_BYTES,
        "first_error_limit_bytes": FIRST_ERROR_BYTES,
    }
    write_json(output / "compile_log_receipt.json", log_receipt)
    compile_argv_value = json.loads((output / "compile_argv.json").read_text(encoding="utf-8"))
    actual_value = json.loads((output / "ACTUAL_COMPILE_SIM_ARGV.json").read_text(encoding="utf-8"))
    write_json(
        output / "COMPILE_CORE.json",
        {
            "schema": "server-compile-core-v2",
            "package_id": compile_argv_value["package_id"],
            "execution_id": compile_argv_value["execution_id"],
            "attempt_id": compile_argv_value["attempt_id"],
            "actual_cwd": compile_argv_value["actual_cwd"],
            "actual_compile_argv": compile_argv_value["argv"],
            "actual_sim_argv": actual_value["sim_argv"],
            "sca_cfg": actual_value["sca_cfg"],
            "sca_cfg_d": actual_value["sca_cfg_d"],
            "repeat_num": actual_value["repeat_num"],
            "compile_exit": args.exit_code,
            "simulation_started": False,
            "first_true_error": {
                "path": "compile_first_error.txt",
                "bytes": len(first),
                "sha256": sha256_bytes(first),
            },
            "complete_log_receipt": log_receipt,
            "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
            "server_runtime_unknown_preserved": True,
        },
    )
    return 0


def return_core(args: argparse.Namespace) -> int:
    output = args.output_root.resolve()
    compile_core_path = output / "COMPILE_CORE.json"
    if compile_core_path.is_file():
        core = json.loads(compile_core_path.read_text(encoding="utf-8"))
    else:
        core = {
            "schema": "server-compile-core-v2",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "compile_exit": args.compile_exit,
            "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
            "server_runtime_unknown_preserved": True,
        }
    core["simulation_started"] = args.simulation_started
    core["sim_exit"] = args.sim_exit
    core["sim_signal"] = args.signal
    core["timed_out"] = args.timed_out
    write_json(compile_core_path, core)
    write_json(
        output / "SIM_EXIT_RECEIPT.json",
        {
            "schema": "server-observer-sim-exit-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "simulation_started": args.simulation_started,
            "exit_code": args.sim_exit,
            "signal": args.signal,
            "timed_out": args.timed_out,
            "compile_exit": args.compile_exit,
        },
    )
    first_error_path = output / "compile_first_error.txt"
    first_error_text = (
        first_error_path.read_text(encoding="utf-8", errors="replace")
        if first_error_path.is_file()
        else ""
    )
    classification = (
        "NOT_APPLICABLE_COMPILE_PASSED"
        if args.compile_exit == 0
        else "SERVER_RUNTIME_UNKNOWN"
    )
    write_json(
        output / "NATIVE_FLOW_FAILURE_DIFFERENTIAL.json",
        {
            "schema": "server-native-flow-failure-differential-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "timing": "AFTER_ACTUAL_FAILURE_BEFORE_SUCCESSOR_DESIGN",
            "classification": classification,
            "compile_exit": args.compile_exit,
            "simulation_started": args.simulation_started,
            "first_true_error": first_error_text,
            "known_native_checks": {
                "actual_cwd_argv_returned": True,
                "same_package_sca_cfg_and_sca_cfg_d_returned": True,
                "repeat_num_returned": True,
                "complete_compile_log_returned": True,
                "server_loader_start_wait_readback": "SERVER_RUNTIME_UNKNOWN",
            },
            "provider_preflight_performed": False,
            "claim_boundary": (
                "Post-actual-command native-flow differential only; unknown "
                "server loader, start, wait, readback, libraries and providers "
                "remain SERVER_RUNTIME_UNKNOWN."
            ),
        },
    )
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root", type=Path, required=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("prepare")
    add_common(start)
    start.add_argument("--package-id", required=True)
    start.add_argument("--execution-id", required=True)
    start.add_argument("--attempt-id", required=True)
    start.add_argument("--cwd", type=Path, required=True)
    start.add_argument("--makefile-name", required=True)
    start.add_argument("--source", type=Path, action="append", required=True)
    start.add_argument("--package-root", type=Path, required=True)
    start.add_argument("--run-dir", type=Path, required=True)
    start.add_argument("--attempt-root", type=Path, required=True)
    start.add_argument("--sca-cfg", type=Path, required=True)
    start.add_argument("--sca-cfg-d", type=Path, required=True)
    start.add_argument("--observer-chunk", type=Path, required=True)
    start.add_argument("--repeat-num", type=int, required=True)
    finish = sub.add_parser("finalize")
    add_common(finish)
    finish.add_argument("--exit-code", type=int, required=True)
    returned = sub.add_parser("return-core")
    add_common(returned)
    returned.add_argument("--package-id", required=True)
    returned.add_argument("--execution-id", required=True)
    returned.add_argument("--attempt-id", required=True)
    returned.add_argument("--compile-exit", type=int, required=True)
    returned.add_argument("--sim-exit", type=int, required=True)
    returned.add_argument("--simulation-started", action="store_true")
    returned.add_argument("--signal", choices=("NONE", "HUP", "INT", "TERM"), required=True)
    returned.add_argument("--timed-out", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare(args)
    if args.command == "finalize":
        return finalize(args)
    return return_core(args)


if __name__ == "__main__":
    raise SystemExit(main())
