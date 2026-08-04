from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.build_requant_quant_tail_evidence_input import (
    OUTPUT_PATH,
    EvidenceInputError,
    build_evidence_input,
    validate_evidence_input,
)


ROOT = Path(__file__).resolve().parents[1]


class RequantQuantTailEvidenceInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_evidence_input(ROOT)

    def test_closed_54_stage_partition_is_preserved(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["requant_stage_count"], 54)
        self.assertEqual(summary["w3_exact_stage_count"], 54)
        self.assertEqual(
            summary["zero_point_zero_compatible_stage_count"], 33
        )
        self.assertEqual(
            summary["nonzero_zero_point_guard_contradicted_stage_count"],
            21,
        )
        self.assertEqual(summary["physical_e2_materialized_stage_count"], 1)
        self.assertEqual(summary["formal_dynamic_pass_count"], 0)

    def test_nonzero_zp_counterexamples_cover_recipe_hazards(self) -> None:
        counterexamples = self.value["counterexample_sets"]
        signed = counterexamples["nonzero_zp_signed_domain_one_per_stage"]
        self.assertEqual(len(signed), 21)
        self.assertTrue(all(item["y_zero_point"] != 0 for item in signed))
        tie = counterexamples["observed_tie_parity"]
        self.assertEqual(len(tie), 1)
        self.assertEqual(tie[0]["request_id"], "r5:hwop-0014-01")
        self.assertEqual(tie[0]["scaled_float32"], 4.5)
        self.assertEqual(tie[0]["y_zero_point"], 123)
        self.assertEqual(tie[0]["exact_uint8"], 127)
        self.assertEqual(tie[0]["magic_add_zp_inside_round_uint8"], 128)
        saturation = counterexamples["saturation_representatives"]
        self.assertEqual(len(saturation["nonzero_zp_lower_observed"]), 0)
        self.assertEqual(len(saturation["nonzero_zp_upper_observed"]), 1)
        self.assertEqual(len(saturation["all_stage_lower_observed"]), 1)
        self.assertNotEqual(
            saturation["nonzero_zp_upper_observed"][0]["y_zero_point"], 0
        )
        self.assertEqual(
            saturation["all_stage_lower_observed"][0]["y_zero_point"], 0
        )
        self.assertTrue(
            saturation["coverage"]["no_synthetic_sample_is_presented_as_w3"]
        )
        self.assertLess(
            saturation["all_stage_lower_observed"][0][
                "integer_before_uint8_clip"
            ],
            0,
        )
        self.assertGreater(
            saturation["nonzero_zp_upper_observed"][0][
                "integer_before_uint8_clip"
            ],
            255,
        )

    def test_numeric_and_physical_gaps_are_independent(self) -> None:
        stages = self.value["stage_evidence"]
        node0001 = next(
            item
            for item in stages
            if item["request_id"] == "r5:hwop-0001-01"
        )
        self.assertEqual(
            node0001["physical_materialization_classification"],
            "PHYSICAL_E2_COMPLETE_CONFIG_BOUND",
        )
        self.assertEqual(
            node0001["numeric_problem_kind"],
            "NONE_EXACT_W3_AND_ZP0_GUARD_COMPATIBLE",
        )
        pending_zp0 = [
            item
            for item in stages
            if item["qparams"]["y_zero_point"] == 0
            and item["request_id"] != "r5:hwop-0001-01"
        ]
        self.assertEqual(len(pending_zp0), 32)
        self.assertTrue(
            all(
                item["physical_materialization_classification"]
                == "PHYSICAL_E2_PENDING_NUMERIC_RECIPE_COMPATIBLE"
                for item in pending_zp0
            )
        )
        nonzero = [
            item for item in stages if item["qparams"]["y_zero_point"] != 0
        ]
        self.assertTrue(
            all(
                item["numeric_problem_kind"].startswith(
                    "NUMERIC_RECIPE_GAP_SIGNED_DOMAIN"
                )
                for item in nonzero
            )
        )

    def test_matmul_zp60_splits_numeric_and_rank2_layout_gaps(self) -> None:
        matmul = self.value["matmul_requant_case"]
        self.assertEqual(matmul["request_id"], "r5:hwop-0075-01")
        self.assertEqual(matmul["logical_shape"], [16, 1000])
        self.assertEqual(matmul["y_zero_point"], 60)
        self.assertEqual(matmul["current_guard_mismatch_count"], 8272)
        self.assertEqual(
            matmul["layout_problem_kind"],
            "RANK2_NOT_PROVEN_BY_NODE0001_HWC8",
        )

    def test_p0a_rounding_and_domain_gates_refine_both_partitions(
        self,
    ) -> None:
        dependency = self.value["p0a_capability_dependency"]
        self.assertEqual(
            dependency["decision"],
            "NO_UNCONDITIONAL_PURE_CONFIG_PROVEN",
        )
        first = dependency["first_hardware_unknown"]
        self.assertEqual(first["id"], "CE_FMA_VS_SEQUENTIAL_ROUND")
        self.assertEqual(first["inputs"]["int32"], 400)
        self.assertEqual(first["inputs"]["multiplier_bits"], "0x3d828f5c")
        self.assertEqual(first["expected_sequential_uint8"], 26)
        self.assertEqual(first["one_round_fused_model_uint8"], 25)
        zp0 = dependency["zp0_partition"]
        self.assertEqual(zp0["stage_count"], 33)
        self.assertEqual(
            zp0["still_blocked_by_fma_rounding_boundary_count"], 33
        )
        self.assertEqual(
            zp0["still_blocked_by_magic_domain_bound_count"], 33
        )
        self.assertEqual(zp0["negative_w3_seen_count"], 33)
        self.assertEqual(zp0["formal_release_count"], 0)
        nonzero = dependency["nonzero_partition"]
        self.assertEqual(
            nonzero["even_zp_signed_rounding_domain_blocked_count"], 16
        )
        self.assertEqual(
            nonzero["odd_zp_signed_rounding_domain_tie_blocked_count"],
            5,
        )
        rules = {
            item["path"]: item["sha256"]
            for item in self.value["active_rule_receipts"]
        }
        self.assertEqual(
            rules[".agents/rules/生成前必读索引.md"],
            "6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4",
        )
        self.assertEqual(
            rules[".agents/rules/精确UINT8量化尾专项规则.md"],
            "5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0",
        )
        self.assertEqual(
            rules[".agents/rules/RequantizeUint8算子配置规则.md"],
            "d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f",
        )
        integration = self.value["active_rule_integration"]
        self.assertTrue(integration["shared_quant_tail_rules_approved"])
        self.assertFalse(
            integration["family_semantic_classification_changed"]
        )

    def test_p0a_stage_mapping_keeps_division_counterexample_scoped(
        self,
    ) -> None:
        stages = self.value["stage_evidence"]
        self.assertTrue(
            all(
                item["p0a_dependency_mapping"][
                    "exact_fp32_division_counterexample_applicability"
                ]
                == "NOT_APPLICABLE_TO_REQUANT_MULTIPLIER_PATH"
                for item in stages
            )
        )
        zp0 = [
            item["p0a_dependency_mapping"]
            for item in stages
            if item["qparams"]["y_zero_point"] == 0
        ]
        self.assertTrue(
            all(
                item["classification"]
                == "ZP0_W3_COMPATIBLE_BUT_ROUNDING_DOMAIN_RELEASE_BLOCKED"
                for item in zp0
            )
        )
        odd = [
            item["p0a_dependency_mapping"]
            for item in stages
            if item["qparams"]["y_zero_point"] % 2 == 1
        ]
        self.assertEqual(len(odd), 5)
        self.assertTrue(
            all(
                "CE_ODD_ZP_TIE_PARITY"
                in item["applicable_counterexample_ids"]
                for item in odd
            )
        )

    def test_on_disk_contract_is_current_and_fail_closed(self) -> None:
        on_disk = json.loads(
            (ROOT / OUTPUT_PATH).read_text(encoding="utf-8")
        )
        validate_evidence_input(on_disk)
        current = copy.deepcopy(self.value)
        recorded = copy.deepcopy(on_disk)
        current.pop("control_read_receipts")
        recorded.pop("control_read_receipts")
        current.pop("control_receipt_policy")
        recorded.pop("control_receipt_policy")
        current.pop("evidence_sha256")
        recorded.pop("evidence_sha256")
        self.assertEqual(recorded, current)
        tampered = copy.deepcopy(on_disk)
        tampered["summary"]["w3_exact_stage_count"] = 53
        with self.assertRaises(EvidenceInputError):
            validate_evidence_input(tampered)

    def test_no_target_or_dynamic_boundary_is_overclaimed(self) -> None:
        boundary = self.value["boundaries"]
        self.assertTrue(boundary["machine_readable_evidence_only"])
        self.assertTrue(boundary["new_operator_json_generated"] is False)
        self.assertTrue(boundary["new_server_package_generated"] is False)
        self.assertTrue(
            boundary["server_inspected_uploaded_or_run"] is False
        )
        self.assertTrue(boundary["dynamic_narrow_probe_continued"] is False)
        self.assertTrue(boundary["event_edge_packages_modified"] is False)
        self.assertTrue(boundary["rtl_modified"] is False)
        self.assertTrue(boundary["counts_as_e4"] is False)
        self.assertTrue(boundary["counts_as_e5"] is False)


if __name__ == "__main__":
    unittest.main()
