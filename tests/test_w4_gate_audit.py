from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.w4_audit import (
    CURRENT_TARGET_REQUIRED_LAYOUT_FAMILIES,
    _current_target_evidence_status,
    audit_w4_gate,
)
from resnet50_pipeline.hashing import sha256_file
from tests.hardware_approval_fixture import valid_hardware_approval


class W4GateAuditTests(unittest.TestCase):
    def test_full_coverage_transitions_and_expected_external_block(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = audit_w4_gate(root)
        self.assertEqual(report["target_family"], "rtl28")
        self.assertEqual(report["slice_count"], 28)
        self.assertEqual(
            report["architecture_sha256"],
            sha256_file(root / "contracts/architecture.json"),
        )
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
            report["gate_decision"]["software_candidate_readiness"], "fail"
        )
        self.assertEqual(report["candidate_layouts"]["count"], 12)
        self.assertEqual(
            report["current_target_evidence"]["layout_evidence_families"],
            ["conv", "global_average_pool", "matmul", "maxpool", "simple", "view"],
        )
        current_interfaces = [
            item
            for item in report["plugin_interfaces"]
            if item["target_family"] == "rtl28"
        ]
        self.assertEqual(len(current_interfaces), 14)
        self.assertTrue(all(item["interface_complete"] for item in current_interfaces))
        self.assertFalse(
            report["current_target_evidence"]["registered_layout_evidence_complete"]
        )
        self.assertTrue(
            report["legacy16_evidence"]["criteria"][
                "all_93_edges_physically_verified"
            ]
        )
        self.assertTrue(
            report["legacy16_evidence"]["criteria"][
                "both_profile_dry_runs_fit_candidate_capacity"
            ]
        )
        self.assertTrue(
            report["legacy16_evidence"]["criteria"][
                "candidate_lifetimes_and_aliases_conflict_free"
            ]
        )
        self.assertTrue(report["gate_criteria"]["logical_result_comparator_ready"])
        self.assertTrue(report["logical_result_comparator"]["interface_ready"])
        self.assertFalse(
            report["logical_result_comparator"]["hardware_results_available"]
        )
        self.assertEqual(report["gate_decision"]["g4_status"], "not_passed")
        self.assertFalse(report["gate_decision"]["w5_authorized"])
        self.assertEqual(report["gate_decision"]["legacy16_software_evidence"], "pass")
        self.assertFalse(report["legacy16_evidence"]["current_gate_eligible"])
        self.assertTrue(
            {
                "target28_operator_layout_evidence_complete",
                "target28_all_93_edges_physically_verified",
                "target28_profile_cost_evidence_complete",
                "target28_clean_elaboration_approved",
                "approved_target_profile_exists",
                "target_rtl_isa_register_map_version_frozen",
                "approved_physical_layout_contract_exists",
            }.issubset(report["gate_decision"]["blocking_criteria"])
        )

    def test_valid_rtl28_hardware_approval_fixture_is_structure_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "hardware_approval.json"
            approval_path.write_text(
                json.dumps(valid_hardware_approval()), encoding="utf-8"
            )
            report = audit_w4_gate(root, approval_path)
        self.assertTrue(report["hardware_approval"]["valid"])
        self.assertEqual(report["hardware_approval"]["validation_scope"], "structure_only")
        self.assertFalse(report["hardware_approval"]["gate_authority_eligible"])
        self.assertFalse(report["hardware_approval"]["current_gate_eligible"])
        self.assertIn(
            "hardware_approval_not_gate_authority_eligible",
            report["hardware_approval"]["current_gate_eligibility_reasons"],
        )
        self.assertIn(
            "target28_operator_layout_evidence_incomplete",
            report["hardware_approval"]["current_gate_eligibility_reasons"],
        )
        self.assertTrue(
            report["current_target_evidence"]["clean_elaboration_approved"]
        )
        self.assertEqual(report["gate_decision"]["g4_status"], "not_passed")
        self.assertFalse(report["gate_decision"]["w5_authorized"])
        self.assertIn(
            "approved_target_profile_exists",
            report["gate_decision"]["blocking_criteria"],
        )

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

    def test_unapproved_layout_registry_cannot_bypass_profile_layout_evidence(self) -> None:
        architecture = {
            "target": {"slice_count": 28},
            "candidate_layouts": {
                f"synthetic_{family}": {
                    "target_family": "rtl28",
                    "slice_count": 28,
                    "operator_family": family,
                    "status": "candidate",
                    "current_gate_eligible": True,
                }
                for family in CURRENT_TARGET_REQUIRED_LAYOUT_FAMILIES
            },
            "candidate_evidence": {
                "edges": {
                    "target_family": "rtl28",
                    "slice_count": 28,
                    "current_gate_eligible": True,
                    "evidence_kind": "network_physical_edge_audit",
                    "edge_count": 93,
                },
                "cost": {
                    "target_family": "rtl28",
                    "slice_count": 28,
                    "current_gate_eligible": True,
                    "evidence_kind": "network_profile_cost",
                },
            },
        }
        approval = {
            "valid": True,
            "clean_elaboration_approved": True,
            "layout_evidence_complete": False,
        }
        status = _current_target_evidence_status(architecture, approval)
        self.assertTrue(status["registered_layout_evidence_complete"])
        self.assertFalse(status["approved_profile_layouts_complete"])
        self.assertFalse(status["layout_evidence_complete"])
        self.assertFalse(status["hardware_approval_current_gate_eligible"])


if __name__ == "__main__":
    unittest.main()
