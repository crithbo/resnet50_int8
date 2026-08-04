"""Materialize the stock-TB-compatible atomic Dequant diagnostic contract."""

from __future__ import annotations

import hashlib
import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator


SCHEMA = "dequant-node0077-atomic-single-stage-contract-v2"
RULE_ID = "CDA-DEQUANT-ATOMIC-STOCK-TB-001"
ACTIVE_SLICES = (0, 1)
SLICE_MASK = "0b0000000000000000000000000011"
ELEMENTS_PER_SLICE = 16
A_BASE = 0x00000000
D_BASE = 0x00000010
SCALE_BITS = 0x3E01622D
ZERO_POINT = 60
SOURCE_CONFIG_REL = Path(
    "configs/native_ndp_sim/"
    "resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json"
)
SOURCE_CONFIG_SHA256 = (
    "72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb"
)
SOURCE_GRAPH_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-dequant-node0077-e2-v6/execplan_request.json"
)
CONFIG_ROOT_REL = Path(
    "configs/native_ndp_sim/node0077_dequant_atomic_single_stage_stocktb_v2"
)
ARTIFACT_ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-dequant-node0077-atomic-single-stage-stocktb-v2"
)
REPORT_REL = ARTIFACT_ROOT_REL / "local_contract_report.json"
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "dequant_node0077_atomic_single_stage_stocktb_v2.json"
)
READ_SOURCES = {
    "agent_policy": Path(".agents/agent.md"),
    "generation_read_index": Path(".agents/rules/生成前必读索引.md"),
    "operator_rules": Path(".agents/rules/算子配置规则.md"),
    "hardware_field_semantics": Path(".agents/rules/NDP硬件字段语义.md"),
    "dequant_rules": Path(".agents/rules/DequantizeLinear算子配置规则.md"),
    "atomic_rules": Path(
        ".agents/rules/DequantizeLinear原子动态合同规则.md"
    ),
    "dequant_materializer": Path(
        "resnet50_pipeline/dequantize_linear_vertical.py"
    ),
    "source_config": SOURCE_CONFIG_REL,
    "source_graph": SOURCE_GRAPH_REL,
    "loop_encoder": Path("ndp-sim-ref/bitstream/config/loop.py"),
    "stream_encoder": Path("ndp-sim-ref/bitstream/config/stream.py"),
    "buffer_encoder": Path("ndp-sim-ref/bitstream/config/buffer.py"),
    "ga_encoder": Path("ndp-sim-ref/bitstream/config/general.py"),
    "stock_tb_entry_contract": Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
    "stock_tb_completion_consumer": Path("NDP_copy01/tb_NDP_Top_new_phy.sv"),
    "full_e4_return_analysis": Path(
        "server_returns/dequant_node0077_stockrtl_e4_return_analysis_20260725.json"
    ),
}
RULE_IDS = (
    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
    "CDA-DEQUANT-ONNX-ORDER-001",
    "CDA-DEQUANT-NO-AFFINE-MAC-001",
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-STREAM-LIFECYCLE-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    RULE_ID,
)


