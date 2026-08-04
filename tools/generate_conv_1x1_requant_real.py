from __future__ import annotations

import argparse
import json
import struct
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    ConvInstanceSpec,
    load_conv_instance_spec,
    validate_conv_requant_output_route,
)
from resnet50_pipeline.conv28_layout import (
    CONV28_HARDWARE_LAYOUT_ABI,
    CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
    QLinearConvPhysicalLayout,
)
from resnet50_pipeline.topology28 import HIGH_RING_OWNERS
from resnet50_pipeline.w5_conv_preflight import (
    _initializer,
    _initializer_values,
    _port,
    _record_by_hw_op,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "ndp-sim-ref" / "jsons" / "quant_from_buffer_int32MN_uint8MN.json"
TYPED_CONTRACT_PATH = PROJECT_ROOT / "contracts" / "typed_config_parameter_contract.json"
MODEL_PATH = PROJECT_ROOT / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
W3_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "w3" / "golden_batch16" / "manifest.json"
OUTPUT_ROOT = PROJECT_ROOT / "conv_1x1_requant_real"
REQUANT_HW_OP_ID = "hwop-0004-01"
GA_MAC_KEYS = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
GA_SUB_KEYS = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
ROUND_MAGIC_BITS = 0x4B400000


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _float32_bits(value: np.float32) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def _real_qparams(
    spec: ConvInstanceSpec | None = None,
) -> tuple[np.ndarray, int, str]:
    spec = spec or load_conv_instance_spec(PROJECT_ROOT, FIRST_REAL_CONV_NODE_ID)
    typed = _load_json(TYPED_CONTRACT_PATH)
    record = _record_by_hw_op(typed, spec.requant_hw_op_id)
    manifest = _load_json(W3_MANIFEST_PATH)
    initializers = _initializer_values(MODEL_PATH)
    values = {
        name: _initializer(initializers, manifest, _port(record, "inputs", name))
        for name in ("x_scale", "w_scale", "y_scale", "y_zero_point")
    }
    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    expected = next(
        item for item in record["parameters"] if item["name"] == "requant_multiplier"
    )["value"]["value_sha256"]
    actual = sha256(np.ascontiguousarray(multiplier).tobytes()).hexdigest()
    if multiplier.shape != (spec.output_channels,) or actual != expected:
        raise ValueError("real Conv requant multiplier identity differs")
    if actual != spec.requant_multiplier_sha256:
        raise ValueError("ConvInstanceSpec requant multiplier identity differs")
    return multiplier, int(values["y_zero_point"][0]), actual


def build_bundle(
    spec: ConvInstanceSpec | None = None,
    *,
    config_root_relative: str = "conv_1x1_requant_real",
) -> tuple[dict[str, Any], dict[str, bytes]]:
    spec = spec or load_conv_instance_spec(PROJECT_ROOT, FIRST_REAL_CONV_NODE_ID)
    spec.validate()
    template = _load_json(TEMPLATE_PATH)
    multiplier, output_zero_point, multiplier_sha = _real_qparams(spec)
    plan = QLinearConvPhysicalLayout(
        layout_abi=(
            CONV28_SIGNED_A_LOCAL_LAYOUT_ABI
            if spec.node_id == FIRST_REAL_CONV_NODE_ID
            else CONV28_HARDWARE_LAYOUT_ABI
        )
    ).plan(
        activation_shape=spec.activation_shape,
        weight_shape=spec.weight_shape,
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
        group=spec.group,
    )
    p_base = plan.port("P").offset_bytes
    d_base = plan.port("D").offset_bytes
    spatial_count = spec.first_tile_spatial_count
    staged_half_bytes = spatial_count * spec.ga_lane_count
    staged_d_base = plan.per_slice_used_bytes
    if any(value % 16 for value in (p_base, d_base, staged_d_base, staged_half_bytes)):
        raise ValueError("real Conv requant addresses must be 16-byte aligned")
    round_magic = np.float32(12582912.0 + output_zero_point)
    files: dict[str, bytes] = {}
    shards: list[dict[str, Any]] = []
    covered: list[int] = []
    for shard_index in range(spec.requant_shard_count):
        owner_step, local_half = divmod(
            shard_index, spec.requant_shards_per_owner
        )
        channel_start = owner_step * plan.k_tile + local_half * spec.ga_lane_count
        channels = list(range(channel_start, channel_start + spec.ga_lane_count))
        if channels[-1] >= spec.output_channels:
            raise ValueError("current GA requant generator requires full 8-channel shards")
        selected_slices = [ring[owner_step] for ring in HIGH_RING_OWNERS]
        config = deepcopy(template)
        config["dram_loop_configs"]["LC0"]["end"] = 1
        config["dram_loop_configs"]["LC1"]["end"] = spatial_count
        config["dram_loop_configs"]["LC2"]["end"] = spatial_count // 4
        pe_array = config["general_array"]["PE_array"]
        for lane, (mac_key, sub_key, channel) in enumerate(
            zip(GA_MAC_KEYS, GA_SUB_KEYS, channels, strict=True)
        ):
            mac = pe_array[mac_key]
            sub = pe_array[sub_key]
            mac["inport1"]["constant"] = float(multiplier[channel])
            mac["inport2"]["constant"] = float(round_magic)
            sub["inport1"]["constant"] = ROUND_MAGIC_BITS
            if mac["alu_opcode"] != "mac" or sub["alu_opcode"] != "int32_sub":
                raise ValueError(f"DeepSeek Quant GA lane {lane} topology differs")
        config["stream_engine"]["stream0"]["base_addr"] = (
            p_base + local_half * spec.ga_lane_count * 4
        )
        config["stream_engine"]["stream0"]["dim_stride"][0] = plan.k_tile_padded * 4
        config["stream_engine"]["stream2"]["base_addr"] = (
            staged_d_base + local_half * staged_half_bytes
        )
        config["stream_engine"]["stream2"]["dim_stride"][0] = spec.ga_lane_count * 4
        validate_conv_requant_output_route(config)
        name = f"shard-{shard_index:02d}.json"
        payload = _canonical_bytes(config)
        files[name] = payload
        shards.append(
            {
                "shard_index": shard_index,
                "config_path": f"{config_root_relative}/{name}",
                "config_sha256": _sha256_bytes(payload),
                "owner_step": owner_step,
                "local_half": local_half,
                "selected_slices": selected_slices,
                "channels": channels,
                "ga_mac_pe_keys": list(GA_MAC_KEYS),
                "multiplier_float32": [float(multiplier[channel]) for channel in channels],
                "multiplier_float32_bits": [_float32_bits(multiplier[channel]) for channel in channels],
                "p_base_offset": p_base + local_half * spec.ga_lane_count * 4,
                "staged_d_base_offset": staged_d_base + local_half * staged_half_bytes,
                "staged_d_size_bytes": staged_half_bytes,
                "flush": "once_after_final_conv_reduction",
            }
        )
        covered.extend(channels)
    if (
        sorted(covered) != list(range(spec.output_channels))
        or len(set(covered)) != spec.output_channels
    ):
        raise ValueError("requant shards must cover every output channel exactly once")
    manifest = {
        "schema_version": "0.1",
        # The validator-facing name is a frozen ABI label.  The requant stage
        # consumes final INT32 P and is independent of the accumulation kernel.
        "contract_type": "conv_1x1_requant_config_bundle",
        "status": "real_qparams_sharded_candidate",
        "node_id": spec.node_id,
        "hw_op_id": spec.requant_hw_op_id,
        "source_template": {
            "path": "ndp-sim-ref/jsons/quant_from_buffer_int32MN_uint8MN.json",
            "sha256": _sha256_bytes(TEMPLATE_PATH.read_bytes()),
            "execution_status": "operator_confirmed_deepseek_json_hardware_executable",
        },
        "requant": {
            "multiplier_sha256": multiplier_sha,
            "channel_count": spec.output_channels,
            "output_zero_point": output_zero_point,
            "rounding": "fp32_magic_add_then_int32_sub_nearest_even",
            "round_magic_float32": float(round_magic),
            "round_magic_bits": _float32_bits(round_magic),
            "subtract_magic_int32": ROUND_MAGIC_BITS,
            "saturation": "general_array.outport.int32touint8",
        },
        "physical_layout": {
            "profile": "group4x7_batch_channel",
            "p_offset": p_base,
            "canonical_d_offset": d_base,
            "staged_d_offset": staged_d_base,
            "staged_half_bytes": staged_half_bytes,
            "staged_total_bytes": staged_half_bytes * spec.requant_shards_per_owner,
            "staged_to_canonical_transform": (
                "concatenate two NHWK8 halves, then reshape to "
                "NH-Qblock-Q8-Kblock-K8"
            ),
            "local_k_tile": plan.k_tile,
            "local_k_tile_padded": plan.k_tile_padded,
            "ga_lane_count": spec.ga_lane_count,
        },
        "coverage": {
            "shard_count": spec.requant_shard_count,
            "covered_channels": covered,
            "unique_channel_count": len(set(covered)),
            "flush_count_per_logical_output": 1,
            "final_reduction_source": f"{spec.accumulate_hw_op_id} final INT32 P",
        },
        "shards": shards,
        "execution_boundary": {
            "encoded_kernel": "each shard is a formal DeepSeek Quant-derived GA kernel",
            "not_yet_automated": "typed execplan dispatch and dynamic base-address schedule",
            "hardware_validation": "deferred_by_operator",
        },
    }
    files["manifest.json"] = _canonical_bytes(manifest)
    return manifest, files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate real 64-channel Conv requant shards")
    parser.add_argument("--node-id", default=FIRST_REAL_CONV_NODE_ID)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--check", action="store_true", help="verify checked-in outputs")
    args = parser.parse_args()
    spec = load_conv_instance_spec(PROJECT_ROOT, args.node_id)
    try:
        config_root_relative = args.output.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError as error:
        raise SystemExit("requant output must stay inside the project root") from error
    _, files = build_bundle(spec, config_root_relative=config_root_relative)
    if args.check:
        for name, expected in files.items():
            path = args.output / name
            if not path.exists() or path.read_bytes() != expected:
                raise SystemExit(f"generated requant output differs: {path}")
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (args.output / name).write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
