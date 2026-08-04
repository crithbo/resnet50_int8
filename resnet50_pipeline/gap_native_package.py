from __future__ import annotations

import hashlib
import json
import math
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_package_validator import OperatorConfigPackageValidator
from .operator_config_validator import TargetProfile
from .typed_config_parameters import validate_typed_config_parameter_contract


TRANSPORT_SCHEMA = "resnet50-gap-hwop0071-native-transport-v1"
SEMANTIC_SCHEMA = "operator-config-semantic-contract-v1"
CANDIDATE_SCHEMA = "resnet50-gap-hwop0071-server-candidate-v1"
OP_TYPE = "resnet50_gap_sum_uint8_int32"
OP_ID = "op0"
NODE_ID = "node-0071"
REQUEST_ID = "r5:hwop-0071-00"
REQUANT_REQUEST_ID = "r5:hwop-0071-01"
HW_OP_ID = "hwop-0071-00"
SLICE_COUNT = 16
CHANNELS = 2048
HEIGHT = 7
WIDTH = 7
CHANNEL_BLOCK = 8
LOCAL_INPUT_SHAPE = (CHANNELS, HEIGHT, WIDTH)
LOCAL_OUTPUT_SHAPE = (CHANNELS, 1, 1)
INPUT_PAYLOAD_BYTES = math.prod(LOCAL_INPUT_SHAPE)
INPUT_GUARD_BYTES = 64
INPUT_ALLOCATION_BYTES = INPUT_PAYLOAD_BYTES + INPUT_GUARD_BYTES
OUTPUT_BYTES = math.prod(LOCAL_OUTPUT_SHAPE) * 4
INPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-55360f2ec724d2f3.npy"
)
OUTPUT_REL = Path(
    "artifacts/w3/subop_batch16/tensors/tensor-internal-node-0071-sum.npy"
)
TYPED_CONFIG_REL = Path("contracts/typed_config_parameter_contract.json")
SCHEDULE_REL = Path("configs/stage_codegen/hwop-0071-00-v1/schedule_ir.json")
STRICT_CONFIG_REL = Path(
    "configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1/config.json"
)
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_gap_v1.json")
MAPPING_REL = Path(
    "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
    "gap-hwop0071-sum-address-bound-seed42-v1"
)
EXECPLAN_REL = Path(
    "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
    "gap-hwop0071-sum-v2"
)
TRANSPORT_REL = Path(
    "artifacts/operator_config_validation/r5-gap-hwop0071-native-inputs-v1"
)
SEMANTIC_REL = Path("contracts/gap_hwop0071_sum_semantic_contract.json")


class GapNativePackageError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GapNativePackageError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise GapNativePackageError(
            "GAP physical payload must be a non-empty 16-byte multiple"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "line_count_128bit": len(lines),
        "sha256": sha256_file(path),
    }


