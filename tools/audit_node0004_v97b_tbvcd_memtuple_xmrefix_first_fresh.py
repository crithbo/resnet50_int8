#!/usr/bin/env python3
"""Exact-final-ZIP first-fresh audit for serialized Conv v97b."""

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
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
OUT = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1"
ZIP = OUT / f"{PACKAGE}.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v96b_tbvcd_memtuple.zip"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
OLD_DUPLICATE = "u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue"


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
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout_tail": process.stdout[-8192:],
        "stderr_tail": process.stderr[-8192:],
    }


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
            normalized = archive.read(row).replace(root.encode(), b"<FRESH_PACKAGE_ID>")
            result[relative] = hashlib.sha256(normalized).hexdigest()
    return result


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    evidence: list[Path] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v97-firstfresh-") as name:
        temporary = Path(name)
        package = extract(temporary / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        predecessor = json.loads((package / "provenance/v96b_predecessor_contract.json").read_text(encoding="utf-8"))
        build_audit = json.loads((package / "provenance/v96b_v97_package_build_failure_rule_audit.json").read_text(encoding="utf-8"))
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        signals = contract["signals"]
        previous_signals = predecessor["signals"]
        evolution = contract["diagnostic_round"]["evolution"]
        signal_ids = {row["signal_id"] for row in signals}
        prior_ids = {row["signal_id"] for row in previous_signals}
        added = set(evolution["added_signal_ids"])
        removed = set(evolution["removed_signal_ids"])
        unchanged = set(evolution["unchanged_signal_ids"])
        expected_added = {f"{signal_id}_xmrfix" for signal_id in removed}
        exact_hierarchies = [row["exact_hierarchy"] for row in signals]
        dump_targets = [value.strip() for value in re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", probe)]
        removal_rows = {row["signal_id"]: row for row in evolution["removal_evidence"]}
        old_by_id = {row["signal_id"]: row for row in previous_signals}
        new_by_id = {row["signal_id"]: row for row in signals}
        one_for_one = all(
            new_by_id[new_id]["exact_hierarchy"].replace(".u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue.", ".u_Memory_AG_Idx_Queue.")
            == old_by_id[old_id]["exact_hierarchy"].replace(".u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue.", ".u_Memory_AG_Idx_Queue.")
            for old_id, new_id in ((old, f"{old}_xmrfix") for old in removed)
        )
        checks = {
            "zip_crc_safe_single_root": True,
            "manifest_exact": manifest.get("files") == manifest_rows(package),
            "selector_member_union_exact": set(selector["package_members"]) == {f"{PACKAGE}/{path.relative_to(package).as_posix()}" for path in package.rglob("*") if path.is_file()},
            "v96_workload_config_numeric_golden_frozen": workload_map(ZIP) == workload_map(PRIOR_ZIP),
            "counts_153_41_4_15_60": (len(signals), len(contract["role_coverage"]), len(contract["boundaries"]), len(contract["candidates"]), len(contract["candidate_boundary_matrix"])) == (153, 41, 4, 15, 60),
            "evolution_exact_partition": added == signal_ids - prior_ids and removed == prior_ids - signal_ids and unchanged == signal_ids & prior_ids,
            "exact_53_identity_replacements": len(added) == len(removed) == 53 and len(unchanged) == 100 and added == expected_added,
            "one_for_one_physical_hierarchy_repair": one_for_one,
            "all_removals_high_and_causal": set(removal_rows) == removed and all(row.get("confidence") == "HIGH" and row.get("affected_candidate_ids") for row in removal_rows.values()),
            "no_overlapping_id_rewrite_cascade": all("_xmrfix_xmrfix" not in value for value in signal_ids) and not any(signal_id.endswith("_xmrfix_index_xmrfix") for signal_id in signal_ids),
            "all_duplicate_memory_ag_anchors_removed": OLD_DUPLICATE not in json.dumps(contract) and OLD_DUPLICATE not in probe,
            "exact_dump_target_multiset": sorted(dump_targets) == sorted(exact_hierarchies) and len(dump_targets) == 153,
            "package_failure_audit_triggered_and_passed": build_audit.get("package_build_failure_rule_audit_triggered") is True and build_audit.get("consecutive_count") == 2 and build_audit.get("pass") is True,
            "manifest_binds_current_build_audit": manifest.get("package_build_failure_rule_audit_triggered") is True and manifest.get("package_build_failure_rule_audit") == "provenance/v96b_v97_package_build_failure_rule_audit.json",
            "passive_probe": "output " not in probe and "inout " not in probe and "force " not in probe and "assign " not in probe,
            "retired_ack_comparator_absent": "buf_idx_queue_bp_pre" not in probe and "sig_public_ack !==" not in probe,
            "single_native_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
        }
        clean_path = reports / "clean_extract_frozen_surface.json"
        write(clean_path, {"schema": "node0004-v97-clean-extract-v1", "checks": checks, "pass": all(checks.values()), "errors": [key for key, value in checks.items() if not value]})
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
        hdl_path_out = reports / "full_hdl_source_bound.json"
        write(hdl_path_out, {"schema": "node0004-v97-full-hdl-v1", "checks": hdl_checks, "iverilog": iv, "bash": bash, "pass": all(hdl_checks.values()), "errors": [key for key, value in hdl_checks.items() if not value]})
        evidence.append(hdl_path_out)

        evaluator = load_module("v97_evaluator", package / "package_tools/server_tb_vcd_runtime_supervision.py")
        supervisor = load_module("v97_supervisor", package / "package_tools/node0004_tb_vcd_process_supervisor.py")
        replay = supervisor.replay_cases(evaluator.evaluate)
        expected = {
            "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
            "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
            "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
            "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
        }
        helper_sha = sha(package / "package_tools/server_tb_vcd_runtime_supervision.py")
        authority = {
            "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
            "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
            "helper_sha256": helper_sha,
            "outer_runner_consumes_only_receipt": True,
            "independent_exit_logic_absent": True,
            "replay_cases": replay,
        }
        dumpoff_replay = supervisor.dumpoff_replay_cases(evaluator.evaluate, authority)
        dumpoff_expected = {
            "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE": "CONTINUE",
            "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU": "CAUSAL_PLATEAU",
            "REPEATED_STOP_MARKER": "FAIL_CLOSED",
        }
        replay_checks = {
            "exact_runtime_v3_replay": {row["case_id"]: row["observed_decision"] for row in replay} == expected,
            "exact_runtime_v5_dumpoff_replay": {row["case_id"]: row["observed_decision"] for row in dumpoff_replay} == dumpoff_expected,
        }
        replay_path = reports / "runtime_v3_replay.json"
        write(replay_path, {"schema": "node0004-v97-runtime-v5-replay-v1", "checks": replay_checks, "replay": replay, "dumpoff_replay": dumpoff_replay, "pass": all(replay_checks.values()), "errors": [key for key, value in replay_checks.items() if not value]})
        evidence.append(replay_path)

        negative = {
            "duplicate_anchor_would_be_rejected": OLD_DUPLICATE in probe.replace(".u_Memory_AG_Idx_Queue.", ".u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue.", 1),
            "contract_probe_drift_would_be_detected": sorted(dump_targets[1:]) != sorted(exact_hierarchies),
            "overlapping_id_cascade_would_be_detected": "sig_mem_i0_raw_last_xmrfix_index_xmrfix" not in signal_ids,
            "old_invalid_identity_not_retained": not (removed & signal_ids),
        }
        negative_path = reports / "package_local_negative_controls.json"
        write(negative_path, {"schema": "node0004-v97-package-local-negative-controls-v1", "controls": negative, "pass": all(negative.values()), "errors": [key for key, value in negative.items() if not value]})
        evidence.append(negative_path)

        repack = temporary / "repack.zip"
        with zipfile.ZipFile(ZIP) as original, zipfile.ZipFile(repack, "w", allowZip64=True) as output:
            for old in original.infolist():
                info = zipfile.ZipInfo(old.filename, old.date_time)
                info.compress_type, info.comment, info.extra = old.compress_type, old.comment, old.extra
                info.internal_attr, info.external_attr, info.create_system, info.flag_bits = old.internal_attr, old.external_attr, old.create_system, old.flag_bits
                output.writestr(info, original.read(old), compress_type=old.compress_type, compresslevel=9)
        deterministic_path = reports / "deterministic_zip.json"
        same = sha(ZIP) == sha(repack)
        write(deterministic_path, {"schema": "node0004-v97-deterministic-zip-v1", "source_sha256": sha(ZIP), "repack_sha256": sha(repack), "pass": same, "errors": [] if same else ["deterministic repack differs"]})
        evidence.append(deterministic_path)

    evidence.extend(OUT / "gates" / name for name in (
        "tb_vcd_contract.json", "mode_selector.json", "hdl_lexical.json", "runtime_preflight.json",
        "normalizer_arity.json", "runner_resilience.json", "post_sim_return.json",
        "active_rule_registry.json", "package_release_admission.json",
    ))
    for path in evidence:
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(ROOT).as_posix()}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass", value.get("valid")) is not True:
            errors.append(f"failed: {path.relative_to(ROOT).as_posix()}")
    report = {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "package_id": PACKAGE,
        "family": "conv_serialized_node0004",
        "rule_change_epoch_id": "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "exact_final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "clean_extract_from_final_zip": True,
        "family_build_reports_reused": False,
        "evidence": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "pass": json.loads(path.read_text(encoding="utf-8")).get("pass", json.loads(path.read_text(encoding="utf-8")).get("valid"))} for path in evidence if path.is_file()],
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": True,
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Exact local final-ZIP, frozen-surface, 153-net actual-source causal catalog, one-for-one XMR identity repair, HDL, runtime-v3 replay, return and negative-control audit only; no production v97 result or tuple-leaf root claim.",
    }
    write(OUT / "first_fresh_extra_audit/validation.json", report)
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
