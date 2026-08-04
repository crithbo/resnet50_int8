from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.address_bound_config import validate_address_bound_config
from resnet50_pipeline.address_bound_config import bind_config_addresses


ROOT = Path(__file__).resolve().parents[1]
CHECKED = (
    ROOT
    / "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_address_bound_v1"
)


class AddressBoundConfigTests(unittest.TestCase):
    def test_address_binding_uses_native_lowercase_hex_canonicalization(self) -> None:
        config = {
            "stream_engine": {
                "stream0": {"target": "A", "base_addr": 0},
                "stream1": {"target": "D", "base_addr": 0},
            }
        }
        graph = {
            "operators": [
                {
                    "inputs": {"A": {"base_addr": "0x0"}},
                    "output": {"base_addr": "0x000311D0"},
                }
            ]
        }
        bound, _ = bind_config_addresses(config, graph)
        self.assertEqual(bound["stream_engine"]["stream1"]["base_addr"], "0x311d0")

    def test_checked_node0004_config_has_only_four_planner_address_changes(self) -> None:
        manifest = validate_address_bound_config(CHECKED, project_root=ROOT)
        self.assertEqual(len(manifest["changes"]), 4)
        self.assertEqual(
            {item["target"]: item["after"] for item in manifest["changes"]},
            {"A": "0x0", "B": "0x400", "C": "0x31400", "D": "0x31440"},
        )
        self.assertFalse(manifest["source_rewrite_performed"])


if __name__ == "__main__":
    unittest.main()
