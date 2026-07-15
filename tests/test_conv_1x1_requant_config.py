from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.w5_conv_preflight import _load_npy, _record_by_hw_op
from tools.generate_conv_1x1_requant_real import (
    GA_MAC_KEYS,
    OUTPUT_ROOT,
    PROJECT_ROOT,
    ROUND_MAGIC_BITS,
    _real_qparams,
    build_bundle,
)


class Conv1x1RealRequantConfigTests(unittest.TestCase):
    def test_checked_in_shards_are_exact_and_cover_each_channel_once(self) -> None:
        manifest, files = build_bundle()
        self.assertEqual(set(files), {"manifest.json", *(f"shard-{i:02d}.json" for i in range(8))})
        for name, expected in files.items():
            self.assertEqual((OUTPUT_ROOT / name).read_bytes(), expected)
        covered = [channel for shard in manifest["shards"] for channel in shard["channels"]]
        self.assertEqual(sorted(covered), list(range(64)))
        self.assertEqual(len(set(covered)), 64)
        self.assertEqual(manifest["coverage"]["flush_count_per_logical_output"], 1)
        for shard in manifest["shards"]:
            self.assertEqual(shard["p_base_offset"] % 16, 0)
            self.assertEqual(shard["staged_d_base_offset"] % 16, 0)
            config = json.loads((PROJECT_ROOT / shard["config_path"]).read_text())
            self.assertEqual(config["dram_loop_configs"]["LC1"]["end"], 9408)
            self.assertEqual(config["dram_loop_configs"]["LC2"]["end"], 2352)
            pe_array = config["general_array"]["PE_array"]
            self.assertEqual(
                [pe_array[key]["inport1"]["constant"] for key in GA_MAC_KEYS],
                shard["multiplier_float32"],
            )

    def test_real_full_operator_magic_requant_and_staging_are_bit_exact(self) -> None:
        typed = json.loads((PROJECT_ROOT / "contracts/typed_config_parameter_contract.json").read_text())
        record = _record_by_hw_op(typed, "hwop-0004-01")
        subop_root = PROJECT_ROOT / "artifacts" / "w3" / "subop_batch16"
        runtime_root = PROJECT_ROOT / "artifacts" / "w3" / "golden_batch16"
        subop_manifest = json.loads((subop_root / "manifest.json").read_text())
        runtime_manifest = json.loads((runtime_root / "manifest.json").read_text())
        p_desc = record["ports"]["inputs"][0]
        d_desc = record["ports"]["outputs"][0]
        accumulator = _load_npy(
            subop_root,
            subop_manifest,
            subop_manifest["internal_tensors"][p_desc["tensor_id"]],
        )
        golden_d = _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][d_desc["tensor_id"]],
        )
        multiplier, output_zero_point, _ = _real_qparams()
        actual = np.empty_like(golden_d)
        flush_count = np.zeros(64, dtype=np.uint8)
        for shard in build_bundle()[0]["shards"]:
            channels = np.asarray(shard["channels"], dtype=np.int64)
            scaled = accumulator[:, channels].astype(np.float32) * multiplier[channels].reshape(
                1, 8, 1, 1
            )
            magic = np.float32(12582912.0 + output_zero_point)
            rounded = (scaled + magic).view(np.int32).astype(np.int64) - ROUND_MAGIC_BITS
            actual[:, channels] = np.clip(rounded, 0, 255).astype(np.uint8)
            flush_count[channels] += 1
        self.assertTrue(np.array_equal(flush_count, np.ones(64, dtype=np.uint8)))
        self.assertTrue(np.array_equal(actual, golden_d))

        # The two aligned staging halves reconstruct the canonical NHWK tile exactly.
        canonical = np.moveaxis(actual[:3, :16], 1, -1)
        low = canonical[..., :8].copy()
        high = canonical[..., 8:].copy()
        rebuilt = np.concatenate((low, high), axis=-1)
        self.assertTrue(np.array_equal(rebuilt, canonical))
        self.assertEqual(low.nbytes, 75264)
        self.assertEqual(high.nbytes, 75264)


if __name__ == "__main__":
    unittest.main()
