#!/usr/bin/env python3
"""Exercise p43's exact packaged portable runtime with positive/negative attempts."""

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


PACKAGE = "r5_n4_0cc_p43_portablevq"
ATTEMPT = f"install/codex_runs/{PACKAGE}/a0"


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(zip_path: Path, target: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        roots = {row.filename.split("/", 1)[0] for row in infos}
        if roots != {PACKAGE} or archive.testzip() is not None:
            raise RuntimeError("p43 exact ZIP root/CRC differs")
        for row in infos:
            member = PurePosixPath(row.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in row.filename:
                raise RuntimeError(f"unsafe ZIP member: {row.filename}")
            if stat.S_ISLNK(row.external_attr >> 16):
                raise RuntimeError(f"symlink ZIP member: {row.filename}")
            path = target.joinpath(*member.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(row.filename))
    return target / PACKAGE


def vcd_text(include_finish: bool = True) -> str:
    finish_var = "$var wire 1 ) slice_cmpt_finish $end\n" if include_finish else ""
    finish_values = "0)\n" if include_finish else ""
    finish_mid = "0)\n" if include_finish else ""
    finish_end = "1)\n" if include_finish else ""
    return f"""$date p43-portable-runtime-fixture $end
$version native-p43-portable-fixture $end
$timescale 1 ns $end
$scope module tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine $end
$var wire 1 ! mse_mem_ag_tag_valid $end
$var wire 1 \" mse_mem_ag_bp_pre $end
$var wire 1 # wr_data_chl_req_valid $end
$var wire 1 $ wr_data_chl_req_ready $end
$var wire 1 % buf2mse_rvalid $end
$var wire 1 & wr_data_chl_ready $end
$var wire 2 ' mse2mem_wdata_valid [1:0] $end
$var wire 2 ( mem2mse_wdata_ready [1:0] $end
{finish_var}$upscope $end
$enddefinitions $end
#0
0!
0\"
0#
0$
0%
0&
b00 '
b00 (
{finish_values}#5
x!
z\"
1#
1$
1%
1&
b1x '
b0z (
{finish_mid}#10
1!
0\"
0#
1$
0%
1&
b11 '
b11 (
{finish_end}"""


def prepare_attempt(asset_root: Path, package: Path, include_finish: bool) -> tuple[Path, list[str]]:
    attempt = asset_root.joinpath(*PurePosixPath(ATTEMPT).parts)
    wave_root = attempt / "run/sim_results"
    evidence = attempt / "evidence/waveform"
    c0 = attempt / "c0"
    wave_root.mkdir(parents=True)
    evidence.mkdir(parents=True)
    c0.mkdir(parents=True)
    vpd = wave_root / "wave.vpd"
    vcd = wave_root / "wave.vcd"
    vpd.write_bytes(b"authoritative-native-p43-fixture\n")
    vcd.write_text(vcd_text(include_finish), encoding="utf-8", newline="\n")
    dump = wave_root / "codex_waveform_portable.tcl"
    shutil.copyfile(package / "contracts/server_waveform_portable_dump.tcl", dump)
    argv = [
        "DUMP_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "DUMP_PORTABLE_VCD=1",
        "timeout",
        "12h",
        "/fixture/simv",
        "-ucli",
        "-i",
        str(dump),
    ]
    write(c0 / "actual_sim_argv.json", argv)
    write(
        attempt / "compile_argv.json",
        {
            "schema": "server-production-compile-argv-v1",
            "argv": ["make", "compile", *argv[:4]],
            "cwd": "/fixture/server",
            "shell_pipeline": False,
        },
    )
    write(
        evidence / "WAVEFORM_RUNTIME_RECEIPT.json",
        {
            "schema": "server-waveform-runtime-receipt-v2",
            "package_id": PACKAGE,
            "execution_id": "fixture-exec",
            "plan_sha256": "a" * 64,
            "simulation_started": True,
            "exit_kind": "NATURAL",
            "waveforms": [
                {
                    "source_path": "run/sim_results/wave.vpd",
                    "archive_path": "waveforms/run/sim_results/wave.vpd",
                    "bytes": vpd.stat().st_size,
                    "sha256": sha(vpd),
                    "format": "VPD",
                    "completeness": "COMPLETE",
                }
            ],
            "no_size_limit": True,
            "all_matching_collected": True,
            "pass": True,
            "errors": [],
            "claim_boundary": "local native p43 portable runtime fixture",
        },
    )
    return attempt, argv


def run_case(package: Path, root: Path, include_finish: bool) -> dict[str, Any]:
    attempt, _ = prepare_attempt(root, package, include_finish)
    output = attempt / "evidence/portable"
    completed = subprocess.run(
        [
            sys.executable,
            str(package / "package_tools/conv_native_portable_vcd_query.py"),
            "collect",
            "--profile",
            str(package / "contracts/server_waveform_portable_profile.json"),
            "--shared-helper",
            str(package / "package_tools/server_waveform_portable_query.py"),
            "--asset-root",
            str(root),
            "--attempt-root",
            str(attempt),
            "--output-dir",
            str(output),
            "--source-report",
            str(package / "diagnostics/portable_query_source_report.json"),
            "--vcd",
            str(attempt / "run/sim_results/wave.vcd"),
            "--actual-compile-argv",
            str(attempt / "compile_argv.json"),
            "--actual-sim-argv",
            str(attempt / "c0/actual_sim_argv.json"),
            "--dump-tcl",
            str(attempt / "run/sim_results/codex_waveform_portable.tcl"),
            "--raw-receipt",
            str(attempt / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"),
            "--package-id",
            PACKAGE,
            "--execution-id",
            "fixture-exec",
            "--attempt-id",
            "a0",
            "--exit-kind",
            "NATURAL",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    status = json.loads((output / "PORTABLE_FIRST_FRESH_STATUS.json").read_text(encoding="utf-8"))
    query = json.loads((output / "SIGNAL_QUERY_RECEIPT.json").read_text(encoding="utf-8"))
    runtime_path = output / "PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.is_file() else None
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "status": status,
        "query": query,
        "runtime": runtime,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="native-p43-portable-") as directory:
        temp = Path(directory)
        package = safe_extract(args.zip, temp / "extracted")
        positive = run_case(package, temp / "positive", True)
        negative = run_case(package, temp / "negative", False)
    positive_query = positive["query"]
    values = [row.get("value") for row in positive_query.get("events", [])]
    checks = {
        "positive_exit_zero": positive["exit_code"] == 0,
        "positive_status_complete": positive["status"].get("pass") is True
        and positive["status"].get("diagnostic_status") == "COMPLETE",
        "positive_runtime_complete": positive["runtime"] is not None
        and positive["runtime"].get("diagnostic_status") == "COMPLETE",
        "positive_candidate_exact_set": positive_query.get("candidate_coverage", {}).get("missing") == []
        and len(positive_query.get("candidate_end_states", [])) == 9,
        "positive_contiguous_sequence": [row.get("sequence") for row in positive_query.get("events", [])]
        == list(range(len(positive_query.get("events", [])))),
        "positive_xz_preserved": any("x" in str(value).lower() for value in values)
        and any("z" in str(value).lower() for value in values),
        "negative_exit_nonzero": negative["exit_code"] != 0,
        "negative_marks_incomplete": negative["status"].get("diagnostic_status")
        == "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "negative_return_preserved": negative["status"].get("return_must_publish") is True
        and negative["status"].get("preserve_on_failure")
        == ["raw_vpd", "compile_core", "sim_core", "signal_core", "return_core"],
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-p43-portable-runtime-fixture-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "checks": checks,
        "errors": errors,
        "positive": {
            "event_count": len(positive_query.get("events", [])),
            "candidate_count": len(positive_query.get("catalog", [])),
            "diagnostic_status": positive["status"].get("diagnostic_status"),
        },
        "negative": {
            "diagnostic_status": negative["status"].get("diagnostic_status"),
            "errors": negative["status"].get("errors"),
        },
        "claim_boundary": "Local exact-package synthetic portable runtime only; no server action or DUT claim.",
        "server_action": False,
    }
    write(args.output, report)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
