from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.w4_audit import audit_w4_gate


class W4GateAuditTests(unittest.TestCase):
    def test_full_coverage_transitions_and_expected_external_block(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = audit_w4_gate(root)
        self.assertEqual(report["node_coverage"]["formal_node_count"], 78)
        self.assertTrue(report["node_coverage"]["all_formal_nodes_covered"])
        self.assertEqual(report["transition_audit"]["runtime_tensor_edge_count"], 93)
        self.assertTrue(
            report["transition_audit"]["all_responsibilities_explicit"]
        )
        self.assertTrue(
            report["transition_audit"]["all_quantized_qparam_identities_exact"]
        )
        self.assertTrue(
            all(
                item["sha256_match"] and item["size_match"]
                for item in report["evidence_artifacts"].values()
            )
        )
        self.assertEqual(
            report["gate_decision"]["software_candidate_readiness"], "pass"
        )
        self.assertEqual(report["gate_decision"]["g4_status"], "not_passed")
        self.assertFalse(report["gate_decision"]["w5_authorized"])
        self.assertEqual(
            set(report["gate_decision"]["blocking_criteria"]),
            {
                "approved_target_profile_exists",
                "target_rtl_isa_register_map_version_frozen",
                "approved_physical_layout_contract_exists",
            },
        )


if __name__ == "__main__":
    unittest.main()
