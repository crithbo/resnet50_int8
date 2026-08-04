from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.validate_node0004_observer_four_way_binding import (
    STATUS_FAIL,
    STATUS_PASS,
    load_zip_entries,
    run_negative_controls,
    validate_entries,
    validate_zip,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
V7 = PACKAGE_DIR / "r5_n4_hw_v7_hangloc_bind.zip"
V8 = PACKAGE_DIR / "r5_n4_hw_v8_hangloc_fourway.zip"


def replaced(
    entries: dict[str, bytes],
    path: str,
    old: bytes,
    new: bytes,
) -> dict[str, bytes]:
    result = dict(entries)
    payload = result[path]
    if old not in payload:
        raise AssertionError(f"negative-control token missing in {path}: {old!r}")
    result[path] = payload.replace(old, new, 1)
    return result


class Node0004ObserverFourWayBindingTest(unittest.TestCase):
    def test_v7_fails_new_manifest_contract(self) -> None:
        result = validate_zip(V7)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], STATUS_FAIL)
        self.assertIn(
            "manifest observer_binding_four_way is missing",
            result["errors"],
        )

    def setUp(self) -> None:
        if not V8.is_file():
            self.skipTest("v8 four-way package is not built")
        self.root, self.entries, self.meta = load_zip_entries(V8)

    def test_v8_final_zip_passes(self) -> None:
        result = validate_zip(V8)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], STATUS_PASS)
        self.assertTrue(all(result["checks"].values()))

    def test_all_four_negative_controls_fail_closed(self) -> None:
        result = run_negative_controls(V8)
        self.assertTrue(result["all_failed_closed"])
        self.assertEqual(len(result["records"]), 4)

    def test_negative_missing_source_fails_closed(self) -> None:
        manifest = json.loads(self.entries["package_manifest.json"])
        source = manifest["observer_binding_four_way"]["source"]["path"]
        mutated = dict(self.entries)
        del mutated[source]
        result = validate_entries(self.root, mutated, self.meta)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], STATUS_FAIL)
        self.assertFalse(result["checks"]["source"])

    def test_negative_missing_incdir_fails_closed(self) -> None:
        mutated = replaced(
            self.entries,
            "PREPARE_AND_RUN.sh",
            b"+incdir+$package_root/tb_probe",
            b"+incdir+REMOVED",
        )
        result = validate_entries(self.root, mutated, self.meta)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], STATUS_FAIL)
        self.assertFalse(result["checks"]["include"])

    def test_negative_missing_enable_macro_fails_closed(self) -> None:
        mutated = replaced(
            self.entries,
            "PREPARE_AND_RUN.sh",
            b"+define+NATIVE_RETURN_OBSERVER_ENABLE ",
            b"",
        )
        result = validate_entries(self.root, mutated, self.meta)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], STATUS_FAIL)
        self.assertFalse(result["checks"]["compile_enable"])

    def test_negative_missing_runtime_return_fails_closed(self) -> None:
        manifest = json.loads(self.entries["package_manifest.json"])
        runtime = manifest["observer_binding_four_way"]["runtime_return"][
            "runtime_source"
        ]
        mutated = replaced(
            self.entries,
            runtime,
            b"runs/c0/return_observer.log",
            b"runs/c0/REMOVED.log",
        )
        result = validate_entries(self.root, mutated, self.meta)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], STATUS_FAIL)
        self.assertFalse(result["checks"]["runtime_return"])


if __name__ == "__main__":
    unittest.main()
