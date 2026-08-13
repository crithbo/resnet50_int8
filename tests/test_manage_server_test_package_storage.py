from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tools.manage_server_test_package_storage import (
    StorageError,
    apply_manifest,
    audit,
    compact_pending,
    flatten_pending,
    io_path,
    path_is_file,
    rotate,
)


def write_package(root: Path, base: str, payload: bytes = b"zip") -> None:
    zip_path = root / f"{base}.zip"
    zip_path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (root / f"{base}.zip.sha256").write_text(
        f"{digest}  {base}.zip\n", encoding="utf-8"
    )
    (root / f"{base}.validation.json").write_text("{}\n", encoding="utf-8")


class PackageStorageTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows long-path regression")
    def test_rotate_supports_extended_length_pending_receipts(self) -> None:
        temporary = tempfile.mkdtemp()
        root = Path(temporary)
        try:
            staging = root / "staging"
            staging.mkdir()
            package_base = "pkg_" + "x" * 136
            write_package(staging, package_base, b"long-path-package")
            evidence = staging / f"{package_base}.validation.json"
            receipt = (
                root
                / "pending_receipts"
                / "family_a"
                / package_base
                / evidence.name
            )
            self.assertGreater(len(str(receipt)), 260)

            result = rotate(
                root=root,
                source_dir=staging,
                family="family_a",
                new_base=package_base,
                previous_disposition=None,
                previous_reason=None,
                previous_evidence=None,
                new_reason="long_path_release",
                new_evidence=evidence,
            )

            self.assertEqual(
                result["pending_by_family"]["family_a"], [package_base]
            )
            self.assertTrue(path_is_file(receipt))
            self.assertTrue(audit(root)["pass"])
        finally:
            if root.exists():
                shutil.rmtree(str(io_path(root)))

    def test_manifest_moves_all_artifacts_and_preserves_one_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_old")
            write_package(root, "pkg_new")
            manifest = root / "migration.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "server_test_package_storage_migration_v1",
                        "packages": [
                            {
                                "family": "family_a",
                                "package_base": "pkg_old",
                                "disposition": "tested",
                                "reason": "formal_return_consumed",
                            },
                            {
                                "family": "family_a",
                                "package_base": "pkg_new",
                                "disposition": "pending",
                                "reason": "current_release",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = apply_manifest(root, manifest)
            self.assertEqual(result["counts"]["pending"], 1)
            self.assertEqual(result["counts"]["tested"], 1)
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_new/pkg_new.validation.json"
                ).is_file()
            )
            self.assertTrue((root / "pending/pkg_new.zip").is_file())
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_new/pkg_new.zip.sha256"
                ).is_file()
            )
            self.assertEqual(
                sorted(path.name for path in (root / "pending").iterdir()),
                ["pkg_new.zip"],
            )
            self.assertFalse((root / "pkg_new.zip").exists())

    def test_multiple_pending_for_one_family_fails_before_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_a")
            write_package(root, "pkg_b")
            manifest = root / "migration.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "server_test_package_storage_migration_v1",
                        "packages": [
                            {
                                "family": "family_a",
                                "package_base": "pkg_a",
                                "disposition": "pending",
                                "reason": "current",
                            },
                            {
                                "family": "family_a",
                                "package_base": "pkg_b",
                                "disposition": "pending",
                                "reason": "also_current",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(StorageError):
                apply_manifest(root, manifest)
            self.assertTrue((root / "pkg_a.zip").is_file())
            self.assertTrue((root / "pkg_b.zip").is_file())

    def test_sidecar_mismatch_fails_before_move(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_bad")
            (root / "pkg_bad.zip.sha256").write_text("0" * 64, encoding="utf-8")
            manifest = root / "migration.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "server_test_package_storage_migration_v1",
                        "packages": [
                            {
                                "family": "family_a",
                                "package_base": "pkg_bad",
                                "disposition": "pending",
                                "reason": "current",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(StorageError):
                apply_manifest(root, manifest)
            self.assertTrue((root / "pkg_bad.zip").is_file())

    def test_audit_rejects_flat_package_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_flat")
            with self.assertRaises(StorageError):
                audit(root)

    def test_rotate_requires_evidence_and_archives_previous(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_old")
            migration = root / "migration.json"
            migration.write_text(
                json.dumps(
                    {
                        "schema": "server_test_package_storage_migration_v1",
                        "packages": [
                            {
                                "family": "family_a",
                                "package_base": "pkg_old",
                                "disposition": "pending",
                                "reason": "current",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            apply_manifest(root, migration)
            staging = root / "staging"
            staging.mkdir()
            write_package(staging, "pkg_new", b"new")
            previous_evidence = root / "return_report.json"
            previous_evidence.write_text("{}\n", encoding="utf-8")
            new_evidence = root / "release_report.json"
            new_evidence.write_text("{}\n", encoding="utf-8")
            result = rotate(
                root=root,
                source_dir=staging,
                family="family_a",
                new_base="pkg_new",
                previous_disposition="tested",
                previous_reason="formal_return_consumed",
                previous_evidence=previous_evidence,
                new_reason="current_release",
                new_evidence=new_evidence,
            )
            self.assertEqual(result["pending_by_family"]["family_a"], ["pkg_new"])
            self.assertTrue((root / "tested/family_a/pkg_old/pkg_old.zip").is_file())
            self.assertTrue((root / "pending/pkg_new.zip").is_file())
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_new/pkg_new.validation.json"
                ).is_file()
            )
            self.assertTrue(audit(root)["pass"])

    def test_rotate_tracks_evidence_that_moves_with_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "pkg_old")
            migration = root / "migration.json"
            migration.write_text(
                json.dumps(
                    {
                        "schema": "server_test_package_storage_migration_v1",
                        "packages": [
                            {
                                "family": "family_a",
                                "package_base": "pkg_old",
                                "disposition": "pending",
                                "reason": "current",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            apply_manifest(root, migration)
            previous_evidence = (
                root
                / "pending_receipts/family_a/pkg_old/pkg_old.validation.json"
            )
            previous_digest = hashlib.sha256(
                previous_evidence.read_bytes()
            ).hexdigest()

            staging = root / "staging"
            staging.mkdir()
            write_package(staging, "pkg_new", b"new")
            new_evidence = staging / "pkg_new.validation.json"
            new_digest = hashlib.sha256(new_evidence.read_bytes()).hexdigest()

            result = rotate(
                root=root,
                source_dir=staging,
                family="family_a",
                new_base="pkg_new",
                previous_disposition="tested",
                previous_reason="formal_return_consumed",
                previous_evidence=previous_evidence,
                new_reason="current_release",
                new_evidence=new_evidence,
            )

            packages = {
                entry["package_base"]: entry for entry in result["packages"]
            }
            archived_path = Path(packages["pkg_old"]["evidence"]["path"])
            published_path = Path(packages["pkg_new"]["evidence"]["path"])
            self.assertEqual(
                archived_path,
                root / "tested/family_a/pkg_old/pkg_old.validation.json",
            )
            self.assertEqual(
                published_path,
                root
                / "pending_receipts/family_a/pkg_new/pkg_new.validation.json",
            )
            self.assertTrue(archived_path.is_file())
            self.assertTrue(published_path.is_file())
            self.assertEqual(
                packages["pkg_old"]["evidence"]["sha256"],
                previous_digest,
            )
            self.assertEqual(
                packages["pkg_new"]["evidence"]["sha256"],
                new_digest,
            )
            self.assertTrue(audit(root)["pass"])

    def test_flatten_pending_migrates_legacy_tree_to_short_pickup_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy_dir = root / "pending/family_a/pkg_old"
            legacy_dir.mkdir(parents=True)
            write_package(legacy_dir, "pkg_old")
            index = {
                "schema": "server_test_package_storage_index_v1",
                "packages": [
                    {
                        "family": "family_a",
                        "package_base": "pkg_old",
                        "disposition": "pending",
                        "reason": "current_release",
                        "evidence": None,
                    }
                ],
            }
            (root / "PACKAGE_STORAGE_INDEX.json").write_text(
                json.dumps(index), encoding="utf-8"
            )
            result = flatten_pending(root)
            self.assertTrue(result["pass"])
            self.assertTrue((root / "pending/pkg_old.zip").is_file())
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_old/pkg_old.zip.sha256"
                ).is_file()
            )
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_old/pkg_old.validation.json"
                ).is_file()
            )
            self.assertFalse((root / "pending/family_a").exists())

    def test_compact_pending_moves_sidecar_out_of_pickup_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pending = root / "pending"
            pending.mkdir()
            write_package(pending, "pkg_old")
            (pending / "pkg_old.validation.json").unlink()
            index = {
                "schema": "server_test_package_storage_index_v1",
                "packages": [
                    {
                        "family": "family_a",
                        "package_base": "pkg_old",
                        "disposition": "pending",
                        "reason": "current_release",
                        "evidence": None,
                    }
                ],
            }
            (root / "PACKAGE_STORAGE_INDEX.json").write_text(
                json.dumps(index), encoding="utf-8"
            )
            result = compact_pending(root)
            self.assertTrue(result["pass"])
            self.assertEqual(
                sorted(path.name for path in pending.iterdir()),
                ["pkg_old.zip"],
            )
            self.assertTrue(
                (
                    root
                    / "pending_receipts/family_a/pkg_old/pkg_old.zip.sha256"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
