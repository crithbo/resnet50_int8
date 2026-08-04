from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_sa_remaining52_expansion import (
    validate_remaining52_expansion,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = (
    ROOT / "contracts/operator_config/conv_sa_remaining52_expansion_v1.json"
)


class ConvSaRemaining52ExpansionTest(unittest.TestCase):
    def test_machine_expansion_contract(self) -> None:
        if not REPORT.is_file():
            self.skipTest("remaining52 report is not generated")
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        validation = validate_remaining52_expansion(ROOT, report)
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertEqual(validation["record_count"], 52)
        self.assertFalse(validation["numeric_analysis_repeated_by_validator"])
        self.assertFalse(
            report["scope"]["new_server_package_generated_for_remaining52"]
        )
        self.assertFalse(
            report["claim_boundary"]["final_trassic20_rtl_commit_bound"]
        )


if __name__ == "__main__":
    unittest.main()
