from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.project_closure import (
    build_project_closure,
    validate_project_closure,
)


ROOT = Path(__file__).resolve().parents[1]


class ProjectClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(
            (ROOT / "contracts/resnet50_project_closure.json").read_text(
                encoding="utf-8"
            )
        )

    def test_exact_graph_lowering_formula_and_edge_coverage(self) -> None:
        coverage = self.report["coverage"]
        self.assertEqual(coverage["node_count"], 78)
        self.assertEqual(coverage["hw_op_count"], 133)
        self.assertEqual(coverage["runtime_edge_count"], 93)
        self.assertEqual(coverage["local_formula_match_count"], 78)
        self.assertEqual(coverage["internal_tensor_count"], 55)
        self.assertEqual(coverage["typed_lowering_request_count"], 133)
        self.assertEqual(len(coverage["typed_lowering_request_set_sha256"]), 64)
        self.assertTrue(coverage["network_scenarios_pass"])

    def test_fail_closed_target_and_server_status(self) -> None:
        coverage = self.report["coverage"]
        self.assertEqual(coverage["formal_target_config_ready_count"], 0)
        self.assertEqual(coverage["formal_e4_pass_count"], 0)
        self.assertEqual(coverage["formal_e5_pass_count"], 0)
        self.assertEqual(coverage["server_e4_attempt_count"], 3)
        self.assertEqual(
            coverage["server_e4_first_dynamic_failure_count"], 3
        )
        self.assertEqual(coverage["server_e4_incomplete_count"], 3)
        self.assertEqual(
            coverage["server_e4_compile_infrastructure_failure_count"], 1
        )
        self.assertEqual(
            coverage["server_e4_compute_started_not_completed_count"], 1
        )
        self.assertEqual(
            coverage[
                "server_e4_stock_tb_completion_mask_incompatible_count"
            ],
            1,
        )
        self.assertEqual(
            coverage["server_e4_nonauthoritative_snapshot_count"], 1
        )
        self.assertEqual(
            coverage["server_e4_compile_fix_verified_snapshot_count"], 1
        )
        self.assertEqual(coverage["local_lowering_resolved_count"], 5)
        self.assertEqual(coverage["local_lowering_unresolved_count"], 128)
        self.assertEqual(coverage["candidate_config_emission_allowed_count"], 2)
        self.assertEqual(coverage["candidate_zero_copy_binding_allowed_count"], 1)
        self.assertEqual(coverage["json_emitter_ready_count"], 4)
        self.assertEqual(coverage["rtl_semantics_compatible_count"], 3)
        self.assertEqual(coverage["dynamic_release_ready_count"], 0)
        self.assertEqual(coverage["candidate_config_stage_count"], 2)
        self.assertEqual(coverage["historical_candidate_config_stage_count"], 11)
        self.assertEqual(coverage["local_candidate_execplan_chain_count"], 2)
        self.assertEqual(
            coverage["requant_numeric_classified_stage_count"], 54
        )
        self.assertEqual(
            coverage["requant_current_guard_compatible_stage_count"], 33
        )
        self.assertEqual(
            coverage["requant_current_guard_contradicted_stage_count"], 21
        )
        self.assertEqual(
            coverage["requant_materialized_e2_stage_count"], 1
        )
        self.assertEqual(coverage["local_two_stage_lifecycle_probe_count"], 1)
        self.assertEqual(coverage["historical_local_execplan_chain_count"], 3)
        self.assertEqual(coverage["matrix_complete_server_candidate_count"], 0)
        self.assertEqual(
            coverage["historical_matrix_complete_server_package_count"], 2
        )
        self.assertEqual(coverage["legacy_normalized_zero_penalty_mapping_count"], 9)
        self.assertEqual(coverage["legacy_normalized_mapping_remaining_count"], 0)
        self.assertEqual(len(self.report["stage_records"]), 133)
        self.assertTrue(
            all(not item["formal_target_instance_allowed"] for item in self.report["stage_records"])
        )

    def test_patched_decode_chain_is_bound_to_one_patchset(self) -> None:
        strategy = self.report["source_strategy"]
        self.assertTrue(strategy["patched_decode_mapping"]["valid"])
        self.assertTrue(strategy["patched_decode_execplan"]["valid"])
        self.assertEqual(
            strategy["patched_decode_mapping"]["patchset_sha256"],
            strategy["patchset_sha256"],
        )
        self.assertEqual(
            strategy["patched_decode_execplan"]["patchset_sha256"],
            strategy["patchset_sha256"],
        )
        node0004 = strategy["patched_node0004_candidate"]
        self.assertEqual(
            node0004["scope"],
            "historical_experimental_liveness_smoke_only_sa_int8_numeric_semantics_blocked",
        )
        self.assertTrue(node0004["mapping"]["valid"])
        self.assertTrue(node0004["execplan"]["valid"])
        self.assertEqual(
            node0004["mapping"]["source_config_sha256"],
            node0004["execplan"]["source_config_sha256"],
        )
        self.assertTrue(node0004["server_candidate"]["valid"])
        self.assertFalse(node0004["server_candidate"]["current_semantics_valid"])
        maxpool = strategy["patched_maxpool_node0002_candidate"]
        self.assertEqual(
            maxpool["scope"],
            "historical_matrix_complete_candidate_only_ga_int8_max_numeric_and_flow_blocked",
        )
        self.assertTrue(maxpool["server_candidate"]["valid"])
        self.assertFalse(maxpool["server_candidate"]["current_semantics_valid"])
        self.assertEqual(
            maxpool["mapping"]["source_config_sha256"],
            maxpool["execplan"]["source_config_sha256"],
        )
        dequant = strategy["dequant_node0077_local_candidate"]
        self.assertEqual(
            dequant["status"],
            "local_e2_complete_e4_first_dynamic_failure",
        )
        self.assertTrue(dequant["materialized_roundtrip_valid"])
        self.assertFalse(dequant["candidate_release"])
        self.assertEqual(
            dequant["dynamic_e4_status"], "FIRST_DYNAMIC_FAILURE"
        )
        self.assertEqual(
            dequant["dynamic_evidence_level"], "SERVER_INCOMPLETE"
        )
        self.assertEqual(dequant["dynamic_baseline"], "NO_DYNAMIC_BASELINE")
        self.assertFalse(dequant["e4_pass"])
        self.assertFalse(dequant["e5_generation_allowed"])
        self.assertEqual(
            dequant["last_proven_dynamic_boundary"], "slice Start Comp"
        )
        self.assertEqual(dequant["completed_slice_count"], 0)
        self.assertEqual(dequant["formal_d_file_count"], 0)
        self.assertEqual(
            dequant["remaining_blockers"], ["B_DEQUANT_SERVER_E4_E5"]
        )
        requant = strategy["requant_node0001_local_candidate"]
        self.assertEqual(
            requant["status"],
            "local_e2_complete_e4_stock_tb_completion_mask_incompatible",
        )
        self.assertEqual(requant["occurrence_count"], 24)
        self.assertEqual(requant["physical_stage_count"], 48)
        self.assertEqual(requant["bitstream_decoded_stage_count"], 48)
        self.assertEqual(requant["consumer_intermediate_preload_count"], 0)
        self.assertEqual(requant["dynamic_baseline"], "NO_DYNAMIC_BASELINE")
        self.assertFalse(requant["candidate_release"])
        self.assertEqual(
            requant["dynamic_e4_status"], "FIRST_DYNAMIC_FAILURE"
        )
        self.assertEqual(
            requant["failure_class"],
            "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE",
        )
        self.assertEqual(requant["formal_e4_attempt_count"], 2)
        self.assertEqual(
            requant["v1_failure_class"],
            "server_test_infrastructure_compile_failure",
        )
        self.assertTrue(requant["simulation_started"])
        self.assertEqual(requant["lifecycle_start_count"], 48)
        self.assertEqual(requant["lifecycle_finish_count"], 48)
        self.assertEqual(requant["same_mask_fence_count"], 48)
        self.assertEqual(requant["historical_guard_observation_count"], 0)
        self.assertEqual(requant["formal_d_file_count"], 0)
        self.assertFalse(requant["e4_pass"])
        self.assertFalse(requant["e5_generation_allowed"])
        self.assertFalse(requant["same_package_rerun_allowed"])
        self.assertEqual(
            requant["v2_partial_snapshot_return_kind"],
            "RETURN_SNAPSHOT_NONAUTHORITATIVE",
        )
        self.assertFalse(
            requant["v2_partial_snapshot_counts_as_e4_attempt"]
        )
        self.assertTrue(requant["v2_compile_repair_server_verified"])
        self.assertTrue(requant["v2_simulation_started"])
        self.assertEqual(requant["v2_preload_completed"], 178)
        self.assertEqual(requant["v2_slice_start_count"], 48)
        self.assertEqual(requant["v2_slice_completion_count"], 48)
        self.assertEqual(requant["v2_same_mask_fence_count"], 48)
        self.assertEqual(requant["v2_formal_d_file_count"], 0)
        self.assertFalse(requant["v2_hardware_hang_proven"])
        self.assertEqual(
            requant["v2_process_state"],
            "FINALIZED_TIMEOUT_124",
        )
        self.assertEqual(
            requant["v2_final_return_kind"],
            "AUTHORITATIVE_FINALIZER_RETURN",
        )
        self.assertTrue(requant["v2_counts_as_formal_e4_attempt"])
        self.assertEqual(
            requant["v2_failure_class"],
            "STOCK_TB_COMPLETION_MASK_INCOMPATIBLE",
        )
        self.assertEqual(
            requant["v2_guard_observer_status"], "fail_unresolved"
        )
        self.assertEqual(requant["v2_guard_observer_pass_count"], 0)
        self.assertFalse(
            requant["v2_guard_observer_root_cause_resolved"]
        )
        self.assertFalse(requant["v2_numeric_mismatch_proven"])
        self.assertFalse(requant["v2_rerun_allowed"])
        scale = requant["v2_workload_scale"]
        self.assertEqual(
            scale["classification"],
            "FULL_TWO_STAGE_W3_E4_NOT_ATOMIC_SMOKE",
        )
        self.assertEqual(scale["requant"]["repeat_num"], 48)
        self.assertEqual(scale["requant"]["preload_file_entry_count"], 178)
        self.assertEqual(
            scale["requant"]["formal_d_128bit_line_count"], 1_505_280
        )
        self.assertEqual(scale["dequant_reference"]["repeat_num"], 1)
        self.assertEqual(
            scale["dequant_reference"]["formal_d_128bit_line_count"], 5_264
        )
        self.assertEqual(
            scale["runtime_risk_classification"],
            "PLAUSIBLE_TEXT_IO_AND_SERIAL_FENCE_DOMINANCE_"
            "NOT_PROVEN_ROOT_CAUSE",
        )
        self.assertFalse(scale["snapshot_proves_hang"])
        self.assertFalse(scale["counts_as_formal_e4_attempt"])
        self.assertEqual(
            requant["remaining_blockers"], ["B_REQUANT_SERVER_E4_E5"]
        )
        family = strategy["requant_family_numeric_classification"]
        self.assertEqual(family["request_count"], 54)
        self.assertEqual(
            family["standard_w3_golden_exact_stage_count"], 54
        )
        self.assertEqual(
            family["zero_point_zero_numeric_compatible_stage_count"], 33
        )
        self.assertEqual(
            family[
                "nonzero_zero_point_guard_contradicted_stage_count"
            ],
            21,
        )
        self.assertEqual(family["physical_materialized_e2_stage_count"], 1)
        self.assertFalse(family["new_json_emission_allowed"])
        lifecycle = strategy["minimal_two_stage_lifecycle"]
        self.assertEqual(
            lifecycle["status"],
            "local_e2_complete_dynamic_hardware_pending",
        )
        self.assertTrue(lifecycle["producer_consumer_alias"])
        self.assertTrue(lifecycle["independent_config_reload"])
        self.assertTrue(lifecycle["dual_golden_bit_exact"])
        self.assertFalse(lifecycle["candidate_release"])
        self.assertFalse(lifecycle["formal_target_config"])
        self.assertFalse(lifecycle["full_network_projection_allowed"])
        legacy = strategy["legacy_gemm_mapping_residuals"]
        self.assertEqual(len(legacy["mappings"]), 3)
        self.assertEqual(
            legacy["reference_commit"],
            "d4ffc32c9b29a858d83e13706cd837c5549521a4",
        )
        self.assertTrue(all(item["penalty"] == 0 for item in legacy["mappings"]))
        self.assertEqual(legacy["remaining"], [])
        self.assertEqual(
            legacy["maxpool"]["scope"],
            "legacy_mapping_closed_not_formal_not_server_run",
        )
        self.assertEqual(legacy["maxpool"]["mapping"]["penalty"], 0)

    def test_checked_in_report_is_current(self) -> None:
        checked = json.loads(
            (ROOT / "contracts/resnet50_project_closure.json").read_text(
                encoding="utf-8"
            )
        )
        validate_project_closure(checked, ROOT)


if __name__ == "__main__":
    unittest.main()
