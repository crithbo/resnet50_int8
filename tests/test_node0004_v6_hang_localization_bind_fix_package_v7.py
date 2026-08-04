from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.node0004_hang_localization_runtime_v7 import analyze, preflight


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v7_hangloc_bind"
)


class Node0004V6HangLocalizationBindFixPackageV7Test(unittest.TestCase):
    def setUp(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v7 diagnostic bind-fix package is not built")

    def test_diagnostic_identity_and_progress_binding(self) -> None:
        manifest = json.loads(
            (PACKAGE / "package_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["classification"],
            "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertEqual(manifest["run_ids"], ["c0"])
        self.assertEqual(manifest["server_rtl_entries"], 0)
        runner = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertIn("+RETURN_OBSERVER", runner)
        self.assertIn("+RETURN_HANG_DIAG", runner)
        self.assertIn(
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            runner,
        )
        self.assertIn("host_progress.log", runner)
        self.assertIn("simulator_argv.txt", runner)
        self.assertNotIn("12h", runner)

    def test_c0_only_and_no_preloaded_d(self) -> None:
        runs = sorted(
            path.name
            for path in (PACKAGE / "workload/runtime/runs").iterdir()
            if path.is_dir()
        )
        self.assertEqual(runs, ["c0"])
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["c0_input_leaf_count"], 86)
        self.assertEqual(report["c0_absent_d_leaf_count"], 28)

    def test_deterministic_zip_sidecar_and_receipt(self) -> None:
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
        self.assertTrue(receipt["observer_compile_enable_macro_bound"])
        self.assertFalse(receipt["numeric_analysis_repeated"])
        self.assertFalse(receipt["node0004_workload_rebuilt"])

    def test_result_parser_distinguishes_progressing_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            run = root / "run"
            evidence.mkdir()
            (run / "c0").mkdir(parents=True)
            (evidence / "compile_exit_status.txt").write_text(
                "0\n", encoding="ascii"
            )
            (evidence / "run_exit_status.txt").write_text(
                "1\n", encoding="ascii"
            )
            (run / "c0/return_observer.log").write_text(
                "1 | PROGRESS_WINDOW | delta=9\n"
                "2 | PROGRESS_WINDOW | delta=11\n"
                "3 | DIAG_DECISION | "
                "reason=MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING "
                "boundary=READ_REQUEST_TO_MEMORY_DATA\n",
                encoding="utf-8",
            )
            result = analyze(PACKAGE, evidence, run)
            self.assertEqual(
                result["status"],
                "C0_STILL_PROGRESSING_NOT_FINISHED_AT_BUDGET",
            )

    def test_result_parser_distinguishes_stall_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            run = root / "run"
            evidence.mkdir()
            (run / "c0").mkdir(parents=True)
            (evidence / "compile_exit_status.txt").write_text(
                "0\n", encoding="ascii"
            )
            (evidence / "run_exit_status.txt").write_text(
                "1\n", encoding="ascii"
            )
            (run / "c0/return_observer.log").write_text(
                "1 | PROGRESS_WINDOW | delta=0\n"
                "2 | DIAG_DECISION | reason=STALL_WINDOW_EXCEEDED "
                "boundary=SA_INPUT_MATCH_TO_SA_OUTPUT_BUFFER5\n",
                encoding="utf-8",
            )
            result = analyze(PACKAGE, evidence, run)
            self.assertEqual(result["status"], "C0_HANG_BOUNDARY_LOCALIZED")


if __name__ == "__main__":
    unittest.main()
