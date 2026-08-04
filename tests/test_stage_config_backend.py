from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.stage_config_backend import (
    StageConfigBlocked,
    build_stage_backend_catalog,
    lower_stage_request,
    materialize_stage_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "contracts/resnet50_r5_lowering_bundle.json"


class StageConfigBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))

    def test_catalog_is_explicit_about_implemented_and_blocked_families(self) -> None:
        catalog = build_stage_backend_catalog(ROOT)
        self.assertEqual(catalog["summary"]["candidate_emitter_count"], 2)
        self.assertEqual(catalog["summary"]["draft_json_emitter_count"], 1)
        self.assertEqual(catalog["summary"]["zero_copy_emitter_count"], 1)
        self.assertIn("ConvInt32Accumulate", catalog["families"])
        self.assertIn(
            "B_CONV_FULL_3WAVE_SCHEDULE",
            catalog["families"]["ConvInt32Accumulate"]["remaining_blockers"],
        )
        self.assertIn(
            "B_CONV_INT8_SA",
            catalog["families"]["ConvInt32Accumulate"]["remaining_blockers"],
        )
        conv_evidence = catalog["families"]["ConvInt32Accumulate"]["evidence"]
        self.assertEqual(len(conv_evidence), 1)
        self.assertTrue(conv_evidence[0]["exists"])
        requant_evidence = catalog["families"]["RequantizeUint8"]["evidence"]
        self.assertEqual(len(requant_evidence), 5)
        self.assertTrue(all(item["exists"] for item in requant_evidence))
        requant = catalog["families"]["RequantizeUint8"]
        self.assertEqual(
            requant["status"],
            "candidate_emitter_implemented_local_e2_exact_node0001",
        )
        self.assertEqual(
            requant["remaining_blockers"],
            [
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
                "B_REQUANT_MAGIC_ZP_TIE_PARITY",
                "B_REQUANT_MATMUL_2D_LAYOUT",
                "B_REQUANT_SERVER_E4_E5",
            ],
        )
        self.assertEqual(len(requant["templates"]), 2)
        self.assertTrue(all(item["exists"] for item in requant["templates"]))
        self.assertTrue(
            catalog["policy"][
                "user_authorized_reference_config_correctness_is_accepted"
            ]
        )
        self.assertTrue(
            catalog["policy"][
                "project_added_configs_are_not_implicitly_accepted"
            ]
        )
        gap = catalog["families"]["GlobalAverageSumInt32"]
        self.assertEqual(
            gap["status"], "candidate_emitter_blocked_by_lc_value_semantics"
        )
        self.assertEqual(len(gap["templates"]), 1)
        self.assertEqual(len(gap["evidence"]), 3)
        self.assertTrue(gap["templates"][0]["exists"])
        self.assertTrue(all(item["exists"] for item in gap["evidence"]))
        self.assertEqual(
            gap["remaining_blockers"],
            [
                "B_GAP_D_INDEX_CARRIER_SEMANTICS",
                "B_GAP_GA_ACCUM_STATE",
                "B_SERVER_E4_E5",
            ],
        )
        dequant = catalog["families"]["DequantizeLinear"]
        self.assertEqual(
            dequant["status"], "candidate_emitter_implemented_local_e2"
        )
        self.assertEqual(
            dequant["remaining_blockers"], ["B_DEQUANT_SERVER_E4_E5"]
        )
        self.assertEqual(len(dequant["templates"]), 1)
        self.assertEqual(len(dequant["evidence"]), 3)
        self.assertTrue(dequant["templates"][0]["exists"])
        self.assertTrue(all(item["exists"] for item in dequant["evidence"]))
        derivation = dequant["templates"][0]["derivation"]
        self.assertEqual(
            derivation["kind"], "contract_derived_local_e2_candidate"
        )
        self.assertEqual(
            derivation["source"]["path"],
            "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json",
        )
        self.assertTrue(derivation["source"]["exists"])
        self.assertEqual(len(derivation["evidence"]), 3)
        self.assertTrue(
            all(item["exists"] for item in derivation["evidence"])
        )

    def test_maxpool_request_fails_closed_on_rtl_semantics(self) -> None:
        with self.assertRaises(StageConfigBlocked) as context:
            lower_stage_request(ROOT, self.bundle, "r5:hwop-0002-00")
        self.assertEqual(
            context.exception.blockers,
            ["B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"],
        )

    def test_view_request_emits_zero_copy_binding(self) -> None:
        schedule, config, source = lower_stage_request(
            ROOT, self.bundle, "r5:hwop-0073-00"
        )
        self.assertEqual(schedule["emission"]["kind"], "zero_copy_binding")
        self.assertIsNone(config)
        self.assertIsNone(source)

    def test_gap_request_fails_closed_on_d_index_carrier_semantics(self) -> None:
        with self.assertRaises(StageConfigBlocked) as context:
            lower_stage_request(ROOT, self.bundle, "r5:hwop-0071-00")
        self.assertEqual(
            context.exception.blockers,
            [
                "B_GAP_D_INDEX_CARRIER_SEMANTICS",
                "B_GAP_GA_ACCUM_STATE",
            ],
        )

    def test_conv_request_fails_closed_until_schedule_semantics_are_resolved(self) -> None:
        with self.assertRaises(StageConfigBlocked) as context:
            lower_stage_request(ROOT, self.bundle, "r5:hwop-0004-00")
        self.assertIn("B_CONV_FULL_3WAVE_SCHEDULE", context.exception.blockers)

    def test_dequant_request_emits_exact_local_e2_candidate(self) -> None:
        schedule, config, source = lower_stage_request(
            ROOT, self.bundle, "r5:hwop-0077-00"
        )
        self.assertIsNotNone(config)
        self.assertIsNotNone(source)
        self.assertEqual(schedule["hw_op_type"], "DequantizeLinear")
        self.assertEqual(
            schedule["emission"]["remaining_blockers"],
            ["B_DEQUANT_SERVER_E4_E5"],
        )
        self.assertFalse(schedule["emission"]["candidate_release"])
        self.assertEqual(
            schedule["dataflow"]["first_stage"],
            ["PE00", "PE02", "PE20", "PE22"],
        )
        self.assertEqual(
            schedule["dataflow"]["second_stage"],
            ["PE10", "PE12", "PE30", "PE32"],
        )
        self.assertFalse(
            schedule["typed_parameter_consumption"]["affine_offset"]["consumed"]
        )

    def test_requant_node0001_emits_exact_two_stage_config_set(self) -> None:
        schedule, config, source = lower_stage_request(
            ROOT, self.bundle, "r5:hwop-0001-01"
        )
        self.assertIsNone(config)
        self.assertIsNone(source)
        self.assertEqual(schedule["hw_op_type"], "RequantizeUint8")
        self.assertEqual(schedule["physical_schedule"]["occurrence_count"], 24)
        self.assertEqual(
            schedule["physical_schedule"]["physical_stage_count"], 48
        )
        self.assertEqual(schedule["config_set"]["file_count"], 10)
        self.assertTrue(
            schedule["dataflow"][
                "producer_consumer_same_slice_same_address"
            ]
        )
        self.assertEqual(
            schedule["dataflow"][
                "consumer_intermediate_sca_preload_count"
            ],
            0,
        )
        self.assertEqual(
            schedule["emission"]["remaining_blockers"],
            ["B_REQUANT_SERVER_E4_E5"],
        )
        self.assertFalse(schedule["emission"]["candidate_release"])

    def test_requant_node0001_materializes_closed_config_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = materialize_stage_candidate(
                ROOT,
                lowering_bundle_path=BUNDLE_PATH,
                request_id="r5:hwop-0001-01",
                output_root=Path(temporary),
            )
            config_set = manifest["operator_config_set"]
            self.assertIsNone(manifest["operator_config"])
            self.assertEqual(config_set["file_count"], 10)
            self.assertTrue(config_set["semantic_identity"])
            self.assertEqual(
                config_set["strict_json_validation"], "passed"
            )
            self.assertEqual(
                len(list((Path(temporary) / "config_set").iterdir())), 10
            )

    def test_materialization_fails_closed_for_semantically_blocked_stage(self) -> None:
        with tempfile.TemporaryDirectory() as first:
            with self.assertRaises(StageConfigBlocked):
                materialize_stage_candidate(
                    ROOT,
                    lowering_bundle_path=BUNDLE_PATH,
                    request_id="r5:hwop-0002-00",
                    output_root=Path(first),
                )


if __name__ == "__main__":
    unittest.main()
