from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.hardware_approval import (
    APPROVAL_SCHEMA_VERSION,
    TARGET_RTL_COMMIT,
    TARGET_RTL_REPOSITORY,
    validate_hardware_approval,
    validate_hardware_approval_file,
)
from resnet50_pipeline.profile28 import DEEPSEEK_HYBRID28_PROFILE
from tests.hardware_approval_fixture import valid_hardware_approval


class HardwareApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.architecture_path = cls.root / "contracts/architecture.json"
        cls.architecture = json.loads(cls.architecture_path.read_text(encoding="utf-8"))

    def test_valid_synthetic_structure_uses_hybrid_profile_without_elaboration_claim(self) -> None:
        result = validate_hardware_approval(valid_hardware_approval(), self.architecture)
        self.assertTrue(result["valid"])
        self.assertEqual(result["network_profile"], DEEPSEEK_HYBRID28_PROFILE)
        self.assertEqual(result["slice_count"], 28)
        self.assertTrue(result["hardware_baseline_confirmed"])
        self.assertFalse(result["clean_elaboration_claimed"])
        self.assertTrue(result["layout_evidence_complete"])
        self.assertFalse(result["referenced_contracts_verified"])
        self.assertFalse(result["gate_authority_eligible"])

    def test_checked_in_approval_verifies_named_decision_and_contract_layers(self) -> None:
        result = validate_hardware_approval_file(
            self.root / "contracts/hardware_approval.json", self.architecture_path
        )
        self.assertTrue(result["referenced_contracts_verified"])
        self.assertTrue(result["gate_authority_eligible"])
        self.assertEqual(result["authority_kind"], "project_operator")

    def test_fake_elaboration_claim_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["baseline_confirmation"]["elaboration_log_claimed"] = True
        with self.assertRaisesRegex(ContractError, "must not fabricate"):
            validate_hardware_approval(approval, self.architecture)

    def test_missing_w5_deferral_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["deferred_to_w5"].remove("typed_qparams_to_register_or_stream_binding")
        with self.assertRaisesRegex(ContractError, "deferred_to_w5"):
            validate_hardware_approval(approval, self.architecture)

    def test_profile_is_not_a_network_wide_group_global_choice(self) -> None:
        approval = valid_hardware_approval()
        approval["network_profile"] = "w4_global_ring28_candidate_v1"
        with self.assertRaisesRegex(ContractError, "hybrid28"):
            validate_hardware_approval(approval, self.architecture)

    def test_operator_domain_mismatch_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["operator_bindings"]["conv"]["communication_domain"] = "low28"
        with self.assertRaisesRegex(ContractError, "selected profile"):
            validate_hardware_approval(approval, self.architecture)

    def test_unknown_layout_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["operator_bindings"]["conv"]["layout_id"] = "made_up_layout"
        with self.assertRaisesRegex(ContractError, "selected profile"):
            validate_hardware_approval(approval, self.architecture)

    def test_short_rtl_commit_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["target_version"]["rtl_commit"] = "abc123"
        with self.assertRaisesRegex(ContractError, "must be"):
            validate_hardware_approval(approval, self.architecture)

    def test_unexpected_authority_field_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["authority"]["unreviewed_note"] = "must not be silently accepted"
        with self.assertRaisesRegex(ContractError, "unexpected fields"):
            validate_hardware_approval(approval, self.architecture)

    def test_legacy16_slice_count_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["architecture"]["slice_count"] = 16
        with self.assertRaisesRegex(ContractError, "slice_count"):
            validate_hardware_approval(approval, self.architecture)

    def test_wrong_target_commit_fails(self) -> None:
        approval = valid_hardware_approval()
        approval["target_version"]["rtl_commit"] = "0" * 40
        with self.assertRaisesRegex(ContractError, "rtl_commit"):
            validate_hardware_approval(approval, self.architecture)

    def test_project_operator_cannot_bypass_reference_hashes(self) -> None:
        approval = json.loads(
            (self.root / "contracts/hardware_approval.json").read_text(encoding="utf-8")
        )
        approval["contract_layers"]["common_baseline"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hardware_approval.json"
            path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "file/hash mismatch"):
                validate_hardware_approval_file(path, self.architecture_path)

    def test_schema_constants_match_manual_validator_target(self) -> None:
        schema = json.loads(
            (self.root / "schemas/hardware_approval.schema.json").read_text(encoding="utf-8")
        )
        properties = schema["properties"]
        self.assertEqual(properties["schema_version"]["const"], APPROVAL_SCHEMA_VERSION)
        self.assertEqual(
            properties["target_version"]["properties"]["repository"]["const"],
            TARGET_RTL_REPOSITORY,
        )
        self.assertEqual(
            properties["target_version"]["properties"]["rtl_commit"]["const"],
            TARGET_RTL_COMMIT,
        )
        self.assertEqual(properties["architecture"]["properties"]["slice_count"]["const"], 28)
        self.assertEqual(properties["network_profile"]["const"], DEEPSEEK_HYBRID28_PROFILE)
        self.assertNotIn("allOf", schema)


if __name__ == "__main__":
    unittest.main()
