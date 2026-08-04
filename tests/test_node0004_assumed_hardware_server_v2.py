from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.node0004_assumed_hardware_server_runtime_v2 import (
    RuntimeErrorContract,
    analyze,
    preflight,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v2_failclosed"
)
OLD_PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1"
)


class Node0004AssumedHardwareServerV2Test(unittest.TestCase):
    def test_v2_package_has_no_preloaded_readback_targets(self) -> None:
        if not PACKAGE_ROOT.is_dir():
            self.skipTest("v2 package is not present")
        report = preflight(PACKAGE_ROOT)
        self.assertTrue(report["valid"])
        self.assertEqual(report["readback_target_count"], 320)
        self.assertEqual(report["preloaded_readback_target_count"], 0)

    def test_old_package_is_rejected_by_v2_preflight(self) -> None:
        if not OLD_PACKAGE_ROOT.is_dir():
            self.skipTest("old expanded package is not present")
        with self.assertRaisesRegex(
            RuntimeErrorContract, "runtime D targets must not be packaged"
        ):
            preflight(OLD_PACKAGE_ROOT)

    def test_compile_failure_cannot_emit_pass(self) -> None:
        if not PACKAGE_ROOT.is_dir():
            self.skipTest("v2 package is not present")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cfg = root / "cfg"
            evidence = root / "evidence"
            cfg.mkdir()
            evidence.mkdir()
            (evidence / "compile_exit_status.txt").write_text(
                "2\n", encoding="ascii"
            )
            (evidence / "run_exit_status.txt").write_text(
                "125\n", encoding="ascii"
            )
            report = analyze(PACKAGE_ROOT, cfg, evidence)
            self.assertEqual(report["status"], "NODE0004_SERVER_FAILURE")
            self.assertEqual(report["missing_count"], 320)
            self.assertFalse(
                report["execution_gate"][
                    "terminal_and_readback_gate_satisfied"
                ]
            )

    def test_zip_sidecar_and_validation_are_bound(self) -> None:
        zip_path = PACKAGE_ROOT.with_suffix(".zip")
        sidecar = Path(str(zip_path) + ".sha256")
        validation = PACKAGE_ROOT.with_suffix(".validation.json")
        if not zip_path.is_file():
            self.skipTest("v2 ZIP is not present")
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        self.assertEqual(sidecar.read_text(encoding="ascii").split()[0], digest)
        receipt = json.loads(validation.read_text(encoding="utf-8"))
        self.assertEqual(receipt["zip_sha256"], digest)
        self.assertTrue(receipt["repeated_build"]["package_tree_equal"])
        self.assertTrue(receipt["repeated_build"]["zip_equal"])
        self.assertFalse(receipt["functional_rtl_modified"])


if __name__ == "__main__":
    unittest.main()
