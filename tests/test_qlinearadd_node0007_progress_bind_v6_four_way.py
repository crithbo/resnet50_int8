from __future__ import annotations

import unittest

from tools.validate_qlinearadd_node0007_progress_bind_v6_four_way import (
    negative_control_receipts,
    validate_final_zip,
)


class QLinearAddNode0007ProgressBindV6FourWayTests(unittest.TestCase):
    def test_final_zip_closes_four_way_binding(self) -> None:
        report = validate_final_zip()
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["status"], "FOUR_WAY_BINDING_VALIDATED")
        self.assertTrue(report["zip_unchanged"])
        self.assertTrue(report["sidecar_exact"])
        self.assertEqual(
            report["four_way"]["directions"],
            {
                "source": True,
                "include": True,
                "compile_enable": True,
                "runtime_return": True,
            },
        )
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertFalse(report["workload_analysis_repeated"])
        self.assertFalse(report["package_rebuilt"])
        self.assertFalse(report["server_action"])

    def test_source_removal_fails_closed(self) -> None:
        receipt = negative_control_receipts()["source_removed"]
        self.assertTrue(receipt["failed_closed"], receipt)

    def test_incdir_removal_fails_closed(self) -> None:
        receipt = negative_control_receipts()["incdir_removed"]
        self.assertTrue(receipt["failed_closed"], receipt)

    def test_macro_removal_fails_closed(self) -> None:
        receipt = negative_control_receipts()["macro_removed"]
        self.assertTrue(receipt["failed_closed"], receipt)

    def test_runtime_return_removal_fails_closed(self) -> None:
        receipt = negative_control_receipts()["runtime_return_removed"]
        self.assertTrue(receipt["failed_closed"], receipt)


if __name__ == "__main__":
    unittest.main()
