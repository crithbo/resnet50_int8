from __future__ import annotations

import copy
import unittest
from pathlib import Path

from resnet50_pipeline.node0071_node0075_uint8_identity_alias_integration import (
    ALLOCATION_OWNER,
    AliasIntegrationError,
    STORAGE_ID,
    build_contract,
    negative_control_results,
    validate_contract,
    validate_contract_value,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0071_node0075_uint8_identity_alias_integration_v1.json"
)


class Node0071Node0075IdentityAliasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_contract(CONTRACT, ROOT)

    def test_overlay_is_metadata_only_and_preserves_node0071_owner(self) -> None:
        overlay = self.report["alias_overlay_materialization"]
        self.assertEqual(overlay["storage_id"], STORAGE_ID)
        self.assertEqual(overlay["allocation_owner"], ALLOCATION_OWNER)
        self.assertFalse(overlay["allocation_owner_changed"])
        self.assertFalse(overlay["new_allocation_created"])
        self.assertFalse(overlay["relocation_used"])
        self.assertFalse(overlay["copy_used"])
        self.assertFalse(overlay["replay_used"])
        self.assertFalse(overlay["host_tensor_used"])
        self.assertFalse(overlay["old_fp32_131072_byte_endpoint_used"])

    def test_typed_edge_is_exact_but_native_execplan_install_is_blocked(self) -> None:
        overlay = self.report["alias_overlay_materialization"]
        closure = self.report["materializer_closure"]
        self.assertEqual(overlay["index_map"], "[n,c,0,0] -> [n,c]")
        self.assertEqual(overlay["storage_offset_bytes"], 0)
        self.assertFalse(overlay["installed_in_native_execplan"])
        self.assertFalse(
            closure["final_materialized_node0075_a_consumer_present"]
        )
        self.assertTrue(closure["missing_native_candidates"])

    def test_consumer_coverage_is_not_inferred_from_producer_bases(self) -> None:
        coverage = self.report["node0075_consumer_address_coverage"]
        self.assertEqual(coverage["required_total_read_bytes"], 32768)
        self.assertFalse(coverage["coverage_proven"])
        self.assertFalse(
            coverage["producer_base_projection_accepted_as_consumer_address"]
        )
        self.assertIsNone(coverage["final_consumer_address_equation"])
        self.assertEqual(len(coverage["required_slice_records"]), 16)
        self.assertTrue(
            all(
                row["consumer_occurrence_addresses"] is None
                for row in coverage["required_slice_records"]
            )
        )

    def test_lifetime_requirements_are_preserved_without_fake_witnesses(self) -> None:
        lifetime = self.report["visibility_and_lifetime"]
        self.assertTrue(lifetime["producer_visibility_witness_accepted"])
        self.assertFalse(lifetime["cross_operator_visibility_barrier_materialized"])
        self.assertIsNone(lifetime["consumer_first_read_accepted_witness"])
        self.assertIsNone(lifetime["allocation_release_witness"])
        self.assertEqual(lifetime["allocation_kept_owned_by"], ALLOCATION_OWNER)

    def test_only_precise_materializer_sub_blocker_is_added(self) -> None:
        first = self.report["first_divergence"]
        self.assertEqual(
            first["id"],
            "B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING",
        )
        self.assertTrue(first["not_yet_an_rtl_first_divergence"])
        self.assertEqual(
            self.report["blocker_delta"][
                "B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING"
            ],
            "REMAINS_OPEN",
        )

    def test_all_negative_controls_fail_closed(self) -> None:
        controls = self.report["negative_controls"]
        self.assertEqual(len(controls), 6)
        self.assertTrue(all(value["fail_closed"] for value in controls.values()))

    def test_mutated_producer_projection_claim_fails_closed(self) -> None:
        contract = build_contract(ROOT)
        candidate = copy.deepcopy(contract)
        candidate["node0075_consumer_address_coverage"][
            "producer_base_projection_accepted_as_consumer_address"
        ] = True
        with self.assertRaises(AliasIntegrationError):
            validate_contract_value(candidate, ROOT)

    def test_negative_controls_are_deterministic(self) -> None:
        contract = build_contract(ROOT)
        self.assertEqual(
            negative_control_results(contract, ROOT),
            negative_control_results(contract, ROOT),
        )

    def test_no_target_or_package_and_no_external_mutation(self) -> None:
        outputs = self.report["outputs"]
        self.assertTrue(outputs["metadata_alias_overlay_contract"])
        self.assertTrue(
            all(not value for key, value in outputs.items() if key != "metadata_alias_overlay_contract")
        )
        self.assertEqual(self.report["package_release"], "NONE")
        self.assertEqual(
            self.report["wait_state"], "WAIT_NODE0075_MATERIALIZER_CAPABILITY"
        )


if __name__ == "__main__":
    unittest.main()
