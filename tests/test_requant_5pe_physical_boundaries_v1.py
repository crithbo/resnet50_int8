import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/prove_requant_5pe_physical_boundaries_v1.py"


class Requant5PEPhysicalBoundariesTest(unittest.TestCase):
    def test_valid_blocked_proof(self):
        with tempfile.TemporaryDirectory() as td:
            output = pathlib.Path(td) / "report.json"
            result = subprocess.run(
                [sys.executable, str(TOOL), "--output", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["structural_errors"], [])
            self.assertTrue(report["blocked_valid"])
            self.assertFalse(report["pass"])
            self.assertTrue(report["duplicate_breakpoint_bst"]["proven"])
            self.assertTrue(report["single_operator_selector_tag_backpressure"]["proven"])
            self.assertEqual(
                report["multiplier_supply_54_stage"]["typed_payload_identity"]["stage_count"], 54
            )
            self.assertTrue(
                report["multiplier_supply_54_stage"]["typed_payload_identity"]["identity_pass"]
            )
            self.assertFalse(report["multiplier_supply_54_stage"]["physical_supply_proven"])
            self.assertEqual(
                [item["id"] for item in report["completion_blockers"]],
                ["MULTIPLIER_SUPPLY_TYPED_ADDRESS_LIFETIME_UNPROVEN"],
            )


if __name__ == "__main__":
    unittest.main()
