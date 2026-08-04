from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_stem_serialized_materialization_gate import (
    validate_stem_materialization_gate,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/conv_stem_serialized_materialization_gate_v1.json"
)


class ConvStemSerializedMaterializationGateTest(unittest.TestCase):
    def test_historical_pre_authorization_gate_is_superseded_fail_closed(self) -> None:
        if not CONTRACT.is_file():
            self.skipTest("stem gate is not generated")
        report = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validation = validate_stem_materialization_gate(ROOT, report)
        self.assertFalse(validation["valid"])
        self.assertFalse(validation["target_and_package_absent"])
        self.assertTrue(
            any(
                "unexpected target/package path exists" in error
                for error in validation["errors"]
            )
        )
        self.assertEqual(report["status"], "BLOCKED_BEFORE_TARGET_JSON")
        self.assertFalse(report["scope"]["new_target_json_generated"])
        self.assertFalse(
            report["symbolic_output_coverage"]["physical_coverage_claimed"]
        )
        self.assertEqual(
            report["first_blocker"]["id"],
            "B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER",
        )


if __name__ == "__main__":
    unittest.main()
