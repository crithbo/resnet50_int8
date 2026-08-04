from __future__ import annotations

import json
import unittest

from tools.qlinearadd_first_request_canonical_decision import (
    CanonicalDecisionError,
    decide,
    load_unique_record,
)


def base_line(cycle: int, req: int = 0) -> str:
    return (
        f"{cycle} | HEARTBEAT | slice=0 active_cycles={cycle} "
        f"gexec=1 gconfig=0 req={req} rdata=0 wdata=0 "
        "buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0"
    )


def chain_line(
    cycle: int,
    *,
    slice_start: int = 1,
    lc_hs: str = "0,0,0,0,0",
    mse0_hs: str = "0,0,0",
    queue_wr: int = 0,
    ag_hs: int = 0,
    req_enq: int = 0,
) -> str:
    return (
        f"{cycle} | FIRST_REQUEST_CHAIN | slice=0 active_cycles={cycle} "
        f"slice_start={slice_start} lc_enable=0x1f lc_valid=0x0 "
        f"lc_ready=0x1f lc_hs={lc_hs} "
        f"mse0_in_valid=0x0 mse0_in_ready=0x7 mse0_in_hs={mse0_hs} "
        f"mse0_match=0 mse0_empty=1 mse0_full=0 mse0_queue_wr={queue_wr} "
        f"mse0_ag_valid=0 mse0_ag_ready=1 mse0_ag_hs={ag_hs} "
        "mse0_req_enq_valid=0 mse0_req_enq_ready=1 "
        f"mse0_req_enq={req_enq} "
        "mse4_in_valid=0x0 mse4_in_ready=0x7 mse4_in_hs=0,0,0 "
        "mse4_match=0 mse4_empty=1 mse4_full=0 mse4_queue_wr=0"
    )


def payload(*lines: str) -> bytes:
    return (
        "# Native NDP return observer v4 enabled\n"
        "0 | EXEC_START | slice=0 active_cycles=0 gexec=1 gconfig=0 "
        "req=0 rdata=0 wdata=0 buf4_wr=0 buf4_rd=0 "
        "buf5_wr=0 buf5_rd=0\n"
        + "\n".join(lines)
        + "\n"
    ).encode()


class FirstRequestCanonicalDecisionTests(unittest.TestCase):
    def test_flat_outer_lc_boundary_is_canonical(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10),
                base_line(110),
                chain_line(110),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(
            record["decision"],
            "LONG_RUNNING_HANG_AT_"
            "SLICE_START_RUN_TO_PHYSICAL_LC4_OUTER_HANDSHAKE",
        )
        self.assertEqual(
            record["boundary"],
            "SLICE_START_RUN_TO_PHYSICAL_LC4_OUTER_HANDSHAKE",
        )
        load_unique_record(json.dumps(record).encode())

    def test_flat_selected_mse_input_boundary_is_canonical(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10, lc_hs="1,1,1,1,1"),
                base_line(110),
                chain_line(110, lc_hs="1,1,1,1,1"),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(
            record["boundary"],
            "LEAF_LC_LCPE_TO_SELECTED_MSE0_INDEX_INPUT_HANDSHAKE",
        )

    def test_request_acceptance_wins_over_partial_chain(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10),
                base_line(20, req=1),
                chain_line(20),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(
            record["decision"],
            "FIRST_REQUEST_ACCEPTED_CONTINUE_STANDARD_PROGRESS",
        )

    def test_monotonic_internal_windows_report_still_progressing(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10, lc_hs="0,1,0,0,0"),
                base_line(20),
                chain_line(20, lc_hs="1,2,1,0,0"),
                base_line(30),
                chain_line(30, lc_hs="2,3,2,1,1"),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(record["decision"], "STILL_PROGRESSING_NOT_FINISHED")

    def test_chain_counter_decrease_fails_diagnostic(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10, lc_hs="1,2,1,0,0"),
                base_line(20),
                chain_line(20, lc_hs="1,1,1,0,0"),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(
            record["decision"], "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        )

    def test_missing_chain_is_fail_closed(self) -> None:
        record = decide(
            payload(base_line(10), base_line(110)),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        self.assertEqual(
            record["decision"], "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        )

    def test_conflicting_or_incomplete_record_is_rejected(self) -> None:
        record = decide(
            payload(
                base_line(10),
                chain_line(10),
                base_line(110),
                chain_line(110),
            ),
            stall_window_cycles=100,
            minimum_monotonic_windows=2,
        )
        with self.assertRaises(CanonicalDecisionError):
            load_unique_record(
                (json.dumps(record) + "\n" + json.dumps(record)).encode()
            )
        record.pop("reason")
        with self.assertRaises(CanonicalDecisionError):
            load_unique_record(json.dumps(record).encode())


if __name__ == "__main__":
    unittest.main()
