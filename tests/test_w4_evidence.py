from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.w4_evidence import (
    LEGACY16_METADATA,
    annotate_legacy16_report,
    architecture_evidence_basis_sha256,
    canonical_json_bytes,
    current_evidence_path,
    resolve_current_output,
    resolve_legacy16_output,
)
from resnet50_pipeline.w4_audit import audit_w4_gate


ROOT = Path(__file__).resolve().parents[1]
LEGACY16_TOOLS = (
    "audit_w4_network_candidates.py",
    "verify_w4_add_layout.py",
    "verify_w4_avgpool_layout.py",
    "verify_w4_conv0_layout.py",
    "verify_w4_conv0_profiles.py",
    "verify_w4_conv_shape_coverage.py",
    "verify_w4_matmul_layout.py",
    "verify_w4_maxpool_layout.py",
)


class W4EvidenceTests(unittest.TestCase):
    def test_architecture_basis_excludes_only_current_eligible_evidence(self) -> None:
        architecture = json.loads(
            (ROOT / "contracts/architecture.json").read_text(encoding="utf-8")
        )
        basis = architecture_evidence_basis_sha256(architecture)
        architecture["candidate_evidence"]["new-current-record"] = {
            "current_gate_eligible": True,
            "sha256": "f" * 64,
        }
        self.assertEqual(architecture_evidence_basis_sha256(architecture), basis)
        architecture["candidate_layouts"]["w4_simple_group4x7_28_candidate_v1"][
            "packing"
        ] += "; changed"
        self.assertNotEqual(architecture_evidence_basis_sha256(architecture), basis)

    def test_project_legacy16_index_covers_exactly_nine_immutable_reports(self) -> None:
        index = json.loads(
            (ROOT / "artifacts/w4/legacy16_index.json").read_text(encoding="utf-8")
        )
        self.assertNotIn(
            b"\r\n", (ROOT / "artifacts/w4/legacy16_index.json").read_bytes()
        )
        self.assertEqual(len(index["reports"]), 9)
        for field, expected in LEGACY16_METADATA.items():
            self.assertEqual(index[field], expected)
        for evidence_id, record in index["reports"].items():
            with self.subTest(evidence_id=evidence_id):
                path = ROOT / record["path"]
                payload = path.read_bytes()
                self.assertNotIn(b"\r\n", payload)
                self.assertEqual(len(payload), record["size_bytes"])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
                report = json.loads(payload)
                for field, expected in LEGACY16_METADATA.items():
                    self.assertEqual(report[field], expected)

    def test_every_legacy16_tool_requires_explicit_acknowledgement(self) -> None:
        for tool in LEGACY16_TOOLS:
            with self.subTest(tool=tool):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / tool)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("--legacy16", result.stderr)

    def test_legacy_report_metadata_and_output_namespace_are_fail_closed(self) -> None:
        report = annotate_legacy16_report({"result": True, "status": "candidate"})
        for field, expected in LEGACY16_METADATA.items():
            self.assertEqual(report[field], expected)
        self.assertEqual(report["legacy_generation_status"], "candidate")
        with self.assertRaisesRegex(ContractError, "status"):
            annotate_legacy16_report({"status": "approved"})
        with self.assertRaisesRegex(ContractError, "only write below"):
            resolve_legacy16_output(
                ROOT, Path("artifacts/w4/network_candidate_dry_run.json")
            )
        accepted = resolve_legacy16_output(
            ROOT, Path("artifacts/w4/legacy16/scratch.json")
        )
        self.assertEqual(
            accepted,
            (ROOT / "artifacts/w4/legacy16/scratch.json").resolve(),
        )

    def test_current_evidence_path_is_content_addressed_and_protected(self) -> None:
        report = {
            "target_family": "rtl28",
            "slice_count": 28,
            "architecture_sha256": "a" * 64,
        }
        payload = canonical_json_bytes(report)
        expected = current_evidence_path(
            ROOT, "a" * 64, "g4-gate-audit", payload
        )
        self.assertIn("rtl28", expected.parts)
        self.assertTrue(expected.name.startswith("g4-gate-audit-"))
        self.assertEqual(
            resolve_current_output(ROOT, None, expected, True), expected
        )
        with self.assertRaisesRegex(ContractError, "content-addressed RTL28"):
            resolve_current_output(
                ROOT,
                Path("artifacts/w4/g4_gate_audit.json"),
                expected,
                False,
            )

    def test_current_cli_writes_the_exact_content_addressed_bytes(self) -> None:
        expected = canonical_json_bytes(audit_w4_gate(ROOT))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "g4.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/audit_w4_gate.py"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
