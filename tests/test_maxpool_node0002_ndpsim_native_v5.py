from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n2_maxpool_ndpsim_native_v5.zip"
)
SIDECAR = ZIP.with_suffix(".zip.sha256")


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module(
    "maxpool_native_v5_validator",
    "tools/validate_maxpool_node0002_ndpsim_native_v5.py",
)
runtime = load_module(
    "maxpool_native_v5_runtime",
    "tools/maxpool_node0002_ndpsim_native_runtime_v5.py",
)


class MaxPoolNode0002NativeV5Test(unittest.TestCase):
    def extract(self, root: Path) -> Path:
        return validator.extract(ZIP, root)

    def test_final_zip_static_native_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.extract(Path(temporary))
            receipt = validator.validate_static(package, ZIP, SIDECAR)
        self.assertTrue(receipt["valid"])
        self.assertTrue(
            receipt["checks"]["materialized_only_two_base_leaves"]
        )

    def test_source_json_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.extract(Path(temporary))
            source = (
                package
                / "workload/native/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json"
            )
            self.assertEqual(validator.sha256(source), validator.SOURCE_SHA)

    def test_wrong_source_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.extract(Path(temporary))
            source = (
                package
                / "workload/native/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json"
            )
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaises(runtime.NativeMaxPoolRuntimeError):
                runtime.preflight_package(package)

    def test_missing_native_operator_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.extract(Path(temporary))
            (
                package
                / "workload/native/jsons/"
                "op0_maxpool_config_16_112_112_stride2_padding1.json"
            ).unlink()
            with self.assertRaises(runtime.NativeMaxPoolRuntimeError):
                runtime.preflight_package(package)


if __name__ == "__main__":
    unittest.main()
