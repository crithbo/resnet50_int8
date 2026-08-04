from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_server_workload import (
    DEFAULT_OUTPUT_REL,
    EXPECTED_TOP_LEVEL,
    GapServerWorkloadError,
    SLICE_COMPANION_FILES,
    build_gap_server_workload,
    validate_gap_server_workload,
)


ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / DEFAULT_OUTPUT_REL


class GapServerWorkloadTests(unittest.TestCase):
    def test_checked_workload_matches_server_passed_folder_shape(self) -> None:
        result = validate_gap_server_workload(ROOT, WORKLOAD)
        self.assertTrue(result["valid"])
        self.assertEqual(result["sca_reference_count"], 34)
        self.assertEqual(result["matrix_file_count"], 96)
        self.assertEqual(result["execplan_line_count"], 17)
        self.assertEqual(result["slice_count"], 16)
        self.assertEqual(set(result["top_level_entries"]), EXPECTED_TOP_LEVEL)
        for index in range(16):
            slice_root = WORKLOAD / "install" / "op0" / f"slice{index:02d}"
            self.assertEqual(
                {path.name for path in slice_root.iterdir() if path.is_file()},
                SLICE_COMPANION_FILES,
            )

    def test_crlf_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            copied = Path(temp) / "workload"
            shutil.copytree(WORKLOAD, copied)
            execplan = copied / "install/execplan.txt"
            execplan.write_bytes(execplan.read_bytes().replace(b"\n", b"\r\n"))
            with self.assertRaisesRegex(GapServerWorkloadError, "tree receipt differs"):
                validate_gap_server_workload(ROOT, copied)

    def test_fresh_rebuild_is_deterministic(self) -> None:
        expected = validate_gap_server_workload(ROOT, WORKLOAD)
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            rebuilt = Path(temp) / "gap_hwop0071_sum_graph"
            payload = build_gap_server_workload(ROOT, rebuilt)
            self.assertEqual(payload["tree_sha256"], expected["tree_sha256"])
            self.assertEqual(payload["file_count"], expected["file_count"])


if __name__ == "__main__":
    unittest.main()
