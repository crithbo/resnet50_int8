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
    validate_first_conv_signed_a_local_contract,
)
from resnet50_pipeline.conv28_layout import (
    CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
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
            layout_abi=CONV28_SIGNED_A_LOCAL_LAYOUT_ABI
        ).plan(
            activation_shape=cls.spec.activation_shape,
            weight_shape=cls.spec.weight_shape,
            strides=cls.spec.strides,
            pads=cls.spec.pads,
            dilations=cls.spec.dilations,
            group=cls.spec.group,
        )

    def test_byte_routes_terminal_tags_and_bias_extent_close(self) -> None:
        report = validate_first_conv_signed_a_local_contract(self.config)
        self.assertEqual(
            report["stream_transaction_bytes"],
            {
                "stream0": WEIGHT_TRANSACTION_BYTES,
                "stream1": INPUT_TRANSACTION_BYTES,
                "stream2": INPUT_TRANSACTION_BYTES,
                "stream3": BIAS_TRANSACTION_BYTES,
                "stream4": OUTPUT_TRANSACTION_BYTES,
            },
        )
        self.assertEqual(report["buffer_loop_bytes"]["GROUP0"], 128)
        self.assertEqual(report["buffer_loop_bytes"]["GROUP1"], 128)
        self.assertEqual(report["buffer_loop_bytes"]["GROUP2"], 128)
        self.assertEqual(report["buffer_loop_bytes"]["GROUP3"], 32)
        self.assertEqual(self.config["n2n"], {})
        self.assertEqual(report["neighbor_stream_count"], 0)
        self.assertEqual(report["sa_data_a_role"], "signed_int8_weight")
        self.assertEqual(report["sa_data_b_role"], "unsigned_uint8_activation")
        self.assertEqual(
            report["a_pingpong_binding"],
            {
                "mse_stream": 0,
                "physical_buffers": [0, 1],
                "sa_inport": 0,
                "enabled": True,
                "terminal_tag": 4,
            },
        )
        self.assertEqual(
            [
                self.config["buffer_config"][f"buffer{index}"]["mode"]
                for index in range(4)
            ],
            [1, 1, 1, 1],
        )
        for index in range(5):
            stream = self.config["stream_engine"][f"stream{index}"]
            group = self.config["buffer_loop_configs"][f"GROUP{index}"]
            self.assertEqual(
                stream["buf_idx_keep_last_index"][0],
                group["COL_LC"]["last_index"],
            )

    def test_physical_input_and_p_write_ranges_are_exact_partitions(self) -> None:
        streams = self.config["stream_engine"]
        c_quartets = self.plan.c_tile_padded // 4
        q_blocks = self.plan.output_width_padded // 8
        k_blocks = self.plan.k_tile_padded // 8

        a_offsets = {
            (ring * c_quartets + c) * streams["stream1"]["dim_stride"][0]
            + q * streams["stream1"]["dim_stride"][1]
            + p * streams["stream1"]["dim_stride"][2]
            for p in range(self.spec.output_height)
            for q in range(q_blocks)
            for ring in range(4)
            for c in range(c_quartets)
        }
        self.assertEqual(len(a_offsets), self.plan.port("A").payload_bytes // 3 // 32)
        self.assertEqual(min(a_offsets), 0)
        self.assertEqual(max(a_offsets) + 32, self.plan.port("A").payload_bytes // 3)

        p_offsets = {
            k * streams["stream4"]["dim_stride"][0]
            + (q * 8 + lane) * streams["stream4"]["dim_stride"][1]
            + p * streams["stream4"]["dim_stride"][2]
            for p in range(self.spec.output_height)
            for q in range(q_blocks)
            for lane in range(8)
            for k in range(k_blocks)
        }
        self.assertEqual(len(p_offsets), self.plan.port("P").payload_bytes // 3 // 32)
        self.assertEqual(min(p_offsets), 0)
        self.assertEqual(max(p_offsets) + 32, self.plan.port("P").payload_bytes // 3)

        weight_offsets = {
            (ring * c_quartets + c) * streams["stream0"]["dim_stride"][0]
            + k * streams["stream0"]["dim_stride"][1]
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
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["buffer_loop_configs"]["GROUP3"]["ROW_LC"]["end"] = 4
        with self.assertRaisesRegex(ValueError, "GROUP3 must cover"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["n2n"] = {"neighbor_stream0": {"mem_loop": 4}}
        with self.assertRaisesRegex(ValueError, "must not depend"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["buffer_config"]["buffer4"]["buffer_life_time"] = 1
        with self.assertRaisesRegex(ValueError, "four bias handshakes"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream3"]["idx"] = ["DRAM_LC.LC13", None, None]
        with self.assertRaisesRegex(ValueError, "Kblock/H/Qblock bias tile branch"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream3"]["dim_stride"][2] = 32
        with self.assertRaisesRegex(ValueError, "change only by 32B per Kblock"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream2"]["dim_stride"][1] += 32
        with self.assertRaisesRegex(ValueError, "B/B' activation producers"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream0"]["buf_idx_keep_last_index"][0] -= 1
        with self.assertRaisesRegex(
            ValueError, "ROW keep threshold must equal GROUP0.COL_LC.last_index"
        ):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream0"]["ping_pong"] = 0
        with self.assertRaisesRegex(ValueError, "ping-pong enables must match"):
            validate_first_conv_signed_a_local_contract(bad)

        bad = json.loads(json.dumps(self.config))
        bad["stream_engine"]["stream0"]["pingpong_last_index"] = 3
        with self.assertRaisesRegex(ValueError, "terminal tags must match"):
            validate_first_conv_signed_a_local_contract(bad)


if __name__ == "__main__":
    unittest.main()
