"""Receipt-bound analysis of the QAdd node0007 v56 lane-phase return.

This never runs the DUT and never recomputes the frozen numeric/workload/config
or golden assets.  The source/return ZIPs are read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
NAME = "r5_qadd_n7_tailround_lanephase_v56"
RETURN_ROOT = NAME + "_return"
EXECUTION = "r1786417542514431046_867213"
RETURN_BYTES = 247_070
RETURN_SHA = "c8a59e24a0acef95210d4ae42872350e5e174a78b9ad7bb39911652b69ea18e4"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{NAME}.zip"
SOURCE_BYTES = 70_701_485
SOURCE_SHA = "78e98876977060c3ea5c29ec93e130dbd48dc13c0d8386e8c5e42c075e2055fc"
PLAN = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-candidate/source_bound_probe_plan.json"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "whole_net_specialist": ROOT / ".agents/rules/整网测试收敛优化专项规则.md",
    "hardware_sim_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inventory(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.filename in seen:
                duplicates.append(info.filename)
            seen.add(info.filename)
            if not pure.parts:
                unsafe.append(info.filename)
                continue
            roots.add(pure.parts[0])
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                symlinks.append(info.filename)
        if len(roots) != 1:
            raise ValueError(f"single ZIP root required: {sorted(roots)}")
        root = next(iter(roots))
        prefix = root + "/"
        for info in archive.infolist():
            if not info.is_dir():
                files[info.filename[len(prefix):]] = archive.read(info)
    return root, files, {
        "crc_valid": bad_crc is None,
        "root": root,
        "entry_count": len(files),
        "duplicates": duplicates,
        "unsafe_paths": unsafe,
        "symlinks": symlinks,
    }


def obj(files: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(files[name])
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    return_path = args.return_zip.resolve()
    if return_path.stat().st_size != RETURN_BYTES or sha(return_path) != RETURN_SHA:
        errors.append("formal return bytes/SHA differ")
    if SOURCE.stat().st_size != SOURCE_BYTES or sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen source bytes/SHA differ")

    return_root, returned, rstruct = inventory(return_path)
    source_root, source, sstruct = inventory(SOURCE)
    if return_root != RETURN_ROOT or source_root != NAME:
        errors.append("return/source internal root identity differs")
    for label, structure in (("return", rstruct), ("source", sstruct)):
        if not structure["crc_valid"] or structure["duplicates"] or structure["unsafe_paths"] or structure["symlinks"]:
            errors.append(f"{label} ZIP structural gate failed")

    core_manifest = obj(returned, "RETURN_CORE_MANIFEST.json")
    core_status = obj(returned, "return_core/RETURN_CORE_STATUS.json")
    sim_receipt = obj(returned, "return_core/SIM_EXIT_RECEIPT.json")
    plugin_status = json.loads(returned["return_core/RETURN_PLUGIN_STATUS.json"])
    receipts = {row["path"]: row for row in core_manifest["core_entry_receipts"]}
    receipt_errors: list[str] = []
    for name, row in receipts.items():
        if name not in returned:
            receipt_errors.append(f"missing:{name}")
        elif len(returned[name]) != row["bytes"]:
            receipt_errors.append(f"size:{name}")
        elif sha_bytes(returned[name]) != row["sha256"]:
            receipt_errors.append(f"sha:{name}")
    plugin_ids = [row["plugin_id"] for row in plugin_status]
    expected = set(receipts) | {
        "RETURN_CORE_MANIFEST.json",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
    }
    for plugin_id in plugin_ids:
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    exact_set = set(returned) == expected
    if receipt_errors or not exact_set or core_manifest.get("missing_required_entries") != []:
        errors.append("return core exact-set/per-file/required-entry gate failed")

    source_manifest_bytes = source["TEST_PACKAGE_MANIFEST.json"]
    source_binding = (
        returned["source_package/TEST_PACKAGE_MANIFEST.json"] == source_manifest_bytes
        and returned["evidence/PACKAGE_MANIFEST.json"] == source_manifest_bytes
    )
    smanifest = json.loads(source_manifest_bytes)
    source_bound_members = {
        "source_package/source_bound_probe_binding.json": "diagnostics/source_bound_probe_binding.json",
        "source_package/source_bound_generation_report.json": "diagnostics/source_bound_observer_generation_report.json",
    }
    source_bound_binding = all(
        returned[returned_name] == source[source_name]
        for returned_name, source_name in source_bound_members.items()
    )
    identity_ok = (
        source_binding and source_bound_binding
        and core_manifest.get("package_id") == NAME
        and core_manifest.get("execution_id") == EXECUTION
        and core_status.get("package_id") == NAME
        and core_status.get("execution_id") == EXECUTION
        and smanifest.get("package_id") == smanifest.get("install_name") == NAME
    )
    if not identity_ok:
        errors.append("source/package/install/execution binding differs")

    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    signal = returned["evidence/signal_status.txt"].decode().strip()
    timing = dict(
        line.split("=", 1)
        for line in returned["evidence/host_timing.txt"].decode().splitlines()
        if "=" in line
    )
    duration = (int(timing["run_end_ns"]) - int(timing["run_start_ns"])) / 1e9
    sim_log = returned["runs/sim.log"].decode(errors="replace")
    preload_lines = re.findall(r"^\[(\d+)\] JSON: Loading matrix\[(\d+)\]: (.+)$", sim_log, re.MULTILINE)
    stage_starts = re.findall(r"INFO: slice start", sim_log)
    stage_finishes = re.findall(r"INFO: slice completed", sim_log)
    last_preload = preload_lines[-1] if preload_lines else None
    last_burst = re.findall(r"\[Read Burst (\d+)\] Addr=(0x[0-9a-fA-F]+), Length=(\d+) words", sim_log)

    decision = obj(returned, "evidence/source_bound_causal_decision.json")
    source_log = returned["runs/source_bound_causal.log"].decode(errors="replace")
    exact_target_times = [
        int(value)
        for value in re.findall(
            r"kind=(?:EVENT|TRIGGER|STALL).*?slice_with_datahub_mc_group_gen\[0\].*?slice_group_gen\[0\].*?BUFFER_MANAGER\[5\].*? time=(\d+)",
            source_log,
        )
    ]
    first_payload_load_ps = min(
        (int(time_ps) for time_ps, _, path in preload_lines if "matrix_A_linearized" in path),
        default=None,
    )
    last_preload_start_ps = int(last_preload[0]) if last_preload else None
    all_exact_records_pre_stage = (
        bool(exact_target_times) and not stage_starts and last_preload_start_ps is not None
        and max(exact_target_times) < last_preload_start_ps
    )
    observed_instance_counts = {
        key: len(value) for key, value in decision.get("observed_instances", {}).items()
    }
    probe_instance_count = sum(observed_instance_counts.values())
    source_decision_consumable_for_target_stage = bool(stage_starts) and not all_exact_records_pre_stage

    plugins = {
        row["plugin_id"]: {
            "exit_code": row["exit_code"],
            "pass": row["pass"],
            "timed_out": row["timed_out"],
            "required_for_adjudication": row["required_for_adjudication"],
        }
        for row in plugin_status
    }
    result_gate = obj(returned, "evidence/SERVER_RESULT_GATE.json")
    formal = {
        "expected": result_gate.get("expected_readback_count"),
        "present": result_gate.get("observed_readback_count"),
        "missing": result_gate.get("missing_count"),
        "invalid": result_gate.get("invalid_count"),
        "mismatch_bytes": result_gate.get("mismatch_byte_count"),
        "mismatch_evaluable": result_gate.get("mismatch_evaluable"),
        "all_terms_true": result_gate.get("result_gate_conjunction", {}).get("all_terms_true"),
    }
    expected_execution = (
        compile_exit == 0 and simulation_exit == 124 and signal == "NONE"
        and not stage_starts and not stage_finishes and len(preload_lines) == 22
        and last_preload is not None and "slice26/matrix_A_linearized_128bit.txt" in last_preload[2]
        and formal == {
            "expected": 28, "present": 0, "missing": 28, "invalid": 0,
            "mismatch_bytes": 0, "mismatch_evaluable": False, "all_terms_true": False,
        }
        and decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and decision.get("accepted_target_record_count") == 35
        and decision.get("ignored_non_target_record_count") == 4725
        and probe_instance_count == 1008
        and all_exact_records_pre_stage
    )
    if not expected_execution:
        errors.append("execution/preload/source-bound evidence differs from formal v56 return")

    preflight = obj(returned, "evidence/package_preflight.json")
    installed = obj(returned, "evidence/installed_preflight.json")
    runtime_layout = obj(returned, "evidence/runtime_layout_receipt.json")
    root_pre = obj(returned, "evidence/ndp_root_toplevel_pre.json")
    root_post = obj(returned, "evidence/ndp_root_toplevel_post.json")
    fixed_publish = obj(returned, "evidence/fixed_result_preflight.json")
    argv = returned["evidence/actual_simulator_argv.txt"].decode(errors="replace").strip()
    compile_argv = returned["evidence/actual_compile_argv.txt"].decode(errors="replace").strip()
    feature = returned["evidence/feature_receipt.txt"].decode(errors="replace").strip()
    observer_binding = returned["evidence/observer_binding.txt"].decode(errors="replace").strip()
    feature_bound = all(token in "\n".join((argv, compile_argv, feature, observer_binding)) for token in (
        "+CODEX_CAUSAL_OBSERVER", "source_bound_causal_observer.svh", "NATIVE_RETURN_OBSERVER_ENABLE"
    ))
    if not feature_bound:
        errors.append("observer compile/runtime/feature binding differs")

    controls = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
            "mutable_provenance_only": name == "plan_mutable",
        }
        for name, path in RULES.items()
    }
    report = {
        "schema": "qlinearadd-node0007-tailround-lanephase-v56-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_REQUIRED",
        "analysis_valid": not errors,
        "errors": errors,
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "dut_rerun": False,
        "control_receipts": controls,
        "generator_receipt": {"path": GENERATOR.relative_to(ROOT).as_posix(), "bytes": GENERATOR.stat().st_size, "sha256": sha(GENERATOR)},
        "transport_and_identity": {
            "external_sidecar": "NOT_REQUIRED_USER_ATTESTED_TRANSPORT",
            "return": {"path": str(return_path), "bytes": return_path.stat().st_size, "sha256": sha(return_path)},
            "return_structure": rstruct,
            "return_core_exact_set": exact_set,
            "return_core_per_file_errors": receipt_errors,
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha(SOURCE), "structure": sstruct},
            "source_manifest_byte_bound": source_binding,
            "source_bound_receipts_byte_bound": source_bound_binding,
            "package_install_execution_identity_bound": identity_ok,
            "package_preflight": preflight,
            "installed_preflight": installed,
            "runtime_layout": runtime_layout,
            "fixed_publication": fixed_publish,
            "ndp_root_exact_set_unchanged": root_pre.get("direct_child_set_sha256") == root_post.get("direct_child_set_sha256"),
            "actual_compile_argv": compile_argv,
            "actual_simulator_argv": argv,
            "feature_four_way_bound": feature_bound,
            "core_disposition": core_status.get("disposition"),
            "core_required_plugin_failures": core_status.get("required_plugin_failures"),
        },
        "RETURN_ANALYSIS": {
            "outcome": "TIMEOUT_DURING_INPUT_PRELOAD_BEFORE_TARGET_STAGE_START",
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "signal": signal,
            "sim_started": sim_receipt.get("sim_started"),
            "natural_terminal": sim_receipt.get("natural_terminal_observed"),
            "host_duration_seconds": duration,
            "host_duration_hours": duration / 3600,
            "preload_records_completed": len(preload_lines),
            "expected_total_preload_records": 30,
            "last_preload": {"time_ps": int(last_preload[0]), "matrix_index": int(last_preload[1]), "path": last_preload[2]} if last_preload else None,
            "last_read_burst": {"index": int(last_burst[-1][0]), "address": last_burst[-1][1], "words": int(last_burst[-1][2])} if last_burst else None,
            "ordered_stage_starts": len(stage_starts),
            "ordered_stage_finishes": len(stage_finishes),
            "plugins": plugins,
        },
        "LANE_PHASE_DIAGNOSTIC": {
            "returned_decision": decision.get("decision"),
            "returned_reason": decision.get("reason"),
            "candidate_match_count": decision.get("candidate_match_count"),
            "observations": decision.get("observations"),
            "raw_records": decision.get("raw_record_count"),
            "accepted_target_records": decision.get("accepted_target_record_count"),
            "ignored_non_target_records": decision.get("ignored_non_target_record_count"),
            "observed_instances_per_boundary": observed_instance_counts,
            "materialized_probe_instances": probe_instance_count,
            "exact_target_event_time_min_ps": min(exact_target_times) if exact_target_times else None,
            "exact_target_event_time_max_ps": max(exact_target_times) if exact_target_times else None,
            "first_payload_preload_time_ps": first_payload_load_ps,
            "all_exact_target_records_pre_target_stage": all_exact_records_pre_stage,
            "target_stage_evidence_consumable": source_decision_consumable_for_target_stage,
            "config_leaf_authorized": False,
            "reason": "No EXEC_START occurred; all accepted exact-target records precede the last observed preload and therefore cannot adjudicate tail_round lane-phase behavior.",
        },
        "LAST_PROVEN_GOOD": "PACKAGE_INSTALL_COMPILE_AND_INPUT_PRELOAD_THROUGH_PART_OF_SLICE26",
        "FIRST_DIVERGENCE": "SIMULATION_TIMEOUT_DURING_MATRIX_A_PRELOAD_BEFORE_OP_TAIL_ROUND_EXEC_START",
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_DIAGNOSTIC_OVERHEAD_AND_PRESTAGE_QUALIFICATION_DEFECT",
            "functional_root_cause_status": "UNRESOLVED_NOT_OBSERVED",
            "proof": [
                "The simulator reached matrix preload index 21 and never emitted INFO: slice start.",
                "The generated source-bound observer materialized six probes in each of 168 Buffer instances (1008 probes total).",
                "All 35 parser-accepted exact-target records occurred without any EXEC_START and before the last observed preload; they are pre-stage state, not tail_round transactions.",
                "The parser correctly returned EVIDENCE_INCOMPLETE; no returned evidence authorizes a config or RTL change.",
            ],
            "correcting_surface": "package-local generated diagnostic topology/predicate qualification only",
            "config_or_rtl_change_allowed": False,
        },
        "PROGRESS_VS_V54": {
            "functional_progress": "ZERO",
            "closed": [],
            "diagnostic_progress": "NEGATIVE_RESULT_IDENTIFIED_PACKAGE_OBSERVER_FANOUT_AND_PRESTAGE_CONTAMINATION",
            "unchanged_open_boundary": "request mask 0x33333333 versus valid mask 0xcccccccc remains unresolved",
        },
        "formal_D": formal,
        "SERVER_RESULT_GATE": {
            "pass": False,
            "reason": "compile=0, but simulation=124, no target stage start/natural terminal, and all 28 formal D are missing; mismatch=0 is unevaluable",
        },
        "evidence_levels": {"E3": False, "E4": False, "E5": False},
        "claim_boundary": {
            "scope": "isolated op_tail_round host-precomputed diagnostic stimulus",
            "host_precomputed_internal_tensor": True,
            "producer_evidence_claimed": False,
            "full_chain_claimed": False,
        },
        "BLOCKER_DELTA": {
            "closed": [],
            "superseded": ["v56 raw pre-stage arm/read observations as target-stage evidence"],
            "opened": ["B_QADD_V56_SOURCE_BOUND_OBSERVER_FANOUT_PRESTAGE_QUALIFICATION"],
            "retained": ["B_QADD_TAILROUND_BUFFER5_TEMPORAL_LANE_PHASE_MISMATCH_3333_VS_CCCC"],
        },
        "SUCCESSOR": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "highest_information_fix": "merge redundant Buffer probes into one generated multiclass boundary and filter to records after ordered EXEC_START; keep workload/config/numeric/golden/2h timeout/RTL byte-equal",
            "config_change": False,
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED_WITH_COUNTEREXAMPLE_APPLICATION",
            "rule_ids": [
                "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "statement": "v56 demonstrates why pre-stage held/default state and non-target instances must not consume or decide the target qualified causal record. Existing rules already require the narrowed successor; no synonymous rule delta is proposed.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"analysis_valid": not errors, "errors": errors, "output": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
