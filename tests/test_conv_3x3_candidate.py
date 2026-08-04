from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.conv28_layout import (
    CONV28_HARDWARE_LAYOUT_ABI,
    QLinearConvPhysicalLayout,
)
from resnet50_pipeline.conv_execplan_transport import (
    build_conv_execplan_request,
    validate_conv_execplan_request,
)
from resnet50_pipeline.conv_instance import build_conv_target_request
from resnet50_pipeline.conv_sa_contract import validate_conv_3x3_sa_contract


ROOT = Path(__file__).resolve().parents[1]


class Conv3x3CandidateTests(unittest.TestCase):
    def test_node0005_checked_config_is_the_reviewed_3x3_contract(self) -> None:
        request = build_conv_target_request(ROOT, "node-0005")
        config = json.loads(request.accumulate_config_path.read_text(encoding="utf-8"))
        report = validate_conv_3x3_sa_contract(
            config,
            output_height=56,
            output_width=56,
            c_quartets=4,
            k_blocks=2,
            halo_width_padded=64,
        )
        evidence = json.loads(
            (request.accumulate_config_path.parent / "encoder_evidence.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(report["status"], "static_3x3_sa_contract_pass")
        self.assertEqual(evidence["connection_count"], 42)
        self.assertEqual(set(report["stream_transaction_bytes"].values()), {32})
        self.assertEqual(report["high_ring_steps"], 4)

    def test_explicit_halo_round_trip_and_coordinate_mapping(self) -> None:
        rng = np.random.default_rng(5)
        activation = rng.integers(0, 256, size=(16, 64, 4, 8), dtype=np.uint8)
        weight = rng.integers(-128, 128, size=(64, 64, 3, 3), dtype=np.int8)
        accumulator = rng.integers(
            -(1 << 20), 1 << 20, size=(16, 64, 4, 8), dtype=np.int32
        )
        output = rng.integers(0, 256, size=(16, 64, 4, 8), dtype=np.uint8)
        values = {
            "activation": activation,
            "weight": weight,
            "bias": rng.integers(-(1 << 18), 1 << 18, size=64, dtype=np.int32),
            "w_scale": np.linspace(0.01, 0.64, 64, dtype=np.float32),
            "w_zero_point": rng.integers(-8, 8, size=64, dtype=np.int8),
            "x_scale": np.array([0.125], dtype=np.float32),
            "x_zero_point": np.array([113], dtype=np.uint8),
            "y_scale": np.array([0.25], dtype=np.float32),
            "y_zero_point": np.array([127], dtype=np.uint8),
            "accumulator": accumulator,
            "output": output,
            "strides": (1, 1),
            "pads": (1, 1, 1, 1),
            "dilations": (1, 1),
        }
        layout = QLinearConvPhysicalLayout(layout_abi=CONV28_HARDWARE_LAYOUT_ABI)
        bundle = layout.forward(**values)
        self.assertTrue(bundle.plan.activation_halo_staged)
        self.assertEqual(bundle.plan.port("A").physical_shape, (3, 6, 4, 16, 4))
        local = layout._read_array(bundle, "A", 0)
        self.assertTrue(np.all(local[:, 0] == 113))
        self.assertTrue(np.all(local[:, -1] == 113))
        self.assertTrue(np.all(local[:, :, :, 0] == 113))
        self.assertTrue(np.all(local[:, :, :, 9:] == 113))
        address = layout.explain_coordinate(bundle, "conv_a", (0, 0, 0, 0))[0]
        self.assertEqual(address["physical_coordinate"], (0, 1, 0, 1, 0))
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["conv_a"], activation)
        np.testing.assert_array_equal(recovered["conv_b"], weight)
        np.testing.assert_array_equal(recovered["conv_p"], accumulator)
        np.testing.assert_array_equal(recovered["conv_d"], output)
        self.assertGreater(layout.validate(bundle)["semantic_tail_elements"], 0)

    def test_typed_request_embeds_all_nine_encoder_bindings(self) -> None:
        value = build_conv_execplan_request(ROOT, "node-0005")
        report = validate_conv_execplan_request(
            value, ROOT, expected_node_id="node-0005"
        )
        self.assertEqual(report["config_artifact_count"], 12)
        roles = [item["role"] for item in value["operators"][1]["config_artifacts"]]
        self.assertEqual(roles.count("requant_encoder_contract"), 1)
        self.assertEqual(roles.count("requant_shard"), 8)
        relationship = value["operators"][1]["attributes"]["artifact_relationship"]
        self.assertEqual(
            relationship["encoder_contract_artifact_id"],
            "hwop-0005-01.encoder-contract",
        )


if __name__ == "__main__":
    unittest.main()
