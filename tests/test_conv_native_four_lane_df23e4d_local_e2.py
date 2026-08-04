from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_native_four_lane_df23e4d_local_e2 import (
    CONTRACT_REL,
    build_contract,
    native_dot4_holdouts,
)


ROOT = Path(__file__).resolve().parents[1]


class ConvNativeFourLaneDf23e4dLocalE2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = build_contract(ROOT)

    def test_contract_is_reproducible_and_local_only(self) -> None:
        on_disk = json.loads((ROOT / CONTRACT_REL).read_text(encoding="utf-8"))
        self.assertEqual(on_disk, self.contract)
        self.assertEqual(self.contract["status"], "LOCAL_E2_PASS")
        self.assertFalse(self.contract["candidate_release"])
        self.assertEqual(self.contract["package_release"], "NONE")
        self.assertFalse(self.contract["server_action"])

    def test_named_boundaries_and_tails_pass(self) -> None:
        holdouts = native_dot4_holdouts()
        by_id = {item["case_id"]: item for item in holdouts["cases"]}
        self.assertEqual(by_id["signed18_min"]["result_s32"], -130_560)
        self.assertEqual(by_id["signed18_max"]["result_s32"], 129_540)
        self.assertEqual(by_id["exact_cancel"]["result_s32"], 0)
        self.assertEqual(
            {by_id[name]["k"] for name in ("k_tail_1", "k_tail_2", "k_tail_3")},
            {1, 2, 3},
        )
        self.assertEqual(by_id["nonzero_xzp"]["x_zero_point"], 11)

    def test_config_bound_three_way_is_bit_exact(self) -> None:
        simulation = self.contract["config_bound_accumulator_simulator"]
        tail = self.contract["config_bound_requant_tail_simulator"]
        three_way = self.contract["address_lifetime_terminal"][
            "three_way_accumulator"
        ]
        self.assertEqual(simulation["physical_mismatch_count"], 0)
        self.assertEqual(simulation["logical_w3_mismatch_count"], 0)
        self.assertTrue(
            simulation["fail_closed_negative_controls"][
                "single_formal_D_bit_flip_detected"
            ]
        )
        self.assertEqual(tail["mismatch_count"], 0)
        self.assertTrue(three_way["all_equal"])

    def test_native_consumer_closure_is_exact(self) -> None:
        roundtrip = self.contract["native_roundtrip"]
        self.assertEqual(roundtrip["mapping_count"], 51)
        self.assertEqual(roundtrip["execplan_count"], 27)
        self.assertEqual(roundtrip["sca_file_count"], 54)
        self.assertTrue(roundtrip["all_mapping_penalty_zero"])
        self.assertTrue(roundtrip["all_mapping_fallback_false"])
        self.assertTrue(roundtrip["all_execplan_double_run_equal"])
        self.assertTrue(roundtrip["exact_consumer_file_receipts"])

    def test_actual_performance_is_inverted_from_final_artifacts(self) -> None:
        performance = self.contract["address_lifetime_terminal"][
            "actual_performance_inversion"
        ]
        self.assertEqual(performance["compute_occurrence_reduction"], 4.0)
        self.assertEqual(
            performance["native_maximum_useful_lane_utilization_percent"],
            100.0,
        )
        self.assertEqual(
            performance["weight_payload_bytes"]["reduction"], 4.0
        )
        self.assertEqual(
            performance["activation_payload_bytes"][
                "per_producer_reduction"
            ],
            4.0,
        )
        self.assertEqual(
            performance["activation_payload_bytes"][
                "total_physical_reduction"
            ],
            2.0,
        )


if __name__ == "__main__":
    unittest.main()
