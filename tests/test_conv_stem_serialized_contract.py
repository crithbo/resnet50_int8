from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_stem_serialized_contract import (
    build_stem_contract,
    validate_stem_contract,
)
from resnet50_pipeline.conv_stem_serialized_local_e2 import CONTRACT_REL


ROOT = Path(__file__).resolve().parents[1]


class ConvStemSerializedContractTest(unittest.TestCase):
    def test_published_contract_is_current_and_fail_closed(self) -> None:
        published = json.loads((ROOT / CONTRACT_REL).read_text(encoding="utf-8"))
        validation = validate_stem_contract(ROOT, published)
        self.assertTrue(validation["valid"])
        self.assertEqual(published, build_stem_contract(ROOT))
        self.assertEqual(
            published["classification"], "CONFIG_ONLY_CORRECTNESS_BASELINE"
        )
        self.assertEqual(
            published["numeric_and_physical_e2"][
                "config_bound_w3_mismatch_count"
            ],
            0,
        )
        self.assertFalse(
            published["claim_controls"]["server_package_generated"]
        )

    def test_contract_claim_drift_is_rejected(self) -> None:
        contract = build_stem_contract(ROOT)
        drifted = copy.deepcopy(contract)
        drifted["claim_controls"]["package_release"] = "PACKAGE_READY_NOT_RUN"
        validation = validate_stem_contract(ROOT, drifted)
        self.assertFalse(validation["valid"])

    def test_mutable_plan_receipt_is_historical_not_semantic_gate(self) -> None:
        contract = build_stem_contract(ROOT)
        historical = copy.deepcopy(contract)
        historical["mutable_plan_provenance"]["sha256_at_build"] = "0" * 64
        validation = validate_stem_contract(ROOT, historical)
        self.assertTrue(validation["valid"])


if __name__ == "__main__":
    unittest.main()
