from __future__ import annotations

import unittest

from tools.audit_server_tb_vcd_exit_returns import classify_evidence


def base(reason: str, archive: int = 100, runtime_time: int = 100) -> tuple[dict, dict, dict, dict, dict, dict]:
    runtime = {
        "stop_reason": reason, "natural_terminal": False, "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "completeness": "PARTIAL", "time_event_counts": {"final_sim_time_ticks": runtime_time},
        "final_counters": {"no_progress_cycles": 4_456_448, "dump_off_cycle": 4_194_304},
        "dump_control": {
            "planned_dumpoff_observed": reason == "CAUSAL_PLATEAU",
            "state_monotonic": True,
            "stop_marker_one_shot": True,
            "stop_marker_count": 1 if reason == "CAUSAL_PLATEAU" else 0,
        },
        "thresholds": {"plateau_dump_off_cycles": 4_194_304, "post_dump_grace_cycles": 262_144},
        "process_tree": {"all_reaped": True},
    }
    request = {"samples": [{"sim_time_ticks": runtime_time}]}
    process = {"stop_reason": reason, "process_tree_reaped": True}
    stop = {"stop_reason": reason, "natural_terminal": False, "pass": False}
    sim_exit = {"signal": "NONE"}
    vcd = {"last_timestamp_ticks": archive}
    return runtime, request, process, stop, sim_exit, vcd


class ExitReturnAuditTests(unittest.TestCase):
    def test_false_freeze_when_archive_advanced(self) -> None:
        result = classify_evidence(*base("SIM_TIME_FREEZE", archive=465335625, runtime_time=102000))
        self.assertEqual(result["classification"], "A_QADD_V63_CLASS_FALSE_FREEZE")

    def test_premature_outer_plateau_is_distinct_shared_defect(self) -> None:
        args = list(base("NONZERO_EXIT"))
        args[2]["stop_reason"] = "CAUSAL_PLATEAU"
        args[0]["final_counters"] = {"no_progress_cycles": 1_409_024, "dump_off_cycle": None}
        result = classify_evidence(*args)
        self.assertEqual(result["classification"], "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT")

    def test_genuine_freeze_and_full_plateau_are_protection(self) -> None:
        freeze = classify_evidence(*base("SIM_TIME_FREEZE", archive=100, runtime_time=100))
        plateau = classify_evidence(*base("CAUSAL_PLATEAU", archive=100, runtime_time=100))
        self.assertEqual(freeze["classification"], "C_GENUINE_NO_PROGRESS_PROTECTION")
        self.assertEqual(plateau["classification"], "C_GENUINE_NO_PROGRESS_PROTECTION")

    def test_planned_dumpoff_vcd_stall_is_not_genuine_freeze(self) -> None:
        args = list(base("SIM_TIME_FREEZE", archive=7689350625, runtime_time=7689350625))
        args[0]["dump_control"] = {
            "planned_dumpoff_observed": True,
            "state_monotonic": True,
            "stop_marker_one_shot": True,
            "stop_marker_count": 1,
        }
        result = classify_evidence(*args)
        self.assertEqual(result["classification"], "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT")
        self.assertIn("PLANNED_DUMPOFF_VCD_STALL_MISCLASSIFIED_AS_FREEZE", result["shared_findings"])

    def test_external_and_natural(self) -> None:
        external_args = list(base("NONZERO_EXIT"))
        external_args[4]["signal"] = "INT"
        self.assertEqual(classify_evidence(*external_args)["classification"], "D_EXTERNAL_OR_MANUAL_TERMINATION")
        natural_args = list(base("NATURAL_TERMINAL"))
        natural_args[0]["natural_terminal"] = True
        self.assertEqual(classify_evidence(*natural_args)["classification"], "E_NORMAL_COMPLETION")

    def test_incomplete_pass_and_unreaped_are_reported(self) -> None:
        args = list(base("SIM_TIME_FREEZE"))
        args[3]["pass"] = True
        args[0]["process_tree"]["all_reaped"] = False
        args[2]["process_tree_reaped"] = False
        result = classify_evidence(*args)
        self.assertIn("FINALIZATION_PASS_CONTRADICTS_INCOMPLETE_RUNTIME", result["shared_findings"])
        self.assertIn("PROCESS_TREE_NOT_REAPED", result["shared_findings"])


if __name__ == "__main__":
    unittest.main()
