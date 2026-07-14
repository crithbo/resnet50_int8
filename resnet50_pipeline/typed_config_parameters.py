from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .lowering import HwOpInfo, lower_model_graph
from .model import ModelGraphCatalog, NodeInfo, TensorInfo, load_model_graph
from .target_config_audit import (
    OFFICIAL_CONFIG_COMMIT,
    OFFICIAL_CONFIG_REPOSITORY,
)


SCHEMA_VERSION = "0.1"
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"
RESOLUTION_STATES = frozenset({"derived", "approval_required", "rejected"})

EXPECTED_NODE_COUNTS = {
    "DequantizeLinear": 2,
    "Flatten": 1,
    "MaxPool": 1,
    "QLinearAdd": 17,
    "QLinearConv": 53,
    "QLinearGlobalAveragePool": 1,
    "QLinearMatMul": 1,
    "QuantizeLinear": 2,
}

NODE_INPUT_ROLES: dict[str, tuple[str, ...]] = {
    "QuantizeLinear": ("x", "y_scale", "y_zero_point"),
    "DequantizeLinear": ("x", "x_scale", "x_zero_point"),
    "QLinearConv": (
        "x",
        "x_scale",
        "x_zero_point",
        "w",
        "w_scale",
        "w_zero_point",
        "y_scale",
        "y_zero_point",
        "bias",
    ),
    "QLinearAdd": (
        "a",
        "a_scale",
        "a_zero_point",
        "b",
        "b_scale",
        "b_zero_point",
        "y_scale",
        "y_zero_point",
    ),
    "QLinearGlobalAveragePool": (
        "x",
        "x_scale",
        "x_zero_point",
        "y_scale",
        "y_zero_point",
    ),
    "QLinearMatMul": (
        "a",
        "a_scale",
        "a_zero_point",
        "b",
        "b_scale",
        "b_zero_point",
        "y_scale",
        "y_zero_point",
    ),
    "MaxPool": ("x",),
    "Flatten": ("x",),
}

STAGE_PARAMETER_ROLES: dict[tuple[str, str], tuple[str, ...]] = {
    ("QuantizeLinear", "quantize"): ("y_scale", "y_zero_point"),
    ("DequantizeLinear", "dequantize"): ("x_scale", "x_zero_point"),
    ("QLinearConv", "accumulate"): ("x_zero_point", "w_zero_point", "bias"),
    ("QLinearConv", "requantize"): (
        "x_scale",
        "w_scale",
        "y_scale",
        "y_zero_point",
    ),
    ("QLinearAdd", "add_requantize"): (
        "a_scale",
        "a_zero_point",
        "b_scale",
        "b_zero_point",
        "y_scale",
        "y_zero_point",
    ),
    ("QLinearGlobalAveragePool", "sum"): ("x_zero_point",),
    ("QLinearGlobalAveragePool", "requantize"): (
        "x_scale",
        "y_scale",
        "y_zero_point",
    ),
    ("QLinearMatMul", "accumulate"): ("a_zero_point", "b_zero_point"),
    ("QLinearMatMul", "requantize"): (
        "a_scale",
        "b_scale",
        "y_scale",
        "y_zero_point",
    ),
    ("MaxPool", "pool"): (),
    ("Flatten", "view"): (),
}

BLOCKERS: dict[str, dict[str, str]] = {
    "B_LAYOUT_APPROVAL": {
        "state": "approval_required",
        "description": "RTL28 physical port layout remains candidate rather than hardware-approved.",
    },
    "B_EXECPLAN_TYPED_TRANSPORT": {
        "state": "rejected",
        "description": "The official OperatorSpec and handlers do not transport typed qparams/constants.",
    },
    "B_QUANT_FP32_INPUT_PATH": {
        "state": "rejected",
        "description": "The audited quant template consumes INT32, not ONNX QuantizeLinear FP32 input.",
    },
    "B_QUANT_ROUNDING_EXECUTION": {
        "state": "rejected",
        "description": "Nearest-even and saturation were inferred but not executed by an approved target model.",
    },
    "B_CONV_INT8_SA": {
        "state": "rejected",
        "description": "No official INT8 SA Conv template and accumulator contract is available.",
    },
    "B_CONV_BIAS_PSUM": {
        "state": "rejected",
        "description": "Bias and first/middle/last-K INT32 psum lifecycle are not bound to official fields.",
    },
    "B_REQUANT_TARGET_NUMERICS": {
        "state": "rejected",
        "description": "INT32-to-UINT8 requant rounding, saturation and target execution are not closed.",
    },
    "B_MAXPOOL_SHAPE_GENERALIZATION": {
        "state": "approval_required",
        "description": "C4 shape-to-LC rules cover audited samples but are not approved as a general generator.",
    },
    "B_MAXPOOL_UINT8_SEMANTICS": {
        "state": "rejected",
        "description": "Signed int8_max behavior has not been proven equivalent to UINT8 MaxPool.",
    },
    "B_ADD_UINT8_REQUANT": {
        "state": "rejected",
        "description": "The audited Add-Dequant template ends in FP32 and does not consume output qparams.",
    },
    "B_GAP_CENTERED_SUM": {
        "state": "rejected",
        "description": "The static AvgPool sum template does not prove subtraction of input zero point.",
    },
    "B_GAP_DIV_REQUANT": {
        "state": "rejected",
        "description": "Division by the spatial count and UINT8 requant are absent from the audited template.",
    },
    "B_SUM_COMPLETION": {
        "state": "rejected",
        "description": "Static full-event wiring does not establish the hardware completion protocol.",
    },
    "B_SUM_CROSS_SLICE": {
        "state": "rejected",
        "description": "Remote-sum names do not prove N2N/neighbor transport or cross-slice reduction.",
    },
    "B_MATMUL_INT8_SA": {
        "state": "rejected",
        "description": "All audited SA GEMM/GEMV templates are FP16 rather than INT8/INT32.",
    },
    "B_MATMUL_TAIL": {
        "state": "rejected",
        "description": "M=16 and N=1000 tail rules are absent and current floor division omits work.",
    },
    "B_MATMUL_PSUM": {
        "state": "rejected",
        "description": "Persistent INT32 psum and SA-to-GA requant boundaries are unbound.",
    },
    "B_DEQUANT_STANDALONE": {
        "state": "rejected",
        "description": "No audited standalone one-input UINT8-to-FP32 Dequantize configuration exists.",
    },
}


