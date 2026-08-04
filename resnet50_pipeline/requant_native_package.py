from __future__ import annotations

import json
import hashlib
import shutil
import struct
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .operator_config_package_validator import OperatorConfigPackageValidator
from .operator_config_validator import TargetProfile
from .typed_config_parameters import validate_typed_config_parameter_contract
from .w5_conv_preflight import (
    _initializer,
    _initializer_values,
    _load_npy,
    _port,
    _record_by_hw_op,
)


SCHEMA = "resnet50-node0004-requant-native-transport-v1"
HW_OP_ID = "hwop-0004-01"
NODE_ID = "node-0004"
SHARD_COUNT = 8
LANES = 8
SPATIAL = 56 * 56
INPUT_BYTES = SPATIAL * LANES * 4
OUTPUT_BYTES = SPATIAL * LANES
ROUND_MAGIC_BITS = 0x4B400000
TYPED_REL = Path("contracts/typed_config_parameter_contract.json")
TEMPLATE_REL = Path("ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
RUNTIME_MANIFEST_REL = Path("artifacts/w3/golden_batch16/manifest.json")
SUBOP_MANIFEST_REL = Path("artifacts/w3/subop_batch16/manifest.json")
INPUT_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0004-accumulate.npy"
)
OUTPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-78b29737ada5ce7a.npy"
)
CONFIG_ROOT_REL = Path("configs/native_ndp_sim/node0004_requant_shards_v1")
TRANSPORT_REL = Path(
    "artifacts/operator_config_validation/r5-node0004-requant-native-inputs-v1"
)
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_requant_v1.json")
EXECPLAN_REL = Path(
    "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "node0004-requant-full-v1"
)
SEMANTIC_REL = Path(
    "contracts/node0004_requant_full_semantic_contract.json"
)
CANDIDATE_REL = Path(
    "artifacts/operator_config_validation/r5-server-candidates/"
    "node0004-requant-full-v1"
)
GA_MAC_KEYS = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
GA_SUB_KEYS = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
WAVE_SAMPLES = (
    (0, 3, 6, 8, 10, 12, 14),
    (1, 4, 7, 9, 11, 13, 15),
    (2, 5),
)
HIGH_RING_OWNERS = (
    (0, 2, 3, 1),
    (4, 6, 7, 5),
    (8, 10, 11, 9),
    (12, 14, 15, 13),
    (16, 18, 19, 17),
    (20, 22, 23, 21),
    (24, 26, 27, 25),
)


class RequantNativePackageError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantNativePackageError(f"cannot parse JSON: {path}") from error
    if not isinstance(value, dict):
        raise RequantNativePackageError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise RequantNativePackageError(
            "requant physical payload must be a non-empty 16-byte multiple"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}\n"
        for offset in range(0, len(payload), 16)
    )
    path.write_text(text, encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "payload_bytes": len(payload),
        "line_count": len(payload) // 16,
        "sha256": sha256_file(path),
    }


def _mask(slice_ids: list[int]) -> str:
    bits = ["0"] * 28
    for slice_id in slice_ids:
        bits[27 - slice_id] = "1"
    return "0b" + "".join(bits)


def operator_type(wave_index: int, shard_index: int) -> str:
    if not 0 <= wave_index < len(WAVE_SAMPLES):
        raise RequantNativePackageError(f"invalid requant wave: {wave_index}")
    if not 0 <= shard_index < SHARD_COUNT:
        raise RequantNativePackageError(f"invalid requant shard: {shard_index}")
    return f"resnet50_requant_node0004_w{wave_index}_s{shard_index:02d}"


def op_id(wave_index: int, shard_index: int) -> str:
    return f"op_w{wave_index}_s{shard_index:02d}"


def wave_active_slices(wave_index: int, shard_index: int) -> list[int]:
    owner_step = shard_index // 2
    return [
        HIGH_RING_OWNERS[group_id][owner_step]
        for group_id in range(len(WAVE_SAMPLES[wave_index]))
    ]


