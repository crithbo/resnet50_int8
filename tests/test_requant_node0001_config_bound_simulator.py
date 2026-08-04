from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file
from resnet50_pipeline.requant_config_bound_simulator import (
    CONTRACT_RELATIVE,
    OUTPUT_RELATIVE,
    build_config_bound_report,
)


ROOT = Path(__file__).resolve().parents[1]


class RequantNode0001ConfigBoundSimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_config_bound_report(ROOT)

    def test_final_json_bound_execution_is_bit_exact(self) -> None:
        report = self.report
        self.assertEqual(
            report["status"],
            "CONFIG_BOUND_SIMULATOR_E2_COMPLETE_HARDWARE_PENDING",
        )
        self.assertEqual(report["source_identity"]["final_json_count"], 48)
        self.assertEqual(report["lifecycle"]["occurrence_count"], 24)
        self.assertEqual(report["lifecycle"]["stage_count"], 48)
        self.assertEqual(report["numeric"]["golden_mismatch_count"], 0)
        self.assertEqual(
            report["numeric"]["native_activation_round_mismatch_count"], 0
        )
        self.assertEqual(
            report["numeric"]["cgra_round_reference_mismatch_count"], 0
        )
        self.assertTrue(report["numeric"]["bit_exact"])

    def test_layout_inverse_and_alias_coverage_are_complete(self) -> None:
        layout = self.report["physical_layout"]
        self.assertEqual(layout["active_slice_execution_count"], 128)
        self.assertEqual(layout["unique_final_d_region_count"], 128)
        self.assertEqual(layout["unique_guard_alias_region_count"], 28)
        self.assertEqual(layout["logical_sample_channel_coverage_min"], 1)
        self.assertEqual(layout["logical_sample_channel_coverage_max"], 1)
        self.assertEqual(
            self.report["lifecycle"]["consumer_external_preload_count"], 0
        )

    def test_hardware_comparison_remains_fail_closed(self) -> None:
        comparisons = self.report["comparisons"]
        self.assertEqual(
            comparisons["golden_vs_config_bound_simulator"]["status"], "PASS"
        )
        self.assertEqual(
            comparisons["golden_vs_stock_rtl_hardware"]["status"],
            "EVIDENCE_MISSING",
        )
        self.assertEqual(
            comparisons["config_bound_simulator_vs_stock_rtl_hardware"][
                "status"
            ],
            "EVIDENCE_MISSING",
        )
        self.assertFalse(self.report["candidate_release"])
        self.assertEqual(
            self.report["remaining_blockers"], ["B_REQUANT_SERVER_E4_E5"]
        )

    def test_checked_in_report_and_contract_are_current(self) -> None:
        report_path = ROOT / OUTPUT_RELATIVE
        contract_path = ROOT / CONTRACT_RELATIVE
        checked_report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(checked_report, self.report)
        content_hash = checked_report.pop("report_content_sha256")
        self.assertEqual(
            content_hash,
            __import__("hashlib").sha256(
                canonical_json_bytes(checked_report)
            ).hexdigest(),
        )
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["artifact"]["sha256"], sha256_file(report_path))
        contract_hash = contract.pop("contract_content_sha256")
        self.assertEqual(
            contract_hash,
            __import__("hashlib").sha256(
                canonical_json_bytes(contract)
            ).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
