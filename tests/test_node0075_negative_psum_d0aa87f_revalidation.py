from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.validate_node0075_negative_psum_d0aa87f_revalidation import (
    BLOCKER,
    fails_closed,
    negative_controls,
    validate,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0075_negative_psum_d0aa87f_revalidation_v1.json"
)


class Node0075D0aa87fRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_current_disk_passes_fail_closed_validation(self) -> None:
        report = validate(ROOT, self.contract)
        self.assertEqual(report["status"], "PASS_FAIL_CLOSED")
        self.assertTrue(all(report["checks"].values()))

    def test_directed_exact_cancellation_and_adjacent_controls(self) -> None:
        cases = self.contract["directed_rtl_gate"]["cases"]
        exact = cases["neg19_plus19"]
        self.assertFalse(exact["pass"])
        self.assertEqual(exact["magnitude_bits"], "0x00000013")
        self.assertEqual(exact["csa_raw_bits"], "0x00000000")
        self.assertEqual(exact["int_result_sign"], "1")
        self.assertEqual(exact["observed_bits"], "0x80000000")
        self.assertEqual(exact["expected_bits"], "0x00000000")
        for label in (
            "neg20_plus19",
            "neg18_plus19",
            "zero_plus19",
            "pos7_plus19",
        ):
            self.assertTrue(cases[label]["pass"], label)

    def test_complete_recurrence_retains_reachable_blocker(self) -> None:
        scan = self.contract["full_frozen_recurrence_gate"]
        self.assertEqual(scan["enumerated_occurrences"], 8_192_000)
        self.assertEqual(scan["negative_psum_occurrences"], 4_343_952)
        self.assertEqual(scan["negative_to_exact_zero"], 272)
        self.assertEqual(scan["formal_accumulator_mismatch_count"], 0)
        first = scan["first_stream_order_hit"]
        self.assertEqual((first["m"], first["n"], first["k_group"]), (0, 65, 3))
        self.assertEqual(first["psum_in_s32"], -19)
        self.assertEqual(first["dot4_s32"], 19)
        self.assertEqual(
            self.contract["blocker_delta"]["retained_exact"], [BLOCKER]
        )

    def test_fail_fast_prevents_materializer_and_package_claims(self) -> None:
        traffic = self.contract["materializer_and_traffic"]
        self.assertEqual(traffic["actual_materialized_reload_passes"], 0)
        self.assertEqual(traffic["actual_accepted_32byte_reads"], 0)
        self.assertEqual(traffic["actual_accepted_a_traffic_bytes"], 0)
        self.assertEqual(traffic["actual_unique_consumer_accepted_bytes"], 0)
        self.assertFalse(any(self.contract["outputs"].values()))
        self.assertEqual(self.contract["package_release"], "NONE")
        self.assertFalse(self.contract["candidate_release"])

    def test_negative_controls_fail_closed(self) -> None:
        controls = negative_controls(ROOT, self.contract)
        self.assertTrue(all(controls.values()), controls)
        mutation = copy.deepcopy(self.contract)
        mutation["full_frozen_recurrence_gate"]["negative_to_exact_zero"] = 0
        self.assertTrue(fails_closed(ROOT, mutation))


if __name__ == "__main__":
    unittest.main()
