from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.test_complete_operator_json_candidate import (
    CompleteJsonCase,
    bound,
    sha256_file,
)
from tools.audit_complete_operator_json_family_set import audit_family_set


class CompleteOperatorJsonFamilySetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = CompleteJsonCase(self.root)
        self.case.flush_contract()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_manifest(
        self,
        stage_contracts: bool = True,
        family_scope: dict | None = None,
        target_hw_op_types: list[str] | None = None,
    ) -> Path:
        manifest = {
            "schema": "operator_config_complete_json_family_set_v1",
            "family": self.case.family,
            "target_hw_op_types": target_hw_op_types or ["MaxPoolUint8"],
            "candidate_contracts": (
                [bound(self.root, self.case.contract_path)]
                if stage_contracts
                else []
            ),
            "no_config_stages": [],
            "claim_boundary": "Synthetic MaxPool family coverage.",
        }
        if family_scope is not None:
            manifest["family_scope"] = family_scope
        path = self.root / "artifacts/synthetic/family_set.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def configure_matmul_shared_primitive_fixture(self) -> None:
        lowering = json.loads(self.case.lowering_path.read_text(encoding="utf-8"))
        accumulate = lowering["requests"][0]
        accumulate["identity"] = {
            "hw_op_id": "hwop-0075-00",
            "node_id": "node-0075",
            "onnx_op_type": "QLinearMatMul",
            "hw_op_type": "MatMulInt32Accumulate",
        }
        requant = json.loads(json.dumps(accumulate))
        requant["identity"]["hw_op_id"] = "hwop-0075-01"
        requant["identity"]["hw_op_type"] = "RequantizeUint8"
        foreign = json.loads(json.dumps(requant))
        foreign["identity"] = {
            "hw_op_id": "hwop-0001-01",
            "node_id": "node-0001",
            "onnx_op_type": "QLinearConv",
            "hw_op_type": "RequantizeUint8",
        }
        lowering["requests"] = [accumulate, requant, foreign]
        lowering["coverage"]["stage_count"] = 3
        self.case.lowering_path.write_text(
            json.dumps(lowering, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        self.case.contract["target_hw_op_types"] = [
            "MatMulInt32Accumulate",
            "RequantizeUint8",
        ]
        self.case.contract["stage_ids"] = ["hwop-0075-00", "hwop-0075-01"]
        self.case.contract_path = self.case.flush_contract()

    def audit(self, manifest: Path) -> dict:
        return audit_family_set(
            workspace_root=self.root,
            manifest_path=manifest,
            authority_path=self.case.authority_path,
            policy_path=self.case.policy_path,
            lowering_path=self.case.lowering_path,
        )

    def test_complete_family_stage_coverage_positive(self) -> None:
        report = self.audit(self.write_manifest())
        self.assertTrue(report["pass"], msg=json.dumps(report, indent=2))
        self.assertEqual(report["expected_stage_count"], 1)
        self.assertEqual(report["covered_stage_count"], 1)

    def test_missing_family_stage_fails_closed(self) -> None:
        report = self.audit(self.write_manifest(stage_contracts=False))
        self.assertFalse(report["pass"])
        self.assertEqual(report["missing_stage_ids"], ["synthetic-stage-0"])

    def exact_scope(self, expected_stage_ids: list[str] | None = None) -> dict:
        return {
            "mode": "PINNED_EXACT_STAGE_IDS",
            "lowering_sha256": sha256_file(self.case.lowering_path),
            "expected_stage_ids": expected_stage_ids or ["synthetic-stage-0"],
        }

    def add_foreign_shared_primitive(self) -> None:
        lowering = json.loads(self.case.lowering_path.read_text(encoding="utf-8"))
        foreign = json.loads(json.dumps(lowering["requests"][0]))
        foreign["identity"]["hw_op_id"] = "foreign-stage"
        foreign["identity"]["node_id"] = "foreign-node"
        foreign["identity"]["onnx_op_type"] = "ForeignLogicalFamily"
        lowering["requests"].append(foreign)
        lowering["coverage"]["stage_count"] = 2
        self.case.lowering_path.write_text(
            json.dumps(lowering, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def test_pinned_exact_scope_refines_shared_hardware_primitive(self) -> None:
        self.add_foreign_shared_primitive()
        unrefined = self.audit(self.write_manifest())
        self.assertFalse(unrefined["pass"])
        self.assertEqual(unrefined["missing_stage_ids"], ["foreign-stage"])

        refined = self.audit(self.write_manifest(family_scope=self.exact_scope()))
        self.assertTrue(refined["pass"], msg=json.dumps(refined, indent=2))
        self.assertEqual(refined["expected_stage_count"], 1)
        self.assertEqual(refined["scope_mode"], "PINNED_EXACT_STAGE_IDS")
        self.assertFalse(refined["legacy_scope_compatibility"])

    def test_pinned_exact_scope_missing_stage_fails_closed(self) -> None:
        report = self.audit(self.write_manifest(stage_contracts=False, family_scope=self.exact_scope()))
        self.assertFalse(report["pass"])
        self.assertEqual(report["missing_stage_ids"], ["synthetic-stage-0"])

    def test_pinned_exact_scope_duplicate_stage_fails_closed(self) -> None:
        report = self.audit(
            self.write_manifest(
                family_scope=self.exact_scope(
                    ["synthetic-stage-0", "synthetic-stage-0"]
                )
            )
        )
        self.assertFalse(report["pass"])
        self.assertIn(
            "family_scope expected_stage_ids contains duplicates",
            report["errors"],
        )

    def test_pinned_exact_scope_type_mismatch_fails_closed(self) -> None:
        manifest = json.loads(self.write_manifest(family_scope=self.exact_scope()).read_text(encoding="utf-8"))
        manifest["target_hw_op_types"] = ["RequantizeUint8"]
        path = self.root / "artifacts/synthetic/family_set_type_mismatch.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        report = self.audit(path)
        self.assertFalse(report["pass"])
        self.assertIn(
            "family_scope stage hw type is outside target_hw_op_types: synthetic-stage-0: MaxPoolUint8",
            report["errors"],
        )

    def test_pinned_exact_scope_extra_cross_family_stage_fails_closed(self) -> None:
        self.add_foreign_shared_primitive()
        contract = json.loads(self.case.contract_path.read_text(encoding="utf-8"))
        contract["stage_ids"].append("foreign-stage")
        self.case.contract_path.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest_path = self.write_manifest(family_scope=self.exact_scope())
        report = self.audit(manifest_path)
        self.assertFalse(report["pass"])
        self.assertEqual(report["unexpected_stage_ids"], ["foreign-stage"])

    def test_pinned_exact_scope_lowering_sha_drift_fails_closed(self) -> None:
        scope = self.exact_scope()
        scope["lowering_sha256"] = "0" * 64
        report = self.audit(self.write_manifest(family_scope=scope))
        self.assertFalse(report["pass"])
        self.assertIn("family_scope lowering SHA mismatch", "\n".join(report["errors"]))

    def test_pinned_exact_scope_stage_id_drift_fails_closed(self) -> None:
        report = self.audit(
            self.write_manifest(
                stage_contracts=False,
                family_scope=self.exact_scope(["renamed-stage"]),
            )
        )
        self.assertFalse(report["pass"])
        self.assertIn(
            "family_scope expected stage is absent from lowering: renamed-stage",
            report["errors"],
        )

    def test_legacy_manifest_retains_explicit_compatibility_mode(self) -> None:
        report = self.audit(self.write_manifest())
        self.assertTrue(report["pass"], msg=json.dumps(report, indent=2))
        self.assertEqual(report["scope_mode"], "LEGACY_HW_OP_TYPE_SELECTOR")
        self.assertTrue(report["legacy_scope_compatibility"])
        self.assertTrue(report["migration_recommended"])

    def test_matmul_exact_scope_requested_positive_and_negative_controls(self) -> None:
        self.configure_matmul_shared_primitive_fixture()
        target_types = ["MatMulInt32Accumulate", "RequantizeUint8"]

        positive_scope = self.exact_scope(
            ["hwop-0075-00", "hwop-0075-01"]
        )
        positive = self.audit(
            self.write_manifest(
                family_scope=positive_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertTrue(positive["pass"], msg=json.dumps(positive, indent=2))
        self.assertEqual(positive["expected_stage_count"], 2)

        self.case.contract["stage_ids"] = ["hwop-0075-00"]
        self.case.contract_path = self.case.flush_contract()
        missing = self.audit(
            self.write_manifest(
                family_scope=positive_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertEqual(missing["missing_stage_ids"], ["hwop-0075-01"])

        self.case.contract["stage_ids"] = ["hwop-0075-00", "hwop-0075-01"]
        self.case.contract_path = self.case.flush_contract()
        duplicate_scope = self.exact_scope(
            ["hwop-0075-00", "hwop-0075-00", "hwop-0075-01"]
        )
        duplicate = self.audit(
            self.write_manifest(
                family_scope=duplicate_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertIn(
            "family_scope expected_stage_ids contains duplicates",
            duplicate["errors"],
        )

        type_mismatch = self.audit(
            self.write_manifest(
                family_scope=positive_scope,
                target_hw_op_types=["MatMulInt32Accumulate"],
            )
        )
        self.assertIn(
            "family_scope stage hw type is outside target_hw_op_types: "
            "hwop-0075-01: RequantizeUint8",
            type_mismatch["errors"],
        )

        self.case.contract["stage_ids"] = [
            "hwop-0075-00",
            "hwop-0075-01",
            "hwop-0001-01",
        ]
        self.case.contract_path = self.case.flush_contract()
        extra = self.audit(
            self.write_manifest(
                family_scope=positive_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertEqual(extra["unexpected_stage_ids"], ["hwop-0001-01"])

        self.case.contract["stage_ids"] = ["hwop-0075-00", "hwop-0075-01"]
        self.case.contract_path = self.case.flush_contract()
        sha_drift_scope = json.loads(json.dumps(positive_scope))
        sha_drift_scope["lowering_sha256"] = "0" * 64
        sha_drift = self.audit(
            self.write_manifest(
                family_scope=sha_drift_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertIn(
            "family_scope lowering SHA mismatch",
            "\n".join(sha_drift["errors"]),
        )

        id_drift_scope = self.exact_scope(
            ["hwop-0075-00", "hwop-0075-renamed"]
        )
        id_drift = self.audit(
            self.write_manifest(
                family_scope=id_drift_scope,
                target_hw_op_types=target_types,
            )
        )
        self.assertIn(
            "family_scope expected stage is absent from lowering: "
            "hwop-0075-renamed",
            id_drift["errors"],
        )


if __name__ == "__main__":
    unittest.main()
