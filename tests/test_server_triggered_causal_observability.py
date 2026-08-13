from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools.validate_server_triggered_causal_observability import (
    BUDGET_RULE_ID,
    LOGGER_PARSER_RULE_ID,
    MULTICLASS_EDGE_RULE_ID,
    DEFAULT_PROFILES,
    DEFAULT_REGISTRY,
    CURRENT_FAMILIES,
    MECHANISM_IDS,
    evaluate_diagnostic_budget_trace,
    evaluate_logger_parser_format_trace,
    evaluate_multiclass_edge_trace,
    evaluate_calibration,
    main,
    validate_bundle,
)

ROOT = DEFAULT_REGISTRY.parents[1]
BUDGET_FIXTURE = (
    ROOT
    / "fixtures/server_diagnostic_budget_separation_v1/"
    "early_slice_state_oscillation.json"
)
BUDGET_FIXTURE_SCHEMA = (
    ROOT / "schemas/server_diagnostic_budget_trace_v1.schema.json"
)
BUDGET_NEGATIVE_FIXTURE = (
    ROOT
    / "fixtures/server_diagnostic_budget_separation_v1/"
    "legacy_shared_counter_mutation.json"
)
LOGGER_PARSER_FIXTURE_SCHEMA = (
    ROOT / "schemas/server_logger_parser_format_trace_v1.schema.json"
)
LOGGER_PARSER_POSITIVE_FIXTURE = (
    ROOT
    / "fixtures/server_logger_parser_format_v1/"
    "gap_v53_right_justified_explicit_normalization.json"
)
LOGGER_PARSER_NEGATIVE_FIXTURE = (
    ROOT
    / "fixtures/server_logger_parser_format_v1/"
    "gap_v53_legacy_unpadded_only_negative.json"
)
MULTICLASS_FIXTURE_SCHEMA = (
    ROOT / "schemas/server_diagnostic_multiclass_edge_trace_v1.schema.json"
)
MULTICLASS_PER_CLASS_POSITIVE = (
    ROOT
    / "fixtures/server_diagnostic_multiclass_edge_v1/"
    "per_class_snapshot_positive.json"
)
MULTICLASS_STICKY_POSITIVE = (
    ROOT
    / "fixtures/server_diagnostic_multiclass_edge_v1/"
    "sticky_all_classes_parser_positive.json"
)
MULTICLASS_V54_NEGATIVE = (
    ROOT
    / "fixtures/server_diagnostic_multiclass_edge_v1/"
    "gap_v54_priority_snapshot_loss_negative.json"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TriggeredCausalObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load(DEFAULT_REGISTRY)
        self.profiles = load(DEFAULT_PROFILES)

    def validate(self, profiles: dict | None = None) -> dict:
        return validate_bundle(
            copy.deepcopy(self.registry),
            copy.deepcopy(profiles or self.profiles),
        )

    def test_current_five_designs_are_complete_and_non_release(self) -> None:
        jsonschema.validate(
            self.profiles,
            load(
                ROOT
                / "schemas/server_triggered_causal_observability_v1.schema.json"
            ),
        )
        report = self.validate()
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(
            report["bundle_scope"], "CURRENT_FIVE_DESIGN_BASELINE"
        )
        self.assertEqual(report["profile_count"], 5)
        self.assertEqual(set(report["families"]), CURRENT_FAMILIES)
        self.assertEqual(
            set(report["registry"]["mechanism_ids"]), MECHANISM_IDS
        )
        self.assertTrue(
            all(not item["release_eligible"] for item in report["profiles"])
        )
        self.assertTrue(
            all(
                item["calibration"]["status"]
                == "PENDING_FRESH_BOUND_PROFILE"
                for item in report["profiles"]
            )
        )
        self.assertFalse(report["policy"]["slowdown_is_hard_gate"])
        self.assertEqual(
            report["policy"]["preferred_max_slowdown_percent"], 50.0
        )

    def test_calibration_at_50_percent_is_preferred_and_nonblocking(self) -> None:
        report = evaluate_calibration(
            baseline_wall_seconds=100,
            instrumented_wall_seconds=150,
        )
        self.assertEqual(report["status"], "WITHIN_PREFERRED")
        self.assertFalse(report["blocking"])
        self.assertEqual(report["slowdown_percent"], 50)

    def test_calibration_above_50_percent_is_report_only(self) -> None:
        report = evaluate_calibration(
            baseline_wall_seconds=100,
            instrumented_wall_seconds=175,
        )
        self.assertEqual(report["status"], "ABOVE_PREFERRED_REPORTED")
        self.assertFalse(report["blocking"])
        self.assertTrue(report["observation_completeness_must_be_preserved"])
        self.assertIn("WITHOUT_DROPPING_REQUIRED_BOUNDARIES", report["action"])

    def test_single_family_fresh_scope_uses_same_validator(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["bundle_scope"] = "FRESH_SUCCESSOR_BOUND_PROFILE"
        profiles["profiles"] = [profiles["profiles"][0]]
        report = self.validate(profiles)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(
            report["bundle_scope"], "FRESH_SUCCESSOR_BOUND_PROFILE"
        )
        self.assertEqual(report["profile_count"], 1)

    def test_per_event_text_io_fails_closed(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["storage"]["per_event_text_io"] = True
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("per-event text I/O" in item for item in report["errors"])
        )

    def test_full_wave_dump_fails_closed(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["storage"]["full_wave_dump"] = True
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("full-wave dump" in item for item in report["errors"])
        )

    def test_budget_separation_is_required_for_every_profile(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        del profiles["profiles"][0]["storage"][
            "diagnostic_budget_separation"
        ]
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any(
                "diagnostic_budget_separation is missing" in item
                for item in report["errors"]
            )
        )

    def test_state_activity_cannot_consume_qualified_budget(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        separation = profiles["profiles"][0]["storage"][
            "diagnostic_budget_separation"
        ]
        separation["state_activity_consumes_qualified_budget"] = True
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any(
                "state_activity_consumes_qualified_budget" in item
                for item in report["errors"]
            )
        )

    def test_late_slice_qualified_event_survives_state_budget_exhaustion(
        self,
    ) -> None:
        fixture = load(BUDGET_FIXTURE)
        jsonschema.validate(fixture, load(BUDGET_FIXTURE_SCHEMA))
        report = evaluate_diagnostic_budget_trace(fixture)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["rule_id"], BUDGET_RULE_ID)
        self.assertGreater(
            report["state_seen"], report["non_progress_state_budget"]
        )
        self.assertTrue(
            report["state_budget_exhausted_before_late_event"]
        )
        self.assertGreater(
            report["state_records_coalesced_or_dropped"], 0
        )
        self.assertTrue(report["late_qualified_event_retained"])
        self.assertFalse(
            report["state_activity_consumed_qualified_budget"]
        )

    def test_legacy_shared_counter_mutation_fails_closed(self) -> None:
        fixture = load(BUDGET_NEGATIVE_FIXTURE)
        report = evaluate_diagnostic_budget_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("must separate" in item for item in report["errors"])
        )
        self.assertFalse(report["late_qualified_event_retained"])
        self.assertTrue(
            report["state_activity_consumed_qualified_budget"]
        )

    def test_exact_right_justified_logger_records_reach_parser(self) -> None:
        fixture = load(LOGGER_PARSER_POSITIVE_FIXTURE)
        jsonschema.validate(fixture, load(LOGGER_PARSER_FIXTURE_SCHEMA))
        report = evaluate_logger_parser_format_trace(fixture)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["rule_id"], LOGGER_PARSER_RULE_ID)
        self.assertTrue(report["exact_logger_rendered_records_tested"])
        self.assertTrue(report["synthetic_unpadded_is_not_sole_positive"])
        self.assertEqual(
            report["parsed_record_counts"],
            {"QUALIFIED_EDGE": 1, "FACTOR_EDGE": 1, "HEARTBEAT": 1},
        )
        fields = {
            item["event"]: item["event_field"]
            for item in report["rendered_records"]
        }
        self.assertEqual(fields["QUALIFIED_EDGE"], "QUALIFIED_EDGE")
        self.assertEqual(fields["FACTOR_EDGE"], "   FACTOR_EDGE")
        self.assertEqual(fields["HEARTBEAT"], "     HEARTBEAT")
        self.assertTrue(
            all(item["event_field_length"] == 14 for item in report["rendered_records"])
        )

    def test_v53_legacy_unpadded_only_parser_fails_exact_logger_trace(
        self,
    ) -> None:
        fixture = load(LOGGER_PARSER_NEGATIVE_FIXTURE)
        jsonschema.validate(fixture, load(LOGGER_PARSER_FIXTURE_SCHEMA))
        report = evaluate_logger_parser_format_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertEqual(report["parsed_record_counts"]["QUALIFIED_EDGE"], 1)
        self.assertEqual(report["parsed_record_counts"]["FACTOR_EDGE"], 0)
        self.assertEqual(report["parsed_record_counts"]["HEARTBEAT"], 0)
        self.assertTrue(
            any("FACTOR_EDGE" in item for item in report["errors"])
        )
        self.assertTrue(
            any("HEARTBEAT" in item for item in report["errors"])
        )

    def test_undeclared_logger_padding_mutations_fail_closed(self) -> None:
        report = evaluate_logger_parser_format_trace(
            load(LOGGER_PARSER_POSITIVE_FIXTURE)
        )
        self.assertTrue(report["all_undeclared_mutations_rejected"])
        self.assertTrue(
            all(report["undeclared_mutation_controls"].values())
        )
        self.assertIn(
            "synthetic_unpadded_not_exact_logger",
            report["undeclared_mutation_controls"],
        )
        self.assertIn(
            "tab_padding_not_declared",
            report["undeclared_mutation_controls"],
        )

    def test_logger_source_identity_drift_fails_closed(self) -> None:
        fixture = load(LOGGER_PARSER_POSITIVE_FIXTURE)
        fixture["source_bindings"]["logger"]["sha256"] = "0" * 64
        report = evaluate_logger_parser_format_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("logger source binding mismatch" in item for item in report["errors"])
        )

    def test_normalization_cannot_exceed_exact_logger_padding(self) -> None:
        fixture = load(LOGGER_PARSER_POSITIVE_FIXTURE)
        fixture["parser_contract"]["normalization_max_padding_chars"] = 6
        report = evaluate_logger_parser_format_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("padding bound differs" in item for item in report["errors"])
        )

    def test_per_class_snapshot_preserves_all_simultaneous_edges(self) -> None:
        fixture = load(MULTICLASS_PER_CLASS_POSITIVE)
        jsonschema.validate(fixture, load(MULTICLASS_FIXTURE_SCHEMA))
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["rule_id"], MULTICLASS_EDGE_RULE_ID)
        self.assertEqual(
            [item["emitted_class"] for item in report["emitted_sequence"]],
            ["QUALIFIED_EDGE", "VIOLATION_EDGE", "FACTOR_EDGE"],
        )
        self.assertEqual(report["covered_required_class_count"], 3)
        self.assertEqual(report["missing_required_classes"], [])
        self.assertEqual(report["progress_record_count"], 1)
        self.assertFalse(report["non_progress_state_counted_as_progress"])
        self.assertEqual(report["budget_blocked_counts"]["QUALIFIED_EDGE"], 2)
        self.assertEqual(report["budget_blocked_counts"]["VIOLATION_EDGE"], 0)
        self.assertEqual(report["sample_trace"][0]["snapshot_before"], {
            "QUALIFIED_EDGE": 0,
            "VIOLATION_EDGE": 0,
            "FACTOR_EDGE": 0,
        })
        self.assertEqual(report["sample_trace"][0]["snapshot_after"], {
            "QUALIFIED_EDGE": 1,
            "VIOLATION_EDGE": 0,
            "FACTOR_EDGE": 0,
        })

    def test_sticky_all_class_parser_recovers_lower_priority_classes(
        self,
    ) -> None:
        fixture = load(MULTICLASS_STICKY_POSITIVE)
        jsonschema.validate(fixture, load(MULTICLASS_FIXTURE_SCHEMA))
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(
            [item["emitted_class"] for item in report["emitted_sequence"]],
            ["QUALIFIED_EDGE"],
        )
        self.assertEqual(
            report["class_evidence_masks"],
            {"QUALIFIED_EDGE": 1, "VIOLATION_EDGE": 2, "FACTOR_EDGE": 4},
        )
        self.assertEqual(report["progress_record_count"], 1)
        self.assertEqual(
            report["sample_trace"][0]["parser_consumed_classes"],
            ["QUALIFIED_EDGE", "VIOLATION_EDGE", "FACTOR_EDGE"],
        )

    def test_gap_v54_priority_snapshot_loss_fails_closed(self) -> None:
        fixture = load(MULTICLASS_V54_NEGATIVE)
        jsonschema.validate(fixture, load(MULTICLASS_FIXTURE_SCHEMA))
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertFalse(report["closure_strategy"]["valid"])
        self.assertEqual(
            report["missing_required_classes"],
            ["VIOLATION_EDGE", "FACTOR_EDGE"],
        )
        self.assertEqual(report["emitted_record_counts"]["QUALIFIED_EDGE"], 1)
        self.assertEqual(report["emitted_record_counts"]["VIOLATION_EDGE"], 0)

    def test_sticky_parser_rejects_nonmonotonic_class_state(self) -> None:
        fixture = load(MULTICLASS_STICKY_POSITIVE)
        fixture["samples"].append(
            {
                "sample_id": "illegal-sticky-regression",
                "class_state": {
                    "QUALIFIED_EDGE": 1,
                    "VIOLATION_EDGE": 0,
                    "FACTOR_EDGE": 4,
                },
            }
        )
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(any("regressed" in item for item in report["errors"]))

    def test_multiclass_source_identity_drift_fails_closed(self) -> None:
        fixture = load(MULTICLASS_PER_CLASS_POSITIVE)
        fixture["source_bindings"]["observer"]["sha256"] = "0" * 64
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("observer source binding mismatch" in item for item in report["errors"])
        )

    def test_nonprogress_multiclass_state_cannot_count_as_progress(self) -> None:
        fixture = load(MULTICLASS_PER_CLASS_POSITIVE)
        fixture["parser_contract"]["non_progress_classes_count_as_progress"] = True
        report = evaluate_multiclass_edge_trace(fixture)
        self.assertFalse(report["valid"])
        self.assertTrue(report["non_progress_state_counted_as_progress"])

    def test_stage_gating_cannot_be_disabled(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["runtime_behavior"]["stage_gating"] = False
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("stage_gating" in item for item in report["errors"])
        )

    def test_observer_cannot_drive_dut_or_replay_internal_tensor(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        runtime = profiles["profiles"][0]["runtime_behavior"]
        runtime["drives_dut"] = True
        runtime["host_internal_tensor_replay"] = True
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(any("drives_dut" in item for item in report["errors"]))
        self.assertTrue(
            any(
                "host_internal_tensor_replay" in item
                for item in report["errors"]
            )
        )

    def test_first_version_cannot_auto_terminate(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["no_progress"]["auto_terminate"] = True
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("auto_terminate" in item for item in report["errors"])
        )

    def test_unknown_hypothesis_boundary_fails_closed(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["hypotheses"][0][
            "distinguished_by"
        ].append("gap.nonexistent")
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("unknown boundaries" in item for item in report["errors"])
        )

    def test_duplicate_hypothesis_observation_signature_fails_closed(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        hypotheses = profiles["profiles"][0]["hypotheses"]
        hypotheses[1]["distinguished_by"] = copy.deepcopy(
            hypotheses[0]["distinguished_by"]
        )
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any(
                "reuse the same observation signature" in item
                for item in report["errors"]
            )
        )

    def test_missing_trigger_fails_closed(self) -> None:
        profiles = copy.deepcopy(self.profiles)
        profiles["profiles"][0]["triggers"] = profiles["profiles"][0][
            "triggers"
        ][1:]
        report = self.validate(profiles)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("trigger set mismatch" in item for item in report["errors"])
        )

    def test_cli_emits_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "report.json"
            exit_code = main(["validate", "--output", str(output)])
            self.assertEqual(exit_code, 0)
            report = load(output)
            self.assertTrue(report["valid"])
            self.assertIn("inputs", report)

    def test_budget_trace_cli_emits_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "budget-trace.json"
            exit_code = main(
                [
                    "validate-budget-trace",
                    "--fixture",
                    str(BUDGET_FIXTURE),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            report = load(output)
            self.assertTrue(report["valid"], report["errors"])
            self.assertTrue(report["late_qualified_event_retained"])

    def test_logger_parser_format_cli_emits_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "logger-parser-format.json"
            exit_code = main(
                [
                    "validate-logger-parser-format",
                    "--fixture",
                    str(LOGGER_PARSER_POSITIVE_FIXTURE),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            report = load(output)
            self.assertTrue(report["valid"], report["errors"])
            self.assertIn("fixture_schema", report["inputs"])

    def test_multiclass_edge_cli_emits_machine_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "multiclass-edge.json"
            exit_code = main(
                [
                    "validate-multiclass-edge-trace",
                    "--fixture",
                    str(MULTICLASS_PER_CLASS_POSITIVE),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            report = load(output)
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["covered_required_class_count"], 3)

    def test_rules_publish_completeness_first_and_soft_50_percent(self) -> None:
        root = DEFAULT_REGISTRY.parents[1]
        server_rule = (
            root / ".agents/rules/服务器测试包生成规则.md"
        ).read_text(encoding="utf-8")
        optimizer_rule = (
            root / ".agents/rules/整网测试收敛优化专项规则.md"
        ).read_text(encoding="utf-8")
        index = (
            root / ".agents/rules/生成前必读索引.md"
        ).read_text(encoding="utf-8")
        rule_id = (
            "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001"
        )
        self.assertIn(rule_id, server_rule)
        self.assertIn(rule_id, optimizer_rule)
        self.assertIn(rule_id, index)
        self.assertIn("不是阻断上限", server_rule)
        self.assertIn("不是硬阻断门", optimizer_rule)
        self.assertIn("不得删除单轮定位仍需的边界", server_rule)

    def test_rules_publish_exact_logger_to_parser_format_gate(self) -> None:
        root = DEFAULT_REGISTRY.parents[1]
        server_rule = (
            root / ".agents/rules/服务器测试包生成规则.md"
        ).read_text(encoding="utf-8")
        index = (
            root / ".agents/rules/生成前必读索引.md"
        ).read_text(encoding="utf-8")
        self.assertIn(LOGGER_PARSER_RULE_ID, server_rule)
        self.assertIn(LOGGER_PARSER_RULE_ID, index)
        self.assertIn("exact logger", server_rule)
        self.assertIn("手写无填充", server_rule)

    def test_rules_publish_multiclass_edge_no_loss_gate(self) -> None:
        root = DEFAULT_REGISTRY.parents[1]
        server_rule = (
            root / ".agents/rules/服务器测试包生成规则.md"
        ).read_text(encoding="utf-8")
        index = (
            root / ".agents/rules/生成前必读索引.md"
        ).read_text(encoding="utf-8")
        self.assertIn(MULTICLASS_EDGE_RULE_ID, server_rule)
        self.assertIn(MULTICLASS_EDGE_RULE_ID, index)
        self.assertIn("per-class pending/snapshot", server_rule)
        self.assertIn("monotonic sticky all-class parse", server_rule)

    def test_registry_and_rules_publish_source_bound_generation_gate(self) -> None:
        registry = load(DEFAULT_REGISTRY)
        mechanism_ids = {
            item["mechanism_id"] for item in registry["mechanisms"]
        }
        self.assertIn("SOURCE_BOUND_GENERATED_OBSERVER", mechanism_ids)
        self.assertIn("CAUSAL_DECISION_MATRIX_UNIQUE", mechanism_ids)
        self.assertIn("HIGH_INFORMATION_SEPARATE_EVENT_RINGS", mechanism_ids)
        server_rule = (
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ).read_text(encoding="utf-8")
        index = (
            ROOT / ".agents/rules/生成前必读索引.md"
        ).read_text(encoding="utf-8")
        rule_id = "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001"
        self.assertIn(rule_id, server_rule)
        self.assertIn(rule_id, index)
        self.assertIn("BITMAP_ALL_TRUE_CLASSES", server_rule)
        self.assertIn("source_bound_observer_generation", server_rule)


if __name__ == "__main__":
    unittest.main()
