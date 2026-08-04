from __future__ import annotations

import unittest

from tools import validate_qlinearadd_node0007_backend_progress_v17_server_package as audit


class QLinearAddBackendProgressV17Test(unittest.TestCase):
    def test_final_zip_rule_self_audit(self) -> None:
        report = audit.validate_final_zip(write_report=False)
        self.assertTrue(report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"], report["errors"])
        self.assertEqual(report["error_count"], 0)

    def test_all_heartbeat_negative_controls_fail_closed(self) -> None:
        report = audit.validate_final_zip(write_report=False)
        self.assertTrue(report["all_required_negative_controls_fail_closed"])
        self.assertTrue(
            all(
                control["failed_closed"]
                for control in report["negative_controls"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
