from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_artifact_validator import (
    OperatorConfigArtifactValidator,
)
from resnet50_pipeline.operator_config_evidence_bundle import (
    create_mapping_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
NDP_SIM = ROOT / "ndp-sim"
CONFIG = (
    NDP_SIM
    / "model_execplan/output/decode_summac_fp32N_fp32N_graph/jsons/op0_decode_summac_fp32N_fp32N.json"
)
PYTHON = ROOT / ".venv/Scripts/python.exe"


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


class OperatorConfigEvidenceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="mapping-evidence-tests-")
        cls.bundle = Path(cls.temp.name) / "bundle"
        cache = NDP_SIM / "bitstream/config/mapping_cache"
        cls.cache_before = {
            path.relative_to(cache).as_posix(): path.read_bytes()
            for path in cache.glob("*.json")
        }
        cls.result = create_mapping_evidence_bundle(
            ndp_sim_root=NDP_SIM,
            config_path=CONFIG,
            output_dir=cls.bundle,
            python_executable=PYTHON,
            seed=42,
            heuristic_iterations=10_000,
            heuristic_restarts=10,
        )
        cls.cache_after = {
            path.relative_to(cache).as_posix(): path.read_bytes()
            for path in cache.glob("*.json")
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_bundle_is_zero_penalty_portable_and_does_not_touch_native_cache(self) -> None:
        self.assertTrue(self.result.valid)
        self.assertEqual(self.result.penalty, 0)
        self.assertEqual(self.cache_before, self.cache_after)
        evidence = json.loads((self.bundle / "mapping_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["schema"], "operator-config-mapping-evidence-v2")
        self.assertEqual(evidence["cache"]["initial_file_count"], 0)
        self.assertEqual(evidence["cache"]["loaded_origin"], "same-run-generated")
        self.assertTrue(evidence["run"]["native_wrapper_missing_return_observed"])
        report = json.loads(
            (self.bundle / "artifact_validation_report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["valid"])
        self.assertEqual(report["facts"]["mirror"]["unpadded_bits"], 2252)

    def test_bound_native_penalty_state_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mapping-state-tamper-") as temp_text:
            tampered = Path(temp_text) / "bundle"
            shutil.copytree(self.bundle, tampered)
            state_path = tampered / "native_mapping_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["last_mapping_cost"] = 1
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            report = self._validate(tampered)
            self.assertIn("MAPPING.PENALTY_SOURCE", _codes(report))

    def test_bound_stdout_and_same_run_cache_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mapping-log-cache-tamper-") as temp_text:
            tampered = Path(temp_text) / "bundle"
            shutil.copytree(self.bundle, tampered)
            (tampered / "native_stdout.log").write_text("altered\n", encoding="utf-8")
            cache_file = next((tampered / "mapping_cache").glob("*.json"))
            cache_file.write_text("{}\n", encoding="utf-8")
            report = self._validate(tampered)
            self.assertIn("MAPPING.RUN_PROVENANCE", _codes(report))
            self.assertIn("MAPPING.CACHE_IDENTITY", _codes(report))

    def test_refuses_overwrite_and_output_inside_native_tree(self) -> None:
        with self.assertRaises(FileExistsError):
            create_mapping_evidence_bundle(
                ndp_sim_root=NDP_SIM,
                config_path=CONFIG,
                output_dir=self.bundle,
                python_executable=PYTHON,
            )
        with self.assertRaises(ValueError):
            create_mapping_evidence_bundle(
                ndp_sim_root=NDP_SIM,
                config_path=CONFIG,
                output_dir=NDP_SIM / "forbidden-evidence-output",
                python_executable=PYTHON,
            )

    def _validate(self, bundle: Path):
        config = json.loads((bundle / "source_config.json").read_text(encoding="utf-8"))
        evidence = json.loads((bundle / "mapping_evidence.json").read_text(encoding="utf-8"))
        return OperatorConfigArtifactValidator().validate(
            config,
            bundle,
            mapping_evidence=evidence,
            source="source_config.json",
        )


class PatchedOperatorConfigEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = (
            ROOT
            / "artifacts/operator_config_validation/r5-patched-mapping-evidence"
            / "decode_summac-seed42-v1"
        )

    def test_checked_in_patched_mapping_is_valid_without_retry_accident(self) -> None:
        evidence = json.loads(
            (self.bundle / "mapping_evidence.json").read_text(encoding="utf-8")
        )
        config = json.loads(
            (self.bundle / "source_config.json").read_text(encoding="utf-8")
        )
        report = OperatorConfigArtifactValidator().validate(
            config,
            self.bundle,
            mapping_evidence=evidence,
            source="source_config.json",
        )
        self.assertTrue(report.valid)
        self.assertFalse(evidence["run"]["native_wrapper_missing_return_observed"])
        self.assertEqual(
            evidence["encoder"]["patchset"]["patchset_id"],
            "resnet50-ndp-toolchain-6144-v1",
        )

    def test_patched_manifest_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="patched-manifest-tamper-") as temp_text:
            tampered = Path(temp_text) / "bundle"
            shutil.copytree(self.bundle, tampered)
            manifest_path = tampered / "patchset_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["target_profile"]["rows_per_bank"] = 8192
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            config = json.loads(
                (tampered / "source_config.json").read_text(encoding="utf-8")
            )
            evidence = json.loads(
                (tampered / "mapping_evidence.json").read_text(encoding="utf-8")
            )
            report = OperatorConfigArtifactValidator().validate(
                config,
                tampered,
                mapping_evidence=evidence,
                source="source_config.json",
            )
            self.assertIn("MAPPING.PATCHSET_IDENTITY", _codes(report))

    def test_three_gemm_residuals_use_one_pinned_zero_penalty_cache(self) -> None:
        expected_commit = "d4ffc32c9b29a858d83e13706cd837c5549521a4"
        expected_seed = "efa39a1a72167936c62ee9389556e8ceda9176ecbbd60a30b9ded0a4359c1b4d"
        for name in (
            "prefill_gemm_local",
            "prefill_gemm_local_qkt",
            "prefill_gemm_ring_4slice",
        ):
            with self.subTest(name=name):
                bundle = (
                    ROOT
                    / "artifacts/operator_config_validation/r5-patched-mapping-evidence"
                    / f"{name}-strict-frozen-fab056-v1"
                )
                evidence = json.loads(
                    (bundle / "mapping_evidence.json").read_text(encoding="utf-8")
                )
                config = json.loads(
                    (bundle / "source_config.json").read_text(encoding="utf-8")
                )
                report = OperatorConfigArtifactValidator().validate(
                    config,
                    bundle,
                    mapping_evidence=evidence,
                    source="source_config.json",
                )
                self.assertTrue(report.valid, report.to_dict())
                self.assertEqual(evidence["mapping_mode"], "frozen-zero-penalty")
                self.assertEqual(evidence["penalty"], 0)
                self.assertEqual(evidence["cache"]["policy"], "frozen")
                self.assertEqual(evidence["cache"]["seed"]["sha256"], expected_seed)
                self.assertEqual(
                    evidence["cache"]["seed"]["origin"]["commit"], expected_commit
                )

    def test_maxpool_residual_uses_pinned_zero_penalty_cache(self) -> None:
        bundle = (
            ROOT
            / "artifacts/operator_config_validation/r5-patched-mapping-evidence"
            / "maxpool-16-16-strict-frozen-dc65-v1"
        )
        evidence = json.loads(
            (bundle / "mapping_evidence.json").read_text(encoding="utf-8")
        )
        config = json.loads(
            (bundle / "source_config.json").read_text(encoding="utf-8")
        )
        report = OperatorConfigArtifactValidator().validate(
            config,
            bundle,
            mapping_evidence=evidence,
            source="source_config.json",
        )
        self.assertTrue(report.valid, report.to_dict())
        self.assertEqual(evidence["mapping_mode"], "frozen-zero-penalty")
        self.assertEqual(evidence["penalty"], 0)
        self.assertFalse(evidence["fallback_used"])
        self.assertEqual(evidence["cache"]["policy"], "frozen")
        self.assertEqual(
            evidence["cache"]["seed"]["origin"]["commit"],
            "d4ffc32c9b29a858d83e13706cd837c5549521a4",
        )


if __name__ == "__main__":
    unittest.main()
