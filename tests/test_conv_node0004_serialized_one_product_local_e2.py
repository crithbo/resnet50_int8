from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_serialized_one_product_local_e2 import (
    CONTRACT_REL,
    TEST_ID,
    build_config,
    build_contract,
    serialized_holdouts,
)


ROOT = Path(__file__).resolve().parents[1]


class ConvNode0004SerializedOneProductLocalE2Tests(unittest.TestCase):
    def test_serialized_config_derivation(self) -> None:
        config = build_config(ROOT, 0)
        self.assertEqual(config["dram_loop_configs"]["LC4"]["end"], 16)
        self.assertEqual(config["dram_loop_configs"]["LC6"]["end"], 16)
        self.assertEqual(
            config["stream_engine"]["stream1"]["dim_stride"],
            [32, 2048, 14336],
        )
        self.assertEqual(config["special_array"]["data_type"], "int8")
        self.assertEqual(config["special_array"]["bias_enable"], 1)

    def test_holdouts_include_tail_xzp_bias_and_wrap(self) -> None:
        evidence = serialized_holdouts()
        self.assertTrue(evidence["all_pass"])
        ids = {item["case_id"] for item in evidence["cases"]}
        self.assertEqual(
            ids,
            {"positive", "negative", "k_tail_odd", "nonzero_xzp", "bias_wrap"},
        )
        self.assertTrue(
            all(
                occurrence["nonzero_product_lane_count"] <= 1
                for case in evidence["cases"]
                for occurrence in case["occurrences"]
            )
        )

    def test_published_contract_is_current_and_closed(self) -> None:
        published = json.loads((ROOT / CONTRACT_REL).read_text(encoding="utf-8"))
        rebuilt = build_contract(ROOT)
        self.assertEqual(published, rebuilt)
        self.assertEqual(published["test_id"], TEST_ID)
        self.assertEqual(
            published["status"], "CONFIG_ONLY_CORRECTNESS_BASELINE"
        )
        self.assertTrue(
            published["field_ownership"]["materialized_leaf_diff"][
                "all_semantic_nonbase_fields_unchanged"
            ]
        )
        simulator = published["config_bound_simulator"]
        self.assertEqual(simulator["inactive_lane_nonzero_value_count"], 0)
        self.assertEqual(simulator["physical_mismatch_count"], 0)
        self.assertEqual(simulator["logical_w3_mismatch_count"], 0)
        self.assertNotEqual(
            simulator["stock_four_lane_negative_control"][
                "stock_four_lane_s32"
            ],
            simulator["stock_four_lane_negative_control"]["w3_target_s32"],
        )
        self.assertFalse(published["stage_gates"]["dynamic_release_ready"])
        self.assertEqual(published["package_release"], "NONE")


if __name__ == "__main__":
    unittest.main()
