from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_dequant_node0077_onecmd_server_test import (
    INSTALL_NAME,
    build_package,
    validate_package,
)
from tools.dequant_node0077_server_runtime import (
    FOCUS_RTL,
    SUPPORT_FILES,
    analyze,
    preflight_package,
    verify_identity,
)


class DequantNode0077OneCommandPackageTests(unittest.TestCase):
    def test_two_builds_are_byte_deterministic_and_preflighted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / INSTALL_NAME
            report = build_package(package)
            self.assertEqual(report["deterministic_package_build_count"], 2)
            self.assertTrue(report["deterministic_zip_byte_identical"])
            self.assertEqual(report["complete_package_self_check_count"], 1)
            validation = validate_package(package)
            self.assertEqual(validation["functional_rtl_file_count"], 0)
            self.assertEqual(validation["preflight"]["formal_readback_count"], 28)
            self.assertEqual(validation["preflight"]["start_comp_count"], 1)
            self.assertTrue(validation["preflight"]["layout_inverse_bit_exact"])
            self.assertEqual(
                validation["probe_transaction"]["status"], "pass"
            )

    def test_package_semantics_and_tail_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / INSTALL_NAME
            build_package(package)
            report = preflight_package(package, INSTALL_NAME)
            self.assertEqual(report["status"], "package_preflight_passed")
            self.assertEqual(report["formal_readback_lines_per_slice"], 188)
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["semantic_contract"]["equation"],
                "y=(float32(uint8(x))-60.0f)*scale",
            )
            self.assertEqual(
                manifest["semantic_contract"]["scale_fp32_bits"], "0x3e01622d"
            )
            self.assertFalse(manifest["rtl_policy"]["rtl_patch_included"])

    def test_synthetic_complete_e4_result_passes_all_dynamic_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / INSTALL_NAME
            build_package(package)
            ndp_root = root / "ndp"
            run_dir = ndp_root / f"run_{INSTALL_NAME}"
            evidence = ndp_root / f"evidence_{INSTALL_NAME}"
            (run_dir / "sim_results").mkdir(parents=True)
            evidence.mkdir(parents=True)
            sim_text = "\n".join(
                [
                    f"Using SCA cfg file: ../install/cfg_pkg/{INSTALL_NAME}/sca_cfg.json",
                    f"Using SCA cfg D file: ../install/cfg_pkg/{INSTALL_NAME}/sca_cfg_D.json",
                    "JSON config: 30 matrices loaded",
                    "INFO: slice start",
                    "INFO: slice completed after 123 cycles",
                    "JSON_D config: 28 matrices dumped",
                    "Simulation completed successfully!",
                ]
            )
            (run_dir / "sim_results/sim.log").write_text(
                sim_text + "\n", encoding="utf-8"
            )
            for slice_id in range(28):
                lifecycle = (
                    run_dir
                    / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
                )
                lifecycle.parent.mkdir(parents=True)
                lifecycle.write_text(
                    "\n".join(
                        [
                            "1 | Start Cfg | sem2scm_cfg_start",
                            "2 | Cfg Finish | scm2sem_cfg_finish",
                            "3 | Start Comp | sem2iga_exec_start",
                            "4 | Comp Finish | slice_cmpt_finish",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                readback = (
                    run_dir
                    / f"sim_results/formal_readback/slice{slice_id:02d}/"
                    "matrix_D_linearized_128bit.txt"
                )
                readback.parent.mkdir(parents=True)
                golden = (
                    package
                    / f"workload/golden/slice{slice_id:02d}/"
                    "matrix_D_linearized_128bit.txt"
                )
                readback.write_bytes(golden.read_bytes())
            (evidence / "stock_rtl_identity_receipt.json").write_text(
                json.dumps(
                    {
                        "status": (
                            "stock_rtl_and_transactional_tb_probe_verified"
                        ),
                        "functional_rtl_unchanged": True,
                        "tb_probe_transactionally_restored": True,
                        "tb_probe_verified_immediately_before_compile": True,
                        "focused_rtl": {
                            relative: True for relative in FOCUS_RTL
                        },
                        "support_files": {
                            relative: True for relative in SUPPORT_FILES
                        },
                    }
                ),
                encoding="utf-8",
            )
            report = analyze(
                ndp_root,
                package,
                INSTALL_NAME,
                evidence,
                run_dir,
                0,
            )
            self.assertEqual(
                report["status"], "E4_COMPUTE_PASS_RETURN_PENDING"
            )
            self.assertTrue(
                report["gates"]["all_slice_lifecycle"][
                    "all_28_slices_naturally_completed"
                ]
            )
            self.assertTrue(
                report["gates"]["formal_d_readback"]["all_28_slices_bit_exact"]
            )
            self.assertTrue(
                report["gates"]["formal_d_readback"]["layout_inverse"][
                    "bit_exact"
                ]
            )
            self.assertEqual(
                report["remaining_blockers"], ["B_DEQUANT_SERVER_E4_E5"]
            )

    def test_identity_receipt_requires_four_phase_byte_stability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            phases = [
                "pre_install",
                "post_probe_install",
                "post_compile",
                "post_run",
                "post_restore",
            ]
            paths: list[Path] = []
            for index, phase in enumerate(phases):
                document = {
                    "schema": "resnet50-dequant-node0077-server-identity-v2",
                    "phase": phase,
                    "server_command": "bash PREPARE_AND_RUN.sh /ndp",
                    "test_package": {"manifest": {"sha256": "a" * 64}},
                    "rtl_tree": {"tree_sha256": "b" * 64},
                    "focused_rtl": {
                        relative: {
                            "exists": True,
                            "size_bytes": 1,
                            "sha256": "c" * 64,
                        }
                        for relative in FOCUS_RTL
                    },
                    "support_files": {
                        relative: {
                            "exists": True,
                            "size_bytes": 1,
                            "sha256": (
                                ("f" * 64)
                                if (
                                    relative == "native_return_observer.svh"
                                    and phase == "post_probe_install"
                                )
                                else "d" * 64
                            ),
                        }
                        for relative in SUPPORT_FILES
                    },
                    "installed_runtime": {
                        "tree_sha256": None if index == 0 else "e" * 64
                    },
                }
                path = root / f"{phase}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.append(path)
            probe_receipt = root / "tb_probe_install_receipt.json"
            probe_receipt.write_text(
                json.dumps(
                    {
                        "schema": "resnet50-dequant-node0077-tb-probe-install-v2",
                        "status": "restored_byte_exact",
                        "preimage_sha256": "d" * 64,
                        "installed_sha256": "f" * 64,
                        "restored": True,
                    }
                ),
                encoding="utf-8",
            )
            precompile_receipt = root / "tb_probe_precompile_receipt.json"
            precompile_receipt.write_text(
                json.dumps(
                    {
                        "schema": (
                            "resnet50-dequant-node0077-tb-probe-"
                            "precompile-verification-v2"
                        ),
                        "status": "installed_observer_verified_for_compile",
                        "target_sha256": "f" * 64,
                        "backup_sha256": "d" * 64,
                        "functional_rtl_modified": False,
                        "passed": True,
                    }
                ),
                encoding="utf-8",
            )
            receipt = verify_identity(
                paths, probe_receipt, precompile_receipt
            )
            self.assertTrue(receipt["functional_rtl_unchanged"])
            self.assertTrue(receipt["installed_namespace_stable_after_install"])
            self.assertTrue(receipt["tb_probe_transactionally_restored"])


if __name__ == "__main__":
    unittest.main()
