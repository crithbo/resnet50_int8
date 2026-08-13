from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import bootstrap
from tools.sync_repositories import (
    RepositoryLockError,
    load_lock,
    load_lock_document,
    main,
    sync_repository,
    verify_external_evidence,
    verify_repository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def git(path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return completed.stdout.strip()


def make_repository(path: Path) -> str:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "test")
    git(path, "config", "user.email", "test@example.invalid")
    (path / "payload.txt").write_text("pinned\n", encoding="utf-8")
    git(path, "add", "payload.txt")
    git(path, "commit", "-m", "initial")
    return git(path, "rev-parse", "HEAD")


def make_directory_link(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def record(name: str, commit: str, upstream: str) -> dict[str, object]:
    return {
        "name": name,
        "path": name,
        "upstream": upstream,
        "mirror": None,
        "branch": "main",
        "commit": commit,
        "dirty": False,
        "dirty_paths": [],
    }


class RepositorySyncTests(unittest.TestCase):
    def test_bootstrap_syncs_all_locks_then_verifies_them(self) -> None:
        with patch(
            "bootstrap.repository_sync_main", side_effect=(0, 0)
        ) as repository_sync:
            self.assertEqual(bootstrap.main(), 0)
        self.assertEqual(repository_sync.call_count, 2)
        self.assertEqual(repository_sync.call_args_list[0].args[0][0], "sync")
        self.assertEqual(repository_sync.call_args_list[1].args[0][0], "verify")

    def test_bootstrap_stops_when_sync_fails(self) -> None:
        with patch("bootstrap.repository_sync_main", return_value=2) as repository_sync:
            self.assertEqual(bootstrap.main(), 2)
        repository_sync.assert_called_once()

    def test_project_lock_and_schema_describe_the_same_contract(self) -> None:
        lock = load_lock_document(PROJECT_ROOT / "repos.lock.json")
        repositories = list(lock.repositories)
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "repositories_lock.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.4")
        self.assertEqual(
            set(schema["required"]),
            {"schema_version", "repositories", "external_evidence"},
        )
        required = set(schema["properties"]["repositories"]["items"]["required"])
        self.assertEqual(required, set(repositories[0]))
        self.assertEqual({item["name"] for item in repositories}, {
            "CGRA_SIM",
            "ndp-sim-ref",
            "NDPFuncModel",
            "ndp-sim",
            "Trassic2.0_RTL",
        })
        self.assertEqual(len(lock.external_evidence), 1)
        evidence = lock.external_evidence[0]
        self.assertEqual(
            set(schema["properties"]["external_evidence"]["items"]["required"]),
            set(evidence),
        )
        state = verify_external_evidence(PROJECT_ROOT, evidence)
        self.assertEqual(
            state.source_commit, "e3bdebba95dec36ee8eba43caa92a326a88392cd"
        )
        self.assertEqual(
            state.sha256,
            "69505a527a53c25b0bb828b192aba991fba78e838a2429f9cb99d251b8a815aa",
        )

    def test_load_lock_rejects_path_escape_and_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {
                "schema_version": "0.4",
                "repositories": [record("repo", "0" * 40, "https://example.invalid/repo.git")],
                "external_evidence": [{}],
            }
            value["repositories"][0]["path"] = "../escape"
            path = root / "repos.lock.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "direct child"):
                load_lock(path)
            value["schema_version"] = "0.2"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "unsupported"):
                load_lock(path)

    def test_external_evidence_rejects_tampering_and_source_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "contracts" / "audit.json"
            path.parent.mkdir()
            snapshot = {
                "status": "candidate_unapproved",
                "source": {
                    "repository": "https://example.invalid/rtl.git",
                    "commit": "1" * 40,
                    "commit_required_for_all_evidence": True,
                },
                "approval": {
                    "approved": False,
                    "approval_artifact_created": False,
                },
            }
            payload = json.dumps(snapshot).encode("utf-8")
            path.write_bytes(payload)
            evidence = {
                "name": "rtl-audit",
                "path": "contracts/audit.json",
                "source_repository": "https://example.invalid/rtl.git",
                "source_commit": "1" * 40,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
                "status": "candidate_unapproved",
            }
            verify_external_evidence(root, evidence)

            path.write_bytes(payload + b"\n")
            with self.assertRaisesRegex(RepositoryLockError, "size mismatch"):
                verify_external_evidence(root, evidence)

            path.write_bytes(payload)
            evidence["source_commit"] = "2" * 40
            with self.assertRaisesRegex(RepositoryLockError, "embedded source"):
                verify_external_evidence(root, evidence)

    def test_fresh_checkout_can_verify_tracked_evidence_without_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "contracts" / "audit.json"
            path.parent.mkdir()
            snapshot = {
                "status": "candidate_unapproved",
                "source": {
                    "repository": "https://example.invalid/rtl.git",
                    "commit": "3" * 40,
                    "commit_required_for_all_evidence": True,
                },
                "approval": {
                    "approved": False,
                    "approval_artifact_created": False,
                },
            }
            payload = json.dumps(snapshot).encode("utf-8")
            path.write_bytes(payload)
            lock = {
                "schema_version": "0.4",
                "repositories": [
                    record("missing-reference-repo", "4" * 40, "https://example.invalid/ref.git")
                ],
                "external_evidence": [
                    {
                        "name": "rtl-audit",
                        "path": "contracts/audit.json",
                        "source_repository": "https://example.invalid/rtl.git",
                        "source_commit": "3" * 40,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size_bytes": len(payload),
                        "status": "candidate_unapproved",
                    }
                ],
            }
            (root / "repos.lock.json").write_text(json.dumps(lock), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = main(["verify", "--root", str(root), "--evidence-only"])
            self.assertEqual(result, 0)
            self.assertIn("3" * 40, output.getvalue())
            self.assertIn(hashlib.sha256(payload).hexdigest(), output.getvalue())

    def test_verify_checks_head_dirty_state_and_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            commit = make_repository(repository)
            upstream = "https://example.invalid/repo.git"
            git(repository, "remote", "add", "origin", upstream)
            state = verify_repository(root, record("repo", commit, upstream))
            self.assertEqual(state.head, commit)
            (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "dirty paths mismatch"):
                verify_repository(root, record("repo", commit, upstream))

    def test_verify_accepts_only_the_matching_local_checkout_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source_root = base / "source"
            worktree_root = base / "worktree"
            source_root.mkdir()
            worktree_root.mkdir()
            repository = source_root / "repo"
            commit = make_repository(repository)
            upstream = "https://example.invalid/repo.git"
            git(repository, "remote", "add", "origin", upstream)
            make_directory_link(worktree_root / "repo", repository)

            with patch(
                "tools.sync_repositories._source_checkout_root",
                return_value=source_root,
            ):
                state = verify_repository(
                    worktree_root, record("repo", commit, upstream)
                )
            self.assertEqual(state.path, repository.resolve())

            other_source = base / "other"
            other_source.mkdir()
            with patch(
                "tools.sync_repositories._source_checkout_root",
                return_value=other_source,
            ), self.assertRaisesRegex(RepositoryLockError, "does not match"):
                verify_repository(worktree_root, record("repo", commit, upstream))

            with self.assertRaisesRegex(RepositoryLockError, "refusing to sync shared"):
                sync_repository(worktree_root, record("repo", commit, upstream))

    def test_sync_clones_missing_repository_at_pinned_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            commit = make_repository(source)
            bare = root / "upstream.git"
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(bare)],
                cwd=root,
                check=True,
                capture_output=True,
            )
            item = record("checkout", commit, bare.as_uri())
            state = sync_repository(root, item)
            self.assertEqual(state.head, commit)
            self.assertEqual(git(state.path, "rev-parse", "HEAD"), commit)

    def test_sync_refuses_existing_dirty_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            commit = make_repository(repository)
            upstream = "https://example.invalid/repo.git"
            git(repository, "remote", "add", "origin", upstream)
            (repository / "payload.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "refusing to sync dirty"):
                sync_repository(root, record("repo", commit, upstream))

    def test_sync_prefers_mirror_for_mirrored_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            make_repository(source)
            upstream = root / "upstream.git"
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(upstream)],
                cwd=root,
                check=True,
                capture_output=True,
            )
            (source / "private.txt").write_text("private commit\n", encoding="utf-8")
            git(source, "add", "private.txt")
            git(source, "commit", "-m", "private")
            mirrored_commit = git(source, "rev-parse", "HEAD")
            mirror = root / "mirror.git"
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(mirror)],
                cwd=root,
                check=True,
                capture_output=True,
            )
            item = record("checkout", mirrored_commit, upstream.as_uri())
            item["mirror"] = mirror.as_uri()
            state = sync_repository(root, item)
            self.assertEqual(state.head, mirrored_commit)
            self.assertIn(mirror.as_uri(), state.remotes)
            self.assertIn(upstream.as_uri(), state.remotes)


if __name__ == "__main__":
    unittest.main()