class DequantAtomicContractError(ValueError):
    """Raised when the atomic Dequant contract is inconsistent."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DequantAtomicContractError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise DequantAtomicContractError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _binding(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _self_hash(value: Mapping[str, Any], field: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    return sha256_bytes(canonical_json_bytes(payload))


def _flatten(value: Any, path: str = "$") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_flatten(value[key], f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{path}[{index}]"))
        return result
    return {path: value}


def derive_config(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    source_path = root / SOURCE_CONFIG_REL
    if sha256_file(source_path) != SOURCE_CONFIG_SHA256:
        raise DequantAtomicContractError("corrected v6 Dequant config identity differs")
    source = _load(source_path)
    config = deepcopy(source)
    config["dram_loop_configs"]["LC1"]["end"] = 1
    config["dram_loop_configs"]["LC3"]["end"] = 1
    config["stream_engine"]["stream0"]["dim_stride"] = [16, 16, 16]
    config["stream_engine"]["stream2"]["dim_stride"] = [64, 64, 64]
    config["stream_engine"]["stream0"]["base_addr"] = "0x00000000"
    config["stream_engine"]["stream2"]["base_addr"] = "0x00000010"

    expected = {
        "$.dram_loop_configs.LC1.end": (47, 1, "logical schedule"),
        "$.dram_loop_configs.LC3.end": (47, 1, "logical schedule"),
        "$.stream_engine.stream0.base_addr": (
            "0b00000_00_0000000000000_000000_0000",
            "0x00000000",
            "address binder",
        ),
        "$.stream_engine.stream0.dim_stride[2]": (
            752,
            16,
            "typed CWH shape",
        ),
        "$.stream_engine.stream2.base_addr": (
            "0b00000_11_0000000000000_000000_0000",
            "0x00000010",
            "address binder",
        ),
        "$.stream_engine.stream2.dim_stride[2]": (
            3008,
            64,
            "typed CWH shape",
        ),
    }
    before = _flatten(source)
    after = _flatten(config)
    changed = sorted(
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    )
    if changed != sorted(expected):
        raise DequantAtomicContractError(
            f"atomic config changed unexpected leaves: {changed}"
        )
    records = []
    for path in changed:
        old, new, owner = expected[path]
        if before[path] != old or after[path] != new:
            raise DequantAtomicContractError(f"atomic leaf differs at {path}")
        records.append(
            {
                "path": path,
                "source_value": old,
                "derived_value": new,
                "owner": owner,
            }
        )
    report = OperatorConfigValidator().validate(
        config,
        source="node0077-dequant-atomic",
        development_mode=True,
    )
    if not report.valid:
        raise DequantAtomicContractError(
            f"strict config invalid: {report.to_dict()['first_error']}"
        )
    if any(
        pe["transout_last_index"] is not None
        for pe in config["general_array"]["PE_array"].values()
    ):
        raise DequantAtomicContractError("atomic Dequant introduced transout")
    write_stream = config["stream_engine"]["stream2"]
    d_row_loop = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
    d_transaction_bytes = int(write_stream["idx_size"][2]) + 1
    d_buffer_bytes_per_request = int(write_stream["buf_spatial_size"])
    d_row_trip_count = (
        int(d_row_loop["end"]) - int(d_row_loop["start"])
    ) // int(d_row_loop["stride"])
    if (
        config["buffer_config"]["buffer5"]["buf_end_row_addr"] != 3
        or d_transaction_bytes != 64
        or d_buffer_bytes_per_request != 16
        or d_row_trip_count != 4
        or d_row_trip_count * d_buffer_bytes_per_request
        != d_transaction_bytes
    ):
        raise DequantAtomicContractError(
            "atomic D buffer supply does not cover one 64-byte transaction"
        )
    provenance = {
        "derivation_mode": "exact_leaf_diff_from_corrected_v6_config",
        "source_config": _binding(root, SOURCE_CONFIG_REL),
        "changed_leaves": records,
        "all_other_leaves_unchanged": True,
        "diagnostic_shape_change_only": True,
        "d_buffer_supply": {
            "transaction_bytes": d_transaction_bytes,
            "buffer_bytes_per_request": d_buffer_bytes_per_request,
            "row_trip_count": d_row_trip_count,
            "supply_bytes": d_row_trip_count * d_buffer_bytes_per_request,
            "last_row_index": 3,
        },
    }
    return config, provenance


def build_vectors() -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    slice0 = np.asarray(
        [0, 1, 15, 31, 59, 60, 61, 63, 64, 95, 127, 128, 191, 254, 255, 42],
        dtype=np.uint8,
    )
    source = np.stack([slice0, np.roll(slice0, 5)], axis=0)
    scale = np.asarray(
        [struct.unpack("<f", SCALE_BITS.to_bytes(4, "little"))[0]],
        dtype=np.float32,
    )[0]
    centered = np.subtract(
        source.astype(np.float32),
        np.float32(ZERO_POINT),
        dtype=np.float32,
    )
    golden = np.multiply(centered, scale, dtype=np.float32)
    coverage = {
        "active_slices": list(ACTIVE_SLICES),
        "element_count_total": int(source.size),
        "element_count_per_slice": ELEMENTS_PER_SLICE,
        "zero_count": int(np.count_nonzero(source == 0)),
        "max_uint8_count": int(np.count_nonzero(source == 255)),
        "below_zero_point_count": int(np.count_nonzero(source < ZERO_POINT)),
        "equal_zero_point_count": int(np.count_nonzero(source == ZERO_POINT)),
        "above_zero_point_count": int(np.count_nonzero(source > ZERO_POINT)),
        "contains_59_60_61_per_slice": [
            all(value in source[index].tolist() for value in (59, 60, 61))
            for index in range(len(ACTIVE_SLICES))
        ],
        "slice1_is_slice0_rotation": bool(
            np.array_equal(source[1], np.roll(source[0], 5))
        ),
        "scale_bits": f"0x{SCALE_BITS:08x}",
        "zero_point": ZERO_POINT,
        "numeric_order": "(float32(uint8(x))-60.0f)*float32(scale)",
    }
    if not (
        coverage["zero_count"]
        and coverage["max_uint8_count"]
        and coverage["below_zero_point_count"]
        and coverage["equal_zero_point_count"]
        and coverage["above_zero_point_count"]
        and all(coverage["contains_59_60_61_per_slice"])
        and coverage["slice1_is_slice0_rotation"]
    ):
        raise DequantAtomicContractError("diagnostic boundary coverage differs")
    return source, golden, coverage


def _lines128(payload: bytes) -> list[str]:
    if len(payload) % 16:
        raise DequantAtomicContractError("payload is not 128-bit aligned")
    return [
        f"{int.from_bytes(payload[offset:offset + 16], 'little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]


def _write_128(path: Path, payload: bytes) -> None:
    path.write_text(
        "\n".join(_lines128(payload)) + "\n",
        encoding="ascii",
        newline="\n",
    )


def _mse4_writes(slice_id: int, payload: bytes) -> list[dict[str, Any]]:
    records = []
    for beat, offset in enumerate(range(0, len(payload), 16)):
        chunk = payload[offset : offset + 16]
        records.append(
            {
                "slice_id": slice_id,
                "stage_index": 0,
                "role": "dequantize",
                "beat_index": beat,
                "byte_address": f"0x{D_BASE + offset:08x}",
                "word_address_128b": f"0x{(D_BASE + offset) // 16:x}",
                "strobe": "0xffff",
                "data": f"0x{int.from_bytes(chunk, 'little'):032x}",
                "data_sha256": hashlib.sha256(chunk).hexdigest(),
            }
        )
    return records


def _graph(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plan_id": "dequant-node0077-atomic-single-stage-stocktb-v2",
        "used_slices": SLICE_MASK,
        "params": {
            "request_id": "r5:hwop-0077-00",
            "diagnostic_only": True,
            "candidate_release": False,
            "logical_occurrence_count": 1,
            "physical_slice_instance_count": 2,
        },
        "operators": [
            {
                "id": "op0",
                "type": "resnet50_dequant_node0077_uint8_fp32",
                "stage": "dequantize",
                "used_slices": SLICE_MASK,
                "inputs": {
                    "A": {
                        "shape": [16, 1, 1],
                        "dtype": "uint8",
                        "tensor_id": "dequant.atomic.A",
                        "source": {"type": "external"},
                        "base_addr": f"0x{A_BASE:08x}",
                    }
                },
                "output": {
                    "shape": [16, 1, 1],
                    "dtype": "float32",
                    "tensor_id": "dequant.atomic.D",
                    "base_addr": f"0x{D_BASE:08x}",
                },
                "constants": {
                    "negative_zero_point": {
                        "dtype": "float32",
                        "float32_bits": ["0xc2700000"],
                        "values": [-60.0],
                    },
                    "x_scale": {
                        "dtype": "float32",
                        "float32_bits": [f"0x{SCALE_BITS:08x}"],
                    },
                },
                "config_sha256": sha256_bytes(canonical_json_bytes(config)),
            }
        ],
    }


def _receipt(root: Path) -> dict[str, Any]:
    missing = [
        relative.as_posix()
        for relative in READ_SOURCES.values()
        if not (root / relative).is_file()
    ]
    if missing:
        raise DequantAtomicContractError(f"read receipt inputs missing: {missing}")
    value: dict[str, Any] = {
        "schema": "dequant-atomic-generation-read-receipt-v1",
        "read_at": "2026-07-26",
        "scope": "derive atomic JSON/golden/lifecycle only; no server package",
        "read_receipt": [
            {
                "label": label,
                **_binding(root, relative),
                "reason": (
                    "rule routing and triggered field semantics"
                    if "rule" in label
                    or label
                    in {
                        "agent_policy",
                        "generation_read_index",
                        "hardware_field_semantics",
                    }
                    else "closed source topology or actual direct consumer"
                ),
            }
            for label, relative in READ_SOURCES.items()
        ],
        "rule_ids": list(RULE_IDS),
        "known_counterexamples": [
            "DEQUANT_AFFINE_ROUNDING_COUNTEREXAMPLE",
            "full E4: 28 starts, zero finishes, no formal D",
        ],
        "open_dynamic_gates": ["B_DEQUANT_SERVER_E4_E5"],
        "omitted_files": [
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "the testing task owns package generation",
            },
            {
                "path": "NDP_copy01/rtl/**",
                "reason": "no RTL is modified; stable field rules are consumed",
            },
        ],
    }
    value["receipt_sha256"] = _self_hash(value, "receipt_sha256")
    return value


def materialize_bundle(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise DequantAtomicContractError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    config, provenance = derive_config(root)
    source, golden, coverage = build_vectors()
    payloads = {
        slice_id: np.ascontiguousarray(golden[index]).tobytes()
        for index, slice_id in enumerate(ACTIVE_SLICES)
    }
    writes = [
        record
        for slice_id in ACTIVE_SLICES
        for record in _mse4_writes(slice_id, payloads[slice_id])
    ]
    lifecycle = {
        "schema": "dequant-atomic-lifecycle-v1",
        "logical_occurrence_count": 1,
        "physical_slice_instance_count": 2,
        "active_slices": list(ACTIVE_SLICES),
        "slice_mask": SLICE_MASK,
        "stage_count": 1,
        "repeat_num": 1,
        "per_slice_shape_cwh": [16, 1, 1],
        "a_bytes_per_slice": 16,
        "d_bytes_per_slice": 64,
        "a_preload_count": 2,
        "formal_d_entry_count": 2,
        "formal_d_words_per_slice": 4,
        "expected_mse4_accepted_write_count": 8,
        "stock_tb_completion_observer": {
            "mask_aware": False,
            "start_sampled_slice": 0,
            "finish_sampled_slice": 1,
            "required_sampled_slices_enabled": True,
            "natural_completion_required": True,
        },
    }
    expected_writes = {
        "schema": "dequant-atomic-mse4-write-contract-v1",
        "physical_engine": "MSE4_WRITE_STREAM0",
        "active_slices": list(ACTIVE_SLICES),
        "expected_count_per_slice": 4,
        "total_expected_accepted_write_count": len(writes),
        "writes": writes,
        "duplicate_or_extra_write_allowed": False,
    }
    receipt = _receipt(root)
    _write_json(output / "config.json", config)
    _write_json(output / "typed_graph.json", _graph(config))
    _write_json(output / "derivation_provenance.json", provenance)
    _write_json(output / "coverage_contract.json", coverage)
    _write_json(output / "lifecycle_contract.json", lifecycle)
    _write_json(output / "expected_mse4_writes.json", expected_writes)
    _write_json(output / "generation_receipt.json", receipt)
    np.save(output / "input_uint8_cwh.npy", source, allow_pickle=False)
    np.save(output / "golden_fp32_cwh.npy", golden, allow_pickle=False)
    for index, slice_id in enumerate(ACTIVE_SLICES):
        _write_128(
            output / f"input_slice{slice_id:02d}_128b.txt",
            np.ascontiguousarray(source[index]).tobytes(),
        )
        _write_128(
            output / f"golden_slice{slice_id:02d}_128b.txt",
            payloads[slice_id],
        )
    files = {
        path.relative_to(output).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in output.rglob("*") if item.is_file())
    }
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN",
        "request_id": "r5:hwop-0077-00",
        "scope": "one CWH16 occurrence replicated on slices0+1, one GA stage",
        "rule_ids": list(RULE_IDS),
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "server_package": False,
        "evidence_level": "E2_LOCAL_CONTRACT_ONLY",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "counts": {
            "logical_occurrence": 1,
            "physical_slice_instance": 2,
            "stage": 1,
            "element_total": 32,
            "a_preload_128bit_lines": 2,
            "d_formal_128bit_lines": 8,
            "mse4_accepted_write_beats": 8,
        },
        "generation_receipt_sha256": receipt["receipt_sha256"],
        "files": files,
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
        "claim_boundary": (
            "diagnostic atomic contract only; no bitstream, server run, "
            "full node0077 E4, E5, or formal target claim"
        ),
    }
    manifest["manifest_sha256"] = _self_hash(manifest, "manifest_sha256")
    _write_json(output / "manifest.json", manifest)
    return manifest


def materialize_project_assets(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config_root = root / CONFIG_ROOT_REL
    report_path = root / REPORT_REL
    contract_path = root / CONTRACT_REL
    if report_path.exists() or contract_path.exists():
        raise DequantAtomicContractError("refusing to overwrite atomic assets")
    manifest = materialize_bundle(root, config_root)
    report: dict[str, Any] = {
        "schema": "dequant-atomic-local-contract-report-v1",
        "status": manifest["status"],
        "request_id": manifest["request_id"],
        "config_root": CONFIG_ROOT_REL.as_posix(),
        "manifest": _binding(root, config_root / "manifest.json"),
        "counts": manifest["counts"],
        "candidate_release": False,
        "server_package": False,
        "dynamic_execution_status": "NOT_RUN",
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }
    report["report_sha256"] = _self_hash(report, "report_sha256")
    _write_json(report_path, report)
    contract: dict[str, Any] = {
        "schema": "operator-config-semantic-contract-v1",
        "contract_id": "dequant-node0077-atomic-single-stage-stocktb-v2",
        "status": manifest["status"],
        "request_id": manifest["request_id"],
        "rule_ids": list(RULE_IDS),
        "config_manifest": _binding(root, config_root / "manifest.json"),
        "local_report": _binding(root, report_path),
        "active_slices": list(ACTIVE_SLICES),
        "repeat_num": 1,
        "candidate_release": False,
        "server_package": False,
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
    }
    contract["contract_sha256"] = _self_hash(contract, "contract_sha256")
    _write_json(contract_path, contract)
    return {
        "status": contract["status"],
        "config_root": CONFIG_ROOT_REL.as_posix(),
        "report": REPORT_REL.as_posix(),
        "contract": CONTRACT_REL.as_posix(),
        "manifest_sha256": manifest["manifest_sha256"],
        "candidate_release": False,
        "server_package": False,
    }


__all__ = [
    "ARTIFACT_ROOT_REL",
    "CONFIG_ROOT_REL",
    "CONTRACT_REL",
    "REPORT_REL",
    "DequantAtomicContractError",
    "build_vectors",
    "derive_config",
    "materialize_bundle",
    "materialize_project_assets",
]
