#!/usr/bin/env python3
"""Deterministic supervisor state machine for bounded causal-cone TB VCD runs.

The production runner can emit periodic samples into JSONL and use the same
thresholds to drive $dumpoff/$dumpflush plus TERM/WAIT/KILL/REAP.  This local
implementation validates the resulting decision and is intentionally free of
vendor waveform APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROFILE = "TB_VCD_BOUNDED_CAUSAL_CONE"
SCHEMA = "server-tb-vcd-runtime-receipt-v1"
SOFT = 100_000_000
OPERATIONAL = 8_000_000_000
RETURN = 10_000_000_000
WALL = 3600
SUSPECTED = 1_048_576
DUMP_OFF = 4_194_304
GRACE = 262_144
FREEZE_INTERVALS = 3
FREEZE_SECONDS = 30
HEARTBEAT_WIDTH_BITS = 64
HEARTBEAT_CADENCE_CYCLES = 16_384
REPLAY_EXPECTED = {
    "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
    "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
    "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
    "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
}
DUMPOFF_REPLAY_EXPECTED = {
    "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE": "CONTINUE",
    "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU": "CAUSAL_PLATEAU",
    "REPEATED_STOP_MARKER": "FAIL_CLOSED",
}


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _identity(request: dict[str, Any], key: str) -> str:
    value = request.get(key)
    return value if isinstance(value, str) and len(value) == 64 else "0" * 64


def _vcd_timestamp(sample: dict[str, Any]) -> int:
    value = sample.get("appended_vcd_timestamp_ticks")
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else -1


def _execution_sim_time(sample: dict[str, Any]) -> int:
    value = sample.get("sim_time_ticks")
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else -1


def _empty_dump_control() -> dict[str, Any]:
    return {
        "state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
        "planned_dumpoff_observed": False,
        "state_monotonic": True,
        "dump_off_cycle": None,
        "dump_off_vcd_timestamp_ticks": None,
        "dump_off_execution_sim_time_ticks": None,
        "post_dump_grace_elapsed_cycles": 0,
        "post_dump_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
        "dump_off_grace_precedes_freeze": True,
        "stop_marker_count": 0,
        "stop_marker_one_shot": True,
    }


def _exact_set_complete(exact_set: Any, evidence: dict[str, Any] | None) -> bool:
    if not isinstance(exact_set, dict) or not isinstance(evidence, dict):
        return False
    members = exact_set.get("members") if isinstance(exact_set.get("members"), list) else []
    paths = [item.get("path") for item in members if isinstance(item, dict)]
    if len(paths) != len(members) or len(paths) != len(set(paths)):
        return False
    vcd_matches = [
        item for item in members
        if isinstance(item, dict)
        and item.get("path") == evidence.get("path")
        and item.get("bytes") == evidence.get("bytes")
        and item.get("sha256") == evidence.get("sha256")
    ]
    return bool(
        len(vcd_matches) == 1
        and exact_set.get("hard_limit_bytes") is None
        and exact_set.get("truncated") is False
        and exact_set.get("sampled") is False
        and exact_set.get("allowlist_complete") is True
        and exact_set.get("published") is True
    )


def _decision_authority_complete(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    rows = value.get("replay_cases") if isinstance(value.get("replay_cases"), list) else []
    observed = {
        row.get("case_id"): row.get("observed_decision")
        for row in rows if isinstance(row, dict)
    }
    return bool(
        value.get("mode") == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and value.get("outer_runner_consumes_only_receipt") is True
        and value.get("independent_exit_logic_absent") is True
        and isinstance(value.get("helper_path"), str) and value.get("helper_path")
        and isinstance(value.get("helper_sha256"), str) and len(value.get("helper_sha256")) == 64
        and observed == REPLAY_EXPECTED
    )


def _dumpoff_consistency_authority_complete(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    rows = value.get("replay_cases") if isinstance(value.get("replay_cases"), list) else []
    observed = {
        row.get("case_id"): row.get("observed_decision")
        for row in rows if isinstance(row, dict)
    }
    return bool(
        value.get("mode") == "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF"
        and isinstance(value.get("helper_path"), str) and value.get("helper_path")
        and isinstance(value.get("helper_sha256"), str) and len(value.get("helper_sha256")) == 64
        and observed == DUMPOFF_REPLAY_EXPECTED
    )


def _archive_timestamp_complete(value: Any, evidence: dict[str, Any] | None, final_tick: int) -> bool:
    return bool(
        isinstance(value, dict)
        and isinstance(evidence, dict)
        and value.get("parse_status") == "COMPLETE"
        and value.get("binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
        and value.get("path") == evidence.get("path")
        and value.get("bytes") == evidence.get("bytes")
        and value.get("sha256") == evidence.get("sha256")
        and value.get("last_timestamp_ticks") == final_tick
    )


def _growth(samples: list[dict[str, Any]], final: dict[str, Any], wall_ceiling: int) -> dict[str, Any]:
    window = samples[-4:]
    if len(window) >= 2:
        dt = max(0.0, float(window[-1].get("wall_seconds", 0)) - float(window[0].get("wall_seconds", 0)))
        db = max(0, int(window[-1].get("vcd_bytes", 0)) - int(window[0].get("vcd_bytes", 0)))
        rate = db / dt if dt else 0.0
    else:
        rate = 0.0
    remaining = max(0.0, wall_ceiling - float(final.get("wall_seconds", 0)))
    projected = int(int(final.get("vcd_bytes", 0)) + rate * remaining)
    return {
        "final_vcd_bytes": int(final.get("vcd_bytes", 0)),
        "soft_warning_exceeded": int(final.get("vcd_bytes", 0)) > SOFT,
        "rolling_bytes_per_second": rate,
        "projected_bytes_at_wall_ceiling": projected,
        "operational_budget_bytes": OPERATIONAL,
        "return_budget_bytes": RETURN,
    }


def evaluate(request: dict[str, Any]) -> dict[str, Any]:
    samples = request.get("samples") if isinstance(request.get("samples"), list) else []
    errors: list[str] = []
    warnings: list[str] = []
    budget_admission = request.get("runtime_budget_admission")
    wall_ceiling = WALL
    if budget_admission is not None:
        guards = budget_admission.get("independent_operational_guards") if isinstance(budget_admission, dict) else None
        selected = budget_admission.get("selected_wall_ceiling_seconds") if isinstance(budget_admission, dict) else None
        recommended = budget_admission.get("projection", {}).get("recommended_wall_ceiling_seconds") if isinstance(budget_admission, dict) else None
        exact_guards = {
            "vcd_operational_budget_bytes": OPERATIONAL,
            "return_budget_bytes": RETURN,
            "disk_space_guard_enabled": True,
            "growth_projection_enabled": True,
            "write_failure_guard_enabled": True,
            "quota_guard_enabled": True,
        }
        if not (
            isinstance(budget_admission, dict)
            and budget_admission.get("schema") == "server-runtime-budget-admission-v1"
            and budget_admission.get("pass") is True
            and isinstance(selected, int) and not isinstance(selected, bool)
            and isinstance(recommended, int) and selected >= recommended
            and WALL <= selected <= 86400
            and isinstance(guards, dict)
            and all(guards.get(key) == value for key, value in exact_guards.items())
        ):
            errors.append("runtime wall override lacks a valid bounded measured admission")
        else:
            wall_ceiling = selected
    heartbeat = request.get("heartbeat_contract") if isinstance(request.get("heartbeat_contract"), dict) else {}
    decision_authority = request.get("decision_authority") if isinstance(request.get("decision_authority"), dict) else None
    dumpoff_consistency_authority = request.get("dumpoff_consistency_authority") if isinstance(request.get("dumpoff_consistency_authority"), dict) else None
    archive_timestamp = request.get("archive_timestamp_receipt") if isinstance(request.get("archive_timestamp_receipt"), dict) else None
    heartbeat_ok = bool(
        heartbeat.get("source") == "APPENDED_VCD_TIMESTAMP"
        and isinstance(heartbeat.get("width_bits"), int)
        and heartbeat.get("width_bits", 0) >= HEARTBEAT_WIDTH_BITS
        and heartbeat.get("signed") is False
        and heartbeat.get("cadence_cycles") == HEARTBEAT_CADENCE_CYCLES
    )
    if not heartbeat_ok:
        errors.append("heartbeat must use non-overflowing unsigned >=64-bit appended VCD timestamps at 16384-cycle cadence")
    if not samples:
        errors.append("runtime sample stream is empty")
        samples = [{"wall_seconds": 0, "sim_cycles": 0, "sim_time_ticks": 0, "appended_vcd_timestamp_ticks": 0, "vcd_bytes": 0}]
    samples = sorted(samples, key=lambda row: (float(row.get("wall_seconds", 0)), int(row.get("seq", 0))))

    started = bool(request.get("started"))
    if not started:
        final = samples[-1]
        return {
            "schema": SCHEMA, "package_id": request.get("package_id", "unknown"),
            "execution_id": request.get("execution_id", "unknown"), "attempt_id": request.get("attempt_id", "unknown"),
            "profile": PROFILE, "actual_argv_sha256": _identity(request, "actual_argv_sha256"),
            "catalog_sha256": _identity(request, "catalog_sha256"), "candidate_matrix_sha256": _identity(request, "candidate_matrix_sha256"),
            "tb_source_sha256": _identity(request, "tb_source_sha256"), "elaboration_sha256": _identity(request, "elaboration_sha256"),
            "started": False, "stop_reason": "COMPILE_NOT_STARTED", "completeness": "ABSENT_COMPILE_NOT_STARTED",
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE", "natural_terminal": False,
            "start": {}, "stop": final, "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
            "time_event_counts": {"final_sim_time_ticks": 0, "final_execution_sim_time_ticks": 0, "final_sim_cycles": 0, "non_clock_events": 0, "causal_progress_events": 0},
            "growth": _growth(samples, final, wall_ceiling), "thresholds": thresholds(wall_ceiling), "final_counters": {},
            "plateau_qualification": _plateau_qualification(False, False, False, False, False, False, False, False),
            "dump_control": _empty_dump_control(),
            "process_tree": {
                "term_sent": False, "wait_completed": True, "kill_sent_if_needed": False,
                "all_reaped": True, "post_kill_reap_deadline_origin": "NOT_APPLICABLE",
                "last_kill_host_monotonic_ns": None, "post_kill_reap_deadline_host_monotonic_ns": None,
                "post_kill_reap_completed": True,
            },
            "runtime_budget_admission": budget_admission,
            "heartbeat_contract": heartbeat, "decision_authority": decision_authority,
            "dumpoff_consistency_authority": dumpoff_consistency_authority,
            "archive_timestamp_receipt": None,
            "target_entry": {"observed": False, "diagnostic_claim": False},
            "vcd_identity": None, "return_exact_set": None, "live_diagnostics": None,
            "warnings": warnings, "errors": errors,
            "claim_boundary": "Compile-not-started core only; no VCD or dynamic claim."
        }

    stop_reason: str | None = None
    stop_sample = samples[-1]
    last_progress_count = -1
    last_progress_cycle = 0
    suspected = False
    dump_off_cycle: int | None = None
    dump_off_vcd_tick: int | None = None
    dump_off_execution_tick: int | None = None
    dump_off_qualified = False
    planned_dumpoff_active = False
    dump_control_monotonic = True
    previous_stop_marker_count = 0
    max_stop_marker_count = 0
    freeze_intervals = 0
    previous: dict[str, Any] | None = None
    candidate_catalog_complete = request.get("candidate_catalog_complete") is True
    unresolved_xz_absent = request.get("unresolved_xz") is False
    owner_clock_advancing = sim_time_advancing = execution_sim_time_advancing = False
    qualified_progress_stable = causal_state_stable = global_progress_stable = False
    timestamp_regression = False

    for sample in samples:
        cycles = int(sample.get("owner_clock_cycles", sample.get("sim_cycles", 0)))
        progress = int(sample.get("causal_progress_events", 0))
        current_vcd_tick = _vcd_timestamp(sample)
        current_execution_tick = _execution_sim_time(sample)
        sample_planned_dumpoff = sample.get("planned_dumpoff") is True
        phase_is_or_enters_dumpoff = planned_dumpoff_active or sample_planned_dumpoff
        raw_stop_marker_count = sample.get("stop_marker_count", previous_stop_marker_count)
        if not isinstance(raw_stop_marker_count, int) or isinstance(raw_stop_marker_count, bool) or raw_stop_marker_count < 0:
            errors.append(f"sample {sample.get('seq')}: stop_marker_count must be a nonnegative cumulative integer")
            stop_marker_count = previous_stop_marker_count
        else:
            stop_marker_count = raw_stop_marker_count
        if stop_marker_count < previous_stop_marker_count:
            dump_control_monotonic = False
            errors.append(f"sample {sample.get('seq')}: stop marker count regressed")
        if stop_marker_count > 1:
            errors.append(f"sample {sample.get('seq')}: STOP marker must be one-shot")
        previous_stop_marker_count = max(previous_stop_marker_count, stop_marker_count)
        max_stop_marker_count = max(max_stop_marker_count, stop_marker_count)
        if current_vcd_tick < 0:
            errors.append(f"sample {sample.get('seq')}: appended VCD timestamp is absent or invalid")
        if current_execution_tick < 0:
            errors.append(f"sample {sample.get('seq')}: execution sim time is absent or invalid")
        if previous is not None:
            previous_vcd_tick = _vcd_timestamp(previous)
            owner_clock_advancing = cycles > int(previous.get("owner_clock_cycles", previous.get("sim_cycles", 0)))
            sim_time_advancing = current_vcd_tick > previous_vcd_tick
            execution_sim_time_advancing = current_execution_tick > _execution_sim_time(previous)
            if current_vcd_tick >= 0 and previous_vcd_tick >= 0 and current_vcd_tick < previous_vcd_tick:
                timestamp_regression = True
            qualified_progress_stable = canonical_sha(sample.get("qualified_progress_counters", {})) == canonical_sha(previous.get("qualified_progress_counters", {}))
            causal_state_stable = isinstance(sample.get("causal_state_digest"), str) and sample.get("causal_state_digest") == previous.get("causal_state_digest")
            global_progress_stable = canonical_sha(sample.get("global_progress_witness", {})) == canonical_sha(previous.get("global_progress_witness", {}))
        plateau_eligible = bool(
            previous is not None and owner_clock_advancing and sim_time_advancing
            and qualified_progress_stable and causal_state_stable and global_progress_stable
            and candidate_catalog_complete and unresolved_xz_absent
        )
        if not phase_is_or_enters_dumpoff and (progress > last_progress_count or not plateau_eligible):
            last_progress_count = progress
            last_progress_cycle = cycles
            suspected = False
        no_progress = max(0, cycles - last_progress_cycle)
        if plateau_eligible and no_progress >= SUSPECTED:
            suspected = True

        if sample_planned_dumpoff and not planned_dumpoff_active:
            declared_cycle = sample.get("planned_dumpoff_cycle")
            declared_vcd_tick = sample.get("planned_dumpoff_vcd_timestamp_ticks")
            if declared_cycle != cycles:
                errors.append(f"sample {sample.get('seq')}: planned dumpoff cycle is not bound to the execution sample")
            if declared_vcd_tick != current_vcd_tick:
                errors.append(f"sample {sample.get('seq')}: planned dumpoff VCD timestamp is not bound to the execution sample")
            dump_off_qualified = bool(plateau_eligible and no_progress >= DUMP_OFF)
            if not dump_off_qualified:
                errors.append(f"sample {sample.get('seq')}: planned dumpoff occurred before the complete plateau intersection")
            planned_dumpoff_active = True
            dump_off_cycle = cycles
            dump_off_vcd_tick = current_vcd_tick
            dump_off_execution_tick = current_execution_tick
        elif planned_dumpoff_active:
            if not sample_planned_dumpoff:
                dump_control_monotonic = False
                errors.append(f"sample {sample.get('seq')}: execution-bound planned dumpoff state cleared")
            if sample.get("planned_dumpoff_cycle", dump_off_cycle) != dump_off_cycle:
                dump_control_monotonic = False
                errors.append(f"sample {sample.get('seq')}: execution-bound planned dumpoff cycle drifted")
            if sample.get("planned_dumpoff_vcd_timestamp_ticks", dump_off_vcd_tick) != dump_off_vcd_tick:
                dump_control_monotonic = False
                errors.append(f"sample {sample.get('seq')}: execution-bound planned dumpoff timestamp drifted")
            if progress > last_progress_count:
                errors.append(f"sample {sample.get('seq')}: qualified progress advanced after planned dumpoff")

        if previous is not None:
            wall_delta = float(sample.get("wall_seconds", 0)) - float(previous.get("wall_seconds", 0))
            previous_freeze_tick = _execution_sim_time(previous) if planned_dumpoff_active else _vcd_timestamp(previous)
            current_freeze_tick = current_execution_tick if planned_dumpoff_active else current_vcd_tick
            if wall_delta >= FREEZE_SECONDS and current_freeze_tick == previous_freeze_tick:
                freeze_intervals += 1
            elif current_freeze_tick != previous_freeze_tick:
                freeze_intervals = 0
        previous = sample

        if timestamp_regression:
            stop_reason, stop_sample = "VCD_TIMESTAMP_REGRESSION", sample
            break
        if sample.get("natural_terminal") is True:
            stop_reason, stop_sample = "NATURAL_TERMINAL", sample
            break
        signal = sample.get("signal")
        if signal in {"HUP", "INT", "TERM"}:
            stop_reason, stop_sample = str(signal), sample
            break
        if sample.get("write_ok") is False:
            stop_reason, stop_sample = "WRITE_FAILURE", sample
            break
        if sample.get("disk_space_ok") is False:
            stop_reason, stop_sample = "DISK_SPACE_FAILURE", sample
            break
        if sample.get("quota_ok") is False:
            stop_reason, stop_sample = "QUOTA_FAILURE", sample
            break
        operational_projection = int(sample.get("vcd_operational_projection_bytes", sample.get("vcd_bytes", 0)))
        return_projection = int(sample.get("return_projection_bytes", sample.get("vcd_bytes", 0)))
        if operational_projection >= OPERATIONAL:
            stop_reason, stop_sample = "VCD_OPERATIONAL_BUDGET", sample
            break
        if return_projection >= RETURN:
            stop_reason, stop_sample = "RETURN_BUDGET_PROJECTION", sample
            break
        if float(sample.get("wall_seconds", 0)) >= wall_ceiling:
            stop_reason, stop_sample = "WALL_CEILING", sample
            break
        if planned_dumpoff_active and dump_off_qualified and dump_off_cycle is not None and cycles - dump_off_cycle >= GRACE:
            stop_reason, stop_sample = "CAUSAL_PLATEAU", sample
            break
        if freeze_intervals >= FREEZE_INTERVALS:
            stop_reason, stop_sample = "SIM_TIME_FREEZE", sample
            break
        if sample.get("exit_code") not in (None, 0):
            stop_reason, stop_sample = "NONZERO_EXIT", sample
            break

    if stop_reason is None:
        stop_reason = "NONZERO_EXIT"
        errors.append("sample stream ended without a terminal supervisor decision")

    if stop_reason == "CAUSAL_PLATEAU" and max_stop_marker_count != 1:
        errors.append("CAUSAL_PLATEAU requires exactly one execution-bound STOP marker")
    if stop_reason != "CAUSAL_PLATEAU" and max_stop_marker_count:
        errors.append("STOP marker appeared without the shared CAUSAL_PLATEAU decision")

    natural = stop_reason == "NATURAL_TERMINAL"
    phase_sim_time_advancing = execution_sim_time_advancing if planned_dumpoff_active else sim_time_advancing
    evidence = request.get("vcd_identity") if isinstance(request.get("vcd_identity"), dict) else None
    return_exact_set = request.get("return_exact_set") if isinstance(request.get("return_exact_set"), dict) else None
    live_diagnostics = request.get("live_diagnostics") if isinstance(request.get("live_diagnostics"), dict) else None
    target_entry_observed = request.get("target_entry_observed") is True
    target_diagnostic_claim = request.get("target_diagnostic_claim") is True
    complete_evidence = bool(
        evidence
        and evidence.get("header_valid") is True
        and isinstance(evidence.get("timescale"), str) and evidence.get("timescale")
        and evidence.get("catalog_complete") is True
        and evidence.get("transitions_complete") is True
        and evidence.get("xz_preserved") is True
        and evidence.get("return_allowlist_member") is True
        and _exact_set_complete(return_exact_set, evidence)
        and _archive_timestamp_complete(archive_timestamp, evidence, max(0, _vcd_timestamp(stop_sample)))
    )
    process = request.get("process_tree") if isinstance(request.get("process_tree"), dict) else {}
    all_reaped = process.get("all_reaped") is True
    kill_sent = process.get("kill_sent_if_needed") is True
    if kill_sent:
        last_kill = process.get("last_kill_host_monotonic_ns")
        reap_deadline = process.get("post_kill_reap_deadline_host_monotonic_ns")
        if not (
            process.get("post_kill_reap_deadline_origin") == "FRESH_AFTER_LAST_KILL"
            and isinstance(last_kill, int) and not isinstance(last_kill, bool)
            and isinstance(reap_deadline, int) and not isinstance(reap_deadline, bool)
            and reap_deadline > last_kill
            and process.get("post_kill_reap_completed") is True
        ):
            errors.append("post-KILL reap must use a fresh bounded deadline started after the last KILL")
    elif not (
        process.get("post_kill_reap_deadline_origin") == "NOT_APPLICABLE"
        and process.get("last_kill_host_monotonic_ns") is None
        and process.get("post_kill_reap_deadline_host_monotonic_ns") is None
        and process.get("post_kill_reap_completed") is True
    ):
        errors.append("non-KILL process receipt has invalid post-KILL reap state")
    flush = request.get("flush") if isinstance(request.get("flush"), dict) else {}
    flush_ok = flush.get("dumpoff") is True and flush.get("dumpflush") is True and flush.get("closed") is True
    if not complete_evidence:
        errors.append("VCD identity/catalog/transition/XZ/allowlist/exact-set/archive-timestamp evidence is incomplete")
    if not _decision_authority_complete(decision_authority):
        errors.append("shared evaluator decision authority or exact four-case replay is incomplete")
    if not _dumpoff_consistency_authority_complete(dumpoff_consistency_authority):
        errors.append("phase-aware planned-dumpoff consistency authority or exact three-case replay is incomplete")
    if not isinstance(live_diagnostics, dict) or live_diagnostics.get("downstream_state_source") != "LIVE_SAME_ATTEMPT" or live_diagnostics.get("first_error_source") != "LIVE_SAME_ATTEMPT" or live_diagnostics.get("stale_evidence_absent") is not True:
        errors.append("downstream and first-error receipts must be live same-attempt state with stale evidence excluded")
    if target_diagnostic_claim and not target_entry_observed:
        errors.append("target diagnostic claim is forbidden because target entry was not observed")
    if not flush_ok:
        errors.append("VCD was not safely dump-off/flushed/closed")
    if not all_reaped:
        errors.append("simulator process tree was not fully reaped")

    diagnostic_complete = natural and complete_evidence and flush_ok and all_reaped and not errors
    if int(stop_sample.get("vcd_bytes", 0)) > SOFT:
        warnings.append("VCD exceeds decimal 100000000-byte soft warning; evidence remains complete and untruncated")
    growth = _growth(samples, stop_sample, wall_ceiling)
    if growth["projected_bytes_at_wall_ceiling"] > RETURN:
        warnings.append("rolling VCD growth projection exceeds the 10GB return planning budget")

    return {
        "schema": SCHEMA,
        "package_id": request.get("package_id", "unknown"), "execution_id": request.get("execution_id", "unknown"), "attempt_id": request.get("attempt_id", "unknown"),
        "profile": PROFILE,
        "actual_argv_sha256": _identity(request, "actual_argv_sha256"), "catalog_sha256": _identity(request, "catalog_sha256"),
        "candidate_matrix_sha256": _identity(request, "candidate_matrix_sha256"), "tb_source_sha256": _identity(request, "tb_source_sha256"),
        "elaboration_sha256": _identity(request, "elaboration_sha256"), "started": True, "stop_reason": stop_reason,
        "completeness": "COMPLETE" if diagnostic_complete else "PARTIAL",
        "diagnostic_status": "DIAGNOSTIC_EVIDENCE_COMPLETE" if diagnostic_complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "natural_terminal": natural,
        "start": samples[0], "stop": stop_sample,
        "flush": {"dumpoff": flush.get("dumpoff") is True, "dumpflush": flush.get("dumpflush") is True, "closed": flush.get("closed") is True},
        "time_event_counts": {
            "final_sim_time_ticks": max(0, _vcd_timestamp(stop_sample)),
            "final_execution_sim_time_ticks": max(0, _execution_sim_time(stop_sample)),
            "final_sim_cycles": int(stop_sample.get("sim_cycles", 0)),
            "non_clock_events": int(stop_sample.get("non_clock_events", 0)), "causal_progress_events": int(stop_sample.get("causal_progress_events", 0)),
        },
        "growth": growth,
        "thresholds": thresholds(wall_ceiling),
        "final_counters": {"no_progress_cycles": max(0, int(stop_sample.get("sim_cycles", 0)) - last_progress_cycle), "plateau_suspected": suspected, "dump_off_cycle": dump_off_cycle, "freeze_intervals": freeze_intervals},
        "plateau_qualification": _plateau_qualification(
            bool(dump_off_qualified or (previous is not None and owner_clock_advancing and phase_sim_time_advancing and qualified_progress_stable and causal_state_stable and global_progress_stable and candidate_catalog_complete and unresolved_xz_absent)),
            owner_clock_advancing, phase_sim_time_advancing, qualified_progress_stable, causal_state_stable,
            global_progress_stable, candidate_catalog_complete, unresolved_xz_absent,
        ),
        "dump_control": {
            "state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
            "planned_dumpoff_observed": planned_dumpoff_active,
            "state_monotonic": dump_control_monotonic,
            "dump_off_cycle": dump_off_cycle,
            "dump_off_vcd_timestamp_ticks": dump_off_vcd_tick,
            "dump_off_execution_sim_time_ticks": dump_off_execution_tick,
            "post_dump_grace_elapsed_cycles": max(0, int(stop_sample.get("sim_cycles", 0)) - dump_off_cycle) if dump_off_cycle is not None else 0,
            "post_dump_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
            "dump_off_grace_precedes_freeze": True,
            "stop_marker_count": max_stop_marker_count,
            "stop_marker_one_shot": max_stop_marker_count <= 1,
        },
        "process_tree": {
            "term_sent": process.get("term_sent") is True, "wait_completed": process.get("wait_completed") is True,
            "kill_sent_if_needed": kill_sent, "all_reaped": all_reaped,
            "post_kill_reap_deadline_origin": process.get("post_kill_reap_deadline_origin"),
            "last_kill_host_monotonic_ns": process.get("last_kill_host_monotonic_ns"),
            "post_kill_reap_deadline_host_monotonic_ns": process.get("post_kill_reap_deadline_host_monotonic_ns"),
            "post_kill_reap_completed": process.get("post_kill_reap_completed") is True,
        },
        "runtime_budget_admission": budget_admission,
        "heartbeat_contract": heartbeat,
        "decision_authority": decision_authority,
        "dumpoff_consistency_authority": dumpoff_consistency_authority,
        "archive_timestamp_receipt": archive_timestamp,
        "target_entry": {"observed": target_entry_observed, "diagnostic_claim": target_diagnostic_claim},
        "vcd_identity": evidence,
        "return_exact_set": return_exact_set,
        "live_diagnostics": live_diagnostics,
        "warnings": warnings, "errors": errors,
        "claim_boundary": "Transport/runtime diagnostic evidence only; non-natural outcomes never imply natural terminal, formal D, E4 or E5."
    }


def thresholds(wall_ceiling: int = WALL) -> dict[str, Any]:
    return {
        "plateau_suspected_cycles": SUSPECTED, "plateau_dump_off_cycles": DUMP_OFF, "post_dump_grace_cycles": GRACE,
        "sim_time_freeze_intervals": FREEZE_INTERVALS, "sim_time_freeze_interval_seconds": FREEZE_SECONDS,
        "soft_warning_bytes": SOFT, "operational_vcd_budget_bytes": OPERATIONAL, "return_budget_bytes": RETURN, "wall_ceiling_seconds": wall_ceiling,
    }


def _plateau_qualification(
    eligible: bool,
    owner_clock_advancing: bool,
    sim_time_advancing: bool,
    qualified_progress_stable: bool,
    causal_state_stable: bool,
    global_progress_stable: bool,
    candidate_catalog_complete: bool,
    unresolved_xz_absent: bool,
) -> dict[str, bool]:
    return {
        "eligible": eligible,
        "owner_clock_advancing": owner_clock_advancing,
        "sim_time_advancing": sim_time_advancing,
        "qualified_progress_stable": qualified_progress_stable,
        "causal_state_stable": causal_state_stable,
        "global_progress_stable": global_progress_stable,
        "candidate_catalog_complete": candidate_catalog_complete,
        "unresolved_xz_absent": unresolved_xz_absent,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    receipt = evaluate(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if not receipt["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
