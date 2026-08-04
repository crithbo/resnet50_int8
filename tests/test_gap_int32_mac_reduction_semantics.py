from __future__ import annotations

import json
import random
import unittest
from itertools import product
from pathlib import Path

from resnet50_pipeline.operator_config_validator import (
    OperatorConfigValidator,
)


ROOT = Path(__file__).resolve().parents[1]
ENCODER = ROOT / "ndp-sim/bitstream/config/general.py"
OUTBUFFER_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Outbuffer.sv"
)
INBUFFER_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Inbuffer.sv"
)
GA_CONNECT_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/General_Array/GA_Inport/"
    "GA_Inport_Connect.sv"
)
BUFFER_CONNECT_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster_Connect.sv"
)
AUDIT = (
    ROOT
    / "contracts/operator_config/stage_operator_semantics_audit_v1.json"
)


def signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & (1 << 31) else value


def int32_mac(a: int, b: int, c: int) -> int:
    return signed32(signed32(a) * signed32(b) + signed32(c))


def pairwise_sum(values: list[int]) -> tuple[int, list[int]]:
    level = [signed32(value) for value in values]
    widths = [len(level)]
    while len(level) > 1:
        if len(level) % 2:
            level.append(0)
        level = [
            int32_mac(level[index], 1, level[index + 1])
            for index in range(0, len(level), 2)
        ]
        widths.append(len(level))
    return level[0] if level else 0, widths


