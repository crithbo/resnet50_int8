from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_gap_node0071_v4_hangloc_package import (
    HEARTBEAT_CYCLES,
    INSTALL_NAME,
    SOURCE_NAME,
    SOURCE_SHA256,
    SOURCE_ZIP,
    STALL_WINDOW_CYCLES,
    build_directory,
    sha256,
)


class GapNode0071V4HanglocPackageTest(unittest.TestCase):
    def test_diagnostic_package_is_bound_and_fail_closed(self) -> None:
        self.assertEqual(sha256(SOURCE_ZIP), SOURCE_SHA256)
        with tempfile.TemporaryDirectory(
            prefix="gap-node0071-v4-test-"
        ) as temporary:
            package, proof = build_directory(Path(temporary))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(
                    encoding="utf-8"
                )
            )
            runner = (package / "PREPARE_AND_RUN.sh").read_text(
                encoding="utf-8"
            )
            sca = (package / "workload/sca_cfg.json").read_text(
                encoding="utf-8"
            )
            sca_d = (package / "workload/sca_cfg_D.json").read_text(
                encoding="utf-8"
            )
            targets = {
                item["target_path"]
                for item in manifest["return_allowlist"]
            }

            self.assertTrue(proof["numeric_workload_tree_equal"])
            self.assertEqual(proof["numeric_workload_file_count"], 73)
            self.assertTrue(proof["package_preflight"]["valid"])
            self.assertEqual(
                manifest["claim"], "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            )
            self.assertFalse(manifest["functional_fix"])
            self.assertFalse(manifest["functional_rtl_modified"])
            self.assertFalse(manifest["numeric_analysis_repeated"])
            self.assertFalse(manifest["sum_or_tail_numeric_reexecuted"])
            self.assertEqual(manifest["install_name"], INSTALL_NAME)
            self.assertEqual(len(manifest["return_allowlist"]), 67)
            self.assertEqual(len(manifest["readback_checks"]), 48)
            self.assertIn("+RETURN_OBSERVER", runner)
            self.assertIn(
                f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}",
                runner,
            )
            self.assertIn(
                f"+RETURN_OBS_STALL_CYCLES={STALL_WINDOW_CYCLES}",
                runner,
            )
            self.assertIn("actual_simulator_argv.txt", runner)
            self.assertIn("progress_samples.log", runner)
            self.assertIn("runs/return_observer.log", targets)
            self.assertIn("evidence/host_timing.txt", targets)
            self.assertIn("evidence/progress_contract.json", targets)
            self.assertIn(INSTALL_NAME, sca)
            self.assertIn(INSTALL_NAME, sca_d)
            self.assertNotIn(SOURCE_NAME, runner)
            self.assertNotIn(SOURCE_NAME, sca)
            self.assertNotIn(SOURCE_NAME, sca_d)


if __name__ == "__main__":
    unittest.main()