class TypedConfigParameterError(ValueError):
    """A C7 input or typed parameter contract violates a frozen invariant."""


@dataclass(frozen=True)
class TypedParameter:
    parameter_id: str
    name: str
    parameter_kind: str
    value: dict[str, Any]
    provenance: dict[str, Any]
    formula: str
    resolution: str = "derived"
    formal_target_write_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        if self.resolution not in RESOLUTION_STATES:
            raise TypedConfigParameterError(
                f"invalid parameter resolution: {self.resolution}"
            )
        if self.formal_target_write_allowed:
            raise TypedConfigParameterError(
                "C7 formula parameters cannot authorize formal target writes"
            )
        return asdict(self)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TypedConfigParameterError(f"cannot read C7 source JSON: {path}") from error
    if not isinstance(value, dict):
        raise TypedConfigParameterError(f"C7 source JSON must be an object: {path}")
    return value


def _as_float32(value: np.ndarray | float | int) -> np.ndarray:
    return np.asarray(value, dtype=np.float32)


def _typed_value(
    value: np.ndarray | np.generic | float | int,
    *,
    shape: tuple[int, ...] | None = None,
    axis: int | None = None,
) -> dict[str, Any]:
    array = np.asarray(value)
    if shape is not None:
        expected = int(np.prod(shape, dtype=np.int64)) if shape else 1
        if array.size != expected:
            raise TypedConfigParameterError(
                f"typed value has {array.size} elements; expected {expected} for {shape}"
            )
        array = array.reshape(shape)
    array = np.ascontiguousarray(array)
    if array.dtype.kind == "f" and not np.all(np.isfinite(array)):
        raise TypedConfigParameterError("typed floating-point value is not finite")
    record: dict[str, Any] = {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "element_count": int(array.size),
        "value_sha256": sha256_bytes(array.tobytes(order="C")),
        "value_kind": "scalar" if array.size == 1 else "per_channel",
    }
    if array.size == 1:
        scalar = array.reshape(-1)[0]
        record["scalar"] = float(scalar) if array.dtype.kind == "f" else int(scalar)
        if array.dtype == np.dtype("float32"):
            bits = int(array.reshape(-1).view(np.uint32)[0])
            record["float32_bits"] = f"0x{bits:08x}"
    else:
        if array.ndim != 1 or axis is None:
            raise TypedConfigParameterError(
                "non-scalar C7 parameters must preserve an explicit per-channel axis"
            )
        record["axis"] = axis
        record["minimum"] = (
            float(array.min()) if array.dtype.kind == "f" else int(array.min())
        )
        record["maximum"] = (
            float(array.max()) if array.dtype.kind == "f" else int(array.max())
        )
    return record


def _parameter_kind(role: str) -> str:
    if role.endswith("_scale"):
        return "scale"
    if role.endswith("_zero_point"):
        return "zero_point"
    if role == "bias":
        return "bias"
    return "derived"


def _concrete_tensor_descriptor(
    tensor_id: str,
    *,
    graph_tensors: dict[str, TensorInfo],
    runtime_tensors: dict[str, Any],
    runtime_initializers: dict[str, Any],
    internal_tensors: dict[str, Any],
) -> dict[str, Any]:
    if tensor_id in internal_tensors:
        record = internal_tensors[tensor_id]
        return {
            "tensor_id": tensor_id,
            "kind": "lowering_internal",
            "onnx_name": None,
            "dtype": record["dtype"],
            "shape": list(record["shape"]),
            "identity_sha256": record["sha256"],
            "identity_source": "artifacts/w3/subop_batch16/manifest.json",
        }
    try:
        tensor = graph_tensors[tensor_id]
    except KeyError as error:
        raise TypedConfigParameterError(f"unknown tensor in C7 hw_op: {tensor_id}") from error
    records = runtime_initializers if tensor.kind == "initializer" else runtime_tensors
    if tensor_id not in records:
        raise TypedConfigParameterError(
            f"W3 manifest lacks a concrete record for {tensor_id}"
        )
    record = records[tensor_id]
    return {
        "tensor_id": tensor_id,
        "kind": tensor.kind,
        "onnx_name": tensor.onnx_name,
        "dtype": record["dtype"],
        "shape": list(record["shape"]),
        "identity_sha256": record["sha256"],
        "identity_source": "artifacts/w3/golden_batch16/manifest.json",
    }


