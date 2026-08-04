from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from tools.build_maxpool_node0002_original_json_retest import (
    INSTALL_NAME,
    OUTPUT_SIDECAR,
    OUTPUT_ZIP,
    PROFILE_RULE,
    SOURCE_JSON_SHA256,
    sha256,
    validate_zip,
)
from tools.maxpool_node0002_original_json_server_runtime import (
    collect,
    file_records,
    preflight_package,
)


class MaxPoolOriginalJsonRetestPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(OUTPUT_ZIP.is_file())

    def _extract(self, root: Path) -> Path:
        with zipfile.ZipFile(OUTPUT_ZIP) as archive:
            archive.extractall(root)
        return root / INSTALL_NAME

    def test_zip_validation_and_sidecar(self) -> None:
        report = validate_zip(OUTPUT_ZIP)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["source_json_sha256"], SOURCE_JSON_SHA256)
        self.assertFalse(report["source_json_rewritten"])
        self.assertEqual(report["rtl_entry_count"], 0)
        self.assertEqual(report["tb_or_observer_entry_count"], 0)
        self.assertEqual(
            OUTPUT_SIDECAR.read_text(encoding="ascii"),
            f"{sha256(OUTPUT_ZIP)}  {OUTPUT_ZIP.name}\n",
        )

    def test_original_json_is_byte_identity_bound_and_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            package = self._extract(Path(temp_text))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["source_json"]["sha256"], SOURCE_JSON_SHA256)
            self.assertTrue(
                manifest["source_json"]["byte_identical_to_active_original"]
            )
            self.assertFalse(manifest["source_json"]["rewritten"])
            source = (
                package
                / "workload/runtime/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json.original"
            )
            self.assertEqual(sha256(source), SOURCE_JSON_SHA256)

    def test_fresh_provenance_empty_cache_and_forbidden_asset_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            package = self._extract(Path(temp_text))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["int8_max_numeric_polarity"],
                "CURRENT_ACTIVE_SOURCE_SELECTS_UNSIGNED_MAX",
            )
            self.assertEqual(
                manifest["int8_max_numeric_rule_status"],
                "CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS",
            )
            self.assertNotIn("B_GA_INT8_MAX_NUMERIC", manifest["open_dynamic_gates"])
            self.assertEqual(
                manifest["open_dynamic_gates"],
                ["B_GA_INT8_MAX_FLOW", "B_MAXPOOL_SERVER_E4_E5"],
            )
            self.assertEqual(
                manifest["known_counterexamples"],
                [
                    "GA int8_max pipeline0 downstream backpressure omits the INT8 branch"
                ],
            )
            source = manifest["source_json"]
            self.assertEqual(
                source["git_remote"], "https://github.com/uSFrances/ndp-sim.git"
            )
            self.assertEqual(
                source["git_commit"], "ec12424516ae0304228dd2321d4e604fe225e04e"
            )
            self.assertEqual(
                source["git_blob"], "4e8f7bb8906ab58f54f4c6507d2b94822f71bf04"
            )

            workload = manifest["workload"]
            encoder = workload["fresh_encoder"]
            self.assertEqual(encoder["seed_order"], [42, 20260728, 314159])
            self.assertEqual(encoder["deterministic_repeat_count"], 2)
            self.assertEqual(encoder["semantic_mismatch_paths"], [])
            first_exact = next(
                item for item in encoder["runs"].values()
                if item["receipt"]["exact_mapping"]
            )
            self.assertEqual(first_exact["receipt"]["seed"], encoder["selected_seed"])
            for run in encoder["runs"].values():
                self.assertEqual(run["penalty"], 0)
                self.assertFalse(run["fallback_used"])
                self.assertEqual(
                    run["receipt"]["mapping_cache_initial_file_count"], 0
                )
                self.assertTrue(run["receipt"]["exact_mapping"])
            run_a = encoder["runs"]["encoder_run_a"]
            run_b = encoder["runs"]["encoder_run_b"]
            for key in (
                "bitstream_128b",
                "bitstream_64b",
                "parsed_bitstream",
                "mapping_review",
                "detailed_dump",
            ):
                self.assertEqual(run_a[key], run_b[key])

            tensors = workload["formal_input_and_golden"]
            self.assertFalse(tensors["output_tensor_read"])
            self.assertIn("artifacts/w3/golden_batch16/tensors/", tensors["input_path"])
            self.assertIn("independent numpy", tensors["golden_generator"])

            audit = workload["forbidden_asset_audit"]
            self.assertEqual(audit["match_count"], 0)
            self.assertEqual(audit["matches"], [])
            self.assertEqual(audit["prior_materialized_asset_read_count"], 0)
            self.assertEqual(
                workload["forbidden_prior_materialized_asset_read_count"], 0
            )

            embedded_runtime = (
                package
                / "package_tools/maxpool_node0002_original_json_server_runtime.py"
            )
            self.assertEqual(
                sha256(embedded_runtime),
                "c996b8250b3277646e38c28319ab7c0d24a1ba439ea84cc5465eff0a748c6b3a",
            )

    def test_version_unbound_no_server_source_scan_or_observer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            package = self._extract(Path(temp_text))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertIn(PROFILE_RULE, manifest["rule_ids"])
            self.assertFalse(manifest["server_source_preflight_performed"])
            self.assertFalse(manifest["server_source_identity_bound"])
            self.assertEqual(manifest["functional_rtl_file_count"], 0)
            self.assertEqual(manifest["tb_or_observer_file_count"], 0)
            self.assertFalse(manifest["counts_as_e4"])
            self.assertFalse(manifest["counts_as_e5"])
            text = (
                (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
                + (
                    package
                    / "package_tools/maxpool_node0002_original_json_server_runtime.py"
                ).read_text(encoding="utf-8")
            )
            for forbidden in (
                "focused_rtl",
                "rtl_tree",
                "capture-identity",
                "verify-identity",
                "install-probe",
                "restore-probe",
            ):
                self.assertNotIn(forbidden, text)

    def test_sca_adaptation_changes_only_payload_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            package = self._extract(Path(temp_text))
            receipt = json.loads(
                (
                    package
                    / "validation/sca_namespace_adaptation_receipt.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                receipt["allowed_changed_files"], ["sca_cfg.json", "sca_cfg_D.json"]
            )
            self.assertFalse(receipt["operator_json_changed"])
            self.assertFalse(receipt["source_json_rewritten"])
            for name in ("sca_cfg.json", "sca_cfg_D.json"):
                value = json.loads(
                    (package / "workload/runtime" / name).read_text(encoding="utf-8")
                )
                for item in value.values():
                    if isinstance(item, dict) and isinstance(item.get("path"), str):
                        self.assertTrue(
                            item["path"].startswith(
                                f"install/cfg_pkg/{INSTALL_NAME}/"
                            )
                        )

    def test_package_manifest_and_paths_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            package = self._extract(Path(temp_text))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["files"], file_records(package, exclude_manifest=True)
            )
            self.assertEqual(
                preflight_package(package, INSTALL_NAME)["status"], "pass"
            )
            (package / "transfer-added-file.txt").write_text(
                "ignored transport artifact\n", encoding="utf-8"
            )
            report = preflight_package(package, INSTALL_NAME)
            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["package_exact_file_set_check_performed"])
            self.assertTrue(report["required_runtime_payload_validated"])
        with zipfile.ZipFile(OUTPUT_ZIP) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            relative = PurePosixPath(name)
            self.assertFalse(relative.is_absolute())
            self.assertNotIn("..", relative.parts)
            self.assertEqual(relative.parts[0], INSTALL_NAME)

    def test_compile_failure_collection_records_staged_tail_without_samefile_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            root = Path(temp_text)
            server_root = root / "server"
            package_root = root / "package"
            evidence_root = root / "evidence"
            run_dir = root / "run"
            cfg_root = (
                server_root / "install" / "cfg_pkg" / INSTALL_NAME
            )
            sim_results = run_dir / "sim_results"
            for directory in (
                server_root,
                package_root,
                evidence_root,
                cfg_root,
                sim_results,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            (package_root / "TEST_PACKAGE_MANIFEST.json").write_text(
                "{}\n", encoding="utf-8", newline="\n"
            )
            (cfg_root / "sca_cfg.json").write_text(
                "{}\n", encoding="utf-8", newline="\n"
            )
            (cfg_root / "sca_cfg_D.json").write_text(
                "{}\n", encoding="utf-8", newline="\n"
            )
            for name in (
                "VERSION_UNBOUND_PROFILE.json",
                "package_preflight.json",
                "installed_preflight.json",
            ):
                (evidence_root / name).write_text(
                    "{}\n", encoding="utf-8", newline="\n"
                )
            (evidence_root / "SERVER_RESULT_GATE.json").write_text(
                json.dumps(
                    {
                        "status": "SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE"
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            for name, value in (
                ("server_command.txt", "compile command\n"),
                ("compile_exit_status.txt", "1\n"),
                ("sim_exit_status.txt", "125\n"),
                ("run_exit_status.txt", "1\n"),
            ):
                (evidence_root / name).write_text(
                    value, encoding="utf-8", newline="\n"
                )
            compile_tail = "compile failed before simulation\n"
            (sim_results / "compile_driver.log").write_text(
                compile_tail, encoding="utf-8", newline="\n"
            )

            report = collect(
                server_root,
                package_root,
                INSTALL_NAME,
                evidence_root,
                run_dir,
                1,
                "compile command",
            )

            return_zip = Path(report["zip"])
            sidecar = Path(report["sidecar"])
            self.assertTrue(return_zip.is_file())
            self.assertTrue(sidecar.is_file())
            self.assertEqual(
                report["classification"],
                "SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE",
            )
            self.assertEqual(report["required_missing"], [])
            self.assertEqual(
                sidecar.read_text(encoding="ascii"),
                f"{sha256(return_zip)}  {return_zip.name}\n",
            )
            with zipfile.ZipFile(return_zip) as archive:
                log_name = (
                    f"{INSTALL_NAME}_return/logs/compile_driver_tail.log"
                )
                self.assertIn(log_name, archive.namelist())
                self.assertEqual(
                    archive.read(log_name).decode("utf-8"),
                    compile_tail,
                )


if __name__ == "__main__":
    unittest.main()
