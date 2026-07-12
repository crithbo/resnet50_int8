from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.w4_audit import audit_w4_gate
from tests.hardware_approval_fixture import valid_hardware_approval


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

    def test_valid_external_hardware_approval_opens_g4(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "hardware_approval.json"
            approval_path.write_text(
                json.dumps(valid_hardware_approval()), encoding="utf-8"
            )
            report = audit_w4_gate(root, approval_path)
        self.assertTrue(report["hardware_approval"]["valid"])
        self.assertEqual(report["gate_decision"]["g4_status"], "passed")
        self.assertTrue(report["gate_decision"]["w5_authorized"])
        self.assertEqual(report["gate_decision"]["blocking_criteria"], [])

    def test_invalid_external_hardware_approval_remains_blocked(self) -> None:
        root = Path(__file__).resolve().parents[1]
        approval = valid_hardware_approval()
        approval["target_version"]["rtl_commit"] = "not-a-real-version"
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "hardware_approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            report = audit_w4_gate(root, approval_path)
        self.assertTrue(report["hardware_approval"]["present"])
        self.assertFalse(report["hardware_approval"]["valid"])
        self.assertIn(
            "full lowercase Git hash",
            report["hardware_approval"]["validation_error"],
        )
        self.assertFalse(report["gate_decision"]["w5_authorized"])


if __name__ == "__main__":
    unittest.main()
