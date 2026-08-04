from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.register_semantics import (
    build_register_semantics_contract,
    read_xlsx_table,
)


ROOT = Path(__file__).resolve().parents[1]


class RegisterSemanticsTests(unittest.TestCase):
    def test_repository_csv_builds_machine_contract(self) -> None:
        contract = build_register_semantics_contract(ROOT)
        self.assertEqual(contract["schema"], "ndpsim-register-semantics-contract-v1")
        self.assertGreaterEqual(contract["summary"]["config_row_count"], 100)
        self.assertGreaterEqual(contract["summary"]["encoder_field_map_count"], 10)
        self.assertTrue(
            contract["authority_policy"]["width_or_offset_conflict_requires_arbitration"]
        )

    def test_xlsx_reader_rejects_invalid_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.xlsx"
            path.write_bytes(b"not an xlsx")
            with self.assertRaises(ValueError):
                read_xlsx_table(path)

    def test_known_width_conflicts_remain_visible(self) -> None:
        contract = build_register_semantics_contract(ROOT)
        conflicts = {
            item["config_name"]
            for item in contract["rows"]
            if item["declared_width"] is not None
            and item["range_span"] is not None
            and item["declared_width"] != item["range_span"]
        }
        self.assertIn("dram_loop_configs.start", conflicts)
        self.assertIn("stream_engine.stream.address_remapping", conflicts)


if __name__ == "__main__":
    unittest.main()
