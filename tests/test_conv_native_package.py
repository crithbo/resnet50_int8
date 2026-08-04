from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.conv_native_package import (
    OP_ALLOCATION_BYTES,
    WAVE_SAMPLES,
    WAVE_SLICE_COUNTS,
    build_strict_configs,
    graph_spec,
)


ROOT = Path(__file__).resolve().parents[1]


class ConvNativePackageTests(unittest.TestCase):
    def test_three_wave_graph_covers_batch16(self) -> None:
        graph = graph_spec()
        self.assertEqual(len(graph["operators"]), 3)
        self.assertEqual(
            sorted(sample for wave in WAVE_SAMPLES for sample in wave),
            list(range(16)),
        )
        self.assertEqual(WAVE_SLICE_COUNTS, (28, 28, 8))
        self.assertEqual(
            [
                int(item["used_slices"], 0).bit_count()
                for item in graph["operators"]
            ],
            [28, 28, 8],
        )

    def test_address_only_configs_match_flat_native_allocations(self) -> None:
        configs, manifest = build_strict_configs(ROOT)
        self.assertEqual(len(configs), 3)
        self.assertEqual(
            manifest["operator_allocation_bytes"], OP_ALLOCATION_BYTES
        )
        for wave_index, config in configs.items():
            observed = {
                stream["target"]: int(stream["base_addr"], 0)
                for stream in config["stream_engine"].values()
            }
            base = wave_index * OP_ALLOCATION_BYTES
            self.assertEqual(
                observed,
                {
                    "A": base,
                    "B": base + 1024,
                    "C": base + 201728,
                    "D": base + 201792,
                },
            )


if __name__ == "__main__":
    unittest.main()
