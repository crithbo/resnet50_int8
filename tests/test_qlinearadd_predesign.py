from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.qlinearadd_predesign import validate_qlinearadd_predesign


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts"
    / "operator_config"
    / "qlinearadd_composite_backend_predesign_v1.json"
)


class QLinearAddPredesignTests(unittest.TestCase):
    def test_repository_contract_is_valid_and_fail_closed(self) -> None:
        report = validate_qlinearadd_predesign(
            CONTRACT, repository_root=ROOT
        )
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["coverage"]["instances"], 17)
        self.assertEqual(report["coverage"]["same_shape_residual_add"], 16)
        self.assertEqual(report["coverage"]["broadcast_bias_add"], 1)
        self.assertFalse(report["materialization_allowed"])
        self.assertEqual(
            report["p0a_decision"],
            "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
        )
        allowed_warnings = {"mutable read receipt drift: .agents/plan.md"}
        self.assertTrue(
            set(report["warnings"]).issubset(allowed_warnings),
            report["warnings"],
        )
        self.assertLessEqual(len(report["warnings"]), 1)
        self.assertEqual(report["current_match_rules_checked"], 2)
        self.assertEqual(
            [item["node_id"] for item in report["affine_reassociation_counterexamples"]],
            ["node-0007", "node-0070"],
        )

    def test_release_mutation_fails(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        value["candidate_release"] = True
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "contract.json"
            mutated.write_text(json.dumps(value), encoding="utf-8")
            report = validate_qlinearadd_predesign(
                mutated, repository_root=ROOT
            )
        self.assertFalse(report["valid"])
        self.assertIn("candidate_release must be false", report["errors"])

    def test_standalone_cli_from_repository_root(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/validate_qlinearadd_predesign.py",
                "contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["coverage"]["instances"], 17)
        self.assertFalse(report["materialization_allowed"])

    def test_mutable_plan_receipt_drift_is_non_blocking(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        value["mutable_read_receipt"][".agents/plan.md"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "contract.json"
            mutated.write_text(json.dumps(value), encoding="utf-8")
            report = validate_qlinearadd_predesign(
                mutated, repository_root=ROOT
            )
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(
            report["warnings"],
            ["mutable read receipt drift: .agents/plan.md"],
        )
        self.assertFalse(report["materialization_allowed"])

    def test_active_rule_drift_is_blocking(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        dependency = value["current_match_rule_dependencies"][0]
        dependency["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "contract.json"
            mutated.write_text(json.dumps(value), encoding="utf-8")
            report = validate_qlinearadd_predesign(
                mutated, repository_root=ROOT
            )
        self.assertFalse(report["valid"])
        self.assertIn(
            "current-match rule SHA mismatch: "
            ".agents/rules/QLinearAdd算子配置规则.md",
            report["errors"],
        )
        self.assertFalse(report["materialization_allowed"])


if __name__ == "__main__":
    unittest.main()
