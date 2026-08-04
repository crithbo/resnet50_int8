from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.deepseek_primitive_rules import (
    DeepSeekPrimitiveRuleError,
    build_deepseek_primitive_rules,
    validate_deepseek_primitive_rules,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/deepseek_primitive_rules_v1.json"
)


class DeepSeekPrimitiveRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_deepseek_primitive_rules(ROOT)

    def test_ga_inventory_opcodes_and_terminals_are_exact(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["ga_elementwise_template_count"], 22)
        self.assertEqual(summary["native_control_handler_count"], 48)
        self.assertEqual(
            summary[
                "graph_referenced_stage_type_native_handler_count"
            ],
            40,
        )
        self.assertEqual(
            summary["strict_validator_incompatible_template_count"], 6
        )
        for stage_type, item in self.value["ga_elementwise"].items():
            self.assertEqual(
                item["ga_facts"]["alu_opcodes"],
                [item["operation"]],
                stage_type,
            )
            self.assertTrue(item["native_control_handler"])
            self.assertIn(
                item["ga_facts"]["active_lane_count"], (4, 8)
            )
            self.assertIn(
                0,
                item["validation"]["completion"][
                    "possible_last_indices"
                ],
            )

    def test_sa_inventory_preserves_local_and_ring_topology(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["sa_template_count"], 6)
        self.assertEqual(summary["ring_template_count"], 2)
        for item in self.value["sa_matmul"].values():
            if item["role"] == "ring_partition":
                self.assertIsNotNone(item["sa_facts"]["n2n"])
                self.assertTrue(
                    item["sa_facts"]["neighbor_enabled_inports"]
                )
            else:
                self.assertIsNone(item["sa_facts"]["n2n"])
                self.assertEqual(
                    item["sa_facts"]["neighbor_enabled_inports"], []
                )

    def test_local_to_ring_is_not_an_n2n_only_patch(self) -> None:
        for pair in self.value["local_ring_pairs"]:
            self.assertTrue(pair["equal_config_mask"])
            self.assertTrue(pair["ring_adds_n2n"])
            self.assertNotEqual(pair["local_shape"], pair["ring_shape"])
            self.assertTrue(
                all(
                    item["equal"]
                    for item in pair["stable_sa_fields"].values()
                )
            )

    def test_int8_and_psum_numeric_transfer_remain_blocked(self) -> None:
        policy = self.value["transfer_policy"]
        self.assertIn("ndp-sim model_execplan", policy["execution_owner"])
        self.assertIn(
            "not a second operator generator",
            policy["project_layer_role"],
        )
        self.assertIn(
            "bias or partial-sum numeric placement",
            policy["not_proven_for_resnet_int8"],
        )
        self.assertIn("no psum-labelled", policy["psum_language_limit"])
        self.assertTrue(
            policy["derived_template_requires_independent_validation"]
        )

    def test_upstream_exact_and_strict_target_compatibility_are_separate(
        self,
    ) -> None:
        vector_add = self.value["ga_elementwise"][
            "prefill_add_V_fp16MN_fp32N_fp16MN"
        ]["validation"]
        self.assertFalse(vector_add["strict_validator_compatible"])
        self.assertEqual(
            {item["code"] for item in vector_add["issues"]},
            {"SCHEMA.UNKNOWN_FIELD"},
        )
        for stage_type in (
            "prefill_gemm_local",
            "prefill_gemm_local_qkt",
            "prefill_gemm_ring_4slice",
        ):
            validation = self.value["sa_matmul"][stage_type]["validation"]
            self.assertFalse(validation["strict_validator_compatible"])
            self.assertEqual(
                validation["issues"][0]["path"],
                "$.stream_engine.stream2.mem_idx_mode[2]",
            )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_deepseek_primitive_rules(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["local_ring_pairs"][0]["ring_adds_n2n"] = False
        with self.assertRaises(DeepSeekPrimitiveRuleError):
            validate_deepseek_primitive_rules(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
