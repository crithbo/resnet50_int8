from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.node0004_semantic_contract import (
    validate_node0004_semantic_contract,
)


ROOT = Path(__file__).resolve().parents[1]
GRAPH = (
    ROOT
    / "ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph"
    / "node0004_accumulate_wave0_nopp_r1_graph_withbaseaddr.json"
)
MAPPING = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-mapping-evidence"
    / "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1"
)
CONTRACT = ROOT / "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"


class Node0004SemanticContractTests(unittest.TestCase):
    def test_checked_contract_rebuilds_exactly(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_node0004_semantic_contract(
            value,
            ROOT,
            graph_withbaseaddr=GRAPH,
            mapping_bundle=MAPPING,
        )
        self.assertFalse(value["candidate_scope"]["formal_target_config"])
        self.assertFalse(value["candidate_scope"]["server_execution_claim"])
        binding = value["operators"]["op0"]["qparams"]["bindings"]["A"]
        self.assertEqual(binding["scale"]["value_kind"], "per_channel")
        self.assertEqual(binding["scale"]["shape"], [64])
        self.assertEqual(binding["zero_point"]["shape"], [64])


if __name__ == "__main__":
    unittest.main()
