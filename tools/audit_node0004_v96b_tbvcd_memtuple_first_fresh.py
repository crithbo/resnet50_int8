#!/usr/bin/env python3
"""Exact-final-ZIP first-fresh audit for serialized Conv v96b."""

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
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
OUT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1"
ZIP = OUT / f"{PACKAGE}.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v95b_tbvcd_metapair.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
ACTUAL_SHA = "2f534813b8d73ff19961541b910c03b417f401d73ae98b2e446e728f384a7b3e"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    process = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": process.returncode, "stdout_tail": process.stdout[-8192:], "stderr_tail": process.stderr[-8192:]}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract(target: Path) -> Path:
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        names = [row.filename for row in archive.infolist() if not row.is_dir()]
        if len(names) != len(set(names)) or {name.split("/", 1)[0] for name in names} != {PACKAGE}:
            raise RuntimeError("ZIP root/duplicate failure")
        if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
            raise RuntimeError("unsafe ZIP member")
        archive.extractall(target)
    return target / PACKAGE


def manifest_rows(package: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
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
            relative = row.filename.split("/workload/", 1)[1]
            result[relative] = hashlib.sha256(archive.read(row).replace(root.encode(), b"<FRESH_PACKAGE_ID>")).hexdigest()
    return result


def rejects(contract: dict[str, Any], package: Path, temporary: Path, name: str) -> bool:
    source = temporary / f"{name}.json"
    report = temporary / f"{name}.report.json"
    write(source, contract)
    call = run([str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(source), "--root", str(package), "--output", str(report)])
    return call["exit_code"] != 0


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    evidence: list[Path] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v96-firstfresh-") as name:
        temporary = Path(name)
        package = extract(temporary / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        signals = contract["signals"]
        evolution = contract["diagnostic_round"]["evolution"]
        new_signals = [row for row in signals if row["signal_id"].startswith("sig_mem_i") or row["signal_id"] in {"sig_mem_raw_idx_all", "sig_mem_raw_tag_all"}]
        input_ids = {
            index: {row["signal_id"] for row in new_signals if row["signal_id"].startswith(f"sig_mem_i{index}_")}
            for index in range(3)
        }
        exact = [row["exact_hierarchy"] for row in signals]
        dump_targets = [value.strip() for value in re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", probe)]
        high = {row["candidate_id"] for row in contract["candidates"] if row["priority"] == "HIGH"}
        high_drivers = {candidate for row in signals if row.get("driver_depth_edges") == 0 for candidate in row.get("driver_leaf_for_candidate_ids", []) if candidate in high}
        clean = {
            "zip_crc_safe_single_root": True,
            "manifest_exact": manifest.get("files") == manifest_rows(package),
            "selector_member_union_exact": set(selector["package_members"]) == {f"{PACKAGE}/{path.relative_to(package).as_posix()}" for path in package.rglob("*") if path.is_file()},
            "v95_workload_config_numeric_golden_frozen": workload_map(ZIP) == workload_map(PRIOR_ZIP),
            "counts_153_41_4_15_60": (len(signals), len(contract["role_coverage"]), len(contract["boundaries"]), len(contract["candidates"]), len(contract["candidate_boundary_matrix"])) == (153, 41, 4, 15, 60),
            "all_100_v95_signals_retained": len(evolution["unchanged_signal_ids"]) == 100,
            "exact_53_signal_addition": len(evolution["added_signal_ids"]) == 53 and {row["signal_id"] for row in new_signals} == set(evolution["added_signal_ids"]),
            "zero_removed_signals": evolution["removed_signal_ids"] == [],
            "three_inputs_independently_observed": all(len(input_ids[index]) == 17 for index in range(3)),
            "new_leaves_bind_returned_actual_source": all(row["source_sha256"] == ACTUAL_SHA and row["source_binding"] == "ACTUAL_SOURCE_NET" for row in new_signals),
            "high_driver_complete": high_drivers == high,
            "exact_dump_target_multiset": sorted(dump_targets) == sorted(exact) and len(dump_targets) == 153,
            "passive_probe": "output " not in probe and "inout " not in probe and "force " not in probe and "assign " not in probe,
            "retired_ack_comparator_absent": "buf_idx_queue_bp_pre" not in probe and "sig_public_ack !==" not in probe,
            "single_native_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
        }
        clean_path = reports / "clean_extract_frozen_surface.json"
        write(clean_path, {"schema": "node0004-v96-clean-extract-v1", "checks": clean, "pass": all(clean.values()), "errors": [key for key, value in clean.items() if not value]})
        evidence.append(clean_path)

        stripped = probe[: probe.index("bind tb_NDP_Top_new_phy")]
        for row in signals:
            stripped = stripped.replace(f"$dumpvars(0, {row['exact_hierarchy']});", f"$dumpvars(0, {row['signal_id']});")
        hdl_path = temporary / "probe.sv"
        hdl_path.write_text(stripped, encoding="utf-8", newline="\n")
        iv = run([str(IVERILOG), "-g2012", "-tnull", str(hdl_path)])
        bash = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        hdl_checks = {
            "iverilog_complete_module": iv["exit_code"] == 0,
            "bash_syntax": bash["exit_code"] == 0,
            "exact_stop_token": "$fscanf(codex_control_fd" in probe and 'codex_control_token == "CAUSAL_PLATEAU"' in probe,
        }
        full_hdl_path = reports / "full_hdl_source_bound.json"
        write(full_hdl_path, {"schema": "node0004-v96-full-hdl-v1", "checks": hdl_checks, "iverilog": iv, "bash": bash, "pass": all(hdl_checks.values()), "errors": [key for key, value in hdl_checks.items() if not value]})
        evidence.append(full_hdl_path)

        evaluator = load_module("v96_evaluator", package / "package_tools/server_tb_vcd_runtime_supervision.py")
        supervisor = load_module("v96_supervisor", package / "package_tools/node0004_tb_vcd_process_supervisor.py")
        replay = supervisor.replay_cases(evaluator.evaluate)
        expected = {"ADVANCING_VCD_TIMESTAMP": "CONTINUE", "PLATEAU_SUSPECTED_ONLY": "CONTINUE", "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU", "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE"}
        replay_checks = {"exact_runtime_v3_replay": {row["case_id"]: row["observed_decision"] for row in replay} == expected}
        replay_path = reports / "runtime_v3_replay.json"
        write(replay_path, {"schema": "node0004-v96-runtime-v3-replay-v1", "checks": replay_checks, "replay": replay, "pass": all(replay_checks.values()), "errors": [key for key, value in replay_checks.items() if not value]})
        evidence.append(replay_path)

        negative: dict[str, bool] = {}
        changed = json.loads(json.dumps(contract)); changed["signals"] = [row for row in changed["signals"] if row["signal_id"] != "sig_mem_i0_raw_valid"]; negative["missing_memory_input_leaf"] = rejects(changed, package, temporary, "missing_leaf")
        changed = json.loads(json.dumps(contract)); left, right = list(INPUT for INPUT in ["memory_input0_keep_token_or_epoch_ends_early", "memory_input1_buffer_token_or_last_ends_early"]); by = {(row["candidate_id"], row["boundary_id"]): row for row in changed["candidate_boundary_matrix"]}; [by[(right, boundary)].__setitem__("expected_signature", json.loads(json.dumps(by[(left, boundary)]["expected_signature"]))) for boundary in {row["boundary_id"] for row in changed["boundaries"]}]; negative["pairwise_candidate_collision"] = rejects(changed, package, temporary, "candidate_collision")
        changed = json.loads(json.dumps(contract)); next(row for row in changed["signals"] if row["signal_id"] == "sig_mem_i0_raw_valid")["source_sha256"] = "0" * 64; negative["actual_source_hash_drift"] = rejects(changed, package, temporary, "source_drift")
        changed = json.loads(json.dumps(contract)); changed["diagnostic_round"]["evolution"]["removed_signal_ids"] = [changed["diagnostic_round"]["evolution"]["unchanged_signal_ids"].pop()]; negative["v95_signal_removal"] = rejects(changed, package, temporary, "v95_removal")
        changed = json.loads(json.dumps(contract)); [row.__setitem__("driver_leaf_for_candidate_ids", []) or row.__setitem__("driver_depth_edges", None) for row in changed["signals"] if row["signal_id"].startswith("sig_mem_i")]; negative["aggregate_only_all_match"] = rejects(changed, package, temporary, "aggregate_only")
        negative_path = reports / "negative_controls.json"
        write(negative_path, {"schema": "node0004-v96-negative-controls-v1", "controls": negative, "pass": all(negative.values()), "errors": [key for key, value in negative.items() if not value]})
        evidence.append(negative_path)

        repack = temporary / "repack.zip"
        with zipfile.ZipFile(ZIP) as original, zipfile.ZipFile(repack, "w", allowZip64=True) as output:
            for old in original.infolist():
                info = zipfile.ZipInfo(old.filename, old.date_time)
                info.compress_type, info.comment, info.extra = old.compress_type, old.comment, old.extra
                info.internal_attr, info.external_attr, info.create_system, info.flag_bits = old.internal_attr, old.external_attr, old.create_system, old.flag_bits
                output.writestr(info, original.read(old), compress_type=old.compress_type, compresslevel=9)
        deterministic_path = reports / "deterministic_zip.json"
        write(deterministic_path, {"schema": "node0004-v96-deterministic-zip-v1", "source_sha256": sha(ZIP), "repack_sha256": sha(repack), "pass": sha(ZIP) == sha(repack), "errors": [] if sha(ZIP) == sha(repack) else ["deterministic repack differs"]})
        evidence.append(deterministic_path)

    evidence.extend(OUT / "gates" / name for name in ("tb_vcd_contract.json", "mode_selector.json", "hdl_lexical.json", "runtime_preflight.json", "normalizer_arity.json", "runner_resilience.json", "post_sim_return.json", "active_rule_registry.json"))
    for path in evidence:
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(ROOT).as_posix()}")
        else:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("pass", value.get("valid")) is not True:
                errors.append(f"failed: {path.relative_to(ROOT).as_posix()}")
    report = {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "package_id": PACKAGE,
        "family": "conv_serialized_node0004",
        "rule_change_epoch_id": "tb-vcd-exit-mechanism-consistency-v3",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "exact_final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "sha256": sha(ZIP)},
        "clean_extract_from_final_zip": True,
        "family_build_reports_reused": False,
        "evidence": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "pass": json.loads(path.read_text(encoding="utf-8")).get("pass", json.loads(path.read_text(encoding="utf-8")).get("valid"))} for path in evidence if path.is_file()],
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
        "package_build_failure_rule_audit_triggered": False,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Exact local final-ZIP, frozen-surface, 153-net actual-source causal catalog, HDL, runtime-v3 replay, return and negative-control audit only; no production v96 result or leaf root claim.",
    }
    write(OUT / "first_fresh_extra_audit/validation.json", report)
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
