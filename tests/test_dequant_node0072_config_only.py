from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.dequant_node0072_config_only import (
    CONFIG_RELATIVE,
    CONTRACT_RELATIVE,
    REPORT_RELATIVE,
    Node0072ConfigOnlyError,
    _address_lifetime_audit,
    _materialized_leaf_audit,
    bypass_annotation,
    input_replay_contract,
    numeric_evidence,
    validate_config,
)
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]


class Node0072ConfigOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads((ROOT / REPORT_RELATIVE).read_text(encoding="utf-8"))
        cls.contract = json.loads(
            (ROOT / CONTRACT_RELATIVE).read_text(encoding="utf-8")
        )

    def test_bypass_annotation_has_all_seven_fields(self) -> None:
        annotation = bypass_annotation()
        expected = {
            "bypass_reason",
            "contradicted_or_missing_native_path",
            "exact_equivalence_scope",
            "materialized_configuration_mechanism",
            "performance_and_resource_cost",
            "unresolved_production_blocker",
            "claim_boundary",
        }
        self.assertTrue(expected.issubset(annotation))
        self.assertEqual(
            annotation["baseline_classification"],
            "CONFIG_ONLY_CORRECTNESS_BASELINE",
        )
        self.assertEqual(self.report["bypass_annotation"], annotation)
        self.assertEqual(self.contract["bypass_annotation"], annotation)

    def test_real_node0072_numeric_domain_is_bit_exact(self) -> None:
        numeric = numeric_evidence(ROOT)
        self.assertTrue(numeric["bit_exact"])
        self.assertEqual(numeric["two_stage_vs_golden_bit_mismatch_count"], 0)
        self.assertEqual(numeric["single_multiply_vs_golden_bit_mismatch_count"], 0)
        self.assertEqual(
            numeric["golden_sha256"],
            "9430e90815858319eb2e08f610a54779bb12a78b7313ece27a92c5042d08018e",
        )

    def test_final_config_and_materialized_chain_are_closed(self) -> None:
        config = json.loads((ROOT / CONFIG_RELATIVE).read_text(encoding="utf-8"))
        facts = validate_config(config)
        self.assertEqual(facts["hardware_shape_cwh"], [16, 74, 1])
        self.assertTrue(facts["two_stage_ga_exact"])
        self.assertEqual(self.report["mapping_bitstream"]["placement_violations"], 0)
        self.assertTrue(
            self.report["execplan_sca"]["machine_explanation_bit_exact"]
        )
        self.assertTrue(
            self.report["address_lifetime"]["a_d_regions_non_overlapping"]
        )
        self.assertEqual(
            self.report["address_lifetime"]["sca_d_lines_per_slice"], 296
        )
        leaf = self.report["materialized_nonbase_field_ownership"]
        self.assertEqual(leaf["static_to_materialized_leaf_diff_count"], 10)
        self.assertEqual(leaf["planner_base_field_diff_count"], 2)
        self.assertEqual(leaf["nonbase_field_diff_count"], 8)
        self.assertEqual(leaf["unexpected_diff_count"], 0)
        self.assertTrue(leaf["all_diff_paths_declared"])
        coverage = self.report["address_lifetime"][
            "final_materialized_output_coverage"
        ]
        self.assertEqual(coverage["covered_byte_count_per_slice"], 4736)
        self.assertEqual(coverage["sca_d_bytes_per_slice"], 4736)
        self.assertTrue(coverage["coverage_complete"])
        self.assertTrue(coverage["coverage_unique"])

    def test_config_bound_simulator_is_physical_and_bit_exact(self) -> None:
        simulator = self.report["config_bound_simulator"]
        self.assertEqual(simulator["physical_d_slice_count"], 28)
        self.assertEqual(simulator["physical_d_bytes_per_slice"], 4736)
        self.assertEqual(simulator["bit_mismatch_count"], 0)
        self.assertTrue(simulator["bit_exact"])
        self.assertTrue(simulator["padding_positive_zero"])
        self.assertTrue(simulator["consumes_final_address_bound_json"])
        self.assertTrue(simulator["consumes_final_bitstream_and_mapping_identity"])
        self.assertTrue(simulator["consumes_execplan_sca_sca_d"])
        self.assertTrue(simulator["consumes_physical_layout_a"])

    def test_claim_remains_local_and_fail_closed(self) -> None:
        self.assertEqual(
            self.report["status"], "CONFIG_ONLY_CORRECTNESS_BASELINE"
        )
        self.assertFalse(self.report["candidate_release"])
        self.assertFalse(self.report["formal_target_instance_allowed"])
        self.assertFalse(self.report["run"]["server_package_generated"])
        self.assertFalse(self.report["run"]["server_files_inspected"])
        self.assertFalse(self.report["run"]["server_run"])
        self.assertFalse(self.contract["gates"]["hardware_evidence"])
        self.assertFalse(self.contract["gates"]["production_release"])

    def test_input_replay_does_not_cross_computation_boundary(self) -> None:
        replay = input_replay_contract(ROOT)
        self.assertEqual(replay, self.report["input_replay_contract"])
        self.assertEqual(replay, self.contract["input_replay_contract"])
        self.assertEqual(replay["source_producer"]["node_id"], "node-0071")
        self.assertFalse(replay["host_precomputed_internal_tensor"])
        self.assertFalse(replay["host_precomputed_final_output"])
        self.assertFalse(replay["dtype_or_value_transform_during_replay"])

    def test_two_isolated_materializations_are_identical(self) -> None:
        reproducibility = self.report[
            "isolated_materialization_reproducibility"
        ]
        self.assertEqual(reproducibility["isolated_run_count"], 2)
        self.assertTrue(reproducibility["semantic_product_hashes_identical"])
        self.assertTrue(reproducibility["normalized_request_identical"])

    def test_node0073_handoff_is_exact_and_integrated_binding_stays_open(self) -> None:
        handoff = self.report["node0073_integrated_binding_handoff"]
        self.assertEqual(handoff, self.contract["node0073_integrated_binding_handoff"])
        self.assertEqual(
            handoff["logical_contract"]["byte_strides"], [8192, 4, 4, 4]
        )
        self.assertEqual(handoff["logical_contract"]["logical_span_bytes"], 131072)
        self.assertEqual(
            handoff["final_written_byte_coverage"]["logical_valid_bytes"], 131072
        )
        self.assertEqual(
            handoff["final_written_byte_coverage"]["padding_bytes"], 1536
        )
        self.assertTrue(
            handoff["final_write_completion"][
                "static_validator_completion_path_accepted"
            ]
        )
        self.assertFalse(
            handoff["final_write_completion"][
                "integrated_node0072_to_node0073_lifetime_accepted"
            ]
        )
        self.assertEqual(handoff["integrated_binding_status"], "UNRESOLVED")

    def test_machine_contract_self_hash_and_artifact_identity(self) -> None:
        contract = dict(self.contract)
        content_hash = contract.pop("contract_content_sha256")
        self.assertEqual(
            content_hash,
            __import__("hashlib").sha256(canonical_json_bytes(contract)).hexdigest(),
        )
        self.assertEqual(
            self.contract["artifact"]["sha256"], sha256_file(ROOT / REPORT_RELATIVE)
        )

    def test_materialized_nonbase_drift_fails_closed(self) -> None:
        static = json.loads((ROOT / CONFIG_RELATIVE).read_text(encoding="utf-8"))
        final_relative = self.report["source_identity"][
            "final_address_bound_config"
        ]["path"]
        materialized = json.loads(
            (ROOT / final_relative).read_text(encoding="utf-8")
        )
        corrupted = deepcopy(materialized)
        corrupted["stream_engine"]["stream2"]["dim_stride"][1] = 256
        with self.assertRaises(Node0072ConfigOnlyError):
            _materialized_leaf_audit(static, corrupted)

    def test_final_output_coverage_regression_fails_closed(self) -> None:
        final_relative = self.report["source_identity"][
            "final_address_bound_config"
        ]["path"]
        materialized = json.loads(
            (ROOT / final_relative).read_text(encoding="utf-8")
        )
        corrupted = deepcopy(materialized)
        corrupted["stream_engine"]["stream2"]["dim_stride"][1] = 256
        sca = json.loads(
            (ROOT / self.report["source_identity"]["sca"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        sca_d = json.loads(
            (ROOT / self.report["source_identity"]["sca_d"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        with self.assertRaises(Node0072ConfigOnlyError):
            _address_lifetime_audit(corrupted, sca, sca_d)


if __name__ == "__main__":
    unittest.main()
