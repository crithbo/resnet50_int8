from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.deepseek_stage_ir import (
    DeepSeekStageIRError,
    build_deepseek_stage_ir,
    validate_deepseek_stage_ir,
)
from resnet50_pipeline.ndpsim_native import (
    load_native_execution_plan,
    native_control_handlers,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json"
)


class DeepSeekStageIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_deepseek_stage_ir(ROOT)

    def test_inventory_and_graph_coverage_are_exact(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["deepseek_template_count"], 47)
        self.assertEqual(summary["graph_referenced_template_count"], 40)
        self.assertEqual(summary["template_without_graph_count"], 7)
        self.assertGreater(summary["unique_graph_count"], 20)
        self.assertGreater(summary["stage_occurrence_count"], 80)
        self.assertEqual(summary["unique_stage_type_count"], 40)

    def test_every_stage_type_binds_one_authorized_template(self) -> None:
        crosswalk = self.value["template_crosswalk"]
        for stage in self.value["stage_records"]:
            template = crosswalk[stage["stage_type"]]
            self.assertTrue(
                template["configuration_authority"][
                    "accepted_as_correct_reference"
                ]
            )
            self.assertEqual(
                stage["template_sha256"],
                template["template"]["sha256"],
            )
            self.assertIn(stage["stage_id"], template["stage_ids"])

    def test_softmax_and_rmsnorm_preserve_stage_dags(self) -> None:
        softmax = [
            item
            for item in self.value["stage_records"]
            if item["graph_path"]
            == "ndp-sim/model_execplan/op_json/softmax.json"
        ]
        rmsnorm = [
            item
            for item in self.value["stage_records"]
            if item["graph_path"]
            == "ndp-sim/model_execplan/op_json/rmsnorm.json"
        ]
        self.assertEqual(len(softmax), 5)
        self.assertEqual(len(rmsnorm), 4)
        self.assertTrue(
            any(
                input_record["source_kind"] == "local_stage"
                for item in softmax
                for input_record in item["inputs"]
            )
        )
        self.assertTrue(
            any("remote_sum" in item["stage_type"] for item in rmsnorm)
        )

    def test_gemm_ring_binds_graphs_base_info_and_instances(self) -> None:
        item = self.value["template_crosswalk"][
            "prefill_gemm_ring_4slice"
        ]
        self.assertEqual(item["graph_reference_count"], 7)
        self.assertIsNotNone(item["operator_base_info"])
        self.assertEqual(len(item["server_package_instances"]), 3)
        self.assertEqual(
            item["reverse_reproduction"]["address_bound_instance_count"],
            1,
        )

    def test_native_model_execplan_owns_parsing_and_control_updates(
        self,
    ) -> None:
        handlers = native_control_handlers(ROOT)
        stage_types = {
            item["stage_type"] for item in self.value["stage_records"]
        }
        self.assertEqual(len(handlers), 48)
        self.assertTrue(stage_types <= set(handlers))
        normalized = load_native_execution_plan(
            ROOT, "ndp-sim/model_execplan/op_json/rmsnorm.json"
        )
        self.assertEqual(
            [item["type"] for item in normalized["operators"]],
            [
                "prefill_summac_fp32MN_fp32MN",
                "prefill_remote_sum_fp32MN_fp32MN",
                "prefill_mac_SFU_fp32MN_fp32MN",
                "prefill_mul_fp32MN_fp32M_fp32MN",
            ],
        )

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_deepseek_stage_ir(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["stage_records"][0]["stage_type"] = "wrong"
        with self.assertRaises(DeepSeekStageIRError):
            validate_deepseek_stage_ir(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
