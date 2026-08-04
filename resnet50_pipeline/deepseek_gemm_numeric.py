from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "deepseek-gemm-ffn-gate-synthetic-numeric-e2-v1"
ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_gemm_numeric_v1"
MANIFEST_PATH = f"{ARTIFACT_ROOT}/manifest.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_gemm_numeric_v1.json"
)
RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_gemm_ring.py"
)
GOLDEN_PATH = (
    "ndp-sim/generate_python_golden/"
    "deepseek1.5b_3_time_golden_smallsize.py"
)
GEMM_RULE_PATH = ".agents/rules/DeepSeek_GEMM增量规则.md"
STAGE_PRODUCER_CONTRACT_PATH = (
    "contracts/operator_config/"
    "deepseek_prefill_rule_normalized_stage_v1.json"
)

K = 896
M = 32
N = 1792
SLICES = 28
SLICE_K = K // SLICES
SLICE_N = N // SLICES


class DeepSeekGemmNumericError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekGemmNumericError(
            f"cannot parse GEMM numeric JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekGemmNumericError(
            f"GEMM numeric JSON root is not an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekGemmNumericError(
            f"GEMM numeric evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _load_relayout_module(root: Path) -> ModuleType:
    path = root / RELAYOUT_PATH
    spec = importlib.util.spec_from_file_location(
        "deepseek_gemm_relayout_e2", path
    )
    if spec is None or spec.loader is None:
        raise DeepSeekGemmNumericError(
            "cannot load native GEMM relayout consumer"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _logical_payload() -> dict[str, np.ndarray]:
    k_axis = np.arange(K, dtype=np.int32)[:, None]
    m_axis = np.arange(M, dtype=np.int32)[None, :]
    n_axis = np.arange(N, dtype=np.int32)[None, :]
    a = (((k_axis * 3 + m_axis * 5) % 17) - 8).astype(
        np.float16
    ) / np.float16(32.0)
    b = (((k_axis * 7 + n_axis * 11) % 19) - 9).astype(
        np.float16
    ) / np.float16(64.0)
    accumulator = (
        a.T.astype(np.float64) @ b.astype(np.float64)
    ).astype(np.float32)
    d = accumulator.astype(np.float16).T.copy()
    return {
        "A_KM": np.asarray(a, dtype=np.float16),
        "B_KN": np.asarray(b, dtype=np.float16),
        "ACC_MN": accumulator,
        "D_NM": d,
    }


def _write_array(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def materialize_gemm_numeric_payload(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact = root / ARTIFACT_ROOT
    if artifact.exists():
        raise DeepSeekGemmNumericError(
            f"GEMM numeric artifact root already exists: {artifact}"
        )
    relayout = _load_relayout_module(root)
    logical = _logical_payload()
    records: list[dict[str, Any]] = []
    for name, value in logical.items():
        relative = f"{ARTIFACT_ROOT}/logical/{name}.bin"
        _write_array(root / relative, value)
        records.append(
            {
                **_binding(root, relative),
                "kind": "logical",
                "name": name,
                "dtype": str(value.dtype),
                "shape": list(value.shape),
            }
        )

    physical_mapping = list(
        relayout.BASE_HW_PARAMS["physical_mapping"]
    )
    ring_order = list(relayout.BASE_HW_PARAMS["ring_order"])
    if (
        sorted(physical_mapping) != list(range(SLICES))
        or sorted(ring_order) != list(range(SLICES))
    ):
        raise DeepSeekGemmNumericError(
            "native GEMM mapping/ring order is not a permutation"
        )
    for logical_slice in range(SLICES):
        physical_slice = int(physical_mapping[logical_slice])
        k0 = logical_slice * SLICE_K
        n0 = logical_slice * SLICE_N
        a_chunk = logical["A_KM"][k0 : k0 + SLICE_K, :]
        b_slice = logical["B_KN"][:, n0 : n0 + SLICE_N]
        d_slice = logical["D_NM"][n0 : n0 + SLICE_N, :]
        a_physical = np.asarray(
            relayout.relayout_in1_L8K2L4K(a_chunk, SLICE_K, M),
            dtype=np.float16,
        )
        b_ring = relayout.reorder_in0_slice_by_ring(
            b_slice,
            logical_slice,
            SLICES,
            SLICE_K,
            ring_order,
        )
        b_physical = np.asarray(
            relayout.relayout_in0_N8K2N4K(
                b_ring, K, SLICE_N, SLICES
            ),
            dtype=np.float16,
        )
        d_physical = np.asarray(
            relayout.relayout_out_L8N8L4N4N2L1(
                d_slice, SLICE_N, M
            ),
            dtype=np.float16,
        )
        for name, value in (
            ("A", a_physical),
            ("B", b_physical),
            ("D", d_physical),
        ):
            relative = (
                f"{ARTIFACT_ROOT}/physical/slice{physical_slice:02d}/"
                f"{name}.bin"
            )
            _write_array(root / relative, value)
            records.append(
                {
                    **_binding(root, relative),
                    "kind": "physical",
                    "name": name,
                    "logical_slice": logical_slice,
                    "physical_slice": physical_slice,
                    "dtype": str(value.dtype),
                    "element_count": int(value.size),
                }
            )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generator": {
            "K": K,
            "M": M,
            "N": N,
            "slice_count": SLICES,
            "slice_k": SLICE_K,
            "slice_n": SLICE_N,
            "A_formula": "(((k*3+m*5) mod 17)-8)/32",
            "B_formula": "(((k*7+n*11) mod 19)-9)/64",
            "accumulator": "exact dyadic fp64 sum cast once to fp32",
            "output": "fp16(transpose(accumulator))",
            "physical_mapping": physical_mapping,
            "ring_order": ring_order,
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


def _logical_array(
    root: Path,
    records: Mapping[tuple[Any, ...], Mapping[str, Any]],
    name: str,
) -> np.ndarray:
    item = records[("logical", name)]
    dtype = np.dtype(str(item["dtype"]))
    shape = tuple(int(value) for value in item["shape"])
    value = np.frombuffer(
        (root / str(item["path"])).read_bytes(), dtype=dtype
    )
    if value.size != int(np.prod(shape)):
        raise DeepSeekGemmNumericError(
            f"GEMM logical payload size differs: {name}"
        )
    return value.reshape(shape)


def build_gemm_numeric_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    manifest = _load_json(root / MANIFEST_PATH)
    manifest_hash = manifest.get("manifest_sha256")
    unhashed = dict(manifest)
    unhashed.pop("manifest_sha256", None)
    if manifest_hash != sha256_bytes(canonical_json_bytes(unhashed)):
        raise DeepSeekGemmNumericError(
            "GEMM numeric manifest self-hash differs"
        )
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 88:
        raise DeepSeekGemmNumericError(
            "GEMM numeric payload file set differs"
        )
    records: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise DeepSeekGemmNumericError(
                "GEMM numeric manifest record is malformed"
            )
        path = root / str(item["path"])
        if (
            not path.is_file()
            or path.stat().st_size <= 0
            or item.get("sha256") != sha256_file(path)
            or item.get("size_bytes") != path.stat().st_size
        ):
            raise DeepSeekGemmNumericError(
                f"GEMM numeric payload binding differs: {path}"
            )
        if item.get("kind") == "logical":
            key = ("logical", str(item["name"]))
        else:
            key = (
                "physical",
                int(item["physical_slice"]),
                str(item["name"]),
            )
        if key in records:
            raise DeepSeekGemmNumericError(
                f"GEMM numeric payload repeats {key}"
            )
        records[key] = item

    a = _logical_array(root, records, "A_KM")
    b = _logical_array(root, records, "B_KN")
    accumulator = _logical_array(root, records, "ACC_MN")
    d = _logical_array(root, records, "D_NM")
    expected_accumulator = (
        a.T.astype(np.float64) @ b.astype(np.float64)
    ).astype(np.float32)
    expected_d = expected_accumulator.astype(np.float16).T
    if not np.array_equal(accumulator, expected_accumulator):
        raise DeepSeekGemmNumericError(
            "GEMM stored FP32 accumulator differs"
        )
    if not np.array_equal(d, expected_d):
        raise DeepSeekGemmNumericError("GEMM stored FP16 D differs")

    max_partial_error = 0.0
    for output_slice in range(SLICES):
        n0 = output_slice * SLICE_N
        partial_sum = np.zeros((M, SLICE_N), dtype=np.float64)
        for input_slice in range(SLICES):
            k0 = input_slice * SLICE_K
            partial_sum += (
                a[k0 : k0 + SLICE_K, :].T.astype(np.float64)
                @ b[
                    k0 : k0 + SLICE_K,
                    n0 : n0 + SLICE_N,
                ].astype(np.float64)
            )
        expected_slice = expected_accumulator[
            :, n0 : n0 + SLICE_N
        ].astype(np.float64)
        max_partial_error = max(
            max_partial_error,
            float(np.max(np.abs(partial_sum - expected_slice))),
        )
    if max_partial_error != 0.0:
        raise DeepSeekGemmNumericError(
            "GEMM ring partial coverage differs"
        )

    relayout = _load_relayout_module(root)
    physical_mapping = list(
        relayout.BASE_HW_PARAMS["physical_mapping"]
    )
    ring_order = list(relayout.BASE_HW_PARAMS["ring_order"])
    expected_sizes = {"A": 2048, "B": 114688, "D": 4096}
    for logical_slice in range(SLICES):
        physical_slice = int(physical_mapping[logical_slice])
        k0 = logical_slice * SLICE_K
        n0 = logical_slice * SLICE_N
        expected_a = np.asarray(
            relayout.relayout_in1_L8K2L4K(
                a[k0 : k0 + SLICE_K, :], SLICE_K, M
            ),
            dtype=np.float16,
        )
        b_slice = b[:, n0 : n0 + SLICE_N]
        expected_b = np.asarray(
            relayout.relayout_in0_N8K2N4K(
                relayout.reorder_in0_slice_by_ring(
                    b_slice,
                    logical_slice,
                    SLICES,
                    SLICE_K,
                    ring_order,
                ),
                K,
                SLICE_N,
                SLICES,
            ),
            dtype=np.float16,
        )
        expected_output = np.asarray(
            relayout.relayout_out_L8N8L4N4N2L1(
                d[n0 : n0 + SLICE_N, :], SLICE_N, M
            ),
            dtype=np.float16,
        )
        for name, expected in (
            ("A", expected_a),
            ("B", expected_b),
            ("D", expected_output),
        ):
            item = records[("physical", physical_slice, name)]
            path = root / str(item["path"])
            if path.stat().st_size != expected_sizes[name]:
                raise DeepSeekGemmNumericError(
                    f"GEMM physical {name} byte count differs"
                )
            stored = np.frombuffer(
                path.read_bytes(), dtype=np.float16
            )
            if not np.array_equal(stored, expected):
                raise DeepSeekGemmNumericError(
                    "GEMM physical relayout differs: "
                    f"slice={physical_slice} {name}"
                )

    materialized = (
        root
        / "artifacts/operator_config_validation/ds_gemm_ffn_gate_v1/"
        "a/t/model_execplan/output/ds_gemm_ffn_gate_v1/jsons/"
        "op0_prefill_gemm_ring_4slice.json"
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
            "gemm_rule": _binding(root, GEMM_RULE_PATH),
            "active_stage_producer_contract": _binding(
                root, STAGE_PRODUCER_CONTRACT_PATH
            ),
            "materialized_json": _binding(
                root, materialized.relative_to(root).as_posix()
            ),
        },
        "coverage": {
            "logical_file_count": 4,
            "physical_file_count": 84,
            "nonempty_file_count": 88,
            "slice_count": SLICES,
            "K_chunk_count_per_output_slice": SLICES,
            "physical_mapping_is_permutation": True,
            "ring_order_is_permutation": True,
            "per_slice_bytes": expected_sizes,
        },
        "numeric_result": {
            "logical_formula": (
                "D_NM=transpose(fp16(fp32(A_KM.T @ B_KN)))"
            ),
            "stored_fp32_accumulator_exact": True,
            "stored_fp16_output_exact": True,
            "max_ring_partial_error": max_partial_error,
            "all_28_K_chunks_covered_per_output_slice": True,
            "physical_payload_matches_native_relayout": True,
        },
        "rule_ids": [
            "CDA-DEEPSEEK-GEMM-NUMERIC-PAYLOAD-001",
            "CDA-DEEPSEEK-GEMM-RING-PARTIAL-COVERAGE-001",
            "CDA-DEEPSEEK-LAYOUT-HINT-OWNER-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_gemm_numeric_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_gemm_numeric_contract(project_root):
        raise DeepSeekGemmNumericError(
            "GEMM numeric contract differs from current payload"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekGemmNumericError",
    "MANIFEST_PATH",
    "build_gemm_numeric_contract",
    "materialize_gemm_numeric_payload",
    "validate_gemm_numeric_contract",
]
