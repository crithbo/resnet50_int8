from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.operator_semantics_local_closure import (
    CONTRACT_PATH,
    OperatorSemanticsLocalClosureError,
    build_operator_semantics_local_closure,
    validate_operator_semantics_local_closure,
)


ROOT = Path(__file__).resolve().parents[1]


class OperatorSemanticsLocalClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_operator_semantics_local_closure(ROOT)

    def test_local_static_scope_is_closed_without_releasing_candidates(
        self,
    ) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["stage_count"], 133)
        self.assertEqual(summary["audit_finding_count"], 28)
        self.assertEqual(summary["rtl_proven_finding_count"], 20)
        self.assertEqual(summary["contradicted_finding_count"], 8)
        self.assertEqual(summary["projected_json_leaf_count"], 1784)
        self.assertTrue(summary["gap_d_index_locally_resolved"])
        self.assertEqual(summary["ga_int32_exact_w3_stage_count"], 55)
        self.assertEqual(summary["conv_shape_signature_count"], 20)
        self.assertEqual(summary["minimal_two_stage_lifecycle_count"], 1)
        self.assertEqual(summary["candidate_json_count"], 2)
        self.assertEqual(
            summary["requant_family_numeric_classified_stage_count"], 54
        )
        self.assertEqual(
            summary[
                "requant_family_current_guard_compatible_stage_count"
            ],
            33,
        )
        self.assertEqual(
            summary[
                "requant_family_current_guard_contradicted_stage_count"
            ],
            21,
        )
        self.assertEqual(summary["formal_release_stage_count"], 0)
        self.assertTrue(
            self.value["claim_boundary"][
                "local_analysis_complete_for_plan_0_3_current_scope"
            ]
        )

    def test_minimal_two_stage_lifecycle_is_local_only(self) -> None:
        lifecycle = self.value["closed_local_work"][
            "minimal_two_stage_lifecycle"
        ]
        self.assertEqual(lifecycle["stage_count"], 2)
        self.assertEqual(lifecycle["runtime_sequence"], ["op0", "op1"])
        self.assertTrue(lifecycle["producer_consumer_alias"])
        self.assertFalse(lifecycle["producer_backed_input_preloaded"])
        self.assertTrue(lifecycle["independent_config_reload"])
        self.assertTrue(lifecycle["dual_golden_bit_exact"])
        self.assertFalse(lifecycle["full_network_projection_allowed"])

    def test_requant_node0001_is_exact_local_e2_only(self) -> None:
        requant = self.value["closed_local_work"][
            "requantize_uint8_node0001"
        ]
        self.assertEqual(requant["request_id"], "r5:hwop-0001-01")
        self.assertEqual(requant["w3_element_count"], 12_845_056)
        self.assertTrue(requant["w3_bit_exact"])
        self.assertEqual(requant["occurrence_count"], 24)
        self.assertEqual(requant["physical_stage_count"], 48)
        self.assertEqual(requant["bitstream_decoded_stage_count"], 48)
        self.assertEqual(requant["consumer_intermediate_preload_count"], 0)
        self.assertFalse(requant["candidate_release"])
        self.assertEqual(
            requant["remaining_blockers"], ["B_REQUANT_SERVER_E4_E5"]
        )

    def test_all_requant_requests_are_numerically_classified(self) -> None:
        family = self.value["closed_local_work"][
            "requantize_uint8_family"
        ]
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
        self.assertEqual(
            family["odd_zero_point_magic_counterexample_stage_ids"],
            ["r5:hwop-0014-01"],
        )
        self.assertEqual(family["physical_materialized_e2_stage_count"], 1)
        self.assertFalse(family["new_json_emission_allowed"])

    def test_gap_server_gate_is_frozen_and_dequant_has_no_package(self) -> None:
        self.assertEqual(
            self.value["remaining_gates"]["server_required_now"], []
        )
        dequant = self.value["remaining_gates"][
            "server_required_after_user_authorization"
        ]
        self.assertEqual(len(dequant), 2)
        self.assertFalse(dequant[0]["package_generated"])
        self.assertEqual(
            dequant[1]["gate"], "REQUANT_NODE0001_E4_E5_READBACK"
        )
        self.assertFalse(dequant[1]["package_generated"])
        gates = self.value["remaining_gates"]["frozen_server_gates"]
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0]["status"], "frozen_by_user")
        package = gates[0]["package"]
        self.assertEqual(package["status"], "validated_ready_for_server")
        self.assertEqual(package["zip_entry_count"], 120)
        self.assertFalse(package["functional_rtl_v_or_sv_included"])
        self.assertFalse(package["waveforms_enabled"])
        self.assertEqual(
            package["zip"]["sha256"],
            "c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893",
        )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )
        validate_operator_semantics_local_closure(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["summary"]["candidate_json_count"] = 0
        with self.assertRaises(OperatorSemanticsLocalClosureError):
            validate_operator_semantics_local_closure(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
