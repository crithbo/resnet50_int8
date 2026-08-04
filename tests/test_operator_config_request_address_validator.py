from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_request_address_validator import (
    OperatorConfigRequestAddressValidator,
    _transfer_lane_indexes,
    enumerate_transfer_word_addresses,
    remap_word_address,
)


IDENTITY = list(range(26))


class OperatorConfigRequestAddressValidatorTests(unittest.TestCase):
    @staticmethod
    def _decode_bundle() -> Path:
        root = Path(__file__).resolve().parents[1]
        return (
            root
            / "artifacts"
            / "operator_config_validation"
            / "r3-execplan-evidence"
            / "decode_summac-seed42-v2"
        )

    def test_transfer_split_matches_128bit_request_words(self) -> None:
        self.assertEqual(
            enumerate_transfer_word_addresses(
                indexes=[0, 0, 0],
                strides=[1, 0, 0],
                transaction_size=20,
                base_addr=0,
                remapping=IDENTITY,
            ),
            [0, 1],
        )
        self.assertEqual(
            enumerate_transfer_word_addresses(
                indexes=[1, 0, 0],
                strides=[4, 0, 0],
                transaction_size=4,
                base_addr=0,
                remapping=IDENTITY,
            ),
            [0],
        )

    def test_remap_is_output_bit_to_input_bit_like_rtl(self) -> None:
        remap = list(range(26))
        remap[0], remap[1] = remap[1], remap[0]
        self.assertEqual(remap_word_address(0b01, remap), 0b10)
        self.assertEqual(remap_word_address(0b10, remap), 0b01)

    def test_remap_can_turn_legal_linear_offset_into_illegal_row(self) -> None:
        remap = list(range(26))
        remap[0], remap[17] = remap[17], remap[0]
        remap[1], remap[18] = remap[18], remap[1]
        word = enumerate_transfer_word_addresses(
            indexes=[3, 0, 0],
            strides=[16, 0, 0],
            transaction_size=16,
            base_addr=0,
            remapping=remap,
        )[0]
        byte_address = word << 4
        self.assertEqual((byte_address >> 10) & 0x1FFF, 6144)

    def test_transfer_lane_indexes_follow_rtl_packed_array_order(self) -> None:
        fields = {
            "idx_size": [7, 3, 0],
            "idx_size_log": [3, 5, 0],
        }
        self.assertEqual(
            _transfer_lane_indexes([12, 48, 0], 0, fields),
            (12, 48, 0),
        )
        self.assertEqual(
            _transfer_lane_indexes([12, 48, 0], 7, fields),
            (19, 48, 0),
        )
        self.assertEqual(
            _transfer_lane_indexes([12, 48, 0], 8, fields),
            (12, 49, 0),
        )
        self.assertEqual(
            _transfer_lane_indexes([12, 48, 0], 31, fields),
            (19, 51, 0),
        )

    def test_native_decode_bundle_replays_writes_and_fits_sca_regions(self) -> None:
        bundle = self._decode_bundle()
        graph_root = bundle / "pipeline_output"
        report = OperatorConfigRequestAddressValidator().validate(
            graph_root,
            graph_path=graph_root / "decode_summac_fp32N_fp32N_graph_withbaseaddr.json",
            source_configs={
                "op0": graph_root / "jsons" / "op0_decode_summac_fp32N_fp32N.json"
            },
        )
        self.assertTrue(report.valid, report.to_dict())
        self.assertEqual(report.facts["request_count_with_multiplicity"], 924)
        self.assertEqual(report.facts["unique_request_address_count"], 252)
        streams = report.facts["stages"][0]["streams"]
        self.assertEqual(len(streams), 56)
        a_slice27 = next(
            item
            for item in streams
            if item["resource"] == "READ_STREAM0" and item["execution_slice"] == 27
        )
        d_slice27 = next(
            item
            for item in streams
            if item["resource"] == "WRITE_STREAM0" and item["execution_slice"] == 27
        )
        self.assertEqual(a_slice27["base_addr"], "0x36000000")
        self.assertEqual(d_slice27["base_addr"], "0x36000080")
        self.assertTrue(all(request["region_hits"] for request in a_slice27["requests"]))
        self.assertTrue(all(request["region_hits"] for request in d_slice27["requests"]))

    def test_duplicate_explanation_index_is_rejected(self) -> None:
        bundle = self._decode_bundle()
        with tempfile.TemporaryDirectory() as temp_text:
            graph_root = Path(temp_text) / "pipeline_output"
            shutil.copytree(bundle / "pipeline_output", graph_root)
            explanation = graph_root / "instructions_explained.txt"
            lines = explanation.read_text(encoding="utf-8").splitlines()
            duplicate = next(line for line in lines if "<" in line and ">" in line)
            explanation.write_text("\n".join(lines + [duplicate]) + "\n", encoding="utf-8")
            report = OperatorConfigRequestAddressValidator().validate(
                graph_root,
                graph_path=graph_root / "decode_summac_fp32N_fp32N_graph_withbaseaddr.json",
                source_configs={
                    "op0": graph_root / "jsons" / "op0_decode_summac_fp32N_fp32N.json"
                },
            )
            self.assertFalse(report.valid)
            self.assertIn(
                "REQUEST.EXPLANATION_DUPLICATE",
                {issue.code for issue in report.issues},
            )


if __name__ == "__main__":
    unittest.main()