def _validate_w3_sources(
    graph: ModelGraphCatalog,
    lowering: Any,
    stored_graph: dict[str, Any],
    runtime: dict[str, Any],
    subop: dict[str, Any],
) -> None:
    if canonical_json_bytes(graph.to_dict()) != canonical_json_bytes(stored_graph):
        raise TypedConfigParameterError(
            "locked ONNX graph differs from artifacts/w3/model_graph.json"
        )
    if runtime.get("schema_version") != "0.1" or runtime.get("model_sha256") != MODEL_SHA256:
        raise TypedConfigParameterError("W3 runtime manifest identity differs")
    if subop.get("schema_version") != "0.1" or subop.get("model_sha256") != MODEL_SHA256:
        raise TypedConfigParameterError("W3 subop manifest identity differs")
    expected_nodes = [
        {
            "node_id": node.node_id,
            "onnx_name": node.onnx_name,
            "op_type": node.op_type,
            "input_tensor_ids": list(node.input_tensor_ids),
            "output_tensor_ids": list(node.output_tensor_ids),
        }
        for node in graph.nodes
    ]
    if runtime.get("nodes") != expected_nodes:
        raise TypedConfigParameterError("W3 runtime node identities differ from model graph")
    expected_runtime_ids = set(graph.graph_input_ids) | {
        tensor_id for node in graph.nodes for tensor_id in node.output_tensor_ids
    }
    if set(runtime.get("tensors", {})) != expected_runtime_ids:
        raise TypedConfigParameterError("W3 runtime tensor coverage differs")
    graph_initializers = {
        tensor.tensor_id: {
            "onnx_name": tensor.onnx_name,
            "sha256": tensor.initializer_sha256,
            "dtype": tensor.dtype,
            "shape": list(tensor.shape),
        }
        for tensor in graph.tensors
        if tensor.kind == "initializer"
    }
    if runtime.get("initializers") != graph_initializers:
        raise TypedConfigParameterError("W3 initializer identities differ from model graph")
    internal = subop.get("internal_tensors", {})
    if set(internal) != set(lowering.internal_tensor_ids):
        raise TypedConfigParameterError("W3 internal tensor coverage differs from lowering")
    producer_by_tensor = {
        output: hw_op.hw_op_id
        for hw_op in lowering.hw_ops
        for output in hw_op.output_tensor_ids
        if output in lowering.internal_tensor_ids
    }
    for tensor_id, record in internal.items():
        if (
            record.get("dtype") != "int32"
            or record.get("producer_hw_op_id") != producer_by_tensor[tensor_id]
            or not record.get("shape")
            or record["shape"][0] != 16
        ):
            raise TypedConfigParameterError(
                f"W3 internal tensor metadata differs for {tensor_id}"
            )


def _initializer_parameter(
    *,
    hw_op: HwOpInfo,
    role: str,
    tensor: TensorInfo,
    value: np.ndarray,
) -> TypedParameter:
    if tensor.kind != "initializer" or tensor.initializer_sha256 is None:
        raise TypedConfigParameterError(
            f"{hw_op.hw_op_id}.{role} is not a locked initializer"
        )
    if str(value.dtype) != tensor.dtype:
        raise TypedConfigParameterError(
            f"initializer dtype mismatch for {tensor.onnx_name}: {value.dtype} != {tensor.dtype}"
        )
    shape = tuple(int(item) for item in tensor.shape)
    reshaped = np.ascontiguousarray(value).reshape(shape)
    digest = sha256_bytes(reshaped.tobytes(order="C"))
    if digest != tensor.initializer_sha256:
        raise TypedConfigParameterError(
            f"initializer hash mismatch for {tensor.onnx_name}"
        )
    axis = 0 if reshaped.size > 1 else None
    return TypedParameter(
        parameter_id=f"{hw_op.hw_op_id}.initializer.{role}",
        name=role,
        parameter_kind=_parameter_kind(role),
        value=_typed_value(reshaped, axis=axis),
        provenance={
            "kind": "onnx_initializer",
            "model_sha256": MODEL_SHA256,
            "tensor_id": tensor.tensor_id,
            "onnx_name": tensor.onnx_name,
            "initializer_sha256": tensor.initializer_sha256,
        },
        formula="identity",
    )


def _derived_parameter(
    hw_op: HwOpInfo,
    name: str,
    value: np.ndarray | np.generic | float | int,
    formula: str,
    source_ids: list[str],
) -> TypedParameter:
    array = np.asarray(value)
    axis = 0 if array.size > 1 else None
    return TypedParameter(
        parameter_id=f"{hw_op.hw_op_id}.derived.{name}",
        name=name,
        parameter_kind="derived",
        value=_typed_value(array, axis=axis),
        provenance={
            "kind": "formula",
            "arithmetic_dtype": str(array.dtype),
            "source_parameter_ids": source_ids,
        },
        formula=formula,
    )


def _parameter_array(parameters: dict[str, tuple[TypedParameter, np.ndarray]], role: str) -> np.ndarray:
    try:
        return parameters[role][1]
    except KeyError as error:
        raise TypedConfigParameterError(f"formula lacks required parameter {role}") from error


