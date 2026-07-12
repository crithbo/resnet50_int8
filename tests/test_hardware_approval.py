from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.hardware_approval import validate_hardware_approval
from tests.hardware_approval_fixture import valid_hardware_approval


class HardwareApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.architecture = json.loads(
            (root / "contracts/architecture.json").read_text(encoding="utf-8")
        )

    def test_valid_batch_profile_passes(self) -> None:
        approval = valid_hardware_approval()
        approval["physical_objects"]["qparams"]["owner"] = "configuration registers"
        approval["physical_objects"]["qparams"]["address_unit"] = "register field"
        result = validate_hardware_approval(approval, self.architecture)
        self.assertTrue(result["valid"])
        self.assertEqual(result["network_profile"], "batch")

    def test_missing_runtime_dump_fails(self) -> None:
        approval = valid_hardware_approval()
        del approval["runtime_protocol"]["dump"]
        with self.assertRaisesRegex(ContractError, "dump"):
            validate_hardware_approval(approval, self.architecture)

    def test_profile_layout_mismatch_fails(self) -> None:
        approval = valid_hardware_approval("ring_channel")
        approval["operator_layouts"]["conv"] = "w4_conv_batch16_candidate_v1"
        with self.assertRaisesRegex(ContractError, "ring_channel"):
            validate_hardware_approval(approval, self.architecture)

    def test_unknown_layout_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["operator_layouts"]["conv"] = "made_up_layout"
        with self.assertRaisesRegex(ContractError, "unknown layout"):
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


if __name__ == "__main__":
    unittest.main()
