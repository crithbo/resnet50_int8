from __future__ import annotations

import unittest
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from resnet50_pipeline.gap_complete_config_only import (
    ARTIFACT_ROOT,
    CONFIG_ROOT,
    FINAL_BASE,
    FINAL_BYTES,
    SCALED_BASE,
    SCALED_BYTES,
    SUM_BASE,
    SUM_BYTES,
    build_logical_tail_configs,
    bind_tail_addresses,
    run_config_bound_full_simulator,
    validate_local_e2,
    validate_tail_materialization,
)
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator
from tools.gap_node0071_complete_server_runtime import (
    RuntimeGateError,
    preflight,
    preflight_installed,
)


ROOT = Path(__file__).resolve().parents[1]


class GapNode0071CompleteConfigOnlyTest(unittest.TestCase):
    def test_exact_tail_configs_are_strict(self) -> None:
        final = bind_tail_addresses(build_logical_tail_configs(ROOT))
        for kind, config in final.items():
            report = OperatorConfigValidator().validate(config, source=kind)
            self.assertTrue(report.valid, report.to_dict().get("first_error"))

    def test_regions_are_nonoverlapping_and_alias_producers(self) -> None:
        self.assertLessEqual(SUM_BASE + SUM_BYTES, SCALED_BASE)
        self.assertLessEqual(SCALED_BASE + SCALED_BYTES, FINAL_BASE)
        self.assertEqual(SUM_BYTES, 8192)
        self.assertEqual(SCALED_BYTES, 8192)
        self.assertEqual(FINAL_BYTES, 2048)

    def test_materialized_coverage(self) -> None:
        if not (ROOT / CONFIG_ROOT).is_dir():
            self.skipTest("complete GAP local materialization absent")
        report = validate_tail_materialization(ROOT, ROOT / CONFIG_ROOT)
        self.assertTrue(report["valid"])
        for item in report["occurrence_and_coverage"].values():
            if isinstance(item, dict):
                self.assertTrue(item["exact_region_coverage"])

    def test_full_config_bound_e2(self) -> None:
        if not (ROOT / CONFIG_ROOT).is_dir():
            self.skipTest("complete GAP local materialization absent")
        report = run_config_bound_full_simulator(ROOT, ROOT / CONFIG_ROOT)
        self.assertTrue(report["valid"])
        self.assertEqual(report["mismatch_count"], 0)
        self.assertFalse(report["sum_numeric_analysis_repeated"])
        self.assertTrue(report["consumed_sum_reuse_asset"])

    def test_frozen_sum_and_full_local_gate(self) -> None:
        if not (ROOT / ARTIFACT_ROOT).is_dir():
            self.skipTest("complete GAP local artifact absent")
        report = validate_local_e2(ROOT)
        self.assertTrue(report["valid"])
        self.assertTrue(report["complete_gap_target"])
        self.assertFalse(report["sum_numeric_analysis_repeated"])

    def test_server_package_ready_not_run(self) -> None:
        package = (
            ROOT
            / "artifacts/operator_config_validation/r5-server-test-packages"
            / "r5_node0071_gap_hw_v1"
        )
        if not package.is_dir():
            self.skipTest("complete GAP server package absent")
        checked = preflight(package)
        self.assertTrue(checked["valid"])
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "PACKAGE_READY_NOT_RUN")
        self.assertEqual(manifest["compile_count"], 1)
        self.assertEqual(manifest["simulation_run_count"], 1)
        self.assertEqual(len(manifest["readback_checks"]), 48)
        self.assertFalse(manifest["server_source_preflight_performed"])
        self.assertFalse(manifest["host_precomputed_internal_tensor_replay"])
        for record in manifest["readback_checks"]:
            self.assertFalse(
                (package / "workload" / record["runtime_path"]).exists()
            )
        archive = package.with_suffix(".zip")
        expected = Path(str(archive) + ".sha256").read_text(
            encoding="ascii"
        ).split()[0]
        self.assertEqual(
            hashlib.sha256(archive.read_bytes()).hexdigest(), expected
        )

    def test_post_install_preseeded_readback_is_rejected(self) -> None:
        package = (
            ROOT
            / "artifacts/operator_config_validation/r5-server-test-packages"
            / "r5_node0071_gap_hw_v1"
        )
        if not package.is_dir():
            self.skipTest("complete GAP server package absent")
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "cfg"
            shutil.copytree(package / "workload", installed)
            self.assertTrue(preflight_installed(package, installed)["valid"])
            target = installed / manifest["readback_checks"][0]["runtime_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("0" * 128 + "\n", encoding="ascii")
            with self.assertRaisesRegex(
                RuntimeGateError, "PACKAGE_PRESEEDED_READBACK_TARGET"
            ):
                preflight_installed(package, installed)


if __name__ == "__main__":
    unittest.main()
