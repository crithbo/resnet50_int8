from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.network_dry_run import audit_network_candidates


class NetworkCandidateDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads(
            (root / "artifacts/w3/model_graph.json").read_text(encoding="utf-8")
        )
        cls.report = audit_network_candidates(catalog)

    def test_all_93_edges_have_verified_physical_relations(self) -> None:
        expected = {
            "batch": {
                "exact_alias_proved": 4,
                "explicit_relayout": 1,
                "layout_compatible_rebase_w7": 87,
                "zero_copy_proved": 1,
            },
            "ring_channel": {
                "exact_alias_proved": 3,
                "explicit_relayout": 4,
                "layout_compatible_rebase_w7": 85,
                "zero_copy_proved": 1,
            },
        }
        for profile, counts in expected.items():
            audit = self.report["profiles"][profile]["transition_audit"]
            self.assertEqual(audit["edge_count"], 93)
            self.assertEqual(audit["classification_counts"], counts)
            self.assertTrue(audit["all_policy_relations_physically_verified"])
            self.assertTrue(audit["all_quantized_qparams_exact"])

    def test_both_profile_costs_cover_all_nodes_without_claiming_timing(self) -> None:
        batch = self.report["profiles"]["batch"]["dry_run_cost"]
        ring = self.report["profiles"]["ring_channel"]["dry_run_cost"]
        self.assertEqual(batch["node_count"], 78)
        self.assertEqual(ring["node_count"], 78)
        self.assertEqual(batch["estimated_ring_neighbor_bytes"], 0)
        self.assertGreater(ring["estimated_ring_neighbor_bytes"], 0)
        self.assertGreater(
            ring["explicit_relayout_read_write_bytes"],
            batch["explicit_relayout_read_write_bytes"],
        )
        self.assertTrue(batch["all_standalone_node_plans_fit"])
        self.assertTrue(ring["all_standalone_node_plans_fit"])
        self.assertTrue(self.report["non_claims"])

    def test_lifetimes_aliases_and_residual_branches_are_conflict_free(self) -> None:
        for profile, transition_count in (("batch", 1), ("ring_channel", 4)):
            memory = self.report["profiles"][profile]["memory_lifecycle"]
            self.assertEqual(memory["transition_buffer_count"], transition_count)
            self.assertEqual(len(memory["alias_edge_checks"]), 93)
            self.assertEqual(len(memory["residual_branch_checks"]), 16)
            self.assertTrue(memory["all_allocations_fit"])
            self.assertTrue(memory["all_lifetime_overlaps_address_disjoint"])
            self.assertTrue(memory["all_alias_actions_conflict_free"])
            self.assertTrue(memory["all_residual_branches_distinct_and_disjoint"])

    def test_report_is_deterministic(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads(
            (root / "artifacts/w3/model_graph.json").read_text(encoding="utf-8")
        )
        self.assertEqual(self.report, audit_network_candidates(catalog))


if __name__ == "__main__":
    unittest.main()
