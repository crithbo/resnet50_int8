from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.view_flatten_complete_json_regeneration import (
    ViewFlattenRegenerationError,
    build_view_flatten_complete_json_regeneration,
    run_negative_controls,
    validate_regeneration_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


class ViewFlattenCompleteJsonRegenerationTests(unittest.TestCase):
    def test_builds_one_stage_no_config_contract_without_hardware_json(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "view_flatten"
            result = build_view_flatten_complete_json_regeneration(ROOT, output)
            self.assertTrue(result["valid"])
            self.assertEqual(result["target_stage_count"], 1)
            self.assertEqual(result["equivalence_class_count"], 1)
            self.assertEqual(result["hardware_json_count"], 0)
            contract = json.loads(
                (output / "complete_json/no_config_contract.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(contract["hardware_json_required"])
            self.assertEqual(
                contract["disposition"], "NO_HARDWARE_JSON_REQUIRED"
            )
            self.assertEqual(
                contract["target_inventory"]["stages"][0]["request_id"],
                "r5:hwop-0073-00",
            )
            self.assertEqual(
                contract["current_approved_overlay"]["total_unique_bytes"], 32768
            )
            self.assertEqual(
                contract["current_approved_overlay"]["hardware_view_stage_count"], 0
            )

    def test_leaf_ledger_is_complete_and_current_diff_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "view_flatten"
            build_view_flatten_complete_json_regeneration(ROOT, output)
            validation = validate_regeneration_bundle(ROOT, output)
            self.assertTrue(validation["leaf_provenance_coverage"])
            self.assertEqual(validation["unresolved_count"], 0)
            diff = json.loads(
                (output / "current_test_diff.json").read_text(encoding="utf-8")
            )
            analysis = json.loads(
                (output / "current_test_diff_analysis.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                set(analysis["categories"]),
                {
                    "same",
                    "intentional_derivation",
                    "suspected_current_defect",
                    "new_candidate_defect",
                    "dynamic_only",
                },
            )
            self.assertTrue(diff["entries"])
            self.assertTrue(
                all(
                    entry["classification"] == "CURRENT_ABSENT"
                    for entry in diff["entries"]
                )
            )
            self.assertEqual(
                analysis["suspected_current_view_config_defect_count"], 0
            )
            self.assertFalse(
                analysis[
                    "can_current_runtime_blocker_be_explained_by_view_config_difference"
                ]
            )

    def test_negative_controls_reject_fabrication_and_overclaim(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "view_flatten"
            build_view_flatten_complete_json_regeneration(ROOT, output)
            result = run_negative_controls(ROOT, output)
            self.assertTrue(result["valid"])
            self.assertEqual(result["case_count"], 5)
            self.assertEqual(result["rejected_count"], 5)

    def test_manual_fake_hardware_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "view_flatten"
            build_view_flatten_complete_json_regeneration(ROOT, output)
            fake = output / "complete_json/fake.json"
            fake.write_text('{"enable": 0}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                ViewFlattenRegenerationError,
                "unexpected complete_json target materialized",
            ):
                validate_regeneration_bundle(ROOT, output)


if __name__ == "__main__":
    unittest.main()
