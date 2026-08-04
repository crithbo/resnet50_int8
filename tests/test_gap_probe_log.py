from __future__ import annotations

import unittest
from pathlib import Path

from tools.analyze_gap_probe_log import analyze_events


ROOT = Path(__file__).resolve().parents[1]


def event(time: int, kind: str, ordinal: int, **fields: str) -> dict:
    return {
        "time": time,
        "kind": kind,
        "ordinal": ordinal,
        "fields": fields,
    }


class GapProbeLogTests(unittest.TestCase):
    def test_tb_includes_read_only_deep_observer(self) -> None:
        tb = (ROOT / "NDP_copy01" / "tb_NDP_Top_new_phy.sv").read_text(
            encoding="utf-8"
        )
        observer = (
            ROOT / "NDP_copy01" / "native_return_observer.svh"
        ).read_text(encoding="utf-8")

        self.assertIn('`include "native_return_observer.svh"', tb)
        self.assertIn('$test$plusargs("RETURN_OBS_DEEP")', observer)
        for marker in (
            "DEEP_RD_ADDR_ENQUEUE",
            "DEEP_RD_REQ_HANDSHAKE",
            "DEEP_RD_META",
            "DEEP_RD_CONSUME",
            "DEEP_MSE0_TO_BUFFER0",
            "DEEP_GA",
            "DEEP_MSE4_INDEX",
            "SG_GA_INPUT",
            "SG_GA_OUTPUT",
            "SG_MSE4_REQ",
            "SG_MSE4_WDATA",
            "GA_ACCUM_STATE",
        ):
            self.assertIn(marker, observer)
        self.assertIn('$test$plusargs("RETURN_OBS_ACCUM_STATE")', observer)
        self.assertIn('"RETURN_OBS_FILE=%s"', observer)

    def test_cross_clock_delayed_valid_snapshot_is_not_called_replay(self) -> None:
        events = [
            event(10, "DEEP_RD_ADDR_ENQUEUE", 0, ch="0", addr_in="0x0"),
            event(
                11,
                "DEEP_RD_REQ_HANDSHAKE",
                1,
                ch="0",
                addr="0x0",
                vld="0x1",
                vld_d="0x0",
                ready="0x1",
            ),
            event(
                12,
                "DEEP_RD_ADDR_ENQUEUE",
                2,
                ch="0",
                addr_in="0x1",
            ),
            event(
                12,
                "DEEP_RD_REQ_HANDSHAKE",
                3,
                ch="0",
                addr="0x0",
                vld="0x0",
                vld_d="0x1",
                ready="0x1",
            ),
        ]

        report = analyze_events(events)

        self.assertEqual(
            report["classification"],
            "cross_clock_request_snapshot_requires_correlation",
        )
        transport = report["mse0_address_transport"]
        self.assertEqual(transport["orphan_request_count"], 1)
        self.assertEqual(
            transport["request_while_only_delayed_valid_count"], 1
        )
        self.assertFalse(transport["standalone_replay_claim_allowed"])

    def test_bad_address_input_is_classified_before_channel_transport(self) -> None:
        events = [
            event(10, "DEEP_RD_ADDR_ENQUEUE", 0, ch="0", addr_in="0x0"),
            event(11, "DEEP_RD_ADDR_ENQUEUE", 1, ch="1", addr_in="0x2"),
            event(
                12,
                "DEEP_RD_REQ_HANDSHAKE",
                2,
                ch="0",
                addr="0x0",
                vld="0x1",
                vld_d="0x0",
                ready="0x1",
            ),
            event(
                13,
                "DEEP_RD_REQ_HANDSHAKE",
                3,
                ch="1",
                addr="0x2",
                vld="0x2",
                vld_d="0x0",
                ready="0x2",
            ),
        ]

        report = analyze_events(events)

        self.assertEqual(
            report["classification"],
            "mse0_address_generation_input_mismatch",
        )
        self.assertEqual(
            report["mse0_address_transport"][
                "enqueue_input_mismatch_count_in_probe_window"
            ],
            1,
        )

    def test_constant_mse4_index_path_is_reported(self) -> None:
        events = [
            event(
                20,
                "DEEP_MSE4_INDEX",
                0,
                lc0="0x0",
                lc2="0x0",
                pe1="0x0",
                idx="0x0",
                addr_bias="0",
            ),
            event(
                21,
                "DEEP_MSE4_INDEX",
                1,
                lc0="0x1",
                lc2="0x0",
                pe1="0x0",
                idx="0x0",
                addr_bias="0",
            ),
        ]

        report = analyze_events(events)

        self.assertTrue(
            report["mse4_index_path"][
                "lc0_changes_but_lc2_pe1_index_bias_remain_zero"
            ]
        )

    def test_invalid_outbuffer_slot_reused_as_input_c_is_decisive(self) -> None:
        events = [
            event(
                700318,
                "GA_ACCUM_STATE",
                0,
                n="401",
                pe="00",
                input2="0x00012ab3",
                matched="1",
                trans_init="0x3",
                calc="0",
                ob_valid="0",
                ob_count="0",
                rd_ptr="1",
                ob_tag0="0x0",
                ob_tag1="0x0",
                ob_data0="0x00000000",
                ob_data1="0x00012ab3",
            )
        ]

        report = analyze_events(events)

        self.assertEqual(
            report["classification"],
            "ga_int32_sum_invalid_outbuffer_slot_reused_as_c",
        )
        self.assertEqual(
            report["ga_accumulator_state"]["invalid_slot_c_reuse_count"],
            1,
        )

    def test_count_underflow_precedes_invalid_slot_reuse(self) -> None:
        events = [
            event(
                700313,
                "GA_ACCUM_STATE",
                0,
                n="225",
                pe="00",
                input2="0x000000a6",
                matched="0",
                trans_init="0x3",
                calc="1",
                calc_v0="1",
                calc_v2="1",
                ob_valid="1",
                ob_count="1",
                rd_ptr="1",
                ob_wr="0",
                ob_tag0="0x0",
                ob_tag1="0x21",
                ob_data0="0x000000a4",
                ob_data1="0x000000a6",
            ),
            event(
                700316,
                "GA_ACCUM_STATE",
                1,
                n="233",
                pe="00",
                input2="0x00000000",
                matched="1",
                trans_init="0x0",
                calc="0",
                calc_v0="0",
                calc_v2="0",
                ob_valid="1",
                ob_count="3",
                rd_ptr="0",
                ob_wr="0",
                ob_tag0="0x21",
                ob_tag1="0x0",
                ob_data0="0x0000014a",
                ob_data1="0x000000a6",
            ),
            event(
                700318,
                "GA_ACCUM_STATE",
                2,
                n="241",
                pe="00",
                input2="0x000000a6",
                matched="1",
                trans_init="0x2",
                calc="0",
                calc_v0="0",
                calc_v2="0",
                ob_valid="0",
                ob_count="2",
                rd_ptr="1",
                ob_wr="1",
                ob_tag0="0x0",
                ob_tag1="0x0",
                ob_data0="0x0000014a",
                ob_data1="0x000000a6",
            ),
        ]

        report = analyze_events(events)

        self.assertEqual(
            report["classification"],
            "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse",
        )
        state = report["ga_accumulator_state"]
        self.assertEqual(state["underflow_transition_count"], 1)
        self.assertEqual(state["illegal_outbuffer_count_event_count"], 1)


if __name__ == "__main__":
    unittest.main()
