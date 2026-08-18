from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.validate_rule_maintenance_incident_adjudication import validate_document


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "rule_maintenance_incident_adjudication_v1.schema.json").read_text(
        encoding="utf-8"
    )
)
BASE = json.loads(
    (ROOT / "contracts" / "rule_maintenance_incident_adjudication_v1.json").read_text(
        encoding="utf-8"
    )
)


class IncidentAdjudicationTests(unittest.TestCase):
    def assert_valid(self, document: dict) -> None:
        self.assertEqual(validate_document(document, SCHEMA), [])

    def assert_invalid(self, document: dict, fragment: str) -> None:
        errors = validate_document(document, SCHEMA)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_reference_implementation_escape_is_valid(self) -> None:
        self.assert_valid(copy.deepcopy(BASE))

    def test_semantic_error_replaces_wrong_text(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "RULE_SEMANTIC_ERROR"
        item["current_rule_audit"]["semantic_coverage"] = "INCORRECT"
        item["current_rule_audit"]["implementation_coverage"] = "NOT_APPLICABLE"
        item["action"]["public_rule_change"] = "REPLACE_OR_NARROW"
        item["action"]["hard_gate_change"] = "NONE"
        item["action"]["replaced_or_removed_sections"] = ["wrong legacy semantics"]
        self.assert_valid(item)

    def test_semantic_omission_merges_in_unique_owner(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "RULE_SEMANTIC_OMISSION"
        item["current_rule_audit"]["semantic_coverage"] = "MISSING"
        item["current_rule_audit"]["implementation_coverage"] = "NOT_APPLICABLE"
        item["action"]["public_rule_change"] = "MERGE_OMISSION"
        item["action"]["hard_gate_change"] = "NONE"
        self.assert_valid(item)

    def test_session_issue_prefers_skill_without_new_gate(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "SESSION_EXECUTION_NONCOMPLIANCE"
        item["current_rule_audit"]["semantic_coverage"] = "COVERED"
        item["current_rule_audit"]["implementation_coverage"] = "PASS"
        item["action"]["hard_gate_change"] = "NONE"
        item["action"]["workflow_change"] = "SKILL_OR_HANDOFF"
        item["action"]["causal_blocking_classes"] = []
        item["action"]["affected_consumers"] = []
        item["positive_controls"] = []
        item["negative_controls"] = []
        self.assert_valid(item)

    def test_one_off_stays_owner_local(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "ONE_OFF_OR_DOMAIN_FAILURE"
        item["current_rule_audit"]["semantic_coverage"] = "NOT_APPLICABLE"
        item["current_rule_audit"]["implementation_coverage"] = "NOT_APPLICABLE"
        item["action"]["hard_gate_change"] = "NONE"
        item["action"]["workflow_change"] = "OWNER_LOCAL_FIX"
        item["action"]["causal_blocking_classes"] = []
        item["action"]["affected_consumers"] = []
        item["positive_controls"] = []
        item["negative_controls"] = []
        self.assert_valid(item)

    def test_append_only_policy_is_rejected_by_schema(self) -> None:
        item = copy.deepcopy(BASE)
        item["action"]["text_delta_policy"] = "APPEND_ONLY"
        self.assert_invalid(item, "REPLACE_MERGE_DELETE_NOT_APPEND_ONLY")

    def test_implementation_escape_cannot_add_public_rule(self) -> None:
        item = copy.deepcopy(BASE)
        item["action"]["public_rule_change"] = "MERGE_OMISSION"
        self.assert_invalid(item, "must not add or rewrite synonymous")

    def test_session_hard_gate_needs_causal_mapping(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "SESSION_EXECUTION_NONCOMPLIANCE"
        item["current_rule_audit"]["implementation_coverage"] = "PASS"
        item["action"]["hard_gate_change"] = "ADD_OR_STRENGTHEN"
        item["action"]["workflow_change"] = "SKILL_OR_HANDOFF"
        item["action"]["causal_blocking_classes"] = []
        item["action"]["affected_consumers"] = []
        self.assert_invalid(item, "requires causal blocking class")

    def test_semantic_omission_requires_controls(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "RULE_SEMANTIC_OMISSION"
        item["current_rule_audit"]["semantic_coverage"] = "MISSING"
        item["current_rule_audit"]["implementation_coverage"] = "NOT_APPLICABLE"
        item["action"]["public_rule_change"] = "MERGE_OMISSION"
        item["action"]["hard_gate_change"] = "NONE"
        item["positive_controls"] = []
        self.assert_invalid(item, "require positive and negative controls")

    def test_one_off_cannot_mutate_shared_gate(self) -> None:
        item = copy.deepcopy(BASE)
        item["classification"] = "ONE_OFF_OR_DOMAIN_FAILURE"
        item["current_rule_audit"]["semantic_coverage"] = "NOT_APPLICABLE"
        item["current_rule_audit"]["implementation_coverage"] = "NOT_APPLICABLE"
        item["action"]["public_rule_change"] = "NONE"
        item["action"]["hard_gate_change"] = "FIX_IMPLEMENTATION"
        item["action"]["workflow_change"] = "OWNER_LOCAL_FIX"
        self.assert_invalid(item, "do not change public rule or gate")


if __name__ == "__main__":
    unittest.main()
