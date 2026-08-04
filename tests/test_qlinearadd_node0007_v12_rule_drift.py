from __future__ import annotations

import unittest

from tools import revalidate_qlinearadd_node0007_v12_rule_drift as audit


class QLinearAddNode0007V12RuleDriftTests(unittest.TestCase):
    def test_content_neutral_revalidation_passes(self) -> None:
        report = audit.revalidate(write_report=False)
        self.assertTrue(
            report["RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"]
        )
        self.assertEqual(report["errors"], [])
        self.assertEqual(
            report["zip_sha256"],
            "87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3",
        )

    def test_new_clock_domain_controls_all_pass(self) -> None:
        report = audit.revalidate(write_report=False)
        controls = report["new_rule_semantic_controls"]
        self.assertTrue(controls["all_passed"])
        self.assertTrue(
            controls["negative_control_old_cross_domain_unique_emitter"][
                "failed_closed"
            ]
        )
        self.assertEqual(
            controls["positive_control_source_stopped"]["snapshots"],
            [
                {"observer_cycle": 4, "qualified_target_edges": 0},
                {"observer_cycle": 8, "qualified_target_edges": 0},
            ],
        )


if __name__ == "__main__":
    unittest.main()
