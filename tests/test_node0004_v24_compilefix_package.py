from __future__ import annotations

import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
ZIP_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{NAME}.zip"
)
AUDIT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-node0004-v24-final-release-diagnostic"
    / "final_zip_rule_self_audit.json"
)
SCOPE_PATH = AUDIT_PATH.parent / "observer_syntax_scope.json"


class Node0004V24CompileFixPackageTest(unittest.TestCase):
    def member(self, path: str) -> bytes:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            return archive.read(f"{NAME}/{path}")

    def test_final_audit_passes_with_all_negatives(self) -> None:
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        self.assertTrue(audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(audit["error_count"], 0)
        self.assertTrue(audit["all_required_negative_controls_fail_closed"])

    def test_observer_declares_updates_and_consumes_edge_counter(self) -> None:
        observer = self.member(
            "tb_probe/native_return_observer.svh"
        ).decode("utf-8")
        self.assertNotIn("return_obs_buf45_wr_edge_count", observer)
        self.assertEqual(
            observer.count(
                "longint unsigned return_obs_fr_buffer5_write_edges;"
            ),
            1,
        )
        self.assertEqual(
            observer.count("return_obs_fr_buffer5_write_edges++;"), 1
        )
        self.assertIn("!return_obs_fr_prev_buffer5_write", observer)

    def test_return_manifest_and_package_identity_are_collected(self) -> None:
        collector = self.member(
            "package_tools/node0004_hang_localization_runtime_v7.py"
        ).decode("utf-8")
        runtime = self.member(
            "package_tools/node0004_hang_localization_runtime.py"
        ).decode("utf-8")
        self.assertIn('"RETURN_MANIFEST.json"', collector)
        self.assertIn(
            '"evidence/returned_package_manifest.json"', collector
        )
        self.assertIn(
            '{"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}', runtime
        )

    def test_focused_hdl_scope_gate_is_not_safe_stub_claim(self) -> None:
        scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
        self.assertTrue(scope["valid"])
        self.assertEqual(
            scope["focused_compatible_frontend"]["positive"]["exit_code"], 0
        )
        self.assertTrue(scope["all_negative_controls_fail_closed"])
        self.assertFalse(scope["safe_compile_stub_used_as_hdl_evidence"])


if __name__ == "__main__":
    unittest.main()
