from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from resnet50_pipeline.qlinearadd_stage0_config_only import (
    BYPASS_FIELDS,
    build_configuration,
    validate_contract,
    validate_configuration,
    validate_receipts,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "configs/qlinearadd_stage0_config_only/"
    "qlinearadd_stage0_config_only_v1.json"
)
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "qlinearadd_stage0_config_only_contract_v1.json"
)


class QLinearAddStage0ConfigOnlyTests(unittest.TestCase):
    def test_receipt_refresh_and_replay_are_noncomputational(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        report = validate_receipts(value, ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertFalse(report["numeric_analysis_repeated"])
        self.assertEqual(report["current_match_dependencies_checked"], 4)
        self.assertEqual(report["replay_nodes_checked"], ["node-0076"])
        node0076 = next(
            item for item in value["instances"] if item["node_id"] == "node-0076"
        )
        replay = node0076["physical_stages"][2]["inputs"][1]["replay"]
        self.assertEqual(
            replay["source_producer"], "hwop-0076-00:B_DEQUANT"
        )
        self.assertEqual(
            replay["source_tensor_identity"], "hwop-0076-00:B_SCALED"
        )
        self.assertFalse(replay["host_precomputed_internal_tensor"])

    def test_materialized_configuration_is_exact_and_tail_blocked(self) -> None:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        report = validate_configuration(value, ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["coverage"]["instances"], 17)
        self.assertEqual(report["coverage"]["physical_stages"], 51)
        self.assertEqual(report["coverage"]["scratch_allocations"], 51)
        self.assertEqual(report["coverage"]["branch_scalar_values_checked"], 8704)
        self.assertEqual(report["coverage"]["fp32_sum_scalar_pairs_checked"], 1114112)
        self.assertEqual(report["coverage"]["node0076_replay_elements_checked"], 16000)
        self.assertIsNone(report["claim"])
        self.assertFalse(report["dependency_on_quant_tail"]["materialized"])
        self.assertEqual(set(value["bypass_annotation"]), set(BYPASS_FIELDS))
        self.assertFalse(value["candidate_release"])
        node0076 = next(
            item for item in value["instances"] if item["node_id"] == "node-0076"
        )
        b_dequant = node0076["physical_stages"][1]
        self.assertEqual(b_dequant["occurrence"]["count"], 63)
        self.assertEqual(b_dequant["occurrence"]["tail_elements"], 8)
        self.assertEqual(
            b_dequant["final_output_byte_coverage"]["tail_valid_bytes"], 32
        )
        self.assertEqual(
            b_dequant["final_output_byte_coverage"]["unique_written_byte_count"],
            4000,
        )

    def test_checked_in_config_is_reproducible(self) -> None:
        checked_in = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(checked_in, build_configuration(ROOT))

    def test_contract_carries_same_seven_field_annotation(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        report = validate_contract(contract, ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(
            contract["bypass_annotation"], config["bypass_annotation"]
        )
        self.assertEqual(set(contract["bypass_annotation"]), set(BYPASS_FIELDS))
        self.assertIsNone(contract["claim"])

    def test_active_rule_drift_blocks(self) -> None:
        value = build_configuration(ROOT)
        value["current_match_rule_dependencies"][0]["sha256"] = "0" * 64
        report = validate_configuration(value, ROOT)
        self.assertFalse(report["valid"])
        self.assertIn(
            "current-match rule SHA mismatch: .agents/rules/算子配置规则.md",
            report["errors"],
        )

    def test_native_reassociation_reintroduction_blocks(self) -> None:
        value = build_configuration(ROOT)
        value["instances"][0]["physical_stages"][0]["ga"]["operation_order"] = [
            "mul(input_f32, scale_f32)",
            "add(previous_f32, negative_zero_point_times_scale_f32)",
        ]
        report = validate_configuration(value, ROOT)
        self.assertFalse(report["valid"])
        self.assertIn(
            "materialized configuration differs from typed-source rebuild",
            report["errors"],
        )

    def test_node0076_replay_copy_mutation_blocks(self) -> None:
        value = build_configuration(ROOT)
        node = next(item for item in value["instances"] if item["node_id"] == "node-0076")
        node["physical_stages"][2]["inputs"][1]["replay"][
            "materialized_16x_copy"
        ] = True
        report = validate_configuration(value, ROOT)
        self.assertFalse(report["valid"])
        self.assertIn(
            "node0076 illegally materializes a 16x B copy",
            report["errors"],
        )

    def test_final_output_byte_coverage_mutation_blocks(self) -> None:
        value = build_configuration(ROOT)
        stage = value["instances"][0]["physical_stages"][2]
        stage["final_output_byte_coverage"]["unique_written_byte_count"] -= 16
        report = validate_configuration(value, ROOT)
        self.assertFalse(report["valid"])
        self.assertIn(
            f"{stage['stage_id']}: final output byte coverage mismatch",
            report["errors"],
        )

    def test_standalone_cli_from_repository_root(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/validate_qlinearadd_stage0_config_only.py",
                "configs/qlinearadd_stage0_config_only/"
                "qlinearadd_stage0_config_only_v1.json",
                "--contract",
                "contracts/operator_config/"
                "qlinearadd_stage0_config_only_contract_v1.json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"])
        self.assertIsNone(report["claim"])
        self.assertEqual(report["package_release"]["status"], (
            "NOT_GENERATED_NO_LEASE_AND_COMPLETE_QADD_UNCLOSED"
        ))


if __name__ == "__main__":
    unittest.main()
