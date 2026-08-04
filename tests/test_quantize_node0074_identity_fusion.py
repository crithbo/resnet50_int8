from __future__ import annotations

import copy
import unittest
from pathlib import Path

from resnet50_pipeline.quantize_node0074_identity_fusion import (
    IdentityFusionError,
    TARGET_TENSOR_ID,
    exact_domain_proof,
    extract_instance_descriptor,
    negative_control_results,
    validate_contract,
    validate_instance_descriptor,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "quantize_node0074_dq_view_q_identity_fusion_v1.json"
)


class QuantizeNode0074IdentityFusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_qparams_and_node0075_qdomain_are_bitwise_identical(self) -> None:
        qparams = self.report["qparam_identity"]
        self.assertTrue(qparams["bitwise_identical"])
        self.assertEqual(qparams["scale_bits"], "0x3cbf57ec")
        self.assertEqual(qparams["zero_point"], 0)
        self.assertIsNone(qparams["axis"])
        self.assertTrue(qparams["downstream_node0075_a_qdomain_identical"])

    def test_full_uint8_domain_binary32_sequence_is_identity(self) -> None:
        proof = self.report["exact_equivalence"]
        self.assertEqual(proof["domain_value_count"], 256)
        self.assertEqual(proof["mismatch_count"], 0)
        self.assertTrue(proof["identity_for_all_values"])
        self.assertTrue(all(row["identity_pass"] for row in proof["per_value_records"]))

    def test_noninteger_quotients_keep_positive_rounding_margin(self) -> None:
        proof = self.report["exact_equivalence"]
        self.assertGreater(proof["noninteger_unrounded_exact_quotient_count"], 0)
        self.assertGreater(
            proof["minimum_margin_to_wrong_nearest_even_boundary"]["float"], 0.0
        )

    def test_all_required_negative_controls_fail_closed(self) -> None:
        controls = self.report["negative_controls"]
        self.assertEqual(
            set(controls),
            {
                "scale_bits",
                "zero_point",
                "dtype",
                "axis",
                "element_order",
                "layout",
                "storage_offset",
            },
        )
        self.assertTrue(all(value["fail_closed"] for value in controls.values()))

    def test_rec_mul_counterexample_remains_generic_only(self) -> None:
        counterexample = self.report["accepted_rec_mul_counterexample"]
        self.assertFalse(counterexample["retested"])
        self.assertEqual(counterexample["divide_then_rne_uint8"], 159)
        self.assertEqual(counterexample["reciprocal_mul_then_rne_uint8"], 158)
        self.assertIn("does not execute", counterexample["scope"])

    def test_uint8_view_rewrite_is_typed_but_physical_binding_waits(self) -> None:
        descriptor = extract_instance_descriptor(ROOT)
        self.assertEqual(descriptor["rewrite"]["alias_tensor_id"], TARGET_TENSOR_ID)
        self.assertEqual(descriptor["rewrite"]["alias_dtype"], "uint8")
        self.assertEqual(descriptor["rewrite"]["alias_shape"], [16, 2048])
        self.assertEqual(descriptor["rewrite"]["alias_byte_strides"], [2048, 1])
        self.assertTrue(self.report["graph_rewrite"]["typed_rewrite_closed"])
        self.assertFalse(self.report["graph_rewrite"]["physical_integration_closed"])
        endpoint = self.report["endpoint_handoff"]
        self.assertTrue(
            all(value is None for value in endpoint["consumer_owned_endpoint_fields"].values())
        )
        self.assertEqual(
            endpoint["first_integration_blocker"]["kind"], "WAIT_INTEGRATION_OWNER"
        )

    def test_generic_divider_blockers_remain_open_but_off_path(self) -> None:
        blockers = self.report["generic_capability_blockers"]
        for value in blockers.values():
            self.assertEqual(value["status"], "OPEN_GENERIC_FAMILY_CAPABILITY")
            self.assertFalse(value["on_this_frozen_chain_execution_path"])

    def test_contract_has_no_target_or_package_and_no_external_mutation(self) -> None:
        self.assertTrue(all(value is False for value in self.report["outputs"].values()))
        self.assertEqual(self.report["package_release"], "NONE")
        self.assertEqual(
            self.report["package_release_reason"], "WAIT_INTEGRATION_OWNER"
        )

    def test_direct_mutation_of_descriptor_fails_closed(self) -> None:
        descriptor = extract_instance_descriptor(ROOT)
        candidate = copy.deepcopy(descriptor)
        candidate["quant"]["scale_bits"] = "0x3cbf57ed"
        with self.assertRaisesRegex(IdentityFusionError, "qparam mismatch"):
            validate_instance_descriptor(candidate)
        self.assertTrue(
            all(
                result["fail_closed"]
                for result in negative_control_results(descriptor).values()
            )
        )

    def test_exact_proof_is_deterministic(self) -> None:
        first = exact_domain_proof()
        second = exact_domain_proof()
        self.assertEqual(
            first["per_value_records_sha256"], second["per_value_records_sha256"]
        )


if __name__ == "__main__":
    unittest.main()
