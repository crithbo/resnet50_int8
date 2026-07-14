from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.network28_audit import (
    GLOBAL_HEAD_SCENARIO,
    GROUP_ONLY_SCENARIO,
    audit_network28_candidates,
    cost_evidence,
    edge_evidence,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from tools.audit_w4_network28_candidates import build_evidence, evidence_records


ROOT = Path(__file__).resolve().parents[1]


class Network28AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (ROOT / "artifacts/w3/model_graph.json").read_text(encoding="utf-8")
        )
        cls.report = audit_network28_candidates(cls.catalog)

    def test_both_scenarios_cover_the_frozen_graph_and_pass(self) -> None:
        self.assertEqual(self.report["formal_node_count"], 78)
        self.assertEqual(self.report["formal_runtime_edge_count"], 93)
        self.assertEqual(
            set(self.report["scenarios"]),
            {GROUP_ONLY_SCENARIO, GLOBAL_HEAD_SCENARIO},
        )
        self.assertTrue(self.report["all_scenarios_pass"])
        for scenario in self.report["scenarios"].values():
            transition = scenario["transition_audit"]
            self.assertEqual(transition["edge_count"], 93)
            self.assertEqual(transition["qparam_edge_count"], 91)
            self.assertEqual(transition["residual_add_count"], 16)
            self.assertTrue(transition["all_qparam_identities_exact"])
            self.assertTrue(transition["all_residual_adds_compatible"])
            self.assertTrue(transition["all_edge_policies_verified"])

    def test_only_global_head_schedule_has_one_explicit_relayout(self) -> None:
        group = self.report["scenarios"][GROUP_ONLY_SCENARIO]["transition_audit"]
        head = self.report["scenarios"][GLOBAL_HEAD_SCENARIO]["transition_audit"]
        self.assertEqual(group["profile_transition_edge_count"], 0)
        self.assertNotIn("explicit_profile_relayout", group["classification_counts"])
        transitions = [edge for edge in head["edges"] if edge["profile_transition"]]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(
            (transitions[0]["producer_op_type"], transitions[0]["consumer_op_type"]),
            ("QuantizeLinear", "QLinearMatMul"),
        )
        self.assertEqual(transitions[0]["classification"], "explicit_profile_relayout")
        self.assertFalse(transitions[0]["physical_signatures_equal"])
        self.assertNotIn(
            "QLinearAdd",
            {transitions[0]["producer_op_type"], transitions[0]["consumer_op_type"]},
        )

    def test_physical_signatures_have_all_28_explicit_slice_regions(self) -> None:
        for scenario in self.report["scenarios"].values():
            transition = scenario["transition_audit"]
            self.assertEqual(len(transition["graph_input_signatures"]), 1)
            self.assertEqual(len(transition["terminal_output_signatures"]), 1)
            for signature in transition["signature_catalog"].values():
                regions = signature["slice_regions"]
                self.assertEqual([item["slice_id"] for item in regions], list(range(28)))
                self.assertEqual(signature["alignment_bytes"], 16)
                self.assertEqual(signature["byte_order"], "little")
                self.assertEqual(
                    signature["aligned_bytes_per_slice"] % signature["alignment_bytes"],
                    0,
                )

    def test_all_runtime_lifetimes_and_residual_aliases_are_conflict_free(self) -> None:
        for scenario in self.report["scenarios"].values():
            memory = scenario["memory_lifecycle"]
            self.assertEqual(memory["runtime_tensor_count"], 79)
            self.assertEqual(len(memory["alias_edge_checks"]), 93)
            self.assertEqual(len(memory["residual_branch_checks"]), 16)
            self.assertTrue(memory["all_allocations_fit"])
            self.assertTrue(memory["all_lifetime_overlaps_address_disjoint"])
            self.assertTrue(memory["all_alias_actions_conflict_free"])
            self.assertTrue(
                memory["all_residual_branches_distinct_live_and_disjoint"]
            )
            self.assertEqual(memory["overlap_conflicts"], [])

    def test_static_costs_distinguish_group_only_and_global_head(self) -> None:
        group = self.report["scenarios"][GROUP_ONLY_SCENARIO]["dry_run_cost"]
        head = self.report["scenarios"][GLOBAL_HEAD_SCENARIO]["dry_run_cost"]
        self.assertEqual(group["node_count"], 78)
        self.assertEqual(
            group["profile_node_counts"],
            {GROUP4X7_BATCH_CHANNEL28_PROFILE: 78},
        )
        self.assertEqual(
            head["profile_node_counts"],
            {GLOBAL_RING28_PROFILE: 3, GROUP4X7_BATCH_CHANNEL28_PROFILE: 75},
        )
        self.assertEqual(group["explicit_profile_relayout_read_write_bytes"], 0)
        self.assertGreater(head["explicit_profile_relayout_read_write_bytes"], 0)
        self.assertEqual(group["group_barrier_shape"]["three_sample_group_count"], 2)
        self.assertEqual(group["group_barrier_shape"]["two_sample_group_count"], 5)
        self.assertEqual(
            group["group_barrier_shape"]["inactive_storage_slots_per_barrier_wave"],
            5,
        )
        self.assertTrue(group["all_standalone_node_plans_fit"])
        self.assertTrue(head["all_standalone_node_plans_fit"])

    def test_split_evidence_preserves_non_claims_and_gate_boundaries(self) -> None:
        edge = edge_evidence(self.report)
        cost = cost_evidence(self.report)
        self.assertEqual(edge["evidence_kind"], "network_physical_edge_audit")
        self.assertEqual(cost["evidence_kind"], "network_profile_cost")
        self.assertEqual(edge["edge_count"], 93)
        self.assertEqual(edge["qparam_edge_count"], 91)
        self.assertEqual(edge["residual_add_count"], 16)
        self.assertEqual(cost["scenario_count"], 2)
        for evidence in (edge, cost):
            self.assertEqual(evidence["status"], "candidate_software_evidence")
            self.assertTrue(evidence["current_gate_eligible"])
            self.assertFalse(evidence["hardware_approval"])
            self.assertFalse(evidence["g4_passed"])
            self.assertFalse(evidence["w5_authorized"])
            self.assertTrue(evidence["all_scenarios_pass"])

    def test_graph_shape_and_edge_count_are_fail_closed(self) -> None:
        missing_node = copy.deepcopy(self.catalog)
        missing_node["nodes"].pop()
        with self.assertRaisesRegex(ValueError, "78-node"):
            audit_network28_candidates(missing_node)
        missing_edge = copy.deepcopy(self.catalog)
        tensor = next(
            item
            for item in missing_edge["tensors"]
            if item["producer_node_id"] is not None and item["consumer_node_ids"]
        )
        tensor["consumer_node_ids"].pop()
        with self.assertRaisesRegex(ValueError, "93 runtime edges"):
            audit_network28_candidates(missing_edge)

    def test_content_addressed_evidence_manifest_is_deterministic(self) -> None:
        first = build_evidence(ROOT)
        second = build_evidence(ROOT)
        self.assertEqual(
            evidence_records(ROOT, first), evidence_records(ROOT, second)
        )
        for record in evidence_records(ROOT, first).values():
            self.assertTrue(record["path"].startswith("artifacts/w4/rtl28/"))
            self.assertIn(record["architecture_basis_sha256"], record["path"])
            self.assertTrue(record["all_scenarios_pass"])
            self.assertFalse(record["hardware_approval"])
            self.assertFalse(record["g4_passed"])
            self.assertFalse(record["w5_authorized"])


if __name__ == "__main__":
    unittest.main()
