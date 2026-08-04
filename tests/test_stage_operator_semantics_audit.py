from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.stage_operator_semantics_audit import (
    CONTRACT_PATH,
    GAP_CONFIG_PATH,
    GAP_D_INDEX_BLOCKER,
    GAP_REQUEST_ID,
    StageOperatorSemanticsAuditError,
    analyze_gap_d_index_coverage,
    buffer_array_request_sequence,
    ga_int32_to_fp32_rtl_result,
    ga_int8_max_rtl_result,
    ga_transout_decision,
    lc_pe_int_result,
    mse_boundary_masks,
    mse_buffer_lane_plan,
    mse_lane_indexes,
    mse_memory_request_address,
    mse_transfer_plan,
    n2n_neighbor,
    n2n_transfer_plan,
    require_gap_d_index_coverage,
    sa_fp32_output_conversion,
    sa_int8_rtl_result,
    sa_int8_rtl_trace,
    sa_transout_decision,
    validate_stage_operator_semantics_audit,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gap_request() -> dict:
    bundle = _load(ROOT / "contracts/resnet50_r5_lowering_bundle.json")
    return next(
        item
        for item in bundle["requests"]
        if item["request_id"] == GAP_REQUEST_ID
    )


class StageOperatorSemanticsAuditTests(unittest.TestCase):
    def test_checked_contract_is_hash_bound_and_classified(self) -> None:
        value = validate_stage_operator_semantics_audit(ROOT, CONTRACT)
        findings = {
            item["issue_id"]: item["classification"]
            for item in value["findings"]
        }
        self.assertEqual(findings["CDA-LC-SRC-001"], "RTL_PROVEN")
        self.assertEqual(
            findings["CDA-GAP-D-INDEX-001"], "CONTRADICTED"
        )
        self.assertEqual(
            findings["CDA-MSE-RD-VALID-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-MSE0-RD-REPLAY-001"], "CONTRADICTED"
        )
        self.assertEqual(
            findings["CDA-GAP-GA-ACCUM-STATE-001"], "CONTRADICTED"
        )
        self.assertEqual(findings["CDA-LCPE-PACK-001"], "RTL_PROVEN")
        self.assertEqual(findings["CDA-LCPE-ALU-001"], "RTL_PROVEN")
        self.assertEqual(
            findings["CDA-LCPE-MODE-TAG-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-MSE-PACK-MODE-001"], "RTL_PROVEN"
        )
        self.assertEqual(findings["CDA-MSE-ADDR-001"], "RTL_PROVEN")
        self.assertEqual(findings["CDA-MSE-SPLIT-001"], "RTL_PROVEN")
        self.assertEqual(findings["CDA-MSE-WR-RMW-001"], "RTL_PROVEN")
        self.assertEqual(
            findings["CDA-MSE-LANE-BOUND-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-PADDING-TAIL-DATA-001"], "RTL_PROVEN"
        )
        self.assertEqual(findings["CDA-BUFFER-AG-001"], "RTL_PROVEN")
        self.assertEqual(
            findings["CDA-BUFFER-MANAGER-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-SA-PACK-TOPOLOGY-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-SA-ACCUM-TAG-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-SA-INT8-CSA-001"], "CONTRADICTED"
        )
        self.assertEqual(findings["CDA-SA-OUTPORT-001"], "RTL_PROVEN")
        self.assertEqual(
            findings["CDA-SA-FP-CONVERT-001"], "CONTRADICTED"
        )
        self.assertEqual(
            findings["CDA-GA-PACK-ROUTE-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-GA-OPCODE-OPERAND-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-GA-INPORT-CONVERT-001"], "CONTRADICTED"
        )
        self.assertEqual(
            findings["CDA-GA-TRANSOUT-OUTPORT-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-GA-INT8-MAX-PIPE-001"], "CONTRADICTED"
        )
        self.assertEqual(
            findings["CDA-N2N-ROUTE-TRANSFER-001"], "RTL_PROVEN"
        )
        self.assertEqual(
            findings["CDA-N2N-PINGPONG-LIFETIME-001"], "CONTRADICTED"
        )
        gap = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-GAP-D-INDEX-001"
        )
        self.assertIn(
            GAP_D_INDEX_BLOCKER, gap["impact"]["stage_backend"]
        )
        lc_pe = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-LCPE-ALU-001"
        )
        corpus = lc_pe["authorized_corpus"]
        self.assertEqual(corpus["authorized_config_count"], 65)
        self.assertEqual(corpus["lc_pe_instance_count"], 193)
        self.assertEqual(corpus["opcode_counts"], {"mac": 42, "mul": 151})
        self.assertEqual(corpus["strict_subset_violation_count"], 0)
        mse = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-MSE-PACK-MODE-001"
        )
        mse_corpus = mse["authorized_corpus"]
        self.assertEqual(mse_corpus["stream_count"], 177)
        self.assertEqual(
            mse_corpus["stream_mode_counts"], {"read": 112, "write": 65}
        )
        self.assertEqual(
            mse_corpus["buf_mode_patterns"], {"keep,buffer": 177}
        )
        self.assertEqual(
            mse_corpus["legacy_integer_zero_null_alias_count"], 4
        )
        self.assertEqual(
            value["next_audit"]["ledger_id"], "C1-DYNAMIC-CONFORMANCE"
        )
        buffer = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-BUFFER-AG-001"
        )
        buffer_corpus = buffer["authorized_corpus"]
        self.assertEqual(buffer_corpus["buffer_instance_count"], 193)
        self.assertEqual(buffer_corpus["pingpong_enabled_count"], 5)
        self.assertEqual(buffer_corpus["read_threshold_match_count"], 112)
        self.assertEqual(buffer_corpus["mapped_buffer_missing_count"], 0)
        sa = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-SA-PACK-TOPOLOGY-001"
        )
        self.assertEqual(sa["authorized_corpus"]["sa_config_count"], 8)
        self.assertEqual(
            sa["authorized_corpus"]["data_type_counts"], {"fp16": 8}
        )
        self.assertEqual(
            sa["authorized_corpus"]["pair_threshold_match_count"], 16
        )
        ga = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-GA-PACK-ROUTE-001"
        )
        self.assertEqual(ga["authorized_corpus"]["ga_config_count"], 60)
        self.assertEqual(ga["authorized_corpus"]["pe_instance_count"], 511)
        self.assertEqual(
            ga["authorized_corpus"]["input_pingpong_enabled_count"], 0
        )
        n2n = next(
            item
            for item in value["findings"]
            if item["issue_id"] == "CDA-N2N-ROUTE-TRANSFER-001"
        )
        self.assertEqual(n2n["authorized_corpus"]["n2n_config_count"], 3)
        self.assertEqual(
            n2n["authorized_corpus"]["neighbor_stream_count"], 3
        )

    def test_lc_pe_rtl_micro_model_wraps_to_low_16_bits(self) -> None:
        self.assertEqual(lc_pe_int_result("add", 0xFFFF, 2), 0x0001)
        self.assertEqual(lc_pe_int_result("mul", 0xFFFF, 2), 0xFFFE)
        self.assertEqual(
            lc_pe_int_result("mac", 0x8000, 2, 1), 0x0001
        )
        with self.assertRaises(StageOperatorSemanticsAuditError):
            lc_pe_int_result("max", 1, 2)

    def test_mse_rtl_address_and_unaligned_split_micro_models(self) -> None:
        self.assertEqual(
            mse_memory_request_address(
                [1, 2, 3],
                [4, 32, 256],
                base_addr=0x1000,
            ),
            0x134,
        )
        self.assertEqual(
            mse_memory_request_address(
                [1, 2, 3],
                [4, 32, 256],
                base_addr=0x1000,
                transfer_bias=12,
            ),
            0x135,
        )
        plan = mse_transfer_plan(4, 32)
        self.assertEqual(
            [
                (
                    item["transfer_bias"],
                    item["start_position"],
                    item["size"],
                    item["valid_mask"],
                )
                for item in plan
            ],
            [
                (0, 4, 12, 0xFFF0),
                (12, 0, 16, 0xFFFF),
                (28, 0, 4, 0x000F),
            ],
        )
        with self.assertRaises(StageOperatorSemanticsAuditError):
            mse_memory_request_address(
                [0, 0],
                [1, 1],
                base_addr=0,
            )
        with self.assertRaises(StageOperatorSemanticsAuditError):
            mse_transfer_plan(0, 0)

    def test_mse_lane_bounds_and_unaligned_mask_priority(self) -> None:
        self.assertEqual(
            mse_lane_indexes(
                [10, 20, 30],
                [3, 1, None],
                transfer_bias=0,
                lane=5,
            ),
            (11, 21, 30),
        )
        masks = mse_boundary_masks(
            [0, 0, 0],
            [3, 1, None],
            transfer_bias=0,
            start_position=4,
            valid_mask=0xFFF0,
            padding_enable=[1, 0, 0],
            padding_low=[1, None, None],
            padding_up=[2, None, None],
            tailing_enable=[0, 1, 0],
            tailing_low=[None, 0, None],
            tailing_up=[None, 0, None],
        )
        self.assertEqual(masks["padding_mask_physical"], 0x9990)
        self.assertEqual(masks["tailing_mask_physical"], 0x0F00)
        self.assertEqual(masks["read_lane_sources"][8], "padding")
        self.assertEqual(masks["read_lane_sources"][9], "zero")
        self.assertEqual(masks["write_lane_sources"][8], "old_ddr")
        self.assertEqual(masks["write_lane_sources"][9], "old_ddr")

    def test_buffer_lane_decode_and_array_traversal(self) -> None:
        plan = mse_buffer_lane_plan(
            2, 30, [0, 1, 2, 3], spatial_size=4
        )
        self.assertEqual(plan["request_valid_mask"], 0xF)
        self.assertEqual(
            [
                (
                    lane["row"],
                    lane["expanded_col"],
                    lane["bank"],
                    lane["byte_offset"],
                )
                for lane in plan["lanes"]
            ],
            [
                (2, 30, 7, 2),
                (2, 31, 7, 3),
                (2, 0, 0, 0),
                (2, 1, 0, 1),
            ],
        )
        self.assertEqual(
            [
                (item["row"], item["lifetime_index"])
                for item in buffer_array_request_sequence(
                    mode=0, end_row=1, logical_lifetime=2
                )
            ],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
        )
        self.assertEqual(
            [
                (item["row"], item["lifetime_index"])
                for item in buffer_array_request_sequence(
                    mode=1, end_row=1, logical_lifetime=2
                )
            ],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
        )

    def test_sa_int8_csa_and_terminal_micro_models(self) -> None:
        positive = sa_int8_rtl_trace([1, 1, 1, 1], [1, 1, 1, 1])
        self.assertEqual(positive["rtl_result32"], 6)
        self.assertEqual(positive["conventional_dot_plus_psum32"], 4)
        self.assertFalse(positive["matches_conventional_dot"])
        self.assertEqual(
            sa_int8_rtl_result([-1, -1, -1, -1], [1, 1, 1, 1]),
            0xFFFFFFFA,
        )
        self.assertEqual(
            sa_transout_decision(
                upstream_last=True,
                upstream_last_index=3,
                transout_last_index=2,
            ),
            {
                "ignore": True,
                "matched": False,
                "out": False,
                "result_last": False,
                "accumulator_bank_change": False,
            },
        )
        self.assertTrue(
            sa_transout_decision(
                upstream_last=True,
                upstream_last_index=1,
                transout_last_index=2,
            )["result_last"]
        )

    def test_sa_fp32_narrowing_preserves_documented_rtl_corners(self) -> None:
        self.assertEqual(sa_fp32_output_conversion(0x3F800000, "fp16"), 0x3C00)
        self.assertEqual(sa_fp32_output_conversion(0x3F800000, "bf16"), 0x3F80)
        self.assertEqual(sa_fp32_output_conversion(0x3FFFF000, "fp16"), 0x3C00)
        self.assertEqual(sa_fp32_output_conversion(0x3FFF8000, "bf16"), 0x3F80)

    def test_ga_conversion_int8_max_and_terminal_rtl_counterexamples(self) -> None:
        self.assertEqual(
            ga_int32_to_fp32_rtl_result(0xFFFFFFFF),
            0xCF000000,
        )
        self.assertEqual(
            ga_int32_to_fp32_rtl_result(0x80000000),
            0xCE800000,
        )
        self.assertEqual(
            ga_int8_max_rtl_result(0x04030201, 0x01020304),
            0x01020201,
        )
        self.assertEqual(
            ga_transout_decision(
                reduction_opcode=True,
                upstream_last=True,
                upstream_last_index=3,
                transout_last_index=3,
            ),
            {
                "ordinary_result_last": False,
                "reduction_flush_trigger": True,
                "reduction_result_forces_last_after_flush": True,
                "threshold_equal_suppresses_pre_flush_last": True,
            },
        )

    def test_n2n_ring_and_hardwired_buffer_transfer_micro_models(self) -> None:
        self.assertEqual(n2n_neighbor(0, 0, "previous"), 1)
        self.assertEqual(n2n_neighbor(0, 0, "next"), 12)
        self.assertEqual(n2n_neighbor(0, 1, "previous"), 1)
        self.assertEqual(n2n_neighbor(0, 1, "next"), 2)
        plan = n2n_transfer_plan(4)
        self.assertEqual(plan["encoded_nse_cnt_size"], 3)
        self.assertEqual(plan["transfer_count"], 3)
        self.assertEqual(
            plan["source_buffers"],
            ["buffer0", "buffer1", "buffer0"],
        )
        self.assertEqual(
            plan["destination_buffers"],
            ["buffer1", "buffer0", "buffer1"],
        )
        self.assertFalse(plan["json_ping_pong_bit_controls_sequence"])

    def test_current_gap_config_fails_typed_d_index_coverage(self) -> None:
        config = _load(ROOT / GAP_CONFIG_PATH)
        request = _gap_request()
        report = analyze_gap_d_index_coverage(config, request)
        self.assertEqual(report["classification"], "CONTRADICTED")
        self.assertEqual(report["derived_distinct_transaction_bases"], 1)
        self.assertEqual(report["required_distinct_transaction_bases"], 256)
        with self.assertRaises(StageOperatorSemanticsAuditError):
            require_gap_d_index_coverage(config, request)

    def test_src_id_change_does_not_change_local_lc_value_domain(self) -> None:
        config = _load(ROOT / GAP_CONFIG_PATH)
        config["dram_loop_configs"]["LC2"]["src_id"] = "DRAM_LC.LC1"
        report = analyze_gap_d_index_coverage(config, _gap_request())
        self.assertEqual(report["derived_distinct_transaction_bases"], 1)
        carrier = report["dimensions"][0]["domain"]["carrier"]
        self.assertEqual(carrier["src_id_role"], "trigger_tag_dependency_only")

    def test_minimal_positive_meets_only_the_necessary_coverage_gate(self) -> None:
        config = _load(ROOT / GAP_CONFIG_PATH)
        config["dram_loop_configs"]["LC2"]["end"] = 256
        report = require_gap_d_index_coverage(config, _gap_request())
        self.assertEqual(report["derived_distinct_transaction_bases"], 256)
        self.assertTrue(report["necessary_condition_passed"])
        self.assertIn("necessary", report["scope"])

    def test_contract_tamper_fails_closed(self) -> None:
        value = _load(CONTRACT)
        tampered = copy.deepcopy(value)
        tampered["findings"][0]["classification"] = "SAMPLE_SUPPORTED"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tampered.json"
            path.write_text(
                json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(StageOperatorSemanticsAuditError):
                validate_stage_operator_semantics_audit(ROOT, path)


if __name__ == "__main__":
    unittest.main()
