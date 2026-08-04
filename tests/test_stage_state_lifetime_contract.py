from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.stage_state_lifetime_contract import (
    CONTRACT_PATH,
    StageStateLifetimeContractError,
    build_stage_state_lifetime_contract,
    validate_stage_state_lifetime_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class StageStateLifetimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_stage_state_lifetime_contract(ROOT)

    def test_all_133_stages_are_ordered_without_implicit_state(self) -> None:
        plan = self.value["ordered_config_plan"]
        self.assertEqual(plan["stage_count"], 133)
        self.assertEqual(plan["blocked_compute_stage_count"], 132)
        self.assertEqual(plan["logical_alias_stage_count"], 1)
        self.assertEqual(plan["encoded_config_transition_count"], 0)
        self.assertFalse(plan["implicit_prior_state_allowed"])
        self.assertEqual(
            [item["ordinal"] for item in plan["stages"]],
            list(range(133)),
        )
        self.assertTrue(
            all(
                not item["implicit_prior_state_allowed"]
                for item in plan["stages"]
            )
        )

    def test_typed_edges_are_exact_but_physical_lifetimes_are_not_fabricated(
        self,
    ) -> None:
        dag = self.value["typed_tensor_dag"]
        self.assertGreater(dag["edge_count"], 0)
        self.assertEqual(dag["typed_identity_mismatch_count"], 0)
        self.assertEqual(dag["physical_allocation_bound_edge_count"], 0)
        self.assertEqual(dag["implicit_reuse_edge_count"], 0)
        self.assertTrue(
            all(edge["typed_identity_exact"] for edge in dag["edges"])
        )

    def test_view_logical_bytes_match_but_physical_alias_remains_blocked(
        self,
    ) -> None:
        view = self.value["view"]
        self.assertTrue(view["flattened_element_order_equal"])
        self.assertTrue(view["exact_byte_equal"])
        self.assertTrue(view["logical_zero_copy_proven"])
        self.assertFalse(view["physical_zero_copy_proven"])
        self.assertEqual(view["input_bytes_sha256"], view["output_bytes_sha256"])
        self.assertEqual(len(view["adjacent_edges"]), 2)

    def test_sa_numeric_freeze_and_n2n_nonselection_are_explicit(self) -> None:
        sa = self.value["sa_control_boundary"]
        n2n = self.value["n2n"]
        self.assertEqual(sa["stage_count"], 54)
        self.assertEqual(sa["conv_stage_count"], 53)
        self.assertEqual(sa["matmul_stage_count"], 1)
        self.assertEqual(sa["conv_shape_signature_count"], 20)
        self.assertEqual(
            sum(
                item["stage_count"]
                for item in sa["conv_shape_signatures"]
            ),
            53,
        )
        self.assertEqual(
            sa["matmul_logical_signature"]["mnk"],
            {"M": 16, "N": 1000, "K": 2048},
        )
        self.assertFalse(
            sa["matmul_logical_signature"][
                "physical_tile_and_tail_schedule_proven"
            ]
        )
        self.assertTrue(sa["all_carry_B_SA_INT8_CSA_NUMERIC"])
        self.assertFalse(sa["numeric_release_allowed"])
        self.assertEqual(n2n["typed_n2n_stage_count"], 0)
        self.assertEqual(n2n["selected_n2n_config_count"], 0)
        self.assertFalse(n2n["required_for_gap"])

    def test_minimal_two_stage_lifecycle_is_closed_without_projecting_release(
        self,
    ) -> None:
        lifecycle = self.value["minimal_two_stage_lifecycle"]
        self.assertEqual(
            lifecycle["status"],
            "local_e2_complete_dynamic_hardware_pending",
        )
        self.assertTrue(lifecycle["synthetic_probe_only"])
        self.assertEqual(lifecycle["stage_count"], 2)
        self.assertEqual(lifecycle["runtime_sequence"], ["op0", "op1"])
        self.assertEqual(lifecycle["repeat_num"], 2)
        self.assertEqual(lifecycle["start_comp_count"], 2)
        self.assertEqual(lifecycle["completion_barrier_count"], 2)
        self.assertTrue(lifecycle["dual_golden_bit_exact"])
        self.assertFalse(lifecycle["producer_backed_input_preloaded"])
        self.assertFalse(lifecycle["candidate_release"])
        self.assertFalse(lifecycle["formal_target_config"])
        self.assertFalse(lifecycle["full_network_projection_allowed"])

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
        validate_stage_state_lifetime_contract(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["n2n"]["selected_n2n_config_count"] = 1
        with self.assertRaises(StageStateLifetimeContractError):
            validate_stage_state_lifetime_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
