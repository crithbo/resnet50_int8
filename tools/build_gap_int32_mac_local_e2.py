from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODEL_SRC = ROOT / "ndp-sim/model_execplan/src"
if str(MODEL_SRC) not in sys.path:
    sys.path.insert(0, str(MODEL_SRC))

from execution_plan_generator.instruction_generator import (  # noqa: E402
    ClockEnableEncoder,
    LoadConfigEncoder,
    StartCompEncoder,
)
from resnet50_pipeline.gap_int32_mac_bypass import (  # noqa: E402
    PHYSICAL_WIDTHS,
    W3_EXPECTED_PATH,
    W3_INPUT_PATH,
)
from resnet50_pipeline.hardware_simulation_frontend import (  # noqa: E402
    build_execution_stages,
    load_execplan_commands,
)
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes, sha256_file  # noqa: E402


SOURCE = Path("configs/gap_int32_mac_bypass_v1")
OUTPUT = Path(
    "artifacts/operator_config_validation/gap-int32-mac-bypass-v1/local-e2"
)
SLICE_MASK = (1 << 16) - 1
CONFIG_BASES = tuple(0x100000 + index * 0x10000 for index in range(6))
OPCODE_BARRIER = 0b110


def _line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def _pack_commands(commands: list[int], output: Path) -> None:
    lines = []
    for index in range(0, len(commands), 2):
        low = commands[index]
        high = commands[index + 1] if index + 1 < len(commands) else 0
        lines.append(f"{high:064b}{low:064b}")
    output.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _numeric_e2(root: Path) -> dict[str, object]:
    tensor = np.load(root / W3_INPUT_PATH, allow_pickle=False)
    expected = np.load(root / W3_EXPECTED_PATH, allow_pickle=False).reshape(16, 2048)
    matrix = tensor.reshape(16, 2048, 49).astype(np.int32)
    physical = np.zeros((16, 256, 64, 8), dtype=np.int32)
    physical[:, :, :49, :] = matrix.reshape(16, 256, 8, 49).transpose(0, 1, 3, 2)
    widths = [physical.shape[2]]
    for _ in range(6):
        physical = (
            physical[:, :, 0::2, :].astype(np.int64)
            + physical[:, :, 1::2, :].astype(np.int64)
        ).astype(np.int32)
        widths.append(physical.shape[2])
    actual = physical[:, :, 0, :].reshape(16, 2048)
    if widths != list(PHYSICAL_WIDTHS):
        raise ValueError(f"physical widths differ: {widths}")
    if not np.array_equal(actual, expected):
        mismatch = np.argwhere(actual != expected)[0].tolist()
        raise ValueError(f"local E2 golden mismatch at {mismatch}")
    line_payload = actual.astype("<i4", copy=False).tobytes()
    return {
        "input_shape": list(tensor.shape),
        "physical_widths": widths,
        "output_shape": [16, 2048, 1, 1],
        "golden_equal": True,
        "output_sha256": sha256_bytes(line_payload),
        "expected_sha256": sha256_bytes(
            expected.astype("<i4", copy=False).tobytes()
        ),
        "slices": 16,
        "int32_values_per_slice": 2048,
        "unique_128bit_lines_per_slice": 512,
    }


