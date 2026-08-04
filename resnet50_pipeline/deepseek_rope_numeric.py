from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "deepseek-rope-canonical-xor2-synthetic-numeric-e2-v1"
ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_rope_numeric_v1"
MANIFEST_PATH = f"{ARTIFACT_ROOT}/manifest.json"
CONTRACT_PATH = "contracts/operator_config/deepseek_rope_numeric_v1.json"
RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_rope.py"
)
ROUTER_OVERLAY_PATH = (
    "resnet50_pipeline/native_overlays/deepseek_rope/"
    "slice_routing.py"
)
ROPE_RULE_PATH = ".agents/rules/DeepSeek_RoPE增量规则.md"
EXECPLAN_PATH = (
    "artifacts/operator_config_validation/ds_rope_v1/a/t/"
    "model_execplan/output/ds_rope_v1/instructions_explained.txt"
)
MATERIALIZED_JSON_ROOT = (
    "artifacts/operator_config_validation/ds_rope_v1/a/t/"
    "model_execplan/output/ds_rope_v1/jsons"
)

HEADS = 7
SLICES_PER_HEAD = 4
SLICES = HEADS * SLICES_PER_HEAD
HEAD_DIM = 128
ELEMENTS_PER_SLICE = HEAD_DIM // SLICES_PER_HEAD
SEQUENCE = 32


