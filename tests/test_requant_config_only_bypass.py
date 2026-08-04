from __future__ import annotations

import copy
import unittest
from pathlib import Path

from resnet50_pipeline.requant_config_only_bypass import (
    ACTIVE_RULE_SHA256,
    BYPASS_FIELDS,
    RequantConfigOnlyBypassError,
    build_adjudication,
    validate_adjudication,
)


ROOT = Path(__file__).resolve().parents[1]


class RequantConfigOnlyBypassTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_adjudication(ROOT)

    def test_partition_is_exact_33_16_5(self) -> None:
        groups = self.value["groups"]
        self.assertEqual(groups["zp0_33"]["count"], 33)
        self.assertEqual(groups["even_nonzero_zp_16"]["count"], 16)
        self.assertEqual(groups["odd_nonzero_zp_5"]["count"], 5)

    def test_all_54_stages_are_w3_exact(self) -> None:
        members = [
            item
            for group in self.value["groups"].values()
            for item in group["members"]
        ]
        self.assertEqual(len(members), 54)
        self.assertTrue(all(item["w3_exact"] for item in members))

    def test_every_group_has_exact_seven_field_annotation(self) -> None:
        expected = set(BYPASS_FIELDS)
        for group in self.value["groups"].values():
            self.assertEqual(set(group["bypass_annotation"]), expected)

    def test_first_break_order(self) -> None:
        groups = self.value["groups"]
        self.assertEqual(
            groups["zp0_33"]["gate_state"][
                "first_non_bypassable_capability_break"
            ],
            "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
        )
        for name in ("even_nonzero_zp_16", "odd_nonzero_zp_5"):
            self.assertEqual(
                groups[name]["gate_state"][
                    "first_non_bypassable_capability_break"
                ],
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
            )

    def test_no_baseline_or_target_artifact_claim(self) -> None:
        boundary = self.value["materialization_boundary"]
        self.assertEqual(boundary["config_only_correctness_baseline_count"], 0)
        self.assertFalse(boundary["new_operator_json_generated"])
        self.assertFalse(boundary["mapping_generated"])
        self.assertFalse(boundary["candidate_release"])
        self.assertFalse(boundary["formal_target_instance_allowed"])
        for group in self.value["groups"].values():
            gate = group["gate_state"]
            self.assertEqual(
                gate["static_logical_to_materialized_leaf_diff"]["status"],
                "NOT_REACHED_NO_MATERIALIZED_JSON",
            )
            self.assertEqual(
                gate[
                    "formal_output_byte_coverage_from_final_occurrence_address_equations"
                ]["status"],
                "NOT_REACHED_NO_FINAL_OCCURRENCE_OR_ADDRESS_EQUATIONS",
            )
        dependency = self.value["shared_rounding_singleton_dependency"]
        self.assertEqual(
            dependency["status"], "CONSUMED_AS_DIAGNOSTIC_DEPENDENCY_ONLY"
        )
        self.assertEqual(dependency["sequential_uint8"], 26)
        self.assertEqual(dependency["fused_negative_control_uint8"], 25)
        self.assertFalse(dependency["requant_group_classification_changed"])
        self.assertFalse(dependency["requant_blocker_closed"])
        self.assertEqual(
            self.value["materialization_boundary"][
                "config_only_correctness_baseline_count"
            ],
            0,
        )

    def test_active_semantic_rule_receipts_are_exact(self) -> None:
        actual = {
            item["path"]: item["sha256"]
            for item in self.value["semantic_rule_receipts"]
        }
        self.assertEqual(actual, ACTIVE_RULE_SHA256)

    def test_validator_accepts_and_rejects_semantic_drift(self) -> None:
        report = validate_adjudication(ROOT, self.value)
        self.assertTrue(report["valid"])
        mutated = copy.deepcopy(self.value)
        mutated["groups"]["zp0_33"]["bypass_annotation"].pop("claim_boundary")
        with self.assertRaises(RequantConfigOnlyBypassError):
            validate_adjudication(ROOT, mutated)

    def test_eventedge_and_server_boundaries_are_frozen(self) -> None:
        boundary = self.value["materialization_boundary"]
        self.assertFalse(boundary["event_edge_packages_modified"])
        self.assertFalse(boundary["server_package_generated"])
        self.assertFalse(boundary["server_inspected_uploaded_or_run"])
        self.assertFalse(boundary["functional_rtl_modified"])


if __name__ == "__main__":
    unittest.main()
