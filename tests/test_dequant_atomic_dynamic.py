from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.dequant_atomic_dynamic import (
    CONFIG_ROOT_REL,
    CONTRACT_REL,
    REPORT_REL,
    build_vectors,
    derive_config,
    materialize_bundle,
)
from resnet50_pipeline.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class DequantAtomicDynamicTests(unittest.TestCase):
    def test_config_is_exact_small_shape_derivation(self) -> None:
        config, provenance = derive_config(ROOT)
        self.assertEqual(config["dram_loop_configs"]["LC1"]["end"], 1)
        self.assertEqual(config["dram_loop_configs"]["LC3"]["end"], 1)
        self.assertEqual(
            config["stream_engine"]["stream0"]["dim_stride"],
            [16, 16, 16],
        )
        self.assertEqual(
            config["stream_engine"]["stream2"]["dim_stride"],
            [64, 64, 64],
        )
        self.assertEqual(
            config["stream_engine"]["stream0"]["base_addr"], "0x00000000"
        )
        self.assertEqual(
            config["stream_engine"]["stream2"]["base_addr"], "0x00000010"
        )
        self.assertEqual(len(provenance["changed_leaves"]), 6)
        self.assertTrue(provenance["all_other_leaves_unchanged"])
        self.assertEqual(
            config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"], 4
        )
        self.assertEqual(
            provenance["d_buffer_supply"],
            {
                "transaction_bytes": 64,
                "buffer_bytes_per_request": 16,
                "row_trip_count": 4,
                "supply_bytes": 64,
                "last_row_index": 3,
            },
        )
        self.assertTrue(
            all(
                pe["transout_last_index"] is None
                for pe in config["general_array"]["PE_array"].values()
            )
        )

    def test_vectors_cover_zero_point_and_extremes(self) -> None:
        source, golden, coverage = build_vectors()
        self.assertEqual(source.shape, (2, 16))
        self.assertEqual(source.dtype, np.dtype("uint8"))
        self.assertEqual(golden.shape, (2, 16))
        self.assertEqual(golden.dtype, np.dtype("float32"))
        self.assertGreater(coverage["below_zero_point_count"], 0)
        self.assertGreater(coverage["equal_zero_point_count"], 0)
        self.assertGreater(coverage["above_zero_point_count"], 0)
        self.assertEqual(coverage["contains_59_60_61_per_slice"], [True, True])
        self.assertTrue(coverage["slice1_is_slice0_rotation"])

    def test_lifecycle_and_write_contract_match_stock_tb(self) -> None:
        root = ROOT / CONFIG_ROOT_REL
        lifecycle = _load(root / "lifecycle_contract.json")
        writes = _load(root / "expected_mse4_writes.json")
        self.assertEqual(lifecycle["active_slices"], [0, 1])
        self.assertEqual(lifecycle["repeat_num"], 1)
        self.assertEqual(lifecycle["formal_d_words_per_slice"], 4)
        self.assertTrue(
            lifecycle["stock_tb_completion_observer"][
                "required_sampled_slices_enabled"
            ]
        )
        self.assertEqual(writes["total_expected_accepted_write_count"], 8)
        self.assertEqual(
            {item["slice_id"] for item in writes["writes"]}, {0, 1}
        )
        self.assertEqual(
            {
                item["byte_address"]
                for item in writes["writes"]
                if item["slice_id"] == 0
            },
            {"0x00000010", "0x00000020", "0x00000030", "0x00000040"},
        )

    def test_checked_assets_match_fresh_build(self) -> None:
        checked = _load(ROOT / CONFIG_ROOT_REL / "manifest.json")
        with tempfile.TemporaryDirectory(prefix="dequant-atomic-") as temp:
            fresh_root = Path(temp) / "bundle"
            fresh = materialize_bundle(ROOT, fresh_root)
            self.assertEqual(fresh, checked)
            for relative, identity in checked["files"].items():
                path = ROOT / CONFIG_ROOT_REL / relative
                self.assertEqual(path.stat().st_size, identity["size_bytes"])
                self.assertEqual(sha256_file(path), identity["sha256"])

    def test_release_boundary_remains_fail_closed(self) -> None:
        manifest = _load(ROOT / CONFIG_ROOT_REL / "manifest.json")
        report = _load(ROOT / REPORT_REL)
        contract = _load(ROOT / CONTRACT_REL)
        self.assertEqual(
            manifest["status"], "LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN"
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["server_package"])
        self.assertFalse(contract["counts_as_node0077_e4"])
        self.assertFalse(contract["counts_as_node0077_e5"])
        self.assertEqual(report["dynamic_execution_status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
