#!/usr/bin/env python3
"""Capture native-flow compile/simulation identity for the p47 TB-VCD run.

Only package-owned sources are hashed before the production command.  Server
Makefiles, RTL, libraries and providers are deliberately adjudicated by the
actual native compile rather than by a separate prelaunch probe.
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


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha_file(resolved),
        "authority": "PACKAGE_OWNED_SOURCE",
    }


def compile_argv(args: argparse.Namespace) -> list[str]:
    sources = " ".join(str(path.resolve()) for path in args.source)
    return [
        "timeout", "--foreground", "--signal=TERM", "--kill-after=30s", "2h",
        "make", "-f", args.makefile_name, "compile",
        "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0",
        f"RUN_DIR={args.run_dir}", f"VCS_EXTRA_OPTS={sources}",
    ]


def sim_argv(args: argparse.Namespace) -> list[str]:
    return [
        str(args.run_dir / "sim_results" / "simv"),
        "-l", str(args.attempt_root / "c0" / "sim.log"), "+vcs+lic+wait",
        f"+SCA_CFG={args.sca_cfg}", f"+SCA_CFG_D={args.sca_cfg_d}",
        "+CODEX_TB_VCD_BOUNDED_CAUSAL_CONE",
        f"+CODEX_TB_VCD_PATH={args.vcd_path}",
        f"+CODEX_PACKAGE_ID={args.package_id}",
        f"+CODEX_EXECUTION_ID={args.execution_id}",
        f"+CODEX_ATTEMPT_ID={args.attempt_id}",
    ]


def prepare(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    actual_compile = compile_argv(args)
    actual_sim = sim_argv(args)
    common = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "actual_cwd": str(args.cwd),
    }
    write_json(root / "compile_argv.json", {
        "schema": "server-production-compile-argv-v2", **common,
        "argv": actual_compile, "shell_pipeline": False,
        "make_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "tb_standard_vcd_is_package_local": True,
        "server_preflight_performed": False,
    })
    write_json(root / "compile_source_identity.json", {
        "schema": "server-production-compile-source-identity-v2", **common,
        "makefile": {
            "path": str(Path(args.cwd) / args.makefile_name),
            "prelaunch_identity_probe": False,
            "identity_disposition": "ADJUDICATED_ONLY_BY_ACTUAL_COMPILE_LOG_EXIT",
        },
        "package_sources": [file_identity(path) for path in args.source],
        "package_root": str(args.package_root.resolve()),
        "source_binding": "ACTUAL_PACKAGE_LOCAL_TB_SOURCE_IN_PRODUCTION_COMPILE_ARGV",
    })
    write_json(root / "ACTUAL_COMPILE_SIM_ARGV.json", {
        "schema": "server-tb-vcd-actual-argv-v1", **common,
        "compile_cwd": str(args.cwd), "sim_cwd": str(args.cwd),
        "compile_argv": actual_compile, "sim_argv": actual_sim,
        "relevant_env": {
            "DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0",
            "SCA_CFG": str(args.sca_cfg), "SCA_CFG_D": str(args.sca_cfg_d),
            "Repeat_Num": args.repeat_num,
        },
        "sca_cfg": str(args.sca_cfg), "sca_cfg_d": str(args.sca_cfg_d),
        "repeat_num": args.repeat_num, "vcd_path": str(args.vcd_path),
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "server_preflight_performed": False,
    })
    (root / "compile_exit.txt").write_text("125\n", encoding="ascii", newline="\n")
    for name in ("compile_driver.log", "compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt"):
        (root / name).write_bytes(b"")
    return 0


def first_error(payload: bytes) -> bytes:
    lines = payload.decode("utf-8", errors="replace").splitlines()
    structured = re.compile(
        r"(?i)^\s*(?:Error-\[[^]]+\]|Error:|Fatal(?:-|:)|\*\*\s*(?:Error|Fatal)|"
        r"[^:\n]+:\d+(?::\d+)?:\s*(?:fatal\s+error|error):)"
    )
    generic = re.compile(
        r"(?i)(^|\s)(fatal|failed|failure|undefined|unresolved|not found|"
        r"no rule to make target|syntax error|xmre|undeclared identifier|"
        r"cannot open|permission denied)(\s|:|$)"
    )
    for matcher in (structured, generic):
        for index, line in enumerate(lines):
            if matcher.search(line) and not (matcher is generic and "warning" in line.lower()):
                excerpt = [*lines[max(0, index - 2):index], *lines[index:index + 8]]
                return (("\n".join(excerpt) + "\n").encode("utf-8"))[:FIRST_ERROR_BYTES]
    return (("\n".join(lines[-8:]) + ("\n" if lines else "")).encode("utf-8"))[:FIRST_ERROR_BYTES]


def finalize_compile(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    log = root / "compile_driver.log"
    payload = log.read_bytes() if log.is_file() else b""
    first = first_error(payload)
    (root / "compile_exit.txt").write_text(f"{args.exit_code}\n", encoding="ascii", newline="\n")
    (root / "compile_log_head.txt").write_bytes(payload[:HEAD_BYTES])
    (root / "compile_log_tail.txt").write_bytes(payload[-TAIL_BYTES:] if payload else b"")
    (root / "compile_first_error.txt").write_bytes(first)
    receipt = {
        "schema": "server-production-compile-driver-log-receipt-v2",
        "path": str(log), "exists": log.is_file(), "bytes": len(payload),
        "sha256": sha_bytes(payload), "complete_log_returned": True,
        "head_limit_bytes": HEAD_BYTES, "tail_limit_bytes": TAIL_BYTES,
        "first_error_limit_bytes": FIRST_ERROR_BYTES,
    }
    write_json(root / "compile_log_receipt.json", receipt)
    argv = json.loads((root / "compile_argv.json").read_text(encoding="utf-8"))
    actual = json.loads((root / "ACTUAL_COMPILE_SIM_ARGV.json").read_text(encoding="utf-8"))
    write_json(root / "COMPILE_CORE.json", {
        "schema": "server-compile-core-v2",
        "package_id": argv["package_id"], "execution_id": argv["execution_id"],
        "attempt_id": argv["attempt_id"], "actual_cwd": argv["actual_cwd"],
        "actual_compile_argv": argv["argv"], "actual_sim_argv": actual["sim_argv"],
        "sca_cfg": actual["sca_cfg"], "sca_cfg_d": actual["sca_cfg_d"],
        "repeat_num": actual["repeat_num"], "compile_exit": args.exit_code,
        "simulation_started": False,
        "first_true_error": {"path": "compile_first_error.txt", "bytes": len(first), "sha256": sha_bytes(first)},
        "complete_log_receipt": receipt,
        "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
        "server_runtime_unknown_preserved": True,
    })
    return 0


def return_core(args: argparse.Namespace) -> int:
    root = args.output_root.resolve()
    core_path = root / "COMPILE_CORE.json"
    core = json.loads(core_path.read_text(encoding="utf-8")) if core_path.is_file() else {
        "schema": "server-compile-core-v2", "package_id": args.package_id,
        "execution_id": args.execution_id, "attempt_id": args.attempt_id,
        "compile_exit": args.compile_exit,
    }
    core.update(
        simulation_started=args.simulation_started, sim_exit=args.sim_exit,
        sim_signal=args.signal, timed_out=args.timed_out,
        server_environment_adjudicator="ACTUAL_PRODUCTION_COMMAND_ONLY",
        server_runtime_unknown_preserved=True,
    )
    write_json(core_path, core)
    write_json(root / "SIM_EXIT_RECEIPT.json", {
        "schema": "server-tb-vcd-sim-exit-v1",
        "package_id": args.package_id, "execution_id": args.execution_id,
        "attempt_id": args.attempt_id, "simulation_started": args.simulation_started,
        "exit_code": args.sim_exit, "signal": args.signal,
        "timed_out": args.timed_out, "compile_exit": args.compile_exit,
    })
    write_json(root / "NATIVE_FLOW_FAILURE_DIFFERENTIAL.json", {
        "schema": "server-native-flow-failure-differential-v1",
        "package_id": args.package_id, "execution_id": args.execution_id,
        "attempt_id": args.attempt_id, "timing": "AFTER_ACTUAL_FAILURE_BEFORE_SUCCESSOR_DESIGN",
        "classification": "NOT_APPLICABLE_COMPILE_PASSED" if args.compile_exit == 0 else "SERVER_RUNTIME_UNKNOWN",
        "compile_exit": args.compile_exit, "simulation_started": args.simulation_started,
        "provider_preflight_performed": False,
        "claim_boundary": "Actual native-flow evidence only; unknown loader, start, wait, readback, libraries and providers remain SERVER_RUNTIME_UNKNOWN.",
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("prepare")
    start.add_argument("--output-root", type=Path, required=True)
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
    start.add_argument("--vcd-path", type=Path, required=True)
    start.add_argument("--repeat-num", type=int, required=True)
    finish = sub.add_parser("finalize")
    finish.add_argument("--output-root", type=Path, required=True)
    finish.add_argument("--exit-code", type=int, required=True)
    returned = sub.add_parser("return-core")
    returned.add_argument("--output-root", type=Path, required=True)
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
        return finalize_compile(args)
    return return_core(args)


if __name__ == "__main__":
    raise SystemExit(main())
