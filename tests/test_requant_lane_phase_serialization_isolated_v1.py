import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/prove_requant_lane_phase_serialization_isolated_v1.py"
SPEC = importlib.util.spec_from_file_location("lane_phase_proof", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RequantLanePhaseSerializationProofTest(unittest.TestCase):
    def test_fresh_isolated_proof_covers_conv53(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--workspace",
                    str(ROOT),
                    "--output",
                    str(output),
                ],
                check=False,
            )
            self.assertEqual(completed.returncode, 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["pass"])
            self.assertEqual(report["conv53_coverage"]["stage_count"], 53)
            self.assertTrue(report["conv53_coverage"]["all_capacity_checks_pass"])
            self.assertTrue(report["scope"]["isolated_worktree_only"])
            self.assertFalse(report["scope"]["target_strict_json_generated"])
            self.assertEqual(report["package_release"], "NONE")

    def test_negative_controls_fail_closed(self):
        native = json.loads(
            (
                ROOT / "ndp-sim/jsons/decode_max_fp32N_fp32N.json"
            ).read_text(encoding="utf-8")
        )
        tampered = copy.deepcopy(native)
        tampered["stream_engine"]["stream0"]["buf_spatial_size"] = 16
        self.assertTrue(MODULE.scalar_template_errors(tampered))
        self.assertFalse(MODULE.stage_capacity(1 << 17)["pass"])


if __name__ == "__main__":
    unittest.main()
