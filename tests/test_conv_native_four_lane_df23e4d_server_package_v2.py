from __future__ import annotations

import hashlib
import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP_PATH = PACKAGE_ROOT / "r5_n4_df23e4d_p4.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
BUILD_RECEIPT = PACKAGE_ROOT / "r5_n4_df23e4d_p4.validation.json"
FINAL_AUDIT = PACKAGE_ROOT / "r5_n4_df23e4d_p4.final_zip_audit.json"
INSTALL_NAME = "r5_n4_df23e4d_p4"
EXPECTED_SOURCE_V1_SHA256 = (
    "5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f"
)
SERVER_MISSING_WITNESSES = (
    "workload/runtime/runs/t000/install/cfg_pkg/"
    "op_mul_w0_s00_resnet50_requant_node0004_mul_w0_s00_bitstream_128b.bin",
    "workload/runtime/runs/t000/install/cfg_pkg/"
    "op_round_w0_s00_resnet50_requant_node0004_round_w0_s00_bitstream_128b.bin",
    "workload/runtime/runs/t000/install/op_round_w0_s00/slice00/"
    "matrix_A_linearized_128bit.txt",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConvNativeFourLaneDf23e4dServerPackageV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        cls.audit = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
        with zipfile.ZipFile(ZIP_PATH) as archive:
            cls.bad_member = archive.testzip()
            cls.members = set(archive.namelist())
            cls.manifest = json.loads(
                archive.read(f"{INSTALL_NAME}/package_manifest.json")
            )

    def test_delivery_identity_and_determinism(self) -> None:
        digest = sha256(ZIP_PATH)
        self.assertEqual(
            SIDECAR_PATH.read_text(encoding="ascii"),
            f"{digest}  {ZIP_PATH.name}\n",
        )
        self.assertEqual(self.build["zip_sha256"], digest)
        self.assertTrue(
            self.build["deterministic_double_build"]["zip_sha256_equal"]
        )
        self.assertTrue(
            self.build["deterministic_double_build"][
                "exact_file_records_equal"
            ]
        )
        self.assertEqual(
            self.build["source_v1_zip_sha256"],
            EXPECTED_SOURCE_V1_SHA256,
        )

    def test_fresh_extract_witnesses_are_present(self) -> None:
        self.assertIsNone(self.bad_member)
        for relative in SERVER_MISSING_WITNESSES:
            self.assertIn(f"{INSTALL_NAME}/{relative}", self.members)
            self.assertIn(relative, self.manifest["files"])

    def test_final_audit_and_path_budget_are_closed(self) -> None:
        self.assertEqual(self.audit["status"], "PACKAGE_READY_NOT_RUN")
        self.assertTrue(self.audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(self.audit["errors"], [])
        self.assertTrue(
            all(self.audit["delivery_successor_checks"].values())
        )
        self.assertTrue(
            all(self.audit["path_length_negative_controls"].values())
        )
        budget = self.audit["path_length_budget_gate"]["declared"]
        self.assertLessEqual(
            budget["max_projected_absolute_path_chars"],
            budget["max_projected_absolute_path_limit_chars"],
        )
        self.assertLessEqual(budget["max_inner_suffix_chars"], 128)
        self.assertLessEqual(budget["max_inner_depth"], 8)

    def test_candidate_boundary_and_workload_identity(self) -> None:
        self.assertEqual(self.manifest["install_name"], INSTALL_NAME)
        self.assertEqual(
            self.manifest["candidate_class"],
            "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        )
        self.assertFalse(self.manifest["candidate_release"])
        self.assertEqual(self.manifest["functional_rtl_file_count"], 0)
        identity = self.audit["v1_v2_workload_identity"]
        self.assertTrue(identity["valid"])
        self.assertEqual(identity["missing"], [])
        self.assertEqual(identity["extra"], [])
        self.assertEqual(identity["changed"], [])


if __name__ == "__main__":
    unittest.main()
