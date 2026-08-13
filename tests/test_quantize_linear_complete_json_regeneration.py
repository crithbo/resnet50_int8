from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.quantize_linear_complete_json_regeneration import (
    ARTIFACT_REL,
    QuantizeCompleteJsonError,
    build_artifacts,
    validate_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


class QuantizeLinearCompleteJsonRegenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.output = ROOT / ARTIFACT_REL
        build_artifacts(ROOT, cls.output)
        cls.validation = validate_artifacts(ROOT, cls.output)

    def test_covers_all_two_stages_and_two_consumer_signatures(self) -> None:
        self.assertEqual(self.validation["stage_count"], 2)
        self.assertEqual(self.validation["equivalence_class_count"], 2)

    def test_full_source_leaf_ledger_is_fail_closed(self) -> None:
        self.assertEqual(self.validation["ledger_entry_count"], 1032)
        self.assertGreater(self.validation["unresolved_count"], 0)
        self.assertEqual(self.validation["materialized_target_count"], 0)

    def test_int32_template_is_not_fp32_quantize_authority(self) -> None:
        references = json.loads(
            (self.output / "reference_applicability.json").read_text(encoding="utf-8")
        )
        quant = next(
            item
            for item in references["selected_references"]
            if item["template_id"] == "quant_from_buffer_int32MN_uint8MN"
        )
        self.assertEqual(quant["self_instance_grade"], "A")
        self.assertEqual(quant["target_grade"], "C")
        self.assertEqual(references["reuse_class"], "STRUCTURE_OR_PRIMITIVE_ONLY")

    def test_node0074_bypass_does_not_close_generic_divider(self) -> None:
        report = json.loads(
            (self.output / "report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["node0074_boundary"]["reuse_class"], "APPROVED_EQUIVALENT")
        self.assertFalse(report["node0074_boundary"]["generic_divider_blocker_closed"])
        self.assertEqual(report["package_release"], "NONE")

    def test_public_gate_binds_both_lowering_stages_once(self) -> None:
        self.assertEqual(self.validation["public_candidate_contract_count"], 2)
        self.assertEqual(
            self.validation["public_family_set_expected_stage_count"], 2
        )
        self.assertEqual(
            self.validation["public_family_set_covered_stage_count"], 2
        )
        self.assertFalse(self.validation["public_family_set_complete"])

    def test_public_blocked_contracts_are_structurally_valid(self) -> None:
        self.assertTrue(
            self.validation["public_candidate_validator_expected_fail_closed"]
        )

    def test_negative_control_unresolved_origin_removal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "quantize_linear"
            shutil.copytree(self.output, copied)
            ledger_path = copied / "field_provenance_ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            first = next(
                item for item in ledger["records"] if item["origin"] == "UNRESOLVED"
            )
            first["origin"] = "MODEL_DERIVED"
            ledger_path.write_text(
                json.dumps(ledger, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(QuantizeCompleteJsonError):
                validate_artifacts(ROOT, copied)

    def test_negative_control_target_json_emission_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "quantize_linear"
            shutil.copytree(self.output, copied)
            leaked = copied / "complete_json" / "hwop-0000-00.json"
            leaked.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(QuantizeCompleteJsonError):
                validate_artifacts(ROOT, copied)


if __name__ == "__main__":
    unittest.main()
