from pathlib import Path
import unittest

from tools.audit_requant_zero_point_shape_holdouts import (
    EXPECTED_SHAPES,
    build,
)


class RequantShapeHoldoutAuditTests(unittest.TestCase):
    def test_four_holdouts_remain_planning_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = build(root)
        self.assertEqual(
            [item["shape_signature"] for item in report["holdouts"]],
            list(EXPECTED_SHAPES),
        )
        self.assertTrue(
            all(item["y_zero_point"] == 0 for item in report["holdouts"])
        )
        self.assertEqual(
            report["boundaries"]["evidence_level"],
            "LOCAL_E2_PLANNING_ONLY",
        )
        self.assertFalse(report["boundaries"]["operator_json_generated"])
        self.assertFalse(report["boundaries"]["server_package_generated"])
        self.assertFalse(report["boundaries"]["rtl_modified"])


if __name__ == "__main__":
    unittest.main()
