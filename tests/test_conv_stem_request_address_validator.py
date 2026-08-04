from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from resnet50_pipeline import conv_stem_request_address_validator as validator
from resnet50_pipeline.conv_stem_request_address_validator import (
    StemRequestAddressError,
    _ordered_unmapped_requests,
    _remap_words,
    validate_stem_request_addresses,
)


ROOT = Path(__file__).resolve().parents[1]


class ConvStemRequestAddressValidatorTest(unittest.TestCase):
    def test_exact_final_native_request_chain(self) -> None:
        report = validate_stem_request_addresses(ROOT)
        self.assertTrue(report["valid"])
        facts = report["facts"]
        self.assertEqual(facts["request_count_with_multiplicity"], 33_354_752)
        self.assertEqual(facts["unique_request_address_count"], 32_953_600)
        self.assertEqual(facts["sca_exact_entry_count"], 1027)
        self.assertEqual(facts["sca_tensor_entry_count"], 1024)
        self.assertEqual(facts["nonbase_leaf_diff_count"], 0)
        self.assertEqual(facts["maximum_data_row"], 6033)
        self.assertTrue(facts["typed_output_byte_conservation"])
        self.assertFalse(report["validation_method"]["sampling"])

    def test_all_stream_patterns_are_exact_not_sampled(self) -> None:
        expected = {
            "A": (592, 296, 592),
            "B": (464_128, 232_064, 464_128),
            "C": (6_272, 3_136, 4),
            "D": (50_176, 25_088, 50_176),
        }
        for target, (requests, tuples, unique) in expected.items():
            unmapped, tuple_count = _ordered_unmapped_requests(target)
            self.assertEqual(unmapped.size, requests)
            self.assertEqual(tuple_count, tuples)
            self.assertEqual(len(set(_remap_words(unmapped).tolist())), unique)

    def test_nonbase_change_fails_closed(self) -> None:
        original_load = validator._load

        def drift(path):
            value = original_load(path)
            if path.parent.name == "jsons" and "stem_serialized_w0_" in path.name:
                value["stream_engine"]["stream1"]["dim_stride"][1] += 1
            return value

        with mock.patch(
            "resnet50_pipeline.conv_stem_request_address_validator._load",
            side_effect=drift,
        ):
            with self.assertRaises(StemRequestAddressError):
                validate_stem_request_addresses(ROOT)


if __name__ == "__main__":
    unittest.main()
