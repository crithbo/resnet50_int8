"""Build node-0004 accumulate wave-0 inputs for the active ndp-sim tools.

The existing ``conv_1x1_real.json`` is copied byte-for-byte as a new operator
input name.  W3 tensors are relaid out through the project's current signed-A
local Conv28 layout.  No file under ``ndp-sim-ref`` and no previous W5/server
package is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv28_layout import (
    CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    QLinearConvPhysicalLayout,
)
from resnet50_pipeline.conv_instance import (
    CONV_TRANSPORT_ABI_SIGNED_A_LOCAL,
    FIRST_REAL_CONV_NODE_ID,
    load_conv_instance_spec,
)
from resnet50_pipeline.w5_conv_preflight import (
    _initializer,
    _initializer_values,
    _load_npy,
    validate_conv_hardware_quantization_preconditions,
)


SOURCE_CONFIG_REL = Path("conv_1x1_real.json")
SOURCE_CONFIG_SHA256 = "df73611d0b3141b50a029c002c7ab0e61e8fa5a47bc0a74dcb3446be69e79c16"
ACTIVE_CONFIG_REL = Path("ndp-sim/jsons/node0004_accumulate_wave0.json")
GRAPH_REL = Path(
    "ndp-sim/generate_python_golden/model_execplan/op_json/"
    "node0004_accumulate_wave0_graph.json"
)
DATA_ROOT_REL = Path(
    "ndp-sim/generate_python_golden/single_op_data/"
    "install_node0004_accumulate_wave0"
)
RUNTIME_ROOT_REL = Path("artifacts/w3/golden_batch16")
SUBOP_ROOT_REL = Path("artifacts/w3/subop_batch16")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
SEMANTIC_CONTRACT_REL = Path("contracts/conv_1x1_lc_pe_stream_semantics.json")
OP_TYPE = "node0004_accumulate_wave0"
SLICE_COUNT = 28
WAVE_INDEX = 0


class AccumulateSmokeInputError(RuntimeError):
    """A source or generated artifact violates the wave-0 input contract."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AccumulateSmokeInputError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _assert_fresh_path(path: Path) -> None:
    if path.exists():
        raise AccumulateSmokeInputError(f"refusing to overwrite generated path: {path}")


def _assert_fresh_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise AccumulateSmokeInputError(f"refusing to mix generated data: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write_128bit_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise AccumulateSmokeInputError(
            f"128-bit payload must be a non-empty multiple of 16 bytes: {len(payload)}"
        )
    lines = [
        f"{int.from_bytes(payload[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "line_count_128bit": len(lines),
        "sha256": _sha256_file(path),
    }


def _write_decimal(path: Path, payload: bytes, dtype: np.dtype[Any]) -> dict[str, Any]:
    values = np.frombuffer(payload, dtype=dtype)
    with path.open("w", encoding="ascii", newline="\n") as stream:
        for value in values:
            stream.write(f"{int(value)}\n")
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "value_count": int(values.size),
        "sha256": _sha256_file(path),
    }


def _write_matrix(
    slice_root: Path,
    port: str,
    payload: bytes,
    dtype: np.dtype[Any],
) -> dict[str, Any]:
    raw_path = slice_root / f"matrix_{port}_linearized_128bit.bin"
    text_path = slice_root / f"matrix_{port}_linearized_128bit.txt"
    decimal_path = slice_root / f"matrix_{port}_linearized_128bit_decimal_1d.txt"
    raw_path.write_bytes(payload)
    return {
        "dtype": np.dtype(dtype).name,
        "element_count": len(payload) // np.dtype(dtype).itemsize,
        "raw_path": raw_path.as_posix(),
        "raw_bytes": len(payload),
        "raw_sha256": _sha256_bytes(payload),
        "text": _write_128bit_text(text_path, payload),
        "decimal": _write_decimal(decimal_path, payload, dtype),
    }


