from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.requant_single_occurrence_dynamic import (
    CONFIG_ROOT_REL,
    CONTRACT_REL,
    REPORT_REL,
    build_vectors,
    derive_configs,
    materialize_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class RequantSingleOccurrenceDynamicTests(unittest.TestCase):
    def test_two_strict_jsons_are_exact_schedule_derivations(self) -> None:
        guard, round_config, provenance = derive_configs(ROOT)
        self.assertEqual(
            [guard["dram_loop_configs"][f"LC{i}"]["end"] for i in range(3)],
            [1, 4, 4],
        )
        self.assertEqual(
            [
                round_config["dram_loop_configs"][f"LC{i}"]["end"]
                for i in range(3)
            ],
            [1, 4, 1],
        )
        self.assertEqual(
            guard["stream_engine"]["stream0"]["dim_stride"],
            [32, 128, None],
        )
        self.assertEqual(
            guard["stream_engine"]["stream2"]["dim_stride"],
            [32, 128, None],
        )
        self.assertEqual(
            round_config["stream_engine"]["stream0"]["dim_stride"],
            [32, 128, None],
        )
        self.assertEqual(
            round_config["stream_engine"]["stream2"]["dim_stride"],
            [32, 32, None],
        )
        self.assertEqual(len(provenance["guard_changed_leaves"]), 4)
        self.assertEqual(len(provenance["round_changed_leaves"]), 4)
        self.assertTrue(
            provenance["all_other_leaves_byte_semantically_unchanged"]
        )

    def test_vector_covers_all_combined_numeric_boundaries(self) -> None:
        _, round_config, _ = derive_configs(ROOT)
        source, guard, final, coverage = build_vectors(round_config)
        self.assertEqual(source.shape, (2, 4, 8))
        self.assertEqual(source.dtype, np.dtype("int32"))
        self.assertEqual(guard.shape, (2, 4, 8))
        self.assertEqual(guard.dtype, np.dtype("float32"))
        self.assertEqual(final.shape, (2, 4, 8))
        self.assertEqual(final.dtype, np.dtype("uint8"))
        self.assertEqual(coverage["active_slices"], [0, 1])
        self.assertEqual(coverage["physical_slice_instance_count"], 2)
        self.assertEqual(coverage["element_count"], 64)
        self.assertTrue(coverage["slice1_is_slice0_row_rotation"])
        self.assertGreater(coverage["negative_count"], 0)
        self.assertGreater(coverage["minus_one_count"], 0)
        self.assertGreater(coverage["zero_count"], 0)
        self.assertGreater(coverage["positive_count"], 0)
        self.assertEqual(coverage["exact_half_even_tie_count"], 16)
        self.assertEqual(
            coverage["exact_half_even_tie_count_by_slice"], [8, 8]
        )
        self.assertGreater(coverage["tie_round_down_to_even_count"], 0)
        self.assertGreater(coverage["tie_round_up_to_even_count"], 0)
        self.assertGreater(coverage["lower_saturation_count"], 0)
        self.assertGreater(coverage["upper_saturation_count"], 0)
        self.assertEqual(coverage["lane_multiplier_count"], 8)
        self.assertEqual(coverage["magic_vs_independent_mismatch_count"], 0)

    def test_mse4_and_two_stage_handoff_contract_are_complete(self) -> None:
        config_root = ROOT / CONFIG_ROOT_REL
        writes = _load(config_root / "expected_mse4_writes.json")
        lifecycle = _load(config_root / "lifecycle_contract.json")
        self.assertEqual(writes["active_slices"], [0, 1])
        self.assertEqual(writes["total_expected_accepted_write_count"], 20)
        self.assertEqual(
            [
                stage["expected_accepted_write_count_total"]
                for stage in writes["stages"]
            ],
            [16, 4],
        )
        self.assertEqual(
            {
                write["slice_id"]
                for stage in writes["stages"]
                for write in stage["writes"]
            },
            {0, 1},
        )
        self.assertTrue(
            lifecycle["handoff"][
                "stage0_output_equals_stage1_input_address"
            ]
        )
        self.assertEqual(
            lifecycle["handoff"]["stage1_external_preload_count"], 0
        )
        self.assertTrue(
            lifecycle["handoff"]["stage1_start_requires_stage0_comp_finish"]
        )
        self.assertEqual(lifecycle["repeat_num"], 2)
        self.assertEqual(lifecycle["logical_occurrence_count"], 1)
        self.assertEqual(lifecycle["physical_slice_instance_count"], 2)
        self.assertEqual(lifecycle["active_slices"], [0, 1])
        self.assertEqual(
            lifecycle["handoff"]["barrier_scope"], "all active slices"
        )
        self.assertEqual(
            lifecycle["dynamic_acceptance"][
                "mse4_total_accepted_write_beat_count"
            ],
            20,
        )
        self.assertEqual(
            lifecycle["stock_tb_completion_observer"],
            {
                "finish_sampled_slice": 1,
                "mask_aware": False,
                "repeat_num_counts_stages_not_slices": True,
                "required_sampled_slices_enabled": True,
                "start_sampled_slice": 0,
                "tb_or_rtl_modification_authorized": False,
            },
        )

    def test_additional_atomics_are_fail_first_only(self) -> None:
        routing = _load(
            ROOT / CONFIG_ROOT_REL / "first_divergence_routing.json"
        )
        self.assertEqual(
            routing["default_enabled_contracts"],
            ["single-occurrence-two-stage"],
        )
        self.assertEqual(
            set(routing["default_disabled_contracts"]),
            {"guard-only", "round-only", "alias-lifetime"},
        )
        self.assertEqual(
            routing["combined_pass_action"],
            "keep_all_additional_atomic_contracts_disabled",
        )

    def test_checked_assets_match_one_fresh_local_build(self) -> None:
        checked_manifest = _load(ROOT / CONFIG_ROOT_REL / "manifest.json")
        with tempfile.TemporaryDirectory(prefix="requant-atomic-test-") as temp:
            fresh_root = Path(temp) / "bundle"
            fresh_manifest = materialize_bundle(ROOT, fresh_root)
            self.assertEqual(fresh_manifest, checked_manifest)
            for relative, identity in checked_manifest["files"].items():
                path = ROOT / CONFIG_ROOT_REL / relative
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, identity["size_bytes"])
                self.assertEqual(sha256_file(path), identity["sha256"])

    def test_release_boundary_remains_fail_closed(self) -> None:
        manifest = _load(ROOT / CONFIG_ROOT_REL / "manifest.json")
        report = _load(ROOT / REPORT_REL)
        contract = _load(ROOT / CONTRACT_REL)
        self.assertEqual(
            manifest["status"],
            "LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN",
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["server_package"])
        self.assertEqual(report["dynamic_execution_status"], "NOT_RUN")
        self.assertEqual(report["additional_atomic_contracts_enabled"], [])
        self.assertFalse(contract["counts_as_node0001_e4"])
        self.assertFalse(contract["counts_as_node0001_e5"])
        self.assertEqual(
            contract["remaining_blockers"], ["B_REQUANT_SERVER_E4_E5"]
        )


if __name__ == "__main__":
    unittest.main()
