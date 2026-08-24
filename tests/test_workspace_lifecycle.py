from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.manage_workspace_lifecycle import (
    LifecycleError,
    build_reports,
    purge_quarantine,
    quarantine_exact,
    sha256,
    verify_quarantine,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts/workspace_lifecycle_policy_v1.json"
SCHEMA = ROOT / "schemas/workspace_lifecycle_v1.schema.json"


def write(path: Path, value: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class WorkspaceLifecycleTests(unittest.TestCase):
    def make_root(self, base: Path) -> Path:
        root = base / "project"
        write(root / ".agents/plan.md", "current `outputs/current_run/receipt.json`\n")
        write(root / ".agents/task_records/history.md", "evidence outputs/old_run/report.json\n")
        write(root / "outputs/current_run/receipt.json", "{}")
        write(root / "outputs/current_run/build/live.bin", "live")
        write(root / "outputs/old_run/report.json", "{}")
        write(root / "outputs/old_run/build/generated.bin", "generated")
        write(root / "outputs/old_run/tmp_tests/cache.bin", "cache")
        write(root / "outputs/old_run/package.zip", "same-size")
        write(root / "outputs/old_run/package.repeat.zip", "same-size")
        write(root / "outputs/unknown_run/data.bin", "unknown")
        write(root / ".pytest_cache/cache", "cache")
        write(root / ".venv/pyvenv.cfg", "home = python")
        storage_root = root / "artifacts/operator_config_validation/r5-server-test-packages"
        write(storage_root / "pending/p.zip", "package")
        write(storage_root / "pending_receipts/f/p/p.zip.sha256", "not-consumed-by-test")
        storage = {
            "schema": "server_test_package_storage_index_v1",
            "packages": [
                {
                    "family": "f",
                    "package_base": "p",
                    "disposition": "pending",
                    "files": [
                        {"relative_path": "pending/p.zip"},
                        {"relative_path": "pending_receipts/f/p/p.zip.sha256"},
                    ],
                }
            ],
        }
        write(storage_root / "PACKAGE_STORAGE_INDEX.json", json.dumps(storage))
        registry = {
            "schema": "session-owner-registry-v1",
            "registry_epoch": 7,
            "roles": [
                {
                    "role_id": "family.f",
                    "current_task": {"pointer": {"path": "outputs/current_run/receipt.json"}},
                    "in_flight": {"package": {"path": "artifacts/operator_config_validation/r5-server-test-packages/pending/p.zip"}},
                }
            ],
        }
        write(root / "contracts/current_session_owner_registry_v1.json", json.dumps(registry))
        return root

    def reports(self, root: Path):
        return build_reports(root, POLICY)

    def test_current_output_root_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, _, plan, _ = self.reports(self.make_root(Path(raw)))
            entry = next(item for item in plan["candidates"] if item["path"] == "outputs/current_run/build")
            self.assertEqual(entry["safety_state"], "PROTECTED")

    def test_ephemeral_cache_is_safe_to_quarantine_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, _, plan, _ = self.reports(self.make_root(Path(raw)))
            entry = next(item for item in plan["candidates"] if item["path"] == ".pytest_cache")
            self.assertEqual(entry["safety_state"], "SAFE_TO_QUARANTINE_AFTER_REVIEW")

    def test_derived_tree_with_referenced_report_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, _, plan, _ = self.reports(self.make_root(Path(raw)))
            entry = next(item for item in plan["candidates"] if item["path"] == "outputs/old_run/build")
            self.assertEqual(entry["safety_state"], "REVIEW_REQUIRED")

    def test_repeat_zip_defers_hash_until_apply(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, _, plan, _ = self.reports(self.make_root(Path(raw)))
            entry = next(item for item in plan["candidates"] if item["path"].endswith("package.repeat.zip"))
            self.assertEqual(entry["safety_state"], "DUPLICATE_CONFIRMATION_REQUIRED")
            self.assertTrue(entry["same_size"])
            self.assertIn("hash this pair only at apply time", entry["requirements"])

    def test_managed_pending_is_in_protected_set(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, protected, _, _ = self.reports(self.make_root(Path(raw)))
            entry = next(item for item in protected["entries"] if item["path"].endswith("pending/p.zip"))
            self.assertTrue(any("managed storage pending" in reason for reason in entry["reasons"]))

    def test_unknown_legacy_is_not_silently_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, _, _, unknown = self.reports(self.make_root(Path(raw)))
            self.assertTrue(any(item["path"] == "outputs/unknown_run" for item in unknown["entries"]))

    def test_first_version_is_dry_run_only_and_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            reports = self.reports(self.make_root(Path(raw)))
            self.assertFalse(reports[2]["apply_authorized"])
            self.assertEqual(reports[2]["mode"], "DRY_RUN_ONLY")
            try:
                import jsonschema
            except ImportError:
                return
            schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
            for report in reports:
                jsonschema.validate(report, schema)

    def test_cli_accepts_only_scan_plan_and_writes_no_apply_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = self.make_root(base)
            output = base / "report"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/manage_workspace_lifecycle.py"),
                    "scan-plan",
                    "--state-root",
                    str(root),
                    "--policy",
                    str(POLICY),
                    "--output-dir",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads((output / "deletion_plan.json").read_text(encoding="utf-8"))
            self.assertFalse(plan["apply_authorized"])
            self.assertFalse((output / "apply_receipt.json").exists())

    def test_exact_quarantine_verify_and_purge_flow(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = self.make_root(base)
            reports = self.reports(root)
            plan_path = base / "plan.json"
            plan_path.write_text(json.dumps(reports[2]), encoding="utf-8")
            approval = {
                "schema": "workspace-quarantine-approval-v1",
                "registry_epoch": 7,
                "dry_run_plan_sha256": sha256(plan_path),
                "approved_paths": [".pytest_cache"],
                "user_authorization": "unit test",
                "claim_boundary": "unit test only"
            }
            approval_path = base / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            quarantine_root = base / "quarantine"
            receipt_path = base / "receipt.json"
            receipt = quarantine_exact(
                state_root=root,
                plan_path=plan_path,
                approval_path=approval_path,
                quarantine_root=quarantine_root,
                receipt_path=receipt_path,
            )
            self.assertTrue(receipt["pass"])
            self.assertFalse((root / ".pytest_cache").exists())
            self.assertTrue((quarantine_root / ".pytest_cache").is_dir())
            verification_path = base / "verification.json"
            verification = verify_quarantine(
                state_root=root, receipt_path=receipt_path, output_path=verification_path
            )
            self.assertTrue(verification["pass"])
            purge_path = base / "purge.json"
            purge = purge_quarantine(
                receipt_path=receipt_path,
                verification_path=verification_path,
                output_path=purge_path,
                confirm="PERMANENT_DELETE_APPROVED_QUARANTINE",
            )
            self.assertTrue(purge["pass"])
            self.assertFalse((quarantine_root / ".pytest_cache").exists())

    def test_quarantine_rejects_unapproved_or_wrong_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = self.make_root(base)
            plan = self.reports(root)[2]
            plan_path = base / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            approval = {
                "schema": "workspace-quarantine-approval-v1",
                "registry_epoch": 8,
                "dry_run_plan_sha256": sha256(plan_path),
                "approved_paths": ["outputs/unknown_run"],
                "user_authorization": "negative",
                "claim_boundary": "negative"
            }
            approval_path = base / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "epoch drift"):
                quarantine_exact(
                    state_root=root,
                    plan_path=plan_path,
                    approval_path=approval_path,
                    quarantine_root=base / "quarantine",
                    receipt_path=base / "receipt.json",
                )

    def test_purge_requires_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            receipt = base / "receipt.json"
            verification = base / "verification.json"
            write(receipt, "{}")
            write(verification, "{}")
            with self.assertRaisesRegex(LifecycleError, "confirmation token"):
                purge_quarantine(
                    receipt_path=receipt,
                    verification_path=verification,
                    output_path=base / "purge.json",
                    confirm="NO",
                )


if __name__ == "__main__":
    unittest.main()
