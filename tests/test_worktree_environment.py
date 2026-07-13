from __future__ import annotations

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
                "artifacts/w3/golden_batch16/manifest.json",
                "artifacts/w3/subop_batch16/manifest.json",
            ],
        )
        self.assertFalse(any(".npy" in entry for entry in entries))
        self.assertFalse(any(entry in {".venv", "artifacts"} for entry in entries))

    def test_setup_script_validates_included_metadata_without_copying_w3(self) -> None:
        script = (ROOT / "tools" / "setup_codex_worktree.ps1").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Copy-Item", script)
        self.assertIn("$destinationItem.Target", script)
        self.assertIn("worktree metadata is missing; check .worktreeinclude", script)

    @unittest.skipUnless(sys.platform == "win32", "PowerShell setup is Windows-only")
    def test_setup_script_check_only_validates_the_source_checkout(self) -> None:
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
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["schema_version"], "1.0")
        self.assertEqual(report["mode"], "local")
        self.assertTrue(report["check_only"])
        self.assertEqual(report["repository_verify"], "not_run")
        self.assertEqual(
            [item["name"] for item in report["shared_paths"]],
            [".venv", "CGRA_SIM", "ndp-sim-ref", "NDPFuncModel"],
        )
        self.assertTrue(all(item["status"] == "source" for item in report["shared_paths"]))
        self.assertTrue(all(item["status"] == "source" for item in report["metadata"]))


if __name__ == "__main__":
    unittest.main()
