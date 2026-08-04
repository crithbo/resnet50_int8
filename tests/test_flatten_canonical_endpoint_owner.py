from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from resnet50_pipeline.flatten_canonical_endpoint_owner import (
    CANONICAL_RELATIVE,
    DEQUANT_SECTION_SHA256,
    QUANTIZE_SECTION_SHA256,
    FlattenCanonicalOwnerError,
    _owner_section_sha256,
    validate_canonical_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class FlattenCanonicalEndpointOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / CANONICAL_RELATIVE).read_text(encoding="utf-8")
        )

    def _validate_mutation(self, mutation: dict) -> None:
        with patch(
            "resnet50_pipeline.flatten_canonical_endpoint_owner._read_json",
            side_effect=lambda path: (
                mutation
                if path.resolve() == (ROOT / CANONICAL_RELATIVE).resolve()
                else json.loads(path.read_text(encoding="utf-8"))
            ),
        ):
            validate_canonical_manifest(ROOT)

    def test_three_sections_present_but_endpoint_stays_blocked(self) -> None:
        report = validate_canonical_manifest(ROOT)
        self.assertTrue(report["valid"])
        self.assertEqual(
            report["owner_sections_present"],
            ["DequantizeLinear", "Flatten_View", "QuantizeLinear"],
        )
        self.assertEqual(report["required_missing_owner_sections"], [])
        self.assertEqual(report["quantize_exact_division"], "OPEN")
        self.assertEqual(report["consumer_final_endpoint_null_field_count"], 6)
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["element_address_mapping_retested"])
        self.assertFalse(report["integrated_target_local_e2"])

    def test_dequant_section_identity_is_unchanged(self) -> None:
        section = self.manifest["owner_sections"]["DequantizeLinear"]
        self.assertEqual(
            section["owner_section_content_sha256"], DEQUANT_SECTION_SHA256
        )
        self.assertEqual(_owner_section_sha256(section), DEQUANT_SECTION_SHA256)
        quantize = self.manifest["owner_sections"]["QuantizeLinear"]
        self.assertEqual(
            quantize["owner_section_content_sha256"], QUANTIZE_SECTION_SHA256
        )
        self.assertEqual(_owner_section_sha256(quantize), QUANTIZE_SECTION_SHA256)

    def test_copy_or_allocation_promotion_fails_closed(self) -> None:
        corrupted = copy.deepcopy(self.manifest)
        view = corrupted["owner_sections"]["Flatten_View"]
        view["materialization"]["copy_enabled"] = True
        view["allocation_ownership"]["view_may_allocate"] = True
        view["owner_section_content_sha256"] = _owner_section_sha256(view)
        with self.assertRaisesRegex(FlattenCanonicalOwnerError, "copy must"):
            self._validate_mutation(corrupted)

    def test_quantize_or_integrated_gate_fabrication_fails_closed(self) -> None:
        corrupted = copy.deepcopy(self.manifest)
        corrupted["owner_sections"]["QuantizeLinear"][
            "consumer_owned_endpoint_fields"
        ]["final_consumer_base"] = "0x000004a0"
        corrupted["integrated_endpoint_closed"] = True
        with self.assertRaises(FlattenCanonicalOwnerError):
            self._validate_mutation(corrupted)

    def test_dequant_owner_mutation_fails_before_view_validation(self) -> None:
        corrupted = copy.deepcopy(self.manifest)
        corrupted["owner_sections"]["DequantizeLinear"]["storage_identity"][
            "byte_offset_within_allocation"
        ] = 4
        with self.assertRaisesRegex(FlattenCanonicalOwnerError, "Dequant section"):
            self._validate_mutation(corrupted)


if __name__ == "__main__":
    unittest.main()
