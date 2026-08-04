from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from tools.build_gap_int32_mac_onecmd_server_test import (  # noqa: E402
    INSTALL_NAME,
    validate_package,
)
from tools.gap_int32_mac_server_runtime import (  # noqa: E402
    _indexed_readbacks,
    preflight_package,
)


PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
SECOND_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "determinism-onecmd-v5"
    / INSTALL_NAME
)


class GapInt32MacOneCommandServerPackageTests(unittest.TestCase):
    def test_exact_package_and_zip_validate(self) -> None:
        report = validate_package(ROOT, PACKAGE)
        self.assertEqual(
            report["status"], "one_command_server_test_package_validated"
        )
        self.assertEqual(report["functional_rtl_file_count"], 0)
        self.assertEqual(report["zip_audit"]["exact_file_set"], True)

    def test_server_equivalent_standard_library_preflight_passes(self) -> None:
        report = preflight_package(PACKAGE, INSTALL_NAME)
        self.assertEqual(report["status"], "package_preflight_passed")
        self.assertEqual(report["repeat_num"], 6)
        self.assertEqual(report["sca_d_readback_count"], 16)

    def test_server_user_operation_is_one_command(self) -> None:
        manifest = json.loads(
            (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["server_operation"]["only_command"],
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        )
        self.assertEqual(
            manifest["server_operation"]["manual_parameters_beyond_ndp_root"],
            0,
        )
        script = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertNotIn("make -f Makefile.tb_NDP_Top_new_phy compile sim", script)
        self.assertNotIn("install_native_return_observer.py", script)
        self.assertNotIn("install_gap_ga_rtl_repair.py", script)
        self.assertIn(
            "timeout --foreground --signal=TERM --kill-after=30s 2h", script
        )
        self.assertIn(
            "timeout --foreground --signal=TERM --kill-after=30s 12h", script
        )
        self.assertIn("trap 'finalize_partial_return $?' EXIT", script)

    def test_no_rtl_or_nested_archive_is_packaged(self) -> None:
        forbidden_rtl = {".v", ".sv", ".vh", ".svh"}
        forbidden_archives = {".zip", ".tar", ".tgz", ".gz", ".7z"}
        payloads = [
            path
            for path in PACKAGE.rglob("*")
            if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
        ]
        self.assertFalse(
            [path for path in payloads if path.suffix.lower() in forbidden_rtl]
        )
        self.assertFalse(
            [
                path
                for path in payloads
                if path.suffix.lower() in forbidden_archives
            ]
        )

    def test_two_fresh_builds_are_byte_deterministic(self) -> None:
        first = validate_package(ROOT, PACKAGE)
        second = validate_package(ROOT, SECOND_PACKAGE)
        self.assertEqual(first["zip_sha256"], second["zip_sha256"])
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(
            first["payload_tree_sha256"], second["payload_tree_sha256"]
        )

    def test_formal_readbacks_use_numeric_not_lexicographic_slice_identity(
        self,
    ) -> None:
        sca_d = json.loads(
            (PACKAGE / "workload/sca_cfg_D.json").read_text(encoding="utf-8")
        )
        indexed = _indexed_readbacks(sca_d)
        self.assertEqual(list(sorted(indexed)), list(range(16)))
        self.assertIn("/readback/slice02/", indexed[2]["path"])
        self.assertIn("/readback/slice10/", indexed[10]["path"])
        self.assertTrue(
            all(
                set(entry) == {"base_addr", "path", "length"}
                and entry["length"] == 512
                for entry in indexed.values()
            )
        )

    def test_tb_readback_length_is_fail_closed(self) -> None:
        sca_d = json.loads(
            (PACKAGE / "workload/sca_cfg_D.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(sca_d), 16)
        self.assertTrue(all(entry.get("length") == 512 for entry in sca_d.values()))


if __name__ == "__main__":
    unittest.main()
