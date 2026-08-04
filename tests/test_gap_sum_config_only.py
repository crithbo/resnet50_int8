from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_sum_config_only import (
    BYPASS_ANNOTATION,
    CLAIM,
    GapSumConfigOnlyError,
    build_materialization_ownership,
    build_typed_request,
    materialize_configs,
    run_config_bound_simulator,
    stage1_buffer_byte_lane_contract,
    validate_input_replay,
    validate_materialized_configs,
)


ROOT = Path(__file__).resolve().parents[1]


class GapSumConfigOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.config_root = Path(self.temp.name) / "configs"
        materialize_configs(ROOT, self.config_root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_typed_scope_and_seven_field_annotation(self) -> None:
        request = build_typed_request()
        self.assertEqual(len(request["operators"]), 6)
        self.assertEqual(set(request["bypass_annotation"]), set(BYPASS_ANNOTATION))
        self.assertFalse(request["quant_tail_dependency"]["materialized"])
        self.assertFalse(request["quant_tail_dependency"]["complete_gap_target"])
        replay = validate_input_replay(ROOT, request)
        self.assertTrue(replay["valid"])
        self.assertFalse(replay["host_precomputed_internal_tensor"])
        self.assertTrue(
            replay["independent_sum_golden_used_only_for_comparison"]
        )

    def test_stage1_is_exact_8byte_even_odd_pair(self) -> None:
        cfg = json.loads(
            (self.config_root / "stage-1/config.json").read_text(encoding="utf-8")
        )
        a = cfg["stream_engine"]["stream0"]
        c = cfg["stream_engine"]["stream1"]
        self.assertEqual(a["idx_size"][0] + 1, 8)
        self.assertEqual(c["idx_size"][0] + 1, 8)
        self.assertEqual(int(c["base_addr"], 0), int(a["base_addr"], 0))
        loops = cfg["dram_loop_configs"]
        self.assertEqual((loops["LC1"]["start"], loops["LC1"]["stride"]), (0, 2))
        self.assertEqual((loops["LC3"]["start"], loops["LC3"]["stride"]), (1, 2))
        self.assertEqual(a["buf_spatial_stride"], list(range(0, 32, 4)))
        self.assertEqual(a["buf_spatial_size"], 8)
        for group_name in ("GROUP0", "GROUP1"):
            col = cfg["buffer_loop_configs"][group_name]["COL_LC"]
            self.assertEqual(
                (col["start"], col["end"], col["stride"]),
                (0, 4, 1),
            )
        fill = stage1_buffer_byte_lane_contract(cfg)
        self.assertTrue(fill["valid"])
        for group in fill["groups"].values():
            self.assertEqual(group["col_values"], [0, 1, 2, 3])
            self.assertTrue(group["all_banks_all_byte_lanes_exact_once"])
            self.assertTrue(
                all(slots == [0, 1, 2, 3] for slots in group["slots_by_bank"].values())
            )

    def test_materialized_roundtrip_and_negative_control(self) -> None:
        report = validate_materialized_configs(ROOT, self.config_root)
        self.assertTrue(report["valid"])
        self.assertEqual(report["final_unique_128bit_lines_per_slice"], 512)
        self.assertTrue(report["negative_control"]["legacy_rejected"])
        self.assertEqual(
            [item["occurrences_per_slice"] for item in report["stage_summaries"]],
            [8192, 4096, 2048, 1024, 512, 256],
        )
        self.assertTrue(
            all(
                item["materialization_diff"][
                    "all_final_leaves_have_unique_owner"
                ]
                for item in report["stage_summaries"]
            )
        )

    def test_config_bound_simulator_matches_real_w3_sum(self) -> None:
        report = run_config_bound_simulator(ROOT, self.config_root)
        self.assertTrue(report["bit_exact"])
        self.assertEqual(report["actual_sha256"], report["expected_sha256"])
        self.assertEqual(report["claim"], CLAIM)
        self.assertFalse(report["complete_gap_target"])

    def test_tampered_stage1_transaction_fails_closed(self) -> None:
        path = self.config_root / "stage-1/config.json"
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["stream_engine"]["stream0"]["idx_size"][0] = 15
        path.write_text(json.dumps(cfg), encoding="utf-8")
        with self.assertRaisesRegex(GapSumConfigOnlyError, "non-base"):
            validate_materialized_configs(ROOT, self.config_root)

    def test_stage1_repeated_byte_lane_schedule_fails_closed(self) -> None:
        values = {}
        for name in ("logical_config.json", "config.json"):
            path = self.config_root / "stage-1" / name
            cfg = json.loads(path.read_text(encoding="utf-8"))
            for group_name in ("GROUP0", "GROUP1"):
                col = cfg["buffer_loop_configs"][group_name]["COL_LC"]
                col["end"] = 32
                col["stride"] = 4
            path.write_text(json.dumps(cfg), encoding="utf-8")
            values[name] = cfg
        ownership = build_materialization_ownership(
            values["logical_config.json"], values["config.json"], 1
        )
        (self.config_root / "stage-1/materialization_ownership.json").write_text(
            json.dumps(ownership), encoding="utf-8"
        )
        with self.assertRaisesRegex(
            GapSumConfigOnlyError, "COL byte-lane sequence"
        ):
            validate_materialized_configs(ROOT, self.config_root)

    def test_final_address_equation_rejects_short_output_coverage(self) -> None:
        values = {}
        for name in ("logical_config.json", "config.json"):
            path = self.config_root / "stage-1" / name
            cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg["stream_engine"]["stream2"]["dim_stride"][1] = 16
            path.write_text(json.dumps(cfg), encoding="utf-8")
            values[name] = cfg
        ownership = build_materialization_ownership(
            values["logical_config.json"], values["config.json"], 1
        )
        (self.config_root / "stage-1/materialization_ownership.json").write_text(
            json.dumps(ownership), encoding="utf-8"
        )
        with self.assertRaisesRegex(GapSumConfigOnlyError, "output coverage"):
            validate_materialized_configs(ROOT, self.config_root)


if __name__ == "__main__":
    unittest.main()
