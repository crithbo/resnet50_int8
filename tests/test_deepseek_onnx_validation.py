from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_onnx_validation import (
    DeepSeekOnnxValidationError,
    build_deepseek_crop_contract,
    build_deepseek_onnx_stage_mapping,
    build_deepseek_prefill_stage_audit,
    validate_deepseek_crop_contract,
    validate_deepseek_onnx_stage_mapping,
    validate_deepseek_prefill_stage_audit,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts"
    / "operator_config"
    / "deepseek_ndpsim_crop_contract_v1.json"
)
STAGE_MAPPING = (
    ROOT
    / "contracts"
    / "operator_config"
    / "deepseek_onnx_stage_mapping_v1.json"
)
PREFILL_AUDIT = (
    ROOT
    / "contracts"
    / "operator_config"
    / "deepseek_onnx_prefill_stage_audit_v1.json"
)


class DeepSeekOnnxValidationTests(unittest.TestCase):
    def test_crop_contract_matches_current_sources(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        rebuilt = build_deepseek_crop_contract(ROOT)
        self.assertEqual(checked, rebuilt)
        validate_deepseek_crop_contract(checked, ROOT)

    def test_crop_contract_is_explicit_and_not_source_identity(self) -> None:
        value = build_deepseek_crop_contract(ROOT)
        self.assertEqual(
            value["identity_boundary"],
            {
                "onnx_identity_classification": "SEMANTIC_MODEL_MATCH",
                "original_source_identity": False,
                "ndpsim_weight_origin_proven": False,
                "direct_equal_shape_claim": False,
                "crop_required": True,
            },
        )
        self.assertEqual(
            value["model_dimensions"]["derived"],
            {
                "query_width": 896,
                "kv_width": 128,
                "hidden_elements_per_slice": 32,
                "intermediate_elements_per_slice": 64,
                "active_slice_count": 28,
            },
        )
        self.assertEqual(
            value["layer_selection"]["selected_source_layers"], [0]
        )
        self.assertFalse(
            value["layer_selection"][
                "crop_producer_removes_unselected_layers"
            ]
        )
        self.assertEqual(len(value["tensor_crop_rules"]), 7)

    def test_crop_contract_tamper_fails_closed(self) -> None:
        value = build_deepseek_crop_contract(ROOT)
        tampered = deepcopy(value)
        tampered["identity_boundary"]["original_source_identity"] = True
        with self.assertRaisesRegex(
            DeepSeekOnnxValidationError,
            "differs from current evidence",
        ):
            validate_deepseek_crop_contract(tampered, ROOT)

    def test_onnx_stage_mapping_matches_current_sources(self) -> None:
        checked = json.loads(STAGE_MAPPING.read_text(encoding="utf-8"))
        rebuilt = build_deepseek_onnx_stage_mapping(ROOT)
        self.assertEqual(checked, rebuilt)
        validate_deepseek_onnx_stage_mapping(checked, ROOT)

    def test_onnx_stage_mapping_fails_before_json_generation(self) -> None:
        value = build_deepseek_onnx_stage_mapping(ROOT)
        self.assertEqual(
            value["status"], "blocked_before_stage_to_json_generation"
        )
        self.assertFalse(
            value["policy_result"]["onnx_to_stage_ir_ready"]
        )
        self.assertFalse(
            value["policy_result"][
                "stage_to_json_forward_generation_allowed"
            ]
        )
        self.assertFalse(
            value["policy_result"][
                "trusted_individual_json_semantics_invalidated"
            ]
        )
        self.assertEqual(
            set(value["blocker_ids"]),
            {
                "B_DS_QKV_SHARED_NORMALIZED_INPUT_IDENTITY",
                "B_DS_KV_GQA_REPLICATION_IDENTITY",
                "B_DS_GQA_SCALE_MISSING",
                "B_DS_QKT_VECTOR_REDUCTION_ROUTE",
                "B_DS_SOFTMAX_GLOBAL_NORMALIZATION",
                "B_DS_DECODE_PROGRAM_GOLDEN_PARITY",
                "B_DS_RESIDUAL_TENSOR_IDENTITY",
                "B_DS_CURRENT_TOKEN_KV_LIFECYCLE",
                "B_DS_DECODE_REGISTRY_JSON_IDENTITY",
            },
        )
        self.assertEqual(
            {
                item["id"]
                for item in value["open_provenance_confirmations"]
            },
            {
                "B_DS_ONNX_ORIGINAL_SOURCE_IDENTITY",
                "B_DS_QKV_FUSED_EXTRACTION_IDENTITY",
            },
        )
        softmax = next(
            item
            for item in value["blockers"]
            if item["id"] == "B_DS_SOFTMAX_GLOBAL_NORMALIZATION"
        )
        for actual in softmax["evidence"][
            "actual_probability_sum_per_head"
        ]:
            self.assertAlmostEqual(actual, 4.0, places=5)

    def test_onnx_stage_mapping_tamper_fails_closed(self) -> None:
        value = build_deepseek_onnx_stage_mapping(ROOT)
        tampered = deepcopy(value)
        tampered["policy_result"][
            "stage_to_json_forward_generation_allowed"
        ] = True
        with self.assertRaisesRegex(
            DeepSeekOnnxValidationError,
            "differs from current evidence",
        ):
            validate_deepseek_onnx_stage_mapping(tampered, ROOT)

    def test_prefill_stage_audit_matches_current_sources(self) -> None:
        checked = json.loads(PREFILL_AUDIT.read_text(encoding="utf-8"))
        rebuilt = build_deepseek_prefill_stage_audit(ROOT)
        self.assertEqual(checked, rebuilt)
        validate_deepseek_prefill_stage_audit(checked, ROOT)

    def test_prefill_stage_audit_closes_numeric_subchains_only(self) -> None:
        value = build_deepseek_prefill_stage_audit(ROOT)
        self.assertEqual(
            set(value["semantic_blocker_ids"]),
            {
                "B_DS_PREFILL_TOP_LEVEL_SLICE_MASK_ENCODING",
                "B_DS_PREFILL_REMOTE_REDUCTION_BYTE_EXTENT",
                "B_DS_PREFILL_LEADER_SLICE_ROUTING",
                "B_DS_PREFILL_EXTERNAL_ALIAS_MANIFEST",
            },
        )
        self.assertTrue(
            value["locally_closed_semantics"]["gqa_scale"]["closed"]
        )
        self.assertTrue(
            value["locally_closed_semantics"]["gqa_kv_replication"][
                "closed_at_relayout_formula_level"
            ]
        )
        self.assertTrue(
            value["locally_closed_semantics"]["prefill_current_kv_sources"][
                "closed_at_program_source_level"
            ]
        )
        self.assertFalse(
            value["locally_closed_semantics"]["softmax_key_axis"][
                "closed_unconditionally"
            ]
        )
        extent = next(
            item
            for item in value["semantic_blockers"]
            if item["id"]
            == "B_DS_PREFILL_REMOTE_REDUCTION_BYTE_EXTENT"
        )
        self.assertEqual(extent["evidence"]["extent_ratio"], 4.0)
        self.assertFalse(
            value["policy_result"][
                "stage_to_json_forward_generation_allowed"
            ]
        )

    def test_prefill_stage_audit_tamper_fails_closed(self) -> None:
        value = build_deepseek_prefill_stage_audit(ROOT)
        tampered = deepcopy(value)
        tampered["policy_result"][
            "stage_to_json_forward_generation_allowed"
        ] = True
        with self.assertRaisesRegex(
            DeepSeekOnnxValidationError,
            "differs from current evidence",
        ):
            validate_deepseek_prefill_stage_audit(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
