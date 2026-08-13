from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.materialize_requant_scalar_phase_strict_json_v1 import materialize
from tools.validate_requant_scalar_phase_strict_json_v1 import (
    INVENTORY,
    ROOT,
    validate,
    validate_candidate,
)


class RequantScalarPhaseStrictJsonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parent = ROOT / "artifacts/operator_config_validation"
        cls._temp = tempfile.TemporaryDirectory(
            prefix="rq_scalar_phase_test_",
            dir=parent,
        )
        cls.artifact_root = Path(cls._temp.name) / "out"
        materialize(cls.artifact_root)
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def test_full_family_local_strict_validation_passes(self) -> None:
        report = validate(self.artifact_root)
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(report["stage_count"], 54)
        self.assertEqual(report["strict_json_count"], 54)
        self.assertEqual(report["conv_stage_count"], 53)
        self.assertEqual(report["matmul_stage_count"], 1)
        self.assertEqual(report["forbidden_output_count"], 0)

    def test_multiplier_bit_tamper_fails_closed(self) -> None:
        stage = self.inventory["stages"][0]
        path = (
            self.artifact_root
            / "candidates"
            / stage["identity"]["hw_op_id"]
            / "complete_json.json"
        )
        candidate = json.loads(path.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(candidate)
        tampered["qparams"]["multiplier_bits"][0] = "0x00000000"
        errors = validate_candidate(tampered, stage)
        self.assertTrue(any("multiplier payload SHA" in item for item in errors))

    def test_scalar_buffer_size_tamper_fails_closed(self) -> None:
        stage = self.inventory["stages"][0]
        path = (
            self.artifact_root
            / "candidates"
            / stage["identity"]["hw_op_id"]
            / "complete_json.json"
        )
        candidate = json.loads(path.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(candidate)
        tampered["physical_schedule"]["buffers"]["buffer2_B"][
            "buf_spatial_size"
        ] = 16
        errors = validate_candidate(tampered, stage)
        self.assertTrue(any("buffer2 spatial size" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
