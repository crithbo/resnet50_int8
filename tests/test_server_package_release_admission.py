from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools.validate_server_package_release_admission import validate_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/server_package_release_admission_v1/package_template"
SCHEMA = ROOT / "schemas/server_package_release_admission_v1.schema.json"
HISTORICAL = ROOT / "fixtures/server_package_release_admission_v1/gap_v62_pending_manifest_escape.json"
PYTHON_SCHEMA_HISTORICAL = (
    ROOT
    / "fixtures/server_package_release_admission_v1/gap_v67_v68_python_schema_escapes.json"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class PackageReleaseAdmissionTests(unittest.TestCase):
    package_id = "synthetic_release_admission_pkg"
    claim = "Local package release only; no server or DUT claim."

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.staging = self.workspace / "staging" / self.package_id
        shutil.copytree(FIXTURE, self.staging)
        self.zip_path = self.workspace / "final" / f"{self.package_id}.zip"
        self.release_path = self.workspace / "receipts/release.json"
        self.failure_path = self.workspace / "receipts/precompile_failure_core.json"
        self.contract = {
            "schema": "server-package-release-admission-v1",
            "package": {
                "package_id": self.package_id,
                "family": "synthetic",
                "staging_root": f"staging/{self.package_id}",
                "final_zip": {"path": f"final/{self.package_id}.zip", "bytes": 1, "sha256": "0" * 64},
                "zip_root_member": self.package_id,
                "runner_member": "PREPARE_AND_RUN.sh",
            },
            "manifest": {
                "member": "TEST_PACKAGE_MANIFEST.json",
                "package_id_pointer": "/test_id",
                "status_pointer": "/status",
                "ready_status": "PACKAGE_READY_NOT_RUN",
                "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
            },
            "release_receipt": {
                "path": "receipts/release.json", "sha256": "0" * 64,
                "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass",
                "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary",
                "expected_claim_boundary": self.claim,
            },
            "runtime_preflight": {
                "runtime_member": "package_tools/package_runtime.py",
                "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"],
                "timeout_seconds": 30, "expected_exit": 0,
                "nonfinal_rejection_marker": "package claim boundary differs", "non_mutating": True,
            },
            "python_schema_runtime": {
                "package_python_source_suffixes": [".py"],
                "exact_set_compile": True,
                "compile_staging_and_clean_exact_zip": True,
                "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
                "schema_validation_enabled": True,
                "schema_dependency": "jsonschema",
                "missing_dependency_disposition": "FAIL_CLOSED",
                "skip_allowed": False,
            },
            "build_receipt_semantics": {
                "aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH",
                "positive_assertions": [
                    {"fact_id": "deterministic_rebuild", "observed": True, "required": True},
                    {"fact_id": "numeric_payload_equal", "observed": True, "required": True},
                ],
                "negative_observations": [
                    {"fact_id": "functional_rtl_modified", "observed": False, "required": False},
                    {"fact_id": "server_action", "observed": False, "required": False},
                ],
                "informational_facts": [{"fact_id": "attempt", "value": 3}],
            },
            "precompile_failure_core": {"path": "receipts/precompile_failure_core.json", "sha256": "0" * 64},
            "claim_boundary": "Synthetic shared release-admission control only.",
        }
        self.refresh_all()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def build_zip(self) -> None:
        self.zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(item for item in self.staging.rglob("*") if item.is_file()):
                archive.write(path, f"{self.package_id}/{path.relative_to(self.staging).as_posix()}")

    def refresh_receipts(self) -> None:
        zip_sha = sha(self.zip_path)
        self.contract["package"]["final_zip"].update({"bytes": self.zip_path.stat().st_size, "sha256": zip_sha})
        release = {
            "schema": "synthetic-package-release-v1", "package_id": self.package_id,
            "status": "PACKAGE_READY_NOT_RUN", "pass": True,
            "package": {"sha256": zip_sha}, "claim_boundary": self.claim,
        }
        write_json(self.release_path, release)
        self.contract["release_receipt"]["sha256"] = sha(self.release_path)
        failure = {
            "schema": "server-precompile-preflight-failure-core-v1",
            "package_id": self.package_id, "final_zip_sha256": zip_sha,
            "runner_member_sha256": sha(self.staging / "PREPARE_AND_RUN.sh"),
            "preflight": {"exit_code": 19, "stdout": "package claim boundary differs\n", "stderr": ""},
            "compile_started": False, "simulation_started": False,
            "core_return": {
                "published": True, "classification": "COMPILE_NOT_STARTED",
                "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"],
            },
            "claim_boundary": "Precompile failure visibility only.",
        }
        write_json(self.failure_path, failure)
        self.contract["precompile_failure_core"]["sha256"] = sha(self.failure_path)

    def refresh_all(self) -> None:
        self.build_zip()
        self.refresh_receipts()

    def report(self, contract: dict | None = None) -> dict:
        return validate_contract(contract or self.contract, self.workspace)

    def test_positive_staging_zip_preflight_and_schema(self) -> None:
        report = self.report()
        self.assertTrue(report["pass"], report)
        self.assertTrue(report["checks"]["staging_runtime_preflight"])
        self.assertTrue(report["checks"]["clean_zip_runtime_preflight"])
        self.assertTrue(report["checks"]["nonfinal_status_negative"])
        self.assertTrue(report["checks"]["schema_runtime_available"])
        self.assertTrue(report["checks"]["contract_schema_valid"])
        self.assertTrue(report["checks"]["package_python_exact_set"])
        self.assertTrue(report["checks"]["clean_zip_package_python_compile"])
        self.assertEqual(report["controls"]["runtime_preflight"]["nonfinal_status"]["exit_code"], 19)
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(self.contract, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_every_package_python_member_is_compiled_from_exact_zip(self) -> None:
        broken = self.staging / "package_tools" / "late_generated_helper.py"
        broken.write_text("def broken(:\n", encoding="utf-8")
        self.refresh_all()
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertFalse(report["checks"]["staging_package_python_compile"])
        self.assertFalse(report["checks"]["clean_zip_package_python_compile"])
        controls = report["controls"]["package_python_exact_set_compile"]
        self.assertIn(
            "package_tools/late_generated_helper.py",
            controls["clean_exact_zip_set"],
        )
        self.assertIn("late_generated_helper.py", "\n".join(report["errors"]))

    def test_python_compile_writes_no_bytecode_into_package(self) -> None:
        report = self.report()
        controls = report["controls"]["package_python_exact_set_compile"]
        self.assertTrue(controls["staging"]["package_tree_unchanged"])
        self.assertTrue(controls["clean_exact_zip"]["package_tree_unchanged"])
        self.assertFalse(controls["staging"]["bytecode_written_inside_package"])
        self.assertFalse(controls["clean_exact_zip"]["bytecode_written_inside_package"])
        self.assertFalse(
            any(path.name == "__pycache__" for path in self.staging.rglob("__pycache__"))
        )

    def test_schema_dependency_absence_fails_closed_instead_of_skip(self) -> None:
        real_import = __import__("importlib").import_module

        def missing_jsonschema(name: str, *args, **kwargs):
            if name == "jsonschema":
                raise ModuleNotFoundError("synthetic missing jsonschema")
            return real_import(name, *args, **kwargs)

        with mock.patch(
            "tools.validate_server_package_release_admission.importlib.import_module",
            side_effect=missing_jsonschema,
        ):
            report = self.report()
        self.assertFalse(report["pass"])
        self.assertFalse(report["checks"]["schema_runtime_available"])
        self.assertFalse(report["checks"]["contract_schema_valid"])
        self.assertIn("fail closed", "\n".join(report["errors"]))

    def test_schema_enabled_contract_cannot_request_skip(self) -> None:
        item = copy.deepcopy(self.contract)
        item["python_schema_runtime"]["skip_allowed"] = True
        report = self.report(item)
        self.assertFalse(report["pass"])
        self.assertFalse(report["checks"]["contract_schema_valid"])
        self.assertIn("skip_allowed", "\n".join(report["errors"]))

    def test_pending_manifest_cannot_be_released(self) -> None:
        manifest_path = self.staging / "TEST_PACKAGE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
        write_json(manifest_path, manifest)
        self.refresh_all()
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("package claim boundary differs", "\n".join(report["errors"]))
        self.assertFalse(report["checks"]["staging_runtime_preflight"])
        self.assertFalse(report["checks"]["clean_zip_runtime_preflight"])

    def test_real_gap_v62_pending_manifest_escape_is_registered(self) -> None:
        historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
        self.assertEqual(historical["package_id"], "r5_n71_gap_v62_sum_s2_tbvcd")
        self.assertEqual(historical["final_zip"]["sha256"], "9256c91dd13905ae8fe573e21d3676a353e92313a57c9d2715078e20df9232a9")
        self.assertEqual(historical["embedded_manifest"]["status"], "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES")
        self.assertEqual(historical["contradictory_release_receipt"]["status"], "PACKAGE_READY_NOT_RUN")
        self.assertFalse(historical["expected_shared_gate_result"]["pass"])
        self.assertEqual(historical["expected_shared_gate_result"]["required_error_substring"], "package claim boundary differs")

    def test_real_gap_v67_v68_python_schema_escapes_are_registered(self) -> None:
        historical = json.loads(PYTHON_SCHEMA_HISTORICAL.read_text(encoding="utf-8"))
        by_package = {
            item["package_id"]: item for item in historical["attempts"]
        }
        self.assertEqual(
            by_package["r5_n71_gap_v67_sum_s2_tbvcd_runtimev3ready"]["required_result"],
            "FAIL_CLOSED_BY_CLEAN_EXACT_ZIP_PY_COMPILE",
        )
        self.assertEqual(
            by_package["r5_n71_gap_v68_sum_s2_tbvcd_runtimev3fixed"]["required_result"],
            "FAIL_CLOSED_IF_JSONSCHEMA_UNAVAILABLE_OR_SKIPPED",
        )
        self.assertEqual(historical["positive_successor"]["python_member_count"], 19)
        self.assertEqual(historical["positive_successor"]["compiled_count"], 19)

    def test_status_negative_must_emit_exact_marker(self) -> None:
        runtime = self.staging / "package_tools/package_runtime.py"
        runtime.write_text(runtime.read_text(encoding="utf-8").replace("package claim boundary differs", "wrong marker"), encoding="utf-8")
        self.refresh_all()
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("did not fail closed", "\n".join(report["errors"]))

    def test_observed_false_is_not_a_positive_all_gate(self) -> None:
        report = self.report()
        self.assertTrue(report["checks"]["positive_assertions"])
        self.assertTrue(report["checks"]["negative_observation_polarity"])
        self.assertTrue(report["controls"]["build_receipt_semantics"]["naive_all_boolean_values_forbidden"])

    def test_wrong_positive_or_negative_polarity_fails(self) -> None:
        for section, value, expected in (
            ("positive_assertions", False, "positive build assertions"),
            ("negative_observations", True, "observed-negative fact polarity mismatch"),
        ):
            with self.subTest(section=section):
                item = copy.deepcopy(self.contract)
                item["build_receipt_semantics"][section][0]["observed"] = value
                report = self.report(item)
                self.assertFalse(report["pass"])
                self.assertIn(expected, "\n".join(report["errors"]))

    def test_duplicate_fact_id_and_command_contract_fail(self) -> None:
        item = copy.deepcopy(self.contract)
        item["build_receipt_semantics"]["negative_observations"][0]["fact_id"] = "deterministic_rebuild"
        item["runtime_preflight"]["command_template"][-1] = "{wrong_root}"
        report = self.report(item)
        self.assertFalse(report["pass"])
        errors = "\n".join(report["errors"])
        self.assertIn("fact IDs overlap", errors)
        self.assertIn("command template differs", errors)

    def test_precompile_core_requires_stdout_stderr_exit_and_identity(self) -> None:
        failure = json.loads(self.failure_path.read_text(encoding="utf-8"))
        del failure["preflight"]["stderr"]
        write_json(self.failure_path, failure)
        self.contract["precompile_failure_core"]["sha256"] = sha(self.failure_path)
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("does not retain preflight stderr", "\n".join(report["errors"]))

    def test_clean_exact_zip_drift_fails(self) -> None:
        (self.staging / "post_zip_drift.txt").write_text("drift", encoding="utf-8")
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("staging tree and clean exact-ZIP extraction differ", "\n".join(report["errors"]))

    def test_release_claim_cannot_outvote_package_bytes(self) -> None:
        release = json.loads(self.release_path.read_text(encoding="utf-8"))
        release["package"]["sha256"] = "f" * 64
        write_json(self.release_path, release)
        self.contract["release_receipt"]["sha256"] = sha(self.release_path)
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("release final ZIP identity differs", "\n".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()
