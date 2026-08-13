from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.validate_complete_operator_json_candidate import validate


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_SOURCE = (
    REPO_ROOT
    / "contracts/operator_config/complete_json_generation_contract_v1.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(root: Path, relative: str, value: Any) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def bound(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def exact_axes() -> dict[str, bool]:
    return {
        "op": True,
        "dtype": True,
        "shape": True,
        "layout": True,
        "qparams": True,
        "topology": True,
        "address": True,
        "schedule": True,
        "consumer": True,
    }


class CompleteJsonCase:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.family = "synthetic_maxpool"
        self.candidate = {"CONFIG": {"enabled": 1}, "loop": 4}
        self.source_path = write_json(
            root, "ndp-sim/jsons/native.json", self.candidate
        )
        self.handler_path = root / "ndp-sim/handler.py"
        self.handler_path.parent.mkdir(parents=True, exist_ok=True)
        self.handler_path.write_text(
            "# exact replay handler\n", encoding="utf-8", newline="\n"
        )
        self.receipt_path = write_json(
            root,
            "artifacts/synthetic/derivation_receipt.json",
            {"schema": "synthetic_receipt_v1", "pass": True},
        )
        self.current_path = write_json(
            root, "artifacts/synthetic/current.json", self.candidate
        )
        self.candidate_path = write_json(
            root, "artifacts/synthetic/complete_json/candidate.json", self.candidate
        )
        self.artifact_root = root / "artifacts/synthetic/complete_json"
        source_sha = sha256_file(self.source_path)
        self.source_commit = "a" * 40
        self.source_blob = "b" * 40
        self.authority = {
            "schema": "operator-config-user-authority-v1",
            "records": [
                {
                    "path": "ndp-sim/jsons/native.json",
                    "sha256": source_sha,
                    "provenance": {
                        "kind": "pinned_upstream_exact_blob",
                        "pinned_commit": self.source_commit,
                        "pinned_git_blob_oid": self.source_blob,
                    },
                }
            ],
        }
        self.authority_path = write_json(
            root,
            "contracts/operator_config/operator_config_authority_v1.json",
            self.authority,
        )
        self.policy_path = root / (
            "contracts/operator_config/complete_json_generation_contract_v1.json"
        )
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.policy_path.write_bytes(POLICY_SOURCE.read_bytes())
        self.lowering_path = write_json(
            root,
            "contracts/resnet50_r5_lowering_bundle.json",
            {
                "schema": "synthetic-lowering-v1",
                "coverage": {"stage_count": 1},
                "requests": [
                    {
                        "identity": {
                            "hw_op_id": "synthetic-stage-0",
                            "hw_op_type": "MaxPoolUint8",
                        }
                    }
                ],
            },
        )
        self.ledger = {
            "schema": "operator_config_field_provenance_ledger_v1",
            "family": self.family,
            "candidate_json_sha256": sha256_file(self.candidate_path),
            "entries": [
                self._reference_entry("/CONFIG/enabled", 1),
                self._reference_entry("/loop", 4),
            ],
            "source_absences": [],
            "claim_boundary": "Synthetic exact-replay field ledger.",
        }
        self.ledger_path = write_json(
            root,
            "artifacts/synthetic/complete_json/field_provenance_ledger.json",
            self.ledger,
        )
        self.handler = {
            "schema": "operator_config_handler_capability_v1",
            "family": self.family,
            "handler": {
                "kind": "NATIVE_COMPLETE",
                "path": "ndp-sim/handler.py",
                "sha256": sha256_file(self.handler_path),
                "source_span": "1:1-1:22",
            },
            "capabilities": {
                axis: {
                    "supported": axis == "exact_replay",
                    "evidence": (
                        "Synthetic exact replay positive control."
                        if axis == "exact_replay"
                        else "Not exercised by the exact-source instance."
                    ),
                }
                for axis in (
                    "exact_replay",
                    "shape",
                    "dtype",
                    "qparam",
                    "layout",
                    "address",
                    "cross_stage_schedule",
                )
            },
            "dependent_leaves": [],
            "claim_boundary": "Exact replay only.",
        }
        self.handler_path_json = write_json(
            root,
            "artifacts/synthetic/complete_json/handler_capability.json",
            self.handler,
        )
        self.diff = {
            "schema": "operator_config_current_test_diff_v1",
            "family": self.family,
            "candidate_json_sha256": sha256_file(self.candidate_path),
            "current_identity": {
                "available": True,
                "path": self.current_path.relative_to(root).as_posix(),
                "sha256": sha256_file(self.current_path),
                "package_or_record": "synthetic-current",
                "latest_result": "LOCAL_STATIC_ONLY",
            },
            "entries": [
                {
                    "json_pointer": "/CONFIG/enabled",
                    "candidate_value": 1,
                    "current_value_present": True,
                    "current_value": 1,
                    "classification": "SAME",
                    "reason": "Exact value equality.",
                    "evidence": ["candidate/current strict JSON"],
                },
                {
                    "json_pointer": "/loop",
                    "candidate_value": 4,
                    "current_value_present": True,
                    "current_value": 4,
                    "classification": "SAME",
                    "reason": "Exact value equality.",
                    "evidence": ["candidate/current strict JSON"],
                },
            ],
            "blocker_attribution": [
                {
                    "blocker_id": "SYNTHETIC_DYNAMIC_GATE",
                    "classification": "DYNAMIC_ONLY",
                    "candidate_json_pointers": [],
                    "reason": "No dynamic evidence is created by this validator.",
                    "evidence": ["synthetic boundary"],
                }
            ],
            "claim_boundary": "Static current-config comparison only.",
        }
        self.diff_path = write_json(
            root,
            "artifacts/synthetic/complete_json/current_test_diff.json",
            self.diff,
        )
        self.contract = {
            "schema": "operator_config_complete_json_candidate_v1",
            "family": self.family,
            "candidate_status": "COMPLETE",
            "reference_class": "A",
            "changed_axes": [],
            "target_hw_op_types": ["MaxPoolUint8"],
            "stage_ids": ["synthetic-stage-0"],
            "candidate_json": bound(root, self.candidate_path),
            "field_provenance_ledger": bound(root, self.ledger_path),
            "handler_capability": bound(root, self.handler_path_json),
            "current_test_diff": bound(root, self.diff_path),
            "composition": {"required": False, "boundary": None},
            "artifact_root": self.artifact_root.relative_to(root).as_posix(),
            "claim_boundary": "Synthetic local complete-JSON candidate.",
        }
        self.contract_path = self.flush_contract()

    def _reference_entry(self, pointer: str, value: Any) -> dict[str, Any]:
        return {
            "json_pointer": pointer,
            "target_value": value,
            "origin": "REFERENCE_EXACT",
            "applicability_class": "EXACT_SOURCE_INSTANCE",
            "exactness_axes": exact_axes(),
            "owner": "pinned native reference instance",
            "consumer_equation": "target leaf equals exact source leaf",
            "derivation_receipt": None,
            "source": {
                "path": "ndp-sim/jsons/native.json",
                "commit": self.source_commit,
                "blob_oid": self.source_blob,
                "file_sha256": sha256_file(self.source_path),
                "json_pointer": pointer,
                "value": value,
            },
            "negative_control_ids": [],
            "status": "RESOLVED",
        }

    def flush_ledger(self) -> None:
        self.ledger_path = write_json(
            self.root,
            self.ledger_path.relative_to(self.root).as_posix(),
            self.ledger,
        )
        self.contract["field_provenance_ledger"] = bound(
            self.root, self.ledger_path
        )

    def flush_handler(self) -> None:
        self.handler_path_json = write_json(
            self.root,
            self.handler_path_json.relative_to(self.root).as_posix(),
            self.handler,
        )
        self.contract["handler_capability"] = bound(
            self.root, self.handler_path_json
        )

    def flush_diff(self) -> None:
        self.diff_path = write_json(
            self.root,
            self.diff_path.relative_to(self.root).as_posix(),
            self.diff,
        )
        self.contract["current_test_diff"] = bound(self.root, self.diff_path)

    def flush_contract(self) -> Path:
        return write_json(
            self.root,
            "artifacts/synthetic/complete_json/candidate_contract.json",
            self.contract,
        )

    def run(self) -> dict[str, Any]:
        self.contract_path = self.flush_contract()
        return validate(
            workspace_root=self.root,
            contract_path=self.contract_path,
            authority_path=self.authority_path,
            policy_path=self.policy_path,
            lowering_path=self.lowering_path,
        )


class CompleteOperatorJsonCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = CompleteJsonCase(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_failed_with(self, report: dict[str, Any], needle: str) -> None:
        self.assertFalse(report["pass"])
        self.assertTrue(
            any(needle in error for error in report["errors"]),
            msg=json.dumps(report, indent=2),
        )

    def test_exact_source_instance_positive(self) -> None:
        report = self.case.run()
        self.assertTrue(report["pass"], msg=json.dumps(report, indent=2))
        self.assertEqual(report["candidate_leaf_count"], 2)
        self.assertEqual(report["ledger_leaf_count"], 2)
        self.assertEqual(report["current_diff_counts"], {"SAME": 2})
        self.assertEqual(report["forbidden_server_package_outputs"], [])

    def test_missing_candidate_leaf_fails_closed(self) -> None:
        self.case.ledger["entries"].pop()
        self.case.flush_ledger()
        report = self.case.run()
        self.assert_failed_with(report, "candidate leaves missing from ledger")

    def test_project_added_source_cannot_claim_native_authority(self) -> None:
        self.case.ledger["entries"][0]["source"]["path"] = (
            "ndp-sim/jsons/project_added.json"
        )
        self.case.flush_ledger()
        report = self.case.run()
        self.assert_failed_with(report, "source is not authorized")

    def test_placeholder_handler_cannot_generalize_shape(self) -> None:
        self.case.contract["reference_class"] = "B"
        self.case.contract["changed_axes"] = ["shape"]
        self.case.handler["handler"]["kind"] = "PLACEHOLDER"
        self.case.handler["capabilities"]["shape"]["supported"] = True
        self.case.handler["dependent_leaves"] = [
            {
                "json_pointer": "/loop",
                "axes": ["shape"],
                "covered_by": "placeholder handler",
                "status": "COVERED",
            }
        ]
        self.case.ledger["entries"][1]["exactness_axes"]["shape"] = False
        self.case.flush_ledger()
        self.case.flush_handler()
        report = self.case.run()
        self.assert_failed_with(report, "overclaims generalization capability")

    def test_complete_candidate_rejects_unknown_absent_field(self) -> None:
        self.case.ledger["source_absences"] = [
            {
                "target_json_pointer": "/missing_required_control",
                "state": "SOURCE_ABSENT_UNKNOWN_FOR_TARGET",
                "reason": "The source instance omits this target-required field.",
                "owner": "current encoder schema",
            }
        ]
        self.case.flush_ledger()
        report = self.case.run()
        self.assert_failed_with(
            report, "COMPLETE candidate has unknown absent source field"
        )

    def test_required_composition_boundary_cannot_be_omitted(self) -> None:
        self.case.contract["composition"] = {
            "required": True,
            "boundary": None,
        }
        report = self.case.run()
        self.assert_failed_with(
            report, "required composition boundary binding is missing"
        )

    def test_same_classification_requires_equal_current_value(self) -> None:
        self.case.diff["entries"][1]["current_value"] = 5
        self.case.flush_diff()
        report = self.case.run()
        self.assert_failed_with(report, "current diff bound value mismatch")

    def test_server_package_output_is_forbidden(self) -> None:
        forbidden = self.case.artifact_root / "candidate.zip"
        forbidden.write_bytes(b"not a package")
        report = self.case.run()
        self.assert_failed_with(report, "server-package outputs are forbidden")

    def test_blocked_candidate_reports_real_completion_blocker(self) -> None:
        self.case.contract["candidate_status"] = "BLOCKED"
        entry = self.case.ledger["entries"][1]
        entry["origin"] = "UNRESOLVED"
        entry["applicability_class"] = "UNRESOLVED"
        entry["status"] = "UNRESOLVED"
        entry["source"] = None
        self.case.flush_ledger()
        report = self.case.run()
        self.assertFalse(report["pass"])
        self.assertTrue(report["contract_valid"], msg=json.dumps(report, indent=2))
        self.assertTrue(report["blocked_valid"], msg=json.dumps(report, indent=2))
        self.assertEqual(report["errors"], [])
        self.assertIn(
            "unresolved candidate leaf: /loop",
            report["completion_blockers"],
        )


if __name__ == "__main__":
    unittest.main()
