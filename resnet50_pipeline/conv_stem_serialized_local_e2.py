from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.generate_active_ndpsim_node0004_accumulate_smoke_inputs import (
    _initializer_values,
)

from .hashing import sha256_file
from .operator_config_validator import OperatorConfigValidator


TEST_ID = "r5_conv_stem_hwop0001_serialized_local_e2_v1"
REQUEST_ID = "r5:hwop-0001-00"
NODE_ID = "node-0001"
REQUEST_SHA256 = (
    "36b50b93353c995ea4392dc5bd535fcecfa70f4a032b860ec4cf81128e6824d6"
)
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
SOURCE_CONFIG_REL = Path("conv_full.json")
SOURCE_CONFIG_SHA256 = (
    "c47d1deb6f7cd0e7a729954084ce6f7753085684f2f3fbb403ed79ea4e16fd4a"
)
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
RUNTIME_MANIFEST_REL = Path("artifacts/w3/golden_batch16/manifest.json")
SUBOP_MANIFEST_REL = Path("artifacts/w3/subop_batch16/manifest.json")
ACTIVATION_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-a60f1132af1aa3d0.npy"
)
W3_ACCUMULATOR_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0001-accumulate.npy"
)
CONFIG_ROOT_REL = Path(
    "configs/native_ndp_sim/r5_conv_stem_serialized_local_e2_v1"
)
ARTIFACT_ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5_conv_stem_serialized_local_e2_v1"
)
GRAPH_REL = ARTIFACT_ROOT_REL / "graph.json"
PHYSICAL_ROOT_REL = ARTIFACT_ROOT_REL / "physical"
PHYSICAL_MANIFEST_REL = ARTIFACT_ROOT_REL / "physical_manifest.json"
PATCHSET_REL = Path(
    "contracts/operator_config/"
    "r5_conv_stem_serialized_one_product_patchset_v1.json"
)
CONTRACT_REL = Path(
    "contracts/operator_config/r5_conv_stem_serialized_local_e2_v1.json"
)
FINAL_EXECPLAN_REL = ARTIFACT_ROOT_REL / "execplan_final"

WAVE_SAMPLES = (
    (0, 3, 6, 8, 10, 12, 14),
    (1, 4, 7, 9, 11, 13, 15),
    (2, 5),
)
WAVE_SLICE_COUNTS = (28, 28, 8)
LOGICAL_K = 147
SERIALIZED_K = 148
OUTPUT_H = 112
OUTPUT_W = 112
Q_BLOCKS = 14
OUTPUT_STEPS = 4
OUTPUT_LANES = 16
SPATIAL_LANES = 8
PRODUCT_LANES = 4
X_ZERO_POINT = 114
WEIGHT_BYTES = SERIALIZED_K * OUTPUT_LANES * PRODUCT_LANES
ACTIVATION_BYTES = OUTPUT_H * Q_BLOCKS * SERIALIZED_K * SPATIAL_LANES * PRODUCT_LANES
CORRECTION_BYTES = OUTPUT_LANES * 4
OUTPUT_BYTES = OUTPUT_H * OUTPUT_W * OUTPUT_LANES * 4
OP_ALLOCATION_BYTES = WEIGHT_BYTES + ACTIVATION_BYTES + CORRECTION_BYTES + OUTPUT_BYTES
SLICE_CAPACITY_BYTES = 4 * 6144 * 64 * 16
# Four-way 128-bit-word striping: virtual address bits [1:0] select the
# physical bank and the remaining virtual bits become the compact bank-local
# word offset.  This is a complete permutation of the 26-bit word address.
INTERLEAVE4_REMAPPING = tuple(
    list(range(2, 8))
    + list(range(8, 21))
    + [0, 1]
    + list(range(21, 26))
)


