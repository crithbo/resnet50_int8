from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.contracts import (
    SUPPORTED_CONTRACT_SCHEMA_VERSIONS,
    load_contracts,
    validate_architecture_contract,
)
from resnet50_pipeline.errors import ContractError


ROOT = Path(__file__).resolve().parents[1]


class ContractSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.architecture = json.loads(
            (ROOT / "contracts/architecture.json").read_text(encoding="utf-8")
        )

    def test_project_contract_set_accepts_versioned_architecture(self) -> None:
        contracts = load_contracts(ROOT / "contracts")
        self.assertEqual(contracts.documents["architecture"]["schema_version"], "0.2")
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["architecture"], {"0.2"})
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["backend"], {"0.1"})
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["quantization"], {"0.1"})

    def test_old16_active_target_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["target"]["slice_count"] = 16
        with self.assertRaisesRegex(ContractError, "current RTL28 candidate"):
            validate_architecture_contract(value)

    def test_arithmetic_or_corrupt_topology_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["target"]["topology"]["high_ring_owners"][0] = [0, 1, 2, 3]
        with self.assertRaisesRegex(ContractError, "HIGH topology"):
            validate_architecture_contract(value)

    def test_corrupt_rtl_entrypoint_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["target"]["rtl"]["top_module"] = "NDP_Top_old"
        with self.assertRaisesRegex(ContractError, "selected candidate"):
            validate_architecture_contract(value)

    def test_corrupt_candidate_address_order_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["candidate_memory"]["address_order"] = "arithmetic_guess"
        with self.assertRaisesRegex(ContractError, "address_order"):
            validate_architecture_contract(value)

    def test_legacy_layout_cannot_enter_current_registry(self) -> None:
        value = deepcopy(self.architecture)
        value["candidate_layouts"]["w4_conv_batch16_candidate_v1"] = {
            "target_family": "legacy16",
            "slice_count": 16,
            "operator_family": "conv",
            "status": "candidate",
            "current_gate_eligible": True,
        }
        with self.assertRaisesRegex(ContractError, "must target rtl28"):
            validate_architecture_contract(value)

    def test_ambiguous_profile_name_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["target"]["profiles"]["candidates"] = ["mixed"]
        with self.assertRaisesRegex(ContractError, "exact profile28 IDs"):
            validate_architecture_contract(value)


if __name__ == "__main__":
    unittest.main()
