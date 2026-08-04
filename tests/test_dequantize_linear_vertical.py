from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.dequantize_linear_vertical import (
    FIRST_STAGE_LINEAR,
    SECOND_STAGE_LINEAR,
    build_execplan_request,
    build_generation_receipt,
    build_layout_evidence,
    build_numeric_evidence,
    build_operator_config,
    validate_execplan_request,
    validate_operator_config,
)


ROOT = Path(__file__).resolve().parents[1]
E2_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-dequant-node0077-e2-v6"
)


class DequantizeLinearVerticalTests(unittest.TestCase):
    def test_generation_gate_binds_rules_and_read_only_upstream(self) -> None:
        receipt = build_generation_receipt(ROOT)
        self.assertEqual(
            receipt["status"],
            "generation_gate_satisfied_before_json_materialization",
        )
        self.assertIn("CDA-DEQUANT-TWO-STAGE-GA-001", receipt["rule_ids"])
        read_receipt = {
            item["path"]: item["sha256"] for item in receipt["read_receipt"]
        }
        self.assertEqual(
            read_receipt[".agents/rules/生成前必读索引.md"],
            "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
        )
        self.assertEqual(
            read_receipt[".agents/rules/算子配置规则.md"],
            "a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b",
        )
        self.assertEqual(
            read_receipt[".agents/rules/DequantizeLinear算子配置规则.md"],
            "2374975170515252b1ea2d1c1ffc806af5b757c286322ba91b194c0bac0419d7",
        )
        self.assertIn(
            "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
            receipt["rule_ids"],
        )
        self.assertEqual(
            receipt["open_dynamic_gates"][0]["classification"],
            "FIRST_DYNAMIC_PASS_E4",
        )
        self.assertEqual(
            receipt["open_dynamic_gates"][0]["blocker_id"],
            "B_DEQUANT_SERVER_E5",
        )
        self.assertEqual(
            receipt["upstream_identity"]["active_source_policy"], "read_only"
        )
        self.assertEqual(
            receipt["lowering_request"]["request_sha256"],
            "cb8522a4ba2386ce3c303f5de274b2fa2e130d719c09933c686a11d28d9b7f63",
        )
        self.assertTrue(
            receipt["lowering_request"][
                "identity_is_independent_of_effective_resolution_overlay"
            ]
        )

    def test_real_w3_golden_requires_subtract_then_multiply(self) -> None:
        evidence = build_numeric_evidence(ROOT)
        self.assertTrue(evidence["two_stage_bit_exact"])
        self.assertEqual(evidence["element_count"], 16000)
        self.assertEqual(evidence["affine_mac_bit_mismatch_count"], 12976)
        self.assertEqual(
            evidence["two_stage_sha256"], evidence["w3_output_sha256"]
        )

    def test_config_is_exact_two_stage_normal_outbuffer_topology(self) -> None:
        config = build_operator_config(ROOT)
        report = validate_operator_config(config, ROOT)
        exact = report["exact_topology"]
        self.assertEqual(
            exact["first_stage"], ["PE00", "PE02", "PE20", "PE22"]
        )
        self.assertEqual(
            exact["second_stage"], ["PE10", "PE12", "PE30", "PE32"]
        )
        self.assertTrue(exact["normal_outbuffer_only"])
        self.assertEqual(exact["stream_targets"], ["A", "D"])
        self.assertNotIn("stream1", config["stream_engine"])
        self.assertNotIn("buffer2", config["buffer_config"])
        self.assertEqual(
            config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"], 4
        )
        self.assertEqual(
            exact["d_buffer_supply"],
            {
                "transaction_bytes": 64,
                "buffer_bytes_per_request": 16,
                "row_trip_count": 4,
                "supply_bytes": 64,
                "last_row_index": 3,
            },
        )

    def test_d_buffer_row_undersupply_is_rejected(self) -> None:
        config = deepcopy(build_operator_config(ROOT))
        config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 1
        with self.assertRaisesRegex(
            ValueError,
            "D buffer supply does not cover one 64-byte transaction",
        ):
            validate_operator_config(config, ROOT)

    def test_high4_layout_has_28_exact_neutral_tails(self) -> None:
        evidence = build_layout_evidence(ROOT)
        self.assertEqual(evidence["slice_count"], 28)
        self.assertEqual(evidence["hardware_shape_cwh"], [16, 47, 1])
        self.assertEqual(evidence["a_bytes_per_slice"], 752)
        self.assertEqual(evidence["d_bytes_per_slice"], 3008)
        self.assertTrue(evidence["prefix_matches_existing_layout"])
        self.assertTrue(evidence["inverse_bit_exact"])
        self.assertEqual(
            {item["a_tail_hex"] for item in evidence["slices"]}, {"3c3c"}
        )
        self.assertEqual(
            {item["d_tail_hex"] for item in evidence["slices"]},
            {"0000000000000000"},
        )

    def test_typed_bindings_use_sparse_coordinate_identity(self) -> None:
        request = build_execplan_request(ROOT)
        report = validate_execplan_request(request, ROOT)
        self.assertEqual(report["typed_constant_count"], 2)
        self.assertEqual(report["target_binding_count"], 8)
        constants = request["operators"][0]["constants"]

        def indices(name: str) -> list[int]:
            return [
                int(
                    item["location"]
                    .split(":", 1)[1]
                    .split(".", 1)[0]
                    .removeprefix("ga_pe")
                )
                for item in constants[name]["target_bindings"]
            ]

        self.assertEqual(indices("negative_zero_point"), list(FIRST_STAGE_LINEAR))
        self.assertEqual(indices("x_scale"), list(SECOND_STAGE_LINEAR))

    def test_materialized_local_e2_report_is_fail_closed_at_e4(self) -> None:
        report = json.loads(
            (E2_ROOT / "local_e2_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            report["status"], "local_e2_passed_server_e4_e5_pending"
        )
        self.assertFalse(report["candidate_release"])
        self.assertTrue(report["bitstream"]["double_run_identical"])
        self.assertTrue(report["bitstream"]["two_isolated_toolchains"])
        self.assertTrue(
            report["bitstream"]["full_lifecycle_products_identical"]
        )
        self.assertTrue(
            report["mapping"]["encoded_bitstream_constants_verified"]
        )
        self.assertEqual(report["mapping"]["placement_penalty"], 0)
        self.assertFalse(report["mapping"]["fallback_used"])
        self.assertTrue(report["materialized_roundtrip"]["valid"])
        self.assertEqual(
            report["materialized_roundtrip"]["d_buffer_rows_per_occurrence"], 4
        )
        self.assertEqual(
            report["materialized_roundtrip"][
                "d_buffer_supply_bytes_per_occurrence"
            ],
            64,
        )
        self.assertEqual(report["execplan_lifecycle"]["sca_d_slice_count"], 28)
        self.assertEqual(
            report["execplan_lifecycle"]["sca_d_words_per_slice"], 188
        )
        self.assertTrue(
            report["execplan_lifecycle"][
                "independent_machine_explanation_roundtrip"
            ]["machine_explanation_bit_exact"]
        )
        self.assertEqual(
            report["mapping"]["constants"],
            {
                "PE00": "0xc2700000",
                "PE02": "0xc2700000",
                "PE10": "0x3e01622d",
                "PE12": "0x3e01622d",
                "PE20": "0xc2700000",
                "PE22": "0xc2700000",
                "PE30": "0x3e01622d",
                "PE32": "0x3e01622d",
            },
        )
        self.assertEqual(
            report["remaining_blockers"], ["B_DEQUANT_SERVER_E4_E5"]
        )


if __name__ == "__main__":
    unittest.main()
