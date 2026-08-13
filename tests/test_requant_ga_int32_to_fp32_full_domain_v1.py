import json
import unittest
from pathlib import Path

from tools.prove_requant_ga_int32_to_fp32_full_domain_v1 import (
    REPORT,
    ieee_int32_to_binary32,
    rtl_current_model,
    rtl_historical_model,
)


class RequantGaInt32ToFp32FullDomainTests(unittest.TestCase):
    def test_required_current_source_vectors(self) -> None:
        cases = {
            0x00000000: 0x00000000,
            0xFFFFFFFF: 0xBF800000,
            0x80000000: 0xCF000000,
            0x7FFFFFFF: 0x4F000000,
            0x01000001: 0x4B800000,
            0x01000003: 0x4B800002,
            0xFEFFFFFF: 0xCB800000,
            0xFEFFFFFD: 0xCB800002,
            0x01FFFFFF: 0x4C000000,
            0xFE000001: 0xCC000000,
        }
        for input_bits, expected in cases.items():
            with self.subTest(input_bits=f"0x{input_bits:08x}"):
                self.assertEqual(rtl_current_model(input_bits), expected)
                self.assertEqual(ieee_int32_to_binary32(input_bits), expected)

    def test_historical_counterexamples_are_source_identity_specific(self) -> None:
        self.assertEqual(rtl_historical_model(0xFFFFFFFF), 0xCF000000)
        self.assertEqual(rtl_historical_model(0x80000000), 0xCE800000)
        self.assertEqual(rtl_current_model(0xFFFFFFFF), 0xBF800000)
        self.assertEqual(rtl_current_model(0x80000000), 0xCF000000)

    def test_machine_report_is_full_domain_and_fail_closed_on_composite(self) -> None:
        report = json.loads(Path(REPORT).read_text(encoding="utf-8"))
        self.assertEqual(
            report["status"],
            "LIVE_GA_INT32_TO_FP32_FULL_DOMAIN_BIT_EXACT_PROVEN",
        )
        proof = report["full_domain_proof"]
        self.assertTrue(proof["pass"])
        self.assertEqual(proof["covered_input_count"], 1 << 32)
        self.assertEqual(proof["mismatch_count"], 0)
        self.assertTrue(report["focused_live_rtl_witness_simulation"]["pass"])
        self.assertEqual(
            report["focused_live_rtl_witness_simulation"]["case_count"], 15
        )
        capability = report["capability_adjudication"]
        self.assertEqual(
            capability[
                "current_live_primitive_signed_int32_to_fp32_numeric_semantics"
            ],
            "FULL_DOMAIN_BIT_EXACT_PROVEN",
        )
        self.assertEqual(capability["family_wide_slow_composite"], "NOT_YET_PROVEN")
        self.assertFalse(capability["capability_elevation"])
        self.assertFalse(capability["strict_json_allowed"])

    def test_magic_and_one_round_counterexamples_remain_present(self) -> None:
        report = json.loads(Path(REPORT).read_text(encoding="utf-8"))
        counterexamples = {
            item["id"]: item
            for item in report["shared_tail_counterexamples_preserved"]
        }
        self.assertEqual(
            counterexamples["SEQUENTIAL_MULTIPLY_RNE_VS_ONE_ROUND_FMA"][
                "sequential_result"
            ],
            26,
        )
        self.assertEqual(
            counterexamples["SEQUENTIAL_MULTIPLY_RNE_VS_ONE_ROUND_FMA"][
                "one_round_fused_result"
            ],
            25,
        )
        self.assertEqual(
            counterexamples["MAGIC_WRAP"]["magic_decode_then_saturate_uint8"],
            255,
        )
        self.assertEqual(counterexamples["MAGIC_WRAP"]["expected_uint8"], 0)


if __name__ == "__main__":
    unittest.main()
