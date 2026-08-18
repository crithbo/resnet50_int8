#!/usr/bin/env python3
"""Independent current-epoch exact-final-ZIP first-fresh audit for QAdd v63."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
FAMILY = "qlinearadd_node0007"
EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
RULE = "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    return result.returncode, result.stdout, result.stderr


def sample(seq: int, cycles: int, sim_time: int, wall: int, **extra: object) -> dict:
    row = {
        "seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles, "sim_time_ticks": sim_time,
        "wall_seconds": wall, "vcd_bytes": 1000 + cycles, "non_clock_events": seq,
        "causal_progress_events": 1, "qualified_progress_counters": {"accept": 1, "write": 0},
        "causal_state_digest": "a" * 64, "global_progress_witness": {"global_accept": 1},
        "write_ok": True, "disk_space_ok": True, "quota_ok": True,
    }
    row.update(extra)
    return row


def request(rows: list[dict], started: bool = True) -> dict:
    return {
        "package_id": PACKAGE, "execution_id": "local-gate", "attempt_id": "synthetic",
        "started": started, "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64,
        "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64,
        "elaboration_sha256": "5" * 64, "candidate_catalog_complete": True, "unresolved_xz": False,
        "samples": rows, "flush": {"dumpoff": True, "dumpflush": True, "closed": True},
        "process_tree": {"term_sent": True, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True},
        "vcd_identity": {"path": "wave.vcd", "bytes": 1000, "sha256": "6" * 64, "header_valid": True, "timescale": "1ns", "catalog_complete": True, "transitions_complete": True, "xz_preserved": True, "return_allowlist_member": True} if started else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    output = args.output_dir.resolve()
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    zip_sha = digest(zip_path)
    with tempfile.TemporaryDirectory(prefix="qadd-v63-firstfresh-") as raw:
        temp = Path(raw)
        extract = temp / "extract"
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
            unsafe = [name for name in names if PurePosixPath(name.replace("\\", "/")).is_absolute() or ".." in PurePosixPath(name.replace("\\", "/")).parts]
            corrupt = archive.testzip()
            if roots != {PACKAGE} or unsafe or corrupt is not None:
                raise RuntimeError(f"unsafe exact ZIP: roots={roots}, unsafe={unsafe}, corrupt={corrupt}")
            archive.extractall(extract)
        package = extract / PACKAGE
        manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/server_diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        declared = {name: (row["size_bytes"], row["sha256"]) for name, row in manifest.get("files", {}).items()}
        actual = {path.relative_to(package).as_posix(): (path.stat().st_size, digest(path)) for path in sorted(package.rglob("*")) if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"}
        clean_checks = {
            "single_root": roots == {PACKAGE}, "crc": corrupt is None, "safe_members": not unsafe,
            "manifest_member_map_exact": declared == actual,
            "identity_exact": manifest.get("package_id") == PACKAGE and manifest.get("install_name") == PACKAGE and contract.get("package_id") == PACKAGE,
            "selected_mode": selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
            "no_runtime_wave_in_package": not any(name.lower().endswith((".vpd", ".fsdb", ".vcd", ".fst")) for name in names),
        }
        clean = {"schema": "qadd-v63-exact-final-zip-clean-extract-v1", "pass": all(clean_checks.values()), "errors": [name for name, ok in clean_checks.items() if not ok], "zip_sha256": zip_sha, "member_count": len(names), "checks": clean_checks}
        write(reports / "exact_final_zip_clean_extract.json", clean)

        harness_path = output / "runtime_layout_harness.json"
        harness_call = run([str(args.python), str(ROOT / "tools/prepare_qlinearadd_node0007_v63_runtime_layout_harness.py"), "--zip", str(zip_path), "--output", str(harness_path)])
        runner_path = temp / "runner.json"
        runner_call = run([str(args.python), str(ROOT / "tools/validate_server_runner_return_resilience.py"), "validate-final-zip", "--zip", str(zip_path), "--contract-member", f"{PACKAGE}/contracts/server_runner_return_resilience_contract.json", "--output", str(runner_path)])
        native_path = temp / "native.json"
        native_call = run([str(args.python), str(ROOT / "tools/validate_server_runtime_preflight_native_flow.py"), "--runner", str(package / "PREPARE_AND_RUN.sh"), "--output", str(native_path)])
        runner_gate = json.loads(runner_path.read_text(encoding="utf-8"))
        native_gate = json.loads(native_path.read_text(encoding="utf-8"))
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        runner_checks = {
            "harness_built": harness_call[0] == 0, "resilience_exact_zip": runner_call[0] == 0 and runner_gate.get("pass") is True,
            "native_flow_noninterference": native_call[0] == 0 and native_gate.get("pass") is True,
            "unique_production_launch": runner_text.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "zero_make_dump_argv": all(token in runner_text for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
            "package_tb_vcd_plusargs": "+CODEX_TB_VCD_ENABLE" in runner_text and "+CODEX_TB_VCD_PATH=" in runner_text,
            "all_exit_traps": all(token in runner_text for token in ("trap 'finalize $?' EXIT", "trap 'on_signal HUP 129' HUP", "trap 'on_signal INT 130' INT", "trap 'on_signal TERM 143' TERM")),
        }
        runner_report = {"schema": "qadd-v63-exact-runner-nativeflow-v1", "pass": all(runner_checks.values()), "errors": [name for name, ok in runner_checks.items() if not ok], "zip_sha256": zip_sha, "checks": runner_checks}
        write(reports / "actual_runner_entry_and_input_open.json", runner_report)

        vcd_path = temp / "vcd.json"
        hdl_path = temp / "hdl.json"
        source_path = temp / "source.json"
        vcd_call = run([str(args.python), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"), "--root", str(package), "--output", str(vcd_path)])
        hdl_call = run([str(args.python), str(ROOT / "tools/validate_qlinearadd_node0007_v63_tb_vcd_hdl.py"), "--zip", str(zip_path), "--iverilog", str(args.iverilog), "--output", str(hdl_path)])
        source_call = run([str(args.python), str(ROOT / "tools/validate_qlinearadd_node0007_v63_tb_vcd_source_bound.py"), "--zip", str(zip_path), "--source-root", str(ROOT / "NDP_copy01"), "--output", str(source_path)])
        vcd_gate = json.loads(vcd_path.read_text(encoding="utf-8")); hdl_gate = json.loads(hdl_path.read_text(encoding="utf-8")); source_gate = json.loads(source_path.read_text(encoding="utf-8"))
        sys.path.insert(0, str(ROOT / "tools"))
        from server_tb_vcd_runtime_supervision import evaluate
        from server_tb_vcd_retention_analysis import analyze_chunk, retention_plan
        runtime_cases = {
            "compile_not_started": evaluate(request([sample(0, 0, 0, 0)], started=False)),
            "natural": evaluate(request([sample(0, 0, 0, 0), sample(1, 10, 10, 1, natural_terminal=True)])),
            "nonzero": evaluate(request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, exit_code=9)])),
            "HUP": evaluate(request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, signal="HUP")])),
            "INT": evaluate(request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, signal="INT")])),
            "TERM": evaluate(request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, signal="TERM")])),
        }
        state_dir = temp / "analysis_state"
        fixture = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/small_causal.vcd"
        analyze_chunk(fixture, state_dir, "vcd", max_bytes=80)
        while json.loads((state_dir / "analysis_state.json").read_text(encoding="utf-8"))["status"] == "IN_PROGRESS":
            analyze_chunk(fixture, state_dir, "vcd", max_bytes=80)
        state = json.loads((state_dir / "analysis_state.json").read_text(encoding="utf-8"))
        checkpoint_count = len((state_dir / "checkpoints.jsonl").read_text(encoding="utf-8").splitlines())
        fake = lambda token: {"path": token, "bytes": 1, "sha256": hashlib.sha256(token.encode()).hexdigest()}
        groups = []
        for seq, metric in enumerate(([0, 1], [0, 2], [9, 0], [0, 4], [0, 5]), start=1):
            groups.append({"group_id": f"g{seq}", "sequence": seq, "progress_metric": metric, "source_package": fake(f"g{seq}/source"), "return_zip": fake(f"g{seq}/return"), "sidecar": fake(f"g{seq}/sidecar"), "raw_evidence": [fake(f"g{seq}/wave")], "analysis_complete": True, "family_consumed": True, "mainline_consumed": True, "deterministic_core_evidence": True, "protected_set_audit_pass": True})
        retention = retention_plan({"schema": "server-tb-vcd-retention-analysis-v1", "kind": "retention_index", "family": FAMILY, "track": "qadd-tail-round", "storage_root": str(temp), "max_raw_groups": 3, "groups": groups})
        source_checks = {
            "vcd_contract": vcd_call[0] == 0 and vcd_gate.get("pass") is True,
            "full_hdl_scope_state": hdl_call[0] == 0 and hdl_gate.get("pass") is True,
            "source_bound_recompute": source_call[0] == 0 and source_gate.get("pass") is True,
            "six_exit_partial_semantics": runtime_cases["natural"].get("completeness") == "COMPLETE" and all(runtime_cases[name].get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE" for name in ("compile_not_started", "nonzero", "HUP", "INT", "TERM")),
            "streaming_resume": state.get("status") == "EOF_REACHED" and state.get("byte_offset") == state.get("source", {}).get("bytes") and checkpoint_count > 1 and all((state_dir / name).is_file() for name in ("analysis_state.json", "checkpoints.jsonl", "report.md")),
            "retention_three_slots": retention.get("pass") is True and set(retention.get("slots", {})) == {"MAX_PROGRESS", "LATEST_1", "LATEST_2"},
        }
        source_report = {"schema": "qadd-v63-source-bound-tbvcd-runtime-streaming-v1", "pass": all(source_checks.values()), "errors": [name for name, ok in source_checks.items() if not ok], "zip_sha256": zip_sha, "checks": source_checks, "runtime_cases": {name: {"stop_reason": value.get("stop_reason"), "completeness": value.get("completeness"), "diagnostic_status": value.get("diagnostic_status")} for name, value in runtime_cases.items()}, "streaming": {"status": state.get("status"), "checkpoint_count": checkpoint_count, "byte_offset": state.get("byte_offset")}, "retention": retention}
        write(reports / "source_bound_logger_collector_parser_roundtrip.json", source_report)

        post_path = reports / "post_sim_return_core_scenarios.json"
        post_call = run([str(args.python), str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(zip_path), "--output", str(post_path)])
        post = json.loads(post_path.read_text(encoding="utf-8"))
        if post_call[0] != 0 or post.get("pass") is not True:
            post.setdefault("errors", []).append("independent exact-ZIP post-sim scenarios failed")
            post["pass"] = False
            write(post_path, post)

        import validate_server_tb_vcd_bounded_causal_cone as vcd_validator
        candidates = [row["candidate_id"] for row in contract["candidates"]]
        boundaries = [row["boundary_id"] for row in contract["boundaries"]]
        signatures = [json.dumps(row["expected_signature"], sort_keys=True) for row in contract["candidate_boundary_matrix"]]
        negatives = []
        for name, mutate in (
            ("mixed_bulk_mode", lambda value: value["execution"].__setitem__("lightweight_observer_jsonl", True)),
            ("hard_truncation", lambda value: value["budget"].__setitem__("hard_truncation", True)),
            ("missing_matrix_row", lambda value: value["candidate_boundary_matrix"].pop()),
            ("missing_standard_task", lambda value: value["execution"]["standard_tasks"].remove("$dumpflush")),
        ):
            mutated = copy.deepcopy(contract); mutate(mutated)
            result = vcd_validator.validate_contract(mutated, package)
            negatives.append({"case": name, "rejected": result.get("pass") is False, "errors": result.get("errors", [])})
        matrix_checks = {
            "candidate_ids_unique": len(candidates) == len(set(candidates)),
            "matrix_complete": len(contract["candidate_boundary_matrix"]) == len(candidates) * len(boundaries),
            "pairwise_signatures_unique": len(signatures) == len(set(signatures)),
            "negative_controls_rejected": all(row["rejected"] for row in negatives),
        }
        matrix = {"schema": "qadd-v63-tbvcd-candidate-discrimination-v1", "pass": all(matrix_checks.values()), "errors": [name for name, ok in matrix_checks.items() if not ok], "zip_sha256": zip_sha, "candidate_ids": candidates, "checks": matrix_checks, "negative_controls": negatives}
        write(reports / "candidate_discrimination_matrix.json", matrix)

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
    audit_contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": zip_sha}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": [RULE], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidates, "covered_candidate_ids": candidates, "uncovered_candidate_ids": [], "positive_control_count": 6, "negative_control_count": len(negatives), "pairwise_distinguishable": matrix.get("pass") is True},
        "findings": [],
    }
    write(output / "contract.json", audit_contract)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
