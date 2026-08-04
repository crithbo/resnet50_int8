"""Generate node-0002 MaxPool wave-0 inputs for the active ndp-sim pipeline.

This bridge deliberately reads the active ``ndp-sim`` checkout and the W3
ResNet-50 tensors only.  It never imports from or resolves ``ndp-sim-ref``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ACTIVE_CONFIG_REL = Path(
    "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json"
)
ACTIVE_CONFIG_SHA256 = "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
INPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy"
)
OUTPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy"
)
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"
OP_TYPE = "maxpool_config_16_112_112_stride2_padding1"
SLICE_COUNT = 28
CHANNELS_PER_TILE = 16
INPUT_SHAPE = (16, 64, 112, 112)
OUTPUT_SHAPE = (16, 64, 56, 56)
LOCAL_INPUT_SHAPE = (112, 112, 16)
LOCAL_OUTPUT_SHAPE = (56, 56, 16)


class MaxPoolSmokeInputError(RuntimeError):
    """Raised when a source or generated artifact violates the bridge contract."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise MaxPoolSmokeInputError(
            f"128-bit payload must be a non-empty multiple of 16 bytes: {len(payload)}"
        )
    lines = [
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "line_count_128bit": len(lines),
        "sha256": _sha256_file(path),
        "first_word_hex": f"0x{int.from_bytes(payload[:16], byteorder='little'):032X}",
    }


def _write_decimal(path: Path, values: np.ndarray) -> dict[str, Any]:
    flat = np.ascontiguousarray(values, dtype=np.uint8).reshape(-1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        for value in flat:
            stream.write(f"{int(value)}\n")
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "value_count": int(flat.size),
        "sha256": _sha256_file(path),
    }


def _maxpool_uint8_nhwc(value: np.ndarray) -> np.ndarray:
    if value.dtype != np.uint8 or value.shape != LOCAL_INPUT_SHAPE:
        raise MaxPoolSmokeInputError(f"unexpected local input: {value.dtype} {value.shape}")
    padded = np.pad(value, ((1, 1), (1, 1), (0, 0)), constant_values=0)
    windows = [
        padded[row : row + 112 : 2, col : col + 112 : 2, :]
        for row in range(3)
        for col in range(3)
    ]
    result = np.maximum.reduce(windows)
    return np.ascontiguousarray(result, dtype=np.uint8)


def _tile_coordinates() -> list[tuple[int, int]]:
    coordinates = [
        (batch, channel_start)
        for batch in range(INPUT_SHAPE[0])
        for channel_start in range(0, INPUT_SHAPE[1], CHANNELS_PER_TILE)
    ]
    if len(coordinates) != 64:
        raise AssertionError(f"expected 64 MaxPool tiles, found {len(coordinates)}")
    return coordinates


def _assert_fresh_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise MaxPoolSmokeInputError(f"refusing to mix generated data: {path}")
    path.mkdir(parents=True, exist_ok=True)


