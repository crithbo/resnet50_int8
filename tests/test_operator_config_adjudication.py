from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_adjudication import (
    NativeEncoderRun,
    classify_normalization,
    compare_native_runs,
    normalize_known_legacy_expressions,
    normalization_adjudication,
    run_native_changed_field_probe,
)
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator


ROOT = Path(__file__).resolve().parents[1]
SHADOW = ROOT / "artifacts/operator_config_validation/r3-shadow-active-jsons-20260723.json"


class OperatorConfigAdjudicationTests(unittest.TestCase):
    def test_all_nine_known_failures_normalize_in_memory_to_strict_valid(self) -> None:
        report = json.loads(SHADOW.read_text(encoding="utf-8"))
        invalid = [item for item in report["reports"] if not item["valid"]]
        self.assertEqual(len(invalid), 9)
        kinds: set[str] = set()
        for item in invalid:
            source = Path(item["source"])
            if not source.is_absolute():
                source = ROOT / source
            original = json.loads(source.read_text(encoding="utf-8"))
            normalized, changes = normalize_known_legacy_expressions(original)
            kinds.update(change.kind for change in changes)
            self.assertTrue(changes, source.name)
            self.assertTrue(
                OperatorConfigValidator().validate(normalized).valid,
                source.name,
            )
            self.assertNotEqual(original, normalized)
        self.assertEqual(
            kinds,
            {
                "explicit_zero_padding",
                "remove_write_read_only_field",
                "typed_null_index_mode",
            },
        )

    def test_normalizer_does_not_mutate_source_or_change_strict_valid_config(self) -> None:
        source = ROOT / "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
        original = json.loads(source.read_text(encoding="utf-8"))
        frozen = json.loads(json.dumps(original))
        normalized, changes = normalize_known_legacy_expressions(original)
        self.assertEqual(original, frozen)
        self.assertEqual(normalized, original)
        self.assertEqual(changes, [])

    def test_padding_normalization_remains_semantically_blocked(self) -> None:
        classification = classify_normalization(
            normalize_known_legacy_expressions(
                json.loads(
                    (ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json").read_text(
                        encoding="utf-8"
                    )
                )
            )[1]
        )
        self.assertEqual(
            classification["normalized_identity"],
            "bit-equivalent-development-candidate-blocked",
        )
        self.assertTrue(classification["semantic_blockers"])

    def test_two_failed_native_runs_are_not_vacuously_bit_equal(self) -> None:
        failed = NativeEncoderRun(
            returncode=1,
            mapping_mode="heuristic",
            mapping_cache_policy="empty",
            mapping_cache_source_sha256=None,
            loaded_cached_mapping=False,
            zero_penalty_mapping=False,
            command=[],
            stdout_sha256="",
            stderr_sha256="",
            stdout_tail=[],
            stderr_tail=[],
            artifact_sha256={},
            artifact_size={},
            detailed_dump_sha256=None,
        )
        comparison = compare_native_runs(failed, failed)
        self.assertFalse(comparison["both_succeeded"])
        self.assertFalse(comparison["all_core_artifacts_equal"])
        self.assertFalse(any(comparison["artifact_equal"].values()))

    def test_native_changed_field_probe_covers_each_normalization_kind(self) -> None:
        sources = [
            ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json",
            ROOT / "ndp-sim/jsons/node0004_accumulate_wave0.json",
            ROOT / "ndp-sim/jsons/prefill_gemm_local.json",
        ]
        with tempfile.TemporaryDirectory(prefix="operator-config-probe-test-") as temp_text:
            temp = Path(temp_text)
            for source in sources:
                normalized, changes = normalize_known_legacy_expressions(
                    json.loads(source.read_text(encoding="utf-8"))
                )
                normalized_path = temp / source.name
                normalized_path.write_text(
                    json.dumps(normalized, indent=2) + "\n",
                    encoding="utf-8",
                )
                probe = run_native_changed_field_probe(
                    ndp_sim_root=ROOT / "ndp-sim",
                    original_path=source,
                    normalized_path=normalized_path,
                    changes=changes,
                    python_executable=Path(sys.executable),
                )
                self.assertEqual(probe.returncode, 0, source.name)
                self.assertIsNotNone(probe.proof, source.name)
                self.assertTrue(probe.proof["all_equivalent"], source.name)

    def test_adjudication_separates_padding_contract_from_schema_cleanup(self) -> None:
        cases = {
            "maxpool_config_16_112_112_stride2_padding1.json": (
                "blocked-missing-operator-padding-contract"
            ),
            "node0004_accumulate_wave0.json": (
                "approved-remove-native-ignored-write-fields"
            ),
            "prefill_gemm_local.json": "approved-typed-null-native-field-equivalent",
        }
        for name, expected in cases.items():
            source = ROOT / "ndp-sim/jsons" / name
            _, changes = normalize_known_legacy_expressions(
                json.loads(source.read_text(encoding="utf-8"))
            )
            decision = normalization_adjudication(
                changes,
                field_encoding_equivalent=True,
            )
            self.assertEqual(decision["normalization_decision"], expected)
            self.assertFalse(decision["source_rewrite_authorized"])

        source = ROOT / "ndp-sim/jsons/maxpool_config_16_16_16_stride2_padding1.json"
        _, changes = normalize_known_legacy_expressions(
            json.loads(source.read_text(encoding="utf-8"))
        )
        approved = normalization_adjudication(
            changes,
            field_encoding_equivalent=True,
            padding_contract_validated=True,
        )
        self.assertEqual(
            approved["normalization_decision"],
            "approved-explicit-zero-padding-operator-contract",
        )


if __name__ == "__main__":
    unittest.main()
