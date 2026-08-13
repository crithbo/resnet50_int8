from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_fsdb_runtime_quiescence import (
    QuiescenceError,
    evaluate_quiescence,
    process_tree,
    validate_execution_identity,
    validate_heartbeat,
    waveform_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_fsdb_runtime_quiescence_v1.schema.json"
DISPATCH = ROOT / "contracts/server_fsdb_process_tree_quiescence_dispatch_v1.json"


def process_receipt(**updates):
    value = {
        "schema": "server-fsdb-runtime-quiescence-v1",
        "kind": "process_tree_receipt",
        "rule_id": "CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001",
        "package_id": "pkg",
        "execution_id": "exec",
        "attempt_id": "attempt",
        "attempt_root": "/attempt",
        "cwd": "/attempt/run",
        "start_new_session": True,
        "child_subreaper": {"enabled": True, "prctl": "PR_SET_CHILD_SUBREAPER", "value": 1},
        "root_pid": 100,
        "pgid": 100,
        "root_reaped": True,
        "remaining_owned_pids": [],
        "process_tree_quiescent": True,
        "heartbeat_source": {"path": "/attempt/run/sim.log", "bytes": 1, "sha256": "1" * 64},
        "heartbeat_output": {"path": "/attempt/evidence/heartbeat.jsonl", "bytes": 1, "sha256": "2" * 64},
        "pass": True,
        "errors": [],
        "claim_boundary": "test",
    }
    value.update(updates)
    return value


class FsdbRuntimeQuiescenceTests(unittest.TestCase):
    def test_process_tree_detects_escaped_descendant(self) -> None:
        rows = [
            {"pid": 100, "ppid": 1, "pgid": 100},
            {"pid": 101, "ppid": 100, "pgid": 100},
            {"pid": 102, "ppid": 101, "pgid": 777},
            {"pid": 200, "ppid": 1, "pgid": 200},
        ]
        tree = process_tree(rows, 100, 100)
        self.assertEqual(tree["owned_pids"], [100, 101, 102])
        self.assertEqual(tree["escaped_pids"], [102])
        self.assertEqual(tree["group_pids"], [100, 101])

    def test_process_group_members_remain_visible_after_root_exit(self) -> None:
        rows = [{"pid": 101, "ppid": 1, "pgid": 100}]
        tree = process_tree(rows, 100, 100)
        self.assertFalse(tree["root_present"])
        self.assertEqual(tree["group_pids"], [101])

    def heartbeat(self, path: Path, sim_times: list[int | None], step_seconds: int = 10) -> dict:
        rows = [
            {
                "sequence": index,
                "host_monotonic_ns": index * step_seconds * 1_000_000_000,
                "sim_time": value,
                "timescale": "1ps",
            }
            for index, value in enumerate(sim_times)
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return validate_heartbeat(path, 25)

    def test_heartbeat_distinguishes_sim_time_progress_and_plateau(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress = self.heartbeat(root / "progress.jsonl", [0, 10, 20, 30])
            self.assertEqual(progress["classification"], "SIM_TIME_PROGRESS_OBSERVED")
            plateau = self.heartbeat(root / "plateau.jsonl", [10, 10, 10, 10])
            self.assertTrue(plateau["plateau"])
            self.assertEqual(plateau["classification"], "HIGH_CPU_OR_HOST_LIVE_ZERO_SIM_TIME_PROGRESS")

    def test_first_observed_positive_time_is_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self.heartbeat(Path(directory) / "late-first-sample.jsonl", [10, 10])
            self.assertTrue(report["sim_time_progress_observed"])

    def test_execution_identity_rejects_shell_or_path_tokens(self) -> None:
        validate_execution_identity("pkg", "exec", "attempt")
        with self.assertRaises(QuiescenceError):
            validate_execution_identity("pkg", "exec", "../attempt")

    def test_noncontiguous_or_regressing_heartbeat_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text(
                '{"sequence":0,"host_monotonic_ns":1,"sim_time":10,"timescale":"1ps"}\n'
                '{"sequence":2,"host_monotonic_ns":2,"sim_time":9,"timescale":"1ps"}\n',
                encoding="utf-8",
            )
            report = validate_heartbeat(path, 10)
            self.assertEqual(report["classification"], "INVALID")
            self.assertGreaterEqual(len(report["errors"]), 2)

    def snapshot(self, root: Path, members: dict[str, bytes]) -> dict:
        wave_root = root / "run/sim_results"
        wave_root.mkdir(parents=True, exist_ok=True)
        for name, payload in members.items():
            (wave_root / name).write_bytes(payload)
        return waveform_snapshot(root)

    def test_stable_snapshot_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pre = self.snapshot(root, {"wave.fsdb": b"a", "wave.fsdb.chain": b"b"})
            post = waveform_snapshot(root)
            heartbeat = self.heartbeat(root / "heartbeat.jsonl", [0, 1, 2])
            report = evaluate_quiescence(process_receipt(), heartbeat, pre, post)
            self.assertTrue(report["pass"], report["errors"])
            if jsonschema is not None:
                jsonschema.validate(report, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_mutating_writer_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pre = self.snapshot(root, {"wave.fsdb": b"a"})
            (root / "run/sim_results/wave.fsdb").write_bytes(b"changed")
            post = waveform_snapshot(root)
            heartbeat = self.heartbeat(root / "heartbeat.jsonl", [0, 1])
            report = evaluate_quiescence(process_receipt(), heartbeat, pre, post)
            self.assertFalse(report["pass"])
            self.assertIn("changed between", " ".join(report["errors"]))
            self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")

    def test_s2_style_slock_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pre = self.snapshot(root, {"wave.fsdb": b"a", "wave.fsdb.slock": b""})
            heartbeat = self.heartbeat(root / "heartbeat.jsonl", [0, 1])
            report = evaluate_quiescence(process_receipt(), heartbeat, pre, waveform_snapshot(root))
            self.assertFalse(report["pass"])
            self.assertIn("slock", " ".join(report["errors"]))

    def test_orphan_process_fails_but_preserves_partial_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self.snapshot(root, {"wave.fsdb": b"partial"})
            heartbeat = self.heartbeat(root / "heartbeat.jsonl", [10, 10, 10, 10])
            report = evaluate_quiescence(
                process_receipt(root_reaped=False, remaining_owned_pids=[101], process_tree_quiescent=False),
                heartbeat,
                snapshot,
                snapshot,
            )
            self.assertFalse(report["pass"])
            self.assertIn("Raw FSDB", report["failure_isolation"])

    def test_no_simulation_time_advance_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self.snapshot(root, {"wave.fsdb": b"time-zero-only"})
            heartbeat = self.heartbeat(root / "heartbeat.jsonl", [0, 0, 0, 0])
            report = evaluate_quiescence(process_receipt(), heartbeat, snapshot, snapshot)
            self.assertFalse(report["pass"])
            self.assertIn("no same-attempt simulation-time advance", " ".join(report["errors"]))

    def test_dispatch_binds_real_s2_counterexample(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            dispatch["source_counterexample"]["return_sha256"],
            "cb66cf7fbffc2c09679c98d9a4a8497918c51264345bc9cc1d7ecc8daa91010b",
        )
        self.assertIn("wave.fsdb.slock", dispatch["source_counterexample"]["failure"])


if __name__ == "__main__":
    unittest.main()