def generate(project_root: Path, graph_output: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = graph_output.resolve()
    install_root = data_root.resolve()
    forbidden = (root / "ndp-sim-ref").resolve()

    source_paths = {
        "active_config": (root / ACTIVE_CONFIG_REL).resolve(),
        "input": (root / INPUT_REL).resolve(),
        "output": (root / OUTPUT_REL).resolve(),
        "model": (root / MODEL_REL).resolve(),
    }
    for label, path in source_paths.items():
        if path == forbidden or forbidden in path.parents:
            raise MaxPoolSmokeInputError(f"forbidden source for {label}: {path}")
        if not path.is_file():
            raise MaxPoolSmokeInputError(f"missing source for {label}: {path}")

    if _sha256_file(source_paths["active_config"]) != ACTIVE_CONFIG_SHA256:
        raise MaxPoolSmokeInputError("active ndp-sim MaxPool config identity differs")
    if _sha256_file(source_paths["model"]) != MODEL_SHA256:
        raise MaxPoolSmokeInputError("formal ResNet-50 ONNX identity differs")
    if graph_path.exists():
        raise MaxPoolSmokeInputError(f"refusing to overwrite graph: {graph_path}")
    _assert_fresh_directory(install_root)

    activation = np.load(source_paths["input"], allow_pickle=False)
    golden = np.load(source_paths["output"], allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != INPUT_SHAPE:
        raise MaxPoolSmokeInputError(
            f"unexpected W3 input: {activation.dtype} {activation.shape}"
        )
    if golden.dtype != np.uint8 or golden.shape != OUTPUT_SHAPE:
        raise MaxPoolSmokeInputError(
            f"unexpected W3 output: {golden.dtype} {golden.shape}"
        )

    graph = {
        "params": {
            "used_slices": SLICE_COUNT,
            "node_id": "node-0002",
            "wave_index": 0,
            "source": "W3 golden_batch16",
        },
        "used_slices": SLICE_COUNT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": "0b" + "1" * SLICE_COUNT,
                "inputs": {
                    "A": {
                        "shape": list(LOCAL_INPUT_SHAPE),
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    }
                },
                "output": {
                    "shape": list(LOCAL_OUTPUT_SHAPE),
                    "dtype": "uint8",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        ],
    }
    _write_json(graph_path, graph)

    records: list[dict[str, Any]] = []
    for slice_id, (batch, channel_start) in enumerate(_tile_coordinates()[:SLICE_COUNT]):
        local_input = np.ascontiguousarray(
            activation[batch, channel_start : channel_start + CHANNELS_PER_TILE].transpose(1, 2, 0)
        )
        local_golden = np.ascontiguousarray(
            golden[batch, channel_start : channel_start + CHANNELS_PER_TILE].transpose(1, 2, 0)
        )
        computed = _maxpool_uint8_nhwc(local_input)
        mismatch_count = int(np.count_nonzero(computed != local_golden))
        if mismatch_count:
            raise MaxPoolSmokeInputError(
                f"W3 MaxPool mismatch on slice {slice_id}: {mismatch_count} bytes"
            )

        slice_root = install_root / "op0" / f"slice{slice_id:02d}"
        slice_root.mkdir(parents=True, exist_ok=True)
        matrix_records: dict[str, Any] = {}
        for port, array in (("A", local_input), ("D", local_golden)):
            raw = np.ascontiguousarray(array, dtype=np.uint8).tobytes(order="C")
            raw_path = slice_root / f"matrix_{port}_linearized_128bit.bin"
            text_path = slice_root / f"matrix_{port}_linearized_128bit.txt"
            decimal_path = slice_root / f"matrix_{port}_linearized_128bit_decimal_1d.txt"
            raw_path.write_bytes(raw)
            matrix_records[port] = {
                "shape_nhwc": list(array.shape),
                "element_count": int(array.size),
                "raw_path": raw_path.relative_to(install_root).as_posix(),
                "raw_bytes": len(raw),
                "raw_sha256": _sha256_bytes(raw),
                "text": _write_128bit_text(text_path, raw),
                "decimal": _write_decimal(decimal_path, array),
            }

        records.append(
            {
                "slice_id": slice_id,
                "global_tile_index": slice_id,
                "batch": batch,
                "channel_start": channel_start,
                "channel_end_exclusive": channel_start + CHANNELS_PER_TILE,
                "mismatch_count": mismatch_count,
                "matrices": matrix_records,
            }
        )

    generated_files = sorted(path for path in install_root.rglob("*") if path.is_file())
    expected_files = SLICE_COUNT * 6
    if len(generated_files) != expected_files:
        raise MaxPoolSmokeInputError(
            f"expected {expected_files} tensor files, found {len(generated_files)}"
        )
    manifest = {
        "format_version": 1,
        "kind": "active_ndpsim_node0002_maxpool_wave0_inputs",
        "status": "generated_and_locally_numeric_checked",
        "forbidden_source": "ndp-sim-ref",
        "wave_index": 0,
        "tile_count": SLICE_COUNT,
        "remaining_full_node_tiles": 64 - SLICE_COUNT,
        "logical_node": {
            "input_shape_nchw": list(INPUT_SHAPE),
            "output_shape_nchw": list(OUTPUT_SHAPE),
            "dtype": "uint8",
            "kernel_shape": [3, 3],
            "strides": [2, 2],
            "pads": [1, 1, 1, 1],
        },
        "local_tile": {
            "input_shape_nhwc": list(LOCAL_INPUT_SHAPE),
            "output_shape_nhwc": list(LOCAL_OUTPUT_SHAPE),
            "input_bytes": math.prod(LOCAL_INPUT_SHAPE),
            "output_bytes": math.prod(LOCAL_OUTPUT_SHAPE),
        },
        "sources": {
            label: {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for label, path in source_paths.items()
        },
        "graph": {
            "path": graph_path.relative_to(root).as_posix(),
            "bytes": graph_path.stat().st_size,
            "sha256": _sha256_file(graph_path),
        },
        "records": records,
        "generated_tensor_file_count": len(generated_files),
        "generated_tensor_bytes": sum(path.stat().st_size for path in generated_files),
    }
    manifest_path = install_root / "maxpool_wave0_input_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "graph": str(graph_path),
        "data_root": str(install_root),
        "manifest": str(manifest_path),
        "tile_count": SLICE_COUNT,
        "tensor_files": len(generated_files),
        "tensor_bytes": manifest["generated_tensor_bytes"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate active-ndp-sim node-0002 MaxPool wave-0 graph and W3 data"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--graph-output",
        type=Path,
        default=Path(
            "ndp-sim/generate_python_golden/model_execplan/op_json/"
            "node0002_maxpool_wave0_graph.json"
        ),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(
            "ndp-sim/generate_python_golden/single_op_data/"
            "install_maxpool_node0002_wave0"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    graph_output = args.graph_output
    if not graph_output.is_absolute():
        graph_output = project_root / graph_output
    data_root = args.data_root
    if not data_root.is_absolute():
        data_root = project_root / data_root
    result = generate(project_root, graph_output, data_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

