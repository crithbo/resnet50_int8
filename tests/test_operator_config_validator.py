from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_validator import (
    ConfigState,
    OperatorConfigValidator,
    encoded_sa_major,
    keep_releases,
    read_lane_value,
    route_sa_outport,
    validate_sequence,
    write_lane_value,
)


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_JSONS = ROOT / "ndp-sim" / "jsons"


def _load(name: str) -> dict:
    return json.loads((ACTIVE_JSONS / name).read_text(encoding="utf-8"))


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


class SaOutportSemanticsTests(unittest.TestCase):
    def test_legacy_labels_encode_the_opposite_physical_major_names(self) -> None:
        matrix = ((1, 2, 3), (10, 20, 30), (100, 200, 300))
        self.assertEqual(encoded_sa_major("col"), 0)
        self.assertEqual(route_sa_outport(matrix, encoded_sa_major("col")), matrix)
        self.assertEqual(encoded_sa_major("row"), 1)
        self.assertEqual(
            route_sa_outport(matrix, encoded_sa_major("row")),
            ((1, 10, 100), (2, 20, 200), (3, 30, 300)),
        )

    def test_development_mode_requires_and_checks_layout_contract(self) -> None:
        config = _load("node0004_accumulate_wave0_nopp_r1.json")
        missing = OperatorConfigValidator().validate(config, development_mode=True)
        self.assertIn("SA.LAYOUT_CONTRACT_REQUIRED", _codes(missing))
        mismatch = OperatorConfigValidator().validate(
            config,
            development_mode=True,
            expected_sa_transpose=True,
        )
        self.assertIn("SA.LAYOUT_MISMATCH", _codes(mismatch))

    def test_sa_inport_companion_fields_and_fixed_pairs_fail_closed(self) -> None:
        config = _load("decode_gemv_local.json")
        config["special_array"]["inport0"]["pingpong_last_index"] = None
        missing = OperatorConfigValidator().validate(config)
        self.assertIn(
            "SA.PINGPONG_THRESHOLD_REQUIRED", _codes(missing)
        )

        config = _load("decode_gemv_local.json")
        config["special_array"]["inport2"]["pingpong_en"] = 1
        config["special_array"]["inport2"]["pingpong_last_index"] = 3
        bad_pair = OperatorConfigValidator().validate(config)
        self.assertIn("SA.INPORT2_PINGPONG_TOPOLOGY", _codes(bad_pair))

        config = _load("decode_gemv_local.json")
        config["buffer_config"]["buffer2"]["buf_full_last_index"] = 4
        mismatch = OperatorConfigValidator().validate(config)
        self.assertIn("SA.PINGPONG_THRESHOLD_MISMATCH", _codes(mismatch))

    def test_sa_bias_seed_relation_and_int8_equation_are_explicit(self) -> None:
        config = _load("decode_gemv_local.json")
        config["special_array"]["inport2"]["enable"] = 1
        enabled_without_bias = OperatorConfigValidator().validate(config)
        self.assertIn("SA.BIAS_INPORT_DISABLED", _codes(enabled_without_bias))

        int8 = _load("node0004_accumulate_wave0_nopp_r1.json")
        report = OperatorConfigValidator().validate(int8)
        self.assertFalse(
            report.facts["sa_int8_mac"][
                "conventional_four_lane_dot_equivalent"
            ]
        )
        self.assertEqual(
            report.facts["sa_int8_mac"]["classification"],
            "CONTRADICTED",
        )


class BoundarySemanticsTests(unittest.TestCase):
    def test_keep_threshold_is_inclusive(self) -> None:
        self.assertTrue(keep_releases(True, 2, 3))
        self.assertTrue(keep_releases(True, 3, 3))
        self.assertFalse(keep_releases(True, 4, 3))
        self.assertFalse(keep_releases(False, 0, 3))

    def test_read_padding_has_priority_over_tailing(self) -> None:
        actual = read_lane_value(
            77,
            (0, 9, 0),
            padding_enable=(1, 0, 0),
            padding_low=(1, None, None),
            padding_up=(8, None, None),
            padding_value=13,
            tailing_enable=(0, 1, 0),
            tailing_low=(None, 0, None),
            tailing_up=(None, 4, None),
        )
        self.assertEqual(actual, 13)

    def test_write_tailing_merges_old_ddr_lane(self) -> None:
        self.assertEqual(
            write_lane_value(
                99,
                42,
                (5, 0, 0),
                tailing_enable=(1, 0, 0),
                tailing_low=(0, None, None),
                tailing_up=(4, None, None),
            ),
            42,
        )


