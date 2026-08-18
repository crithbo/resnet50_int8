from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.server_package_pipeline import compile_profile


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads(
    (ROOT / "contracts/server_package_build_gate_registry_v1.json").read_text(
        encoding="utf-8"
    )
)
ALLOWLIST = {
    "runner_control_flow",
    "package_local_hdl",
    "materialized_config",
    "diagnostic_semantics",
    "post_sim_return_core",
    "final_zip_content",
}


class FastClosurePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".agents/rules").mkdir(parents=True)
        (self.root / ".agents/rules/生成前必读索引.md").write_text(
            "router\n", encoding="utf-8"
        )
        (self.root / ".agents/rules/服务器测试包生成规则.md").write_text(
            "server\n", encoding="utf-8"
        )
        (self.root / "payload").mkdir()
        (self.root / "payload/runner.sh").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def spec(self) -> dict:
        runner = self.root / "payload/runner.sh"
        return {
            "schema": "server-package-build-spec-v1",
            "package_id": "patch_first_v1",
            "family": "synthetic",
            "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
            "lifecycle": "NEXT_FRESH_SUCCESSOR",
            "shadow_only": True,
            "current_package_impact": False,
            "rule_change_epoch": {
                "epoch_id": "fast-closure-v2",
                "first_fresh_after_change": True,
                "prior_audit_receipt": None,
            },
            "changed_surfaces": ["runner"],
            "inputs": [
                {
                    "path": "payload/runner.sh",
                    "surface": "runner",
                    "bytes": runner.stat().st_size,
                    "sha256": "0" * 64,
                }
            ],
            "validators": {},
            "receipt_reuse_candidates": [],
            "cheap_check_reports": [],
            "require_all_cheap_checks": False,
        }

    def test_registry_has_only_six_blocking_purposes(self) -> None:
        self.assertEqual(set(REGISTRY["blocking_gate_allowlist"]), ALLOWLIST)
        self.assertFalse(REGISTRY["input_sha256_is_transport_blocker"])
        self.assertFalse(REGISTRY["validator_identity_is_transport_blocker"])
        self.assertTrue(REGISTRY["patch_first"])
        self.assertFalse(REGISTRY["full_rebuild_default"])

    def test_non_allowlisted_legacy_gates_are_record_only(self) -> None:
        profile = compile_profile(self.spec(), REGISTRY, self.root)
        self.assertTrue(profile["contract_valid"], profile["preflight"])
        by_gate = {
            item["gate_id"]: item for item in profile["gate_dispositions"]
        }
        for gate_id, item in by_gate.items():
            if gate_id not in ALLOWLIST:
                self.assertEqual(item["disposition"], "record_only", gate_id)
                self.assertEqual(item["causal_blocking_classes"], [], gate_id)
        self.assertEqual(
            set(profile["execution_contract"]["final_zip_subgates"]),
            {"post_sim_return_core", "final_zip_content"},
        )

    def test_wrong_transport_digest_does_not_block(self) -> None:
        profile = compile_profile(self.spec(), REGISTRY, self.root)
        self.assertTrue(profile["contract_valid"], profile["preflight"])
        self.assertNotIn(
            "input sha256 mismatch",
            "\n".join(profile["preflight"]["errors"]),
        )

    def test_changed_actual_input_blocks_only_its_gate(self) -> None:
        spec = self.spec()
        spec["changed_surfaces"] = ["config"]
        spec["inputs"][0]["surface"] = "config"
        profile = compile_profile(spec, REGISTRY, self.root)
        by_gate = {
            item["gate_id"]: item["disposition"]
            for item in profile["gate_dispositions"]
        }
        self.assertEqual(by_gate["materialized_config"], "blocking_applicable")
        self.assertEqual(by_gate["package_local_hdl"], "not_applicable")

    def test_unrun_revision_patch_is_allowed(self) -> None:
        spec = self.spec()
        spec.update(
            lifecycle="PATCH_UNRUN_REVISION",
            current_package_impact=True,
            prior_server_execution=False,
        )
        profile = compile_profile(spec, REGISTRY, self.root)
        self.assertTrue(profile["contract_valid"], profile["preflight"])
        self.assertTrue(profile["claim_boundary"]["changes_current_package"])

    def test_executed_package_cannot_be_patched(self) -> None:
        spec = self.spec()
        spec.update(
            lifecycle="PATCH_UNRUN_REVISION",
            current_package_impact=True,
            prior_server_execution=True,
        )
        profile = compile_profile(spec, REGISTRY, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertIn(
            "only a package with prior_server_execution=false may be patched",
            profile["preflight"]["errors"],
        )

    def test_full_rebuild_policy_cannot_be_silently_flipped(self) -> None:
        registry = copy.deepcopy(REGISTRY)
        registry["full_rebuild_default"] = True
        profile = compile_profile(self.spec(), registry, self.root)
        self.assertFalse(profile["contract_valid"])
        self.assertIn(
            "full_rebuild_default must be false", profile["preflight"]["errors"]
        )


if __name__ == "__main__":
    unittest.main()
