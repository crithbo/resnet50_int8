from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.node0004_assumed_hardware_server_runtime_v2 import preflight


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v5_observe"
)


class Node0004AssumedHardwareServerV5Test(unittest.TestCase):
    def setUp(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v5 package is not built")

    def test_observer_is_runtime_enabled_and_returned(self) -> None:
        runner = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertIn("+RETURN_OBSERVER", runner)
        self.assertIn("+RETURN_OBS_DEEP", runner)
        self.assertIn("+RETURN_OBS_ACCUM_STATE", runner)
        self.assertIn(
            '"+RETURN_OBS_FILE=$run_root/$id/return_observer.log"', runner
        )
        runtime = (
            PACKAGE
            / "package_tools/node0004_assumed_hardware_server_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn('OBSERVER_LOG = "return_observer.log"', runtime)
        self.assertIn("OBSERVER_LOG_MAX_BYTES = 8 * 1024 * 1024", runtime)

    def test_sca_root_and_readback_absence_are_valid(self) -> None:
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            receipt["path_resolution"]["stale_install_path_count"], 0
        )
        self.assertEqual(
            receipt["path_resolution"]["static_input_path_count"], 398
        )
        self.assertEqual(
            receipt["path_resolution"]["deferred_tail_input_path_count"], 128
        )
        self.assertEqual(
            receipt["path_resolution"]["absent_formal_readback_path_count"],
            320,
        )
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["preloaded_readback_target_count"], 0)

    def test_zip_sidecar_and_double_build_are_bound(self) -> None:
        zip_path = PACKAGE.with_suffix(".zip")
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sidecar = Path(str(zip_path) + ".sha256")
        self.assertEqual(sidecar.read_text(encoding="ascii").split()[0], digest)
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["zip_sha256"], digest)
        self.assertTrue(receipt["repeated_build"]["package_tree_equal"])
        self.assertTrue(receipt["repeated_build"]["zip_equal"])
        self.assertFalse(receipt["numeric_analysis_repeated"])
        self.assertFalse(receipt["node0004_workload_rebuilt"])


if __name__ == "__main__":
    unittest.main()
