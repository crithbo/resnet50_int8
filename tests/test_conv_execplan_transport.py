from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_execplan_transport import (
    ConvExecplanTransportError,
    build_conv_execplan_request,
    build_conv_execplan_transport_contract,
    validate_conv_execplan_request,
    validate_conv_execplan_transport_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class ConvExecplanTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.first = build_conv_execplan_request(ROOT, "node-0004")

    def test_same_node_id_cli_contract_builds_first_e1_and_e2(self) -> None:
        expected = {
            "node-0004": (64, 8, 11),
            "node-0008": (64, 8, 11),
            "node-0003": (256, 32, 35),
        }
        for node_id, (channels, shards, artifacts) in expected.items():
            with self.subTest(node_id=node_id):
                value = build_conv_execplan_request(ROOT, node_id)
                report = validate_conv_execplan_request(
                    value, ROOT, expected_node_id=node_id
                )
                self.assertEqual(report["requant_channel_count"], channels)
                self.assertEqual(report["requant_shard_count"], shards)
                self.assertEqual(report["config_artifact_count"], artifacts)
                self.assertEqual(
                    report["n2n"],
                    {
                        "mem_loop": 4,
                        "src_slice_sel": 1,
                        "dst_slice_sel": 1,
                        "ping_pong": 0,
                    },
                )
                accumulate, requant = value["operators"]
                self.assertEqual(accumulate["instance_id"], requant["instance_id"])
                relationship = requant["attributes"]["artifact_relationship"]
                self.assertEqual(
                    relationship["cardinality"], "one_manifest_to_many_shards"
                )
                self.assertEqual(len(relationship["member_artifact_ids"]), shards)

    def test_missing_scale_zero_point_or_bias_fails_before_execution(self) -> None:
        mutations = (
            (1, "x_scale"),
            (0, "x_zero_point"),
            (0, "bias"),
        )
        for operator_index, name in mutations:
            value = copy.deepcopy(self.first)
            del value["operators"][operator_index]["constants"][name]
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    ConvExecplanTransportError, "constant coverage differs"
                ):
                    validate_conv_execplan_request(value, ROOT)

    def test_axis_loss_float_truncation_old16_and_sha_drift_fail_closed(self) -> None:
        axis_loss = copy.deepcopy(self.first)
        axis_loss["operators"][1]["constants"]["w_scale"]["axis"] = None
        with self.assertRaisesRegex(ConvExecplanTransportError, "axis was lost"):
            validate_conv_execplan_request(axis_loss, ROOT)

        float_truncation = copy.deepcopy(self.first)
        float_truncation["operators"][1]["constants"]["w_scale"]["values"][0] = 0
        with self.assertRaisesRegex(ConvExecplanTransportError, "JSON float"):
            validate_conv_execplan_request(float_truncation, ROOT)

        old16 = copy.deepcopy(self.first)
        old16["used_slices"] = "0b1111111111111111"
        for operator in old16["operators"]:
            operator["used_slices"] = "0b1111111111111111"
            operator["attributes"]["target"]["slice_count"] = 16
        with self.assertRaisesRegex(ConvExecplanTransportError, "28-slice"):
            validate_conv_execplan_request(old16, ROOT)

        sha_drift = copy.deepcopy(self.first)
        sha_drift["operators"][1]["config_artifacts"][1]["raw_text"] += " "
        with self.assertRaisesRegex(ConvExecplanTransportError, "sha256"):
            validate_conv_execplan_request(sha_drift, ROOT)

    def test_w5_closure_contract_does_not_rewrite_approved_w4_snapshots(self) -> None:
        value = build_conv_execplan_transport_contract(ROOT)
        validate_conv_execplan_transport_contract(value, ROOT)
        self.assertEqual(value["status"], "resolved_for_closed_conv_instances")
        self.assertEqual(
            [item["node_id"] for item in value["instances"]],
            ["node-0004", "node-0008", "node-0003"],
        )
        self.assertTrue(
            all(item["unchanged"] for item in value["approved_w4_snapshots"])
        )
        self.assertTrue(
            value["boundary"]["conv_shape_family_parallel_expansion_allowed"]
        )
        checked_in = ROOT / "contracts" / "conv_execplan_transport.json"
        self.assertEqual(
            checked_in.read_text(encoding="utf-8"),
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )


if __name__ == "__main__":
    unittest.main()
