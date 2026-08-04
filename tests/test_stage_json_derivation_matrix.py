from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.stage_json_derivation_matrix import (
    StageJsonDerivationMatrixError,
    build_stage_json_derivation_matrix,
    flatten_json_leaves,
    validate_representative_signature,
    validate_stage_json_derivation_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "contracts/operator_config/stage_json_derivation_matrix_v1.json"
)


class StageJsonDerivationMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_stage_json_derivation_matrix(ROOT)
        cls.by_id = {
            item["request_id"]: item for item in cls.value["stages"]
        }

    def test_five_representatives_cover_every_projected_leaf(self) -> None:
        self.assertEqual(
            set(self.by_id),
            {
                "r5:hwop-0002-00",
                "r5:hwop-0004-01",
                "r5:hwop-0071-00",
                "r5:hwop-0073-00",
                "r5:hwop-0077-00",
            },
        )
        self.assertEqual(self.value["summary"]["json_projection_count"], 4)
        self.assertEqual(self.value["summary"]["alias_projection_count"], 1)
        self.assertEqual(
            self.value["summary"]["fully_covered_projection_count"], 5
        )
        for item in self.value["stages"]:
            self.assertTrue(item["full_json_leaf_coverage"])
            self.assertEqual(item["json_leaf_count"], len(item["rows"]))

    def test_rows_reverse_bind_exact_projection_values(self) -> None:
        for item in self.value["stages"]:
            projection = item["json_projection"]
            if projection is None:
                self.assertEqual(item["rows"], [])
                continue
            config = json.loads(
                (ROOT / projection["path"]).read_text(encoding="utf-8")
            )
            expected = flatten_json_leaves(config)
            actual = [
                (row["json_path"], row["reference_value"])
                for row in item["rows"]
            ]
            self.assertEqual(actual, expected)
            self.assertTrue(
                all(row["semantic_owner"] for row in item["rows"])
            )
            self.assertTrue(
                all(row["source_kind"] for row in item["rows"])
            )

    def test_addresses_are_reference_only_and_late_bound(self) -> None:
        address_rows = [
            row
            for item in self.value["stages"]
            for row in item["rows"]
            if row["json_path"].endswith(".base_addr")
        ]
        self.assertTrue(address_rows)
        self.assertTrue(
            all(row["source_kind"] == "late_bound_address" for row in address_rows)
        )
        self.assertTrue(
            all(
                row["emission_value_policy"]
                == "replace_reference_with_late_bound_value"
                for row in address_rows
            )
        )

    def test_stage_blockers_override_structural_projection(self) -> None:
        maxpool = self.by_id["r5:hwop-0002-00"]
        gap = self.by_id["r5:hwop-0071-00"]
        requant = self.by_id["r5:hwop-0004-01"]
        view = self.by_id["r5:hwop-0073-00"]
        dequant = self.by_id["r5:hwop-0077-00"]
        self.assertTrue(maxpool["readiness_axes"]["json_emitter_ready"])
        self.assertFalse(maxpool["readiness_axes"]["rtl_semantics_compatible"])
        self.assertEqual(
            set(maxpool["stage_blockers"]),
            {"B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"},
        )
        self.assertEqual(
            set(gap["stage_blockers"]),
            {"B_GAP_GA_ACCUM_STATE"},
        )
        self.assertEqual(
            gap["locally_resolved_blockers"],
            ["B_GAP_D_INDEX_CARRIER_SEMANTICS"],
        )
        self.assertEqual(
            gap["json_projection"]["path"],
            "configs/stage_codegen/hwop-0071-00-d-index-v1/config.json",
        )
        self.assertIn("derived_evidence", gap["json_projection"])
        self.assertIn(
            "B_GA_INT32TOFP32_INPUT_DOMAIN", requant["stage_blockers"]
        )
        self.assertIsNone(view["json_projection"])
        self.assertEqual(view["json_leaf_count"], 0)
        self.assertEqual(
            dequant["json_projection"]["path"],
            "configs/native_ndp_sim/"
            "resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json",
        )
        self.assertIn(
            "derived_candidate_materialization",
            dequant["json_projection"],
        )
        self.assertEqual(dequant["stage_blockers"], [])
        self.assertEqual(self.value["summary"]["current_candidate_json_count"], 1)

    def test_signature_change_fails_closed(self) -> None:
        maxpool = self.by_id["r5:hwop-0002-00"]
        lowering = json.loads(
            (ROOT / "contracts/resnet50_r5_lowering_bundle.json").read_text(
                encoding="utf-8"
            )
        )
        request = next(
            item
            for item in lowering["requests"]
            if item["request_id"] == maxpool["request_id"]
        )
        validate_representative_signature(
            maxpool["request_id"], request["logical_geometry"]
        )
        changed = copy.deepcopy(request["logical_geometry"])
        changed["input_shapes"][0][2] = 111
        with self.assertRaises(StageJsonDerivationMatrixError):
            validate_representative_signature(maxpool["request_id"], changed)

    def test_checked_contract_and_tamper_fail_closed(self) -> None:
        checked = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_stage_json_derivation_matrix(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["stages"][0]["rows"][0]["semantic_owner"] = "unknown"
        with self.assertRaises(StageJsonDerivationMatrixError):
            validate_stage_json_derivation_matrix(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
