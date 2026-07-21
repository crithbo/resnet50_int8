from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_instance import load_conv_instance_spec
from resnet50_pipeline.conv_sa_contract import (
    BIAS_TRANSACTION_BYTES,
    INPUT_TRANSACTION_BYTES,
    OUTPUT_TRANSACTION_BYTES,
    SA_BIAS_HANDSHAKES_PER_TILE,
    WEIGHT_TRANSACTION_BYTES,
    stream_total_bytes,
    validate_first_conv_sa_contract,
)
from resnet50_pipeline.conv28_layout import (
    CONV28_HARDWARE_LAYOUT_ABI,
    QLinearConvPhysicalLayout,
)
from tools.generate_conv_1x1_real import build_real_1x1


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ConvSaHardwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = load_conv_instance_spec(ROOT, "node-0004")
        cls.config = build_real_1x1(_json(ROOT / "conv_full.json"), cls.spec)
        cls.plan = QLinearConvPhysicalLayout(
            layout_abi=CONV28_HARDWARE_LAYOUT_ABI
        ).plan(
            activation_shape=cls.spec.activation_shape,
            weight_shape=cls.spec.weight_shape,
            strides=cls.spec.strides,
            pads=cls.spec.pads,
            dilations=cls.spec.dilations,
            group=cls.spec.group,
        )

    def test_byte_routes_terminal_tags_and_bias_extent_close(self) -> None:
        report = validate_first_conv_sa_contract(self.config)
        self.assertEqual(
            report["stream_transaction_bytes"],
            {
                "stream0": INPUT_TRANSACTION_BYTES,
                "stream1": WEIGHT_TRANSACTION_BYTES,
                "stream2": OUTPUT_TRANSACTION_BYTES,
                "stream3": BIAS_TRANSACTION_BYTES,
            },
        )
        self.assertEqual(report["buffer_loop_bytes"]["GROUP0"], 128)
        self.assertEqual(report["buffer_loop_bytes"]["GROUP1"], 128)
        self.assertEqual(report["buffer_loop_bytes"]["GROUP2"], 32)
        self.assertEqual(set(self.config["n2n"]), {"neighbor_stream0"})
        self.assertEqual(report["bias_extent_bytes"], 64)
        self.assertEqual(report["bias_transaction_count"], 2 * 56 * 7)
        self.assertEqual(report["bias_unique_address_count"], 2)
        self.assertEqual(
            report["bias_handshakes_per_tile"], SA_BIAS_HANDSHAKES_PER_TILE
        )

    def test_physical_input_and_p_write_ranges_are_exact_partitions(self) -> None:
        streams = self.config["stream_engine"]
        c_quartets = self.plan.c_tile_padded // 4
        q_blocks = self.plan.output_width_padded // 8
        k_blocks = self.plan.k_tile_padded // 8

        a_offsets = {
            c * streams["stream0"]["dim_stride"][0]
            + q * streams["stream0"]["dim_stride"][1]
            + p * streams["stream0"]["dim_stride"][2]
            for p in range(self.spec.output_height)
            for q in range(q_blocks)
            for c in range(c_quartets)
        }
        self.assertEqual(len(a_offsets), self.plan.port("A").payload_bytes // 3 // 32)
        self.assertEqual(min(a_offsets), 0)
        self.assertEqual(max(a_offsets) + 32, self.plan.port("A").payload_bytes // 3)

        p_offsets = {
            k * streams["stream2"]["dim_stride"][0]
            + (q * 8 + lane) * streams["stream2"]["dim_stride"][1]
            + p * streams["stream2"]["dim_stride"][2]
            for p in range(self.spec.output_height)
            for q in range(q_blocks)
            for lane in range(8)
            for k in range(k_blocks)
        }
        self.assertEqual(len(p_offsets), self.plan.port("P").payload_bytes // 3 // 32)
        self.assertEqual(min(p_offsets), 0)
        self.assertEqual(max(p_offsets) + 32, self.plan.port("P").payload_bytes // 3)

        weight_offsets = {
            (ring * c_quartets + c) * streams["stream1"]["dim_stride"][0]
            + k * streams["stream1"]["dim_stride"][1]
            for ring in range(4)
            for c in range(c_quartets)
            for k in range(k_blocks)
        }
        self.assertEqual(len(weight_offsets), self.plan.port("B").payload_bytes // 32)
        self.assertEqual(max(weight_offsets) + 32, self.plan.port("B").payload_bytes)

        bias_offsets = {
            k * streams["stream3"]["dim_stride"][0] for k in range(k_blocks)
        }
        self.assertEqual(bias_offsets, {0, 32})
        self.assertEqual(max(bias_offsets) + 32, self.plan.port("bias").payload_bytes)
        self.assertEqual(self.config["buffer_config"]["buffer4"]["buffer_life_time"], 4)

    def test_v8_contract_is_rejected_without_another_simulation(self) -> None:
        v8 = _json(
            ROOT
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v8/configs/conv_1x1_real.json"
        )
        self.assertEqual(stream_total_bytes(v8["stream_engine"]["stream1"]), 4)
        with self.assertRaisesRegex(ValueError, "stream0 transaction is 128B"):
            validate_first_conv_sa_contract(v8)

    def test_individual_regressions_fail_closed(self) -> None:
        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream1"]["idx_size"] = [3, 0, 0]
        with self.assertRaisesRegex(ValueError, "stream1 transaction is 4B"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 4
        with self.assertRaisesRegex(ValueError, "K8 int32 bias row"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["n2n"] = {"neighbor_stream1": bad["n2n"].pop("neighbor_stream0")}
        with self.assertRaisesRegex(ValueError, "neighbor_stream0"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["buffer_config"]["buffer4"]["buffer_life_time"] = 1
        with self.assertRaisesRegex(ValueError, "four bias handshakes"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream3"]["idx"] = ["DRAM_LC.LC13", None, None]
        with self.assertRaisesRegex(ValueError, "Kblock/H/Qblock bias tile branch"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream3"]["dim_stride"][2] = 32
        with self.assertRaisesRegex(ValueError, "change only by 32B per Kblock"):
            validate_first_conv_sa_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["src_id"] = "DRAM_LC.LC13"
        with self.assertRaisesRegex(ValueError, "Qblock bias tile event"):
            validate_first_conv_sa_contract(bad)


if __name__ == "__main__":
    unittest.main()
