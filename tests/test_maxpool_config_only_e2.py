from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.maxpool_config_only_e2 import (
    CLAIM,
    MaxPoolConfigOnlyE2Error,
    _load_json,
    _output_coverage,
    _validate_graph,
    materialized_leaf_diff,
    validate_maxpool_config_only_e2,
)


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = (
    ROOT
    / "artifacts/operator_config_validation/maxpool-node0002-config-only-e2-v1"
)


class MaxPoolConfigOnlyE2Tests(unittest.TestCase):
    def test_final_bundle_closes_local_e2_only(self) -> None:
        report = validate_maxpool_config_only_e2(ROOT, ARTIFACT)
        self.assertTrue(report["valid"])
        self.assertEqual(report["claim"], CLAIM)
        self.assertEqual(report["evidence_level"], "E2")
        self.assertFalse(report["formal_target_instance_allowed"])
        simulator = report["config_bound_simulator"]
        self.assertEqual(simulator["wave_counts"], [28, 28, 8])
        self.assertEqual(simulator["physical_occurrence_count"], 64)
        self.assertEqual(simulator["logical_element_count"], 3211264)
        self.assertEqual(simulator["logical_mismatch_count"], 0)
        self.assertEqual(simulator["physical_mismatch_count"], 0)
        self.assertEqual(simulator["formal_D_total_written_bytes"], 3211264)
        self.assertFalse(simulator["target_simulator_validated"])

    def test_materialized_non_base_fields_do_not_drift(self) -> None:
        source = _load_json(ARTIFACT / "source_config.json")
        for op_id in ("op0", "op1", "op2"):
            final = _load_json(
                ARTIFACT
                / "pipeline_output/jsons"
                / f"{op_id}_maxpool_config_16_112_112_stride2_padding1.json"
            )
            self.assertTrue(
                all(
                    item["path"].endswith(".base_addr")
                    for item in materialized_leaf_diff(source, final)
                )
            )

    def test_output_stride_partial_coverage_negative_control(self) -> None:
        config = _load_json(
            ARTIFACT
            / "pipeline_output/jsons"
            / "op0_maxpool_config_16_112_112_stride2_padding1.json"
        )
        mutated = copy.deepcopy(config)
        mutated["stream_engine"]["stream1"]["dim_stride"][1] = 1024
        with self.assertRaisesRegex(
            MaxPoolConfigOnlyE2Error, "occurrence/stride equation differs"
        ):
            _output_coverage(
                mutated,
                int(config["stream_engine"]["stream1"]["base_addr"], 0),
            )

    def test_wave2_full_mask_negative_control(self) -> None:
        graph = json.loads(
            (ROOT / "configs/maxpool/node0002_config_only_e2_v1/graph.json").read_text(
                encoding="utf-8"
            )
        )
        graph["operators"][2]["used_slices"] = (
            "0b1111111111111111111111111111"
        )
        with self.assertRaisesRegex(MaxPoolConfigOnlyE2Error, "slice mask differs"):
            _validate_graph(graph)

    def test_replay_uses_only_formal_producer_output(self) -> None:
        contract = _load_json(
            ROOT / "contracts/operator_config/maxpool_node0002_config_only_e2_v1.json"
        )
        replay = contract["input_replay_boundary"]
        self.assertEqual(replay["tensor_identity"], "tensor-f6c1a8fb6fd529e8")
        self.assertIn("does not precompute", replay["uncomputed_boundary"])
        self.assertIn("independent golden", replay["uncomputed_boundary"])


if __name__ == "__main__":
    unittest.main()
