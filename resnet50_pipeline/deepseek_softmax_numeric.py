from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "deepseek-softmax-synthetic-numeric-e2-v1"
ARTIFACT_ROOT = (
    "artifacts/operator_config_validation/ds_softmax_numeric_v1"
)
MANIFEST_PATH = f"{ARTIFACT_ROOT}/manifest.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_softmax_numeric_v1.json"
)
RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_softmax.py"
)
GOLDEN_PATH = (
    "ndp-sim/generate_python_golden/"
    "deepseek1.5b_3_time_golden_smallsize.py"
)
SCALE_PATH = "ndp-sim/generate_python_golden/softmax_scale.bin"
STAGE_PRODUCER_CONTRACT_PATH = (
    "contracts/operator_config/"
    "deepseek_prefill_rule_normalized_stage_v1.json"
)

HEADS = 7
SLICES_PER_HEAD = 4
SEQUENCE = 32
SCALE = np.float32(1.0 / math.sqrt(128.0))


class DeepSeekSoftmaxNumericError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekSoftmaxNumericError(
            f"cannot parse Softmax numeric JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekSoftmaxNumericError(
            f"Softmax numeric JSON root is not an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekSoftmaxNumericError(
            f"Softmax numeric evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _load_relayout_module(root: Path) -> ModuleType:
    path = root / RELAYOUT_PATH
    spec = importlib.util.spec_from_file_location(
        "deepseek_softmax_relayout_e2", path
    )
    if spec is None or spec.loader is None:
        raise DeepSeekSoftmaxNumericError(
            "cannot load native Softmax relayout consumer"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _logical_head(head: int) -> dict[str, np.ndarray]:
    rows = np.arange(SEQUENCE, dtype=np.int32)[:, None]
    cols = np.arange(SEQUENCE, dtype=np.int32)[None, :]
    qk = (
        ((head + 1) * 13 + rows * 7 - cols * 5) % 37 - 18
    ).astype(np.float32) / np.float32(8.0)
    mask = np.where(cols <= rows, 0.0, -10000.0).astype(np.float32)
    op0 = (qk * SCALE + mask).astype(np.float32)
    op1 = np.max(op0, axis=1, keepdims=True).astype(np.float32)
    op2 = np.exp((op0 - op1).astype(np.float32)).astype(np.float32)
    op3 = (
        np.float32(1.0)
        / np.sum(op2, axis=1, keepdims=True, dtype=np.float32)
    ).astype(np.float32)
    op4 = (op2 * op3).astype(np.float16)
    return {
        "op0_A": qk,
        "op0_C": mask,
        "op0_D": op0,
        "op1_D": op1,
        "op2_D": op2,
        "op3_D": op3,
        "op4_D": op4,
    }


def _write_array(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def materialize_softmax_numeric_payload(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact = root / ARTIFACT_ROOT
    if artifact.exists():
        raise DeepSeekSoftmaxNumericError(
            f"Softmax numeric artifact root already exists: {artifact}"
        )
    relayout = _load_relayout_module(root)
    records: list[dict[str, Any]] = []
    for head in range(HEADS):
        logical = _logical_head(head)
        for name, value in logical.items():
            relative = (
                f"{ARTIFACT_ROOT}/logical/head{head:02d}/{name}.bin"
            )
            _write_array(root / relative, value)
            records.append(
                {
                    **_binding(root, relative),
                    "kind": "logical",
                    "head": head,
                    "name": name,
                    "dtype": str(value.dtype),
                    "shape": list(value.shape),
                }
            )
        for replica in range(SLICES_PER_HEAD):
            slice_index = head * SLICES_PER_HEAD + replica
            for name, value in logical.items():
                physical = np.asarray(
                    relayout.relayout_slice_M8_N(value),
                    dtype=value.dtype,
                )
                relative = (
                    f"{ARTIFACT_ROOT}/physical/slice{slice_index:02d}/"
                    f"{name}.bin"
                )
                _write_array(root / relative, physical)
                records.append(
                    {
                        **_binding(root, relative),
                        "kind": "physical",
                        "head": head,
                        "replica": replica,
                        "slice": slice_index,
                        "name": name,
                        "dtype": str(value.dtype),
                        "logical_shape": list(value.shape),
                    }
                )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generator": {
            "formula": (
                "fp16(exp(fp32(scale*qk+mask-row_max))/"
                "sum(exp(...)))"
            ),
            "scale": float(SCALE),
            "heads": HEADS,
            "slices_per_head": SLICES_PER_HEAD,
            "sequence_length": SEQUENCE,
            "input_seed_formula": (
                "(((head+1)*13 + row*7 - col*5) mod 37 - 18)/8"
            ),
            "mask": "0 for col<=row else -10000",
        },
        "files": sorted(records, key=lambda item: str(item["path"])),
    }
    manifest["manifest_sha256"] = sha256_bytes(
        canonical_json_bytes(manifest)
    )
    (root / MANIFEST_PATH).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_array(
    root: Path, item: Mapping[str, Any], shape_key: str
) -> np.ndarray:
    dtype = np.dtype(str(item["dtype"]))
    shape = tuple(int(value) for value in item[shape_key])
    path = root / str(item["path"])
    value = np.frombuffer(path.read_bytes(), dtype=dtype)
    if value.size != int(np.prod(shape)):
        raise DeepSeekSoftmaxNumericError(
            f"Softmax payload size differs: {item['path']}"
        )
    return value.reshape(shape)


def build_softmax_numeric_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    manifest = _load_json(root / MANIFEST_PATH)
    manifest_hash = manifest.get("manifest_sha256")
    unhashed = dict(manifest)
    unhashed.pop("manifest_sha256", None)
    if manifest_hash != sha256_bytes(canonical_json_bytes(unhashed)):
        raise DeepSeekSoftmaxNumericError(
            "Softmax numeric manifest self-hash differs"
        )
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 245:
        raise DeepSeekSoftmaxNumericError(
            "Softmax numeric payload file set differs"
        )
    by_key: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise DeepSeekSoftmaxNumericError(
                "Softmax numeric manifest record is malformed"
            )
        path = root / str(item["path"])
        if (
            not path.is_file()
            or path.stat().st_size <= 0
            or item.get("sha256") != sha256_file(path)
            or item.get("size_bytes") != path.stat().st_size
        ):
            raise DeepSeekSoftmaxNumericError(
                f"Softmax numeric payload binding differs: {path}"
            )
        if item.get("kind") == "logical":
            key = ("logical", int(item["head"]), str(item["name"]))
        else:
            key = (
                "physical",
                int(item["slice"]),
                str(item["name"]),
            )
        if key in by_key:
            raise DeepSeekSoftmaxNumericError(
                f"Softmax numeric payload repeats {key}"
            )
        by_key[key] = item

    relayout = _load_relayout_module(root)
    max_row_sum_error = 0.0
    max_masked_probability = 0.0
    for head in range(HEADS):
        expected = _logical_head(head)
        for name, expected_value in expected.items():
            logical_item = by_key[("logical", head, name)]
            stored = _read_array(root, logical_item, "shape")
            if not np.array_equal(stored, expected_value):
                raise DeepSeekSoftmaxNumericError(
                    f"Softmax logical formula differs: head={head} {name}"
                )
            expected_physical = np.asarray(
                relayout.relayout_slice_M8_N(expected_value),
                dtype=expected_value.dtype,
            )
            for replica in range(SLICES_PER_HEAD):
                slice_index = head * SLICES_PER_HEAD + replica
                physical_item = by_key[
                    ("physical", slice_index, name)
                ]
                stored_physical = np.frombuffer(
                    (root / str(physical_item["path"])).read_bytes(),
                    dtype=expected_value.dtype,
                )
                if not np.array_equal(
                    stored_physical, expected_physical
                ):
                    raise DeepSeekSoftmaxNumericError(
                        "Softmax physical relayout differs: "
                        f"slice={slice_index} {name}"
                    )
        output = expected["op4_D"].astype(np.float32)
        row_error = float(
            np.max(np.abs(np.sum(output, axis=1) - 1.0))
        )
        upper = np.triu(np.ones((SEQUENCE, SEQUENCE), bool), k=1)
        masked = float(np.max(np.abs(output[upper])))
        max_row_sum_error = max(max_row_sum_error, row_error)
        max_masked_probability = max(max_masked_probability, masked)
    if max_row_sum_error > 5.0e-4 or max_masked_probability != 0.0:
        raise DeepSeekSoftmaxNumericError(
            "Softmax probability invariants differ"
        )

    materialized_jsons = []
    base = (
        root
        / "artifacts/operator_config_validation/ds_softmax_v1/a/t/"
        "model_execplan/output/ds_softmax_v1/jsons"
    )
    for path in sorted(base.glob("op*.json")):
        materialized_jsons.append(
            _binding(root, path.relative_to(root).as_posix())
        )
    if len(materialized_jsons) != 5:
        raise DeepSeekSoftmaxNumericError(
            "Softmax materialized JSON set differs"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_NUMERIC_E2_COMPLETE",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "payload_kind": "DETERMINISTIC_SYNTHETIC",
            "onnx_original_weight_payload": False,
            "hardware_readback": False,
        },
        "inputs": {
            "manifest": _binding(root, MANIFEST_PATH),
            "native_relayout_consumer": _binding(root, RELAYOUT_PATH),
            "native_formula_consumer": _binding(root, GOLDEN_PATH),
            "scale": _binding(root, SCALE_PATH),
            "active_stage_producer_contract": _binding(
                root, STAGE_PRODUCER_CONTRACT_PATH
            ),
            "materialized_jsons": materialized_jsons,
        },
        "coverage": {
            "logical_file_count": 49,
            "physical_file_count": 196,
            "nonempty_file_count": 245,
            "head_count": HEADS,
            "slice_count": HEADS * SLICES_PER_HEAD,
            "replicas_per_head": SLICES_PER_HEAD,
            "stages": ["op0", "op1", "op2", "op3", "op4"],
            "all_four_slice_replicas_bit_equal": True,
        },
        "numeric_result": {
            "formula": (
                "prob=fp16(exp(fp32(scale*qk+mask-row_max))*"
                "reciprocal(sum(exp(...))))"
            ),
            "scale_fp32": float(SCALE),
            "max_fp16_row_sum_error": max_row_sum_error,
            "max_masked_probability": max_masked_probability,
            "logical_payload_matches_independent_formula": True,
            "physical_payload_matches_native_relayout": True,
        },
        "rule_ids": [
            "CDA-DEEPSEEK-SOFTMAX-PAYLOAD-COVERAGE-001",
            "CDA-DEEPSEEK-SOFTMAX-NORMALIZED-ROUNDTRIP-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_softmax_numeric_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_softmax_numeric_contract(project_root):
        raise DeepSeekSoftmaxNumericError(
            "Softmax numeric contract differs from current payload"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekSoftmaxNumericError",
    "MANIFEST_PATH",
    "build_softmax_numeric_contract",
    "materialize_softmax_numeric_payload",
    "validate_softmax_numeric_contract",
]
