from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_gemv_validation import (
    CONTRACT_PATH,
    DeepSeekGemvValidationError,
    build_gemv_graph,
    build_gemv_validation_contract,
    validate_gemv_graph,
    validate_gemv_validation_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


class DeepSeekGemvValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            CONTRACT.read_text(encoding="utf-8")
        )

    def test_graph_is_crop_derived_decode_ffn_gate(self) -> None:
        graph = build_gemv_graph(ROOT)
        validate_gemv_graph(graph, ROOT)
        op = graph["operators"][0]
        self.assertEqual(op["type"], "decode_gemv_ring")
        self.assertEqual(op["id"], "op0")
        self.assertEqual(
            op["inputs"]["A"]["source"], {"type": "external"}
        )
        self.assertEqual(
            op["inputs"]["A"]["shape"],
            ["hidden_size//used_slices", 1, 1],
        )
        self.assertEqual(
            op["inputs"]["B"]["shape"],
            ["hidden_size", 1, "intermediate_size//used_slices"],
        )

    def test_checked_contract_matches_current_evidence(self) -> None:
        rebuilt = build_gemv_validation_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_gemv_validation_contract(self.checked, ROOT)

    def test_identity_and_numeric_oracle_class_are_explicit(self) -> None:
        boundary = self.checked["identity_boundary"]
        self.assertEqual(
            boundary["onnx_repository_classification"],
            "SEMANTIC_MODEL_MATCH",
        )
        self.assertFalse(boundary["original_source_identity"])
        self.assertFalse(boundary["direct_onnx_shape_equals_stage"])
        self.assertTrue(boundary["crop_contract_required"])
        self.assertEqual(
            boundary["numeric_oracle_classification"],
            "TRUSTED_CROP_DERIVED_HWVERIFIED_NUMERIC_ORACLE",
        )

    def test_numeric_formula_is_bitwise_closed(self) -> None:
        comparison = self.checked["numeric_oracle"]["comparison"]
        self.assertEqual(comparison["element_count"], 1792)
        self.assertEqual(
            comparison["bitwise_fp16_mismatch_count"], 0
        )
        self.assertTrue(comparison["bitwise_fp16_equal"])
        self.assertTrue(
            self.checked["policy_result"][
                "numeric_formula_bitwise_closed"
            ]
        )

    def test_B_and_B_prime_are_independent_half_allocations(self) -> None:
        contract = self.checked["address_layout_and_occurrence"]
        self.assertTrue(
            contract[
                "B_and_B_prime_are_independent_half_allocations"
            ]
        )
        self.assertEqual(
            contract["per_slice_bytes"]["B"], 57344
        )
        self.assertEqual(
            contract["per_slice_bytes"]["B_prime"], 57344
        )
        self.assertEqual(
            contract["base_addresses"],
            {
                "A": "0x00000000",
                "B": "0x00000040",
                "B_prime": "0x0000E040",
                "D": "0x0001C040",
            },
        )

    def test_ring_and_D_coverage_are_exact(self) -> None:
        contract = self.checked["address_layout_and_occurrence"]
        self.assertEqual(
            contract["ring"],
            {
                "participating_slice_count": 28,
                "n2n_mem_loop": 28,
                "src_slice_sel": 0,
                "dst_slice_sel": 0,
            },
        )
        self.assertEqual(contract["sca_d"]["slice_count"], 28)
        self.assertEqual(
            contract["sca_d"]["lines_128b_per_slice"], 8
        )

    def test_double_isolated_rebuild_is_deterministic(self) -> None:
        lifecycle = self.checked[
            "stage_json_bitstream_lifecycle"
        ]
        native = lifecycle["native_double_run"]
        self.assertTrue(native["empty_cache_at_start"])
        self.assertEqual(native["random_seed"], 42)
        self.assertEqual(native["python_hash_seed"], 0)
        self.assertEqual(native["output_file_count_per_run"], 16)
        self.assertEqual(native["deterministic_file_count"], 15)
        self.assertTrue(
            native["deterministic_outputs_byte_identical"]
        )
        self.assertEqual(lifecycle["mapping_exact_penalty"], 0.0)

    def test_config_length_is_closed_by_the_64bit_source_stream(self) -> None:
        self.assertEqual(self.checked["blockers"], [])
        comparison = self.checked[
            "stage_json_bitstream_lifecycle"
        ]["config_length"]
        self.assertEqual(comparison["physical_128bit_rows"], 39)
        self.assertEqual(
            comparison["physical_64bit_transport_slots"], 78
        )
        self.assertEqual(
            comparison["source_64bit_word_count"], 78
        )
        self.assertEqual(
            comparison["generated_load_config_length_64bit_words"],
            78,
        )
        self.assertTrue(
            comparison["matches_rtl_padding_contract"]
        )
        self.assertTrue(
            self.checked["policy_result"][
                "local_e2_reference_conformant"
            ]
        )

    def test_graph_and_contract_tamper_fail_closed(self) -> None:
        graph = build_gemv_graph(ROOT)
        tampered_graph = deepcopy(graph)
        tampered_graph["operators"][0]["inputs"]["B'"]["source"] = {
            "type": "external",
            "alias": "B",
        }
        with self.assertRaisesRegex(
            DeepSeekGemvValidationError,
            "differs from ONNX/crop/decode-stage evidence",
        ):
            validate_gemv_graph(tampered_graph, ROOT)

        tampered_contract = deepcopy(self.checked)
        tampered_contract["policy_result"][
            "load_config_length_closed"
        ] = False
        with self.assertRaisesRegex(
            DeepSeekGemvValidationError,
            "differs from current evidence",
        ):
            validate_gemv_validation_contract(
                tampered_contract, ROOT
            )


if __name__ == "__main__":
    unittest.main()
