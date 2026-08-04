from __future__ import annotations

import unittest

from tools.analyze_gap_sim_path import (
    ReadReturn,
    Request,
    WriteData,
    associate_returns,
    decode_int32_write_stream,
    expected_read_addresses,
)


class GapSimPathTests(unittest.TestCase):
    def test_gap_request_split_count_and_prefix(self) -> None:
        addresses, blocks = expected_read_addresses(
            outer_count=256,
            outer_stride_bytes=392,
            inner_start=0,
            inner_end=56,
            inner_stride=4,
            inner_dim_stride_bytes=8,
            transaction_bytes=32,
        )
        self.assertEqual(len(addresses), 8960)
        self.assertEqual(blocks[0], (0, 28))
        self.assertEqual(blocks[1], (28, 70))
        self.assertEqual(addresses[:12], list(range(12)))
        self.assertEqual(
            addresses[28:40],
            [24, 25, 26, 26, 27, 28, 28, 29, 30, 30, 31, 32],
        )

    def test_aligned_and_unaligned_transactions(self) -> None:
        aligned, _ = expected_read_addresses(
            outer_count=1,
            outer_stride_bytes=16,
            inner_start=0,
            inner_end=1,
            inner_stride=1,
            inner_dim_stride_bytes=1,
            transaction_bytes=32,
        )
        unaligned, _ = expected_read_addresses(
            outer_count=1,
            outer_stride_bytes=16,
            inner_start=8,
            inner_end=9,
            inner_stride=1,
            inner_dim_stride_bytes=1,
            transaction_bytes=32,
        )
        self.assertEqual(aligned, [0, 1])
        self.assertEqual(unaligned, [0, 1, 2])

    def test_returns_are_associated_per_physical_channel(self) -> None:
        requests = [
            Request(time=10, channel=0, address=0x10),
            Request(time=10, channel=1, address=0x11),
        ]
        returns = [
            ReadReturn(
                return_time=20,
                return_channel=1,
                issue_channel=0,
                issue_time=10,
                data=0xAA,
            ),
            ReadReturn(
                return_time=21,
                return_channel=0,
                issue_channel=1,
                issue_time=10,
                data=0xBB,
            ),
        ]

        associated, unmatched, pending = associate_returns(requests, returns)

        self.assertEqual(associated, [(0x11, 0xAA), (0x10, 0xBB)])
        self.assertEqual(unmatched, 0)
        self.assertEqual(pending, 0)

    def test_odd_write_stream_is_still_decoded_for_partial_diagnosis(self) -> None:
        records = [
            WriteData(time=10, channel=0, data=1),
            WriteData(time=11, channel=1, data=2),
            WriteData(time=12, channel=1, data=3),
        ]

        values = decode_int32_write_stream(records)

        self.assertEqual(len(values), 12)
        self.assertEqual(values[0], 1)
        self.assertEqual(values[4], 2)
        self.assertEqual(values[8], 3)


if __name__ == "__main__":
    unittest.main()
