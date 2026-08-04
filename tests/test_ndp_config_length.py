from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.ndp_config_length import (
    NdpConfigLengthError,
    analyze_config_length,
    parse_load_config_length,
)


class NdpConfigLengthTests(unittest.TestCase):
    def test_odd_64bit_stream_requires_one_transport_padding_half(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path64 = root / "config_64b.bin"
            path128 = root / "config_128b.bin"
            path64.write_text(
                ("1" * 64) + "\n"
                + ("0" * 64) + "\n"
                + ("1" * 64) + "\n",
                encoding="ascii",
            )
            path128.write_text(
                ("0" * 64) + ("1" * 64) + "\n"
                + ("0" * 64) + ("1" * 64) + "\n",
                encoding="ascii",
            )
            accepted = analyze_config_length(path64, path128, 3)
            rejected = analyze_config_length(path64, path128, 4)
        self.assertEqual(
            accepted["padding_classification"],
            "ODD_ONE_TRANSPORT_PADDING_HALF",
        )
        self.assertEqual(
            accepted["rtl_meaningful_64bit_word_count"], 3
        )
        self.assertTrue(accepted["matches_rtl_padding_contract"])
        self.assertFalse(rejected["matches_rtl_padding_contract"])

    def test_even_zero_high_half_is_a_meaningful_source_word(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path64 = root / "config_64b.bin"
            path128 = root / "config_128b.bin"
            path64.write_text(
                ("1" * 64) + "\n" + ("0" * 64) + "\n",
                encoding="ascii",
            )
            path128.write_text(
                ("0" * 64) + ("1" * 64) + "\n",
                encoding="ascii",
            )
            result = analyze_config_length(path64, path128, 2)
        self.assertEqual(
            result["padding_classification"],
            "EVEN_NO_TRANSPORT_PADDING_HALF",
        )
        self.assertTrue(result["matches_rtl_padding_contract"])

    def test_mismatched_repacking_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path64 = root / "config_64b.bin"
            path128 = root / "config_128b.bin"
            path64.write_text("1" * 64 + "\n", encoding="ascii")
            path128.write_text("1" * 128 + "\n", encoding="ascii")
            with self.assertRaisesRegex(
                NdpConfigLengthError,
                "not the exact reordered packing",
            ):
                analyze_config_length(path64, path128, 1)

    def test_invalid_binary_width_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path64 = root / "config_64b.bin"
            path128 = root / "config_128b.bin"
            path64.write_text("0" * 63 + "\n", encoding="ascii")
            path128.write_text("0" * 128 + "\n", encoding="ascii")
            with self.assertRaisesRegex(
                NdpConfigLengthError,
                "64-bit binary rows",
            ):
                analyze_config_length(path64, path128, 1)

    def test_load_config_parser_requires_one_exact_operator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instructions.txt"
            path.write_text(
                "0001 <x> Load_Config for operator op0 (x): "
                "config_length_bin=00111011\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_load_config_length(path, "op0"), 59)
            with self.assertRaises(NdpConfigLengthError):
                parse_load_config_length(path, "op1")


if __name__ == "__main__":
    unittest.main()
