from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.hardware_approval import (
    TARGET_RTL_COMMIT,
    TARGET_RTL_REPOSITORY,
    validate_hardware_approval,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)
from tests.hardware_approval_fixture import valid_hardware_approval


class HardwareApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.architecture = json.loads(
            (root / "contracts/architecture.json").read_text(encoding="utf-8")
        )

    def test_valid_rtl28_structure_sees_complete_candidate_layout_registry(self) -> None:
        approval = valid_hardware_approval()
        approval["physical_objects"]["qparams"]["owner"] = "configuration registers"
        approval["physical_objects"]["qparams"]["address_unit"] = "register field"
        result = validate_hardware_approval(approval, self.architecture)
        self.assertTrue(result["valid"])
        self.assertEqual(
            result["network_profile"], GROUP4X7_BATCH_CHANNEL28_PROFILE
        )
        self.assertEqual(result["slice_count"], 28)
        self.assertTrue(result["clean_elaboration_approved"])
        self.assertTrue(result["layout_evidence_complete"])

    def test_missing_runtime_dump_fails(self) -> None:
        approval = valid_hardware_approval()
        del approval["runtime_protocol"]["dump"]
        with self.assertRaisesRegex(ContractError, "dump"):
            validate_hardware_approval(approval, self.architecture)

    def test_profile_layout_mismatch_fails(self) -> None:
        approval = valid_hardware_approval(GLOBAL_RING28_PROFILE)
        approval["operator_layouts"]["conv"] = (
            "w4_conv_group4x7_28_candidate_v1"
        )
        with self.assertRaisesRegex(ContractError, GLOBAL_RING28_PROFILE):
            validate_hardware_approval(approval, self.architecture)

    def test_unknown_layout_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["operator_layouts"]["conv"] = "made_up_layout"
        with self.assertRaisesRegex(ContractError, "do not match selected profile"):
            validate_hardware_approval(approval, self.architecture)

    def test_short_rtl_commit_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["target_version"]["rtl_commit"] = "abc123"
        with self.assertRaisesRegex(ContractError, "full lowercase Git hash"):
            validate_hardware_approval(approval, self.architecture)

    def test_wrong_rounding_fails(self) -> None:
        approval = deepcopy(valid_hardware_approval())
        approval["numeric_semantics"]["requant"]["rounding"] = "truncate"
        with self.assertRaisesRegex(ContractError, "nearest-even"):
            validate_hardware_approval(approval, self.architecture)

    def test_unexpected_field_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["authority"]["unreviewed_note"] = "must not be silently accepted"
        with self.assertRaisesRegex(ContractError, "unexpected fields"):
            validate_hardware_approval(approval, self.architecture)

    def test_zero_isa_field_width_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["isa"]["field_widths"]["mask"] = 0
        with self.assertRaisesRegex(ContractError, "positive integer"):
            validate_hardware_approval(approval, self.architecture)

    def test_legacy16_slice_count_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["architecture"]["slice_count"] = 16
        with self.assertRaisesRegex(ContractError, "slice_count"):
            validate_hardware_approval(approval, self.architecture)

    def test_legacy_mixed_profile_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["network_profile"] = "mixed"
        with self.assertRaisesRegex(ContractError, "exact profile28 ID"):
            validate_hardware_approval(approval, self.architecture)

    def test_wrong_target_commit_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["target_version"]["rtl_commit"] = "0" * 40
        with self.assertRaisesRegex(ContractError, "must match architecture contract"):
            validate_hardware_approval(approval, self.architecture)

    def test_clean_elaboration_must_be_approved(self) -> None:
        approval = valid_hardware_approval()
        approval["clean_elaboration"]["status"] = "candidate"
        with self.assertRaisesRegex(ContractError, "clean_elaboration.status"):
            validate_hardware_approval(approval, self.architecture)

    def test_schema_constants_match_manual_validator_target(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "schemas/hardware_approval.schema.json").read_text(
                encoding="utf-8"
            )
        )
        properties = schema["properties"]
        self.assertEqual(properties["schema_version"]["const"], "0.2")
        self.assertEqual(
            properties["target_version"]["properties"]["repository"]["const"],
            TARGET_RTL_REPOSITORY,
        )
        self.assertEqual(
            properties["target_version"]["properties"]["rtl_commit"]["const"],
            TARGET_RTL_COMMIT,
        )
        self.assertEqual(properties["architecture"]["properties"]["slice_count"]["const"], 28)
        self.assertEqual(
            properties["architecture"]["properties"]["specialized_array"][
                "properties"
            ]["rows"]["const"],
            8,
        )
        self.assertEqual(
            properties["architecture"]["properties"]["general_array"][
                "properties"
            ]["rows"]["const"],
            4,
        )
        self.assertEqual(
            set(properties["network_profile"]["enum"]),
            {GROUP4X7_BATCH_CHANNEL28_PROFILE, GLOBAL_RING28_PROFILE},
        )
        conditional_profiles = {
            item["if"]["properties"]["network_profile"]["const"]
            for item in schema["allOf"]
        }
        self.assertEqual(
            conditional_profiles,
            {GROUP4X7_BATCH_CHANNEL28_PROFILE, GLOBAL_RING28_PROFILE},
        )


if __name__ == "__main__":
    unittest.main()