def _derived_parameters(
    node: NodeInfo,
    hw_op: HwOpInfo,
    parameters: dict[str, tuple[TypedParameter, np.ndarray]],
    input_descriptors: list[dict[str, Any]],
    node_input_descriptors: list[dict[str, Any]],
) -> list[TypedParameter]:
    ids = lambda *roles: [parameters[role][0].parameter_id for role in roles]
    result: list[TypedParameter] = []
    key = (node.op_type, hw_op.stage)
    if key == ("QuantizeLinear", "quantize"):
        scale = _as_float32(_parameter_array(parameters, "y_scale"))
        result.append(
            _derived_parameter(
                hw_op,
                "reciprocal_output_scale",
                np.asarray(np.float32(1.0) / scale, dtype=np.float32),
                "float32(1.0 / y_scale)",
                ids("y_scale"),
            )
        )
    elif key == ("DequantizeLinear", "dequantize"):
        scale = _as_float32(_parameter_array(parameters, "x_scale"))
        zero = _parameter_array(parameters, "x_zero_point").astype(np.float32)
        result.append(
            _derived_parameter(
                hw_op,
                "affine_offset",
                np.asarray(-zero * scale, dtype=np.float32),
                "float32(-x_zero_point * x_scale)",
                ids("x_zero_point", "x_scale"),
            )
        )
    elif key == ("QLinearConv", "requantize"):
        x_scale = _as_float32(_parameter_array(parameters, "x_scale"))
        w_scale = _as_float32(_parameter_array(parameters, "w_scale"))
        y_scale = _as_float32(_parameter_array(parameters, "y_scale"))
        result.append(
            _derived_parameter(
                hw_op,
                "requant_multiplier",
                np.asarray(x_scale * w_scale / y_scale, dtype=np.float32),
                "float32(x_scale * w_scale / y_scale)",
                ids("x_scale", "w_scale", "y_scale"),
            )
        )
    elif key == ("QLinearAdd", "add_requantize"):
        for branch in ("a", "b"):
            scale_role = f"{branch}_scale"
            zero_role = f"{branch}_zero_point"
            scale = _as_float32(_parameter_array(parameters, scale_role))
            zero = _parameter_array(parameters, zero_role).astype(np.float32)
            result.append(
                _derived_parameter(
                    hw_op,
                    f"{branch}_dequant_offset",
                    np.asarray(-zero * scale, dtype=np.float32),
                    f"float32(-{zero_role} * {scale_role})",
                    ids(zero_role, scale_role),
                )
            )
    elif key == ("QLinearGlobalAveragePool", "requantize"):
        if not input_descriptors or input_descriptors[0]["kind"] != "lowering_internal":
            raise TypedConfigParameterError("GAP requantize lacks its internal sum input")
        output_shape = input_descriptors[0]["shape"]
        if len(output_shape) != 4 or output_shape[2:] != [1, 1]:
            raise TypedConfigParameterError("GAP internal output geometry differs")
        activation_shape = node_input_descriptors[0]["shape"]
        if len(activation_shape) != 4:
            raise TypedConfigParameterError("GAP activation geometry differs")
        spatial_count_value = int(activation_shape[2] * activation_shape[3])
        spatial_count = np.asarray(spatial_count_value, dtype=np.int32)
        x_scale = _as_float32(_parameter_array(parameters, "x_scale"))
        y_scale = _as_float32(_parameter_array(parameters, "y_scale"))
        result.extend(
            (
                _derived_parameter(
                    hw_op,
                    "spatial_element_count",
                    spatial_count,
                    "H * W from the W3 GAP input shape",
                    [],
                ),
                _derived_parameter(
                    hw_op,
                    "requant_multiplier",
                    np.asarray(
                        x_scale / (y_scale * np.float32(spatial_count_value)),
                        dtype=np.float32,
                    ),
                    "float32(x_scale / (y_scale * spatial_element_count))",
                    ids("x_scale", "y_scale"),
                ),
            )
        )
    elif key == ("QLinearMatMul", "requantize"):
        a_scale = _as_float32(_parameter_array(parameters, "a_scale"))
        b_scale = _as_float32(_parameter_array(parameters, "b_scale"))
        y_scale = _as_float32(_parameter_array(parameters, "y_scale"))
        result.append(
            _derived_parameter(
                hw_op,
                "requant_multiplier",
                np.asarray(a_scale * b_scale / y_scale, dtype=np.float32),
                "float32(a_scale * b_scale / y_scale)",
                ids("a_scale", "b_scale", "y_scale"),
            )
        )
    return result


