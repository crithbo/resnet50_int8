from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.audit_current_pending_one_return_matrix import audit


class CurrentPendingOneReturnMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = (
            self.root
            / "artifacts/operator_config_validation/r5-server-test-packages"
        )
        (self.storage / "pending").mkdir(parents=True)
        (self.root / ".agents/task_records").mkdir(parents=True)
        self.base = "synthetic_v1"
        self.zip_path = self.storage / "pending" / f"{self.base}.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            archive.writestr("synthetic/contract.json", '{"token":"EDGE_A"}')
        self.record = self.root / ".agents/task_records/20260807_synthetic.md"
        self.record.write_text(
            f"{self.base} PACKAGE_READY_NOT_RUN TERMINAL\n", encoding="utf-8"
        )
        self.index = self.storage / "PACKAGE_STORAGE_INDEX.json"
        self.index.write_text(
            json.dumps(
                {
                    "schema": "server_test_package_storage_index_v1",
                    "pass": True,
                    "packages": [
                        {
                            "family": "synthetic",
                            "disposition": "pending",
                            "package_base": self.base,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.contract = {
            "schema": "current-pending-one-return-matrix-v1",
            "source_state": {
                "storage_index_sha256": self.sha(self.index),
                "serialized_conv_v60_disposition": "NOT_APPLICABLE",
            },
            "packages": [
                {
                    "family": "synthetic",
                    "package_base": self.base,
                    "zip_sha256": self.sha(self.zip_path),
                    "task_record": ".agents/task_records/20260807_synthetic.md",
                    "task_record_sha256": self.sha(self.record),
                    "evidence_members": ["synthetic/contract.json"],
                    "scope": "FIRST_DIVERGENCE",
                    "candidates": [
                        {
                            "candidate_id": "A",
                            "distinguished_by": ["edge_a"],
                            "decision": "EDGE_A decides A",
                            "evidence_tokens": ["EDGE_A"],
                        },
                        {
                            "candidate_id": "B",
                            "distinguished_by": ["terminal"],
                            "decision": "TERMINAL decides B",
                            "evidence_tokens": ["TERMINAL"],
                        },
                    ],
                    "deferred_after_this_return": [],
                }
            ],
            "claim_boundary": "read-only",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_complete_matrix_passes(self) -> None:
        report = audit(self.root, self.contract)
        self.assertTrue(report["pass"])
        self.assertEqual(report["families"][0]["covered_candidate_count"], 2)

    def test_missing_evidence_token_fails(self) -> None:
        self.contract["packages"][0]["candidates"][0][
            "evidence_tokens"
        ].append("ABSENT")
        report = audit(self.root, self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("evidence tokens missing" in item for item in report["errors"]))

    def test_duplicate_signature_fails(self) -> None:
        first = self.contract["packages"][0]["candidates"][0]
        second = self.contract["packages"][0]["candidates"][1]
        second["distinguished_by"] = list(first["distinguished_by"])
        second["decision"] = first["decision"]
        report = audit(self.root, self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("duplicate decision signature" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
