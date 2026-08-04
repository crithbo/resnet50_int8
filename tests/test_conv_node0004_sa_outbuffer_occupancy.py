import unittest


def stock_count_next(count: int, initial_write: bool, alu_write: bool, output_read: bool) -> int:
    """Model SA_PE_Outbuffer.sv:453-456,501-516 exactly."""
    del alu_write  # The defect: an accepted ALU write is absent from wr_cnt_update.
    write_update = initial_write
    if write_update and output_read:
        return count
    if write_update:
        return count + 4
    if output_read:
        return count - 1
    return count


def repaired_count_next(count: int, initial_write: bool, alu_write: bool, output_read: bool) -> int:
    """Required occupancy arithmetic: four initial slots, one ALU slot, one output read."""
    return count + (4 if initial_write else 0) + (1 if alu_write else 0) - (
        1 if output_read else 0
    )


def naive_or_count_next(count: int, initial_write: bool, alu_write: bool, output_read: bool) -> int:
    """Rejected repair: OR both write enables into the existing +4/hold state machine."""
    write_update = initial_write or alu_write
    if write_update and output_read:
        return count
    if write_update:
        return count + 4
    if output_read:
        return count - 1
    return count


class TestConvNode0004SaOutbufferOccupancy(unittest.TestCase):
    def test_positive_control_initial_write_is_four_slots(self) -> None:
        self.assertEqual(stock_count_next(0, True, False, False), 4)
        self.assertEqual(repaired_count_next(0, True, False, False), 4)

    def test_negative_control_stock_drops_single_alu_write(self) -> None:
        self.assertEqual(stock_count_next(0, False, True, False), 0)
        self.assertEqual(repaired_count_next(0, False, True, False), 1)

    def test_negative_control_simple_or_counts_alu_write_as_four(self) -> None:
        self.assertEqual(naive_or_count_next(0, False, True, False), 4)
        self.assertEqual(repaired_count_next(0, False, True, False), 1)

    def test_negative_control_simple_or_loses_mixed_delta(self) -> None:
        # Same-group initial(+4), ALU(+1), and output(-1) must net +4.
        self.assertEqual(naive_or_count_next(0, True, True, True), 0)
        self.assertEqual(repaired_count_next(0, True, True, True), 4)


if __name__ == "__main__":
    unittest.main()
