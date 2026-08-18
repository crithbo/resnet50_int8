from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "tools" / "server_observer_operational_guard_v2.py"
VALIDATOR_PATH = ROOT / "tools" / "validate_server_observer_operational_guard_v2.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_module("operational_guard_v2", RUNTIME_PATH)
VALIDATOR = load_module("operational_guard_v2_validator", VALIDATOR_PATH)


class OperationalGuardV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.mkdtemp(prefix="observer-operational-guard-v2-")
        self.root = Path(self.temporary).resolve()
        self.attempt = self.root / "attempt"
        self.attempt.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _symlink(self, link: Path, target: Path | str) -> bool:
        try:
            link.symlink_to(target)
        except OSError:
            return False
        return True

    class _FakeScandir:
        def __init__(self, entries):
            self.entries = entries

        def __enter__(self):
            return iter(self.entries)

        def __exit__(self, _kind, _value, _traceback):
            return False

    class _FakeEntry:
        def __init__(self, path: Path, mode: int, size: int = 0):
            self.path = str(path)
            self.name = path.name
            self._stat = SimpleNamespace(st_mode=mode, st_size=size)

        def stat(self, *, follow_symlinks: bool):
            if follow_symlinks:
                raise AssertionError("live-tree scan must never follow symlinks")
            return self._stat

    def test_mocked_internal_symlink_contract_is_platform_independent(self) -> None:
        link = self.attempt / "simv.daidir" / "vcs_link"
        entry = self._FakeEntry(link, stat.S_IFLNK | 0o777, size=8)
        with patch.object(RUNTIME.os, "scandir", return_value=self._FakeScandir([entry])), patch.object(
            RUNTIME.os, "readlink", return_value="../csrc/object.o"
        ):
            snapshot = RUNTIME._scan_owned_roots_once([self.attempt])
        self.assertEqual(snapshot["bytes"], 8)
        self.assertEqual(snapshot["entries"][0]["entry_type"], "symlink_no_follow")

    def test_mocked_escaping_symlink_contract_fails_platform_independent(self) -> None:
        link = self.attempt / "escape"
        entry = self._FakeEntry(link, stat.S_IFLNK | 0o777, size=8)
        with patch.object(RUNTIME.os, "scandir", return_value=self._FakeScandir([entry])), patch.object(
            RUNTIME.os, "readlink", return_value=str(self.root.parent / "foreign")
        ):
            with self.assertRaises(RUNTIME.GuardError):
                RUNTIME._scan_owned_roots_once([self.attempt])

    def test_vcs_style_internal_symlink_is_recorded_without_following(self) -> None:
        target = self.attempt / "csrc" / "link_object.o"
        target.parent.mkdir()
        target.write_bytes(b"object")
        link = self.attempt / "simv.daidir" / "link_object.o"
        link.parent.mkdir()
        if not self._symlink(link, Path("../csrc/link_object.o")):
            self.test_mocked_internal_symlink_contract_is_platform_independent()
            return
        receipt = RUNTIME.snapshot_owned_roots([self.attempt])
        regular = [item for item in receipt["entries"] if item["entry_type"] == "regular"]
        links = [item for item in receipt["entries"] if item["entry_type"] == "symlink_no_follow"]
        self.assertEqual(len(regular), 1)
        self.assertEqual(len(links), 1)
        self.assertFalse(receipt["symlink_targets_traversed"])
        self.assertEqual(links[0]["link_target"], "../csrc/link_object.o")

    def test_symlink_target_escape_fails_closed(self) -> None:
        foreign = self.root / "foreign"
        foreign.write_text("foreign", encoding="utf-8")
        if not self._symlink(self.attempt / "escape", foreign):
            self.test_mocked_escaping_symlink_contract_fails_platform_independent()
            return
        with self.assertRaises(RUNTIME.GuardError):
            RUNTIME.snapshot_owned_roots([self.attempt])

    def test_internal_link_cleanup_unlinks_entry_without_deleting_target(self) -> None:
        target = self.attempt / "csrc" / "object.o"
        target.parent.mkdir()
        target.write_text("object", encoding="utf-8")
        link = self.attempt / "simv.daidir" / "object.o"
        link.parent.mkdir()
        if not self._symlink(link, Path("../csrc/object.o")):
            return
        receipt = RUNTIME.unlink_exact_owned_link_entry(link, [self.attempt])
        self.assertTrue(receipt["unlinked"])
        self.assertFalse(receipt["target_traversed"])
        self.assertFalse(link.exists())
        self.assertTrue(target.is_file())

    def test_mocked_link_cleanup_is_nofollow_and_platform_independent(self) -> None:
        link = self.attempt / "simv.daidir" / "object.o"
        real_lstat = os.lstat

        def fake_lstat(path):
            if RUNTIME._absolute_lexical(Path(path)) == RUNTIME._absolute_lexical(link):
                return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_size=8)
            return real_lstat(path)

        with patch.object(
            RUNTIME.os, "lstat", side_effect=fake_lstat
        ), patch.object(RUNTIME.os, "readlink", return_value="../csrc/object.o"), patch.object(
            RUNTIME.os, "unlink"
        ) as unlink:
            receipt = RUNTIME.unlink_exact_owned_link_entry(link, [self.attempt])
        unlink.assert_called_once_with(RUNTIME._absolute_lexical(link))
        self.assertFalse(receipt["target_traversed"])

    def test_transient_disappearing_file_is_resampled(self) -> None:
        (self.attempt / "stable").write_text("stable", encoding="utf-8")
        original = RUNTIME._scan_owned_roots_once
        calls = {"count": 0}

        def flaky(roots):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RUNTIME.LiveTreeRace("temporary compiler file vanished")
            return original(roots)

        with patch.object(RUNTIME, "_scan_owned_roots_once", side_effect=flaky):
            receipt = RUNTIME.snapshot_owned_roots([self.attempt], max_resamples=2, resample_delay_seconds=0)
        self.assertEqual(receipt["resample_count"], 1)
        self.assertEqual(calls["count"], 2)

    def test_proc_stat_parser_preserves_comm_and_start_time(self) -> None:
        # field 22 (starttime) is the twentieth token after the closing ')'.
        value = "321 (vcs worker) name) S 7 321 321 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 987654 0\n"
        row = RUNTIME.parse_proc_stat(value)
        self.assertEqual(row["pid"], 321)
        self.assertEqual(row["ppid"], 7)
        self.assertEqual(row["comm"], "vcs worker) name")
        self.assertEqual(row["start_time_ticks"], 987654)

    def test_procfs_snapshot_does_not_spawn_self_enumerator(self) -> None:
        proc_root = self.root / "proc"
        stat_dir = proc_root / "123"
        stat_dir.mkdir(parents=True)
        stat_dir.joinpath("stat").write_text(
            "123 (simv) S 1 123 123 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 42 0\n",
            encoding="utf-8",
        )
        with patch.object(RUNTIME.subprocess, "Popen", side_effect=AssertionError("no child enumerator")):
            rows = RUNTIME.ps_table(proc_root)
        self.assertEqual([(row["pid"], row["start_time_ticks"]) for row in rows], [(123, 42)])

    def test_owned_processes_keeps_real_child_and_rejects_reused_pid_seed(self) -> None:
        guard_pid = RUNTIME.os.getpid()
        rows = [
            {"pid": 100, "ppid": guard_pid, "pgid": 100, "sid": 100, "stat": "S", "comm": "simv", "start_time_ticks": 10},
            {"pid": 101, "ppid": 100, "pgid": 100, "sid": 100, "stat": "S", "comm": "worker", "start_time_ticks": 20},
            # Same PID as a stale known key, different start time: it must not
            # inherit ownership through that stale identity.
            {"pid": 202, "ppid": 1, "pgid": 202, "sid": 202, "stat": "S", "comm": "foreign", "start_time_ticks": 99},
        ]
        with patch.object(RUNTIME, "ps_table", return_value=rows):
            owned = RUNTIME.owned_processes((100, 10), 100, {(202, 88)})
        self.assertEqual([(row["pid"], row["start_time_ticks"]) for row in owned], [(100, 10), (101, 20)])

    def test_signal_owned_skips_pid_identity_drift(self) -> None:
        row = {"pid": 101, "ppid": 1, "pgid": 999, "sid": 999, "stat": "S", "comm": "worker", "start_time_ticks": 20}
        with patch.object(RUNTIME, "owned_processes", return_value=[row]), patch.object(
            RUNTIME, "identity_matches", return_value=False
        ), patch.object(RUNTIME.os, "kill") as kill:
            receipt = RUNTIME.signal_owned(None, 100, set(), RUNTIME.signal.SIGTERM)
        kill.assert_not_called()
        self.assertEqual(receipt["identity_drift_skipped"], [{"pid": 101, "start_time_ticks": 20}])

    def test_short_successful_guarded_command_preserves_child_exit_zero(self) -> None:
        receipt_path = self.attempt / "short.json"
        args = SimpleNamespace(
            attempt_root=self.attempt,
            owned_root=[],
            receipt=receipt_path,
            log=self.attempt / "short.log",
            disk_path=self.attempt,
            timeout=5.0,
            interval=0.01,
            grace=0.1,
            growth_limit_bytes=10_000_000,
            min_free_bytes=1,
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            cwd=self.attempt,
            max_resamples=1,
            resample_delay=0.0,
            watch=[],
            package_id="pkg",
            execution_id="exec",
            attempt_id="attempt",
            mode="compile",
        )
        with patch.object(RUNTIME.sys, "platform", "linux"), patch.object(
            RUNTIME, "enable_child_subreaper", return_value={"enabled": True, "primitive": "TEST"}
        ), patch.object(RUNTIME, "read_proc_row", return_value=None), patch.object(
            RUNTIME, "owned_processes", return_value=[]
        ):
            receipt, exit_code = RUNTIME.supervise(args)
        self.assertEqual(exit_code, 0)
        self.assertEqual(receipt["child_exit"], 0)
        self.assertEqual(receipt["failure_classification"], "GUARDED_COMMAND_EXIT")
        self.assertTrue(receipt["process_fully_reaped"])
        self.assertTrue(RUNTIME.validate_receipt(receipt)["pass"])

    def test_emergency_monitor_exception_reaps_and_publishes_stderr(self) -> None:
        receipt_path = self.attempt / "guard_receipt.json"
        stderr_path = self.attempt / "guard.stderr.log"
        called = {"count": 0}

        def terminate():
            called["count"] += 1
            return {
                "actions": [{"signal": "SIGTERM"}],
                "root_exit": 143,
                "reaped_pids": [12],
                "owned_pids_remaining": [],
                "owned_process_identities_remaining": [],
                "process_tree_reaped": True,
            }

        receipt = RUNTIME.emergency_finalize(
            receipt_path=receipt_path,
            stderr_path=stderr_path,
            base_receipt={
                "schema": RUNTIME.SCHEMA,
                "package_id": "pkg",
                "execution_id": "exec",
                "attempt_id": "attempt",
                "phase": "compile",
                "command_started": True,
                "child_pid": 11,
                "child_process_identity": {"pid": 11, "start_time_ticks": 1},
                "process_identity_model": {
                    "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
                    "identity_fields": ["pid", "start_time_ticks"],
                    "pid_reuse_protection": True,
                    "self_enumerator_child_process": False,
                },
                "samples": [],
            },
            error=RUNTIME.GuardError("injected monitor exception"),
            terminate=terminate,
        )
        self.assertEqual(called["count"], 1)
        self.assertTrue(receipt_path.is_file())
        self.assertIn("OPERATIONAL_GUARD_MONITOR_EXCEPTION", stderr_path.read_text(encoding="utf-8"))
        self.assertTrue(receipt["process_fully_reaped"])
        self.assertFalse(receipt["production_compile_error_claim_allowed"])
        self.assertTrue(RUNTIME.validate_receipt(receipt)["pass"])

    def test_surviving_child_fails_receipt(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_monitor_exception_receipt.json").read_text(encoding="utf-8"))
        fixture["process_fully_reaped"] = False
        fixture["termination"]["process_tree_reaped"] = False
        fixture["termination"]["owned_pids_remaining"] = [1002]
        report = VALIDATOR.validate_receipt(fixture)
        self.assertFalse(report["pass"])
        self.assertTrue(any("reaped" in error or "non-empty" in error for error in report["errors"]))

    def test_exit_two_without_receipt_is_not_compile_error(self) -> None:
        report = VALIDATOR.classify_exit(2, None)
        self.assertTrue(report["pass"])
        self.assertEqual(report["classification"]["classification"], "GUARD_RECEIPT_MISSING_INFRASTRUCTURE_FAILURE")
        self.assertFalse(report["classification"]["production_compile_error"])

    def test_valid_guarded_compile_child_exit_can_be_compile_error(self) -> None:
        receipt = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_monitor_exception_receipt.json").read_text(encoding="utf-8"))
        receipt.update({
            "monitor_exception": None,
            "stop_count": 0,
            "guard_triggered": False,
            "stop_reason": None,
            "failure_classification": "GUARDED_COMMAND_EXIT",
            "production_compile_error_claim_allowed": True,
            "diagnostic_status": "COMPLETE",
            "pass": True,
        })
        path = self.attempt / "receipt.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        report = VALIDATOR.classify_exit(2, path)
        self.assertTrue(report["pass"], report)
        self.assertTrue(report["classification"]["production_compile_error"])

    def test_repeated_stop_fails_closed(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_monitor_exception_receipt.json").read_text(encoding="utf-8"))
        fixture["stop_count"] = 2
        report = VALIDATOR.validate_receipt(fixture)
        self.assertFalse(report["pass"])

    def test_live_tree_policy_positive_and_traversal_negative(self) -> None:
        policy = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_live_tree_policy.json").read_text(encoding="utf-8"))
        self.assertTrue(VALIDATOR.validate_policy(policy)["pass"])
        policy["symlink_target_traversal"] = True
        report = VALIDATOR.validate_policy(policy)
        self.assertFalse(report["pass"])
        self.assertTrue(any("symlink_target_traversal" in error for error in report["errors"]))

    def test_failure_handoff_preserves_unique_returns_before_cleanup(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_failure_handoff.json").read_text(encoding="utf-8"))
        self.assertTrue(VALIDATOR.validate_failure_handoff(fixture)["pass"])

        overwritten = json.loads(json.dumps(fixture))
        overwritten["published_returns"][0]["path"] = overwritten["published_returns"][1]["path"]
        self.assertFalse(VALIDATOR.validate_failure_handoff(overwritten)["pass"])

        premature_cleanup = json.loads(json.dumps(fixture))
        premature_cleanup["finalization_guard_receipt_valid"] = False
        self.assertFalse(VALIDATOR.validate_failure_handoff(premature_cleanup)["pass"])


if __name__ == "__main__":
    unittest.main()
