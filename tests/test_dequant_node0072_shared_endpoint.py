from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from resnet50_pipeline.dequant_node0072_shared_endpoint import (
    MANIFEST_RELATIVE,
    DequantSharedEndpointError,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class DequantNode0072SharedEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / MANIFEST_RELATIVE).read_text(encoding="utf-8")
        )

    def test_frozen_dequant_owner_section_validates(self) -> None:
        report = validate_manifest(ROOT)
        self.assertTrue(report["valid"])
        self.assertEqual(report["logical_valid_bytes"], 131072)
        self.assertEqual(report["physical_written_bytes"], 132608)
        self.assertEqual(report["physical_padding_bytes"], 1536)
        self.assertTrue(report["same_storage_id_frozen"])
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["operator_e2_retested"])

    def test_only_dequant_owner_section_is_written(self) -> None:
        self.assertEqual(
            set(self.manifest["owner_sections"]), {"DequantizeLinear"}
        )
        self.assertEqual(
            self.manifest["required_missing_owner_sections"],
            ["Flatten_View", "QuantizeLinear"],
        )
        self.assertFalse(self.manifest["integrated_endpoint_closed"])

    def test_storage_identity_drift_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        corrupted["owner_sections"]["DequantizeLinear"]["storage_identity"][
            "storage_id"
        ] = "wrong-storage"
        with patch(
            "resnet50_pipeline.dequant_node0072_shared_endpoint._read_json",
            return_value=corrupted,
        ):
            with self.assertRaises(DequantSharedEndpointError):
                validate_manifest(ROOT)

    def test_slice_base_drift_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        corrupted["owner_sections"]["DequantizeLinear"]["coverage"][
            "slice_records"
        ][27]["physical_d_base_addr"] = "0x360004b0"
        with patch(
            "resnet50_pipeline.dequant_node0072_shared_endpoint._read_json",
            return_value=corrupted,
        ):
            with self.assertRaises(DequantSharedEndpointError):
                validate_manifest(ROOT)

    def test_padding_or_valid_coverage_drift_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        corrupted["owner_sections"]["DequantizeLinear"]["coverage"][
            "slice_records"
        ][27]["valid_logical_bytes"] = 4736
        corrupted["owner_sections"]["DequantizeLinear"]["coverage"][
            "slice_records"
        ][27]["physical_padding_bytes"] = 0
        with patch(
            "resnet50_pipeline.dequant_node0072_shared_endpoint._read_json",
            return_value=corrupted,
        ):
            with self.assertRaises(DequantSharedEndpointError):
                validate_manifest(ROOT)

    def test_integrated_or_dynamic_overclaim_fails_closed(self) -> None:
        corrupted = deepcopy(self.manifest)
        section = corrupted["owner_sections"]["DequantizeLinear"]
        section["final_accepted_write_completion"][
            "dynamic_hardware_final_write_accepted"
        ] = True
        with patch(
            "resnet50_pipeline.dequant_node0072_shared_endpoint._read_json",
            return_value=corrupted,
        ):
            with self.assertRaises(DequantSharedEndpointError):
                validate_manifest(ROOT)


if __name__ == "__main__":
    unittest.main()
