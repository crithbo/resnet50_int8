from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.node0004_server_candidate import (
    Node0004ServerCandidateError,
    validate_node0004_server_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-candidates/node0004-nopp-r1-v2"
)


class Node0004ServerCandidateTests(unittest.TestCase):
    def test_checked_smoke_candidate_is_complete_but_not_numeric_or_formal(self) -> None:
        result = validate_node0004_server_candidate(ROOT, CANDIDATE)
        self.assertTrue(result["valid"])
        self.assertFalse(result["current_semantics_valid"])
        self.assertEqual(
            result["current_semantic_blockers"],
            ["B_SA_INT8_CSA_NUMERIC"],
        )
        self.assertEqual(result["companion_tensor_file_count"], 336)
        manifest = json.loads(
            (CANDIDATE / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        scope = manifest["candidate_scope"]
        self.assertFalse(scope["numeric_pass_claim"])
        self.assertFalse(scope["formal_target_config"])
        self.assertFalse(scope["server_execution_claim"])

    def test_incomplete_copy_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            (temp / "candidate_manifest.json").write_text(
                (CANDIDATE / "candidate_manifest.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaises(Node0004ServerCandidateError):
                validate_node0004_server_candidate(ROOT, temp)


if __name__ == "__main__":
    unittest.main()
