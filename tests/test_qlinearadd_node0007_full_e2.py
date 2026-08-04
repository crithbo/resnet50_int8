from __future__ import annotations

import unittest
import json
from pathlib import Path

from resnet50_pipeline.qlinearadd_node0007_full_e2 import (
    build_configs,
    config_bound_simulator,
    graph_spec,
    scalar_tail_proof,
)
from resnet50_pipeline.qlinearadd_node0007_closure import validate_closure


ROOT = Path(__file__).resolve().parents[1]


class QLinearAddNode0007FullE2Test(unittest.TestCase):
    def test_five_configs_and_graph_are_closed(self) -> None:
        configs = build_configs(ROOT)
        self.assertEqual(
            set(configs),
            {
                "op_a_dequant",
                "op_b_dequant",
                "op_relocation_pad",
                "op_fp32_add",
                "op_tail_mul",
                "op_tail_round",
            },
        )
        graph = graph_spec()
        self.assertEqual(len(graph["operators"]), 6)
        self.assertEqual(graph["operators"][-1]["output"]["dtype"], "uint8")

    def test_node0007_tail_and_config_bound_golden(self) -> None:
        proof = scalar_tail_proof(ROOT)
        self.assertEqual(
            proof["division_rne_vs_reciprocal_rne_uint8_mismatch_count"], 0
        )
        self.assertEqual(
            proof["reciprocal_rne_vs_magic_uint8_mismatch_count"], 0
        )
        report = config_bound_simulator(ROOT)
        self.assertEqual(report["physical_mismatch_count"], 0)
        self.assertEqual(report["logical_mismatch_count"], 0)
        self.assertFalse(report["host_precomputed_internal_tensor"])

    def test_frozen_first_breakpoint_is_fail_closed(self) -> None:
        path = (
            ROOT
            / "contracts/operator_config/"
            "qlinearadd_node0007_full_e2_blocker_v1.json"
        )
        blocker = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(blocker["status"], "E2_FAILED_FIRST_BREAKPOINT")
        self.assertFalse(blocker["candidate_release"])
        self.assertIsNone(blocker["claim"])
        first = blocker["first_breakpoint"]
        self.assertEqual(first["code"], "REQUEST.ROW_LIMIT")
        self.assertEqual(first["operator_id"], "op_fp32_add")
        self.assertEqual(first["observed_row"], 6144)
        self.assertEqual(
            blocker["package_release"]["status"], "NOT_GENERATED_E2_FAILED"
        )

    def test_relocated_native_chain_closes_the_row_limit(self) -> None:
        report = validate_closure(ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["status"], "E2_LOCAL_COMPLETE")
        self.assertFalse(report["candidate_release"])
        self.assertEqual(
            report["static_to_final_leaf_diff"]["non_base_count"], 0
        )
        self.assertEqual(
            max(
                item["max_row"]
                for item in report["stream_address_coverage"].values()
            ),
            6143,
        )
        self.assertFalse(
            report["relocation_mechanism"]["host_precomputed_internal_tensor"]
        )


if __name__ == "__main__":
    unittest.main()
