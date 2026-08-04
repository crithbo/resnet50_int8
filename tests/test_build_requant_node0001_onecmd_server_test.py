from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path, PurePosixPath

from tools.build_requant_node0001_onecmd_server_test import (
    INSTALL_NAME,
    build_package,
    validate_package,
)
from tools.requant_node0001_server_runtime import (
    FOCUS_RTL,
    IDENTITY_SCHEMA,
    PRECOMPILE_RECEIPT_SCHEMA,
    SUPPORT_FILES,
    install_probe,
    restore_probe,
    verify_identity,
    verify_probe_installed,
)


class RequantNode0001OneCommandPackageTests(unittest.TestCase):
    def test_two_fresh_builds_are_byte_deterministic_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first" / INSTALL_NAME
            second = root / "second" / INSTALL_NAME
            first_report = build_package(first)
            second_report = build_package(second)
            self.assertEqual(first_report["zip_sha256"], second_report["zip_sha256"])
            self.assertEqual(
                first.with_suffix(".zip").read_bytes(),
                second.with_suffix(".zip").read_bytes(),
            )
            validation = validate_package(first)
            self.assertTrue(validation["zip_exact_set"])
            self.assertEqual(validation["formal_readback_count"], 156)
            self.assertEqual(validation["historical_guard_probe_count"], 128)
            self.assertEqual(validation["functional_rtl_file_count"], 0)

    def test_alias_aware_evidence_and_all_address_ranges_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / INSTALL_NAME
            build_package(package)
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            layout = json.loads(
                (package / "workload/runtime/layout_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            sca_d = json.loads(
                (package / "workload/runtime/sca_cfg_D.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest["dynamic_evidence_columns"],
                {
                    "TRANSIENT_GUARD_WRITE_OBSERVER": 128,
                    "FINAL_UINT8_FORMAL_SCA_D": 128,
                    "LAST_RESIDENT_GUARD_FORMAL_D": 28,
                },
            )
            self.assertFalse(
                manifest["alias_claim_boundary"][
                    "historical_alias_sca_d_treated_as_formal_readback"
                ]
            )
            self.assertEqual(len(sca_d), 156)
            self.assertEqual(len(layout["address_ranges"]), 384)
            self.assertEqual(
                Counter(item["role"] for item in layout["address_ranges"]),
                {
                    "guard_input_int32": 128,
                    "guard_intermediate_int32": 128,
                    "round_final_uint8": 128,
                },
            )
            self.assertLess(layout["maximum_address_row"], 6144)
            self.assertTrue(
                all(
                    0 <= item["start_row"] <= item["end_row"] < 6144
                    for item in layout["address_ranges"]
                )
            )
            self.assertFalse(
                any(
                    "rtl" in {part.lower() for part in PurePosixPath(path).parts}
                    for path in manifest["files"]
                )
            )

    def test_runner_and_observer_bind_same_clock_handshake_and_five_identities(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / INSTALL_NAME
            build_package(package)
            runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
            probe = (
                package / "tb_probe/requant_mse4_guard_observer_tail.svh"
            ).read_text(encoding="utf-8")
            for phase in (
                "pre_install",
                "post_probe_install",
                "post_compile",
                "post_run",
                "post_restore",
            ):
                self.assertIn(f"--phase {phase}", runner)
            self.assertLess(
                runner.index("--phase post_compile"), runner.index("./sim_results/simv")
            )
            self.assertIn("local_wdata_valid", probe)
            self.assertIn("local_wdata_ready", probe)
            self.assertIn("accepted=1 valid=1 ready=1 strobe=0xffff", probe)
            self.assertIn("cycle=%0d slice=%0d local_stage=%0d", probe)
            self.assertNotIn("force ", probe.lower())
            self.assertIn("+REQUANT_GUARD_PROBE", runner)
            self.assertIn("verify-probe-installed", runner)
            self.assertIn('VCS_EXTRA_OPTS="+incdir+${ndp_root}"', runner)
            self.assertIn("compile_driver.log", runner)
            self.assertLess(
                runner.index("verify-probe-installed"),
                runner.index("make -f Makefile.tb_NDP_Top_new_phy compile"),
            )

    def test_non_rtl_probe_install_is_transactionally_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            evidence = root / "evidence"
            ndp = root / "ndp"
            evidence.mkdir()
            (package / "tb_probe").mkdir(parents=True)
            ndp.mkdir()
            original = b"// frozen observer preimage\n"
            tail = b"// read-only test tail\n"
            observer = ndp / "native_return_observer.svh"
            observer.write_bytes(original)
            (
                package / "tb_probe/requant_mse4_guard_observer_tail.svh"
            ).write_bytes(tail)
            installed = install_probe(ndp, package, evidence)
            self.assertEqual(
                hashlib.sha256(observer.read_bytes()).hexdigest(),
                installed["installed_sha256"],
            )
            precompile = verify_probe_installed(ndp, evidence)
            self.assertEqual(
                precompile["status"], "installed_observer_verified_for_compile"
            )
            self.assertEqual(
                precompile["target_sha256"], installed["installed_sha256"]
            )
            restored = restore_probe(ndp, evidence)
            self.assertTrue(restored["restored"])
            self.assertEqual(observer.read_bytes(), original)
            self.assertFalse((ndp / "rtl").exists())

    def test_identity_receipt_requires_five_phase_byte_stability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            phases = [
                "pre_install",
                "post_probe_install",
                "post_compile",
                "post_run",
                "post_restore",
            ]
            preimage = "a" * 64
            installed_hash = "b" * 64
            paths: list[Path] = []
            for index, phase in enumerate(phases):
                document = {
                    "schema": IDENTITY_SCHEMA,
                    "phase": phase,
                    "server_command": "bash PREPARE_AND_RUN.sh /ndp",
                    "test_package": {"manifest": {"sha256": "c" * 64}},
                    "rtl_tree": {"tree_sha256": "d" * 64},
                    "focused_rtl": {
                        relative: {
                            "exists": True,
                            "size_bytes": 1,
                            "sha256": "e" * 64,
                        }
                        for relative in FOCUS_RTL
                    },
                    "support_files": {
                        relative: {
                            "exists": True,
                            "size_bytes": 1,
                            "sha256": (
                                installed_hash
                                if relative == "native_return_observer.svh"
                                and index == 1
                                else preimage
                            ),
                        }
                        for relative in SUPPORT_FILES
                    },
                    "installed_runtime": {
                        "tree_sha256": None if index == 0 else "f" * 64
                    },
                }
                path = root / f"{phase}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.append(path)
            probe_receipt = root / "probe.json"
            probe_receipt.write_text(
                json.dumps(
                    {
                        "preimage_sha256": preimage,
                        "installed_sha256": installed_hash,
                        "restored": True,
                    }
                ),
                encoding="utf-8",
            )
            precompile_receipt = root / "precompile.json"
            precompile_receipt.write_text(
                json.dumps(
                    {
                        "schema": PRECOMPILE_RECEIPT_SCHEMA,
                        "status": "installed_observer_verified_for_compile",
                        "target_sha256": installed_hash,
                        "backup_sha256": preimage,
                        "functional_rtl_modified": False,
                        "passed": True,
                    }
                ),
                encoding="utf-8",
            )
            receipt = verify_identity(paths, probe_receipt, precompile_receipt)
            self.assertEqual(
                receipt["status"], "stock_rtl_and_transactional_tb_probe_verified"
            )
            self.assertTrue(receipt["functional_rtl_unchanged"])
            self.assertTrue(receipt["tb_probe_transactionally_restored"])
            self.assertTrue(
                receipt["tb_probe_verified_immediately_before_compile"]
            )
            self.assertEqual(receipt["phases"], phases)

    def test_precompile_probe_gate_rejects_missing_or_tampered_observer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            evidence = root / "evidence"
            ndp = root / "ndp"
            evidence.mkdir()
            (package / "tb_probe").mkdir(parents=True)
            ndp.mkdir()
            observer = ndp / "native_return_observer.svh"
            observer.write_bytes(b"// original\n")
            (
                package / "tb_probe/requant_mse4_guard_observer_tail.svh"
            ).write_bytes(b"// tail\n")
            install_probe(ndp, package, evidence)
            observer.write_bytes(observer.read_bytes() + b"// tampered\n")
            with self.assertRaisesRegex(
                RuntimeError, "precompile byte identity differs"
            ):
                verify_probe_installed(ndp, evidence)


if __name__ == "__main__":
    unittest.main()
