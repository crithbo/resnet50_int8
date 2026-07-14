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
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["backend"], {"0.2"})
        self.assertEqual(SUPPORTED_CONTRACT_SCHEMA_VERSIONS["quantization"], {"0.1"})
        architecture = contracts.documents["architecture"]
        self.assertEqual(len(architecture["candidate_layouts"]), 14)
        self.assertEqual(len(architecture["planned_layouts"]), 0)
        self.assertEqual(
            {
                record["operator_family"]
                for record in architecture["candidate_layouts"].values()
            },
            {
                "simple",
                "view",
                "conv",
                "maxpool",
                "add",
                "global_average_pool",
                "matmul",
            },
        )
        self.assertEqual(
            {
                record["operator_family"]
                for record in architecture["planned_layouts"].values()
            },
            set(),
        )
        self.assertEqual(
            sum(
                record["current_gate_eligible"]
                for record in architecture["candidate_layouts"].values()
            ),
            7,
        )
        self.assertEqual(
            sum(record["status"] == "approved" for record in architecture["candidate_layouts"].values()),
            7,
        )
        self.assertEqual(len(architecture["candidate_evidence"]), 3)
        self.assertTrue(
            architecture["candidate_evidence"][
                "w4_rtl28_network_physical_edges_v1"
            ]["current_gate_eligible"]
        )
        self.assertTrue(
            architecture["candidate_evidence"][
                "w4_rtl28_network_profile_cost_v1"
            ]["current_gate_eligible"]
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
        with self.assertRaisesRegex(ContractError, "approved RTL28 W4 baseline"):
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
        value["target"]["profiles"]["approved"] = ["mixed"]
        with self.assertRaisesRegex(ContractError, "DeepSeek hybrid28"):
            validate_architecture_contract(value)

    def test_backend_keeps_ndpfuncmodel_config_adapter_boundary(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["ndp_conv_functional"]["config_adapter_available"] = False
        with self.assertRaisesRegex(ContractError, "identity/config-adapter boundary"):
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

    def test_target_config_source_is_version_and_scope_bound(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"]["source_commit"] = "0" * 40
        with self.assertRaisesRegex(ContractError, "approved configuration source"):
            validate_backend_contract(value, self.architecture)

    def test_target_config_source_does_not_become_numerical_simulator(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"]["can_execute_numerical_model"] = True
        with self.assertRaisesRegex(ContractError, "approved configuration source"):
            validate_backend_contract(value, self.architecture)

    def test_target_config_authority_audit_hash_is_bound(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"]["audit_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "audit hash mismatch"):
            validate_backend_contract(value, self.architecture, ROOT / "contracts")

    def test_typed_config_parameter_contract_hash_is_bound(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"][
            "typed_parameter_contract_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ContractError, "parameter contract hash mismatch"):
            validate_backend_contract(value, self.architecture, ROOT / "contracts")

    def test_typed_config_parameter_contract_remains_formula_only(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"][
            "typed_config_parameter_contract_validated"
        ] = False
        with self.assertRaisesRegex(ContractError, "approved configuration source"):
            validate_backend_contract(value, self.architecture)

    def test_target_config_source_requires_pool_family_probe(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"][
            "pool_family_encoder_probe_validated"
        ] = False
        with self.assertRaisesRegex(ContractError, "approved configuration source"):
            validate_backend_contract(value, self.architecture)

    def test_target_config_source_requires_ga_quant_add_dequant_probe(self) -> None:
        value = deepcopy(self.backend)
        value["backends"]["target_config_toolchain"][
            "ga_quant_add_dequant_probe_validated"
        ] = False
        with self.assertRaisesRegex(ContractError, "approved configuration source"):
            validate_backend_contract(value, self.architecture)

    def test_target_config_source_requires_c6_candidate_probes(self) -> None:
        for field in (
            "matmul_gemv_config_probe_validated",
            "sum_family_config_probe_validated",
        ):
            with self.subTest(field=field):
                value = deepcopy(self.backend)
                value["backends"]["target_config_toolchain"][field] = False
                with self.assertRaisesRegex(
                    ContractError,
                    "approved configuration source",
                ):
                    validate_backend_contract(value, self.architecture)

    def test_current_network_evidence_metrics_fail_closed(self) -> None:
        value = deepcopy(self.architecture)
        value["candidate_evidence"]["w4_rtl28_network_physical_edges_v1"][
            "edge_count"
        ] = 92
        with self.assertRaisesRegex(ContractError, "edge_count must be 93"):
            validate_architecture_contract(value)

    def test_current_network_evidence_path_and_hash_are_bound(self) -> None:
        value = deepcopy(self.architecture)
        value["candidate_evidence"]["w4_rtl28_network_profile_cost_v1"][
            "sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(ContractError, "path must be"):
            validate_architecture_contract(value, ROOT / "contracts")


if __name__ == "__main__":
    unittest.main()
