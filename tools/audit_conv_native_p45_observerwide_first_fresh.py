#!/usr/bin/env python3
"""Independent exact-ZIP first-fresh audit for native Conv p45 observer-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p45_obswide"
FAMILY = "conv_native_four_lane"
EPOCH = "observer-only-post-sim-conjunction-fix-v1"
RULE_IDS = [
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": completed.returncode, "stdout_tail": completed.stdout[-4096:], "stderr_tail": completed.stderr[-4096:]}


def safe_extract(source: Path, destination: Path) -> tuple[Path, list[str]]:
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        roots: set[str] = set()
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or "\\" in name:
                raise ValueError(f"unsafe ZIP member: {name}")
            if member.parts:
                roots.add(member.parts[0])
        if roots != {PACKAGE_ID}:
            raise ValueError(f"root mismatch: {sorted(roots)}")
        archive.extractall(destination)
    return destination / PACKAGE_ID, names


def member_map(package: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.name == "package_manifest.json":
            continue
        result[path.relative_to(package).as_posix()] = {"size_bytes": path.stat().st_size, "sha256": digest(path)}
    return result


def runtime_layout_case(package: Path, python: Path, root: Path) -> dict[str, Any]:
    server = root / "server"
    (server / "install").mkdir(parents=True)
    tool = package / "package_tools/server_package_runtime_layout.py"
    base = [str(python), str(tool), "prepare", "--server-root", str(server.resolve()), "--package-id", PACKAGE_ID, "--install-name", PACKAGE_ID, "--attempt", "a_repeat", "--format", "json"]
    first = run(base)
    foreign_cfg = server / "install/cfg_pkg/foreign-family/keep.txt"
    foreign_run = server / "install/codex_runs/foreign-family/keep.txt"
    foreign_cfg.parent.mkdir(parents=True, exist_ok=True)
    foreign_run.parent.mkdir(parents=True, exist_ok=True)
    foreign_cfg.write_text("foreign\n", encoding="utf-8")
    foreign_run.write_text("foreign\n", encoding="utf-8")
    owned_cfg = server / f"install/cfg_pkg/{PACKAGE_ID}/stale.txt"
    owned_run = server / f"install/codex_runs/{PACKAGE_ID}/a_repeat/stale.txt"
    owned_cfg.write_text("stale\n", encoding="utf-8")
    owned_run.write_text("stale\n", encoding="utf-8")
    second = run(base)
    fresh = run(base[:-3] + ["a_fresh", "--format", "json"])
    checks = {
        "first_prepare": first["exit_code"] == 0,
        "repeat_prepare": second["exit_code"] == 0,
        "fresh_attempt_prepare": fresh["exit_code"] == 0,
        "owned_cfg_stale_reset": not owned_cfg.exists(),
        "owned_attempt_stale_reset": not owned_run.exists(),
        "foreign_cfg_preserved": foreign_cfg.read_text(encoding="utf-8") == "foreign\n",
        "foreign_run_preserved": foreign_run.read_text(encoding="utf-8") == "foreign\n",
    }
    return {"pass": all(checks.values()), "checks": checks, "invocations": [first, second, fresh]}


def event_value(width: int, index: int) -> str:
    if index == 1:
        return "x" + "0" * (width - 1)
    if index == 2:
        return "z" + "1" * (width - 1)
    return format(index & ((1 << min(width, 16)) - 1), f"0{width}b")[-width:]


def parser_return_case(package: Path, python: Path, case_root: Path, contract: dict[str, Any], *, case_name: str, exit_code: int, signal: str, timed_out: bool) -> dict[str, Any]:
    execution = f"r_firstfresh_{case_name}"
    attempt = f"a_{case_name}"
    work = case_root / case_name
    return_root = work / f"{PACKAGE_ID}_return"
    evidence = return_root / "evidence"
    observer_out = evidence / "observer"
    chunk = return_root / "observer/chunks/events-000000.jsonl"
    chunk.parent.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for index, signal_row in enumerate(contract["signals"]):
        width = int(signal_row["width_bits"])
        rows.append({
            "record_type": "EVENT", "package_id": PACKAGE_ID, "execution_id": execution,
            "attempt_id": attempt, "seq": len(rows), "sim_time": 0, "timescale": "1ps",
            "signal_id": signal_row["signal_id"], "width_bits": width, "value_4state": event_value(width, index),
        })
    rows.append({"record_type": "HEARTBEAT", "package_id": PACKAGE_ID, "execution_id": execution, "attempt_id": attempt, "seq": len(rows), "sim_time": 1000, "timescale": "1ps", "signal_id": "__heartbeat__", "width_bits": 1, "value_4state": "0"})
    chunk.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")
    process_receipt = evidence / "PROCESS_TREE_RECEIPT.json"
    heartbeat_log = evidence / "supervisor_heartbeat.jsonl"
    actual_argv = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    write_json(process_receipt, {"schema": "server-observer-process-tree-receipt-v1", "package_id": PACKAGE_ID, "execution_id": execution, "attempt_id": attempt, "process_tree_reaped": True, "owned_pids_remaining": []})
    heartbeat_log.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in ({"simulation_time": 0, "timescale": "1ps"}, {"simulation_time": 1000, "timescale": "1ps"})), encoding="utf-8", newline="\n")
    write_json(actual_argv, {"schema": "server-observer-actual-argv-v1", "package_id": PACKAGE_ID, "execution_id": execution, "attempt_id": attempt, "source_identity_status": "COMPLETE", "compile_argv": contract["execution"]["compile_argv"], "sim_argv": contract["execution"]["sim_argv"]})
    parser_call = run([
        str(python), str(package / "package_tools/node0004_observerwide_event_parser.py"),
        "--contract", str(package / "contracts/observer_only_wide_causal_contract.json"),
        "--chunk", str(chunk), "--package-id", PACKAGE_ID, "--execution-id", execution,
        "--attempt-id", attempt, "--exit-code", str(exit_code), "--signal", signal,
        "--timed-out", str(timed_out).lower(), "--simulation-started", "true",
        "--process-receipt", str(process_receipt), "--heartbeat-log", str(heartbeat_log),
        "--actual-argv", str(actual_argv), "--output-dir", str(observer_out),
    ])
    manifest_path = return_root / "RETURN_CORE_MANIFEST.json"
    members = sorted(f"{PACKAGE_ID}_return/" + path.relative_to(return_root).as_posix() for path in return_root.rglob("*") if path.is_file() and path != manifest_path)
    write_json(manifest_path, {"schema": "server-post-sim-return-core-manifest-v1", "package_id": PACKAGE_ID, "execution_id": execution, "attempt_id": attempt, "members": members})
    return_zip = work / f"{case_name}_return.zip"
    with zipfile.ZipFile(return_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(item for item in return_root.rglob("*") if item.is_file()):
            archive.write(path, f"{PACKAGE_ID}_return/" + path.relative_to(return_root).as_posix())
    validation = work / "return_validation.json"
    validate_call = run([str(python), str(ROOT / "tools/validate_server_observer_only_wide_causal.py"), "validate-return", "--zip", str(return_zip), "--contract", str(package / "contracts/observer_only_wide_causal_contract.json"), "--output", str(validation)])
    report = json.loads(validation.read_text(encoding="utf-8"))
    final_rows = [json.loads(line) for line in chunk.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"case": case_name, "parser_exit": parser_call["exit_code"], "validator_exit": validate_call["exit_code"], "pass": report.get("pass"), "diagnostic_status": report.get("diagnostic_status"), "event_summary": report.get("event_summary"), "errors": report.get("errors", []), "four_state_xz_count": sum(1 for row in final_rows if any(char in str(row.get("value_4state", "")).lower() for char in ("x", "z")))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    output = args.output_dir.resolve()
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    zip_sha = digest(zip_path)
    with tempfile.TemporaryDirectory(prefix="native-p45-firstfresh-") as temporary:
        temp = Path(temporary)
        package, names = safe_extract(zip_path, temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        helper = package / "package_tools/server_post_sim_return.py"
        preflight = run([str(args.python), str(package / "package_tools/node0004_assumed_hardware_server_runtime.py"), "preflight", "--package-root", str(package)])
        clean_checks = {
            "manifest_member_map_exact": manifest.get("files") == member_map(package),
            "single_root": all(PurePosixPath(name).parts[0] == PACKAGE_ID for name in names),
            "no_wave_members": not any(name.lower().endswith((".vpd", ".fsdb", ".vcd", ".fst")) for name in names),
            "canonical_post_sim_helper_exact": helper.read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "post_sim_request_inert": request.get("package_id") == PACKAGE_ID and request.get("waveform_discovery") is None,
            "conjunction_epoch_bound": manifest.get("activation_epoch") == EPOCH,
            "package_local_preflight": preflight["exit_code"] == 0,
        }
        clean = {"schema": "conv-native-p45-exact-final-zip-clean-extract-v1", "pass": all(clean_checks.values()), "errors": [key for key, passed in clean_checks.items() if not passed], "zip_sha256": zip_sha, "member_count": len(names), "checks": clean_checks, "preflight": preflight}
        write_json(reports / "exact_final_zip_clean_extract.json", clean)

        runner_validation = temp / "runner_validation.json"
        runner_call = run([str(args.python), str(ROOT / "tools/validate_server_runner_return_resilience.py"), "validate-final-zip", "--zip", str(zip_path), "--contract-member", f"{PACKAGE_ID}/server_runner_return_resilience_contract.json", "--output", str(runner_validation)])
        runner_value = json.loads(runner_validation.read_text(encoding="utf-8"))
        layout = runtime_layout_case(package, args.python, temp / "layout")
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        helper_text = helper.read_text(encoding="utf-8")
        runner_checks = {
            "runner_resilience_exact_zip": runner_call["exit_code"] == 0 and runner_value.get("pass") is True,
            "runtime_layout_repeat": layout["pass"] is True,
            "supervisor_invoked": "server_observer_runtime_supervision.py" in runner_text and "--timeout 43200" in runner_text,
            "all_exit_trap_armed": all(token in runner_text for token in ("trap 'finalize $?' EXIT", "trap 'on_signal HUP 129' HUP", "trap 'on_signal INT 130' INT", "trap 'on_signal TERM 143' TERM")),
            "unique_atomic_return": "return_tag=\"r$(date -u +%s%N)_$$\"" in runner_text and "os.replace" in helper_text,
            "dump_zero_exact": all(token in runner_text for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
        }
        runner_report = {"schema": "conv-native-p45-exact-runner-input-v1", "pass": all(runner_checks.values()), "errors": [key for key, passed in runner_checks.items() if not passed], "zip_sha256": zip_sha, "checks": runner_checks, "runtime_layout": layout}
        write_json(reports / "actual_runner_entry_and_input_open.json", runner_report)

        hdl_path = temp / "hdl.json"
        hdl_call = run([str(args.python), str(ROOT / "tools/validate_conv_native_four_lane_p45_observerwide_hdl.py"), "--zip", str(zip_path), "--package-id", PACKAGE_ID, "--iverilog", str(args.iverilog), "--output", str(hdl_path)])
        hdl = json.loads(hdl_path.read_text(encoding="utf-8"))
        exit_cases = {
            name: parser_return_case(package, args.python, temp / "cases", contract, case_name=name, exit_code=code, signal=signal, timed_out=timeout)
            for name, code, signal, timeout in (
                ("natural", 0, "NONE", False), ("timeout", 124, "NONE", True),
                ("nonzero", 9, "NONE", False), ("hup", 129, "HUP", False),
                ("int", 130, "INT", False), ("term", 143, "TERM", False),
            )
        }
        sys.path.insert(0, str(ROOT / "tools"))
        import validate_server_observer_only_wide_causal as observer_gate
        soft_budget = observer_gate.evaluate_soft_budget(100_000_001, 100_000_001)
        natural = exit_cases["natural"]
        source_checks = {
            "full_hdl_positive_negative": hdl_call["exit_code"] == 0 and hdl.get("pass") is True,
            "natural_roundtrip": natural.get("pass") is True,
            "six_exit_roundtrip": all(row.get("pass") is True and (name == "natural" or row.get("event_summary", {}).get("partial_exit_count", 0) >= 1) for name, row in exit_cases.items()),
            "all_26_roles": len(contract.get("role_coverage", [])) == 26,
            "all_4state_preserved": natural.get("four_state_xz_count", 0) >= 2,
            "over_soft_limit_warning_only": soft_budget.get("soft_limit_exceeded") is True and soft_budget.get("coverage_reduced") is False and soft_budget.get("hard_limit_bytes") is None,
        }
        source_report = {"schema": "conv-native-p45-source-bound-observer-roundtrip-v1", "pass": all(source_checks.values()), "errors": [key for key, passed in source_checks.items() if not passed], "zip_sha256": zip_sha, "checks": source_checks, "exit_cases": exit_cases, "soft_budget": soft_budget}
        write_json(reports / "source_bound_logger_collector_parser_roundtrip.json", source_report)

        post_path = reports / "post_sim_return_core_scenarios.json"
        post_call = run([str(args.python), str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(zip_path), "--output", str(post_path)])
        post = json.loads(post_path.read_text(encoding="utf-8"))
        if post_call["exit_code"] != 0 or post.get("pass") is not True:
            post.setdefault("errors", []).append("independent exact-ZIP post-sim invocation failed")
            post["pass"] = False
            write_json(post_path, post)

        candidate_ids = [row["candidate_id"] for row in contract["candidates"]]
        signatures = [json.dumps(row["signature"], sort_keys=True) for row in contract["candidates"]]
        negative_results: list[dict[str, Any]] = []
        for name, mutate in (
            ("conflicting_dump", lambda value: value["execution"]["sim_argv"].append("DUMP_VCD=1")),
            ("derived_only_signal", lambda value: value["signals"][0].__setitem__("source_binding", "DERIVED_EXPECTED")),
            ("duplicate_candidate_signature", lambda value: value["candidates"][1].__setitem__("signature", value["candidates"][0]["signature"])),
        ):
            value = json.loads(json.dumps(contract))
            mutate(value)
            result = observer_gate.validate_contract(value)
            negative_results.append({"case": name, "rejected": result.get("pass") is False, "errors": result.get("errors", [])})
        matrix_checks = {
            "candidate_ids_unique": len(candidate_ids) == len(set(candidate_ids)),
            "signatures_pairwise_distinguishable": len(signatures) == len(set(signatures)),
            "positive_natural": natural.get("pass") is True,
            "positive_partial": exit_cases["term"].get("pass") is True,
            "negative_controls_rejected": all(row["rejected"] for row in negative_results),
        }
        matrix = {"schema": "conv-native-p45-candidate-discrimination-matrix-v1", "pass": all(matrix_checks.values()), "errors": [key for key, passed in matrix_checks.items() if not passed], "zip_sha256": zip_sha, "candidate_ids": candidate_ids, "checks": matrix_checks, "positive_controls": list(exit_cases.values()), "negative_controls": negative_results}
        write_json(reports / "candidate_discrimination_matrix.json", matrix)

    specs = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", "exact_final_zip_clean_extract.json"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", "actual_runner_entry_and_input_open.json"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", "source_bound_logger_collector_parser_roundtrip.json"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", "post_sim_return_core_scenarios.json"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", "candidate_discrimination_matrix.json"),
    ]
    evidence: list[dict[str, Any]] = []
    all_pass = True
    for gate_id, kind, name in specs:
        path = reports / name
        value = json.loads(path.read_text(encoding="utf-8"))
        all_pass = all_pass and value.get("pass") is True
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)})
    contract_value = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE_ID, "family": FAMILY, "final_zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": zip_sha}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": RULE_IDS, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidate_ids, "covered_candidate_ids": candidate_ids, "uncovered_candidate_ids": [], "positive_control_count": 6, "negative_control_count": 3, "pairwise_distinguishable": all_pass},
        "findings": [],
    }
    write_json(output / "contract.json", contract_value)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
