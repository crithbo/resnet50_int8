from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.exact_uint8_quant_tail_capability import (
    one_round_fused_magic,
    oracle_bias_patch,
    proposed_subtract_patch,
    quantize_division_tail,
    sequential_multiplier_tail,
    validate_capability_contract,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json"


class ExactUint8QuantTailCapabilityTests(unittest.TestCase):
    def test_contract_and_source_identities(self) -> None:
        report = validate_capability_contract(CONTRACT, ROOT)
        self.assertEqual(
            report["status"], "PASS_PROPOSAL_VALID_NO_UNCONDITIONAL_PURE_CONFIG"
        )
        self.assertEqual(report["capability_cell_count"], 12)
        self.assertEqual(report["counterexample_count"], 5)
        self.assertEqual(report["read_receipt_count"], 4)
        self.assertEqual(report["final_refresh_receipt_count"], 2)
        self.assertEqual(report["semantic_source_identity_count"], 14)
        plan_receipt = next(
            item for item in report["read_receipts"] if item["path"] == ".agents/plan.md"
        )
        self.assertEqual(
            plan_receipt["recorded_sha256"],
            "697b1b5de15a713d7731dfea20d497e80f12852e08755d5fcd1b251eb616256e",
        )
        self.assertEqual(plan_receipt["gate"], "historical_provenance_only")
        self.assertFalse(plan_receipt["current_match"])
        self.assertTrue(
            all(
                item["gate"] == "current_match_fail_closed" and item["matched"]
                for item in report["semantic_source_identities"]
            )
        )
        final_plan = next(
            item
            for item in report["final_refresh_receipts"]
            if item["path"] == ".agents/plan.md"
        )
        self.assertEqual(
            final_plan["recorded_sha256"],
            "a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516",
        )
        self.assertEqual(
            final_plan["gate"], "final_validation_snapshot_provenance_only"
        )
        published_rule = next(
            item
            for item in report["semantic_source_identities"]
            if item["path"] == ".agents/rules/精确UINT8量化尾专项规则.md"
        )
        self.assertEqual(
            published_rule["sha256"],
            "5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0",
        )
        bypass_rule = next(
            item
            for item in report["semantic_source_identities"]
            if item["path"] == ".agents/rules/算子配置规则.md"
        )
        self.assertEqual(
            bypass_rule["sha256"],
            "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc",
        )

    def test_odd_zero_point_must_be_added_after_rounding(self) -> None:
        self.assertEqual(oracle_bias_patch(0.5, 1), 2)
        self.assertEqual(proposed_subtract_patch(0.5, 1), 1)
        self.assertEqual(proposed_subtract_patch(-0.5, 1), 1)

    def test_fma_contraction_changes_required_rounding_point(self) -> None:
        multiplier = np.asarray(0x3D828F5C, dtype=np.uint32).view(np.float32)
        value = np.float32(400)
        self.assertEqual(sequential_multiplier_tail(value, multiplier, 0), 26)
        self.assertEqual(one_round_fused_magic(value, multiplier, 0), 25)

    def test_quantize_division_is_not_reciprocal_fma(self) -> None:
        x = np.asarray(0x3D0F81F1, dtype=np.uint32).view(np.float32)
        scale = np.asarray(0x3CBF57EC, dtype=np.uint32).view(np.float32)
        reciprocal = np.asarray(0x422B4095, dtype=np.uint32).view(np.float32)
        self.assertEqual(quantize_division_tail(x, scale, 0), 2)
        self.assertEqual(one_round_fused_magic(x, reciprocal, 0), 1)

    def test_magic_domain_requires_bound(self) -> None:
        self.assertEqual(proposed_subtract_patch(-12582913.0, 0), 255)


if __name__ == "__main__":
    unittest.main()
