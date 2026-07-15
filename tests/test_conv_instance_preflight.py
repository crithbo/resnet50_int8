from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.conv_instance import build_conv_target_request
from resnet50_pipeline.conv_instance_preflight import (
    ConvInstancePreflightError,
    validate_conv_instance_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "artifacts" / "w5" / "hwop-0008-00" / "preflight.json"


class ConvInstancePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request = build_conv_target_request(ROOT, "node-0008")
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_candidate_identity_encoder_and_config_bindings_are_exact(self) -> None:
        report = self.report
        self.assertEqual(report["identity"]["node_id"], "node-0008")
        self.assertEqual(
            report["identity"]["hw_op_ids"],
            ["hwop-0008-00", "hwop-0008-01"],
        )
        self.assertEqual(
            report["instance_spec"]["geometry"]["activation_shape"],
            [16, 256, 56, 56],
        )
        self.assertEqual(
            report["instance_spec"]["geometry"]["output_shape"],
            [16, 64, 56, 56],
        )
        self.assertEqual(report["instance_spec"]["target"]["c_tile"], 64)
        self.assertEqual(report["instance_spec"]["target"]["k_tile"], 16)
        self.assertEqual(report["official_encoder"]["connection_count"], 46)
        self.assertEqual(report["official_encoder"]["constraint_cost"], 0)
        self.assertTrue(report["official_encoder"]["repeat_outputs_identical"])
        self.assertEqual(report["configs"]["requant_manifest"]["shard_count"], 8)
        validate_conv_instance_preflight(report, self.request)

    def test_four_k_segments_and_three_pd_scopes_are_bit_exact(self) -> None:
        tile = self.report["first_tile"]
        self.assertEqual(
            [item["phase"] for item in tile["k_lifecycle"]],
            ["first", "middle", "middle", "last"],
        )
        self.assertEqual(
            sum(item["channel_count"] for item in tile["k_lifecycle"]), 256
        )
        comparisons = self.report["config_bound_comparison"]["ordered_comparisons"]
        self.assertEqual(
            [item["name"] for item in comparisons],
            ["single_coordinate", "first_tile", "full_operator"],
        )
        for item in comparisons:
            for port in ("P", "D"):
                self.assertEqual(item[port]["mismatch_count"], 0)
                self.assertEqual(item[port]["actual_sha256"], item[port]["golden_sha256"])
        self.assertEqual(
            len(self.report["config_bound_comparison"]["physical_writebacks"]), 28
        )

    def test_report_cannot_overclaim_hardware_or_accept_config_drift(self) -> None:
        changed = deepcopy(self.report)
        changed["gate_state"]["hardware_passed"] = True
        with self.assertRaisesRegex(ConvInstancePreflightError, "gate boundary"):
            validate_conv_instance_preflight(changed, self.request)

        changed = deepcopy(self.report)
        changed["configs"]["requant_manifest"]["shard_count"] = 7
        with self.assertRaisesRegex(ConvInstancePreflightError, "config binding"):
            validate_conv_instance_preflight(changed, self.request)


if __name__ == "__main__":
    unittest.main()
