#!/usr/bin/env python3
"""Materialize the df23e4d node0075 diagnostic target in active ndp-sim.

The target keeps logical QLinearMatMul ports intact while binding the UINT8 A
port to the approved node0071-owned slice-local allocation.  The eight A
reloads are real consumer stream occurrences; no A preload file is emitted.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper


ROOT = Path(__file__).resolve().parents[1]
NDP = ROOT / "ndp-sim"
TEST_ID = "r5-node0075-df23e4d-eight-pass-materializer-v1"
TARGET_STEM = "node0075_df23e4d_eight_pass_target"
OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
TARGET = OUT / f"{TARGET_STEM}.json"
PIPELINE_OUT = NDP / "model_execplan/output" / TARGET_STEM
ACTIVE_SLICES = tuple(range(16))
USED_SLICES = sum(1 << slice_id for slice_id in ACTIVE_SLICES)
K = 2048
N = 1000
PHYSICAL_PASS_N = 128
PASS_COUNT = 8
A_LOCAL_BASE = 0x000A2000
SLICE_STRIDE = 1 << 25
FINAL_D_LOCAL_BASE = 0x01700000
MULTIPLIER_BITS = 0x3A510DB3
MULTIPLIER = np.array([MULTIPLIER_BITS], dtype=np.uint32).view(np.float32)[0]
Y_ZERO_POINT = 60
MAGIC = np.float32(12582912.0)
MAGIC_BITS = 0x4B400000
APPROVED_SLICE0_ORDERED_ADDRESS_SHA256 = (
    "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
)
APPROVED_SLICE0_READ_BYTE_SET_SHA256 = (
    "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
)

MODEL = ROOT / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
A_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
ACC_NPY = ROOT / "artifacts/w3/subop_batch16/tensors/tensor-internal-node-0075-accumulate.npy"
D_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6cc774b369e8dea4.npy"
ACCUM_MAPPING_CACHE = NDP / "bitstream/config/mapping_cache/fab05601add9259e.json"
TAIL_MAPPING_CACHE = NDP / "bitstream/config/mapping_cache/96a15d1499ab2ed0.json"


class MaterializerError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaterializerError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _materialize_accumulate_template() -> Path:
    source = NDP / "jsons/prefill_gemm_local.json"
    payload = copy.deepcopy(_read_json(source))
    loops = payload["dram_loop_configs"]
    for name, end in {
        "LC0": 16,
        "LC1": 64,
        "LC2": 8,
        "LC3": 1,
        "LC4": 64,
        "LC5": 8,
        "LC6": 16,
        "LC7": 1,
    }.items():
        loops[name]["end"] = end

    buffers = payload["buffer_config"]
    buffers["buffer0"]["buffer_life_time"] = 1
    buffers["buffer1"]["buffer_life_time"] = 16
    buffers["buffer2"]["buffer_life_time"] = 1
    buffers["buffer3"]["buffer_life_time"] = 1
    payload["stream_engine"]["stream1"]["buf_spatial_stride"] = [
        0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1
    ]
    special = payload["special_array"]
    special["mode"] = "gemm"
    special["bias_enable"] = 0
    special["data_type"] = "int8"
    special["outport"]["mode"] = "col"
    special["outport"]["fp32tofp16"] = "false"
    special["outport"]["fp32tobf16"] = "false"
    destination = NDP / "jsons/MatMulInt32Accumulate.json"
    _write_json(destination, payload)
    return destination


def _materialize_scale_template() -> Path:
    source = (
        ROOT
        / "configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v2/round_saturate.json"
    )
    payload = copy.deepcopy(_read_json(source))
    payload["dram_loop_configs"]["LC0"]["end"] = 4
    payload["dram_loop_configs"]["LC1"]["end"] = 4
    payload["dram_loop_configs"]["LC2"]["end"] = 4
    pe_array = payload["general_array"]["PE_array"]
    for key in list(pe_array):
        if int(key[-1]) % 2:
            del pe_array[key]
            continue
        pe = pe_array[key]
        pe["alu_opcode"] = "mul"
        pe["inport1"] = {
            "src_id": None,
            "mode": "constant",
            "keep_last_index": None,
            "constant": float(MULTIPLIER),
        }
        pe["inport2"] = {
            "src_id": None,
            "mode": None,
            "keep_last_index": None,
            "constant": 0,
        }
    inports = payload["general_array"]["inport"]
    inports["inport0"]["int32tofp32"] = "true"
    payload["general_array"]["outport"]["src_id"] = 0
    payload["general_array"]["outport"]["int32touint8"] = "false"
    destination = NDP / "jsons/Node0075RequantScaleInt32ToFp32.json"
    _write_json(destination, payload)
    return destination


def _materialize_round_template() -> Path:
    source = (
        ROOT
        / "configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v2/round_saturate.json"
    )
    payload = copy.deepcopy(_read_json(source))
    payload["dram_loop_configs"]["LC0"]["end"] = 4
    payload["dram_loop_configs"]["LC1"]["end"] = 4
    payload["dram_loop_configs"]["LC2"]["end"] = 4
    pe_array = payload["general_array"]["PE_array"]
    for key, pe in pe_array.items():
        if int(key[-1]) % 2 == 0:
            pe["inport1"]["constant"] = 1.0
            pe["inport2"]["constant"] = float(MAGIC)
        else:
            pe["inport1"]["constant"] = MAGIC_BITS - Y_ZERO_POINT
    payload["general_array"]["inport"]["inport0"]["int32tofp32"] = "false"
    payload["general_array"]["outport"]["int32touint8"] = "true"
    destination = NDP / "jsons/Node0075RequantRoundFp32ToUint8.json"
    _write_json(destination, payload)
    return destination


def _common_attributes(pass_index: int) -> dict[str, Any]:
    n_start = pass_index * PHYSICAL_PASS_N
    logical_count = min(PHYSICAL_PASS_N, N - n_start)
    return {
        "node_id": "node-0075",
        "request_id": "r5:hwop-0075-00",
        "pass_index": pass_index,
        "n_start": n_start,
        "n_count": logical_count,
        "physical_n_count": PHYSICAL_PASS_N,
        "reload_pass_count": PASS_COUNT,
        "diagnostic_only": True,
    }


def _source_external() -> dict[str, str]:
    return {"type": "external"}


def _source_operator(op_id: str) -> dict[str, str]:
    return {"type": "operator", "operator_id": op_id}


def _a_alias_binding() -> dict[str, Any]:
    return {
        "kind": "existing_storage_alias",
        "allocation_owner": "r5:hwop-0071-01:D",
        "storage_id": (
            "r5:activation:node-0071:D:tensor-ab32f279540568c3:"
            "batch-slice-sharded-16x2048-v1"
        ),
        "per_slice_base_addresses": {
            str(slice_id): f"0x{A_LOCAL_BASE + slice_id * SLICE_STRIDE:08x}"
            for slice_id in ACTIVE_SLICES
        },
        "host_materialized": False,
    }


def _fixed_d_binding(pass_index: int) -> dict[str, Any]:
    local = FINAL_D_LOCAL_BASE + pass_index * PHYSICAL_PASS_N
    return {
        "kind": "fixed_formal_endpoint_fragment",
        "logical_valid_bytes": min(PHYSICAL_PASS_N, N - pass_index * PHYSICAL_PASS_N),
        "physical_bytes": PHYSICAL_PASS_N,
        "padding_value": Y_ZERO_POINT,
        "per_slice_base_addresses": {
            str(slice_id): f"0x{local + slice_id * SLICE_STRIDE:08x}"
            for slice_id in ACTIVE_SLICES
        },
    }


def _build_target() -> dict[str, Any]:
    operators: list[dict[str, Any]] = []
    for pass_index in range(PASS_COUNT):
        attrs = _common_attributes(pass_index)
        attrs.update(
            {
                "a_zero_point": 0,
                "b_zero_point": 0,
                "initial_psum": 0,
                "logical_rank": 2,
                "logical_A_shape": [16, K],
                "logical_B_shape": [K, N],
                "logical_D_shape": [16, N],
                "physical_bindings": {"inputs": {"A": _a_alias_binding()}},
                "producer_visibility_precondition": (
                    "node0071 final uint8 D byte-set accepted AND node0071 completion/final barrier accepted"
                ),
                "emit_formal_readback": False,
            }
        )
        op_id = f"node0075_accum_pass{pass_index:02d}"
        operators.append(
            {
                "id": op_id,
                "type": "MatMulInt32Accumulate",
                "used_slices": f"0b{USED_SLICES:028b}",
                "attributes": attrs,
                "inputs": {
                    "A": {"shape": [1, 1, K], "dtype": "uint8", "source": _source_external()},
                    "B": {
                        "shape": [1, K, PHYSICAL_PASS_N],
                        "dtype": "int8",
                        "source": _source_external(),
                    },
                    "B'": {
                        "shape": [1, K, PHYSICAL_PASS_N],
                        "dtype": "int8",
                        "source": _source_external(),
                    },
                },
                "output": {"shape": [1, 1, PHYSICAL_PASS_N], "dtype": "int32"},
            }
        )

    for pass_index in range(PASS_COUNT):
        attrs = _common_attributes(pass_index)
        attrs.update(
            {
                "request_id": "r5:hwop-0075-01",
                "requant_multiplier_bits": f"0x{MULTIPLIER_BITS:08x}",
                "numeric_order": "int32_to_fp32_then_mul_then_explicit_fp32_scratch",
                "emit_formal_readback": False,
            }
        )
        operators.append(
            {
                "id": f"node0075_scale_pass{pass_index:02d}",
                "type": "Node0075RequantScaleInt32ToFp32",
                "used_slices": f"0b{USED_SLICES:028b}",
                "attributes": attrs,
                "inputs": {
                    "A": {
                        "shape": [1, 1, PHYSICAL_PASS_N],
                        "dtype": "int32",
                        "source": _source_operator(f"node0075_accum_pass{pass_index:02d}"),
                    }
                },
                "output": {"shape": [1, 1, PHYSICAL_PASS_N], "dtype": "fp32"},
            }
        )

    for pass_index in range(PASS_COUNT):
        attrs = _common_attributes(pass_index)
        attrs.update(
            {
                "request_id": "r5:hwop-0075-01",
                "y_zero_point": Y_ZERO_POINT,
                "magic_bits": f"0x{MAGIC_BITS:08x}",
                "subtract_constant": MAGIC_BITS - Y_ZERO_POINT,
                "numeric_order": "raw_fp32_plus_fixed_magic_then_int32_sub_then_uint8_saturate",
                "physical_bindings": {"output": _fixed_d_binding(pass_index)},
                "emit_formal_readback": True,
            }
        )
        operators.append(
            {
                "id": f"node0075_round_pass{pass_index:02d}",
                "type": "Node0075RequantRoundFp32ToUint8",
                "used_slices": f"0b{USED_SLICES:028b}",
                "attributes": attrs,
                "inputs": {
                    "A": {
                        "shape": [1, 1, PHYSICAL_PASS_N],
                        "dtype": "fp32",
                        "source": _source_operator(f"node0075_scale_pass{pass_index:02d}"),
                    }
                },
                "output": {"shape": [1, 1, PHYSICAL_PASS_N], "dtype": "uint8"},
            }
        )

    return {
        "schema": "node0075-qlinearmatmul-rank2-diagnostic-target-v1",
        "params": {
            "node_id": "node-0075",
            "M": 16,
            "K": K,
            "N": N,
            "physical_padded_N": PASS_COUNT * PHYSICAL_PASS_N,
            "candidate_release": False,
        },
        "used_slices": f"0b{USED_SLICES:028b}",
        "operators": operators,
    }


def _run_pipeline() -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(NDP / "model_execplan/main.py"),
        str(TARGET),
        "--dump-normalized-json",
        str(OUT / "normalized_target.json"),
    ]
    return subprocess.run(
        command,
        cwd=NDP,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _canonicalize_mapping_reviews() -> list[Path]:
    """Remove set-iteration ordering noise from mapper review receipts."""
    paths = sorted((PIPELINE_OUT / "config").glob("*/mapping_review.json"))
    for path in paths:
        payload = _read_json(path)
        nodes = payload.get("node_to_resource")
        connections = payload.get("connection_mapping")
        if not isinstance(nodes, list) or not isinstance(connections, list):
            raise MaterializerError(f"invalid mapping review schema: {path}")
        payload["node_to_resource"] = sorted(
            nodes,
            key=lambda item: (str(item.get("node", "")), str(item.get("resource", ""))),
        )
        payload["connection_mapping"] = sorted(
            connections,
            key=lambda item: (
                str(item.get("src_node", "")),
                str(item.get("src_resource", "")),
                str(item.get("dst_node", "")),
                str(item.get("dst_resource", "")),
            ),
        )
        _write_json(path, payload)
    return paths


def _load_weight() -> np.ndarray:
    model = onnx.load(MODEL, load_external_data=True)
    for tensor in model.graph.initializer:
        if tensor.name == "resnetv17_dense0_weight_quantized":
            value = np.ascontiguousarray(numpy_helper.to_array(tensor, base_dir=str(MODEL.parent)))
            if value.dtype != np.int8 or value.shape != (K, N):
                raise MaterializerError(f"unexpected weight: {value.dtype} {value.shape}")
            return value
    raise MaterializerError("node0075 weight initializer not found")


def _pack_weight_pass(weight: np.ndarray, pass_index: int) -> bytes:
    n_start = pass_index * PHYSICAL_PASS_N
    logical_count = min(PHYSICAL_PASS_N, N - n_start)
    tile = np.zeros((K, PHYSICAL_PASS_N), dtype=np.int8)
    tile[:, :logical_count] = weight[:, n_start : n_start + logical_count]
    words: list[bytes] = []
    for output_group in range(PHYSICAL_PASS_N // 8):
        for k_chunk in range(K // 32):
            for dot4_subgroup in range(8):
                packed = bytearray()
                k_start = k_chunk * 32 + dot4_subgroup * 4
                for output_lane in range(8):
                    packed.extend(tile[k_start : k_start + 4, output_group * 8 + output_lane].tobytes())
                if len(packed) != 32:
                    raise MaterializerError("weight word is not 32 bytes")
                words.append(bytes(packed))
    payload = b"".join(words)
    if len(payload) != K * PHYSICAL_PASS_N:
        raise MaterializerError(f"weight pass payload size mismatch: {len(payload)}")
    return payload


def _write_matrix_files(root: Path, port: str, payload: bytes, dtype: np.dtype[Any]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    raw = root / f"matrix_{port}_linearized_128bit.bin"
    text = root / f"matrix_{port}_linearized_128bit.txt"
    decimal = root / f"matrix_{port}_linearized_128bit_decimal_1d.txt"
    raw.write_bytes(payload)
    lines = [
        f"{int.from_bytes(payload[offset:offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    text.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    values = np.frombuffer(payload, dtype=dtype)
    decimal.write_text(
        "\n".join(str(int(value)) for value in values) + "\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        "raw_bytes": len(payload),
        "raw_sha256": _sha256_bytes(payload),
        "text_sha256": _sha256_file(text),
        "line_count_128bit": len(lines),
    }


def _materialize_weight_payloads(weight: np.ndarray) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pass_index in range(PASS_COUNT):
        payload = _pack_weight_pass(weight, pass_index)
        slice_records = []
        for slice_id in ACTIVE_SLICES:
            destination = (
                PIPELINE_OUT
                / "install"
                / f"node0075_accum_pass{pass_index:02d}"
                / f"slice{slice_id:02d}"
            )
            receipt = _write_matrix_files(destination, "B", payload, np.dtype(np.int8))
            slice_records.append({"slice_id": slice_id, **receipt})
        records.append(
            {
                "pass_index": pass_index,
                "logical_n_count": min(PHYSICAL_PASS_N, N - pass_index * PHYSICAL_PASS_N),
                "physical_n_count": PHYSICAL_PASS_N,
                "payload_sha256": _sha256_bytes(payload),
                "payload_bytes_per_slice": len(payload),
                "slice_records": slice_records,
            }
        )
    return records


def _a_coverage() -> dict[str, Any]:
    passes = []
    all_occurrences: list[dict[str, int]] = []
    for pass_index in range(PASS_COUNT):
        slice_records = []
        pass_addresses: list[int] = []
        for slice_id in ACTIVE_SLICES:
            base = A_LOCAL_BASE + slice_id * SLICE_STRIDE
            addresses = [base + transaction * 32 for transaction in range(64)]
            byte_set = sorted(
                byte
                for address in addresses
                for byte in range(address, address + 32)
            )
            slice_records.append(
                {
                    "slice_id": slice_id,
                    "base_addr": f"0x{base:08x}",
                    "accepted_occurrence_count": 64,
                    "ordered_address_sha256": _canonical_sha256(addresses),
                    "read_byte_set_sha256": _canonical_sha256(byte_set),
                    "first_address": f"0x{addresses[0]:08x}",
                    "last_address": f"0x{addresses[-1]:08x}",
                }
            )
            pass_addresses.extend(addresses)
            all_occurrences.extend(
                {
                    "pass_index": pass_index,
                    "slice_id": slice_id,
                    "transaction_index": transaction,
                    "address": address,
                    "bytes": 32,
                }
                for transaction, address in enumerate(addresses)
            )
        passes.append(
            {
                "pass_index": pass_index,
                "ordered_address_sha256": _canonical_sha256(pass_addresses),
                "accepted_occurrence_count": len(pass_addresses),
                "accepted_traffic_bytes": len(pass_addresses) * 32,
                "slice_records": slice_records,
            }
        )
    unique_bytes = sorted(
        {
            byte
            for item in all_occurrences
            for byte in range(item["address"], item["address"] + item["bytes"])
        }
    )
    slice0 = passes[0]["slice_records"][0]
    if slice0["ordered_address_sha256"] != APPROVED_SLICE0_ORDERED_ADDRESS_SHA256:
        raise MaterializerError("slice0 ordered A address hash drifted from approved alias")
    if slice0["read_byte_set_sha256"] != APPROVED_SLICE0_READ_BYTE_SET_SHA256:
        raise MaterializerError("slice0 A byte-set hash drifted from approved alias")
    if len(all_occurrences) != 8192 or len(unique_bytes) != 32768:
        raise MaterializerError("eight-pass A traffic accounting drifted")
    return {
        "reload_pass_count": PASS_COUNT,
        "accepted_occurrence_count": len(all_occurrences),
        "accepted_traffic_bytes": sum(item["bytes"] for item in all_occurrences),
        "unique_consumer_byte_count": len(unique_bytes),
        "unique_read_byte_set_sha256": _canonical_sha256(unique_bytes),
        "occurrence_sha256": _canonical_sha256(all_occurrences),
        "passes": passes,
        "producer_final_to_first_read_barrier": {
            "producer_event": (
                "node0071 final uint8 D byte-set accepted AND node0071 completion/final barrier accepted"
            ),
            "consumer_event": "node0075_accum_pass00 first qualified rd_stream1 data acceptance",
            "ordering": "producer_event happens-before consumer_event",
            "config_bound_materialization": (
                "accepted producer visibility receipt composed with typed target precondition "
                "and first configured consumer occurrence"
            ),
            "cross_operator_execplan_barrier_materialized": False,
            "dynamic_consumer_acceptance_observed": False,
        },
        "release": {
            "event": "node0075_accum_pass07 last qualified rd_stream1 data acceptance",
            "pending_consumer_reads": 0,
            "replayed_consumer_reads": 0,
            "allocation_owner_retained": "r5:hwop-0071-01:D",
            "claim_kind": "configured terminal/lifetime equation",
            "dynamic_release_observed": False,
        },
        "count_semantics": (
            "accepted_* fields are configured qualified consumer occurrences at E2; "
            "they are not server/runtime acceptance observations"
        ),
    }


def _local_e2(weight: np.ndarray) -> dict[str, Any]:
    activation = np.load(A_NPY, allow_pickle=False)
    expected_acc = np.load(ACC_NPY, allow_pickle=False)
    expected_d = np.load(D_NPY, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (16, K):
        raise MaterializerError("unexpected node0075 A tensor")
    computed_acc64 = activation.astype(np.int64) @ weight.astype(np.int64)
    computed_acc = computed_acc64.astype(np.int32)
    acc_mismatch = int(np.count_nonzero(computed_acc != expected_acc))

    padded_acc = np.zeros((16, PASS_COUNT * PHYSICAL_PASS_N), dtype=np.int32)
    padded_acc[:, :N] = computed_acc
    fp32_ingress = padded_acc.astype(np.float32)
    scaled = np.multiply(fp32_ingress, np.float32(MULTIPLIER), dtype=np.float32)
    magic_sum = np.add(scaled, MAGIC, dtype=np.float32)
    decoded = magic_sum.view(np.int32).astype(np.int64) - MAGIC_BITS + Y_ZERO_POINT
    quantized = np.clip(decoded, 0, 255).astype(np.uint8)
    d_mismatch = int(np.count_nonzero(quantized[:, :N] != expected_d))
    padding_mismatch = int(np.count_nonzero(quantized[:, N:] != Y_ZERO_POINT))

    patched_jsons = sorted((PIPELINE_OUT / "jsons").glob("*.json"))
    mapping_reviews = sorted((PIPELINE_OUT / "config").glob("*/mapping_review.json"))
    bitstreams_128 = sorted((PIPELINE_OUT / "config").glob("*/*bitstream_128b.bin"))
    bitstreams_64 = sorted((PIPELINE_OUT / "config").glob("*/*bitstream_64b.bin"))
    execplan = PIPELINE_OUT / "install/execplan.txt"
    sca = PIPELINE_OUT / "sca_cfg.json"
    sca_d = PIPELINE_OUT / "sca_cfg_D.json"
    sca_payload = _read_json(sca)
    forbidden_a_preloads = sorted(key for key in sca_payload if "_matrixA_" in key)
    expected_b_preloads = sorted(key for key in sca_payload if "_matrixB_" in key)
    sca_d_payload = _read_json(sca_d)

    passed = (
        acc_mismatch == 0
        and d_mismatch == 0
        and padding_mismatch == 0
        and len(patched_jsons) == 24
        and len(mapping_reviews) == 24
        and len(bitstreams_128) == 24
        and len(bitstreams_64) == 24
        and execplan.is_file()
        and not forbidden_a_preloads
        and len(expected_b_preloads) == 8 * 16
        and len(sca_d_payload) == 8 * 16
    )
    return {
        "status": "CONFIG_BOUND_LOCAL_E2_PASS" if passed else "CONFIG_BOUND_LOCAL_E2_FAIL",
        "passed": passed,
        "accumulator_mismatch_count": acc_mismatch,
        "uint8_d_mismatch_count": d_mismatch,
        "padding_value": Y_ZERO_POINT,
        "padding_element_count": 16 * (PASS_COUNT * PHYSICAL_PASS_N - N),
        "padding_mismatch_count": padding_mismatch,
        "patched_json_count": len(patched_jsons),
        "mapping_review_count": len(mapping_reviews),
        "bitstream_128b_count": len(bitstreams_128),
        "bitstream_64b_count": len(bitstreams_64),
        "execplan_present": execplan.is_file(),
        "sca_present": sca.is_file(),
        "sca_d_present": sca_d.is_file(),
        "forbidden_a_preload_keys": forbidden_a_preloads,
        "b_preload_key_count": len(expected_b_preloads),
        "formal_d_fragment_count": len(sca_d_payload),
        "frozen_inputs": {
            "A": _identity(A_NPY),
            "accumulator": _identity(ACC_NPY),
            "D": _identity(D_NPY),
        },
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    templates = [
        _materialize_accumulate_template(),
        _materialize_scale_template(),
        _materialize_round_template(),
    ]
    target = _build_target()
    _write_json(TARGET, target)
    pipeline = _run_pipeline()
    (OUT / "pipeline.stdout.log").write_text(
        pipeline.stdout, encoding="utf-8", newline="\n"
    )
    (OUT / "pipeline.stderr.log").write_text(
        pipeline.stderr, encoding="utf-8", newline="\n"
    )
    if pipeline.returncode != 0:
        raise MaterializerError(
            f"active ndp-sim pipeline failed rc={pipeline.returncode}: {pipeline.stderr[-4000:]}"
        )

    canonical_mapping_reviews = _canonicalize_mapping_reviews()

    weight = _load_weight()
    expected_acc = np.load(ACC_NPY, allow_pickle=False)
    weight_records = _materialize_weight_payloads(weight)
    coverage = _a_coverage()
    e2 = _local_e2(weight)
    report = {
        "schema": "node0075-df23e4d-eight-pass-materializer-report-v1",
        "test_id": TEST_ID,
        "status": e2["status"],
        "owner": {
            "operator_family": "QLinearMatMul/node0075",
            "owner_thread": "019fc775-8de0-7f10-bc4a-026a4673776f",
            "mainline_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        },
        "claim_boundary": (
            "deterministic diagnostic-only compositional local materialization and "
            "config-bound E2 under the approved producer-visibility precondition; "
            "no cross-operator execplan barrier, server upload/run/lease, or dynamic acceptance"
        ),
        "target": _identity(TARGET),
        "templates": [_identity(path) for path in templates],
        "pipeline": {
            "return_code": pipeline.returncode,
            "output_root": PIPELINE_OUT.relative_to(ROOT).as_posix(),
            "stdout": _identity(OUT / "pipeline.stdout.log"),
            "stderr": _identity(OUT / "pipeline.stderr.log"),
            "mapping_caches": [
                _identity(ACCUM_MAPPING_CACHE),
                _identity(TAIL_MAPPING_CACHE),
            ],
            "canonical_mapping_review_count": len(canonical_mapping_reviews),
            "canonical_mapping_review_sha256": _canonical_sha256(
                [_identity(path) for path in canonical_mapping_reviews]
            ),
        },
        "a_consumer_coverage": coverage,
        "weight_materialization": {
            "initializer_name": "resnetv17_dense0_weight_quantized",
            "logical_shape": [K, N],
            "logical_dtype": "int8",
            "physical_shape_per_pass": [K, PHYSICAL_PASS_N],
            "padding_columns": 24,
            "host_computed_tensor_replay": False,
            "records": weight_records,
        },
        "bias_and_psum": {
            "onnx_bias_present": False,
            "a_zero_point": 0,
            "b_zero_point": 0,
            "initial_psum": 0,
            "sa_datac_recurrence": "current df23e4d full-width recurrence",
        },
        "requant": {
            "multiplier_bits": f"0x{MULTIPLIER_BITS:08x}",
            "y_zero_point": Y_ZERO_POINT,
            "two_stage_order": [
                "INT32->FP32 then FP32 MUL then scratch",
                "raw FP32 + 0x4b400000 then INT32_SUB(0x4b400000-60) then UINT8 saturation",
            ],
            "magic_domain_scaled_min": float(
                np.min(expected_acc.astype(np.float32) * MULTIPLIER)
            ),
            "magic_domain_scaled_max": float(
                np.max(expected_acc.astype(np.float32) * MULTIPLIER)
            ),
        },
        "local_e2": e2,
        "release": {
            "candidate_release": False,
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_release": "NONE",
            "server_package_allowed": False,
            "server_uploaded": False,
            "server_run": False,
            "lease_taken": False,
            "blocking_leaf": (
                "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED"
            ),
        },
    }
    _write_json(OUT / "materializer_report.json", report)
    report["report_identity"] = _identity(OUT / "materializer_report.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    try:
        report = build()
    except Exception as exc:
        print(f"NODE0075_MATERIALIZER_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["local_e2"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
