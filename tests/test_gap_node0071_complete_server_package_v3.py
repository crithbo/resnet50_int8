from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_gap_node0071_complete_server_package_v3 import (
    INSTALL_NAME,
    SOURCE_INSTALL_NAME,
    SOURCE_ZIP,
    SOURCE_ZIP_SHA256,
    build_directory,
    sha256,
)


class GapNode0071CompleteServerPackageV3Test(unittest.TestCase):
    def test_runner_cwd_fix_preserves_frozen_payload(self) -> None:
        self.assertEqual(sha256(SOURCE_ZIP), SOURCE_ZIP_SHA256)
        with tempfile.TemporaryDirectory(
            prefix="gap-node0071-v3-test-"
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

            self.assertTrue(proof["frozen_payload_tree_equal"])
            self.assertEqual(proof["frozen_payload_file_count"], 119)
            self.assertTrue(proof["package_preflight"]["valid"])
            self.assertTrue(
                proof["simulation_cwd_bound_to_server_root"]
            )
            self.assertEqual(manifest["install_name"], INSTALL_NAME)
            self.assertEqual(manifest["package_name"], INSTALL_NAME)
            self.assertEqual(
                manifest["repair_classification"],
                "PACKAGE_RUNNER_CWD_NOT_BOUND_TO_SERVER_ROOT",
            )
            self.assertIn('cd "$server_root"', runner)
            self.assertIn(
                "(cd <user-root> && <unique-run>/sim_results/simv",
                runner,
            )
            self.assertIn(INSTALL_NAME, sca)
            self.assertIn(INSTALL_NAME, sca_d)
            self.assertNotIn(SOURCE_INSTALL_NAME, runner)
            self.assertNotIn(SOURCE_INSTALL_NAME, sca)
            self.assertNotIn(SOURCE_INSTALL_NAME, sca_d)
            self.assertFalse(manifest["functional_rtl_modified"])
            self.assertFalse(manifest["numeric_analysis_repeated"])
            self.assertFalse(manifest["sum_or_tail_numeric_reexecuted"])
            self.assertEqual(len(manifest["return_allowlist"]), 60)
            self.assertEqual(len(manifest["readback_checks"]), 48)


if __name__ == "__main__":
    unittest.main()