def build(root: Path, output: Path) -> dict[str, object]:
    if output.exists():
        shutil.rmtree(output)
    (output / "install/cfg_pkg").mkdir(parents=True)
    commands = [ClockEnableEncoder.encode(SLICE_MASK)]
    explanations = [
        f"Clock_Enable: slice_mask_bin={SLICE_MASK:028b}, clock_select_bin=1111"
    ]
    stages = []
    for stage in range(1, 7):
        source = root / SOURCE / f"stage-{stage}"
        config = source / "config.json"
        mapping = source / "encoded/mapping_review.json"
        parsed = source / "encoded/parsed_bitstream.txt"
        bitstream = source / "encoded/modules_dump_128b.bin"
        for path in (config, mapping, parsed, bitstream):
            if not path.is_file():
                raise FileNotFoundError(path)
        installed = output / "install/cfg_pkg" / f"gap_int32_mac_stage{stage}_128b.bin"
        shutil.copy2(bitstream, installed)
        length = _line_count(bitstream) * 2
        load = LoadConfigEncoder.encode(
            length, CONFIG_BASES[stage - 1] >> 10, False, SLICE_MASK
        )
        start = StartCompEncoder.encode(SLICE_MASK)
        barrier = (SLICE_MASK << 3) | OPCODE_BARRIER
        commands.extend((load, start, barrier))
        op_id = f"gap_mac_s{stage}"
        explanations.extend(
            (
                f"Load_Config for operator {op_id} (gap_int32_mac_stage{stage}): "
                f"config_length={length}, ddr_config_addr=0x{CONFIG_BASES[stage - 1] >> 10:X}, "
                f"slice_mask_bin={SLICE_MASK:028b}",
                f"Start_Comp for operator {op_id} (gap_int32_mac_stage{stage}): "
                f"slice_mask_bin={SLICE_MASK:028b}",
                f"Barrier for operator {op_id}: slice_mask_bin={SLICE_MASK:028b}",
            )
        )
        stages.append(
            {
                "operator_id": op_id,
                "operator_type": f"gap_int32_mac_stage{stage}",
                "stage_kind": "int32_mac_pairwise_reduction",
                "config": {
                    "path": config.relative_to(root).as_posix(),
                    "sha256": sha256_file(config),
                    "mapping_sha256": sha256_file(mapping),
                    "parsed_bitstream_sha256": sha256_file(parsed),
                    "installed_bitstream": installed.relative_to(output).as_posix(),
                    "installed_bitstream_sha256": sha256_file(installed),
                    "config_length_64bit_words": length,
                    "ddr_config_base": CONFIG_BASES[stage - 1],
                },
            }
        )
    execplan = output / "install/execplan.txt"
    _pack_commands(commands, execplan)
    explanation = output / "instructions_explained.txt"
    explanation.write_text(
        "\n".join(
            f"Command {index}: {word:064b} | {text}"
            for index, (word, text) in enumerate(zip(commands, explanations))
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runtime_manifest = {
        "runtime_operators": stages,
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_count": 6,
            "barrier_opcode": "0b110",
        },
    }
    decoded = load_execplan_commands(execplan)
    global_commands, execution_stages = build_execution_stages(
        decoded, runtime_manifest
    )
    if len(global_commands) != 1 or len(execution_stages) != 6:
        raise ValueError("six-stage lifecycle decode differs")
    if any(stage.completion_barrier is None for stage in execution_stages):
        raise ValueError("stage completion barrier is missing")
    numeric = _numeric_e2(root)
    report = {
        "schema": "gap-int32-mac-local-e2-v1",
        "status": "pass_local_e2",
        "candidate_release": False,
        "server_package_allowed": True,
        "functional_rtl_modified": False,
        "rtl_patch_present": False,
        "json_stage_count": 6,
        "load_config_count": 6,
        "start_comp_count": 6,
        "completion_barrier_count": 6,
        "clock_enable_count": 1,
        "lifecycle": {
            "full_config_reload_each_stage": True,
            "write_reg_base_patch_count": 0,
            "next_load_blocked_until_same_mask_barrier": True,
            "configure_clear_used_as_fifo_drain": False,
        },
        "numeric_e2": numeric,
        "runtime": runtime_manifest,
        "execplan": {
            "path": execplan.relative_to(output).as_posix(),
            "sha256": sha256_file(execplan),
            "command_count": len(commands),
            "beat_count": _line_count(execplan),
        },
    }
    report_path = output / "LOCAL_E2_REPORT.json"
    report_path.write_bytes(canonical_json_bytes(report) + b"\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output.resolve() if args.output else (root / OUTPUT).resolve()
    report = build(root, output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
