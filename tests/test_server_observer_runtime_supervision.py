from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "server_observer_runtime_supervision.py"
SPEC = importlib.util.spec_from_file_location("observer_runtime", TOOL_PATH)
assert SPEC and SPEC.loader
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class ObserverRuntimeSupervisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_heartbeat_progress_and_no_progress(self) -> None:
        path = self.root / "heartbeat.jsonl"
        path.write_text(
            "\n".join(json.dumps({"seq": seq, "host_monotonic_ns": seq + 1, "simulation_time": sim, "timescale": "1ps"}) for seq, sim in enumerate((0, 5))) + "\n",
            encoding="utf-8",
        )
        report = RUNTIME.validate_heartbeat_rows(path)
        self.assertTrue(report["pass"], report)
        self.assertTrue(report["simulation_time_progress_observed"])
        path.write_text(json.dumps({"seq": 0, "host_monotonic_ns": 1, "simulation_time": 0, "timescale": "1ps"}) + "\n", encoding="utf-8")
        self.assertFalse(RUNTIME.validate_heartbeat_rows(path)["simulation_time_progress_observed"])

    def test_heartbeat_sequence_and_host_time_fail(self) -> None:
        path = self.root / "heartbeat.jsonl"
        rows = [
            {"seq": 0, "host_monotonic_ns": 2, "simulation_time": 0, "timescale": "1ps"},
            {"seq": 2, "host_monotonic_ns": 1, "simulation_time": 1, "timescale": "1ps"},
        ]
        path.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")
        report = RUNTIME.validate_heartbeat_rows(path)
        self.assertFalse(report["pass"])
        self.assertTrue(any("sequence" in item for item in report["errors"]))
        self.assertTrue(any("monotonic" in item for item in report["errors"]))

    def test_attempt_root_escape_fails(self) -> None:
        inside = self.root / "inside"
        inside.mkdir()
        with self.assertRaises(RUNTIME.SupervisionError):
            RUNTIME.require_inside(self.root.parent / "escape", inside, "test path")

    def test_receipt_validation(self) -> None:
        path = self.root / "receipt.json"
        receipt = {
            "schema": RUNTIME.SCHEMA,
            "child_subreaper": {"enabled": True},
            "process_tree_reaped": True,
            "post_kill_reap": {
                "deadline_origin": "NOT_APPLICABLE",
                "last_kill_host_monotonic_ns": None,
                "deadline_host_monotonic_ns": None,
                "completed": True,
            },
            "owned_pids_remaining": [],
            "simulation_time_progress_observed": True,
            "errors": [],
        }
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertTrue(RUNTIME.validate_receipt(path)["pass"])
        receipt["owned_pids_remaining"] = [123]
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertFalse(RUNTIME.validate_receipt(path)["pass"])

    def test_stubborn_descendant_requires_fresh_post_kill_deadline(self) -> None:
        path = self.root / "receipt.json"
        receipt = {
            "schema": RUNTIME.SCHEMA,
            "child_subreaper": {"enabled": True},
            "process_tree_reaped": True,
            "owned_pids_remaining": [],
            "simulation_time_progress_observed": True,
            "termination": [{"signal": RUNTIME.SIGKILL_NUMBER}],
            "post_kill_reap": {
                "deadline_origin": "FRESH_AFTER_LAST_KILL",
                "last_kill_host_monotonic_ns": 200,
                "deadline_host_monotonic_ns": 199,
                "completed": True,
            },
            "errors": [],
        }
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertFalse(RUNTIME.validate_receipt(path)["pass"])
        receipt["post_kill_reap"]["deadline_host_monotonic_ns"] = 300
        path.write_text(json.dumps(receipt), encoding="utf-8")
        self.assertTrue(RUNTIME.validate_receipt(path)["pass"])


if __name__ == "__main__":
    unittest.main()
