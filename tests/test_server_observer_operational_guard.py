from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "tools/server_observer_operational_guard.py"
SPEC = importlib.util.spec_from_file_location("observer_operational_guard", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ObserverOperationalGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.mkdtemp(prefix="observer-guard-test-")
        self.root = Path(self.temporary)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_watch_file_limit(self) -> None:
        attempt = self.root / "attempt"
        attempt.mkdir()
        watched = attempt / "events.jsonl"
        watched.write_bytes(b"x" * 10)
        with patch.object(MODULE.shutil, "disk_usage", return_value=SimpleNamespace(free=10_000)):
            report = MODULE.evaluate(watches=[("observer", watched, 10)], attempt_root=attempt, baseline_bytes=0, growth_limit_bytes=1000, disk_path=self.root, min_free_bytes=100)
        self.assertEqual(report["reason"], "WATCH_FILE_LIMIT:observer")

    def test_attempt_growth_limit(self) -> None:
        attempt = self.root / "attempt"
        attempt.mkdir()
        (attempt / "artifact").write_bytes(b"x" * 20)
        with patch.object(MODULE.shutil, "disk_usage", return_value=SimpleNamespace(free=10_000)):
            report = MODULE.evaluate(watches=[], attempt_root=attempt, baseline_bytes=0, growth_limit_bytes=20, disk_path=self.root, min_free_bytes=100)
        self.assertEqual(report["reason"], "ATTEMPT_GROWTH_LIMIT")

    def test_disk_reserve_limit(self) -> None:
        attempt = self.root / "attempt"
        attempt.mkdir()
        with patch.object(MODULE.shutil, "disk_usage", return_value=SimpleNamespace(free=99)):
            report = MODULE.evaluate(watches=[], attempt_root=attempt, baseline_bytes=0, growth_limit_bytes=20, disk_path=self.root, min_free_bytes=100)
        self.assertEqual(report["reason"], "DISK_FREE_RESERVE")

    def test_symlink_in_attempt_fails_closed(self) -> None:
        attempt = self.root / "attempt"
        attempt.mkdir()
        target = self.root / "foreign"
        target.write_text("foreign", encoding="utf-8")
        link = attempt / "link"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("host does not permit test symlinks")
        with self.assertRaises(MODULE.GuardError):
            MODULE.tree_bytes(attempt)


if __name__ == "__main__":
    unittest.main()
