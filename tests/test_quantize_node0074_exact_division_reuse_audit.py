from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.quantize_node0074_exact_division_reuse_audit import (
    validate_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json"
)


class QuantizeNode0074ExactDivisionReuseAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_reuse_is_structure_or_primitive_only(self) -> None:
        reuse = self.report["reuse_class_and_boundary"]
        self.assertEqual(reuse["class"], "STRUCTURE_OR_PRIMITIVE_ONLY")
        self.assertFalse(
            reuse["parameter_shape_layout_substitutions"][
                "source_numeric_formula_reused"
            ]
        )

    def test_current_corpus_has_no_division_entry(self) -> None:
        corpus = self.report["current_corpus_audit"]
        self.assertEqual(corpus["template_count"], 55)
        self.assertEqual(corpus["quantize_template_count"], 1)
        self.assertFalse(corpus["direct_division_template_present"])
        self.assertFalse(corpus["direct_division_opcode_present"])

    def test_encoder_handler_mapper_and_rtl_stop_at_rec(self) -> None:
        transport = self.report["encoder_handler_mapper_audit"]
        self.assertEqual(transport["rec_opcode"], 17)
        self.assertIsNone(transport["division_opcode"])
        self.assertEqual(transport["quant_handler"], "PLACEHOLDER_BLOCKED")
        self.assertEqual(transport["quant_mapper"], "REGISTRY_MISSING")
        rtl = self.report["rtl_consumer_audit"]
        self.assertFalse(rtl["direct_binary32_divider_present"])
        self.assertIn("slope_intercept_MAC", rtl["rec_datapath"])

    def test_counterexample_is_bound_without_retest(self) -> None:
        counterexample = self.report["accepted_counterexample_binding"]
        self.assertFalse(counterexample["retested"])
        self.assertEqual(counterexample["divide_then_rne_uint8"], 159)
        self.assertEqual(counterexample["reciprocal_mul_then_rne_uint8"], 158)
        self.assertTrue(counterexample["still_contradicts_rec_mul"])

    def test_endpoint_and_outputs_remain_fail_closed(self) -> None:
        endpoint = self.report["endpoint_binding"]
        self.assertTrue(endpoint["consumer_owned_fields_all_null"])
        self.assertFalse(endpoint["provisional_address_allowed"])
        self.assertFalse(endpoint["integrated_endpoint_closed"])
        self.assertTrue(
            all(value is False for value in self.report["generated_outputs"].values())
        )
        self.assertEqual(self.report["package_release"], "NONE")


if __name__ == "__main__":
    unittest.main()