def c8hw8_pack(value: np.ndarray) -> np.ndarray:
    """Pack one NCHW sample as [C/8,H,W,8], matching the native read strides."""

    if value.dtype != np.uint8 or value.shape != LOCAL_INPUT_SHAPE:
        raise GapNativePackageError(
            f"GAP input must be uint8 {LOCAL_INPUT_SHAPE}, got {value.dtype} {value.shape}"
        )
    return np.ascontiguousarray(
        value.reshape(CHANNELS // CHANNEL_BLOCK, CHANNEL_BLOCK, HEIGHT, WIDTH)
        .transpose(0, 2, 3, 1)
    )


def c8hw8_unpack(value: np.ndarray) -> np.ndarray:
    if value.dtype != np.uint8 or value.shape != (
        CHANNELS // CHANNEL_BLOCK,
        HEIGHT,
        WIDTH,
        CHANNEL_BLOCK,
    ):
        raise GapNativePackageError("GAP C8HW8 image shape differs")
    return np.ascontiguousarray(
        value.transpose(0, 3, 1, 2).reshape(LOCAL_INPUT_SHAPE)
    )


def output_pack(value: np.ndarray) -> np.ndarray:
    if value.dtype != np.int32 or value.shape != LOCAL_OUTPUT_SHAPE:
        raise GapNativePackageError(
            f"GAP output must be int32 {LOCAL_OUTPUT_SHAPE}, got {value.dtype} {value.shape}"
        )
    return np.ascontiguousarray(value.reshape(CHANNELS // CHANNEL_BLOCK, CHANNEL_BLOCK))


def stream_reference_sum(packed: np.ndarray) -> np.ndarray:
    """Replay the template's 14 four-position groups, including the seven zero tails."""

    if packed.shape != (CHANNELS // CHANNEL_BLOCK, HEIGHT, WIDTH, CHANNEL_BLOCK):
        raise GapNativePackageError("GAP packed input shape differs")
    flattened = packed.reshape(CHANNELS // CHANNEL_BLOCK, HEIGHT * WIDTH, CHANNEL_BLOCK)
    padded = np.pad(flattened, ((0, 0), (0, 7), (0, 0)), constant_values=0)
    grouped = padded.reshape(CHANNELS // CHANNEL_BLOCK, 14, 4, CHANNEL_BLOCK)
    result = grouped.astype(np.int32).sum(axis=(1, 2))
    return np.ascontiguousarray(result.reshape(LOCAL_OUTPUT_SHAPE))


def graph_spec() -> dict[str, Any]:
    mask = "0b" + "0" * (28 - SLICE_COUNT) + "1" * SLICE_COUNT
    return {
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "active_slice_count": SLICE_COUNT,
            "source": "W3 golden_batch16/subop_batch16",
            "transport_storage": "C8HW8",
        },
        "used_slices": mask,
        "operators": [
            {
                "id": OP_ID,
                "type": OP_TYPE,
                "used_slices": mask,
                "inputs": {
                    "A": {
                        "shape": [1, 1, INPUT_ALLOCATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                        "logical_storage": {
                            "schema": "resnet50-gap-c8hw8-input-v1",
                            "logical_shape_nchw": list(LOCAL_INPUT_SHAPE),
                            "physical_shape": [
                                CHANNELS // CHANNEL_BLOCK,
                                HEIGHT,
                                WIDTH,
                                CHANNEL_BLOCK,
                            ],
                            "layout": "C8HW8",
                            "payload_bytes": INPUT_PAYLOAD_BYTES,
                            "allocation_bytes": INPUT_ALLOCATION_BYTES,
                            "prefix_guard_bytes": 0,
                            "suffix_guard_bytes": INPUT_GUARD_BYTES,
                        },
                    }
                },
                "output": {
                    "shape": list(LOCAL_OUTPUT_SHAPE),
                    "dtype": "int32",
                    "bank_interleave": 1,
                    "remapping": None,
                    "logical_storage": {
                        "schema": "resnet50-gap-c8-output-v1",
                        "logical_shape_nchw": list(LOCAL_OUTPUT_SHAPE),
                        "physical_shape": [
                            CHANNELS // CHANNEL_BLOCK,
                            CHANNEL_BLOCK,
                        ],
                        "layout": "C8",
                        "payload_bytes": OUTPUT_BYTES,
                    },
                },
            }
        ],
    }


def address_seed_graph_spec() -> dict[str, Any]:
    """Bind the deterministic flat-planner tensor addresses, not execution evidence."""

    graph = deepcopy(graph_spec())
    operator = graph["operators"][0]
    operator["inputs"]["A"]["base_addr"] = "0x00000000"
    operator["output"]["base_addr"] = f"0x{INPUT_ALLOCATION_BYTES:08X}"
    return graph


def write_gap_native_transport(
    project_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapNativePackageError(f"refusing to overwrite GAP transport: {output}")
    input_path = root / INPUT_REL
    golden_path = root / OUTPUT_REL
    for path in (
        input_path,
        golden_path,
        root / TYPED_CONFIG_REL,
        root / SCHEDULE_REL,
        root / STRICT_CONFIG_REL,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    activation = np.load(input_path, allow_pickle=False)
    golden = np.load(golden_path, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (
        SLICE_COUNT,
        *LOCAL_INPUT_SHAPE,
    ):
        raise GapNativePackageError("W3 GAP input identity/shape differs")
    if golden.dtype != np.int32 or golden.shape != (
        SLICE_COUNT,
        *LOCAL_OUTPUT_SHAPE,
    ):
        raise GapNativePackageError("W3 GAP sum identity/shape differs")

    output.mkdir(parents=True)
    graph_path = output / "graph.json"
    _write_json(graph_path, graph_spec())
    address_seed_path = output / "graph_address_seed.json"
    _write_json(address_seed_path, address_seed_graph_spec())
    records: list[dict[str, Any]] = []
    mismatch_total = 0
    for slice_id in range(SLICE_COUNT):
        local_input = np.ascontiguousarray(activation[slice_id])
        local_output = np.ascontiguousarray(golden[slice_id])
        packed_a = c8hw8_pack(local_input)
        if not np.array_equal(c8hw8_unpack(packed_a), local_input):
            raise AssertionError("GAP C8HW8 round trip differs")
        reference = stream_reference_sum(packed_a)
        mismatch = int(np.count_nonzero(reference != local_output))
        mismatch_total += mismatch
        if mismatch:
            raise GapNativePackageError(
                f"independent GAP sum mismatch on slice {slice_id}: {mismatch}"
            )
        packed_d = output_pack(local_output)
        slice_root = output / "data" / OP_ID / f"slice{slice_id:02d}"
        a_path = slice_root / "matrix_A_linearized_128bit.txt"
        d_path = slice_root / "matrix_D_linearized_128bit.txt"
        a_record = _write_128bit_text(
            a_path,
            packed_a.tobytes(order="C") + bytes(INPUT_GUARD_BYTES),
        )
        d_record = _write_128bit_text(d_path, packed_d.tobytes(order="C"))
        a_record["path"] = a_path.relative_to(output).as_posix()
        d_record["path"] = d_path.relative_to(output).as_posix()
        records.append(
            {
                "slice_id": slice_id,
                "batch": slice_id,
                "logical_input_sha256": hashlib.sha256(
                    local_input.tobytes(order="C")
                ).hexdigest(),
                "logical_output_sha256": hashlib.sha256(
                    local_output.tobytes(order="C")
                ).hexdigest(),
                "stream_reference_mismatch_count": mismatch,
                "A": a_record,
                "D": d_record,
            }
        )

    manifest: dict[str, Any] = {
        "schema": TRANSPORT_SCHEMA,
        "status": "native_c8hw8_transport_and_independent_sum_reference_passed",
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "slice_count": SLICE_COUNT,
            "batch_count": SLICE_COUNT,
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "graph": {"path": "graph.json", "sha256": sha256_file(graph_path)},
        "address_seed": {
            "path": "graph_address_seed.json",
            "sha256": sha256_file(address_seed_path),
            "status": "mechanical_flat_address_seed_not_execution_evidence",
            "A": "0x00000000",
            "D": f"0x{INPUT_ALLOCATION_BYTES:08X}",
        },
        "layout": {
            "A": (
                "C8HW8 [256,7,7,8], 100352-byte payload plus "
                "64-byte zero suffix guard per active slice"
            ),
            "D": "C8 [256,8] int32, 8192 bytes per active slice",
            "read_stream_groups": 14,
            "spatial_values": 49,
            "zero_tail_values": 7,
        },
        "sources": {
            "input": {
                "path": INPUT_REL.as_posix(),
                "sha256": sha256_file(input_path),
            },
            "golden_sum": {
                "path": OUTPUT_REL.as_posix(),
                "sha256": sha256_file(golden_path),
            },
            "schedule": {
                "path": SCHEDULE_REL.as_posix(),
                "sha256": sha256_file(root / SCHEDULE_REL),
            },
            "strict_config": {
                "path": STRICT_CONFIG_REL.as_posix(),
                "sha256": sha256_file(root / STRICT_CONFIG_REL),
            },
        },
        "records": records,
        "summary": {
            "slice_count": len(records),
            "matrix_file_count": 2 * len(records),
            "input_payload_bytes": INPUT_PAYLOAD_BYTES * len(records),
            "input_allocation_bytes": INPUT_ALLOCATION_BYTES * len(records),
            "output_payload_bytes": OUTPUT_BYTES * len(records),
            "independent_mismatch_count": mismatch_total,
        },
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    _write_json(output / "manifest.json", manifest)
    return manifest


def validate_gap_native_transport(
    project_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    manifest = _load(output / "manifest.json")
    if manifest.get("schema") != TRANSPORT_SCHEMA:
        raise GapNativePackageError("GAP transport schema differs")
    expected_hash = manifest.pop("manifest_sha256", None)
    if expected_hash != sha256_bytes(canonical_json_bytes(manifest)):
        raise GapNativePackageError("GAP transport manifest receipt differs")
    manifest["manifest_sha256"] = expected_hash
    if manifest.get("graph", {}).get("sha256") != sha256_file(output / "graph.json"):
        raise GapNativePackageError("GAP transport graph differs")
    if manifest.get("address_seed", {}).get("sha256") != sha256_file(
        output / "graph_address_seed.json"
    ):
        raise GapNativePackageError("GAP address seed differs")
    if manifest.get("summary") != {
        "slice_count": 16,
        "matrix_file_count": 32,
        "input_payload_bytes": INPUT_PAYLOAD_BYTES * 16,
        "input_allocation_bytes": INPUT_ALLOCATION_BYTES * 16,
        "output_payload_bytes": OUTPUT_BYTES * 16,
        "independent_mismatch_count": 0,
    }:
        raise GapNativePackageError("GAP transport summary differs")
    for record in manifest.get("records", []):
        if not isinstance(record, Mapping):
            raise GapNativePackageError("GAP transport record is malformed")
        for tensor, size in (("A", INPUT_ALLOCATION_BYTES), ("D", OUTPUT_BYTES)):
            item = record.get(tensor)
            path = output / str(item.get("path")) if isinstance(item, Mapping) else None
            if (
                path is None
                or not path.is_file()
                or item.get("payload_bytes") != size
                or item.get("sha256") != sha256_file(path)
            ):
                raise GapNativePackageError(
                    f"GAP transport slice {record.get('slice_id')} {tensor} differs"
                )
    for source in manifest.get("sources", {}).values():
        path = root / str(source.get("path"))
        if not path.is_file() or source.get("sha256") != sha256_file(path):
            raise GapNativePackageError(f"GAP source identity differs: {path}")
    return manifest


def _typed_stage(bundle: Mapping[str, Any], hw_op_id: str) -> Mapping[str, Any]:
    matches = [
        item
        for item in bundle.get("hw_ops", [])
        if isinstance(item, Mapping) and item.get("hw_op_id") == hw_op_id
    ]
    if len(matches) != 1:
        raise GapNativePackageError(f"expected one typed stage: {hw_op_id}")
    return matches[0]


def _parameter(stage: Mapping[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("resolution") != "derived":
        raise GapNativePackageError(f"expected one derived parameter: {name}")
    return deepcopy(dict(matches[0]["value"]))


def _stable_request_proof_sha256(proof: Mapping[str, Any]) -> str:
    """Hash request semantics while excluding output-directory-only paths."""

    stable = deepcopy(dict(proof))
    stable.pop("graph_root", None)
    facts = stable.get("facts")
    if isinstance(facts, dict):
        facts.pop("graph", None)
    return sha256_bytes(canonical_json_bytes(stable))


def build_gap_semantic_contract(
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
    request_proof: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    mapping = mapping_bundle.resolve()
    proof_path = request_proof.resolve()
    typed_path = root / TYPED_CONFIG_REL
    typed = _load(typed_path)
    validate_typed_config_parameter_contract(typed)
    graph = _load(graph_path)
    transport = validate_gap_native_transport(root, root / TRANSPORT_REL)
    mapping_manifest = _load(mapping / "bundle_manifest.json")
    mapping_evidence = _load(mapping / "mapping_evidence.json")
    proof = _load(proof_path)
    patchset = _load(root / PATCHSET_REL)
    operators = graph.get("operators")
    if (
        not isinstance(operators, list)
        or len(operators) != 1
        or operators[0].get("id") != OP_ID
        or operators[0].get("type") != OP_TYPE
    ):
        raise GapNativePackageError("GAP graph identity differs")
    op = operators[0]
    if (
        set(op.get("inputs", {})) != {"A"}
        or op["inputs"]["A"].get("shape") != [1, 1, INPUT_ALLOCATION_BYTES]
        or op["inputs"]["A"].get("dtype") != "uint8"
        or op.get("output", {}).get("shape") != list(LOCAL_OUTPUT_SHAPE)
        or op.get("output", {}).get("dtype") != "int32"
    ):
        raise GapNativePackageError("GAP graph ABI differs")
    if (
        mapping_manifest.get("summary", {}).get("valid") is not True
        or mapping_manifest.get("summary", {}).get("penalty") != 0.0
        or mapping_manifest.get("summary", {}).get("fallback_used") is not False
        or mapping_manifest.get("mapping_evidence_sha256")
        != sha256_file(mapping / "mapping_evidence.json")
        or mapping_evidence.get("encoder", {}).get("patchset", {}).get("patchset_id")
        != patchset.get("patchset_id")
        or proof.get("valid") is not True
        or proof.get("facts", {}).get("graph_sha256") != sha256_file(graph_path)
    ):
        raise GapNativePackageError("GAP mapping/request evidence differs")

    stage = _typed_stage(typed, HW_OP_ID)
    requant_stage = _typed_stage(typed, "hwop-0071-01")
    schedule = _load(root / SCHEDULE_REL)
    if (
        stage.get("node_id") != NODE_ID
        or stage.get("hw_op_type") != "GlobalAverageSumInt32"
        or stage.get("stage") != "sum"
        or schedule.get("request_id") != REQUEST_ID
        or schedule.get("hw_op_type") != stage.get("hw_op_type")
        or schedule.get("logical_geometry") != stage.get("logical_geometry")
        or stage.get("ports", {}).get("outputs", [{}])[0].get("identity_sha256")
        != "101cad4fd5b2d055a03e7ea0e5586a6b399fb9e1aa07c924bccfe9c3ea3f973b"
        or requant_stage.get("node_id") != NODE_ID
        or requant_stage.get("stage") != "requantize"
        or requant_stage.get("predecessor_hw_op_ids") != [HW_OP_ID]
    ):
        raise GapNativePackageError("GAP typed-stage/schedule identity differs")
    stage_sha256 = sha256_bytes(canonical_json_bytes(stage))
    requant_stage_sha256 = sha256_bytes(canonical_json_bytes(requant_stage))
    qbinding = {
        "scale": _parameter(requant_stage, "x_scale"),
        "zero_point": _parameter(stage, "x_zero_point"),
        "source": (
            f"{typed['contract_type']}:{typed['contract_id']}:{HW_OP_ID}@"
            f"{stage_sha256};"
            f"scale={requant_stage['hw_op_id']}@{requant_stage_sha256}"
        ),
    }
    contract: dict[str, Any] = {
        "schema": SEMANTIC_SCHEMA,
        "graph_sha256": sha256_file(graph_path),
        "target_profile": asdict(TargetProfile()),
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "slice_count": SLICE_COUNT,
            "formal_target_config": False,
            "server_execution_claim": False,
            "purpose": "full native NDP-Sim GAP sum package awaiting hardware",
        },
        "source_identities": {
            "typed_config_parameter_contract_sha256": sha256_file(typed_path),
            "typed_stage_sha256": stage_sha256,
            "typed_requant_stage_sha256": requant_stage_sha256,
            "schedule_sha256": sha256_file(root / SCHEDULE_REL),
            "strict_config_sha256": sha256_file(root / STRICT_CONFIG_REL),
            "patchset_sha256": sha256_file(root / PATCHSET_REL),
            "transport_manifest_sha256": sha256_file(
                root / TRANSPORT_REL / "manifest.json"
            ),
            "mapping_bundle_manifest_sha256": sha256_file(
                mapping / "bundle_manifest.json"
            ),
            "request_proof_content_sha256": _stable_request_proof_sha256(proof),
            "independent_mismatch_count": transport["summary"][
                "independent_mismatch_count"
            ],
        },
        "operators": {
            OP_ID: {
                "op_type": OP_TYPE,
                "layouts": {
                    "A": (
                        "UINT8 C8HW8 [256,7,7,8], 100352-byte payload plus "
                        "64-byte zero suffix guard"
                    ),
                    "D": "INT32 C8 [256,8], 8192 bytes per slice",
                },
                "qparams": {
                    "policy": "explicit",
                    "bindings": {"A": qbinding},
                },
                "stage": {
                    "role": "node-0071 spatial sum over 49 values; one batch per slice",
                    "dependencies": [],
                },
                "tail": {
                    "policy": "exact",
                    "stream_padding": {
                        "logical_spatial_values": 49,
                        "scheduled_spatial_values": 56,
                        "padding_value": 0,
                    },
                },
                "provenance": {
                    "source_config": {
                        "artifact": "mapping_evidence/op0/source_config.json",
                        "sha256": sha256_file(mapping / "source_config.json"),
                    },
                    "mapping_evidence": {
                        "artifact": "mapping_evidence/op0/mapping_evidence.json",
                        "sha256": sha256_file(mapping / "mapping_evidence.json"),
                    },
                },
            }
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def validate_gap_semantic_contract(
    value: Mapping[str, Any],
    project_root: Path,
    *,
    graph_withbaseaddr: Path,
    mapping_bundle: Path,
    request_proof: Path,
) -> None:
    expected = build_gap_semantic_contract(
        project_root,
        graph_withbaseaddr=graph_withbaseaddr,
        mapping_bundle=mapping_bundle,
        request_proof=request_proof,
    )
    if value != expected:
        raise GapNativePackageError("GAP semantic contract differs from bound inputs")


def _files(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "candidate_manifest.json":
            continue
        if path.is_symlink():
            raise GapNativePackageError(f"GAP candidate contains a symlink: {path}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def build_gap_server_candidate(
    project_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapNativePackageError(f"output must be a fresh path: {output}")
    exec_root = root / EXECPLAN_REL
    mapping = root / MAPPING_REL
    transport_root = root / TRANSPORT_REL
    semantic_path = root / SEMANTIC_REL
    exec_manifest = _load(exec_root / "bundle_manifest.json")
    transport = validate_gap_native_transport(root, transport_root)
    semantic = _load(semantic_path)
    graph_name = "graph_withbaseaddr.json"
    pipeline_graphs = list((exec_root / "pipeline_output").glob("*_withbaseaddr.json"))
    if len(pipeline_graphs) != 1:
        raise GapNativePackageError("GAP execplan must contain one withbaseaddr graph")
    if (
        exec_manifest.get("package_validation_report", {}).get("valid") is not True
        or exec_manifest.get("request_address_validation_report", {}).get("valid")
        is not True
        or exec_manifest.get("native_repository", {}).get("patchset", {}).get(
            "patchset_id"
        )
        != _load(root / PATCHSET_REL).get("patchset_id")
    ):
        raise GapNativePackageError("GAP execplan evidence is not closed")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exec_root / "pipeline_output", output)
    original_graph = output / pipeline_graphs[0].name
    if original_graph.name != graph_name:
        original_graph.rename(output / graph_name)
    graph_path = output / graph_name
    shutil.copytree(exec_root / "mapping_evidence", output / "mapping_evidence")
    shutil.copy2(semantic_path, output / "semantic_contract.json")
    evidence_root = output / "evidence"
    evidence_root.mkdir()
    for name in (
        "bundle_manifest.json",
        "double_run_comparison.json",
        "execplan_validation_report.json",
        "package_validation_report.json",
        "request_address_validation_report.json",
        "native_source_manifest.json",
        "patchset_manifest.json",
    ):
        shutil.copy2(exec_root / name, evidence_root / name)
    shutil.copy2(
        transport_root / "manifest.json",
        evidence_root / "transport_manifest.json",
    )

    matrix_count = 0
    for record in transport["records"]:
        slice_id = int(record["slice_id"])
        destination = output / "install" / OP_ID / f"slice{slice_id:02d}"
        destination.mkdir(parents=True, exist_ok=True)
        for tensor in ("A", "D"):
            source = transport_root / record[tensor]["path"]
            shutil.copy2(source, destination / source.name)
            matrix_count += 1
    if matrix_count != 32:
        raise GapNativePackageError("GAP candidate must contain 32 matrix files")

    request_proof = evidence_root / "request_address_validation_report.json"
    validate_gap_semantic_contract(
        semantic,
        root,
        graph_withbaseaddr=graph_path,
        mapping_bundle=output / "mapping_evidence/op0",
        request_proof=request_proof,
    )
    package_report = OperatorConfigPackageValidator().validate(
        output,
        graph_path=graph_path,
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=output,
    ).to_dict()
    if not package_report["valid"]:
        raise GapNativePackageError(
            f"matrix-complete GAP package rejected: {package_report.get('first_error')}"
        )
    _write_json(
        evidence_root / "matrix_complete_package_validation_report.json",
        package_report,
    )
    request_report = _load(request_proof)
    request_count = request_report.get("facts", {}).get(
        "request_count_with_multiplicity"
    )
    if (
        request_report.get("valid") is not True
        or request_report.get("facts", {}).get("graph_sha256")
        != sha256_file(graph_path)
        or not isinstance(request_count, int)
        or request_count <= 0
    ):
        raise GapNativePackageError("GAP request proof differs")

    files = _files(output)
    relative = output.relative_to(root).as_posix()
    manifest: dict[str, Any] = {
        "schema": CANDIDATE_SCHEMA,
        "status": "local_numeric_and_native_package_valid_server_execution_not_claimed",
        "candidate_scope": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "slice_count": SLICE_COUNT,
            "batch_count": SLICE_COUNT,
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "execution_payload": {
            "execplan_sha256": sha256_file(output / "install/execplan.txt"),
            "graph_sha256": sha256_file(graph_path),
            "matrix_file_count": matrix_count,
            "config_bitstream_count": len(
                list((output / "install/cfg_pkg").glob("*.bin"))
            ),
        },
        "local_validation": {
            "matrix_complete_package_valid": True,
            "request_address_valid": True,
            "request_count_with_multiplicity": request_count,
            "mapping_penalty": 0.0,
            "independent_w3_sum_mismatch_count": 0,
            "input_layout_roundtrip_mismatch_count": 0,
        },
        "external_gate": {
            "approved_server_protocol_required": True,
            "e4_run1_required": True,
            "e5_run2_required": True,
        },
        "commands": {
            "e4": (
                "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                f"--package {relative} --output <fresh-return-run1> --run-id run1"
            ),
            "e5": (
                "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                f"--package {relative} --output <fresh-return-run2> --run-id run2"
            ),
        },
        "payload_file_count": len(files),
        "payload_tree_sha256": _tree_sha256(files),
        "files": files,
    }
    _write_json(output / "candidate_manifest.json", manifest)
    validate_gap_server_candidate(root, output)
    return manifest


def validate_gap_server_candidate(
    project_root: Path,
    candidate_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    candidate = candidate_root.resolve()
    manifest = _load(candidate / "candidate_manifest.json")
    if manifest.get("schema") != CANDIDATE_SCHEMA:
        raise GapNativePackageError("GAP candidate identity differs")
    actual = _files(candidate, exclude_manifest=True)
    if (
        manifest.get("files") != actual
        or manifest.get("payload_file_count") != len(actual)
        or manifest.get("payload_tree_sha256") != _tree_sha256(actual)
    ):
        raise GapNativePackageError("GAP candidate tree receipt differs")
    semantic = _load(candidate / "semantic_contract.json")
    graph = candidate / "graph_withbaseaddr.json"
    request_proof = candidate / "evidence/request_address_validation_report.json"
    validate_gap_semantic_contract(
        semantic,
        root,
        graph_withbaseaddr=graph,
        mapping_bundle=candidate / "mapping_evidence/op0",
        request_proof=request_proof,
    )
    report = OperatorConfigPackageValidator().validate(
        candidate,
        graph_path=graph,
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=candidate,
    ).to_dict()
    if not report["valid"] or report["facts"].get("missing_matrix_files"):
        raise GapNativePackageError("GAP candidate package is incomplete")
    return {
        "valid": True,
        "matrix_file_count": manifest["execution_payload"]["matrix_file_count"],
        "payload_tree_sha256": manifest["payload_tree_sha256"],
    }


__all__ = [
    "GapNativePackageError",
    "build_gap_semantic_contract",
    "build_gap_server_candidate",
    "address_seed_graph_spec",
    "c8hw8_pack",
    "c8hw8_unpack",
    "graph_spec",
    "output_pack",
    "stream_reference_sum",
    "validate_gap_native_transport",
    "validate_gap_semantic_contract",
    "validate_gap_server_candidate",
    "write_gap_native_transport",
]
