from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from resnet50_pipeline.native_json_maxpool_package import (
    SOURCE_CONFIG_SHA256,
    _load_reused_e2_tiles,
)
from tools.validate_maxpool_node0002_native_reuse_v4_final_zip import (
    INSTALL_NAME,
    ZIP_PATH,
    validate,
)


ROOT = Path(__file__).resolve().parents[1]


class MaxPoolNode0002NativeReuseV4Tests(unittest.TestCase):
    def test_reuses_frozen_e2_without_numeric_reanalysis(self) -> None:
        inputs, outputs, sources, records = _load_reused_e2_tiles(ROOT)
        self.assertEqual([value.shape for value in inputs], [(112, 112, 16)] * 2)
        self.assertEqual([value.shape for value in outputs], [(56, 56, 16)] * 2)
        self.assertFalse(sources["numeric_analysis_repeated"])
        self.assertEqual(sources["reuse_class"], "EXACT_FULL_OPERATOR")
        self.assertTrue(
            all(record["numeric_analysis_repeated"] is False for record in records)
        )

    def test_final_zip_keeps_source_json_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with zipfile.ZipFile(ZIP_PATH) as archive:
                archive.extractall(raw)
            package = Path(raw) / INSTALL_NAME
            source = (
                package
                / "workload/runtime/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json.original"
            )
            import hashlib

            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), SOURCE_CONFIG_SHA256)
            materialized = json.loads(
                (package / "validation/materialized_diff.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(materialized["operator_json_diff_count"], 0)
            self.assertEqual(materialized["semantic_non_base_diff_count"], 0)

    def test_observer_focused_systemverilog_compile(self) -> None:
        if shutil.which("iverilog") is None:
            self.skipTest("iverilog unavailable")
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "observer.out"
            result = subprocess.run(
                [
                    "iverilog",
                    "-g2012",
                    "-I",
                    str(ROOT / "tools"),
                    "-s",
                    "tb_maxpool_node0002_observer_compile",
                    "-o",
                    str(output),
                    str(
                        ROOT
                        / "tests/rtl/tb_maxpool_node0002_observer_compile.sv"
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_final_zip_rule_self_audit_passes(self) -> None:
        report = validate()
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["all_negative_controls_fail_closed"])


if __name__ == "__main__":
    unittest.main()
