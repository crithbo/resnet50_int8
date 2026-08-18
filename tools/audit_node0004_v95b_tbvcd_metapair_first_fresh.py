#!/usr/bin/env python3
"""Exact-final-ZIP first-fresh audit for serialized Conv v95b."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v95b_tbvcd_metapair"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_release1"
ZIP = OUT / f"{PACKAGE}.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v94b_tbvcd_wrdrain.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
EXPECTED_REPLAY = {
    "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
    "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
    "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
    "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
}
NEW_IDS = {
    "sig_meta_input_valid", "sig_meta_input_ready", "sig_meta_transaction_bias_valid",
    "sig_meta_transaction_valid", "sig_meta_transaction_finish", "sig_meta_size_left",
    "sig_meta_final_size", "sig_meta_transfer_valid", "sig_meta_transfer_accept",
    "sig_meta_output_ready", "sig_meta_output_valid", "sig_meta_output_wr",
    "sig_meta_output_rd", "sig_buf_last_masked", "sig_buf_selected_last",
    "sig_buf_selected_last_index", "sig_cfg_mem_idx_mode", "sig_cfg_mem_keep_last",
    "sig_cfg_buf_keep_last", "sig_cfg_transaction_total_size",
    "sig_memidx_all_matched", "sig_memidx_buffer_last", "sig_memidx_buffer_last_index",
    "sig_memidx_queue_wr", "sig_memidx_queue_rd", "sig_memidx_queue_empty",
    "sig_memidx_queue_full",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(argv: list[str]) -> dict[str, Any]:
    proc = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-16384:],
        "stderr_tail": proc.stderr[-16384:],
    }


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_final_zip(target: Path) -> Path:
    target.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        names = [row.filename for row in archive.infolist() if not row.is_dir()]
        if len(names) != len(set(names)):
            raise RuntimeError("duplicate ZIP member")
        if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
            raise RuntimeError("unsafe ZIP member")
        if {name.split("/", 1)[0] for name in names} != {PACKAGE}:
            raise RuntimeError("ZIP root differs")
        archive.extractall(target)
    return target / PACKAGE


def manifest_rows(package: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(package).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def workload_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        root = next(name.split("/", 1)[0] for name in archive.namelist() if "/" in name)
        for row in archive.infolist():
            if row.is_dir() or "/workload/" not in row.filename:
                continue
            rel = row.filename.split("/workload/", 1)[1]
            data = archive.read(row).replace(root.encode(), b"<FRESH_PACKAGE_ID>")
            result[rel] = hashlib.sha256(data).hexdigest()
    return result


def generic_contract_rejects(contract: dict[str, Any], package: Path, temp: Path, name: str) -> bool:
    path = temp / f"{name}.json"
    output = temp / f"{name}.report.json"
    write_json(path, contract)
    call = run([
        str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
        "--contract", str(path), "--root", str(package), "--output", str(output),
    ])
    return call["exit_code"] != 0


def real_interheartbeat_samples() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seq = 0
    # Source heartbeats progress to the known v94 last-progress boundary.
    for cycles in (0, 16384, 1966080):
        rows.append({
            "seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles,
            "sim_time_ticks": cycles, "appended_vcd_timestamp_ticks": cycles,
            "wall_seconds": float(seq), "vcd_bytes": 1000 + cycles,
            "causal_progress_events": 1, "qualified_progress_counters": {"events": 1},
            "causal_state_digest": "a" * 64, "global_progress_witness": {"digest": "b" * 64},
            "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True,
            "quota_ok": True,
        })
        seq += 1
    # Host polls advance VCD timestamps but repeat the most recent source
    # heartbeat. v94 incorrectly treated each poll as causal progress.
    for index in range(1, 12):
        rows.append({**rows[-1], "seq": seq, "wall_seconds": 2.0 + index,
                     "appended_vcd_timestamp_ticks": 1966080 + index * 500000,
                     "sim_time_ticks": 1966080 + index * 500000})
        seq += 1
    # Two real source heartbeats cross dump-off and then its grace period.
    rows.append({**rows[-1], "seq": seq, "owner_clock_cycles": 6160384,
                 "sim_cycles": 6160384, "sim_time_ticks": 6160384,
                 "appended_vcd_timestamp_ticks": 6160384, "wall_seconds": 20.0})
    seq += 1
    rows.append({**rows[-1], "seq": seq, "owner_clock_cycles": 6422528,
                 "sim_cycles": 6422528, "sim_time_ticks": 6422528,
                 "appended_vcd_timestamp_ticks": 6422528, "wall_seconds": 21.0})
    return rows


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    evidence: list[Path] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v95-firstfresh-") as temp_name:
        temp = Path(temp_name)
        package = extract_final_zip(temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        supervisor_text = (package / "package_tools/node0004_tb_vcd_process_supervisor.py").read_text(encoding="utf-8")
        finalizer_text = (package / "package_tools/node0004_tb_vcd_finalize.py").read_text(encoding="utf-8")
        signals = contract["signals"]
        ids = {row["signal_id"] for row in signals}
        exact = {row["exact_hierarchy"] for row in signals}
        dump_targets = {value.strip() for value in re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", probe)}
        evolution = contract["diagnostic_round"]["evolution"]
        candidates = {row["candidate_id"]: row for row in contract["candidates"]}
        high = {cid for cid, row in candidates.items() if row["priority"] == "HIGH"}
        high_drivers = {
            cid for row in signals if row.get("driver_depth_edges") == 0
            for cid in row.get("driver_leaf_for_candidate_ids", []) if cid in high
        }
        clean = {
            "zip_crc_safe_single_root": True,
            "manifest_exact": manifest.get("files") == manifest_rows(package),
            "selector_member_union_exact": set(selector.get("package_members", [])) == {
                f"{PACKAGE}/{path.relative_to(package).as_posix()}" for path in package.rglob("*") if path.is_file()
            },
            "v94_workload_config_numeric_golden_frozen": workload_map(ZIP) == workload_map(PRIOR_ZIP),
            "counts_100_41_4_10_40": (
                len(signals), len(contract["role_coverage"]), len(contract["boundaries"]),
                len(contract["candidates"]), len(contract["candidate_boundary_matrix"])
            ) == (100, 41, 4, 10, 40),
            "all_73_predecessor_signals_retained": len(evolution["unchanged_signal_ids"]) == 73,
            "exact_28_signal_addition": set(evolution["added_signal_ids"]) == NEW_IDS,
            "zero_removed_signals": evolution["removed_signal_ids"] == [],
            "high_candidate_direct_driver_complete": high_drivers == high,
            "exact_dump_target_union": dump_targets == exact and len(dump_targets) == 100,
            "all_actual_source_bound_passive": all(
                row.get("source_binding") == "ACTUAL_SOURCE_NET"
                and row.get("derived_expected_equation") is False
                and row.get("drives_dut") is False for row in signals
            ),
            "retired_ack_comparator_absent": "buf_idx_queue_bp_pre" not in probe and "sig_public_ack !==" not in probe,
            "single_native_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "direct_config_rtl_dynamic_policy_bound": "v95_config_actual_consumer_validation_plan.json" in {
                path.name for path in (package / "provenance").iterdir()
            },
        }
        clean_path = reports / "clean_extract_frozen_surface.json"
        write_json(clean_path, {"schema": "node0004-v95-clean-extract-v1", "pass": all(clean.values()), "checks": clean, "errors": [k for k, v in clean.items() if not v]})
        evidence.append(clean_path)

        stripped = probe[: probe.index("bind tb_NDP_Top_new_phy")]
        for row in signals:
            stripped = stripped.replace(f"$dumpvars(0, {row['exact_hierarchy']});", f"$dumpvars(0, {row['signal_id']});")
        hdl = temp / "probe.sv"
        hdl.write_text(stripped, encoding="utf-8", newline="\n")
        iv = run([str(IVERILOG), "-g2012", "-tnull", str(hdl)])
        bash = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        hdl_checks = {
            "iverilog_complete_module": iv["exit_code"] == 0,
            "bash_syntax": bash["exit_code"] == 0,
            "passive_input_only": "output " not in probe and "inout " not in probe and "force " not in probe and "assign " not in probe,
            "precreated_empty_control_is_inert": all(token in probe for token in (
                "$fscanf(codex_control_fd", 'codex_control_token == "CAUSAL_PLATEAU"',
            )),
        }
        hdl_path = reports / "full_hdl_source_bound.json"
        write_json(hdl_path, {"schema": "node0004-v95-full-hdl-v1", "pass": all(hdl_checks.values()), "checks": hdl_checks, "iverilog": iv, "bash": bash, "errors": [k for k, v in hdl_checks.items() if not v]})
        evidence.append(hdl_path)

        evaluator = load_module("packaged_v95_evaluator", package / "package_tools/server_tb_vcd_runtime_supervision.py")
        supervisor = load_module("packaged_v95_supervisor", package / "package_tools/node0004_tb_vcd_process_supervisor.py")
        replay = supervisor.replay_cases(evaluator.evaluate)
        observed = {row["case_id"]: row["observed_decision"] for row in replay}
        raw = real_interheartbeat_samples()
        selected = supervisor.select_evaluation_samples(raw)
        authority = {
            "mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "packaged",
            "helper_sha256": "7" * 64, "outer_runner_consumes_only_receipt": True,
            "independent_exit_logic_absent": True,
            "replay_cases": [{"case_id": key, "observed_decision": value} for key, value in EXPECTED_REPLAY.items()],
        }
        decision, _ = supervisor.shared_decision(evaluator.evaluate, selected, authority)
        runtime = {
            "exact_four_replay": observed == EXPECTED_REPLAY,
            "v94_interheartbeat_host_polls_removed": len(selected) == 5 and len(raw) == 16,
            "full_plateau_after_filtered_source_heartbeat_stops": decision == "CAUSAL_PLATEAU",
            "shared_receipt_is_only_stop_authority": "if decision != \"CONTINUE\"" in supervisor_text,
            "exact_token_atomic_stop": "os.replace(temporary, control)" in supervisor_text and 'temporary.write_text("CAUSAL_PLATEAU\\n"' in supervisor_text,
            "full_hierarchy_catalog": "required={x['exact_hierarchy']" in finalizer_text,
            "no_duplicate_final_evaluator_sample": "final=dict(samples[-1])" not in finalizer_text,
            "archive_sha_bytes_last_timestamp_bound": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT" in finalizer_text,
            "separate_console_capture": "--console-log" in runner and "stdout=console_stream" in supervisor_text,
        }
        runtime_path = reports / "runtime_v3_replay_false_freeze_control.json"
        write_json(runtime_path, {"schema": "node0004-v95-runtime-v3-audit-v1", "pass": all(runtime.values()), "checks": runtime, "replay": replay, "raw_sample_count": len(raw), "selected_sample_count": len(selected), "filtered_decision": decision, "errors": [k for k, v in runtime.items() if not v]})
        evidence.append(runtime_path)

        negatives: dict[str, bool] = {}
        mutations: list[tuple[str, Any]] = [
            ("missing_soft_reference", lambda c: c["diagnostic_round"].pop("breadth_baseline", None)),
            ("low_candidate_removed", lambda c: c.__setitem__("candidates", [row for row in c["candidates"] if row["candidate_id"] != "prepared_valid_size_gate"])),
            ("added_signal_identity_drift", lambda c: c["diagnostic_round"]["evolution"].__setitem__("added_signal_ids", c["diagnostic_round"]["evolution"]["added_signal_ids"][:-1])),
            ("high_driver_removed", lambda c: [row.__setitem__("driver_leaf_for_candidate_ids", []) for row in c["signals"] if "metadata_generation_lifetime_ends_early" in row.get("driver_leaf_for_candidate_ids", [])]),
            ("hard_truncation_added", lambda c: c["budget"].__setitem__("hard_truncation", True)),
        ]
        for name, mutate in mutations:
            changed = json.loads(json.dumps(contract))
            mutate(changed)
            negatives[name] = generic_contract_rejects(changed, package, temp, name)
        negatives["empty_control_exists_stop_rejected"] = 'codex_control_token == "CAUSAL_PLATEAU"' in probe
        negatives["raw_host_poll_stream_not_directly_evaluated"] = "evaluation_samples = select_evaluation_samples(samples)" in supervisor_text
        negative_path = reports / "negative_controls.json"
        write_json(negative_path, {"schema": "node0004-v95-negative-controls-v1", "pass": all(negatives.values()), "controls": negatives, "errors": [k for k, v in negatives.items() if not v]})
        evidence.append(negative_path)

        repack = temp / "repack.zip"
        with zipfile.ZipFile(ZIP) as original, zipfile.ZipFile(repack, "w", allowZip64=True) as output:
            for old in original.infolist():
                info = zipfile.ZipInfo(old.filename, old.date_time)
                info.compress_type = old.compress_type
                info.comment = old.comment
                info.extra = old.extra
                info.internal_attr = old.internal_attr
                info.external_attr = old.external_attr
                info.create_system = old.create_system
                info.flag_bits = old.flag_bits
                output.writestr(info, original.read(old), compress_type=old.compress_type, compresslevel=9)
        deterministic = sha(repack) == sha(ZIP)
        deterministic_path = reports / "deterministic_zip.json"
        write_json(deterministic_path, {"schema": "node0004-v95-deterministic-zip-v1", "pass": deterministic, "source_sha256": sha(ZIP), "repack_sha256": sha(repack), "errors": [] if deterministic else ["deterministic repack differs"]})
        evidence.append(deterministic_path)

    evidence.extend([
        OUT / "gates/tb_vcd_contract.json", OUT / "gates/mode_selector.json",
        OUT / "gates/hdl_lexical.json", OUT / "gates/runtime_preflight.json",
        OUT / "gates/normalizer_arity.json", OUT / "gates/runner_resilience.json",
        OUT / "gates/post_sim_return.json", OUT / "gates/active_rule_registry.json",
    ])
    for path in evidence:
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(ROOT).as_posix()}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True and value.get("valid") is not True:
            errors.append(f"failed: {path.relative_to(ROOT).as_posix()}")
    report = {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "package_id": PACKAGE, "family": FAMILY,
        "rule_change_epoch_id": "tb-vcd-exit-mechanism-consistency-v3",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "exact_final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "sha256": sha(ZIP)},
        "clean_extract_from_final_zip": True,
        "family_build_reports_reused": False,
        "evidence": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
             "pass": json.loads(path.read_text(encoding="utf-8")).get("pass", json.loads(path.read_text(encoding="utf-8")).get("valid"))}
            for path in evidence if path.is_file()
        ],
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
        "package_build_failure_rule_audit_triggered": False,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Independent local exact-ZIP, frozen-surface, source-bound HDL, adaptive breadth, direct-driver, runtime-v3 replay/false-freeze, return and negative-control audit only; no production v95 execution or validated functional root claim.",
    }
    write_json(OUT / "first_fresh_extra_audit/validation.json", report)
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
