from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.node0004_hang_localization_runtime_v9 import analyze


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v9_hangloc_qualified"
)


class Node0004QualifiedProgressV9Test(unittest.TestCase):
    def test_reason_record_is_not_overwritten_by_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            run = root / "run/c0"
            evidence.mkdir()
            run.mkdir(parents=True)
            (evidence / "compile_exit_status.txt").write_text("0\n")
            (evidence / "run_exit_status.txt").write_text("1\n")
            (run / "return_observer.log").write_text(
                "1 | PROGRESS_WINDOW | delta=0\n"
                "2 | DIAG_DECISION | reason=STALL_WINDOW_EXCEEDED "
                "boundary=BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS\n"
                "2 | DIAG_DECISION | slice=0 active_cycles=1048576\n",
                encoding="utf-8",
            )
            result = analyze(PACKAGE, evidence, root / "run")
            self.assertEqual(result["status"], "C0_HANG_BOUNDARY_LOCALIZED")
            self.assertIn("reason=STALL_WINDOW_EXCEEDED", result["diagnostic_decision"])
            self.assertEqual(result["diagnostic_summary_line_count"], 2)
            self.assertEqual(result["reason_bearing_decision_line_count"], 1)

    def test_final_observer_excludes_buffer_levels_from_progress(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v9 package is not built")
        observer = (PACKAGE / "tb_probe/native_return_observer.svh").read_text(
            encoding="utf-8"
        )
        progress = observer.rsplit(
            "return_hang_diag_current_progress =", 1
        )[1].split(";", 1)[0]
        self.assertNotIn("return_obs_buf45_", progress)
        self.assertIn("return_obs_req_count[4]", progress)
        self.assertIn("return_obs_wdata_count[4]", progress)
        self.assertIn("buf5_wr_edge", observer)

    def test_manifest_records_diagnostic_only_repair(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v9 package is not built")
        manifest = json.loads(
            (PACKAGE / "package_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["classification"], "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["progress_contract"]["buffer_level_samples_count_as_progress"])
        self.assertFalse(manifest["numeric_analysis_repeated"])
        self.assertFalse(manifest["node0004_workload_rebuilt"])


if __name__ == "__main__":
    unittest.main()
