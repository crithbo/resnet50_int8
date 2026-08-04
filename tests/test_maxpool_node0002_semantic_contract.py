from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.maxpool_node0002_semantic_contract import (
    validate_maxpool_node0002_semantic_contract,
)
from resnet50_pipeline.operator_config_package_validator import (
    OperatorConfigPackageValidator,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "maxpool-node0002-guarded-wave0-v3"
)
MAPPING = (
    ROOT
    / "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
    "maxpool-node0002-guarded-address-bound-v2"
)
CONTRACT = ROOT / "contracts/maxpool_node0002_guarded_wave0_semantic_contract.json"


class MaxPoolNode0002SemanticContractTests(unittest.TestCase):
    def test_contract_is_current_and_package_validator_accepts_it(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        graph = EVIDENCE / "pipeline_output/graph_withbaseaddr.json"
        validate_maxpool_node0002_semantic_contract(
            value, ROOT, graph_withbaseaddr=graph, mapping_bundle=MAPPING
        )
        report = OperatorConfigPackageValidator().validate(
            EVIDENCE / "pipeline_output",
            graph_path=graph,
            semantic_contract=value,
            require_matrix_files=False,
            provenance_root=EVIDENCE,
        )
        self.assertTrue(report.valid, report.to_dict().get("first_error"))

    def test_tampered_qparam_fails_closed(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        value = copy.deepcopy(value)
        value["operators"]["op0"]["qparams"]["bindings"]["D"]["zero_point"][
            "scalar"
        ] = 1
        with self.assertRaises(ValueError):
            validate_maxpool_node0002_semantic_contract(
                value,
                ROOT,
                graph_withbaseaddr=EVIDENCE
                / "pipeline_output/graph_withbaseaddr.json",
                mapping_bundle=MAPPING,
            )


if __name__ == "__main__":
    unittest.main()
