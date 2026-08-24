from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.prepare_project_migration import build, plan


def git(root: Path, *args: str) -> None:
    result = subprocess.run(["git", "-c", f"safe.directory={root}", "-C", str(root), *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(result.stderr)


class PrepareProjectMigrationTests(unittest.TestCase):
    def make_repo(self, base: Path) -> Path:
        root = base / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "test@example.invalid")
        git(root, "config", "user.name", "Migration Test")
        (root / "contracts").mkdir()
        (root / "artifacts/operator_config_validation/r5-server-test-packages").mkdir(parents=True)
        (root / "contracts/current_session_owner_registry_v1.json").write_text(json.dumps({"registry_epoch": 1, "mainline_role_id": "mainline.control", "roles": [{"role_id": "mainline.control"}]}), encoding="utf-8")
        (root / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json").write_text(json.dumps({"packages": [{"package_base": "p", "disposition": "pending"}]}), encoding="utf-8")
        (root / "requirements-resnet50.lock.txt").write_text("x==1\n", encoding="utf-8")
        (root / "source.py").write_text("print('ok')\n", encoding="utf-8")
        (root / ".gitignore").write_text("outputs/\n.venv/\n", encoding="utf-8")
        (root / "outputs").mkdir()
        (root / "outputs/ignored.bin").write_bytes(b"ignored")
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        return root

    def test_plan_requires_clean_git(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = self.make_repo(Path(raw))
            clean = plan(root)
            self.assertTrue(clean["ready_for_build"])
            (root / "source.py").write_text("dirty\n", encoding="utf-8")
            dirty = plan(root)
            self.assertFalse(dirty["ready_for_build"])
            self.assertEqual(dirty["git"]["status_count"], 1)

    def test_build_creates_verified_bundle_and_source_archive(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = self.make_repo(base)
            manifest = plan(root)
            receipt = build(root, base / "handoff", manifest)
            self.assertTrue(receipt["pass"], receipt)
            self.assertTrue(receipt["bundle_verify_pass"])
            self.assertEqual(receipt["archive_forbidden_members"], [])
            with zipfile.ZipFile(receipt["source_archive"]["path"]) as archive:
                self.assertIn("source.py", archive.namelist())
                self.assertNotIn("outputs/ignored.bin", archive.namelist())

    def test_build_excludes_intentionally_tracked_output_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = self.make_repo(base)
            tracked = root / "outputs/tracked_receipt.json"
            tracked.write_text("{}\n", encoding="utf-8")
            git(root, "add", "-f", "outputs/tracked_receipt.json")
            git(root, "commit", "-m", "track historical output receipt")
            manifest = plan(root)
            receipt = build(root, base / "handoff", manifest)
            self.assertTrue(receipt["pass"], receipt)
            with zipfile.ZipFile(receipt["source_archive"]["path"]) as archive:
                self.assertNotIn("outputs/tracked_receipt.json", archive.namelist())


if __name__ == "__main__":
    unittest.main()
