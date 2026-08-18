from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.server_tb_vcd_runtime_supervision import evaluate


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_tb_vcd_runtime_receipt_v1.schema.json"
P51_FIXTURE = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/p51_planned_dumpoff_false_freeze.json"


def sample(seq: int, cycles: int, sim_time: int, wall: int, **extra: object) -> dict:
    row = {
        "seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles,
        "sim_time_ticks": sim_time, "appended_vcd_timestamp_ticks": sim_time,
        "wall_seconds": wall, "vcd_bytes": 1000 + cycles,
        "non_clock_events": seq, "causal_progress_events": 1,
        "qualified_progress_counters": {"accept": 1, "write": 0},
        "causal_state_digest": "a" * 64, "global_progress_witness": {"global_accept": 1},
        "write_ok": True, "disk_space_ok": True, "quota_ok": True,
    }
    row.update(extra)
    return row


def request(samples: list[dict]) -> dict:
    return {
        "package_id": "p", "execution_id": "e", "attempt_id": "a", "started": True,
        "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64, "candidate_matrix_sha256": "3" * 64,
        "tb_source_sha256": "4" * 64, "elaboration_sha256": "5" * 64,
        "candidate_catalog_complete": True, "unresolved_xz": False, "samples": samples,
        "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": {
            "mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
            "helper_sha256": "7" * 64, "outer_runner_consumes_only_receipt": True, "independent_exit_logic_absent": True,
            "replay_cases": [
                {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
                {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
                {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
                {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
            ],
        },
        "dumpoff_consistency_authority": {
            "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF",
            "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
            "helper_sha256": "7" * 64,
            "replay_cases": [
                {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
                {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
                {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
            ],
        },
        "target_entry_observed": True, "target_diagnostic_claim": True,
        "flush": {"dumpoff": True, "dumpflush": True, "closed": True},
        "process_tree": {
            "term_sent": True, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True,
            "post_kill_reap_deadline_origin": "NOT_APPLICABLE",
            "last_kill_host_monotonic_ns": None,
            "post_kill_reap_deadline_host_monotonic_ns": None,
            "post_kill_reap_completed": True,
        },
        "vcd_identity": {"path": "wave.vcd", "bytes": 1000, "sha256": "6" * 64, "header_valid": True, "timescale": "1ns", "catalog_complete": True, "transitions_complete": True, "xz_preserved": True, "return_allowlist_member": True},
        "archive_timestamp_receipt": {"binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT", "parse_status": "COMPLETE", "path": "wave.vcd", "bytes": 1000, "sha256": "6" * 64, "last_timestamp_ticks": samples[-1].get("appended_vcd_timestamp_ticks", 0)},
        "return_exact_set": {"members": [{"path": "wave.vcd", "bytes": 1000, "sha256": "6" * 64}], "hard_limit_bytes": None, "truncated": False, "sampled": False, "allowlist_complete": True, "published": True},
        "live_diagnostics": {"downstream_state_source": "LIVE_SAME_ATTEMPT", "first_error_source": "LIVE_SAME_ATTEMPT", "stale_evidence_absent": True},
    }


class TbVcdRuntimeSupervisionTests(unittest.TestCase):
    def test_measured_pretarget_budget_prevents_false_3600_stop(self) -> None:
        item = request([
            sample(0, 0, 0, 0),
            sample(1, 100, 100, 3608, causal_progress_events=19, qualified_progress_counters={"pretarget": 19}),
            sample(2, 200, 200, 8000, natural_terminal=True, causal_progress_events=30, qualified_progress_counters={"pretarget": 30}),
        ])
        item["runtime_budget_admission"] = {
            "schema": "server-runtime-budget-admission-v1",
            "package_id": "p", "execution_id": "e", "mode": "MEASURED_PRETARGET_AWARE",
            "source_measurement": {},
            "projection": {"recommended_wall_ceiling_seconds": 8022},
            "selected_wall_ceiling_seconds": 8400,
            "absolute_maximum_wall_seconds": 86400,
            "independent_operational_guards": {
                "vcd_operational_budget_bytes": 8000000000,
                "return_budget_bytes": 10000000000,
                "disk_space_guard_enabled": True, "growth_projection_enabled": True,
                "write_failure_guard_enabled": True, "quota_guard_enabled": True,
            },
            "pass": True,
        }
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "NATURAL_TERMINAL")
        self.assertEqual(report["thresholds"]["wall_ceiling_seconds"], 8400)

    def test_unbound_or_unbounded_wall_override_fails_closed(self) -> None:
        item = request([sample(0, 0, 0, 0), sample(1, 1, 1, 3600)])
        item["runtime_budget_admission"] = {
            "schema": "server-runtime-budget-admission-v1", "pass": True,
            "projection": {"recommended_wall_ceiling_seconds": 3600},
            "selected_wall_ceiling_seconds": 1000000,
            "independent_operational_guards": {},
        }
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "WALL_CEILING")
        self.assertIn("bounded measured admission", "\n".join(report["errors"]))

    def test_post_kill_requires_fresh_reap_deadline(self) -> None:
        item = request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, natural_terminal=True)])
        item["process_tree"] = {
            "term_sent": True, "wait_completed": True, "kill_sent_if_needed": True, "all_reaped": True,
            "post_kill_reap_deadline_origin": "FRESH_AFTER_LAST_KILL",
            "last_kill_host_monotonic_ns": 200,
            "post_kill_reap_deadline_host_monotonic_ns": 199,
            "post_kill_reap_completed": True,
        }
        report = evaluate(item)
        self.assertIn("fresh bounded deadline", "\n".join(report["errors"]))

        item["process_tree"]["post_kill_reap_deadline_host_monotonic_ns"] = 300
        self.assertNotIn("fresh bounded deadline", "\n".join(evaluate(item)["errors"]))
    def test_compile_not_started_preserves_core_without_vcd(self) -> None:
        item = request([sample(0, 0, 0, 0)])
        item["started"] = False
        item["vcd_identity"] = None
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "COMPILE_NOT_STARTED")
        self.assertEqual(report["completeness"], "ABSENT_COMPILE_NOT_STARTED")
        self.assertIsNone(report["vcd_identity"])
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(report, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_natural_terminal_complete_and_schema(self) -> None:
        item = request([sample(0, 0, 0, 0), sample(1, 10, 10, 1, natural_terminal=True)])
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "NATURAL_TERMINAL")
        self.assertEqual(report["completeness"], "COMPLETE")
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(report, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_strict_plateau_intersection_stops_after_grace(self) -> None:
        rows = [
            sample(0, 0, 0, 0), sample(1, 1048576, 1048576, 10),
            sample(
                2, 4194304, 4194304, 20,
                planned_dumpoff=True,
                planned_dumpoff_cycle=4194304,
                planned_dumpoff_vcd_timestamp_ticks=4194304,
            ),
            sample(
                3, 4456448, 4456448, 30,
                appended_vcd_timestamp_ticks=4194304,
                planned_dumpoff=True,
                planned_dumpoff_cycle=4194304,
                planned_dumpoff_vcd_timestamp_ticks=4194304,
                stop_marker_count=1,
            ),
        ]
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "CAUSAL_PLATEAU")
        self.assertTrue(report["plateau_qualification"]["eligible"])
        self.assertEqual(report["dump_control"]["dump_off_cycle"], 4194304)
        self.assertEqual(report["dump_control"]["stop_marker_count"], 1)
        self.assertEqual(report["completeness"], "PARTIAL")

    def test_p51_planned_dumpoff_frozen_vcd_uses_execution_grace(self) -> None:
        fixture = json.loads(P51_FIXTURE.read_text(encoding="utf-8"))
        expected = fixture["expected"]
        report = evaluate(request(fixture["replay_samples"]))
        self.assertEqual(report["stop_reason"], expected["stop_reason"])
        self.assertNotEqual(report["stop_reason"], "SIM_TIME_FREEZE")
        self.assertEqual(report["time_event_counts"]["final_sim_time_ticks"], expected["final_vcd_timestamp_ticks"])
        self.assertEqual(report["time_event_counts"]["final_execution_sim_time_ticks"], expected["final_execution_sim_time_ticks"])
        self.assertEqual(report["final_counters"]["freeze_intervals"], expected["freeze_intervals"])
        self.assertEqual(report["dump_control"]["dump_off_cycle"], expected["dump_off_cycle"])
        self.assertEqual(report["dump_control"]["stop_marker_count"], expected["stop_marker_count"])

    def test_planned_dumpoff_state_and_stop_marker_fail_closed(self) -> None:
        repeated = [
            sample(0, 0, 0, 0),
            sample(
                1, 4194304, 4194304, 10,
                planned_dumpoff=True,
                planned_dumpoff_cycle=4194304,
                planned_dumpoff_vcd_timestamp_ticks=4194304,
            ),
            sample(
                2, 4456448, 4456448, 40,
                appended_vcd_timestamp_ticks=4194304,
                planned_dumpoff=True,
                planned_dumpoff_cycle=4194304,
                planned_dumpoff_vcd_timestamp_ticks=4194304,
                stop_marker_count=2,
            ),
        ]
        report = evaluate(request(repeated))
        self.assertEqual(report["stop_reason"], "CAUSAL_PLATEAU")
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("one-shot", "\n".join(report["errors"]))

        cleared = copy.deepcopy(repeated)
        cleared[-1]["stop_marker_count"] = 1
        cleared[-1]["planned_dumpoff"] = False
        report = evaluate(request(cleared))
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("state cleared", "\n".join(report["errors"]))

    def test_planned_dumpoff_before_full_intersection_fails_closed(self) -> None:
        rows = [
            sample(0, 0, 0, 0),
            sample(
                1, 100, 100, 1,
                planned_dumpoff=True,
                planned_dumpoff_cycle=100,
                planned_dumpoff_vcd_timestamp_ticks=100,
            ),
            sample(2, 200, 200, 3600, planned_dumpoff=True, planned_dumpoff_cycle=100, planned_dumpoff_vcd_timestamp_ticks=100),
        ]
        report = evaluate(request(rows))
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("before the complete plateau intersection", "\n".join(report["errors"]))

    def test_global_progress_forbids_local_plateau_stop(self) -> None:
        rows = []
        for seq, cycles in enumerate((0, 1048576, 4194304, 4456448)):
            rows.append(sample(seq, cycles, cycles, seq * 10, global_progress_witness={"global_accept": seq + 1}))
        rows.append(sample(5, 5000000, 5000000, 3600, global_progress_witness={"global_accept": 6}))
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "WALL_CEILING")
        self.assertFalse(report["plateau_qualification"]["global_progress_stable"])

    def test_local_counter_or_state_change_forbids_plateau_stop(self) -> None:
        for changed_field, changed_value in (
            ("qualified_progress_counters", {"accept": 2, "write": 0}),
            ("causal_state_digest", "b" * 64),
        ):
            rows = [sample(0, 0, 0, 0)]
            for seq, cycles in enumerate((1048576, 4194304, 4456448), start=1):
                rows.append(sample(seq, cycles, cycles, seq * 10, **{changed_field: changed_value if seq % 2 else sample(0, 0, 0, 0)[changed_field]}))
            rows.append(sample(5, 5000000, 5000000, 3600, **{changed_field: changed_value}))
            report = evaluate(request(rows))
            self.assertEqual(report["stop_reason"], "WALL_CEILING")

    def test_owner_clock_not_advancing_forbids_plateau(self) -> None:
        rows = [
            sample(0, 0, 0, 0),
            sample(1, 0, 1048576, 10),
            sample(2, 0, 4194304, 20),
            sample(3, 0, 4456448, 3600),
        ]
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "WALL_CEILING")
        self.assertFalse(report["plateau_qualification"]["owner_clock_advancing"])

    def test_incomplete_catalog_or_unresolved_xz_forbids_plateau(self) -> None:
        item = request([
            sample(0, 0, 0, 0), sample(1, 4194304, 4194304, 10),
            sample(2, 4456448, 4456448, 3600),
        ])
        item["candidate_catalog_complete"] = False
        item["unresolved_xz"] = True
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "WALL_CEILING")
        self.assertFalse(report["plateau_qualification"]["eligible"])

    def test_sim_time_freeze_three_intervals(self) -> None:
        rows = [sample(i, i * 100, 7, i * 30) for i in range(4)]
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "SIM_TIME_FREEZE")

    def test_display_heartbeat_cannot_mask_stalled_appended_vcd_timestamp(self) -> None:
        rows = [
            sample(i, i * 100, i * 1000, i * 30, appended_vcd_timestamp_ticks=7)
            for i in range(4)
        ]
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "SIM_TIME_FREEZE")

    def test_appended_vcd_timestamp_regression_fails_closed(self) -> None:
        rows = [sample(0, 0, 100, 0), sample(1, 100, 99, 1)]
        report = evaluate(request(rows))
        self.assertEqual(report["stop_reason"], "VCD_TIMESTAMP_REGRESSION")
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")

    def test_size_disk_signal_and_unflushed_are_partial(self) -> None:
        cases = [
            (sample(1, 1, 1, 1, vcd_bytes=8000000000), "VCD_OPERATIONAL_BUDGET"),
            (sample(1, 1, 1, 1, vcd_operational_projection_bytes=8000000000), "VCD_OPERATIONAL_BUDGET"),
            (sample(1, 1, 1, 1, return_projection_bytes=10000000000), "RETURN_BUDGET_PROJECTION"),
            (sample(1, 1, 1, 1, disk_space_ok=False), "DISK_SPACE_FAILURE"),
            (sample(1, 1, 1, 1, write_ok=False), "WRITE_FAILURE"),
            (sample(1, 1, 1, 1, quota_ok=False), "QUOTA_FAILURE"),
            (sample(1, 1, 1, 1, signal="INT"), "INT"),
        ]
        for row, reason in cases:
            report = evaluate(request([sample(0, 0, 0, 0), row]))
            self.assertEqual(report["stop_reason"], reason)
            self.assertEqual(report["completeness"], "PARTIAL")
        item = request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, natural_terminal=True)])
        item["flush"]["dumpflush"] = False
        self.assertEqual(evaluate(item)["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")

    def test_decimal_soft_limit_warns_without_truncation_or_failure(self) -> None:
        item = request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, vcd_bytes=100000001, natural_terminal=True)])
        report = evaluate(item)
        self.assertEqual(report["stop_reason"], "NATURAL_TERMINAL")
        self.assertEqual(report["completeness"], "COMPLETE")
        self.assertTrue(report["growth"]["soft_warning_exceeded"])
        self.assertIn("untruncated", "\n".join(report["warnings"]))

    def test_process_tree_must_be_reaped(self) -> None:
        item = request([sample(0, 0, 0, 0), sample(1, 1, 1, 1, natural_terminal=True)])
        item["process_tree"]["all_reaped"] = False
        report = evaluate(item)
        self.assertEqual(report["completeness"], "PARTIAL")
        self.assertIn("not fully reaped", "\n".join(report["errors"]))

    def test_heartbeat_exact_set_target_and_live_state_fail_closed(self) -> None:
        base = [sample(0, 0, 0, 0), sample(1, 1, 1, 1, natural_terminal=True)]
        cases = []
        bad_heartbeat = request(copy.deepcopy(base))
        bad_heartbeat["heartbeat_contract"]["width_bits"] = 32
        cases.append((bad_heartbeat, "non-overflowing"))
        bad_exact = request(copy.deepcopy(base))
        bad_exact["return_exact_set"]["hard_limit_bytes"] = 100000000
        cases.append((bad_exact, "exact-set"))
        bad_target = request(copy.deepcopy(base))
        bad_target["target_entry_observed"] = False
        cases.append((bad_target, "target entry"))
        bad_live = request(copy.deepcopy(base))
        bad_live["live_diagnostics"]["first_error_source"] = "STALE_PRIOR_ATTEMPT"
        cases.append((bad_live, "live same-attempt"))
        for item, message in cases:
            report = evaluate(item)
            self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
            self.assertIn(message, "\n".join(report["errors"]))

    def test_archive_timestamp_mismatch_and_outer_decision_escape_fail_closed(self) -> None:
        base = [sample(0, 0, 0, 0), sample(1, 1, 1, 1, natural_terminal=True)]
        archive_drift = request(copy.deepcopy(base))
        archive_drift["archive_timestamp_receipt"]["last_timestamp_ticks"] = 999
        report = evaluate(archive_drift)
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("archive-timestamp", "\n".join(report["errors"]))

        premature = request(copy.deepcopy(base))
        for row in premature["decision_authority"]["replay_cases"]:
            if row["case_id"] == "PLATEAU_SUSPECTED_ONLY":
                row["observed_decision"] = "CAUSAL_PLATEAU"
        report = evaluate(premature)
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("decision authority", "\n".join(report["errors"]))

        missing_phase_replay = request(copy.deepcopy(base))
        missing_phase_replay["dumpoff_consistency_authority"]["replay_cases"].pop()
        report = evaluate(missing_phase_replay)
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
        self.assertIn("planned-dumpoff consistency authority", "\n".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()
