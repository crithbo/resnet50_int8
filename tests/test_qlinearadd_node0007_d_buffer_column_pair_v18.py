from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    FIXED_STAGES,
    build_configs,
    validate_d_buffer_column_pair,
)
from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    build_configs as build_v15_configs,
)


ROOT = Path(__file__).resolve().parents[1]


class QLinearAddNode0007DBufferColumnPairV18Tests(unittest.TestCase):
    def test_exact_two_half_row_windows(self) -> None:
        report = validate_d_buffer_column_pair(build_configs(ROOT))
        self.assertTrue(report["valid"])
        self.assertTrue(report["old_scalar_formula_refuted"])
        for stage in FIXED_STAGES:
            record = report["records"][stage]
            self.assertEqual(record["row_indices"], [0])
            self.assertEqual(record["column_indices"], [0, 16])
            self.assertEqual(record["covered_byte_offsets"], list(range(32)))

    def test_only_authorized_buffer_addressing_leaves_change(self) -> None:
        before = build_v15_configs(ROOT)
        after = build_configs(ROOT)
        expected = {
            ("buffer_config", "buffer5", "buf_end_row_addr"),
            ("buffer_loop_configs", "GROUP2", "ROW_LC", "end"),
            ("buffer_loop_configs", "GROUP2", "COL_LC", "end"),
            ("buffer_loop_configs", "GROUP2", "COL_LC", "stride"),
        }
        for stage in before:
            changed = set()
            for path in expected:
                old = before[stage]
                new = after[stage]
                for key in path:
                    old = old[key]
                    new = new[key]
                if old != new:
                    changed.add(path)
            if stage in FIXED_STAGES:
                self.assertEqual(changed, expected)
            else:
                self.assertEqual(before[stage], after[stage])

    def test_old_row_only_formula_is_rejected_by_physical_widths(self) -> None:
        old = build_v15_configs(ROOT)["op_relocation_pad"]
        rows = len(
            range(
                old["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["start"],
                old["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"],
                old["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["stride"],
            )
        )
        self.assertEqual(rows * old["stream_engine"]["stream2"]["buf_spatial_size"], 32)
        self.assertEqual(rows * 32, 64)
        self.assertNotEqual(rows * 32, 32)


if __name__ == "__main__":
    unittest.main()
