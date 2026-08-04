from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.gap_repair_release import (
    DEFAULT_OUTPUT_REL,
    RULE_D_COVERAGE,
    RULE_GA_CROSS_BLOCK,
    RULE_GA_INVALID_SLOT,
    RULE_GA_OCCUPANCY,
    build_gap_repair_release_gate,
    validate_gap_repair_release_gate,
)


ROOT = Path(__file__).resolve().parents[1]


class GapRepairReleaseTests(unittest.TestCase):
    def test_checked_gate_has_full_static_d_coverage_and_pending_dynamic_gates(
        self,
    ) -> None:
        path = ROOT / DEFAULT_OUTPUT_REL / "GAP_REPAIR_RELEASE_GATE.json"
        gate = json.loads(path.read_text(encoding="utf-8"))
        validate_gap_repair_release_gate(ROOT, gate)
        self.assertFalse(gate["candidate_release"])
        self.assertEqual(gate["evidence_level"], "E2_LOCAL_ONLY")
        self.assertEqual(
            len(gate["d_static_coverage"]["per_slice"]),
            16,
        )
        for item in gate["d_static_coverage"]["per_slice"]:
            self.assertEqual(item["transaction_base_count_32byte"], 256)
            self.assertEqual(item["request_count_128bit"], 512)
            self.assertEqual(item["unique_request_count_128bit"], 512)
            self.assertEqual(item["sca_d_length_128bit"], 512)
            self.assertEqual(item["golden_line_count_128bit"], 512)
            self.assertEqual(
                item["server_readback_golden_result"],
                "PENDING_SERVER_RETURN",
            )

    def test_all_required_gap_rules_are_explicit(self) -> None:
        gate = build_gap_repair_release_gate(ROOT)
        for rule_id in (
            RULE_D_COVERAGE,
            RULE_GA_OCCUPANCY,
            RULE_GA_INVALID_SLOT,
            RULE_GA_CROSS_BLOCK,
        ):
            self.assertIn(rule_id, gate["rule_ids"])
        self.assertTrue(gate["remaining_blockers"])


if __name__ == "__main__":
    unittest.main()
