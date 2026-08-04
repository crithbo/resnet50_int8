from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_rope_validation import (
    CONTRACT_PATH,
    DeepSeekRopeValidationError,
    OPERATOR_TYPES,
    build_rope_blocker_contract,
    build_rope_graph,
    validate_rope_blocker_contract,
    validate_rope_graph,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class DeepSeekRopeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            CONTRACT.read_text(encoding="utf-8")
        )

    def test_graph_binds_onnx_crop_and_three_native_stages(self) -> None:
        graph = build_rope_graph(ROOT)
        validate_rope_graph(graph, ROOT)
        self.assertEqual(
            [item["type"] for item in graph["operators"]],
            list(OPERATOR_TYPES),
        )
        self.assertEqual(
            graph["operators"][1]["output"]["type"],
            "rope_slice_xor2",
        )
        self.assertEqual(
            graph["operators"][2]["inputs"]["A"]["source"], "op0"
        )
        self.assertEqual(
            graph["operators"][2]["inputs"]["B"]["source"], "op1"
        )

    def test_checked_blocker_contract_matches_current_evidence(self) -> None:
        rebuilt = build_rope_blocker_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_rope_blocker_contract(self.checked, ROOT)

    def test_identity_and_crop_boundaries_are_fail_closed(self) -> None:
        boundary = self.checked["identity_boundary"]
        self.assertEqual(
            boundary["onnx_repository_classification"],
            "SEMANTIC_MODEL_MATCH",
        )
        self.assertFalse(boundary["original_source_identity"])
        self.assertFalse(boundary["direct_onnx_shape_equals_stage"])
        self.assertTrue(boundary["crop_contract_required"])
        stage = self.checked["onnx_to_stage"]
        self.assertEqual(stage["crop_derived_hidden_size"], 896)
        self.assertEqual(stage["crop_derived_q_heads"], 7)
        self.assertEqual(stage["crop_derived_kv_heads"], 1)
        self.assertEqual(stage["head_dim"], 128)

    def test_three_stage_native_lifecycle_is_structurally_closed(self) -> None:
        lifecycle = self.checked[
            "stage_json_bitstream_lifecycle"
        ]
        self.assertTrue(lifecycle["structurally_complete"])
        self.assertTrue(lifecycle["semantically_accepted"])
        self.assertTrue(
            lifecycle["synthetic_numerical_equation_executed"]
        )
        self.assertTrue(
            lifecycle["complete_synthetic_payload_golden_executed"]
        )
        self.assertFalse(
            lifecycle["complete_trusted_payload_golden_executed"]
        )
        self.assertEqual(
            [
                item["mapping_exact_penalty"]
                for item in lifecycle["materialized_configs"]
            ],
            [0.0, 0.0, 0.0],
        )
        self.assertEqual(
            lifecycle["lifecycle"]["event_order"],
            [
                "Load_Config:op0",
                "Start_Comp:op0",
                "Load_Config:op1",
                "Start_Comp:op1",
                "Load_Config:op2",
                "Start_Comp:op2",
            ],
        )
        self.assertEqual(
            lifecycle["lifecycle"]["command_count"], 250
        )
        native = lifecycle["native_double_run"]
        self.assertEqual(native["output_file_count_per_run"], 38)
        self.assertEqual(native["deterministic_file_count"], 35)
        self.assertTrue(
            native["deterministic_outputs_byte_identical"]
        )

    def test_active_xor2_route_closes_all_slices(self) -> None:
        route = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["route_semantics"]
        self.assertEqual(route["expected_half_distance_elements"], 64)
        self.assertEqual(route["expected_half_distance_slices"], 2)
        self.assertEqual(
            route["active_router_expression"], "slice_id ^ 0b10"
        )
        self.assertEqual(route["active_route_mismatch_count"], 0)
        self.assertFalse(
            route["trusted_and_rebuilt_route_writes_identical"]
        )
        self.assertEqual(
            route["expected_producer_to_destination"][:4],
            [2, 3, 0, 1],
        )
        self.assertEqual(
            route["active_producer_to_destination"][:4],
            [2, 3, 0, 1],
        )
        self.assertEqual(
            route["legacy_trusted_producer_to_destination"][:4],
            [3, 2, 1, 0],
        )
        self.assertEqual(
            route["legacy_trusted_route_mismatch_count"], 28
        )
        self.assertEqual(
            route["elided_default_route"],
            {"producer_slice": 2, "destination_slice": 0},
        )

    def test_active_sign_has_one_owner_and_preserves_counterexample(self) -> None:
        sign = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["sign_pipeline"]
        self.assertEqual(
            sign["golden_saved_sin_sign_by_source_quarter"],
            [1, 1, -1, -1],
        )
        self.assertEqual(
            sign["post_relayout_sin_sign_by_source_quarter"],
            [-1, -1, 1, 1],
        )
        self.assertTrue(
            sign[
                "correct_xor2_route_with_current_relayout_still_wrong"
            ]
        )
        self.assertFalse(
            sign["historical_relayout_has_global_negation"]
        )
        active = sign["active_implementation"]
        self.assertFalse(active["activation_pre_swapped"])
        self.assertFalse(active["relayout_global_negation"])
        self.assertEqual(
            active["sin_sign_by_source_quarter"], [1, 1, -1, -1]
        )
        self.assertTrue(active["semantics_closed"])

    def test_numeric_equation_rejects_current_route_and_sign(self) -> None:
        evidence = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["synthetic_onnx_equation"]
        self.assertEqual(evidence["tested_element_count"], 128)
        self.assertEqual(
            evidence[
                "current_prefill_xor3_plus_global_negation_mismatch_count"
            ],
            128,
        )
        self.assertEqual(
            evidence[
                "cross_slice_xor2_without_global_negation_mismatch_count"
            ],
            0,
        )
        self.assertEqual(
            evidence[
                "preswapped_activation_rearranged_sin_same_slice_mismatch_count"
            ],
            0,
        )
        self.assertEqual(
            evidence["active_canonical_pipeline_mismatch_count"], 0
        )
        self.assertTrue(
            evidence["active_canonical_pipeline_matches_onnx_equation"]
        )

    def test_trusted_package_has_no_complete_numeric_payload(self) -> None:
        coverage = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["trusted_payload_coverage"]
        self.assertEqual(coverage["observed_tensor_file_count"], 252)
        self.assertEqual(coverage["nonempty_tensor_file_count"], 1)
        self.assertEqual(coverage["empty_tensor_file_count"], 251)
        self.assertFalse(
            coverage["complete_three_stage_numeric_oracle"]
        )
        synthetic = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["synthetic_numeric_e2"]
        self.assertEqual(
            synthetic["coverage"]["physical_file_count"], 252
        )
        self.assertEqual(
            synthetic["coverage"]["nonempty_file_count"], 301
        )
        self.assertEqual(self.checked["blockers"], [])

    def test_local_e2_is_accepted_without_claiming_dynamic_closure(self) -> None:
        policy = self.checked["policy_result"]
        self.assertTrue(
            policy["onnx_to_three_stage_decomposition_closed"]
        )
        self.assertTrue(
            policy[
                "three_stage_json_lifecycle_structurally_closed"
            ]
        )
        self.assertTrue(
            policy["inter_stage_route_semantics_closed"]
        )
        self.assertTrue(
            policy["golden_relayout_sign_semantics_closed"]
        )
        self.assertTrue(policy["synthetic_equation_diagnosis_closed"])
        self.assertFalse(policy["trusted_payload_coverage_closed"])
        self.assertTrue(
            policy["local_synthetic_payload_coverage_closed"]
        )
        self.assertTrue(policy["three_stage_local_e2_accepted"])
        self.assertFalse(policy["advance_to_server_test"])

    def test_graph_and_contract_tamper_fail_closed(self) -> None:
        graph = build_rope_graph(ROOT)
        tampered_graph = deepcopy(graph)
        tampered_graph["operators"][1]["output"]["type"] = None
        with self.assertRaisesRegex(
            DeepSeekRopeValidationError,
            "differs from ONNX/crop/native-stage evidence",
        ):
            validate_rope_graph(tampered_graph, ROOT)

        tampered_contract = deepcopy(self.checked)
        tampered_contract["policy_result"][
            "three_stage_local_e2_accepted"
        ] = False
        with self.assertRaisesRegex(
            DeepSeekRopeValidationError,
            "differs from current evidence",
        ):
            validate_rope_blocker_contract(
                tampered_contract, ROOT
            )


if __name__ == "__main__":
    unittest.main()
