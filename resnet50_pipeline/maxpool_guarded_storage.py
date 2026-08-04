from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np


SCHEMA = "maxpool-node0002-guarded-wave0-v1"
STORAGE_SCHEMA = "maxpool-guarded-c4hwc4-storage-v1"
NODE_ID = "node-0002"
OP_TYPE = "maxpool_config_16_112_112_stride2_padding1"
INPUT_REL = Path("artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy")
OUTPUT_REL = Path("artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"
INPUT_SHAPE = (16, 64, 112, 112)
OUTPUT_SHAPE = (16, 64, 56, 56)
LOCAL_INPUT_SHAPE = (112, 112, 16)
LOCAL_OUTPUT_SHAPE = (56, 56, 16)
CHANNEL_BLOCK = 4
SLICE_COUNT = 28
CHANNELS_PER_TILE = 16
ORIGIN_XY = (1, 1)
PAYLOAD_OFFSET_BYTES = ORIGIN_XY[1] * LOCAL_INPUT_SHAPE[1] * CHANNEL_BLOCK + ORIGIN_XY[0] * CHANNEL_BLOCK
PAYLOAD_BYTES = math.prod(LOCAL_INPUT_SHAPE)
ALLOCATION_BYTES = math.ceil((PAYLOAD_OFFSET_BYTES + PAYLOAD_BYTES) / 16) * 16
SUFFIX_GUARD_BYTES = ALLOCATION_BYTES - PAYLOAD_OFFSET_BYTES - PAYLOAD_BYTES


class MaxPoolGuardedStorageError(ValueError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(value), encoding="utf-8", newline="\n")


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise MaxPoolGuardedStorageError("physical payload must be a non-empty 16-byte multiple")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "payload_bytes": len(payload),
        "line_count_128bit": len(lines),
        "sha256": _sha256_file(path),
        "payload_sha256": _sha256_bytes(payload),
    }


def c4hwc4_pack(value: np.ndarray) -> np.ndarray:
    if value.ndim != 3 or value.shape[2] % CHANNEL_BLOCK:
        raise MaxPoolGuardedStorageError("C4HWC4 packing requires HWC with C divisible by four")
    height, width, channels = value.shape
    return np.ascontiguousarray(
        value.reshape(height, width, channels // CHANNEL_BLOCK, CHANNEL_BLOCK).transpose(2, 0, 1, 3)
    )


def c4hwc4_unpack(value: np.ndarray) -> np.ndarray:
    if value.ndim != 4 or value.shape[-1] != CHANNEL_BLOCK:
        raise MaxPoolGuardedStorageError("C4HWC4 payload must have rank four and inner C=4")
    blocks, height, width, inner = value.shape
    return np.ascontiguousarray(value.transpose(1, 2, 0, 3).reshape(height, width, blocks * inner))


def guarded_input_image(value: np.ndarray) -> bytes:
    if value.dtype != np.uint8 or value.shape != LOCAL_INPUT_SHAPE:
        raise MaxPoolGuardedStorageError(f"unexpected local MaxPool input {value.dtype} {value.shape}")
    payload = c4hwc4_pack(value).tobytes(order="C")
    image = bytes(PAYLOAD_OFFSET_BYTES) + payload + bytes(SUFFIX_GUARD_BYTES)
    if len(image) != ALLOCATION_BYTES:
        raise AssertionError("guarded MaxPool allocation length differs")
    return image


def output_image(value: np.ndarray) -> bytes:
    if value.dtype != np.uint8 or value.shape != LOCAL_OUTPUT_SHAPE:
        raise MaxPoolGuardedStorageError(f"unexpected local MaxPool output {value.dtype} {value.shape}")
    return c4hwc4_pack(value).tobytes(order="C")


def maxpool_uint8_nhwc(value: np.ndarray) -> np.ndarray:
    if value.dtype != np.uint8 or value.shape != LOCAL_INPUT_SHAPE:
        raise MaxPoolGuardedStorageError("unexpected MaxPool reference input")
    padded = np.pad(value, ((1, 1), (1, 1), (0, 0)), constant_values=0)
    windows = [
        padded[row : row + 112 : 2, col : col + 112 : 2, :]
        for row in range(3)
        for col in range(3)
    ]
    return np.ascontiguousarray(np.maximum.reduce(windows), dtype=np.uint8)


def storage_descriptor() -> dict[str, Any]:
    return {
        "schema": STORAGE_SCHEMA,
        "logical_shape_nhwc": list(LOCAL_INPUT_SHAPE),
        "layout": "C4HWC4",
        "channel_block": CHANNEL_BLOCK,
        "coordinate_origin_xy": list(ORIGIN_XY),
        "padding_value": 0,
        "payload_offset_bytes": PAYLOAD_OFFSET_BYTES,
        "payload_bytes": PAYLOAD_BYTES,
        "allocation_bytes": ALLOCATION_BYTES,
        "prefix_guard_bytes": PAYLOAD_OFFSET_BYTES,
        "suffix_guard_bytes": SUFFIX_GUARD_BYTES,
    }


def graph_spec() -> dict[str, Any]:
    return {
        "params": {
            "used_slices": SLICE_COUNT,
            "node_id": NODE_ID,
            "wave_index": 0,
            "source": "W3 golden_batch16",
            "transport_storage": STORAGE_SCHEMA,
        },
        "used_slices": SLICE_COUNT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": "0b" + "1" * SLICE_COUNT,
                "inputs": {
                    "A": {
                        "shape": [1, 1, ALLOCATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                        "logical_storage": storage_descriptor(),
                    }
                },
                "output": {
                    "shape": list(LOCAL_OUTPUT_SHAPE),
                    "dtype": "uint8",
                    "bank_interleave": 1,
                    "remapping": None,
                    "logical_storage": {
                        "schema": "maxpool-c4hwc4-output-v1",
                        "logical_shape_nhwc": list(LOCAL_OUTPUT_SHAPE),
                        "layout": "C4HWC4",
                        "payload_bytes": math.prod(LOCAL_OUTPUT_SHAPE),
                    },
                },
            }
        ],
    }