class TerminalChainTests(unittest.TestCase):
    def test_real_nopp_candidate_reaches_terminal_zero(self) -> None:
        config = _load("node0004_accumulate_wave0_nopp_r1.json")
        report = OperatorConfigValidator().validate(config)
        self.assertIn(0, report.facts["completion"]["possible_last_indices"])
        self.assertEqual(report.facts["completion"]["terminal_condition"], "last=1 && last_index=0, then final DDR write-data handshake")

    def test_breaking_outmost_terminal_source_fails(self) -> None:
        config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        config["dram_loop_configs"]["LC0"]["outmost_loop"] = 0
        report = OperatorConfigValidator().validate(config)
        self.assertIn("GRAPH.ROOT_NOT_OUTMOST", _codes(report))
        self.assertIn("COMPLETION.NO_TERMINAL_ZERO", _codes(report))


class StrictSchemaInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")

    def test_unknown_field_fails_closed(self) -> None:
        self.config["stream_engine"]["stream0"]["ignored_typo"] = 1
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("SCHEMA.UNKNOWN_FIELD", _codes(report))

    def test_spatial_length_must_equal_enabled_size(self) -> None:
        self.config["stream_engine"]["stream0"]["buf_spatial_stride"].pop()
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("STREAM.SPATIAL_ARITY", _codes(report))

    def test_disabled_bound_must_be_null(self) -> None:
        stream = self.config["stream_engine"]["stream0"]
        stream["idx_tailing_range"]["low"][0] = 0
        stream["idx_tailing_range"]["up"][0] = 0
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("STREAM.DISABLED_BOUNDS", _codes(report))

    def test_read_only_padding_fields_on_write_fail(self) -> None:
        stream = next(
            value
            for value in self.config["stream_engine"].values()
            if value["mode"] == "write"
        )
        stream["padding_enable"] = [0, 0, 0]
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("SCHEMA.UNKNOWN_FIELD", _codes(report))

    def test_illegal_address_string_and_row_limit_fail(self) -> None:
        self.config["stream_engine"]["stream0"]["base_addr"] = "1010"
        parsed = OperatorConfigValidator().validate(self.config)
        self.assertIn("ADDRESS.PARSE", _codes(parsed))

        self.config["stream_engine"]["stream0"]["base_addr"] = 6144 << 10
        row = OperatorConfigValidator().validate(self.config)
        self.assertIn("ADDRESS.ROW", _codes(row))

    def test_width_overflow_fails_before_native_wrap(self) -> None:
        self.config["stream_engine"]["stream0"]["dim_stride"][0] = 1 << 20
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("VALUE.UINT_RANGE", _codes(report))

    def test_missing_b_prime_producer_fails_sa_pingpong(self) -> None:
        config = _load("decode_gemv_local.json")
        b_prime = next(
            name
            for name, stream in config["stream_engine"].items()
            if stream["target"] == "B'"
        )
        del config["stream_engine"][b_prime]
        report = OperatorConfigValidator().validate(config)
        self.assertIn("TOPOLOGY.SA_B_PINGPONG", _codes(report))


class MseRtlSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        self.stream = self.config["stream_engine"]["stream0"]

    def test_memory_index_mode_requires_the_rtl_companion_field(self) -> None:
        self.stream["idx"][1] = None
        missing_source = OperatorConfigValidator().validate(self.config)
        self.assertIn(
            "STREAM.INDEX_SOURCE_REQUIRED", _codes(missing_source)
        )

        self.stream["mem_idx_mode"][1] = "constant"
        missing_constant = OperatorConfigValidator().validate(self.config)
        self.assertIn(
            "STREAM.INDEX_CONSTANT_REQUIRED", _codes(missing_constant)
        )

    def test_inactive_memory_index_fields_fail_closed(self) -> None:
        self.stream["mem_idx_mode"][1] = None
        unused_source = OperatorConfigValidator().validate(self.config)
        self.assertIn(
            "STREAM.UNUSED_INDEX_SOURCE", _codes(unused_source)
        )

        self.stream["mem_idx_mode"][1] = "keep"
        self.stream["mem_idx_constant"][1] = 1
        unused_constant = OperatorConfigValidator().validate(self.config)
        self.assertIn(
            "STREAM.UNUSED_INDEX_CONSTANT", _codes(unused_constant)
        )

    def test_buffer_index_has_only_buffer_and_keep_modes(self) -> None:
        self.stream["buf_idx_mode"][0] = None
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("STREAM.BUFFER_INDEX_MODE", _codes(report))

    def test_legacy_integer_zero_requires_strict_materialization(self) -> None:
        self.stream["mem_idx_mode"][2] = 0
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("VALUE.ENUM", _codes(report))

    def test_enabled_pingpong_requires_terminal_threshold(self) -> None:
        self.stream["ping_pong"] = 1
        self.stream["pingpong_last_index"] = None
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("STREAM.PINGPONG_THRESHOLD", _codes(report))

    def test_stream_requires_its_fixed_physical_buffer_and_threshold(self) -> None:
        del self.config["buffer_config"]["buffer0"]
        missing = OperatorConfigValidator().validate(self.config)
        self.assertIn("BUFFER.MAPPED_INSTANCE_REQUIRED", _codes(missing))

        self.config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        self.config["buffer_config"]["buffer0"]["buf_full_last_index"] = 0
        mismatch = OperatorConfigValidator().validate(self.config)
        self.assertIn("BUFFER.FULL_THRESHOLD_MISMATCH", _codes(mismatch))

    def test_only_read_target_a_has_a_real_pingpong_pair(self) -> None:
        stream = self.config["stream_engine"]["stream1"]
        stream["ping_pong"] = 1
        stream["pingpong_last_index"] = 3
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("BUFFER.PINGPONG_TOPOLOGY", _codes(report))

    def test_buffer5_selector_is_array_source_not_destination(self) -> None:
        self.config["buffer_config"]["buffer5"]["dst_port"] = 0
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("BUFFER.ARRAY_SOURCE", _codes(report))


class LcPeRtlSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        self.pe = self.config["lc_pe_configs"]["PE0"]

    def test_authorized_mul_shape_uses_exact_rtl_operands(self) -> None:
        report = OperatorConfigValidator().validate(self.config)
        self.assertNotIn("LC_PE.OPERAND_DISABLED", _codes(report))
        self.assertNotIn("LC_PE.UNUSED_OPERAND_ENABLED", _codes(report))
        self.assertNotIn("LC_PE.CONSTANT_DOMAIN", _codes(report))

    def test_null_used_operand_and_enabled_ignored_operand_fail_closed(self) -> None:
        self.pe["inport1"] = {
            "src_id": None,
            "mode": None,
            "keep_last_index": None,
            "constant": 0,
        }
        disabled = OperatorConfigValidator().validate(self.config)
        self.assertIn("LC_PE.OPERAND_DISABLED", _codes(disabled))

        self.pe["inport1"] = {
            "src_id": None,
            "mode": "constant",
            "keep_last_index": None,
            "constant": 1,
        }
        self.pe["inport2"] = {
            "src_id": None,
            "mode": "constant",
            "keep_last_index": None,
            "constant": 0,
        }
        enabled = OperatorConfigValidator().validate(self.config)
        self.assertIn("LC_PE.UNUSED_OPERAND_ENABLED", _codes(enabled))

    def test_lc_pe_constant_is_integer_or_exact_raw_bits(self) -> None:
        self.pe["inport1"]["constant"] = 1.0
        floating = OperatorConfigValidator().validate(self.config)
        self.assertIn("LC_PE.CONSTANT_DOMAIN", _codes(floating))

        self.pe["inport1"]["constant"] = 1 << 15
        signed_overflow = OperatorConfigValidator().validate(self.config)
        self.assertIn("VALUE.SIGNED_RANGE", _codes(signed_overflow))

        self.pe["inport1"]["constant"] = "0x8000"
        raw_bits = OperatorConfigValidator().validate(self.config)
        self.assertNotIn("LC_PE.CONSTANT_DOMAIN", _codes(raw_bits))
        self.assertNotIn("VALUE.SIGNED_RANGE", _codes(raw_bits))
        self.assertNotIn("VALUE.UINT_RANGE", _codes(raw_bits))

    def test_source_and_keep_threshold_are_rejected_when_rtl_ignores_them(self) -> None:
        self.pe["inport1"]["src_id"] = "DRAM_LC.LC0"
        self.pe["inport1"]["keep_last_index"] = 3
        report = OperatorConfigValidator().validate(self.config)
        self.assertIn("GRAPH.UNUSED_SOURCE", _codes(report))
        self.assertIn("TAG.UNUSED_KEEP_THRESHOLD", _codes(report))


