from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from resnet50_pipeline.gap_node0071_dequant_node0072_shared_endpoint import (
    CANONICAL_RELATIVE,
    GapDequantSharedEndpointError,
    build_manifest,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class GapNode0071DequantNode0072SharedEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / CANONICAL_RELATIVE).read_text(encoding="utf-8")
        )

    def _validate_corrupted(self, corrupted: dict) -> None:
        real_read = (
            "resnet50_pipeline.gap_node0071_dequant_node0072_shared_endpoint."
            "_read_json"
        )
        original = json.loads

        def read_override(path: Path) -> dict:
            if path.resolve() == (ROOT / CANONICAL_RELATIVE).resolve():
                return corrupted
            return original(path.read_text(encoding="utf-8"))

        with patch(real_read, side_effect=read_override):
            with self.assertRaises(GapDequantSharedEndpointError):
                validate_manifest(ROOT)

    def test_deterministic_build_equals_canonical(self) -> None:
        self.assertEqual(self.manifest, build_manifest(ROOT))

    def test_only_gap_producer_owner_section_is_written(self) -> None:
        self.assertEqual(
            set(self.manifest["owner_sections"]),
            {"QLinearGlobalAveragePool"},
        )
        self.assertEqual(
            self.manifest["required_missing_owner_sections"],
            ["DequantizeLinear"],
        )
        self.assertFalse(self.manifest["integrated_endpoint_closed"])

    def test_frozen_gap_endpoint_validates_without_numeric_retest(self) -> None:
        report = validate_manifest(ROOT)
        self.assertTrue(report["valid"])
        self.assertEqual(report["active_slice_count"], 16)
        self.assertEqual(report["physical_written_bytes"], 32768)
        self.assertEqual(report["physical_padding_bytes"], 0)
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["operator_e2_retested"])
        self.assertFalse(report["dequant_consumer_section_present"])

    def test_foreign_consumer_section_injection_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        corrupted["owner_sections"]["DequantizeLinear"] = {"owner_node": "node-0072"}
        self._validate_corrupted(corrupted)

    def test_storage_or_base_drift_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["storage_identity"]["storage_id"] = "wrong-storage"
        self._validate_corrupted(corrupted)

        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["coverage"]["slice_records"][15]["physical_d_base_addr"] = (
            "0x1e0a2010"
        )
        self._validate_corrupted(corrupted)

    def test_coverage_or_offset_drift_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["coverage"]["slice_records"][15]["valid_logical_bytes"] = 2016
        self._validate_corrupted(corrupted)

        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["consumer_match_requirements"]["required_view_byte_offset"] = 32
        self._validate_corrupted(corrupted)

    def test_integrated_visibility_or_completion_overclaim_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["visibility_and_lifetime"][
            "shared_multi_operator_barrier_materialized"
        ] = True
        self._validate_corrupted(corrupted)

        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["QLinearGlobalAveragePool"]
        section["final_accepted_write_completion"][
            "integrated_node0071_to_node0072_completion_accepted"
        ] = True
        self._validate_corrupted(corrupted)

    def test_existing_package_is_frozen_not_rebuilt(self) -> None:
        section = self.manifest["owner_sections"]["QLinearGlobalAveragePool"]
        package = section["frozen_complete_e2_identity"]["existing_package"]
        self.assertEqual(
            package["sha256"],
            "bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74",
        )
        self.assertEqual(package["status"], "PACKAGE_READY_NOT_RUN")
        self.assertFalse(package["rebuilt_or_modified_by_this_task"])
        self.assertEqual(
            package["dynamic_return_status"],
            "COMPILE_FAILED_NO_DYNAMIC_GAP_EVIDENCE",
        )
        replacement = section["frozen_complete_e2_identity"][
            "replacement_candidate_package"
        ]
        self.assertEqual(replacement["identity"], "r5_n71_gap_v2_obs")
        self.assertEqual(replacement["status"], "PACKAGE_READY_NOT_RUN")
        self.assertTrue(
            replacement["source_numeric_payload_reused_without_rebuild"]
        )


if __name__ == "__main__":
    unittest.main()
