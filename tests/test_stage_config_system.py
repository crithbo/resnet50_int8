from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.stage_config_system import (
    StageConfigSystemError,
    build_stage_config_system,
    validate_stage_config_system,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT / "contracts/operator_config/stage_config_system_v1.json"
)


class StageConfigSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_stage_config_system(ROOT)

    def test_all_133_stages_and_ten_families_have_plans(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["stage_count"], 133)
        self.assertEqual(summary["family_count"], 10)
        self.assertEqual(len(self.value["stage_plans"]), 133)
        self.assertEqual(
            len({item["request_id"] for item in self.value["stage_plans"]}),
            133,
        )
        self.assertEqual(
            summary["family_stage_counts"]["ConvInt32Accumulate"], 53
        )
        self.assertEqual(
            summary["family_stage_counts"]["RequantizeUint8"], 54
        )
        self.assertEqual(summary["family_stage_counts"]["QLinearAddUint8"], 17)
        self.assertEqual(
            self.value["families"]["ConvInt32Accumulate"][
                "shape_variant_count"
            ],
            20,
        )
        self.assertEqual(
            self.value["families"]["QLinearAddUint8"][
                "shape_variant_count"
            ],
            5,
        )

    def test_readiness_and_formal_release_are_separate(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["candidate_json_ready_count"], 2)
        self.assertEqual(summary["zero_copy_binding_ready_count"], 1)
        self.assertEqual(summary["blocked_stage_count"], 130)
        self.assertEqual(summary["formal_release_stage_count"], 0)
        self.assertEqual(summary["json_emitter_ready_count"], 4)
        self.assertEqual(summary["rtl_semantics_compatible_count"], 3)
        self.assertEqual(summary["dynamic_release_ready_count"], 0)
        plans = {item["request_id"]: item for item in self.value["stage_plans"]}
        self.assertEqual(
            plans["r5:hwop-0002-00"]["readiness"],
            "blocked",
        )
        self.assertEqual(
            plans["r5:hwop-0073-00"]["readiness"],
            "zero_copy_binding_ready_non_formal",
        )
        self.assertEqual(
            plans["r5:hwop-0071-00"]["readiness"],
            "blocked",
        )
        self.assertEqual(
            plans["r5:hwop-0077-00"]["readiness"],
            "candidate_json_ready_non_formal",
        )
        self.assertEqual(
            plans["r5:hwop-0077-00"]["candidate_blockers"], []
        )
        self.assertEqual(
            plans["r5:hwop-0077-00"]["formal_release_blockers"],
            ["B_DEQUANT_SERVER_E4_E5"],
        )
        self.assertEqual(
            plans["r5:hwop-0001-01"]["readiness"],
            "candidate_json_ready_non_formal",
        )
        self.assertEqual(
            plans["r5:hwop-0001-01"]["candidate_blockers"], []
        )
        self.assertEqual(
            plans["r5:hwop-0001-01"]["formal_release_blockers"],
            ["B_REQUANT_SERVER_E4_E5"],
        )
        self.assertEqual(
            plans["r5:hwop-0071-00"]["candidate_blockers"],
            [
                "B_GAP_D_INDEX_CARRIER_SEMANTICS",
                "B_GAP_GA_ACCUM_STATE",
            ],
        )
        self.assertEqual(
            plans["r5:hwop-0002-00"]["candidate_blockers"],
            ["B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"],
        )
        self.assertFalse(plans["r5:hwop-0002-00"]["formal_release_allowed"])

    def test_template_authority_is_scoped_by_git_origin(self) -> None:
        families = self.value["families"]
        conv = families["ConvInt32Accumulate"]
        requant = families["RequantizeUint8"]
        self.assertFalse(conv["all_reference_templates_authorized"])
        self.assertFalse(
            conv["reference_templates"][0]["accepted_as_correct_reference"]
        )
        self.assertTrue(requant["all_reference_templates_authorized"])
        self.assertTrue(
            requant["reference_templates"][0]["accepted_as_correct_reference"]
        )
        dequant = families["DequantizeLinear"]
        self.assertFalse(dequant["all_reference_templates_authorized"])
        self.assertFalse(
            dequant["reference_templates"][0][
                "accepted_as_correct_reference"
            ]
        )
        self.assertTrue(
            dequant["reference_templates"][0][
                "derived_candidate_local_e2_bound"
            ]
        )
        self.assertEqual(
            dequant["reference_templates"][0]["materialization"]["kind"],
            "contract_derived_local_e2_candidate",
        )
        self.assertEqual(
            requant["emission"]["candidate_scope"],
            ["r5:hwop-0001-01"],
        )
        self.assertEqual(requant["emission"]["candidate_blockers"], [])
        self.assertEqual(
            requant["emission"]["formal_release_blockers"],
            ["B_REQUANT_SERVER_E4_E5"],
        )
        self.assertEqual(
            self.value["inputs"]["deepseek_primitive_rules"]["path"],
            "contracts/operator_config/deepseek_primitive_rules_v1.json",
        )
        self.assertTrue(
            self.value["policy"][
                "deepseek_primitive_transfer_is_structural_only"
            ]
        )
        self.assertTrue(
            self.value["policy"][
                "native_ndpsim_owns_supported_graph_to_execplan_flow"
            ]
        )
        self.assertTrue(
            self.value["policy"][
                "project_must_not_duplicate_native_operator_generator"
            ]
        )

    def test_every_operator_json_module_has_one_owner(self) -> None:
        self.assertEqual(
            set(self.value["field_ownership"]),
            {
                "CONFIG",
                "dram_loop_configs",
                "processing_element",
                "stream_engine",
                "scratchpad",
                "special_array",
                "general_array",
                "n2n",
            },
        )
        self.assertTrue(
            all(
                item["owner"] and item["rule"]
                for item in self.value["field_ownership"].values()
            )
        )

    def test_blocked_families_have_exact_next_actions(self) -> None:
        families = self.value["families"]
        for name, item in families.items():
            mode = item["emission"]["mode"]
            if mode == "blocked":
                self.assertTrue(item["emission"]["candidate_blockers"], name)
                self.assertTrue(item["next_action"], name)
                self.assertTrue(
                    item["rule_layers"]["json_emission"].startswith("blocked")
                )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_stage_config_system(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["summary"]["blocked_stage_count"] -= 1
        with self.assertRaises(StageConfigSystemError):
            validate_stage_config_system(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