class GaRtlSemanticsTests(unittest.TestCase):
    def test_all_authorized_references_pass_ga_and_n2n_static_rules(self) -> None:
        authority = json.loads(
            (
                ROOT
                / "contracts/operator_config/operator_config_authority_v1.json"
            ).read_text(encoding="utf-8")
        )
        records = [
            record
            for record in authority["records"]
            if record["configuration_correctness"]
            == "user_authorized_correct_reference"
        ]
        self.assertEqual(len(records), 65)
        failures = []
        for record in records:
            config = json.loads(
                (ROOT / record["path"]).read_text(encoding="utf-8")
            )
            report = OperatorConfigValidator().validate(config)
            codes = sorted(
                code
                for code in _codes(report)
                if code.startswith(("GA.", "N2N."))
            )
            if codes:
                failures.append((record["path"], codes))
        self.assertEqual(failures, [])

    def test_native_ga_references_pass_new_static_rules(self) -> None:
        for name in (
            "prefill_sum_rec_fp32MN_fp32MN.json",
            "maxpool_config_16_16_16_stride2_padding1.json",
            "quant_from_buffer_int32MN_uint8MN.json",
        ):
            report = OperatorConfigValidator().validate(_load(name))
            self.assertFalse(
                any(code.startswith("GA.") for code in _codes(report)),
                (name, sorted(_codes(report))),
            )

    def test_ga_pingpong_companion_and_source_topology_fail_closed(self) -> None:
        config = _load("prefill_sum_rec_fp32MN_fp32MN.json")
        port = config["general_array"]["inport"]["inport0"]
        port["pingpong_en"] = 1
        port["pingpong_last_index"] = None
        missing = OperatorConfigValidator().validate(config)
        self.assertIn("GA.PINGPONG_THRESHOLD_REQUIRED", _codes(missing))

        port["src_id"] = 1
        port["pingpong_last_index"] = 3
        bad_source = OperatorConfigValidator().validate(config)
        self.assertIn("GA.PINGPONG_SOURCE", _codes(bad_source))

    def test_ga_required_operand_and_sfu_column_fail_closed(self) -> None:
        config = _load("prefill_sum_rec_fp32MN_fp32MN.json")
        pe = config["general_array"]["PE_array"]["PE01"]
        pe["inport0"] = {
            "src_id": None,
            "mode": None,
            "keep_last_index": None,
            "constant": 0,
        }
        disabled = OperatorConfigValidator().validate(config)
        self.assertIn("GA.OPERAND_DISABLED", _codes(disabled))

        config = _load("prefill_sum_rec_fp32MN_fp32MN.json")
        config["general_array"]["PE_array"]["PE00"]["alu_opcode"] = "rec"
        placement = OperatorConfigValidator().validate(config)
        self.assertIn("GA.SFU_PLACEMENT", _codes(placement))

    def test_ga_known_semantic_results_are_reported_per_rule(self) -> None:
        int32 = OperatorConfigValidator().validate(
            _load("quant_from_buffer_int32MN_uint8MN.json")
        )
        self.assertEqual(
            int32.facts["ga_int32tofp32"]["classification"],
            "CONTRADICTED",
        )
        maxpool = OperatorConfigValidator().validate(
            _load("maxpool_config_16_16_16_stride2_padding1.json")
        )
        facts = maxpool.facts["ga_int8_max"]
        self.assertEqual(
            facts["rule_results"],
            {
                "CDA-GA-INT8-MAX-NUMERIC-001": "LOCAL_SOURCE_PASS",
                "CDA-GA-INT8-MAX-PIPE-001": "CONTRADICTED",
            },
        )
        self.assertEqual(facts["numeric_classification"], "LOCAL_SOURCE_PASS")
        self.assertEqual(
            facts["numeric_equation"], "unsigned bytewise max(A,C)"
        )
        self.assertEqual(facts["pipeline_classification"], "CONTRADICTED")
        self.assertFalse(facts["pipeline0_accepts_second_item"])
        self.assertNotIn("classification", facts)

    def test_ga_int8_max_pipeline_failure_does_not_become_numeric_failure(
        self,
    ) -> None:
        facts = OperatorConfigValidator().validate(
            _load("maxpool_config_16_16_16_stride2_padding1.json")
        ).facts["ga_int8_max"]
        self.assertFalse(facts["pipeline0_accepts_second_item"])
        self.assertEqual(
            facts["rule_results"]["CDA-GA-INT8-MAX-PIPE-001"],
            "CONTRADICTED",
        )
        self.assertEqual(
            facts["rule_results"]["CDA-GA-INT8-MAX-NUMERIC-001"],
            "LOCAL_SOURCE_PASS",
        )


