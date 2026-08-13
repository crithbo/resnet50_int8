from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

from tools.build_current_family_pointer import build_pointer


SCHEMA = Path("schemas/current_family_pointer_v1.schema.json")
REGISTRY = Path("contracts/current_family_pointer_registry_v1.json")


class CurrentFamilyPointerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package_root = (
            self.root
            / "artifacts/operator_config_validation/r5-server-test-packages"
        )
        (self.package_root / "pending").mkdir(parents=True)
        (self.root / ".agents/task_records").mkdir(parents=True)
        (self.root / ".agents").mkdir(exist_ok=True)
        self.package_base = "r5_n4_hw_v60_install_only"
        self.zip_path = self.package_root / "pending" / f"{self.package_base}.zip"
        self.zip_path.write_bytes(b"exact zip")
        digest = hashlib.sha256(self.zip_path.read_bytes()).hexdigest()
        self.index = self.package_root / "PACKAGE_STORAGE_INDEX.json"
        self.index.write_text(
            json.dumps(
                {
                    "schema": "server_test_package_storage_index_v1",
                    "pass": True,
                    "pending_by_family": {
                        "conv_serialized_node0004": [self.package_base]
                    },
                    "packages": [
                        {
                            "disposition": "pending",
                            "family": "conv_serialized_node0004",
                            "package_base": self.package_base,
                            "pickup_zip": f"pending/{self.package_base}.zip",
                            "reason": "PACKAGE_READY_NOT_RUN",
                            "files": [
                                {
                                    "relative_path": f"pending/{self.package_base}.zip",
                                    "bytes": self.zip_path.stat().st_size,
                                    "sha256": digest,
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.record = (
            self.root
            / ".agents/task_records"
            / "20260807_conv_node0004_v59_hold_to_v60_release.md"
        )
        self.record.write_text(
            f"PACKAGE_READY_NOT_RUN {self.package_base}\n", encoding="utf-8"
        )
        self.plan = self.root / ".agents/plan.md"
        self.plan.write_text("stale r5_n4_hw_v49\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> dict:
        return build_pointer(
            self.root,
            self.index,
            self.root / ".agents/task_records",
            self.plan,
            REGISTRY.resolve(),
        )

    def test_pointer_uses_storage_and_exact_package_record(self) -> None:
        result = self.build()
        self.assertTrue(result["pass"])
        self.assertEqual(result["families"][0]["package_base"], self.package_base)
        self.assertFalse(result["plan_coherence"]["pass"])
        self.assertEqual(
            result["plan_coherence"]["missing_current_package_tokens"],
            [self.package_base],
        )
        jsonschema.validate(result, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_plan_drift_does_not_invalidate_pointer(self) -> None:
        result = self.build()
        self.assertTrue(result["pass"])
        self.assertTrue(result["plan_coherence"]["drift_is_report_only"])

    def test_duplicate_pending_fails_closed(self) -> None:
        data = json.loads(self.index.read_text(encoding="utf-8"))
        data["packages"].append(dict(data["packages"][0]))
        self.index.write_text(json.dumps(data), encoding="utf-8")
        result = self.build()
        self.assertFalse(result["pass"])
        self.assertTrue(any("pending package count" in item for item in result["errors"]))

    def test_record_must_bind_exact_package(self) -> None:
        self.record.write_text("PACKAGE_READY_NOT_RUN other.zip\n", encoding="utf-8")
        result = self.build()
        self.assertFalse(result["pass"])
        self.assertTrue(any("no task record binds" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