class DeepSeekRopeNumericError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekRopeNumericError(
            f"cannot parse RoPE numeric JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekRopeNumericError(
            f"RoPE numeric JSON root is not an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekRopeNumericError(
            f"RoPE numeric evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _load_relayout_module(root: Path) -> ModuleType:
    path = root / RELAYOUT_PATH
    spec = importlib.util.spec_from_file_location(
        "deepseek_rope_relayout_primitive_e2", path
    )
    if spec is None or spec.loader is None:
        raise DeepSeekRopeNumericError(
            "cannot load native RoPE relayout primitive"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _logical_head(head: int) -> dict[str, np.ndarray]:
    element = np.arange(HEAD_DIM, dtype=np.int32)[:, None]
    token = np.arange(SEQUENCE, dtype=np.int32)[None, :]
    half_element = np.arange(HEAD_DIM // 2, dtype=np.int32)[:, None]
    x = (
        ((head + 1) * 11 + element * 5 + token * 3) % 41 - 20
    ).astype(np.float32) / np.float32(16.0)
    cos_half = (
        ((head + 2) * 7 + half_element * 3 + token) % 23 + 1
    ).astype(np.float32) / np.float32(32.0)
    sin_half = (
        ((head + 3) * 5 + half_element * 7 + token * 2) % 19 + 1
    ).astype(np.float32) / np.float32(64.0)
    cos = np.concatenate((cos_half, cos_half), axis=0)
    signed_sin = np.concatenate((sin_half, -sin_half), axis=0)
    op0_d = (x * cos).astype(np.float32)
    op1_source = (x * signed_sin).astype(np.float32)
    op1_routed = np.empty_like(op1_source)
    for source_quarter in range(SLICES_PER_HEAD):
        destination_quarter = source_quarter ^ 0b10
        source_start = source_quarter * ELEMENTS_PER_SLICE
        destination_start = destination_quarter * ELEMENTS_PER_SLICE
        op1_routed[
            destination_start : destination_start + ELEMENTS_PER_SLICE
        ] = op1_source[
            source_start : source_start + ELEMENTS_PER_SLICE
        ]
    op2_fp32 = (op0_d + op1_routed).astype(np.float32)
    op2_d = op2_fp32.astype(np.float16)
    return {
        "X": x,
        "COS": cos,
        "SIN_SIGNED": signed_sin,
        "OP0_D": op0_d,
        "OP1_D_SOURCE": op1_source,
        "OP1_D_ROUTED": op1_routed,
        "OP2_D": op2_d,
    }


def _physical_stage_payload(
    logical: Mapping[str, np.ndarray],
    quarter: int,
) -> dict[str, np.ndarray]:
    start = quarter * ELEMENTS_PER_SLICE
    end = start + ELEMENTS_PER_SLICE
    source_quarter = quarter ^ 0b10
    source_start = source_quarter * ELEMENTS_PER_SLICE
    source_end = source_start + ELEMENTS_PER_SLICE
    return {
        "op0_A": logical["X"][start:end],
        "op0_B": logical["COS"][start:end],
        "op0_D": logical["OP0_D"][start:end],
        "op1_A": logical["X"][start:end],
        "op1_B": logical["SIN_SIGNED"][start:end],
        "op1_D": logical["OP1_D_SOURCE"][start:end],
        "op2_A": logical["OP0_D"][start:end],
        "op2_B": logical["OP1_D_SOURCE"][source_start:source_end],
        "op2_D": logical["OP2_D"][start:end],
    }


def _write_array(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def materialize_rope_numeric_payload(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact = root / ARTIFACT_ROOT
    if artifact.exists():
        raise DeepSeekRopeNumericError(
            f"RoPE numeric artifact root already exists: {artifact}"
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
        for quarter in range(SLICES_PER_HEAD):
            slice_id = head * SLICES_PER_HEAD + quarter
            for name, value in _physical_stage_payload(
                logical, quarter
            ).items():
                physical = np.asarray(
                    relayout.relayout_slice_M8_N(value),
                    dtype=value.dtype,
                )
                relative = (
                    f"{ARTIFACT_ROOT}/physical/slice{slice_id:02d}/"
                    f"{name}.bin"
                )
                _write_array(root / relative, physical)
                records.append(
                    {
                        **_binding(root, relative),
                        "kind": "physical",
                        "head": head,
                        "quarter": quarter,
                        "slice": slice_id,
                        "name": name,
                        "dtype": str(value.dtype),
                        "logical_shape": list(value.shape),
                    }
                )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generator": {
            "implementation_choice": (
                "unmodified activation, signed sin [+,-] halves, "
                "producer-to-destination XOR2, no global negation"
            ),
            "heads": HEADS,
            "slices_per_head": SLICES_PER_HEAD,
            "head_dim": HEAD_DIM,
            "elements_per_slice": ELEMENTS_PER_SLICE,
            "sequence_length": SEQUENCE,
            "route": "destination_slice=source_slice xor 0b10",
            "relayout": (
                "native relayout_slice_M8_N primitive; sign unchanged"
            ),
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


def _parse_generated_route(path: Path) -> dict[int, int]:
    explicit: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "base address for operator op1 output D" not in line:
            continue
        match = re.search(
            r"slice_bin=([01]{5}), source_slice_bin=([01]{5})",
            line,
        )
        if not match:
            raise DeepSeekRopeNumericError(
                "RoPE generated route explanation differs"
            )
        explicit[int(match.group(1), 2)] = int(match.group(2), 2)
    full = {slice_id: explicit.get(slice_id, 0) for slice_id in range(SLICES)}
    expected = {slice_id: slice_id ^ 0b10 for slice_id in range(SLICES)}
    if full != expected:
        raise DeepSeekRopeNumericError(
            "RoPE generated execplan does not implement canonical XOR2"
        )
    return full


def _read_array(
    root: Path, item: Mapping[str, Any], shape_key: str
) -> np.ndarray:
    dtype = np.dtype(str(item["dtype"]))
    shape = tuple(int(value) for value in item[shape_key])
    value = np.frombuffer(
        (root / str(item["path"])).read_bytes(), dtype=dtype
    )
    if value.size != int(np.prod(shape)):
        raise DeepSeekRopeNumericError(
            f"RoPE payload size differs: {item['path']}"
        )
    return value.reshape(shape)


def build_rope_numeric_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    manifest = _load_json(root / MANIFEST_PATH)
    manifest_hash = manifest.get("manifest_sha256")
    unhashed = dict(manifest)
    unhashed.pop("manifest_sha256", None)
    if manifest_hash != sha256_bytes(canonical_json_bytes(unhashed)):
        raise DeepSeekRopeNumericError(
            "RoPE numeric manifest self-hash differs"
        )
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 301:
        raise DeepSeekRopeNumericError(
            "RoPE numeric payload file set differs"
        )
    records: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise DeepSeekRopeNumericError(
                "RoPE numeric manifest record is malformed"
            )
        path = root / str(item["path"])
        if (
            not path.is_file()
            or path.stat().st_size <= 0
            or item.get("sha256") != sha256_file(path)
            or item.get("size_bytes") != path.stat().st_size
        ):
            raise DeepSeekRopeNumericError(
                f"RoPE numeric payload binding differs: {path}"
            )
        key = (
            ("logical", int(item["head"]), str(item["name"]))
            if item.get("kind") == "logical"
            else ("physical", int(item["slice"]), str(item["name"]))
        )
        if key in records:
            raise DeepSeekRopeNumericError(
                f"RoPE numeric payload repeats {key}"
            )
        records[key] = item

    relayout = _load_relayout_module(root)
    max_fp16_error = 0.0
    op0_op1_input_equal = True
    for head in range(HEADS):
        expected = _logical_head(head)
        for name, expected_value in expected.items():
            item = records[("logical", head, name)]
            stored = _read_array(root, item, "shape")
            if not np.array_equal(stored, expected_value):
                raise DeepSeekRopeNumericError(
                    f"RoPE logical formula differs: head={head} {name}"
                )
        fp32_expected = (
            expected["OP0_D"] + expected["OP1_D_ROUTED"]
        ).astype(np.float32)
        max_fp16_error = max(
            max_fp16_error,
            float(
                np.max(
                    np.abs(
                        expected["OP2_D"].astype(np.float32)
                        - fp32_expected
                    )
                )
            ),
        )
        for quarter in range(SLICES_PER_HEAD):
            slice_id = head * SLICES_PER_HEAD + quarter
            stage_payload = _physical_stage_payload(expected, quarter)
            for name, value in stage_payload.items():
                physical_item = records[
                    ("physical", slice_id, name)
                ]
                stored = np.frombuffer(
                    (root / str(physical_item["path"])).read_bytes(),
                    dtype=value.dtype,
                )
                physical_expected = np.asarray(
                    relayout.relayout_slice_M8_N(value),
                    dtype=value.dtype,
                )
                if not np.array_equal(stored, physical_expected):
                    raise DeepSeekRopeNumericError(
                        "RoPE physical relayout differs: "
                        f"slice={slice_id} {name}"
                    )
            op0_a = records[("physical", slice_id, "op0_A")]
            op1_a = records[("physical", slice_id, "op1_A")]
            op0_op1_input_equal &= (
                (root / str(op0_a["path"])).read_bytes()
                == (root / str(op1_a["path"])).read_bytes()
            )
    if not op0_op1_input_equal:
        raise DeepSeekRopeNumericError(
            "RoPE op0/op1 external activation payloads differ"
        )

    route = _parse_generated_route(root / EXECPLAN_PATH)
    materialized_jsons = [
        _binding(
            root,
            (
                f"{MATERIALIZED_JSON_ROOT}/op{index}_{op_type}.json"
            ),
        )
        for index, op_type in enumerate(
            (
                "prefill_mul_fp32MN_fp32MN_fp32MN",
                "prefill_mul_fp32MN_fp32MN_fp32MN",
                "prefill_add_fp32MN_fp32MN_fp16MN",
            )
        )
    ]
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
            "native_relayout_primitive": _binding(root, RELAYOUT_PATH),
            "active_router_overlay": _binding(
                root, ROUTER_OVERLAY_PATH
            ),
            "rope_rule": _binding(root, ROPE_RULE_PATH),
            "generated_execplan": _binding(root, EXECPLAN_PATH),
            "materialized_jsons": materialized_jsons,
        },
        "implementation_choice": {
            "name": "CANONICAL_CROSS_SLICE_XOR2",
            "activation_pre_swapped": False,
            "sin_sign_by_half": [1, -1],
            "global_relayout_negation": False,
            "producer_to_destination_slice": "slice_id xor 0b10",
            "same_slice_add": False,
        },
        "coverage": {
            "logical_file_count": 49,
            "physical_file_count": 252,
            "nonempty_file_count": 301,
            "head_count": HEADS,
            "slice_count": SLICES,
            "stage_count": 3,
            "physical_tensors_per_slice": 9,
            "all_stage_inputs_outputs_covered": True,
            "op0_op1_external_activation_payloads_bit_equal": True,
        },
        "numeric_result": {
            "onnx_non_interleaved_equation": (
                "y_first=x_first*cos-x_second*sin; "
                "y_second=x_first*sin+x_second*cos"
            ),
            "generated_route": [
                route[slice_id] for slice_id in range(SLICES)
            ],
            "route_mismatch_count": 0,
            "logical_payload_matches_equation": True,
            "physical_payload_matches_native_relayout_primitive": True,
            "max_fp16_cast_error": max_fp16_error,
        },
        "rule_ids": [
            "CDA-DEEPSEEK-ROPE-HALF-PAIRING-001",
            "CDA-DEEPSEEK-ROPE-SIGN-SINGLE-OWNER-001",
            "CDA-DEEPSEEK-ROPE-PAYLOAD-COVERAGE-001",
            "CDA-DEEPSEEK-ROPE-IMPLEMENTATION-CHOICE-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_rope_numeric_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_rope_numeric_contract(project_root):
        raise DeepSeekRopeNumericError(
            "RoPE numeric contract differs from current payload"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekRopeNumericError",
    "MANIFEST_PATH",
    "build_rope_numeric_contract",
    "materialize_rope_numeric_payload",
    "validate_rope_numeric_contract",
]