class N2nRtlSemanticsTests(unittest.TestCase):
    def test_native_ring_reference_records_material_transfer(self) -> None:
        report = OperatorConfigValidator().validate(
            _load("decode_gemv_ring.json")
        )
        self.assertFalse(
            any(code.startswith("N2N.") for code in _codes(report))
        )
        stream = report.facts["n2n"]["streams"]["neighbor_stream0"]
        self.assertEqual(stream["encoded_nse_cnt_size"], 27)
        self.assertEqual(stream["material_transfer_count"], 27)
        self.assertEqual(stream["rows_per_transfer"], [0, 1, 2, 3])
        self.assertFalse(
            report.facts["n2n"]["ping_pong_json_controls_hardware"]
        )

    def test_n2n_hardwired_pingpong_and_physical_pair_fail_closed(self) -> None:
        config = _load("decode_gemv_ring.json")
        config["n2n"]["neighbor_stream0"]["ping_pong"] = 0
        pingpong = OperatorConfigValidator().validate(config)
        self.assertIn("N2N.PINGPONG_HARDWIRED", _codes(pingpong))

        config = _load("decode_gemv_ring.json")
        config["buffer_config"]["buffer0"]["buf_end_row_addr"] = 2
        rows = OperatorConfigValidator().validate(config)
        self.assertIn("N2N.FULL_ROW_REQUIRED", _codes(rows))

        config = _load("decode_gemv_ring.json")
        config["buffer_config"]["buffer1"]["mask"][0] ^= 1
        pair = OperatorConfigValidator().validate(config)
        self.assertIn("N2N.BUFFER_PAIR_MISMATCH", _codes(pair))


class ConfigStateTests(unittest.TestCase):
    def test_first_stage_reuse_is_rejected(self) -> None:
        config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        config["CONFIG"] = "11010000"
        report = OperatorConfigValidator().validate(config, previous_state=ConfigState())
        self.assertIn("CONFIG.REUSE_WITHOUT_STATE", _codes(report))

    def test_update_reuse_disable_then_reuse_tracks_persistent_state(self) -> None:
        initial = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        reuse = copy.deepcopy(initial)
        reuse["CONFIG"] = "11010000"
        disable_ga = copy.deepcopy(initial)
        disable_ga["CONFIG"] = "11001100"
        disable_ga.pop("general_array")
        reuse_after_clear = copy.deepcopy(reuse)
        reports = validate_sequence(
            [
                ("initial", initial),
                ("reuse", reuse),
                ("disable", disable_ga),
                ("reuse_after_clear", reuse_after_clear),
            ]
        )
        self.assertNotIn("CONFIG.REUSE_WITHOUT_STATE", _codes(reports[1]))
        self.assertIsNone(reports[2].next_state.fingerprints["GA"])
        self.assertIn("CONFIG.REUSE_WITHOUT_STATE", _codes(reports[3]))

    def test_reuse_with_changed_body_is_rejected(self) -> None:
        initial = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        drift = copy.deepcopy(initial)
        drift["CONFIG"] = "11010000"
        drift["general_array"]["outport"]["src_id"] ^= 1
        reports = validate_sequence([("initial", initial), ("drift", drift)])
        self.assertIn("CONFIG.REUSE_DRIFT", _codes(reports[1]))

    def test_disabled_subsystem_cannot_hide_ignored_body_or_update(self) -> None:
        config = _load("add_dequant_uint8CWH_uint8CWH_fp32CWH.json")
        config["CONFIG"] = "11001101"
        report = OperatorConfigValidator().validate(config)
        self.assertIn("CONFIG.DISABLED_UPDATE", _codes(report))
        self.assertIn("CONFIG.DISABLED_BODY", _codes(report))


if __name__ == "__main__":
    unittest.main()
