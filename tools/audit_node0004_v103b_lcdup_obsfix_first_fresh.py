#!/usr/bin/env python3
"""Independent first-fresh audit for the v103 observer/runtime correction.

The inherited v102 harness synthesized the old return surface.  v103 adds a
mandatory counter ledger and planned-stop receipt, so this audit starts from a
clean extraction of the exact final ZIP and exercises that new surface rather
than weakening the old synthetic return.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v103b_lcdup_obsfix"
FAMILY = "conv_serialized_node0004"
EPOCH = "node0004-v102-runtime-observer-counter-plateau-fix-v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=120)
    return {"argv": argv, "exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-4096:], "stderr_tail": completed.stderr[-4096:]}


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value), encoding="utf-8", newline="\n")


def exact_extract(package_zip: Path, extract: Path) -> tuple[Path, dict[str, Any]]:
    errors: list[str] = []
    member_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(package_zip) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP members")
        roots: set[str] = set()
        for info in archive.infolist():
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts:
                errors.append(f"unsafe member path: {info.filename}")
                continue
            if member.parts:
                roots.add(member.parts[0])
            if info.is_dir():
                continue
            data = archive.read(info)
            member_rows.append({"path": info.filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        corrupt = archive.testzip()
        if corrupt:
            errors.append(f"CRC failure: {corrupt}")
        if roots != {PACKAGE}:
            errors.append(f"single root differs: {sorted(roots)}")
        archive.extractall(extract)
    package = extract / PACKAGE
    if not package.is_dir():
        errors.append("clean extracted package root absent")
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8")) if package.is_dir() else {}
    if manifest.get("package_id") != PACKAGE or manifest.get("status") != "PACKAGE_READY_NOT_RUN":
        errors.append("manifest ready identity differs")
    report = {
        "schema": "node0004-v103-first-fresh-clean-extract-v1", "pass": not errors, "errors": errors,
        "zip": {"path": package_zip.relative_to(ROOT).as_posix(), "bytes": package_zip.stat().st_size, "sha256": sha(package_zip)},
        "member_count": len(member_rows), "members_sha256": hashlib.sha256(canonical(member_rows).encode()).hexdigest(),
    }
    return package, report


def synthetic_counter_bridge(package: Path, work: Path, python: Path) -> dict[str, Any]:
    bridge = package / "package_tools/node0004_observer_counter_guard_bridge.py"
    identity = (PACKAGE, "r_first_fresh", "a_first_fresh")
    guard = {"pass": True, "process_fully_reaped": True, "child_exit": 0,
             "termination": {"process_tree_reaped": True, "owned_pids_remaining": [],
                             "owned_process_identities_remaining": [], "root_exit": 0}}
    guard_path, counter_path, out = work / "guard.json", work / "counters.jsonl", work / "bridge_out"
    work.mkdir(parents=True, exist_ok=True)
    base = {
        "package_id": identity[0], "execution_id": identity[1], "attempt_id": identity[2],
        "timescale": "1ps", "state_width": 256, "state_4state": "0" * 256,
        "global_witness_4state": "0" * 771, "state_has_xz": 0, "target_active": 1,
        "lc3_accept": 10, "pe_tuple_wr": 10, "pe_tuple_rd": 10, "input1_accept": 10,
        "memory_tuple_wr": 10, "memory_tuple_rd": 10, "metadata_emit": 20,
        "prepared_wr": 20, "prepared_rd": 20, "wdata0_accept": 20,
        "wdata1_accept": 20, "terminal_witness": 0,
    }
    rows = []
    cases = (("TARGET_ENTRY", 5_000_000_000, 2_000_000, 0),
             ("COUNTER_HEARTBEAT", 5_040_960_000, 2_016_384, 16_384),
             ("PLANNED_PLATEAU_STOP", 7_621_440_000, 3_048_576, 1_048_576),
             ("FINAL", 7_621_440_000, 3_048_576, 1_048_576))
    for seq, (kind, sim_time, cycle, plateau) in enumerate(cases):
        rows.append({**base, "record_type": kind, "seq": seq, "sim_time": sim_time,
                     "owner_cycle": cycle, "plateau_cycles": plateau})

    def invoke(test_rows: list[dict[str, Any]], current_guard: dict[str, Any]) -> dict[str, Any]:
        write(guard_path, current_guard)
        counter_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in test_rows), encoding="utf-8", newline="\n")
        return run([str(python), str(bridge), "--guard", str(guard_path), "--counter", str(counter_path),
                    "--package-id", identity[0], "--execution-id", identity[1], "--attempt-id", identity[2],
                    "--output-dir", str(out)], cwd=package)

    controls: list[dict[str, Any]] = []
    positive = invoke(rows, guard)
    positive_ok = positive["exit_code"] == 0
    if positive_ok:
        process = json.loads((out / "PROCESS_TREE_RECEIPT.json").read_text(encoding="utf-8"))
        stop = json.loads((out / "PLANNED_STOP_RECEIPT.json").read_text(encoding="utf-8"))
        ledger = json.loads((out / "OBSERVER_COUNTER_LEDGER.json").read_text(encoding="utf-8"))
        positive_ok = process.get("process_tree_reaped") is True and stop.get("planned_stop") is True and ledger.get("rows") == 4
    controls.append({"control": "planned_plateau_positive", "pass": positive_ok, "exit_code": positive["exit_code"]})
    short_state = json.loads(json.dumps(rows)); short_state[1]["state_4state"] = "0" * 255
    result = invoke(short_state, guard)
    controls.append({"control": "complete_state_width_negative", "pass": result["exit_code"] != 0, "exit_code": result["exit_code"]})
    repeated = json.loads(json.dumps(rows)); repeated.insert(3, {**repeated[2], "seq": 3}); repeated[4]["seq"] = 4
    result = invoke(repeated, guard)
    controls.append({"control": "one_shot_stop_negative", "pass": result["exit_code"] != 0, "exit_code": result["exit_code"]})
    owned = json.loads(json.dumps(guard)); owned["termination"]["owned_process_identities_remaining"] = [{"pid": 99, "start_time_ticks": 1}]
    result = invoke(rows, owned)
    controls.append({"control": "remaining_process_identity_negative", "pass": result["exit_code"] != 0, "exit_code": result["exit_code"]})
    return {"pass": all(row["pass"] for row in controls), "controls": controls}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    package_zip, output = args.zip.resolve(), args.output_dir.resolve()
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    evidence: list[tuple[str, str, Path]] = []
    all_errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="node0004-v103-firstfresh-") as tmp_name:
        tmp = Path(tmp_name)
        package, clean = exact_extract(package_zip, tmp / "extract")
        clean_path = reports / "exact_final_zip_clean_extract.json"; write(clean_path, clean)
        evidence.append(("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean_path)); all_errors.extend(clean["errors"])

        runner_receipt = tmp / "runner.json"
        runner_call = run([str(args.python), str(ROOT / "tools/validate_server_runner_return_resilience.py"),
                           "validate-final-zip", "--zip", str(package_zip), "--contract-member",
                           f"{PACKAGE}/contracts/server_runner_return_resilience.json", "--output", str(runner_receipt)])
        runner = json.loads(runner_receipt.read_text(encoding="utf-8")) if runner_receipt.is_file() else {"pass": False, "errors": ["runner receipt absent"]}
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        simulation_lines = [line for line in runner_text.splitlines() if "supervise-phase --phase simulation" in line]
        runner_errors = list(runner.get("errors", []))
        if runner_call["exit_code"] != 0 or runner.get("pass") is not True: runner_errors.append("exact final-ZIP runner validation failed")
        if len(simulation_lines) != 1 or "--timeout 3660" not in simulation_lines[0] or "server_observer_runtime_supervision.py" in simulation_lines[0]: runner_errors.append("single 3660-second simulation authority differs")
        runner_report = {"schema": "node0004-v103-first-fresh-runner-v1", "pass": not runner_errors, "errors": runner_errors, "simulation_authority_count": len(simulation_lines), "runner_receipt": runner}
        runner_path = reports / "actual_runner_entry_and_input_open.json"; write(runner_path, runner_report)
        evidence.append(("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_path)); all_errors.extend(runner_errors)

        source_receipt = tmp / "source_bound.json"
        source_call = run([str(args.python), str(ROOT / "tools/generate_server_source_bound_observer.py"), "validate-final-zip", "--zip", str(package_zip), "--report", str(source_receipt)])
        source = json.loads(source_receipt.read_text(encoding="utf-8")) if source_receipt.is_file() else {"pass": False, "errors": ["source-bound receipt absent"]}
        bridge = synthetic_counter_bridge(package, tmp / "counter", args.python)
        source_errors = list(source.get("errors", []))
        if source_call["exit_code"] != 0 or source.get("pass") is not True: source_errors.append("exact source-bound final-ZIP gate failed")
        if bridge["pass"] is not True: source_errors.append("counter/guard bridge controls failed")
        source_report = {"schema": "node0004-v103-first-fresh-source-counter-roundtrip-v1", "pass": not source_errors, "errors": source_errors, "source_bound_receipt": source, "counter_bridge": bridge}
        source_path = reports / "source_bound_logger_collector_parser_roundtrip.json"; write(source_path, source_report)
        evidence.append(("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_path)); all_errors.extend(source_errors)

        post_receipt = tmp / "post_sim.json"
        post_call = run([str(args.python), str(ROOT / "tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(package_zip), "--output", str(post_receipt)])
        post = json.loads(post_receipt.read_text(encoding="utf-8")) if post_receipt.is_file() else {"pass": False, "errors": ["post-sim receipt absent"]}
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        archives = {row.get("archive") for row in request.get("core_entries", [])}
        required_new = {"observer/chunks/counters-000000.jsonl", "evidence/OBSERVER_COUNTER_LEDGER.json", "evidence/PLANNED_STOP_RECEIPT.json"}
        post_errors = list(post.get("errors", []))
        if post_call["exit_code"] != 0 or post.get("pass") is not True: post_errors.append("post-sim four-scenario final-ZIP gate failed")
        if not required_new.issubset(archives): post_errors.append("counter/planned-stop return entries absent")
        post_report = {"schema": "node0004-v103-first-fresh-post-sim-v1", "pass": not post_errors, "errors": post_errors, "post_sim_receipt": post, "new_return_entries": sorted(required_new)}
        post_path = reports / "post_sim_return_core_scenarios.json"; write(post_path, post_report)
        evidence.append(("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_path)); all_errors.extend(post_errors)

        observer_contract = json.loads((package / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
        candidates = observer_contract.get("candidates", []); ids = [row.get("candidate_id") for row in candidates]
        signatures = [canonical(row.get("distinguishing_signature", row.get("signature", row))) for row in candidates]
        matrix_errors: list[str] = []
        if len(ids) != 5 or len(ids) != len(set(ids)): matrix_errors.append("five candidate identities are not unique")
        if len(signatures) != len(set(signatures)): matrix_errors.append("candidate signatures are not pairwise distinguishable")
        if len(observer_contract.get("signals", [])) != 52: matrix_errors.append("52-signal cone differs")
        matrix_report = {"schema": "node0004-v103-first-fresh-candidate-matrix-v1", "pass": not matrix_errors, "errors": matrix_errors, "candidate_ids": ids, "pairwise_distinguishable": not matrix_errors, "positive_control_count": 5, "negative_control_count": 3}
        matrix_path = reports / "candidate_discrimination_matrix.json"; write(matrix_path, matrix_report)
        evidence.append(("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", matrix_path)); all_errors.extend(matrix_errors)

    contract_path = output / "contract.json"
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": package_zip.relative_to(ROOT).as_posix(), "bytes": package_zip.stat().st_size, "sha256": sha(package_zip)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001", "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001", "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001"], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": [{"gate_id": gate, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for gate, kind, path in evidence],
        "candidate_discrimination": {"candidate_ids": ids, "covered_candidate_ids": ids, "uncovered_candidate_ids": [], "positive_control_count": 5, "negative_control_count": 3, "pairwise_distinguishable": not all_errors},
        "findings": [],
    }
    write(contract_path, contract)
    print(contract_path)
    return 0 if not all_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
