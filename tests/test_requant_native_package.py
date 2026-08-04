from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.requant_native_package import (
    WAVE_SAMPLES,
    build_strict_configs,
    graph_spec,
    wave_active_slices,
)


ROOT = Path(__file__).resolve().parents[1]


class RequantNativePackageTests(unittest.TestCase):
    def test_strict_configs_cover_all_64_channels(self) -> None:
        configs, manifest = build_strict_configs(ROOT)
        self.assertEqual(len(configs), 24)
        channels = [
            channel
            for record in manifest["records"]
            for channel in record["channels"]
            if record["wave_index"] == 0
        ]
        self.assertEqual(channels, list(range(64)))
        for config in configs.values():
            self.assertEqual(config["dram_loop_configs"]["LC0"]["end"], 1)
            self.assertEqual(config["dram_loop_configs"]["LC1"]["end"], 3136)
            self.assertEqual(config["dram_loop_configs"]["LC2"]["end"], 784)
            self.assertEqual(
                config["stream_engine"]["stream0"]["dim_stride"][0], 32
            )

    def test_three_wave_dispatch_covers_every_sample_and_shard(self) -> None:
        graph = graph_spec()
        self.assertEqual(len(graph["operators"]), 24)
        self.assertEqual(
            sorted(sample for wave in WAVE_SAMPLES for sample in wave),
            list(range(16)),
        )
        for wave_index, samples in enumerate(WAVE_SAMPLES):
            observed = []
            for shard_index in range(8):
                slices = wave_active_slices(wave_index, shard_index)
                self.assertEqual(len(slices), len(samples))
                self.assertEqual(len(slices), len(set(slices)))
                observed.extend(slices)
            self.assertEqual(
                sorted(set(observed)),
                list(range(28)) if wave_index < 2 else list(range(8)),
            )


if __name__ == "__main__":
    unittest.main()
