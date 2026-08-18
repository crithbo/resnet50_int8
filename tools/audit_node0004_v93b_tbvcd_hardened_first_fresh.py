#!/usr/bin/env python3
"""Independent first-fresh and negative-control audit for v93b."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v93d_tbvcd_hardened"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_release3"
ZIP = OUT / f"{PACKAGE_ID}.zip"
V91 = ROOT / "outputs/conv_node0004_v91b_normfix_release1/build/r5_n4_hw_v91b_normfix"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")

SPEC = importlib.util.spec_from_file_location("v92_audit", ROOT / "tools/audit_node0004_v92b_tbvcd_first_fresh.py")
assert SPEC and SPEC.loader
V92 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V92)
V92.PACKAGE_ID = PACKAGE_ID
V92.OUT = OUT
V92.ZIP = ZIP


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path | None = None) -> dict[str, object]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": result.returncode, "stdout_tail": result.stdout[-8192:], "stderr_tail": result.stderr[-8192:]}


REQUIRED_DRIVER_SIGNALS = {
    "sig_rd_ob_count",
    "sig_rd_ob_full",
    "sig_rd_ob_empty",
    "sig_rd_ob_wr",
    "sig_rd_ob_rd",
    "sig_buf_rreq_ready",
    "sig_buf_rvalid",
    "sig_buf_rreq_valid",
    "sig_wr_data_ready",
    "sig_hold_data_valid",
    "sig_prepared_bp",
    "sig_prepared_count",
}


def hardening_errors(
    contract: dict[str, object], probe: str, finalizer: str, source_tool: str
) -> list[str]:
    errors: list[str] = []
    signals = {item["signal_id"] for item in contract["signals"]}
    if not REQUIRED_DRIVER_SIGNALS.issubset(signals):
        errors.append("RD_Buffer_AG/WR_Data_Channel driver cone incomplete")
    if "$rtoi($realtime" in probe or "longint'($realtime * 1000.0)" not in probe:
        errors.append("64-bit-safe realtime conversion absent")
    if "64'h3fff" not in probe or "64'h3ffff" in probe:
        errors.append("heartbeat cadence is not 16384 owner cycles")
    accepted = (
        "sig_row_wr && !sig_row_full",
        "sig_queue_wr && !sig_queue_full",
        "sig_rd_ob_wr && !sig_rd_ob_full",
        "sig_rd_ob_rd && !sig_rd_ob_empty",
    )
    if any(token not in probe for token in accepted):
        errors.append("qualified accepted-progress predicates incomplete")
    if "in_timescale" not in finalizer or "runtime_signals" not in finalizer:
        errors.append("multiline timescale or actual-source rebinding absent")
    if "warnings.append" not in source_tool or "actual_sources" not in source_tool:
        errors.append("actual-source drift/replay handling absent")
    rows = contract["candidate_boundary_matrix"]
    candidate_signatures: dict[str, str] = {}
    for row in rows:
        signature = row["expected_signature"]
        if "decision_predicate" not in signature or "candidate_signal_ids" not in signature:
            errors.append("candidate matrix uses a non-causal signature")
            break
        if not set(signature["candidate_signal_ids"]).issubset(signals):
            errors.append("candidate matrix references absent signals")
            break
        encoded = json.dumps(
            {"predicate": signature["decision_predicate"], "signals": signature["candidate_signal_ids"]},
            sort_keys=True,
        )
        previous = candidate_signatures.setdefault(row["candidate_id"], encoded)
        if previous != encoded:
            errors.append("candidate signature drifts across boundaries")
            break
    if len(set(candidate_signatures.values())) != len(candidate_signatures):
        errors.append("two candidates are not causally distinguishable")
    return errors


def source_archive_errors(request: dict[str, object]) -> list[str]:
    archives = [
        row["archive"]
        for row in request["core_entries"]
        if "actual_source_files/" in row["archive"]
    ]
    errors: list[str] = []
    if len(archives) != len(set(archives)):
        errors.append("actual-source archive basename collision")
    if any(len(f"{PACKAGE_ID}_return/{archive}") > 128 for archive in archives):
        errors.append("actual-source archive exceeds family Windows projection budget")
    return errors


def multiline_vcd_roundtrip(package: Path, work: Path) -> dict[str, object]:
    contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
    attempt = work / "attempt"
    c0 = attempt / "c0"
    evidence = attempt / "evidence"
    c0.mkdir(parents=True)
    evidence.mkdir(parents=True)
    source = evidence / "compiled_source/source_identity.json"
    argv = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    process = evidence / "PROCESS_TREE_RECEIPT.json"
    write_json(source, {"status": "COMPLETE", "sources": []})
    write_json(argv, {"compile_argv": contract["execution"]["compile_argv"], "sim_argv": contract["execution"]["sim_argv"]})
    samples = [
        {"seq": 0, "wall_seconds": 0, "sim_time_ticks": 1, "owner_clock_cycles": 1, "sim_cycles": 1, "vcd_bytes": 1, "causal_progress_events": 1, "causal_state_digest": "1" * 64, "global_progress_witness": {"x": 0}, "qualified_progress_counters": {"accept": 1}, "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True},
        {"seq": 1, "wall_seconds": 1, "sim_time_ticks": 1000, "owner_clock_cycles": 2, "sim_cycles": 2, "vcd_bytes": 2, "causal_progress_events": 2, "causal_state_digest": "2" * 64, "global_progress_witness": {"x": 1}, "qualified_progress_counters": {"accept": 2}, "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True, "natural_terminal": True},
    ]
    write_json(process, {"root_exit": 0, "stop_reason": "NATURAL_TERMINAL", "process_tree_reaped": True, "vcd_stable": True, "samples": samples, "process_tree": {"term_sent": False, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True}})
    sim_log = c0 / "sim.log"
    sim_log.write_text("CODEX_TB_VCD_FINAL_FLUSH_V1 sim_time=1000 owner_cycles=2\nCODEX_TB_VCD_NATURAL_TERMINAL_WITNESS_V1 sim_time=1000 owner_cycles=2\n", encoding="utf-8")
    rows = ["$date\n synthetic\n$end\n", "$version\n synthetic\n$end\n", "$timescale\n 1ps\n$end\n", "$scope module probe $end\n"]
    for index, item in enumerate(contract["signals"]):
        rows.append(f"$var wire {item['width_bits']} s{index} {item['signal_id']} $end\n")
    rows.extend(["$upscope $end\n", "$enddefinitions $end\n", "#0\n"])
    for index, item in enumerate(contract["signals"]):
        width = int(item["width_bits"])
        rows.append(f"0s{index}\n" if width == 1 else f"b{'0' * width} s{index}\n")
    rows.append("#1000\n")
    vcd = c0 / "causal_cone.vcd"
    vcd.write_text("".join(rows), encoding="utf-8", newline="\n")
    invocation = run(
        [
            str(PYTHON),
            str(package / "package_tools/node0004_tb_vcd_finalize.py"),
            "--contract", str(package / "contracts/tb_vcd_bounded_causal_cone_contract.json"),
            "--selector", str(package / "contracts/diagnostic_mode_selector.json"),
            "--tb-source", str(package / "tb_probe/tb_vcd_bounded_causal_cone.svh"),
            "--vcd", str(vcd),
            "--sim-log", str(sim_log),
            "--process-receipt", str(process),
            "--source-identity", str(source),
            "--actual-argv", str(argv),
            "--output-dir", str(evidence / "vcd"),
            "--package-id", PACKAGE_ID,
            "--execution-id", "r_multiline",
            "--attempt-id", "a_multiline",
            "--compile-exit", "0",
            "--run-exit", "0",
        ]
    )
    identity_path = evidence / "vcd/VCD_IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.is_file() else {}
    checks = {
        "finalizer_exit_zero": invocation["exit_code"] == 0,
        "multiline_timescale_1ps": identity.get("identity", {}).get("timescale") == "1ps",
        "header_valid": identity.get("identity", {}).get("header_valid") is True,
        "catalog_complete": identity.get("identity", {}).get("catalog_complete") is True,
    }
    return {"schema": "node0004-v93b-multiline-vcd-negative-control-v1", "pass": all(checks.values()), "checks": checks, "invocation": invocation}


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v93-firstfresh-") as temporary:
        temp = Path(temporary)
        package, infos = V92.safe_extract(ZIP, temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        finalizer = (package / "package_tools/node0004_tb_vcd_finalize.py").read_text(encoding="utf-8")
        source_tool = (package / "package_tools/node0004_tb_vcd_source_identity.py").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        declared = {row["path"]: (row["bytes"], row["sha256"]) for row in manifest["files"]}
        actual = V92.member_map(package)
        names = {info.filename for info in infos if not info.is_dir()}
        old = json.loads((V91 / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
        old_map = {row["signal_id"]: (row["exact_hierarchy"], row["width_bits"], row["source_path"], row["source_sha256"]) for row in old["signals"]}
        new_map = {row["signal_id"]: (row["exact_hierarchy"], row["width_bits"], row["source_path"], row["source_sha256"]) for row in contract["signals"]}
        post = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        returned_sources = {row["archive"] for row in post["core_entries"] if "actual_source_files/" in row["archive"]}
        expected_sources = {
            "evidence/compiled_source/actual_source_files/" + Path(row["source_path"]).name
            for row in contract["signals"]
        }
        clean_checks = {
            "manifest_exact": declared == actual,
            "selector_members_exact": set(selector["package_members"]) == names,
            "workload_byte_frozen": V92.workload_map(package) == V92.workload_map(V91),
            "v91_38_signal_baseline_preserved": all(new_map.get(key) == value for key, value in old_map.items()),
            "driver_cone_added_exact": REQUIRED_DRIVER_SIGNALS.issubset(new_map),
            "actual_source_bytes_in_return_exact_set": expected_sources == returned_sources,
            "actual_source_archive_path_budget_and_collision": not source_archive_errors(post),
            "retired_comparator_absent": "buf_idx_queue_bp_pre" not in probe and "sig_public_ack !==" not in probe,
            "single_native_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "normalizer_arity_preserved": '"$compile_log_tail_txt" <<\'PY\'' in runner and "s,d,f,h,t=map(pathlib.Path,sys.argv[1:])" in runner,
            "mode_exact": selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
        }
        write_json(reports / "clean_extract_frozen_surface.json", {"schema": "node0004-v93b-clean-extract-v1", "pass": all(clean_checks.values()), "checks": clean_checks, "errors": [k for k, v in clean_checks.items() if not v]})

        hardening = hardening_errors(contract, probe, finalizer, source_tool)
        negative = {}
        mutated = json.loads(json.dumps(contract))
        mutated["signals"] = [row for row in mutated["signals"] if row["signal_id"] != "sig_rd_ob_full"]
        negative["missing_driver_signal_rejected"] = bool(hardening_errors(mutated, probe, finalizer, source_tool))
        negative["rtoi_wrap_rejected"] = bool(hardening_errors(contract, probe.replace("longint'($realtime * 1000.0)", "$rtoi($realtime * 1000.0)"), finalizer, source_tool))
        negative["sparse_heartbeat_rejected"] = bool(hardening_errors(contract, probe.replace("64'h3fff", "64'h3ffff"), finalizer, source_tool))
        mutated = json.loads(json.dumps(contract))
        first = mutated["candidate_boundary_matrix"][0]["expected_signature"]
        other = mutated["candidate_boundary_matrix"][4]["candidate_id"]
        for row in mutated["candidate_boundary_matrix"]:
            if row["candidate_id"] == other:
                row["expected_signature"] = json.loads(json.dumps(first))
        negative["duplicate_causal_candidate_rejected"] = bool(hardening_errors(mutated, probe, finalizer, source_tool))
        negative["single_line_timescale_parser_rejected"] = bool(hardening_errors(contract, probe, finalizer.replace("in_timescale", "removed_timescale_state"), source_tool))
        mutated_post = json.loads(json.dumps(post))
        source_rows = [row for row in mutated_post["core_entries"] if "actual_source_files/" in row["archive"]]
        if len(source_rows) >= 2:
            source_rows[1]["archive"] = source_rows[0]["archive"]
        negative["source_basename_collision_rejected"] = bool(source_archive_errors(mutated_post))
        mutated_post = json.loads(json.dumps(post))
        source_rows = [row for row in mutated_post["core_entries"] if "actual_source_files/" in row["archive"]]
        if source_rows:
            source_rows[0]["archive"] = "evidence/compiled_source/actual_source_files/" + "x" * 160 + ".sv"
        negative["source_archive_path_budget_rejected"] = bool(source_archive_errors(mutated_post))
        hardening_report = {"schema": "node0004-v93b-rule-gap-first-fresh-negative-controls-v1", "pass": not hardening and all(negative.values()), "positive_errors": hardening, "negative_controls": negative}
        write_json(reports / "rule_gap_hardening.json", hardening_report)

        stripped = probe[: probe.index("bind tb_NDP_Top_new_phy")]
        hdl = temp / "probe.sv"
        hdl.write_text(stripped, encoding="utf-8")
        hdl_compile = run([str(IVERILOG), "-g2012", "-tnull", str(hdl)])
        bash_syntax = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        hdl_checks = {"iverilog_module_frontend": hdl_compile["exit_code"] == 0, "bash_syntax": bash_syntax["exit_code"] == 0, "all_54_signals_source_bound": len(contract["signals"]) == 54}
        write_json(reports / "full_hdl_source_bound.json", {"schema": "node0004-v93b-full-hdl-source-bound-v1", "pass": all(hdl_checks.values()), "checks": hdl_checks, "iverilog": hdl_compile, "bash": bash_syntax})

        multiline = multiline_vcd_roundtrip(package, temp / "multiline")
        write_json(reports / "multiline_vcd_roundtrip.json", multiline)
        runtime = V92.runtime_matrix()
        runtime["schema"] = "node0004-v93b-runtime-six-exit-matrix-v1"
        write_json(reports / "runtime_six_exit_matrix.json", runtime)

        repack = temp / "repack.zip"
        repack_sha = V92.exact_repack(ZIP, repack)
        deterministic = {"schema": "node0004-v93b-deterministic-zip-v1", "pass": repack_sha == V92.digest(ZIP), "source_sha256": V92.digest(ZIP), "repack_sha256": repack_sha}
        write_json(reports / "deterministic_zip.json", deterministic)

        report_paths = [
            reports / "clean_extract_frozen_surface.json",
            reports / "rule_gap_hardening.json",
            reports / "full_hdl_source_bound.json",
            reports / "multiline_vcd_roundtrip.json",
            reports / "runtime_six_exit_matrix.json",
            reports / "deterministic_zip.json",
        ]
        for path in report_paths:
            if json.loads(path.read_text(encoding="utf-8")).get("pass") is not True:
                errors.append(f"failed: {path.name}")

    validation = {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437+v92-rule-gap-hardening",
        "clean_extraction": True,
        "reports": [path.relative_to(ROOT).as_posix() for path in sorted(reports.glob("*.json"))],
        "rule_gap_audit": "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/rule_gap_audit.json",
        "rule_audit_disposition": "RULE_CONFIRMATION",
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Independent local exact-ZIP, HDL, runtime, multiline VCD, actual-source return and v92-escape negative-control audit only.",
    }
    write_json(OUT / "first_fresh_extra_audit/validation.json", validation)
    print(json.dumps({"pass": validation["pass"], "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