def _load_w3_bundle(project_root: Path):
    spec = load_conv_instance_spec(project_root, FIRST_REAL_CONV_NODE_ID)
    semantic_contract = _read_json(project_root / SEMANTIC_CONTRACT_REL)
    if semantic_contract.get("transport_abi") != CONV_TRANSPORT_ABI_SIGNED_A_LOCAL:
        raise AccumulateSmokeInputError("node-0004 transport ABI is not signed-A local v3")

    runtime_root = project_root / RUNTIME_ROOT_REL
    subop_root = project_root / SUBOP_ROOT_REL
    runtime_manifest = _read_json(runtime_root / "manifest.json")
    subop_manifest = _read_json(subop_root / "manifest.json")
    initializers = _initializer_values(project_root / MODEL_REL)
    descriptors = {
        name: spec.tensor(name).descriptor()
        for name in (
            "A",
            "B",
            "bias",
            "w_scale",
            "w_zero_point",
            "x_scale",
            "x_zero_point",
            "y_scale",
            "y_zero_point",
            "P",
            "D",
        )
    }
    values = {
        "A": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["A"]["tensor_id"]],
        ),
        "P": _load_npy(
            subop_root,
            subop_manifest,
            subop_manifest["internal_tensors"][descriptors["P"]["tensor_id"]],
        ),
        "D": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["D"]["tensor_id"]],
        ),
    }
    for port in {
        "B",
        "bias",
        "w_scale",
        "w_zero_point",
        "x_scale",
        "x_zero_point",
        "y_scale",
        "y_zero_point",
    }:
        values[port] = _initializer(
            initializers,
            runtime_manifest,
            descriptors[port],
        )
    validate_conv_hardware_quantization_preconditions(values)

    layout = QLinearConvPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE,
        layout_abi=CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
    )
    bundle = layout.forward(
        activation=values["A"],
        weight=values["B"],
        bias=values["bias"],
        w_scale=values["w_scale"],
        w_zero_point=values["w_zero_point"],
        x_scale=values["x_scale"],
        x_zero_point=values["x_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        accumulator=values["P"],
        output=values["D"],
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
        group=spec.group,
        tensor_ids={name: descriptor["tensor_id"] for name, descriptor in descriptors.items()},
    )
    layout.validate(bundle)
    return spec, bundle, runtime_manifest, subop_manifest


def generate(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    forbidden = (root / "ndp-sim-ref").resolve()
    old_w5 = (root / "artifacts" / "w5").resolve()
    source_config = (root / SOURCE_CONFIG_REL).resolve()
    active_config = (root / ACTIVE_CONFIG_REL).resolve()
    graph_path = (root / GRAPH_REL).resolve()
    data_root = (root / DATA_ROOT_REL).resolve()

    for path in (source_config, root / MODEL_REL, root / SEMANTIC_CONTRACT_REL):
        resolved = path.resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise AccumulateSmokeInputError(f"forbidden ndp-sim-ref source: {resolved}")
        if resolved == old_w5 or old_w5 in resolved.parents:
            raise AccumulateSmokeInputError(f"forbidden previous W5 package source: {resolved}")
        if not resolved.is_file():
            raise AccumulateSmokeInputError(f"missing source: {resolved}")
    if _sha256_file(source_config) != SOURCE_CONFIG_SHA256:
        raise AccumulateSmokeInputError("existing node-0004 config identity differs")

    _assert_fresh_path(active_config)
    _assert_fresh_path(graph_path)
    _assert_fresh_directory(data_root)

    # This is an input alias only; the existing configuration bytes are not regenerated.
    active_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_config, active_config)
    if _sha256_file(active_config) != SOURCE_CONFIG_SHA256:
        raise AssertionError("active config copy differs from the existing source config")

    spec, bundle, runtime_manifest, subop_manifest = _load_w3_bundle(root)
    if bundle.plan.storage_sample_count != 3:
        raise AccumulateSmokeInputError("expected three local storage sample slots")

    activation_slot_bytes = bundle.plan.port("A").payload_bytes // 3
    accumulator_slot_bytes = bundle.plan.port("P").payload_bytes // 3
    weight_bytes = bundle.plan.port("B").payload_bytes
    bias_bytes = bundle.plan.port("bias").payload_bytes
    if (activation_slot_bytes, accumulator_slot_bytes, weight_bytes, bias_bytes) != (
        200704,
        200704,
        1024,
        64,
    ):
        raise AccumulateSmokeInputError(
            "node-0004 wave-0 physical sizes differ: "
            f"activation={activation_slot_bytes}, P={accumulator_slot_bytes}, "
            f"weight={weight_bytes}, bias={bias_bytes}"
        )

    graph = {
        "params": {
            "used_slices": SLICE_COUNT,
            "node_id": FIRST_REAL_CONV_NODE_ID,
            "wave_index": WAVE_INDEX,
            "source": "W3 golden_batch16 + subop_batch16 through signed-A Conv28 layout",
            "logical_samples": [0, 3, 6, 8, 10, 12, 14],
        },
        "used_slices": SLICE_COUNT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": "0b" + "1" * SLICE_COUNT,
                "inputs": {
                    "A": {
                        "shape": [1, 1, weight_bytes],
                        "dtype": "int8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": [1, 1, activation_slot_bytes],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "B'": {
                        "shape": [1, 1, activation_slot_bytes],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "C": {
                        "shape": [1, 1, bias_bytes // 4],
                        "dtype": "int32",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": [1, 1, accumulator_slot_bytes // 4],
                    "dtype": "int32",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        ],
    }
    _write_json(graph_path, graph)

    records: list[dict[str, Any]] = []
    logical_samples = (0, 3, 6, 8, 10, 12, 14)
    for slice_id in range(SLICE_COUNT):
        region = bundle.region("A", slice_id)
        if region.group_id is None or not 0 <= region.group_id < len(logical_samples):
            raise AccumulateSmokeInputError(f"slice {slice_id} has no wave-0 group")
        slice_root = data_root / "op0" / f"slice{slice_id:02d}"
        slice_root.mkdir(parents=True, exist_ok=True)
        matrices = {
            # Config target A is signed weight; physical-layout port B is weight.
            "A": _write_matrix(
                slice_root,
                "A",
                bundle.read("B", slice_id),
                np.dtype("int8"),
            ),
            # Config targets B/B' share the same unsigned activation slot.
            "B": _write_matrix(
                slice_root,
                "B",
                bundle.read("A", slice_id)[:activation_slot_bytes],
                np.dtype("uint8"),
            ),
            "C": _write_matrix(
                slice_root,
                "C",
                bundle.read("bias", slice_id),
                np.dtype("<i4"),
            ),
            # D is not preloaded; this W3 P slot is a same-run readback companion.
            "D": _write_matrix(
                slice_root,
                "D",
                bundle.read("P", slice_id)[:accumulator_slot_bytes],
                np.dtype("<i4"),
            ),
        }
        records.append(
            {
                "slice_id": slice_id,
                "group_id": region.group_id,
                "owner_step": region.owner_step,
                "logical_sample": logical_samples[region.group_id],
                "local_sample_slot": 0,
                "matrices": matrices,
            }
        )

    generated_tensor_files = sorted(path for path in data_root.rglob("*") if path.is_file())
    expected_tensor_files = SLICE_COUNT * 4 * 3
    if len(generated_tensor_files) != expected_tensor_files:
        raise AccumulateSmokeInputError(
            f"expected {expected_tensor_files} tensor files, found {len(generated_tensor_files)}"
        )

    source_paths = {
        "existing_accumulate_config": source_config,
        "active_accumulate_config_alias": active_config,
        "typed_contract": root / "contracts" / "typed_config_parameter_contract.json",
        "semantic_contract": root / SEMANTIC_CONTRACT_REL,
        "runtime_manifest": root / RUNTIME_ROOT_REL / "manifest.json",
        "subop_manifest": root / SUBOP_ROOT_REL / "manifest.json",
        "reference_model": root / MODEL_REL,
    }
    manifest = {
        "format_version": 1,
        "kind": "active_ndpsim_node0004_accumulate_wave0_inputs",
        "status": "generated_from_W3_for_single_stage_smoke",
        "prohibited_sources": ["ndp-sim-ref", "artifacts/w5 previous packages"],
        "configuration_policy": "byte-identical alias of existing conv_1x1_real.json",
        "node_id": spec.node_id,
        "operator_type": OP_TYPE,
        "wave_index": WAVE_INDEX,
        "used_slices": SLICE_COUNT,
        "logical_samples": list(logical_samples),
        "physical_sizes_per_slice": {
            "config_A_weight_int8": weight_bytes,
            "config_B_and_B_prime_activation_uint8": activation_slot_bytes,
            "config_C_bias_int32": bias_bytes,
            "config_D_accumulator_int32": accumulator_slot_bytes,
        },
        "graph": {
            "path": graph_path.relative_to(root).as_posix(),
            "bytes": graph_path.stat().st_size,
            "sha256": _sha256_file(graph_path),
        },
        "sources": {
            label: {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for label, path in source_paths.items()
        },
        "w3_manifest_identities": {
            "runtime_manifest_schema": runtime_manifest.get("schema_version"),
            "subop_manifest_schema": subop_manifest.get("schema_version"),
        },
        "records": records,
        "generated_tensor_file_count": len(generated_tensor_files),
        "generated_tensor_bytes": sum(path.stat().st_size for path in generated_tensor_files),
    }
    manifest_path = data_root / "node0004_accumulate_wave0_input_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "active_config": str(active_config),
        "graph": str(graph_path),
        "data_root": str(data_root),
        "manifest": str(manifest_path),
        "slice_count": SLICE_COUNT,
        "tensor_files": len(generated_tensor_files),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate active-ndp-sim node-0004 accumulate wave-0 inputs"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args()


def main() -> int:
    result = generate(parse_args().project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
