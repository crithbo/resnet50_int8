from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.e4e5_handoff import (
    E4E5HandoffError,
    build_e4e5_handoff_readiness,
    validate_e4e5_handoff_readiness,
    validate_server_execution_protocol,
)
from tools.run_e4e5_server_protocol import run_server_protocol


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict[str, object]:
    return {
        "schema": "resnet50-server-execution-protocol-v1",
        "status": "approved",
        "server_id": "unit-test-server",
        "rtl_identity": {
            "repository": "unit-test-rtl",
            "commit": "1" * 40,
            "filelist_sha256": "2" * 64,
        },
        "phases": [
            {
                "name": name,
                "cwd": "server_workspace",
                "argv": [sys.executable, "-c", f"print('{name}')"],
                "timeout_seconds": 30,
            }
            for name in ("load", "start", "wait", "readback")
        ],
        "return_paths": [
            {
                "path": "server_workspace/payload.bin",
                "kind": "readback",
                "required": True,
            }
        ],
    }


class E4E5HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readiness = build_e4e5_handoff_readiness(ROOT)

    def test_readiness_covers_one_representative_per_stage_type(self) -> None:
        coverage = self.readiness["coverage"]
        self.assertEqual(coverage["representative_count"], 10)
        self.assertEqual(coverage["ready_package_count"], 0)
        self.assertEqual(coverage["blocked_package_count"], 10)
        self.assertEqual(coverage["server_test_candidate_ready_count"], 0)
        self.assertEqual(coverage["server_test_candidate_blocked_count"], 10)
        self.assertEqual(
            coverage["historical_server_test_candidate_package_count"], 2
        )
        self.assertEqual(coverage["zero_copy_standalone_not_applicable_count"], 1)
        self.assertEqual(coverage["formal_target_stage_count"], 0)
        self.assertEqual(
            {item["hw_op_type"] for item in self.readiness["representatives"]},
            {
                "AverageRequantizeUint8",
                "ConvInt32Accumulate",
                "DequantizeLinear",
                "GlobalAverageSumInt32",
                "MatMulInt32Accumulate",
                "MaxPoolUint8",
                "QLinearAddUint8",
                "QuantizeLinear",
                "RequantizeUint8",
                "View",
            },
        )
        candidates = {
            item["hw_op_id"]: item
            for item in self.readiness["representatives"]
            if item["server_test_candidate_ready"]
        }
        self.assertEqual(candidates, {})
        self.assertEqual(self.readiness["execution_command_templates"], [])
        self.assertEqual(
            len(self.readiness["blocked_historical_command_templates"]), 2
        )

    def test_protocol_template_is_deliberately_not_executable(self) -> None:
        template = json.loads(
            (ROOT / "contracts/server_execution_protocol.template.json").read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaisesRegex(E4E5HandoffError, "not approved"):
            validate_server_execution_protocol(template)

    def test_protocol_validator_and_runner_use_exact_argv_without_shell(self) -> None:
        protocol = _protocol()
        validate_server_execution_protocol(protocol)
        root_cwd = copy.deepcopy(protocol)
        root_cwd["phases"][0]["cwd"] = "."
        validate_server_execution_protocol(root_cwd)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "package"
            workspace = package / "server_workspace"
            workspace.mkdir(parents=True)
            (workspace / "payload.bin").write_bytes(b"independent-readback")
            protocol_path = root / "protocol.json"
            protocol_path.write_text(
                json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
            )
            output = root / "return-run1"
            receipt = run_server_protocol(
                protocol_path, package, output, "run1"
            )
            self.assertEqual(receipt["status"], "passed_commands_and_return_collection")
            self.assertEqual([item["name"] for item in receipt["phases"]], [
                "load", "start", "wait", "readback"
            ])
            self.assertEqual(
                (output / "raw_return/server_workspace/payload.bin").read_bytes(),
                b"independent-readback",
            )
            self.assertEqual(len(receipt["return_tree"]["files"]), 1)
            self.assertEqual(len(receipt["return_tree"]["tree_sha256"]), 64)

    def test_wrong_phase_order_and_checked_in_drift_fail_closed(self) -> None:
        bad = copy.deepcopy(_protocol())
        bad["phases"][0], bad["phases"][1] = bad["phases"][1], bad["phases"][0]
        with self.assertRaisesRegex(E4E5HandoffError, "load/start/wait/readback"):
            validate_server_execution_protocol(bad)
        checked = json.loads(
            (ROOT / "contracts/resnet50_e4e5_handoff_readiness.json").read_text(
                encoding="utf-8"
            )
        )
        validate_e4e5_handoff_readiness(checked, ROOT)
        checked["coverage"]["ready_package_count"] = 1
        with self.assertRaises(E4E5HandoffError):
            validate_e4e5_handoff_readiness(checked, ROOT)

    def test_runner_aborts_on_first_failed_phase_and_preserves_receipt(self) -> None:
        protocol = _protocol()
        protocol["phases"][1]["argv"] = [sys.executable, "-c", "raise SystemExit(7)"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "package"
            (package / "server_workspace").mkdir(parents=True)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(protocol) + "\n", encoding="utf-8")
            output = root / "failed-return"
            with self.assertRaisesRegex(E4E5HandoffError, "server phase failed: start"):
                run_server_protocol(protocol_path, package, output, "run1")
            receipt = json.loads(
                (output / "run_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(
                [(item["name"], item["returncode"]) for item in receipt["phases"]],
                [("load", 0), ("start", 7)],
            )
            with self.assertRaisesRegex(E4E5HandoffError, "must not be inside"):
                run_server_protocol(
                    protocol_path,
                    package,
                    package / "nested-output",
                    "run2",
                )


if __name__ == "__main__":
    unittest.main()
