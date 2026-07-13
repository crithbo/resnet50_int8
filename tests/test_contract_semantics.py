from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.contracts import (
    SUPPORTED_CONTRACT_SCHEMA_VERSIONS,
    load_contracts,
    validate_architecture_contract,
    validate_backend_contract,
)
from resnet50_pipeline.errors import ContractError


ROOT = Path(__file__).resolve().parents[1]


class ContractSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.architecture = json.loads(
            (ROOT / "contracts/architecture.json").read_text(encoding="utf-8")
        )
        cls.backend = json.loads(
            (ROOT / "contracts/backend.json").read_text(encoding="utf-8")
        )

    def test_project_contract_set_accepts_versioned_architecture(self) -> None:
        contracts = load_contracts(ROOT / "contracts")
        self.assertEqual(contracts.documents["architecture"]["schema_version"], "0.2")
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["architecture"], {"0.2"})
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["backend"], {"0.1"})
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["quantization"], {"0.1"})
        architecture = contracts.documents["architecture"]
        self.assertEqual(len(architecture["candidate_layouts"]), 12)
        self.assertEqual(len(architecture["planned_layouts"]), 2)
        self.assertEqual(
            {
                record["operator_family"]
                for record in architecture["candidate_layouts"].values()
            },
            {"simple", "view", "conv", "maxpool", "global_average_pool", "matmul"},
        )
        self.assertEqual(
            {
                record["operator_family"]
                for record in architecture["planned_layouts"].values()
            },
            {"add"},
        )
        self.assertTrue(
            all(
                record["current_gate_eligible"]
                for record in architecture["candidate_layouts"].values()
            )
        )

    def test_layout_cannot_be_both_planned_and_candidate(self) -> None:
        value = deepcopy(self.architecture)
        layout_id = "w4_simple_group4x7_28_candidate_v1"
        value["planned_layouts"][layout_id] = deepcopy(
            value["candidate_layouts"][layout_id]
        )
        value["planned_layouts"][layout_id]["status"] = "planned"
        value["planned_layouts"][layout_id]["current_gate_eligible"] = False
        with self.assertRaisesRegex(ContractError, "must be disjoint"):
            validate_architecture_contract(value)

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

    def test_legacy_evidence_cannot_become_gate_eligible(self) -> None:
        value = deepcopy(self.architecture)
        value["legacy_evidence"]["w4_conv_shape_coverage_v1"][
            "current_gate_eligible"
        ] = True
        with self.assertRaisesRegex(ContractError, "must remain legacy16"):
            validate_architecture_contract(value)

    def test_ambiguous_profile_name_fails(self) -> None:
        value = deepcopy(self.architecture)
        value["target"]["profiles"]["candidates"] = ["mixed"]
        with self.assertRaisesRegex(ContractError, "exact profile28 IDs"):
            validate_architecture_contract(value)

    def test_backend_keeps_ndpfuncmodel_as_w2_reference_only(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["ndp_conv_functional"]["is_target_backend"] = True
        with self.assertRaisesRegex(ContractError, "W2-only functional reference"):
            validate_backend_contract(value, self.architecture)

    def test_backend_cannot_approve_target_hardware(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_hardware"]["approved"] = True
        with self.assertRaisesRegex(ContractError, "target hardware"):
            validate_backend_contract(value, self.architecture)

    def test_backend_candidate_evidence_hash_must_match_architecture(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["rtl28_candidate_evidence"]["snapshot_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "differs from locked evidence"):
            validate_backend_contract(value, self.architecture)


if __name__ == "__main__":
    unittest.main()
