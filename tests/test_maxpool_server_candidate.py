from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.maxpool_server_candidate import (
    MaxPoolServerCandidateError,
    validate_maxpool_server_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-candidates/"
    "maxpool-node0002-guarded-wave0-v1"
)


class MaxPoolServerCandidateTests(unittest.TestCase):
    def test_checked_candidate_is_matrix_complete_and_not_formally_claimed(self) -> None:
        result = validate_maxpool_server_candidate(ROOT, CANDIDATE)
        self.assertTrue(result["valid"])
        self.assertFalse(result["current_semantics_valid"])
        self.assertEqual(
            result["current_semantic_blockers"],
            ["B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"],
        )
        self.assertEqual(result["matrix_file_count"], 56)
        manifest = json.loads(
            (CANDIDATE / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        self.assertFalse(manifest["candidate_scope"]["formal_target_config"])
        self.assertFalse(manifest["candidate_scope"]["server_execution_claim"])

    def test_incomplete_copy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            (temp / "candidate_manifest.json").write_text(
                (CANDIDATE / "candidate_manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaises(MaxPoolServerCandidateError):
                validate_maxpool_server_candidate(ROOT, temp)


if __name__ == "__main__":
    unittest.main()
