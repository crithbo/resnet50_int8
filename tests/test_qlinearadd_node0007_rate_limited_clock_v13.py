from __future__ import annotations

import unittest

from tools import validate_qlinearadd_node0007_rate_limited_clock_v13 as validator


class QLinearAddNode0007RateLimitedClockV13Tests(unittest.TestCase):
    def test_final_zip_self_audit_passes(self) -> None:
        report = validator.validate_final_zip(write_report=False)
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"])
        self.assertEqual(report["errors"], [])
        self.assertTrue(
            report["checks"]["clock_record_rate_limited_with_chain"]
        )

    def test_unbounded_and_clock_binding_controls_fail_closed(self) -> None:
        tail, manifest = validator._load_final()
        controls = validator._negative_controls(tail, manifest)
        self.assertEqual(len(controls), 4)
        self.assertTrue(all(item["failed_closed"] for item in controls.values()))


if __name__ == "__main__":
    unittest.main()
