from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_gap_stock_rtl_identity import (
    EXPECTED_PHASES,
    IDENTITY_SCHEMA,
    REQUIRED_FOCUS_RTL,
    build_receipt,
)


def _identity(phase: str) -> dict:
    focus = {
        relative: {
            "exists": True,
            "size_bytes": 123,
            "sha256": f"raw-{relative}",
            "canonical_text_sha256": f"text-{relative}",
        }
        for relative in sorted(REQUIRED_FOCUS_RTL)
    }
    return {
        "schema": IDENTITY_SCHEMA,
        "phase": phase,
        "server_command": "make compile sim",
        "test_package": {
            "install_name": "gap_v10",
            "manifest": {"sha256": "manifest-sha"},
        },
        "rtl_tree": {"tree_sha256": "rtl-tree-sha"},
        "artifacts": {
            "focus_rtl_files": focus,
            "makefile": {
                "exists": True,
                "size_bytes": 10,
                "sha256": "makefile-sha",
            },
            "active_filelist": {
                "exists": True,
                "size_bytes": 20,
                "sha256": "filelist-sha",
            },
            "testbench": {
                "exists": True,
                "size_bytes": 30,
                "sha256": "tb-sha",
            },
        },
    }


class GapStockRtlIdentityTests(unittest.TestCase):
    def _write(self, root: Path, documents: list[dict]) -> list[Path]:
        paths = []
        for index, document in enumerate(documents):
            path = root / f"identity-{index}.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            paths.append(path)
        return paths

    def test_stable_stock_rtl_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = [_identity(phase) for phase in EXPECTED_PHASES]
            receipt = build_receipt(self._write(root, documents))
        self.assertTrue(receipt["functional_rtl_unchanged"])
        self.assertEqual(receipt["status"], "rtl_unchanged")
        self.assertFalse(receipt["functional_rtl_write_requested"])
        self.assertFalse(receipt["restore_required"])

    def test_focused_rtl_change_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = [_identity(phase) for phase in EXPECTED_PHASES]
            target = sorted(REQUIRED_FOCUS_RTL)[0]
            documents[2]["artifacts"]["focus_rtl_files"][target][
                "sha256"
            ] = "changed"
            receipt = build_receipt(self._write(root, documents))
        self.assertFalse(receipt["functional_rtl_unchanged"])
        self.assertEqual(receipt["status"], "rtl_identity_changed")


if __name__ == "__main__":
    unittest.main()
