from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.gap_int32_mac_bypass import (
    CGRA_REPORT_PATH,
    CONTRACT_PATH,
    FINAL_LINES_PER_SLICE,
    LOGICAL_WIDTHS,
    PHYSICAL_WIDTHS,
    W3_EXPECTED_PATH,
    W3_INPUT_PATH,
    build_contract,
    load_locked_cgra_sum,
    pairwise_int32_tree,
    relative_regions,
    stage_output_records,
    stage_pair_records,
    validate_contract,
    validate_memory_plan,
)


ROOT = Path(__file__).resolve().parents[1]
SUM = load_locked_cgra_sum(ROOT)


class GapInt32MacStageMemoryTests(unittest.TestCase):
    def test_six_real_jsons_preserve_the_proven_dual_stream_route(self) -> None:
        for stage_index in range(1, 7):
            config_path = (
                ROOT
                / "configs/gap_int32_mac_bypass_v1"
                / f"stage-{stage_index}"
                / "config.json"
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            pe_array = config["general_array"]["PE_array"]
            self.assertEqual(len(pe_array), 8)
            for pe in pe_array.values():
                self.assertEqual(pe["alu_opcode"], "int32_mac")
                self.assertEqual(pe["inport0"]["mode"], "buffer")
                self.assertEqual(pe["inport1"]["mode"], "constant")
                self.assertEqual(pe["inport1"]["constant"], 1)
                self.assertEqual(pe["inport2"]["mode"], "buffer")
                self.assertIsNone(pe["transout_last_index"])
            streams = config["stream_engine"]
            self.assertEqual(
                [(item["mode"], item["target"]) for item in streams.values()],
                [("read", "A"), ("read", "C"), ("write", "D")],
            )
            self.assertTrue(
                all(item["ping_pong"] == 0 for item in streams.values())
            )
            self.assertTrue(
                all(
                    item["tailing_enable"] == [0, 0, 0]
                    for item in streams.values()
                )
            )
            self.assertTrue(
                all(
                    int(item["base_addr"], 16) % 16 == 0
                    for item in streams.values()
                )
            )
            inports = config["general_array"]["inport"]
            self.assertEqual(inports["inport0"]["pingpong_en"], 0)
            self.assertEqual(inports["inport2"]["pingpong_en"], 0)
            if stage_index == 1:
                self.assertEqual(
                    inports["inport0"]["uint8toint32"], "true"
                )
                self.assertEqual(
                    inports["inport2"]["uint8toint32"], "true"
                )
            else:
                self.assertEqual(
                    inports["inport0"]["uint8toint32"], "false"
                )
                self.assertEqual(
                    inports["inport2"]["uint8toint32"], "false"
                )

    def test_stock_encoder_and_rtl_expose_two_independent_mse_routes(self) -> None:
        encoder = (
            ROOT / "ndp-sim/bitstream/config/stream.py"
        ).read_text(encoding="utf-8")
        connect = (
            ROOT
            / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
            "Buffer_Manager_Cluster_Connect.sv"
        ).read_text(encoding="utf-8")
        memory_ag = (
            ROOT
            / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
            "Memory_Stream_Engine/Memory_RD_Stream_Engine/"
            "RD_Memory_AG.sv"
        ).read_text(encoding="utf-8")
        memory_req = (
            ROOT
            / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
            "Memory_Req_Manager.sv"
        ).read_text(encoding="utf-8")
        buffer_rtl = (
            ROOT
            / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
            "Buffer.sv"
        ).read_text(encoding="utf-8")
        self.assertIn("'A': 0", encoder)
        self.assertIn("'C': 3", encoder)
        self.assertIn('resource = f"READ_STREAM{physical_read_idx}"', encoder)
        self.assertIn(
            "self.values[\"total_size\"] = dim2",
            encoder,
        )
        # Stock connect maps buffer0 from MSE0.  For BUF_IDX=4, the
        # BUF_IDX-1 expression maps buffer4 from MSE3.
        self.assertIn(
            "se2buf_mem_wreq_valid[BUF_IDX/2]",
            connect,
        )
        self.assertIn(
            "se2buf_mem_wreq_valid[BUF_IDX-1]",
            connect,
        )
        # Eight-byte transactions are split/masked by the stock MSE and
        # deposit one selected byte into each buffer bank.  Four byte slots
        # must all become valid before a normal array read can be accepted.
        self.assertIn(
            "transfer_final_size = transfer_try_size_overflow",
            memory_ag,
        )
        self.assertIn(
            "transfer_valid_mask_temp",
            memory_ag,
        )
        self.assertIn(
            "mrm2buf_wdata[bank_idx][se2buf_req_bank_offest",
            memory_req,
        )
        self.assertIn(
            "buf2arm_rreq_bank_ready[BANK_IDX] = &valid_buf",
            buffer_rtl,
        )
        col_bases = [0, 1, 2, 3]
        spatial_strides = list(range(0, 32, 4))
        slots_by_bank = {bank: [] for bank in range(8)}
        for col_base in col_bases:
            for stride in spatial_strides:
                position = (col_base + stride) & 0x1F
                slots_by_bank[position >> 2].append(position & 0x3)
        self.assertTrue(
            all(slots == [0, 1, 2, 3] for slots in slots_by_bank.values())
        )

    def test_stage1_two_mse_streams_pair_even_odd_occurrences(self) -> None:
        pairs = stage_pair_records(1)
        self.assertEqual(len(pairs), 256 * 32)
        for item in pairs:
            self.assertEqual(item["left_index"], 2 * item["output_index"])
            self.assertEqual(item["right_index"], 2 * item["output_index"] + 1)
            self.assertEqual(
                item["c_relative_address"] - item["a_relative_address"],
                8,
            )
            self.assertEqual(item["transaction_bytes"], 8)
            self.assertEqual(item["a_tag"], item["c_tag"])
            self.assertEqual(
                item["buffer_columns"],
                [
                    item["buffer_byte_slot"] + lane * 4
                    for lane in range(8)
                ],
            )
        first_tail = next(
            item
            for item in pairs
            if item["c8_block"] == 0 and item["output_index"] == 24
        )
        self.assertFalse(first_tail["a_padding_substitute_zero"])
        self.assertTrue(first_tail["c_padding_substitute_zero"])
        all_tail = [
            item
            for item in pairs
            if item["c8_block"] == 0 and item["output_index"] >= 25
        ]
        self.assertTrue(
            all(
                item["a_padding_substitute_zero"]
                and item["c_padding_substitute_zero"]
                for item in all_tail
            )
        )

    def test_scratch_reads_cover_every_previous_transaction_once(self) -> None:
        regions = relative_regions()
        for stage_index in range(2, 7):
            previous = regions[stage_index - 1]
            pairs = stage_pair_records(stage_index)
            for block in (0, 1, 255):
                addresses = sorted(
                    address
                    for item in pairs
                    if item["c8_block"] == block
                    for address in (
                        item["a_relative_address"],
                        item["c_relative_address"],
                    )
                )
                expected = [
                    previous.base
                    + (block * previous.physical_width + index) * 32
                    for index in range(previous.physical_width)
                ]
                self.assertEqual(addresses, expected)

    def test_regions_and_writebacks_are_aligned_nonoverlapping_contiguous(
        self,
    ) -> None:
        plan = validate_memory_plan()
        regions = relative_regions()
        self.assertEqual(regions[0].size, 100480)
        self.assertEqual(plan["input_guard_bytes_per_slice"], 128)
        for left, right in zip(regions, regions[1:]):
            self.assertLessEqual(left.end, right.base)
        for stage_index in range(1, 7):
            writes = stage_output_records(stage_index)
            self.assertEqual(
                [item["relative_address"] for item in writes],
                list(range(regions[stage_index].base, regions[stage_index].end, 32)),
            )
            self.assertTrue(
                all(item["relative_address"] % 32 == 0 for item in writes)
            )
        self.assertEqual(
            plan["final_d"]["unique_128bit_lines_per_slice"],
            FINAL_LINES_PER_SLICE,
        )

    def test_each_stage_has_one_terminal_and_matching_a_c_tags(self) -> None:
        for stage_index in range(1, 7):
            pairs = stage_pair_records(stage_index)
            self.assertTrue(
                all(item["a_tag"] == item["c_tag"] for item in pairs)
            )
            terminals = [
                item for item in pairs if item["a_tag"] == [1, 0]
            ]
            local_ends = [
                item for item in pairs if item["a_tag"] == [1, 1]
            ]
            self.assertEqual(len(terminals), 1)
            self.assertEqual(len(local_ends), 255)
            self.assertEqual(terminals[0]["c8_block"], 255)
            self.assertEqual(
                terminals[0]["output_index"],
                PHYSICAL_WIDTHS[stage_index] - 1,
            )

    def test_padded_physical_tree_matches_logical_pairwise_sum(self) -> None:
        vectors = [
            list(range(49)),
            [0] * 49,
            [255] * 49,
            [index % 256 for index in range(49)],
        ]
        for values in vectors:
            actual, widths, physical_levels = pairwise_int32_tree(values)
            self.assertEqual(widths, list(LOGICAL_WIDTHS))
            self.assertEqual(
                [len(level) for level in physical_levels],
                list(PHYSICAL_WIDTHS),
            )
            self.assertEqual(actual, sum(values))
            for level, logical_width in zip(physical_levels, LOGICAL_WIDTHS):
                self.assertTrue(
                    all(value == 0 for value in level[logical_width:])
                )

    def test_cgra_sum_explicit_tree_and_w3_expected_match(self) -> None:
        tensor = np.load(ROOT / W3_INPUT_PATH, allow_pickle=False)
        expected = np.load(ROOT / W3_EXPECTED_PATH, allow_pickle=False).reshape(-1)
        matrix = tensor.reshape(16 * 2048, 49).astype(np.int32)
        operator = SUM("int32", "rowmajor", 16 * 2048, 49, axis=1)
        cgra = operator.SUM(matrix).astype(np.int32)
        level = matrix
        widths = [level.shape[1]]
        while level.shape[1] > 1:
            if level.shape[1] % 2:
                level = np.pad(level, ((0, 0), (0, 1)))
            level = (level[:, 0::2] + level[:, 1::2]).astype(np.int32)
            widths.append(level.shape[1])
        self.assertEqual(widths, list(LOGICAL_WIDTHS))
        np.testing.assert_array_equal(cgra, level[:, 0])
        np.testing.assert_array_equal(cgra, expected)

    def test_generated_report_and_contract_are_current_and_fail_closed(
        self,
    ) -> None:
        report = json.loads((ROOT / CGRA_REPORT_PATH).read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass_local_semantic_reference_only")
        self.assertTrue(
            report["comparison"][
                "cgra_equal_explicit_int32_mac_tree"
            ]
        )
        contract = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
        validate_contract(contract, ROOT)
        self.assertFalse(contract["candidate_release"])
        self.assertTrue(contract["server_package_allowed"])
        self.assertFalse(contract["functional_rtl_modified"])
        self.assertEqual(contract, build_contract(ROOT))
        tampered = json.loads(json.dumps(contract))
        tampered["candidate_release"] = True
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_contract(tampered, ROOT)

    def test_contract_keeps_dynamic_and_real_artifact_claims_open(self) -> None:
        contract = build_contract(ROOT)
        blocker_ids = {
            item["id"]: item["status"] for item in contract["blockers"]
        }
        self.assertEqual(
            blocker_ids["B_GAP_GA_ACCUM_STATE"],
            "still_open_for_original_int32_sum_route",
        )
        self.assertEqual(
            blocker_ids["B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM"],
            "open",
        )
        self.assertEqual(
            blocker_ids["B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS"],
            "closed_local_e2",
        )
        self.assertEqual(
            contract["local_e2"]["status"],
            "pass_materialized_json_bitstream_execplan_and_golden",
        )
        self.assertTrue(contract["server_package_allowed"])
        self.assertFalse(contract["local_e2"]["dynamic_rtl_execution"])
        for stage in contract["memory_plan"]["stages"]:
            provenance = stage["candidate_stage_artifacts"]
            self.assertEqual(
                provenance["status"],
                "materialized_and_bound_by_local_e2",
            )


if __name__ == "__main__":
    unittest.main()