class StemSerializedE2Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StemSerializedE2Error(f"JSON root must be object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mask(count: int) -> str:
    return "0b" + "0" * (28 - count) + "1" * count


def operator_type(wave: int) -> str:
    return f"resnet50_conv_stem_hwop0001_serialized_wave{wave}"


def op_id(wave: int) -> str:
    return f"stem_serialized_w{wave}"


def _loop(source: str | None, end: int, last: int) -> dict[str, Any]:
    return {
        "src_id": source,
        "outmost_loop": 1 if source is None else 0,
        "start": 0,
        "end": end,
        "stride": 1,
        "last_index": last,
    }


def _disabled_loop() -> dict[str, Any]:
    return {
        "src_id": None,
        "outmost_loop": 0,
        "start": 0,
        "end": 0,
        "stride": 0,
        "last_index": 0,
    }


def _pe(source0: str, keep: int, constant: int, source2: str) -> dict[str, Any]:
    return {
        "alu_opcode": "mac",
        "inport2": {
            "src_id": source2,
            "mode": "buffer",
            "keep_last_index": None,
            "constant": 0,
        },
        "inport1": {
            "src_id": None,
            "mode": "constant",
            "keep_last_index": None,
            "constant": constant,
        },
        "inport0": {
            "src_id": source0,
            "mode": "keep",
            "keep_last_index": keep,
            "constant": 0,
        },
    }


def _group(target: str, source: str, row_end: int, row_last: int, col_last: int) -> dict[str, Any]:
    return {
        "target": target,
        "ROW_LC": {
            "src_id": source,
            "start": 0,
            "end": row_end,
            "stride": 1,
            "last_index": row_last,
        },
        "COL_LC": {
            "src_id": None,
            "start": 0,
            "end": 32,
            "stride": 16,
            "last_index": col_last,
        },
    }


def _stream_template(
    *,
    target: str,
    mode: str,
    base_addr: int,
    mem_idx_mode: list[str | None],
    mem_keep: list[int | None],
    idx: list[str | None],
    dim_stride: list[int | None],
    buf_mode: list[str],
    buf_keep: list[int],
    buf_stride: list[int],
    full_last: int | None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "target": target,
        "mode": mode,
        "base_addr": f"0x{base_addr:08X}",
        "mem_idx_mode": mem_idx_mode,
        "mem_idx_keep_last_index": mem_keep,
        "mem_idx_constant": [None, None, None],
        "idx": idx,
        "idx_size": [31, 0, 0],
        "dim_stride": dim_stride,
        "tailing_enable": [0, 0, 0],
        "idx_tailing_range": {
            "low": [None, None, None],
            "up": [None, None, None],
        },
        "address_remapping": None,
        "buf_idx_mode": buf_mode,
        "buf_idx_keep_last_index": buf_keep,
        "buf_spatial_stride": buf_stride,
        "buf_spatial_size": 16,
        "ping_pong": 0,
        "pingpong_last_index": None,
    }
    if mode == "read":
        value.update(
            padding_enable=[0, 0, 0],
            padding_reg_value=None,
            idx_padding_range={
                "low_bound": [None, None, None],
                "up_bound": [None, None, None],
            },
        )
    if full_last is not None:
        value["buf_full_last_index"] = full_last
    return value


def _typed_request(root: Path) -> dict[str, Any]:
    lowering = _load(root / LOWERING_REL)
    matches = [
        row
        for row in lowering.get("requests", [])
        if isinstance(row, dict) and row.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise StemSerializedE2Error("stem typed request is not unique")
    request = matches[0]
    if (
        request.get("request_sha256") != REQUEST_SHA256
        or request.get("identity", {}).get("node_id") != NODE_ID
        or request.get("identity", {}).get("hw_op_type") != "ConvInt32Accumulate"
    ):
        raise StemSerializedE2Error("stem typed request identity differs")
    return request


def build_config(root: Path, wave: int) -> dict[str, Any]:
    if wave not in range(3):
        raise StemSerializedE2Error(f"invalid wave: {wave}")
    source_path = root / SOURCE_CONFIG_REL
    if sha256_file(source_path) != SOURCE_CONFIG_SHA256:
        raise StemSerializedE2Error("trusted Conv topology inventory seed differs")
    source = _load(source_path)
    required = {
        "CONFIG",
        "dram_loop_configs",
        "lc_pe_configs",
        "buffer_loop_configs",
        "buffer_config",
        "stream_engine",
        "n2n",
        "special_array",
    }
    if set(source) != required:
        raise StemSerializedE2Error("trusted Conv topology inventory differs")
    config = deepcopy(source)
    config["CONFIG"] = "11101110"
    config["dram_loop_configs"] = {
        "LC0": _loop(None, 2, 0),
        "LC1": _loop("DRAM_LC.LC0", OUTPUT_H, 1),
        "LC2": _loop("DRAM_LC.LC1", Q_BLOCKS, 2),
        "LC3": _disabled_loop(),
        "LC4": _loop("DRAM_LC.LC2", SERIALIZED_K // 4, 3),
        "LC5": _loop("DRAM_LC.LC4", 4, 4),
        "LC6": _loop("DRAM_LC.LC2", SERIALIZED_K // 4, 3),
        "LC7": _loop("DRAM_LC.LC6", 4, 4),
        "LC8": _disabled_loop(),
        "LC9": _loop("DRAM_LC.LC15", SPATIAL_LANES, 3),
        "LC10": _loop(None, 2, 0),
        "LC11": _loop("DRAM_LC.LC10", OUTPUT_H, 1),
        "LC12": _loop("DRAM_LC.LC11", Q_BLOCKS, 2),
        "LC13": _loop(None, 2, 0),
        "LC14": _loop("DRAM_LC.LC13", OUTPUT_H, 1),
        "LC15": _loop("DRAM_LC.LC14", Q_BLOCKS, 2),
    }
    config["lc_pe_configs"] = {
        "PE0": _pe("DRAM_LC.LC6", 3, 4, "DRAM_LC.LC7"),
        "PE1": _pe("DRAM_LC.LC15", 2, 8, "DRAM_LC.LC9"),
        "PE2": _pe("DRAM_LC.LC4", 3, 4, "DRAM_LC.LC5"),
    }
    config["buffer_loop_configs"] = {
        "GROUP0": _group("A", "DRAM_LC.LC6", 4, 4, 5),
        "GROUP1": _group("B", "DRAM_LC.LC4", 4, 4, 5),
        "GROUP3": _group("C", "DRAM_LC.LC12", 1, 3, 4),
        "GROUP4": _group("D", "DRAM_LC.LC9", 4, 4, 5),
    }
    for name, group in config["buffer_loop_configs"].items():
        group["COL_LC"]["src_id"] = f"{name}.ROW_LC"
    masks = [1] * 8
    config["buffer_config"] = {
        f"buffer{index}": {
            "dst_port": 0,
            "nbr_enable": 0,
            "buf_full_last_index": 2 if index >= 4 else 4,
            "buffer_life_time": 1 if index == 5 else 4,
            "mode": 1 if index in (2, 3) else 0,
            "mask": masks,
            "buf_end_row_addr": 0 if index == 4 else 3,
            "buffer_nbr_cnt": 0,
        }
        for index in range(6)
    }
    # Source mapping uses the same four-bank word striping as the typed graph.
    # Since base addition happens after remapping, region offsets are divided
    # by four and remain bank-local; the native graph planner replaces these
    # mapping-time bases with final graph-wide addresses.
    base = wave * (OP_ALLOCATION_BYTES // 4)
    offsets = {
        "A": 0,
        "B": WEIGHT_BYTES // 4,
        "C": (WEIGHT_BYTES + ACTIVATION_BYTES) // 4,
        "D": (WEIGHT_BYTES + ACTIVATION_BYTES + CORRECTION_BYTES) // 4,
    }
    linear = list(range(16))
    transpose = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]
    config["stream_engine"] = {
        "stream0": _stream_template(
            target="A",
            mode="read",
            base_addr=base + offsets["A"],
            mem_idx_mode=["buffer", "keep", None],
            mem_keep=[4, 0, None],
            idx=["LC_PE.PE0", "DRAM_LC.LC0", None],
            dim_stride=[64, 32, None],
            buf_mode=["keep", "buffer"],
            buf_keep=[4, 5],
            buf_stride=linear,
            full_last=4,
        ),
        "stream1": _stream_template(
            target="B",
            mode="read",
            base_addr=base + offsets["B"],
            mem_idx_mode=["buffer", "keep", "keep"],
            mem_keep=[4, 2, 1],
            idx=["LC_PE.PE2", "DRAM_LC.LC2", "DRAM_LC.LC1"],
            dim_stride=[32, SERIALIZED_K * 32, Q_BLOCKS * SERIALIZED_K * 32],
            buf_mode=["keep", "buffer"],
            buf_keep=[4, 5],
            buf_stride=linear,
            full_last=4,
        ),
        "stream3": _stream_template(
            target="C",
            mode="read",
            base_addr=base + offsets["C"],
            mem_idx_mode=["keep", "keep", "buffer"],
            mem_keep=[0, 1, 2],
            idx=["DRAM_LC.LC10", "DRAM_LC.LC11", "DRAM_LC.LC12"],
            dim_stride=[32, 0, 0],
            buf_mode=["keep", "buffer"],
            buf_keep=[3, 4],
            buf_stride=linear,
            full_last=2,
        ),
        "stream4": _stream_template(
            target="D",
            mode="write",
            base_addr=base + offsets["D"],
            mem_idx_mode=["keep", "buffer", "keep"],
            mem_keep=[0, 3, 1],
            idx=["DRAM_LC.LC13", "LC_PE.PE1", "DRAM_LC.LC14"],
            dim_stride=[32, 64, OUTPUT_W * 64],
            buf_mode=["keep", "buffer"],
            buf_keep=[4, 5],
            buf_stride=transpose,
            full_last=None,
        ),
    }
    config["n2n"] = {}
    for stream in config["stream_engine"].values():
        stream["address_remapping"] = list(INTERLEAVE4_REMAPPING)
    config["special_array"] = {
        "mode": "gemm",
        "bias_enable": 1,
        "data_type": "int8",
        "transout_last_index": 2,
        "inport0": {
            "enable": 1,
            "pingpong_en": 0,
            "pingpong_last_index": None,
            "nbr_enable": 0,
        },
        "inport1": {
            "enable": 1,
            "pingpong_en": 0,
            "pingpong_last_index": None,
            "nbr_enable": 0,
        },
        "inport2": {
            "enable": 1,
            "pingpong_en": 0,
            "pingpong_last_index": None,
            "nbr_enable": 0,
        },
        "outport": {
            "mode": "col",
            "fp32tofp16": "false",
            "fp32tobf16": "false",
        },
    }
    report = OperatorConfigValidator().validate(
        config,
        source=f"{TEST_ID}#wave{wave}",
        development_mode=True,
        expected_sa_transpose=False,
    )
    if not report.valid:
        first = report.issues[0]
        raise StemSerializedE2Error(
            f"stem config rejected: {first.code} at {first.path}: {first.message}"
        )
    return config


def graph_spec() -> dict[str, Any]:
    operators = []
    for wave, count in enumerate(WAVE_SLICE_COUNTS):
        operators.append(
            {
                "id": op_id(wave),
                "type": operator_type(wave),
                "used_slices": _mask(count),
                "inputs": {
                    "A": {
                        "shape": [1, 1, WEIGHT_BYTES],
                        "dtype": "int8",
                        "bank_interleave": 4,
                        "remapping": list(INTERLEAVE4_REMAPPING),
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": [1, 1, ACTIVATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 4,
                        "remapping": list(INTERLEAVE4_REMAPPING),
                        "source": {"type": "external"},
                    },
                    "C": {
                        "shape": [1, 1, CORRECTION_BYTES // 4],
                        "dtype": "int32",
                        "bank_interleave": 4,
                        "remapping": list(INTERLEAVE4_REMAPPING),
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": [1, 1, OUTPUT_BYTES // 4],
                    "dtype": "int32",
                    "bank_interleave": 4,
                    "remapping": list(INTERLEAVE4_REMAPPING),
                },
            }
        )
    return {
        "params": {
            "test_id": TEST_ID,
            "request_id": REQUEST_ID,
            "node_id": NODE_ID,
            "logical_k": LOGICAL_K,
            "serialized_k": SERIALIZED_K,
            "wave_samples": [list(row) for row in WAVE_SAMPLES],
        },
        "operators": operators,
    }


def _stem_values(root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    runtime = _load(root / RUNTIME_MANIFEST_REL)
    subop = _load(root / SUBOP_MANIFEST_REL)
    activation_entry = runtime["tensors"]["tensor-a60f1132af1aa3d0"]
    accumulator_entry = subop["internal_tensors"][
        "tensor-internal-node-0001-accumulate"
    ]
    activation_path = root / "artifacts/w3/golden_batch16" / activation_entry["path"]
    accumulator_path = root / "artifacts/w3/subop_batch16" / accumulator_entry["path"]
    if (
        sha256_file(activation_path) != activation_entry["sha256"]
        or sha256_file(accumulator_path) != accumulator_entry["sha256"]
    ):
        raise StemSerializedE2Error("W3 stem tensor receipt differs")
    activation = np.load(activation_path)
    accumulator = np.load(accumulator_path)
    values = _initializer_values(root / MODEL_REL)
    weight = values["ConvBnFusion_W_resnetv17_conv0_weight_quantized"]
    bias = values["ConvBnFusion_BN_B_resnetv17_batchnorm0_beta_quantized"]
    xzp = values["data_zero_point"]
    wzp = values["ConvBnFusion_W_resnetv17_conv0_weight_zero_point"]
    if (
        activation.shape != (16, 3, 224, 224)
        or activation.dtype != np.uint8
        or weight.shape != (64, 3, 7, 7)
        or weight.dtype != np.int8
        or bias.shape != (64,)
        or bias.dtype != np.int32
        or accumulator.shape != (16, 64, 112, 112)
        or accumulator.dtype != np.int32
        or int(xzp.reshape(-1)[0]) != X_ZERO_POINT
        or np.count_nonzero(wzp) != 0
    ):
        raise StemSerializedE2Error("stem W3 typed values differ")
    return activation, weight, bias, accumulator


def _write_npy(path: Path, value: np.ndarray) -> dict[str, Any]:
    np.save(path, value, allow_pickle=False)
    return {
        "path": path.as_posix(),
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def materialize_inputs(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    _typed_request(root)
    config_root = root / CONFIG_ROOT_REL
    artifact_root = root / ARTIFACT_ROOT_REL
    physical_root = root / PHYSICAL_ROOT_REL
    for path in (config_root, artifact_root):
        if path.exists():
            raise StemSerializedE2Error(f"refusing to overwrite generated path: {path}")
    config_root.mkdir(parents=True)
    physical_root.mkdir(parents=True)
    for wave in range(3):
        _write_json(config_root / f"wave-{wave}.json", build_config(root, wave))
    _write_json(
        config_root / "manifest.json",
        {
            "schema": "resnet50-conv-stem-serialized-config-manifest-v1",
            "source_inventory": {
                "path": SOURCE_CONFIG_REL.as_posix(),
                "sha256": SOURCE_CONFIG_SHA256,
                "semantic_owner": False,
            },
            "request_id": REQUEST_ID,
            "request_sha256": REQUEST_SHA256,
            "configs": {
                op_id(wave): {
                    "path": f"wave-{wave}.json",
                    "sha256": sha256_file(config_root / f"wave-{wave}.json"),
                    "operator_type": operator_type(wave),
                }
                for wave in range(3)
            },
        },
    )
    _write_json(root / GRAPH_REL, graph_spec())

    activation, weight, bias, accumulator = _stem_values(root)
    flat_weight = weight.reshape(64, LOGICAL_K)
    weight_lanes = np.zeros(
        (OUTPUT_STEPS, SERIALIZED_K, OUTPUT_LANES, PRODUCT_LANES),
        dtype=np.int8,
    )
    for step in range(OUTPUT_STEPS):
        for k in range(LOGICAL_K):
            weight_lanes[step, k, :, k & 3] = flat_weight[
                step * OUTPUT_LANES : (step + 1) * OUTPUT_LANES, k
            ]
    correction = (
        bias.astype(np.int64)
        - X_ZERO_POINT * flat_weight.astype(np.int64).sum(axis=1)
    ).astype(np.uint32).view(np.int32).reshape(OUTPUT_STEPS, OUTPUT_LANES)

    padded = np.pad(
        activation,
        ((0, 0), (0, 0), (3, 3), (3, 3)),
        constant_values=X_ZERO_POINT,
    )
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (7, 7), axis=(2, 3)
    )[:, :, ::2, ::2]
    logical_x = (
        windows.transpose(0, 2, 3, 1, 4, 5)
        .reshape(16, OUTPUT_H, OUTPUT_W, LOGICAL_K)
    )
    logical_x = logical_x.reshape(16, OUTPUT_H, Q_BLOCKS, SPATIAL_LANES, LOGICAL_K)
    activation_shape = (
        16,
        OUTPUT_STEPS,
        OUTPUT_H,
        Q_BLOCKS,
        SERIALIZED_K,
        SPATIAL_LANES,
        PRODUCT_LANES,
    )
    activation_path = physical_root / "activation_u8.npy"
    activation_lanes = np.lib.format.open_memmap(
        activation_path, mode="w+", dtype=np.uint8, shape=activation_shape
    )
    activation_lanes[:] = 0
    for k in range(LOGICAL_K):
        lane = k & 3
        activation_lanes[:, :, :, :, k, :, lane] = logical_x[
            ..., k
        ][:, None, :, :, :]
    for step in range(OUTPUT_STEPS):
        activation_lanes[:, step, :, :, LOGICAL_K, :, LOGICAL_K & 3] = X_ZERO_POINT
    activation_lanes.flush()
    del activation_lanes

    expected = (
        accumulator.reshape(16, OUTPUT_STEPS, OUTPUT_LANES, OUTPUT_H, OUTPUT_W)
        .transpose(0, 1, 3, 4, 2)
        .reshape(16, OUTPUT_STEPS, OUTPUT_H, Q_BLOCKS, SPATIAL_LANES, OUTPUT_LANES)
    )
    assets = {
        "weight_s8": _write_npy(physical_root / "weight_s8.npy", weight_lanes),
        "activation_u8": {
            "path": (physical_root / "activation_u8.npy").as_posix(),
            "shape": list(activation_shape),
            "dtype": "uint8",
            "bytes": activation_path.stat().st_size,
            "sha256": sha256_file(activation_path),
        },
        "correction_s32": _write_npy(
            physical_root / "correction_s32.npy", correction
        ),
        "expected_d_s32": _write_npy(
            physical_root / "expected_d_s32.npy", expected
        ),
    }
    physical_manifest = {
        "schema": "resnet50-conv-stem-serialized-physical-assets-v1",
        "request_id": REQUEST_ID,
        "source_ownership": {
            "activation": {
                "kind": "formal_producer_output",
                "path": ACTIVATION_REL.as_posix(),
                "sha256": sha256_file(root / ACTIVATION_REL),
            },
            "weight_bias": {
                "kind": "frozen_onnx_initializers",
                "model": MODEL_REL.as_posix(),
                "model_sha256": sha256_file(root / MODEL_REL),
            },
            "golden": {
                "kind": "oracle_only_not_compute_input",
                "path": W3_ACCUMULATOR_REL.as_posix(),
                "sha256": sha256_file(root / W3_ACCUMULATOR_REL),
            },
        },
        "packing": {
            "k_order": "input_channel,kernel_h,kernel_w",
            "active_lane": "k mod 4 for k<147",
            "padded_k": 147,
            "padded_weight": 0,
            "padded_activation": X_ZERO_POINT,
            "inactive_lanes": 0,
            "input_padding_value": X_ZERO_POINT,
        },
        "assets": assets,
    }
    _write_json(root / PHYSICAL_MANIFEST_REL, physical_manifest)
    return {
        "config_manifest": str(config_root / "manifest.json"),
        "graph": str(root / GRAPH_REL),
        "physical_manifest": str(root / PHYSICAL_MANIFEST_REL),
        "physical_bytes": sum(row["bytes"] for row in assets.values()),
    }


def validate_physical_assets(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    manifest = _load(root / PHYSICAL_MANIFEST_REL)
    for row in manifest["assets"].values():
        if sha256_file(Path(row["path"])) != row["sha256"]:
            raise StemSerializedE2Error("physical asset SHA differs")
    physical = root / PHYSICAL_ROOT_REL
    weights = np.load(physical / "weight_s8.npy", mmap_mode="r")
    activations = np.load(physical / "activation_u8.npy", mmap_mode="r")
    correction = np.load(physical / "correction_s32.npy", mmap_mode="r")
    expected = np.load(physical / "expected_d_s32.npy", mmap_mode="r")
    if (
        weights.shape
        != (OUTPUT_STEPS, SERIALIZED_K, OUTPUT_LANES, PRODUCT_LANES)
        or activations.shape
        != (
            16,
            OUTPUT_STEPS,
            OUTPUT_H,
            Q_BLOCKS,
            SERIALIZED_K,
            SPATIAL_LANES,
            PRODUCT_LANES,
        )
        or correction.shape != (OUTPUT_STEPS, OUTPUT_LANES)
        or expected.shape
        != (
            16,
            OUTPUT_STEPS,
            OUTPUT_H,
            Q_BLOCKS,
            SPATIAL_LANES,
            OUTPUT_LANES,
        )
    ):
        raise StemSerializedE2Error("physical asset shape differs")
    for lane in range(PRODUCT_LANES):
        inactive = [index for index in range(PRODUCT_LANES) if index != lane]
        ks = np.arange(lane, SERIALIZED_K, PRODUCT_LANES)
        if np.count_nonzero(weights[:, ks, :, :][:, :, :, inactive]):
            raise StemSerializedE2Error("weight inactive product lane is nonzero")
        if np.count_nonzero(activations[:, :, :, :, ks, :, :][..., inactive]):
            raise StemSerializedE2Error("activation inactive product lane is nonzero")
    if np.count_nonzero(weights[:, LOGICAL_K]):
        raise StemSerializedE2Error("K tail weight is nonzero")
    collapsed_w = weights.sum(axis=-1, dtype=np.int16)
    simulated = np.empty_like(expected)
    mismatch = 0
    for sample in range(16):
        for step in range(OUTPUT_STEPS):
            collapsed_x = activations[sample, step].sum(axis=-1, dtype=np.uint16)
            wide = np.einsum(
                "hbks,kc->hbsc",
                collapsed_x.astype(np.int64),
                collapsed_w[step].astype(np.int64),
                optimize=True,
            )
            wide += correction[step]
            result = wide.astype(np.uint32).view(np.int32)
            simulated[sample, step] = result
            mismatch += int(np.count_nonzero(result != expected[sample, step]))
    if mismatch:
        raise StemSerializedE2Error(f"config-bound W3 mismatch count: {mismatch}")
    expected_offsets = {
        row * (OUTPUT_W * OUTPUT_LANES * 4)
        + (block * SPATIAL_LANES + q) * (OUTPUT_LANES * 4)
        + half * 32
        + byte
        for row in range(OUTPUT_H)
        for block in range(Q_BLOCKS)
        for q in range(SPATIAL_LANES)
        for half in range(2)
        for byte in range(32)
    }
    if (
        len(expected_offsets) != OUTPUT_BYTES
        or min(expected_offsets) != 0
        or max(expected_offsets) != OUTPUT_BYTES - 1
    ):
        raise StemSerializedE2Error("D physical coverage is not contiguous")
    return {
        "schema": "resnet50-conv-stem-serialized-physical-validation-v1",
        "valid": True,
        "logical_k": LOGICAL_K,
        "serialized_k": SERIALIZED_K,
        "serialized_occurrences": 1_901_068_288,
        "normal_dot4_occurrences": 475_267_072,
        "occurrence_ratio": 4.0,
        "lane_utilization": LOGICAL_K / (SERIALIZED_K * PRODUCT_LANES),
        "nonzero_product_lanes_per_occurrence_max": 1,
        "k_tail": {"k": 147, "weight_zero": True},
        "x_zero_point": X_ZERO_POINT,
        "bias_xzp_correction": "bit-exact modulo-s32",
        "config_bound_w3_mismatch": 0,
        "d_coverage": {
            "bytes": OUTPUT_BYTES,
            "unique_offsets": len(expected_offsets),
            "minimum": 0,
            "maximum": OUTPUT_BYTES - 1,
            "terminal_contiguous": True,
        },
        "physical_manifest_sha256": sha256_file(root / PHYSICAL_MANIFEST_REL),
    }


__all__ = [
    "ARTIFACT_ROOT_REL",
    "CONFIG_ROOT_REL",
    "CONTRACT_REL",
    "FINAL_EXECPLAN_REL",
    "GRAPH_REL",
    "PATCHSET_REL",
    "PHYSICAL_MANIFEST_REL",
    "StemSerializedE2Error",
    "build_config",
    "graph_spec",
    "materialize_inputs",
    "op_id",
    "operator_type",
    "validate_physical_assets",
]
