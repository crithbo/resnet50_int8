from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[1] / "tools/server_package_attempt_cleanup.py"
SPEC = importlib.util.spec_from_file_location("server_package_attempt_cleanup", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(tmp_path: Path) -> tuple[SimpleNamespace, Path]:
    package = "r5_n4_hw_v99b_lcdup_guarded"
    execution = "r123_456"
    attempt = "a456"
    parent = tmp_path / "install/codex_runs" / package
    run = parent / attempt
    boot = parent / f"bootstrap-{execution}"
    run.mkdir(parents=True)
    boot.mkdir()
    (run / "payload").write_text("owned", encoding="utf-8")
    (boot / ".codex_bootstrap_owner.json").write_text(json.dumps({"attempt_id": attempt, "execution_id": execution, "package_id": package}), encoding="utf-8")
    (parent / f".codex_owner.{attempt}.json").write_text(json.dumps({"attempt": attempt, "package_id": package}), encoding="utf-8")
    foreign = tmp_path / "install/codex_runs/foreign/sibling"
    foreign.mkdir(parents=True)
    (foreign / "keep").write_text("keep", encoding="utf-8")
    result = tmp_path / "simresult/return.zip"
    result.parent.mkdir()
    result.write_bytes(b"durable")
    args = SimpleNamespace(
        server_root=tmp_path, package_id=package, execution_id=execution, attempt_id=attempt,
        run_root=run, bootstrap_root=boot, return_zip=result,
    )
    return args, foreign / "keep"


class PackageAttemptCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.mkdtemp(prefix="attempt-cleanup-test-")
        self.root = Path(self.temporary)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_exact_cleanup_preserves_foreign_sibling(self) -> None:
        args, foreign = fixture(self.root)
        report = MODULE.cleanup(args)
        self.assertTrue(report["pass"])
        self.assertEqual(report["persistent_install_codex_runs_bytes_for_exact_attempt"], 0)
        self.assertEqual(foreign.read_text(encoding="utf-8"), "keep")

    def test_cleanup_rejects_path_drift(self) -> None:
        args, foreign = fixture(self.root)
        args.run_root = foreign.parent
        with self.assertRaisesRegex(MODULE.CleanupError, "identity differs"):
            MODULE.cleanup(args)


if __name__ == "__main__":
    unittest.main()