def address_seed_graph_spec() -> dict[str, Any]:
    """Return the flat planner result used only to bind stream base fields.

    The patched planner is still rerun twice after mapping.  This seed is not
    accepted as execution evidence; it exists to break the mapper/planner
    address-binding cycle while retaining the exact guarded allocation size.
    """

    graph = deepcopy(graph_spec())
    operator = graph["operators"][0]
    operator["inputs"]["A"]["base_addr"] = "0x00000000"
    operator["output"]["base_addr"] = f"0x{ALLOCATION_BYTES:08X}"
    return graph


def write_address_seed(project_root: Path, guarded_root: Path, output_path: Path) -> dict[str, Any]:
    root = project_root.resolve()
    guarded = guarded_root.resolve()
    destination = output_path.resolve()
    validate_guarded_wave0(root, guarded)
    if destination.exists():
        raise MaxPoolGuardedStorageError(f"refusing to overwrite address seed: {destination}")
    value = address_seed_graph_spec()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_json(destination, value)
    return {
        "schema": "maxpool-node0002-guarded-address-seed-v1",
        "status": "mechanical_flat_address_seed_not_execution_evidence",
        "guarded_graph": {
            "artifact": str((guarded / "graph.json").relative_to(root)).replace("\\", "/"),
            "sha256": _sha256_file(guarded / "graph.json"),
        },
        "address_seed": {
            "artifact": str(destination.relative_to(root)).replace("\\", "/"),
            "sha256": _sha256_file(destination),
            "A": "0x00000000",
            "D": f"0x{ALLOCATION_BYTES:08X}",
        },
        "planner_policy": "flat monotonic 16-byte allocation; final patched planner must reproduce these bases",
    }


def _tile_coordinates() -> list[tuple[int, int]]:
    return [
        (batch, channel_start)
        for batch in range(INPUT_SHAPE[0])
        for channel_start in range(0, INPUT_SHAPE[1], CHANNELS_PER_TILE)
    ]


