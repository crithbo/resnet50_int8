from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_gap_node0071_complete_server_package_v2 import (
    INSTALL_NAME,
    OBSERVER_SHA256,
    SOURCE_INSTALL_NAME,
    SOURCE_ZIP,
    SOURCE_ZIP_SHA256,
    build_directory,
    sha256,
)


class GapNode0071CompleteServerPackageV2Test(unittest.TestCase):
    def test_package_local_observer_fix_preserves_numeric_payload(self) -> None:
        self.assertEqual(sha256(SOURCE_ZIP), SOURCE_ZIP_SHA256)
        with tempfile.TemporaryDirectory(
            prefix="gap-node0071-v2-test-"
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
            observer = package / "tb_probe/native_return_observer.svh"
            self.assertTrue(proof["source_numeric_payload_tree_equal"])
            self.assertTrue(proof["package_preflight"]["valid"])
            self.assertEqual(manifest["install_name"], INSTALL_NAME)
            self.assertEqual(len(manifest["return_allowlist"]), 60)
            self.assertEqual(sha256(observer), OBSERVER_SHA256)
            self.assertIn(
                'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"',
                runner,
            )
            self.assertIn("observer_precompile.json", runner)
            self.assertIn(INSTALL_NAME, sca)
            self.assertIn(INSTALL_NAME, sca_d)
            self.assertNotIn(SOURCE_INSTALL_NAME, sca)
            self.assertNotIn(SOURCE_INSTALL_NAME, sca_d)
            self.assertFalse(manifest["functional_rtl_modified"])
            self.assertEqual(manifest["server_rtl_entries"], 0)
            self.assertEqual(
                manifest["package_local_tb_or_observer_entries"], 1
            )
            self.assertFalse(manifest["numeric_analysis_repeated"])
            self.assertFalse(manifest["sum_or_tail_numeric_reexecuted"])


if __name__ == "__main__":
    unittest.main()
