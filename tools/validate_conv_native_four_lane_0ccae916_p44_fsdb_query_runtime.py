#!/usr/bin/env python3
"""Positive/negative runtime fixtures for p44 registered FSDB event evidence."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_0cc_p44_fsdbvq"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def extract(zip_path: Path, root: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        for row in archive.infolist():
            member = PurePosixPath(row.filename)
            if member.is_absolute() or ".." in member.parts or stat.S_ISLNK(row.external_attr >> 16):
                raise RuntimeError(f"unsafe ZIP member: {row.filename}")
        archive.extractall(root)
    return root / PACKAGE


def invoke(
    package: Path,
    root: Path,
    *,
    missing_last: bool,
    raw_pass: bool,
    execution: str,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    root.mkdir(parents=True, exist_ok=True)
    profile_path = package / "contracts/native_fsdb_query_profile.json"
    source_path = package / "diagnostics/native_fsdb_query_source_report.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    rows = profile["candidates"][:-1] if missing_last else profile["candidates"]
    log = root / "sim.log"
    values = ["x", "z", "1", "0", "x", "1", "b1x", "b0z", "1"]
    lines = [
        (
            f"CODEX_NATIVE_FSDB_EVENT_V1 instance={profile['exact_probe_instance']} sequence={index} "
            f"time_tick={index} candidate={row['candidate_id']} width={row['width']} value={values[index]}"
        )
        for index, row in enumerate(rows)
    ]
    lines.append(
        f"CODEX_NATIVE_FSDB_SUMMARY_V1 instance={profile['exact_probe_instance']} "
        f"sequence_count={len(rows)} time_tick=9 end_vector=b00000000000"
    )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    compile_argv = root / "actual_compile_argv.json"
    write_json(
        compile_argv,
        {
            "schema": "server-production-compile-argv-v1",
            "argv": [
                "make",
                "compile",
                "DUMP_VCD=0",
                "DUMP_FSDB=1",
                "TB_DUMP_FSDB=0",
                str(package / "tb_probe/source_bound_causal_observer.svh"),
                str(package / "tb_probe/native_fsdb_event_probe.svh"),
            ],
        },
    )
    sim_argv = root / "actual_sim_argv.json"
    write_json(
        sim_argv,
        {
            "schema": "server-production-simulation-argv-v1",
            "cwd": str(root),
            "argv_text": "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 simv -ucli -i dump_waveform.tcl +CODEX_NATIVE_FSDB_QUERY",
            "shell_pipeline": False,
        },
    )
    dump = root / "dump_waveform.tcl"
    dump.write_text(
        "set CODEX_WAVE_PATH {/tmp/wave.fsdb}\n"
        "fsdbDumpfile $CODEX_WAVE_PATH\n"
        "fsdbDumpvars 0 tb_NDP_Top_new_phy\n"
        "fsdbDumpMDA 0 tb_NDP_Top_new_phy\n"
        "fsdbDumpflush\nrun\nquit\n",
        encoding="utf-8",
        newline="\n",
    )
    raw = root / "WAVEFORM_RUNTIME_RECEIPT.json"
    write_json(
        raw,
        {
            "schema": "server-waveform-runtime-receipt-v3",
            "pass": raw_pass,
            "package_id": PACKAGE,
            "execution_id": execution,
            "waveforms": [
                {
                    "archive": "waveforms/run/sim_results/wave.fsdb",
                    "bytes": 9,
                    "sha256": "0" * 64,
                    "completeness": "COMPLETE" if raw_pass else "PARTIAL",
                }
            ],
        },
    )
    output = root / "evidence"
    completed = subprocess.run(
        [
            sys.executable,
            str(package / "package_tools/conv_native_fsdb_event_query.py"),
            "collect",
            "--log",
            str(log),
            "--profile",
            str(profile_path),
            "--source-report",
            str(source_path),
            "--waveform-receipt",
            str(raw),
            "--actual-compile-argv",
            str(compile_argv),
            "--actual-sim-argv",
            str(sim_argv),
            "--dump-control",
            str(dump),
            "--output-dir",
            str(output),
            "--package-id",
            PACKAGE,
            "--execution-id",
            execution,
            "--attempt-id",
            "a0",
            "--exit-kind",
            "NATURAL",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return completed, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-p44-query-") as temporary:
        root = Path(temporary)
        package = extract(args.zip, root / "extract")
        positive, positive_root = invoke(package, root / "positive", missing_last=False, raw_pass=True, execution="exec-positive")
        negative, negative_root = invoke(package, root / "negative", missing_last=True, raw_pass=False, execution="exec-negative")
        positive_receipt = json.loads((positive_root / "SIGNAL_QUERY_RECEIPT.json").read_text(encoding="utf-8"))
        positive_status = json.loads((positive_root / "DIAGNOSTIC_STATUS.json").read_text(encoding="utf-8"))
        negative_receipt = json.loads((negative_root / "SIGNAL_QUERY_RECEIPT.json").read_text(encoding="utf-8"))
        negative_status = json.loads((negative_root / "DIAGNOSTIC_STATUS.json").read_text(encoding="utf-8"))
        checks = {
            "positive_exit_zero": positive.returncode == 0,
            "positive_complete": positive_receipt.get("completeness") == "COMPLETE",
            "positive_status_complete": positive_status.get("status") == "DIAGNOSTIC_EVIDENCE_COMPLETE",
            "positive_contiguous": [row["sequence"] for row in positive_receipt.get("events", [])] == list(range(9)),
            "positive_xz_preserved": {row["value"] for row in positive_receipt.get("events", [])} >= {"x", "z", "b1x", "b0z"},
            "positive_exact_candidate_set": positive_receipt.get("candidate_coverage", {}).get("missing") == [],
            "negative_exit_nonzero": negative.returncode != 0,
            "negative_partial": negative_receipt.get("completeness") == "PARTIAL",
            "negative_marks_incomplete": negative_status.get("status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "negative_raw_and_core_preserved": negative_status.get("raw_fsdb_preserved") is True and negative_status.get("core_return_must_publish") is True,
            "negative_receipts_still_published": all((negative_root / name).is_file() for name in ("SIGNAL_QUERY_RECEIPT.json", "FSDB_QUERY_BINDING.json", "DIAGNOSTIC_STATUS.json")),
        }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-p44-fsdb-query-runtime-fixture-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "positive_stderr": positive.stderr[-4096:],
        "negative_stderr": negative.stderr[-4096:],
        "claim_boundary": "Synthetic exact-ZIP registered-query plumbing controls only; no production simulator or DUT claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": errors, "output": str(args.output)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
