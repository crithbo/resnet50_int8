from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.exact_uint8_quant_tail_rounding_discriminator import (
    build_bundle,
    validate_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/exact_uint8_quant_tail_rounding_discriminator_v1.json"
)


class ExactUint8QuantTailRoundingDiscriminatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tempdir.name) / "bundle"
        build_bundle(CONTRACT, ROOT, self.output_dir)
        self.report = validate_bundle(CONTRACT, ROOT, self.output_dir)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_config_bound_discriminator_is_26_vs_25(self) -> None:
        discriminator = self.report["discriminator"]
        self.assertEqual(discriminator["stage0_scratch_fp32_bits"], "0x41cc0000")
        self.assertEqual(discriminator["staged_config_result_uint8"], 26)
        self.assertEqual(discriminator["fused_negative_control_result_uint8"], 25)
        self.assertEqual(discriminator["separation"], 1)

    def test_all_seven_bypass_fields_are_required(self) -> None:
        bypass = self.report["bypass_annotation"]
        self.assertTrue(bypass["passed"])
        self.assertEqual(len(bypass["required_fields"]), 7)

    def test_every_materialized_leaf_diff_has_one_owner(self) -> None:
        ownership = self.report["materialized_leaf_ownership"]
        self.assertTrue(ownership["all_final_leaf_diffs_owned"])
        self.assertEqual(
            ownership["declaration_count"],
            sum(ownership["per_config_count"].values()),
        )
        self.assertGreater(ownership["declaration_count"], 0)
        replay = self.report["replay_contract"]
        self.assertEqual(
            replay["classification"],
            "formal_producer_output_delivery_not_host_precompute",
        )
        self.assertFalse(replay["host_precompute"])

    def test_output_coverage_is_recomputed_from_final_configs(self) -> None:
        coverage = self.report["materialized_output_coverage"]
        self.assertEqual(
            [item["unique_written_byte_count"] for item in coverage], [128, 32, 32]
        )
        self.assertTrue(all(item["coverage_ratio"] == "1/1" for item in coverage))

    def test_node0074_stops_at_exact_division(self) -> None:
        node = self.report["node0074_first_unavoidable_break"]
        self.assertEqual(node["first_unavoidable_break"], "exact_binary32_division")
        self.assertEqual(node["divide_then_rne_uint8"], 2)
        self.assertEqual(node["reciprocal_fma_magic_uint8"], 1)
        flatten = self.report["node0074_flatten_endpoint_dependency"]
        self.assertEqual(flatten["blocked_by"], "B_QUANT_NODE0074_EXACT_DIVISION")
        self.assertEqual(
            flatten["required_final_interface"]["read_coverage"]["required_bytes"],
            131072,
        )
        self.assertFalse(flatten["provisional_address_allowed"])
        self.assertFalse(flatten["target_endpoint_claimed"])

    def test_release_and_server_outputs_remain_forbidden(self) -> None:
        self.assertEqual(
            self.report["status"], "PASS_LOCAL_CONFIG_BOUND_26_VS_25_DIAGNOSTIC"
        )
        self.assertEqual(
            self.report["claim"], "LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE"
        )
        self.assertFalse(self.report["candidate_release"])
        generated = self.report["generated_outputs"]
        self.assertFalse(generated["target_json"])
        self.assertFalse(generated["mapping"])
        self.assertFalse(generated["bitstream"])
        self.assertFalse(generated["execplan"])
        self.assertFalse(generated["sca"])
        self.assertFalse(generated["server_package"])
        self.assertEqual(self.report["final_refresh_receipt_count"], 2)
        self.assertTrue(
            all(
                item["gate"] == "final_validation_snapshot_provenance_only"
                for item in self.report["final_refresh_receipts"]
            )
        )


if __name__ == "__main__":
    unittest.main()
