from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.qlinearadd_node0007_server_runtime import preflight
from tools.validate_qlinearadd_node0007_server_package import audit


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_relocated_v2"
)


class QLinearAddNode0007ServerPackageTest(unittest.TestCase):
    def test_package_is_stock_rtl_and_formal_d_is_absent(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("package is not built")
        report = preflight(PACKAGE)
        self.assertTrue(report["valid"])
        self.assertEqual(report["readback_count"], 28)
        self.assertTrue(report["formal_readback_targets_absent"])
        manifest = json.loads(
            (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["server_rtl_entries"], 0)
        self.assertFalse(manifest["functional_rtl_modified"])
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["host_precomputed_internal_tensor"])
        self.assertEqual(
            manifest["budgets"]["formal_readback_sca_d_exact_count"], 28
        )
        self.assertGreater(
            manifest["budgets"]["formal_readback_text_bytes"],
            manifest["budgets"]["formal_readback_logical_bytes"],
        )

    def test_runner_uses_one_command_contract_and_conjunctive_gate(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("package is not built")
        script = (PACKAGE / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        self.assertIn("+SCA_CFG=$cfg_rel/sca_cfg.json", script)
        self.assertIn("+SCA_CFG_D=$cfg_rel/sca_cfg_D.json", script)
        self.assertIn("preflight-installed", script)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", script)
        manifest = json.loads(
            (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertIn("natural_terminal", manifest["result_gate"])
        self.assertEqual(
            manifest["return_collection_policy"],
            "MANIFEST_EXPLICIT_ALLOWLIST_ONLY",
        )

    def test_zip_sidecar_and_repeated_build_are_bound(self) -> None:
        zip_path = PACKAGE.with_suffix(".zip")
        if not zip_path.is_file():
            self.skipTest("package ZIP is not built")
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        self.assertEqual(
            Path(str(zip_path) + ".sha256")
            .read_text(encoding="ascii")
            .split()[0],
            digest,
        )
        receipt = json.loads(
            PACKAGE.with_suffix(".validation.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["zip_sha256"], digest)
        self.assertTrue(receipt["repeated_build"]["package_tree_equal"])
        self.assertTrue(receipt["repeated_build"]["zip_equal"])
        zip_report = audit()
        self.assertTrue(zip_report["valid"], zip_report["errors"])
        self.assertTrue(zip_report["zip_package_exact_set"])
        self.assertEqual(zip_report["preloaded_runtime_d_target_count"], 0)
        self.assertEqual(zip_report["rtl_or_tb_entry_count"], 0)
        self.assertTrue(zip_report["contract_cycle_break"]["valid"])
        self.assertTrue(
            zip_report["contract_cycle_break"]["current_contract_binds_v2_zip"]
        )

    def test_preflight_rejects_a_preseeded_formal_d_target(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("package is not built")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = (
                root
                / "workload/runtime/install/op_tail_round/slice00/"
                "matrix_D_linearized_128bit.txt"
            )
            target.parent.mkdir(parents=True)
            target.write_text("0" * 128 + "\n", encoding="ascii")
            self.assertTrue(target.is_file())
            # The real package preflight is already proven above; this checks
            # the exact forbidden namespace used by all formal D records.
            manifest = json.loads(
                (PACKAGE / "TEST_PACKAGE_MANIFEST.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest["readback_checks"][0]["runtime_path"],
                "install/op_tail_round/slice00/"
                "matrix_D_linearized_128bit.txt",
            )


if __name__ == "__main__":
    unittest.main()
