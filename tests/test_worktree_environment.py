from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexWorktreeEnvironmentTests(unittest.TestCase):
    def test_project_config_uses_auto_review_without_full_access(self) -> None:
        with (ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)

        self.assertEqual(config["approval_policy"], "on-request")
        self.assertEqual(config["approvals_reviewer"], "auto_review")
        self.assertEqual(config["sandbox_mode"], "workspace-write")
        self.assertTrue(config["sandbox_workspace_write"]["network_access"])
        self.assertNotEqual(config["sandbox_mode"], "danger-full-access")

    def test_worktree_include_is_small_metadata_only(self) -> None:
        entries = [
            line.strip()
            for line in (ROOT / ".worktreeinclude").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            entries,
            [
                "artifacts/w3/legacy77_mapping.json",
                "artifacts/w3/model_graph.json",
            ],
        )
        self.assertFalse(any(".npy" in entry for entry in entries))
        self.assertFalse(any(entry in {".venv", "artifacts"} for entry in entries))

    def test_nested_w3_manifest_snapshots_are_tracked_small_and_frozen(self) -> None:
        specifications = {
            "contracts/w3_metadata/golden_batch16_manifest.json.base64": (
                170131,
                "f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180",
            ),
            "contracts/w3_metadata/subop_batch16_manifest.json.base64": (
                49674,
                "8bfdd042570408c1df793044407a8e6262bfa261b3cc6f02f64b94ad47d9c1c2",
            ),
        }
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT}",
                "ls-files",
                "--error-unmatch",
                *specifications,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(set(completed.stdout.splitlines()), set(specifications))
        for relative_path, (expected_size, expected_hash) in specifications.items():
            payload = base64.b64decode((ROOT / relative_path).read_text(encoding="ascii"))
            self.assertEqual(len(payload), expected_size)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), expected_hash)

    def test_setup_script_validates_included_metadata_without_copying_w3(self) -> None:
        script = (ROOT / "tools" / "setup_codex_worktree.ps1").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Copy-Item", script)
        self.assertNotIn("New-Item -ItemType Junction", script)
        self.assertIn("managed worktree dependency setup is disabled", script)
        self.assertIn("worktree metadata is missing; check .worktreeinclude", script)

    @unittest.skipUnless(sys.platform == "win32", "PowerShell setup is Windows-only")
    def test_setup_script_check_only_validates_the_current_checkout(self) -> None:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "tools" / "setup_codex_worktree.ps1"),
                "-WorktreeRoot",
                str(ROOT),
                "-CheckOnly",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            self.assertIn(
                "managed worktree dependency setup is disabled", completed.stderr
            )
            return
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "1.0")
        self.assertTrue(report["check_only"])
        self.assertEqual(report["repository_verify"], "not_run")
        self.assertEqual(
            [item["name"] for item in report["shared_paths"]],
            [".venv", "CGRA_SIM", "ndp-sim-ref", "NDPFuncModel"],
        )
        self.assertEqual(report["mode"], "local")
        self.assertTrue(
            all(item["status"] == "source" for item in report["shared_paths"])
        )
        self.assertTrue(all(item["status"] == "source" for item in report["metadata"]))


if __name__ == "__main__":
    unittest.main()
