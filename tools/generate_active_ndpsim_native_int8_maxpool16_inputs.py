"""Generate a deterministic 28-slice input package for the upstream INT8 MaxPool.

The static operator configuration remains the Git-tracked active ``ndp-sim``
template.  This bridge only supplies the graph, deterministic UINT8 tensors,
independent MaxPool golden data, and the C4HWC4 physical layout expected by the
template.  It never reads from ``ndp-sim-ref``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


CONFIG_REL = Path("ndp-sim/jsons/maxpool_config_16_16_16_stride2_padding1.json")
CONFIG_SHA256 = "624d675ddde6f386474289d473d1c69559691794f3c1ea775dfc99325cc8f072"
OP_TYPE = "maxpool_config_16_16_16_stride2_padding1"
SLICE_COUNT = 28
INPUT_SHAPE = (16, 16, 16)
OUTPUT_SHAPE = (8, 8, 16)
CHANNEL_BLOCK = 4
PADDING = 1
PAYLOAD_OFFSET_BYTES = (
    PADDING * INPUT_SHAPE[1] * CHANNEL_BLOCK + PADDING * CHANNEL_BLOCK
)
INPUT_PAYLOAD_BYTES = math.prod(INPUT_SHAPE)
INPUT_ALLOCATION_BYTES = math.ceil(
    (PAYLOAD_OFFSET_BYTES + INPUT_PAYLOAD_BYTES) / 16
) * 16
INPUT_SUFFIX_GUARD_BYTES = (
    INPUT_ALLOCATION_BYTES - PAYLOAD_OFFSET_BYTES - INPUT_PAYLOAD_BYTES
)


class NativeInt8MaxPool16InputError(RuntimeError):
    """Raised when a source or generated artifact violates the bridge contract."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise NativeInt8MaxPool16InputError(
            f"payload must be a non-empty 16-byte multiple: {len(payload)}"
        )
    lines = [
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "line_count_128bit": len(lines),
        "sha256": _sha256_file(path),
        "payload_bytes": len(payload),
        "payload_sha256": _sha256_bytes(payload),
    }


def _write_decimal(path: Path, payload: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{value}\n" for value in payload),
        encoding="ascii",
        newline="\n",
    )
    return {
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "value_count": len(payload),
        "sha256": _sha256_file(path),
    }


