from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_config_length_audit import (
    CONTRACT_PATH,
    DeepSeekConfigLengthAuditError,
    build_deepseek_config_length_audit,
    validate_deepseek_config_length_audit,
)


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekConfigLengthAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )

    def test_checked_contract_matches_current_evidence(self) -> None:
        rebuilt = build_deepseek_config_length_audit(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_deepseek_config_length_audit(self.checked, ROOT)

    def test_summary_and_family_partition_are_exact(self) -> None:
        summary = self.checked["summary"]
        self.assertEqual(summary["family_count"], 6)
        self.assertEqual(summary["operator_count"], 16)
        self.assertEqual(summary["closed_operator_count"], 16)
        self.assertEqual(summary["open_operator_count"], 0)
        self.assertEqual(
            summary["closed_families"],
            ["gemm", "gemv", "rmsnorm", "rope", "silu", "softmax"],
        )
        self.assertEqual(summary["open_families"], [])

    def test_closed_families_use_real_even_zero_words(self) -> None:
        silu = self.checked["families"]["silu"]["operators"]["op0"]
        gemv = self.checked["families"]["gemv"]["operators"]["op0"]
        self.assertEqual(silu["analysis"]["source_64bit_word_count"], 50)
        self.assertEqual(gemv["analysis"]["source_64bit_word_count"], 78)
        self.assertFalse(
            silu["analysis"]["last_row_high_half_is_transport_padding"]
        )
        self.assertFalse(
            gemv["analysis"]["last_row_high_half_is_transport_padding"]
        )
        self.assertTrue(silu["analysis"]["matches_rtl_padding_contract"])
        self.assertTrue(gemv["analysis"]["matches_rtl_padding_contract"])

    def test_previously_odd_families_use_64bit_source_lengths(self) -> None:
        families = self.checked["families"]
        expected_odd = {
            "rmsnorm": {"op0": 67, "op1": 49},
            "rope": {"op0": 61, "op1": 61, "op2": 61},
            "softmax": {
                "op0": 61,
                "op1": 49,
                "op2": 79,
                "op3": 67,
            },
            "gemm": {"op0": 59},
        }
        for family, operators in expected_odd.items():
            self.assertEqual(families[family]["open_operator_ids"], [])
            for op_id, expected_words in operators.items():
                op = families[family]["operators"][op_id]
                self.assertEqual(op["programmed_minus_source_words"], 0)
                self.assertEqual(
                    op["analysis"]["source_64bit_word_count"],
                    expected_words,
                )
                self.assertTrue(
                    op["analysis"][
                        "last_row_high_half_is_transport_padding"
                    ]
                )
                self.assertTrue(
                    op["analysis"]["matches_rtl_padding_contract"]
                )

    def test_contract_tamper_fails_closed(self) -> None:
        tampered = deepcopy(self.checked)
        tampered["summary"]["open_operator_count"] = 1
        with self.assertRaisesRegex(
            DeepSeekConfigLengthAuditError,
            "differs from current evidence",
        ):
            validate_deepseek_config_length_audit(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
