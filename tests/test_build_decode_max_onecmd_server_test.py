from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from tools.build_decode_max_onecmd_server_test import (  # noqa: E402
    INSTALL_NAME,
    validate_package,
)
from tools.decode_max_server_runtime import (  # noqa: E402
    _formal_d_gate,
    _indexed_readbacks,
    _simulation_log_gate,
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
    "determinism-decode-max-v2"
    / INSTALL_NAME
)


class DecodeMaxOneCommandServerPackageTests(unittest.TestCase):
    def test_exact_package_and_server_preflight_pass(self) -> None:
        report = validate_package(ROOT, PACKAGE)
        self.assertEqual(
            report["status"], "one_command_server_test_package_validated"
        )
        self.assertEqual(report["functional_rtl_file_count"], 0)
        self.assertTrue(report["zip_audit"]["exact_file_set"])
        preflight = preflight_package(PACKAGE, INSTALL_NAME)
        self.assertEqual(preflight["payload_count"], 30)
        self.assertEqual(preflight["readback_count"], 28)
        self.assertEqual(preflight["repeat_num"], 1)

    def test_two_fresh_builds_are_byte_deterministic(self) -> None:
        first = validate_package(ROOT, PACKAGE)
        second = validate_package(ROOT, SECOND_PACKAGE)
        self.assertEqual(first["zip_sha256"], second["zip_sha256"])
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(
            first["payload_tree_sha256"], second["payload_tree_sha256"]
        )

    def test_single_command_has_explicit_dual_sca_and_no_rtl_action(self) -> None:
        manifest = json.loads(
            (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["server_operation"]["only_command"],
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertIn("does not exercise ResNet INT8 MaxPool", manifest["claim_boundary"])
        script = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertIn(
            f"+SCA_CFG=install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json", script
        )
        self.assertIn(
            f"+SCA_CFG_D=install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json", script
        )
        self.assertIn("DUMP_VCD=0", script)
        self.assertIn("DUMP_FSDB=0", script)
        self.assertIn("trap 'finalize_partial_return $?' EXIT", script)
        self.assertNotIn("install_gap_ga_rtl_repair.py", script)

    def test_readback_entries_are_numeric_complete_and_fail_closed(self) -> None:
        sca_d = json.loads(
            (PACKAGE / "workload/sca_cfg_D.json").read_text(encoding="utf-8")
        )
        indexed = _indexed_readbacks(sca_d)
        self.assertEqual(sorted(indexed), list(range(28)))
        self.assertTrue(
            all(
                set(entry) == {"base_addr", "path", "length"}
                and entry["length"] == 1
                for entry in indexed.values()
            )
        )
        self.assertIn("/readback/slice02/", indexed[2]["path"])
        self.assertIn("/readback/slice20/", indexed[20]["path"])

    def test_formal_full_line_gate_and_loader_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cfg_root = root / "install/cfg_pkg" / INSTALL_NAME
            shutil.copytree(PACKAGE / "workload", cfg_root)
            sca_d = json.loads(
                (cfg_root / "sca_cfg_D.json").read_text(encoding="utf-8")
            )
            for slice_id, entry in _indexed_readbacks(sca_d).items():
                target = root.joinpath(*Path(entry["path"]).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(
                    PACKAGE
                    / f"workload/golden/slice{slice_id:02d}/matrix_D_128bit.txt",
                    target,
                )
            formal = _formal_d_gate(root, PACKAGE, INSTALL_NAME)
            self.assertEqual(formal["status"], "pass")
            self.assertTrue(formal["all_28_full_128bit_lines_match"])

            sim_log = root / f"run_{INSTALL_NAME}/sim_results/sim.log"
            sim_log.parent.mkdir(parents=True)
            sim_log.write_text(
                "\n".join(
                    [
                        f"Using SCA cfg file: install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json",
                        f"Using SCA cfg D file: install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json",
                        "JSON config: 30 matrices loaded",
                        "INFO: slice start",
                        "INFO: slice completed after 65 cycles",
                        "JSON_D config: 28 matrices dumped",
                        "Simulation completed successfully!",
                    ]
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            loader, _ = _simulation_log_gate(root, INSTALL_NAME)
            self.assertEqual(loader["status"], "pass")


if __name__ == "__main__":
    unittest.main()
