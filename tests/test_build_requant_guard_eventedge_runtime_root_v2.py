import json
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from tools.build_requant_guard_eventedge_runtime_root_v2 import (
    PROFILE_RULE,
    SERVER_RULE_SHA256,
    SOURCE_SHA256,
    SOURCE_ZIP,
    TARGET_NAME,
    TARGET_ZIP,
    records,
    sha256,
    validate_zip,
)


class RequantRuntimeRootV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(TARGET_ZIP.is_file())

    def _extract(self, root: Path) -> Path:
        with zipfile.ZipFile(TARGET_ZIP) as archive:
            archive.extractall(root)
        return root / TARGET_NAME

    def test_source_v1_is_frozen(self) -> None:
        self.assertEqual(sha256(SOURCE_ZIP), SOURCE_SHA256)

    def test_zip_exact_set_sidecar_and_no_rtl(self) -> None:
        report = validate_zip(TARGET_ZIP)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["rtl_entry_count"], 0)
        sidecar = TARGET_ZIP.with_suffix(".zip.sha256")
        self.assertEqual(
            sidecar.read_text(encoding="ascii"),
            f"{sha256(TARGET_ZIP)}  {TARGET_ZIP.name}\n",
        )

    def test_manifest_binds_current_rules_and_version_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._extract(Path(temp))
            manifest = json.loads(
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["files"], records(package, exclude_manifest=True))
            self.assertIn(PROFILE_RULE, manifest["rule_ids"])
            self.assertEqual(
                manifest["current_rule_receipts"]["server_rule_sha256"],
                SERVER_RULE_SHA256,
            )
            self.assertFalse(
                manifest["version_unbound_compatibility"][
                    "server_source_identity_bound"
                ]
            )
            self.assertFalse(manifest["counts_as_node0001_e4"])
            self.assertFalse(manifest["counts_as_node0001_e5"])

    def test_semantic_23_files_are_byte_identical_to_v1(self) -> None:
        with tempfile.TemporaryDirectory() as old_temp, tempfile.TemporaryDirectory() as new_temp:
            old_root = Path(old_temp)
            new_root = Path(new_temp)
            with zipfile.ZipFile(SOURCE_ZIP) as archive:
                archive.extractall(old_root)
            new_package = self._extract(new_root)
            old_package = old_root / SOURCE_ZIP.stem
            freeze = json.loads(
                (
                    new_package
                    / "validation/semantic_freeze_numeric_v1_to_eventedge_v1.json"
                ).read_text(encoding="utf-8")
            )
            for relative in freeze["files"]:
                self.assertEqual(
                    (old_package / relative).read_bytes(),
                    (new_package / relative).read_bytes(),
                )

    def test_entry_scripts_have_no_fixed_root_or_identity_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._extract(Path(temp))
            text = "\n".join(
                (package / relative).read_text(encoding="utf-8")
                for relative in (
                    "PREPARE_AND_RUN.sh",
                    "README.md",
                    "package_tools/requant_runtime_root_v2_server_runtime.py",
                    "package_tools/requant_node0001_server_runtime.py",
                )
            )
            for forbidden in (
                "NDP_copy01",
                "NDP_copy02",
                "NDP_copy03",
                "capture-identity",
                "verify-identity",
                "focused_rtl",
                "rtl_tree",
                "_git_identity",
            ):
                self.assertNotIn(forbidden, text)
            self.assertIn("/absolute/path/to/server_root", text)
            self.assertIn(
                'make -f Makefile.tb_NDP_Top_new_phy compile',
                text,
            )
            self.assertNotIn(
                'Missing required stock-RTL server input',
                text,
            )

    def test_only_exact_observer_target_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._extract(Path(temp))
            runtime = (
                package
                / "package_tools/requant_runtime_root_v2_server_runtime.py"
            ).read_text(encoding="utf-8")
            self.assertIn('TB_RELATIVE = "native_return_observer.svh"', runtime)
            self.assertNotIn("root.rglob(", runtime)
            self.assertNotIn("server_root.rglob(", runtime)
            self.assertNotIn("os.walk", runtime)
            self.assertIn("target.parent != root", runtime)

    def test_zip_paths_are_safe_and_single_rooted(self) -> None:
        with zipfile.ZipFile(TARGET_ZIP) as archive:
            names = archive.namelist()
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            relative = PurePosixPath(name)
            self.assertFalse(relative.is_absolute())
            self.assertNotIn("..", relative.parts)
            self.assertEqual(relative.parts[0], TARGET_NAME)


if __name__ == "__main__":
    unittest.main()
