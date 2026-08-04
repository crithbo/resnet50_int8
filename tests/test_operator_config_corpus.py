from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_corpus import (
    build_hardware_evidence_audit,
    build_operator_config_authority,
    build_operator_config_corpus,
)


ROOT = Path(__file__).resolve().parents[1]


class OperatorConfigCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.authority = build_operator_config_authority(ROOT)
        cls.corpus = build_operator_config_corpus(ROOT)
        cls.hardware = build_hardware_evidence_audit(ROOT, cls.corpus)

    def test_current_and_historical_inventory_are_distinguished(self) -> None:
        self.assertEqual(self.corpus["summary"]["template_count"], 55)
        self.assertEqual(self.corpus["summary"]["historical_inventory_count"], 42)
        self.assertEqual(self.corpus["summary"]["historical_overlap_count"], 42)
        self.assertEqual(
            self.corpus["summary"]["user_authorized_correct_template_count"], 53
        )
        self.assertEqual(
            self.corpus["summary"]["project_added_or_modified_template_count"], 2
        )

    def test_authority_distinguishes_upstream_from_later_additions(self) -> None:
        summary = self.authority["summary"]
        self.assertEqual(summary["inventory_operator_config_count"], 67)
        self.assertEqual(summary["authorized_operator_config_count"], 65)
        self.assertEqual(
            summary["source_root_inventory_counts"],
            {"jsons": 12, "ndp-sim/jsons": 55},
        )
        self.assertEqual(
            summary["source_root_authorized_counts"],
            {"jsons": 12, "ndp-sim/jsons": 53},
        )
        self.assertFalse(summary["all_inventory_records_authorized_correct"])
        self.assertEqual(
            summary["excluded_paths"],
            [
                "ndp-sim/jsons/node0004_accumulate_wave0.json",
                "ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json",
            ],
        )

    def test_corpus_captures_real_hardware_control_features(self) -> None:
        templates = {item["template_id"]: item for item in self.corpus["templates"]}
        self.assertIn("maxpool_config_16_112_112_stride2_padding1", templates)
        self.assertGreaterEqual(
            templates["maxpool_config_16_112_112_stride2_padding1"]["features"][
                "padding_stream_count"
            ],
            1,
        )
        self.assertIn("prefill_gemm_ring_4slice", templates)
        self.assertTrue(
            templates["prefill_gemm_ring_4slice"]["features"]["has_special_array"]
        )

    def test_correct_reference_authority_is_separate_from_exact_run_receipts(self) -> None:
        summary = self.hardware["summary"]
        self.assertFalse(summary["all_templates_authorized_correct_references"])
        self.assertEqual(summary["user_authorized_correct_reference_count"], 53)
        self.assertFalse(summary["all_templates_positive_hardware_test_proven"])
        self.assertFalse(summary["all_templates_numeric_hardware_test_proven"])
        self.assertGreaterEqual(summary["exact_hardware_negative_count"], 2)

    def test_exact_reported_and_negative_cases_are_preserved(self) -> None:
        records = {item["template_id"]: item for item in self.hardware["records"]}
        self.assertEqual(
            records["decode_summac_fp32N_fp32N"]["exact_config_evidence"][
                "evidence_level"
            ],
            "E3-reported",
        )
        self.assertEqual(
            records["node0004_accumulate_wave0"]["exact_config_evidence"][
                "evidence_level"
            ],
            "hardware-negative",
        )
        self.assertFalse(
            records["node0004_accumulate_wave0"]["positive_hardware_test_proven"]
        )
        self.assertFalse(
            records["node0004_accumulate_wave0"][
                "reference_configuration_correctness"
            ]["accepted_as_correct_reference"]
        )
        self.assertTrue(
            records["quant_from_buffer_int32MN_uint8MN"][
                "reference_configuration_correctness"
            ]["accepted_as_correct_reference"]
        )
        self.assertEqual(
            records["decode_max_fp32N_fp32N"]["exact_config_evidence"][
                "evidence_level"
            ],
            "E3",
        )
        self.assertTrue(records["decode_max_fp32N_fp32N"]["positive_hardware_test_proven"])
        self.assertFalse(records["decode_max_fp32N_fp32N"]["numeric_hardware_test_proven"])
        self.assertEqual(
            records["node0004_accumulate_wave0_nopp_r1"]["exact_config_evidence"][
                "evidence_level"
            ],
            "hardware-attempt-invalid",
        )


if __name__ == "__main__":
    unittest.main()
