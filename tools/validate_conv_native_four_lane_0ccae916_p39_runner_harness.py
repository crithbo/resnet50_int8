#!/usr/bin/env python3
"""Exercise the exact p39 compile-core helper and bootstrap publisher locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE = "r5_n4_0cc_p39_compilecore"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--harness-output", type=Path, required=True)
    parser.add_argument("--shared-output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    details: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="p39_harness_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(args.zip) as archive:
            infos = archive.infolist()
            names = [row.filename for row in infos]
            safe = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
            if archive.testzip() is not None or not safe or len(names) != len(set(names)):
                errors.append("unsafe, corrupt or duplicate exact ZIP")
            archive.extractall(root)
        package = root / PACKAGE
        runner = package / "PREPARE_AND_RUN.sh"
        runner_sha = sha(runner)
        text = runner.read_text(encoding="utf-8")
        checks = {
            "nounset": "set -u" in text,
            "finalizer_once": text.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') == 1,
            "compile_core_prepare": '"$compile_core_helper" prepare' in text,
            "compile_core_finalize": '"$compile_core_helper" finalize' in text,
            "explicit_waveform_disable": all(token in text for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "bounded_tokens": all(token in text for token in ("compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt")),
            "bootstrap_publisher": '--bootstrap-root "$bootstrap_root"' in text,
        }
        bash = shutil.which("bash")
        if bash:
            syntax = run([bash, "-n", str(runner)])
            checks["bash_syntax"] = syntax.returncode == 0
            details["bash_syntax"] = {"exit_code": syntax.returncode, "stderr": syntax.stderr}
        server = root / "server"
        server.mkdir()
        makefile = server / "Makefile.tb_NDP_Top_new_phy"
        makefile.write_text("compile:\n\t@false\n", encoding="utf-8", newline="\n")
        bootstrap = server / "install/codex_runs" / PACKAGE / "bootstrap-test"
        helper = package / "package_tools/compile_core_evidence.py"
        source = package / "tb_probe/source_bound_causal_observer.svh"
        start = run([sys.executable, str(helper), "prepare", "--output-root", str(bootstrap), "--cwd", str(server), "--makefile", str(makefile), "--source", str(source), "--package-root", str(package), "--run-dir", str(server / "compile")])
        payload = b"compile banner\n" + b"A" * 70000 + b"\nError: actual first compile failure\n" + b"Z" * 70000 + b"\ncompile tail\n"
        (bootstrap / "compile_driver.log").write_bytes(payload)
        finish = run([sys.executable, str(helper), "finalize", "--output-root", str(bootstrap), "--exit-code", "2"])
        required = ("compile_argv.json", "compile_source_identity.json", "compile_exit.txt", "compile_log_receipt.json", "compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt")
        checks.update({
            "helper_prepare": start.returncode == 0,
            "helper_finalize": finish.returncode == 0,
            "core_exact_set": all((bootstrap / name).is_file() for name in required),
            "head_bounded": (bootstrap / "compile_log_head.txt").stat().st_size <= 65536,
            "tail_bounded": (bootstrap / "compile_log_tail.txt").stat().st_size <= 65536,
            "first_error_bounded": (bootstrap / "compile_first_error.txt").stat().st_size <= 4096,
            "first_error_actual": "actual first compile failure" in (bootstrap / "compile_first_error.txt").read_text(encoding="utf-8"),
            "exit_actual": (bootstrap / "compile_exit.txt").read_text(encoding="ascii").strip() == "2",
        })
        source_id = json.loads((bootstrap / "compile_source_identity.json").read_text(encoding="utf-8"))
        argv = json.loads((bootstrap / "compile_argv.json").read_text(encoding="utf-8"))
        checks["actual_source_identity"] = source_id["package_source"]["sha256"] == sha(source)
        checks["actual_compile_argv"] = str(source.resolve()) in argv["argv"][-1] and str(server.resolve()) == argv["cwd"]
        publisher = package / "package_tools/fixed_simresult_publisher.py"
        fixed = root / "simresult"
        publisher.write_text(publisher.read_text(encoding="utf-8").replace('FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"', f"FIXED_RESULT_ROOT = {str(fixed)!r}"), encoding="utf-8", newline="\n")
        target = fixed / f"{PACKAGE}_rtest_return.zip"
        publication = run([sys.executable, str(publisher), "--bootstrap-partial", "--package-root", str(package), "--bootstrap-root", str(bootstrap), "--exit-code", "2", "--stage", "PRODUCTION_COMPILE", "--server-root", str(server), "--return-zip", str(target)])
        checks["compile_fail_return_published"] = publication.returncode == 0 and target.is_file() and Path(str(target) + ".sha256").is_file()
        returned: list[str] = []
        if target.is_file():
            with zipfile.ZipFile(target) as archive:
                returned = archive.namelist()
                manifest = json.loads(archive.read(f"{PACKAGE}/RETURN_MANIFEST.json"))
            expected = {f"{PACKAGE}/RETURN_MANIFEST.json", f"{PACKAGE}/RETURN_ALLOWLIST.txt", f"{PACKAGE}/evidence/package_local_preflight_status.json", *(f"{PACKAGE}/compile_core/{name}" for name in required)}
            checks["return_exact_allowlist"] = set(returned) == expected
            checks["compile_core_complete"] = manifest.get("compile_core_complete") is True and manifest.get("runner_exit_code") == 2
            checks["waveform_absent"] = all(not any(token in name.lower() for token in ("vcd", "fsdb", "waveform")) for name in returned)
        else:
            checks.update({"return_exact_allowlist": False, "compile_core_complete": False, "waveform_absent": False})
        details.update({"checks": checks, "returned_members": returned, "publication": {"exit_code": publication.returncode, "stdout": publication.stdout, "stderr": publication.stderr}})
        errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-four-lane-p39-runner-harness-v1", "valid": not errors, "pass": not errors,
        "errors": errors, "scenarios": {"compile_fail": {"runner_exit": 2, "finalizer_reached": not errors, "fixed_result_return_published": not errors, "compile_core_complete": not errors}},
        "details": details, "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "server_action": False,
    }
    shared = {"schema": "server_package_runtime_layout_harness_v1", "pass": not errors, "errors": errors, "runner_member_sha256": runner_sha, "fixed_result_root": "/home/panqs/ndp/simresult", "scenarios": report["scenarios"], "claim_boundary": "Local exact-ZIP harness only; no server action."}
    write(args.harness_output, report)
    write(args.shared_output, shared)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.harness_output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
