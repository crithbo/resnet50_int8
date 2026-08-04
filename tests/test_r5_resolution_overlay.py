from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.r5_resolution_overlay import (
    blocker_resolution,
    build_r5_resolution_overlay,
    validate_r5_resolution_overlay,
)


ROOT = Path(__file__).resolve().parents[1]


class R5ResolutionOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.overlay = build_r5_resolution_overlay(ROOT)

    def test_layout_transport_maxpool_and_gap_scopes_are_exact(self) -> None:
        resolutions = self.overlay["resolutions"]
        self.assertEqual(len(resolutions["B_LAYOUT_APPROVAL"]["hw_op_ids"]), 133)
        self.assertEqual(len(resolutions["B_EXECPLAN_TYPED_TRANSPORT"]["hw_op_ids"]), 9)
        self.assertEqual(
            resolutions["B_MAXPOOL_SHAPE_GENERALIZATION"]["hw_op_ids"],
            ["hwop-0002-00"],
        )
        self.assertEqual(
            resolutions["B_MAXPOOL_UINT8_SEMANTICS"]["hw_op_ids"],
            ["hwop-0002-00"],
        )
        self.assertEqual(
            resolutions["B_GAP_CENTERED_SUM"]["hw_op_ids"],
            ["hwop-0071-00"],
        )
        self.assertEqual(
            resolutions["B_SUM_CROSS_SLICE"]["hw_op_ids"],
            ["hwop-0071-00"],
        )
        self.assertEqual(
            resolutions["B_SUM_COMPLETION"]["hw_op_ids"],
            ["hwop-0071-00"],
        )
        self.assertEqual(
            resolutions["B_DEQUANT_STANDALONE"]["hw_op_ids"],
            ["hwop-0077-00"],
        )
        self.assertEqual(
            resolutions["B_REQUANT_TARGET_NUMERICS"]["hw_op_ids"],
            ["hwop-0001-01"],
        )
        self.assertIsNotNone(
            blocker_resolution(self.overlay, "B_LAYOUT_APPROVAL", "hwop-0002-00")
        )
        self.assertIsNone(
            blocker_resolution(
                self.overlay, "B_MAXPOOL_UINT8_SEMANTICS", "hwop-0003-00"
            )
        )

    def test_gap_local_numeric_semantics_are_bound(self) -> None:
        summary = self.overlay["gap_sum_local_semantics"]
        self.assertEqual(summary["hw_op_id"], "hwop-0071-00")
        self.assertEqual(summary["input_zero_point"], 0)
        self.assertEqual(summary["spatial_element_count"], 49)
        self.assertEqual(summary["lane_count"], 8)
        self.assertEqual(summary["lane_opcode"], "int32_sum")
        self.assertEqual(summary["padding_identity"], 0)
        self.assertEqual(summary["wave_active_slice_counts"], [16])
        self.assertFalse(summary["cross_slice_reduction_required"])
        self.assertIn(0, summary["terminal_possible_last_indices"])

    def test_maxpool_byte_level_proof_is_bound(self) -> None:
        summary = self.overlay["maxpool_local_closure"]
        self.assertEqual(summary["logical_payload_bytes_checked_with_multiplicity"], 28 * 200704)
        self.assertEqual(summary["padding_masked_bytes_checked_with_multiplicity"], 28 * 3600)
        self.assertEqual(summary["logical_address_mismatch_count"], 0)
        self.assertEqual(summary["padding_mask_mismatch_count"], 0)
        self.assertEqual(summary["independent_w3_mismatch_count"], 0)

    def test_dequant_local_e2_is_bound_but_not_released(self) -> None:
        summary = self.overlay["dequant_local_closure"]
        self.assertEqual(summary["hw_op_id"], "hwop-0077-00")
        self.assertEqual(summary["local_evidence_level"], "E2")
        self.assertFalse(summary["candidate_release"])
        self.assertEqual(summary["hardware_elements_per_slice"], 752)
        self.assertEqual(summary["mapping_penalty"], 0)
        self.assertTrue(summary["encoded_physical_pe_constants_verified"])
        self.assertEqual(
            summary["dynamic_e4_status"], "FIRST_DYNAMIC_FAILURE"
        )
        self.assertEqual(
            summary["dynamic_evidence_level"], "SERVER_INCOMPLETE"
        )
        self.assertEqual(summary["dynamic_baseline"], "NO_DYNAMIC_BASELINE")
        self.assertFalse(summary["e4_pass"])
        self.assertFalse(summary["e5_generation_allowed"])
        self.assertEqual(
            summary["last_proven_dynamic_boundary"], "slice Start Comp"
        )
        self.assertEqual(summary["completed_slice_count"], 0)
        self.assertEqual(summary["formal_d_file_count"], 0)
        self.assertEqual(
            summary["remaining_blocker"], "B_DEQUANT_SERVER_E4_E5"
        )

    def test_requant_local_e2_is_bound_but_not_released(self) -> None:
        summary = self.overlay["requant_local_closure"]
        self.assertEqual(summary["hw_op_id"], "hwop-0001-01")
        self.assertEqual(summary["local_evidence_level"], "E2")
        self.assertFalse(summary["candidate_release"])
        self.assertEqual(summary["occurrence_count"], 24)
        self.assertEqual(summary["stage_count"], 48)
        self.assertEqual(summary["static_config_type_count"], 9)
        self.assertEqual(summary["w3_element_count"], 12_845_056)
        self.assertTrue(summary["w3_bit_exact"])
        self.assertEqual(summary["bitstream_decoded_stage_count"], 48)
        self.assertEqual(summary["consumer_intermediate_preload_count"], 0)
        self.assertEqual(
            summary["dynamic_e4_status"], "FIRST_DYNAMIC_FAILURE"
        )
        self.assertEqual(
            summary["failure_class"],
            "server_test_infrastructure_compile_failure",
        )
        self.assertFalse(summary["simulation_started"])
        self.assertEqual(summary["lifecycle_start_count"], 0)
        self.assertEqual(summary["historical_guard_observation_count"], 0)
        self.assertEqual(summary["formal_d_file_count"], 0)
        self.assertFalse(summary["e4_pass"])
        self.assertFalse(summary["e5_generation_allowed"])
        self.assertFalse(summary["same_package_rerun_allowed"])
        self.assertEqual(
            summary["v2_partial_snapshot_return_kind"],
            "RETURN_SNAPSHOT_NONAUTHORITATIVE",
        )
        self.assertFalse(
            summary["v2_partial_snapshot_counts_as_e4_attempt"]
        )
        self.assertTrue(summary["v2_compile_repair_server_verified"])
        self.assertTrue(summary["v2_simulation_started"])
        self.assertEqual(summary["v2_preload_completed"], 178)
        self.assertEqual(summary["v2_slice_start_count"], 1)
        self.assertEqual(summary["v2_slice_completion_count"], 0)
        self.assertEqual(summary["v2_formal_d_file_count"], 0)
        self.assertFalse(summary["v2_hardware_hang_proven"])
        self.assertEqual(
            summary["v2_process_state"],
            "UNKNOWN_CHECK_EXISTING_PROCESS_FIRST",
        )
        scale = summary["v2_workload_scale"]
        self.assertEqual(
            scale["classification"],
            "FULL_TWO_STAGE_W3_E4_NOT_ATOMIC_SMOKE",
        )
        self.assertEqual(scale["requant"]["execplan_length"], 317)
        self.assertEqual(scale["requant"]["raw_input_bytes"], 51_380_224)
        self.assertEqual(
            scale["requant"]["guard_round_element_stage_operations"],
            25_690_112,
        )
        self.assertEqual(scale["requant"]["formal_d_bytes"], 24_084_480)
        self.assertEqual(scale["dequant_reference"]["execplan_length"], 29)
        self.assertEqual(
            scale["dequant_reference"]["raw_input_bytes"], 21_056
        )
        self.assertEqual(
            scale["dequant_reference"]["formal_d_bytes"], 84_224
        )
        self.assertEqual(scale["relative_scale"]["start_comp_multiple"], 48)
        self.assertEqual(
            scale["stock_text_monitor_evidence"][
                "total_files_expected_after_first_start"
            ],
            756,
        )
        self.assertFalse(scale["snapshot_proves_hang"])
        self.assertFalse(scale["counts_as_formal_e4_attempt"])
        self.assertEqual(
            summary["remaining_blocker"], "B_REQUANT_SERVER_E4_E5"
        )

    def test_checked_overlay_and_tamper_are_fail_closed(self) -> None:
        checked = json.loads(
            (ROOT / "contracts/resnet50_r5_resolution_overlay.json").read_text(encoding="utf-8")
        )
        validate_r5_resolution_overlay(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["maxpool_local_closure"]["padding_mask_mismatch_count"] = 1
        with self.assertRaises(ValueError):
            validate_r5_resolution_overlay(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
