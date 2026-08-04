from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4 import (
    ADD_INNER,
    ADD_OUTER,
    DEQUANT_INNER,
    DEQUANT_OUTER,
    build_configs,
    geometry_equivalence_proof,
    validate_signed_feedback_bounds,
)
from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4_closure import (
    validate_closure,
)


ROOT = Path(__file__).resolve().parents[1]


class QLinearAddNode0007NestedLCV4Test(unittest.TestCase):
    def test_nested_domains_preserve_ordered_logical_occurrences(self) -> None:
        proof = geometry_equivalence_proof()
        self.assertTrue(proof["valid"])
        self.assertFalse(proof["numeric_analysis_repeated"])
        self.assertTrue(
            all(
                item["ordered_equal"]
                for item in proof["records"].values()
            )
        )

    def test_all_positive_dram_loop_ends_fit_signed_feedback(self) -> None:
        configs = build_configs(ROOT)
        report = validate_signed_feedback_bounds(configs)
        self.assertTrue(report["valid"])
        self.assertLessEqual(report["maximum_positive_stride_end"], 32768)
        self.assertEqual(
            configs["op_a_dequant"]["dram_loop_configs"]["LC0"]["end"],
            DEQUANT_OUTER,
        )
        self.assertEqual(
            configs["op_a_dequant"]["dram_loop_configs"]["LC1"]["end"],
            DEQUANT_INNER,
        )
        self.assertEqual(
            configs["op_fp32_add"]["dram_loop_configs"]["LC0"]["end"],
            ADD_OUTER,
        )
        self.assertEqual(
            configs["op_fp32_add"]["dram_loop_configs"]["LC1"]["end"],
            ADD_INNER,
        )

    def test_outer_strides_are_exact_tile_bytes(self) -> None:
        configs = build_configs(ROOT)
        a = configs["op_a_dequant"]["stream_engine"]
        self.assertEqual(a["stream0"]["dim_stride"], [16, 16, 150528])
        self.assertEqual(a["stream2"]["dim_stride"], [64, 64, 602112])
        add = configs["op_fp32_add"]["stream_engine"]
        for stream in add.values():
            self.assertEqual(stream["dim_stride"], [16, 301056, None])

    def test_fresh_native_closure_when_materialized(self) -> None:
        evidence = (
            ROOT
            / "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-nested-lc-full-e2-v4/execplan/"
            "bundle_manifest.json"
        )
        if not evidence.is_file():
            self.skipTest("fresh nested-LC native chain is not materialized")
        report = validate_closure(ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["status"], "E2_LOCAL_COMPLETE")
        self.assertFalse(report["candidate_release"])
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertEqual(
            report["static_to_final_leaf_diff"]["non_base_count"], 0
        )
        self.assertTrue(
            report[
                "per_slice_stream_signatures_match_frozen_logical_domain"
            ]
        )


if __name__ == "__main__":
    unittest.main()
