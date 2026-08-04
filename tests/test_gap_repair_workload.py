from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_repair_workload import (
    ADDRESS_BOUND_CONFIG_REL,
    DEFAULT_OUTPUT_REL,
    MAPPING_REL,
    build_address_bound_d_index_config,
    build_gap_repair_workload,
    derive_address_bound_d_index_config,
    validate_address_bound_d_index_config,
    validate_gap_repair_workload,
)


ROOT = Path(__file__).resolve().parents[1]


class GapRepairWorkloadTests(unittest.TestCase):
    def test_address_bound_config_is_exact_four_field_patch(self) -> None:
        config, analysis = derive_address_bound_d_index_config(ROOT)
        self.assertEqual(
            [item["json_path"] for item in analysis["semantic_patches"]],
            [
                "$.dram_loop_configs.LC2.end",
                "$.dram_loop_configs.LC2.last_index",
                "$.dram_loop_configs.LC2.outmost_loop",
                "$.dram_loop_configs.LC2.src_id",
            ],
        )
        self.assertEqual(config["stream_engine"]["stream0"]["base_addr"], "0x0")
        self.assertEqual(config["stream_engine"]["stream1"]["base_addr"], "0x18840")
        self.assertEqual(
            analysis["coverage"]["derived_distinct_transaction_bases"], 256
        )

    def test_published_address_bound_config_validates(self) -> None:
        manifest = validate_address_bound_d_index_config(
            ROOT, ROOT / ADDRESS_BOUND_CONFIG_REL
        )
        self.assertEqual(manifest["strict_validation"]["issue_count"], 0)

    @unittest.skipUnless(
        (ROOT / MAPPING_REL / "bundle_manifest.json").is_file(),
        "address-bound repaired mapping has not been generated",
    )
    def test_repair_workload_rebuild_is_exact(self) -> None:
        published = validate_gap_repair_workload(ROOT, ROOT / DEFAULT_OUTPUT_REL)
        self.assertTrue(
            published["full_rebuild"][
                "planner_encoder_bitstream_execplan_sca_regenerated"
            ]
        )
        self.assertFalse(published["candidate_release"])
        with tempfile.TemporaryDirectory() as temporary:
            rebuilt = Path(temporary) / "workload"
            rebuilt_manifest = build_gap_repair_workload(ROOT, rebuilt)
            self.assertEqual(rebuilt_manifest["tree_sha256"], published["tree_sha256"])
            self.assertEqual(
                rebuilt_manifest["full_rebuild"]["controls"]["runtime_bitstream"][
                    "installed_sha256"
                ],
                published["full_rebuild"]["controls"]["runtime_bitstream"][
                    "installed_sha256"
                ],
            )


if __name__ == "__main__":
    unittest.main()
