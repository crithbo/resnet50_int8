from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.node0004_assumed_hardware_server_runtime_v2 import preflight
from tools.node0004_package_observer_guard import (
    observer_precompile_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v4_rootbind"
)
OBSERVER_SHA = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
STALE_PREFIX = "install/cfg_pkg/r5_node0004_hw_v2_failclosed/"
CURRENT_PREFIX = "install/cfg_pkg/r5_n4_hw_v4_rootbind/"


class Node0004AssumedHardwareServerV4Test(unittest.TestCase):
    def setUp(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v4 package is not built")

    def test_sca_install_root_is_fully_rebound(self) -> None:
        files = sorted(
            (PACKAGE / "workload/runtime/runs").glob("*/sca_cfg*.json")
        )
        self.assertEqual(len(files), 54)
        count = 0
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(STALE_PREFIX, text)
            value = json.loads(text)
            stack = [value]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
                elif isinstance(item, str) and "install/cfg_pkg/" in item:
                    self.assertTrue(item.startswith(CURRENT_PREFIX), item)
                    count += 1
        self.assertEqual(count, 846)

    def test_path_resolution_and_formal_absence_receipt(self) -> None:
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        resolution = receipt["path_resolution"]
        self.assertEqual(resolution["stale_install_path_count"], 0)
        self.assertEqual(resolution["static_input_path_count"], 398)
        self.assertEqual(resolution["deferred_tail_input_path_count"], 128)
        self.assertEqual(
            resolution["absent_formal_readback_path_count"], 320
        )
        self.assertTrue(resolution["all_static_inputs_resolve"])
        self.assertTrue(resolution["all_formal_readbacks_begin_absent"])

    def test_package_preflight_and_observer_still_pass(self) -> None:
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["readback_target_count"], 320)
        self.assertEqual(report["preloaded_readback_target_count"], 0)
        observer = observer_precompile_receipt(PACKAGE, OBSERVER_SHA)
        self.assertTrue(observer["valid"], observer["errors"])

    def test_zip_sidecar_and_repeated_build_are_bound(self) -> None:
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
