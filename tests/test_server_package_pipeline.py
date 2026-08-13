from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools.server_package_pipeline import compile_profile, semantic_sha256


REGISTRY = Path(
    "contracts/server_package_build_gate_registry_v1.json"
)
PROFILE_SCHEMA = Path("schemas/server_package_build_profile_v1.schema.json")
CHEAP_SCHEMA = Path(
    "schemas/server_package_cheap_check_result_v1.schema.json"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ServerPackagePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".agents/rules").mkdir(parents=True)
        (self.root / ".agents/rules/生成前必读索引.md").write_text(
            "routing\n", encoding="utf-8"
        )
        (self.root / ".agents/rules/服务器测试包生成规则.md").write_text(
            "server rule\n", encoding="utf-8"
        )
        (self.root / "payload").mkdir()
        (self.root / "payload/observer.svh").write_text(
            "module observer; endmodule\n", encoding="utf-8"
        )
        self.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.validator_sha = "1" * 64
        self.fixture_sha = "2" * 64
        self.cheap_dir = self.root / "cheap"
        self.cheap_dir.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def spec(self) -> dict:
        payload = self.root / "payload/observer.svh"
        validators = {
            gate["gate_id"]: {
                "validator_sha256": self.validator_sha,
                "fixture_sha256": self.fixture_sha,
            }
            for gate in self.registry["gates"]
            if gate["validator_identity_required"]
        }
        return {
            "schema": "server-package-build-spec-v1",
            "package_id": "next_fresh_shadow_v1",
            "family": "synthetic",
            "lifecycle": "NEXT_FRESH_SUCCESSOR",
            "shadow_only": True,
            "current_package_impact": False,
            "rule_change_epoch": {
                "epoch_id": "20260810-first-fresh-extra-audit-v1",
                "first_fresh_after_change": True,
                "prior_audit_receipt": None,
            },
            "changed_surfaces": ["observer"],
            "inputs": [
                {
                    "path": "payload/observer.svh",
                    "surface": "observer",
                    "bytes": payload.stat().st_size,
                    "sha256": sha(payload),
                }
            ],
            "validators": validators,
            "receipt_reuse_candidates": [],
            "cheap_check_reports": [],
            "require_all_cheap_checks": False,
        }

    def add_cheap_result(
        self, spec: dict, gate_id: str, passed: bool, errors: list[str]
    ) -> None:
        path = self.cheap_dir / f"{gate_id}.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "server-package-cheap-check-result-v1",
                    "gate_id": gate_id,
                    "pass": passed,
                    "errors": errors,
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        spec["cheap_check_reports"].append(
            {
                "gate_id": gate_id,
                "path": path.relative_to(self.root).as_posix(),
                "sha256": sha(path),
            }
        )

    def add_source_bound_inputs(self, spec: dict) -> None:
        for surface, filename, payload in (
            ("probe_catalog", "catalog.json", "{}\n"),
            ("probe_plan", "plan.json", "{}\n"),
            ("parser", "parser.py", "raise SystemExit(0)\n"),
            ("package_local_hdl", "generated_observer.svh", "module generated_observer; endmodule\n"),
        ):
            path = self.root / "payload" / filename
            path.write_text(payload, encoding="utf-8")
            spec["inputs"].append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "surface": surface,
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
            )
            if surface not in spec["changed_surfaces"]:
                spec["changed_surfaces"].append(surface)

    def test_next_fresh_shadow_profile(self) -> None:
        profile = compile_profile(self.spec(), self.registry, self.root)
        self.assertTrue(profile["contract_valid"])
        jsonschema.validate(
            profile, json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
        )
        self.assertFalse(profile["claim_boundary"]["changes_current_package"])
        by_gate = {
            item["gate_id"]: item["disposition"]
            for item in profile["gate_dispositions"]
        }
        self.assertEqual(
            by_gate["diagnostic_semantics"], "blocking_applicable"
        )
        self.assertEqual(by_gate["materialized_config"], "not_applicable")
        self.assertEqual(
            by_gate["intermediate_report_format"], "record_only"
        )
        self.assertEqual(
            by_gate["runtime_layout"], "blocking_applicable"
        )
        self.assertEqual(
            by_gate["first_fresh_extra_audit"], "blocking_applicable"
        )
        self.assertTrue(
            profile["claim_boundary"]["first_fresh_extra_audit_required"]
        )
        self.assertEqual(
            profile["execution_contract"][
                "final_zip_release_driver_top_level_invocations"
            ],
            1,
        )
        for gate in profile["gate_dispositions"]:
            if gate["disposition"] == "blocking_applicable":
                self.assertTrue(gate["causal_blocking_classes"])

    def test_collects_all_cheap_errors_without_fail_fast(self) -> None:
        spec = self.spec()
        spec["lifecycle"] = "CURRENT_PENDING"
        spec["shadow_only"] = False
        spec["current_package_impact"] = True
        spec["changed_surfaces"] = ["unknown", "unknown"]
        spec["inputs"][0]["bytes"] = 0
        spec["inputs"][0]["sha256"] = "0" * 64
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertGreaterEqual(len(profile["preflight"]["errors"]), 7)
        self.assertTrue(profile["preflight"]["all_errors_collected"])

    def test_missing_rule_change_epoch_is_rejected(self) -> None:
        spec = self.spec()
        del spec["rule_change_epoch"]
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertTrue(
            any(
                "rule_change_epoch" in message
                for message in profile["preflight"]["errors"]
            )
        )

    def test_nonfirst_package_requires_bound_prior_pass_receipt(self) -> None:
        spec = self.spec()
        spec["rule_change_epoch"]["first_fresh_after_change"] = False
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        receipt = self.root / "first_fresh_audit.json"
        receipt.write_text(
            json.dumps(
                {
                    "schema": "server-first-fresh-extra-audit-validation-v1",
                    "pass": True,
                    "family": "synthetic",
                    "package_id": "first_fresh_v1",
                    "rule_change_epoch_id": (
                        "20260810-first-fresh-extra-audit-v1"
                    ),
                }
            ),
            encoding="utf-8",
        )
        spec["rule_change_epoch"]["prior_audit_receipt"] = {
            "path": receipt.relative_to(self.root).as_posix(),
            "sha256": sha(receipt),
        }
        profile = compile_profile(spec, self.registry, self.root)
        self.assertTrue(profile["contract_valid"])
        gate = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "first_fresh_extra_audit"
        )
        self.assertEqual(gate["disposition"], "not_applicable")
        self.assertFalse(
            profile["claim_boundary"]["first_fresh_extra_audit_required"]
        )

    def test_exact_receipt_is_reused_for_unchanged_always_gate(self) -> None:
        spec = self.spec()
        spec["changed_surfaces"] = ["observer"]
        initial = compile_profile(spec, self.registry, self.root)
        gate = next(
            item
            for item in initial["gate_dispositions"]
            if item["gate_id"] == "runner_control_flow"
        )
        spec["receipt_reuse_candidates"] = [
            {
                "gate_id": "runner_control_flow",
                "result": "PASS",
                "exact_bytes_equal": True,
                "direct_consumers_equal": True,
                "surface_sha256": semantic_sha256(
                    {
                        surface: initial["surface_hashes"][surface]
                        for surface in sorted(["runner", "return_collector"])
                    }
                ),
                "semantic_version": "1",
                "validator_sha256": self.validator_sha,
                "fixture_sha256": self.fixture_sha,
                "report_sha256": "3" * 64,
            }
        ]
        profile = compile_profile(spec, self.registry, self.root)
        reused = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "runner_control_flow"
        )
        self.assertEqual(reused["disposition"], "receipt_reuse")
        self.assertEqual(reused["cache_key"], gate["cache_key"])

    def test_stale_validator_receipt_is_rejected(self) -> None:
        spec = self.spec()
        initial = compile_profile(spec, self.registry, self.root)
        surface_sha = semantic_sha256(
            {
                surface: initial["surface_hashes"][surface]
                for surface in sorted(["runner", "return_collector"])
            }
        )
        spec["receipt_reuse_candidates"] = [
            {
                "gate_id": "runner_control_flow",
                "result": "PASS",
                "exact_bytes_equal": True,
                "direct_consumers_equal": True,
                "surface_sha256": surface_sha,
                "semantic_version": "1",
                "validator_sha256": "9" * 64,
                "fixture_sha256": self.fixture_sha,
                "report_sha256": "3" * 64,
            }
        ]
        profile = compile_profile(spec, self.registry, self.root)
        gate = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "runner_control_flow"
        )
        self.assertEqual(gate["disposition"], "blocking_applicable")
        self.assertTrue(
            any(
                "stale or incomplete receipt rejected" in warning
                for warning in profile["preflight"]["warnings"]
            )
        )

    def test_runtime_layout_cannot_be_reused(self) -> None:
        spec = self.spec()
        initial = compile_profile(spec, self.registry, self.root)
        gate = next(
            item
            for item in initial["gate_dispositions"]
            if item["gate_id"] == "runtime_layout"
        )
        spec["receipt_reuse_candidates"] = [
            {
                "gate_id": "runtime_layout",
                "result": "PASS",
                "exact_bytes_equal": True,
                "direct_consumers_equal": True,
                "surface_sha256": semantic_sha256(
                    {
                        surface: initial["surface_hashes"][surface]
                        for surface in sorted(
                            ["runner", "sca", "return_collector", "storage"]
                        )
                    }
                ),
                "semantic_version": "1",
                "validator_sha256": self.validator_sha,
                "fixture_sha256": self.fixture_sha,
                "report_sha256": "3" * 64,
            }
        ]
        profile = compile_profile(spec, self.registry, self.root)
        runtime_layout = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "runtime_layout"
        )
        self.assertEqual(
            runtime_layout["disposition"], "blocking_applicable"
        )
        self.assertEqual(runtime_layout["cache_key"], gate["cache_key"])

    def test_current_package_cannot_enter_shadow_driver(self) -> None:
        spec = self.spec()
        spec["lifecycle"] = "CURRENT_PENDING"
        spec["current_package_impact"] = True
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertIn(
            "only NEXT_FRESH_SUCCESSOR is accepted",
            profile["preflight"]["errors"],
        )
        self.assertIn(
            "current package impact must be false",
            profile["preflight"]["errors"],
        )

    def test_cache_key_is_input_order_independent(self) -> None:
        extra = self.root / "payload/runner.sh"
        extra.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        spec = self.spec()
        spec["inputs"].append(
            {
                "path": "payload/runner.sh",
                "surface": "runner",
                "bytes": extra.stat().st_size,
                "sha256": sha(extra),
            }
        )
        first = compile_profile(spec, self.registry, self.root)
        reversed_spec = copy.deepcopy(spec)
        reversed_spec["inputs"].reverse()
        second = compile_profile(reversed_spec, self.registry, self.root)
        self.assertEqual(first["surface_hashes"], second["surface_hashes"])
        self.assertEqual(
            [
                item["cache_key"] for item in first["gate_dispositions"]
            ],
            [
                item["cache_key"] for item in second["gate_dispositions"]
            ],
        )

    def test_all_cheap_reports_are_aggregated_in_one_pass(self) -> None:
        spec = self.spec()
        self.add_cheap_result(
            spec, "core_identity_bootstrap", False, ["identity mismatch"]
        )
        self.add_cheap_result(
            spec, "storage_rotation", False, ["duplicate pending"]
        )
        self.add_cheap_result(
            spec, "source_bound_observer_generation", True, []
        )
        self.add_cheap_result(
            spec, "intermediate_report_format", False, ["missing optional title"]
        )
        supplied = {item["gate_id"] for item in spec["cheap_check_reports"]}
        for gate in self.registry["gates"]:
            if gate.get("cheap_prebuild_eligible") is True and gate["gate_id"] not in supplied:
                self.add_cheap_result(spec, gate["gate_id"], True, [])
        spec["require_all_cheap_checks"] = True
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertEqual(
            profile["aggregate_prebuild"]["top_level_invocations"], 1
        )
        self.assertTrue(profile["aggregate_prebuild"]["coverage_complete"])
        self.assertIn(
            "core_identity_bootstrap: identity mismatch",
            profile["preflight"]["errors"],
        )
        self.assertIn(
            "storage_rotation: duplicate pending",
            profile["preflight"]["errors"],
        )
        self.assertNotIn(
            "intermediate_report_format: missing optional title",
            profile["preflight"]["errors"],
        )
        self.assertIn(
            "intermediate_report_format: missing optional title",
            profile["preflight"]["warnings"],
        )
        for path in self.cheap_dir.glob("*.json"):
            jsonschema.validate(
                json.loads(path.read_text(encoding="utf-8")),
                json.loads(CHEAP_SCHEMA.read_text(encoding="utf-8")),
            )

    def test_missing_required_cheap_reports_is_one_aggregate_error(self) -> None:
        spec = self.spec()
        spec["require_all_cheap_checks"] = True
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertTrue(
            any(
                "missing required cheap check reports" in item
                for item in profile["preflight"]["errors"]
            )
        )

    def test_next_fresh_required_aggregate_accepts_source_bound_receipts(self) -> None:
        spec = self.spec()
        self.add_source_bound_inputs(spec)
        for gate in self.registry["gates"]:
            if gate.get("cheap_prebuild_eligible") is True:
                self.add_cheap_result(spec, gate["gate_id"], True, [])
        spec["require_all_cheap_checks"] = True
        profile = compile_profile(spec, self.registry, self.root)
        self.assertTrue(profile["contract_valid"], profile["preflight"])
        self.assertTrue(profile["aggregate_prebuild"]["coverage_complete"])
        gate = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "source_bound_observer_generation"
        )
        self.assertEqual(gate["disposition"], "blocking_applicable")
        self.assertEqual(
            gate["causal_blocking_classes"], ["server_start", "return"]
        )
        self.assertEqual(gate["enforcement"], "required_next_fresh")
        self.assertTrue(
            profile["claim_boundary"][
                "source_bound_gate_required_next_fresh"
            ]
        )
        return_gate = next(
            item
            for item in profile["gate_dispositions"]
            if item["gate_id"] == "post_sim_return_core"
        )
        self.assertEqual(return_gate["disposition"], "blocking_applicable")
        self.assertEqual(return_gate["causal_blocking_classes"], ["return"])
        self.assertEqual(return_gate["enforcement"], "required_next_fresh")
        self.assertTrue(
            profile["claim_boundary"][
                "post_sim_return_gate_required_next_fresh"
            ]
        )

    def test_post_sim_return_core_cannot_be_downgraded_to_shadow(self) -> None:
        spec = self.spec()
        registry = copy.deepcopy(self.registry)
        gate = next(
            item
            for item in registry["gates"]
            if item["gate_id"] == "post_sim_return_core"
        )
        gate["enforcement"] = "shadow_only"
        profile = compile_profile(spec, registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertTrue(
            any(
                "post_sim_return_core must be required_next_fresh" in item
                for item in profile["preflight"]["errors"]
            )
        )

    def test_next_fresh_required_aggregate_rejects_missing_source_bound_inputs(self) -> None:
        spec = self.spec()
        for gate in self.registry["gates"]:
            if gate.get("cheap_prebuild_eligible") is True:
                self.add_cheap_result(spec, gate["gate_id"], True, [])
        spec["require_all_cheap_checks"] = True
        profile = compile_profile(spec, self.registry, self.root)
        self.assertFalse(profile["contract_valid"])
        errors = "\n".join(profile["preflight"]["errors"])
        self.assertIn("source-bound observer generation inputs are incomplete", errors)
        self.assertIn("probe_catalog", errors)
        self.assertIn("probe_plan", errors)
        self.assertIn("parser", errors)

    def test_registry_rejects_blocking_gate_without_causal_mapping(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["gates"][0]["causal_blocking_classes"] = []
        profile = compile_profile(self.spec(), registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertIn(
            "core_identity_bootstrap: blocking gate lacks causal mapping",
            profile["preflight"]["errors"],
        )


if __name__ == "__main__":
    unittest.main()
