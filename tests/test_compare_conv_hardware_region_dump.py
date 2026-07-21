from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from resnet50_pipeline.conv_execplan_hardware import ConvHardwareExecplanError
from tools.compare_conv_hardware_region_dump import _extract_return_archive


class CompareConvHardwareRegionDumpTests(unittest.TestCase):
    def test_return_zip_extracts_one_bound_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "run1.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "v18_run1_return/run_metadata.json",
                    json.dumps({"server_run_id": "run1"}),
                )
                archive.writestr("v18_run1_return/readback/value.txt", "0\n")
            returned, record = _extract_return_archive(
                archive_path, root / "extracted", expected_run_id="run1"
            )
            self.assertEqual(returned.name, "v18_run1_return")
            self.assertEqual(record["server_run_id"], "run1")
            self.assertEqual(len(str(record["archive_sha256"])), 64)

    def test_return_zip_rejects_path_traversal_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "escape\n")
            with self.assertRaisesRegex(
                ConvHardwareExecplanError, "unsafe server return ZIP entry"
            ):
                _extract_return_archive(
                    archive_path, root / "extracted", expected_run_id="run1"
                )
            self.assertFalse((root / "escape.txt").exists())

    def test_return_zip_rejects_multiple_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "multiple.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("run1/run_metadata.json", "{}")
                archive.writestr("other/value.txt", "0\n")
            with self.assertRaisesRegex(
                ConvHardwareExecplanError, "must contain one root directory"
            ):
                _extract_return_archive(
                    archive_path, root / "extracted", expected_run_id="run1"
                )


if __name__ == "__main__":
    unittest.main()
