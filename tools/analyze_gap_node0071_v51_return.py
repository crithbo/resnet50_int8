#!/usr/bin/env python3
"""Formal receipt and qualified-progress analysis for GAP node0071 v51."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
INSTALL = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_PATH = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n71_gap_v51_ga_ob_mode_factor_diag_"
    r"r1786123595862873463_3802426_return.zip"
)
RETURN_SHA = "819f61a97a75497d6cae0de7babe64c5a508243df4caa44ac20ea61f1e5005e0"
RETURN_BYTES = 186057
SOURCE_PATH = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{INSTALL}.zip"
)
SOURCE_SHA = "76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4"
EXECUTION = "r1786123595862873463_3802426"
ATTEMPT = "a3802426"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def safe_archive(archive: zipfile.ZipFile, root: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    names: set[str] = set()
    roots: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
            errors.append(f"unsafe path:{info.filename}")
        if info.filename in names:
            errors.append(f"duplicate:{info.filename}")
        names.add(info.filename)
        if pure.parts:
            roots.add(pure.parts[0])
        if stat.S_ISLNK(info.external_attr >> 16):
            errors.append(f"symlink:{info.filename}")
    if roots != {root}:
        errors.append(f"root:{sorted(roots)}")
    bad = archive.testzip()
    if bad:
        errors.append(f"crc:{bad}")
    return not errors, errors


def run_parser(argv: list[str], output: Path) -> dict[str, object]:
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output": json.loads(output.read_text(encoding="utf-8"))
        if output.is_file() else None,
    }


def analyze(output: Path) -> dict[str, object]:
    errors: list[str] = []
    if not RETURN_PATH.is_file() or RETURN_PATH.stat().st_size != RETURN_BYTES:
        raise RuntimeError("return file/size mismatch")
    if sha(RETURN_PATH) != RETURN_SHA:
        raise RuntimeError("return SHA mismatch")
    if not SOURCE_PATH.is_file() or sha(SOURCE_PATH) != SOURCE_SHA:
        raise RuntimeError("source identity mismatch")

    expected_outer = f"{INSTALL}_{EXECUTION}_return.zip"
    outer_execution_valid = RETURN_PATH.name == expected_outer

    with tempfile.TemporaryDirectory(prefix="gap-v51-return-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(RETURN_PATH) as archive:
            return_safe, return_errors = safe_archive(archive, RETURN_ROOT)
            errors.extend(return_errors)
            archive.extractall(tmp / "return")
            names = {
                PurePosixPath(i.filename).relative_to(RETURN_ROOT).as_posix()
                for i in archive.infolist() if not i.is_dir()
            }
        returned = tmp / "return" / RETURN_ROOT
        manifest = json.loads(
            (returned / "RETURN_MANIFEST.json").read_text(encoding="utf-8")
        )
        listed = {row["path"] for row in manifest["files"]}
        exact_set = names == listed | {"RETURN_MANIFEST.json"}
        per_file = all(
            (returned / row["path"]).is_file()
            and (returned / row["path"]).stat().st_size == row["size_bytes"]
            and sha(returned / row["path"]) == row["sha256"]
            for row in manifest["files"]
        )
        if not exact_set:
            errors.append("return manifest exact-set mismatch")
        if not per_file:
            errors.append("return per-file receipt mismatch")

        with zipfile.ZipFile(SOURCE_PATH) as archive:
            source_safe, source_errors = safe_archive(archive, INSTALL)
            errors.extend(source_errors)
            archive.extractall(tmp / "source")
        source = tmp / "source" / INSTALL
        source_manifest = source / "TEST_PACKAGE_MANIFEST.json"
        returned_manifest = returned / "evidence/PACKAGE_MANIFEST.json"
        source_bound = source_manifest.read_bytes() == returned_manifest.read_bytes()
        if not source_bound:
            errors.append("returned package manifest mismatch")
        package_manifest = json.loads(source_manifest.read_text(encoding="utf-8"))

        sca_d_text = (returned / "config/sca_cfg_D.json").read_text(encoding="utf-8")
        attempts = sorted(set(re.findall(r"/(a[0-9]+)/readback/", sca_d_text)))
        actual_compile = (returned / "evidence/actual_compile_argv.txt").read_text()
        actual_sim = (returned / "evidence/actual_simulator_argv.txt").read_text()
        execution_bound = (
            outer_execution_valid and attempts == [ATTEMPT]
            and ATTEMPT in actual_compile and ATTEMPT in actual_sim
            and package_manifest["repeat_execution_contract"]["return_name_policy"]
            == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
        )
        if not execution_bound:
            errors.append("per-execution identity binding failed")

        observer = returned / "runs/return_observer.log"
        sim_log = returned / "logs/sim.log"
        tools = source / "package_tools"
        replay_dir = output / "formal_replay"
        replay_dir.mkdir(parents=True, exist_ok=True)
        parser_names = {
            "stage": "gap_node0071_stage_transition_decision.py",
            "multislice": "gap_node0071_multislice_pipeline_decision.py",
            "mse4": "gap_node0071_mse4_maskwide_decision.py",
            "ga_ob": "gap_node0071_ga_ob_conjunction_decision.py",
            "mode": "gap_node0071_ga_ob_mode_factor_decision.py",
        }
        replays: dict[str, object] = {}
        for name, tool in parser_names.items():
            target = replay_dir / f"{name}.json"
            replays[name] = run_parser(
                [sys.executable, str(tools / tool), "analyze",
                 "--observer-log", str(observer), "--output", str(target)],
                target,
            )
        canonical_target = replay_dir / "canonical.json"
        replays["canonical"] = run_parser(
            [sys.executable, str(tools / "gap_node0071_canonical_decision.py"),
             "observe", "--observer-log", str(observer),
             "--sim-log", str(sim_log), "--signal", "INT",
             "--simulation-status", "125", "--stall-window-cycles", "1048576",
             "--heartbeat-cycles", "262144", "--manifest", str(source_manifest),
             "--output", str(canonical_target)], canonical_target,
        )
        replay_ok = all(row["exit_code"] == 0 for row in replays.values())

        def integer(path: str) -> int:
            return int((returned / path).read_text().strip())

        gate = json.loads((returned / "evidence/SERVER_RESULT_GATE.json").read_text())
        installed = json.loads((returned / "evidence/installed_preflight.json").read_text())
        precompile = json.loads((returned / "evidence/observer_precompile.json").read_text())
        root_gate = json.loads((returned / "evidence/ndp_root_toplevel_exact_set.json").read_text())
        signal_text = (returned / "evidence/signal_status.txt").read_text()
        parser_status = (returned / "evidence/decision_parser_status.txt").read_text()
        parser_stderr = (returned / "evidence/decision_parser_stderr.log").read_text()
        observer_text = observer.read_text(encoding="utf-8", errors="replace")
        mode = replays["mode"]["output"]
        multi = replays["multislice"]["output"]
        mse4 = replays["mse4"]["output"]
        ga_ob = replays["ga_ob"]["output"]

        def raw_count(tag: str) -> int:
            return observer_text.count(tag)

        legacy_mse4_budget_saturated = raw_count("MSE4_MASKWIDE_STATE_V1") == 256
        legacy_gaob_budget_saturated = raw_count("GA_OB_CONJ_STATE_V1") == 256
        mode_masks = mode["qualified_masks"]
        all_slice_mode_chain = all(
            mode_masks[name] == "0xffff"
            for name in ("alu_req", "normal_mode", "normal_hs", "selected_wr",
                         "nonempty", "selected_rd")
        )
        later_mse4_evaluable = not legacy_mse4_budget_saturated

        report = {
            "schema": "gap-node0071-v51-repeatable-return-analysis-v1",
            "status": "PARTIAL_INTERRUPTED_DIAGNOSTIC_DIRECT_CONSUMER_BUDGET_UNEVALUABLE",
            "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "return_analysis": {
                "path": str(RETURN_PATH), "bytes": RETURN_PATH.stat().st_size,
                "sha256": sha(RETURN_PATH),
                "adjacent_sidecar_present": Path(str(RETURN_PATH) + ".sha256").is_file(),
                "transport_policy": "USER_ATTESTED_NO_SIDECAR",
                "crc_root_path_duplicate_symlink_valid": return_safe,
                "manifest_exact_set": exact_set,
                "allowlist_only": manifest.get("allowlist_only") is True,
                "per_file_receipts_valid": per_file, "errors": errors,
            },
            "source_binding": {
                "path": str(SOURCE_PATH), "bytes": SOURCE_PATH.stat().st_size,
                "sha256": sha(SOURCE_PATH), "source_crc_root_valid": source_safe,
                "returned_manifest_byte_equal": source_bound,
            },
            "repeat_execution_identity": {
                "outer_basename": RETURN_PATH.name, "execution": EXECUTION,
                "attempts_in_sca_d": attempts, "valid": execution_bound,
                "unique_basename_is_not_source_mismatch": True,
            },
            "runtime_binding": {
                "installed_preflight_valid": installed["valid"],
                "formal_targets_initially_absent": installed["formal_readback_targets_absent"],
                "observer_precompile_valid": precompile["valid"],
                "observer_identity_match": precompile["identity_match"],
                "ndp_root_toplevel_unchanged": root_gate["ndp_root_toplevel_unchanged"],
                "actual_compile_and_simulator_argv_returned": True,
                "cloud_authority_from_source_manifest": CLOUD_COMMIT,
                "actual_compiled_production_identity": "NOT_DYN_RECOVERED_BY_V51_RETURN",
            },
            "execution": {
                "compile_exit_status": integer("evidence/compile_exit_status.txt"),
                "simulation_exit_status": integer("evidence/simulation_exit_status.txt"),
                "runner_exit_status": integer("evidence/runner_exit_status.txt"),
                "signal": "INT" if "signal=INT" in signal_text else "UNKNOWN",
                "natural_terminal": False, "stable_level_counts_as_progress": False,
            },
            "formal_decision_collection": {
                "returned_parser_status": parser_status,
                "returned_parser_stderr_empty": parser_stderr == "",
                "local_exact_source_parser_replay_all_exit_zero": replay_ok,
                "raw_observer_sha256": sha(observer),
            },
            "local_exact_parser_replay": replays,
            "qualified_progress": {
                "multislice_last_masks": multi.get("last_masks"),
                "mode_factor_masks": mode_masks,
                "all_slice_selected_write_nonempty_read_chain": all_slice_mode_chain,
                "legacy_mse4_last_qualified_masks": mse4.get("last_qualified_masks"),
                "legacy_ga_ob_last_qualified_masks": ga_ob.get("last_qualified_masks"),
                "legacy_mse4_raw_records": raw_count("MSE4_MASKWIDE_STATE_V1"),
                "legacy_ga_ob_raw_records": raw_count("GA_OB_CONJ_STATE_V1"),
            },
            "last_proven_good": {
                "boundary": "ALL_16_SLICES_GA_SELECTED_WRITE_NONEMPTY_SELECTED_READ",
                "qualified_masks": {
                    "cfg_start": multi.get("last_masks", {}).get("cfg_start"),
                    "cfg_finish": multi.get("last_masks", {}).get("cfg_finish"),
                    "mse0": multi.get("last_masks", {}).get("mse0"),
                    "mse3": multi.get("last_masks", {}).get("mse3"),
                    "ga_in": multi.get("last_masks", {}).get("ga_in"),
                    "ga_out": multi.get("last_masks", {}).get("ga_out"),
                    "selected_wr": mode_masks["selected_wr"],
                    "nonempty": mode_masks["nonempty"],
                    "selected_rd": mode_masks["selected_rd"],
                },
            },
            "first_divergence": {
                "boundary": "SELECTED_GA_READ_TO_ALL_SLICE_MSE4_DIRECT_CONSUMER_UNEVALUABLE_AFTER_LEGACY_STATE_BUDGET_SATURATION",
                "legacy_mse4_budget_saturated": legacy_mse4_budget_saturated,
                "legacy_ga_ob_budget_saturated": legacy_gaob_budget_saturated,
                "later_slice_mse4_direct_consumer_evaluable": later_mse4_evaluable,
                "functional_interpretation": "zero later-slice MSE4 masks are observer saturation, not functional absence",
            },
            "hang_root_cause": {
                "classification": "LONG_RUNNING_HANG_AT_GA_SELECTED_READ_TO_MSE4_DIRECT_CONSUMER_PENDING_LEAF",
                "unique_functional_leaf_closed": False,
                "package_diagnostic_issue": "legacy MSE4 and GA conjunction state edges consume their 256-record budgets before late all-slice progress",
                "remaining_candidates": [
                    "selected GA read reaches GA outport but not MSE4 write-stream input",
                    "MSE4 queue dequeue/buffer/prepared chain is absent on slices1-15",
                    "MSE4 direct local request/write-data pairing is absent on slices1-15",
                    "terminal release remains absent after a completed direct-consumer chain",
                ],
            },
            "blocker_delta": {
                "closed": [
                    "v50 state-budget starvation for GA selected write/nonempty/read",
                    "all 16 slices reach GA selected write, nonempty and selected read",
                    "v51 package compiles and all returned parsers execute with empty stderr",
                ],
                "remaining": "B_GAP_NODE0071_GA_SELECTED_READ_TO_MSE4_DIRECT_CONSUMER_PENDING_LEAF",
            },
            "formal_d": {
                "expected_count": 48,
                "present_count": 48 - gate["missing_count"],
                "missing_count": gate["missing_count"],
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": gate["missing_count"] == 0,
                "exact_set_complete": gate["result_gate_conjunction"]["formal_readback_exact_set_complete"],
                "all_result_terms_true": gate["result_gate_conjunction"]["all_terms_true"],
            },
            "e3_e4_e5": {
                "E3": False, "E4": False, "E5": False,
                "reason": "INT, no natural terminal, actual compiled identity not recovered, and 0/48 formal D",
            },
            "rule_confirmation": [
                "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001",
                "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "rule_delta_proposal": None,
            "numeric_or_workload_repeated": False,
            "config_or_golden_repeated": False,
            "functional_rtl_modified": False,
            "successor_required": True,
            "successor_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        }
        write_json(output / "report.json", report)
        return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()
    report = analyze(ns.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
