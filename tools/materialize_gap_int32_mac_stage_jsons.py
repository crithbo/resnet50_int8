from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_int32_mac_bypass import (  # noqa: E402
    PHYSICAL_WIDTHS,
    relative_regions,
    stage_pair_records,
)
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file  # noqa: E402
from resnet50_pipeline.operator_config_validator import (  # noqa: E402
    OperatorConfigValidator,
)


TEMPLATE = "configs/stage_codegen/hwop-0071-00-d-index-v1/config.json"
OUTPUT_ROOT = "configs/gap_int32_mac_bypass_v1"
STAGE_OUTPUT_BASES = (0x40000, 0x80000, 0xA0000, 0xB0000, 0xB8000, 0xBC000)


def _stream(
    *,
    target: str,
    mode: str,
    base: int,
    transaction_bytes: int,
    block_stride: int,
    item_stride: int,
    padding_upper: int | None = None,
) -> dict[str, object]:
    read = mode == "read"
    result: dict[str, object] = {
        "target": target,
        "mode": mode,
        "base_addr": hex(base),
        "mem_idx_mode": ["buffer", "keep", None],
        "mem_idx_keep_last_index": [None, 1, None],
        "mem_idx_constant": [None, None, None],
        "idx": ["DRAM_LC.LC0", "DRAM_LC.LC1", None],
        "idx_size": [transaction_bytes - 1, 0, None],
        "dim_stride": [block_stride, item_stride, None],
        "tailing_enable": [0, 0, 0],
        "idx_tailing_range": {
            "low": [None, None, None],
            "up": [None, None, None],
        },
        "address_remapping": None,
        "buf_idx_mode": ["keep", "buffer"],
        "buf_idx_keep_last_index": [3, None],
        "buf_spatial_stride": (
            [lane * 4 for lane in range(8)]
            if transaction_bytes == 8
            else list(range(16))
        ),
        "buf_spatial_size": 8 if transaction_bytes == 8 else 16,
        "ping_pong": 0,
        "pingpong_last_index": None,
    }
    if read:
        result.update(
            {
                "padding_enable": [0, int(padding_upper is not None), 0],
                "padding_reg_value": 0 if padding_upper is not None else None,
                "idx_padding_range": {
                    "low_bound": [None, 0 if padding_upper is not None else None, None],
                    "up_bound": [None, padding_upper, None],
                },
                "buf_full_last_index": 2,
            }
        )
    return result


def _buffer_group(target: str) -> dict[str, object]:
    return {
        "target": target,
        "ROW_LC": {
            "src_id": "DRAM_LC.LC1",
            "start": 0,
            "end": 1,
            "stride": 1,
            "last_index": 2,
        },
        "COL_LC": {
            "src_id": f"GROUP{{group}}.ROW_LC",
            "start": 0,
            "end": 32,
            "stride": 16,
            "last_index": 3,
        },
    }


def build_stage(template: dict[str, object], stage_index: int) -> dict[str, object]:
    config = copy.deepcopy(template)
    regions = relative_regions()
    source = regions[stage_index - 1]
    output = regions[stage_index]
    output_width = PHYSICAL_WIDTHS[stage_index]
    config["dram_loop_configs"] = {
        "LC0": {
            "src_id": None,
            "outmost_loop": 1,
            "start": 0,
            "end": 256,
            "stride": 1,
            "last_index": 0,
        },
        "LC1": {
            "src_id": "DRAM_LC.LC0",
            "outmost_loop": 0,
            "start": 0,
            "end": output_width,
            "stride": 1,
            "last_index": 1,
        },
    }
    config["lc_pe_configs"] = {}
    groups = {}
    for index, target in enumerate(("A", "C", "D")):
        group = _buffer_group(target)
        group["COL_LC"]["src_id"] = f"GROUP{index}.ROW_LC"
        groups[f"GROUP{index}"] = group
    config["buffer_loop_configs"] = groups

    transaction_bytes = 16 if stage_index == 1 else 32
    source_base = 0 if stage_index == 1 else STAGE_OUTPUT_BASES[stage_index - 2]
    output_base = STAGE_OUTPUT_BASES[stage_index - 1]
    source_stride = 512 if stage_index == 1 else source.physical_width * 32
    item_stride = 16 if stage_index == 1 else 64
    a_padding = 24 if stage_index == 1 else None
    c_padding = 23 if stage_index == 1 else None
    config["stream_engine"] = {
        "stream0": _stream(
            target="A",
            mode="read",
            base=source_base,
            transaction_bytes=transaction_bytes,
            block_stride=source_stride,
            item_stride=item_stride,
            padding_upper=a_padding,
        ),
        "stream1": _stream(
            target="C",
            mode="read",
            base=0x20000 if stage_index == 1 else source_base + 32,
            transaction_bytes=transaction_bytes,
            block_stride=source_stride,
            item_stride=item_stride,
            padding_upper=c_padding,
        ),
        "stream2": _stream(
            target="D",
            mode="write",
            base=output_base,
            transaction_bytes=32,
            block_stride=output.physical_width * 32,
            item_stride=32,
        ),
    }
    buffer_seed = next(iter(template["buffer_config"].values()))
    config["buffer_config"] = {
        name: {**copy.deepcopy(buffer_seed), "enable": 1}
        for name in ("buffer0", "buffer4", "buffer5")
    }
    ga = config["general_array"]
    for name in ("inport0", "inport2"):
        ga["inport"][name]["mask"] = [1] * 8
        ga["inport"][name]["src_id"] = 0
        ga["inport"][name]["uint8toint32"] = (
            "true" if stage_index == 1 else "false"
        )
    ga["inport"]["inport1"]["mask"] = [0] * 8
    for pe in ga["PE_array"].values():
        pe["alu_opcode"] = "int32_mac"
        pe["transout_last_index"] = None
        pe["inport0"].update({"src_id": 0, "mode": "buffer", "constant": 0})
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "constant": 1}
        )
        pe["inport2"].update({"src_id": 0, "mode": "buffer", "constant": 0})
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root is not None
        else (root / OUTPUT_ROOT).resolve()
    )
    template = json.loads((root / TEMPLATE).read_text(encoding="utf-8"))
    manifest = {"schema": "gap-int32-mac-six-stage-json-set-v1", "stages": []}
    for stage_index in range(1, 7):
        output = output_root / f"stage-{stage_index}" / "config.json"
        if output.exists() and not args.overwrite:
            raise FileExistsError(output)
        config = build_stage(template, stage_index)
        report = OperatorConfigValidator().validate(
            config,
            source=str(output),
            development_mode=True,
        )
        errors = [item for item in report.issues if item.severity == "error"]
        if errors:
            raise ValueError(
                f"stage {stage_index} validator errors: "
                + "; ".join(f"{item.code}:{item.path}" for item in errors)
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(canonical_json_bytes(config) + b"\n")
        manifest["stages"].append(
            {
                "stage_index": stage_index,
                "config": output.relative_to(root).as_posix(),
                "sha256": sha256_file(output),
                "validator_error_count": 0,
            }
        )
    manifest_path = output_root / "manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