def write_guarded_wave0(
    project_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise MaxPoolGuardedStorageError(f"refusing to overwrite guarded MaxPool output: {output}")
    input_path = root / INPUT_REL
    output_path = root / OUTPUT_REL
    model_path = root / MODEL_REL
    for path in (input_path, output_path, model_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if _sha256_file(model_path) != MODEL_SHA256:
        raise MaxPoolGuardedStorageError("formal ONNX identity differs")
    activation = np.load(input_path, allow_pickle=False)
    golden = np.load(output_path, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != INPUT_SHAPE:
        raise MaxPoolGuardedStorageError("W3 MaxPool input identity/shape differs")
    if golden.dtype != np.uint8 or golden.shape != OUTPUT_SHAPE:
        raise MaxPoolGuardedStorageError("W3 MaxPool output identity/shape differs")

    output.mkdir(parents=True)
    graph_path = output / "graph.json"
    _write_json(graph_path, graph_spec())
    records: list[dict[str, Any]] = []
    for slice_id, (batch, channel_start) in enumerate(_tile_coordinates()[:SLICE_COUNT]):
        local_input = np.ascontiguousarray(
            activation[batch, channel_start : channel_start + CHANNELS_PER_TILE].transpose(1, 2, 0)
        )
        local_golden = np.ascontiguousarray(
            golden[batch, channel_start : channel_start + CHANNELS_PER_TILE].transpose(1, 2, 0)
        )
        computed = maxpool_uint8_nhwc(local_input)
        mismatch_count = int(np.count_nonzero(computed != local_golden))
        if mismatch_count:
            raise MaxPoolGuardedStorageError(
                f"independent W3 MaxPool mismatch on slice {slice_id}: {mismatch_count}"
            )
        a_image = guarded_input_image(local_input)
        d_image = output_image(local_golden)
        if c4hwc4_unpack(
            np.frombuffer(
                a_image[PAYLOAD_OFFSET_BYTES : PAYLOAD_OFFSET_BYTES + PAYLOAD_BYTES],
                dtype=np.uint8,
            ).reshape(4, 112, 112, 4)
        ).tobytes(order="C") != local_input.tobytes(order="C"):
            raise AssertionError("C4HWC4 input round trip differs")
        slice_root = output / "data" / "op0" / f"slice{slice_id:02d}"
        a_path = slice_root / "matrix_A_linearized_128bit.txt"
        d_path = slice_root / "matrix_D_linearized_128bit.txt"
        a_record = _write_128bit_text(a_path, a_image)
        d_record = _write_128bit_text(d_path, d_image)
        for item in (a_record, d_record):
            item["path"] = str(Path(item["path"]).relative_to(output)).replace("\\", "/")
        records.append(
            {
                "slice_id": slice_id,
                "batch": batch,
                "channel_start": channel_start,
                "channel_end_exclusive": channel_start + CHANNELS_PER_TILE,
                "logical_input_sha256": _sha256_bytes(local_input.tobytes(order="C")),
                "logical_output_sha256": _sha256_bytes(local_golden.tobytes(order="C")),
                "independent_maxpool_mismatch_count": mismatch_count,
                "A": a_record,
                "D": d_record,
            }
        )

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "guarded_c4hwc4_transport_generated_and_independently_numeric_checked",
        "candidate_scope": {
            "node_id": NODE_ID,
            "wave_index": 0,
            "slice_count": SLICE_COUNT,
            "remaining_tiles": 64 - SLICE_COUNT,
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "graph": {
            "artifact": "graph.json",
            "sha256": _sha256_file(graph_path),
        },
        "storage": storage_descriptor(),
        "output_storage": {
            "layout": "C4HWC4",
            "logical_shape_nhwc": list(LOCAL_OUTPUT_SHAPE),
            "payload_bytes": math.prod(LOCAL_OUTPUT_SHAPE),
        },
        "sources": {
            "input": {"artifact": INPUT_REL.as_posix(), "sha256": _sha256_file(input_path)},
            "output": {"artifact": OUTPUT_REL.as_posix(), "sha256": _sha256_file(output_path)},
            "model": {"artifact": MODEL_REL.as_posix(), "sha256": _sha256_file(model_path)},
        },
        "records": records,
        "summary": {
            "slice_count": len(records),
            "independent_mismatch_count": sum(item["independent_maxpool_mismatch_count"] for item in records),
            "input_payload_bytes": sum(item["A"]["payload_bytes"] for item in records),
            "output_payload_bytes": sum(item["D"]["payload_bytes"] for item in records),
        },
    }
    manifest["manifest_sha256"] = _sha256_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    _write_json(output / "manifest.json", manifest)
    return manifest


def validate_guarded_wave0(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    manifest_path = output / "manifest.json"
    graph_path = output / "graph.json"
    if not manifest_path.is_file() or not graph_path.is_file():
        raise MaxPoolGuardedStorageError("guarded MaxPool graph/manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise MaxPoolGuardedStorageError("guarded MaxPool manifest schema differs")
    embedded_hash = manifest.pop("manifest_sha256", None)
    expected_hash = _sha256_bytes(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    manifest["manifest_sha256"] = embedded_hash
    if embedded_hash != expected_hash:
        raise MaxPoolGuardedStorageError("guarded MaxPool manifest self hash differs")
    if manifest.get("storage") != storage_descriptor() or manifest.get("graph", {}).get("sha256") != _sha256_file(graph_path):
        raise MaxPoolGuardedStorageError("guarded MaxPool storage/graph identity differs")
    if json.loads(graph_path.read_text(encoding="utf-8")) != graph_spec():
        raise MaxPoolGuardedStorageError("guarded MaxPool graph content differs")
    for name, item in manifest.get("sources", {}).items():
        path = root / str(item.get("artifact"))
        if not path.is_file() or item.get("sha256") != _sha256_file(path):
            raise MaxPoolGuardedStorageError(f"guarded MaxPool source differs: {name}")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != SLICE_COUNT:
        raise MaxPoolGuardedStorageError("guarded MaxPool record count differs")
    for record in records:
        for port, expected_bytes in (("A", ALLOCATION_BYTES), ("D", math.prod(LOCAL_OUTPUT_SHAPE))):
            item = record.get(port)
            path = output / str(item.get("path")) if isinstance(item, Mapping) else output
            if (
                not isinstance(item, Mapping)
                or not path.is_file()
                or item.get("payload_bytes") != expected_bytes
                or item.get("line_count_128bit") != expected_bytes // 16
                or item.get("sha256") != _sha256_file(path)
            ):
                raise MaxPoolGuardedStorageError(f"guarded MaxPool {port} record differs")
    return manifest


__all__ = [
    "ALLOCATION_BYTES",
    "MaxPoolGuardedStorageError",
    "PAYLOAD_BYTES",
    "PAYLOAD_OFFSET_BYTES",
    "STORAGE_SCHEMA",
    "SUFFIX_GUARD_BYTES",
    "c4hwc4_pack",
    "c4hwc4_unpack",
    "address_seed_graph_spec",
    "graph_spec",
    "guarded_input_image",
    "output_image",
    "storage_descriptor",
    "validate_guarded_wave0",
    "write_address_seed",
    "write_guarded_wave0",
]
