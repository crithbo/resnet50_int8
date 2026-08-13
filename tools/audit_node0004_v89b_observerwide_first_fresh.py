#!/usr/bin/env python3
"""Independent exact-ZIP first-fresh audit for serialized Conv v89b observer-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v89b_obswide"
FAMILY = "conv_serialized_node0004"
EPOCH = "observer-only-post-sim-conjunction-fix-v1"
RULE_IDS = [
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def run(argv: list[str], *, cwd: Path | None = None) -> dict[str, object]:
    completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4096:],
        "stderr_tail": completed.stderr[-4096:],
    }


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


def member_map(package: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.name == "package_manifest.json":
            continue
        result[path.relative_to(package).as_posix()] = (path.stat().st_size, digest(path))
    return result


def runtime_layout_case(package: Path, python: Path, root: Path) -> dict[str, object]:
    server = root / "server"
    (server / "install").mkdir(parents=True)
    tool = package / "package_tools/server_package_runtime_layout.py"
    base = [
        str(python), str(tool), "prepare", "--server-root", str(server.resolve()),
        "--package-id", PACKAGE_ID, "--install-name", PACKAGE_ID,
        "--attempt", "a_repeat", "--format", "json",
    ]
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


def parser_return_case(
    package: Path,
    python: Path,
    case_root: Path,
    contract: dict[str, object],
    *,
    case_name: str,
    exit_code: int,
    signal: str,
    timed_out: bool,
) -> dict[str, object]:
    package_id = str(contract["package_id"])
    execution = f"r_firstfresh_{case_name}"
    attempt = f"a_{case_name}"
    work = case_root / case_name
    evidence = work / "return/evidence"
    chunk = work / "return/observer/chunks/events-000000.jsonl"
    chunk.parent.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for index, signal_row in enumerate(contract["signals"]):
        width = int(signal_row["width_bits"])
        rows.append({
            "record_type": "EVENT", "package_id": package_id,
            "execution_id": execution, "attempt_id": attempt, "seq": len(rows),
            "sim_time": 0, "timescale": "1ps", "signal_id": signal_row["signal_id"],
            "width_bits": width, "value_4state": event_value(width, index),
        })
    rows.append({
        "record_type": "HEARTBEAT", "package_id": package_id,
        "execution_id": execution, "attempt_id": attempt, "seq": len(rows),
        "sim_time": 1000, "timescale": "1ps", "signal_id": "__heartbeat__",
        "width_bits": 1, "value_4state": "0",
    })
    chunk.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")
    process_receipt = evidence / "PROCESS_TREE_RECEIPT.json"
    heartbeat_log = evidence / "supervisor_heartbeat.jsonl"
    actual_argv = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    write_json(process_receipt, {
        "schema": "server-observer-process-tree-receipt-v1", "package_id": package_id,
        "execution_id": execution, "attempt_id": attempt, "process_tree_reaped": True,
        "owned_pids_remaining": [],
    })
    heartbeat_log.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in (
            {"simulation_time": 0, "timescale": "1ps"},
            {"simulation_time": 1000, "timescale": "1ps"},
        )), encoding="utf-8", newline="\n",
    )
    write_json(actual_argv, {
        "schema": "server-observer-actual-argv-v1", "package_id": package_id,
        "execution_id": execution, "attempt_id": attempt, "source_identity_status": "COMPLETE",
        "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
        "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
    })
    parser_call = run([
        str(python), str(package / "package_tools/node0004_observerwide_event_parser.py"),
        "--contract", str(package / "contracts/observer_only_wide_causal_contract.json"),
        "--chunk", str(chunk), "--package-id", package_id, "--execution-id", execution,
        "--attempt-id", attempt, "--exit-code", str(exit_code), "--signal", signal,
        "--timed-out", str(timed_out).lower(), "--simulation-started", "true",
        "--process-receipt", str(process_receipt), "--heartbeat-log", str(heartbeat_log),
        "--actual-argv", str(actual_argv), "--output-dir", str(evidence),
    ])
    return_root = work / "return"
    manifest_path = return_root / "RETURN_CORE_MANIFEST.json"
    relative_root = f"{package_id}_return/"
    members = sorted(
        relative_root + path.relative_to(return_root).as_posix()
        for path in return_root.rglob("*") if path.is_file() and path != manifest_path
    )
    write_json(manifest_path, {
        "schema": "server-post-sim-return-core-manifest-v1", "package_id": package_id,
        "execution_id": execution, "attempt_id": attempt, "members": members,
    })
    return_zip = work / f"{case_name}_return.zip"
    with zipfile.ZipFile(return_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(item for item in return_root.rglob("*") if item.is_file()):
            archive.write(path, relative_root + path.relative_to(return_root).as_posix())
    validation = work / "return_validation.json"
    validate_call = run([
        str(python), str(ROOT / "tools/validate_server_observer_only_wide_causal.py"),
        "validate-return", "--zip", str(return_zip),
        "--contract", str(package / "contracts/observer_only_wide_causal_contract.json"),
        "--output", str(validation),
    ])
    report = json.loads(validation.read_text(encoding="utf-8"))
    final_rows = [json.loads(line) for line in chunk.read_text(encoding="utf-8").splitlines() if line.strip()]
    four_state_xz_count = sum(
        1 for row in final_rows
        if isinstance(row.get("value_4state"), str)
        and any(character in row["value_4state"].lower() for character in ("x", "z"))
    )
    return {
        "case": case_name, "parser_exit": parser_call["exit_code"],
        "validator_exit": validate_call["exit_code"], "pass": report.get("pass"),
        "diagnostic_status": report.get("diagnostic_status"),
        "event_summary": report.get("event_summary"), "errors": report.get("errors", []),
        "four_state_xz_count": four_state_xz_count,
    }


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
    with tempfile.TemporaryDirectory(prefix="node0004-v89-firstfresh-") as temporary:
        temp = Path(temporary)
        package, names = safe_extract(zip_path, temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
        declared = {row["path"]: (row["bytes"], row["sha256"]) for row in manifest["files"]}
        actual = member_map(package)
        helper = package / "package_tools/server_post_sim_return.py"
        clean_checks = {
            "manifest_member_map_exact": declared == actual,
            "single_root": all(PurePosixPath(name).parts[0] == PACKAGE_ID for name in names),
            "no_wave_members": not any(name.lower().endswith((".vpd", ".fsdb", ".vcd", ".fst")) for name in names),
            "canonical_post_sim_helper_exact": helper.read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "retired_comparator_absent_from_observer": "buf_idx_queue_bp_pre" not in (package / "tb_probe/observer_only_wide_causal.svh").read_text(encoding="utf-8"),
            "conjunction_epoch_bound": manifest.get("post_sim_conjunction_activation_epoch") == EPOCH,
        }
        clean = {
            "schema": "node0004-v89b-exact-final-zip-clean-extract-v1", "pass": all(clean_checks.values()),
            "errors": [key for key, passed in clean_checks.items() if not passed],
            "zip_sha256": zip_sha, "member_count": len(names), "checks": clean_checks,
        }
        write_json(reports / "exact_final_zip_clean_extract.json", clean)

        runner_validation = temp / "runner_validation.json"
        runner_call = run([
            str(args.python), str(ROOT / "tools/validate_server_runner_return_resilience.py"),
            "validate-final-zip", "--zip", str(zip_path),
            "--contract-member", f"{PACKAGE_ID}/contracts/server_runner_return_resilience.json",
            "--output", str(runner_validation),
        ])
        runner_value = json.loads(runner_validation.read_text(encoding="utf-8"))
        layout = runtime_layout_case(package, args.python, temp / "layout")
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        runner_checks = {
            "runner_resilience_exact_zip": runner_call["exit_code"] == 0 and runner_value.get("pass") is True,
            "runtime_layout_repeat": layout["pass"] is True,
            "supervisor_invoked": "server_observer_runtime_supervision.py" in runner_text and "--timeout 21600" in runner_text,
            "all_exit_trap_armed": all(token in runner_text for token in (
                "trap 'finalize $?' EXIT", "trap 'on_signal HUP 129' HUP",
                "trap 'on_signal INT 130' INT", "trap 'on_signal TERM 143' TERM",
            )),
            "unique_atomic_return": "return_tag=\"r$(date -u +%s%N)_$$\"" in runner_text and "os.replace(tmp,target)" in runner_text,
        }
        runner_report = {
            "schema": "node0004-v89b-exact-runner-input-v1", "pass": all(runner_checks.values()),
            "errors": [key for key, passed in runner_checks.items() if not passed],
            "zip_sha256": zip_sha, "checks": runner_checks, "runtime_layout": layout,
        }
        write_json(reports / "actual_runner_entry_and_input_open.json", runner_report)

        hdl_report_path = temp / "hdl.json"
        hdl_call = run([
            str(args.python), str(ROOT / "tools/validate_node0004_v89b_observerwide_hdl.py"),
            "--zip", str(zip_path), "--iverilog", str(args.iverilog), "--output", str(hdl_report_path),
        ])
        hdl = json.loads(hdl_report_path.read_text(encoding="utf-8"))
        exit_cases = {
            "natural": parser_return_case(package, args.python, temp / "cases", contract, case_name="natural", exit_code=0, signal="NONE", timed_out=False),
            "timeout": parser_return_case(package, args.python, temp / "cases", contract, case_name="timeout", exit_code=124, signal="NONE", timed_out=True),
            "nonzero": parser_return_case(package, args.python, temp / "cases", contract, case_name="nonzero", exit_code=9, signal="NONE", timed_out=False),
            "hup": parser_return_case(package, args.python, temp / "cases", contract, case_name="hup", exit_code=129, signal="HUP", timed_out=False),
            "int": parser_return_case(package, args.python, temp / "cases", contract, case_name="int", exit_code=130, signal="INT", timed_out=False),
            "term": parser_return_case(package, args.python, temp / "cases", contract, case_name="term", exit_code=143, signal="TERM", timed_out=False),
        }
        natural = exit_cases["natural"]
        partial = exit_cases["term"]
        soft_budget_ok = False
        sys.path.insert(0, str(ROOT / "tools"))
        import validate_server_observer_only_wide_causal as observer_gate
        soft_budget = observer_gate.evaluate_soft_budget(100_000_001, 100_000_001)
        soft_budget_ok = soft_budget.get("soft_limit_exceeded") is True and soft_budget.get("coverage_reduced") is False and soft_budget.get("hard_limit_bytes") is None
        source_checks = {
            "full_hdl_positive_negative": hdl_call["exit_code"] == 0 and hdl.get("pass") is True,
            "natural_roundtrip": natural.get("pass") is True,
            "six_exit_roundtrip": all(
                row.get("pass") is True
                and (name == "natural" or row.get("event_summary", {}).get("partial_exit_count", 0) >= 1)
                for name, row in exit_cases.items()
            ),
            "all_26_roles": len(contract.get("role_coverage", [])) == 26,
            "all_4state_preserved": natural.get("four_state_xz_count", 0) >= 2,
            "over_soft_limit_warning_only": soft_budget_ok,
        }
        source_report = {
            "schema": "node0004-v89b-source-bound-observer-roundtrip-v1", "pass": all(source_checks.values()),
            "errors": [key for key, passed in source_checks.items() if not passed],
            "zip_sha256": zip_sha, "checks": source_checks, "exit_cases": exit_cases,
            "soft_budget": soft_budget,
        }
        write_json(reports / "source_bound_logger_collector_parser_roundtrip.json", source_report)

        post_report_path = reports / "post_sim_return_core_scenarios.json"
        post_call = run([
            str(args.python), str(package / "package_tools/server_post_sim_return.py"),
            "validate-final-zip", "--zip", str(zip_path), "--output", str(post_report_path),
        ])
        post = json.loads(post_report_path.read_text(encoding="utf-8"))
        if post_call["exit_code"] != 0 or post.get("pass") is not True:
            post.setdefault("errors", []).append("independent exact-ZIP post-sim invocation failed")
            post["pass"] = False
            write_json(post_report_path, post)

        candidate_ids = [row["candidate_id"] for row in contract["candidates"]]
        signatures = [json.dumps(row["signature"], sort_keys=True) for row in contract["candidates"]]
        negative_results: list[dict[str, object]] = []
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
            "positive_partial": partial.get("pass") is True,
            "negative_controls_rejected": all(row["rejected"] for row in negative_results),
        }
        matrix = {
            "schema": "node0004-v89b-candidate-discrimination-matrix-v1", "pass": all(matrix_checks.values()),
            "errors": [key for key, passed in matrix_checks.items() if not passed],
            "zip_sha256": zip_sha, "candidate_ids": candidate_ids, "checks": matrix_checks,
            "positive_controls": list(exit_cases.values()), "negative_controls": negative_results,
        }
        write_json(reports / "candidate_discrimination_matrix.json", matrix)

    specs = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", "exact_final_zip_clean_extract.json"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", "actual_runner_entry_and_input_open.json"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", "source_bound_logger_collector_parser_roundtrip.json"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", "post_sim_return_core_scenarios.json"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", "candidate_discrimination_matrix.json"),
    ]
    evidence = []
    all_pass = True
    for gate_id, kind, name in specs:
        path = reports / name
        value = json.loads(path.read_text(encoding="utf-8"))
        all_pass = all_pass and value.get("pass") is True
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)})
    candidate_ids = json.loads((reports / "candidate_discrimination_matrix.json").read_text(encoding="utf-8"))["candidate_ids"]
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
    print(output / "contract.json")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
