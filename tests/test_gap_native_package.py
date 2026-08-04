from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.gap_native_package import (
    CHANNELS,
    HEIGHT,
    WIDTH,
    c8hw8_pack,
    c8hw8_unpack,
    graph_spec,
    stream_reference_sum,
)


ROOT = Path(__file__).resolve().parents[1]


class GapNativePackageTests(unittest.TestCase):
    def test_c8hw8_roundtrip_and_stream_tail_reference(self) -> None:
        values = np.arange(CHANNELS * HEIGHT * WIDTH, dtype=np.uint32)
        source = (values % 251).astype(np.uint8).reshape(CHANNELS, HEIGHT, WIDTH)
        packed = c8hw8_pack(source)
        self.assertEqual(packed.shape, (256, 7, 7, 8))
        self.assertTrue(np.array_equal(c8hw8_unpack(packed), source))
        expected = source.astype(np.int32).sum(axis=(1, 2), keepdims=True)
        self.assertTrue(np.array_equal(stream_reference_sum(packed), expected))

    def test_graph_is_exact_low_16_slice_gap_abi(self) -> None:
        graph = graph_spec()
        op = graph["operators"][0]
        self.assertEqual(graph["used_slices"], "0b" + "0" * 12 + "1" * 16)
        self.assertEqual(op["used_slices"], graph["used_slices"])
        self.assertEqual(op["inputs"]["A"]["shape"], [1, 1, 100416])
        self.assertEqual(op["output"]["shape"], [2048, 1, 1])
        self.assertEqual(op["output"]["dtype"], "int32")


if __name__ == "__main__":
    unittest.main()
