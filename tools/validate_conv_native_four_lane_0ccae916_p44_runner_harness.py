#!/usr/bin/env python3
"""Exercise p44 bootstrap compile-core evidence with both actual HDL sources."""

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


PACKAGE = "r5_n4_0cc_p44_fsdbvq"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--harness-output", type=Path, required=True)
    parser.add_argument("--shared-output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    returned: list[str] = []
    with tempfile.TemporaryDirectory(prefix="p44_compile_core_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(args.zip) as archive:
            infos = archive.infolist()
            safe = all(
                not PurePosixPath(row.filename).is_absolute()
                and ".." not in PurePosixPath(row.filename).parts
                and "\\" not in row.filename
                and not stat.S_ISLNK(row.external_attr >> 16)
                for row in infos
            )
            checks["zip_safe_crc_unique"] = archive.testzip() is None and safe and len(infos) == len({row.filename for row in infos})
            archive.extractall(root)
        package = root / PACKAGE
        runner = package / "PREPARE_AND_RUN.sh"
        text = runner.read_text(encoding="utf-8")
        checks.update(
            {
                "nounset": "set -u" in text,
                "definition_before_use_contract": (package / "server_runner_return_resilience_contract.json").is_file(),
                "compile_core_prepare_finalize": '"$compile_core_helper" prepare' in text and '"$compile_core_helper" finalize' in text,
                "fsdb_v3_compile_flags": all(token in text for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")),
                "retired_waveform_absent": all(token not in text for token in ("DUMP_PORTABLE_VCD", "wave.vpd", "wave.vcd")),
                "two_actual_sources_in_runner": '--source "$source_bound_observer" --source "$fsdb_query_probe"' in text,
                "bounded_compile_core": all(token in text for token in ("compile_log_head.txt", "compile_log_tail.txt", "compile_first_error.txt")),
                "waveform_collector_before_post_sim": text.find('"$waveform_helper" collect-runtime') < text.find('python3 "$post_sim_helper" finalize --request "$post_sim_request"'),
            }
        )
        bash = shutil.which("bash")
        if bash is None:
            fallback = Path("C:/Program Files/Git/bin/bash.exe")
            bash = str(fallback) if fallback.is_file() else None
        syntax = run([bash, "-n", str(runner)]) if bash else None
        checks["bash_syntax"] = syntax is not None and syntax.returncode == 0
        server = root / "server"
        server.mkdir()
        makefile = server / "Makefile.tb_NDP_Top_new_phy"
        makefile.write_text("compile:\n\t@false\n", encoding="utf-8", newline="\n")
        bootstrap = server / "install/codex_runs" / PACKAGE / "bootstrap-test"
        helper = package / "package_tools/compile_core_evidence.py"
        sources = [
            package / "tb_probe/source_bound_causal_observer.svh",
            package / "tb_probe/native_fsdb_event_probe.svh",
        ]
        start = run(
            [
                sys.executable,
                str(helper),
                "prepare",
                "--output-root",
                str(bootstrap),
                "--cwd",
                str(server),
                "--makefile",
                str(makefile),
                "--source",
                str(sources[0]),
                "--source",
                str(sources[1]),
                "--package-root",
                str(package),
                "--run-dir",
                str(server / "compile"),
            ]
        )
        payload = b"compile banner\n" + b"A" * 70000 + b"\nError: actual first compile failure\n" + b"Z" * 70000 + b"\ncompile tail\n"
        (bootstrap / "compile_driver.log").write_bytes(payload)
        finish = run([sys.executable, str(helper), "finalize", "--output-root", str(bootstrap), "--exit-code", "2"])
        required = (
            "compile_argv.json",
            "compile_source_identity.json",
            "compile_exit.txt",
            "compile_log_receipt.json",
            "compile_log_head.txt",
            "compile_log_tail.txt",
            "compile_first_error.txt",
        )
        source_identity = json.loads((bootstrap / "compile_source_identity.json").read_text(encoding="utf-8"))
        argv = json.loads((bootstrap / "compile_argv.json").read_text(encoding="utf-8"))
        identities = source_identity.get("package_sources", [])
        argv_text = " ".join(str(row) for row in argv.get("argv", []))
        checks.update(
            {
                "helper_prepare_finalize": start.returncode == 0 and finish.returncode == 0,
                "compile_core_exact_set": all((bootstrap / name).is_file() for name in required),
                "bounded_head_tail_first_error": (bootstrap / "compile_log_head.txt").stat().st_size <= 65536 and (bootstrap / "compile_log_tail.txt").stat().st_size <= 65536 and (bootstrap / "compile_first_error.txt").stat().st_size <= 4096,
                "first_real_error": "actual first compile failure" in (bootstrap / "compile_first_error.txt").read_text(encoding="utf-8"),
                "actual_exit": (bootstrap / "compile_exit.txt").read_text(encoding="ascii").strip() == "2",
                "actual_source_exact_set": len(identities) == 2 and [row.get("sha256") for row in identities] == [sha(path) for path in sources],
                "actual_argv_exact_sources": all(str(path.resolve()) in argv_text for path in sources),
                "actual_argv_fsdb_flags": all(token in argv_text for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")),
            }
        )
        publisher = package / "package_tools/fixed_simresult_publisher.py"
        fixed = root / "simresult"
        publisher.write_text(
            publisher.read_text(encoding="utf-8").replace('FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"', f"FIXED_RESULT_ROOT = {str(fixed)!r}"),
            encoding="utf-8",
            newline="\n",
        )
        target = fixed / f"{PACKAGE}_rtest_return.zip"
        publication = run(
            [
                sys.executable,
                str(publisher),
                "--bootstrap-partial",
                "--package-root",
                str(package),
                "--bootstrap-root",
                str(bootstrap),
                "--exit-code",
                "2",
                "--stage",
                "PRODUCTION_COMPILE",
                "--server-root",
                str(server),
                "--return-zip",
                str(target),
            ]
        )
        checks["compile_fail_return_published"] = publication.returncode == 0 and target.is_file() and Path(str(target) + ".sha256").is_file()
        if target.is_file():
            with zipfile.ZipFile(target) as archive:
                returned = archive.namelist()
                return_manifest = json.loads(archive.read(f"{PACKAGE}/RETURN_MANIFEST.json"))
            expected = {
                f"{PACKAGE}/RETURN_MANIFEST.json",
                f"{PACKAGE}/RETURN_ALLOWLIST.txt",
                f"{PACKAGE}/evidence/package_local_preflight_status.json",
                *(f"{PACKAGE}/compile_core/{name}" for name in required),
            }
            checks["return_exact_allowlist"] = set(returned) == expected
            checks["compile_core_complete"] = return_manifest.get("compile_core_complete") is True and return_manifest.get("runner_exit_code") == 2
            checks["compile_not_started_waveform_absent"] = all(not name.lower().endswith((".vpd", ".vcd", ".fsdb")) and "/waveforms/" not in name.lower() for name in returned)
        else:
            checks.update({"return_exact_allowlist": False, "compile_core_complete": False, "compile_not_started_waveform_absent": False})
    errors.extend(name for name, passed in checks.items() if not passed)
    scenario = {
        "runner_exit": 2,
        "finalizer_reached": not errors,
        "fixed_result_return_published": checks.get("compile_fail_return_published", False),
        "compile_core_complete": checks.get("compile_core_complete", False),
        "waveform_required": False,
    }
    report = {
        "schema": "conv-native-four-lane-p44-compile-core-harness-v1",
        "valid": not errors,
        "pass": not errors,
        "errors": errors,
        "scenarios": {"compile_fail": scenario},
        "details": {"checks": checks, "returned_members": returned},
        "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "server_action": False,
    }
    shared = {
        "schema": "server_package_runtime_layout_harness_v1",
        "pass": not errors,
        "errors": errors,
        "runner_member_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": report["scenarios"],
        "claim_boundary": "Local exact-ZIP compile-fail harness only; no server action.",
    }
    write(args.harness_output, report)
    write(args.shared_output, shared)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.harness_output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
