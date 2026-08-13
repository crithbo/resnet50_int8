from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/validate_server_runner_return_resilience.py"
SCHEMA = ROOT / "schemas/server_runner_return_resilience_v1.schema.json"
FIXTURES = ROOT / "fixtures/server_runner_return_resilience_v1"

SPEC = importlib.util.spec_from_file_location("runner_resilience", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RunnerReturnResilienceTests(unittest.TestCase):
    def load(self, name: str):
        root = FIXTURES / name
        contract = json.loads((root / "contract.json").read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], schema["properties"]["schema"]["const"])
        self.assertTrue(set(schema["required"]).issubset(contract))
        return root, contract

    def test_positive_exact_runner_passes(self):
        root, contract = self.load("positive")
        report = MODULE.validate_tree(root, root / "contract.json")
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(report["definition_before_use"]["unsafe_uses"], [])
        self.assertEqual(report["causal_mapping"], ["server_start", "return"])

    def test_v57d_unbound_shape_fails_closed(self):
        root, _ = self.load("negative_unbound")
        report = MODULE.validate_tree(root, root / "contract.json")
        self.assertFalse(report["pass"])
        self.assertTrue(any("run_root" in item for item in report["errors"]))

    def test_compilefail_missing_evidence_is_aggregated(self):
        root, _ = self.load("negative_compile_evidence")
        report = MODULE.validate_tree(root, root / "contract.json")
        self.assertFalse(report["pass"])
        joined = "\n".join(report["errors"])
        self.assertIn("compile evidence token absent: argv", joined)
        self.assertIn("compile evidence token absent: source_identity", joined)
        self.assertIn("compile evidence token absent: first_error", joined)
        self.assertGreaterEqual(len(report["errors"]), 6)

    def test_attempt_root_bootstrap_and_late_finalizer_fail(self):
        root, _ = self.load("negative_attempt_root")
        report = MODULE.validate_tree(root, root / "contract.json")
        self.assertFalse(report["pass"])
        joined = "\n".join(report["errors"])
        self.assertIn("run_root", joined)
        self.assertIn("finalizer is armed after first fallible action", joined)

    def test_exact_final_zip_is_rechecked(self):
        root, _ = self.load("positive")
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.write(root / "contract.json", "contract.json")
                archive.write(root / "PREPARE_AND_RUN.sh", "PREPARE_AND_RUN.sh")
            report = MODULE.validate_zip(zip_path, "contract.json")
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(report["zip"]["runner_member"], "PREPARE_AND_RUN.sh")

    def test_final_zip_post_contract_mutation_fails(self):
        root, _ = self.load("positive")
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "package.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.write(root / "contract.json", "contract.json")
                archive.writestr("PREPARE_AND_RUN.sh", "#!/bin/bash\nset -u\n")
            report = MODULE.validate_zip(zip_path, "contract.json")
            self.assertFalse(report["pass"])
            self.assertIn("exact runner sha256 mismatch", report["errors"])


if __name__ == "__main__":
    unittest.main()

