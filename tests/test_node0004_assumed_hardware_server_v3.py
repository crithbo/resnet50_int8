from __future__ import annotations

import hashlib
import json
import tempfile
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
    "r5_n4_hw_v3_obs"
)
OBSERVER_SHA = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)


class Node0004AssumedHardwareServerV3Test(unittest.TestCase):
    def test_package_local_observer_is_bound_without_server_write(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v3 package is not built")
        manifest = json.loads(
            (PACKAGE / "package_manifest.json").read_text(encoding="utf-8")
        )
        observer = manifest["package_local_observer"]
        self.assertEqual(observer["sha256"], OBSERVER_SHA)
        self.assertFalse(observer["server_install"])
        self.assertEqual(manifest["server_rtl_entries"], 0)
        self.assertEqual(
            manifest["server_tb_or_observer_install_entries"], 0
        )
        self.assertFalse(manifest["functional_rtl_modified"])
        receipt = observer_precompile_receipt(PACKAGE, OBSERVER_SHA)
        self.assertTrue(receipt["valid"], receipt["errors"])

    def test_runner_hash_checks_and_passes_explicit_include_dir(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v3 package is not built")
        script = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertIn(
            '--expected-sha256 "47f0d66728f47c92f9f93f8cf87b47a0'
            'ff8567d587c3a099e2d03f610af09f49"',
            script,
        )
        self.assertIn(
            'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"', script
        )
        self.assertNotIn("cp ", script.split("observer_guard=", 1)[1].split(
            'cd "$server_root"', 1
        )[0])
        self.assertLess(
            script.index("observer_precompile.json"),
            script.index("Makefile.tb_NDP_Top_new_phy compile"),
        )

    def test_payload_and_failclosed_package_preflight(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v3 package is not built")
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["preloaded_readback_target_count"], 0)
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        self.assertTrue(receipt["source_payload_tree_equal"])
        self.assertTrue(receipt["result_gate_fail_closed"])

    def test_zip_sidecar_and_repeated_build_are_bound(self) -> None:
        zip_path = PACKAGE.with_suffix(".zip")
        if not zip_path.is_file():
            self.skipTest("v3 ZIP is not built")
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        self.assertEqual(
            Path(str(zip_path) + ".sha256")
            .read_text(encoding="ascii")
            .split()[0],
            digest,
        )
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["zip_sha256"], digest)
        self.assertTrue(receipt["repeated_build"]["package_tree_equal"])
        self.assertTrue(receipt["repeated_build"]["zip_equal"])

    def test_observer_guard_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            observer = package / "tb_probe/native_return_observer.svh"
            observer.parent.mkdir()
            observer.write_text("// tampered\n", encoding="utf-8")
            receipt = observer_precompile_receipt(package, OBSERVER_SHA)
            self.assertFalse(receipt["valid"])
            self.assertIn(
                "package-local observer SHA-256 differs", receipt["errors"]
            )


if __name__ == "__main__":
    unittest.main()
