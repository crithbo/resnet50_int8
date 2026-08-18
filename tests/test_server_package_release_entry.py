from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_package_pipeline import admit_release


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_package_release_admission_v1.schema.json"


class ServerPackageReleaseEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.zip_path = self.root / "candidate.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            archive.writestr("PREPARE_AND_RUN.sh", "#!/bin/sh\n")
        self.profile = {
            "schema": "server-package-build-profile-v1",
            "mode": "ACTIVE_PATCH_FIRST_CHANGED_SURFACE_V3",
            "package_id": "candidate",
            "family": "synthetic",
            "lifecycle": "PATCH_UNRUN_REVISION",
            "contract_valid": True,
            "gate_dispositions": [
                {"gate_id": "runner", "disposition": "blocking_applicable"},
                {"gate_id": "config", "disposition": "receipt_reuse"},
                {"gate_id": "style", "disposition": "record_only"},
                {"gate_id": "vcd", "disposition": "not_applicable"},
            ],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def results(self) -> dict:
        return {
            "schema": "server-package-gate-results-v1",
            "package_id": "candidate",
            "results": [
                {"gate_id": "runner", "pass": True, "errors": [], "warnings": []},
                {"gate_id": "style", "pass": False, "errors": ["cosmetic"], "warnings": []},
            ],
        }

    def test_active_release_positive_and_record_only_warning(self) -> None:
        report = admit_release(self.profile, self.results(), self.zip_path, self.root)
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["status"], "PACKAGE_READY_NOT_RUN")
        self.assertTrue(any("cosmetic" in item for item in report["warnings"]))
        if jsonschema is not None:
            jsonschema.validate(report, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_missing_blocking_result_fails(self) -> None:
        results = self.results()
        results["results"] = [item for item in results["results"] if item["gate_id"] != "runner"]
        report = admit_release(self.profile, results, self.zip_path, self.root)
        self.assertFalse(report["pass"])
        self.assertTrue(any("missing blocking" in item for item in report["errors"]))

    def test_failed_blocking_result_fails(self) -> None:
        results = self.results()
        results["results"][0] = {"gate_id": "runner", "pass": False, "errors": ["cannot launch"], "warnings": []}
        report = admit_release(self.profile, results, self.zip_path, self.root)
        self.assertTrue(any("cannot launch" in item for item in report["errors"]))

    def test_receipt_reuse_needs_no_fresh_result(self) -> None:
        report = admit_release(self.profile, self.results(), self.zip_path, self.root)
        reused = next(item for item in report["checked_gates"] if item["gate_id"] == "config")
        self.assertFalse(reused["fresh_result_supplied"])
        self.assertIsNone(reused["pass"])

    def test_corrupt_zip_fails(self) -> None:
        self.zip_path.write_bytes(b"not a zip")
        report = admit_release(self.profile, self.results(), self.zip_path, self.root)
        self.assertFalse(report["pass"])
        self.assertTrue(any("ZIP" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
