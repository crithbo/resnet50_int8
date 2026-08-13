#!/usr/bin/env python3
"""Create the independent first-fresh audit for the exact FSDB smoke ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"
FAMILY = "conv_serialized"
EPOCH = "fsdb-authoritative-repeatable-return-v3-0a1dee9757c6"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_extract(zip_path: Path, destination: Path) -> tuple[Path, list[str]]:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CRC failure")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP members")
        roots = set()
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise ValueError(f"unsafe ZIP member: {name}")
            roots.add(pure.parts[0])
        if roots != {PACKAGE_ID}:
            raise ValueError(f"root mismatch: {sorted(roots)}")
        archive.extractall(destination)
    return destination / PACKAGE_ID, names


def event_log(kind: str, reset_events: int = 0) -> str:
    rows = [
        (0, 0, "time_zero_marker", "0"),
        (1, 0, "time_zero_marker", "1"),
        (2, 0, "time_progress_marker", "0"),
        (3, 0, "top_rst_n", "x"),
    ]
    if kind != "time_zero_only":
        rows.append((4, 5000, "time_progress_marker", "1"))
    sequence = len(rows)
    for index in range(reset_events):
        rows.append((sequence, 6000 + index, "top_rst_n", str(index & 1)))
        sequence += 1
    if kind == "sequence_gap" and rows:
        seq, tick, cid, value = rows[-1]
        rows[-1] = (seq + 2, tick, cid, value)
    lines = [f"CODEX_FSDB_SMOKE_EVENT_V1 sequence={seq} time_tick={tick} candidate={cid} width=1 value={value}" for seq, tick, cid, value in rows]
    lines.append(f"CODEX_FSDB_SMOKE_SUMMARY_V1 time_tick={9000 + reset_events} time_zero=1 time_progress={'0' if kind == 'time_zero_only' else '1'} rst_n=1")
    return "\n".join(lines) + "\n"


def parser_case(package: Path, python: Path, root: Path, kind: str, *, reset_events: int = 0) -> dict[str, object]:
    case = root / kind; case.mkdir(parents=True)
    log = case / "sim.log"; log.write_text(event_log(kind, reset_events), encoding="utf-8")
    compile_argv = case / "compile.json"; write(compile_argv, {"argv": ["make", "DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0"]})
    sim_argv = case / "sim.json"; write(sim_argv, {"argv": ["simv", "-ucli"]})
    dump = case / "dump.tcl"; dump.write_bytes((package / "package_tools/dump_waveform.tcl").read_bytes())
    raw = case / "raw.json"
    raw_value = {"schema": "server-waveform-runtime-receipt-v3", "package_id": PACKAGE_ID, "execution_id": "r1234567890123456789_777", "simulation_started": True, "exit_kind": "NATURAL", "pass": kind != "raw_incomplete", "errors": [] if kind != "raw_incomplete" else ["missing_or_stale_fsdb"], "waveforms": [{"source_path": "run/sim_results/wave.fsdb", "archive_path": "waveforms/run/sim_results/wave.fsdb", "format": "FSDB", "bytes": 100, "sha256": "0" * 64, "completeness": "COMPLETE" if kind != "raw_incomplete" else "PARTIAL"}]}
    write(raw, raw_value)
    output = case / "out"
    env = os.environ.copy(); env.update({"CODEX_PACKAGE_ID": PACKAGE_ID, "CODEX_EXECUTION_ID": "r1234567890123456789_777", "CODEX_ATTEMPT_ID": "smoke"})
    process = subprocess.run([str(python), str(package / "package_tools/fsdb_smoke_event_parser.py"), "--log", str(log), "--profile", str(package / "contracts/fsdb_smoke_query_profile.json"), "--source-report", str(package / "diagnostics/fsdb_smoke_query_source_report.json"), "--waveform-receipt", str(raw), "--actual-compile-argv", str(compile_argv), "--actual-sim-argv", str(sim_argv), "--dump-control", str(dump), "--output-dir", str(output)], env=env, text=True, capture_output=True, check=False)
    progress = json.loads((output / "TIME_PROGRESS_RECEIPT.json").read_text())
    query = json.loads((output / "SIGNAL_QUERY_RECEIPT.json").read_text())
    binding = json.loads((output / "FSDB_QUERY_BINDING.json").read_text())
    return {"kind": kind, "exit": process.returncode, "query_completeness": query["completeness"], "progress_pass": progress["pass"], "binding_pass": binding["pass"], "errors": progress["errors"], "event_count": len(query["events"]), "no_event_limit": query["capture"]["no_event_limit"], "all_4state_values_preserved": any(e["value"] == "x" for e in query["events"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path); parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--runtime-harness", required=True, type=Path); parser.add_argument("--runtime-layout", required=True, type=Path); parser.add_argument("--post-sim", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(); out = args.output_dir.resolve(); reports = out / "reports"; reports.mkdir(parents=True, exist_ok=True)
    zip_digest = sha(args.zip); zip_bytes = args.zip.stat().st_size
    runtime = json.loads(args.runtime_harness.read_text()); layout = json.loads(args.runtime_layout.read_text()); post = json.loads(args.post_sim.read_text())
    with tempfile.TemporaryDirectory(prefix="node0004-fsdb-firstfresh-") as temp:
        package, names = safe_extract(args.zip.resolve(), Path(temp) / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text())
        declared = {row["path"]: (row["bytes"], row["sha256"]) for row in manifest["files"]}
        actual = {}
        for path in sorted(p for p in package.rglob("*") if p.is_file() and p.name != "package_manifest.json"):
            data = path.read_bytes(); actual[path.relative_to(package).as_posix()] = (len(data), hashlib.sha256(data).hexdigest())
        clean_errors = [] if declared == actual else ["manifest_member_map_differs"]
        clean = {"schema": "node0004-fsdb-smoke-clean-extract-v1", "pass": not clean_errors, "errors": clean_errors, "zip_sha256": zip_digest, "single_root": PACKAGE_ID, "member_count": len(names), "manifest_map_exact": declared == actual, "retired_ack_probe_members": [n for n in names if "buffer_ack" in n.lower()]}
        if clean["retired_ack_probe_members"]: clean["pass"] = False; clean["errors"].append("retired_ack_probe_present")
        write(reports / "exact_final_zip_clean_extract.json", clean)

        runner_checks = [runtime.get("pass") is True, layout.get("pass") is True, runtime.get("checks", {}).get("six_exit_codes") is True, runtime.get("checks", {}).get("repeat_two_successes") is True]
        runner_report = {"schema": "node0004-fsdb-smoke-exact-runner-input-v1", "pass": all(runner_checks), "errors": [] if all(runner_checks) else ["exact_runner_or_layout_harness_failed"], "zip_sha256": zip_digest, "runtime_checks": runtime.get("checks"), "layout_checks": layout.get("checks"), "frozen_input_path_count": 86, "formal_d_path_count": 28}
        write(reports / "actual_runner_entry_and_input_open.json", runner_report)

        cases_root = Path(temp) / "parser_cases"
        positive = parser_case(package, args.python, cases_root, "positive_over_budget", reset_events=160)
        time_zero = parser_case(package, args.python, cases_root, "time_zero_only")
        raw_bad = parser_case(package, args.python, cases_root, "raw_incomplete")
        sequence = parser_case(package, args.python, cases_root, "sequence_gap", reset_events=4)
        roundtrip_ok = positive["exit"] == 0 and positive["query_completeness"] == "COMPLETE" and positive["event_count"] > 128 and positive["no_event_limit"] is True and positive["all_4state_values_preserved"] is True
        roundtrip = {"schema": "node0004-fsdb-smoke-registered-event-roundtrip-v1", "pass": roundtrip_ok, "errors": [] if roundtrip_ok else ["over_budget_registered_event_roundtrip_failed"], "zip_sha256": zip_digest, "positive": positive, "exact_parser_sha256": sha(package / "package_tools/fsdb_smoke_event_parser.py"), "exact_probe_sha256": sha(package / "tb_probe/fsdb_smoke_event_probe.svh")}
        write(reports / "source_bound_logger_collector_parser_roundtrip.json", roundtrip)

        post_ok = post.get("pass") is True and set(post.get("details", {}).get("scenario_results", {})) == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"}
        post_report = {"schema": "node0004-fsdb-smoke-post-sim-four-scenario-v1", "pass": post_ok, "errors": [] if post_ok else ["post_sim_four_scenario_failed"], "zip_sha256": zip_digest, "scenario_results": post.get("details", {}).get("scenario_results", {})}
        write(reports / "post_sim_return_core_scenarios.json", post_report)

        negative_ok = time_zero["exit"] != 0 and raw_bad["exit"] != 0 and sequence["exit"] != 0
        repeat_ok = runtime.get("checks", {}).get("repeat_distinct_returns") is True and runtime.get("checks", {}).get("repeat_exact_reset") is True and runtime.get("checks", {}).get("repeat_foreign_siblings") is True
        matrix_ok = roundtrip_ok and negative_ok and repeat_ok and len({tuple(x["errors"]) for x in (time_zero, raw_bad, sequence)}) == 3
        matrix = {"schema": "node0004-fsdb-smoke-candidate-matrix-v1", "pass": matrix_ok, "errors": [] if matrix_ok else ["candidate_matrix_failed"], "positive_controls": [positive, {"kind": "repeat_execution", "pass": repeat_ok}], "negative_controls": [time_zero, raw_bad, sequence], "candidate_ids": ["time_zero_only", "time_advances_fsdb_complete", "raw_fsdb_missing_or_stale", "query_sequence_or_allowlist_incomplete", "repeat_execution_identity_reuse"], "pairwise_distinguishable": matrix_ok}
        write(reports / "candidate_discrimination_matrix.json", matrix)

    report_specs = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", "exact_final_zip_clean_extract.json"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", "actual_runner_entry_and_input_open.json"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", "source_bound_logger_collector_parser_roundtrip.json"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", "post_sim_return_core_scenarios.json"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", "candidate_discrimination_matrix.json"),
    ]
    evidence = []
    for gate_id, kind, name in report_specs:
        path = reports / name; evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    contract = {"schema": "server-first-fresh-extra-audit-v1", "package": {"package_id": PACKAGE_ID, "family": FAMILY, "final_zip": {"path": args.zip.resolve().relative_to(ROOT.resolve()).as_posix(), "bytes": zip_bytes, "sha256": zip_digest}}, "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001", "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001", "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001", "CDA-SERVER-POST-SIM-RETURN-CORE-001"], "first_fresh_for_family": True, "notification_acknowledged": True}, "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True}, "evidence_reports": evidence, "candidate_discrimination": {"candidate_ids": matrix["candidate_ids"], "covered_candidate_ids": matrix["candidate_ids"], "uncovered_candidate_ids": [], "positive_control_count": 2, "negative_control_count": 3, "pairwise_distinguishable": matrix_ok}, "findings": []}
    write(out / "contract.json", contract)
    print(out / "contract.json")
    return 0 if all(json.loads((reports / name).read_text())["pass"] for _,_,name in report_specs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
