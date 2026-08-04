from __future__ import annotations

import unittest

from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    FIXED_STAGES,
    build_configs,
    validate_d_buffer_supply,
)
from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4 import (
    build_configs as build_source_configs,
)
from tools.build_qlinearadd_node0007_d_buffer_supply_v15 import ROOT


class QLinearAddNode0007DBufferSupplyV15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.before = build_source_configs(ROOT)
        cls.after = build_configs(ROOT)
        cls.proof = validate_d_buffer_supply(cls.after)

    def test_all_six_stage_write_supplies_are_conserved(self) -> None:
        self.assertTrue(self.proof["valid"])
        for record in self.proof["records"].values():
            self.assertTrue(record["conservation_valid"])
            self.assertEqual(
                record["transaction_bytes"], record["supplied_bytes"]
            )

    def test_only_three_known_32_byte_writes_change(self) -> None:
        for stage in self.after:
            before = self.before[stage]
            after = self.after[stage]
            old_row = before["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"]
            new_row = after["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"]
            old_end = before["buffer_config"]["buffer5"]["buf_end_row_addr"]
            new_end = after["buffer_config"]["buffer5"]["buf_end_row_addr"]
            if stage in FIXED_STAGES:
                self.assertEqual((old_row, new_row), (1, 2))
                self.assertEqual((old_end, new_end), (0, 1))
            else:
                self.assertEqual(old_row, new_row)
                self.assertEqual(old_end, new_end)

    def test_arithmetic_and_address_fields_are_unchanged(self) -> None:
        for stage in self.after:
            self.assertEqual(
                self.before[stage]["general_array"],
                self.after[stage]["general_array"],
            )
            self.assertEqual(
                self.before[stage]["dram_loop_configs"],
                self.after[stage]["dram_loop_configs"],
            )
            self.assertEqual(
                self.before[stage]["stream_engine"],
                self.after[stage]["stream_engine"],
            )


if __name__ == "__main__":
    unittest.main()
