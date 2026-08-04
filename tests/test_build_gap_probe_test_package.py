from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_gap_probe_test_package import (
    DEFAULT_OUTPUT_REL,
    INSTALL_NAME,
    ROOT,
    _run_script,
    validate_package,
)


class BuildGapProbeTestPackageTests(unittest.TestCase):
    def test_checked_v7_package_zip_and_sidecar_are_exact(self) -> None:
        report = validate_package(ROOT, ROOT / DEFAULT_OUTPUT_REL)

        self.assertEqual(report["status"], "server_test_package_validated")
        self.assertEqual(report["payload_file_count"], 119)
        self.assertEqual(report["zip_audit"]["entry_count"], 120)
        self.assertEqual(
            report["zip_sha256"],
            "c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893",
        )
        self.assertFalse(report["functional_rtl_v_or_sv_included"])
        self.assertTrue(report["server_execution_required"])
        self.assertEqual(
            Path(report["zip"]).name,
            f"{INSTALL_NAME}.zip",
        )

    def test_run_script_makes_tb_include_discoverable(self) -> None:
        script = _run_script(INSTALL_NAME)

        self.assertIn("--fix-run-time", script)
        self.assertIn('test -s "${installed_observer}"', script)
        self.assertIn("cmp -s", script)
        self.assertIn("+incdir+${ndp_root}", script)
        self.assertIn('VCS_EXTRA_OPTS="${vcs_extra_opts# }"', script)
        self.assertIn("+RETURN_OBS_ACCUM_STATE", script)
        self.assertIn("+RETURN_OBS_ACCUM_LIMIT=512", script)
        self.assertIn("+RETURN_OBS_FILE=${evidence_root}/return_observer.log", script)
        self.assertNotIn("+RETURN_OBS_DEEP", script)

    def test_run_script_disables_waves_and_builds_bounded_return(self) -> None:
        script = _run_script(INSTALL_NAME)

        self.assertIn("DUMP_VCD=0", script)
        self.assertIn("DUMP_FSDB=0", script)
        self.assertIn("TB_DUMP_FSDB=0", script)
        self.assertNotIn("DUMP_FSDB=1", script)
        self.assertIn("build_gap_probe_return.py", script)
        self.assertIn(f"{INSTALL_NAME}_return.zip", script)
        self.assertIn('return_sha="${return_zip}.sha256"', script)

    def test_run_script_uses_isolated_compile_directory(self) -> None:
        script = _run_script(INSTALL_NAME)

        self.assertIn(
            f'probe_run_dir="${{ndp_root}}/run_{INSTALL_NAME}"',
            script,
        )
        self.assertIn('RUN_DIR="${probe_run_dir}"', script)
        self.assertEqual(INSTALL_NAME, "gap_hwop0071_sum_probe_v7")


if __name__ == "__main__":
    unittest.main()
