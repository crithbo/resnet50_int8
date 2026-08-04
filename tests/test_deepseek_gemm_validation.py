from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_gemm_validation import (
    A_LAYOUT_HINT,
    B_LAYOUT_HINT,
    CONTRACT_PATH,
    DeepSeekGemmValidationError,
    build_gemm_graph,
    build_gemm_validation_contract,
    build_raw_gemm_stage_graph,
    validate_gemm_graph,
    validate_gemm_validation_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class DeepSeekGemmValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            CONTRACT.read_text(encoding="utf-8")
        )

    def test_raw_stage_requires_rule_normalized_layout_hints(self) -> None:
        raw = build_raw_gemm_stage_graph(ROOT)
        normalized = build_gemm_graph(ROOT)
        self.assertIsNone(
            raw["operators"][0]["inputs"]["A"]["write_reg_hint"]
        )
        self.assertIsNone(
            raw["operators"][0]["inputs"]["B"]["write_reg_hint"]
        )
        self.assertEqual(
            normalized["operators"][0]["inputs"]["A"][
                "write_reg_hint"
            ],
            A_LAYOUT_HINT,
        )
        self.assertEqual(
            normalized["operators"][0]["inputs"]["B"][
                "write_reg_hint"
            ],
            B_LAYOUT_HINT,
        )
        validate_gemm_graph(normalized, ROOT)

    def test_checked_contract_matches_current_evidence(self) -> None:
        rebuilt = build_gemm_validation_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_gemm_validation_contract(self.checked, ROOT)

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
        self.assertIn("[1,32,896]", stage["crop_formula"])
        self.assertIn("28 slices", stage["hardware_slice_formula"])

    def test_occurrence_ring_and_output_coverage_are_exact(self) -> None:
        layout = self.checked["layout_and_occurrence_contract"]
        self.assertEqual(layout["per_slice"]["A_bytes"], 2048)
        self.assertEqual(layout["per_slice"]["B_bytes"], 114688)
        self.assertEqual(layout["per_slice"]["D_bytes"], 4096)
        self.assertEqual(layout["ring"]["n2n_mem_loop"], 28)
        self.assertEqual(layout["ring"]["src_slice_sel"], 0)
        self.assertEqual(layout["ring"]["dst_slice_sel"], 0)
        self.assertTrue(
            layout["B_and_B_prime_share_logical_allocation"]
        )
        self.assertEqual(layout["sca_d"]["slice_count"], 28)
        self.assertEqual(
            layout["sca_d"]["lines_128b_per_slice"], 256
        )

    def test_double_isolated_rebuild_is_deterministic(self) -> None:
        lifecycle = self.checked[
            "stage_json_bitstream_lifecycle"
        ]
        native = lifecycle["native_double_run"]
        self.assertTrue(native["empty_cache_at_start"])
        self.assertEqual(native["random_seed"], 19)
        self.assertEqual(native["python_hash_seed"], 0)
        self.assertEqual(native["output_file_count_per_run"], 16)
        self.assertEqual(native["deterministic_file_count"], 15)
        self.assertTrue(
            native["deterministic_outputs_byte_identical"]
        )
        self.assertEqual(lifecycle["mapping_exact_penalty"], 0.0)

    def test_address_graph_and_lifecycle_match_trusted_package(self) -> None:
        lifecycle = self.checked[
            "stage_json_bitstream_lifecycle"
        ]
        self.assertEqual(lifecycle["address_bound_graph_diff"], [])
        comparison = lifecycle["instruction_comparison"]
        self.assertEqual(comparison["difference_count"], 0)
        self.assertTrue(
            comparison["all_write_reg_and_start_comp_commands_equal"]
        )
        self.assertTrue(comparison["all_commands_equal"])
        self.assertEqual(
            lifecycle["generated_lifecycle"]["command_count"], 111
        )
        self.assertEqual(
            lifecycle["trusted_lifecycle"]["command_count"], 111
        )

    def test_config_length_excludes_padded_high_half(self) -> None:
        comparison = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["config_length_comparison"]
        self.assertEqual(comparison["physical_128bit_rows"], 30)
        self.assertEqual(comparison["source_64bit_word_count"], 59)
        self.assertEqual(
            comparison["physical_64bit_transport_slots"], 60
        )
        self.assertTrue(
            comparison["last_row_high_half_is_transport_padding"]
        )
        self.assertEqual(
            comparison["trusted_load_config_length_64bit_words"], 59
        )
        self.assertEqual(
            comparison["generated_load_config_length_64bit_words"], 59
        )
        blocker_ids = {
            item["id"] for item in self.checked["blockers"]
        }
        self.assertNotIn(
            "B_DS_GEMM_CONFIG_LENGTH_ORACLE_DIVERGENCE",
            blocker_ids,
        )
        self.assertTrue(
            self.checked["policy_result"][
                "load_config_length_matches_trusted_oracle"
            ]
        )

    def test_synthetic_numeric_e2_closes_local_payload_gap(self) -> None:
        numeric = self.checked["trusted_numeric_payload_boundary"]
        self.assertFalse(numeric["onnx_external_weight_payload_downloaded"])
        self.assertFalse(
            numeric["trusted_package_tensor_payload_available"]
        )
        self.assertFalse(numeric["numerical_golden_available"])
        synthetic = self.checked["synthetic_numeric_e2"]
        self.assertEqual(synthetic["coverage"]["nonempty_file_count"], 88)
        self.assertEqual(
            synthetic["coverage"]["K_chunk_count_per_output_slice"],
            28,
        )
        self.assertTrue(
            synthetic["numeric_result"][
                "all_28_K_chunks_covered_per_output_slice"
            ]
        )
        self.assertTrue(
            synthetic["numeric_result"][
                "physical_payload_matches_native_relayout"
            ]
        )
        policy = self.checked["policy_result"]
        self.assertTrue(policy["local_e2_reference_conformant"])
        self.assertEqual(self.checked["blockers"], [])
        self.assertFalse(policy["advance_to_server_test"])

    def test_graph_and_contract_tamper_fail_closed(self) -> None:
        graph = build_gemm_graph(ROOT)
        tampered_graph = deepcopy(graph)
        tampered_graph["operators"][0]["inputs"]["A"][
            "write_reg_hint"
        ] = None
        with self.assertRaisesRegex(
            DeepSeekGemmValidationError,
            "differs from ONNX/crop/native-stage evidence",
        ):
            validate_gemm_graph(tampered_graph, ROOT)

        tampered_contract = deepcopy(self.checked)
        tampered_contract["policy_result"][
            "load_config_length_matches_trusted_oracle"
        ] = False
        with self.assertRaisesRegex(
            DeepSeekGemmValidationError,
            "differs from current evidence",
        ):
            validate_gemm_validation_contract(
                tampered_contract, ROOT
            )


if __name__ == "__main__":
    unittest.main()
