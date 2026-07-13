from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sync_repositories import (
    RepositoryLockError,
    load_lock,
    sync_repository,
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
        "private_mirror": None,
        "branch": "main",
        "commit": commit,
        "dirty": False,
        "dirty_paths": [],
    }


class RepositorySyncTests(unittest.TestCase):
    def test_project_lock_and_schema_describe_the_same_contract(self) -> None:
        repositories = load_lock(PROJECT_ROOT / "repos.lock.json")
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "repositories_lock.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema_version"]["const"], "0.2")
        required = set(schema["properties"]["repositories"]["items"]["required"])
        self.assertEqual(required, set(repositories[0]))
        self.assertEqual({item["name"] for item in repositories}, {
            "CGRA_SIM",
            "ndp-sim-ref",
            "NDPFuncModel",
        })

    def test_load_lock_rejects_path_escape_and_version_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {
                "schema_version": "0.2",
                "repositories": [record("repo", "0" * 40, "https://example.invalid/repo.git")],
            }
            value["repositories"][0]["path"] = "../escape"
            path = root / "repos.lock.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "direct child"):
                load_lock(path)
            value["schema_version"] = "0.1"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(RepositoryLockError, "unsupported"):
                load_lock(path)

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

    def test_sync_prefers_private_mirror_for_private_commit(self) -> None:
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
            private_commit = git(source, "rev-parse", "HEAD")
            private = root / "private.git"
            subprocess.run(
                ["git", "clone", "--bare", str(source), str(private)],
                cwd=root,
                check=True,
                capture_output=True,
            )
            item = record("checkout", private_commit, upstream.as_uri())
            item["private_mirror"] = private.as_uri()
            state = sync_repository(root, item)
            self.assertEqual(state.head, private_commit)
            self.assertIn(private.as_uri(), state.remotes)
            self.assertIn(upstream.as_uri(), state.remotes)


if __name__ == "__main__":
    unittest.main()
