from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_artifact_validator import (
    ACTIVE_ENCODER_COMMIT,
    OperatorConfigArtifactValidator,
)


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "ndp-sim/model_execplan/output/decode_summac_fp32N_fp32N_graph"
CONFIG = GRAPH / "jsons/op0_decode_summac_fp32N_fp32N.json"
ARTIFACTS = GRAPH / "config/op0"
POSITIVE_ARTIFACTS = (
    ("decode_summac_fp32N_fp32N_graph", "op0"),
    ("deepseek_hwverified_decode_summac_graph", "op0"),
    ("decode_max_fp32N_fp32N_graph", "op10"),
    ("silu_withbaseaddr", "op0"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence(artifact_dir: Path) -> dict:
    return {
        "schema": "operator-config-mapping-evidence-v1",
        "mapping_mode": "heuristic",
        "penalty": 0,
        "fallback_used": False,
        "cache": {"policy": "empty", "loaded": False, "portable": True, "sha256": None},
        "encoder": {"repository": "ndp-sim", "commit": ACTIVE_ENCODER_COMMIT},
        "mapping_review_sha256": _sha256(artifact_dir / "mapping_review.json"),
    }


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


class OperatorConfigArtifactValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_real_native_artifacts_match_independent_bit_mirror(self) -> None:
        for graph_name, op_name in POSITIVE_ARTIFACTS:
            with self.subTest(graph=graph_name):
                graph = ROOT / "ndp-sim/model_execplan/output" / graph_name
                config_path = next((graph / "jsons").glob("*.json"))
                artifact_dir = graph / "config" / op_name
                config = json.loads(config_path.read_text(encoding="utf-8"))
                report = OperatorConfigArtifactValidator().validate(
                    config,
                    artifact_dir,
                    mapping_evidence=_evidence(artifact_dir),
                    source=str(config_path),
                )
                self.assertTrue(report.valid, report.to_dict())
                self.assertGreater(report.facts["mirror"]["bit_range_count"], 100)

    def test_single_encoded_bit_tamper_locates_an_owner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-bit-tamper-") as temp_text:
            temp = Path(temp_text)
            for name in ("mapping_review.json", "parsed_bitstream.txt", "modules_dump_64b.bin", "modules_dump_128b.bin"):
                shutil.copy2(ARTIFACTS / name, temp / name)
            lines = (temp / "modules_dump_64b.bin").read_text(encoding="utf-8").splitlines()
            bit = 100
            joined = "".join(lines)
            joined = joined[:bit] + ("0" if joined[bit] == "1" else "1") + joined[bit + 1 :]
            (temp / "modules_dump_64b.bin").write_text(
                "\n".join(joined[index : index + 64] for index in range(0, len(joined), 64)) + "\n",
                encoding="utf-8",
            )
            report = OperatorConfigArtifactValidator().validate(
                self.config,
                temp,
                mapping_evidence=_evidence(temp),
            )
            self.assertIn("BITSTREAM.BINARY_MISMATCH", _codes(report))
            issue = next(issue for issue in report.issues if issue.code == "BITSTREAM.BINARY_MISMATCH")
            self.assertIn("owner=", issue.message)

    def test_nonzero_penalty_and_fallback_fail_closed(self) -> None:
        evidence = _evidence(ARTIFACTS)
        evidence["penalty"] = 1.0
        evidence["fallback_used"] = True
        report = OperatorConfigArtifactValidator().validate(
            self.config,
            ARTIFACTS,
            mapping_evidence=evidence,
        )
        self.assertIn("MAPPING.NONZERO_PENALTY", _codes(report))
        self.assertIn("MAPPING.FALLBACK", _codes(report))

    def test_mapping_review_hash_and_nonportable_cache_fail_closed(self) -> None:
        evidence = copy.deepcopy(_evidence(ARTIFACTS))
        evidence["mapping_review_sha256"] = "0" * 64
        evidence["cache"] = {"policy": "host-local", "loaded": True, "portable": False, "sha256": None}
        report = OperatorConfigArtifactValidator().validate(
            self.config,
            ARTIFACTS,
            mapping_evidence=evidence,
        )
        self.assertIn("MAPPING.REVIEW_IDENTITY", _codes(report))
        self.assertIn("MAPPING.CACHE_NONPORTABLE", _codes(report))

    def test_native_silent_default_and_wrap_candidates_fail_before_mirroring(self) -> None:
        missing = copy.deepcopy(self.config)
        del missing["stream_engine"]["stream0"]["dim_stride"]
        missing_report = OperatorConfigArtifactValidator().validate(
            missing,
            ARTIFACTS,
            mapping_evidence=_evidence(ARTIFACTS),
        )
        self.assertIn("ARTIFACT.INPUT_CONFIG_INVALID", _codes(missing_report))
        self.assertNotIn("mirror", missing_report.facts)

        wrapped = copy.deepcopy(self.config)
        wrapped["stream_engine"]["stream0"]["dim_stride"][0] = 1 << 20
        wrap_report = OperatorConfigArtifactValidator().validate(
            wrapped,
            ARTIFACTS,
            mapping_evidence=_evidence(ARTIFACTS),
        )
        self.assertIn("ARTIFACT.INPUT_CONFIG_INVALID", _codes(wrap_report))
        self.assertNotIn("mirror", wrap_report.facts)

    def test_rtl_unreachable_mapping_is_rejected_even_when_review_is_self_consistent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-unreachable-") as temp_text:
            temp = Path(temp_text)
            for name in ("mapping_review.json", "parsed_bitstream.txt", "modules_dump_64b.bin", "modules_dump_128b.bin"):
                shutil.copy2(ARTIFACTS / name, temp / name)
            review_path = temp / "mapping_review.json"
            review = json.loads(review_path.read_text(encoding="utf-8"))
            for row in review["node_to_resource"]:
                if row["node"] == "DRAM_LC.LC0":
                    row["resource"] = "LC9"
            for row in review["connection_mapping"]:
                if row["src_node"] == "DRAM_LC.LC0":
                    row["src_resource"] = "LC9"
                if row["dst_node"] == "DRAM_LC.LC0":
                    row["dst_resource"] = "LC9"
            review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
            report = OperatorConfigArtifactValidator().validate(
                self.config,
                temp,
                mapping_evidence=_evidence(temp),
            )
            self.assertIn("MAPPING.RTL_UNREACHABLE", _codes(report))


if __name__ == "__main__":
    unittest.main()