def _typed_stage(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    typed = _load(root / TYPED_REL)
    validate_typed_config_parameter_contract(typed)
    stage = _record_by_hw_op(typed, HW_OP_ID)
    if (
        stage.get("node_id") != NODE_ID
        or stage.get("hw_op_type") != "RequantizeUint8"
        or stage.get("stage") != "requantize"
        or stage.get("predecessor_hw_op_ids") != ["hwop-0004-00"]
    ):
        raise RequantNativePackageError("node-0004 typed requant identity differs")
    return typed, stage


def requant_parameters(
    project_root: Path,
) -> tuple[np.ndarray, int, dict[str, Any]]:
    root = project_root.resolve()
    typed, stage = _typed_stage(root)
    runtime = _load(root / RUNTIME_MANIFEST_REL)
    initializers = _initializer_values(root / MODEL_REL)
    values = {
        name: _initializer(
            initializers,
            runtime,
            _port(stage, "inputs", name),
        )
        for name in ("x_scale", "w_scale", "y_scale", "y_zero_point")
    }
    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    parameter = next(
        item for item in stage["parameters"] if item["name"] == "requant_multiplier"
    )
    multiplier_sha = sha256_bytes(np.ascontiguousarray(multiplier).tobytes())
    if (
        multiplier.shape != (64,)
        or multiplier_sha != parameter["value"]["value_sha256"]
    ):
        raise RequantNativePackageError("node-0004 requant multiplier differs")
    zero_point = int(values["y_zero_point"][0])
    if zero_point != 0:
        raise RequantNativePackageError(
            "current exact node-0004 requant specialization requires y_zero_point=0"
        )
    identity = {
        "typed_contract_sha256": sha256_file(root / TYPED_REL),
        "typed_stage_sha256": sha256_bytes(canonical_json_bytes(stage)),
        "multiplier_sha256": multiplier_sha,
        "output_zero_point": zero_point,
        "typed_contract_id": typed["contract_id"],
    }
    return multiplier, zero_point, identity


def build_strict_configs(
    project_root: Path,
) -> tuple[dict[tuple[int, int], dict[str, Any]], dict[str, Any]]:
    root = project_root.resolve()
    template_path = root / TEMPLATE_REL
    template = _load(template_path)
    multiplier, zero_point, identity = requant_parameters(root)
    round_magic = np.float32(12_582_912.0 + zero_point)
    configs: dict[tuple[int, int], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    allocation_bytes = INPUT_BYTES + OUTPUT_BYTES
    for wave_index in range(len(WAVE_SAMPLES)):
        for shard_index in range(SHARD_COUNT):
            config = deepcopy(template)
            config["dram_loop_configs"]["LC0"]["end"] = 1
            config["dram_loop_configs"]["LC1"]["end"] = SPATIAL
            config["dram_loop_configs"]["LC2"]["end"] = SPATIAL // 4
            config["stream_engine"]["stream0"]["dim_stride"][0] = LANES * 4
            operator_index = wave_index * SHARD_COUNT + shard_index
            input_base = operator_index * allocation_bytes
            output_base = input_base + INPUT_BYTES
            config["stream_engine"]["stream0"]["base_addr"] = (
                f"0x{input_base:08X}"
            )
            config["stream_engine"]["stream2"]["base_addr"] = (
                f"0x{output_base:08X}"
            )
            channels = list(
                range(shard_index * LANES, (shard_index + 1) * LANES)
            )
            pe_array = config["general_array"]["PE_array"]
            for mac_key, sub_key, channel in zip(
                GA_MAC_KEYS, GA_SUB_KEYS, channels, strict=True
            ):
                pe_array[mac_key]["inport1"]["constant"] = float(
                    multiplier[channel]
                )
                pe_array[mac_key]["inport2"]["constant"] = float(round_magic)
                pe_array[sub_key]["inport1"]["constant"] = ROUND_MAGIC_BITS
            report = OperatorConfigValidator().validate(
                config,
                source=(
                    f"{TEMPLATE_REL.as_posix()}#node0004-wave{wave_index}-"
                    f"shard{shard_index:02d}"
                ),
            )
            if not report.valid:
                raise RequantNativePackageError(
                    "derived requant config is not strict-valid: "
                    f"{report.to_dict()['first_error']}"
                )
            configs[(wave_index, shard_index)] = config
            records.append(
                {
                    "wave_index": wave_index,
                    "shard_index": shard_index,
                    "operator_type": operator_type(wave_index, shard_index),
                    "channels": channels,
                    "input_base_addr": f"0x{input_base:08X}",
                    "output_base_addr": f"0x{output_base:08X}",
                    "config_sha256": sha256_bytes(
                        canonical_json_bytes(config)
                    ),
                    "mapping_validation": report.to_dict()["facts"].get(
                        "mapping"
                    ),
                }
            )
    manifest = {
        "schema": "resnet50-node0004-requant-config-set-v1",
        "source_template": {
            "path": TEMPLATE_REL.as_posix(),
            "sha256": sha256_file(template_path),
            "provenance": "pinned upstream exact authorized reference",
        },
        "typed_identity": identity,
        "shape_specialization": {
            "input": [1, SPATIAL, LANES],
            "output": [1, SPATIAL, LANES],
            "input_dtype": "int32",
            "output_dtype": "uint8",
            "wave_count": len(WAVE_SAMPLES),
            "shard_count_per_wave": SHARD_COUNT,
            "operator_config_count": len(configs),
            "covered_channels": list(range(64)),
        },
        "rounding": {
            "round_magic_float32": float(round_magic),
            "round_magic_bits": (
                f"0x{struct.unpack('<I', struct.pack('<f', float(round_magic)))[0]:08x}"
            ),
            "subtract_magic_int32": ROUND_MAGIC_BITS,
            "saturation": "general_array.outport.int32touint8",
        },
        "records": records,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    return configs, manifest


def graph_spec() -> dict[str, Any]:
    operators: list[dict[str, Any]] = []
    for wave_index in range(len(WAVE_SAMPLES)):
        for shard_index in range(SHARD_COUNT):
            slices = wave_active_slices(wave_index, shard_index)
            operators.append(
                {
                    "id": op_id(wave_index, shard_index),
                    "type": operator_type(wave_index, shard_index),
                    "used_slices": _mask(slices),
                    "inputs": {
                        "A": {
                            "shape": [1, SPATIAL, LANES],
                            "dtype": "int32",
                            "bank_interleave": 1,
                            "remapping": None,
                            "source": {"type": "external"},
                        }
                    },
                    "output": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                    },
                }
            )
    return {
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "wave_count": len(WAVE_SAMPLES),
            "shard_count_per_wave": SHARD_COUNT,
            "source": "independent W3 INT32 accumulator and UINT8 golden",
        },
        "used_slices": _mask(list(range(28))),
        "operators": operators,
    }


def write_requant_native_inputs(
    project_root: Path,
    output_root: Path,
    config_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    config_output = config_root.resolve()
    if output.exists() or config_output.exists():
        raise RequantNativePackageError(
            "requant config/transport outputs must both be fresh paths"
        )
    configs, config_manifest = build_strict_configs(root)
    config_output.mkdir(parents=True)
    for (wave_index, shard_index), config in sorted(configs.items()):
        _write_json(
            config_output
            / f"wave-{wave_index}-shard-{shard_index:02d}.json",
            config,
        )
    _write_json(config_output / "manifest.json", config_manifest)

    _, stage = _typed_stage(root)
    runtime = _load(root / RUNTIME_MANIFEST_REL)
    subop = _load(root / SUBOP_MANIFEST_REL)
    accumulator = _load_npy(
        root / "artifacts/w3/subop_batch16",
        subop,
        subop["internal_tensors"]["tensor-internal-node-0004-accumulate"],
    )
    golden = _load_npy(
        root / "artifacts/w3/golden_batch16",
        runtime,
        runtime["tensors"]["tensor-78b29737ada5ce7a"],
    )
    if (
        accumulator.shape != (16, 64, 56, 56)
        or accumulator.dtype != np.dtype("int32")
        or golden.shape != accumulator.shape
        or golden.dtype != np.dtype("uint8")
    ):
        raise RequantNativePackageError("node-0004 W3 tensor identity differs")
    multiplier, zero_point, typed_identity = requant_parameters(root)
    scaled = accumulator.astype(np.float32) * multiplier.reshape(1, 64, 1, 1)
    round_magic = np.float32(12_582_912.0 + zero_point)
    rounded = (
        (scaled + round_magic).view(np.int32).astype(np.int64)
        - ROUND_MAGIC_BITS
    )
    replay = np.clip(rounded, 0, 255).astype(np.uint8)
    mismatch_count = int(np.count_nonzero(replay != golden))
    if mismatch_count:
        raise RequantNativePackageError(
            f"independent node-0004 requant replay differs: {mismatch_count}"
        )

    output.mkdir(parents=True)
    graph_path = output / "graph.json"
    _write_json(graph_path, graph_spec())
    records: list[dict[str, Any]] = []
    for wave_index, samples in enumerate(WAVE_SAMPLES):
        for shard_index in range(SHARD_COUNT):
            channel_start = shard_index * LANES
            channel_stop = channel_start + LANES
            slices = wave_active_slices(wave_index, shard_index)
            for group_id, (slice_id, sample_id) in enumerate(
                zip(slices, samples, strict=True)
            ):
                local_a = np.ascontiguousarray(
                    accumulator[sample_id, channel_start:channel_stop]
                    .transpose(1, 2, 0)
                    .reshape(1, SPATIAL, LANES)
                )
                local_d = np.ascontiguousarray(
                    golden[sample_id, channel_start:channel_stop]
                    .transpose(1, 2, 0)
                    .reshape(1, SPATIAL, LANES)
                )
                relative_root = (
                    Path(op_id(wave_index, shard_index)) / f"slice{slice_id:02d}"
                )
                a_path = output / relative_root / "matrix_A_linearized_128bit.txt"
                d_path = output / relative_root / "matrix_D_linearized_128bit.txt"
                a_record = _write_128bit_text(a_path, local_a.tobytes())
                d_record = _write_128bit_text(d_path, local_d.tobytes())
                a_record["path"] = a_path.relative_to(output).as_posix()
                d_record["path"] = d_path.relative_to(output).as_posix()
                records.append(
                    {
                        "wave_index": wave_index,
                        "shard_index": shard_index,
                        "op_id": op_id(wave_index, shard_index),
                        "operator_type": operator_type(
                            wave_index, shard_index
                        ),
                        "group_id": group_id,
                        "slice_id": slice_id,
                        "sample_id": sample_id,
                        "channels": list(range(channel_start, channel_stop)),
                        "A": a_record,
                        "D": d_record,
                    }
                )
    manifest = {
        "schema": SCHEMA,
        "graph": {
            "path": "graph.json",
            "sha256": sha256_file(graph_path),
        },
        "config_set": {
            "path": config_output.relative_to(root).as_posix(),
            "manifest_sha256": sha256_file(config_output / "manifest.json"),
        },
        "typed_identity": typed_identity,
        "sources": {
            "typed_stage_sha256": sha256_bytes(canonical_json_bytes(stage)),
            "input": {
                "path": INPUT_REL.as_posix(),
                "sha256": sha256_file(root / INPUT_REL),
            },
            "golden": {
                "path": OUTPUT_REL.as_posix(),
                "sha256": sha256_file(root / OUTPUT_REL),
            },
        },
        "dispatch": {
            "wave_samples": [list(item) for item in WAVE_SAMPLES],
            "wave_active_slice_counts": [28, 28, 8],
            "operator_count": len(graph_spec()["operators"]),
            "operator_slice_record_count": len(records),
            "matrix_file_count": len(records) * 2,
            "covered_samples": sorted(
                {sample for wave in WAVE_SAMPLES for sample in wave}
            ),
            "covered_channels": list(range(64)),
        },
        "independent_numeric_replay": {
            "element_count": int(replay.size),
            "mismatch_count": mismatch_count,
            "actual_sha256": sha256_bytes(np.ascontiguousarray(replay).tobytes()),
            "golden_sha256": sha256_bytes(np.ascontiguousarray(golden).tobytes()),
        },
        "records": records,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(output / "manifest.json", manifest)
    return manifest


def _parameter(stage: Mapping[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("resolution") != "derived":
        raise RequantNativePackageError(f"typed requant parameter differs: {name}")
    return deepcopy(dict(matches[0]["value"]))


def _stable_request_proof_sha256(proof: Mapping[str, Any]) -> str:
    stable = deepcopy(dict(proof))
    stable.pop("graph_root", None)
    facts = stable.get("facts")
    if isinstance(facts, dict):
        facts.pop("graph", None)
    return sha256_bytes(canonical_json_bytes(stable))


def build_requant_semantic_contract(
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    execplan_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    exec_root = execplan_root.resolve()
    graph = _load(graph_path)
    _, stage = _typed_stage(root)
    proof = _load(exec_root / "request_address_validation_report.json")
    transport = _load(root / TRANSPORT_REL / "manifest.json")
    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 24:
        raise RequantNativePackageError("requant graph must contain 24 stages")
    if (
        proof.get("valid") is not True
        or proof.get("facts", {}).get("graph_sha256") != sha256_file(graph_path)
        or proof.get("facts", {}).get("operator_count") != 24
        or proof.get("facts", {}).get("request_count_with_multiplicity")
        != 1_003_520
        or proof.get("facts", {}).get("issue_count") != 0
        or transport.get("independent_numeric_replay", {}).get(
            "mismatch_count"
        )
        != 0
    ):
        raise RequantNativePackageError("requant request/numeric proof differs")
    typed_stage_sha = sha256_bytes(canonical_json_bytes(stage))
    scale = _parameter(stage, "y_scale")
    zero_point = _parameter(stage, "y_zero_point")
    semantic_ops: dict[str, Any] = {}
    mapping_receipts: dict[str, str] = {}
    for operator in operators:
        current_id = str(operator.get("id"))
        parts = current_id.split("_")
        if len(parts) != 3 or not parts[1].startswith("w") or not parts[2].startswith("s"):
            raise RequantNativePackageError(
                f"requant graph operator id differs: {current_id}"
            )
        wave_index = int(parts[1][1:])
        shard_index = int(parts[2][1:])
        if (
            operator.get("type") != operator_type(wave_index, shard_index)
            or set(operator.get("inputs", {})) != {"A"}
            or operator["inputs"]["A"].get("shape") != [1, SPATIAL, LANES]
            or operator["inputs"]["A"].get("dtype") != "int32"
            or operator.get("output", {}).get("shape")
            != [1, SPATIAL, LANES]
            or operator.get("output", {}).get("dtype") != "uint8"
        ):
            raise RequantNativePackageError(
                f"requant graph ABI differs: {current_id}"
            )
        mapping_root = exec_root / "mapping_evidence" / current_id
        mapping_manifest = _load(mapping_root / "bundle_manifest.json")
        if (
            mapping_manifest.get("summary", {}).get("valid") is not True
            or mapping_manifest.get("summary", {}).get("penalty") != 0.0
            or mapping_manifest.get("summary", {}).get("fallback_used") is not False
        ):
            raise RequantNativePackageError(
                f"requant mapping differs: {current_id}"
            )
        mapping_receipts[current_id] = sha256_file(
            mapping_root / "bundle_manifest.json"
        )
        semantic_ops[current_id] = {
            "op_type": operator["type"],
            "layouts": {
                "A": "INT32 HWC8 [1,3136,8], one sample/channel shard",
                "D": "UINT8 HWC8 [1,3136,8], one sample/channel shard",
            },
            "qparams": {
                "policy": "explicit",
                "bindings": {
                    "D": {
                        "scale": deepcopy(scale),
                        "zero_point": deepcopy(zero_point),
                        "source": (
                            "typed_config_parameter_contract:"
                            f"{HW_OP_ID}@{typed_stage_sha}"
                        ),
                    }
                },
            },
            "stage": {
                "role": "standalone W3 accumulator requant validation",
                "wave_index": wave_index,
                "shard_index": shard_index,
                "channels": list(
                    range(shard_index * LANES, (shard_index + 1) * LANES)
                ),
                "sample_ids": list(WAVE_SAMPLES[wave_index]),
                "dependencies": [],
            },
            "tail": {"policy": "exact", "padding": None},
            "provenance": {
                "source_config": {
                    "artifact": (
                        f"mapping_evidence/{current_id}/source_config.json"
                    ),
                    "sha256": sha256_file(mapping_root / "source_config.json"),
                },
                "mapping_evidence": {
                    "artifact": (
                        f"mapping_evidence/{current_id}/mapping_evidence.json"
                    ),
                    "sha256": sha256_file(
                        mapping_root / "mapping_evidence.json"
                    ),
                },
            },
        }
    contract: dict[str, Any] = {
        "schema": "operator-config-semantic-contract-v1",
        "graph_sha256": sha256_file(graph_path),
        "target_profile": asdict(TargetProfile()),
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "operator_count": 24,
            "wave_count": 3,
            "formal_target_config": False,
            "server_execution_claim": False,
            "purpose": (
                "full node-0004 Requantize native package using independent "
                "W3 INT32 accumulator input"
            ),
        },
        "source_identities": {
            "typed_config_parameter_contract_sha256": sha256_file(
                root / TYPED_REL
            ),
            "typed_stage_sha256": typed_stage_sha,
            "patchset_sha256": sha256_file(root / PATCHSET_REL),
            "transport_manifest_sha256": sha256_file(
                root / TRANSPORT_REL / "manifest.json"
            ),
            "request_proof_content_sha256": _stable_request_proof_sha256(
                proof
            ),
            "mapping_bundle_manifest_sha256": mapping_receipts,
            "independent_mismatch_count": 0,
        },
        "operators": semantic_ops,
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def _candidate_files(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "candidate_manifest.json":
            continue
        if path.is_symlink():
            raise RequantNativePackageError(
                f"requant candidate contains a symlink: {path}"
            )
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode(
                "utf-8"
            )
        )
    return digest.hexdigest()


def build_requant_server_candidate(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise RequantNativePackageError(
            f"requant candidate output must be fresh: {output}"
        )
    exec_root = root / EXECPLAN_REL
    transport_root = root / TRANSPORT_REL
    pipeline_graphs = list(
        (exec_root / "pipeline_output").glob("*_withbaseaddr.json")
    )
    if len(pipeline_graphs) != 1:
        raise RequantNativePackageError(
            "requant execplan must contain one withbaseaddr graph"
        )
    semantic = build_requant_semantic_contract(
        root,
        graph_withbaseaddr=pipeline_graphs[0],
        execplan_root=exec_root,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exec_root / "pipeline_output", output)
    copied_graph = output / pipeline_graphs[0].name
    copied_graph.rename(output / "graph_withbaseaddr.json")
    shutil.copytree(exec_root / "mapping_evidence", output / "mapping_evidence")
    _write_json(output / "semantic_contract.json", semantic)
    evidence = output / "evidence"
    evidence.mkdir()
    for name in (
        "bundle_manifest.json",
        "double_run_comparison.json",
        "execplan_validation_report.json",
        "request_address_validation_report.json",
        "native_source_manifest.json",
        "patchset_manifest.json",
    ):
        shutil.copy2(exec_root / name, evidence / name)
    shutil.copy2(
        transport_root / "manifest.json",
        evidence / "transport_manifest.json",
    )
    transport = _load(transport_root / "manifest.json")
    matrix_count = 0
    for record in transport["records"]:
        destination = (
            output
            / "install"
            / str(record["op_id"])
            / f"slice{int(record['slice_id']):02d}"
        )
        destination.mkdir(parents=True, exist_ok=True)
        for tensor in ("A", "D"):
            source = transport_root / str(record[tensor]["path"])
            shutil.copy2(source, destination / source.name)
            matrix_count += 1
    if matrix_count != 256:
        raise RequantNativePackageError(
            "requant candidate must contain 256 matrix files"
        )
    report = OperatorConfigPackageValidator().validate(
        output,
        graph_path=output / "graph_withbaseaddr.json",
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=output,
    ).to_dict()
    if not report["valid"]:
        raise RequantNativePackageError(
            "matrix-complete requant package rejected: "
            f"{report.get('first_error')}"
        )
    _write_json(evidence / "matrix_complete_package_validation_report.json", report)
    files = _candidate_files(output)
    manifest: dict[str, Any] = {
        "schema": "resnet50-node0004-requant-server-candidate-v1",
        "status": (
            "local_numeric_and_native_package_valid_server_execution_not_claimed"
        ),
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "operator_count": 24,
            "wave_count": 3,
            "formal_target_config": False,
            "server_execution_claim": False,
            "predecessor_conv_execution_included": False,
        },
        "execution_payload": {
            "execplan_sha256": sha256_file(output / "install/execplan.txt"),
            "graph_sha256": sha256_file(output / "graph_withbaseaddr.json"),
            "matrix_file_count": matrix_count,
            "config_bitstream_count": len(
                list((output / "install/cfg_pkg").glob("*.bin"))
            ),
        },
        "local_validation": {
            "matrix_complete_package_valid": True,
            "request_address_valid": True,
            "request_count_with_multiplicity": 1_003_520,
            "mapping_penalty": 0.0,
            "independent_w3_requant_mismatch_count": 0,
        },
        "external_gate": {
            "approved_server_protocol_required": True,
            "e4_run1_required": True,
            "e5_run2_required": True,
        },
        "payload_file_count": len(files),
        "payload_tree_sha256": _tree_sha256(files),
        "files": files,
    }
    _write_json(output / "candidate_manifest.json", manifest)
    return manifest


__all__ = [
    "CONFIG_ROOT_REL",
    "CANDIDATE_REL",
    "EXECPLAN_REL",
    "PATCHSET_REL",
    "RequantNativePackageError",
    "TRANSPORT_REL",
    "WAVE_SAMPLES",
    "build_strict_configs",
    "build_requant_semantic_contract",
    "build_requant_server_candidate",
    "graph_spec",
    "op_id",
    "operator_type",
    "requant_parameters",
    "wave_active_slices",
    "write_requant_native_inputs",
]
