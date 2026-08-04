from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_rule_extractor import (
    build_operator_config_rule_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


class OperatorConfigRuleExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_operator_config_rule_evidence(ROOT)

    def test_maxpool_pair_proves_schedule_not_scalar_template_fill(self) -> None:
        pair = next(
            item
            for item in self.value["pairs"]
            if item["relation"] == "same_operator_family_different_spatial_shape"
        )
        paths = {item["path"] for item in pair["differences"]}
        self.assertIn("$.dram_loop_configs.LC1.end", paths)
        self.assertIn("$.buffer_loop_configs.GROUP0.ROW_LC.src_id", paths)
        self.assertTrue(pair["topology_changes"])
        self.assertFalse(pair["relocation_only"])

    def test_server_instances_are_compared_to_source_templates(self) -> None:
        pairs = [
            item
            for item in self.value["pairs"]
            if item["relation"] == "source_template_to_server_package_instance"
        ]
        self.assertGreaterEqual(len(pairs), 10)
        self.assertTrue(any(item["difference_count"] > 0 for item in pairs))

    def test_inference_is_fail_closed(self) -> None:
        policy = self.value["inference_policy"]
        self.assertTrue(policy["do_not_interpolate_register_values_blindly"])
        self.assertTrue(policy["every_rule_must_reproduce_known_configs"])


if __name__ == "__main__":
    unittest.main()
