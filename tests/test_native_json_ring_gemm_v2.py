from __future__ import annotations

import unittest

from resnet50_pipeline.conv_execplan_hardware import (
    ConvHardwareExecplanError,
    _expected_testbench_repeat_num,
)
from resnet50_pipeline.hardware_simulation_frontend import (
    HardwareSimulationPreparationError,
    OPCODE_BARRIER,
    OPCODE_CLOCK_ENABLE,
    OPCODE_LOAD_CONFIG,
    OPCODE_START_COMP,
    ROW_SHIFT,
    build_execution_stages,
    decode_command,
)


def _manifest() -> dict[str, object]:
    return {
        "runtime_operator_count": 1,
        "runtime_sequence": ["ring4"],
        "runtime_operators": [
            {
                "operator_id": "ring4",
                "slice_mask": "0x000000F",
                "attributes": {
                    "runtime_partition": "full_ring_group",
                    "selected_slices": [0, 1, 2, 3],
                },
            }
        ],
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_count": 1,
            "barrier_opcode": "0b110",
            "configuration_strategy": (
                "four_independent_config_loads_then_one_full_ring4_start"
            ),
        },
        "testbench_observer": {
            "mode": "fixed_slice0_start_slice1_finish",
            "repeat_num": 1,
            "runtime_stage_count": 1,
            "final_pair_finishes_at_stage": 0,
            "all_prior_stages_barrier_ordered": True,
            "final_stage_slice_mask": "0x000000F",
            "final_stage_is_finish_slice_only": False,
            "final_stage_is_full_mask_ring_group": True,
            "final_stage_completion_barrier_mask": "0x000000F",
            "readback_after_final_finish_is_full_mask_completion_safe": True,
            "pairs": [
                {
                    "pair_index": 0,
                    "slice0_start_stage": 0,
                    "slice1_finish_stage": 0,
                }
            ],
        },
    }


def _commands() -> list[object]:
    raw_commands = [
        (0xF << 31) | (0xF << 3) | OPCODE_CLOCK_ENABLE,
        *[
            (60 << 56)
            | ((base >> ROW_SHIFT) << 34)
            | ((1 << slice_id) << 3)
            | OPCODE_LOAD_CONFIG
            for slice_id, base in enumerate((0x10000, 0x10400, 0x10800, 0x10C00))
        ],
        (0xF << 3) | OPCODE_START_COMP,
        (0xF << 3) | OPCODE_BARRIER,
    ]
    return [
        decode_command(raw, index=index, beat_index=index // 2, lane="low")
        for index, raw in enumerate(raw_commands)
    ]


class NativeJsonRingGemmV2ContractTests(unittest.TestCase):
    def test_full_ring_observer_accepts_exact_four_slice_group(self) -> None:
        self.assertEqual(_expected_testbench_repeat_num(_manifest(), 1), 1)

    def test_full_ring_observer_rejects_missing_member(self) -> None:
        manifest = _manifest()
        manifest["runtime_operators"][0]["attributes"]["selected_slices"] = [0, 1, 2]
        with self.assertRaisesRegex(ConvHardwareExecplanError, "complete four-slice"):
            _expected_testbench_repeat_num(manifest, 1)

    def test_four_single_slice_configs_feed_one_full_ring_start(self) -> None:
        _globals, stages = build_execution_stages(_commands(), _manifest())
        self.assertEqual(len(stages), 1)
        self.assertEqual(stages[0].slice_mask, 0xF)
        self.assertEqual(
            [int(command.fields["slice_mask"]) for command in stages[0].load_configs],
            [0x1, 0x2, 0x4, 0x8],
        )
        self.assertEqual(int(stages[0].completion_barrier.fields["slice_mask"]), 0xF)

    def test_four_single_slice_configs_require_explicit_strategy(self) -> None:
        manifest = _manifest()
        del manifest["runtime_serialization"]["configuration_strategy"]
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "Load_Config/Start_Comp"
        ):
            build_execution_stages(_commands(), manifest)


if __name__ == "__main__":
    unittest.main()
