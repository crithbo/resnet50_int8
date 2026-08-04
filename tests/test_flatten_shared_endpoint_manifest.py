from __future__ import annotations

import copy
import unittest
from pathlib import Path

from resnet50_pipeline.flatten_shared_endpoint_manifest import (
    FlattenSharedEndpointError,
    build_manifest,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class FlattenSharedEndpointManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # This consumes frozen receipts only; it does not invoke either numeric path.
        cls.manifest = build_manifest(ROOT)

    def test_reuse_only_manifest_is_fail_closed(self) -> None:
        report = validate_manifest(self.manifest, ROOT)
        self.assertTrue(report["valid"])
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertTrue(report["reused_assets_consumed"])
        self.assertFalse(report["integrated_target_local_e2"])
        self.assertIsNone(report["claim_label"])
        self.assertEqual(report["consumer_final_endpoint_null_field_count"], 6)

    def test_producer_standalone_evidence_is_not_shared_binding(self) -> None:
        producer = self.manifest["producer_standalone_evidence"]
        shared = self.manifest["shared_endpoint_binding"]
        self.assertEqual(producer["logical_valid_write_coverage_bytes"], 131072)
        self.assertEqual(len(producer["slice_d_base_addresses"]), 28)
        self.assertIsNone(shared["storage_id"])
        self.assertFalse(shared["same_storage_proven"])
        self.assertFalse(shared["same_base_plus_offset_proven"])

    def test_consumer_endpoint_fabrication_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["consumer_endpoint"]["final_consumer_base"] = "0x000004a0"
        with self.assertRaisesRegex(
            FlattenSharedEndpointError, "consumer final_consumer_base must remain null"
        ):
            validate_manifest(mutated, ROOT)

    def test_integrated_claim_promotion_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["integrated_target_local_e2"] = True
        with self.assertRaisesRegex(
            FlattenSharedEndpointError,
            "integrated target local E2 must remain false",
        ):
            validate_manifest(mutated, ROOT)

    def test_copy_or_replay_fallback_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.manifest)
        mutated["view_alias"]["copies"] = True
        with self.assertRaisesRegex(FlattenSharedEndpointError, "copy fallback"):
            validate_manifest(mutated, ROOT)


if __name__ == "__main__":
    unittest.main()
