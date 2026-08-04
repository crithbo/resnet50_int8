from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_rmsnorm_validation import (
    CONTRACT_PATH,
    DeepSeekRmsNormValidationError,
    OPERATOR_TYPES,
    build_rmsnorm_blocker_contract,
    build_rmsnorm_graph,
    validate_rmsnorm_blocker_contract,
    validate_rmsnorm_graph,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class DeepSeekRmsNormValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_graph_binds_onnx_crop_and_five_native_stages(self) -> None:
        graph = build_rmsnorm_graph(ROOT)
        validate_rmsnorm_graph(graph, ROOT)
        self.assertEqual(
            [item["type"] for item in graph["operators"]],
            list(OPERATOR_TYPES),
        )
        self.assertEqual(
            graph["operators"][1]["used_slices"],
            "0b1111111111111111111111111111",
        )
        self.assertEqual(
            graph["operators"][1]["inputs"]["A"]["shape"], [1, 4, 32]
        )
        self.assertEqual(
            graph["operators"][1]["inputs"]["A"]["type"], "slice0"
        )
        self.assertNotIn("type", graph["operators"][2]["inputs"]["A"])
        self.assertEqual(
            graph["operators"][4]["inputs"]["B"]["source"], "op3"
        )

    def test_checked_blocker_contract_matches_current_evidence(self) -> None:
        rebuilt = build_rmsnorm_blocker_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_rmsnorm_blocker_contract(self.checked, ROOT)

    def test_onnx_decomposition_includes_separate_gamma_stage(self) -> None:
        stage = self.checked["onnx_to_stage"]
        self.assertEqual(
            stage["onnx_anchor"]["op_type"],
            "SimplifiedLayerNormalization",
        )
        self.assertEqual(stage["crop_derived_hidden_size"], 896)
        self.assertEqual(stage["hidden_elements_per_slice"], 32)
        self.assertEqual(
            stage["normalized_stage_sequence"], list(OPERATOR_TYPES)
        )
        self.assertEqual(
            stage["fused_semantics"],
            "gamma * x / sqrt(mean(x*x, axis=-1) + 1e-6)",
        )

    def test_grouped_remote_sum_closes_old_route_blockers(self) -> None:
        grouped = self.checked["onnx_to_stage"]["grouped_remote_sum"]
        self.assertEqual(grouped["head_count"], 7)
        self.assertEqual(grouped["slices_per_head"], 4)
        self.assertEqual(grouped["op1_active_slices"], 28)
        self.assertEqual(grouped["op1_A_shape"], [1, 4, 32])
        self.assertEqual(
            set(self.checked["closed_previous_blockers"]),
            {
                "B_DS_RMSNORM_LEADER_SLICE_ROUTING",
                "B_DS_RMSNORM_REMOTE_SUM_GATHER",
                "B_DS_RMSNORM_CONTROL_FIELD_RESOLUTION",
                "B_DS_RMSNORM_STAGE_TOPOLOGY_GAP",
            },
        )

    def test_raw_stage_gap_is_closed_by_active_stage_producer(self) -> None:
        self.assertEqual(self.checked["blockers"], [])
        gap = self.checked["onnx_to_stage"][
            "raw_to_normalized_topology_gap"
        ]
        self.assertEqual(
            gap["raw_op1_used_slices"],
            "0b1000000000000000000000000000",
        )
        self.assertEqual(gap["normalized_op1_A_shape"], [1, 4, 32])
        self.assertEqual(gap["raw_op2_A_type"], "slice0")
        self.assertIsNone(gap["normalized_op2_A_type"])

    def test_normalized_double_run_and_final_controls_are_closed(self) -> None:
        lifecycle = self.checked["stage_json_bitstream_lifecycle"]
        native = lifecycle["native_double_run"]
        self.assertEqual(native["returncode"], 0)
        self.assertEqual(native["parsed_operator_count"], 5)
        self.assertEqual(native["output_file_count_per_run"], 61)
        self.assertTrue(native["deterministic_outputs_byte_identical"])
        self.assertTrue(
            lifecycle[
                "first_four_address_bound_stages_match_trusted_package"
            ]
        )
        constants = lifecycle["op2_config_loaded_constants"]
        self.assertEqual(
            constants["mean_1_div_896_fp32_occurrences"], 8
        )
        self.assertEqual(
            constants["epsilon_1e_minus_6_fp32_occurrences"], 8
        )
        self.assertTrue(
            constants[
                "unresolved_dynamic_control_names_are_config_load_owned"
            ]
        )
        self.assertEqual(lifecycle["config_length"]["status"], "CLOSED")
        policy = self.checked["policy_result"]
        self.assertTrue(
            policy["onnx_to_five_stage_semantic_decomposition_closed"]
        )
        self.assertTrue(
            policy["rule_normalized_five_stage_lifecycle_accepted"]
        )
        self.assertFalse(
            policy["upstream_raw_stage_is_active_stage"]
        )
        self.assertTrue(
            policy[
                "active_stage_is_sufficient_for_automatic_generation"
            ]
        )
        self.assertTrue(policy["local_e2_reference_conformant"])
        self.assertFalse(policy["advance_to_server_test"])

    def test_graph_and_contract_tamper_fail_closed(self) -> None:
        graph = build_rmsnorm_graph(ROOT)
        tampered_graph = deepcopy(graph)
        tampered_graph["operators"][2]["inputs"]["A"]["type"] = "slice0"
        with self.assertRaisesRegex(
            DeepSeekRmsNormValidationError,
            "differs from ONNX/crop/native-stage evidence",
        ):
            validate_rmsnorm_graph(tampered_graph, ROOT)

        tampered_contract = deepcopy(self.checked)
        tampered_contract["policy_result"][
            "rule_normalized_five_stage_lifecycle_accepted"
        ] = False
        with self.assertRaisesRegex(
            DeepSeekRmsNormValidationError,
            "differs from current evidence",
        ):
            validate_rmsnorm_blocker_contract(
                tampered_contract, ROOT
            )


if __name__ == "__main__":
    unittest.main()
