from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.w5_conv_preflight import (
    W5ConvPreflightError,
    build_w5_first_conv_preflight,
    validate_w5_first_conv_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "artifacts" / "w5" / "hwop-0004-00" / "preflight.json"


class W5FirstConvPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_w5_first_conv_preflight(ROOT)

    def test_selects_the_real_recommended_1x1_instance(self) -> None:
        report = self.report
        self.assertEqual(report["selection"]["node_id"], "node-0004")
        self.assertEqual(
            report["selection"]["hw_op_ids"],
            ["hwop-0004-00", "hwop-0004-01"],
        )
        logical = report["logical_instance"]
        self.assertEqual(logical["activation_shape"], [16, 64, 56, 56])
        self.assertEqual(logical["weight_shape"], [64, 64, 1, 1])
        self.assertEqual(logical["output_shape"], [16, 64, 56, 56])
        self.assertEqual(
            logical["dtype_path"],
            ["uint8_A", "int8_B", "int32_bias_and_P", "uint8_D"],
        )
        self.assertEqual(len(report["field_provenance"]), 11)
        self.assertTrue(all(item["verified"] for item in report["field_provenance"]))

    def test_real_high4_tile_matches_w3_golden_and_w4_physical_bytes(self) -> None:
        tile = self.report["first_tile_golden_preflight"]
        self.assertEqual(tile["destination_slice"], 0)
        self.assertEqual(tile["high_ring_owners"], [0, 2, 3, 1])
        self.assertEqual(tile["reduction_traversal"], [0, 1, 3, 2])
        self.assertEqual(tile["logical_im2col_projection"], {"M": 9408, "N": 16, "K": 64})
        self.assertEqual([item["phase"] for item in tile["k_lifecycle"]], [
            "first", "middle", "middle", "last"
        ])
        self.assertEqual(
            sum(item["channel_count"] for item in tile["k_lifecycle"]), 64
        )
        for port in ("P", "D"):
            comparison = tile["comparisons"][port]
            self.assertEqual(comparison["mismatch_count"], 0)
            self.assertEqual(
                comparison["recomputed_sha256"], comparison["w3_sha256"]
            )
            self.assertEqual(len(comparison["physical_sha256"]), 64)

    def test_simulator_and_target_configuration_stop_fail_closed(self) -> None:
        simulator = self.report["deepseek_target_simulator_entry"]
        self.assertEqual(
            simulator["status"],
            "operator_confirmed_conv_backend_config_bound_candidate",
        )
        self.assertFalse(simulator["packager"]["executes_numerical_model"])
        self.assertTrue(simulator["target_runner"]["command"])
        self.assertTrue(simulator["target_runner"]["config_adapter_available"])
        self.assertTrue(simulator["target_runner"]["consumes_target_json"])
        self.assertFalse(simulator["target_runner"]["consumes_target_bitstream"])
        target = self.report["target_configuration"]
        self.assertEqual(target["official_named_conv_template_count"], 0)
        self.assertEqual(target["candidate_named_conv_template_count"], 2)
        self.assertTrue(target["candidate_json_encoded"])
        self.assertTrue(target["candidate_bitstream_generated"])
        self.assertTrue(target["candidate_mapping_review_generated"])
        self.assertTrue(target["real_1x1_patched_json_generated"])
        self.assertTrue(target["real_1x1_bitstream_generated"])
        self.assertTrue(target["real_1x1_mapping_review_generated"])
        self.assertEqual(
            target["operator_candidate"]["placement"]["constraint_cost"], 0
        )
        legacy = target["legacy_generator_probe"]
        self.assertEqual(legacy["status"], "legacy16_reference_only")
        self.assertEqual(legacy["observed"]["slice_count"], 16)
        self.assertEqual(legacy["observed"]["sa_bias_enable"], 0)
        self.assertFalse(legacy["can_serve_as_target_template"])
        self.assertEqual(
            {item["blocker"] for item in target["unresolved_target_bindings"]},
            {
                "B_CONV_TARGET_EXECUTION_SEMANTICS",
                "B_N2N_TARGET_SELECTOR",
                "B_REQUANT_TARGET_NUMERICS",
                "B_EXECPLAN_TYPED_TRANSPORT",
            },
        )
        self.assertTrue(self.report["gate_state"]["stop_expansion"])
        self.assertFalse(self.report["gate_state"]["g5_passed"])
        self.assertFalse(self.report["gate_state"]["g6_passed"])

    def test_real_1x1_first_coordinate_passes_ndp_conv_simulator(self) -> None:
        result = self.report["ndp_conv_simulator_first_coordinate"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["coordinate"], [0, 0, 0, 0])
        self.assertEqual(result["kernel_shape"], [1, 1])
        self.assertEqual(result["source_owners"], [0, 1, 3, 2])
        self.assertEqual(result["accumulator"]["mismatch_count"], 0)
        self.assertEqual(result["output"]["mismatch_count"], 0)
        self.assertEqual(
            result["config_link_status"], "target_json_consumed_and_validated"
        )

    def test_target_config_compares_coordinate_tile_and_full_operator(self) -> None:
        result = self.report["ndp_target_config_comparison"]
        self.assertEqual(result["status"], "passed_with_execution_boundary")
        self.assertTrue(result["not_cycle_accurate_lc_interpretation"])
        comparisons = result["ordered_comparisons"]
        self.assertEqual(
            [item["name"] for item in comparisons],
            ["single_coordinate", "first_tile", "full_operator"],
        )
        self.assertEqual(
            [item["P"]["element_count"] for item in comparisons],
            [1, 150528, 3211264],
        )
        for item in comparisons:
            for port in ("P", "D"):
                self.assertEqual(item[port]["mismatch_count"], 0)
                self.assertEqual(
                    item[port]["actual_sha256"], item[port]["golden_sha256"]
                )

    def test_validator_rejects_target_json_or_gate_overclaim(self) -> None:
        changed = deepcopy(self.report)
        changed["target_configuration"]["real_1x1_bitstream_generated"] = False
        with self.assertRaisesRegex(W5ConvPreflightError, "evidence differs"):
            validate_w5_first_conv_preflight(changed)

        changed = deepcopy(self.report)
        changed["gate_state"]["g6_passed"] = True
        with self.assertRaisesRegex(W5ConvPreflightError, "overclaims"):
            validate_w5_first_conv_preflight(changed)

    def test_checked_in_report_is_exact_generated_output(self) -> None:
        expected = json.dumps(
            self.report, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        self.assertTrue(REPORT_PATH.is_file())
        self.assertEqual(REPORT_PATH.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