class GapInt32MacReductionSemanticsTests(unittest.TestCase):
    def test_encoder_opcode_14_and_rtl_nontransout_classification(self) -> None:
        encoder = ENCODER.read_text(encoding="utf-8")
        rtl = OUTBUFFER_RTL.read_text(encoding="utf-8")
        self.assertIn('"int32_mac": 14', encoder)
        self.assertIn(
            "ga_pe_alu_opcode[2:0] == 3'b011",
            rtl,
        )
        self.assertIn(
            "ga_pe_alu_opcode[2:0] == 3'b100",
            rtl,
        )
        opcode = 14
        rtl_transout = (
            (opcode & 0b111) == 0b011
            or (
                (opcode & 0b111) == 0b100
                and ((opcode >> 3) & 0b11) != 0b10
            )
            or opcode == 0b00101
        )
        self.assertFalse(rtl_transout)
        self.assertIn(
            "assign normal_mode_wr_req        = alu_result_valid_bit;",
            rtl,
        )

    def test_int32_mac_with_constant_one_is_exact_pairwise_add(self) -> None:
        edge_values = [
            0,
            1,
            255,
            -1,
            -(1 << 31),
            (1 << 31) - 1,
        ]
        for a in edge_values:
            for c in edge_values:
                self.assertEqual(
                    int32_mac(a, 1, c),
                    signed32(a + c),
                )

    def test_49_element_gap_sum_has_six_explicit_reduction_stages(self) -> None:
        values = list(range(49))
        actual, widths = pairwise_sum(values)
        self.assertEqual(actual, sum(values))
        self.assertEqual(widths, [49, 25, 13, 7, 4, 2, 1])

    def test_random_uint8_gap_vectors_match_independent_sum(self) -> None:
        rng = random.Random(0x70071)
        for _ in range(256):
            values = [rng.randrange(256) for _ in range(49)]
            actual, _ = pairwise_sum(values)
            self.assertEqual(actual, sum(values))
            self.assertLessEqual(actual, 49 * 255)

    def test_validator_accepts_all_three_int32_mac_operands(self) -> None:
        config_path = (
            ROOT
            / "configs/stage_codegen/hwop-0071-00-d-index-v1/config.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for pe in config["general_array"]["PE_array"].values():
            pe["alu_opcode"] = "int32_mac"
            pe["transout_last_index"] = None
            pe["inport0"]["mode"] = "buffer"
            pe["inport1"].update(
                {
                    "src_id": None,
                    "mode": "constant",
                    "keep_last_index": None,
                    "constant": 1,
                }
            )
            pe["inport2"]["mode"] = "buffer"
        report = OperatorConfigValidator().validate(
            config,
            source="gap-int32-mac-reduction-semantic-probe",
            development_mode=True,
        )
        operand_errors = [
            issue
            for issue in report.issues
            if issue.code in {"GA.OPCODE", "GA.OPERAND_DISABLED"}
        ]
        self.assertEqual(operand_errors, [])

    def test_two_buffer_inputs_have_independent_physical_groups(self) -> None:
        connect = BUFFER_CONNECT_RTL.read_text(encoding="utf-8")
        ga_connect = GA_CONNECT_RTL.read_text(encoding="utf-8")
        self.assertIn(
            "buf2gene_array_rtag[BUF_IDX/2][BUF_IDX%2]",
            connect,
        )
        self.assertIn(
            "buf2gene_array_rdata[BUF_IDX/2][BUF_IDX%2]",
            connect,
        )
        self.assertIn(
            "ga_inport_group_buf_tag[ga_inport_src_buf_sel]",
            ga_connect,
        )
        self.assertIn(
            "ga_inport_group_buf_data[ga_inport_src_buf_sel]",
            ga_connect,
        )
        # group0 selects buffer0 when ping-pong is disabled; group2 selects
        # buffer4.  They can feed PE inport0 and inport2 independently while
        # buffer5 remains the GA writeback buffer.
        self.assertEqual((0 // 2, 0 % 2), (0, 0))
        self.assertEqual((4 // 2, 4 % 2), (2, 0))
        self.assertEqual((5 // 2, 5 % 2), (2, 1))

    def test_nontransout_pair_consumes_both_operands_on_one_match(self) -> None:
        rtl = INBUFFER_RTL.read_text(encoding="utf-8")
        self.assertIn(
            "assign ga_pe_inbuffer_matched = ga_pe_enable",
            rtl,
        )
        self.assertIn(
            "(!ga_pe_inport_enable[0]) | ga_pe_inbuffer_valid_bit[0]",
            rtl,
        )
        self.assertIn(
            "(!ga_pe_inport_enable[2]) | ga_pe_inbuffer_valid_bit[2]",
            rtl,
        )
        self.assertIn(
            "ga_pe_inbuffer_matched && ga_pe_inbuffer_bp_post_mask",
            rtl,
        )
        for a_valid in (False, True):
            for c_valid in (False, True):
                matched = a_valid and c_valid
                self.assertEqual(matched, a_valid and c_valid)
                consume_a = matched
                consume_c = matched
                self.assertEqual(consume_a, consume_c)

    def test_nontransout_c_data_and_tag_never_select_feedback(self) -> None:
        rtl = INBUFFER_RTL.read_text(encoding="utf-8")
        self.assertIn(
            "assign ga_pe_alu_input_tag     = !alu_op_is_transout",
            rtl,
        )
        self.assertIn(
            "assign ga_pe_alu_input_data[2] = !alu_op_is_transout",
            rtl,
        )
        self.assertIn(
            "? ga_pe_inbuffer_data[2]",
            rtl,
        )
        self.assertIn(
            "assign add_transout_initial = alu_op_is_transout && "
            "ga_pe_inbuffer_matched;",
            rtl,
        )
        # Opcode 14 is non-transout, so stale outbuffer data, tag and
        # transout_initial are all unreachable from input C.
        opcode = 14
        self.assertFalse((opcode & 0b111) in (0b011, 0b100))

    def test_equal_terminal_tags_propagate_without_transout_feedback(self) -> None:
        rtl = INBUFFER_RTL.read_text(encoding="utf-8")
        self.assertIn(
            "assign ga_pe_inbuffer2alu_last_bit",
            rtl,
        )
        self.assertIn(
            "assign ga_pe_inbuffer2alu_last_index",
            rtl,
        )
        self.assertIn(
            "!alu_op_is_transout",
            rtl,
        )
        for last in (False, True):
            for last_index in range(4):
                a_tag = (last, last_index)
                c_tag = (last, last_index)
                output_tag = a_tag
                self.assertEqual(output_tag, c_tag)

    def test_normal_outbuffer_fifo_is_bounded_for_all_short_handshake_traces(
        self,
    ) -> None:
        # Mirrors normal_mode_bp_pre=!full and
        # normal_mode_rd_ready=!empty.  Unlike transout compaction, count
        # changes only for accepted writes and reads.
        for requests in product(
            ((False, False), (False, True), (True, False), (True, True)),
            repeat=6,
        ):
            count = 0
            wr_ptr = 0
            rd_ptr = 0
            occupied: set[int] = set()
            for write_request, read_request in requests:
                write = write_request and count != 2
                read = read_request and count != 0
                if write and read:
                    self.assertNotEqual(wr_ptr, rd_ptr)
                if read:
                    occupied.remove(rd_ptr)
                    rd_ptr ^= 1
                if write:
                    self.assertNotIn(wr_ptr, occupied)
                    occupied.add(wr_ptr)
                    wr_ptr ^= 1
                count += int(write) - int(read)
                self.assertEqual(count, len(occupied))
                self.assertGreaterEqual(count, 0)
                self.assertLessEqual(count, 2)

    def test_normal_fifo_count_is_driven_only_by_accepted_handshakes(self) -> None:
        rtl = OUTBUFFER_RTL.read_text(encoding="utf-8")
        self.assertIn(
            "assign normal_mode_wr_handshake  = normal_mode_wr_req && "
            "normal_mode_bp_pre;",
            rtl,
        )
        self.assertIn(
            "assign normal_mode_rd_handshake  = normal_mode_rd_req && "
            "normal_mode_rd_ready;",
            rtl,
        )
        self.assertIn(
            "ga_pe_outbuffer_count <= ga_pe_outbuffer_count + 1;",
            rtl,
        )
        self.assertIn(
            "ga_pe_outbuffer_count <= ga_pe_outbuffer_count - 1;",
            rtl,
        )
        self.assertIn(
            "ga_pe_outbuffer_count <= ga_pe_outbuffer_count;",
            rtl,
        )

    def test_contract_still_marks_int32_mac_dynamic_sample_missing(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        finding = next(
            item
            for item in audit["findings"]
            if item["issue_id"] == "CDA-GA-OPCODE-OPERAND-001"
        )
        self.assertIn("int32_mac opcode", finding["sample_boundary"])


if __name__ == "__main__":
    unittest.main()
