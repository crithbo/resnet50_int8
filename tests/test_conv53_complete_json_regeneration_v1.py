from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.validate_conv53_complete_json_regeneration_v1 import (
    run_negative_controls,
    validate_payload,
)


OUTPUT = (
    PROJECT_ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/conv_int32_accumulate"
)


class Conv53CompleteJsonRegenerationTest(unittest.TestCase):
    def test_conv53_regeneration_fail_closed_contract(self) -> None:
        result = validate_payload(PROJECT_ROOT, OUTPUT)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["stage_count"], 53)
        self.assertEqual(result["signature_class_count"], 20)
        self.assertEqual(result["materialized_complete_json_count"], 0)
        self.assertGreater(result["unresolved_or_unknown_count"], 0)

    def test_conv53_regeneration_negative_controls(self) -> None:
        result = run_negative_controls(PROJECT_ROOT, OUTPUT)
        self.assertTrue(result["positive_validation_pass"])
        self.assertEqual(result["negative_control_count"], 4)
        self.assertTrue(result["all_negative_controls_fail_closed"])


if __name__ == "__main__":
    unittest.main()
