from __future__ import annotations

import json
import unittest

from tools.qlinearadd_progress_canonical_decision import (
    CanonicalDecisionError,
    decide,
    load_unique_record,
)


MARKER = "# Native NDP return observer v4\n"


def heartbeat(
    time: int,
    cycles: int,
    *,
    gexec: int = 1,
    req: int = 0,
    rdata: int = 0,
    wdata: int = 0,
    raw_level: int = 0,
) -> str:
    return (
        f"{time} | HEARTBEAT | slice=0 active_cycles={cycles} "
        f"gexec={gexec} gconfig=0 req={req} rdata={rdata} wdata={wdata} "
        f"buf4_wr={raw_level} buf4_rd=0 buf5_wr=0 buf5_rd=0\n"
    )


class QLinearAddProgressCanonicalDecisionTests(unittest.TestCase):
    def test_two_qualified_windows_publish_still_progressing(self) -> None:
        payload = (
            MARKER
            + heartbeat(10, 10, req=1)
            + heartbeat(20, 20, req=2)
            + heartbeat(30, 30, req=3)
        ).encode()
        record = decide(
            payload, stall_window_cycles=100, minimum_monotonic_windows=2
        )
        self.assertEqual(record["decision"], "STILL_PROGRESSING_NOT_FINISHED")
        self.assertEqual(record["boundary"], "MSE_REQUEST_ACCEPTED")
        self.assertEqual(len(record["windows"]), 2)

    def test_sustained_high_raw_level_is_not_qualified_progress(self) -> None:
        payload = (
            MARKER
            + heartbeat(10, 10, raw_level=1)
            + heartbeat(20, 20, raw_level=1)
            + heartbeat(30, 30, raw_level=1)
        ).encode()
        record = decide(
            payload, stall_window_cycles=100, minimum_monotonic_windows=2
        )
        self.assertEqual(record["decision"], "INSUFFICIENT_PROGRESS_EVIDENCE")
        self.assertEqual(
            record["counter_snapshot"]["qualified"],
            {"gexec": 1, "req": 0, "rdata": 0, "wdata": 0},
        )
        self.assertEqual(
            record["counter_snapshot"]["max_consecutive_advancing_windows"], 0
        )

    def test_summary_only_append_cannot_override_canonical_json(self) -> None:
        payload = (
            MARKER
            + heartbeat(10, 10, req=1)
            + heartbeat(20, 20, req=2)
            + heartbeat(30, 30, req=3)
        ).encode()
        record = decide(
            payload, stall_window_cycles=100, minimum_monotonic_windows=2
        )
        encoded = json.dumps(record).encode() + b"\nSUMMARY_ONLY decision=HANG\n"
        with self.assertRaises(CanonicalDecisionError):
            load_unique_record(encoded)

    def test_conflicting_dual_decisions_fail_closed(self) -> None:
        payload = (
            MARKER
            + heartbeat(10, 10, req=1)
            + heartbeat(20, 20, req=2)
            + heartbeat(30, 30, req=3)
        ).encode()
        first = decide(
            payload, stall_window_cycles=100, minimum_monotonic_windows=2
        )
        second = dict(first)
        second["decision"] = "LONG_RUNNING_HANG_AT_MSE_REQUEST_ACCEPTED"
        with self.assertRaises(CanonicalDecisionError):
            load_unique_record(json.dumps([first, second]).encode())

    def test_missing_reason_or_boundary_fails_closed(self) -> None:
        payload = (
            MARKER
            + heartbeat(10, 10, req=1)
            + heartbeat(20, 20, req=2)
            + heartbeat(30, 30, req=3)
        ).encode()
        record = decide(
            payload, stall_window_cycles=100, minimum_monotonic_windows=2
        )
        for missing in ("reason", "boundary"):
            damaged = dict(record)
            damaged.pop(missing)
            with self.subTest(missing=missing):
                with self.assertRaises(CanonicalDecisionError):
                    load_unique_record(json.dumps(damaged).encode())


if __name__ == "__main__":
    unittest.main()
