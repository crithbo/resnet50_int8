"""Fail-closed full-family audit for all ResNet50 RequantizeUint8 stages.

This module performs a read-only E2 numeric classification.  It does not
generate operator JSON, invoke the native planner, create a server package,
or modify any RTL source.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .w5_conv_preflight import _initializer_values


SCHEMA = "resnet50-requant-family-classification-v1"
RECEIPT_SCHEMA = "resnet50-requant-family-read-receipt-v1"
CONTRACT_SCHEMA = "operator-config-semantic-contract-v1"
ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-family-classification-v1"
)
REPORT_PATH = ARTIFACT_ROOT / "report.json"
RECEIPT_PATH = ARTIFACT_ROOT / "generation_receipt.json"
CONTRACT_PATH = Path(
    "contracts/operator_config/requant_family_classification_v1.json"
)
TYPED_PATH = Path("contracts/typed_config_parameter_contract.json")
LOWERING_PATH = Path("contracts/resnet50_r5_lowering_bundle.json")
MODEL_PATH = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
SUBOP_MANIFEST_PATH = Path("artifacts/w3/subop_batch16/manifest.json")
GOLDEN_MANIFEST_PATH = Path("artifacts/w3/golden_batch16/manifest.json")
NODE0001_REPORT_PATH = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1/local_e2_report.json"
)
NODE0001_CONTRACT_PATH = Path(
    "contracts/operator_config/"
    "requant_node0001_two_stage_contract_v1.json"
)
ACCUMULATOR_ROOT = Path("artifacts/w3/subop_batch16/tensors")
GOLDEN_ROOT = Path("artifacts/w3/golden_batch16/tensors")
ROUND_MAGIC = np.float32(12_582_912.0)
ROUND_MAGIC_BITS = np.int64(0x4B400000)

FAMILY_RULE_IDS = (
    "CDA-REQUANT-FAMILY-QPARAM-CLASSIFICATION-001",
    "CDA-REQUANT-FAMILY-W3-REPLAY-001",
    "CDA-REQUANT-NONZERO-ZP-GUARD-001",
    "CDA-REQUANT-ZP-TIE-PARITY-001",
    "CDA-REQUANT-FAMILY-EMISSION-BOUNDARY-001",
)


class RequantFamilyClassificationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantFamilyClassificationError(
            f"cannot parse JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RequantFamilyClassificationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise RequantFamilyClassificationError(
            f"required input is missing: {relative.as_posix()}"
        )
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _self_hash(value: Mapping[str, Any], field: str) -> str:
    payload = {key: item for key, item in value.items() if key != field}
    return sha256_bytes(canonical_json_bytes(payload))


def _parameter(
    stage: Mapping[str, Any], name: str
) -> Mapping[str, Any]:
    matches = [
        item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise RequantFamilyClassificationError(
            f"typed parameter is not unique: "
            f"{stage.get('hw_op_id')}:{name}"
        )
    return matches[0]


def _initializer_array(
    initializers: Mapping[str, Any],
    parameter: Mapping[str, Any],
    *,
    dtype: np.dtype[Any],
) -> np.ndarray:
    provenance = parameter.get("provenance")
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("kind") != "onnx_initializer"
        or not isinstance(provenance.get("onnx_name"), str)
    ):
        raise RequantFamilyClassificationError(
            f"initializer provenance is not exact: "
            f"{parameter.get('parameter_id')}"
        )
    onnx_name = str(provenance["onnx_name"])
    if onnx_name not in initializers:
        raise RequantFamilyClassificationError(
            f"ONNX initializer is missing: {onnx_name}"
        )
    array = np.asarray(initializers[onnx_name], dtype=dtype).reshape(-1)
    expected_shape = tuple(parameter.get("value", {}).get("shape", []))
    if tuple(array.shape) != expected_shape:
        raise RequantFamilyClassificationError(
            f"initializer shape differs: {onnx_name}: "
            f"{array.shape} != {expected_shape}"
        )
    return array


def _multiplier_and_zero_point(
    stage: Mapping[str, Any],
    initializers: Mapping[str, Any],
) -> tuple[np.ndarray, int]:
    multiplier_parameter = _parameter(stage, "requant_multiplier")
    provenance = multiplier_parameter.get("provenance")
    source_ids = (
        provenance.get("source_parameter_ids")
        if isinstance(provenance, Mapping)
        else None
    )
    if (
        multiplier_parameter.get("formula")
        not in {
            "float32(x_scale * w_scale / y_scale)",
            "float32(a_scale * b_scale / y_scale)",
        }
        or not isinstance(source_ids, list)
        or len(source_ids) != 3
    ):
        raise RequantFamilyClassificationError(
            f"requant multiplier formula differs: {stage.get('hw_op_id')}"
        )
    parameter_by_id = {
        str(item.get("parameter_id")): item
        for item in stage.get("parameters", [])
        if isinstance(item, Mapping)
    }
    source_parameters = [parameter_by_id.get(str(item)) for item in source_ids]
    if any(not isinstance(item, Mapping) for item in source_parameters):
        raise RequantFamilyClassificationError(
            f"multiplier source parameter is missing: {stage.get('hw_op_id')}"
        )
    arrays = [
        _initializer_array(
            initializers,
            item,
            dtype=np.dtype("float32"),
        )
        for item in source_parameters
        if isinstance(item, Mapping)
    ]
    if arrays[0].shape != (1,) or arrays[2].shape != (1,):
        raise RequantFamilyClassificationError(
            f"requant scalar scale ABI differs: {stage.get('hw_op_id')}"
        )
    multiplier = np.asarray(
        np.float32(arrays[0][0])
        * arrays[1]
        / np.float32(arrays[2][0]),
        dtype=np.float32,
    )
    expected = multiplier_parameter.get("value", {})
    multiplier_hash = hashlib.sha256(
        np.ascontiguousarray(multiplier).tobytes()
    ).hexdigest()
    if (
        tuple(multiplier.shape) != tuple(expected.get("shape", []))
        or multiplier_hash != expected.get("value_sha256")
        or not np.isfinite(multiplier).all()
        or not np.all(multiplier > 0)
    ):
        raise RequantFamilyClassificationError(
            f"requant multiplier identity/precondition differs: "
            f"{stage.get('hw_op_id')}"
        )
    zero_parameter = _parameter(stage, "y_zero_point")
    zero_array = _initializer_array(
        initializers, zero_parameter, dtype=np.dtype("uint8")
    )
    if zero_array.shape != (1,):
        raise RequantFamilyClassificationError(
            f"output zero-point ABI differs: {stage.get('hw_op_id')}"
        )
    zero_point = int(zero_array[0])
    if zero_point != zero_parameter.get("value", {}).get("scalar"):
        raise RequantFamilyClassificationError(
            f"output zero-point identity differs: {stage.get('hw_op_id')}"
        )
    return multiplier, zero_point


def _channel_multiplier_view(
    multiplier: np.ndarray, shape: tuple[int, ...]
) -> np.ndarray:
    if len(shape) == 4 and multiplier.shape == (shape[1],):
        return multiplier.reshape(1, shape[1], 1, 1)
    if len(shape) == 2 and multiplier.shape == (1,):
        return multiplier.reshape(1, 1)
    raise RequantFamilyClassificationError(
        f"unsupported requant multiplier/tensor ABI: "
        f"multiplier={multiplier.shape}, tensor={shape}"
    )


def _standard_replay(
    accumulator: np.ndarray,
    multiplier: np.ndarray,
    zero_point: int,
) -> tuple[np.ndarray, np.ndarray]:
    scaled = np.multiply(
        accumulator.astype(np.float32),
        _channel_multiplier_view(multiplier, tuple(accumulator.shape)),
        dtype=np.float32,
    )
    rounded = np.rint(scaled).astype(np.int64) + np.int64(zero_point)
    return np.clip(rounded, 0, 255).astype(np.uint8), scaled


def _magic_replay(
    scaled: np.ndarray, zero_point: int
) -> np.ndarray:
    rounded = (
        np.add(
            scaled,
            np.float32(ROUND_MAGIC + zero_point),
            dtype=np.float32,
        )
        .view(np.int32)
        .astype(np.int64)
        - ROUND_MAGIC_BITS
    )
    return np.clip(rounded, 0, 255).astype(np.uint8)


def _guarded_magic_replay(
    accumulator: np.ndarray,
    multiplier: np.ndarray,
    zero_point: int,
) -> tuple[np.ndarray, np.ndarray]:
    converted = accumulator.astype(np.float32)
    guard = np.maximum(converted, np.float32(0.0))
    expected_guard = np.maximum(accumulator, 0).astype(np.float32)
    if np.any(guard.view(np.uint32) != expected_guard.view(np.uint32)):
        raise RequantFamilyClassificationError(
            "software guard conversion does not preserve the expected bits"
        )
    scaled = np.multiply(
        guard,
        _channel_multiplier_view(multiplier, tuple(accumulator.shape)),
        dtype=np.float32,
    )
    return _magic_replay(scaled, zero_point), guard


def build_read_receipt(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    sources = {
        "agent_policy": Path(".agents/agent.md"),
        "generation_read_index": Path(
            ".agents/rules/生成前必读索引.md"
        ),
        "operator_rules": Path(".agents/rules/算子配置规则.md"),
        "hardware_field_semantics": Path(
            ".agents/rules/NDP硬件字段语义.md"
        ),
        "requant_rules": Path(
            ".agents/rules/RequantizeUint8算子配置规则.md"
        ),
        "typed_contract": TYPED_PATH,
        "lowering_bundle": LOWERING_PATH,
        "onnx_model": MODEL_PATH,
        "w3_subop_manifest": SUBOP_MANIFEST_PATH,
        "w3_golden_manifest": GOLDEN_MANIFEST_PATH,
        "node0001_local_e2_report": NODE0001_REPORT_PATH,
        "node0001_semantic_contract": NODE0001_CONTRACT_PATH,
    }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "scope": (
            "read-only 54-stage qparam/W3 numeric classification; "
            "no JSON, mapping, bitstream, execplan, SCA or server package "
            "is generated"
        ),
        "read_receipt": [
            {
                "label": label,
                **_binding(root, relative),
                "reason": (
                    "routing/rules"
                    if label
                    in {
                        "agent_policy",
                        "generation_read_index",
                        "operator_rules",
                        "hardware_field_semantics",
                        "requant_rules",
                    }
                    else "typed/qparam/W3 identity"
                ),
            }
            for label, relative in sources.items()
        ],
        "rule_ids": list(FAMILY_RULE_IDS),
        "known_counterexamples": [
            "CDA-GA-INPORT-CONVERT-001",
            "node0001 guard is only algebraically valid when y_zero_point=0",
            "adding an odd y_zero_point inside FP32 magic rounding changes tie parity",
        ],
        "open_dynamic_gates": ["B_REQUANT_SERVER_E4_E5"],
        "omitted_files": [
            {
                "path": "ndp-sim native planner/encoder/execplan consumers",
                "reason": (
                    "this audit does not generate or re-encode hardware "
                    "artifacts; node0001's existing materialized E2 identity "
                    "is only read as evidence"
                ),
            },
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "reason": "no server package is generated",
            },
        ],
        "rtl_modified": False,
        "server_package_generated": False,
    }
    receipt["receipt_sha256"] = _self_hash(receipt, "receipt_sha256")
    return receipt


def build_requant_family_classification(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = build_read_receipt(root)
    typed = _load(root / TYPED_PATH)
    lowering = _load(root / LOWERING_PATH)
    initializers = _initializer_values(root / MODEL_PATH)
    typed_by_id = {
        str(item.get("hw_op_id")): item
        for item in typed.get("hw_ops", [])
        if isinstance(item, Mapping)
    }
    requests = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping)
        and item.get("identity", {}).get("hw_op_type")
        == "RequantizeUint8"
    ]
    if len(requests) != 54:
        raise RequantFamilyClassificationError(
            f"RequantizeUint8 request count differs: {len(requests)}"
        )

    records: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    zero_point_counts: Counter[int] = Counter()
    shape_counts: Counter[str] = Counter()
    total_elements = 0
    total_negative = 0
    total_minus_one = 0
    total_zero = 0
    total_guard_mismatch = 0
    total_magic_mismatch = 0
    standard_mismatch_stages = 0
    magic_counterexample_stages: list[str] = []

    for request in requests:
        identity = request.get("identity", {})
        hw_op_id = str(identity.get("hw_op_id"))
        request_id = str(request.get("request_id"))
        stage = typed_by_id.get(hw_op_id)
        if not isinstance(stage, Mapping):
            raise RequantFamilyClassificationError(
                f"typed stage is missing: {hw_op_id}"
            )
        if request.get("request_sha256") is None:
            raise RequantFamilyClassificationError(
                f"request identity is missing: {request_id}"
            )
        multiplier, zero_point = _multiplier_and_zero_point(
            stage, initializers
        )
        input_port = request.get("ports", {}).get("inputs", [None])[0]
        output_port = request.get("ports", {}).get("outputs", [None])[0]
        if not isinstance(input_port, Mapping) or not isinstance(
            output_port, Mapping
        ):
            raise RequantFamilyClassificationError(
                f"typed ports are missing: {request_id}"
            )
        accumulator_relative = (
            ACCUMULATOR_ROOT / f"{input_port['tensor_id']}.npy"
        )
        golden_relative = GOLDEN_ROOT / f"{output_port['tensor_id']}.npy"
        accumulator_path = root / accumulator_relative
        golden_path = root / golden_relative
        if (
            not accumulator_path.is_file()
            or not golden_path.is_file()
            or sha256_file(accumulator_path)
            != input_port.get("identity_sha256")
            or sha256_file(golden_path)
            != output_port.get("identity_sha256")
        ):
            raise RequantFamilyClassificationError(
                f"W3 tensor identity differs: {request_id}"
            )
        accumulator = np.load(accumulator_path, allow_pickle=False)
        golden = np.load(golden_path, allow_pickle=False)
        expected_shape = tuple(
            request.get("logical_geometry", {}).get("output_shapes", [[]])[0]
        )
        if (
            accumulator.dtype != np.dtype("int32")
            or golden.dtype != np.dtype("uint8")
            or tuple(accumulator.shape) != expected_shape
            or tuple(golden.shape) != expected_shape
        ):
            raise RequantFamilyClassificationError(
                f"W3 tensor ABI differs: {request_id}"
            )
        standard, signed_scaled = _standard_replay(
            accumulator, multiplier, zero_point
        )
        magic = _magic_replay(signed_scaled, zero_point)
        guarded, guard = _guarded_magic_replay(
            accumulator, multiplier, zero_point
        )
        standard_mismatch = int(np.count_nonzero(standard != golden))
        magic_mismatch = int(np.count_nonzero(magic != golden))
        guard_mismatch = int(np.count_nonzero(guarded != golden))
        if standard_mismatch:
            standard_mismatch_stages += 1
        if magic_mismatch:
            magic_counterexample_stages.append(request_id)
        negative_count = int(np.count_nonzero(accumulator < 0))
        minus_one_count = int(np.count_nonzero(accumulator == -1))
        zero_count = int(np.count_nonzero(accumulator == 0))
        if zero_point == 0:
            if magic_mismatch or guard_mismatch:
                raise RequantFamilyClassificationError(
                    f"zero-point-zero guard recipe differs: {request_id}"
                )
            classification = (
                "FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001"
                if request_id == "r5:hwop-0001-01"
                else "NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING"
            )
            blockers = (
                ["B_REQUANT_SERVER_E4_E5"]
                if request_id == "r5:hwop-0001-01"
                else [
                    "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                    "B_REQUANT_SERVER_E4_E5",
                ]
            )
        else:
            if guard_mismatch == 0:
                raise RequantFamilyClassificationError(
                    f"nonzero zero-point unexpectedly passed guard: {request_id}"
                )
            classification = (
                "CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_ODD_ZP"
                if zero_point % 2
                else "CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_EVEN_ZP"
            )
            blockers = ["B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN"]
            if zero_point % 2:
                blockers.append("B_REQUANT_MAGIC_ZP_TIE_PARITY")
            if len(expected_shape) == 2:
                blockers.append("B_REQUANT_MATMUL_2D_LAYOUT")
            blockers.append("B_REQUANT_SERVER_E4_E5")
        if standard_mismatch:
            raise RequantFamilyClassificationError(
                f"independent ONNX requant replay differs: {request_id}"
            )
        channels = expected_shape[1]
        channel_tail = channels % 8
        shard_count = (channels + 7) // 8
        occurrence_forecast = 3 * shard_count
        physical_stage_forecast = 2 * occurrence_forecast
        shape_key = "x".join(str(item) for item in expected_shape)
        class_counts[classification] += 1
        zero_point_counts[zero_point] += 1
        shape_counts[shape_key] += 1
        total_elements += int(accumulator.size)
        total_negative += negative_count
        total_minus_one += minus_one_count
        total_zero += zero_count
        total_guard_mismatch += guard_mismatch
        total_magic_mismatch += magic_mismatch
        records.append(
            {
                "ordinal": len(records),
                "request_id": request_id,
                "request_sha256": request["request_sha256"],
                "identity": dict(identity),
                "predecessor_hw_op_ids": list(
                    request.get("predecessor_hw_op_ids", [])
                ),
                "logical_shape": list(expected_shape),
                "shape_signature": shape_key,
                "channels": channels,
                "channel_tail_mod8": channel_tail,
                "three_wave_occurrence_forecast_not_emission_authority": (
                    occurrence_forecast
                ),
                "two_stage_physical_stage_forecast_not_emission_authority": (
                    physical_stage_forecast
                ),
                "qparams": {
                    "y_zero_point": zero_point,
                    "zero_point_parity": (
                        "odd" if zero_point % 2 else "even"
                    ),
                    "multiplier_shape": list(multiplier.shape),
                    "multiplier_sha256": hashlib.sha256(
                        np.ascontiguousarray(multiplier).tobytes()
                    ).hexdigest(),
                    "multiplier_minimum": float(multiplier.min()),
                    "multiplier_maximum": float(multiplier.max()),
                    "all_multiplier_finite_positive": True,
                },
                "w3": {
                    "accumulator": _binding(root, accumulator_relative),
                    "golden": _binding(root, golden_relative),
                    "element_count": int(accumulator.size),
                    "minimum": int(accumulator.min()),
                    "maximum": int(accumulator.max()),
                    "negative_count": negative_count,
                    "minus_one_count": minus_one_count,
                    "zero_count": zero_count,
                    "standard_round_then_add_zp_mismatch_count": (
                        standard_mismatch
                    ),
                    "authorized_magic_mismatch_count": magic_mismatch,
                    "node0001_guard_recipe_mismatch_count": guard_mismatch,
                    "standard_replay_payload_sha256": hashlib.sha256(
                        np.ascontiguousarray(standard).tobytes()
                    ).hexdigest(),
                    "golden_payload_sha256": hashlib.sha256(
                        np.ascontiguousarray(golden).tobytes()
                    ).hexdigest(),
                },
                "classification": classification,
                "candidate_json_emission_allowed": (
                    request_id == "r5:hwop-0001-01"
                ),
                "formal_target_instance_allowed": False,
                "dynamic_release_ready": False,
                "blockers": blockers,
            }
        )

    if (
        standard_mismatch_stages != 0
        or class_counts["FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001"]
        != 1
        or class_counts[
            "NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING"
        ]
        != 32
        or class_counts[
            "CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_EVEN_ZP"
        ]
        != 16
        or class_counts[
            "CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_ODD_ZP"
        ]
        != 5
        or magic_counterexample_stages != ["r5:hwop-0014-01"]
    ):
        raise RequantFamilyClassificationError(
            "family classification totals differ from the closed W3 audit"
        )
    shape_records = [
        {"shape_signature": key, "request_count": count}
        for key, count in sorted(shape_counts.items())
    ]
    zero_records = [
        {"zero_point": key, "request_count": count}
        for key, count in sorted(zero_point_counts.items())
    ]
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "REQUANT_54_OF_54_NUMERIC_CLASSIFIED_"
            "NODE0001_ONLY_MATERIALIZED_E2"
        ),
        "inputs": {
            "read_receipt_semantic_sha256": receipt["receipt_sha256"],
            "typed_contract": _binding(root, TYPED_PATH),
            "lowering_bundle": _binding(root, LOWERING_PATH),
            "onnx_model": _binding(root, MODEL_PATH),
            "w3_subop_manifest": _binding(root, SUBOP_MANIFEST_PATH),
            "w3_golden_manifest": _binding(root, GOLDEN_MANIFEST_PATH),
            "node0001_local_e2_report": _binding(
                root, NODE0001_REPORT_PATH
            ),
            "node0001_semantic_contract": _binding(
                root, NODE0001_CONTRACT_PATH
            ),
        },
        "rule_ids": list(FAMILY_RULE_IDS),
        "summary": {
            "requant_stage_count": len(records),
            "standard_w3_golden_exact_stage_count": len(records),
            "standard_w3_golden_mismatch_stage_count": 0,
            "positive_finite_multiplier_stage_count": len(records),
            "zero_output_zero_point_stage_count": 33,
            "nonzero_output_zero_point_stage_count": 21,
            "odd_nonzero_output_zero_point_stage_count": 5,
            "even_nonzero_output_zero_point_stage_count": 16,
            "current_guard_numeric_compatible_stage_count": 33,
            "current_guard_contradicted_stage_count": 21,
            "full_materialized_local_e2_stage_count": 1,
            "numeric_compatible_physical_e2_pending_stage_count": 32,
            "candidate_json_emission_allowed_count": 1,
            "formal_target_instance_allowed_count": 0,
            "dynamic_release_ready_count": 0,
            "w3_element_count": total_elements,
            "w3_negative_element_count": total_negative,
            "w3_minus_one_element_count": total_minus_one,
            "w3_zero_element_count": total_zero,
            "guard_recipe_mismatch_count_for_nonzero_zp": (
                total_guard_mismatch
            ),
            "magic_rounding_mismatch_count": total_magic_mismatch,
            "magic_rounding_counterexample_stage_ids": (
                magic_counterexample_stages
            ),
            "classification_counts": dict(sorted(class_counts.items())),
            "shape_counts": shape_records,
            "zero_point_counts": zero_records,
        },
        "emission_boundary": {
            "node0001_remains_the_only_materialized_candidate": True,
            "compatible_numeric_recipe_does_not_approve_shape_schedule": True,
            "forecast_occurrence_and_stage_counts_are_not_emission_authority": True,
            "no_new_json_generated": True,
            "no_native_pipeline_invoked": True,
            "no_server_package_generated": True,
            "rtl_modified": False,
        },
        "records": records,
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "dynamic_release_ready": False,
        "remaining_work": {
            "zero_point_zero_holdouts": (
                "select one representative for each of the four unmaterialized "
                "shape signatures and independently close JSON, W4 lifetime, "
                "bitstream and execplan before extending emission scope"
            ),
            "nonzero_zero_point": (
                "derive a magnitude-preserving signed-domain path; the "
                "node0001 clamp guard is disproven for all 21 stages"
            ),
            "odd_zero_point": (
                "move zero-point addition after round-to-even or prove an "
                "equivalent topology; node0014 supplies a 32-element W3 "
                "tie-parity counterexample"
            ),
            "matmul_2d_layout": (
                "node0075 [16,1000] is divisible by eight but needs an "
                "explicit two-dimensional MatMul output layout contract"
            ),
            "dynamic": "B_REQUANT_SERVER_E4_E5",
        },
    }
    report["report_sha256"] = _self_hash(report, "report_sha256")
    return report


def build_requant_family_contract(
    project_root: Path,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    value = (
        dict(report)
        if report is not None
        else build_requant_family_classification(root)
    )
    summary = value["summary"]
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "contract_id": "requant-family-54-stage-classification-v1",
        "status": (
            "NUMERIC_CLASSIFICATION_COMPLETE_"
            "PHYSICAL_GENERALIZATION_FAIL_CLOSED"
        ),
        "scope": "all 54 ResNet50 RequantizeUint8 typed requests",
        "report_semantic_sha256": value["report_sha256"],
        "rule_ids": list(FAMILY_RULE_IDS),
        "counts": {
            "total": summary["requant_stage_count"],
            "node0001_full_local_e2": (
                summary["full_materialized_local_e2_stage_count"]
            ),
            "numeric_compatible_physical_e2_pending": (
                summary[
                    "numeric_compatible_physical_e2_pending_stage_count"
                ]
            ),
            "current_guard_contradicted": (
                summary["current_guard_contradicted_stage_count"]
            ),
        },
        "candidate_json_emission_allowed_ids": ["r5:hwop-0001-01"],
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "dynamic_release_ready": False,
        "server_package": False,
        "remaining_blockers": [
            "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
            "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
            "B_REQUANT_MAGIC_ZP_TIE_PARITY",
            "B_REQUANT_MATMUL_2D_LAYOUT",
            "B_REQUANT_SERVER_E4_E5",
        ],
    }
    contract["contract_sha256"] = _self_hash(
        contract, "contract_sha256"
    )
    return contract


def validate_requant_family_classification(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_requant_family_classification(project_root)
    if value != expected:
        raise RequantFamilyClassificationError(
            "requant family classification differs from hash-bound inputs"
        )


def validate_requant_family_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_requant_family_contract(project_root)
    if value != expected:
        raise RequantFamilyClassificationError(
            "requant family contract differs from hash-bound inputs"
        )


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "FAMILY_RULE_IDS",
    "REPORT_PATH",
    "RECEIPT_PATH",
    "RequantFamilyClassificationError",
    "build_read_receipt",
    "build_requant_family_classification",
    "build_requant_family_contract",
    "validate_requant_family_classification",
    "validate_requant_family_contract",
    "write_json",
]
