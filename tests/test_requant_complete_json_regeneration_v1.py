from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "requantize_uint8"
)


class RequantCompleteJsonRegenerationV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = json.loads((OUT / "stage_inventory.json").read_text(encoding="utf-8"))
        cls.ledger = json.loads(
            (OUT / "field_provenance_ledger.json").read_text(encoding="utf-8")
        )
        cls.report = json.loads((OUT / "report.json").read_text(encoding="utf-8"))

    def test_all_54_stages_are_covered(self) -> None:
        stages = self.inventory["stages"]
        self.assertEqual(len(stages), 54)
        self.assertEqual(len({stage["request_id"] for stage in stages}), 54)
        self.assertEqual(
            {stage["qparams"]["zero_point_class"] for stage in stages},
            {"ZERO", "EVEN_NONZERO", "ODD_NONZERO"},
        )

    def test_every_stage_is_fail_closed_before_json_emission(self) -> None:
        self.assertEqual(self.report["coverage"]["materialized_strict_json_count"], 0)
        self.assertEqual(
            sorted(path.name for path in (OUT / "complete_json").iterdir()),
            ["index.json"],
        )
        for stage in self.ledger["stages"]:
            self.assertIsNone(stage["materialized_target_json"])
            self.assertGreater(stage["target_required_unresolved_count"], 0)

    def test_ledger_has_required_provenance_fields(self) -> None:
        required = {
            "json_pointer",
            "target_value",
            "origin",
            "source",
            "applicability",
            "exactness_axes",
            "derivation",
            "current_consumer_equation",
            "status",
        }
        for stage in self.ledger["stages"]:
            for section in (
                stage["target_requirement_ledger"],
                stage["reference_leaf_applicability_ledger"],
            ):
                self.assertTrue(section)
                self.assertTrue(all(required <= set(row) for row in section))

    def test_exact_consumer_signatures_are_not_collapsed(self) -> None:
        self.assertEqual(
            self.report["coverage"]["exact_materialized_consumer_signature_class_count"],
            54,
        )
        self.assertEqual(
            len(self.report["equivalence_classes"]["exact_materialized_consumer_signature"]),
            54,
        )

    def test_no_server_package_or_runtime_is_emitted(self) -> None:
        files = [path for path in OUT.rglob("*") if path.is_file()]
        self.assertFalse(any(path.suffix.lower() == ".zip" for path in files))
        self.assertFalse(any(path.name == "PREPARE_AND_RUN.sh" for path in files))
        self.assertFalse(any("rtl" in path.parts for path in files))

    def test_current_card_point_is_not_misclassified_as_config(self) -> None:
        diff = json.loads((OUT / "current_test_diff.json").read_text(encoding="utf-8"))
        self.assertEqual(diff["categories"]["suspected_current_defect"], [])
        self.assertFalse(
            diff["config_explanation_judgement"][
                "current_card_point_explained_by_configuration_difference"
            ]
        )

    def test_negative_controls_fail_closed(self) -> None:
        negative = json.loads(
            (OUT / "validation" / "negative_controls.json").read_text(encoding="utf-8")
        )
        self.assertTrue(negative["all_fail_closed"])
        self.assertTrue(all(case["observed"] == "REJECT" for case in negative["cases"]))


if __name__ == "__main__":
    unittest.main()
