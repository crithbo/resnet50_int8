#!/usr/bin/env python3
"""Validate QAdd v68 exact tree/ZIP and the audited third-attempt fixes."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import types
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
PRIOR = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
PRIOR_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"
TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v68.svh"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v68.py"
EVALUATOR = "package_tools/server_tb_vcd_runtime_supervision.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def module(path: Path, name: str) -> Any:
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), value.__dict__)
    return value


def adapted_v67_validator() -> dict[str, Any]:
    path = ROOT / "tools/validate_qlinearadd_node0007_v67_cfg42_target_capture.py"
    source = path.read_text(encoding="utf-8")
    replacements = {
        'PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"': f'PACKAGE = "{PACKAGE}"',
        'PRIOR = "r5_qadd_n7_tailround_lanephase_v66_cfg42"': f'PRIOR = "{PRIOR}"',
        'PRIOR_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"': f'PRIOR_SHA = "{PRIOR_SHA}"',
        'TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"': f'TB = "{TB}"',
        'FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"': 'FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v68.py"',
        'provenance/v67_current_source_identity.json': 'provenance/v68_current_source_identity.json',
        'qlinearadd_node0007_tb_vcd_live_supervision_v67.py': 'qlinearadd_node0007_tb_vcd_live_supervision_v68.py',
        'CODEX_TBVCD_PRETARGET_SAFETY_SNAPSHOT_V1': 'CODEX_TBVCD_PRETARGET_SAFETY_PULSE_OPEN_V1',
        'snapshot = "if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active)) begin" in tb': 'snapshot = "if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active) && !tbvcd_pretarget_pulse_open) begin" in tb',
    }
    for old, new in replacements.items():
        if old not in source:
            raise RuntimeError(f"v67 validator adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v68_adapted_v67_validator", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def evaluator_request(samples: list[dict[str, Any]]) -> dict[str, Any]:
    helper = ROOT / "tools/server_tb_vcd_runtime_supervision.py"
    authority = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "helper_path": EVALUATOR,
        "helper_sha256": sha(helper),
        "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }
    phase = {
        "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF",
        "helper_path": EVALUATOR,
        "helper_sha256": sha(helper),
        "replay_cases": [
            {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
            {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
        ],
    }
    return {
        "package_id": PACKAGE,
        "execution_id": "v68-negative-control",
        "attempt_id": "a0",
        "started": True,
        "actual_argv_sha256": "0" * 64,
        "catalog_sha256": "0" * 64,
        "candidate_matrix_sha256": "0" * 64,
        "tb_source_sha256": "0" * 64,
        "elaboration_sha256": "0" * 64,
        "samples": samples,
        "candidate_catalog_complete": True,
        "unresolved_xz": True,
        "flush": {},
        "process_tree": {},
        "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority,
        "dumpoff_consistency_authority": phase,
    }


def sample(seq: int, wall: int, vcd_tick: int, execution_tick: int, cycles: int) -> dict[str, Any]:
    return {
        "seq": seq,
        "wall_seconds": wall,
        "appended_vcd_timestamp_ticks": vcd_tick,
        "sim_time_ticks": execution_tick,
        "display_sim_time_ticks": execution_tick,
        "owner_clock_cycles": cycles,
        "sim_cycles": cycles,
        "causal_progress_events": 0,
        "qualified_progress_counters": {"pretarget_matrix_completions": 2},
        "causal_state_digest": "x" * 64,
        "global_progress_witness": {"target_count": 0, "pretarget_matrix_completions": 2},
        "unresolved_xz": True,
        "vcd_bytes": 6360 + seq * 100,
        "disk_space_ok": True,
        "write_ok": True,
        "quota_ok": True,
        "stop_marker_count": 0,
        "target_entry_observed": False,
    }


def validate_delta(package: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    tb = (package / TB).read_text(encoding="utf-8")
    live_path = package / LIVE
    live_text = live_path.read_text(encoding="utf-8")
    pulse = load(package / "diagnostics/pretarget_safety_pulse_contract.json")
    audit = load(package / "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    evaluator = module(package / EVALUATOR, "qadd_v68_eval")
    live = module(live_path, "qadd_v68_live")

    frozen_trace = [sample(0, 0, 0, 0, 0), sample(1, 30, 0, 100, 81920), sample(2, 60, 0, 300, 278528), sample(3, 90, 0, 500, 425984)]
    pulse_trace = [sample(0, 0, 0, 0, 0), sample(1, 30, 100, 100, 81920), sample(2, 60, 300, 300, 278528), sample(3, 90, 500, 500, 425984)]
    frozen_receipt = evaluator.evaluate(evaluator_request(frozen_trace))
    pulse_receipt = evaluator.evaluate(evaluator_request(pulse_trace))

    original_rows = live.process_rows
    try:
        live.process_rows = lambda: [
            {"pid": 123, "ppid": 1, "pgid": 555, "sid": 555, "stat": "S", "comm": "reused", "start_time_ticks": 11}
        ]
        reused_known = {123: 10}
        pid_reuse_excluded = live.owned(123, 123, reused_known) == [] and reused_known == {}
        live.process_rows = lambda: [
            {"pid": 124, "ppid": 1, "pgid": 124, "sid": 124, "stat": "Z", "comm": "dead", "start_time_ticks": 12}
        ]
        zombie_known = {124: 12}
        nonchild_zombie_excluded = live.owned(124, 124, zombie_known) == []
    finally:
        live.process_rows = original_rows

    pulse_open = tb.index("CODEX_TBVCD_PRETARGET_SAFETY_PULSE_OPEN_V1")
    pulse_close = tb.index("CODEX_TBVCD_PRETARGET_SAFETY_PULSE_CLOSE_V1")
    same_time_pattern = "$dumpon;\n          $dumpflush;\n          $dumpoff;"
    final_reap_block = live_text[live_text.index("reap_deadline ="):live_text.index("    finally:", live_text.index("reap_deadline ="))]
    checks = {
        "audit_triggered_and_passed": audit.get("pass") is True and audit.get("disposition") == "MACHINE_READABLE_PACKAGE_LOCAL_EXEMPTION_WITH_NEGATIVE_CONTROLS",
        "exact_exemption_bound": pulse.get("exemption_id") == "qadd-pretarget-safety-pulse-v1" and pulse.get("pass") is True,
        "pulse_state_declared": "logic tbvcd_pretarget_pulse_open;" in tb,
        "pulse_open_and_close_markers": pulse_open >= 0 and pulse_close >= 0,
        "pulse_close_on_later_owner_edge": "if (tbvcd_pretarget_pulse_open &&" in tb and "spanned_owner_tick=1" in tb,
        "same_time_dumpon_dumpoff_absent": same_time_pattern not in tb,
        "target_capture_still_continuous": "Full 64-signal causal-cone capture is continuous from this boundary" in tb and "full_continuous_capture=1" in tb,
        "real_v67_static_trace_freezes": frozen_receipt.get("stop_reason") == "SIM_TIME_FREEZE",
        "owner_tick_pulse_trace_continues": pulse_receipt.get("stop_reason") != "SIM_TIME_FREEZE" and pulse_receipt.get("final_counters", {}).get("freeze_intervals") == 0,
        "pid_reuse_identity_excluded": pid_reuse_excluded,
        "nonchild_zombie_excluded": nonchild_zombie_excluded,
        "pid_start_time_bound": all(token in live_text for token in ("start_time_ticks", "PID_PLUS_PROC_START_TIME_TICKS", "group_still_owned")),
        "final_kill_action_bounded": final_reap_block.count("signal_owned(") <= 1,
        "canonical_evaluator_byte_equal": (package / EVALUATOR).read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
    }
    return checks, {
        "frozen_trace_stop_reason": frozen_receipt.get("stop_reason"),
        "pulse_trace_stop_reason": pulse_receipt.get("stop_reason"),
        "pid_reuse_known_after": reused_known,
        "zombie_known_after": zombie_known,
        "final_reap_signal_calls": final_reap_block.count("signal_owned("),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    adapter = adapted_v67_validator()
    base = adapter["load_v66_validator"]()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qadd-v68-exact-") as raw:
        temp = Path(raw)
        package = base["safe_extract"](args.zip, temp / "package", PACKAGE)
        prior = base["safe_extract"](args.prior_zip, temp / "prior", PRIOR)
        tree_base, tree_base_errors, tree_base_facts = base["validate_tree"](args.tree.resolve(), prior)
        zip_base, zip_base_errors, zip_base_facts = base["validate_tree"](package, prior)
        tree_capture, tree_capture_facts = adapter["validate_capture"](args.tree.resolve(), temp / "tree_probe")
        zip_capture, zip_capture_facts = adapter["validate_capture"](package, temp / "zip_probe")
        tree_contract = load(args.tree.resolve() / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        zip_contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        tree_capture["first_round_current_source"] = tree_contract["diagnostic_round"].get("round_index") == 2 and tree_contract["diagnostic_round"].get("round_kind") == "EVIDENCE_REFINED_SUCCESSOR" and tree_contract["diagnostic_round"].get("evolution", {}).get("predecessor", {}).get("package_id") == PRIOR
        zip_capture["first_round_current_source"] = zip_contract["diagnostic_round"].get("round_index") == 2 and zip_contract["diagnostic_round"].get("round_kind") == "EVIDENCE_REFINED_SUCCESSOR" and zip_contract["diagnostic_round"].get("evolution", {}).get("predecessor", {}).get("package_id") == PRIOR
        tree_delta, tree_delta_facts = validate_delta(args.tree.resolve())
        zip_delta, zip_delta_facts = validate_delta(package)
        checks = {
            "base_config42_staging": not tree_base_errors,
            "base_config42_exact_zip": not zip_base_errors,
            "base_target_capture_staging": all(tree_capture.values()),
            "base_target_capture_exact_zip": all(zip_capture.values()),
            "third_attempt_delta_staging": all(tree_delta.values()),
            "third_attempt_delta_exact_zip": all(zip_delta.values()),
            "tree_zip_file_map_equal": base["file_map"](args.tree.resolve()) == base["file_map"](package),
            "deterministic_zip_recompute_equal": args.zip.read_bytes() == args.repeat_zip.read_bytes(),
            "v67_pending_byte_frozen": sha(args.prior_zip) == PRIOR_SHA,
        }
        errors.extend(f"tree_base:{item}" for item in tree_base_errors)
        errors.extend(f"zip_base:{item}" for item in zip_base_errors)
        errors.extend(f"tree_capture:{name}" for name, passed in tree_capture.items() if not passed)
        errors.extend(f"zip_capture:{name}" for name, passed in zip_capture.items() if not passed)
        errors.extend(f"tree_delta:{name}" for name, passed in tree_delta.items() if not passed)
        errors.extend(f"zip_delta:{name}" for name, passed in zip_delta.items() if not passed)
        errors.extend(name for name, passed in checks.items() if not passed)
        report = {
            "schema": "qadd-v68-config42-owner-tick-exact-validation-v1",
            "package_id": PACKAGE,
            "checks": checks,
            "tree_base_checks": tree_base,
            "zip_base_checks": zip_base,
            "tree_capture_checks": tree_capture,
            "zip_capture_checks": zip_capture,
            "tree_delta_checks": tree_delta,
            "zip_delta_checks": zip_delta,
            "facts": {
                "tree_base": tree_base_facts,
                "zip_base": zip_base_facts,
                "tree_capture": tree_capture_facts,
                "zip_capture": zip_capture_facts,
                "tree_delta": tree_delta_facts,
                "zip_delta": zip_delta_facts,
            },
            "package": identity(args.zip.resolve()),
            "prior_pending": identity(args.prior_zip.resolve()),
            "storage_manager_called": False,
            "server_actions_performed": [],
            "pass": not errors,
            "errors": errors,
            "claim_boundary": "Local exact package/negative-control validation only; no production or terminal claim.",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
