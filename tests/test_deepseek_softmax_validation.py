from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_softmax_validation import (
    CONTRACT_PATH,
    DeepSeekSoftmaxValidationError,
    EXP_LAYOUT_HINT,
    MASK_LAYOUT_HINT,
    OPERATOR_TYPES,
    build_softmax_blocker_contract,
    build_softmax_graph,
    build_raw_softmax_stage_graph,
    validate_softmax_blocker_contract,
    validate_softmax_graph,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class DeepSeekSoftmaxValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            CONTRACT.read_text(encoding="utf-8")
        )

    def test_graph_binds_fused_gqa_crop_and_five_stages(self) -> None:
        raw = build_raw_softmax_stage_graph(ROOT)
        graph = build_softmax_graph(ROOT)
        validate_softmax_graph(graph, ROOT)
        self.assertEqual(
            [item["type"] for item in graph["operators"]],
            list(OPERATOR_TYPES),
        )
        self.assertEqual(graph["used_slices"], 28)
        self.assertEqual(
            graph["operators"][0]["inputs"]["A"]["source"],
            {"type": "external"},
        )
        self.assertNotIn(
            "type", graph["operators"][0]["inputs"]["A"]
        )
        self.assertEqual(
            graph["operators"][4]["inputs"]["B"]["source"], "op3"
        )
        self.assertNotIn(
            "write_reg_hint",
            raw["operators"][0]["inputs"]["C"],
        )
        self.assertNotIn(
            "write_reg_hint",
            raw["operators"][2]["inputs"]["A"],
        )
        self.assertEqual(
            graph["operators"][0]["inputs"]["C"]["write_reg_hint"],
            MASK_LAYOUT_HINT,
        )
        self.assertEqual(
            graph["operators"][2]["inputs"]["A"]["write_reg_hint"],
            EXP_LAYOUT_HINT,
        )

    def test_checked_blocker_contract_matches_current_evidence(self) -> None:
        rebuilt = build_softmax_blocker_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_softmax_blocker_contract(self.checked, ROOT)

    def test_identity_crop_and_input_representation_are_explicit(self) -> None:
        boundary = self.checked["identity_boundary"]
        self.assertEqual(
            boundary["onnx_repository_classification"],
            "SEMANTIC_MODEL_MATCH",
        )
        self.assertFalse(boundary["original_source_identity"])
        self.assertFalse(boundary["direct_onnx_shape_equals_stage"])
        self.assertTrue(boundary["crop_contract_required"])
        stage = self.checked["onnx_to_stage"]
        self.assertEqual(stage["crop_derived_q_heads"], 7)
        self.assertEqual(stage["head_dim"], 128)
        self.assertEqual(stage["sequence_length"], 32)
        self.assertIn(
            "replicated onto all four slices",
            stage["isolated_input_representation_contract"],
        )

    def test_double_run_is_structurally_complete_and_stable(self) -> None:
        lifecycle = self.checked[
            "stage_json_bitstream_lifecycle"
        ]
        self.assertTrue(lifecycle["structurally_complete"])
        self.assertTrue(lifecycle["rule_normalized_config_accepted"])
        native = lifecycle["native_double_run"]
        self.assertEqual(native["output_file_count_per_run"], 62)
        self.assertEqual(native["deterministic_file_count"], 57)
        self.assertTrue(
            native["deterministic_outputs_byte_identical"]
        )
        self.assertEqual(
            lifecycle["generated_lifecycle"]["event_order"],
            lifecycle["trusted_lifecycle"]["event_order"],
        )
        self.assertEqual(
            lifecycle["generated_lifecycle"]["command_count"], 364
        )
        self.assertEqual(
            lifecycle["trusted_lifecycle"]["command_count"], 392
        )

    def test_all_rule_normalized_jsons_match_trusted_oracle(self) -> None:
        comparison = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["trusted_materialized_oracle_comparison"]
        self.assertEqual(
            comparison["matching_operator_ids"],
            ["op0", "op1", "op2", "op3", "op4"],
        )
        self.assertEqual(comparison["divergent_operator_ids"], [])
        self.assertTrue(comparison["generated_package_accepted"])
        self.assertTrue(
            all(
                item["canonical_json_equal"]
                for item in comparison["operator_comparisons"]
            )
        )

    def test_raw_stage_layout_hint_gap_is_closed_by_active_stage(self) -> None:
        finding = next(
            item
            for item in self.checked["closed_findings"]
            if item["id"]
            == "B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP"
        )
        self.assertIn(
            "active Stage producer", finding["closure"]
        )
        raw = self.checked["onnx_to_stage"][
            "raw_stage_missing_layout_hints"
        ]
        self.assertIsNone(raw["op0_C"])
        self.assertIsNone(raw["op2_A"])

    def test_closed_layout_differences_are_recorded(self) -> None:
        self.assertEqual(
            {
                item["id"] for item in self.checked["closed_findings"]
            },
            {
                "B_DS_SOFTMAX_MASK_C_STRIDE_ORACLE_DIVERGENCE",
                (
                    "B_DS_SOFTMAX_EXP_INPUT_BANK_LAYOUT_"
                    "ORACLE_DIVERGENCE"
                ),
                "B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP",
                "B_DS_SOFTMAX_NUMERIC_PAYLOAD_EVIDENCE",
            },
        )

    def test_synthetic_numeric_e2_closes_local_payload_gap(self) -> None:
        boundary = self.checked["trusted_numeric_payload_boundary"]
        self.assertEqual(boundary["install_tensor_file_count"], 1092)
        self.assertEqual(boundary["output_tensor_file_count"], 140)
        self.assertFalse(boundary["numerical_golden_available"])
        numeric = self.checked["synthetic_numeric_e2"]
        self.assertEqual(numeric["coverage"]["nonempty_file_count"], 245)
        self.assertEqual(numeric["coverage"]["slice_count"], 28)
        self.assertTrue(
            numeric["numeric_result"][
                "logical_payload_matches_independent_formula"
            ]
        )
        self.assertTrue(
            numeric["numeric_result"][
                "physical_payload_matches_native_relayout"
            ]
        )
        policy = self.checked["policy_result"]
        self.assertTrue(
            policy["materialized_json_matches_trusted_oracle"]
        )
        self.assertTrue(
            policy["rule_normalized_five_stage_lifecycle_accepted"]
        )
        self.assertTrue(policy["local_e2_reference_conformant"])
        self.assertEqual(self.checked["blockers"], [])
        self.assertFalse(policy["advance_to_server_test"])

    def test_graph_and_contract_tamper_fail_closed(self) -> None:
        graph = build_softmax_graph(ROOT)
        tampered_graph = deepcopy(graph)
        tampered_graph["operators"][2]["inputs"]["B"]["source"] = "op0"
        with self.assertRaisesRegex(
            DeepSeekSoftmaxValidationError,
            "differs from ONNX/crop/native-stage evidence",
        ):
            validate_softmax_graph(tampered_graph, ROOT)

        tampered_contract = deepcopy(self.checked)
        tampered_contract["policy_result"][
            "materialized_json_matches_trusted_oracle"
        ] = False
        with self.assertRaisesRegex(
            DeepSeekSoftmaxValidationError,
            "differs from current evidence",
        ):
            validate_softmax_blocker_contract(
                tampered_contract, ROOT
            )


if __name__ == "__main__":
    unittest.main()
