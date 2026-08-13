import json
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/prove_requant_multiplier_occurrence_supply_v1.py"


class RequantMultiplierOccurrenceSupplyTest(unittest.TestCase):
    def test_exact_payload_valid_blocked_supply(self):
        with tempfile.TemporaryDirectory() as td:
            report_path = pathlib.Path(td) / "report.json"
            result = subprocess.run(
                [sys.executable, str(TOOL), "--output", str(report_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["structural_errors"], [])
            self.assertTrue(report["blocked_valid"])
            self.assertFalse(report["pass"])
            self.assertEqual(
                report["exact_payload_bits_and_axis"]["stage_count"], 54
            )
            self.assertTrue(
                report["exact_payload_bits_and_axis"][
                    "all_exact_payload_hashes_match"
                ]
            )
            self.assertEqual(
                report["family_adjudication"]["conv_stage_count"], 53
            )
            self.assertEqual(
                report["family_adjudication"]["scalar_stage_count"], 1
            )
            self.assertEqual(
                report["completion_blockers"][0]["id"],
                "CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1",
            )
            counterexample = report["native_primitive_supply"][
                "single_chain_counterexample"
            ]
            self.assertNotEqual(
                counterexample["channel0_bits"],
                counterexample["first_distinct_channel_bits"],
            )
            self.assertNotEqual(counterexample["native_lane"], 0)
            self.assertNotEqual(
                counterexample["native_destination_pe"], "PE00"
            )
            self.assertEqual(
                report["native_primitive_supply"]["scalar_stage"]["exact_bits"],
                "0x3a510db3",
            )

    def test_tampered_payload_identity_fails_closed(self):
        spec = importlib.util.spec_from_file_location("requant_supply_proof", TOOL)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        lowering = json.loads(module.LOWERING.read_text(encoding="utf-8"))
        evidence = json.loads(module.EVIDENCE.read_text(encoding="utf-8"))
        evidence["stage_evidence"][0]["qparams"]["multiplier_sha256"] = "0" * 64
        initializers = module.load_float_initializers(module.MODEL)
        result = module.analyze_payloads(lowering, evidence, initializers)
        self.assertFalse(result["all_exact_payload_hashes_match"])
        self.assertEqual(result["mismatch_stage_ids"], ["hwop-0001-01"])


if __name__ == "__main__":
    unittest.main()
