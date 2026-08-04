from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.gap_sum_padding_contract import (
    GapSumPaddingContractError,
    validate_gap_sum_zero_padding_contract,
)
from resnet50_pipeline.operator_padding_contract import (
    validate_operator_padding_contract,
)
from resnet50_pipeline.strict_config_materialization import (
    validate_materialized_strict_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/gap_sum_zero_padding_contract_v1.json"
)
STRICT = (
    ROOT / "configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1"
)


class GapSumPaddingContractTests(unittest.TestCase):
    def test_exact_gap_sum_zero_identity_is_hash_bound(self) -> None:
        value = validate_gap_sum_zero_padding_contract(ROOT, CONTRACT)
        self.assertEqual(
            value["operator_semantics"]["request_id"], "r5:hwop-0071-00"
        )
        self.assertEqual(value["operator_semantics"]["input_zero_point"], 0)
        self.assertEqual(
            value["operator_semantics"]["spatial_element_count"], 49
        )
        self.assertEqual(value["operator_semantics"]["lane_count"], 8)
        self.assertFalse(value["authorization"]["formal_target_config"])
        self.assertFalse(value["authorization"]["server_execution_claim"])

    def test_generic_dispatcher_accepts_gap_and_existing_maxpool(self) -> None:
        gap = validate_operator_padding_contract(ROOT, CONTRACT)
        maxpool = validate_operator_padding_contract(
            ROOT, ROOT / "contracts/maxpool_uint8_zero_padding_contract.json"
        )
        self.assertEqual(
            gap["schema"], "gap-sum-uint8-zero-padding-contract-v1"
        )
        self.assertEqual(
            maxpool["schema"], "maxpool-uint8-zero-padding-contract-v1"
        )

    def test_strict_materialization_is_authorized_and_valid(self) -> None:
        manifest = validate_materialized_strict_config(STRICT)
        self.assertEqual(
            manifest["source"]["path"],
            "ndp-sim/jsons/avgpool_config_2048_7_7.json",
        )
        self.assertEqual(
            manifest["changes"][0],
            {
                "after": 0,
                "before": None,
                "kind": "explicit_zero_padding",
                "path": "$.stream_engine.stream0.padding_reg_value",
            },
        )
        self.assertFalse(manifest["source_rewrite_performed"])

    def test_tamper_fails_closed(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(value)
        tampered["operator_semantics"]["input_zero_point"] = 1
        temporary = CONTRACT.parent / "_tampered_gap_padding_test.json"
        try:
            temporary.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(GapSumPaddingContractError):
                validate_gap_sum_zero_padding_contract(ROOT, temporary)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
