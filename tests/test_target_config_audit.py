from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.target_config_audit import (
    ADD_DEQUANT_TEMPLATE,
    AVGPOOL_TEMPLATE,
    MAXPOOL_TEMPLATE,
    QUANT_TEMPLATE,
    SECOND_MAXPOOL_TEMPLATE,
    TargetConfigAuditError,
    add_dequant_constant_patch,
    audit_execplan_qparam_binding,
    audit_ga_quant_add,
    audit_register_map,
    audit_maxpool_encoder,
    audit_pool_family,
    audit_resnet_scalar_qparams,
    extract_ga_quant_add_crosswalk,
    extract_pool_family_linkage,
    inventory_templates,
    quant_requant_constant_patch,
    validate_add_dequant_template,
    validate_avgpool_shape_linkage,
    validate_avgpool_template,
    validate_maxpool_shape_linkage,
    validate_maxpool_template,
    validate_quant_template,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ndp-sim-ref"


class TargetConfigAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = json.loads((SOURCE / "jsons" / MAXPOOL_TEMPLATE).read_text(encoding="utf-8"))
        cls.second_maxpool = json.loads(
            (SOURCE / "jsons" / SECOND_MAXPOOL_TEMPLATE).read_text(encoding="utf-8")
        )
        cls.avgpool = json.loads(
            (SOURCE / "jsons" / AVGPOOL_TEMPLATE).read_text(encoding="utf-8")
        )
        cls.quant = json.loads(
            (SOURCE / "jsons" / QUANT_TEMPLATE).read_text(encoding="utf-8")
        )
        cls.add_dequant = json.loads(
            (SOURCE / "jsons" / ADD_DEQUANT_TEMPLATE).read_text(encoding="utf-8")
        )
        cls.model_graph = json.loads(
            (ROOT / "artifacts" / "w3" / "model_graph.json").read_text(encoding="utf-8")
        )

    def test_official_inventory_is_complete_and_exposes_conv_gap(self) -> None:
        inventory = inventory_templates(SOURCE)
        self.assertEqual(inventory["json_count"], 42)
        self.assertEqual(inventory["resnet_or_shared_count"], 7)
        self.assertEqual(inventory["deepseek_transformer_count"], 35)
        self.assertEqual(inventory["named_conv_template_count"], 0)

    def test_maxpool_preflight_binds_resources_and_field_routes(self) -> None:
        result = validate_maxpool_template(self.template)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["resources"]["dram_loops"], 8)
        self.assertEqual(result["resources"]["read_streams"], 1)
        self.assertEqual(result["resources"]["write_streams"], 1)
        self.assertEqual(result["resources"]["ga_pes"], 8)
        self.assertEqual(result["field_routes"]["general_array.PE_array"]["encoder_class"], "GAPEConfig")

    def test_register_map_declared_widths_align_despite_bad_range_annotations(self) -> None:
        report = audit_register_map(SOURCE)
        self.assertEqual(report["declared_width_alignment_status"], "passed")
        self.assertGreater(report["annotation_range_mismatch_count"], 0)
        self.assertTrue(all(item["aligned"] for item in report["maxpool_module_alignment"]))
        self.assertGreater(report["maxpool_semantic_field_rows"], 0)
        self.assertEqual(report["official_consumer_probe"]["field_binding_count"], 739)
        self.assertEqual(
            report["official_consumer_probe"]["sample_binding_widths"][
                "rd_stream0.stream_engine.stream.base_addr"
            ],
            30,
        )

    def test_unknown_top_level_group_fails_closed(self) -> None:
        value = deepcopy(self.template)
        value["guessed_hardware_field"] = 1
        with self.assertRaisesRegex(TargetConfigAuditError, "unexpected"):
            validate_maxpool_template(value)

    def test_encoder_overflow_fails_before_silent_truncation(self) -> None:
        value = deepcopy(self.template)
        value["dram_loop_configs"]["LC1"]["end"] = 1 << 17
        with self.assertRaisesRegex(TargetConfigAuditError, "refusing silent truncation"):
            validate_maxpool_template(value)

    def test_maxpool_encoder_is_reproducible_and_field_sensitive(self) -> None:
        report = audit_maxpool_encoder(SOURCE)
        self.assertEqual(report["determinism"]["status"], "passed")
        self.assertEqual(report["differential_sensitivity"]["status"], "passed")
        self.assertNotEqual(
            report["differential_sensitivity"]["baseline_128b_sha256"],
            report["differential_sensitivity"]["modified_128b_sha256"],
        )
        self.assertEqual(report["fail_closed"]["status"], "passed")

    def test_second_maxpool_accepts_official_binary_addresses_and_links_shape(self) -> None:
        structural = validate_maxpool_template(self.second_maxpool)
        linkage = validate_maxpool_shape_linkage(
            self.second_maxpool,
            channels=16,
            height=16,
            width=16,
        )
        self.assertEqual(structural["ga_opcodes"], ["int8_max"])
        self.assertEqual(linkage["shape"]["output_height"], 8)
        self.assertEqual(linkage["stream_formulas"]["read_dim_stride_bytes"], [4, 64, 1024])
        self.assertTrue(linkage["buffer_schedule"]["collapsed_single_width_tile"])
        self.assertEqual(linkage["buffer_schedule"]["a_buffer_full_last_index"], 5)
        self.assertEqual(linkage["base_addresses"]["rule"], "planner_owned_and_not_inferred_from_shape")

    def test_avgpool_links_shape_to_int32_sum_but_not_requantization(self) -> None:
        structural = validate_avgpool_template(self.avgpool)
        linkage = validate_avgpool_shape_linkage(
            self.avgpool,
            channels=2048,
            height=7,
            width=7,
        )
        self.assertEqual(structural["resources"]["dram_loops"], 3)
        self.assertEqual(structural["ga_opcodes"], ["int32_sum"])
        self.assertEqual(linkage["shape"]["reduction_elements"], 49)
        self.assertEqual(linkage["shape"]["padded_reduction_elements"], 56)
        self.assertEqual(linkage["ga"]["input_conversion"], "uint8_to_int32")
        self.assertEqual(linkage["stage_scope"], "uint8_input_to_int32_spatial_sum_only")
        self.assertIn("x_scale/y_scale requantization", linkage["not_proven"])

    def test_pool_family_delta_and_shared_chain_are_fully_accounted(self) -> None:
        linkage = extract_pool_family_linkage(
            self.template,
            self.second_maxpool,
            self.avgpool,
        )
        self.assertEqual(linkage["status"], "passed")
        self.assertEqual(linkage["maxpool_template_delta"]["changed_leaf_count"], 18)
        self.assertEqual(linkage["maxpool_template_delta"]["unexpected_paths"], [])
        self.assertEqual(
            [stage["stage"] for stage in linkage["shared_chain"]],
            ["shape", "LC", "stream", "buffer", "GA"],
        )
        self.assertIn(
            "stream_engine.stream1.base_addr",
            linkage["maxpool_template_delta"]["planner_owned_paths"],
        )

    def test_second_maxpool_and_avgpool_encoders_are_reproducible_sensitive_and_safe(self) -> None:
        report = audit_pool_family(SOURCE)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["template_count"], 3)
        for template_name in (SECOND_MAXPOOL_TEMPLATE, AVGPOOL_TEMPLATE):
            probe = report["encoder_probes"][template_name]
            self.assertEqual(probe["determinism"]["status"], "passed")
            self.assertEqual(probe["differential_sensitivity"]["status"], "passed")
            self.assertNotEqual(
                probe["differential_sensitivity"]["baseline_128b_sha256"],
                probe["differential_sensitivity"]["modified_128b_sha256"],
            )
            self.assertEqual(probe["fail_closed"]["status"], "passed")
        self.assertEqual(report["numerical_scope"]["status"], "not_validated")

    def test_pool_linkage_mutations_fail_closed(self) -> None:
        bad_address = deepcopy(self.second_maxpool)
        bad_address["stream_engine"]["stream0"]["base_addr"] = "0b101"
        with self.assertRaisesRegex(TargetConfigAuditError, "exactly 30 binary bits"):
            validate_maxpool_template(bad_address)

        bad_avg_opcode = deepcopy(self.avgpool)
        bad_avg_opcode["general_array"]["PE_array"]["PE00"]["alu_opcode"] = "int8_max"
        with self.assertRaisesRegex(TargetConfigAuditError, "must use one of"):
            validate_avgpool_template(bad_avg_opcode)

        bad_avg_conversion = deepcopy(self.avgpool)
        bad_avg_conversion["general_array"]["inport"]["inport0"]["uint8toint32"] = "false"
        with self.assertRaisesRegex(TargetConfigAuditError, "Pool linkage"):
            validate_avgpool_shape_linkage(
                bad_avg_conversion,
                channels=2048,
                height=7,
                width=7,
            )

    def test_quant_and_add_dequant_crosswalk_exposes_exact_dtype_and_constant_recipe(self) -> None:
        quant = validate_quant_template(self.quant)
        add_dequant = validate_add_dequant_template(self.add_dequant)
        crosswalk = extract_ga_quant_add_crosswalk(self.quant, self.add_dequant)

        self.assertEqual(quant["ga_topology"], "8x(mac_then_int32_sub)")
        self.assertEqual(add_dequant["ga_topology"], "4x(two_branch_mac_then_add)")
        quant_crosswalk = crosswalk["quant_from_buffer"]
        self.assertEqual(
            quant_crosswalk["declared_dtype_path"],
            ["int32_buffer", "fp32_mac", "int32_sub", "uint8_D"],
        )
        self.assertEqual(quant_crosswalk["fixed_constants"]["magic_addend_fp32_bits"], "0x4b400040")
        self.assertEqual(quant_crosswalk["fixed_constants"]["derived_output_zero_point"], 64)
        self.assertEqual(quant_crosswalk["saturation"]["status"], "rtl_static_semantics_identified")
        self.assertFalse(quant_crosswalk["direct_onnx_quantize_linear_compatible"])
        add_crosswalk = crosswalk["add_dequant"]
        self.assertEqual(add_crosswalk["static_formula"], "(A*1.0+1.0) + (B*1.0+1.0)")
        self.assertEqual(add_crosswalk["output_dtype"], "fp32")
        self.assertFalse(add_crosswalk["complete_qlinearadd_compatible"])

    def test_semantic_qparam_patch_maps_replicate_all_ga_lanes(self) -> None:
        quant_patch = quant_requant_constant_patch(
            multiplier=0.125,
            output_zero_point=114,
        )
        self.assertEqual(len(quant_patch), 24)
        self.assertEqual(
            quant_patch["general_array.PE_array.PE00.inport2.constant"],
            12_583_026.0,
        )
        self.assertEqual(
            quant_patch["general_array.PE_array.PE33.inport1.constant"],
            0x4B400000,
        )
        add_patch = add_dequant_constant_patch(
            a_scale=0.25,
            a_zero_point=8,
            b_scale=0.5,
            b_zero_point=3,
        )
        self.assertEqual(len(add_patch), 16)
        self.assertEqual(add_patch["general_array.PE_array.PE00.inport2.constant"], -2.0)
        self.assertEqual(add_patch["general_array.PE_array.PE01.inport2.constant"], -1.5)

    def test_real_resnet_scalar_qparams_do_not_match_static_template_samples(self) -> None:
        report = audit_resnet_scalar_qparams(
            ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx",
            expected_sha256=self.model_graph["model_sha256"],
        )
        self.assertEqual(
            report["operator_counts"],
            {"QuantizeLinear": 2, "DequantizeLinear": 2, "QLinearAdd": 17},
        )
        comparison = report["static_template_comparison"]
        self.assertEqual(comparison["quantize_linear_output_zero_points"], [114, 0])
        self.assertEqual(comparison["quantize_linear_direct_match_count"], 0)
        self.assertEqual(
            comparison["dequantize_linear_zero_points"],
            [0, 60],
        )
        self.assertEqual(comparison["dequantize_linear_fixed_branch_match_count"], 0)
        self.assertEqual(comparison["qlinearadd_branch_affine_match_count"], 0)
        self.assertEqual(comparison["qlinearadd_branch_count"], 34)
        self.assertFalse(comparison["qlinearadd_y_qparams_consumed_by_template"])

    def test_execplan_handlers_confirm_qparam_binding_gap(self) -> None:
        report = audit_execplan_qparam_binding(SOURCE)
        self.assertEqual(report["status"], "gap_confirmed")
        self.assertEqual(report["current_binding"], "shape_and_stream_stride_only")
        self.assertEqual(len(report["handler_fields"]["quant_from_buffer"]), 5)
        self.assertEqual(len(report["handler_fields"]["add_dequant"]), 8)
        self.assertFalse(report["ga_constant_qparams_patched"])

    def test_quant_and_add_dequant_encoders_are_constant_sensitive_and_fail_closed(self) -> None:
        report = audit_ga_quant_add(
            SOURCE,
            model_path=ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx",
            model_sha256=self.model_graph["model_sha256"],
        )
        self.assertEqual(report["status"], "passed_with_numerical_gaps")
        self.assertEqual(report["template_count"], 2)
        for template_name in (QUANT_TEMPLATE, ADD_DEQUANT_TEMPLATE):
            probe = report["encoder_probes"][template_name]
            self.assertEqual(probe["determinism"]["status"], "passed")
            self.assertEqual(probe["differential_sensitivity"]["status"], "passed")
            self.assertIn("constant", probe["differential_sensitivity"]["field"])
            self.assertNotEqual(
                probe["differential_sensitivity"]["baseline_128b_sha256"],
                probe["differential_sensitivity"]["modified_128b_sha256"],
            )
            self.assertEqual(probe["fail_closed"]["status"], "passed")
        self.assertEqual(report["numerical_scope"]["status"], "not_validated")

    def test_ga_qparam_and_conversion_mutations_fail_closed(self) -> None:
        bad_quant = deepcopy(self.quant)
        bad_quant["general_array"]["inport"]["inport0"]["int32tofp32"] = "false"
        with self.assertRaisesRegex(TargetConfigAuditError, "conversion route"):
            validate_quant_template(bad_quant)

        bad_add = deepcopy(self.add_dequant)
        bad_add["general_array"]["outport"]["int32touint8"] = "true"
        with self.assertRaisesRegex(TargetConfigAuditError, "remain FP32"):
            validate_add_dequant_template(bad_add)

        with self.assertRaisesRegex(TargetConfigAuditError, "unsigned 8-bit"):
            quant_requant_constant_patch(multiplier=0.5, output_zero_point=256)
        with self.assertRaisesRegex(TargetConfigAuditError, "finite and positive"):
            add_dequant_constant_patch(
                a_scale=float("nan"),
                a_zero_point=0,
                b_scale=1.0,
                b_zero_point=0,
            )


if __name__ == "__main__":
    unittest.main()
