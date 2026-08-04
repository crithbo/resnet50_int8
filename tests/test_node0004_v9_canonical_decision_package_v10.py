from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.node0004_hang_localization_runtime_v10 import (
    CANONICAL_PREFIX,
    analyze,
    parse_canonical_records,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v10_hangloc_canonical"
)


def record(
    *,
    decision: str = (
        "LONG_RUNNING_HANG_AT_"
        "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS"
    ),
    reason: str = "STALL_WINDOW_EXCEEDED",
    boundary: str = "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS",
) -> str:
    return (
        f"100 | {CANONICAL_PREFIX.strip('| ')} | "
        "schema=node0004_hang_diag version=1 "
        f"decision={decision} reason={reason} boundary={boundary} "
        "window_first=1 window_last=4 window_cycles=262144 "
        "qualified_progress=136 qualified_delta=0 "
        "req0=32 req1=32 req3=28 rdata0=12 rdata1=12 rdata3=16 "
        "d_req=4 d_wdata=0 content_digest=QIOV1_136_0_4"
    )


class Node0004CanonicalDecisionV10Test(unittest.TestCase):
    def test_complete_unique_record_passes(self) -> None:
        result = parse_canonical_records([record()])
        self.assertTrue(result["valid"])
        self.assertEqual(result["candidate_count"], 1)

    def test_summary_only_append_fails_closed(self) -> None:
        result = parse_canonical_records(
            [record(), f"101 {CANONICAL_PREFIX} summary=only"]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["candidate_count"], 2)

    def test_conflicting_double_decision_fails_closed(self) -> None:
        result = parse_canonical_records(
            [
                record(),
                record(
                    decision="STILL_PROGRESSING",
                    reason="MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING",
                ),
            ]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["candidate_count"], 2)

    def test_missing_reason_or_boundary_fails_closed(self) -> None:
        missing_reason = record().replace(
            "reason=STALL_WINDOW_EXCEEDED ", ""
        )
        missing_boundary = record().replace(
            "boundary=BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS ",
            "",
        )
        self.assertFalse(parse_canonical_records([missing_reason])["valid"])
        self.assertFalse(parse_canonical_records([missing_boundary])["valid"])

    def test_ambiguous_record_sets_required_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "evidence"
            run = root / "run/c0"
            evidence.mkdir()
            run.mkdir(parents=True)
            (evidence / "compile_exit_status.txt").write_text("0\n")
            (evidence / "run_exit_status.txt").write_text("1\n")
            (run / "return_observer.log").write_text(
                record() + "\n" + f"101 {CANONICAL_PREFIX} summary=only\n",
                encoding="utf-8",
            )
            result = analyze(PACKAGE, evidence, root / "run")
            self.assertEqual(
                result["status"],
                "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS",
            )

    def test_persistent_level_is_not_n_transactions(self) -> None:
        levels = [False] + [True] * 32
        rising_edges = sum(
            current and not previous
            for previous, current in zip(levels, levels[1:])
        )
        self.assertEqual(rising_edges, 1)
        if PACKAGE.is_dir():
            observer = (
                PACKAGE / "tb_probe/native_return_observer.svh"
            ).read_text(encoding="utf-8")
            progress = observer.rsplit(
                "return_hang_diag_current_progress =", 1
            )[1].split(";", 1)[0]
            self.assertNotIn("return_obs_buf45_", progress)
            self.assertIn("!return_hang_diag_buf5_rd_d", observer)

    def test_final_observer_has_one_canonical_prefix(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v10 package is not built")
        observer = (
            PACKAGE / "tb_probe/native_return_observer.svh"
        ).read_text(encoding="utf-8")
        self.assertEqual(observer.count("CANONICAL_DIAG_DECISION_V1"), 1)
        self.assertIn('return_obs_write_summary("DIAG_SUMMARY")', observer)
        self.assertNotIn(
            'return_obs_write_summary("DIAG_DECISION")', observer
        )


if __name__ == "__main__":
    unittest.main()