def _logical_geometry(
    node: NodeInfo,
    hw_op: HwOpInfo,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    geometry: dict[str, Any] = {
        "input_shapes": [item["shape"] for item in inputs],
        "output_shapes": [item["shape"] for item in outputs],
        "input_dtypes": [item["dtype"] for item in inputs],
        "output_dtypes": [item["dtype"] for item in outputs],
        "attributes": node.attributes,
    }
    if node.op_type == "QLinearAdd":
        data_shapes = [inputs[0]["shape"], inputs[3]["shape"]]
        geometry["broadcast"] = {
            "a_shape": data_shapes[0],
            "b_shape": data_shapes[1],
            "output_shape": outputs[0]["shape"],
            "kind": "numpy_trailing_axis_broadcast",
        }
    elif node.op_type == "QLinearMatMul" and hw_op.stage == "accumulate":
        data_shapes = [inputs[0]["shape"], inputs[2]["shape"]]
        geometry["mnk"] = {
            "M": data_shapes[0][-2],
            "N": data_shapes[1][-1],
            "K": data_shapes[0][-1],
        }
    elif node.op_type == "QLinearGlobalAveragePool":
        # Sum stage input is the original activation; requant stage input is internal.
        if inputs[0]["kind"] != "lowering_internal":
            shape = inputs[0]["shape"]
            geometry["reduction"] = {
                "axes": [2, 3],
                "spatial_element_count": int(shape[2] * shape[3]),
                "keepdims": True,
            }
    elif node.op_type == "Flatten":
        geometry["view"] = {
            "axis": int(node.attributes.get("axis", 1)),
            "logical_zero_copy_candidate": True,
        }
    return geometry


def _field_binding(
    hw_op: HwOpInfo,
    field_family: str,
    resolution: str,
    *,
    parameter_ids: list[str] | None = None,
    blockers: list[str] | None = None,
    evidence: str,
) -> dict[str, Any]:
    if resolution not in RESOLUTION_STATES:
        raise TypedConfigParameterError(f"invalid field resolution {resolution}")
    blocker_ids = blockers or []
    if resolution == "derived" and blocker_ids:
        raise TypedConfigParameterError("derived field binding cannot carry blockers")
    if resolution != "derived" and not blocker_ids:
        raise TypedConfigParameterError("non-derived field binding must identify blockers")
    for blocker in blocker_ids:
        if blocker not in BLOCKERS or BLOCKERS[blocker]["state"] != resolution:
            raise TypedConfigParameterError(
                f"field binding {field_family} has an incompatible blocker {blocker}"
            )
    return {
        "field_binding_id": f"{hw_op.hw_op_id}.field.{field_family}",
        "field_family": field_family,
        "resolution": resolution,
        "parameter_ids": parameter_ids or [],
        "blockers": blocker_ids,
        "evidence": evidence,
        "formal_target_write_allowed": False,
    }


def _field_bindings(
    node: NodeInfo,
    hw_op: HwOpInfo,
    direct: list[TypedParameter],
    derived: list[TypedParameter],
) -> list[dict[str, Any]]:
    direct_ids = [item.parameter_id for item in direct]
    derived_ids = [item.parameter_id for item in derived]
    fields = [
        _field_binding(
            hw_op,
            "logical_tensor_geometry_and_dtype",
            "derived",
            evidence="locked W3 batch16 manifests plus model_graph/lowering identities",
        ),
        _field_binding(
            hw_op,
            "rtl28_physical_port_layout",
            "approval_required",
            blockers=["B_LAYOUT_APPROVAL"],
            evidence="W4-28 C1-C3 candidate layouts; no approved hardware layout contract",
        ),
    ]
    if direct_ids:
        fields.append(
            _field_binding(
                hw_op,
                "logical_typed_parameters",
                "derived",
                parameter_ids=direct_ids,
                evidence="locked ONNX initializer values with exact dtype/shape/hash provenance",
            )
        )
        fields.append(
            _field_binding(
                hw_op,
                "execplan_typed_parameter_transport",
                "rejected",
                parameter_ids=direct_ids,
                blockers=["B_EXECPLAN_TYPED_TRANSPORT"],
                evidence="C5/C6 AST audit of official OperatorSpec and handlers",
            )
        )
    if derived_ids:
        fields.append(
            _field_binding(
                hw_op,
                "formula_derived_parameters",
                "derived",
                parameter_ids=derived_ids,
                evidence="W3 independently replayed QNN formulas; formula scope only",
            )
        )

    key = (node.op_type, hw_op.stage)
    rejection_rules: dict[tuple[str, str], tuple[str, list[str], str]] = {
        ("QuantizeLinear", "quantize"): (
            "ga_fp32_to_uint8_quant_recipe",
            ["B_QUANT_FP32_INPUT_PATH", "B_QUANT_ROUNDING_EXECUTION"],
            "C5 proved the static template is INT32-to-UINT8 rather than ONNX QuantizeLinear",
        ),
        ("QLinearConv", "accumulate"): (
            "sa_int8_conv_accumulate_bias_psum",
            ["B_CONV_INT8_SA", "B_CONV_BIAS_PSUM"],
            "C6 found no official INT8 SA template or psum lifecycle",
        ),
        ("QLinearConv", "requantize"): (
            "ga_conv_int32_to_uint8_requant",
            ["B_REQUANT_TARGET_NUMERICS"],
            "per-channel multiplier is derived but target numerical execution is not closed",
        ),
        ("MaxPool", "pool"): (
            "ga_uint8_maxpool_semantics",
            ["B_MAXPOOL_UINT8_SEMANTICS"],
            "C4 only proved static signed int8_max encoding",
        ),
        ("QLinearAdd", "add_requantize"): (
            "ga_qlinearadd_uint8_output_requant",
            ["B_ADD_UINT8_REQUANT"],
            "C5 Add-Dequant ends in FP32 and ignores y_scale/y_zero_point",
        ),
        ("QLinearGlobalAveragePool", "sum"): (
            "ga_centered_uint8_to_int32_sum",
            ["B_GAP_CENTERED_SUM", "B_SUM_CROSS_SLICE", "B_SUM_COMPLETION"],
            "C4/C6 do not close zero-point subtraction, cross-slice transport or completion semantics",
        ),
        ("QLinearGlobalAveragePool", "requantize"): (
            "ga_gap_divide_requant_uint8",
            ["B_GAP_DIV_REQUANT", "B_REQUANT_TARGET_NUMERICS"],
            "spatial divisor and multiplier are derived but absent from the official template",
        ),
        ("QLinearMatMul", "accumulate"): (
            "sa_int8_matmul_accumulate_psum_tail",
            ["B_MATMUL_INT8_SA", "B_MATMUL_TAIL", "B_MATMUL_PSUM"],
            "C6 templates are FP16 and omit the ResNet M/N tail and INT32 psum lifecycle",
        ),
        ("QLinearMatMul", "requantize"): (
            "ga_matmul_int32_to_uint8_requant",
            ["B_MATMUL_PSUM", "B_REQUANT_TARGET_NUMERICS"],
            "C6 found no validated SA-to-GA requant boundary",
        ),
        ("DequantizeLinear", "dequantize"): (
            "ga_standalone_uint8_to_fp32_dequant",
            ["B_DEQUANT_STANDALONE"],
            "C5 only proved branch affine constants inside a two-input Add-Dequant template",
        ),
    }
    if key == ("MaxPool", "pool"):
        fields.append(
            _field_binding(
                hw_op,
                "maxpool_shape_lc_stream_buffer_ga_linkage",
                "approval_required",
                blockers=["B_MAXPOOL_SHAPE_GENERALIZATION"],
                evidence="C4 exact linkage over two audited non-tail templates",
            )
        )
    if key in {
        ("QLinearAdd", "add_requantize"),
        ("DequantizeLinear", "dequantize"),
    } and derived_ids:
        fields.append(
            _field_binding(
                hw_op,
                "ga_add_dequant_affine_constants_formula",
                "derived",
                parameter_ids=direct_ids + derived_ids,
                evidence="C5 four-lane/eight-lane affine constant crosswalk; formula scope only",
            )
        )
    if key in rejection_rules:
        family, blockers, evidence = rejection_rules[key]
        fields.append(
            _field_binding(
                hw_op,
                family,
                "rejected",
                parameter_ids=direct_ids + derived_ids,
                blockers=blockers,
                evidence=evidence,
            )
        )
    elif key == ("Flatten", "view"):
        fields.append(
            _field_binding(
                hw_op,
                "view_zero_copy_physical_identity",
                "approval_required",
                blockers=["B_LAYOUT_APPROVAL"],
                evidence="C1 zero-copy candidate requires the approved adjacent physical layouts",
            )
        )
    return fields


def _load_initializer_arrays(model_path: Path, graph: ModelGraphCatalog) -> dict[str, np.ndarray]:
    model = onnx.load(model_path, load_external_data=True)
    by_name = {tensor.onnx_name: tensor for tensor in graph.tensors}
    arrays: dict[str, np.ndarray] = {}
    for initializer in model.graph.initializer:
        tensor = by_name[initializer.name]
        array = np.ascontiguousarray(
            numpy_helper.to_array(initializer, base_dir=str(model_path.parent))
        )
        expected_shape = tuple(int(item) for item in tensor.shape)
        arrays[tensor.tensor_id] = array.reshape(expected_shape)
    expected = {tensor.tensor_id for tensor in graph.tensors if tensor.kind == "initializer"}
    if set(arrays) != expected:
        raise TypedConfigParameterError("locked ONNX initializer coverage differs from model graph")
    return arrays


def build_typed_config_parameter_contract(project_root: Path) -> dict[str, Any]:
    """Build the deterministic W4-28 C7 formula-only typed parameter contract.

    The function only reads the locked ONNX model and the three small W3 JSON
    manifests.  It never reads W3 .npy payloads or emits target instances.
    """

    root = project_root.resolve()
    model_path = root / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
    graph_path = root / "artifacts" / "w3" / "model_graph.json"
    runtime_path = root / "artifacts" / "w3" / "golden_batch16" / "manifest.json"
    subop_path = root / "artifacts" / "w3" / "subop_batch16" / "manifest.json"
    authority_path = root / "contracts" / "target_config_authority_audit.json"

    stored_graph = _load_json(graph_path)
    runtime = _load_json(runtime_path)
    subop = _load_json(subop_path)
    graph = load_model_graph(model_path, expected_sha256=MODEL_SHA256)
    # ModelGraphCatalog intentionally records paths relative to the caller's
    # cwd.  C7 is rooted by project_root instead, so normalize that display
    # field to the already frozen W3 identity before comparing/serializing.
    graph = replace(graph, model_path=str(stored_graph.get("model_path", "")))
    lowering = lower_model_graph(graph)
    _validate_w3_sources(graph, lowering, stored_graph, runtime, subop)
    arrays = _load_initializer_arrays(model_path, graph)

    graph_tensors = {tensor.tensor_id: tensor for tensor in graph.tensors}
    nodes = {node.node_id: node for node in graph.nodes}
    descriptor_kwargs = {
        "graph_tensors": graph_tensors,
        "runtime_tensors": runtime["tensors"],
        "runtime_initializers": runtime["initializers"],
        "internal_tensors": subop["internal_tensors"],
    }
    records: list[dict[str, Any]] = []
    all_parameter_ids: set[str] = set()
    for hw_op in lowering.hw_ops:
        node = nodes[hw_op.node_id]
        roles = NODE_INPUT_ROLES[node.op_type]
        if len(roles) != len(node.input_tensor_ids):
            raise TypedConfigParameterError(
                f"input role schema differs for {node.node_id} {node.op_type}"
            )
        role_by_tensor = dict(zip(node.input_tensor_ids, roles, strict=True))
        input_descriptors = [
            _concrete_tensor_descriptor(tensor_id, **descriptor_kwargs)
            for tensor_id in hw_op.input_tensor_ids
        ]
        node_input_descriptors = [
            _concrete_tensor_descriptor(tensor_id, **descriptor_kwargs)
            for tensor_id in node.input_tensor_ids
        ]
        output_descriptors = [
            _concrete_tensor_descriptor(tensor_id, **descriptor_kwargs)
            for tensor_id in hw_op.output_tensor_ids
        ]
        direct: list[TypedParameter] = []
        parameter_arrays: dict[str, tuple[TypedParameter, np.ndarray]] = {}
        for role in STAGE_PARAMETER_ROLES[(node.op_type, hw_op.stage)]:
            tensor_id = node.input_tensor_ids[roles.index(role)]
            tensor = graph_tensors[tensor_id]
            parameter = _initializer_parameter(
                hw_op=hw_op,
                role=role,
                tensor=tensor,
                value=arrays[tensor_id],
            )
            direct.append(parameter)
            parameter_arrays[role] = (parameter, arrays[tensor_id])
        derived = _derived_parameters(
            node,
            hw_op,
            parameter_arrays,
            input_descriptors,
            node_input_descriptors,
        )
        parameters = [item.to_dict() for item in (*direct, *derived)]
        for parameter in parameters:
            if parameter["parameter_id"] in all_parameter_ids:
                raise TypedConfigParameterError("duplicate typed parameter ID")
            all_parameter_ids.add(parameter["parameter_id"])
        input_roles = [
            "internal_accumulator"
            if item["tensor_id"] in lowering.internal_tensor_ids
            else role_by_tensor[item["tensor_id"]]
            for item in input_descriptors
        ]
        fields = _field_bindings(node, hw_op, direct, derived)
        records.append(
            {
                "hw_op_id": hw_op.hw_op_id,
                "node_id": node.node_id,
                "onnx_name": node.onnx_name,
                "onnx_op_type": node.op_type,
                "stage": hw_op.stage,
                "hw_op_type": hw_op.op_type,
                "predecessor_hw_op_ids": list(hw_op.predecessor_hw_op_ids),
                "ports": {
                    "inputs": [
                        {**descriptor, "role": role}
                        for descriptor, role in zip(
                            input_descriptors, input_roles, strict=True
                        )
                    ],
                    "outputs": output_descriptors,
                },
                "logical_geometry": _logical_geometry(
                    node, hw_op, input_descriptors, output_descriptors
                ),
                "parameters": parameters,
                "field_bindings": fields,
                "formal_target_instance_allowed": False,
            }
        )

    direct_parameters = [
        parameter
        for record in records
        for parameter in record["parameters"]
        if parameter["provenance"]["kind"] == "onnx_initializer"
    ]
    derived_parameters = [
        parameter
        for record in records
        for parameter in record["parameters"]
        if parameter["provenance"]["kind"] == "formula"
    ]
    fields = [field for record in records for field in record["field_bindings"]]
    resolution_counts = dict(
        sorted(Counter(field["resolution"] for field in fields).items())
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "contract_type": "typed_config_parameter_contract",
        "contract_id": "w4-28-c7-resnet50-batch16-typed-parameters-v1",
        "status": "candidate_formula_contract",
        "source": {
            "model_path": "artifacts/reference_model/resnet50-v1-12-int8.onnx",
            "model_sha256": MODEL_SHA256,
            "model_graph_path": "artifacts/w3/model_graph.json",
            "model_graph_sha256": sha256_file(graph_path),
            "runtime_manifest_path": "artifacts/w3/golden_batch16/manifest.json",
            "runtime_manifest_sha256": sha256_file(runtime_path),
            "subop_manifest_path": "artifacts/w3/subop_batch16/manifest.json",
            "subop_manifest_sha256": sha256_file(subop_path),
            "lowering_sha256": sha256_bytes(
                canonical_json_bytes(lowering.to_dict(graph))
            ),
            "target_config_repository": OFFICIAL_CONFIG_REPOSITORY,
            "target_config_commit": OFFICIAL_CONFIG_COMMIT,
            "target_config_authority_path": "contracts/target_config_authority_audit.json",
            "target_config_authority_sha256": sha256_file(authority_path),
        },
        "scope": {
            "batch_size": 16,
            "slice_count": 28,
            "reads_w3_tensor_payloads": False,
            "formula_scope_only": True,
            "patched_json_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "bank_data_generated": False,
            "w5_authorized": False,
            "g4_passed": False,
            "no_gate_authority": True,
        },
        "resolution_semantics": {
            "derived": "exactly determined model fact or formula; never target-write authority",
            "approval_required": "candidate target mapping exists but needs external hardware approval",
            "rejected": "current evidence is insufficient or incompatible; target instantiation must fail",
        },
        "blockers": BLOCKERS,
        "coverage": {
            "node_count": len(graph.nodes),
            "hw_op_count": len(lowering.hw_ops),
            "internal_tensor_count": len(lowering.internal_tensor_ids),
            "operator_counts": graph.operator_counts,
            "direct_initializer_parameter_binding_count": len(direct_parameters),
            "quantization_parameter_binding_count": sum(
                item["parameter_kind"] in {"scale", "zero_point"}
                for item in direct_parameters
            ),
            "bias_parameter_binding_count": sum(
                item["parameter_kind"] == "bias" for item in direct_parameters
            ),
            "derived_parameter_count": len(derived_parameters),
            "per_channel_direct_parameter_count": sum(
                item["value"]["value_kind"] == "per_channel"
                for item in direct_parameters
            ),
            "field_binding_count": len(fields),
            "field_resolution_counts": resolution_counts,
            "all_nodes_bound": {record["node_id"] for record in records}
            == {node.node_id for node in graph.nodes},
            "all_hw_ops_bound": len(records) == len(lowering.hw_ops),
            "all_formal_target_instances_rejected": all(
                record["formal_target_instance_allowed"] is False
                for record in records
            ),
        },
        "hw_ops": records,
    }
    validate_typed_config_parameter_contract(report)
    return report


def validate_typed_config_parameter_contract(value: dict[str, Any]) -> None:
    """Validate the fail-closed, deterministic invariants of a C7 contract."""

    if value.get("schema_version") != SCHEMA_VERSION:
        raise TypedConfigParameterError("typed parameter contract schema differs")
    if value.get("contract_type") != "typed_config_parameter_contract":
        raise TypedConfigParameterError("typed parameter contract type differs")
    if value.get("status") != "candidate_formula_contract":
        raise TypedConfigParameterError("typed parameter contract status differs")
    source = value.get("source", {})
    if (
        source.get("model_sha256") != MODEL_SHA256
        or source.get("target_config_repository") != OFFICIAL_CONFIG_REPOSITORY
        or source.get("target_config_commit") != OFFICIAL_CONFIG_COMMIT
    ):
        raise TypedConfigParameterError("typed parameter source identity differs")
    scope = value.get("scope", {})
    required_false = (
        "reads_w3_tensor_payloads",
        "patched_json_generated",
        "bitstream_generated",
        "execplan_generated",
        "bank_data_generated",
        "w5_authorized",
        "g4_passed",
    )
    if any(scope.get(field) is not False for field in required_false):
        raise TypedConfigParameterError("typed parameter contract exceeds C7 scope")
    if scope.get("formula_scope_only") is not True or scope.get("no_gate_authority") is not True:
        raise TypedConfigParameterError("typed parameter contract must remain formula-only")
    if value.get("blockers") != BLOCKERS:
        raise TypedConfigParameterError("typed parameter blocker registry differs")

    records = value.get("hw_ops")
    if not isinstance(records, list) or len(records) != 133:
        raise TypedConfigParameterError("typed parameter contract must bind 133 hw_ops")
    hw_ids = [record.get("hw_op_id") for record in records]
    node_ids = {record.get("node_id") for record in records}
    if len(set(hw_ids)) != 133 or len(node_ids) != 78:
        raise TypedConfigParameterError("typed parameter hw_op/node identities differ")
    if Counter(record.get("onnx_op_type") for record in records) != Counter(
        {
            **EXPECTED_NODE_COUNTS,
            "QLinearConv": 106,
            "QLinearGlobalAveragePool": 2,
            "QLinearMatMul": 2,
        }
    ):
        # Counter construction above replaces the three multi-stage values while
        # preserving all single-stage counts.
        raise TypedConfigParameterError("typed parameter lowered operator counts differ")

    parameters = [parameter for record in records for parameter in record.get("parameters", [])]
    parameter_ids = [parameter.get("parameter_id") for parameter in parameters]
    if len(parameter_ids) != len(set(parameter_ids)):
        raise TypedConfigParameterError("typed parameter IDs are not unique")
    direct = [
        parameter
        for parameter in parameters
        if parameter.get("provenance", {}).get("kind") == "onnx_initializer"
    ]
    if len(direct) != 491:
        raise TypedConfigParameterError("typed initializer parameter coverage differs")
    if sum(item.get("parameter_kind") in {"scale", "zero_point"} for item in direct) != 438:
        raise TypedConfigParameterError("typed qparam coverage differs")
    if sum(item.get("parameter_kind") == "bias" for item in direct) != 53:
        raise TypedConfigParameterError("typed bias coverage differs")
    for parameter in parameters:
        if parameter.get("resolution") != "derived":
            raise TypedConfigParameterError("model/formula parameters must be derived")
        if parameter.get("formal_target_write_allowed") is not False:
            raise TypedConfigParameterError("typed parameter authorized a target write")
        typed = parameter.get("value", {})
        if not isinstance(typed.get("element_count"), int) or typed["element_count"] <= 0:
            raise TypedConfigParameterError("typed parameter element count is invalid")
        if not isinstance(typed.get("value_sha256"), str) or len(typed["value_sha256"]) != 64:
            raise TypedConfigParameterError("typed parameter value hash is invalid")
        if typed.get("value_kind") == "per_channel":
            if typed.get("axis") != 0 or typed["element_count"] <= 1:
                raise TypedConfigParameterError("per-channel parameter lost its axis")
        elif typed.get("value_kind") == "scalar":
            if typed["element_count"] != 1 or "scalar" not in typed:
                raise TypedConfigParameterError("scalar parameter representation differs")
        else:
            raise TypedConfigParameterError("typed parameter value kind differs")

    fields = [field for record in records for field in record.get("field_bindings", [])]
    for field in fields:
        resolution = field.get("resolution")
        blockers = field.get("blockers")
        if resolution not in RESOLUTION_STATES:
            raise TypedConfigParameterError("field binding resolution differs")
        if field.get("formal_target_write_allowed") is not False:
            raise TypedConfigParameterError("field binding authorized a target write")
        if resolution == "derived" and blockers:
            raise TypedConfigParameterError("derived field binding has blockers")
        if resolution != "derived" and not blockers:
            raise TypedConfigParameterError("unresolved field binding lacks blockers")
        if any(
            blocker not in BLOCKERS or BLOCKERS[blocker]["state"] != resolution
            for blocker in blockers
        ):
            raise TypedConfigParameterError("field binding blocker state differs")
    if not all(record.get("formal_target_instance_allowed") is False for record in records):
        raise TypedConfigParameterError("C7 authorized a formal target instance")

    coverage = value.get("coverage", {})
    expected_resolution_counts = dict(
        sorted(Counter(field["resolution"] for field in fields).items())
    )
    expected_coverage = {
        "node_count": 78,
        "hw_op_count": 133,
        "internal_tensor_count": 55,
        "operator_counts": EXPECTED_NODE_COUNTS,
        "direct_initializer_parameter_binding_count": 491,
        "quantization_parameter_binding_count": 438,
        "bias_parameter_binding_count": 53,
        "derived_parameter_count": len(parameters) - len(direct),
        "per_channel_direct_parameter_count": sum(
            item["value"]["value_kind"] == "per_channel" for item in direct
        ),
        "field_binding_count": len(fields),
        "field_resolution_counts": expected_resolution_counts,
        "all_nodes_bound": True,
        "all_hw_ops_bound": True,
        "all_formal_target_instances_rejected": True,
    }
    if coverage != expected_coverage:
        raise TypedConfigParameterError("typed parameter coverage summary differs")