def _c4hwc4_pack(value: np.ndarray) -> bytes:
    if value.dtype != np.uint8 or value.ndim != 3:
        raise NativeInt8MaxPool16InputError("C4HWC4 source must be rank-3 UINT8")
    height, width, channels = value.shape
    if channels % CHANNEL_BLOCK:
        raise NativeInt8MaxPool16InputError("channels must be divisible by four")
    packed = (
        value.reshape(height, width, channels // CHANNEL_BLOCK, CHANNEL_BLOCK)
        .transpose(2, 0, 1, 3)
        .copy()
    )
    return packed.tobytes(order="C")


def _logical_input(slice_id: int) -> np.ndarray:
    row = np.arange(INPUT_SHAPE[0], dtype=np.uint16)[:, None, None]
    col = np.arange(INPUT_SHAPE[1], dtype=np.uint16)[None, :, None]
    channel = np.arange(INPUT_SHAPE[2], dtype=np.uint16)[None, None, :]
    value = (slice_id * 17 + row * 29 + col * 11 + channel * 7 + 3) % 256
    return np.ascontiguousarray(value, dtype=np.uint8)


def _maxpool_uint8(value: np.ndarray) -> np.ndarray:
    if value.dtype != np.uint8 or value.shape != INPUT_SHAPE:
        raise NativeInt8MaxPool16InputError("unexpected logical MaxPool input")
    padded = np.pad(value, ((1, 1), (1, 1), (0, 0)), constant_values=0)
    windows = [
        padded[row : row + INPUT_SHAPE[0] : 2, col : col + INPUT_SHAPE[1] : 2, :]
        for row in range(3)
        for col in range(3)
    ]
    result = np.maximum.reduce(windows)
    if result.shape != OUTPUT_SHAPE:
        raise AssertionError(f"unexpected MaxPool result shape: {result.shape}")
    return np.ascontiguousarray(result, dtype=np.uint8)


def _input_image(value: np.ndarray) -> bytes:
    payload = _c4hwc4_pack(value)
    image = (
        bytes(PAYLOAD_OFFSET_BYTES)
        + payload
        + bytes(INPUT_SUFFIX_GUARD_BYTES)
    )
    if len(image) != INPUT_ALLOCATION_BYTES:
        raise AssertionError("guarded input allocation differs")
    return image


def _graph() -> dict[str, Any]:
    return {
        "params": {
            "used_slices": SLICE_COUNT,
            "purpose": "native upstream GA INT8_MAX backpressure discriminator",
            "source_config_sha256": CONFIG_SHA256,
        },
        "used_slices": SLICE_COUNT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": "0b" + "1" * SLICE_COUNT,
                "inputs": {
                    "A": {
                        "shape": [1, 1, INPUT_ALLOCATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    }
                },
                "output": {
                    "shape": list(OUTPUT_SHAPE),
                    "dtype": "uint8",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        ],
    }


def generate(project_root: Path, graph_path: Path, data_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_output = graph_path.resolve()
    install_root = data_root.resolve()
    forbidden = (root / "ndp-sim-ref").resolve()
    config_path = (root / CONFIG_REL).resolve()

    if config_path == forbidden or forbidden in config_path.parents:
        raise NativeInt8MaxPool16InputError("active config resolved into ndp-sim-ref")
    if not config_path.is_file() or _sha256_file(config_path) != CONFIG_SHA256:
        raise NativeInt8MaxPool16InputError("upstream INT8 MaxPool config identity differs")
    if graph_output.exists():
        raise NativeInt8MaxPool16InputError(f"refusing to overwrite graph: {graph_output}")
    if install_root.exists():
        raise NativeInt8MaxPool16InputError(
            f"refusing to mix generated data: {install_root}"
        )
    install_root.mkdir(parents=True)
    _write_json(graph_output, _graph())

    records: list[dict[str, Any]] = []
    for slice_id in range(SLICE_COUNT):
        logical_input = _logical_input(slice_id)
        logical_output = _maxpool_uint8(logical_input)
        input_image = _input_image(logical_input)
        output_image = _c4hwc4_pack(logical_output)
        slice_root = install_root / "op0" / f"slice{slice_id:02d}"
        matrices: dict[str, Any] = {}
        for port, payload, logical in (
            ("A", input_image, logical_input),
            ("D", output_image, logical_output),
        ):
            stem = f"matrix_{port}_linearized_128bit"
            binary_path = slice_root / f"{stem}.bin"
            text_path = slice_root / f"{stem}.txt"
            decimal_path = slice_root / f"{stem}_decimal_1d.txt"
            binary_path.parent.mkdir(parents=True, exist_ok=True)
            binary_path.write_bytes(payload)
            matrices[port] = {
                "logical_shape_hwc": list(logical.shape),
                "logical_sha256": _sha256_bytes(logical.tobytes(order="C")),
                "binary": {
                    "path": binary_path.relative_to(install_root).as_posix(),
                    "size_bytes": binary_path.stat().st_size,
                    "sha256": _sha256_file(binary_path),
                },
                "text": _write_128bit_text(text_path, payload),
                "decimal": _write_decimal(decimal_path, payload),
            }
            matrices[port]["text"]["path"] = text_path.relative_to(
                install_root
            ).as_posix()
            matrices[port]["decimal"]["path"] = decimal_path.relative_to(
                install_root
            ).as_posix()
        records.append({"slice_id": slice_id, "matrices": matrices})

    files = sorted(path for path in install_root.rglob("*") if path.is_file())
    if len(files) != SLICE_COUNT * 6:
        raise NativeInt8MaxPool16InputError(
            f"expected {SLICE_COUNT * 6} matrix files, found {len(files)}"
        )
    manifest: dict[str, Any] = {
        "schema": "active-ndpsim-native-int8-maxpool16-inputs-v1",
        "status": "deterministic_inputs_and_independent_golden_generated",
        "purpose": "exercise the upstream GA INT8_MAX path; server completion is not claimed",
        "forbidden_source": "ndp-sim-ref",
        "source_config": {
            "path": CONFIG_REL.as_posix(),
            "size_bytes": config_path.stat().st_size,
            "sha256": _sha256_file(config_path),
            "git_tracked_upstream": True,
        },
        "graph": {
            "path": graph_output.relative_to(root).as_posix(),
            "size_bytes": graph_output.stat().st_size,
            "sha256": _sha256_file(graph_output),
        },
        "logical_operator": {
            "dtype": "uint8",
            "input_shape_hwc": list(INPUT_SHAPE),
            "output_shape_hwc": list(OUTPUT_SHAPE),
            "kernel_shape": [3, 3],
            "strides": [2, 2],
            "pads": [1, 1, 1, 1],
            "padding_value": 0,
        },
        "physical_storage": {
            "layout": "C4HWC4",
            "channel_block": CHANNEL_BLOCK,
            "input_payload_offset_bytes": PAYLOAD_OFFSET_BYTES,
            "input_payload_bytes": INPUT_PAYLOAD_BYTES,
            "input_suffix_guard_bytes": INPUT_SUFFIX_GUARD_BYTES,
            "input_allocation_bytes": INPUT_ALLOCATION_BYTES,
            "output_payload_bytes": math.prod(OUTPUT_SHAPE),
        },
        "generation": {
            "formula": "(slice*17 + row*29 + col*11 + channel*7 + 3) mod 256",
            "slice_count": SLICE_COUNT,
            "independent_golden": "UINT8 3x3 MaxPool, stride 2, zero padding 1",
        },
        "records": records,
        "generated_matrix_file_count": len(files),
        "generated_matrix_bytes": sum(path.stat().st_size for path in files),
    }
    manifest_path = install_root / "native_int8_maxpool16_input_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "graph": str(graph_output),
        "data_root": str(install_root),
        "manifest": str(manifest_path),
        "slice_count": SLICE_COUNT,
        "matrix_file_count": len(files),
        "input_allocation_bytes_per_slice": INPUT_ALLOCATION_BYTES,
        "output_payload_bytes_per_slice": math.prod(OUTPUT_SHAPE),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate active-ndp-sim upstream INT8 MaxPool 16x16 graph/data"
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
            "native_int8_maxpool16_r1_graph.json"
        ),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(
            "ndp-sim/generate_python_golden/single_op_data/"
            "install_native_int8_maxpool16_r1"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    graph_path = args.graph_output
    if not graph_path.is_absolute():
        graph_path = root / graph_path
    data_root = args.data_root
    if not data_root.is_absolute():
        data_root = root / data_root
    result = generate(root, graph_path, data_root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
